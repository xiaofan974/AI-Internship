"""Offline, source-bound review extraction. Not a general ingestion pipeline.

Requires lxml and jsonschema. Run with this script's parent package intact.
No network, model, embedding or vector-store calls are made.
"""

import copy
import hashlib
import json
import re
from pathlib import Path
from lxml import etree
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
NS = {"h": "http://www.w3.org/1999/xhtml"}


def text(element):
    return " ".join("".join(element.itertext()).split())


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse(path):
    return etree.parse(str(path), etree.XMLParser(resolve_entities=False, no_network=True))


def unique_id(tree, node_id):
    found = tree.xpath("//*[@id=$key]", key=node_id)
    if len(found) != 1:
        raise ValueError(f"Expected exactly one source element: {node_id}")
    return found[0]


def numbered_label(element):
    match = re.match(r"^(\d+[a-z]?)\.\s", text(element))
    return match.group(1) if match else None


def paragraph_groups(article):
    """Group immediate siblings from one top-level numbered paragraph to the next.

    The consolidated document does not wrap all of paragraph 3 in one div.
    Original OJ paragraph divs contain nested lists. Revision-marker siblings
    stay with their source position; a complete parent is always retained.
    """
    groups = []
    current = None
    for child in article:
        name = etree.QName(child).localname if isinstance(child.tag, str) else ""
        if name not in {"p", "div"}:
            continue
        number = numbered_label(child)
        if number:
            current = {"number": number, "elements": [child]}
            groups.append(current)
        elif current is not None:
            current["elements"].append(child)
    return groups


def join_blocks(elements):
    return " ".join(text(e) for e in elements if text(e))


def article_block(tree, number):
    headings = tree.xpath("//h:p[@class='ti-art']", namespaces=NS)
    matches = [h for h in headings if text(h) == f"Article {number}"]
    if len(matches) != 1:
        raise ValueError(f"Charter article {number} not uniquely identified")
    heading = matches[0]
    elements = [heading]
    for sibling in heading.itersiblings():
        if sibling.get("class") in {"ti-art", "ti-section-1", "ti-section-2"}:
            break
        elements.append(sibling)
    return elements


def area_groups(annex):
    """Identify direct, numbered Annex III area containers in either HTML form."""
    groups = {}
    for child in annex:
        if not isinstance(child.tag, str):
            continue
        name = etree.QName(child).localname
        if name not in {"table", "div"}:
            continue
        number = numbered_label(child)
        if number is not None:
            if number in groups:
                raise ValueError("Duplicated Annex III area")
            groups[number] = child
    if set(groups) != {str(i) for i in range(1, 9)}:
        raise ValueError("Annex III area inventory does not match this review target")
    return groups


