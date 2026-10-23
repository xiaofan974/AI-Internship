"""Offline Week 4 taxonomy freeze and deterministic checker evaluation."""

from __future__ import annotations

from evals.week4.codify import evaluate_baseline, write_outputs
from evals.week4.checkers import DEFERRED_DATE_CHECKER_ID, S19_BUDGET_CHECKER_ID


def main() -> int:
    payload = evaluate_baseline()
    results_path, report_path = write_outputs(payload)
    human = payload["human_reviewed_taxonomy"]
    deferred = payload["deterministic_assertions"][DEFERRED_DATE_CHECKER_ID]
    budget = payload["deterministic_assertions"][S19_BUDGET_CHECKER_ID]
    print(f"source_sha256: {payload['source']['sha256']}")
    print("source_sha256_verified: true")
    print(
        "human_taxonomy: "
        f"F1={human['category_failures']['F1']} "
        f"F2={human['category_failures']['F2']} "
        f"F3={human['category_failures']['F3']} "
        f"F4={human['category_failures']['F4']} "
        f"distinct_failing={human['distinct_failing_traces']}"
    )
    print(
        "deferred_date_qualifications: "
        f"applicable={deferred['applicable']} pass={deferred['pass']} "
        f"fail={deferred['fail']} ids={deferred['fail_ids']}"
    )
    print(
        "s19_retrieval_budget: "
        f"applicable={budget['applicable']} pass={budget['pass']} "
        f"fail={budget['fail']} ids={budget['fail_ids']}"
    )
    print(
        "disagreements_with_reviewed_labels: "
        f"{len(payload['disagreements_with_reviewed_labels'])}"
    )
    print(f"results: {results_path}")
    print(f"report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
