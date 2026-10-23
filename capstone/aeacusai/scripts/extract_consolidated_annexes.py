"""Stage 5 offline parser checkpoint: extract complete annex parent records (Annexes I–XIV)
from the pinned consolidated EU AI Act edition dated 2026-07-27 (T1-AIA-CONS-20260727).

Preserves all existing files and Stage 1–4 outputs.
Retains complete parent annex text only, including all headings, clauses, lists, and
table-cell text in source order while skipping genuinely empty layout elements.
Performs no child record decomposition, row/column table structure modeling,
cross-reference inference, network calls, embeddings, or vector-store operations.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from lxml import etree
from jsonschema import Draft202012Validator

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from extract_consolidated_articles import (
    CONSOLIDATED_SOURCE_ID,
    load_consolidated_artifact,
)
from extract_original_annexes import ANNEX_ID_RE, EXPECTED_ANNEX_NUMERALS
from extract_review_samples import NS, ROOT, digest, join_blocks, parse, text

EXPECTED_CONSOLIDATED_ANNEX_NUMERALS = [*EXPECTED_ANNEX_NUMERALS, "XIV"]

# Known nonempty (tag, class) patterns inside native annex containers in T1-AIA-CONS-20260727
SUPPORTED_CONSOLIDATED_ANNEX_TAG_CLASSES = {
    ("div", None),
    ("div", "centered"),
    ("div", "grid-container grid-list"),
    ("div", "list grid-list-column-1"),
    ("div", "grid-list-column-2"),
    ("div", "list"),
    ("p", "title-annex-1"),
    ("p", "title-annex-2"),
    ("p", "title-gr-seq-level-1"),
    ("p", "title-gr-seq-level-2"),
    ("p", "norm"),
    ("p", "normal"),
    ("p", "list"),
    ("p", "modref"),
    ("p", "tbl-norm"),
    ("p", None),
    ("table", None),
    ("tbody", None),
    ("tr", None),
    ("td", None),
    ("col", None),
    ("span", None),
    ("span", "boldface"),
    ("span", "italics"),
    ("span", "norm"),
    ("a", None),
}


def _consolidated_annex_label_from_source(annex_el, roman: str) -> str:
    """Build the annex label from native title-annex-1 / title-annex-2 headings in the source."""
    title_1 = [
        text(el)
        for el in annex_el.xpath("./h:p[@class='title-annex-1']", namespaces=NS)
        if text(el)
    ]
    title_2 = [
        text(el)
        for el in annex_el.xpath("./h:p[@class='title-annex-2']", namespaces=NS)
        if text(el)
    ]
    subtitles = title_1[1:] + title_2
    if subtitles:
        return f"Annex {roman} — {' — '.join(subtitles)}"
    return f"Annex {roman}"


def _inspect_consolidated_annex(
    annex_el,
) -> tuple[list[etree._Element], list[dict], list[dict], int]:
    """Classify direct children into nonempty content blocks vs. empty layout elements,
    detect any unsupported nonempty descendants, and count source tables.

    Never discards paragraphs based solely on tag name; skips only elements whose
    normalized text is genuinely empty (such as <p><br/></p> or <hr class='separator-annex'/>).
    """
    nonempty_children: list[etree._Element] = []
    skipped_empty_children: list[dict] = []
    unsupported_nonempty: list[dict] = []

    for idx, child in enumerate(annex_el):
        if not isinstance(child.tag, str):
            continue
        tag_name = etree.QName(child).localname
        cls_name = child.get("class")
        child_text = text(child)
        if not child_text:
            skipped_empty_children.append(
                {
                    "child_index": idx,
                    "tag": tag_name,
                    "class": cls_name,
                    "inner_tags": [
                        etree.QName(gc).localname
                        for gc in child
                        if isinstance(gc.tag, str)
                    ],
                }
            )
            continue
        nonempty_children.append(child)

    for desc in annex_el.iter():
        if not isinstance(desc.tag, str):
            continue
        tag_name = etree.QName(desc).localname
        cls_name = desc.get("class")
        desc_text = text(desc)
        if desc_text and (tag_name, cls_name) not in SUPPORTED_CONSOLIDATED_ANNEX_TAG_CLASSES:
            unsupported_nonempty.append(
                {
                    "tag": tag_name,
                    "class": cls_name,
                    "id": desc.get("id"),
                    "text_excerpt": desc_text[:120],
                }
            )

    tables = annex_el.xpath(".//h:table", namespaces=NS)
    return nonempty_children, skipped_empty_children, unsupported_nonempty, len(tables)


def _inspect_annex_xiv_components(annex_xiv_el) -> dict:
    """Extract and summarize the specific structural components of Annex XIV for verification."""
    section_headings = [
        text(el)
        for el in annex_xiv_el.xpath("./h:p[@class='title-gr-seq-level-1']", namespaces=NS)
        if text(el)
    ]
    subsection_headings = [
        text(el)
        for el in annex_xiv_el.xpath("./h:p[@class='title-gr-seq-level-2']", namespaces=NS)
        if text(el)
    ]
    norm_paragraphs = [
        text(el)
        for el in annex_xiv_el.xpath("./h:p[@class='norm']", namespaces=NS)
        if text(el)
    ]
    tables = annex_xiv_el.xpath(".//h:table", namespaces=NS)
    table_summaries = []
    for idx, tbl in enumerate(tables, start=1):
        tbl_text = text(tbl)
        rows = tbl.xpath(".//h:tr", namespaces=NS)
        codes = [
            text(tr[0])
            for tr in rows[1:]
            if len(tr) >= 1 and text(tr[0])
        ]
        table_summaries.append(
            {
                "table_index": idx,
                "row_count": len(rows),
                "aia_codes": codes,
                "normalized_text": tbl_text,
                "char_count": len(tbl_text),
            }
        )
    return {
        "section_headings": section_headings,
        "subsection_headings": subsection_headings,
        "norm_paragraphs": norm_paragraphs,
        "tables": table_summaries,
    }


def extract_consolidated_annexes(
    artifact: dict,
    validator: Draft202012Validator,
) -> tuple[list[dict], list[dict], list[dict], dict]:
    """Extract all 14 native annex containers (I–XIV) in document order from T1-AIA-CONS-20260727."""
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
    annex_xiv_details: dict = {}

    for annex_el in annex_elements:
        native_id = annex_el.get("id", "")
        match = ANNEX_ID_RE.fullmatch(native_id)
        if not match:
            raise ValueError(f"Unexpected annex id: {native_id}")
        roman = match.group(1)
        path = f"annex/{roman}"

        (
            nonempty_children,
            skipped_empty_children,
            unsupported,
            table_count,
        ) = _inspect_consolidated_annex(annex_el)

        if unsupported:
            for item in unsupported:
                unsupported_structures.append({"native_id": native_id, **item})

        normalized_text = join_blocks(nonempty_children)
        container_text = join_blocks([annex_el])
        if normalized_text != container_text:
            raise ValueError(
                f"Text mismatch between nonempty direct children and full container in {native_id}"
            )

        if roman == "XIV":
            annex_xiv_details = {
                "skipped_empty_layout_elements": skipped_empty_children,
                "preserved_nonempty_direct_child_count": len(nonempty_children),
                **_inspect_annex_xiv_components(annex_el),
            }

        record = {
            "schema_version": "0.1.0",
            "record_id": f"{snap}::{path}",
            "source_snapshot_id": snap,
            "parent_id": None,
            "unit_kind": "annex",
            "legal_function": "operative",
            "label": _consolidated_annex_label_from_source(annex_el, roman),
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
                "skipped_empty_layout_element_count": len(skipped_empty_children),
                "text_sha256": record["text_sha256"],
            }
        )

    return records, per_annex_metrics, unsupported_structures, annex_xiv_details


def run_stage5_checks(
    records_pass1: list[dict],
    records_pass2: list[dict],
    per_annex_metrics: list[dict],
    unsupported_structures: list[dict],
    annex_xiv_details: dict,
    validator: Draft202012Validator,
    baseline_path: Path = ROOT / "records" / "review_records.json",
    stage3_path: Path = ROOT / "records" / "original_annexes_stage3.json",
) -> dict:
    """Run focused offline verification checks for Stage 5 consolidated annexes."""
    extracted_numerals = [r["locator"]["annex"] for r in records_pass1]
    record_ids = [r["record_id"] for r in records_pass1]
    selectors = [r["source_location"]["selector"] for r in records_pass1]

    # Check 1: Exactly 14 unique annex records, I–XIV in source order
    count_is_14 = len(records_pass1) == 14
    unique_record_ids = len(set(record_ids)) == 14
    unique_selectors = len(set(selectors)) == 14
    exact_i_to_xiv_order = extracted_numerals == EXPECTED_CONSOLIDATED_ANNEX_NUMERALS
    assert count_is_14, f"Expected 14 annex records, got {len(records_pass1)}"
    assert unique_record_ids, "Duplicate record_id values detected"
    assert unique_selectors, "Duplicate source_location selector values detected"
    assert exact_i_to_xiv_order, (
        f"Extracted annexes {extracted_numerals} do not match expected {EXPECTED_CONSOLIDATED_ANNEX_NUMERALS}"
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

    # Check 3: Consolidated Annex III text and text_sha256 exactly match existing parent baseline
    baseline_records = json.loads(baseline_path.read_text(encoding="utf-8"))
    snap = records_pass1[0]["source_snapshot_id"]
    baseline_anx3_id = f"{snap}::annex/III"
    baseline_anx3 = next(
        (r for r in baseline_records if r["record_id"] == baseline_anx3_id),
        None,
    )
    if baseline_anx3 is None:
        raise ValueError(f"Baseline record not found: {baseline_anx3_id}")

    stage5_anx3 = next(
        (r for r in records_pass1 if r["record_id"] == baseline_anx3_id),
        None,
    )
    if stage5_anx3 is None:
        raise ValueError(f"Stage 5 Annex III record not found: {baseline_anx3_id}")

    anx3_text_matches = stage5_anx3["text"] == baseline_anx3["text"]
    anx3_sha256_matches = stage5_anx3["text_sha256"] == baseline_anx3["text_sha256"]
    anx3_selector_matches = (
        stage5_anx3["source_location"]["selector"]
        == baseline_anx3["source_location"]["selector"]
    )
    assert anx3_text_matches, "Stage 5 Consolidated Annex III text does not match baseline"
    assert anx3_sha256_matches, "Stage 5 Consolidated Annex III text_sha256 does not match baseline"
    assert anx3_selector_matches, "Stage 5 Consolidated Annex III selector does not match baseline"

    # Check 5: Repeating extraction produces identical records
    reproducible = records_pass1 == records_pass2
    assert reproducible, "Second extraction did not produce identical records"

    # Check 6: No record IDs collide with Stage 3 original-edition annex IDs
    stage3_records = json.loads(stage3_path.read_text(encoding="utf-8"))
    stage3_ids = {r["record_id"] for r in stage3_records}
    stage5_ids = set(record_ids)
    all_use_consolidated_snapshot = all(
        r["source_snapshot_id"] == snap and r["record_id"].startswith(snap + "::")
        for r in records_pass1
    )
    no_stage3_id_collision = len(stage3_ids.intersection(stage5_ids)) == 0
    assert all_use_consolidated_snapshot, "Not all records use the consolidated snapshot ID"
    assert no_stage3_id_collision, "Record ID collision detected between Stage 3 and Stage 5"

    # Check 7: Annex XIV retains all section/subsection headings, all 3 p.norm blocks,
    # and all 6 code tables in source order
    stage5_anx14 = next(r for r in records_pass1 if r["locator"]["annex"] == "XIV")
    anx14_text = stage5_anx14["text"]
    norm_blocks = annex_xiv_details["norm_paragraphs"]
    table_entries = annex_xiv_details["tables"]
    section_headings = annex_xiv_details["section_headings"]
    subsection_headings = annex_xiv_details["subsection_headings"]

    assert len(norm_blocks) == 3, f"Expected 3 p.norm blocks in Annex XIV, got {len(norm_blocks)}"
    assert len(table_entries) == 6, f"Expected 6 tables in Annex XIV, got {len(table_entries)}"
    assert len(section_headings) == 4, f"Expected 4 level-1 headings in Annex XIV, got {len(section_headings)}"
    assert len(subsection_headings) == 6, f"Expected 6 level-2 headings in Annex XIV, got {len(subsection_headings)}"

    # Verify ordered appearance in Annex XIV text
    ordered_snippets = [
        "ANNEX XIV",
        norm_blocks[0],
        section_headings[0],
        norm_blocks[1],
        section_headings[1],
        subsection_headings[0],
        table_entries[0]["normalized_text"],
        subsection_headings[1],
        table_entries[1]["normalized_text"],
        section_headings[2],
        subsection_headings[2],
        table_entries[2]["normalized_text"],
        subsection_headings[3],
        table_entries[3]["normalized_text"],
        subsection_headings[4],
        table_entries[4]["normalized_text"],
        subsection_headings[5],
        table_entries[5]["normalized_text"],
        section_headings[3],
        norm_blocks[2],
    ]
    cursor = 0
    anx14_ordered_preservation = True
    for snippet in ordered_snippets:
        pos = anx14_text.find(snippet, cursor)
        if pos == -1:
            anx14_ordered_preservation = False
            break
        cursor = pos + len(snippet)
    assert anx14_ordered_preservation, (
        "Annex XIV text does not preserve all headings, 3 p.norm blocks, and 6 tables in source order"
    )

    return {
        "stage": "consolidated_annexes_stage5",
        "source_id": CONSOLIDATED_SOURCE_ID,
        "source_snapshot_id": snap,
        "edition_description": (
            "Pinned consolidated reading edition dated 2026-07-27 (CELEX 02024R1689-20260727). "
            "Consolidated texts produced by the Publications Office are meant purely as a "
            "documentation/reading tool and are not independently authentic Official Journal "
            "legislation, nor does this extraction claim that this snapshot is the latest or "
            "currently applicable law."
        ),
        "record_count": len(records_pass1),
        "technical_checks": {
            "manifest_sha256_verified": True,
            "exact_14_unique_annexes_I_to_XIV_in_order": (
                count_is_14 and unique_record_ids and unique_selectors and exact_i_to_xiv_order
            ),
            "all_records_satisfy_json_schema": True,
            "all_text_sha256_match_extracted_text": all_sha256_match_text,
            "consolidated_annex_III_matches_baseline_text_and_sha256": (
                anx3_text_matches and anx3_sha256_matches and anx3_selector_matches
            ),
            "consolidated_annex_III_text_sha256": stage5_anx3["text_sha256"],
            "consolidated_annex_III_char_length": len(stage5_anx3["text"]),
            "second_extraction_identical": reproducible,
            "all_records_use_consolidated_snapshot_id": all_use_consolidated_snapshot,
            "zero_record_id_collisions_with_stage3_original_annexes": no_stage3_id_collision,
            "annex_XIV_retains_all_headings_3_norm_blocks_and_6_tables_in_order": (
                anx14_ordered_preservation
            ),
            "unsupported_nonempty_element_count": len(unsupported_structures),
        },
        "annex_xiv_verification": {
            "native_id": "anx_XIV",
            "record_id": stage5_anx14["record_id"],
            "extracted_character_count": len(anx14_text),
            "text_sha256": stage5_anx14["text_sha256"],
            "skipped_empty_layout_element_count": len(
                annex_xiv_details["skipped_empty_layout_elements"]
            ),
            "skipped_empty_layout_elements": annex_xiv_details["skipped_empty_layout_elements"],
            "preserved_nonempty_direct_child_count": annex_xiv_details[
                "preserved_nonempty_direct_child_count"
            ],
            "level_1_section_headings": section_headings,
            "level_2_subsection_headings": subsection_headings,
            "norm_paragraph_count": len(norm_blocks),
            "norm_paragraph_char_lengths": [len(p) for p in norm_blocks],
            "table_count": len(table_entries),
            "tables": [
                {
                    "table_index": t["table_index"],
                    "row_count": t["row_count"],
                    "aia_codes": t["aia_codes"],
                    "char_count": t["char_count"],
                }
                for t in table_entries
            ],
        },
        "limitations_and_scope": {
            "complete_parent_text_only": True,
            "structural_table_records_created": False,
            "row_column_semantics_established": False,
            "table_text_limitation": (
                "This checkpoint extracts complete parent annex records only and does not "
                "create structural section, point, table, or table_row child records. "
                "Although all 6 AIA code tables in Consolidated Annex XIV (and all grid-list "
                "blocks in Annexes I–XIII) have their text preserved in source order, "
                "flattened whitespace-normalized table text does not preserve row/column "
                "relational semantics."
            ),
            "child_decomposition_performed": False,
            "cross_reference_or_legal_mapping_inferred": False,
        },
        "content_review_and_ingestion_status": {
            "validation_status": "pending",
            "review_status": "not_reviewed",
            "all_indexable_false": True,
            "legally_reviewed": False,
            "ready_for_indexing": False,
            "note": (
                "Passing Stage 5 technical extraction checks does not mean the corpus is "
                "legally reviewed or ready for indexing."
            ),
        },
        "unsupported_nonempty_structures": unsupported_structures,
        "annex_inventory": per_annex_metrics,
    }


def main() -> None:
    schema = json.loads((ROOT / "legal_record.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    artifact = load_consolidated_artifact()

    (
        records_pass1,
        per_annex_metrics,
        unsupported_structures,
        annex_xiv_details,
    ) = extract_consolidated_annexes(artifact, validator)
    records_pass2, _, _, _ = extract_consolidated_annexes(artifact, validator)

    report = run_stage5_checks(
        records_pass1,
        records_pass2,
        per_annex_metrics,
        unsupported_structures,
        annex_xiv_details,
        validator,
    )

    records_out = ROOT / "records" / "consolidated_annexes_stage5.json"
    records_out.parent.mkdir(parents=True, exist_ok=True)
    records_out.write_text(
        json.dumps(records_pass1, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    report_out = ROOT / "reports" / "consolidated_annexes_stage5_validation.json"
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
