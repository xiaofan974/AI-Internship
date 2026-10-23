"""F1 judge v2: single permitted calibration refinement of v1.

Reuses v1 payload construction, output schema, and response validation.
Does not run the capstone agent, retrieve sources, or open SQLite.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

from evals.week4.f1_judge_v1 import (
    CONTRACT_ID,
    PROJECT_DIR,
    RUBRIC_ID,
    SPLIT_ID,
    JudgeError,
    JudgeStopError,
    LiveJudgeTransport,
    association_map,
    assert_request_has_no_leakage,
    build_user_text,
    calibration_case_rows,
    disagreement_markdown,
    format_rate,
    load_json,
    load_jsonl_by_id,
    load_manifest,
    load_prediction_lines,
    load_rubric,
    load_split,
    persist_prediction_line,
    parse_and_validate,
    project_path,
    select_calibration_jobs,
    score_predictions,
    sha256_file,
    sha256_text,
    utc_now,
    write_json,
)

JUDGE_ID = "week4_f1_judge_v2"
PARENT_JUDGE_ID = "week4_f1_judge_v1"
PROMPT_VERSION = "f1_judge_prompt_v2"
PROMPT_RELATIVE = "evals/week4/judge/f1_v2/prompt_v2.txt"
CONFIG_RELATIVE = "evals/week4/judge/f1_v2/inference_config.json"
PROVENANCE_RELATIVE = "evals/week4/judge/f1_v2/refinement_provenance.json"
MANIFEST_RELATIVE = "evals/week4/golden/f1_v1/manifest.json"
SPLIT_RELATIVE = "evals/week4/golden/f1_v1/split.json"
RUBRIC_RELATIVE = "evals/week4/golden/f1_v1/f1_rubric.json"
CONTRACT_RELATIVE = "evals/week4/golden/f1_v1/judge_contract.json"
CASES_RELATIVE = "data/local/evals/week4/golden/f1_v1/cases.jsonl"
PAYLOADS_RELATIVE = "data/local/evals/week4/golden/f1_v1/judge_payloads.jsonl"
PREDICTIONS_DIR_RELATIVE = "data/local/evals/week4/judge/f1_v2/calibration_v2"
V1_PREDICTIONS_RELATIVE = "data/local/evals/week4/judge/f1_v1/calibration_v1/predictions.json"
V1_REPORT_RELATIVE = "reports/week4_f1_judge_v1_calibration.json"
REPORT_MD_RELATIVE = "reports/week4_f1_judge_v2_calibration.md"
REPORT_JSON_RELATIVE = "reports/week4_f1_judge_v2_calibration.json"

EXPECTED_HASHES = {
    "prompt": "abf09e1eb07c4a2da859182d6a64b2c1f94124afddfcfab1b1af08f581f7ad0e",
    "inference_config": (
        "98647f8ff1b59f504b1642c96a24c1f18ec1898dc4b9f4748f47d976f11f05c1"
    ),
    "refinement_provenance": (
        "63135e4127fdd397c9c6fe08708fc50d4812fba73a518132bdd2411411e514cc"
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

V1_GENERATION = {
    "temperature": 0.0,
    "max_output_tokens": 400,
    "candidate_count": 1,
    "response_mime_type": "application/json",
    "thinking_budget": 0,
    "include_thoughts": False,
    "tools": [],
}


def load_prompt(root: Path | None = None) -> str:
    return project_path(PROMPT_RELATIVE, root).read_text(encoding="utf-8")


def load_inference_config(root: Path | None = None) -> dict[str, Any]:
    return load_json(project_path(CONFIG_RELATIVE, root))


def load_provenance(root: Path | None = None) -> dict[str, Any]:
    return load_json(project_path(PROVENANCE_RELATIVE, root))


def verify_frozen_inputs(root: Path | None = None) -> dict[str, str]:
    root = root or PROJECT_DIR
    paths = {
        "prompt": project_path(PROMPT_RELATIVE, root),
        "inference_config": project_path(CONFIG_RELATIVE, root),
        "refinement_provenance": project_path(PROVENANCE_RELATIVE, root),
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
    provenance = load_json(paths["refinement_provenance"])
    if rubric.get("rubric_id") != RUBRIC_ID:
        raise JudgeError("frozen rubric_id drifted.")
    if contract.get("contract_id") != CONTRACT_ID:
        raise JudgeError("frozen contract_id drifted.")
    if split.get("split_id") != SPLIT_ID:
        raise JudgeError("frozen split_id drifted.")
    if config.get("judge_id") != JUDGE_ID:
        raise JudgeError("frozen judge_id drifted.")
    if config.get("generation") != V1_GENERATION:
        raise JudgeError("v2 generation settings drifted from v1.")
    if config.get("model") != "gemini-3.8-flash":
        raise JudgeError("v2 model drifted from v1.")
    if provenance.get("used_validation") is not False:
        raise JudgeError("v2 provenance must not use validation.")
    if provenance.get("validation_cases_inspected"):
        raise JudgeError("v2 provenance lists validation inspection.")
    prompt = paths["prompt"].read_text(encoding="utf-8")
    if sha256_text(prompt) != observed["prompt"]:
        raise JudgeError("prompt hash drifted after read.")
    for token in ("TRACE-S", "week4_adk_preview", "week4_f1_golden"):
        if token in prompt:
            raise JudgeError(f"v2 prompt contains forbidden identifier {token}.")
    return observed


def assert_provenance_is_calibration_only(
    provenance: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> None:
    calibration_ids = {
        str(row["evaluation_id"]) for row in calibration_case_rows(manifest)
    }
    validation_ids = {
        str(row["evaluation_id"])
        for row in manifest.get("cases") or []
        if row.get("group") == "validation"
    }
    informed = provenance.get("informed_by_calibration_cases") or []
    if not informed:
        raise JudgeError("v2 provenance lists no informing calibration cases.")
    for row in informed:
        evaluation_id = str(row.get("evaluation_id") or "")
        if evaluation_id not in calibration_ids:
            raise JudgeError(
                f"provenance case {evaluation_id} is not a calibration id."
            )
        if evaluation_id in validation_ids:
            raise JudgeError(
                f"provenance case {evaluation_id} is a validation id."
            )


def build_model_request(
    payload: Mapping[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    prompt = load_prompt(root)
    config = load_inference_config(root)
    request = {
        "model": config["model"],
        "system_instruction": prompt,
        "user_text": build_user_text(payload),
        "generation": dict(config["generation"]),
        "prompt_version": config["prompt_version"],
        "prompt_sha256": sha256_text(prompt),
        "config_sha256": sha256_file(project_path(CONFIG_RELATIVE, root)),
        "turns": 1,
        "tools": [],
    }
    assert_request_has_no_leakage(request, payload)
    return request


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
        from evals.week4.f1_judge_v1 import is_stop_error

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
    except Exception as exc:
        from evals.week4.f1_judge_v1 import JudgeContractError

        if not isinstance(exc, JudgeContractError):
            raise
        record["status"] = "invalid"
        record["parsed"] = None
        record["validation_error"] = str(exc)
    return record


def verdicts_by_id(predictions: list[Mapping[str, Any]]) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for row in predictions:
        evaluation_id = str(row.get("evaluation_id"))
        parsed = row.get("parsed") or {}
        if row.get("status") == "valid" and parsed.get("verdict") in {"pass", "fail"}:
            out[evaluation_id] = parsed["verdict"]
        else:
            out[evaluation_id] = None
    return out


def compare_versions(
    *,
    v1_predictions: list[Mapping[str, Any]],
    v2_predictions: list[Mapping[str, Any]],
    labels: Mapping[str, Mapping[str, Any]],
    v1_score: Mapping[str, Any],
    v2_score: Mapping[str, Any],
) -> dict[str, Any]:
    v1_verdicts = verdicts_by_id(v1_predictions)
    v2_verdicts = verdicts_by_id(v2_predictions)
    corrected: list[dict[str, Any]] = []
    retained: list[dict[str, Any]] = []
    new_false_positives: list[dict[str, Any]] = []
    other_regressions: list[dict[str, Any]] = []
    for evaluation_id, label_row in labels.items():
        gold = label_row["f1"]
        left = v1_verdicts.get(evaluation_id)
        right = v2_verdicts.get(evaluation_id)
        item = {
            "evaluation_id": evaluation_id,
            "scenario_id": label_row.get("scenario_id"),
            "reviewed_label": gold,
            "v1_verdict": left,
            "v2_verdict": right,
        }
        if gold == "fail" and left == "pass" and right == "fail":
            corrected.append(item)
        elif gold == "fail" and right == "pass":
            retained.append(item)
        elif gold == "pass" and left == "pass" and right == "fail":
            new_false_positives.append(item)
        elif left != right:
            other_regressions.append(item)
    return {
        "held_out": False,
        "examples_reused_calibration_cases": True,
        "v1": v1_score["metrics"] | {
            "valid_n": v1_score["valid_n"],
            "invalid_n": v1_score["invalid_n"],
            "missing_n": v1_score["missing_n"],
            "prediction_coverage": v1_score["prediction_coverage"],
            "valid_response_only": v1_score["valid_response_only"],
        },
        "v2": v2_score["metrics"] | {
            "valid_n": v2_score["valid_n"],
            "invalid_n": v2_score["invalid_n"],
            "missing_n": v2_score["missing_n"],
            "prediction_coverage": v2_score["prediction_coverage"],
            "valid_response_only": v2_score["valid_response_only"],
        },
        "false_negatives_corrected": corrected,
        "false_negatives_retained": retained,
        "new_false_positives": new_false_positives,
        "other_regressions": other_regressions,
    }


def render_rate_with_counts(label: str, value: float | None, num: int, den: int) -> str:
    if value is None or den == 0:
        return f"- {label}: undefined (denominator {den})"
    return f"- {label}: {format_rate(value)} = {num}/{den}"


def render_calibration_report(
    score: Mapping[str, Any],
    run: Mapping[str, Any],
    comparison: Mapping[str, Any],
    provenance: Mapping[str, Any],
) -> str:
    metrics = score["metrics"]
    coverage_note = (
        "Rates are valid-response-only and do not cover all 20 calibration cases."
        if score["valid_response_only"]
        else "All 20 calibration outputs produced a valid judge response."
    )
    informed = ", ".join(
        f"{row['scenario_id']} `{row['evaluation_id']}`"
        for row in provenance.get("informed_by_calibration_cases") or []
    )
    v1m = comparison["v1"]
    v2m = comparison["v2"]
    return (
        "# Week 4 F1 judge v2 calibration\n\n"
        "This report scores the frozen F1 judge v2 on the calibration split "
        "only. This is the single permitted calibration refinement. The prompt "
        "was not refined after this batch. The judge is not an application or "
        "approval gate. These are not held-out results.\n\n"
        "## Scope\n\n"
        "- Judge ID: `week4_f1_judge_v2`\n"
        "- Parent: `week4_f1_judge_v1`\n"
        "- Split: calibration only (20 outputs from 10 paired scenarios)\n"
        "- Positive class: F1 failure (`fail`)\n"
        f"- Model: `{run.get('model')}`\n"
        f"- Prompt version: `{run.get('prompt_version')}`\n"
        f"- Prompt SHA-256: `{run.get('prompt_sha256')}`\n"
        f"- Inference config SHA-256: `{run.get('config_sha256')}`\n"
        "- Generation settings: identical to v1\n"
        f"- Stopped: {run.get('stopped')}\n"
        f"- Stop reason: {run.get('stop_reason') or 'none'}\n\n"
        "## Refinement provenance\n\n"
        f"- Hypothesis: {provenance.get('hypothesis')}\n"
        f"- Calibration cases that informed v2: {informed}\n"
        "- Example A (fail despite a caveat) is adapted from calibration "
        "`TRACE-S04` / `c953f67527f058d9` without identifiers in the prompt.\n"
        "- Example B (conditional pass) is adapted from calibration "
        "`TRACE-S02` / `c46d129cacb772e2` without identifiers in the prompt.\n"
        "- Prompt examples reuse calibration cases. Do not treat this batch "
        "as held-out validation.\n"
        "- Validation payloads and labels were not inspected for this "
        "refinement.\n\n"
        "## v2 confusion matrix\n\n"
        "Failure is the positive class. Invalid or missing predictions are "
        "excluded from TP/FN/TN/FP and are not coerced into pass or fail.\n\n"
        f"- TP: {metrics['TP']}\n"
        f"- FN: {metrics['FN']}\n"
        f"- TN: {metrics['TN']}\n"
        f"- FP: {metrics['FP']}\n"
        + render_rate_with_counts(
            "TPR = TP/(TP+FN)",
            metrics["TPR"],
            metrics["TP"],
            metrics["positives_in_metrics"],
        )
        + "\n"
        + render_rate_with_counts(
            "TNR = TN/(TN+FP)",
            metrics["TNR"],
            metrics["TN"],
            metrics["negatives_in_metrics"],
        )
        + "\n"
        f"- Positives represented in the rates: {metrics['positives_in_metrics']}\n"
        f"- Negatives represented in the rates: {metrics['negatives_in_metrics']}\n\n"
        "## Coverage\n\n"
        f"- Expected calibration outputs: {score['expected_n']}\n"
        f"- Valid predictions: {score['valid_n']}\n"
        f"- Invalid / contract errors: {score['invalid_n']}\n"
        f"- Missing predictions: {score['missing_n']}\n"
        f"- Prediction coverage: {score['prediction_coverage']}\n"
        f"- {coverage_note}\n\n"
        "## v1 versus v2\n\n"
        "Both rows are calibration results. Prompt examples reuse calibration "
        "cases, so v2 is not a held-out comparison.\n\n"
        "| Metric | v1 | v2 |\n"
        "|---|---|---|\n"
        f"| TP | {v1m['TP']} | {v2m['TP']} |\n"
        f"| FN | {v1m['FN']} | {v2m['FN']} |\n"
        f"| TN | {v1m['TN']} | {v2m['TN']} |\n"
        f"| FP | {v1m['FP']} | {v2m['FP']} |\n"
        f"| TPR | {format_rate(v1m['TPR'])} "
        f"({v1m['TP']}/{v1m['positives_in_metrics']}) | "
        f"{format_rate(v2m['TPR'])} "
        f"({v2m['TP']}/{v2m['positives_in_metrics']}) |\n"
        f"| TNR | {format_rate(v1m['TNR'])} "
        f"({v1m['TN']}/{v1m['negatives_in_metrics']}) | "
        f"{format_rate(v2m['TNR'])} "
        f"({v2m['TN']}/{v2m['negatives_in_metrics']}) |\n"
        f"| Valid | {v1m['valid_n']} | {v2m['valid_n']} |\n"
        f"| Contract errors | {v1m['invalid_n']} | {v2m['invalid_n']} |\n"
        f"| Missing | {v1m['missing_n']} | {v2m['missing_n']} |\n\n"
        f"- False negatives corrected: {len(comparison['false_negatives_corrected'])}\n"
        f"- False negatives retained: {len(comparison['false_negatives_retained'])}\n"
        f"- New false positives: {len(comparison['new_false_positives'])}\n"
        f"- Other regressions: {len(comparison['other_regressions'])}\n\n"
        + _change_list(
            "False negatives corrected",
            comparison["false_negatives_corrected"],
        )
        + _change_list(
            "False negatives retained",
            comparison["false_negatives_retained"],
        )
        + _change_list(
            "New false positives",
            comparison["new_false_positives"],
        )
        + _change_list(
            "Other regressions",
            comparison["other_regressions"],
        )
        + disagreement_markdown("Calibration false negatives", score["false_negatives"])
        + disagreement_markdown("Calibration false positives", score["false_positives"])
        + "## Limitations\n\n"
        "- 20 outputs from 10 paired scenarios, not 20 independent cases.\n"
        "- Only 5 labeled failures in calibration.\n"
        "- AI-assisted labels reviewed by Lily; not independent legal adjudication.\n"
        "- The judge uses the same model family as the assessed agent.\n"
        "- Calibration performance is not held-out validation.\n"
        "- Prompt examples reuse calibration cases named above.\n"
        "- This comparison does not promise improvement and does not relabel "
        "disagreements to fit the judge.\n"
        "- Validation examples were not used to design or refine this prompt.\n"
        "- This judge is not wired into the application or approval controls.\n"
    )


def _change_list(title: str, rows: list[Mapping[str, Any]]) -> str:
    if not rows:
        return f"### {title}\n\nNone.\n\n"
    parts = [f"### {title}\n"]
    for row in rows:
        parts.append(
            f"- {row.get('scenario_id')} / `{row.get('evaluation_id')}`: "
            f"reviewed {row.get('reviewed_label')}; "
            f"v1={row.get('v1_verdict')}; v2={row.get('v2_verdict')}"
        )
    return "\n".join(parts) + "\n\n"


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
    provenance = load_provenance(root)
    assert_provenance_is_calibration_only(provenance, manifest)
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
            snapshot = load_prediction_lines(predictions_jsonl)
            write_json(
                predictions_json,
                {
                    "schema": "aeacus.week4.f1_judge.predictions.v1",
                    "judge_id": JUDGE_ID,
                    "split": "calibration",
                    "labels_included": False,
                    "frozen": run_meta,
                    "predictions": snapshot,
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
    v1_predictions_path = project_path(V1_PREDICTIONS_RELATIVE, root)
    if not v1_predictions_path.is_file():
        raise JudgeError("v1 calibration predictions are required for comparison.")
    v1_bundle = load_json(v1_predictions_path)
    v1_predictions = list(v1_bundle.get("predictions") or [])
    v1_score = score_predictions(v1_predictions, labels, payloads)
    comparison = compare_versions(
        v1_predictions=v1_predictions,
        v2_predictions=predictions,
        labels=labels,
        v1_score=v1_score,
        v2_score=score,
    )
    report = {
        "schema": "aeacus.week4.f1_judge.calibration_report.v2",
        "judge_id": JUDGE_ID,
        "parent_judge_id": PARENT_JUDGE_ID,
        "split": "calibration",
        "held_out": False,
        "examples_reused_calibration_cases": True,
        "not_an_application_or_approval_gate": True,
        "prompt_refined_after_batch": False,
        "validation_inference": False,
        "run": run_meta,
        "hashes": hashes,
        "provenance": {
            "hypothesis": provenance.get("hypothesis"),
            "informed_by_calibration_cases": provenance.get(
                "informed_by_calibration_cases"
            ),
            "used_validation": provenance.get("used_validation"),
        },
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
        "comparison": comparison,
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
            "prompt examples reuse calibration cases",
        ],
    }
    write_json(project_path(REPORT_JSON_RELATIVE, root), report)
    project_path(REPORT_MD_RELATIVE, root).write_text(
        render_calibration_report(score, run_meta, comparison, provenance),
        encoding="utf-8",
    )
    write_json(
        out_dir / "scored.json",
        {
            "schema": "aeacus.week4.f1_judge.scored.v1",
            "labels_joined_after_predictions_saved": True,
            "score": score,
            "comparison": comparison,
            "run": run_meta,
        },
    )
    return report
