"""Isolated dense vs cross-encoder rerank experiment.

Retrieves top 10 from the Add-on 2 baseline namespace, then reranks to top 5
with a pretrained cross-encoder. Production POST /ask is unchanged.

The reranker is an optional local dependency (sentence-transformers + a
cross-encoder checkpoint). It is not added to production requirements.txt.
The first live run may download model weights.

  python rerank_experiment.py
  python rerank_experiment.py --live   # 5 Pinecone queries + local rerank; wait for approval
"""

from __future__ import annotations

import argparse
import importlib.util
import time
from typing import Any, Protocol

import rag
from chunking_experiment import (
    BASELINE,
    BASELINE_NAMESPACE,
    DIAGNOSTIC_TOP_K,
    EMBEDDING_MODEL,
    EMBEDDING_USD_PER_1K,
    INDEX_NAME,
    METRIC_TOP_K,
    PRODUCTION_NAMESPACE,
    Q5_CASE_ID,
    first_supporting_rank,
    factual_cases,
    live_config,
    score_condition,
)
from rag import RetrievedChunk

RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
Q5_CHUNK_ID = "exampleco-information-security:2"


class PredictsPairs(Protocol):
    def predict(self, pairs: list[tuple[str, str]]) -> Any: ...


def sentence_transformers_available() -> bool:
    return importlib.util.find_spec("sentence_transformers") is not None


def load_reranker(model_name: str = RERANK_MODEL) -> PredictsPairs:
    """Load the cross-encoder once. May download weights on first use."""

    try:
        from sentence_transformers import CrossEncoder
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers is not installed. This experiment is isolated "
            "from production requirements. Install it locally with: "
            "pip install sentence-transformers"
        ) from exc
    return CrossEncoder(model_name)


def rerank_chunks(
    query: str,
    chunks: list[RetrievedChunk],
    reranker: PredictsPairs,
    *,
    top_k: int = METRIC_TOP_K,
) -> tuple[list[RetrievedChunk], float]:
    """Rerank with (query, chunk text) pairs only. Does not use labels or gold evidence."""

    if not chunks:
        return [], 0.0
    pairs = [(query, chunk.text) for chunk in chunks]
    started = time.perf_counter()
    raw_scores = reranker.predict(pairs)
    latency_ms = (time.perf_counter() - started) * 1000
    scored = []
    for chunk, score in zip(chunks, raw_scores, strict=True):
        scored.append(
            RetrievedChunk(
                id=chunk.id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                source=chunk.source,
                score=float(score),
                text=chunk.text,
            )
        )
    ranked = sorted(scored, key=lambda chunk: (-chunk.score, chunk.id))
    return ranked[:top_k], latency_ms


def dense_candidates(
    cases: list[dict],
    *,
    top_k: int = DIAGNOSTIC_TOP_K,
) -> dict[str, list[RetrievedChunk]]:
    config = live_config(BASELINE)
    if config.namespace != BASELINE_NAMESPACE:
        raise RuntimeError("Rerank experiment must read maven-session2-chunk800-test.")
    retrieved: dict[str, list[RetrievedChunk]] = {}
    for case in cases:
        retrieved[case["id"]] = rag.retrieve_chunks(
            query=case["question"],
            top_k=top_k,
            config=config,
        )
    return retrieved


def chunk_id_rank(chunks: list[RetrievedChunk], chunk_id: str) -> int | None:
    for rank, chunk in enumerate(chunks, start=1):
        if chunk.id == chunk_id:
            return rank
    return None


def evaluate_rerank(
    cases: list[dict],
    *,
    candidates_by_case: dict[str, list[RetrievedChunk]],
    reranker: PredictsPairs,
    metric_k: int = METRIC_TOP_K,
) -> dict:
    dense_top = {
        case["id"]: candidates_by_case[case["id"]][:metric_k] for case in cases
    }
    reranked: dict[str, list[RetrievedChunk]] = {}
    latencies: dict[str, float] = {}
    candidate_misses: dict[str, bool] = {}
    q5_candidate_rank: int | None = None

    for case in cases:
        candidates = candidates_by_case[case["id"]]
        evidence = case.get("evidence_phrases") or []
        in_candidates = first_supporting_rank(candidates, evidence) is not None
        candidate_misses[case["id"]] = not in_candidates
        reranked[case["id"]], latencies[case["id"]] = rerank_chunks(
            case["question"],
            candidates,
            reranker,
            top_k=metric_k,
        )
        if case["id"] == Q5_CASE_ID:
            q5_candidate_rank = chunk_id_rank(candidates, Q5_CHUNK_ID)

    dense_scores = score_condition(cases, dense_top)
    rerank_scores = score_condition(cases, reranked)
    dense_scores["q5_chunk_id_rank"] = chunk_id_rank(
        candidates_by_case[Q5_CASE_ID], Q5_CHUNK_ID
    )
    rerank_scores["q5_chunk_id_rank"] = chunk_id_rank(reranked[Q5_CASE_ID], Q5_CHUNK_ID)
    return {
        "dense": dense_scores,
        "rerank": rerank_scores,
        "latencies_ms": latencies,
        "candidate_misses": candidate_misses,
        "q5_candidate_rank": q5_candidate_rank,
    }


