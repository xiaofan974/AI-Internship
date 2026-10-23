"""Held-out validation of frozen F1 judges v1 and v2.

Does not refine prompts, run the capstone agent, retrieve sources, or open
SQLite. Labels are joined only after both versions' predictions are saved.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

from evals.week4 import f1_judge_v1 as v1
from evals.week4 import f1_judge_v2 as v2
from evals.week4.f1_judge_v1 import (
    PROJECT_DIR,
    JudgeError,
    JudgeStopError,
    approved_payload,
    association_map,
    disagreement_markdown,
    format_rate,
    load_json,
    load_jsonl_by_id,
    load_manifest,
    load_prediction_lines,
    load_rubric,
    load_split,
    persist_prediction_line,
    project_path,
    score_predictions,
    sha256_file,
    utc_now,
    write_json,
)

PROTOCOL_ID = "week4_f1_judge_validation_v1"
PROTOCOL_RELATIVE = "evals/week4/judge/validation_v1/protocol.json"
PREDICTIONS_DIR_RELATIVE = "data/local/evals/week4/judge/validation_v1"
REPORT_MD_RELATIVE = "reports/week4_f1_judge_validation.md"
REPORT_JSON_RELATIVE = "reports/week4_f1_judge_validation.json"

HASH_PATHS = {
    "protocol": PROTOCOL_RELATIVE,
    "v1_prompt": v1.PROMPT_RELATIVE,
    "v1_inference_config": v1.CONFIG_RELATIVE,
    "v2_prompt": v2.PROMPT_RELATIVE,
    "v2_inference_config": v2.CONFIG_RELATIVE,
    "v2_refinement_provenance": v2.PROVENANCE_RELATIVE,
    "manifest": "evals/week4/golden/f1_v1/manifest.json",
    "split": "evals/week4/golden/f1_v1/split.json",
    "f1_rubric": "evals/week4/golden/f1_v1/f1_rubric.json",
    "judge_contract": "evals/week4/golden/f1_v1/judge_contract.json",
    "parent_f2_pointer": "evals/week4/golden/f1_v1/parent_f2_pointer.json",
    "cases_jsonl": "data/local/evals/week4/golden/f1_v1/cases.jsonl",
    "judge_payloads_jsonl": "data/local/evals/week4/golden/f1_v1/judge_payloads.jsonl",
    "checkers": "evals/week4/checkers.py",
    "annotations_v1": "evals/week4/annotations_v1.json",
    "annotations_f1_v2": "evals/week4/annotations_f1_v2.json",
    "taxonomy": "evals/week4/taxonomy_v1.json",
    "scenarios": "evals/week4/scenarios_v1.json",
}

EXPECTED_HASHES = {
    "protocol": "344d963698f6eb9cf95dac8e93557049947a920d6177125b645036b5b3afb8b8",
    "v1_prompt": "27e571fcc3830852133bed275fd00a272b41f8fabfc2d8d30e7de05e17a5c700",
    "v1_inference_config": (
        "358ad788ff2be762aaf5083114bff3cf93db1c08b8df8f15b3b7db76b6defc0c"
    ),
    "v2_prompt": "abf09e1eb07c4a2da859182d6a64b2c1f94124afddfcfab1b1af08f581f7ad0e",
    "v2_inference_config": (
        "98647f8ff1b59f504b1642c96a24c1f18ec1898dc4b9f4748f47d976f11f05c1"
    ),
    "v2_refinement_provenance": (
        "63135e4127fdd397c9c6fe08708fc50d4812fba73a518132bdd2411411e514cc"
    ),
    "manifest": "262ce9b1401be57dd61ff8f0b43c08b6cea9d44008e030a816acacad78669963",
    "split": "a57e8cac7d357b67f98a04f5b83a65da39a5cc8f54b6c26ecad3ae6596e54d30",
    "f1_rubric": "1db86276750dab8e6f93c34ef429482065eff5373a6d6e72b4c43625999a7502",
    "judge_contract": (
        "91aae84736794d980e37251173dfc98b999147086ef56e8142224f369ec5a480"
    ),
    "parent_f2_pointer": (
        "1db39213879580dfd1618679835d85396a6494f32105b53867f9d93594843eea"
    ),
    "cases_jsonl": (
        "152adaebbcd9c51c83bbdfcbf37bab694eeb4f9668c226563c9f69c652a0c15c"
    ),
    "judge_payloads_jsonl": (
        "1f9abd172f98692b3d62a071664caf7be3347fbd23a3cb2d5b961bf234d8f3f6"
    ),
    "checkers": "330fce7b22fc3d7ff140839dcc20dd811ee6ffef3da00111134674508a484b33",
    "annotations_v1": (
        "50bde98943fc656a598e2e449bf6cfaec73387cb04d3f05adadf4a3c90f489ee"
    ),
    "annotations_f1_v2": (
        "c382664896c8b909654dd1628fcb1a61fd1ce75b6be35cf3cd5484e4970a819a"
    ),
    "taxonomy": "336f5f3e6fe9ab7042b83bf1869161be1e86aaee4c718d9e9b0738f7808d7718",
    "scenarios": "02aeb6ae8c7af29864d493c08621ba048c73680e89cd34e466ebe46cd86b2070",
}


def load_protocol(root: Path | None = None) -> dict[str, Any]:
    return load_json(project_path(PROTOCOL_RELATIVE, root))


def verify_frozen_artifacts(root: Path | None = None) -> dict[str, str]:
    root = root or PROJECT_DIR
    observed: dict[str, str] = {}
    missing = [
        key
        for key, relative in HASH_PATHS.items()
        if not project_path(relative, root).is_file()
    ]
    if missing:
        raise JudgeError(f"required frozen artifacts missing: {missing}")
    for key, relative in HASH_PATHS.items():
        digest = sha256_file(project_path(relative, root))
        expected = EXPECTED_HASHES[key]
        if digest != expected:
            raise JudgeError(
                f"{key} hash mismatch: expected {expected}, observed {digest}."
            )
        observed[key] = digest
    v1.verify_frozen_inputs(root)
    v2.verify_frozen_inputs(root)
    v1_config = v1.load_inference_config(root)
    v2_config = v2.load_inference_config(root)
    if v1_config["generation"] != v2_config["generation"]:
        raise JudgeError("v1 and v2 generation settings are not identical.")
    if v1_config["model"] != v2_config["model"]:
        raise JudgeError("v1 and v2 models are not identical.")
    return observed


def validation_case_rows(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = [
        dict(row)
        for row in manifest.get("cases") or []
        if row.get("group") == "validation"
    ]
    if len(rows) != 20:
        raise JudgeError(f"expected 20 validation cases, found {len(rows)}.")
    return rows


def confirm_validation_split(
    manifest: Mapping[str, Any],
    split: Mapping[str, Any],
) -> dict[str, Any]:
    validation = validation_case_rows(manifest)
    calibration = [
        row
        for row in manifest.get("cases") or []
        if row.get("group") == "calibration"
    ]
    validation_scenarios = {row["scenario_id"] for row in validation}
    calibration_scenarios = {row["scenario_id"] for row in calibration}
    overlap = sorted(validation_scenarios & calibration_scenarios)
    if overlap:
        raise JudgeError(f"validation overlaps calibration scenarios: {overlap}")
    if validation_scenarios != set(split.get("validation_scenario_ids") or []):
        raise JudgeError("validation scenarios drifted from frozen split.")
    if calibration_scenarios != set(split.get("calibration_scenario_ids") or []):
        raise JudgeError("calibration scenarios drifted from frozen split.")
    fails = sum(1 for row in validation if row.get("f1") == "fail")
    passes = sum(1 for row in validation if row.get("f1") == "pass")
    if fails != 5 or passes != 15:
        raise JudgeError(
            f"validation label balance drifted: fail={fails} pass={passes}."
        )
    if len(validation_scenarios) != 10:
        raise JudgeError("validation must contain 10 scenario groups.")
    return {
        "n_outputs": len(validation),
        "n_scenario_groups": len(validation_scenarios),
        "fail": fails,
        "pass": passes,
        "overlap": overlap,
        "evaluation_ids": [row["evaluation_id"] for row in validation],
    }


def derive_request_schedule(evaluation_ids: list[str]) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    seq = 1
    for index, evaluation_id in enumerate(evaluation_ids):
        first, second = ("v1", "v2") if index % 2 == 0 else ("v2", "v1")
        for version in (first, second):
            requests.append(
                {
                    "seq": seq,
                    "evaluation_id": evaluation_id,
                    "judge_id": f"week4_f1_judge_{version}",
                    "version": version,
                }
            )
            seq += 1
    return requests


def verify_protocol(
    protocol: Mapping[str, Any],
    evaluation_ids: list[str],
) -> None:
    if protocol.get("protocol_id") != PROTOCOL_ID:
        raise JudgeError("validation protocol_id drifted.")
    expected = derive_request_schedule(evaluation_ids)
    if protocol.get("requests") != expected:
        raise JudgeError("frozen request schedule drifted from the interleave rule.")
    if protocol.get("n_requests") != 40 or len(expected) != 40:
        raise JudgeError("validation protocol must contain 40 requests.")
    if protocol.get("interleave", {}).get("retries") != 0:
        raise JudgeError("validation protocol must forbid retries.")
    serialized = str(protocol.get("requests"))
    if '"f1"' in serialized:
        raise JudgeError("protocol requests include labels.")


def select_validation_jobs(
    manifest: Mapping[str, Any],
    payloads: Mapping[str, Mapping[str, Any]],
    *,
    rubric: Mapping[str, Any],
    split: Mapping[str, Any],
) -> list[dict[str, Any]]:
    validation_ids = {str(row["evaluation_id"]) for row in validation_case_rows(manifest)}
    calibration_ids = {
        str(row["evaluation_id"])
        for row in manifest.get("cases") or []
        if row.get("group") == "calibration"
    }
    calibration_scenarios = set(split.get("calibration_scenario_ids") or [])
    jobs: list[dict[str, Any]] = []
    for row in validation_case_rows(manifest):
        evaluation_id = str(row["evaluation_id"])
        if evaluation_id in calibration_ids or row.get("group") != "validation":
            raise JudgeError(f"{evaluation_id} is not a validation case.")
        if row.get("scenario_id") in calibration_scenarios:
            raise JudgeError(
                f"{evaluation_id} scenario {row.get('scenario_id')} is calibration."
            )
        payload = payloads.get(evaluation_id)
        if payload is None:
            raise JudgeError(f"no payload for validation id {evaluation_id}.")
        incoming = payload.get("f1_rubric") or {}
        for key in ("rubric_id", "category_id", "title", "positive_means"):
            if incoming.get(key) != rubric.get(key):
                raise JudgeError(f"payload rubric field {key} does not match freeze.")
        jobs.append(
            {
                "evaluation_id": evaluation_id,
                "payload": approved_payload(payload),
            }
        )
    extra = set(payloads) - validation_ids
    if extra:
        raise JudgeError(f"non-validation payloads supplied to runner: {sorted(extra)}")
    if len(jobs) != 20:
        raise JudgeError(f"validation runner requires 20 jobs, found {len(jobs)}.")
    return jobs


def predict_for_version(
    version: str,
    transport: Any,
    job: Mapping[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    if version == "v1":
        record = v1.predict_one(transport, job, root=root)
    elif version == "v2":
        record = v2.predict_one(transport, job, root=root)
    else:
        raise JudgeError(f"unknown judge version {version}.")
    record["version"] = version
    record["judge_id"] = f"week4_f1_judge_{version}"
    return record


def request_has_forbidden_context(request: Mapping[str, Any]) -> None:
    blob = f"{request.get('system_instruction')} {request.get('user_text')}"
    for token in (
        "week4_f1_judge_v1_calibration",
        "week4_f1_judge_v2_calibration",
        "false_negatives_corrected",
        "held-out validation",
    ):
        if token in blob:
            raise JudgeError(f"calibration or comparison context leaked: {token}")


def paired_validation_comparison(
    *,
    v1_score: Mapping[str, Any],
    v2_score: Mapping[str, Any],
    labels: Mapping[str, Mapping[str, Any]],
    v1_predictions: list[Mapping[str, Any]],
    v2_predictions: list[Mapping[str, Any]],
) -> dict[str, Any]:
    v1_verdicts = v2.verdicts_by_id(v1_predictions)
    v2_verdicts = v2.verdicts_by_id(v2_predictions)
    newly_detected: list[dict[str, Any]] = []
    newly_missed: list[dict[str, Any]] = []
    newly_flagged: list[dict[str, Any]] = []
    newly_corrected_pass: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
    for evaluation_id, label_row in labels.items():
        gold = label_row["f1"]
        left = v1_verdicts.get(evaluation_id)
        right = v2_verdicts.get(evaluation_id)
        item = {
            "evaluation_id": evaluation_id,
            "scenario_id": label_row.get("scenario_id"),
            "case_id": label_row.get("case_id"),
            "reviewed_label": gold,
            "v1_verdict": left,
            "v2_verdict": right,
        }
        if left != right:
            changed.append(item)
        if gold == "fail" and left == "pass" and right == "fail":
            newly_detected.append(item)
        elif gold == "fail" and left == "fail" and right == "pass":
            newly_missed.append(item)
        elif gold == "pass" and left == "pass" and right == "fail":
            newly_flagged.append(item)
        elif gold == "pass" and left == "fail" and right == "pass":
            newly_corrected_pass.append(item)
    return {
        "held_out_from_refinement": True,
        "unseen_capstone_scenarios": False,
        "mixed_with_calibration": False,
        "statistical_significance_claimed": False,
        "v1": _score_summary(v1_score),
        "v2": _score_summary(v2_score),
        "failures_newly_detected": newly_detected,
        "failures_newly_missed": newly_missed,
        "passes_newly_flagged_incorrectly": newly_flagged,
        "passes_newly_corrected": newly_corrected_pass,
        "changed_verdicts": changed,
    }


def _score_summary(score: Mapping[str, Any]) -> dict[str, Any]:
    metrics = score["metrics"]
    return {
        "TP": metrics["TP"],
        "FN": metrics["FN"],
        "TN": metrics["TN"],
        "FP": metrics["FP"],
        "TPR": metrics["TPR"],
        "TNR": metrics["TNR"],
        "positives_in_metrics": metrics["positives_in_metrics"],
        "negatives_in_metrics": metrics["negatives_in_metrics"],
        "valid_n": score["valid_n"],
        "invalid_n": score["invalid_n"],
        "missing_n": score["missing_n"],
        "attempted_n": score["valid_n"] + score["invalid_n"],
        "prediction_coverage": score["prediction_coverage"],
        "valid_response_only": score["valid_response_only"],
    }


def recommend_use(comparison: Mapping[str, Any]) -> dict[str, Any]:
    v1m = comparison["v1"]
    v2m = comparison["v2"]
    better = None
    if (
        v2m["TPR"] is not None
        and v1m["TPR"] is not None
        and v2m["TNR"] is not None
        and v1m["TNR"] is not None
    ):
        if v2m["TPR"] > v1m["TPR"] and v2m["TNR"] >= v1m["TNR"]:
            better = "v2"
        elif v1m["TPR"] > v2m["TPR"] and v1m["TNR"] >= v2m["TNR"]:
            better = "v1"
    if (v1m["TP"] + v2m["TP"]) == 0:
        use = (
            "Neither frozen judge detected a validation F1 failure. Use them "
            "only as an offline research record, not as a detector."
        )
    elif (v1m["FP"] + v2m["FP"]) > 0:
        use = (
            "At least one version flagged a reviewed pass. Do not use either "
            "judge to auto-reject or block a review."
        )
    elif better:
        use = (
            f"On this 20-output validation set, {better} detected more reviewed "
            "F1 failures without adding false positives. That is a diagnostic "
            "signal only. Keep the judge offline as a second look for "
            "reviewers, not a gate."
        )
    else:
        use = (
            "The two versions do not give a clean dominance pattern on this "
            "set. Keep both as frozen research artifacts and continue human "
            "review of F1."
        )
    return {
        "approval_or_release_gate": False,
        "automatic_qualification": False,
        "statistical_significance": False,
        "preferred_version_on_this_set": better,
        "appropriate_use": use,
    }


def _excerpt(row: Mapping[str, Any]) -> str:
    excerpt = row.get("excerpt") or ""
    if excerpt:
        return excerpt
    answer = str(row.get("answer") or "")
    return answer[:280] + ("…" if len(answer) > 280 else "")


def _disagreement_rows(score: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    rows = []
    for row in score[key]:
        rows.append(
            {
                "evaluation_id": row["evaluation_id"],
                "scenario_id": row["scenario_id"],
                "input": row["input"],
                "exact_answer_excerpt": _excerpt(row),
                "reviewed_label": row["reviewed_label"],
                "judge_verdict": row["judge_verdict"],
                "reason": row["reason"],
            }
        )
    return rows


def render_version_section(title: str, score: Mapping[str, Any]) -> str:
    metrics = score["metrics"]
    coverage_note = (
        "Rates are valid-response-only and do not cover all 20 validation cases."
        if score["valid_response_only"]
        else "All 20 validation outputs produced a valid judge response."
    )
    tpr_den = metrics["positives_in_metrics"]
    tnr_den = metrics["negatives_in_metrics"]
    return (
        f"## {title}\n\n"
        "Positive class: F1 failure (`fail`). Invalid or missing predictions "
        "are excluded from TP/FN/TN/FP.\n\n"
        f"- TP: {metrics['TP']}\n"
        f"- FN: {metrics['FN']}\n"
        f"- TN: {metrics['TN']}\n"
        f"- FP: {metrics['FP']}\n"
        f"- TPR = TP/(TP+FN): {format_rate(metrics['TPR'])} "
        f"= {metrics['TP']}/{tpr_den}\n"
        f"- TNR = TN/(TN+FP): {format_rate(metrics['TNR'])} "
        f"= {metrics['TN']}/{tnr_den}\n"
        f"- Attempted predictions: {score['valid_n'] + score['invalid_n']}\n"
        f"- Valid: {score['valid_n']}\n"
        f"- Invalid / contract errors: {score['invalid_n']}\n"
        f"- Missing: {score['missing_n']}\n"
        f"- Prediction coverage: {score['prediction_coverage']}\n"
        f"- {coverage_note}\n\n"
        + disagreement_markdown(
            f"{title} false negatives", score["false_negatives"]
        )
        + disagreement_markdown(
            f"{title} false positives", score["false_positives"]
        )
    )


def _change_list(title: str, rows: list[Mapping[str, Any]]) -> str:
    if not rows:
        return f"### {title}\n\nNone.\n\n"
    parts = [f"### {title}\n"]
    for row in rows:
        parts.append(
            f"- {row.get('scenario_id')} / `{row.get('evaluation_id')}` "
            f"(`{row.get('case_id')}`): reviewed {row.get('reviewed_label')}; "
            f"v1={row.get('v1_verdict')}; v2={row.get('v2_verdict')}"
        )
    return "\n".join(parts) + "\n\n"


def render_validation_report(
    *,
    v1_score: Mapping[str, Any],
    v2_score: Mapping[str, Any],
    comparison: Mapping[str, Any],
    recommendation: Mapping[str, Any],
    run: Mapping[str, Any],
) -> str:
    return (
        "# Week 4 F1 judge validation\n\n"
        "Frozen judges v1 and v2 were scored on the validation split only. "
        "Prompts were not refined after this batch. This evaluation does not "
        "automatically qualify either judge as an approval or release gate. "
        "Do not mix these figures with calibration scores.\n\n"
        "## Protocol\n\n"
        f"- Protocol ID: `{PROTOCOL_ID}`\n"
        f"- Requests: {run.get('n_attempted')} attempted / 40 scheduled\n"
        "- Interleave: even validation index v1 then v2; odd index v2 then v1\n"
        f"- Stopped: {run.get('stopped')}\n"
        f"- Stop reason: {run.get('stop_reason') or 'none'}\n"
        f"- v1 prompt SHA-256: `{run.get('v1_prompt_sha256')}`\n"
        f"- v2 prompt SHA-256: `{run.get('v2_prompt_sha256')}`\n"
        "- Generation settings: identical across versions\n\n"
        + render_version_section("Judge v1", v1_score)
        + render_version_section("Judge v2", v2_score)
        + "## Paired comparison\n\n"
        "These counts are validation only. They are not a combined "
        "calibration-plus-validation score and are not statistically "
        "significant.\n\n"
        f"- Failures newly detected by v2: {len(comparison['failures_newly_detected'])}\n"
        f"- Failures newly missed by v2: {len(comparison['failures_newly_missed'])}\n"
        f"- Passes newly flagged incorrectly by v2: "
        f"{len(comparison['passes_newly_flagged_incorrectly'])}\n"
        f"- Passes newly corrected by v2: {len(comparison['passes_newly_corrected'])}\n"
        f"- Changed verdicts: {len(comparison['changed_verdicts'])}\n\n"
        + _change_list(
            "Failures newly detected", comparison["failures_newly_detected"]
        )
        + _change_list(
            "Failures newly missed", comparison["failures_newly_missed"]
        )
        + _change_list(
            "Passes newly flagged incorrectly",
            comparison["passes_newly_flagged_incorrectly"],
        )
        + _change_list(
            "Passes newly corrected", comparison["passes_newly_corrected"]
        )
        + _change_list("Every changed verdict", comparison["changed_verdicts"])
        + "## Recommended use\n\n"
        f"- Approval or release gate: {recommendation['approval_or_release_gate']}\n"
        f"- Automatic qualification: {recommendation['automatic_qualification']}\n"
        f"- Preferred version on this set: "
        f"{recommendation['preferred_version_on_this_set'] or 'none'}\n"
        f"- {recommendation['appropriate_use']}\n\n"
        "## Limitations\n\n"
        "- Validation comprises 20 outputs from 10 paired scenarios.\n"
        "- Only 5 labeled failures: one detection changes TPR by 20 percentage points.\n"
        "- Cases were held out from judge refinement, not unseen capstone scenarios.\n"
        "- Labels are AI-assisted and reviewed by Lily.\n"
        "- Judge and agent use the same model family.\n"
        "- No statistical significance or general reliability is claimed.\n"
        "- This evaluation does not make either judge an application or approval gate.\n"
    )


def run_validation(
    transport_factory: Callable[[], Any],
    *,
    root: Path | None = None,
    load_labels: bool = False,
) -> dict[str, Any]:
    if load_labels:
        raise JudgeError("labels must not be loaded before predictions are saved.")
    root = root or PROJECT_DIR
    hashes = verify_frozen_artifacts(root)
    manifest = load_manifest(root)
    split = load_split(root)
    rubric = load_rubric(root)
    protocol = load_protocol(root)
    split_info = confirm_validation_split(manifest, split)
    verify_protocol(protocol, split_info["evaluation_ids"])
    validation_rows = validation_case_rows(manifest)
    validation_ids = {str(row["evaluation_id"]) for row in validation_rows}
    payloads = load_jsonl_by_id(
        project_path("data/local/evals/week4/golden/f1_v1/judge_payloads.jsonl", root),
        validation_ids,
    )
    jobs = select_validation_jobs(manifest, payloads, rubric=rubric, split=split)
    jobs_by_id = {job["evaluation_id"]: job for job in jobs}
    out_dir = project_path(PREDICTIONS_DIR_RELATIVE, root)
    requests_jsonl = out_dir / "requests.jsonl"
    predictions_json = out_dir / "predictions.json"
    freeze_path = out_dir / "freeze.json"
    if not freeze_path.is_file():
        write_json(
            freeze_path,
            {
                "schema": "aeacus.week4.f1_judge.validation_freeze.v1",
                "protocol_id": PROTOCOL_ID,
                "frozen_before_inference": True,
                "hashes": hashes,
                "frozen_at": utc_now(),
            },
        )
    existing = load_prediction_lines(requests_jsonl)
    done = {
        (str(row.get("evaluation_id")), str(row.get("version")))
        for row in existing
        if row.get("status") != "stopped"
    }
    pending = [
        item
        for item in protocol["requests"]
        if (item["evaluation_id"], item["version"]) not in done
    ]
    run_meta: dict[str, Any] = {
        "protocol_id": PROTOCOL_ID,
        "split": "validation",
        "n_scheduled": 40,
        "n_existing": len(existing),
        "n_pending": len(pending),
        "stopped": False,
        "stop_reason": None,
        "started_at": utc_now(),
        "v1_prompt_sha256": hashes["v1_prompt"],
        "v2_prompt_sha256": hashes["v2_prompt"],
        "v1_config_sha256": hashes["v1_inference_config"],
        "v2_config_sha256": hashes["v2_inference_config"],
    }
    if pending:
        transport = transport_factory()
        for item in pending:
            if sha256_file(project_path(v1.PROMPT_RELATIVE, root)) != hashes["v1_prompt"]:
                raise JudgeError("v1 prompt changed during validation.")
            if sha256_file(project_path(v2.PROMPT_RELATIVE, root)) != hashes["v2_prompt"]:
                raise JudgeError("v2 prompt changed during validation.")
            job = jobs_by_id[item["evaluation_id"]]
            request = (
                v1.build_model_request(job["payload"], root=root)
                if item["version"] == "v1"
                else v2.build_model_request(job["payload"], root=root)
            )
            request_has_forbidden_context(request)
            try:
                record = predict_for_version(
                    item["version"], transport, job, root=root
                )
            except JudgeStopError as exc:
                run_meta["stopped"] = True
                run_meta["stop_reason"] = str(exc)
                persist_prediction_line(
                    requests_jsonl,
                    {
                        "seq": item["seq"],
                        "evaluation_id": item["evaluation_id"],
                        "version": item["version"],
                        "judge_id": item["judge_id"],
                        "status": "stopped",
                        "provider_error": str(exc),
                        "parsed": None,
                        "raw_response": None,
                    },
                )
                break
            record["seq"] = item["seq"]
            persist_prediction_line(requests_jsonl, record)
            snapshot = load_prediction_lines(requests_jsonl)
            write_json(
                predictions_json,
                {
                    "schema": "aeacus.week4.f1_judge.validation_predictions.v1",
                    "protocol_id": PROTOCOL_ID,
                    "split": "validation",
                    "labels_included": False,
                    "predictions": snapshot,
                },
            )
    predictions = load_prediction_lines(requests_jsonl)
    write_json(
        predictions_json,
        {
            "schema": "aeacus.week4.f1_judge.validation_predictions.v1",
            "protocol_id": PROTOCOL_ID,
            "split": "validation",
            "labels_included": False,
            "predictions": predictions,
        },
    )
    run_meta["ended_at"] = utc_now()
    run_meta["n_attempted"] = len(predictions)
    v1_predictions = [row for row in predictions if row.get("version") == "v1"]
    v2_predictions = [row for row in predictions if row.get("version") == "v2"]
    write_json(
        out_dir / "v1_predictions.json",
        {
            "judge_id": "week4_f1_judge_v1",
            "split": "validation",
            "labels_included": False,
            "predictions": v1_predictions,
        },
    )
    write_json(
        out_dir / "v2_predictions.json",
        {
            "judge_id": "week4_f1_judge_v2",
            "split": "validation",
            "labels_included": False,
            "predictions": v2_predictions,
        },
    )
    labels = association_map(validation_rows)
    v1_score = score_predictions(v1_predictions, labels, payloads)
    v2_score = score_predictions(v2_predictions, labels, payloads)
    comparison = paired_validation_comparison(
        v1_score=v1_score,
        v2_score=v2_score,
        labels=labels,
        v1_predictions=v1_predictions,
        v2_predictions=v2_predictions,
    )
    recommendation = recommend_use(comparison)
    report = {
        "schema": "aeacus.week4.f1_judge.validation_report.v1",
        "protocol_id": PROTOCOL_ID,
        "split": "validation",
        "held_out_from_refinement": True,
        "unseen_capstone_scenarios": False,
        "mixed_with_calibration": False,
        "not_an_application_or_approval_gate": True,
        "prompt_refined_after_batch": False,
        "run": run_meta,
        "hashes": hashes,
        "split_check": {
            key: split_info[key]
            for key in ("n_outputs", "n_scenario_groups", "fail", "pass", "overlap")
        },
        "v1": {
            "score": {
                key: v1_score[key]
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
            "false_negatives": _disagreement_rows(v1_score, "false_negatives"),
            "false_positives": _disagreement_rows(v1_score, "false_positives"),
        },
        "v2": {
            "score": {
                key: v2_score[key]
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
            "false_negatives": _disagreement_rows(v2_score, "false_negatives"),
            "false_positives": _disagreement_rows(v2_score, "false_positives"),
        },
        "comparison": comparison,
        "recommendation": recommendation,
        "limitations": [
            "Validation comprises 20 outputs from 10 paired scenarios.",
            "Only 5 labeled failures: one detection changes TPR by 20 percentage points.",
            "Cases were held out from judge refinement, not unseen capstone scenarios.",
            "Labels are AI-assisted and reviewed by Lily.",
            "Judge and agent use the same model family.",
        ],
    }
    write_json(project_path(REPORT_JSON_RELATIVE, root), report)
    project_path(REPORT_MD_RELATIVE, root).write_text(
        render_validation_report(
            v1_score=v1_score,
            v2_score=v2_score,
            comparison=comparison,
            recommendation=recommendation,
            run=run_meta,
        ),
        encoding="utf-8",
    )
    write_json(
        out_dir / "scored.json",
        {
            "schema": "aeacus.week4.f1_judge.validation_scored.v1",
            "labels_joined_after_predictions_saved": True,
            "v1": v1_score,
            "v2": v2_score,
            "comparison": comparison,
            "recommendation": recommendation,
            "run": run_meta,
        },
    )
    return report
