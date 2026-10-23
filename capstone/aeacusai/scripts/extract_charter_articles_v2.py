"""Stage 6 v2 offline parser checkpoint: extract all 54 Charter of Fundamental Rights
article parent records with corrected DOM boundary handling for Article 54.

Supersedes Stage 6 (`records/charter_articles_stage6.json`) for future corpus assembly;
the two outputs must not be combined as separate corpus records.

Preserves all existing scripts, baseline files, and Stage 1–6 outputs unchanged.
Performs no paragraph child decomposition, no Charter-to-AI-Act mapping inference,
and no network, embedding, or vector-store operations.
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

from extract_charter_articles import (
    CHARTER_SOURCE_ID,
    EXPECTED_CHARTER_ARTICLES,
    load_charter_artifact,
)
from extract_review_samples import NS, ROOT, digest, join_blocks, parse, text

PARSER_REVISION = "charter-articles-stage6-v2"

# DOM classes that terminate an article sibling span inside div#C_2012326EN.01039301:
# - ti-art: next article heading
# - ti-section-1 / ti-section-2: next Title heading
# - ti-grseq-1: document-level sequence heading / closing asterism separator ('°', '°°')
ARTICLE_BOUNDARY_STOP_CLASSES = frozenset(
    {"ti-art", "ti-section-1", "ti-section-2", "ti-grseq-1"}
)

SUPPORTED_CHARTER_V2_ARTICLE_TAG_CLASSES = {
    ("p", "ti-art"),
    ("p", "sti-art"),
    ("p", "normal"),
    ("table", None),
    ("tbody", None),
    ("tr", None),
    ("td", None),
    ("col", None),
    ("span", None),
}


def charter_article_block_v2(tree, number: int) -> list[etree._Element]:
    """Collect the DOM elements belonging to Charter Article `number`.

    Starts at `<p class='ti-art'>Article {number}</p>` and collects following siblings
    until the next article heading (`ti-art`), Title heading (`ti-section-1`, `ti-section-2`),
    or document-level sequence/closing separator (`ti-grseq-1`).
    """
    headings = tree.xpath("//h:p[@class='ti-art']", namespaces=NS)
    matches = [h for h in headings if text(h) == f"Article {number}"]
    if len(matches) != 1:
        raise ValueError(f"Charter article {number} not uniquely identified")
    heading = matches[0]
    elements = [heading]
    for sibling in heading.itersiblings():
        if not isinstance(sibling.tag, str):
            continue
        if sibling.get("class") in ARTICLE_BOUNDARY_STOP_CLASSES:
            break
        elements.append(sibling)
    return elements


def _extract_closing_document_material(tree) -> list[dict]:
    """Extract the trailing document-level closing elements after Article 54 from the DOM."""
    art54_elements = charter_article_block_v2(tree, 54)
    last_art54_el = art54_elements[-1]
    closing_elements = []
    for sibling in last_art54_el.itersiblings():
        if not isinstance(sibling.tag, str):
            continue
        closing_elements.append(
            {
                "selector": tree.getpath(sibling),
                "id": sibling.get("id"),
                "tag": etree.QName(sibling).localname,
                "class": sibling.get("class"),
                "text": text(sibling),
            }
        )
    return closing_elements


def extract_charter_articles_v2(
    artifact: dict,
    validator: Draft202012Validator,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Extract all 54 Charter articles (1–54) in document order with corrected Article 54 boundary."""
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
        elements = charter_article_block_v2(tree, number_int)
        for el in elements:
            for desc in el.iter():
                if not isinstance(desc.tag, str):
                    continue
                tname = etree.QName(desc).localname
                cls = desc.get("class")
                dtext = text(desc)
                if dtext and (tname, cls) not in SUPPORTED_CHARTER_V2_ARTICLE_TAG_CLASSES:
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

    closing_material = _extract_closing_document_material(tree)
    return records, unsupported_structures, closing_material