def render_markdown(results: dict, cases: list[dict]) -> str:
    def rank_cell(value: int | None) -> str:
        return "not in window" if value is None else str(value)

    dense = results["dense"]
    rerank = results["rerank"]
    lines = [
        "# Cross-encoder rerank experiment",
        "",
        f"Dense candidates: top {DIAGNOSTIC_TOP_K} from `{BASELINE_NAMESPACE}`. "
        f"Reranker: `{RERANK_MODEL}` keeping top {METRIC_TOP_K}. "
        "Production `/ask` is unchanged.",
        "",
        "| Retriever | Recall@5 | Hit@1 | MRR | Q5 evidence rank | Q5 chunk ID rank |",
        "| --- | --- | --- | --- | --- | --- |",
        f"| Dense top-5 | {dense['recall_at_5']:.0%} | {dense['hit_at_1']:.0%} | "
        f"{dense['mrr']:.2f} | {rank_cell(dense['q5_supporting_rank'])} | "
        f"{rank_cell(dense.get('q5_chunk_id_rank'))} |",
        f"| Dense top-10 + rerank top-5 | {rerank['recall_at_5']:.0%} | {rerank['hit_at_1']:.0%} | "
        f"{rerank['mrr']:.2f} | {rank_cell(rerank['q5_supporting_rank'])} | "
        f"{rank_cell(rerank.get('q5_chunk_id_rank'))} |",
        "",
        f"Q5 `{Q5_CHUNK_ID}` rank in dense top 10 (before rerank): "
        f"{rank_cell(results.get('q5_candidate_rank'))}.",
        "",
        "| Question | Dense@5 rank | Rerank@5 rank | In dense top-10? | Rerank latency ms |",
        "| --- | --- | --- | --- | --- |",
    ]
    for index, case in enumerate(cases):
        miss = results["candidate_misses"].get(case["id"], False)
        latency = results["latencies_ms"].get(case["id"], 0.0)
        note = "candidate-retrieval miss" if miss else "yes"
        lines.append(
            f"| `{case['id']}` | {rank_cell(dense['ranks'][index])} | "
            f"{rank_cell(rerank['ranks'][index])} | {note} | {latency:.1f} |"
        )
    lines.extend(
        [
            "",
            "Supporting evidence is scored from chunk text, not document IDs. "
            "If the supporting chunk is missing from the dense top 10, that is a "
            "candidate-retrieval miss, not a reranker failure. "
            "Five questions are not enough to claim statistical significance.",
        ]
    )
    return "\n".join(lines) + "\n"


def plan_text(cases: list[dict]) -> str:
    query_calls = len(cases)
    query_tokens = 80 * query_calls / 4
    usd = query_tokens / 1000 * EMBEDDING_USD_PER_1K
    st_ok = sentence_transformers_available()
    return "\n".join(
        [
            "Rerank experiment dry run (no OpenAI, Pinecone, or model download).",
            "",
            f"Dense namespace (read-only): {BASELINE_NAMESPACE}",
            f"Production namespace (untouched): {PRODUCTION_NAMESPACE}",
            f"Index: {INDEX_NAME}. Embedding: {EMBEDDING_MODEL}.",
            f"Rerank model: {RERANK_MODEL}",
            f"sentence-transformers installed: {st_ok}",
            "First live run may download cross-encoder weights (not done in dry-run).",
            f"Queries: {len(cases)}. Retrieve top {DIAGNOSTIC_TOP_K}, keep reranked top {METRIC_TOP_K}.",
            "",
            "Live API estimate (no ingest, no chat generation):",
            f"- OpenAI query embeddings: {query_calls}",
            "- Pinecone queries: 5 (dense top 10 only)",
            "- Document embeddings: 0",
            "- Pinecone upserts: 0",
            "- Cross-encoder: local, one model load for all questions",
            f"- Estimated embedding tokens: ~{int(query_tokens)}",
            f"- Estimated OpenAI cost: ~${usd:.6f}",
            "- Reranker cost: local CPU/GPU time; no OpenAI chat tokens",
        ]
    )


def run_live(cases: list[dict]) -> dict:
    reranker = load_reranker()
    candidates = dense_candidates(cases)
    return evaluate_rerank(cases, candidates_by_case=candidates, reranker=reranker)


def main() -> int:
    parser = argparse.ArgumentParser(description="Dense vs cross-encoder rerank experiment.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Query Pinecone and load the local reranker. Do not use until authorized.",
    )
    args = parser.parse_args()
    cases = factual_cases()
    if not args.live:
        print(plan_text(cases))
        print("\nPass --live only after authorization. Default mode makes no API or model-download calls.")
        return 0
    if live_config(BASELINE).namespace == PRODUCTION_NAMESPACE:
        raise RuntimeError("Refusing to query the production namespace.")
    results = run_live(cases)
    print(render_markdown(results, cases))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
