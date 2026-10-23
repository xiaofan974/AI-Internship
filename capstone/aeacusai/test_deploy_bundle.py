"""Offline checks for the Render Week 4 deployment bundle.

These tests copy listed artifacts into a temporary layout. They do not
call a model, open the review register, or rewrite frozen originals.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from aeacus_agent.trace_store import PROJECT_DIR, sha256_file
from deploy.materialize_week4_bundle import (
    BUNDLE_DIR,
    EXCLUSIONS,
    MANIFEST_PATH,
    SCHEMA,
    load_manifest,
    materialize,
)
from evals.week4.evaluations_view import load_evaluations_view

SECRET_RE = re.compile(
    r"AIza[0-9A-Za-z\-_]{20,}|sk-[A-Za-z0-9]{20,}|pcsk_[0-9A-Za-z\-_]{20,}|"
    r"sk-lf-|pk-lf-|GOOGLE_API_KEY\s*=|OPENAI_API_KEY\s*=|"
    r"PINECONE_API_KEY\s*=|LANGFUSE_SECRET_KEY\s*="
)
FORBIDDEN_NAMES = {
    ".env",
    "review_register.sqlite",
    "review_register.sqlite-wal",
    "review_register.sqlite-shm",
}


def _isolated_layout(manifest: dict) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="aeacusai-deploy-"))
    for item in manifest["files"]:
        relative = item["path"]
        dest = tmp / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        if item["role"] == "tracked_required":
            shutil.copyfile(PROJECT_DIR / relative, dest)
    return tmp


class DeployBundleTests(unittest.TestCase):
    def test_manifest_lists_required_files_and_excludes_secrets(self) -> None:
        manifest = load_manifest()
        self.assertEqual(manifest["schema"], SCHEMA)
        roles = {item["path"]: item for item in manifest["files"]}
        self.assertIn("data/local/traces/week4_adk_preview_v1.jsonl", roles)
        self.assertIn("evals/week4/scenarios_v1.json", roles)
        self.assertIn("records/classification_children_stage9.json", roles)
        self.assertTrue(roles["data/local/traces/week4_adk_preview_v1.jsonl"]["gitignored"])
        self.assertFalse(roles["evals/week4/scenarios_v1.json"]["gitignored"])
        self.assertIn("data/local/review_register.sqlite", EXCLUSIONS)
        self.assertIn(".env", EXCLUSIONS)
        for path in BUNDLE_DIR.rglob("*"):
            if path.is_dir():
                continue
            self.assertNotIn(path.name, FORBIDDEN_NAMES)
            if path.suffix in {".json", ".jsonl", ".md"}:
                text = path.read_text(encoding="utf-8", errors="replace")
                self.assertFalse(SECRET_RE.search(text), path)

    def test_isolated_layout_loads_week4_results(self) -> None:
        manifest = load_manifest()
        tmp = _isolated_layout(manifest)
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        self.assertFalse(
            (tmp / "data/local/traces/week4_adk_preview_v1.jsonl").exists()
        )
        result = materialize(tmp)
        self.assertTrue(result["copied"])
        model = load_evaluations_view(tmp)
        self.assertTrue(model["ok"], model.get("errors"))
        self.assertEqual(model["source"], "historical")
        self.assertEqual(model["timing"]["raw"]["pass"], 18)
        self.assertEqual(model["timing"]["raw"]["denominator"], 20)
        self.assertEqual(model["timing"]["delivered"]["pass"], 20)
        self.assertEqual(model["timing"]["change_pp"], 10.0)
        self.assertEqual(model["f1"]["parent_fail_count"], 5)
        self.assertEqual(model["f1"]["candidate_fail_count"], 5)
        judge = model["judge"]
        self.assertEqual(judge["validation"]["v1"]["TP"], 0)
        self.assertEqual(judge["validation"]["v1"]["FN"], 5)
        self.assertEqual(judge["validation"]["v2"]["TP"], 0)
        self.assertFalse(judge["invoked_judge"])
        self.assertEqual(
            model["hashes"]["parent_traces"],
            "29871169b2db5aebeac179cdd254a4700e36f252b2873ea9e05e334400204db1",
        )
        self.assertFalse((tmp / "data" / "local" / "review_register.sqlite").exists())
        self.assertFalse((tmp / ".env").exists())

    def test_materialize_refuses_to_overwrite_different_bytes(self) -> None:
        manifest = load_manifest()
        tmp = _isolated_layout(manifest)
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        target = tmp / "data/local/traces/week4_adk_preview_v1.jsonl"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("not-the-frozen-trace\n", encoding="utf-8")
        with self.assertRaises(RuntimeError) as raised:
            materialize(tmp)
        self.assertIn("Refusing to overwrite", str(raised.exception))
        self.assertEqual(target.read_text(encoding="utf-8"), "not-the-frozen-trace\n")

    def test_render_start_files_bind_render_port(self) -> None:
        start = (PROJECT_DIR / "deploy" / "start.sh").read_text(encoding="utf-8")
        render = (PROJECT_DIR / "render.yaml").read_text(encoding="utf-8")
        config = (PROJECT_DIR / ".streamlit" / "config.toml").read_text(
            encoding="utf-8"
        )
        self.assertIn("0.0.0.0", start)
        self.assertIn("$PORT", start)
        self.assertIn("materialize_week4_bundle.py", start)
        self.assertIn("name: aeacusai-demo", render)
        self.assertIn("bash deploy/start.sh", render)
        self.assertNotIn("ai-internship-5ei0", render.split("name:", 1)[1])
        self.assertIn('address = "0.0.0.0"', config)
        self.assertTrue(MANIFEST_PATH.is_file())
        parent = PROJECT_DIR / "data/local/traces/week4_adk_preview_v1.jsonl"
        bundled = BUNDLE_DIR / "data/local/traces/week4_adk_preview_v1.jsonl"
        if parent.is_file():
            self.assertEqual(sha256_file(parent), sha256_file(bundled))


if __name__ == "__main__":
    os.environ.setdefault("AEACUS_UI_DISABLE_LIVE", "1")
    unittest.main()
