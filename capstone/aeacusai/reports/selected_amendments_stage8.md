# AeacusAI — Stage 8 Targeted Amendment Provenance Check (Articles 6 and 113)

- **Scope**: Targeted provenance check for EU AI Act `Article 6` and `Article 113` only (not a generic amendment parser).
- **Ingestion permitted**: `false` (all canonical records and Stage 7 selection files remain untouched).
- **Comparison basis**: Performed on temporary derived text only; canonical records and raw XHTML files are unmodified.

---

## 1. Verified Source Artifacts

1. **Original 2024 Official Journal AI Act (`T1-AIA-OJ-2024`)**: `T1-AIA-OJ-2024@sha256:8f0b656302f9864cc87e040c371f209a9d65ae1a6cecc25ca5eb737e872d721a` (`data/raw/ai-act-oj-2024-en.xhtml`)
2. **Amending Regulation (EU) 2026/1744 (`T1-AIA-AMEND-2026-1744`)**: `T1-AIA-AMEND-2026-1744@sha256:9d754652b867722807e4219c85912ce354233e58a1b4eb8c7752b4d1922993db` (`data/raw/ai-act-amendment-2026-1744-en.xhtml`)
3. **Pinned Consolidated AI Act dated 2026-07-27 (`T1-AIA-CONS-20260727`)**: `T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715` (`data/raw/ai-act-consolidated-20260727-en.xhtml`)

### Declared Temporary Comparison Normalizations

1. **`legal-whitespace-v1`**: Collapses runs of whitespace (`" ".join("".join(el.itertext()).split())`), matching all prior stages.
2. **Outer quotation boundary stripping on quoted amendment blocks (`strip_outer_amendment_quotes`)**: Removes only the single leading opening quote (`‘`) and/or single trailing closing quote (`’`) that the Official Journal amending act places around quoted insertion/replacement blocks (and excludes the trailing `;` sibling paragraph that terminates each amending point in the OJ table).
3. **Editorial consolidation marker exclusion (`<p class="modref">`)**: Excludes `<p class="modref">` sibling markers (`2` markers in `Article 6`: `▼M1`, `▼B`; `5` markers in `Article 113`: `▼M1`, `▼B`, `▼M1`, `▼M1`, `▼B`) on the temporary consolidated comparison copy when testing residual parity against the original 2024 OJ wording. No internal punctuation, symbols, or legal text are stripped.

---

## 2. Article 6 Provenance Check (`Amending Article 1, point (8)`)

- **Amending container selector**: `/*/*[2]/*[4]/*[3]/*[1]/*[11]`
- **Operation label** (`/*/*[2]/*[4]/*[3]/*[1]/*[11]/*[3]/*/*[2]/*[1]`): `in Article 6, the following paragraphs are inserted:`
- **Inserted paragraphs `1a`, `1b`, `1c` match amendment**: `True`
- **Removing insertions (`1a`–`1c`) and editorial markers (`▼M1`, `▼B`) leaves exact original Article 6 wording**: `True` (`4,041` chars, SHA-256 `f4c56417818fa2f1eea5d28b5be8b562ab2e7eb18a6cfe143ebbed7ce5aa61ac`)

### Quoted Amendment Text vs. Consolidated Paragraphs `1a–1c`

#### Paragraph `1a` (`exact_match=True`)
- **Amendment selector**: `/*/*[2]/*[4]/*[3]/*[1]/*[11]/*[3]/*/*[2]/*[2]`
- **Consolidated selector**: `/*/*[2]/*[9]/*[4]/*[4]/*[3]/*[3]/*[5]`
- **Quoted in 2026/1744**: ‘1a. For the purposes of this Regulation, including paragraph 1 of this Article, AI systems that are solely used for non-safety related aspects of user assistance, performance optimisation, service efficiency, automation or convenience or quality control shall not qualify as safety components.
- **Consolidated text**: 1a. For the purposes of this Regulation, including paragraph 1 of this Article, AI systems that are solely used for non-safety related aspects of user assistance, performance optimisation, service efficiency, automation or convenience or quality control shall not qualify as safety components.

