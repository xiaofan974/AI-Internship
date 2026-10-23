# AeacusAI — Tier 1 source acquisition and review samples

**Source review v0.2 · 22 October 2026 · No ingestion performed**

## Start here

Open **Review_Samples.md** to review the four requested categories of source text. It includes both the original and consolidated Article 6, original Recital 47, both versions of Annex III point 4, and Charter Article 21 with Articles 51–54 as context. These are source-derived passages, not model-generated legal summaries.

The package also contains the four exact official XHTML artifacts in `data/raw/`, an acquisition manifest with SHA-256 hashes and actual download URLs, 45 structured review records, the proposed JSON Schema, a sample comparison, a validation report, and the offline extraction script.

## Acquisition route and identity checks

EUR-Lex's main document pages returned robot-verification responses. The Publications Office of the European Union's public CELEX/CELLAR repository returned the actual XHTML documents via ordinary content negotiation (`Accept: application/xhtml+xml`, `Accept-Language: en`). This is an official EU repository, not a third-party summary or mirror. No captcha interaction or verification bypass was used.

All four response bodies were parsed as XHTML. Their publication identifiers, document titles and English body text were checked; the consolidated title includes 27.07.2026. Exact downloaded bytes were preserved and hashed. See `acquisition_manifest.json` for the request and resolved artifact URL, response type, byte count, timestamp, source title and checksum. Original and consolidated artifacts have distinct snapshot IDs.

## Structural findings

| Artifact | Structural observation |
| --- | --- |
| Original AI Act, 2024 OJ | 180 recital IDs, 113 article IDs, 13 annex IDs |
| Consolidated AI Act dated 27 July 2026 | 119 article IDs, 14 annex IDs, no native recital IDs |
| Charter, 2012 publication | Ordered Article 1–54 headings |
| Amending Regulation (EU) 2026/1744 | Acquired as a separate original-publication artifact; not used as a substitute for the consolidated text |

The consolidated artifact contains inserted article IDs (`art_4a`, `art_60a`, `art_75a`, `art_75b`, `art_75c`, `art_75d`) and `anx_XIV`. These are observations of this downloaded edition, not a complete legal-effects analysis. Original-edition count assertions must not be imposed on the consolidated copy. Recitals from the original remain separately identified legislative context, not silently relabeled as consolidated text.

**Paragraph-boundary finding:** the consolidated Article 6(3) is split into multiple sibling HTML blocks. Selecting only the first numbered div would omit its four lettered conditions and final profiling qualification. The sample extractor groups the complete numbered paragraph through the next top-level paragraph and verifies those elements are present. The full Article 6 parent is retained alongside the paragraph records.

## Scope and limits of this extraction

The Python script extracts a **partial review set**, not a full generic Article/Paragraph/Annex parser. It materializes Article 6 and its top-level paragraphs in both editions, Annex III and its eight areas in both editions, original Recital 47, and selected Charter articles. Not all subpoints, headings, footnotes or document-wide legal references are separately decomposed.

Sample records pass JSON Schema shape checks, checksum checks, source-block text comparisons and same-snapshot parent-link checks. `validation_status` remains `pending`, `review_status` remains `not_reviewed`, and `indexable` remains false because full parser coverage, cross-reference resolution, footnote expansion, legal-version/language-correction audit and human review are incomplete. Empty `cross_references` arrays explicitly mean the inventory is pending, not that the source has no references.

The full parent source text contains its original introductions and wording. Retrieved sub-items must later expand to those parents before a legal conclusion. These records neither classify the recruitment scenario nor establish conformity, control effectiveness or temporal applicability.

## Comparison of the selected editions

See `sample_comparison.json`: it compares complete normalized text without drawing legal conclusions. The original and consolidated Article 6 differ. The selected complete paragraph 3 and Annex III point 4 text compare equal under the declared whitespace normalization. This comparison is limited to the acquired snapshots and those selections.

## Review questions

1. Does the original/consolidated separation provide the source control you want?
2. In the sample text, are the exception conditions and surrounding qualifications visible rather than isolated into misleading snippets?
3. Are the source identity, locator, parent context and non-indexable review statuses sufficient for the next parser iteration?

Once these samples are accepted, the next implementation step is a complete offline parser and its coverage report, plus an amendment/corrigendum relationship audit. Source acceptance and extraction validation must precede embedding/upsert. Tier 2 and Tier 3 remain outside this first legal retrieval collection.

## Reproducibility

The included script uses only local artifacts and the pinned dependencies in `scripts/requirements.txt`. It recomputes source digests, verifies its selectors, extracts the review records, checks schema and critical paragraph/area completeness, and regenerates the review note and validation report. Running it again against unchanged inputs reproduces the same output records. It makes no model, embedding or Pinecone calls. Cursor can run it later from this package when we reach that checkpoint; no terminal commands are needed to review the files now.

## Official source pages

- [AI Act original OJ](https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng)
- [AI Act consolidated reading version](https://eur-lex.europa.eu/eli/reg/2024/1689/2026-07-27/eng)
- [Amending Regulation (EU) 2026/1744](https://eur-lex.europa.eu/eli/reg/2026/1744/oj/eng)
- [Charter](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX%3A12012P%2FTXT)
- [Publications Office original AI Act publication record](https://op.europa.eu/en/publication-detail/-/publication/dc8116a1-3fe6-11ef-865a-01aa75ed71a1/language-en)