def run_stage6_v2_checks(
    records_pass1: list[dict],
    records_pass2: list[dict],
    unsupported_structures: list[dict],
    closing_material: list[dict],
    validator: Draft202012Validator,
    stage6_v1_path: Path = ROOT / "records" / "charter_articles_stage6.json",
    baseline_path: Path = ROOT / "records" / "review_records.json",
) -> dict:
    """Run focused offline verification checks for Stage 6 v2 Charter articles."""
    extracted_numbers = [r["locator"]["article"] for r in records_pass1]
    record_ids = [r["record_id"] for r in records_pass1]
    selectors = [r["source_location"]["selector"] for r in records_pass1]

    # Check 1: Exactly 54 unique article records satisfy the schema
    count_is_54 = len(records_pass1) == 54
    unique_record_ids = len(set(record_ids)) == 54
    unique_selectors = len(set(selectors)) == 54
    exact_1_to_54_order = extracted_numbers == EXPECTED_CHARTER_ARTICLES
    assert count_is_54, f"Expected 54 records, got {len(records_pass1)}"
    assert unique_record_ids, "Duplicate record_id values detected"
    assert unique_selectors, "Duplicate source_location selector values detected"
    assert exact_1_to_54_order, "Extracted Charter articles do not match ordered Articles 1–54"

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

    # Check 2: Articles 1–53 are unchanged from Stage 6
    stage6_v1_records = json.loads(stage6_v1_path.read_text(encoding="utf-8"))
    articles_1_to_53_unchanged = records_pass1[:53] == stage6_v1_records[:53]
    assert articles_1_to_53_unchanged, "Articles 1–53 differ from Stage 6 v1 records"

    # Check 3: Baseline Articles 21, 51, 52, 53 still match baseline exactly
    baseline_records = json.loads(baseline_path.read_text(encoding="utf-8"))
    snap = records_pass1[0]["source_snapshot_id"]
    baseline_by_id = {r["record_id"]: r for r in baseline_records}
    v2_by_id = {r["record_id"]: r for r in records_pass1}
    for num in ["21", "51", "52", "53"]:
        rec_id = f"{snap}::article/{num}"
        assert v2_by_id[rec_id] == baseline_by_id[rec_id], (
            f"Article {num} changed unexpectedly from baseline"
        )

    # Check 4: Verify corrected Article 54 content, length (314), and SHA-256 independently
    art54_v2 = records_pass1[53]
    art54_v1 = stage6_v1_records[53]
    assert art54_v2["record_id"] == art54_v1["record_id"] == f"{snap}::article/54"

    art54_text = art54_v2["text"]
    art54_sha256 = art54_v2["text_sha256"]
    art54_char_count = len(art54_text)

    has_heading = art54_text.startswith("Article 54 Prohibition of abuse of rights ")
    has_operative_body = (
        "Nothing in this Charter shall be interpreted as implying any right to engage in any "
        "activity or to perform any act aimed at the destruction of any of the rights and "
        "freedoms recognised in this Charter or at their limitation to a greater extent than "
        "is provided for herein."
    ) in art54_text
    excludes_closing_separators = "°" not in art54_text
    excludes_proclamation_note = "proclaimed on 7 December 2000" not in art54_text
    expected_sha256 = "ce552ea083a96962e6722f57b5e35d7011d0ff755bae68783cace3e096612a5c"
    matches_expected_314_and_sha256 = (
        art54_char_count == 314 and art54_sha256 == expected_sha256
    )

    assert has_heading, "Article 54 missing heading or subtitle"
    assert has_operative_body, "Article 54 missing complete operative body text"
    assert excludes_closing_separators, "Article 54 still contains closing ° / °° separators"
    assert excludes_proclamation_note, "Article 54 still contains closing proclamation note"
    assert matches_expected_314_and_sha256, (
        f"Expected 314 chars and {expected_sha256}, got {art54_char_count} and {art54_sha256}"
    )

    # Verify excluded closing material is preserved in the report
    assert len(closing_material) == 3, f"Expected 3 closing elements, got {len(closing_material)}"
    assert [c["text"] for c in closing_material[:2]] == ["°", "°°"]
    assert closing_material[2]["text"].startswith(
        "The above text adapts the wording of the Charter proclaimed on 7 December 2000"
    )

    # Check 5: Repeated extraction produces identical records
    reproducible = records_pass1 == records_pass2
    assert reproducible, "Second extraction did not produce identical records"

    return {
        "stage": "charter_articles_stage6_v2",
        "parser_revision": PARSER_REVISION,
        "supersedes_stage": "charter_articles_stage6",
        "supersession_policy": (
            "records/charter_articles_stage6_v2.json supersedes "
            "records/charter_articles_stage6.json for all future corpus assembly. "
            "Both files share identical source-based record_id values for Articles 1–54 "
            "and must never be combined as separate corpus records."
        ),
        "source_id": CHARTER_SOURCE_ID,
        "source_snapshot_id": snap,
        "record_count": len(records_pass1),
        "technical_checks": {
            "manifest_sha256_verified": True,
            "exact_54_unique_articles_satisfy_json_schema": (
                count_is_54 and unique_record_ids and unique_selectors and exact_1_to_54_order
            ),
            "articles_1_to_53_unchanged_from_stage6": articles_1_to_53_unchanged,
            "articles_21_51_52_53_match_review_baseline": True,
            "article_54_has_heading_subtitle_and_complete_operative_text": (
                has_heading and has_operative_body
            ),
            "article_54_excludes_closing_separators_and_proclamation_note": (
                excludes_closing_separators and excludes_proclamation_note
            ),
            "article_54_confirmed_314_chars_and_expected_sha256": matches_expected_314_and_sha256,
            "all_text_sha256_match_extracted_text": all_sha256_match_text,
            "second_extraction_identical": reproducible,
            "unsupported_nonempty_element_count": len(unsupported_structures),
        },
        "article_54_boundary_correction": {
            "record_id": art54_v2["record_id"],
            "dom_boundary_rule": (
                "charter_article_block_v2 stops sibling traversal inside div#C_2012326EN.01039301 "
                "when encountering any element with class in {'ti-art', 'ti-section-1', "
                "'ti-section-2', 'ti-grseq-1'}. Because the closing asterism separator "
                "(<p id='d1e829-393-1' class='ti-grseq-1'>°</p>) immediately follows Article 54's "
                "operative paragraph, traversal stops cleanly at the DOM boundary without "
                "hardcoding text or character counts."
            ),
            "why_article_54_intentionally_differs_from_original_baseline": (
                "In the v0.2 sample extractor (scripts/extract_review_samples.py), "
                "article_block(tree, number) stopped only on {'ti-art', 'ti-section-1', "
                "'ti-section-2'}. Because Article 54 is the final article in TITLE VII, "
                "no further article or title heading follows it inside div#C_2012326EN.01039301, "
                "causing the baseline extractor to sweep in three trailing document-level "
                "closing elements ('°', '°°', and the Treaty of Lisbon proclamation adaptation "
                "sentence). Treating that over-inclusion as a baseline boundary defect, "
                "Stage 6 v2 stops at p.ti-grseq-1 so Article 54 contains only its heading, "
                "subtitle, and operative text."
            ),
            "corrected_selector": art54_v2["source_location"]["selector"],
            "corrected_char_length": art54_char_count,
            "corrected_text_sha256": art54_sha256,
            "corrected_text": art54_text,
            "previous_baseline_and_stage6_v1_selector": art54_v1["source_location"]["selector"],
            "previous_baseline_and_stage6_v1_char_length": len(art54_v1["text"]),
            "previous_baseline_and_stage6_v1_text_sha256": art54_v1["text_sha256"],
        },
        "excluded_document_level_closing_material": {
            "container_id": "C_2012326EN.01039301",
            "element_count": len(closing_material),
            "combined_normalized_text": " ".join(c["text"] for c in closing_material if c["text"]),
            "combined_text_sha256": digest(
                " ".join(c["text"] for c in closing_material if c["text"])
            ),
            "elements": closing_material,
        },
        "content_review_and_ingestion_status": {
            "validation_status": "pending",
            "review_status": "not_reviewed",
            "all_indexable_false": True,
            "legally_reviewed": False,
            "ready_for_indexing": False,
        },
        "unsupported_nonempty_structures": unsupported_structures,
    }


