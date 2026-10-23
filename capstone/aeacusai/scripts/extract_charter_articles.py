"""Stage 6 offline parser checkpoint: extract complete article parent records (Articles 1–54)
from the pinned Charter of Fundamental Rights of the European Union source (T1-CHARTER-OJ-2012).

Preserves all existing files, the 45-record review baseline, and Stage 1–5 outputs.
Performs no paragraph child decomposition, no Charter-to-AI-Act mapping inference,
no rights-impact classification, and no network, embedding, or vector-store operations.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from lxml import etree
from jsonschema import Draft202012Validator

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from extract_review_samples import NS, ROOT, article_block, digest, join_blocks, parse, text

CHARTER_SOURCE_ID = "T1-CHARTER-OJ-2012"
EXPECTED_CHARTER_ARTICLES = [str(i) for i in range(1, 55)]

# Known (tag, class) patterns inside Charter article sibling blocks
SUPPORTED_CHARTER_ARTICLE_TAG_CLASSES = {
    ("p", "ti-art"),
    ("p", "sti-art"),
    ("p", "normal"),
    ("p", "ti-grseq-1"),
    ("table", None),
    ("tbody", None),
    ("tr", None),
    ("td", None),
    ("col", None),
    ("span", None),
}


def load_charter_artifact(
    manifest_path: Path = ROOT / "acquisition_manifest.json",
) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = {a["source_id"]: a for a in manifest["artifacts"]}
    if CHARTER_SOURCE_ID not in artifacts:
        raise ValueError(f"Missing required artifact in manifest: {CHARTER_SOURCE_ID}")
    artifact = artifacts[CHARTER_SOURCE_ID]
    raw_path = ROOT / artifact["relative_path"]
    actual_sha256 = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    if actual_sha256 != artifact["sha256"]:
        raise ValueError(
            f"Source artifact checksum mismatch for {CHARTER_SOURCE_ID}: "
            f"expected {artifact['sha256']}, got {actual_sha256}"
        )
    return artifact


def _inspect_non_article_material(tree) -> dict:
    """Catalog preamble, title headings, and any footnote/closing material outside article boundaries."""
    body_children = [el for el in tree.xpath("//h:body/*", namespaces=NS) if isinstance(el.tag, str)]
    main_div = tree.xpath("//h:div[@id='C_2012326EN.01039301']", namespaces=NS)[0]
    main_children = [el for el in main_div if isinstance(el.tag, str)]

    # Top-level body elements outside main_div (OJ banner, pre-div title listing, separators)
    outside_main_div = [
        {
            "selector": tree.getpath(el),
            "tag": etree.QName(el).localname,
            "class": el.get("class"),
            "text_excerpt": text(el)[:120],
        }
        for el in body_children
        if el is not main_div
    ]

    # Preamble blocks inside main_div before first TITLE I heading (indices 0..9)
    first_title_idx = next(
        i for i, el in enumerate(main_children) if el.get("class") == "ti-section-1"
    )
    preamble_elements = [
        {
            "child_index": i,
            "selector": tree.getpath(el),
            "tag": etree.QName(el).localname,
            "class": el.get("class"),
            "text_excerpt": text(el)[:120],
        }
        for i, el in enumerate(main_children[:first_title_idx])
    ]

    # Title headings (ti-section-1 / ti-section-2 pairs) inside main_div
    title_headings = []
    for i, el in enumerate(main_children):
        if el.get("class") == "ti-section-1":
            sub = (
                main_children[i + 1]
                if i + 1 < len(main_children) and main_children[i + 1].get("class") == "ti-section-2"
                else None
            )
            title_headings.append(
                {
                    "title_number": text(el),
                    "title_name": text(sub) if sub is not None else "",
                    "selectors": [tree.getpath(el)]
                    + ([tree.getpath(sub)] if sub is not None else []),
                }
            )

    # Footnote / anchor check across the entire Charter XHTML
    footnote_or_note_elements = tree.xpath(
        "//*[contains(@class, 'note') or contains(@class, 'footnote')]",
        namespaces=NS,
    )

    # Explicit inspection of Article 54's end boundary
    art54_elements = article_block(tree, 54)
    art54_operative_only = [
        el for el in art54_elements if el.get("class") in {"ti-art", "sti-art"} or not text(el).startswith(("°", "The above text adapts"))
    ]
    art54_trailing_proclamation = [
        {
            "selector": tree.getpath(el),
            "tag": etree.QName(el).localname,
            "class": el.get("class"),
            "text": text(el),
        }
        for el in art54_elements
        if el not in art54_operative_only
    ]

    return {
        "top_level_body_elements_outside_main_container_count": len(outside_main_div),
        "top_level_body_elements_outside_main_container": outside_main_div,
        "preamble_elements_before_title_I_count": len(preamble_elements),
        "preamble_elements_before_title_I": preamble_elements,
        "title_heading_pairs_count": len(title_headings),
        "title_heading_pairs": title_headings,
        "footnote_elements_in_source_count": len(footnote_or_note_elements),
        "article_54_end_boundary_inspection": {
            "baseline_rule": (
                "article_block(tree, number) collects p.ti-art ('Article N') and subsequent "
                "siblings inside div#C_2012326EN.01039301 until the next {'ti-art', 'ti-section-1', "
                "'ti-section-2'} element or the end of div#C_2012326EN.01039301."
            ),
            "baseline_selector": " | ".join(tree.getpath(e) for e in art54_elements),
            "baseline_char_length": len(join_blocks(art54_elements)),
            "baseline_text_sha256": digest(join_blocks(art54_elements)),
            "operative_only_selector_without_closing_note": " | ".join(
                tree.getpath(e) for e in art54_operative_only
            ),
            "operative_only_char_length": len(join_blocks(art54_operative_only)),
            "operative_only_text_sha256": digest(join_blocks(art54_operative_only)),
            "trailing_siblings_after_article_54_paragraph": art54_trailing_proclamation,
            "handling_note": (
                "Following the existing Charter baseline rule in scripts/extract_review_samples.py "
                "and records/review_records.json, Article 54's sibling scan stops at the end of "
                "div#C_2012326EN.01039301 (excluding body-level <hr class='doc-end'/>) and retains "
                "the three trailing sibling blocks ('°', '°°', and the Lisbon proclamation adaptation "
                "sentence) so that Article 54 matches the baseline text and text_sha256 "
                "(4003a2b3d029a370a04f55c897735bd93ea51db879017896a378b13f9a16cb3d) exactly. "
                "Both the baseline-compatible span and the operative-only span are documented here "
                "for explicit boundary transparency."
            ),
        },
    }


def extract_charter_articles(
    artifact: dict,
    validator: Draft202012Validator,
) -> tuple[list[dict], list[dict], dict]:
    """Extract all 54 Charter articles (1–54) in document order following baseline boundary rules."""
    raw_path = ROOT / artifact["relative_path"]
    tree = parse(raw_path)
    snap = artifact["source_snapshot_id"]
    url = artifact["resolved_content_url"]

    headings = tree.xpath("//h:p[@class='ti-art']", namespaces=NS)
    observed_heading_texts = [text(h) for h in headings]
    expected_heading_texts = [f"Article {i}" for i in range(1, 55)]
    if observed_heading_texts != expected_heading_texts:
        raise ValueError(
            f"Charter article headings do not match ordered Article 1–54: {observed_heading_texts}"
        )

    records: list[dict] = []
    unsupported_structures: list[dict] = []

    for number_int in range(1, 55):
        number = str(number_int)
        elements = article_block(tree, number_int)
        for el in elements:
            for desc in el.iter():
                if not isinstance(desc.tag, str):
                    continue
                tname = etree.QName(desc).localname
                cls = desc.get("class")
                dtext = text(desc)
                if dtext and (tname, cls) not in SUPPORTED_CHARTER_ARTICLE_TAG_CLASSES:
                    unsupported_structures.append(
                        {
                            "article": number,
                            "tag": tname,
                            "class": cls,
                            "text_excerpt": dtext[:120],
                        }
                    )

        path = f"article/{number}"
        normalized_text = join_blocks(elements)
        record = {
            "schema_version": "0.1.0",
            "record_id": f"{snap}::{path}",
            "source_snapshot_id": snap,
            "parent_id": None,
            "unit_kind": "article",
            "legal_function": "operative",
            "label": f"Charter Article {number}",
            "locator": {
                "path": path,
                "article": number,
            },
            "language": "en",
            "tier": 1,
            "text": normalized_text,
            "text_sha256": digest(normalized_text),
            "source_location": {
                "url": url,
                "format": "html",
                "selector": " | ".join(tree.getpath(e) for e in elements),
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

    boundary_report = _inspect_non_article_material(tree)
    return records, unsupported_structures, boundary_report


def run_stage6_checks(
    records_pass1: list[dict],
    records_pass2: list[dict],
    unsupported_structures: list[dict],
    boundary_report: dict,
    validator: Draft202012Validator,
    baseline_path: Path = ROOT / "records" / "review_records.json",
    stage1_path: Path = ROOT / "records" / "original_articles_stage1.json",
    stage4_path: Path = ROOT / "records" / "consolidated_articles_stage4.json",
) -> dict:
    """Run focused offline verification checks for Stage 6 Charter articles."""
    extracted_numbers = [r["locator"]["article"] for r in records_pass1]
    record_ids = [r["record_id"] for r in records_pass1]
    selectors = [r["source_location"]["selector"] for r in records_pass1]

    # Check 1: Exactly 54 unique articles, numbered 1–54 in source order
    count_is_54 = len(records_pass1) == 54
    unique_record_ids = len(set(record_ids)) == 54
    unique_selectors = len(set(selectors)) == 54
    exact_1_to_54_order = extracted_numbers == EXPECTED_CHARTER_ARTICLES
    assert count_is_54, f"Expected 54 Charter article records, got {len(records_pass1)}"
    assert unique_record_ids, "Duplicate record_id values detected"
    assert unique_selectors, "Duplicate source_location selector values detected"
    assert exact_1_to_54_order, "Extracted Charter articles do not match ordered Articles 1–54"

    # Check 2 & 4: Every record satisfies legal_record.schema.json and text_sha256 matches text
    all_sha256_match_text = True
    for record in records_pass1:
        validator.validate(record)
        num = record["locator"]["article"]
        assert record["unit_kind"] == "article"
        assert record["legal_function"] == "operative"
        assert record["label"] == f"Charter Article {num}"
        assert record["children"] == []
        assert record["cross_references"] == []
        assert record["validation_status"] == "pending"
        assert record["review_status"] == "not_reviewed"
        assert record["indexable"] is False
        computed_digest = digest(record["text"])
        if record["text_sha256"] != computed_digest:
            all_sha256_match_text = False
        assert record["text_sha256"] == computed_digest
        assert record["text"].startswith(f"Article {num} "), (
            f"Charter Article {num} text does not start with heading 'Article {num} '"
        )

    # Check 3: Articles 21 and 51–54 exactly match existing baseline text, text_sha256, and full record
    baseline_records = json.loads(baseline_path.read_text(encoding="utf-8"))
    snap = records_pass1[0]["source_snapshot_id"]
    baseline_by_id = {r["record_id"]: r for r in baseline_records}
    stage6_by_id = {r["record_id"]: r for r in records_pass1}

    baseline_target_numbers = ["21", "51", "52", "53", "54"]
    baseline_comparisons = {}
    all_baseline_targets_match = True
    for num in baseline_target_numbers:
        target_id = f"{snap}::article/{num}"
        if target_id not in baseline_by_id:
            raise ValueError(f"Missing baseline Charter record: {target_id}")
        if target_id not in stage6_by_id:
            raise ValueError(f"Missing Stage 6 Charter record: {target_id}")
        base_rec = baseline_by_id[target_id]
        s6_rec = stage6_by_id[target_id]
        text_eq = s6_rec["text"] == base_rec["text"]
        sha_eq = s6_rec["text_sha256"] == base_rec["text_sha256"]
        sel_eq = s6_rec["source_location"]["selector"] == base_rec["source_location"]["selector"]
        rec_eq = s6_rec == base_rec
        if not (text_eq and sha_eq and sel_eq and rec_eq):
            all_baseline_targets_match = False
        assert text_eq, f"Charter Article {num} text mismatch against baseline"
        assert sha_eq, f"Charter Article {num} text_sha256 mismatch against baseline"
        assert sel_eq, f"Charter Article {num} selector mismatch against baseline"
        assert rec_eq, f"Charter Article {num} record mismatch against baseline"
        baseline_comparisons[f"article/{num}"] = {
            "record_id": target_id,
            "text_matches": text_eq,
            "text_sha256_matches": sha_eq,
            "selector_matches": sel_eq,
            "char_length": len(s6_rec["text"]),
            "text_sha256": s6_rec["text_sha256"],
        }

    # Check 5: Repeating extraction produces identical records
    reproducible = records_pass1 == records_pass2
    assert reproducible, "Second extraction did not produce identical records"

    # Check 6: Record IDs use the Charter source snapshot and do not collide with AI Act record IDs
    stage1_ids = {
        r["record_id"]
        for r in json.loads(stage1_path.read_text(encoding="utf-8"))
    }
    stage4_ids = {
        r["record_id"]
        for r in json.loads(stage4_path.read_text(encoding="utf-8"))
    }
    stage6_ids = set(record_ids)
    all_use_charter_snapshot = all(
        r["source_snapshot_id"] == snap and r["record_id"].startswith(snap + "::")
        for r in records_pass1
    )
    no_ai_act_id_collision = (
        len(stage6_ids.intersection(stage1_ids)) == 0
        and len(stage6_ids.intersection(stage4_ids)) == 0
    )
    assert all_use_charter_snapshot, "Not all records use the Charter snapshot ID"
    assert no_ai_act_id_collision, "Record ID collision detected with AI Act article records"

    return {
        "stage": "charter_articles_stage6",
        "source_id": CHARTER_SOURCE_ID,
        "source_snapshot_id": snap,
        "record_count": len(records_pass1),
        "technical_checks": {
            "manifest_sha256_verified": True,
            "exact_54_unique_articles_1_to_54_in_order": (
                count_is_54 and unique_record_ids and unique_selectors and exact_1_to_54_order
            ),
            "all_records_satisfy_json_schema": True,
            "all_text_sha256_match_extracted_text": all_sha256_match_text,
            "articles_21_and_51_to_54_match_baseline_text_and_sha256": all_baseline_targets_match,
            "second_extraction_identical": reproducible,
            "all_records_use_charter_snapshot_id": all_use_charter_snapshot,
            "zero_record_id_collisions_with_ai_act_records": no_ai_act_id_collision,
            "unsupported_nonempty_element_count": len(unsupported_structures),
        },
        "baseline_parity_details": baseline_comparisons,
        "boundary_and_non_article_material_handling": boundary_report,
        "content_review_and_ingestion_status": {
            "validation_status": "pending",
            "review_status": "not_reviewed",
            "all_indexable_false": True,
            "charter_to_ai_act_mapping_inferred": False,
            "rights_impact_classified": False,
            "legally_reviewed": False,
            "ready_for_indexing": False,
            "note": (
                "Passing Stage 6 technical extraction checks does not mean the corpus is "
                "legally reviewed or ready for indexing. No Charter-to-AI-Act mappings or "
                "rights-impact classifications are inferred."
            ),
        },
        "unsupported_nonempty_structures": unsupported_structures,
        "extracted_article_inventory": {
            "first_article_id": records_pass1[0]["record_id"],
            "first_article_label": records_pass1[0]["label"],
            "last_article_id": records_pass1[-1]["record_id"],
            "last_article_label": records_pass1[-1]["label"],
            "articles_containing_lettered_subpoint_tables": ["article/3", "article/41"],
            "article_numbers": extracted_numbers,
        },
    }


def main() -> None:
    schema = json.loads((ROOT / "legal_record.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    artifact = load_charter_artifact()

    records_pass1, unsupported_structures, boundary_report = extract_charter_articles(
        artifact, validator
    )
    records_pass2, _, _ = extract_charter_articles(artifact, validator)

    report = run_stage6_checks(
        records_pass1,
        records_pass2,
        unsupported_structures,
        boundary_report,
        validator,
    )

    records_out = ROOT / "records" / "charter_articles_stage6.json"
    records_out.parent.mkdir(parents=True, exist_ok=True)
    records_out.write_text(
        json.dumps(records_pass1, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    report_out = ROOT / "reports" / "charter_articles_stage6_validation.json"
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
