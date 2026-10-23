"""Stage 4 offline parser checkpoint: extract complete article-level parent records
from the pinned consolidated EU AI Act edition dated 2026-07-27 (T1-AIA-CONS-20260727).

This artifact is a pinned consolidated reading edition from the Publications Office /
EUR-Lex repository, not independently authentic Official Journal legislation and not
a claim of latest/current applicable law.

Preserves all existing scripts, sources, schemas, manifests, baseline records, and
Stage 1–3 outputs. Performs no paragraph child decomposition, annex parsing,
cross-reference resolution, network calls, embeddings, or vector-store operations.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from lxml import etree
from jsonschema import Draft202012Validator

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from extract_original_articles import ARTICLE_ID_RE
from extract_review_samples import NS, ROOT, digest, join_blocks, parse, text

CONSOLIDATED_SOURCE_ID = "T1-AIA-CONS-20260727"
REVISION_MARKER_RE = re.compile(r"(▼[A-Z0-9]+(?:\s*—————)?|►[A-Z0-9]+|◄)")

# Known (tag, class) patterns inside native article containers in T1-AIA-CONS-20260727
SUPPORTED_CONSOLIDATED_ARTICLE_TAG_CLASSES = {
    ("div", "eli-subdivision"),
    ("div", "eli-title"),
    ("div", "norm"),
    ("div", "norm inline-element"),
    ("div", "grid-container grid-list"),
    ("div", "list grid-list-column-1"),
    ("div", "grid-list-column-2"),
    ("p", "title-article-norm"),
    ("p", "stitle-article-norm"),
    ("p", "norm"),
    ("p", "norm inline-element"),
    ("p", "normal"),
    ("p", "modref"),
    ("span", None),
    ("span", "no-parag"),
    ("span", "italics"),
    ("span", "superscript"),
    ("a", None),
}


def load_consolidated_artifact(
    manifest_path: Path = ROOT / "acquisition_manifest.json",
) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = {a["source_id"]: a for a in manifest["artifacts"]}
    if CONSOLIDATED_SOURCE_ID not in artifacts:
        raise ValueError(f"Missing required artifact in manifest: {CONSOLIDATED_SOURCE_ID}")
    artifact = artifacts[CONSOLIDATED_SOURCE_ID]
    raw_path = ROOT / artifact["relative_path"]
    actual_sha256 = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    if actual_sha256 != artifact["sha256"]:
        raise ValueError(
            f"Source artifact checksum mismatch for {CONSOLIDATED_SOURCE_ID}: "
            f"expected {artifact['sha256']}, got {actual_sha256}"
        )
    return artifact


def _consolidated_article_label_from_source(article_el, fallback_number: str) -> str:
    """Build the article label from headings actually present in the consolidated source."""
    title_nodes = article_el.xpath(
        "./h:p[@class='title-article-norm'] | ./h:p[@class='oj-ti-art']",
        namespaces=NS,
    )
    subtitle_nodes = article_el.xpath(
        "./h:div[@class='eli-title']//h:p[@class='stitle-article-norm'] "
        "| ./h:p[@class='stitle-article-norm'] "
        "| ./h:div[@class='eli-title']//h:p[@class='oj-sti-art']",
        namespaces=NS,
    )
    heading = text(title_nodes[0]) if title_nodes else f"Article {fallback_number}"
    subtitle = text(subtitle_nodes[0]) if subtitle_nodes else ""
    return f"{heading} — {subtitle}" if subtitle else heading


def _inspect_article_elements(article_el) -> tuple[list[etree._Element], list[dict], int]:
    """Return nonempty direct child blocks, any unfamiliar nonempty structures, and table count."""
    nonempty_children: list[etree._Element] = []
    unsupported_nonempty: list[dict] = []

    for child in article_el:
        if not isinstance(child.tag, str):
            continue
        child_text = text(child)
        if not child_text:
            continue
        nonempty_children.append(child)

    for desc in article_el.iter():
        if not isinstance(desc.tag, str):
            continue
        tag_name = etree.QName(desc).localname
        cls_name = desc.get("class")
        desc_text = text(desc)
        if desc_text and (tag_name, cls_name) not in SUPPORTED_CONSOLIDATED_ARTICLE_TAG_CLASSES:
            unsupported_nonempty.append(
                {
                    "tag": tag_name,
                    "class": cls_name,
                    "id": desc.get("id"),
                    "text_excerpt": desc_text[:120],
                }
            )

    tables = article_el.xpath(".//h:table", namespaces=NS)
    return nonempty_children, unsupported_nonempty, len(tables)


def extract_consolidated_articles(
    artifact: dict,
    validator: Draft202012Validator,
) -> tuple[list[dict], list[dict], dict]:
    """Extract all 119 native article containers in document order from T1-AIA-CONS-20260727."""
    raw_path = ROOT / artifact["relative_path"]
    tree = parse(raw_path)
    snap = artifact["source_snapshot_id"]
    url = artifact["resolved_content_url"]

    article_elements = [
        el
        for el in tree.xpath("//*[@id]")
        if isinstance(el.tag, str) and ARTICLE_ID_RE.fullmatch(el.get("id", ""))
    ]

    records: list[dict] = []
    unsupported_structures: list[dict] = []
    articles_with_internal_markers: list[str] = []

    for article_el in article_elements:
        native_id = article_el.get("id", "")
        match = ARTICLE_ID_RE.fullmatch(native_id)
        if not match:
            raise ValueError(f"Unexpected article id: {native_id}")
        # Preserve native article identifier including letter suffixes (e.g. 4a, 60a, 75a..75d)
        number = match.group(1)
        path = f"article/{number}"

        nonempty_children, unsupported, _ = _inspect_article_elements(article_el)
        if unsupported:
            for item in unsupported:
                unsupported_structures.append({"native_id": native_id, **item})

        # Follow the consolidated Article 6 baseline convention: join_blocks([article_el])
        # retains all in-container text including child <p class="modref"> markers in source order.
        normalized_text = join_blocks(nonempty_children)
        container_text = join_blocks([article_el])
        if normalized_text != container_text:
            raise ValueError(
                f"Text mismatch between nonempty direct children and full container in {native_id}"
            )

        if REVISION_MARKER_RE.search(normalized_text):
            articles_with_internal_markers.append(native_id)

        record = {
            "schema_version": "0.1.0",
            "record_id": f"{snap}::{path}",
            "source_snapshot_id": snap,
            "parent_id": None,
            "unit_kind": "article",
            "legal_function": "operative",
            "label": _consolidated_article_label_from_source(article_el, number),
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
                "selector": tree.getpath(article_el),
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

    # Also catalog container-level sibling <p class="modref"> markers placed outside article divs
    sibling_modrefs_outside_articles: list[dict] = []
    for mod_el in tree.xpath("//h:p[@class='modref']", namespaces=NS):
        in_article = any(
            anc.get("id") and ARTICLE_ID_RE.fullmatch(anc.get("id", ""))
            for anc in mod_el.iterancestors()
        )
        if not in_article:
            parent_el = mod_el.getparent()
            next_el = mod_el.getnext()
            sibling_modrefs_outside_articles.append(
                {
                    "marker_text": text(mod_el),
                    "parent_id": parent_el.get("id") if parent_el is not None else None,
                    "following_sibling_id": (
                        next_el.get("id")
                        if next_el is not None and isinstance(next_el.tag, str)
                        else None
                    ),
                }
            )

    marker_summary = {
        "articles_containing_internal_modref_markers_count": len(articles_with_internal_markers),
        "articles_containing_internal_modref_markers": articles_with_internal_markers,
        "sibling_modrefs_outside_article_containers": sibling_modrefs_outside_articles,
    }
    return records, unsupported_structures, marker_summary


def run_stage4_checks(
    records_pass1: list[dict],
    records_pass2: list[dict],
    unsupported_structures: list[dict],
    marker_summary: dict,
    validator: Draft202012Validator,
    baseline_path: Path = ROOT / "records" / "review_records.json",
    stage1_path: Path = ROOT / "records" / "original_articles_stage1.json",
    validation_report_path: Path = ROOT / "validation_report.json",
) -> dict:
    """Run focused offline verification checks for Stage 4 consolidated articles."""
    expected_native_ids = json.loads(
        validation_report_path.read_text(encoding="utf-8")
    )["inventories"][CONSOLIDATED_SOURCE_ID]["native_article_ids"]
    extracted_numbers = [r["locator"]["article"] for r in records_pass1]
    extracted_native_ids = [f"art_{num}" for num in extracted_numbers]
    record_ids = [r["record_id"] for r in records_pass1]
    selectors = [r["source_location"]["selector"] for r in records_pass1]

    # Check 1: Exactly 119 unique article records matching native inventory and source order
    count_is_119 = len(records_pass1) == 119
    unique_record_ids = len(set(record_ids)) == 119
    unique_selectors = len(set(selectors)) == 119
    matches_native_inventory_order = extracted_native_ids == expected_native_ids
    assert count_is_119, f"Expected 119 records, got {len(records_pass1)}"
    assert unique_record_ids, "Duplicate record_id values detected"
    assert unique_selectors, "Duplicate source_location selector values detected"
    assert matches_native_inventory_order, (
        "Extracted article IDs do not match native consolidated article inventory in source order"
    )

    # Check 2 & 4: Every record satisfies legal_record.schema.json and text_sha256 matches text
    all_sha256_match_text = True
    for record in records_pass1:
        validator.validate(record)
        assert record["unit_kind"] == "article"
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

    # Check 3: Consolidated Article 6 text and text_sha256 exactly match existing parent baseline
    baseline_records = json.loads(baseline_path.read_text(encoding="utf-8"))
    snap = records_pass1[0]["source_snapshot_id"]
    baseline_art6_id = f"{snap}::article/6"
    baseline_art6 = next(
        (r for r in baseline_records if r["record_id"] == baseline_art6_id),
        None,
    )
    if baseline_art6 is None:
        raise ValueError(f"Baseline record not found: {baseline_art6_id}")

    stage4_art6 = next(
        (r for r in records_pass1 if r["record_id"] == baseline_art6_id),
        None,
    )
    if stage4_art6 is None:
        raise ValueError(f"Stage 4 Article 6 record not found: {baseline_art6_id}")

    art6_text_matches = stage4_art6["text"] == baseline_art6["text"]
    art6_sha256_matches = stage4_art6["text_sha256"] == baseline_art6["text_sha256"]
    art6_selector_matches = (
        stage4_art6["source_location"]["selector"]
        == baseline_art6["source_location"]["selector"]
    )
    assert art6_text_matches, "Stage 4 Consolidated Article 6 text does not match baseline"
    assert art6_sha256_matches, "Stage 4 Consolidated Article 6 text_sha256 does not match baseline"
    assert art6_selector_matches, "Stage 4 Consolidated Article 6 selector does not match baseline"

    # Check 5: Repeating extraction produces identical records
    reproducible = records_pass1 == records_pass2
    assert reproducible, "Second extraction did not produce identical records"

    # Check 6: Record IDs use the consolidated source snapshot and do not collide with Stage 1
    stage1_records = json.loads(stage1_path.read_text(encoding="utf-8"))
    stage1_ids = {r["record_id"] for r in stage1_records}
    stage4_ids = set(record_ids)
    all_use_consolidated_snapshot = all(
        r["source_snapshot_id"] == snap and r["record_id"].startswith(snap + "::")
        for r in records_pass1
    )
    no_stage1_id_collision = len(stage1_ids.intersection(stage4_ids)) == 0
    assert all_use_consolidated_snapshot, "Not all records use the consolidated snapshot ID"
    assert no_stage1_id_collision, "Record ID collision detected between Stage 1 and Stage 4"

    # Compare article identifiers present in this consolidated edition vs. Stage 1 original edition
    stage1_numbers = [r["locator"]["article"] for r in stage1_records]
    stage1_number_set = set(stage1_numbers)
    present_in_consolidated_absent_in_original = [
        {
            "native_id": f"art_{r['locator']['article']}",
            "article_identifier": r["locator"]["article"],
            "locator_path": r["locator"]["path"],
            "label": r["label"],
        }
        for r in records_pass1
        if r["locator"]["article"] not in stage1_number_set
    ]
    present_in_original_absent_in_consolidated = [
        f"art_{num}" for num in stage1_numbers if num not in set(extracted_numbers)
    ]

    return {
        "stage": "consolidated_articles_stage4",
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
            "exact_119_unique_articles_matching_native_inventory_in_order": (
                count_is_119
                and unique_record_ids
                and unique_selectors
                and matches_native_inventory_order
            ),
            "native_letter_suffix_identifiers_preserved_without_renumbering": (
                [item["article_identifier"] for item in present_in_consolidated_absent_in_original]
                == ["4a", "60a", "75a", "75b", "75c", "75d"]
            ),
            "all_records_satisfy_json_schema": True,
            "all_text_sha256_match_extracted_text": all_sha256_match_text,
            "consolidated_article_6_matches_baseline_text_and_sha256": (
                art6_text_matches and art6_sha256_matches and art6_selector_matches
            ),
            "consolidated_article_6_text_sha256": stage4_art6["text_sha256"],
            "consolidated_article_6_char_length": len(stage4_art6["text"]),
            "second_extraction_identical": reproducible,
            "all_records_use_consolidated_snapshot_id": all_use_consolidated_snapshot,
            "zero_record_id_collisions_with_stage1_original_articles": no_stage1_id_collision,
            "unsupported_nonempty_element_count": len(unsupported_structures),
        },
        "editorial_amendment_marker_treatment": {
            "treatment": (
                "Following the consolidated Article 6 parent baseline in records/review_records.json, "
                "each article parent record extracts the full normalized text of its native "
                "<div class='eli-subdivision' id='art_*'> container via join_blocks([article_el]). "
                "Editorial revision markers (<p class='modref'> such as '▼M1', '▼B', and repealed-provision "
                "ellipsis markers '▼M1 —————') that reside inside the article container are retained "
                "in-place in source order within the normalized text. Container-level <p class='modref'> "
                "siblings placed outside article divs (at chapter/section level, e.g. immediately preceding "
                "inserted articles art_4, art_4a, art_60a, art_75a) remain outside the individual article "
                "container selector and are cataloged separately below."
            ),
            **marker_summary,
        },
        "edition_article_identifier_comparison": {
            "original_stage1_article_count": len(stage1_records),
            "consolidated_stage4_article_count": len(records_pass1),
            "present_in_consolidated_absent_from_original": present_in_consolidated_absent_in_original,
            "present_in_original_absent_from_consolidated": present_in_original_absent_in_consolidated,
            "legal_effect_or_applicability_assessed": False,
            "note": (
                "This comparison reports structural identifier presence only between the pinned "
                "2024-07-12 OJ snapshot and the pinned 2026-07-27 consolidated snapshot. It does "
                "not interpret legal effect, entry into force, or temporal applicability dates."
            ),
        },
        "content_review_and_ingestion_status": {
            "validation_status": "pending",
            "review_status": "not_reviewed",
            "all_indexable_false": True,
            "legally_reviewed": False,
            "ready_for_indexing": False,
            "note": (
                "Passing Stage 4 technical extraction checks does not mean the corpus is "
                "legally reviewed or ready for indexing. Paragraph child decomposition, "
                "consolidated annexes (including Annex XIV), cross-reference resolution, and "
                "amendment/corrigendum applicability audits remain out of scope for this checkpoint."
            ),
        },
        "unsupported_nonempty_structures": unsupported_structures,
        "extracted_article_inventory": {
            "first_article_id": records_pass1[0]["record_id"],
            "first_article_label": records_pass1[0]["label"],
            "last_article_id": records_pass1[-1]["record_id"],
            "last_article_label": records_pass1[-1]["label"],
            "article_identifiers": extracted_numbers,
        },
    }


def main() -> None:
    schema = json.loads((ROOT / "legal_record.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    artifact = load_consolidated_artifact()

    records_pass1, unsupported_structures, marker_summary = extract_consolidated_articles(
        artifact, validator
    )
    records_pass2, _, _ = extract_consolidated_articles(artifact, validator)

    report = run_stage4_checks(
        records_pass1,
        records_pass2,
        unsupported_structures,
        marker_summary,
        validator,
    )

    records_out = ROOT / "records" / "consolidated_articles_stage4.json"
    records_out.parent.mkdir(parents=True, exist_ok=True)
    records_out.write_text(
        json.dumps(records_pass1, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    report_out = ROOT / "reports" / "consolidated_articles_stage4_validation.json"
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
