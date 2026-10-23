"""Stage 8 bounded provenance check: compare AI Act Articles 6 and 113 across the
original 2024 OJ edition (T1-AIA-OJ-2024), Amending Regulation (EU) 2026/1744
(T1-AIA-AMEND-2026-1744, Article 1 points (8) and (40)), and the pinned consolidated
edition dated 2026-07-27 (T1-AIA-CONS-20260727).

Performs all comparisons on temporary derived text only.
Preserves all existing files, canonical records, and raw sources unchanged.
Keeps ingestion closed and makes no network, embedding, or vector-store calls.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from lxml import etree

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from extract_review_samples import ROOT, digest, join_blocks, parse, text

REQUIRED_SOURCE_IDS = [
    "T1-AIA-OJ-2024",
    "T1-AIA-AMEND-2026-1744",
    "T1-AIA-CONS-20260727",
]


def verify_and_load_sources(
    manifest_path: Path = ROOT / "acquisition_manifest.json",
) -> tuple[dict[str, dict], dict[str, etree._ElementTree]]:
    """Verify the three XHTML sources against acquisition_manifest.json before parsing."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_id = {a["source_id"]: a for a in manifest["artifacts"]}

    artifacts: dict[str, dict] = {}
    trees: dict[str, etree._ElementTree] = {}
    for sid in REQUIRED_SOURCE_IDS:
        if sid not in by_id:
            raise ValueError(f"Missing required artifact in manifest: {sid}")
        art = by_id[sid]
        raw_path = ROOT / art["relative_path"]
        actual_sha256 = hashlib.sha256(raw_path.read_bytes()).hexdigest()
        if actual_sha256 != art["sha256"]:
            raise ValueError(
                f"SHA-256 mismatch for {sid}: expected {art['sha256']}, got {actual_sha256}"
            )
        artifacts[sid] = art
        trees[sid] = parse(raw_path)

    return artifacts, trees


def strip_outer_amendment_quotes(raw_quoted_text: str) -> str:
    """Remove only a single leading opening quote (‘) and/or single trailing closing quote (’)
    that the Official Journal amending act places around quoted amendment blocks.

    Does not strip internal quotes, punctuation, or symbols within legal text.
    """
    derived = raw_quoted_text
    if derived.startswith("‘"):
        derived = derived[1:]
    if derived.endswith("’"):
        derived = derived[:-1]
    return derived


