"""Copy the reviewable Week 4 offline bundle into the app layout.

The Streamlit evaluations view still reads the original relative paths
under data/local/. Those paths are gitignored, so a Git deploy does not
contain them. This script copies byte-identical bundled files into place
and refuses to overwrite a different existing file.

It does not rewrite the original frozen artifacts. Use --refresh only to
rebuild deploy/week4_offline/ from the current local originals.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

THIS_DIR = Path(__file__).resolve().parent
PROJECT_DIR = THIS_DIR.parent
BUNDLE_DIR = THIS_DIR / "week4_offline"
MANIFEST_PATH = BUNDLE_DIR / "MANIFEST.json"
SCHEMA = "aeacus.deploy.week4_offline_bundle.v1"

BUNDLED_COPIES = (
    {
        "source": "data/local/traces/week4_adk_preview_v1.jsonl",
        "needed_by": ["week4_evaluations"],
        "kind": "frozen_parent_traces",
    },
    {
        "source": "data/local/traces/week4_adk_preview_f1_v2.jsonl",
        "needed_by": ["week4_evaluations"],
        "kind": "frozen_candidate_traces",
    },
    {
        "source": "data/local/evals/week4/golden/f1_v1/judge_payloads.jsonl",
        "needed_by": ["week4_evaluations"],
        "kind": "f1_judge_payloads",
    },
    {
        "source": "data/local/evals/week4/judge/f1_v1/calibration_v1/predictions.json",
        "needed_by": ["week4_evaluations"],
        "kind": "saved_judge_predictions",
    },
    {
        "source": "data/local/evals/week4/judge/f1_v2/calibration_v2/predictions.json",
        "needed_by": ["week4_evaluations"],
        "kind": "saved_judge_predictions",
    },
    {
        "source": "data/local/evals/week4/judge/validation_v1/v1_predictions.json",
        "needed_by": ["week4_evaluations"],
        "kind": "saved_judge_predictions",
    },
    {
        "source": "data/local/evals/week4/judge/validation_v1/v2_predictions.json",
        "needed_by": ["week4_evaluations"],
        "kind": "saved_judge_predictions",
    },
)

TRACKED_REQUIRED = (
    {
        "path": "evals/week4/scenarios_v1.json",
        "needed_by": ["week4_evaluations"],
        "kind": "fictional_scenarios",
    },
    {
        "path": "evals/week4/taxonomy_v1.json",
        "needed_by": ["week4_evaluations"],
        "kind": "taxonomy",
    },
    {
        "path": "evals/week4/annotations_v1.json",
        "needed_by": ["week4_evaluations"],
        "kind": "reviewed_labels",
    },
    {
        "path": "evals/week4/annotations_f1_v2.json",
        "needed_by": ["week4_evaluations"],
        "kind": "reviewed_labels",
    },
    {
        "path": "evals/week4/results/week4_codify_baseline_v1.json",
        "needed_by": ["week4_evaluations"],
        "kind": "saved_results",
    },
    {
        "path": "evals/week4/results/week4_adk_preview_f1_v2_assertions.json",
        "needed_by": ["week4_evaluations"],
        "kind": "saved_results",
    },
    {
        "path": "evals/week4/checkers.py",
        "needed_by": ["week4_evaluations"],
        "kind": "frozen_checker",
    },
    {
        "path": "reports/week4_timing_repair_eval.json",
        "needed_by": ["week4_evaluations"],
        "kind": "saved_results",
    },
    {
        "path": "evals/week4/golden/f1_v1/manifest.json",
        "needed_by": ["week4_evaluations"],
        "kind": "golden_dataset",
    },
    {
        "path": "evals/week4/golden/f1_v1/split.json",
        "needed_by": ["week4_evaluations"],
        "kind": "golden_dataset",
    },
    {
        "path": "evals/week4/judge/f1_v2/refinement_provenance.json",
        "needed_by": ["week4_evaluations"],
        "kind": "judge_provenance",
    },
    {
        "path": "reports/week4_f1_judge_v1_calibration.json",
        "needed_by": ["week4_evaluations"],
        "kind": "saved_results",
    },
    {
        "path": "reports/week4_f1_judge_v2_calibration.json",
        "needed_by": ["week4_evaluations"],
        "kind": "saved_results",
    },
    {
        "path": "reports/week4_f1_judge_validation.json",
        "needed_by": ["week4_evaluations"],
        "kind": "saved_results",
    },
    {
        "path": "records/classification_children_stage9.json",
        "needed_by": ["assessment"],
        "kind": "pinned_corpus",
    },
    {
        "path": "records/consolidated_articles_stage4.json",
        "needed_by": ["assessment"],
        "kind": "pinned_corpus",
    },
    {
        "path": "records/consolidated_annexes_stage5.json",
        "needed_by": ["assessment"],
        "kind": "pinned_corpus",
    },
)

EXCLUSIONS = [
    ".env",
    ".env.example values used as secrets",
    ".venv/",
    ".venv-langfuse/",
    ".venv-langgraph/",
    "data/local/review_register.sqlite",
    "other *.sqlite*",
    "data/local/traces/adk_preview.jsonl",
    "data/local/traces/timing_repair_smoke.jsonl",
    "data/local/traces/week4_langfuse_connection_smoke*",
    "data/local/traces/*.txt",
    "data/local/evals/week4/langfuse/",
    "data/local/evals/week4/golden/f1_v1/cases.jsonl",
    "data/local/evals/week4/judge/**/freeze.json",
    "data/local/evals/week4/judge/**/scored.json",
    "data/local/evals/week4/judge/**/predictions.jsonl",
    "data/local/evals/week4/judge/validation_v1/requests.jsonl",
    "data/local/evals/week4/*/run_index.json",
    "data/raw/",
    "credentials and API keys",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_entry(
    *,
    role: str,
    relative: str,
    sha256: str,
    needed_by: list[str],
    kind: str,
    gitignored: bool,
    bundle: str | None = None,
) -> dict[str, Any]:
    entry = {
        "role": role,
        "path": relative,
        "sha256": sha256,
        "needed_by": list(needed_by),
        "kind": kind,
        "gitignored": gitignored,
    }
    if bundle is not None:
        entry["bundle"] = bundle
    return entry


def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.is_file():
        raise FileNotFoundError(f"Missing bundle manifest: {MANIFEST_PATH}")
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if payload.get("schema") != SCHEMA:
        raise ValueError(
            f"Unexpected bundle schema {payload.get('schema')!r}, expected {SCHEMA}."
        )
    return payload


def refresh_bundle(source_root: Path) -> dict[str, Any]:
    """Build deploy/week4_offline/ from local originals. Does not rewrite them."""
    files: list[dict[str, Any]] = []
    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
    for item in BUNDLED_COPIES:
        relative = item["source"]
        source = source_root / relative
        if not source.is_file():
            raise FileNotFoundError(f"Cannot refresh missing original: {source}")
        digest = sha256_file(source)
        dest = BUNDLE_DIR / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        copied = sha256_file(dest)
        if copied != digest:
            raise RuntimeError(f"Bundle copy hash mismatch for {relative}")
        files.append(
            _file_entry(
                role="bundled_copy",
                relative=relative,
                sha256=digest,
                needed_by=item["needed_by"],
                kind=item["kind"],
                gitignored=True,
                bundle=relative,
            )
        )
    for item in TRACKED_REQUIRED:
        relative = item["path"]
        source = source_root / relative
        if not source.is_file():
            raise FileNotFoundError(f"Cannot refresh missing tracked file: {source}")
        files.append(
            _file_entry(
                role="tracked_required",
                relative=relative,
                sha256=sha256_file(source),
                needed_by=item["needed_by"],
                kind=item["kind"],
                gitignored=False,
            )
        )
    manifest = {
        "schema": SCHEMA,
        "service": "aeacusai-demo",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_root": str(source_root),
        "note": (
            "Byte-identical copies of gitignored Week 4 traces, judge payloads, "
            "and saved predictions. Tracked scenarios, reports, and corpus files "
            "stay in the repository and are listed for review. Originals under "
            "data/local/ are not rewritten."
        ),
        "exclusions": EXCLUSIONS,
        "files": files,
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def materialize(
    dest_root: Path,
    *,
    verify_only: bool = False,
) -> dict[str, Any]:
    manifest = load_manifest()
    copied: list[str] = []
    verified: list[str] = []
    for item in manifest.get("files") or []:
        relative = item["path"]
        expected = item["sha256"]
        if item.get("role") == "bundled_copy":
            source = BUNDLE_DIR / item.get("bundle", relative)
            dest = dest_root / relative
            if not source.is_file():
                raise FileNotFoundError(f"Bundled file missing: {source}")
            observed = sha256_file(source)
            if observed != expected:
                raise RuntimeError(
                    f"Bundled {relative} SHA-256 {observed} does not match "
                    f"manifest {expected}."
                )
            if dest.is_file():
                dest_hash = sha256_file(dest)
                if dest_hash != expected:
                    raise RuntimeError(
                        f"Refusing to overwrite {dest} with a different SHA-256 "
                        f"({dest_hash} != {expected}). Originals are preserved."
                    )
                verified.append(relative)
                continue
            if verify_only:
                raise FileNotFoundError(f"Destination missing: {dest}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
            dest_hash = sha256_file(dest)
            if dest_hash != expected:
                dest.unlink()
                raise RuntimeError(f"Materialized hash mismatch for {relative}")
            copied.append(relative)
            continue
        tracked = dest_root / relative
        if not tracked.is_file():
            raise FileNotFoundError(f"Tracked required file missing: {tracked}")
        observed = sha256_file(tracked)
        if observed != expected:
            raise RuntimeError(
                f"Tracked {relative} SHA-256 {observed} does not match "
                f"manifest {expected}."
            )
        verified.append(relative)
    return {
        "ok": True,
        "copied": copied,
        "verified": verified,
        "dest_root": str(dest_root),
        "manifest": str(MANIFEST_PATH),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Rebuild the bundle from local originals without rewriting them.",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=PROJECT_DIR,
        help="Project root that should receive data/local copies.",
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=PROJECT_DIR,
        help="Project root that holds the original artifacts for --refresh.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Check hashes only. Do not copy missing destination files.",
    )
    args = parser.parse_args(argv)
    if args.refresh:
        manifest = refresh_bundle(args.source_root.resolve())
        print(f"Wrote {MANIFEST_PATH} with {len(manifest['files'])} files.")
        return 0
    result = materialize(args.dest.resolve(), verify_only=args.verify_only)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
