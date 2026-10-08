"""Controlled A/B chunking experiment for Session 2 retrieval.

Compares 800/100 vs 600/100 on the same five ExampleCo documents in isolated
Pinecone namespaces. Does not write to the production `maven-session2` namespace
and does not call POST /ask or change default application chunking.

Default mode is a dry run (local chunk counts only):

  python chunking_experiment.py
  python chunking_experiment.py --live   # real embeddings + Pinecone; wait for approval
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

import rag
from eval_rag import all_phrases_present, load_spec

THIS_DIR = Path(__file__).resolve().parent
SAMPLE_DOCS = THIS_DIR / "sample_docs"
CASES_PATH = THIS_DIR / "eval_cases.json"

PRODUCTION_NAMESPACE = "maven-session2"
BASELINE_NAMESPACE = "maven-session2-chunk800-test"
CANDIDATE_NAMESPACE = "maven-session2-chunk600-test"
EMBEDDING_MODEL = "text-embedding-3-small"
INDEX_NAME = "maven-rag"
METRIC_TOP_K = 5
DIAGNOSTIC_TOP_K = 10
OVERLAP = 100
EMBEDDING_USD_PER_1K = 0.00002
CHARS_PER_TOKEN = 4

FORBIDDEN_DOCUMENT_IDS = frozenset(
    {"northwind-handbook", "exampleco-ui-smoke-test"}
)
CORPUS = (
    ("exampleco-remote-work", "remote_work.txt"),
    ("exampleco-annual-leave", "annual_leave.txt"),
    ("exampleco-expenses", "expenses.txt"),
    ("exampleco-it-equipment", "it_equipment.txt"),
    ("exampleco-information-security", "information_security.txt"),
)
Q5_CASE_ID = "q5_unused_access"


@dataclass(frozen=True)
class Condition:
    name: str
    namespace: str
    chunk_size: int
    chunk_overlap: int = OVERLAP


BASELINE = Condition("baseline_800", BASELINE_NAMESPACE, 800)
CANDIDATE = Condition("candidate_600", CANDIDATE_NAMESPACE, 600)


def load_corpus() -> list[dict]:
    documents = []
    for document_id, filename in CORPUS:
        if document_id in FORBIDDEN_DOCUMENT_IDS:
            raise RuntimeError(f"Forbidden document included: {document_id}")
        text = (SAMPLE_DOCS / filename).read_text(encoding="utf-8")
        documents.append(
            {
                "document_id": document_id,
                "filename": filename,
                "source": "exampleco-synthetic-policies",
                "text": text,
            }
        )
    ids = {item["document_id"] for item in documents}
    if ids & FORBIDDEN_DOCUMENT_IDS:
        raise RuntimeError("Corpus includes Northwind or the UI smoke-test document.")
    if len(documents) != 5:
        raise RuntimeError("Experiment corpus must be the five ExampleCo policies.")
    return documents


def factual_cases(spec: dict | None = None) -> list[dict]:
    spec = spec or load_spec(CASES_PATH)
    cases = [case for case in spec["cases"] if case["type"] == "factual"]
    if len(cases) != 5:
        raise RuntimeError("Expected five factual evaluation questions.")
    return cases


def dummy_config(condition: Condition) -> rag.PineconeConfig:
    return rag.PineconeConfig(
        api_key="unset",
        index_name=INDEX_NAME,
        namespace=condition.namespace,
        embedding_model=EMBEDDING_MODEL,
        chunk_size=condition.chunk_size,
        chunk_overlap=condition.chunk_overlap,
    )


def live_config(condition: Condition) -> rag.PineconeConfig:
    ensure_experimental_namespace(condition.namespace)
    env = rag.PineconeConfig.from_env()
    config = replace(
        env,
        namespace=condition.namespace,
        chunk_size=condition.chunk_size,
        chunk_overlap=condition.chunk_overlap,
        embedding_model=EMBEDDING_MODEL,
        index_name=INDEX_NAME,
    )
    ensure_experimental_namespace(config.namespace)
    return config


def ensure_experimental_namespace(namespace: str) -> None:
    allowed = {BASELINE_NAMESPACE, CANDIDATE_NAMESPACE}
    if namespace == PRODUCTION_NAMESPACE or namespace not in allowed:
        raise RuntimeError(
            f"Refusing namespace '{namespace}'. Production {PRODUCTION_NAMESPACE} "
            "must stay unchanged."
        )


def local_chunk_preview(documents: list[dict], condition: Condition) -> dict:
    config = dummy_config(condition)
    per_doc = []
    total = 0
    for document in documents:
        chunks = rag.chunk_document(document["text"], config)
        lengths = [len(chunk) for chunk in chunks]
        total += len(chunks)
        per_doc.append(
            {
                "document_id": document["document_id"],
                "chunk_count": len(chunks),
                "lengths": lengths,
            }
        )
    return {"condition": condition.name, "chunk_count": total, "documents": per_doc}


def first_supporting_rank(chunks: list, evidence_phrases: list[str]) -> int | None:
    for rank, chunk in enumerate(chunks, start=1):
        text = chunk.text if hasattr(chunk, "text") else str(chunk.get("text", ""))
        if evidence_phrases and all_phrases_present(text, evidence_phrases):
            return rank
    return None


def score_condition(
    cases: list[dict],
    retrieved_by_case: dict[str, list],
    *,
    metric_k: int = METRIC_TOP_K,
) -> dict:
    ranks: list[int | None] = []
    for case in cases:
        chunks = retrieved_by_case[case["id"]]
        ranks.append(first_supporting_rank(chunks, case.get("evidence_phrases") or []))

    recall = sum(rank is not None and rank <= metric_k for rank in ranks) / len(ranks)
    hit1 = sum(rank == 1 for rank in ranks) / len(ranks)
    mrr = sum(
        (1 / rank) if rank is not None and rank <= metric_k else 0.0 for rank in ranks
    ) / len(ranks)
    q5_index = next(i for i, case in enumerate(cases) if case["id"] == Q5_CASE_ID)
    return {
        "recall_at_5": recall,
        "hit_at_1": hit1,
        "mrr": mrr,
        "ranks": ranks,
        "q5_supporting_rank": ranks[q5_index],
    }


def estimate_cost(documents: list[dict], n_queries: int) -> dict:
    ingest_calls = len(documents) * 2
    query_calls = n_queries * 2
    baseline_chunks = local_chunk_preview(documents, BASELINE)["chunk_count"]
    candidate_chunks = local_chunk_preview(documents, CANDIDATE)["chunk_count"]
    ingest_chars = sum(len(document["text"]) for document in documents) * 2
    query_chars = 80 * query_calls
    embedding_tokens = (ingest_chars + query_chars) / CHARS_PER_TOKEN
    usd = embedding_tokens / 1000 * EMBEDDING_USD_PER_1K
    return {
        "openai_embedding_calls": ingest_calls + query_calls,
        "ingest_embedding_calls": ingest_calls,
        "query_embedding_calls": query_calls,
        "pinecone_upserts": ingest_calls,
        "pinecone_queries": query_calls,
        "generation_calls": 0,
        "baseline_chunks": baseline_chunks,
        "candidate_chunks": candidate_chunks,
        "estimated_embedding_tokens": int(embedding_tokens),
        "estimated_usd": round(usd, 6),
    }


def ingest_condition(
    condition: Condition,
    documents: list[dict],
    config: rag.PineconeConfig,
) -> list[dict]:
    ensure_experimental_namespace(config.namespace)
    results = []
    for document in documents:
        if document["document_id"] in FORBIDDEN_DOCUMENT_IDS:
            raise RuntimeError("Refusing to ingest a forbidden document.")
        chunks_indexed = rag.ingest_document(
            text=document["text"],
            document_id=document["document_id"],
            source=document["source"],
            config=config,
        )
        results.append(
            {
                "document_id": document["document_id"],
                "chunks_indexed": chunks_indexed,
                "namespace": config.namespace,
                "chunk_size": config.chunk_size,
            }
        )
    return results


def retrieve_condition(
    condition: Condition,
    cases: list[dict],
    config: rag.PineconeConfig,
    *,
    top_k: int = DIAGNOSTIC_TOP_K,
) -> dict[str, list]:
    ensure_experimental_namespace(config.namespace)
    retrieved: dict[str, list] = {}
    for case in cases:
        retrieved[case["id"]] = rag.retrieve_chunks(
            query=case["question"],
            top_k=top_k,
            config=config,
        )
    return retrieved


def namespace_vector_counts() -> dict[str, int]:
    """Read-only index stats. Does not query, upsert, or generate."""

    env = rag.PineconeConfig.from_env()
    index = rag.connect_to_index(env)
    stats = index.describe_index_stats()
    namespaces = rag._value(stats, "namespaces", {}) or {}
    counts: dict[str, int] = {}
    for name in (PRODUCTION_NAMESPACE, BASELINE_NAMESPACE, CANDIDATE_NAMESPACE):
        namespace_stats = (
            namespaces.get(name, {}) if isinstance(namespaces, Mapping) else {}
        )
        counts[name] = int(rag._value(namespace_stats, "vector_count", 0) or 0)
    return counts


def preflight_or_stop() -> dict[str, int]:
    counts = namespace_vector_counts()
    for name in (BASELINE_NAMESPACE, CANDIDATE_NAMESPACE):
        if counts[name]:
            raise RuntimeError(
                f"Unexpected vectors in experimental namespace '{name}': "
                f"{counts[name]}. Stopping without ingest or retrieve."
            )
    return counts


def disable_provider_retries() -> None:
    client = rag.get_openai_client()
    if hasattr(client, "max_retries"):
        client.max_retries = 0


def run_live(documents: list[dict], cases: list[dict]) -> dict:
    scored = {}
    for condition in (BASELINE, CANDIDATE):
        config = live_config(condition)
        ingested = ingest_condition(condition, documents, config)
        retrieved = retrieve_condition(condition, cases, config)
        result = score_condition(cases, retrieved)
        result["total_chunks"] = sum(item["chunks_indexed"] for item in ingested)
        scored[condition.name] = result
    return scored


def render_markdown(scores: dict) -> str:
    baseline = scores[BASELINE.name]
    candidate = scores[CANDIDATE.name]

    def rank_cell(value: int | None) -> str:
        return "not in top 10" if value is None else str(value)

    lines = [
        "# Chunking A/B experiment",
        "",
        "Isolated namespaces only. Production `maven-session2` was not modified.",
        "Corpus: five ExampleCo policies. Excluded: `northwind-handbook`, "
        "`exampleco-ui-smoke-test`.",
        "",
        "| Condition | Namespace | Chunking | Recall@5 | Hit@1 | MRR | Q5 supporting rank |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        f"| Baseline | `{BASELINE_NAMESPACE}` | 800/100 | "
        f"{baseline['recall_at_5']:.0%} | {baseline['hit_at_1']:.0%} | "
        f"{baseline['mrr']:.2f} | {rank_cell(baseline['q5_supporting_rank'])} |",
        f"| Candidate | `{CANDIDATE_NAMESPACE}` | 600/100 | "
        f"{candidate['recall_at_5']:.0%} | {candidate['hit_at_1']:.0%} | "
        f"{candidate['mrr']:.2f} | {rank_cell(candidate['q5_supporting_rank'])} |",
        "",
        f"Total chunks indexed: baseline {baseline.get('total_chunks', '-')} "
        f"(800/100), candidate {candidate.get('total_chunks', '-')} (600/100).",
        "",
        "| Question | Baseline supporting rank | Candidate supporting rank |",
        "| --- | --- | --- |",
    ]
    cases = factual_cases()
    for index, case in enumerate(cases):
        lines.append(
            f"| `{case['id']}` | {rank_cell(baseline['ranks'][index])} | "
            f"{rank_cell(candidate['ranks'][index])} |"
        )
    lines.extend(
        [
            "",
            "Recall@5, Hit@1, and MRR use the first supporting chunk in the top 5. "
            "Per-question ranks and Q5 use a top_k=10 list from the same query embedding.",
            "Five questions are not enough to claim statistical significance.",
        ]
    )
    return "\n".join(lines) + "\n"


def plan_text(documents: list[dict], cases: list[dict]) -> str:
    cost = estimate_cost(documents, len(cases))
    baseline_preview = local_chunk_preview(documents, BASELINE)
    candidate_preview = local_chunk_preview(documents, CANDIDATE)
    security_800 = next(
        item
        for item in baseline_preview["documents"]
        if item["document_id"] == "exampleco-information-security"
    )
    security_600 = next(
        item
        for item in candidate_preview["documents"]
        if item["document_id"] == "exampleco-information-security"
    )
    return "\n".join(
        [
            "Chunking A/B dry run (no OpenAI or Pinecone calls).",
            "",
            f"Production namespace (unchanged): {PRODUCTION_NAMESPACE}",
            f"Baseline namespace: {BASELINE_NAMESPACE} (800/{OVERLAP})",
            f"Candidate namespace: {CANDIDATE_NAMESPACE} (600/{OVERLAP})",
            "Index: maven-rag. Embedding: text-embedding-3-small. Metric: cosine.",
            f"Queries: {len(cases)} factual ExampleCo questions. top_k={METRIC_TOP_K} "
            f"(diagnostic window {DIAGNOSTIC_TOP_K}).",
            "Excluded from both conditions: northwind-handbook, exampleco-ui-smoke-test.",
            "",
            f"Local chunk counts: baseline {cost['baseline_chunks']}, "
            f"candidate {cost['candidate_chunks']}.",
            f"Security policy lengths 800/100: {security_800['lengths']}",
            f"Security policy lengths 600/100: {security_600['lengths']}",
            "",
            "Live API estimate (embeddings only, no /ask generation):",
            f"- OpenAI embedding calls: {cost['openai_embedding_calls']} "
            f"({cost['ingest_embedding_calls']} ingest + {cost['query_embedding_calls']} query)",
            f"- Pinecone upserts: {cost['pinecone_upserts']}",
            f"- Pinecone queries: {cost['pinecone_queries']}",
            f"- Chat/generation calls: {cost['generation_calls']}",
            f"- Estimated embedding tokens: ~{cost['estimated_embedding_tokens']}",
            f"- Estimated OpenAI cost: ~${cost['estimated_usd']:.6f} "
            "(text-embedding-3-small $0.00002/1K; char/4 heuristic)",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="A/B chunking retrieval experiment.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Ingest and retrieve in isolated namespaces. Do not use until authorized.",
    )
    args = parser.parse_args()
    documents = load_corpus()
    cases = factual_cases()

    if not args.live:
        print(plan_text(documents, cases))
        print("\nPass --live only after authorization. Default mode makes no API calls.")
        return 0

    ids_a = [item["document_id"] for item in documents]
    ids_b = [item["document_id"] for item in documents]
    if ids_a != ids_b:
        raise RuntimeError("Document IDs do not match across conditions.")
    print("Corpus document IDs:", ", ".join(ids_a))
    print("Embedding model:", EMBEDDING_MODEL)
    print("Index:", INDEX_NAME)
    counts = preflight_or_stop()
    print(
        "Preflight namespace vector counts "
        f"(production={counts[PRODUCTION_NAMESPACE]}, "
        f"baseline={counts[BASELINE_NAMESPACE]}, "
        f"candidate={counts[CANDIDATE_NAMESPACE]})."
    )
    disable_provider_retries()
    scores = run_live(documents, cases)
    print(render_markdown(scores))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
