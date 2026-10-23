"""Stage 2 offline parser checkpoint: extract complete recital records (Recitals 1–180)
from the original 2024 EU AI Act Official Journal XHTML artifact (T1-AIA-OJ-2024).

Preserves all existing files, Stage 1 article outputs, and the 45-record review baseline.
Performs no recital-to-article mapping inference, annex parsing, paragraph decomposition,
consolidated parsing, cross-reference resolution, Charter parsing, network calls or
vector-store operations.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from jsonschema import Draft202012Validator

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from extract_original_articles import SOURCE_ID, load_source_artifact
from extract_review_samples import ROOT, digest, join_blocks, parse

RECITAL_ID_RE = re.compile(r"^rct_(\d+[a-z]*)$")


def extract_original_recitals(
    artifact: dict,
    validator: Draft202012Validator,
) -> list[dict]:
    """Extract all 180 native recital containers in document order from T1-AIA-OJ-2024."""
    raw_path = ROOT / artifact["relative_path"]
    tree = parse(raw_path)
    snap = artifact["source_snapshot_id"]
    url = artifact["resolved_content_url"]

    recital_elements = [
        el
        for el in tree.xpath("//*[@id]")
        if isinstance(el.tag, str) and RECITAL_ID_RE.fullmatch(el.get("id", ""))
    ]

    records: list[dict] = []
    for recital_el in recital_elements:
        native_id = recital_el.get("id", "")
        match = RECITAL_ID_RE.fullmatch(native_id)
        if not match:
            raise ValueError(f"Unexpected recital id: {native_id}")
        number = match.group(1)
        path = f"recital/{number}"
        normalized_text = join_blocks([recital_el])
        record = {
            "schema_version": "0.1.0",
            "record_id": f"{snap}::{path}",
            "source_snapshot_id": snap,
            "parent_id": None,
            "unit_kind": "recital",
            "legal_function": "interpretive",
            "label": f"Recital {number}",
            "locator": {
                "path": path,
                "recital": number,
            },
            "language": "en",
            "tier": 1,
            "text": normalized_text,
            "text_sha256": digest(normalized_text),
            "source_location": {
                "url": url,
                "format": "html",
                "selector": tree.getpath(recital_el),
            },
            "children": [],
            "cross_references": [],
            "normalization_version": "legal-whitespace-v1",
            "validation_status": "pending",
            "review_status": "not_reviewed",
            "indexable": False,
        }
        validator.validate(record)
        records.append(record)

    return records


def run_stage2_checks(
    records_pass1: list[dict],
    records_pass2: list[dict],
    validator: Draft202012Validator,
    baseline_path: Path = ROOT / "records" / "review_records.json",
) -> dict:
    """Run focused offline verification checks for Stage 2 original recitals."""
    expected_numbers = [str(i) for i in range(1, 181)]
    extracted_numbers = [r["locator"]["recital"] for r in records_pass1]
    record_ids = [r["record_id"] for r in records_pass1]
    selectors = [r["source_location"]["selector"] for r in records_pass1]

    # Check 1: Exactly 180 unique recitals, numbered 1–180 in document order
    count_is_180 = len(records_pass1) == 180
    unique_record_ids = len(set(record_ids)) == 180
    unique_selectors = len(set(selectors)) == 180
    exact_1_to_180_order = extracted_numbers == expected_numbers
    assert count_is_180, f"Expected 180 records, got {len(records_pass1)}"
    assert unique_record_ids, "Duplicate record_id values detected"
    assert unique_selectors, "Duplicate source_location selector values detected"
    assert exact_1_to_180_order, "Extracted recitals do not match ordered Recitals 1–180"

    # Check 2 & 4: Every record satisfies legal_record.schema.json, interpretive function,
    # non-indexable gate, and each text_sha256 matches its extracted text
    all_sha256_match_text = True
    all_prefixed_with_number = True
    for record in records_pass1:
        validator.validate(record)
        num = record["locator"]["recital"]
        assert record["unit_kind"] == "recital"
        assert record["legal_function"] == "interpretive"
        assert record["label"] == f"Recital {num}"
        assert record["children"] == []
        assert record["cross_references"] == []
        assert record["validation_status"] == "pending"
        assert record["review_status"] == "not_reviewed"
        assert record["indexable"] is False
        computed_digest = digest(record["text"])
        if record["text_sha256"] != computed_digest:
            all_sha256_match_text = False
        assert record["text_sha256"] == computed_digest
        if not record["text"].startswith(f"({num}) "):
            all_prefixed_with_number = False
        assert record["text"].startswith(f"({num}) "), f"Recital {num} missing leading marker"

    # Check 3: Recital 47 text and text_sha256 (and full record) exactly match the baseline
    baseline_records = json.loads(baseline_path.read_text(encoding="utf-8"))
    snap = records_pass1[0]["source_snapshot_id"]
    baseline_rct47_id = f"{snap}::recital/47"
    baseline_rct47 = next(
        (r for r in baseline_records if r["record_id"] == baseline_rct47_id),
        None,
    )
    if baseline_rct47 is None:
        raise ValueError(f"Baseline record not found: {baseline_rct47_id}")

    stage2_rct47 = next(
        (r for r in records_pass1 if r["record_id"] == baseline_rct47_id),
        None,
    )
    if stage2_rct47 is None:
        raise ValueError(f"Stage 2 Recital 47 record not found: {baseline_rct47_id}")

    rct47_text_matches = stage2_rct47["text"] == baseline_rct47["text"]
    rct47_sha256_matches = stage2_rct47["text_sha256"] == baseline_rct47["text_sha256"]
    rct47_record_matches = stage2_rct47 == baseline_rct47
    assert rct47_text_matches, "Stage 2 Recital 47 text does not match baseline"
    assert rct47_sha256_matches, "Stage 2 Recital 47 text_sha256 does not match baseline"
    assert rct47_record_matches, "Stage 2 Recital 47 record differs from baseline"

    # Check 5: Repeating extraction produces identical records
    reproducible = records_pass1 == records_pass2
    assert reproducible, "Second extraction did not produce identical records"

    return {
        "stage": "original_recitals_stage2",
        "source_id": SOURCE_ID,
        "source_snapshot_id": snap,
        "record_count": len(records_pass1),
        "technical_checks": {
            "manifest_sha256_verified": True,
            "exact_180_unique_recitals_1_to_180_in_order": (
                count_is_180 and unique_record_ids and unique_selectors and exact_1_to_180_order
            ),
            "all_records_satisfy_json_schema": True,
            "all_recitals_marked_interpretive": True,
            "all_text_sha256_match_extracted_text": all_sha256_match_text,
            "all_recitals_start_with_parenthesized_number": all_prefixed_with_number,
            "recital_47_matches_baseline_text_and_sha256": (
                rct47_text_matches and rct47_sha256_matches and rct47_record_matches
            ),
            "recital_47_text_sha256": stage2_rct47["text_sha256"],
            "recital_47_char_length": len(stage2_rct47["text"]),
            "second_extraction_identical": reproducible,
        },
        "content_review_and_ingestion_status": {
            "validation_status": "pending",
            "review_status": "not_reviewed",
            "all_indexable_false": True,
            "recital_to_article_mapping_inferred": False,
            "cross_reference_resolution": "pending",
            "legally_reviewed": False,
            "ready_for_indexing": False,
            "note": (
                "Recitals are recorded strictly with legal_function='interpretive' and not as "
                "standalone operative obligations. No recital-to-article mappings are inferred, "
                "and cross_references remain explicitly pending ([]). Passing Stage 2 technical "
                "checks does not mean the corpus is legally reviewed or ready for indexing."
            ),
        },
        "source_observations": [
            {
                "scope": "Stage 1 original articles (T1-AIA-OJ-2024)",
                "locator": "article/1",
                "native_id": "art_1",
                "observed_subtitle": "Subject matter`",
                "handling": (
                    "Source observation only: official OJ XHTML contains a literal trailing "
                    "backtick in p.oj-sti-art. Preserved verbatim without editorial modification."
                ),
            },
            {
                "scope": "Stage 1 original articles (T1-AIA-OJ-2024)",
                "locator": "article/111",
                "native_id": "art_111",
                "observed_subtitle": (
                    "AI systems already placed on the market or put into service and "
                    "general-purpose AI models already placed on the marked"
                ),
                "handling": (
                    "Source observation only: official OJ XHTML contains 'placed on the marked' "
                    "in p.oj-sti-art. Preserved verbatim without editorial modification."
                ),
            },
        ],
        "extracted_recital_inventory": {
            "first_recital_id": records_pass1[0]["record_id"],
            "first_recital_label": records_pass1[0]["label"],
            "last_recital_id": records_pass1[-1]["record_id"],
            "last_recital_label": records_pass1[-1]["label"],
            "recital_numbers": extracted_numbers,
        },
    }


def main() -> None:
    schema = json.loads((ROOT / "legal_record.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    artifact = load_source_artifact()

    records_pass1 = extract_original_recitals(artifact, validator)
    records_pass2 = extract_original_recitals(artifact, validator)

    report = run_stage2_checks(records_pass1, records_pass2, validator)

    records_out = ROOT / "records" / "original_recitals_stage2.json"
    records_out.parent.mkdir(parents=True, exist_ok=True)
    records_out.write_text(
        json.dumps(records_pass1, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    report_out = ROOT / "reports" / "original_recitals_stage2_validation.json"
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "stage": report["stage"],
                "records_written": len(records_pass1),
                "technical_checks_passed": all(
                    v is True
                    for k, v in report["technical_checks"].items()
                    if isinstance(v, bool)
                ),
                "review_status": report["content_review_and_ingestion_status"]["review_status"],
                "indexable": False,
            }
        )
    )


if __name__ == "__main__":
    main()
