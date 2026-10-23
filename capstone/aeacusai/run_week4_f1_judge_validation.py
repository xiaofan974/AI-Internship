"""Run frozen F1 judges v1 and v2 on the validation split only.

Forty interleaved single-turn requests. Does not refine prompts, run the
capstone agent, retrieve sources, or open SQLite.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from evals.week4.f1_judge_v1 import LiveJudgeTransport, format_rate
from evals.week4.f1_judge_validation import PROTOCOL_ID, run_validation

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
        print("Live validation stopped: GOOGLE_API_KEY is not configured.")
        return 2

    def factory() -> LiveJudgeTransport:
        return LiveJudgeTransport(os.environ["GOOGLE_API_KEY"])

    report = run_validation(factory)
    print(f"protocol_id: {PROTOCOL_ID}")
    print("split: validation")
    print(f"attempted: {report['run']['n_attempted']}/40")
    for version in ("v1", "v2"):
        metrics = report[version]["score"]["metrics"]
        score = report[version]["score"]
        print(
            f"{version}: TP={metrics['TP']} FN={metrics['FN']} "
            f"TN={metrics['TN']} FP={metrics['FP']} "
            f"TPR={format_rate(metrics['TPR'])} "
            f"TNR={format_rate(metrics['TNR'])} "
            f"valid={score['valid_n']} invalid={score['invalid_n']} "
            f"missing={score['missing_n']}"
        )
    print(
        "changed_verdicts: "
        f"{len(report['comparison']['changed_verdicts'])}"
    )
    print(f"gate: {report['recommendation']['approval_or_release_gate']}")
    print(f"stopped: {report['run']['stopped']}")
    if report["run"]["stop_reason"]:
        print(f"stop_reason: {report['run']['stop_reason']}")
    print("report: reports/week4_f1_judge_validation.md")
    print("machine: reports/week4_f1_judge_validation.json")
    return 1 if report["run"]["stopped"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
