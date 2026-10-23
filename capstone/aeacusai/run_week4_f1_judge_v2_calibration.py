"""Run F1 judge v2 on the frozen calibration split only.

One sequential live call per calibration output. Does not call the capstone
agent, retrieve sources, open SQLite, or score validation cases.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from evals.week4.f1_judge_v1 import LiveJudgeTransport, format_rate
from evals.week4.f1_judge_v2 import JUDGE_ID, run_calibration

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parents[1]
GOOGLE_API_KEY_PLACEHOLDER = "your_google_api_key_here"


def _google_api_key_is_configured() -> bool:
    value = os.getenv("GOOGLE_API_KEY", "").strip()
    return bool(value) and value != GOOGLE_API_KEY_PLACEHOLDER


def _load_local_google_api_key() -> None:
    """Load GOOGLE_API_KEY only. Do not load OpenAI or Pinecone credentials."""
    load_dotenv(THIS_DIR / ".env")
    if _google_api_key_is_configured():
        return
    bootcamp_env = (
        REPO_ROOT
        / "ai-engineering-bootcamp"
        / "adk-multi-agent-systems"
        / ".env"
    )
    if not bootcamp_env.exists():
        return
    for raw_line in bootcamp_env.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() != "GOOGLE_API_KEY":
            continue
        value = value.strip().strip('"').strip("'")
        if value and value != GOOGLE_API_KEY_PLACEHOLDER:
            os.environ["GOOGLE_API_KEY"] = value
        break


def main() -> int:
    _load_local_google_api_key()
    if not _google_api_key_is_configured():
        print("Live calibration stopped: GOOGLE_API_KEY is not configured.")
        return 2

    def factory() -> LiveJudgeTransport:
        return LiveJudgeTransport(os.environ["GOOGLE_API_KEY"])

    report = run_calibration(factory)
    score = report["score"]
    metrics = score["metrics"]
    comparison = report["comparison"]
    print(f"judge_id: {JUDGE_ID}")
    print("split: calibration")
    print("held_out: false")
    print(f"valid: {score['valid_n']}/{score['expected_n']}")
    print(f"invalid: {score['invalid_n']}")
    print(f"missing: {score['missing_n']}")
    print(
        "v2 counts: "
        f"TP={metrics['TP']} FN={metrics['FN']} "
        f"TN={metrics['TN']} FP={metrics['FP']}"
    )
    print(f"v2 TPR: {format_rate(metrics['TPR'])}")
    print(f"v2 TNR: {format_rate(metrics['TNR'])}")
    print(
        "v1 counts: "
        f"TP={comparison['v1']['TP']} FN={comparison['v1']['FN']} "
        f"TN={comparison['v1']['TN']} FP={comparison['v1']['FP']}"
    )
    print(f"FN corrected: {len(comparison['false_negatives_corrected'])}")
    print(f"FN retained: {len(comparison['false_negatives_retained'])}")
    print(f"new FP: {len(comparison['new_false_positives'])}")
    if score["valid_response_only"]:
        print("rates: valid-response-only; they do not cover all 20 cases.")
    print(f"stopped: {report['run']['stopped']}")
    if report["run"]["stop_reason"]:
        print(f"stop_reason: {report['run']['stop_reason']}")
    print("report: reports/week4_f1_judge_v2_calibration.md")
    print("machine: reports/week4_f1_judge_v2_calibration.json")
    return 1 if report["run"]["stopped"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
