"""Offline Week 4 baseline tests. Zero Gemini/OpenAI/Pinecone calls."""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aeacus_agent.preview_agent import aeacus_preview_agent
from aeacus_agent.trace_store import PROJECT_DIR, build_trace_record, utc_now
from evals.week4.baseline import (
    BASELINE_ID,
    CANDIDATE_F1_ID,
    BATCH1_IDS,
    BaselinePaths,
    DriftError,
    DuplicateAttemptError,
    SystemicStop,
    already_attempted,
    collect_batch,
    freeze_baseline,
    load_run_index,
    load_scenarios,
    parse_scenario_selector,
    verify_no_drift,
)
from run_review import MAX_LLM_CALLS, RUN_TIMEOUT_SECONDS

REAL_SCENARIOS = PROJECT_DIR / "evals" / "week4" / "scenarios_v1.json"
STATUTE = (
    "AI systems intended to be used for the recruitment or selection of natural persons."
)


def _paths(tmp: Path) -> BaselinePaths:
    return BaselinePaths(
        project_dir=PROJECT_DIR,
        scenarios_path=tmp / "scenarios_v1.json",
        manifest_path=tmp / "manifest.json",
        run_index_path=tmp / "run_index.json",
        trace_path=tmp / "baseline.jsonl",
    )


def _copy_scenarios(tmp: Path) -> Path:
    dest = tmp / "scenarios_v1.json"
    shutil.copyfile(REAL_SCENARIOS, dest)
    return dest


def _observe_payload() -> dict:
    return {
        "status": "ok",
        "matches": [
            {
                "label": "Annex III, point 4",
                "record_id": "T1-example::annex/III/point/4",
                "source_snapshot_id": "T1-example",
                "text": STATUTE,
                "text_sha256": "hash-1",
            }
        ],
        "context_records": [
            {
                "label": "Article 6",
                "record_id": "T1-example::article/6",
                "source_snapshot_id": "T1-example",
                "text": "Complete Article 6 parent text.",
                "text_sha256": "hash-2",
            }
        ],
    }


class ScenarioFileTests(unittest.TestCase):
    def test_twenty_unique_nonempty_inputs(self) -> None:
        scenarios = load_scenarios(REAL_SCENARIOS)
        self.assertEqual(len(scenarios), 20)
        ids = [item.id for item in scenarios]
        self.assertEqual(ids, [f"TRACE-S{index:02d}" for index in range(1, 21)])
        self.assertEqual(len(set(ids)), 20)
        for item in scenarios:
            self.assertTrue(item.input.strip())
            self.assertNotIn("expected", item.__dict__)
        raw = json.loads(REAL_SCENARIOS.read_text(encoding="utf-8"))
        for item in raw["scenarios"]:
            self.assertEqual(set(item), {"id", "input"})

    def test_verbatim_s01_and_s05(self) -> None:
        by_id = {item.id: item.input for item in load_scenarios(REAL_SCENARIOS)}
        self.assertEqual(
            by_id["TRACE-S01"],
            "A mid-size logistics company uses an AI system to read incoming CVs, "
            "discard applications that lack a driving licence, and show remaining "
            "candidates in a ranked list to human recruiters. Recruiters may "
            "interview anyone on the list.",
        )
        self.assertEqual(
            by_id["TRACE-S05"],
            "A furniture retailer’s website chatbot answers questions about "
            "delivery times and return policy from a product FAQ. It cannot place "
            "orders or change prices. Conversations are stored for two weeks.",
        )

    def test_selector_requires_explicit_ids_and_excludes_smoke(self) -> None:
        self.assertEqual(
            parse_scenario_selector("TRACE-S01:TRACE-S05"), list(BATCH1_IDS)
        )
        with self.assertRaises(Exception):
            parse_scenario_selector(None)
        with self.assertRaises(Exception):
            parse_scenario_selector("capture_smoke")


