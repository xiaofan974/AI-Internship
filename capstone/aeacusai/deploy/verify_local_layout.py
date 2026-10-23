"""Verify a deployment-style layout without model calls."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ["AEACUS_UI_DISABLE_LIVE"] = "1"

THIS_DIR = Path(__file__).resolve().parent
PROJECT_DIR = THIS_DIR.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from deploy.materialize_week4_bundle import load_manifest, materialize
from evals.week4.evaluations_view import load_evaluations_view


def _isolated_layout() -> Path:
    manifest = load_manifest()
    tmp = Path(tempfile.mkdtemp(prefix="aeacusai-deploy-verify-"))
    for item in manifest["files"]:
        if item["role"] != "tracked_required":
            continue
        dest = tmp / item["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PROJECT_DIR / item["path"], dest)
    return tmp


def main() -> int:
    tmp = _isolated_layout()
    try:
        result = materialize(tmp)
        model = load_evaluations_view(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    summary = {
        "ok": bool(model.get("ok")),
        "source": model.get("source"),
        "materialized": result.get("copied"),
        "timing_raw": model.get("timing", {}).get("raw"),
        "timing_delivered": model.get("timing", {}).get("delivered"),
        "change_pp": model.get("timing", {}).get("change_pp"),
        "f1_parent_fail_count": model.get("f1", {}).get("parent_fail_count"),
        "f1_candidate_fail_count": model.get("f1", {}).get("candidate_fail_count"),
        "judge_validation_v1_tpr": (
            (model.get("judge") or {}).get("validation", {}).get("v1", {}).get("TPR")
        ),
        "invoked_judge": (model.get("judge") or {}).get("invoked_judge"),
        "errors": model.get("errors") or [],
    }
    print(json.dumps(summary, indent=2))
    if not model.get("ok"):
        return 1
    if model["timing"]["raw"]["pass"] != 18:
        return 1
    if model["timing"]["delivered"]["pass"] != 20:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
