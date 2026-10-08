"""Isolated hybrid retrieval experiment: dense + BM25 + RRF.

Uses the same five ExampleCo documents and 800/100 chunks as the Add-on 2
baseline. Dense retrieval reads the isolated namespace
`maven-session2-chunk800-test`. BM25 is local. Production `/ask` is unchanged.

  python hybrid_experiment.py
  python hybrid_experiment.py --live   # 5 query embeddings only; wait for approval
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from typing import Any

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
    dummy_config,
    factual_cases,
    live_config,
    load_corpus,
    score_condition,
)
from rag import RetrievedChunk

RRF_K = 60
TOKEN_RE = re.compile(r"[a-z]+|\d+(?:\.\d+)?")


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens; keep decimal numbers such as 400.01."""

    cleaned = str(text or "").lower().replace("£", " ")
    return TOKEN_RE.findall(cleaned)


def reciprocal_rank_fusion(
    ranked_id_lists: list[list[str]],
    *,
    k: int = RRF_K,
) -> list[tuple[str, float]]:
    """Combine ranked ID lists. Missing IDs contribute 0. Ties break on ID."""

    if k <= 0:
        raise ValueError("RRF k must be positive.")
    scores: dict[str, float] = {}
    for ranked_ids in ranked_id_lists:
        seen: set[str] = set()
        for rank, chunk_id in enumerate(ranked_ids, start=1):
            if not chunk_id or chunk_id in seen:
                continue
            seen.add(chunk_id)
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def build_local_chunks(documents: list[dict] | None = None) -> list[RetrievedChunk]:
    documents = documents if documents is not None else load_corpus()
    config = dummy_config(BASELINE)
    chunks: list[RetrievedChunk] = []
    for document in documents:
        parts = rag.chunk_document(document["text"], config)
        for chunk_index, text in enumerate(parts):
            chunks.append(
                RetrievedChunk(
                    id=rag.stable_chunk_id(document["document_id"], chunk_index),
                    document_id=document["document_id"],
                    chunk_index=chunk_index,
                    source=document["source"],
                    score=0.0,
                    text=text,
                )
            )
    return chunks


@dataclass
class BM25Index:
    chunks: list[RetrievedChunk]
    bm25: Any

    @classmethod
    def from_chunks(cls, chunks: list[RetrievedChunk]) -> "BM25Index":
        if not chunks:
            raise ValueError("Cannot build a BM25 index from an empty chunk list.")
        try:
            from rank_bm25 import BM25Okapi
        except ImportError as exc:
            raise RuntimeError(
                "rank-bm25 is an optional experiment dependency. "
                "Install it locally with: pip install rank-bm25"
            ) from exc
        tokenized = [tokenize(chunk.text) for chunk in chunks]
        return cls(chunks=chunks, bm25=BM25Okapi(tokenized))

    def search(self, query: str, *, top_k: int = DIAGNOSTIC_TOP_K) -> list[RetrievedChunk]:
        tokens = tokenize(query)
        if not tokens:
            return []
        scores = self.bm25.get_scores(tokens)
        ranked = sorted(
            zip(self.chunks, scores, strict=True),
            key=lambda item: (-float(item[1]), item[0].id),
        )
        results: list[RetrievedChunk] = []
        for chunk, score in ranked[:top_k]:
            results.append(
                RetrievedChunk(
                    id=chunk.id,
                    document_id=chunk.document_id,
                    chunk_index=chunk.chunk_index,
                    source=chunk.source,
                    score=float(score),
                    text=chunk.text,
                )
            )
        return results


def fuse_rankings(
    dense: list[RetrievedChunk],
    sparse: list[RetrievedChunk],
    *,
    k: int = RRF_K,
) -> list[RetrievedChunk]:
    catalog = {chunk.id: chunk for chunk in sparse}
    catalog.update({chunk.id: chunk for chunk in dense})
    fused = reciprocal_rank_fusion(
        [[chunk.id for chunk in dense], [chunk.id for chunk in sparse]],
        k=k,
    )
    return [catalog[chunk_id] for chunk_id, _score in fused if chunk_id in catalog]


def dense_retrieve(
    cases: list[dict],
    *,
    top_k: int = DIAGNOSTIC_TOP_K,
) -> dict[str, list[RetrievedChunk]]:
    config = live_config(BASELINE)
    if config.namespace != BASELINE_NAMESPACE:
        raise RuntimeError("Hybrid dense retrieval must use the 800/100 experiment namespace.")
    retrieved: dict[str, list[RetrievedChunk]] = {}
    for case in cases:
        retrieved[case["id"]] = rag.retrieve_chunks(
            query=case["question"],
            top_k=top_k,
            config=config,
        )
    return retrieved


