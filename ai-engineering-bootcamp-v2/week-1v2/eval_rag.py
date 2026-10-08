"""Golden-set evaluation for the Session 2 FastAPI RAG service.

Scores existing POST /ask and GET /debug/retrieve responses. Does not implement
a second retrieval or generation pipeline.

Default (no --live) prints methodology and does not call the API.

  python eval_rag.py
  python eval_rag.py --live   # real API calls; do not run until authorized
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

import httpx
from dotenv import load_dotenv

THIS_DIR = Path(__file__).resolve().parent
CASES_PATH = THIS_DIR / "eval_cases.json"
REFUSAL_ANSWER = "I don't have enough information to answer that."
DEFAULT_API_BASE_URL = "https://ai-internship-5ei0.onrender.com"
ASK_TIMEOUT_SECONDS = 120.0
RETRIEVE_TIMEOUT_SECONDS = 120.0

load_dotenv(THIS_DIR / ".env")
load_dotenv(THIS_DIR.parent / ".env")


def load_spec(path: Path = CASES_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fold(text: str) -> str:
    """Lowercase, strip currency symbols, keep letters/digits for phrase checks."""
    cleaned = str(text or "").lower().replace("£", "").replace(",", "")
    cleaned = re.sub(r"[^a-z0-9.\s-]", " ", cleaned)
    return " ".join(cleaned.split())


def contains_phrase(haystack: str, phrase: str) -> bool:
    needle = fold(phrase)
    if re.fullmatch(r"\d+(?:\.\d+)?", needle):
        return needle in _numeric_tokens(haystack)
    return needle in fold(haystack)


def all_phrases_present(haystack: str, phrases: list[str]) -> bool:
    return all(contains_phrase(haystack, phrase) for phrase in phrases)


def document_id_from_chunk(chunk_id: str) -> str:
    return str(chunk_id).rsplit(":", 1)[0]


def parse_ask_response(payload: dict | str) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Ask response is not JSON.")
    answer = payload.get("answer")
    if isinstance(answer, dict):
        text = str(answer.get("answer") or "")
        citations = [str(item) for item in (answer.get("citations") or [])]
    else:
        text = str(answer or "")
        citations = []
    return {
        "answer": text,
        "citations": citations,
        "retrieved_chunk_ids": [str(item) for item in (payload.get("retrieved_chunk_ids") or [])],
        "model": payload.get("model"),
        "tokens_used": payload.get("tokens_used"),
        "cost_usd": payload.get("cost_usd"),
        "latency_ms": payload.get("latency_ms"),
    }


def parse_retrieve_response(payload: dict | str) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Retrieve response is not JSON.")
    matches = payload.get("matches") or []
    texts = [str(match.get("text") or "") for match in matches]
    ids = [str(match.get("id") or "") for match in matches]
    return {"match_ids": ids, "match_texts": texts, "context": "\n".join(texts)}


def score_retrieval_hit(case: dict, retrieve: dict) -> dict:
    if case["type"] == "refusal":
        return {
            "score": None,
            "method": "n/a",
            "note": "No supporting document exists; retrieval hit is not scored.",
        }
    context = retrieve.get("context") or ""
    phrases = case.get("evidence_phrases") or []
    hit = bool(phrases) and all_phrases_present(context, phrases)
    return {
        "score": hit,
        "method": "deterministic_phrase_in_retrieved_text",
        "note": (
            "Pass if every evidence phrase appears in GET /debug/retrieve match text."
        ),
    }


def score_correctness(case: dict, ask: dict) -> dict:
    answer = ask["answer"].strip()
    if case["type"] == "refusal":
        ok = answer == REFUSAL_ANSWER
        return {
            "score": ok,
            "method": "exact_refusal_string",
            "note": "Pass only on the exact insufficient-information refusal.",
        }
    phrases = case.get("answer_phrases") or []
    ok = bool(phrases) and all_phrases_present(answer, phrases)
    return {
        "score": ok,
        "method": "deterministic_required_phrases",
        "note": (
            "Heuristic/deterministic: pass if the generated answer contains the "
            "required phrases from sample_docs/README.md. Wording may still vary."
        ),
    }


def _numeric_tokens(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:\.\d+)?", fold(text)))


def score_faithfulness(case: dict, ask: dict, retrieve: dict) -> dict:
    answer = ask["answer"].strip()
    context = retrieve.get("context") or ""
    if case["type"] == "refusal":
        ok = answer == REFUSAL_ANSWER
        return {
            "score": ok,
            "method": "exact_refusal_implies_no_invented_facts",
            "note": "An exact refusal is treated as faithful. Any other answer is not.",
        }
    extra_numbers = _numeric_tokens(answer) - _numeric_tokens(context)
    phrases_ok = all_phrases_present(context, [p for p in (case.get("answer_phrases") or []) if contains_phrase(answer, p)])
    ok = phrases_ok and not extra_numbers
    return {
        "score": ok,
        "method": "heuristic_numbers_and_required_phrases_in_context",
        "note": (
            "Heuristic, not a definitive NLI score. Fails if required answer phrases "
            "are missing from retrieved text, or if the answer introduces numbers "
            "absent from retrieved text."
        ),
    }


def score_citation_validity(case: dict, ask: dict) -> dict:
    citations = ask["citations"]
    retrieved = set(ask["retrieved_chunk_ids"])
    if case["type"] == "refusal":
        ok = citations == []
        return {
            "score": ok,
            "method": "refusal_must_have_empty_citations",
            "note": "Refusals must not cite chunks.",
        }
    unknown = [item for item in citations if item not in retrieved]
    expected = case.get("expected_document_id")
    expected_ok = any(document_id_from_chunk(item) == expected for item in citations)
    forbidden = set(case.get("forbidden_document_ids") or [])
    forbidden_hit = any(document_id_from_chunk(item) in forbidden for item in citations)
    ok = bool(citations) and not unknown and expected_ok and not forbidden_hit
    return {
        "score": ok,
        "method": "deterministic_citation_membership",
        "note": (
            "Pass if citations are a non-empty subset of /ask retrieved_chunk_ids, "
            "at least one is from the expected document, and none are from forbidden documents."
        ),
    }


def score_refusal(case: dict, ask: dict) -> dict:
    if case["type"] != "refusal":
        return {
            "score": None,
            "method": "n/a",
            "note": "Factual questions are not included in the refusal rate.",
        }
    ok = ask["answer"].strip() == REFUSAL_ANSWER and ask["citations"] == []
    return {
        "score": ok,
        "method": "exact_refusal_and_empty_citations",
        "note": "Pass if the API refuses exactly and does not cite sources.",
    }


@dataclass
class CaseScore:
    case_id: str
    question: str
    case_type: str
    retrieval_hit: bool | None
    correctness: bool | None
    faithfulness: bool | None
    citation_validity: bool | None
    refusal: bool | None
    notes: str


def evaluate_case(case: dict, ask_payload: dict, retrieve_payload: dict) -> CaseScore:
    ask = parse_ask_response(ask_payload)
    retrieve = parse_retrieve_response(retrieve_payload)
    retrieval = score_retrieval_hit(case, retrieve)
    correctness = score_correctness(case, ask)
    faithfulness = score_faithfulness(case, ask, retrieve)
    citations = score_citation_validity(case, ask)
    refusal = score_refusal(case, ask)
    notes = "; ".join(
        item["note"]
        for item in (retrieval, correctness, faithfulness, citations, refusal)
        if item.get("score") is False
    )
    return CaseScore(
        case_id=case["id"],
        question=case["question"],
        case_type=case["type"],
        retrieval_hit=retrieval["score"],
        correctness=correctness["score"],
        faithfulness=faithfulness["score"],
        citation_validity=citations["score"],
        refusal=refusal["score"],
        notes=notes,
    )


def _rate(values: list[bool | None]) -> str:
    scored = [item for item in values if item is not None]
    if not scored:
        return "n/a"
    return f"{sum(bool(item) for item in scored) / len(scored):.0%} ({sum(bool(item) for item in scored)}/{len(scored)})"


def _cell(value: bool | None) -> str:
    if value is None:
        return "n/a"
    return "pass" if value else "fail"


def render_markdown(spec: dict, scores: list[CaseScore]) -> str:
    baseline = spec["previous_retrieval_baseline"]
    lines = [
        "# RAG golden-set evaluation",
        "",
        "This table scores the existing FastAPI RAG API (`POST /ask` and "
        "`GET /debug/retrieve`). It does not re-implement retrieval or generation.",
        "",
        "## Previous retrieval baseline",
        "",
        "These metrics were measured earlier on the five factual ExampleCo questions. "
        "They are **not** recomputed by this evaluation run.",
        "",
        "| Metric | Previous result |",
        "| --- | --- |",
        f"| Recall@5 | {baseline['recall_at_5']:.0%} |",
        f"| Hit@1 | {baseline['hit_at_1']:.0%} |",
        f"| MRR | {baseline['mrr']:.2f} |",
        f"| Notes | {baseline['notes']} |",
        "",
        "## Golden-set results",
        "",
        "| ID | Type | Retrieval hit | Correctness | Faithfulness | Citation validity | Refusal |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for score in scores:
        lines.append(
            f"| `{score.case_id}` | {score.case_type} | {_cell(score.retrieval_hit)} | "
            f"{_cell(score.correctness)} | {_cell(score.faithfulness)} | "
            f"{_cell(score.citation_validity)} | {_cell(score.refusal)} |"
        )
    lines.extend(
        [
            "",
            "## Aggregates",
            "",
            "| Metric | Rate |",
            "| --- | --- |",
            f"| Retrieval hit (factual) | {_rate([s.retrieval_hit for s in scores])} |",
            f"| Answer correctness (factual) | {_rate([s.correctness for s in scores])} |",
            f"| Faithfulness (all scored) | {_rate([s.faithfulness for s in scores])} |",
            f"| Citation validity (all scored) | {_rate([s.citation_validity for s in scores])} |",
            f"| Refusal success (refusal cases) | {_rate([s.refusal for s in scores])} |",
            "",
            "## Scoring notes",
            "",
            "- Retrieval hit: deterministic phrase check against `GET /debug/retrieve` chunk text.",
            "- Correctness: required phrases from `sample_docs/README.md`, or an exact refusal.",
            "- Faithfulness: heuristic (required phrases and numbers must appear in retrieved text).",
            "- Citation validity: citations must be retrieved chunk IDs from the matching `/ask` call.",
            "- Refusal: exact string `I don't have enough information to answer that.` and no citations.",
        ]
    )
    return "\n".join(lines) + "\n"


def call_json(
    method: str,
    url: str,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
    params: dict | None = None,
    timeout: float = ASK_TIMEOUT_SECONDS,
) -> tuple[int, dict | str]:
    try:
        if method == "POST":
            response = httpx.post(
                url, json=payload, headers=headers, timeout=timeout
            )
        else:
            response = httpx.get(
                url, headers=headers, params=params, timeout=timeout
            )
        try:
            return response.status_code, response.json()
        except json.JSONDecodeError:
            return response.status_code, response.text
    except httpx.HTTPError as exc:
        return 0, {"error": str(exc)}


def run_live(spec: dict, base_url: str, ingest_key: str) -> list[CaseScore]:
    scores: list[CaseScore] = []
    for case in spec["cases"]:
        ask_status, ask_payload = call_json(
            "POST",
            f"{base_url.rstrip('/')}/ask",
            {"question": case["question"], "model": "gpt-4o-mini", "force_bad": False},
            timeout=ASK_TIMEOUT_SECONDS,
        )
        retrieve_status, retrieve_payload = call_json(
            "GET",
            f"{base_url.rstrip('/')}/debug/retrieve",
            headers={"X-Ingest-Key": ingest_key},
            params={"q": case["question"], "top_k": spec.get("top_k", 5)},
            timeout=RETRIEVE_TIMEOUT_SECONDS,
        )
        if ask_status != 200 or not isinstance(ask_payload, dict):
            raise RuntimeError(f"{case['id']} /ask failed: HTTP {ask_status}")
        if retrieve_status != 200 or not isinstance(retrieve_payload, dict):
            raise RuntimeError(
                f"{case['id']} /debug/retrieve failed: HTTP {retrieve_status}"
            )
        scores.append(evaluate_case(case, ask_payload, retrieve_payload))
    return scores


def methodology_text(spec: dict) -> str:
    baseline = spec["previous_retrieval_baseline"]
    factual = [case for case in spec["cases"] if case["type"] == "factual"]
    refusals = [case for case in spec["cases"] if case["type"] == "refusal"]
    return "\n".join(
        [
            "RAG golden-set evaluation (dry run: no API calls).",
            "",
            f"Cases: {len(factual)} factual + {len(refusals)} refusal = {len(spec['cases'])}.",
            "Live plan: 1 POST /ask and 1 GET /debug/retrieve per case "
            f"({len(spec['cases']) * 2} HTTP requests).",
            "Model: gpt-4o-mini. top_k=5. force_bad=false.",
            "",
            "Previous retrieval baseline (not re-measured here): "
            f"Recall@5 {baseline['recall_at_5']:.0%}, "
            f"Hit@1 {baseline['hit_at_1']:.0%}, "
            f"MRR {baseline['mrr']:.2f}.",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the FastAPI RAG golden set.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Call the deployed API. Do not use until explicitly authorized.",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/"),
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    spec = load_spec()

    if not args.live:
        print(methodology_text(spec))
        print("\nPass --live only after authorization. Default mode makes no API calls.")
        return 0

    ingest_key = os.getenv("INGEST_API_KEY", "").strip()
    if not ingest_key:
        print("INGEST_API_KEY is missing. Refusing to call /debug/retrieve unauthenticated.")
        return 2

    scores = run_live(spec, args.base_url, ingest_key)
    markdown = render_markdown(spec, scores)
    print(markdown)
    if args.output:
        args.output.write_text(markdown, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