class BaselineHarnessTests(unittest.TestCase):
    def test_dry_run_makes_zero_provider_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            _copy_scenarios(tmp)
            paths = _paths(tmp)
            freeze_baseline(paths)
            calls: list[str] = []

            async def forbidden(description, *, capture, agent):
                calls.append(description)
                raise AssertionError("dry-run must not execute")

            result = asyncio.run(
                collect_batch(
                    paths=paths,
                    selected_ids=BATCH1_IDS,
                    phase="batch1",
                    dry_run=True,
                    execute=forbidden,
                )
            )
            self.assertEqual(calls, [])
            self.assertEqual(result.selected, list(BATCH1_IDS))
            self.assertEqual(result.attempts, [])
            self.assertFalse(paths.run_index_path.exists())
            self.assertFalse(paths.trace_path.exists())

    def test_mocked_collection_uses_fresh_sessions_and_captures_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            _copy_scenarios(tmp)
            paths = _paths(tmp)
            freeze_baseline(paths)
            sessions: list[str] = []

            async def fake(description, *, capture, agent):
                sessions.append(capture.config.extra["runner_session_id"])
                capture.started_at = utc_now()
                capture.ended_at = utc_now()
                capture.elapsed_ms = 12.0
                failed = description.startswith("A private language school")
                if failed:
                    answer = "[FAILED] Provider/execution failure (RuntimeError): mocked failure"
                    capture.events = [{"kind": "failed", "message": answer}]
                    build_trace_record(
                        capture,
                        agent=agent,
                        user_input=description,
                        max_llm_calls=MAX_LLM_CALLS,
                        timeout_seconds=RUN_TIMEOUT_SECONDS,
                        result=answer,
                    )
                    return answer
                answer = "### Provisional finding\nmocked"
                capture.events = [
                    {
                        "kind": "act",
                        "tool": "preview_classification_search",
                        "arguments": {"query": "q"},
                        "association_key": "trace_call_1",
                        "provider_call_id": None,
                    },
                    {
                        "kind": "observe",
                        "tool": "preview_classification_search",
                        "association_key": "trace_call_1",
                        "provider_call_id": None,
                        "payload": _observe_payload(),
                    },
                    {"kind": "final", "text": answer},
                ]
                build_trace_record(
                    capture,
                    agent=agent,
                    user_input=description,
                    max_llm_calls=MAX_LLM_CALLS,
                    timeout_seconds=RUN_TIMEOUT_SECONDS,
                    result=answer,
                )
                return answer

            with mock.patch("evals.week4.baseline.run_review", side_effect=AssertionError("no live run_review")):
                result = asyncio.run(
                    collect_batch(
                        paths=paths,
                        selected_ids=["TRACE-S01", "TRACE-S02"],
                        phase="batch1",
                        execute=fake,
                        agent=aeacus_preview_agent,
                    )
                )
            self.assertEqual(len(sessions), 2)
            self.assertEqual(len(set(sessions)), 2)
            self.assertEqual(result.attempts[0].status, "ok")
            self.assertEqual(result.attempts[1].status, "failed")
            self.assertTrue(result.attempts[0].capture_saved)
            self.assertTrue(result.attempts[1].capture_saved)
            index = load_run_index(paths)
            self.assertTrue(already_attempted(index, "TRACE-S01"))
            self.assertTrue(already_attempted(index, "TRACE-S02"))
            self.assertNotIn("capture_smoke", index["attempts"])
            traces = [
                json.loads(line)
                for line in paths.trace_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(traces), 2)
            self.assertEqual(traces[0]["baseline"]["id"], BASELINE_ID)
            self.assertEqual(traces[0]["baseline"]["phase"], "batch1")
            self.assertEqual(traces[1]["execution_status"], "failed")
            self.assertIsNone(traces[1]["final_output"])
            self.assertEqual(
                traces[1]["application_outcome"]["register_opened"], "not_observed"
            )
            self.assertEqual(
                traces[1]["application_outcome"]["pending_review"]["status"],
                "not_created",
            )

            with self.assertRaises(DuplicateAttemptError):
                asyncio.run(
                    collect_batch(
                        paths=paths,
                        selected_ids=["TRACE-S01"],
                        phase="batch1",
                        execute=fake,
                    )
                )

    def test_systemic_capture_failure_stops_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            _copy_scenarios(tmp)
            paths = _paths(tmp)
            freeze_baseline(paths)
            calls: list[str] = []

            async def fake(description, *, capture, agent):
                calls.append(capture.config.scenario_id)
                capture.started_at = utc_now()
                capture.ended_at = utc_now()
                capture.elapsed_ms = 1.0
                answer = "### Provisional finding\nmocked"
                capture.events = [{"kind": "final", "text": answer}]
                build_trace_record(
                    capture,
                    agent=agent,
                    user_input=description,
                    max_llm_calls=MAX_LLM_CALLS,
                    timeout_seconds=RUN_TIMEOUT_SECONDS,
                    result=answer,
                )
                capture.config.output_path = tmp / "missing-dir-as-file"
                capture.config.output_path.write_text("not a dir", encoding="utf-8")
                capture.config.output_path = capture.config.output_path / "trace.jsonl"
                return answer

            with self.assertRaises(SystemicStop):
                asyncio.run(
                    collect_batch(
                        paths=paths,
                        selected_ids=["TRACE-S01", "TRACE-S02"],
                        phase="batch1",
                        execute=fake,
                    )
                )
            self.assertEqual(calls, ["TRACE-S01"])
            index = load_run_index(paths)
            self.assertEqual(index["attempts"]["TRACE-S01"]["capture_saved"], False)
            self.assertNotIn("TRACE-S02", index["attempts"])

    def test_drift_stops_without_updating_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            _copy_scenarios(tmp)
            paths = _paths(tmp)
            freeze_baseline(paths)
            original = paths.manifest_path.read_text(encoding="utf-8")
            payload = json.loads(paths.scenarios_path.read_text(encoding="utf-8"))
            payload["scenarios"][0]["input"] += " changed"
            paths.scenarios_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            with self.assertRaises(DriftError):
                verify_no_drift(paths)
            self.assertEqual(paths.manifest_path.read_text(encoding="utf-8"), original)
            with self.assertRaises(Exception):
                freeze_baseline(paths)

    def test_limits_are_the_existing_preview_limits(self) -> None:
        self.assertEqual(MAX_LLM_CALLS, 8)
        self.assertEqual(RUN_TIMEOUT_SECONDS, 90)

    def test_candidate_id_uses_separate_paths_and_does_not_write_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            scenarios = _copy_scenarios(tmp)
            baseline_paths = BaselinePaths(
                project_dir=PROJECT_DIR,
                baseline_id=BASELINE_ID,
                scenarios_path=scenarios,
                manifest_path=tmp / "v1" / "manifest.json",
                run_index_path=tmp / "v1" / "run_index.json",
                trace_path=tmp / "v1" / "baseline.jsonl",
            )
            candidate_paths = BaselinePaths(
                project_dir=PROJECT_DIR,
                baseline_id=CANDIDATE_F1_ID,
                scenarios_path=scenarios,
                manifest_path=tmp / "candidate" / "manifest.json",
                run_index_path=tmp / "candidate" / "run_index.json",
                trace_path=tmp / "candidate" / "candidate.jsonl",
            )
            freeze_baseline(baseline_paths)
            freeze_baseline(candidate_paths)
            self.assertEqual(
                json.loads(candidate_paths.manifest_path.read_text(encoding="utf-8"))[
                    "baseline_id"
                ],
                CANDIDATE_F1_ID,
            )

            async def fake(description, *, capture, agent):
                answer = "### Provisional finding\nmocked"
                capture.started_at = utc_now()
                capture.ended_at = utc_now()
                capture.elapsed_ms = 1.0
                capture.events = [
                    {
                        "kind": "act",
                        "tool": "preview_classification_search",
                        "arguments": {"query": "q"},
                    },
                    {
                        "kind": "observe",
                        "tool": "preview_classification_search",
                        "payload": _observe_payload(),
                    },
                    {"kind": "final", "text": answer},
                ]
                build_trace_record(
                    capture,
                    agent=agent,
                    user_input=description,
                    max_llm_calls=MAX_LLM_CALLS,
                    timeout_seconds=RUN_TIMEOUT_SECONDS,
                    result=answer,
                )
                return answer

            asyncio.run(
                collect_batch(
                    paths=candidate_paths,
                    selected_ids=["TRACE-S01"],
                    phase="batch1",
                    execute=fake,
                )
            )
            traces = [
                json.loads(line)
                for line in candidate_paths.trace_path.read_text(
                    encoding="utf-8"
                ).splitlines()
                if line.strip()
            ]
            self.assertEqual(traces[0]["baseline"]["id"], CANDIDATE_F1_ID)
            self.assertFalse(baseline_paths.trace_path.exists())
            self.assertEqual(load_run_index(baseline_paths)["attempts"], {})


if __name__ == "__main__":
    unittest.main()