def evaluate_retrievers(
    cases: list[dict],
    *,
    dense_by_case: dict[str, list[RetrievedChunk]],
    bm25_index: BM25Index,
    top_k: int = DIAGNOSTIC_TOP_K,
    rrf_k: int = RRF_K,
) -> dict[str, dict]:
    bm25_by_case = {
        case["id"]: bm25_index.search(case["question"], top_k=top_k) for case in cases
    }
    hybrid_by_case = {
        case["id"]: fuse_rankings(
            dense_by_case[case["id"]],
            bm25_by_case[case["id"]],
            k=rrf_k,
        )
        for case in cases
    }
    return {
        "dense": score_condition(cases, dense_by_case),
        "bm25": score_condition(cases, bm25_by_case),
        "hybrid": score_condition(cases, hybrid_by_case),
    }


def render_markdown(scores: dict[str, dict], cases: list[dict]) -> str:
    def rank_cell(value: int | None) -> str:
        return "not in top 10" if value is None else str(value)

    lines = [
        "# Hybrid retrieval experiment",
        "",
        "Dense retrieval uses isolated namespace `maven-session2-chunk800-test`. "
        "BM25 uses the same local 800/100 ExampleCo chunks. Production `/ask` is unchanged.",
        "",
        "| Retriever | Recall@5 | Hit@1 | MRR | Q5 supporting rank |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name in ("dense", "bm25", "hybrid"):
        result = scores[name]
        lines.append(
            f"| {name} | {result['recall_at_5']:.0%} | {result['hit_at_1']:.0%} | "
            f"{result['mrr']:.2f} | {rank_cell(result['q5_supporting_rank'])} |"
        )
    lines.extend(
        [
            "",
            "| Question | Dense rank | BM25 rank | Hybrid rank |",
            "| --- | --- | --- | --- |",
        ]
    )
    for index, case in enumerate(cases):
        lines.append(
            f"| `{case['id']}` | {rank_cell(scores['dense']['ranks'][index])} | "
            f"{rank_cell(scores['bm25']['ranks'][index])} | "
            f"{rank_cell(scores['hybrid']['ranks'][index])} |"
        )
    lines.extend(
        [
            "",
            "Supporting chunks are identified by evidence phrases in chunk text, "
            "not by document ID alone. Five questions are not enough to claim "
            "statistical significance.",
        ]
    )
    return "\n".join(lines) + "\n"


def plan_text(documents: list[dict], cases: list[dict], chunks: list[RetrievedChunk]) -> str:
    query_calls = len(cases)
    query_tokens = 80 * query_calls / 4
    usd = query_tokens / 1000 * EMBEDDING_USD_PER_1K
    return "\n".join(
        [
            "Hybrid retrieval dry run (no OpenAI or Pinecone calls).",
            "",
            f"Dense namespace (read-only): {BASELINE_NAMESPACE}",
            f"Production namespace (untouched): {PRODUCTION_NAMESPACE}",
            f"Index: {INDEX_NAME}. Embedding: {EMBEDDING_MODEL}. RRF k={RRF_K}.",
            f"Local 800/100 chunks: {len(chunks)}. Documents: "
            + ", ".join(item["document_id"] for item in documents),
            f"Queries: {len(cases)} factual questions. Diagnostic top_k={DIAGNOSTIC_TOP_K}.",
            "",
            "Live API estimate (no ingest, no chat generation):",
            f"- OpenAI query embeddings: {query_calls}",
            "- Document embeddings: 0 (reuse Add-on 2 baseline vectors)",
            "- Pinecone queries: 5 (dense only)",
            "- Pinecone upserts: 0",
            "- BM25/RRF: local",
            f"- Estimated embedding tokens: ~{int(query_tokens)}",
            f"- Estimated OpenAI cost: ~${usd:.6f}",
        ]
    )


def run_live(cases: list[dict], bm25_index: BM25Index) -> dict[str, dict]:
    dense_by_case = dense_retrieve(cases)
    return evaluate_retrievers(cases, dense_by_case=dense_by_case, bm25_index=bm25_index)


def main() -> int:
    parser = argparse.ArgumentParser(description="Dense vs BM25 vs hybrid RRF experiment.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Query Pinecone for dense results. Do not use until authorized.",
    )
    args = parser.parse_args()
    documents = load_corpus()
    cases = factual_cases()
    chunks = build_local_chunks(documents)
    bm25_index = BM25Index.from_chunks(chunks)

    if not args.live:
        print(plan_text(documents, cases, chunks))
        print("\nPass --live only after authorization. Default mode makes no API calls.")
        return 0

    if live_config(BASELINE).namespace == PRODUCTION_NAMESPACE:
        raise RuntimeError("Refusing to query the production namespace.")
    scores = run_live(cases, bm25_index)
    print(render_markdown(scores, cases))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
