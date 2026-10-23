"""Stage 9 bounded chunking checkpoint for the pinned consolidated edition only
(T1-AIA-CONS-20260727):
- Article 6: paragraphs 1, 1a, 1b, 1c, 2–8 (11 child records)
- Annex III: areas 1–8 (8 child records)

Extracts directly from the manifest-verified consolidated XHTML source.
Uses the 45-record review baseline strictly for regression comparison, not as the
extraction data source.
Preserves all existing canonical records, scripts, and manifests unchanged.
Keeps ingestion closed and makes no network, embedding, or vector-store calls.
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
from extract_review_samples import (
    ROOT,
    area_groups,
    digest,
    join_blocks,
    numbered_label,
    parse,
    text,
    unique_id,
)

EXPECTED_ARTICLE_6_PARAGRAPHS = [
    "1",
    "1a",
    "1b",
    "1c",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
]
EXPECTED_ANNEX_III_POINTS = [str(i) for i in range(1, 9)]


def clean_paragraph_groups(article_el) -> tuple[list[dict], list[dict]]:
    """Group immediate siblings from one top-level numbered paragraph to the next
    while excluding standalone editorial revision-marker siblings (`p.modref`).

    Returns:
      - groups: ordered list of {"number": str, "elements": list[Element]}
      - omitted_elements: non-paragraph sibling elements inside `article_el` (heading,
        subtitle, and `p.modref` editorial markers) retained in the parent record.
    """
    groups: list[dict] = []
    omitted_elements: list[dict] = []
    current: dict | None = None
    tree = article_el.getroottree()

    for child in article_el:
        if not isinstance(child.tag, str):
            continue
        name = etree.QName(child).localname
        cls = child.get("class")
        child_text = text(child)

        if cls == "modref":
            omitted_elements.append(
                {
                    "category": "editorial_revision_marker",
                    "selector": tree.getpath(child),
                    "tag": name,
                    "class": cls,
                    "text": child_text,
                }
            )
            continue

        if name not in {"p", "div"}:
            omitted_elements.append(
                {
                    "category": "non_paragraph_element",
                    "selector": tree.getpath(child),
                    "tag": name,
                    "class": cls,
                    "text": child_text,
                }
            )
            continue

        number = numbered_label(child)
        if number:
            current = {"number": number, "elements": [child]}
            groups.append(current)
        elif current is not None:
            current["elements"].append(child)
        else:
            omitted_elements.append(
                {
                    "category": "article_heading_or_title_retained_in_parent",
                    "selector": tree.getpath(child),
                    "tag": name,
                    "class": cls,
                    "text": child_text,
                }
            )

    return groups, omitted_elements


def _inspect_annex_iii_non_area_children(annex_el, area_element_set: set) -> list[dict]:
    """Catalog direct children of Annex III that are outside the 8 numbered area divs."""
    tree = annex_el.getroottree()
    omitted: list[dict] = []
    for child in annex_el:
        if not isinstance(child.tag, str) or child in area_element_set:
            continue
        name = etree.QName(child).localname
        cls = child.get("class")
        child_text = text(child)
        category = (
            "empty_layout_spacer"
            if not child_text
            else "annex_heading_or_intro_retained_in_parent"
        )
        omitted.append(
            {
                "category": category,
                "selector": tree.getpath(child),
                "tag": name,
                "class": cls,
                "text": child_text,
            }
        )
    return omitted


def extract_stage9_classification_children(
    artifact: dict,
    validator: Draft202012Validator,
) -> tuple[list[dict], dict]:
    """Extract the 11 Article 6 paragraph records and 8 Annex III area records
    from the manifest-verified consolidated XHTML source.
    """
    raw_path = ROOT / artifact["relative_path"]
    tree = parse(raw_path)
    snap = artifact["source_snapshot_id"]
    url = artifact["resolved_content_url"]

    art6_parent_id = f"{snap}::article/6"
    anx3_parent_id = f"{snap}::annex/III"

    records: list[dict] = []

    # 1. Extract Article 6 paragraphs (1, 1a, 1b, 1c, 2..8)
    article_6 = unique_id(tree, "art_6")
    para_groups, art6_omitted = clean_paragraph_groups(article_6)

    for group in para_groups:
        number = group["number"]
        elements = group["elements"]
        path = f"article/6/paragraph/{number}"
        normalized_text = join_blocks(elements)
        record = {
            "schema_version": "0.1.0",
            "record_id": f"{snap}::{path}",
            "source_snapshot_id": snap,
            "parent_id": art6_parent_id,
            "unit_kind": "paragraph",
            "legal_function": "operative",
            "label": f"Article 6({number})",
            "locator": {
                "path": path,
                "article": "6",
                "paragraph": number,
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

    # 2. Extract Annex III areas 1..8
    annex_iii = unique_id(tree, "anx_III")
    areas = area_groups(annex_iii)
    anx3_omitted = _inspect_annex_iii_non_area_children(
        annex_iii, set(areas.values())
    )

    for number, element in areas.items():
        path = f"annex/III/point/{number}"
        normalized_text = join_blocks([element])
        record = {
            "schema_version": "0.1.0",
            "record_id": f"{snap}::{path}",
            "source_snapshot_id": snap,
            "parent_id": anx3_parent_id,
            "unit_kind": "point",
            "legal_function": "operative",
            "label": f"Annex III, point {number}",
            "locator": {
                "path": path,
                "annex": "III",
                "point": number,
            },
            "language": "en",
            "tier": 1,
            "text": normalized_text,
            "text_sha256": digest(normalized_text),
            "source_location": {
                "url": url,
                "format": "html",
                "selector": tree.getpath(element),
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

    omitted_summary = {
        "article_6_non_child_elements": art6_omitted,
        "annex_iii_non_child_elements": anx3_omitted,
    }
    return records, omitted_summary


def run_stage9_checks(
    records_pass1: list[dict],
    records_pass2: list[dict],
    omitted_summary: dict,
    validator: Draft202012Validator,
    stage4_path: Path = ROOT / "records" / "consolidated_articles_stage4.json",
    stage5_path: Path = ROOT / "records" / "consolidated_annexes_stage5.json",
    baseline_path: Path = ROOT / "records" / "review_records.json",
) -> dict:
    """Verify all Stage 9 requirements and compare against the 45-record baseline."""
    snap = records_pass1[0]["source_snapshot_id"]
    art6_parent_id = f"{snap}::article/6"
    anx3_parent_id = f"{snap}::annex/III"

    # Check 1: Count, source order, schema validity, and digest integrity
    art6_children = [r for r in records_pass1 if r["unit_kind"] == "paragraph"]
    anx3_children = [r for r in records_pass1 if r["unit_kind"] == "point"]
    assert len(records_pass1) == 19, f"Expected 19 child records, got {len(records_pass1)}"
    assert len(art6_children) == 11, f"Expected 11 Article 6 paragraphs, got {len(art6_children)}"
    assert len(anx3_children) == 8, f"Expected 8 Annex III areas, got {len(anx3_children)}"

    extracted_para_nums = [r["locator"]["paragraph"] for r in art6_children]
    extracted_area_nums = [r["locator"]["point"] for r in anx3_children]
    assert extracted_para_nums == EXPECTED_ARTICLE_6_PARAGRAPHS, (
        f"Unexpected Article 6 paragraph sequence: {extracted_para_nums}"
    )
    assert extracted_area_nums == EXPECTED_ANNEX_III_POINTS, (
        f"Unexpected Annex III area sequence: {extracted_area_nums}"
    )

    record_ids = [r["record_id"] for r in records_pass1]
    selectors = [r["source_location"]["selector"] for r in records_pass1]
    assert len(set(record_ids)) == 19, "Duplicate record_id values detected"
    assert len(set(selectors)) == 19, "Duplicate selector values detected"

    for r in records_pass1:
        validator.validate(r)
        assert r["source_snapshot_id"] == snap
        assert r["text_sha256"] == digest(r["text"])
        assert r["children"] == []
        assert r["cross_references"] == []
        assert r["validation_status"] == "pending"
        assert r["review_status"] == "not_reviewed"
        assert r["indexable"] is False

    # Check 2: Parent resolution against existing Stage 4 Article 6 and Stage 5 Annex III parents
    stage4_records = {
        r["record_id"]: r
        for r in json.loads(stage4_path.read_text(encoding="utf-8"))
    }
    stage5_records = {
        r["record_id"]: r
        for r in json.loads(stage5_path.read_text(encoding="utf-8"))
    }
    assert art6_parent_id in stage4_records, f"Missing Stage 4 parent: {art6_parent_id}"
    assert anx3_parent_id in stage5_records, f"Missing Stage 5 parent: {anx3_parent_id}"

    stage4_art6_parent = stage4_records[art6_parent_id]
    stage5_anx3_parent = stage5_records[anx3_parent_id]

    for r in art6_children:
        assert r["parent_id"] == stage4_art6_parent["record_id"]
        assert r["text"] in stage4_art6_parent["text"], (
            f"Paragraph {r['record_id']} text is not a substring of Stage 4 Article 6 parent"
        )
    for r in anx3_children:
        assert r["parent_id"] == stage5_anx3_parent["record_id"]
        assert r["text"] in stage5_anx3_parent["text"], (
            f"Point {r['record_id']} text is not a substring of Stage 5 Annex III parent"
        )

    # Check 3: Structural unit completeness checks (Article 6(1), Article 6(3), Annex III area 4, and other areas)
    by_id = {r["record_id"]: r for r in records_pass1}
    art6_p1 = by_id[f"{snap}::article/6/paragraph/1"]
    for marker in [
        "1. Irrespective of whether an AI system is placed on the market",
        "(a) the AI system is intended to be used as a safety component",
        "(b) the product whose safety component pursuant to point (a)",
    ]:
        assert marker in art6_p1["text"], f"Incomplete Article 6(1): missing {marker!r}"

    art6_p3 = by_id[f"{snap}::article/6/paragraph/3"]
    for marker in [
        "3. By derogation from paragraph 2",
        "The first subparagraph shall apply where any of the following conditions is fulfilled:",
        "(a) the AI system is intended to perform a narrow procedural task;",
        "(b) the AI system is intended to improve the result of a previously completed human activity;",
        "(c) the AI system is intended to detect decision-making patterns",
        "(d) the AI system is intended to perform a preparatory task",
        "Notwithstanding the first subparagraph, an AI system referred to in Annex III shall always be considered to be high-risk where the AI system performs profiling of natural persons.",
    ]:
        assert marker in art6_p3["text"], f"Incomplete Article 6(3): missing {marker!r}"

    anx3_pt4 = by_id[f"{snap}::annex/III/point/4"]
    for marker in [
        "4. Employment, workers’ management and access to self-employment:",
        "(a) AI systems intended to be used for the recruitment or selection of natural persons",
        "(b) AI systems intended to be used to make decisions affecting terms of work-related relationships",
    ]:
        assert marker in anx3_pt4["text"], f"Incomplete Annex III area 4: missing {marker!r}"

    # Verify qualifications and exceptions across other Annex III areas
    other_area_qualifications = [
        ("1", "This shall not include AI systems intended to be used for biometric verification"),
        ("5", "with the exception of AI systems used for the purpose of detecting financial fraud"),
        ("6", "in so far as their use is permitted under relevant Union or national law"),
        ("7", "with the exception of the verification of travel documents"),
        ("8", "This does not include AI systems to the output of which natural persons are not directly exposed"),
    ]
    for pt_num, qual_snippet in other_area_qualifications:
        pt_rec = by_id[f"{snap}::annex/III/point/{pt_num}"]
        assert qual_snippet in pt_rec["text"], (
            f"Annex III area {pt_num} missing qualification: {qual_snippet!r}"
        )

    # Check 4: Compare all 19 child records with corresponding consolidated records in review_records.json
    baseline_records = {
        r["record_id"]: r
        for r in json.loads(baseline_path.read_text(encoding="utf-8"))
    }
    baseline_comparisons: list[dict] = []
    discrepancies: list[dict] = []

    for r in records_pass1:
        rid = r["record_id"]
        if rid not in baseline_records:
            raise ValueError(f"Expected consolidated baseline record not found: {rid}")
        base = baseline_records[rid]
        text_eq = r["text"] == base["text"]
        sha_eq = r["text_sha256"] == base["text_sha256"]
        sel_eq = r["source_location"]["selector"] == base["source_location"]["selector"]

        comp_entry = {
            "record_id": rid,
            "label": r["label"],
            "stage9_char_length": len(r["text"]),
            "baseline_char_length": len(base["text"]),
            "stage9_text_sha256": r["text_sha256"],
            "baseline_text_sha256": base["text_sha256"],
            "stage9_selector": r["source_location"]["selector"],
            "baseline_selector": base["source_location"]["selector"],
            "exact_text_and_sha256_match": text_eq and sha_eq,
        }
        baseline_comparisons.append(comp_entry)

        if not (text_eq and sha_eq):
            discrepancies.append(
                {
                    **comp_entry,
                    "difference_explanation": (
                        "In the v0.2 sample extractor (scripts/extract_review_samples.py), "
                        "paragraph_groups(article) appended every non-numbered <p> or <div> sibling "
                        "to the preceding paragraph group, including standalone <p class='modref'> "
                        "editorial revision markers ('▼M1' after paragraph 1 and '▼B' after "
                        "paragraph 1c). Stage 9's clean_paragraph_groups excludes standalone "
                        "p.modref siblings from child paragraph text (matching Stage 8's verified "
                        "paragraph wording) while the complete Stage 4 Article 6 parent record "
                        "retains those markers in source position."
                    ),
                }
            )

    # Confirm that the only baseline differences are the 2 trailing modref markers on 6(1) and 6(1c)
    exact_match_count = sum(
        1 for c in baseline_comparisons if c["exact_text_and_sha256_match"]
    )
    assert exact_match_count == 17 and len(discrepancies) == 2
    assert [d["label"] for d in discrepancies] == ["Article 6(1)", "Article 6(1c)"]
    assert baseline_records[f"{snap}::article/6/paragraph/1"]["text"] == (
        by_id[f"{snap}::article/6/paragraph/1"]["text"] + " ▼M1"
    )
    assert baseline_records[f"{snap}::article/6/paragraph/1c"]["text"] == (
        by_id[f"{snap}::article/6/paragraph/1c"]["text"] + " ▼B"
    )

    # Check 5: Deterministic repeat extraction
    reproducible = records_pass1 == records_pass2
    assert reproducible, "Second extraction did not produce identical records"

    return {
        "stage": "classification_children_stage9",
        "source_id": CONSOLIDATED_SOURCE_ID,
        "source_snapshot_id": snap,
        "record_count": len(records_pass1),
        "article_6_paragraph_count": len(art6_children),
        "annex_iii_area_count": len(anx3_children),
        "technical_checks": {
            "manifest_sha256_verified": True,
            "extracted_from_consolidated_xhtml_not_baseline": True,
            "exact_19_schema_valid_child_records": len(records_pass1) == 19,
            "all_parent_ids_resolve_to_stage4_art6_or_stage5_annex_iii": True,
            "article_6_1_retains_intro_and_both_conditions_a_b": True,
            "article_6_3_retains_intro_conditions_a_to_d_and_profiling_rule": True,
            "annex_iii_area_4_retains_heading_and_both_subpoints_a_b": True,
            "other_annex_iii_areas_retain_qualifications_and_exceptions": True,
            "no_arbitrary_token_or_character_splitting": True,
            "all_text_sha256_digests_verified": True,
            "unique_record_ids_and_selectors_in_source_order": True,
            "second_extraction_identical": reproducible,
            "all_records_pending_not_reviewed_and_indexable_false": True,
        },
        "parent_context_retrieval_policy": {
            "policy_type": "retrieval_policy_requirement (not an inferred statutory cross-reference mapping)",
            "same_snapshot_parent_expansion": (
                "Retrieving any Article 6(1)–(8) paragraph child or Annex III area 1–8 point "
                "child must make its complete same-snapshot parent record available "
                f"({art6_parent_id} or {anx3_parent_id}) so introductory wording, sibling "
                "paragraphs, and surrounding qualifications are never omitted."
            ),
            "annex_iii_to_article_6_co_retrieval_context": (
                "When an Annex III area 1–8 child record is retrieved, the retrieval layer "
                "must also provide same-snapshot Article 6 classification context "
                f"({art6_parent_id}, specifically including Article 6(2) and the Article 6(3) "
                "derogation conditions and profiling rule) before any high-risk classification "
                "assessment is drafted."
            ),
            "child_text_purity": (
                "Child record text remains strictly source-faithful to its own DOM element(s); "
                "no parent text, generated summaries, or legal interpretations are prepended."
            ),
        },
        "baseline_comparison_summary": {
            "total_compared": len(baseline_comparisons),
            "exact_matches_with_v0_2_baseline": exact_match_count,
            "intentional_modref_boundary_differences": len(discrepancies),
            "discrepancies_explained": discrepancies,
            "all_19_comparisons": baseline_comparisons,
        },
        "omitted_editorial_and_layout_elements": omitted_summary,
        "content_review_and_ingestion_status": {
            "validation_status": "pending",
            "review_status": "not_reviewed",
            "all_indexable_false": True,
            "ingestion_permitted": False,
            "stage7_manifest_modified": False,
        },
    }


def build_stage9_markdown(records: list[dict], report: dict) -> str:
    snap = report["source_snapshot_id"]
    by_id = {r["record_id"]: r for r in records}
    art6_p3 = by_id[f"{snap}::article/6/paragraph/3"]
    anx3_pt4 = by_id[f"{snap}::annex/III/point/4"]

    lines = [
        "# AeacusAI — Stage 9 Classification Children Review Report (Consolidated Article 6 & Annex III)",
        "",
        "- **Stage**: `classification_children_stage9`",
        f"- **Source Snapshot ID**: `{snap}` (`data/raw/ai-act-consolidated-20260727-en.xhtml`)",
        "- **Total child records extracted**: `19` (`11` Article 6 paragraphs + `8` Annex III areas)",
        "- **All records status**: `validation_status=\"pending\"`, `review_status=\"not_reviewed\"`, `indexable=false`",
        "- **Ingestion permitted**: `false`",
        "",
        "---",
        "",
        "## 1. Inventory of All 19 Extracted Child Records",
        "",
        "| # | Record ID | Label | Unit Kind | Chars | Parent ID | Selector |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]

    for idx, r in enumerate(records, start=1):
        lines.append(
            f"| {idx} | `{r['record_id']}` | {r['label']} | `{r['unit_kind']}` | "
            f"`{len(r['text'])}` | `{r['parent_id']}` | `{r['source_location']['selector']}` |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## 2. Complete Untruncated Excerpts (`Article 6(3)` and `Annex III, point 4`)",
            "",
            "### Consolidated Article 6(3)",
            "",
            f"- **Record ID**: `{art6_p3['record_id']}`",
            f"- **Parent ID**: `{art6_p3['parent_id']}`",
            f"- **DOM Selector**: `{art6_p3['source_location']['selector']}`",
            f"- **Character Count**: `{len(art6_p3['text'])}`",
            f"- **Text SHA-256**: `{art6_p3['text_sha256']}`",
            "",
            art6_p3["text"],
            "",
            "### Consolidated Annex III, point 4",
            "",
            f"- **Record ID**: `{anx3_pt4['record_id']}`",
            f"- **Parent ID**: `{anx3_pt4['parent_id']}`",
            f"- **DOM Selector**: `{anx3_pt4['source_location']['selector']}`",
            f"- **Character Count**: `{len(anx3_pt4['text'])}`",
            f"- **Text SHA-256**: `{anx3_pt4['text_sha256']}`",
            "",
            anx3_pt4["text"],
            "",
            "---",
            "",
            "## 3. Baseline Regression Comparison (19 Consolidated Child Records)",
            "",
            "- **17 of 19 records** (`Article 6(1a)`, `6(1b)`, `6(2)`–`6(8)`, and all `8` `Annex III` points `1`–`8`) match the v0.2 `records/review_records.json` baseline `text`, `text_sha256`, and `selector` identically.",
            "- **2 records (`Article 6(1)` and `Article 6(1c)`) intentionally exclude trailing standalone `<p class=\"modref\">` editorial markers**:",
            "  - In `scripts/extract_review_samples.py`, `paragraph_groups(article)` appended every unnumbered `<p>` or `<div>` sibling to the preceding paragraph group, which swept the standalone `<p class=\"modref\">▼M1</p>` sibling (`/*/*[2]/*[9]/*[4]/*[4]/*[3]/*[3]/*[4]`) onto the end of `Article 6(1)` (`767` chars vs. `763` chars) and swept `<p class=\"modref\">▼B</p>` (`/*/*[2]/*[9]/*[4]/*[4]/*[3]/*[3]/*[8]`) onto the end of `Article 6(1c)` (`355` chars vs. `352` chars).",
            "  - In `scripts/extract_classification_children.py`, `clean_paragraph_groups` excludes standalone `<p class=\"modref\">` siblings so each paragraph child contains only its statutory wording (matching the amending text verified in Stage 8), while the Stage 4 `article/6` parent record retains those editorial markers in source position.",
            "",
            "---",
            "",
            "## 4. Parent-Context Retrieval Policy Requirements",
            "",
            "These requirements are documented as **application retrieval policy**, not inferred statutory cross-references (`cross_references` remains `[]` on every record):",
            "",
            "1. **Mandatory Same-Snapshot Parent Expansion**:",
            f"   - Whenever any `Article 6` paragraph child (`article/6/paragraph/1`..`8`) or `Annex III` point child (`annex/III/point/1`..`8`) is retrieved, the retrieval pipeline must make its complete same-snapshot parent record available (`{snap}::article/6` or `{snap}::annex/III`).",
            "2. **Mandatory Article 6 Context for Annex III Areas**:",
            f"   - Retrieving any `Annex III` area (`annex/III/point/1`..`8`) is legally incomplete in isolation because Annex III areas are invoked via `Article 6(2)` and qualified by the `Article 6(3)` derogation conditions and profiling rule (as well as `Article 6(4)` documentation/registration duties). Retrieval of an Annex III area must therefore also surface same-snapshot `Article 6` context (`{snap}::article/6`).",
            "3. **No Text Prepending in Child Records**:",
            "   - Child records store only the normalized text of their own DOM element(s); parent headings, introductory sentences, or summaries are never prepended into child `text`.",
            "",
            "---",
            "",
            "## 5. Omitted Editorial/Layout Elements & Remaining Limitations",
            "",
            "1. **Elements outside child spans inside `art_6` (`4` direct child elements retained in the Stage 4 `article/6` parent)**:",
            "   - `/*/*[2]/*[9]/*[4]/*[4]/*[3]/*[3]/*[1]` (`<p class=\"title-article-norm\">`): `'Article 6'`",
            "   - `/*/*[2]/*[9]/*[4]/*[4]/*[3]/*[3]/*[2]` (`<div class=\"eli-title\">`): `'Classification rules for high-risk AI systems'`",
            "   - `/*/*[2]/*[9]/*[4]/*[4]/*[3]/*[3]/*[4]` (`<p class=\"modref\">`): `'▼M1'` (preceding inserted paragraph `1a`)",
            "   - `/*/*[2]/*[9]/*[4]/*[4]/*[3]/*[3]/*[8]` (`<p class=\"modref\">`): `'▼B'` (following inserted paragraph `1c`)",
            "2. **Elements outside child spans inside `anx_III` (`6` direct child elements)**:",
            "   - `3` empty layout elements skipped in both Stage 5 and Stage 9: `*[1]` (`<p><br/></p>`), `*[2]` (`<hr class=\"separator-annex\"/>`), `*[3]` (`<p><br/></p>`).",
            "   - `3` heading/introductory elements retained in the Stage 5 `annex/III` parent: `*[4]` (`<p class=\"title-annex-1\">ANNEX III</p>`), `*[5]` (`<p class=\"title-annex-2\">High-risk AI systems referred to in Article 6(2)</p>`), and `*[6]` (`<p class=\"norm\">High-risk AI systems pursuant to Article 6(2) are the AI systems listed in any of the following areas:</p>`).",
            "3. **Remaining limitations**:",
            "   - Sub-items `(a)`–`(d)` inside `Article 6(3)` and lettered subpoints `(a)`–`(e)` inside `Annex III` areas `1`–`8` are kept together inside their enclosing paragraph/area records rather than split into isolated leaf records.",
            "   - Paragraph/point child decomposition for the remaining consolidated articles/annexes, cross-reference resolution, corrigendum verification, and human legal review remain pending. All 19 child records remain `indexable=false`.",
        ]
    )

    return "\n".join(lines) + "\n"


def main() -> None:
    schema = json.loads((ROOT / "legal_record.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    artifact = load_consolidated_artifact()

    records_pass1, omitted_summary = extract_stage9_classification_children(
        artifact, validator
    )
    records_pass2, _ = extract_stage9_classification_children(artifact, validator)

    report = run_stage9_checks(
        records_pass1,
        records_pass2,
        omitted_summary,
        validator,
    )
    md_text = build_stage9_markdown(records_pass1, report)

    records_out = ROOT / "records" / "classification_children_stage9.json"
    records_out.parent.mkdir(parents=True, exist_ok=True)
    records_out.write_text(
        json.dumps(records_pass1, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    val_out = ROOT / "reports" / "classification_children_stage9_validation.json"
    val_out.parent.mkdir(parents=True, exist_ok=True)
    val_out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    md_out = ROOT / "reports" / "classification_children_stage9_review.md"
    md_out.write_text(md_text, encoding="utf-8")

    print(
        json.dumps(
            {
                "stage": report["stage"],
                "records_written": report["record_count"],
                "article_6_paragraphs": report["article_6_paragraph_count"],
                "annex_iii_areas": report["annex_iii_area_count"],
                "technical_checks_passed": all(
                    v is True for v in report["technical_checks"].values()
                ),
                "baseline_exact_matches": report["baseline_comparison_summary"][
                    "exact_matches_with_v0_2_baseline"
                ],
                "intentional_modref_differences": report["baseline_comparison_summary"][
                    "intentional_modref_boundary_differences"
                ],
                "indexable": False,
            }
        )
    )


if __name__ == "__main__":
    main()