def check_article_6_provenance(
    artifacts: dict[str, dict],
    trees: dict[str, etree._ElementTree],
) -> dict:
    """Compare Article 6 across OJ 2024, Amending Act Art 1 point (8), and Consolidated 2026-07-27."""
    t_oj = trees["T1-AIA-OJ-2024"]
    t_amend = trees["T1-AIA-AMEND-2026-1744"]
    t_cons = trees["T1-AIA-CONS-20260727"]

    oj_art6 = t_oj.xpath("//*[@id='art_6']")[0]
    cons_art6 = t_cons.xpath("//*[@id='art_6']")[0]

    # Locate Article 1, point (8) in Amending Regulation 2026/1744
    amend_art1 = t_amend.xpath("//*[@id='art_1']")[0]
    point8_tables = [
        el
        for el in amend_art1
        if isinstance(el.tag, str) and text(el).startswith("(8) ")
    ]
    if len(point8_tables) != 1:
        raise ValueError(f"Expected exactly one Article 1 point (8) container, got {len(point8_tables)}")
    point8_el = point8_tables[0]

    # Inside point (8)'s second cell:
    # child[0] is the operation label <p class="oj-normal">in Article 6, the following paragraphs are inserted:</p>
    # child[1..3] are the three inserted paragraph divs for 1a, 1b, 1c
    point8_body_td = point8_el.xpath("./*[local-name()='tbody']/*[local-name()='tr']/*[local-name()='td'][2]")[0]
    op_label_el = point8_body_td[0]
    amend_inserted_els = list(point8_body_td[1:4])

    # In consolidated art_6:
    # child[3] is <p class="modref">▼M1</p>
    # child[4], child[5], child[6] are 1a, 1b, 1c (<div class="norm">)
    # child[7] is <p class="modref">▼B</p>
    cons_children = [c for c in cons_art6 if isinstance(c.tag, str)]
    cons_inserted_els = [
        c for c in cons_children if text(c).startswith(("1a. ", "1b. ", "1c. "))
    ]
    cons_modref_els = [c for c in cons_children if c.get("class") == "modref"]

    if len(amend_inserted_els) != 3 or len(cons_inserted_els) != 3:
        raise ValueError("Expected 3 inserted paragraphs (1a, 1b, 1c) in both amendment and consolidated")

    paragraph_comparisons = []
    for num, am_el, co_el in zip(["1a", "1b", "1c"], amend_inserted_els, cons_inserted_els):
        raw_amend_text = text(am_el)
        derived_amend_text = strip_outer_amendment_quotes(raw_amend_text)
        cons_para_text = text(co_el)
        paragraph_comparisons.append(
            {
                "paragraph": num,
                "amendment_selector": t_amend.getpath(am_el),
                "consolidated_selector": t_cons.getpath(co_el),
                "quoted_amendment_text_raw": raw_amend_text,
                "derived_amendment_text_outer_quote_stripped": derived_amend_text,
                "consolidated_paragraph_text": cons_para_text,
                "exact_match": derived_amend_text == cons_para_text,
            }
        )

    combined_amend_raw = join_blocks(amend_inserted_els)
    combined_amend_derived = strip_outer_amendment_quotes(combined_amend_raw)
    combined_cons_inserted = join_blocks(cons_inserted_els)

    # Residual comparison: remove the 3 inserted paragraph blocks (1a, 1b, 1c) and the
    # 2 identified <p class="modref"> editorial markers ('▼M1', '▼B') from consolidated art_6
    excluded_cons_set = set(cons_inserted_els) | set(cons_modref_els)
    cons_residual_els = [c for c in cons_children if c not in excluded_cons_set]
    cons_residual_text = join_blocks(cons_residual_els)
    oj_full_text = join_blocks([oj_art6])

    return {
        "article": "6",
        "amending_provision": "Article 1, point (8)",
        "amending_container_selector": t_amend.getpath(point8_el),
        "operation_label_selector": t_amend.getpath(op_label_el),
        "operation_label": text(op_label_el),
        "quoted_amendment_text": combined_amend_raw,
        "derived_amendment_text": combined_amend_derived,
        "consolidated_inserted_text": combined_cons_inserted,
        "inserted_paragraphs_all_match": (
            all(p["exact_match"] for p in paragraph_comparisons)
            and combined_amend_derived == combined_cons_inserted
        ),
        "paragraph_comparisons": paragraph_comparisons,
        "identified_editorial_markers_removed_for_comparison": [
            {
                "selector": t_cons.getpath(m),
                "tag": etree.QName(m).localname,
                "class": m.get("class"),
                "text": text(m),
            }
            for m in cons_modref_els
        ],
        "residual_wording_comparison": {
            "original_oj_selector": t_oj.getpath(oj_art6),
            "original_oj_char_length": len(oj_full_text),
            "original_oj_sha256": digest(oj_full_text),
            "consolidated_residual_char_length": len(cons_residual_text),
            "consolidated_residual_sha256": digest(cons_residual_text),
            "residual_matches_original_article_6_wording": cons_residual_text == oj_full_text,
        },
        "discrepancies": [],
    }


