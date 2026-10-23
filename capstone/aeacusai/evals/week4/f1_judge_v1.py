"""F1 judge v1: frozen prompt, request builder, parse/validate, and metrics.

Assesses F1 only. Does not run the capstone agent, retrieve sources, or open
SQLite. Human labels are not used when building judge requests.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

PROJECT_DIR = Path(__file__).resolve().parents[2]
JUDGE_ID = "week4_f1_judge_v1"
PROMPT_VERSION = "f1_judge_prompt_v1"
SPLIT_ID = "week4_f1_split_v1"
RUBRIC_ID = "week4_f1_rubric_v1"
CONTRACT_ID = "week4_f1_judge_contract_v1"

PROMPT_RELATIVE = "evals/week4/judge/f1_v1/prompt_v1.txt"
CONFIG_RELATIVE = "evals/week4/judge/f1_v1/inference_config.json"
MANIFEST_RELATIVE = "evals/week4/golden/f1_v1/manifest.json"
SPLIT_RELATIVE = "evals/week4/golden/f1_v1/split.json"
RUBRIC_RELATIVE = "evals/week4/golden/f1_v1/f1_rubric.json"
CONTRACT_RELATIVE = "evals/week4/golden/f1_v1/judge_contract.json"
CASES_RELATIVE = "data/local/evals/week4/golden/f1_v1/cases.jsonl"
PAYLOADS_RELATIVE = "data/local/evals/week4/golden/f1_v1/judge_payloads.jsonl"
PREDICTIONS_DIR_RELATIVE = "data/local/evals/week4/judge/f1_v1/calibration_v1"
REPORT_MD_RELATIVE = "reports/week4_f1_judge_v1_calibration.md"
REPORT_JSON_RELATIVE = "reports/week4_f1_judge_v1_calibration.json"

EXPECTED_HASHES = {
    "prompt": "27e571fcc3830852133bed275fd00a272b41f8fabfc2d8d30e7de05e17a5c700",
    "inference_config": (
        "358ad788ff2be762aaf5083114bff3cf93db1c08b8df8f15b3b7db76b6defc0c"
    ),
    "manifest": "262ce9b1401be57dd61ff8f0b43c08b6cea9d44008e030a816acacad78669963",
    "split": "a57e8cac7d357b67f98a04f5b83a65da39a5cc8f54b6c26ecad3ae6596e54d30",
    "f1_rubric": "1db86276750dab8e6f93c34ef429482065eff5373a6d6e72b4c43625999a7502",
    "judge_contract": (
        "91aae84736794d980e37251173dfc98b999147086ef56e8142224f369ec5a480"
    ),
    "cases_jsonl": (
        "152adaebbcd9c51c83bbdfcbf37bab694eeb4f9668c226563c9f69c652a0c15c"
    ),
    "judge_payloads_jsonl": (
        "1f9abd172f98692b3d62a071664caf7be3347fbd23a3cb2d5b961bf234d8f3f6"
    ),
}

ALLOWED_PAYLOAD_FIELDS = (
    "f1_rubric",
    "system_description",
    "retrieved_evidence",
    "answer",
)
UNTRUSTED_FIELDS = ("system_description", "retrieved_evidence", "answer")
FORBIDDEN_REQUEST_FIELDS = (
    "f1",
    "gold",
    "gold_label",
    "human_label",
    "annotation",
    "annotation_reason",
    "notes",
    "baseline_id",
    "case_id",
    "group",
    "scenario_id",
    "run_id",
    "evaluation_id",
    "expected",
    "expected_result",
    "comparison",
    "version_comparison",
    "recovery",
    "regression",
    "parent",
    "candidate",
)
METADATA_LEAK_FIELDS = (
    "evaluation_id",
    "case_id",
    "baseline_id",
    "scenario_id",
    "run_id",
    "group",
    "f1",
    "gold",
    "expected",
    "expected_result",
)
STOP_ERROR_RE = re.compile(
    r"(UNAUTHENTICATED|PERMISSION_DENIED|RESOURCE_EXHAUSTED|quota|"
    r"API key|api key|401|403|429|authentication|insufficient[_ ]quota)",
    re.IGNORECASE,
)
JSON_FENCE_RE = re.compile(
    r"^```(?:json)?\s*(.*?)\s*```$",
    re.IGNORECASE | re.DOTALL,
)
RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "verdict": {"type": "STRING", "enum": ["pass", "fail"]},
        "reason": {"type": "STRING"},
        "excerpt": {"type": "STRING"},
    },
    "required": ["verdict", "reason", "excerpt"],
}


class JudgeError(RuntimeError):
    """Judge configuration, request, or scoring failure."""


class JudgeStopError(JudgeError):
    """Authentication, quota, or persistence failure that must halt the batch."""


class JudgeContractError(JudgeError):
    """A model response that does not satisfy the frozen output contract."""


def sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def project_path(relative: str, root: Path | None = None) -> Path:
    return (root or PROJECT_DIR) / relative


def load_prompt(root: Path | None = None) -> str:
    return project_path(PROMPT_RELATIVE, root).read_text(encoding="utf-8")


def load_inference_config(root: Path | None = None) -> dict[str, Any]:
    return load_json(project_path(CONFIG_RELATIVE, root))


def verify_frozen_inputs(root: Path | None = None) -> dict[str, str]:
    root = root or PROJECT_DIR
    paths = {
        "prompt": project_path(PROMPT_RELATIVE, root),
        "inference_config": project_path(CONFIG_RELATIVE, root),
        "manifest": project_path(MANIFEST_RELATIVE, root),
        "split": project_path(SPLIT_RELATIVE, root),
        "f1_rubric": project_path(RUBRIC_RELATIVE, root),
        "judge_contract": project_path(CONTRACT_RELATIVE, root),
        "cases_jsonl": project_path(CASES_RELATIVE, root),
        "judge_payloads_jsonl": project_path(PAYLOADS_RELATIVE, root),
    }
    observed: dict[str, str] = {}
    missing = [key for key, path in paths.items() if not path.is_file()]
    if missing:
        raise JudgeError(f"required judge inputs missing: {missing}")
    for key, path in paths.items():
        digest = sha256_file(path)
        expected = EXPECTED_HASHES[key]
        if digest != expected:
            raise JudgeError(
                f"{key} hash mismatch: expected {expected}, observed {digest}."
            )
        observed[key] = digest
    rubric = load_json(paths["f1_rubric"])
    contract = load_json(paths["judge_contract"])
    split = load_json(paths["split"])
    config = load_json(paths["inference_config"])
    if rubric.get("rubric_id") != RUBRIC_ID:
        raise JudgeError("frozen rubric_id drifted.")
    if contract.get("contract_id") != CONTRACT_ID:
        raise JudgeError("frozen contract_id drifted.")
    if split.get("split_id") != SPLIT_ID:
        raise JudgeError("frozen split_id drifted.")
    if config.get("judge_id") != JUDGE_ID:
        raise JudgeError("frozen judge_id drifted.")
    if sha256_text(paths["prompt"].read_text(encoding="utf-8")) != observed["prompt"]:
        raise JudgeError("prompt hash drifted after read.")
    return observed


def load_split(root: Path | None = None) -> dict[str, Any]:
    return load_json(project_path(SPLIT_RELATIVE, root))


def load_manifest(root: Path | None = None) -> dict[str, Any]:
    return load_json(project_path(MANIFEST_RELATIVE, root))


def load_rubric(root: Path | None = None) -> dict[str, Any]:
    return load_json(project_path(RUBRIC_RELATIVE, root))


def calibration_case_rows(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = [
        dict(row)
        for row in manifest.get("cases") or []
        if row.get("group") == "calibration"
    ]
    if len(rows) != 20:
        raise JudgeError(f"expected 20 calibration cases, found {len(rows)}.")
    return rows


def validation_evaluation_ids(manifest: Mapping[str, Any]) -> set[str]:
    return {
        str(row["evaluation_id"])
        for row in manifest.get("cases") or []
        if row.get("group") == "validation"
    }


def association_map(rows: list[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for row in rows:
        evaluation_id = str(row["evaluation_id"])
        mapping[evaluation_id] = {
            "evaluation_id": evaluation_id,
            "case_id": row.get("case_id"),
            "baseline_id": row.get("baseline_id"),
            "scenario_id": row.get("scenario_id"),
            "run_id": row.get("run_id"),
            "group": row.get("group"),
            "f1": row.get("f1"),
        }
    return mapping


def load_jsonl_by_id(
    path: Path,
    allowed_ids: set[str],
    id_field: str = "evaluation_id",
) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            row = json.loads(line)
            evaluation_id = str(row.get(id_field) or "")
            if evaluation_id not in allowed_ids:
                continue
            found[evaluation_id] = row
    missing = sorted(allowed_ids - set(found))
    if missing:
        raise JudgeError(f"missing payloads for evaluation_ids: {missing}")
    return found


def _payload_rubric_ok(payload: Mapping[str, Any], rubric: Mapping[str, Any]) -> None:
    incoming = payload.get("f1_rubric") or {}
    for key in ("rubric_id", "category_id", "title", "positive_means"):
        if incoming.get(key) != rubric.get(key):
            raise JudgeError(f"payload rubric field {key} does not match freeze.")


def approved_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    missing = [
        field
        for field in ("system_description", "retrieved_evidence", "answer")
        if field not in payload
    ]
    if missing:
        raise JudgeError(f"payload missing required fields: {missing}")
    if not isinstance(payload.get("system_description"), str):
        raise JudgeError("system_description must be a string.")
    if not isinstance(payload.get("answer"), str):
        raise JudgeError("answer must be a string.")
    if not isinstance(payload.get("retrieved_evidence"), list):
        raise JudgeError("retrieved_evidence must be a list.")
    return {
        "system_description": payload["system_description"],
        "retrieved_evidence": [
            {
                "label": item.get("label"),
                "record_id": item.get("record_id"),
                "text_sha256": item.get("text_sha256"),
                "text": item.get("text"),
            }
            for item in payload["retrieved_evidence"]
            if isinstance(item, Mapping)
        ],
        "answer": payload["answer"],
    }


def format_evidence(records: list[Mapping[str, Any]]) -> str:
    if not records:
        return "(no retrieved evidence)"
    parts: list[str] = []
    for index, item in enumerate(records, start=1):
        parts.append(
            f"[{index}] {item.get('label') or 'record'}\n"
            f"record_id: {item.get('record_id') or ''}\n"
            f"text_sha256: {item.get('text_sha256') or ''}\n"
            f"{item.get('text') or ''}"
        )
    return "\n\n".join(parts)


def build_user_text(payload: Mapping[str, Any]) -> str:
    approved = approved_payload(payload)
    return (
        "BEGIN UNTRUSTED SYSTEM DESCRIPTION\n"
        f"{approved['system_description']}\n"
        "END UNTRUSTED SYSTEM DESCRIPTION\n\n"
        "BEGIN UNTRUSTED RETRIEVED EVIDENCE\n"
        f"{format_evidence(approved['retrieved_evidence'])}\n"
        "END UNTRUSTED RETRIEVED EVIDENCE\n\n"
        "BEGIN UNTRUSTED ANSWER\n"
        f"{approved['answer']}\n"
        "END UNTRUSTED ANSWER\n"
    )


def build_model_request(
    payload: Mapping[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    prompt = load_prompt(root)
    config = load_inference_config(root)
    generation = dict(config["generation"])
    user_text = build_user_text(payload)
    request = {
        "model": config["model"],
        "system_instruction": prompt,
        "user_text": user_text,
        "generation": generation,
        "prompt_version": config["prompt_version"],
        "prompt_sha256": sha256_text(prompt),
        "config_sha256": sha256_file(project_path(CONFIG_RELATIVE, root)),
        "turns": 1,
        "tools": [],
    }
    assert_request_has_no_leakage(request, payload)
    return request


def untrusted_blob(payload: Mapping[str, Any]) -> str:
    approved = approved_payload(payload)
    evidence = format_evidence(approved["retrieved_evidence"])
    return (
        f"{approved['system_description']}\n{evidence}\n{approved['answer']}"
    )


def assert_request_has_no_leakage(
    request: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> None:
    user_text = str(request.get("user_text") or "")
    system_instruction = str(request.get("system_instruction") or "")
    blob = untrusted_blob(payload)
    for field in FORBIDDEN_REQUEST_FIELDS:
        if field in request:
            raise JudgeError(f"forbidden field {field} present on model request.")
    for field in METADATA_LEAK_FIELDS:
        value = payload.get(field)
        if value is None:
            continue
        token = str(value)
        if token and token not in blob and token in user_text:
            raise JudgeError(f"metadata field {field} leaked into judge request.")
    if "evaluation_id" in system_instruction and payload.get("evaluation_id"):
        if str(payload["evaluation_id"]) in system_instruction:
            raise JudgeError("opaque evaluation_id leaked into system instruction.")


def select_calibration_jobs(
    manifest: Mapping[str, Any],
    payloads: Mapping[str, Mapping[str, Any]],
    *,
    rubric: Mapping[str, Any],
    split: Mapping[str, Any],
) -> list[dict[str, Any]]:
    calibration_ids = {str(row["evaluation_id"]) for row in calibration_case_rows(manifest)}
    blocked = validation_evaluation_ids(manifest)
    validation_scenarios = set(split.get("validation_scenario_ids") or [])
    jobs: list[dict[str, Any]] = []
    for row in calibration_case_rows(manifest):
        evaluation_id = str(row["evaluation_id"])
        if evaluation_id in blocked or row.get("group") != "calibration":
            raise JudgeError(f"{evaluation_id} is not a calibration case.")
        if row.get("scenario_id") in validation_scenarios:
            raise JudgeError(
                f"{evaluation_id} scenario {row.get('scenario_id')} is held out."
            )
        payload = payloads.get(evaluation_id)
        if payload is None:
            raise JudgeError(f"no payload for calibration id {evaluation_id}.")
        _payload_rubric_ok(payload, rubric)
        jobs.append(
            {
                "evaluation_id": evaluation_id,
                "payload": approved_payload(payload),
            }
        )
    extra = set(payloads) - calibration_ids
    if extra:
        raise JudgeError(f"non-calibration payloads supplied to runner: {sorted(extra)}")
    if len(jobs) != 20:
        raise JudgeError(f"calibration runner requires 20 jobs, found {len(jobs)}.")
    return jobs


def parse_judge_json(raw_text: str) -> dict[str, Any]:
    text = (raw_text or "").strip()
    fenced = JSON_FENCE_RE.match(text)
    if fenced:
        text = fenced.group(1).strip()
    if not text:
        raise JudgeContractError("empty judge response.")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise JudgeContractError(f"judge response is not JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise JudgeContractError("judge response is not a JSON object.")
    return parsed


def validate_prediction(
    parsed: Mapping[str, Any],
    answer: str,
) -> dict[str, str]:
    unexpected = sorted(set(parsed) - {"verdict", "reason", "excerpt"})
    if unexpected:
        raise JudgeContractError(f"unexpected keys: {unexpected}")
    missing = [key for key in ("verdict", "reason", "excerpt") if key not in parsed]
    if missing:
        raise JudgeContractError(f"missing keys: {missing}")
    verdict = parsed["verdict"]
    reason = parsed["reason"]
    excerpt = parsed["excerpt"]
    if verdict not in {"pass", "fail"}:
        raise JudgeContractError(f"invalid verdict: {verdict!r}")
    if not isinstance(reason, str) or not reason.strip() or "\n" in reason or "\r" in reason:
        raise JudgeContractError("reason must be a non-empty single line.")
    if not isinstance(excerpt, str):
        raise JudgeContractError("excerpt must be a string.")
    if verdict == "pass":
        if excerpt != "":
            raise JudgeContractError("pass verdict must use an empty excerpt.")
    else:
        if not excerpt:
            raise JudgeContractError("fail verdict requires a non-empty excerpt.")
        if excerpt not in answer:
            raise JudgeContractError("fail excerpt is not an exact answer substring.")
    return {
        "verdict": verdict,
        "reason": reason.strip(),
        "excerpt": excerpt,
    }


def parse_and_validate(raw_text: str, answer: str) -> dict[str, str]:
    return validate_prediction(parse_judge_json(raw_text), answer)


def confusion_counts(pairs: list[tuple[str, str]]) -> dict[str, int]:
    counts = {"TP": 0, "FN": 0, "TN": 0, "FP": 0}
    for gold, pred in pairs:
        if gold not in {"pass", "fail"} or pred not in {"pass", "fail"}:
            raise JudgeError(f"non-binary pair: gold={gold!r} pred={pred!r}")
        if gold == "fail" and pred == "fail":
            counts["TP"] += 1
        elif gold == "fail" and pred == "pass":
            counts["FN"] += 1
        elif gold == "pass" and pred == "pass":
            counts["TN"] += 1
        else:
            counts["FP"] += 1
    return counts


def rate_or_undefined(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def metric_block(counts: Mapping[str, int]) -> dict[str, Any]:
    positives = counts["TP"] + counts["FN"]
    negatives = counts["TN"] + counts["FP"]
    return {
        "TP": counts["TP"],
        "FN": counts["FN"],
        "TN": counts["TN"],
        "FP": counts["FP"],
        "TPR": rate_or_undefined(counts["TP"], positives),
        "TNR": rate_or_undefined(counts["TN"], negatives),
        "positives_in_metrics": positives,
        "negatives_in_metrics": negatives,
        "positive_class": "fail",
    }


def is_stop_error(exc: BaseException) -> bool:
    text = f"{type(exc).__name__}: {exc}"
    code = getattr(exc, "code", None) or getattr(exc, "status", None)
    if code in (401, 403, 429):
        return True
    if str(code).upper() in {
        "UNAUTHENTICATED",
        "PERMISSION_DENIED",
        "RESOURCE_EXHAUSTED",
    }:
        return True
    return bool(STOP_ERROR_RE.search(text))


def usage_from_response(response: Any) -> dict[str, Any] | None:
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return None
    return {
        "prompt_token_count": getattr(meta, "prompt_token_count", None),
        "candidates_token_count": getattr(meta, "candidates_token_count", None),
        "thoughts_token_count": getattr(meta, "thoughts_token_count", None),
        "total_token_count": getattr(meta, "total_token_count", None),
    }


def generation_config_kwargs(generation: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "temperature": generation["temperature"],
        "max_output_tokens": generation["max_output_tokens"],
        "candidate_count": generation["candidate_count"],
        "response_mime_type": generation["response_mime_type"],
        "response_schema": RESPONSE_SCHEMA,
        "thinking_budget": generation.get("thinking_budget", 0),
        "include_thoughts": generation.get("include_thoughts", False),
    }


class LiveJudgeTransport:
    """Single-turn google-genai transport. No tools or retrieval."""

    def __init__(self, api_key: str):
        from google import genai

        self.client = genai.Client(api_key=api_key)

    def generate(self, request: Mapping[str, Any]) -> dict[str, Any]:
        from google.genai import types

        generation = request["generation"]
        config = types.GenerateContentConfig(
            system_instruction=request["system_instruction"],
            temperature=generation["temperature"],
            max_output_tokens=generation["max_output_tokens"],
            candidate_count=generation["candidate_count"],
            response_mime_type=generation["response_mime_type"],
            response_schema=RESPONSE_SCHEMA,
            thinking_config=types.ThinkingConfig(
                thinking_budget=generation.get("thinking_budget", 0),
                include_thoughts=generation.get("include_thoughts", False),
            ),
        )
        started = time.perf_counter()
        started_at = utc_now()
        response = self.client.models.generate_content(
            model=request["model"],
            contents=request["user_text"],
            config=config,
        )
        return {
            "raw_text": getattr(response, "text", None) or "",
            "usage": usage_from_response(response),
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "started_at": started_at,
            "ended_at": utc_now(),
            "model_version": getattr(response, "model_version", None),
        }


def predict_one(
    transport: Any,
    job: Mapping[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    request = build_model_request(job["payload"], root=root)
    record: dict[str, Any] = {
        "evaluation_id": job["evaluation_id"],
        "status": "invalid",
        "raw_response": None,
        "parsed": None,
        "validation_error": None,
        "usage": None,
        "elapsed_ms": None,
        "started_at": utc_now(),
        "ended_at": None,
        "model": request["model"],
        "prompt_version": request["prompt_version"],
        "prompt_sha256": request["prompt_sha256"],
        "config_sha256": request["config_sha256"],
        "generation": request["generation"],
    }
    try:
        result = transport.generate(request)
    except Exception as exc:
        record["ended_at"] = utc_now()
        record["provider_error"] = f"{type(exc).__name__}: {exc}"
        if is_stop_error(exc):
            record["status"] = "stopped"
            raise JudgeStopError(record["provider_error"]) from exc
        record["status"] = "provider_error"
        return record
    record["raw_response"] = result.get("raw_text")
    record["usage"] = result.get("usage")
    record["elapsed_ms"] = result.get("elapsed_ms")
    record["started_at"] = result.get("started_at") or record["started_at"]
    record["ended_at"] = result.get("ended_at") or utc_now()
    record["model_version"] = result.get("model_version")
    try:
        record["parsed"] = parse_and_validate(
            str(result.get("raw_text") or ""),
            job["payload"]["answer"],
        )
        record["status"] = "valid"
        record["validation_error"] = None
    except JudgeContractError as exc:
        record["status"] = "invalid"
        record["parsed"] = None
        record["validation_error"] = str(exc)
    return record


def persist_prediction_line(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
    except OSError as exc:
        raise JudgeStopError(f"persistence failed: {exc}") from exc


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise JudgeStopError(f"persistence failed: {exc}") from exc


def load_prediction_lines(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            rows.append(json.loads(raw))
    return rows


def score_predictions(
    predictions: list[Mapping[str, Any]],
    labels: Mapping[str, Mapping[str, Any]],
    payloads: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    pairs: list[tuple[str, str]] = []
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    missing: list[str] = []
    disagreements: list[dict[str, Any]] = []
    expected_ids = [str(evaluation_id) for evaluation_id in labels]
    predicted_ids = {str(row.get("evaluation_id")) for row in predictions}
    for evaluation_id in expected_ids:
        if evaluation_id not in predicted_ids:
            missing.append(evaluation_id)
    for row in predictions:
        evaluation_id = str(row.get("evaluation_id"))
        label_row = labels.get(evaluation_id)
        if label_row is None:
            raise JudgeError(f"no label loaded for {evaluation_id}.")
        gold = label_row["f1"]
        if row.get("status") != "valid" or not row.get("parsed"):
            invalid.append(
                {
                    "evaluation_id": evaluation_id,
                    "scenario_id": label_row.get("scenario_id"),
                    "status": row.get("status"),
                    "validation_error": row.get("validation_error"),
                    "provider_error": row.get("provider_error"),
                    "reviewed_label": gold,
                }
            )
            continue
        pred = row["parsed"]["verdict"]
        pairs.append((gold, pred))
        joined = {
            "evaluation_id": evaluation_id,
            "scenario_id": label_row.get("scenario_id"),
            "reviewed_label": gold,
            "judge_verdict": pred,
            "reason": row["parsed"]["reason"],
            "excerpt": row["parsed"]["excerpt"],
            "input": payloads[evaluation_id]["system_description"],
            "answer": payloads[evaluation_id]["answer"],
        }
        valid.append(joined)
        if gold != pred:
            disagreements.append(joined)
    counts = confusion_counts(pairs) if pairs else {
        "TP": 0,
        "FN": 0,
        "TN": 0,
        "FP": 0,
    }
    metrics = metric_block(counts)
    coverage = len(valid)
    expected = len(labels)
    false_negatives = [
        item for item in disagreements if item["reviewed_label"] == "fail"
    ]
    false_positives = [
        item for item in disagreements if item["reviewed_label"] == "pass"
    ]
    return {
        "metrics": metrics,
        "expected_n": expected,
        "valid_n": coverage,
        "invalid_n": len(invalid),
        "missing_n": len(missing),
        "prediction_coverage": coverage / expected if expected else None,
        "valid_response_only": coverage < expected,
        "invalid": invalid,
        "missing": missing,
        "false_negatives": false_negatives,
        "false_positives": false_positives,
        "valid": valid,
    }


def format_rate(value: float | None) -> str:
    if value is None:
        return "undefined"
    return f"{value:.3f}"


def disagreement_markdown(title: str, rows: list[Mapping[str, Any]]) -> str:
    if not rows:
        return f"## {title}\n\nNone.\n\n"
    parts = [f"## {title}\n"]
    for index, row in enumerate(rows, start=1):
        excerpt = row.get("excerpt") or ""
        if not excerpt:
            answer = str(row.get("answer") or "")
            excerpt = answer[:280] + ("…" if len(answer) > 280 else "")
        parts.append(
            f"### {index}. {row.get('scenario_id')} / `{row.get('evaluation_id')}`\n"
            f"- Reviewed label: {row.get('reviewed_label')}\n"
            f"- Judge verdict: {row.get('judge_verdict')}\n"
            f"- Reason: {row.get('reason')}\n"
            f"- Relevant answer excerpt: {excerpt}\n"
            f"- Input: {row.get('input')}\n"
        )
    return "\n".join(parts) + "\n"


def render_calibration_report(score: Mapping[str, Any], run: Mapping[str, Any]) -> str:
    metrics = score["metrics"]
    coverage_note = (
        "Rates are valid-response-only and do not cover all 20 calibration cases."
        if score["valid_response_only"]
        else "All 20 calibration outputs produced a valid judge response."
    )
    return (
        "# Week 4 F1 judge v1 calibration\n\n"
        "This report scores the frozen F1 judge v1 on the calibration split "
        "only. The judge is not an application or approval gate. The prompt "
        "was not refined after this batch.\n\n"
        "## Scope\n\n"
        "- Judge ID: `week4_f1_judge_v1`\n"
        "- Split: calibration only (20 outputs from 10 paired scenarios)\n"
        "- Positive class: F1 failure (`fail`)\n"
        f"- Model: `{run.get('model')}`\n"
        f"- Prompt version: `{run.get('prompt_version')}`\n"
        f"- Prompt SHA-256: `{run.get('prompt_sha256')}`\n"
        f"- Inference config SHA-256: `{run.get('config_sha256')}`\n"
        f"- Stopped: {run.get('stopped')}\n"
        f"- Stop reason: {run.get('stop_reason') or 'none'}\n\n"
        "## Confusion matrix\n\n"
        "Failure is the positive class. Invalid or missing predictions are "
        "excluded from TP/FN/TN/FP and are not coerced into pass or fail.\n\n"
        f"- TP: {metrics['TP']}\n"
        f"- FN: {metrics['FN']}\n"
        f"- TN: {metrics['TN']}\n"
        f"- FP: {metrics['FP']}\n"
        f"- TPR = TP/(TP+FN): {format_rate(metrics['TPR'])}\n"
        f"- TNR = TN/(TN+FP): {format_rate(metrics['TNR'])}\n"
        f"- Positives represented in the rates: {metrics['positives_in_metrics']}\n"
        f"- Negatives represented in the rates: {metrics['negatives_in_metrics']}\n\n"
        "## Coverage\n\n"
        f"- Expected calibration outputs: {score['expected_n']}\n"
        f"- Valid predictions: {score['valid_n']}\n"
        f"- Invalid responses: {score['invalid_n']}\n"
        f"- Missing predictions: {score['missing_n']}\n"
        f"- Prediction coverage: {score['prediction_coverage']}\n"
        f"- {coverage_note}\n\n"
        + disagreement_markdown("Calibration false negatives", score["false_negatives"])
        + disagreement_markdown("Calibration false positives", score["false_positives"])
        + "## Limitations\n\n"
        "- 20 outputs from 10 paired scenarios, not 20 independent cases.\n"
        "- Only 5 labeled failures in calibration.\n"
        "- AI-assisted labels reviewed by Lily; not independent legal adjudication.\n"
        "- The judge uses the same model family as the assessed agent.\n"
        "- Calibration performance is not held-out validation.\n"
        "- Validation examples were not used to design or refine this prompt.\n"
        "- This judge is not wired into the application or approval controls.\n"
    )


def write_freeze_record(path: Path, hashes: Mapping[str, str]) -> None:
    write_json(
        path,
        {
            "schema": "aeacus.week4.f1_judge.freeze.v1",
            "judge_id": JUDGE_ID,
            "prompt_version": PROMPT_VERSION,
            "frozen_before_first_call": True,
            "hashes": dict(hashes),
            "frozen_at": utc_now(),
        },
    )


def assert_freeze_unchanged(hashes: Mapping[str, str], root: Path | None = None) -> None:
    current = {
        "prompt": sha256_file(project_path(PROMPT_RELATIVE, root)),
        "inference_config": sha256_file(project_path(CONFIG_RELATIVE, root)),
    }
    if current["prompt"] != hashes["prompt"]:
        raise JudgeError("prompt changed during the calibration batch.")
    if current["inference_config"] != hashes["inference_config"]:
        raise JudgeError("inference config changed during the calibration batch.")


def run_calibration(
    transport_factory: Callable[[], Any],
    *,
    root: Path | None = None,
    load_labels: bool = False,
) -> dict[str, Any]:
    if load_labels:
        raise JudgeError("labels must not be loaded before predictions are saved.")
    root = root or PROJECT_DIR
    hashes = verify_frozen_inputs(root)
    manifest = load_manifest(root)
    split = load_split(root)
    rubric = load_rubric(root)
    calibration_rows = calibration_case_rows(manifest)
    calibration_ids = {str(row["evaluation_id"]) for row in calibration_rows}
    payloads = load_jsonl_by_id(
        project_path(PAYLOADS_RELATIVE, root),
        calibration_ids,
    )
    jobs = select_calibration_jobs(manifest, payloads, rubric=rubric, split=split)
    out_dir = project_path(PREDICTIONS_DIR_RELATIVE, root)
    freeze_path = out_dir / "freeze.json"
    predictions_jsonl = out_dir / "predictions.jsonl"
    predictions_json = out_dir / "predictions.json"
    if not freeze_path.is_file():
        write_freeze_record(freeze_path, hashes)
    existing = load_prediction_lines(predictions_jsonl)
    done_ids = {str(row.get("evaluation_id")) for row in existing}
    pending = [job for job in jobs if job["evaluation_id"] not in done_ids]
    run_meta: dict[str, Any] = {
        "judge_id": JUDGE_ID,
        "split": "calibration",
        "model": load_inference_config(root)["model"],
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": hashes["prompt"],
        "config_sha256": hashes["inference_config"],
        "generation": load_inference_config(root)["generation"],
        "n_existing": len(existing),
        "n_pending": len(pending),
        "stopped": False,
        "stop_reason": None,
        "started_at": utc_now(),
    }
    predictions = list(existing)
    if pending:
        transport = transport_factory()
        for job in pending:
            assert_freeze_unchanged(hashes, root)
            try:
                record = predict_one(transport, job, root=root)
            except JudgeStopError as exc:
                run_meta["stopped"] = True
                run_meta["stop_reason"] = str(exc)
                persist_prediction_line(
                    predictions_jsonl,
                    {
                        "evaluation_id": job["evaluation_id"],
                        "status": "stopped",
                        "provider_error": str(exc),
                        "parsed": None,
                        "raw_response": None,
                        "started_at": utc_now(),
                        "ended_at": utc_now(),
                    },
                )
                break
            persist_prediction_line(predictions_jsonl, record)
            predictions.append(record)
            write_json(
                predictions_json,
                {
                    "schema": "aeacus.week4.f1_judge.predictions.v1",
                    "judge_id": JUDGE_ID,
                    "split": "calibration",
                    "labels_included": False,
                    "frozen": run_meta,
                    "predictions": predictions,
                },
            )
    predictions = load_prediction_lines(predictions_jsonl)
    write_json(
        predictions_json,
        {
            "schema": "aeacus.week4.f1_judge.predictions.v1",
            "judge_id": JUDGE_ID,
            "split": "calibration",
            "labels_included": False,
            "frozen": run_meta,
            "predictions": predictions,
        },
    )
    run_meta["ended_at"] = utc_now()
    run_meta["n_persisted"] = len(predictions)
    labels = association_map(calibration_rows)
    score = score_predictions(predictions, labels, payloads)
    report = {
        "schema": "aeacus.week4.f1_judge.calibration_report.v1",
        "judge_id": JUDGE_ID,
        "split": "calibration",
        "not_an_application_or_approval_gate": True,
        "prompt_refined_after_batch": False,
        "validation_inference": False,
        "run": run_meta,
        "hashes": hashes,
        "score": {
            key: score[key]
            for key in (
                "metrics",
                "expected_n",
                "valid_n",
                "invalid_n",
                "missing_n",
                "prediction_coverage",
                "valid_response_only",
                "invalid",
                "missing",
            )
        },
        "false_negatives": [
            {
                "evaluation_id": row["evaluation_id"],
                "scenario_id": row["scenario_id"],
                "input": row["input"],
                "relevant_answer_excerpt": row["excerpt"]
                or (row["answer"][:280] + ("…" if len(row["answer"]) > 280 else "")),
                "reviewed_label": row["reviewed_label"],
                "judge_verdict": row["judge_verdict"],
                "reason": row["reason"],
            }
            for row in score["false_negatives"]
        ],
        "false_positives": [
            {
                "evaluation_id": row["evaluation_id"],
                "scenario_id": row["scenario_id"],
                "input": row["input"],
                "relevant_answer_excerpt": row["excerpt"]
                or (row["answer"][:280] + ("…" if len(row["answer"]) > 280 else "")),
                "reviewed_label": row["reviewed_label"],
                "judge_verdict": row["judge_verdict"],
                "reason": row["reason"],
            }
            for row in score["false_positives"]
        ],
        "limitations": [
            "20 outputs from 10 paired scenarios",
            "only 5 labeled failures",
            "AI-assisted labels reviewed by Lily",
            "same model family as the assessed agent",
            "calibration performance is not held-out validation",
        ],
    }
    write_json(project_path(REPORT_JSON_RELATIVE, root), report)
    project_path(REPORT_MD_RELATIVE, root).write_text(
        render_calibration_report(score, run_meta),
        encoding="utf-8",
    )
    scored_path = out_dir / "scored.json"
    write_json(
        scored_path,
        {
            "schema": "aeacus.week4.f1_judge.scored.v1",
            "labels_joined_after_predictions_saved": True,
            "score": score,
            "run": run_meta,
        },
    )
    return report