def main() -> None:
    schema = json.loads((ROOT / "legal_record.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    artifact = load_charter_artifact()

    records_pass1, unsupported_structures, closing_material = extract_charter_articles_v2(
        artifact, validator
    )
    records_pass2, _, _ = extract_charter_articles_v2(artifact, validator)

    report = run_stage6_v2_checks(
        records_pass1,
        records_pass2,
        unsupported_structures,
        closing_material,
        validator,
    )

    records_out = ROOT / "records" / "charter_articles_stage6_v2.json"
    records_out.parent.mkdir(parents=True, exist_ok=True)
    records_out.write_text(
        json.dumps(records_pass1, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    report_out = ROOT / "reports" / "charter_articles_stage6_v2_validation.json"
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "stage": report["stage"],
                "parser_revision": report["parser_revision"],
                "records_written": len(records_pass1),
                "technical_checks_passed": all(
                    v is True
                    for k, v in report["technical_checks"].items()
                    if isinstance(v, bool)
                ),
                "article_54_char_length": report["article_54_boundary_correction"][
                    "corrected_char_length"
                ],
                "article_54_text_sha256": report["article_54_boundary_correction"][
                    "corrected_text_sha256"
                ],
                "indexable": False,
            }
        )
    )


if __name__ == "__main__":
    main()
