"""CLI for the Week 4 ADK classification-preview baseline."""

from __future__ import annotations

import argparse
import asyncio
import inspect
import sys
from pathlib import Path

from aeacus_agent.agent import MODEL, aeacus_review_agent
from aeacus_agent.context_preview import preview_classification_search
from aeacus_agent.preview_agent import aeacus_preview_agent
from aeacus_agent.retrieval import search_legal_sources
from evals.week4.baseline import (
    BASELINE_ID,
    CANDIDATE_F1_ID,
    BaselineError,
    BaselinePaths,
    DriftError,
    DuplicateAttemptError,
    SystemicStop,
    candidate_parent_extra,
    collect_batch,
    freeze_baseline,
    parse_scenario_selector,
    verify_no_drift,
)
from run_classification_preview import _google_api_key_is_configured
from run_review import MAX_LLM_CALLS, RUN_TIMEOUT_SECONDS


def _offline_configuration_check() -> None:
    assert aeacus_preview_agent.name == "aeacus_preview_agent"
    assert aeacus_preview_agent.model == MODEL
    assert len(aeacus_preview_agent.tools) == 1
    assert aeacus_preview_agent.tools[0] is preview_classification_search
    assert getattr(aeacus_preview_agent, "sub_agents", []) == []
    assert list(inspect.signature(preview_classification_search).parameters) == [
        "query"
    ]
    assert aeacus_review_agent.tools[0] is search_legal_sources
    print("offline configuration check: passed")
    print("preview agent tools: ['preview_classification_search']")
    print("pinecone agent tools unchanged: ['search_legal_sources']")
    print(f"limits: max_llm_calls={MAX_LLM_CALLS} timeout_seconds={RUN_TIMEOUT_SECONDS}")


def _paths(args: argparse.Namespace) -> BaselinePaths:
    return BaselinePaths(baseline_id=args.id)


def _add_id_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--id",
        default=BASELINE_ID,
        help=(
            "Collection identity. Defaults to the original baseline "
            f"{BASELINE_ID}. Use {CANDIDATE_F1_ID} for the F1 candidate."
        ),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Freeze and collect the Week 4 ADK preview TRACE baseline."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    freeze = sub.add_parser("freeze", help="Write a frozen collection manifest once.")
    _add_id_argument(freeze)
    freeze.add_argument(
        "--parent",
        default=None,
        help=(
            "Optional parent collection ID. Records an intentional instruction "
            "change and refuses freeze if model, tools, corpus, generation, "
            "limits, or the scenario-file hash differ."
        ),
    )
    freeze.add_argument(
        "--instruction-diff",
        default=None,
        help="Optional path to the saved instruction diff, stored on the manifest.",
    )
    run = sub.add_parser("run", help="Collect selected scenarios sequentially.")
    _add_id_argument(run)
    run.add_argument(
        "--scenarios",
        required=True,
        help="Required selection, for example TRACE-S01:TRACE-S05.",
    )
    run.add_argument("--phase", required=True, help="Baseline phase label, for example batch1.")
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="Select scenarios and verify freeze without provider calls.",
    )
    return parser


def _print_batch(result) -> None:
    print(f"baseline_id: {result.baseline_id}")
    print(f"phase: {result.phase}")
    print(f"dry_run: {result.dry_run}")
    print(f"selected: {', '.join(result.selected)}")
    for attempt in result.attempts:
        print(
            f"{attempt.scenario_id} run_id={attempt.run_id} "
            f"status={attempt.status} capture_saved={attempt.capture_saved} "
            f"elapsed_ms={attempt.elapsed_ms}"
        )
    if result.stopped:
        print(f"batch stopped: {result.stop_reason}")


async def _run(args: argparse.Namespace) -> int:
    paths = _paths(args)
    selected = parse_scenario_selector(args.scenarios)
    _offline_configuration_check()
    verify_no_drift(paths)
    if args.dry_run:
        result = await collect_batch(
            paths=paths,
            selected_ids=selected,
            phase=args.phase,
            dry_run=True,
        )
        print("dry-run: zero provider calls")
        _print_batch(result)
        return 0
    if not _google_api_key_is_configured():
        print("Live collection stopped: GOOGLE_API_KEY is not configured.")
        return 2
    try:
        result = await collect_batch(
            paths=paths,
            selected_ids=selected,
            phase=args.phase,
            dry_run=False,
        )
    except DuplicateAttemptError as exc:
        print(f"duplicate attempt blocked: {exc}")
        return 3
    except DriftError as exc:
        print(f"drift detected: {exc}")
        return 4
    except SystemicStop as exc:
        print(f"systemic stop: {exc}")
        return 5
    _print_batch(result)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "freeze":
            _offline_configuration_check()
            paths = _paths(args)
            extra = None
            if args.parent:
                extra = candidate_parent_extra(
                    paths,
                    BaselinePaths(baseline_id=args.parent),
                    instruction_diff_path=(
                        Path(args.instruction_diff) if args.instruction_diff else None
                    ),
                )
            manifest = freeze_baseline(paths, extra=extra)
            print(f"froze baseline {manifest['baseline_id']}")
            print(f"manifest: {paths.manifest_path}")
            print(f"scenario hash: {manifest['scenarios']['sha256']}")
            if extra:
                print(f"parent: {extra['parent_baseline_id']}")
                print(
                    "instruction_sha256_parent: "
                    f"{extra['change']['instruction_sha256_parent']}"
                )
                print(
                    "instruction_sha256_candidate: "
                    f"{extra['change']['instruction_sha256_candidate']}"
                )
            return 0
        if args.command == "run":
            return asyncio.run(_run(args))
    except BaselineError as exc:
        print(f"baseline error: {exc}")
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