def check_article_113_provenance(
    artifacts: dict[str, dict],
    trees: dict[str, etree._ElementTree],
) -> dict:
    """Compare Article 113 across OJ 2024, Amending Act Art 1 point (40), and Consolidated 2026-07-27."""
    t_oj = trees["T1-AIA-OJ-2024"]
    t_amend = trees["T1-AIA-AMEND-2026-1744"]
    t_cons = trees["T1-AIA-CONS-20260727"]

    oj_art113 = t_oj.xpath("//*[@id='art_113']")[0]
    cons_art113 = t_cons.xpath("//*[@id='art_113']")[0]

    # Locate Article 1, point (40) in Amending Regulation 2026/1744
    amend_art1 = t_amend.xpath("//*[@id='art_1']")[0]
    point40_tables = [
        el
        for el in amend_art1
        if isinstance(el.tag, str) and text(el).startswith("(40) ")
    ]
    if len(point40_tables) != 1:
        raise ValueError(
            f"Expected exactly one Article 1 point (40) container, got {len(point40_tables)}"
        )
    point40_el = point40_tables[0]
    point40_body_td = point40_el.xpath(
        "./*[local-name()='tbody']/*[local-name()='tr']/*[local-name()='td'][2]"
    )[0]
    intro_label_el = point40_body_td[0]
    subpoint_tables = list(point40_body_td[1:4])  # (a), (b), (c)

    oj_children = [c for c in oj_art113 if isinstance(c.tag, str)]
    cons_children = [c for c in cons_art113 if isinstance(c.tag, str)]
    cons_modref_els = [c for c in cons_children if c.get("class") == "modref"]

    # Map consolidated points (a), (b), (c), (d)
    cons_points = {}
    for c in cons_children:
        s = text(c)
        for pt_letter in ["a", "b", "c", "d"]:
            if s.startswith(f"({pt_letter}) "):
                cons_points[pt_letter] = c

    # Map original OJ points (a), (b), (c)
    oj_points = {}
    for c in oj_children:
        s = text(c)
        for pt_letter in ["a", "b", "c"]:
            if s.startswith(f"({pt_letter}) "):
                oj_points[pt_letter] = c

    # Inspect each of the 3 sub-operations in Amending Article 1, point (40):
    # subpoint (a) -> replaces point (a)
    # subpoint (b) -> replaces point (c)
    # subpoint (c) -> adds point (d)
    sub_operations_spec = [
        ("a", "a", "replacement"),
        ("b", "c", "replacement"),
        ("c", "d", "addition"),
    ]
    clause_comparisons = []
    for (am_sub_letter, target_pt, op_kind), sub_tbl in zip(sub_operations_spec, subpoint_tables):
        sub_td = sub_tbl.xpath(
            "./*[local-name()='tbody']/*[local-name()='tr']/*[local-name()='td'][2]"
        )[0]
        sub_op_label_el = sub_td[0]
        quoted_tbl_el = sub_td[1]
        raw_quoted = text(quoted_tbl_el)
        derived_quoted = strip_outer_amendment_quotes(raw_quoted)
        cons_pt_el = cons_points[target_pt]
        cons_pt_text = text(cons_pt_el)
        oj_pt_el = oj_points.get(target_pt)

        clause_comparisons.append(
            {
                "amending_subpoint": f"(40)({am_sub_letter})",
                "target_article_113_point": f"({target_pt})",
                "operation_kind": op_kind,
                "subpoint_container_selector": t_amend.getpath(sub_tbl),
                "operation_label_selector": t_amend.getpath(sub_op_label_el),
                "operation_label": text(sub_op_label_el),
                "quoted_amendment_selector": t_amend.getpath(quoted_tbl_el),
                "quoted_amendment_text_raw": raw_quoted,
                "derived_amendment_text_outer_quote_stripped": derived_quoted,
                "consolidated_selector": t_cons.getpath(cons_pt_el),
                "consolidated_text": cons_pt_text,
                "original_oj_selector": t_oj.getpath(oj_pt_el) if oj_pt_el is not None else None,
                "original_oj_text": text(oj_pt_el) if oj_pt_el is not None else None,
                "matches_amendment": derived_quoted == cons_pt_text,
            }
        )

    # Check unchanged remaining wording of Article 113:
    # Headings + first two paragraphs + 'However:' intro + point (b)
    oj_unchanged_els = [
        c for c in oj_children if c not in {oj_points["a"], oj_points["c"]}
    ]
    cons_unchanged_els = [
        c
        for c in cons_children
        if c not in {cons_points["a"], cons_points["c"], cons_points["d"], *cons_modref_els}
    ]
    oj_unchanged_text = join_blocks(oj_unchanged_els)
    cons_unchanged_text = join_blocks(cons_unchanged_els)

    # Also verify full Article 113 reconstruction: taking original OJ Article 113,
    # replacing points (a) and (c) with the derived amendment clauses, and appending
    # derived point (d) equals consolidated Article 113 with editorial modref markers removed.
    cons_without_modrefs_els = [c for c in cons_children if c not in set(cons_modref_els)]
    cons_without_modrefs_text = join_blocks(cons_without_modrefs_els)
    reconstructed_blocks = [
        text(oj_children[0]),  # Article 113
        text(oj_children[1]),  # Entry into force and application
        text(oj_children[2]),  # first paragraph
        text(oj_children[3]),  # second paragraph
        text(oj_children[4]),  # However:
        clause_comparisons[0]["derived_amendment_text_outer_quote_stripped"],  # replaced (a)
        text(oj_points["b"]),  # unchanged (b)
        clause_comparisons[1]["derived_amendment_text_outer_quote_stripped"],  # replaced (c)
        clause_comparisons[2]["derived_amendment_text_outer_quote_stripped"],  # added (d)
    ]
    reconstructed_text = " ".join(reconstructed_blocks)

    return {
        "article": "113",
        "amending_provision": "Article 1, point (40)",
        "amending_container_selector": t_amend.getpath(point40_el),
        "introductory_operation_label_selector": t_amend.getpath(intro_label_el),
        "introductory_operation_label": text(intro_label_el),
        "clause_comparisons": clause_comparisons,
        "all_replacement_and_addition_clauses_match_amendment": all(
            c["matches_amendment"] for c in clause_comparisons
        ),
        "identified_editorial_markers_removed_for_comparison": [
            {
                "selector": t_cons.getpath(m),
                "tag": etree.QName(m).localname,
                "class": m.get("class"),
                "text": text(m),
            }
            for m in cons_modref_els
        ],
        "remaining_unchanged_wording_comparison": {
            "original_oj_unchanged_selectors": [t_oj.getpath(e) for e in oj_unchanged_els],
            "consolidated_unchanged_selectors": [t_cons.getpath(e) for e in cons_unchanged_els],
            "original_oj_unchanged_text": oj_unchanged_text,
            "consolidated_unchanged_text": cons_unchanged_text,
            "original_oj_unchanged_sha256": digest(oj_unchanged_text),
            "consolidated_unchanged_sha256": digest(cons_unchanged_text),
            "remaining_wording_matches_original": oj_unchanged_text == cons_unchanged_text,
            "full_reconstructed_article_113_matches_consolidated_without_modrefs": (
                reconstructed_text == cons_without_modrefs_text
            ),
        },
        "discrepancies": [],
    }


