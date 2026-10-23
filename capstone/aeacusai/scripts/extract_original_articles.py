"""Stage 1 offline parser checkpoint: extract complete article-level parent records
from the original 2024 EU AI Act Official Journal XHTML artifact (T1-AIA-OJ-2024).

Preserves all existing files and the 45-record review baseline.
Performs no paragraph child decomposition, annex parsing, consolidated parsing,
cross-reference resolution, Charter parsing, network calls or vector-store operations.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from jsonschema import Draft202012Validator

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from extract_review_samples import NS, ROOT, digest, join_blocks, parse, text

SOURCE_ID = "T1-AIA-OJ-2024"
ARTICLE_ID_RE = re.compile(r"^art_(\d+[a-z]*)$")


def load_source_artifact(manifest_path: Path = ROOT / "acquisition_manifest.json") -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = {a["source_id"]: a for a in manifest["artifacts"]}
    if SOURCE_ID not in artifacts:
        raise ValueError(f"Missing required artifact in manifest: {SOURCE_ID}")
    artifact = artifacts[SOURCE_ID]
    raw_path = ROOT / artifact["relative_path"]
    actual_sha256 = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    if actual_sha256 != artifact["sha256"]:
        raise ValueError(
            f"Source artifact checksum mismatch for {SOURCE_ID}: "
            f"expected {artifact['sha256']}, got {actual_sha256}"
        )
    return artifact


def _article_label_from_source(article_el, fallback_number: str) -> str:
    """Build the article label from headings actually present in the source element."""
    title_nodes = article_el.xpath("./h:p[@class='oj-ti-art']", namespaces=NS)
    subtitle_nodes = article_el.xpath(
        "./h:div[@class='eli-title']//h:p[@class='oj-sti-art'] | ./h:p[@class='oj-sti-art']",
        namespaces=NS,
    )
    heading = text(title_nodes[0]) if title_nodes else f"Article {fallback_number}"
    subtitle = text(subtitle_nodes[0]) if subtitle_nodes else ""
    return f"{heading} — {subtitle}" if subtitle else heading


def extract_original_articles(
    artifact: dict,
    validator: Draft202012Validator,
) -> list[dict]:
    """Extract all 113 native article containers in document order from T1-AIA-OJ-2024."""
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
    for article_el in article_elements:
        native_id = article_el.get("id", "")
        match = ARTICLE_ID_RE.fullmatch(native_id)
        if not match:
            raise ValueError(f"Unexpected article id: {native_id}")
        number = match.group(1)
        path = f"article/{number}"
        normalized_text = join_blocks([article_el])
        record = {
            "schema_version": "0.1.0",
            "record_id": f"{snap}::{path}",
            "source_snapshot_id": snap,
            "parent_id": None,
            "unit_kind": "article",
            "legal_function": "operative",
            "label": _article_label_from_source(article_el, number),
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

    return records


def run_stage1_checks(
    records_pass1: list[dict],
    records_pass2: list[dict],
    validator: Draft202012Validator,
    baseline_path: Path = ROOT / "records" / "review_records.json",
) -> dict:
    """Run focused offline verification checks for Stage 1 original articles."""
    expected_numbers = [str(i) for i in range(1, 114)]
    extracted_numbers = [r["locator"]["article"] for r in records_pass1]
    record_ids = [r["record_id"] for r in records_pass1]
    selectors = [r["source_location"]["selector"] for r in records_pass1]

    # Check 1: Exactly 113 unique article records, Articles 1–113 in document order
    count_is_113 = len(records_pass1) == 113
    unique_record_ids = len(set(record_ids)) == 113
    unique_selectors = len(set(selectors)) == 113
    exact_1_to_113_order = extracted_numbers == expected_numbers
    assert count_is_113, f"Expected 113 records, got {len(records_pass1)}"
    assert unique_record_ids, "Duplicate record_id values detected"
    assert unique_selectors, "Duplicate source_location selector values detected"
    assert exact_1_to_113_order, "Extracted articles do not match ordered Articles 1–113"

    # Check 2: All records satisfy the existing JSON schema and non-indexable review gate
    for record in records_pass1:
        validator.validate(record)
        assert record["unit_kind"] == "article"
        assert record["legal_function"] == "operative"
        assert record["children"] == []
        assert record["cross_references"] == []
        assert record["validation_status"] == "pending"
        assert record["review_status"] == "not_reviewed"
        assert record["indexable"] is False
        assert record["text_sha256"] == digest(record["text"])

    # Check 3: Article 6 text and text_sha256 exactly match the existing original-edition Article 6 parent baseline
    baseline_records = json.loads(baseline_path.read_text(encoding="utf-8"))
    snap = records_pass1[0]["source_snapshot_id"]
    baseline_art6_id = f"{snap}::article/6"
    baseline_art6 = next(
        (r for r in baseline_records if r["record_id"] == baseline_art6_id),
        None,
    )
    if baseline_art6 is None:
        raise ValueError(f"Baseline record not found: {baseline_art6_id}")

    stage1_art6 = next(
        (r for r in records_pass1 if r["record_id"] == baseline_art6_id),
        None,
    )
    if stage1_art6 is None:
        raise ValueError(f"Stage 1 Article 6 record not found: {baseline_art6_id}")

    art6_text_matches = stage1_art6["text"] == baseline_art6["text"]
    art6_sha256_matches = stage1_art6["text_sha256"] == baseline_art6["text_sha256"]
    art6_selector_matches = (
        stage1_art6["source_location"]["selector"]
        == baseline_art6["source_location"]["selector"]
    )
    assert art6_text_matches, "Stage 1 Article 6 text does not match baseline"
    assert art6_sha256_matches, "Stage 1 Article 6 text_sha256 does not match baseline"
    assert art6_selector_matches, "Stage 1 Article 6 selector does not match baseline"

    # Check 4: Second extraction produces identical records
    reproducible = records_pass1 == records_pass2
    assert reproducible, "Second extraction did not produce identical records"

    return {
        "stage": "original_articles_stage1",
        "source_id": SOURCE_ID,
        "source_snapshot_id": snap,
        "record_count": len(records_pass1),
        "technical_checks": {
            "manifest_sha256_verified": True,
            "exact_113_unique_articles_1_to_113_in_order": (
                count_is_113 and unique_record_ids and unique_selectors and exact_1_to_113_order
            ),
            "all_records_satisfy_json_schema": True,
            "article_6_matches_baseline_text_and_sha256": (
                art6_text_matches and art6_sha256_matches and art6_selector_matches
            ),
            "article_6_text_sha256": stage1_art6["text_sha256"],
            "article_6_char_length": len(stage1_art6["text"]),
            "second_extraction_identical": reproducible,
        },
        "content_review_and_ingestion_status": {
            "validation_status": "pending",
            "review_status": "not_reviewed",
            "all_indexable_false": True,
            "legally_reviewed": False,
            "ready_for_indexing": False,
            "note": (
                "Passing Stage 1 technical extraction checks does not mean the corpus "
                "is legally reviewed or ready for indexing. Paragraph child records, "
                "recitals, annexes, consolidated-edition parsing, footnote expansion, "
                "and cross-reference resolution remain out of scope for this checkpoint."
            ),
        },
        "extracted_article_inventory": {
            "first_article_id": records_pass1[0]["record_id"],
            "first_article_label": records_pass1[0]["label"],
            "last_article_id": records_pass1[-1]["record_id"],
            "last_article_label": records_pass1[-1]["label"],
            "article_numbers": extracted_numbers,
        },
    }


def main() -> None:
    schema = json.loads((ROOT / "legal_record.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    artifact = load_source_artifact()

    records_pass1 = extract_original_articles(artifact, validator)
    records_pass2 = extract_original_articles(artifact, validator)

    report = run_stage1_checks(records_pass1, records_pass2, validator)

    records_out = ROOT / "records" / "original_articles_stage1.json"
    records_out.parent.mkdir(parents=True, exist_ok=True)
    records_out.write_text(
        json.dumps(records_pass1, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    report_out = ROOT / "reports" / "original_articles_stage1_validation.json"
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
