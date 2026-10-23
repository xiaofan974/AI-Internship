"""Offline verification of the Week 4 F1 golden dataset and frozen split."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from aeacus_agent.trace_store import PROJECT_DIR, sha256_file
from evals.week4.build_golden_dataset import (
    CANDIDATE_BASELINE_ID,
    CANDIDATE_FAIL_IDS,
    DATASET_ID,
    EXPECTED_CANDIDATE_TRACE_SHA256,
    EXPECTED_PARENT_TRACE_SHA256,
    PARENT_BASELINE_ID,
    PARENT_FAIL_IDS,
    build_dataset,
    frozen_split,
    verify_dataset,
)

CORPUS_PATHS = (
    PROJECT_DIR / "records" / "classification_children_stage9.json",
    PROJECT_DIR / "records" / "consolidated_articles_stage4.json",
    PROJECT_DIR / "records" / "consolidated_annexes_stage5.json",
)


class Week4GoldenDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.built = build_dataset(PROJECT_DIR)
        cls.verified = verify_dataset(PROJECT_DIR)

    def test_source_integrity_and_join_keys(self) -> None:
        hashes = self.built["hashes"]
        self.assertEqual(hashes["parent_traces"], EXPECTED_PARENT_TRACE_SHA256)
        self.assertEqual(hashes["candidate_traces"], EXPECTED_CANDIDATE_TRACE_SHA256)
        cases = self.built["cases"]
        self.assertEqual(len(cases), 40)
        keys = {
            (row["baseline_id"], row["scenario_id"], row["run_id"]) for row in cases
        }
        self.assertEqual(len(keys), 40)
        self.assertEqual(len({row["case_id"] for row in cases}), 40)
        self.assertEqual(len({row["evaluation_id"] for row in cases}), 40)
        self.assertTrue(all(row["dataset_id"] == DATASET_ID for row in cases))
        self.assertTrue(
            all(row["answer_source"] == "original_raw_model_output" for row in cases)
        )
        self.assertFalse(any(row["timing_repair_present"] for row in cases))

    def test_label_counts_are_ten_fail_thirty_pass(self) -> None:
        cases = self.built["cases"]
        fails = [row for row in cases if row["f1"] == "fail"]
        passes = [row for row in cases if row["f1"] == "pass"]
        self.assertEqual(len(fails), 10)
        self.assertEqual(len(passes), 30)
        parent_fail = {
            row["scenario_id"]
            for row in fails
            if row["baseline_id"] == PARENT_BASELINE_ID
        }
        candidate_fail = {
            row["scenario_id"]
            for row in fails
            if row["baseline_id"] == CANDIDATE_BASELINE_ID
        }
        self.assertEqual(parent_fail, set(PARENT_FAIL_IDS))
        self.assertEqual(candidate_fail, set(CANDIDATE_FAIL_IDS))

    def test_split_sizes_no_overlap_and_paired_versions(self) -> None:
        split = self.built["split"]
        self.assertEqual(len(split["calibration"]), 10)
        self.assertEqual(len(split["validation"]), 10)
        self.assertFalse(set(split["calibration"]) & set(split["validation"]))
        self.assertEqual(
            split,
            frozen_split(split["calibration"] + split["validation"]),
        )
        by_group = {"calibration": [], "validation": []}
        for row in self.built["cases"]:
            by_group[row["group"]].append(row)
        for name, rows in by_group.items():
            self.assertEqual(len(rows), 20, name)
            self.assertEqual({row["scenario_id"] for row in rows}, set(split[name]))
            self.assertEqual(sum(1 for row in rows if row["f1"] == "fail"), 5)
            self.assertEqual(sum(1 for row in rows if row["f1"] == "pass"), 15)
            versions = {}
            for row in rows:
                versions.setdefault(row["scenario_id"], set()).add(row["baseline_id"])
            for scenario_id, baselines in versions.items():
                self.assertEqual(
                    baselines,
                    {PARENT_BASELINE_ID, CANDIDATE_BASELINE_ID},
                    scenario_id,
                )

    def test_judge_payloads_exclude_labels_and_version_hints(self) -> None:
        for row in self.built["cases"]:
            payload = row["judge_payload"]
            self.assertEqual(
                set(payload),
                {
                    "evaluation_id",
                    "f1_rubric",
                    "system_description",
                    "retrieved_evidence",
                    "answer",
                    "untrusted_data",
                    "untrusted_data_notice",
                },
            )
            self.assertNotIn("f1", payload)
            self.assertNotIn("baseline_id", payload)
            self.assertNotIn("group", payload)
            blob = json.dumps(payload)
            self.assertNotIn(PARENT_BASELINE_ID, blob)
            self.assertNotIn(CANDIDATE_BASELINE_ID, blob)
            self.assertNotIn("accepted by Lily", blob)
            self.assertEqual(payload["system_description"], row["input"])
            self.assertEqual(payload["answer"], row["answer"])
            self.assertTrue(payload["retrieved_evidence"])
            self.assertIn("untrusted data", payload["untrusted_data_notice"])

    def test_goldens_are_not_in_retrieval_corpus(self) -> None:
        cases_path = Path(self.built["cases_path"])
        self.assertTrue(str(cases_path).endswith("data/local/evals/week4/golden/f1_v1/cases.jsonl"))
        self.assertTrue(cases_path.is_file())
        ignore = (PROJECT_DIR / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("data/local/", ignore)
        case_id = self.built["cases"][0]["case_id"]
        for path in CORPUS_PATHS:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(case_id, text)
            self.assertNotIn(DATASET_ID, text)

    def test_not_forty_independent_scenarios(self) -> None:
        scenarios = {row["scenario_id"] for row in self.built["cases"]}
        self.assertEqual(len(scenarios), 20)
        self.assertEqual(self.built["manifest"]["n_scenarios"], 20)
        self.assertIn("not a dataset of 40 independent scenarios", self.built["manifest"]["description"])

    def test_historical_sources_unchanged(self) -> None:
        self.assertEqual(
            sha256_file(PROJECT_DIR / "data/local/traces/week4_adk_preview_v1.jsonl"),
            EXPECTED_PARENT_TRACE_SHA256,
        )
        self.assertEqual(
            sha256_file(PROJECT_DIR / "data/local/traces/week4_adk_preview_f1_v2.jsonl"),
            EXPECTED_CANDIDATE_TRACE_SHA256,
        )
        self.assertTrue(self.verified["ok"])


if __name__ == "__main__":
    unittest.main()