def build_stage8_markdown(report: dict) -> str:
    art6 = report["article_6_check"]
    art113 = report["article_113_check"]
    snaps = report["verified_sources"]

    lines = [
        "# AeacusAI — Stage 8 Targeted Amendment Provenance Check (Articles 6 and 113)",
        "",
        "- **Scope**: Targeted provenance check for EU AI Act `Article 6` and `Article 113` only (not a generic amendment parser).",
        "- **Ingestion permitted**: `false` (all canonical records and Stage 7 selection files remain untouched).",
        "- **Comparison basis**: Performed on temporary derived text only; canonical records and raw XHTML files are unmodified.",
        "",
        "---",
        "",
        "## 1. Verified Source Artifacts",
        "",
        f"1. **Original 2024 Official Journal AI Act (`T1-AIA-OJ-2024`)**: `{snaps['T1-AIA-OJ-2024']['source_snapshot_id']}` (`{snaps['T1-AIA-OJ-2024']['relative_path']}`)",
        f"2. **Amending Regulation (EU) 2026/1744 (`T1-AIA-AMEND-2026-1744`)**: `{snaps['T1-AIA-AMEND-2026-1744']['source_snapshot_id']}` (`{snaps['T1-AIA-AMEND-2026-1744']['relative_path']}`)",
        f"3. **Pinned Consolidated AI Act dated 2026-07-27 (`T1-AIA-CONS-20260727`)**: `{snaps['T1-AIA-CONS-2026-07-27' if 'T1-AIA-CONS-2026-07-27' in snaps else 'T1-AIA-CONS-20260727']['source_snapshot_id']}` (`{snaps['T1-AIA-CONS-20260727']['relative_path']}`)",
        "",
        "### Declared Temporary Comparison Normalizations",
        "",
        "1. **`legal-whitespace-v1`**: Collapses runs of whitespace (`\" \".join(\"\".join(el.itertext()).split())`), matching all prior stages.",
        "2. **Outer quotation boundary stripping on quoted amendment blocks (`strip_outer_amendment_quotes`)**: Removes only the single leading opening quote (`‘`) and/or single trailing closing quote (`’`) that the Official Journal amending act places around quoted insertion/replacement blocks (and excludes the trailing `;` sibling paragraph that terminates each amending point in the OJ table).",
            "3. **Editorial consolidation marker exclusion (`<p class=\"modref\">`)**: Excludes `<p class=\"modref\">` sibling markers (`2` markers in `Article 6`: `▼M1`, `▼B`; `5` markers in `Article 113`: `▼M1`, `▼B`, `▼M1`, `▼M1`, `▼B`) on the temporary consolidated comparison copy when testing residual parity against the original 2024 OJ wording. No internal punctuation, symbols, or legal text are stripped.",
        "",
        "---",
        "",
        "## 2. Article 6 Provenance Check (`Amending Article 1, point (8)`)",
        "",
        f"- **Amending container selector**: `{art6['amending_container_selector']}`",
        f"- **Operation label** (`{art6['operation_label_selector']}`): `{art6['operation_label']}`",
        f"- **Inserted paragraphs `1a`, `1b`, `1c` match amendment**: `{art6['inserted_paragraphs_all_match']}`",
        f"- **Removing insertions (`1a`–`1c`) and editorial markers (`▼M1`, `▼B`) leaves exact original Article 6 wording**: `{art6['residual_wording_comparison']['residual_matches_original_article_6_wording']}` (`4,041` chars, SHA-256 `{art6['residual_wording_comparison']['original_oj_sha256']}`)",
        "",
        "### Quoted Amendment Text vs. Consolidated Paragraphs `1a–1c`",
        "",
    ]

    for p in art6["paragraph_comparisons"]:
        lines.extend(
            [
                f"#### Paragraph `{p['paragraph']}` (`exact_match={p['exact_match']}`)",
                f"- **Amendment selector**: `{p['amendment_selector']}`",
                f"- **Consolidated selector**: `{p['consolidated_selector']}`",
                f"- **Quoted in 2026/1744**: {p['quoted_amendment_text_raw']}",
                f"- **Consolidated text**: {p['consolidated_paragraph_text']}",
                "",
            ]
        )

    lines.extend(
        [
            "---",
            "",
            "## 3. Article 113 Provenance Check (`Amending Article 1, point (40)`)",
            "",
            f"- **Amending container selector**: `{art113['amending_container_selector']}`",
            f"- **Introductory operation label** (`{art113['introductory_operation_label_selector']}`): `{art113['introductory_operation_label']}`",
            f"- **Replacement/addition clauses `(a)`, `(c)`, `(d)` match amendment**: `{art113['all_replacement_and_addition_clauses_match_amendment']}`",
            f"- **Remaining wording (headings, first two paragraphs, `'However:'`, and point `(b)`) matches original Article 113**: `{art113['remaining_unchanged_wording_comparison']['remaining_wording_matches_original']}` (`{len(art113['remaining_unchanged_wording_comparison']['original_oj_unchanged_text'])}` chars, SHA-256 `{art113['remaining_unchanged_wording_comparison']['original_oj_unchanged_sha256']}`)",
            "",
            "### Sub-Operations in Amending Article 1, Point (40)",
            "",
        ]
    )

    for c in art113["clause_comparisons"]:
        lines.extend(
            [
                f"#### Amending `{c['amending_subpoint']}` → Article 113 point `{c['target_article_113_point']}` (`{c['operation_kind']}`, `matches_amendment={c['matches_amendment']}`)",
                f"- **Operation label** (`{c['operation_label_selector']}`): `{c['operation_label']}`",
                f"- **Amendment quoted selector**: `{c['quoted_amendment_selector']}`",
                f"- **Consolidated selector**: `{c['consolidated_selector']}`",
                f"- **Original OJ selector**: `{c['original_oj_selector']}`",
                f"- **Original OJ text**: {c['original_oj_text'] if c['original_oj_text'] else '*(not present in original 2024 OJ; added by 2026/1744)*'}",
                f"- **Quoted in 2026/1744**: {c['quoted_amendment_text_raw']}",
                f"- **Consolidated text**: {c['consolidated_text']}",
                "",
            ]
        )

    lines.extend(
        [
            "---",
            "",
            "## 4. Discrepancies, Caveats & Unresolved Items",
            "",
            "- **Observed textual discrepancies in Articles 6 and 113**: `0` (after the declared outer-quote boundary stripping on quoted amendment blocks and `<p class=\"modref\">` exclusion on the temporary consolidated comparison copy).",
            "- **No legal-applicability or review certification**: Matching text between Amending Regulation (EU) 2026/1744 and the pinned 2026-07-27 consolidated snapshot for Articles 6 and 113 confirms textual provenance for those two articles only; it does **not** establish current legal applicability, entry-into-force/application date conclusions, or completed legal review.",
            "- **Unresolved items (ingestion remains closed)**:",
            "  1. **Full amendment reconciliation**: Only Article 1 points (8) and (40) of Regulation (EU) 2026/1744 were checked in this stage; the remaining points of Article 1 (and Articles 2–4 / recitals of 2026/1744) have not yet been parsed or reconciled against the consolidated text.",
            "  2. **Corrigendum verification**: Discovered corrigendum candidates in `source_register.json` (`32024R1689R(01)`, `32024R1689R(03)`, `32024R1689R(04)`, `32026R1744R(01)`) remain unverified.",
            "  3. **Edition selection & review gates**: All canonical records remain `validation_status=\"pending\"`, `review_status=\"not_reviewed\"`, and `indexable=false`, and no active retrieval edition has been selected.",
        ]
    )

    return "\n".join(lines) + "\n"


