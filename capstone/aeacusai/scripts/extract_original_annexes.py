"""Stage 3 offline parser checkpoint: extract complete parent records for the
original 2024 EU AI Act's 13 annexes (Annexes I–XIII, T1-AIA-OJ-2024).

Preserves all existing files, Stage 1/2 outputs, and the 45-record review baseline.
Performs no section, point, table, or table-row child decomposition, no cross-reference
or risk/actor inference, no consolidated-edition or Annex XIV parsing, and no network,
embedding, or vector-store operations.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from lxml import etree
from jsonschema import Draft202012Validator

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from extract_original_articles import SOURCE_ID, load_source_artifact
from extract_review_samples import NS, ROOT, digest, join_blocks, parse, text

ANNEX_ID_RE = re.compile(r"^anx_([IVXLCDM]+)$")
EXPECTED_ANNEX_NUMERALS = [
    "I",
    "II",
    "III",
    "IV",
    "V",
    "VI",
    "VII",
    "VIII",
    "IX",
    "X",
    "XI",
    "XII",
    "XIII",
]

# Known structural/inline (tag, class) patterns inside T1-AIA-OJ-2024 annexes
SUPPORTED_ANNEX_TAG_CLASSES = {
    ("div", "eli-container"),
    ("div", "oj-enumeration-spacing"),
    ("p", "oj-doc-ti"),
    ("p", "oj-ti-grseq-1"),
    ("p", "oj-normal"),
    ("p", None),
    ("table", None),
    ("tbody", None),
    ("tr", None),
    ("td", None),
    ("col", None),
    ("span", None),
    ("span", "oj-italic"),
    ("a", None),
}


def _annex_label_from_source(annex_el, roman: str) -> str:
    """Build the annex label from the native oj-doc-ti heading elements in the source."""
    doc_titles = [
        text(el)
        for el in annex_el.xpath("./h:p[@class='oj-doc-ti']", namespaces=NS)
        if text(el)
    ]
    if len(doc_titles) >= 2:
        return f"Annex {roman} — {' — '.join(doc_titles[1:])}"
    if len(doc_titles) == 1:
        return doc_titles[0]
    return f"Annex {roman}"


def _inspect_annex_elements(annex_el) -> tuple[list[etree._Element], list[dict], int]:
    """Return nonempty direct child blocks, any unsupported nonempty elements, and table count.

    Skips only genuinely empty layout elements (where normalized text is empty).
    Never silently discards an unfamiliar nonempty element.
    """
    nonempty_children: list[etree._Element] = []
    unsupported_nonempty: list[dict] = []

    for child in annex_el:
        if not isinstance(child.tag, str):
            continue
        child_text = text(child)
        if not child_text:
            # Genuinely empty layout element
            continue
        nonempty_children.append(child)

    for desc in annex_el.iter():
        if not isinstance(desc.tag, str):
            continue
        tag_name = etree.QName(desc).localname
        cls_name = desc.get("class")
        desc_text = text(desc)
        if desc_text and (tag_name, cls_name) not in SUPPORTED_ANNEX_TAG_CLASSES:
            unsupported_nonempty.append(
                {
                    "tag": tag_name,
                    "class": cls_name,
                    "id": desc.get("id"),
                    "text_excerpt": desc_text[:120],
                }
            )

    tables = annex_el.xpath(".//h:table", namespaces=NS)
    return nonempty_children, unsupported_nonempty, len(tables)


def extract_original_annexes(
    artifact: dict,
    validator: Draft202012Validator,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Extract all 13 native annex containers in document order from T1-AIA-OJ-2024."""
    raw_path = ROOT / artifact["relative_path"]
    tree = parse(raw_path)
    snap = artifact["source_snapshot_id"]
    url = artifact["resolved_content_url"]

    annex_elements = [
        el
        for el in tree.xpath("//*[@id]")
        if isinstance(el.tag, str) and ANNEX_ID_RE.fullmatch(el.get("id", ""))
    ]

    records: list[dict] = []
    per_annex_metrics: list[dict] = []
    unsupported_structures: list[dict] = []

    for annex_el in annex_elements:
        native_id = annex_el.get("id", "")
        match = ANNEX_ID_RE.fullmatch(native_id)
        if not match:
            raise ValueError(f"Unexpected annex id: {native_id}")
        roman = match.group(1)
        path = f"annex/{roman}"

        nonempty_children, unsupported, table_count = _inspect_annex_elements(annex_el)
        if unsupported:
            for item in unsupported:
                unsupported_structures.append({"native_id": native_id, **item})

        # Join nonempty direct children in source order and verify no text was lost from annex_el
        normalized_text = join_blocks(nonempty_children)
        container_text = join_blocks([annex_el])
        if normalized_text != container_text:
            raise ValueError(
                f"Text mismatch between nonempty direct children and full container in {native_id}"
            )

        record = {
            "schema_version": "0.1.0",
            "record_id": f"{snap}::{path}",
            "source_snapshot_id": snap,
            "parent_id": None,
            "unit_kind": "annex",
            "legal_function": "operative",
            "label": _annex_label_from_source(annex_el, roman),
            "locator": {
                "path": path,
                "annex": roman,
            },
            "language": "en",
            "tier": 1,
            "text": normalized_text,
            "text_sha256": digest(normalized_text),
            "source_location": {
                "url": url,
                "format": "html",
                "selector": tree.getpath(annex_el),
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
        per_annex_metrics.append(
            {
                "native_id": native_id,
                "annex_numeral": roman,
                "record_id": record["record_id"],
                "label": record["label"],
                "extracted_character_count": len(normalized_text),
                "source_table_count": table_count,
                "text_sha256": record["text_sha256"],
            }
        )

    return records, per_annex_metrics, unsupported_structures


def run_stage3_checks(
    records_pass1: list[dict],
    records_pass2: list[dict],
    per_annex_metrics: list[dict],
    unsupported_structures: list[dict],
    validator: Draft202012Validator,
    baseline_path: Path = ROOT / "records" / "review_records.json",
) -> dict:
    """Run focused offline verification checks for Stage 3 original annexes."""
    extracted_numerals = [r["locator"]["annex"] for r in records_pass1]
    record_ids = [r["record_id"] for r in records_pass1]
    selectors = [r["source_location"]["selector"] for r in records_pass1]

    # Check 1: Exactly 13 unique annex records, I–XIII in source order
    count_is_13 = len(records_pass1) == 13
    unique_record_ids = len(set(record_ids)) == 13
    unique_selectors = len(set(selectors)) == 13
    exact_i_to_xiii_order = extracted_numerals == EXPECTED_ANNEX_NUMERALS
    assert count_is_13, f"Expected 13 annex records, got {len(records_pass1)}"
    assert unique_record_ids, "Duplicate record_id values detected"
    assert unique_selectors, "Duplicate source_location selector values detected"
    assert exact_i_to_xiii_order, (
        f"Extracted annexes {extracted_numerals} do not match expected {EXPECTED_ANNEX_NUMERALS}"
    )

    # Check 2 & 4: Every record satisfies legal_record.schema.json and text_sha256 matches text
    all_sha256_match_text = True
    for record in records_pass1:
        validator.validate(record)
        assert record["unit_kind"] == "annex"
        assert record["legal_function"] == "operative"
        assert record["children"] == []
        assert record["cross_references"] == []
        assert record["validation_status"] == "pending"
        assert record["review_status"] == "not_reviewed"
        assert record["indexable"] is False
        computed_digest = digest(record["text"])
        if record["text_sha256"] != computed_digest:
            all_sha256_match_text = False
        assert record["text_sha256"] == computed_digest

    # Check 3: Original Annex III text and text_sha256 exactly match existing parent baseline
    baseline_records = json.loads(baseline_path.read_text(encoding="utf-8"))
    snap = records_pass1[0]["source_snapshot_id"]
    baseline_anx3_id = f"{snap}::annex/III"
    baseline_anx3 = next(
        (r for r in baseline_records if r["record_id"] == baseline_anx3_id),
        None,
    )
    if baseline_anx3 is None:
        raise ValueError(f"Baseline record not found: {baseline_anx3_id}")

    stage3_anx3 = next(
        (r for r in records_pass1 if r["record_id"] == baseline_anx3_id),
        None,
    )
    if stage3_anx3 is None:
        raise ValueError(f"Stage 3 Annex III record not found: {baseline_anx3_id}")

    anx3_text_matches = stage3_anx3["text"] == baseline_anx3["text"]
    anx3_sha256_matches = stage3_anx3["text_sha256"] == baseline_anx3["text_sha256"]
    anx3_selector_matches = (
        stage3_anx3["source_location"]["selector"]
        == baseline_anx3["source_location"]["selector"]
    )
    assert anx3_text_matches, "Stage 3 Annex III text does not match baseline"
    assert anx3_sha256_matches, "Stage 3 Annex III text_sha256 does not match baseline"
    assert anx3_selector_matches, "Stage 3 Annex III selector does not match baseline"

    # Check 5: Repeating extraction produces identical records
    reproducible = records_pass1 == records_pass2
    assert reproducible, "Second extraction did not produce identical records"

    return {
        "stage": "original_annexes_stage3",
        "source_id": SOURCE_ID,
        "source_snapshot_id": snap,
        "record_count": len(records_pass1),
        "technical_checks": {
            "manifest_sha256_verified": True,
            "exact_13_unique_annexes_I_to_XIII_in_order": (
                count_is_13 and unique_record_ids and unique_selectors and exact_i_to_xiii_order
            ),
            "all_records_satisfy_json_schema": True,
            "all_text_sha256_match_extracted_text": all_sha256_match_text,
            "annex_III_matches_baseline_text_and_sha256": (
                anx3_text_matches and anx3_sha256_matches and anx3_selector_matches
            ),
            "annex_III_text_sha256": stage3_anx3["text_sha256"],
            "annex_III_char_length": len(stage3_anx3["text"]),
            "second_extraction_identical": reproducible,
            "unsupported_nonempty_element_count": len(unsupported_structures),
        },
        "limitations_and_scope": {
            "structural_table_records_created": False,
            "row_column_semantics_established": False,
            "table_text_limitation": (
                "This checkpoint extracts complete parent annex records only and does not "
                "create structural table or table_row records. While all meaningful table-cell "
                "text is retained in source order under legal-whitespace-v1 normalization, "
                "retaining flattened table text does not yet establish preservation of "
                "row/column semantics (such as 2-column or 3-column list-item marker/body "
                "cells in OJ Annexes I–XIII or multi-row data tables in Consolidated Annex XIV)."
            ),
            "child_decomposition_performed": False,
            "cross_reference_or_risk_inference_performed": False,
            "consolidated_or_annex_xiv_parsed": False,
        },
        "content_review_and_ingestion_status": {
            "validation_status": "pending",
            "review_status": "not_reviewed",
            "all_indexable_false": True,
            "legally_reviewed": False,
            "ready_for_indexing": False,
            "note": (
                "Passing Stage 3 technical extraction checks does not mean the corpus is "
                "legally reviewed or ready for indexing."
            ),
        },
        "unsupported_nonempty_structures": unsupported_structures,
        "annex_inventory": per_annex_metrics,
    }


def main() -> None:
    schema = json.loads((ROOT / "legal_record.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    artifact = load_source_artifact()

    records_pass1, per_annex_metrics, unsupported_structures = extract_original_annexes(
        artifact, validator
    )
    records_pass2, _, _ = extract_original_annexes(artifact, validator)

    report = run_stage3_checks(
        records_pass1,
        records_pass2,
        per_annex_metrics,
        unsupported_structures,
        validator,
    )

    records_out = ROOT / "records" / "original_annexes_stage3.json"
    records_out.parent.mkdir(parents=True, exist_ok=True)
    records_out.write_text(
        json.dumps(records_pass1, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    report_out = ROOT / "reports" / "original_annexes_stage3_validation.json"
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
                "unsupported_nonempty_element_count": len(unsupported_structures),
                "review_status": report["content_review_and_ingestion_status"]["review_status"],
                "indexable": False,
            }
        )
    )


if __name__ == "__main__":
    main()