def main():
    manifest = json.loads((ROOT / "acquisition_manifest.json").read_text())
    schema = json.loads((ROOT / "legal_record.schema.json").read_text())
    validator = Draft202012Validator(schema)
    artifacts = {a["source_id"]: a for a in manifest["artifacts"]}
    trees = {}
    for artifact in artifacts.values():
        raw = ROOT / artifact["relative_path"]
        if hashlib.sha256(raw.read_bytes()).hexdigest() != artifact["sha256"]:
            raise ValueError("Source artifact checksum mismatch")
        trees[artifact["source_id"]] = parse(raw)

    records = []
    selections = {}

    def add(source_id, path, label, kind, elements, function="operative", parent=None, locator=None):
        artifact = artifacts[source_id]
        snap = artifact["source_snapshot_id"]
        record = {
            "schema_version": "0.1.0", "record_id": snap + "::" + path,
            "source_snapshot_id": snap, "parent_id": parent,
            "unit_kind": kind, "legal_function": function, "label": label,
            "locator": {"path": path, **(locator or {})}, "language": "en", "tier": 1,
            "text": join_blocks(elements), "text_sha256": digest(join_blocks(elements)),
            "source_location": {
                "url": artifact["resolved_content_url"], "format": "html",
                "selector": " | ".join(trees[source_id].getpath(e) for e in elements),
            },
            "children": [], "cross_references": [],
            "normalization_version": "legal-whitespace-v1",
            "validation_status": "pending", "review_status": "not_reviewed", "indexable": False,
        }
        # Cross-reference inventory is intentionally pending. Do not manufacture
        # legal relationships from regex matches or label the source fully validated.
        validator.validate(record)
        records.append(record)
        selections[record["record_id"]] = (source_id, elements)
        return record

    for source_id in ["T1-AIA-OJ-2024", "T1-AIA-CONS-20260727"]:
        tree = trees[source_id]
        article = unique_id(tree, "art_6")
        parent = add(source_id, "article/6", "Article 6 — complete source parent", "article", [article], locator={"article": "6"})
        for group in paragraph_groups(article):
            number = group["number"]
            child = add(source_id, f"article/6/paragraph/{number}", f"Article 6({number})", "paragraph", group["elements"], parent=parent["record_id"], locator={"article": "6", "paragraph": number})
            parent["children"].append(child["record_id"])
        annex = unique_id(tree, "anx_III")
        parent = add(source_id, "annex/III", "Annex III — complete source parent", "annex", [annex], locator={"annex": "III"})
        for number, element in area_groups(annex).items():
            child = add(source_id, f"annex/III/point/{number}", f"Annex III, point {number}", "point", [element], parent=parent["record_id"], locator={"annex": "III", "point": number})
            parent["children"].append(child["record_id"])

    source_id = "T1-AIA-OJ-2024"
    add(source_id, "recital/47", "Recital 47", "recital", [unique_id(trees[source_id], "rct_47")], function="interpretive", locator={"recital": "47"})

    source_id = "T1-CHARTER-OJ-2012"
    for number in [21, 51, 52, 53, 54]:
        add(source_id, f"article/{number}", f"Charter Article {number}", "article", article_block(trees[source_id], number), locator={"article": str(number)})

    by_id = {r["record_id"]: r for r in records}
    assert len(by_id) == len(records), "Duplicate record IDs"
    for record in records:
        validator.validate(record)
        source_id, elements = selections[record["record_id"]]
        assert record["text"] == join_blocks(elements)
        assert record["text_sha256"] == digest(record["text"])
        for child in record["children"]:
            assert by_id[child]["parent_id"] == record["record_id"]
            assert by_id[child]["source_snapshot_id"] == record["source_snapshot_id"]
        assert not record["indexable"]
    for source_id in ["T1-AIA-OJ-2024", "T1-AIA-CONS-20260727"]:
        group = next(r for r in records if r["record_id"].startswith(artifacts[source_id]["source_snapshot_id"] + "::article/6/paragraph/3"))
        for marker in ["(a)", "(b)", "(c)", "(d)", "Notwithstanding", "profiling"]:
            assert marker in group["text"], f"Incomplete paragraph 3: {marker}"
        area = next(r for r in records if r["record_id"] == artifacts[source_id]["source_snapshot_id"] + "::annex/III/point/4")
        for marker in ["(a)", "(b)", "recruitment", "workers"]:
            assert marker in area["text"], f"Incomplete area 4: {marker}"

    output = ROOT / "records" / "review_records.json"
    output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n")
    review = ["# AeacusAI — source-derived review samples", "", "All text below comes from the downloaded official artifacts with whitespace normalization only. These are partial review selections, not a complete parsed corpus. Overall validation and cross-reference review remain pending; every record is non-indexable.", ""]
    targets = [
        ("T1-AIA-OJ-2024", "article/6"),
        ("T1-AIA-CONS-20260727", "article/6"),
        ("T1-AIA-OJ-2024", "recital/47"),
        ("T1-AIA-OJ-2024", "annex/III/point/4"),
        ("T1-AIA-CONS-20260727", "annex/III/point/4"),
        ("T1-CHARTER-OJ-2012", "article/21"),
    ]
    for sid, path in targets:
        record = by_id[artifacts[sid]["source_snapshot_id"] + "::" + path]
        review += [f"## {record['label']} · {sid}", "", f"Source artifact: `{artifacts[sid]['relative_path']}`", "", record["text"], ""]
    review += ["## Charter context — Articles 51–54", ""]
    for number in [51, 52, 53, 54]:
        record = by_id[artifacts["T1-CHARTER-OJ-2012"]["source_snapshot_id"] + f"::article/{number}"]
        review += [f"### {record['label']}", "", record["text"], ""]
    (ROOT / "Review_Samples.md").write_text("\n".join(review))

    inventory = {}
    for sid, tree in trees.items():
        ids = [e.get("id") for e in tree.xpath("//*[@id]")]
        inventory[sid] = {
            "native_article_ids": [i for i in ids if re.fullmatch(r"art_\d+[a-z]*", i)],
            "native_recital_ids": [i for i in ids if re.fullmatch(r"rct_\d+[a-z]*", i)],
            "native_annex_ids": [i for i in ids if re.fullmatch(r"anx_[IVXLCDM]+", i)],
            "charter_article_headings": [text(e) for e in tree.xpath("//h:p[@class='ti-art']", namespaces=NS)] if sid == "T1-CHARTER-OJ-2012" else [],
        }
    assert len(inventory["T1-AIA-OJ-2024"]["native_article_ids"]) == 113
    assert len(inventory["T1-AIA-OJ-2024"]["native_recital_ids"]) == 180
    assert len(inventory["T1-AIA-OJ-2024"]["native_annex_ids"]) == 13
    assert inventory["T1-CHARTER-OJ-2012"]["charter_article_headings"] == [f"Article {i}" for i in range(1, 55)]

    summary = {
        "sample_record_count": len(records), "all_indexable_false": True,
        "checks_passed": ["Downloaded artifact digests match manifest", "Sample JSON Schema validation", "Stable unique IDs and same-snapshot parent links", "Sample text equals complete selected source blocks", "Article 6(3) contains four conditions and profiling qualification in both editions", "Annex III point 4 contains both sub-items in both editions", "Original AI Act native IDs: 180 recitals, 113 articles, 13 annexes", "Charter article headings: ordered 1–54"],
        "incomplete_checks": ["Full generic parser and full source-text coverage", "Explicit cross-reference resolution (empty arrays are pending, not proof of no references)", "Footnote text expansion", "Complete amendment/corrigendum and language-applicability audit", "Human/legal review and release admission"],
        "scope_note": "This script extracts review samples only. Complete Article 6 and Annex III parent text are retained. Not all subpoints/headings/footnotes are separately decomposed. No compliance classification is performed.",
        "inventories": inventory,
    }
    (ROOT / "validation_report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"sample_records": len(records), "schema": "passed", "ingestion": "closed"}))


if __name__ == "__main__":
    main()