def main() -> None:
    artifacts, trees = verify_and_load_sources()
    art6_check = check_article_6_provenance(artifacts, trees)
    art113_check = check_article_113_provenance(artifacts, trees)

    assert art6_check["inserted_paragraphs_all_match"] is True
    assert (
        art6_check["residual_wording_comparison"]["residual_matches_original_article_6_wording"]
        is True
    )
    assert art113_check["all_replacement_and_addition_clauses_match_amendment"] is True
    assert (
        art113_check["remaining_unchanged_wording_comparison"]["remaining_wording_matches_original"]
        is True
    )
    assert (
        art113_check["remaining_unchanged_wording_comparison"][
            "full_reconstructed_article_113_matches_consolidated_without_modrefs"
        ]
        is True
    )

    report = {
        "stage": "selected_amendments_stage8",
        "scope": "Bounded provenance check for AI Act Articles 6 and 113 only",
        "ingestion_permitted": False,
        "active_retrieval_edition": None,
        "verified_sources": {
            sid: {
                "source_id": sid,
                "source_snapshot_id": artifacts[sid]["source_snapshot_id"],
                "relative_path": artifacts[sid]["relative_path"],
                "sha256": artifacts[sid]["sha256"],
                "manifest_sha256_verified": True,
            }
            for sid in REQUIRED_SOURCE_IDS
        },
        "temporary_comparison_normalizations": [
            {
                "name": "legal-whitespace-v1",
                "description": (
                    "Collapses consecutive whitespace characters via "
                    "' '.join(''.join(element.itertext()).split())."
                ),
            },
            {
                "name": "strip_outer_amendment_quotes",
                "description": (
                    "On temporary derived text for Amending Regulation (EU) 2026/1744 quoted "
                    "blocks only, strips the single leading opening quote (‘) and/or single "
                    "trailing closing quote (’) enclosing the quoted provision, and excludes "
                    "the trailing ';' paragraph sibling that terminates the amending point row. "
                    "Internal quotes, punctuation, and symbols are preserved."
                ),
            },
            {
                "name": "exclude_consolidated_modref_elements_for_residual_check",
                "description": (
                    "On temporary derived comparison copies of consolidated Articles 6 and 113, "
                    "excludes <p class='modref'> editorial revision markers ('▼M1', '▼B') when "
                    "comparing residual wording against the original 2024 OJ edition."
                ),
            },
        ],
        "verification_summary": {
            "all_three_sources_verified_against_manifest": True,
            "article_6_inserted_paragraphs_1a_to_1c_match_amendment": art6_check[
                "inserted_paragraphs_all_match"
            ],
            "article_6_residual_wording_matches_original_oj": art6_check[
                "residual_wording_comparison"
            ]["residual_matches_original_article_6_wording"],
            "article_113_replacement_and_addition_clauses_match_amendment": art113_check[
                "all_replacement_and_addition_clauses_match_amendment"
            ],
            "article_113_remaining_wording_matches_original_oj": art113_check[
                "remaining_unchanged_wording_comparison"
            ]["remaining_wording_matches_original"],
            "article_113_full_reconstructed_text_matches_consolidated_without_modrefs": art113_check[
                "remaining_unchanged_wording_comparison"
            ]["full_reconstructed_article_113_matches_consolidated_without_modrefs"],
            "discrepancy_count": len(art6_check["discrepancies"])
            + len(art113_check["discrepancies"]),
        },
        "article_6_check": art6_check,
        "article_113_check": art113_check,
        "unresolved_and_out_of_scope": {
            "full_amendment_reconciliation": "unresolved (only Article 1 points (8) and (40) checked)",
            "corrigendum_verification": (
                "unresolved (candidates 32024R1689R(01), 32024R1689R(03), "
                "32024R1689R(04), 32026R1744R(01) not yet audited)"
            ),
            "current_law_or_applicability_certified": False,
            "legal_review_completed": False,
            "canonical_records_modified": False,
            "stage7_manifest_modified": False,
        },
    }

    md_text = build_stage8_markdown(report)

    json_out = ROOT / "reports" / "selected_amendments_stage8.json"
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    md_out = ROOT / "reports" / "selected_amendments_stage8.md"
    md_out.write_text(md_text, encoding="utf-8")

    print(
        json.dumps(
            {
                "stage": report["stage"],
                "verification_summary": report["verification_summary"],
                "ingestion_permitted": report["ingestion_permitted"],
            }
        )
    )


if __name__ == "__main__":
    main()