#### Paragraph `1b` (`exact_match=True`)
- **Amendment selector**: `/*/*[2]/*[4]/*[3]/*[1]/*[11]/*[3]/*/*[2]/*[3]`
- **Consolidated selector**: `/*/*[2]/*[9]/*[4]/*[4]/*[3]/*[3]/*[6]`
- **Quoted in 2026/1744**: 1b. Notwithstanding paragraph 1a, AI systems the failure or malfunctioning of which would endanger health and safety shall qualify as safety components.
- **Consolidated text**: 1b. Notwithstanding paragraph 1a, AI systems the failure or malfunctioning of which would endanger health and safety shall qualify as safety components.

#### Paragraph `1c` (`exact_match=True`)
- **Amendment selector**: `/*/*[2]/*[4]/*[3]/*[1]/*[11]/*[3]/*/*[2]/*[4]`
- **Consolidated selector**: `/*/*[2]/*[9]/*[4]/*[4]/*[3]/*[3]/*[7]`
- **Quoted in 2026/1744**: 1c. A product that is required to undergo a third-party conformity assessment solely due to risks other than risks to health and safety, in particular risks relating to the distribution of radio spectrum or electromagnetic interference that do not affect health and safety, shall not be considered as fulfilling the condition in paragraph 1, point (b).’
- **Consolidated text**: 1c. A product that is required to undergo a third-party conformity assessment solely due to risks other than risks to health and safety, in particular risks relating to the distribution of radio spectrum or electromagnetic interference that do not affect health and safety, shall not be considered as fulfilling the condition in paragraph 1, point (b).

---

## 3. Article 113 Provenance Check (`Amending Article 1, point (40)`)

- **Amending container selector**: `/*/*[2]/*[4]/*[3]/*[1]/*[43]`
- **Introductory operation label** (`/*/*[2]/*[4]/*[3]/*[1]/*[43]/*[3]/*/*[2]/*[1]`): `in Article 113, the third paragraph is amended as follows:`
- **Replacement/addition clauses `(a)`, `(c)`, `(d)` match amendment**: `True`
- **Remaining wording (headings, first two paragraphs, `'However:'`, and point `(b)`) matches original Article 113**: `True` (`377` chars, SHA-256 `949b29e3a41d3d5f028143f5dd7fdd89e7e09f0d50324839ebb8c72bfb6d0aaf`)

### Sub-Operations in Amending Article 1, Point (40)

#### Amending `(40)(a)` → Article 113 point `(a)` (`replacement`, `matches_amendment=True`)
- **Operation label** (`/*/*[2]/*[4]/*[3]/*[1]/*[43]/*[3]/*/*[2]/*[2]/*[3]/*/*[2]/*[1]`): `point (a) is replaced by the following:`
- **Amendment quoted selector**: `/*/*[2]/*[4]/*[3]/*[1]/*[43]/*[3]/*/*[2]/*[2]/*[3]/*/*[2]/*[2]`
- **Consolidated selector**: `/*/*[2]/*[9]/*[4]/*[14]/*[14]/*[7]`
- **Original OJ selector**: `/*/*[2]/*[4]/*[3]/*[13]/*[14]/*[6]`
- **Original OJ text**: (a) Chapters I and II shall apply from 2 February 2025;
- **Quoted in 2026/1744**: ‘(a) Chapters I and II shall apply from 2 February 2025, with the exception of Article 5(1), first subparagraph, points (ba) and (bb), and Article 5(1a) and (1b) which shall apply from 2 December 2026;’
- **Consolidated text**: (a) Chapters I and II shall apply from 2 February 2025, with the exception of Article 5(1), first subparagraph, points (ba) and (bb), and Article 5(1a) and (1b) which shall apply from 2 December 2026;

