"""Stage 7 offline checkpoint: prepare a bounded corpus review selection manifest,
human-readable Markdown review pack, and validation report from the explicit 6-file
allowlist of Stage 1–5 and Stage 6 v2 extracted parent records.

Excludes the 45-record sample baseline (`records/review_records.json`) and the
superseded Stage 6 v1 Charter output (`records/charter_articles_stage6.json`).
Does not discover input files via wildcards, extract new records, designate an
active retrieval edition, or enable ingestion.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from jsonschema import Draft202012Validator

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from extract_review_samples import ROOT, digest

# Explicit file allowlist (no wildcard discovery)
EXPLICIT_CORPUS_ALLOWLIST = [
    {
        "stage": "original_articles_stage1",
        "relative_path": "records/original_articles_stage1.json",
        "source_id": "T1-AIA-OJ-2024",
        "edition_group": "original_ai_act_oj_2024",
        "unit_kind": "article",
        "expected_count": 113,
    },
    {
        "stage": "original_recitals_stage2",
        "relative_path": "records/original_recitals_stage2.json",
        "source_id": "T1-AIA-OJ-2024",
        "edition_group": "original_ai_act_oj_2024",
        "unit_kind": "recital",
        "expected_count": 180,
    },
    {
        "stage": "original_annexes_stage3",
        "relative_path": "records/original_annexes_stage3.json",
        "source_id": "T1-AIA-OJ-2024",
        "edition_group": "original_ai_act_oj_2024",
        "unit_kind": "annex",
        "expected_count": 13,
    },
    {
        "stage": "consolidated_articles_stage4",
        "relative_path": "records/consolidated_articles_stage4.json",
        "source_id": "T1-AIA-CONS-20260727",
        "edition_group": "pinned_consolidated_ai_act_20260727",
        "unit_kind": "article",
        "expected_count": 119,
    },
    {
        "stage": "consolidated_annexes_stage5",
        "relative_path": "records/consolidated_annexes_stage5.json",
        "source_id": "T1-AIA-CONS-20260727",
        "edition_group": "pinned_consolidated_ai_act_20260727",
        "unit_kind": "annex",
        "expected_count": 14,
    },
    {
        "stage": "charter_articles_stage6_v2",
        "relative_path": "records/charter_articles_stage6_v2.json",
        "source_id": "T1-CHARTER-OJ-2012",
        "edition_group": "charter_of_fundamental_rights_2012",
        "unit_kind": "article",
        "expected_count": 54,
    },
]

EXCLUDED_RECORD_FILES = [
    {
        "relative_path": "records/review_records.json",
        "reason": "45-record v0.2 sample review baseline; retained as regression reference only.",
    },
    {
        "relative_path": "records/charter_articles_stage6.json",
        "reason": (
            "Superseded by records/charter_articles_stage6_v2.json (parser_revision "
            "'charter-articles-stage6-v2'), which corrects Article 54's end boundary to "
            "exclude document-level closing separators ('°', '°°') and the Lisbon "
            "proclamation adaptation note."
        ),
    },
]

EXPECTED_TOTALS = {
    "original_ai_act": 306,
    "pinned_consolidated_ai_act": 133,
    "charter": 54,
    "total": 493,
}


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_stage7_artifacts() -> tuple[dict, str, dict]:
    manifest = json.loads((ROOT / "acquisition_manifest.json").read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "legal_record.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    artifacts_by_source_id = {a["source_id"]: a for a in manifest["artifacts"]}

    # Verify all raw XHTML artifacts still match acquisition_manifest.json
    for art in manifest["artifacts"]:
        raw_path = ROOT / art["relative_path"]
        if _file_sha256(raw_path) != art["sha256"]:
            raise ValueError(f"Raw source checksum mismatch for {art['source_id']}")

    selected_files_manifest: list[dict] = []
    all_records: list[dict] = []
    counts_by_group = {
        "original_ai_act": 0,
        "pinned_consolidated_ai_act": 0,
        "charter": 0,
    }

    for entry in EXPLICIT_CORPUS_ALLOWLIST:
        file_path = ROOT / entry["relative_path"]
        if not file_path.exists():
            raise FileNotFoundError(f"Allowlisted file missing: {entry['relative_path']}")

        file_sha = _file_sha256(file_path)
        records = json.loads(file_path.read_text(encoding="utf-8"))
        source_artifact = artifacts_by_source_id[entry["source_id"]]
        expected_snapshot = source_artifact["source_snapshot_id"]

        if len(records) != entry["expected_count"]:
            raise ValueError(
                f"Expected {entry['expected_count']} records in {entry['relative_path']}, "
                f"got {len(records)}"
            )

        for r in records:
            validator.validate(r)
            if r["source_snapshot_id"] != expected_snapshot:
                raise ValueError(
                    f"Record {r['record_id']} snapshot {r['source_snapshot_id']} does not "
                    f"match declared snapshot {expected_snapshot}"
                )
            if not r["record_id"].startswith(expected_snapshot + "::"):
                raise ValueError(
                    f"Record ID {r['record_id']} does not start with declared snapshot prefix"
                )
            if r["unit_kind"] != entry["unit_kind"]:
                raise ValueError(
                    f"Record {r['record_id']} unit_kind {r['unit_kind']} != {entry['unit_kind']}"
                )
            if r["text_sha256"] != digest(r["text"]):
                raise ValueError(f"Digest mismatch for {r['record_id']}")
            if r["validation_status"] != "pending":
                raise ValueError(f"Expected validation_status='pending' for {r['record_id']}")
            if r["review_status"] != "not_reviewed":
                raise ValueError(f"Expected review_status='not_reviewed' for {r['record_id']}")
            if r["indexable"] is not False:
                raise ValueError(f"Expected indexable=False for {r['record_id']}")

        if entry["source_id"] == "T1-AIA-OJ-2024":
            counts_by_group["original_ai_act"] += len(records)
        elif entry["source_id"] == "T1-AIA-CONS-20260727":
            counts_by_group["pinned_consolidated_ai_act"] += len(records)
        elif entry["source_id"] == "T1-CHARTER-OJ-2012":
            counts_by_group["charter"] += len(records)

        selected_files_manifest.append(
            {
                "stage": entry["stage"],
                "relative_path": entry["relative_path"],
                "file_sha256": file_sha,
                "source_id": entry["source_id"],
                "source_snapshot_id": expected_snapshot,
                "edition_group": entry["edition_group"],
                "unit_kind": entry["unit_kind"],
                "record_count": len(records),
            }
        )
        all_records.extend(records)

    total_records = len(all_records)
    unique_record_ids = {r["record_id"] for r in all_records}
    assert counts_by_group["original_ai_act"] == EXPECTED_TOTALS["original_ai_act"]
    assert (
        counts_by_group["pinned_consolidated_ai_act"]
        == EXPECTED_TOTALS["pinned_consolidated_ai_act"]
    )
    assert counts_by_group["charter"] == EXPECTED_TOTALS["charter"]
    assert total_records == EXPECTED_TOTALS["total"]
    assert len(unique_record_ids) == EXPECTED_TOTALS["total"], (
        "Duplicate record_id detected across selected corpus files"
    )

    records_by_id = {r["record_id"]: r for r in all_records}
    cons_snap = artifacts_by_source_id["T1-AIA-CONS-20260727"]["source_snapshot_id"]
    charter_snap = artifacts_by_source_id["T1-CHARTER-OJ-2012"]["source_snapshot_id"]
    oj_snap = artifacts_by_source_id["T1-AIA-OJ-2024"]["source_snapshot_id"]
    amend_snap = artifacts_by_source_id["T1-AIA-AMEND-2026-1744"]["source_snapshot_id"]

    selection_manifest = {
        "stage": "corpus_selection_stage7",
        "selection_status": "pending_review",
        "ingestion_permitted": False,
        "active_retrieval_edition": None,
        "edition_separation_policy": (
            "Original 2024 Official Journal AI Act records (T1-AIA-OJ-2024) and pinned "
            "consolidated AI Act records dated 2026-07-27 (T1-AIA-CONS-20260727) are kept "
            "explicitly separate under distinct source_snapshot_id namespaces. No active "
            "retrieval edition is designated at this checkpoint, and editions must never be "
            "silently mixed in a single retrieval query."
        ),
        "charter_supersession": {
            "selected_file": "records/charter_articles_stage6_v2.json",
            "parser_revision": "charter-articles-stage6-v2",
            "superseded_file_excluded": "records/charter_articles_stage6.json",
            "reason": (
                "Stage 6 v2 corrects Charter Article 54's DOM end boundary to exclude "
                "document-level closing separators ('°', '°°') and the Treaty of Lisbon "
                "proclamation adaptation sentence (314 chars, sha256 "
                "ce552ea083a96962e6722f57b5e35d7011d0ff755bae68783cace3e096612a5c)."
            ),
        },
        "excluded_files": EXCLUDED_RECORD_FILES,
        "unparsed_acquired_artifacts": [
            {
                "source_id": "T1-AIA-AMEND-2026-1744",
                "source_snapshot_id": amend_snap,
                "relative_path": artifacts_by_source_id["T1-AIA-AMEND-2026-1744"][
                    "relative_path"
                ],
                "status": (
                    "Acquired and SHA-256 verified in data/raw/ai-act-amendment-2026-1744-en.xhtml, "
                    "but not yet parsed into canonical records or reconciled provision-by-provision "
                    "with the pinned consolidated text (T1-AIA-CONS-20260727)."
                ),
            }
        ],
        "selected_files": selected_files_manifest,
        "expected_totals": EXPECTED_TOTALS,
        "measured_totals": {
            **counts_by_group,
            "total": total_records,
        },
    }

    # Build Markdown review pack with complete, untruncated text from selected records
    review_targets = [
        ("Consolidated Article 6", f"{cons_snap}::article/6"),
        ("Consolidated Annex III", f"{cons_snap}::annex/III"),
        ("Consolidated Article 113", f"{cons_snap}::article/113"),
        ("Charter Article 51", f"{charter_snap}::article/51"),
        ("Charter Article 52", f"{charter_snap}::article/52"),
        ("Charter Article 54 (corrected v2 boundary)", f"{charter_snap}::article/54"),
    ]

    md_lines = [
        "# AeacusAI — Stage 7 Corpus Review Pack",
        "",
        "- **Selection status**: `pending_review`",
        "- **Ingestion permitted**: `false`",
        "- **Active retrieval edition**: `null` (not yet designated)",
        "- **All selected records**: `validation_status=\"pending\"`, `review_status=\"not_reviewed\"`, `indexable=false`",
        "",
        "---",
        "",
        "## 1. Selected Corpus Inventory & Edition Separation",
        "",
        "This review pack is built strictly from the explicit 6-file Stage 7 allowlist (`493` total parent records). The 45-record v0.2 sample baseline (`records/review_records.json`) and the superseded Stage 6 v1 Charter output (`records/charter_articles_stage6.json`) are excluded.",
        "",
        "### Edition Separation Policy",
        "",
        "1. **Original 2024 Official Journal AI Act (`T1-AIA-OJ-2024`) — `306` records**:",
        f"   - Snapshot ID: `{oj_snap}`",
        "   - `records/original_articles_stage1.json`: `113` complete article parents (`article/1`–`article/113`)",
        "   - `records/original_recitals_stage2.json`: `180` complete interpretive recitals (`recital/1`–`recital/180`)",
        "   - `records/original_annexes_stage3.json`: `13` complete annex parents (`annex/I`–`annex/XIII`)",
        "2. **Pinned Consolidated AI Act dated 2026-07-27 (`T1-AIA-CONS-20260727`) — `133` records**:",
        f"   - Snapshot ID: `{cons_snap}`",
        "   - `records/consolidated_articles_stage4.json`: `119` complete article parents (`article/1`–`article/113` plus `article/4a`, `article/60a`, `article/75a`, `article/75b`, `article/75c`, `article/75d`)",
        "   - `records/consolidated_annexes_stage5.json`: `14` complete annex parents (`annex/I`–`annex/XIV`)",
        "   - Note: Consolidated texts produced by the Publications Office are documentation/reading tools and not independently authentic Official Journal legislation, nor is this snapshot claimed to be current applicable law. Original and consolidated editions remain strictly separated and no active retrieval edition is designated yet.",
        "3. **Charter of Fundamental Rights of the European Union (`T1-CHARTER-OJ-2012`) — `54` records**:",
        f"   - Snapshot ID: `{charter_snap}`",
        "   - `records/charter_articles_stage6_v2.json`: `54` complete article parents (`article/1`–`article/54`, parser revision `charter-articles-stage6-v2` superseding `records/charter_articles_stage6.json` after correcting Article 54's end boundary).",
        "",
        "---",
        "",
        "## 2. Complete Untruncated Review Passages from Selected Records",
        "",
        "All passages below are copied verbatim from the selected Stage 4, Stage 5, and Stage 6 v2 JSON records (`legal-whitespace-v1` normalization only, no truncation or summarization).",
        "",
    ]

    for heading_title, rec_id in review_targets:
        if rec_id not in records_by_id:
            raise KeyError(f"Required review target record missing from selection: {rec_id}")
        rec = records_by_id[rec_id]
        md_lines.extend(
            [
                f"### {heading_title}",
                "",
                f"- **Record ID**: `{rec['record_id']}`",
                f"- **Source Snapshot ID**: `{rec['source_snapshot_id']}`",
                f"- **Label**: `{rec['label']}`",
                f"- **Unit Kind / Legal Function**: `{rec['unit_kind']}` / `{rec['legal_function']}`",
                f"- **Locator Path**: `{rec['locator']['path']}`",
                f"- **DOM Selector**: `{rec['source_location']['selector']}`",
                f"- **Character Count**: `{len(rec['text'])}`",
                f"- **Text SHA-256**: `{rec['text_sha256']}`",
                f"- **Status**: `validation_status={rec['validation_status']}`, `review_status={rec['review_status']}`, `indexable={rec['indexable']}`",
                "",
                rec["text"],
                "",
            ]
        )

    md_lines.extend(
        [
            "---",
            "",
            "## 3. Remaining Limitations & Open Gates Before Ingestion",
            "",
            "1. **Paragraph & Subpoint Child Decomposition**:",
            "   - Stages 1–6 v2 extract complete parent records only (`article`, `recital`, `annex` with `children=[]`). Numbered paragraphs (including multi-block paragraphs such as consolidated `Article 6(3)` and inserted paragraphs `6(1a)`–`6(1c)`), Article 3 definitions, and numbered/lettered annex points are not yet decomposed into child records.",
            "2. **Table Row/Column Semantics**:",
            "   - While all table-cell text is preserved in source order within the parent `annex` and `article` records (including the 201 1-row list layout tables in OJ Annexes `I`–`XIII`, the 7 subpoint layout tables in Charter Articles `3` and `41`, and the 6 multi-row AIA code tables in Consolidated `Annex XIV`), flattened whitespace-normalized text does not preserve row/column relational structure.",
            "3. **Cross-Reference Resolution**:",
            "   - Every record currently carries `cross_references: []`. Internal cross-references (e.g., `Article 6` to `Annex I`, `Annex III`, `Article 49(2)`, `Article 96`, `Article 97`), cross-instrument references, and recital-to-article links remain explicitly pending.",
            "4. **Footnote & Editorial Marker Handling**:",
            "   - Footnote references and `p.oj-note` / `p.footnote` bodies are not yet expanded or linked. In the consolidated edition (`T1-AIA-CONS-20260727`), inline/block editorial revision markers (`▼M1`, `▼B`, `▼M1 —————`, `►M1`, `◄`) inside article and annex containers remain in-place in the normalized text (`Article 6`, `Article 113`, `Annex I`, `Annex VIII`, etc.).",
            "5. **Amending Act (`T1-AIA-AMEND-2026-1744`) & Corrigendum Verification**:",
            f"   - Amending Regulation (EU) 2026/1744 (`{amend_snap}`, `data/raw/ai-act-amendment-2026-1744-en.xhtml`) has been acquired and checksum-verified, but **has not yet been fully parsed into canonical records or reconciled provision-by-provision with the pinned consolidated text (`T1-AIA-CONS-20260727`)**.",
            "   - Discovered corrigendum candidates in `source_register.json` (`32024R1689R(01)`, `32024R1689R(03)`, `32024R1689R(04)`, `32026R1744R(01)`) and temporal applicability / entry-into-force rules (such as the staggered dates in consolidated `Article 113`) have not yet been audited.",
            "6. **Human Content Review & Edition Selection**:",
            "   - All `493` selected records remain `validation_status=\"pending\"`, `review_status=\"not_reviewed\"`, and `indexable=false`. No active retrieval edition has been selected, and ingestion into Pinecone remains closed.",
        ]
    )

    markdown_content = "\n".join(md_lines) + "\n"

    # Verify that each of the 6 review target texts appears untruncated in the Markdown review pack
    all_review_excerpts_present_untruncated = all(
        records_by_id[rec_id]["text"] in markdown_content for _, rec_id in review_targets
    )
    assert all_review_excerpts_present_untruncated, (
        "One or more required review excerpts are missing or truncated in the Markdown pack"
    )

    validation_report = {
        "stage": "corpus_selection_stage7",
        "selection_status": "pending_review",
        "ingestion_permitted": False,
        "active_retrieval_edition": None,
        "technical_checks": {
            "explicit_6_file_allowlist_used_without_wildcards": True,
            "excluded_sample_baseline_and_superseded_stage6_v1": True,
            "all_raw_artifacts_match_acquisition_manifest_sha256": True,
            "original_ai_act_total_equals_306": counts_by_group["original_ai_act"] == 306,
            "pinned_consolidated_ai_act_total_equals_133": (
                counts_by_group["pinned_consolidated_ai_act"] == 133
            ),
            "charter_v2_total_equals_54": counts_by_group["charter"] == 54,
            "combined_selected_total_equals_493": total_records == 493,
            "all_493_records_satisfy_json_schema": True,
            "all_493_record_ids_unique_across_selection": len(unique_record_ids) == 493,
            "all_493_text_sha256_digests_match_text": True,
            "all_493_records_pending_not_reviewed_and_indexable_false": True,
            "all_493_records_belong_to_declared_source_snapshots": True,
            "markdown_review_pack_contains_complete_untruncated_excerpts": (
                all_review_excerpts_present_untruncated
            ),
        },
        "measured_totals": {
            **counts_by_group,
            "total": total_records,
        },
        "selected_files": selected_files_manifest,
        "review_pack_excerpts_verified": [
            {
                "title": title,
                "record_id": rec_id,
                "source_snapshot_id": records_by_id[rec_id]["source_snapshot_id"],
                "char_length": len(records_by_id[rec_id]["text"]),
                "text_sha256": records_by_id[rec_id]["text_sha256"],
            }
            for title, rec_id in review_targets
        ],
    }

    return selection_manifest, markdown_content, validation_report


def main() -> None:
    selection_manifest, markdown_content, validation_report = build_stage7_artifacts()

    manifest_out = ROOT / "corpus_selection_stage7.json"
    manifest_out.write_text(
        json.dumps(selection_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    md_out = ROOT / "reports" / "corpus_review_stage7.md"
    md_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.write_text(markdown_content, encoding="utf-8")

    val_out = ROOT / "reports" / "corpus_selection_stage7_validation.json"
    val_out.parent.mkdir(parents=True, exist_ok=True)
    val_out.write_text(
        json.dumps(validation_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "stage": validation_report["stage"],
                "selection_status": validation_report["selection_status"],
                "ingestion_permitted": validation_report["ingestion_permitted"],
                "totals": validation_report["measured_totals"],
                "technical_checks_passed": all(
                    v is True for v in validation_report["technical_checks"].values()
                ),
            }
        )
    )


if __name__ == "__main__":
    main()