#### Amending `(40)(b)` → Article 113 point `(c)` (`replacement`, `matches_amendment=True`)
- **Operation label** (`/*/*[2]/*[4]/*[3]/*[1]/*[43]/*[3]/*/*[2]/*[3]/*[3]/*/*[2]/*[1]`): `point (c) is replaced by the following:`
- **Amendment quoted selector**: `/*/*[2]/*[4]/*[3]/*[1]/*[43]/*[3]/*/*[2]/*[3]/*[3]/*/*[2]/*[2]`
- **Consolidated selector**: `/*/*[2]/*[9]/*[4]/*[14]/*[14]/*[11]`
- **Original OJ selector**: `/*/*[2]/*[4]/*[3]/*[13]/*[14]/*[8]`
- **Original OJ text**: (c) Article 6(1) and the corresponding obligations in this Regulation shall apply from 2 August 2027.
- **Quoted in 2026/1744**: ‘(c) Chapter III, Sections 1, 2, and 3, with the exception of Article 6(5), shall apply from: (i) 2 December 2027 as regards AI systems classified as high-risk pursuant to Article 6(2) and Annex III; and (ii) 2 August 2028 as regards AI systems classified as high-risk pursuant to Article 6(1) and Annex I;’
- **Consolidated text**: (c) Chapter III, Sections 1, 2, and 3, with the exception of Article 6(5), shall apply from: (i) 2 December 2027 as regards AI systems classified as high-risk pursuant to Article 6(2) and Annex III; and (ii) 2 August 2028 as regards AI systems classified as high-risk pursuant to Article 6(1) and Annex I;

#### Amending `(40)(c)` → Article 113 point `(d)` (`addition`, `matches_amendment=True`)
- **Operation label** (`/*/*[2]/*[4]/*[3]/*[1]/*[43]/*[3]/*/*[2]/*[4]/*[3]/*/*[2]/*[1]`): `the following point is added:`
- **Amendment quoted selector**: `/*/*[2]/*[4]/*[3]/*[1]/*[43]/*[3]/*/*[2]/*[4]/*[3]/*/*[2]/*[2]`
- **Consolidated selector**: `/*/*[2]/*[9]/*[4]/*[14]/*[14]/*[13]`
- **Original OJ selector**: `None`
- **Original OJ text**: *(not present in original 2024 OJ; added by 2026/1744)*
- **Quoted in 2026/1744**: ‘(d) Articles 102 to 110 shall apply from 27 July 2026.’
- **Consolidated text**: (d) Articles 102 to 110 shall apply from 27 July 2026.

---

## 4. Discrepancies, Caveats & Unresolved Items

- **Observed textual discrepancies in Articles 6 and 113**: `0` (after the declared outer-quote boundary stripping on quoted amendment blocks and `<p class="modref">` exclusion on the temporary consolidated comparison copy).
- **No legal-applicability or review certification**: Matching text between Amending Regulation (EU) 2026/1744 and the pinned 2026-07-27 consolidated snapshot for Articles 6 and 113 confirms textual provenance for those two articles only; it does **not** establish current legal applicability, entry-into-force/application date conclusions, or completed legal review.
- **Unresolved items (ingestion remains closed)**:
  1. **Full amendment reconciliation**: Only Article 1 points (8) and (40) of Regulation (EU) 2026/1744 were checked in this stage; the remaining points of Article 1 (and Articles 2–4 / recitals of 2026/1744) have not yet been parsed or reconciled against the consolidated text.
  2. **Corrigendum verification**: Discovered corrigendum candidates in `source_register.json` (`32024R1689R(01)`, `32024R1689R(03)`, `32024R1689R(04)`, `32026R1744R(01)`) remain unverified.
  3. **Edition selection & review gates**: All canonical records remain `validation_status="pending"`, `review_status="not_reviewed"`, and `indexable=false`, and no active retrieval edition has been selected.
