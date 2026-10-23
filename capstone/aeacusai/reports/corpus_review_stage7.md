# AeacusAI — Stage 7 Corpus Review Pack

- **Selection status**: `pending_review`
- **Ingestion permitted**: `false`
- **Active retrieval edition**: `null` (not yet designated)
- **All selected records**: `validation_status="pending"`, `review_status="not_reviewed"`, `indexable=false`

---

## 1. Selected Corpus Inventory & Edition Separation

This review pack is built strictly from the explicit 6-file Stage 7 allowlist (`493` total parent records). The 45-record v0.2 sample baseline (`records/review_records.json`) and the superseded Stage 6 v1 Charter output (`records/charter_articles_stage6.json`) are excluded.

### Edition Separation Policy

1. **Original 2024 Official Journal AI Act (`T1-AIA-OJ-2024`) — `306` records**:
   - Snapshot ID: `T1-AIA-OJ-2024@sha256:8f0b656302f9864cc87e040c371f209a9d65ae1a6cecc25ca5eb737e872d721a`
   - `records/original_articles_stage1.json`: `113` complete article parents (`article/1`–`article/113`)
   - `records/original_recitals_stage2.json`: `180` complete interpretive recitals (`recital/1`–`recital/180`)
   - `records/original_annexes_stage3.json`: `13` complete annex parents (`annex/I`–`annex/XIII`)
2. **Pinned Consolidated AI Act dated 2026-07-27 (`T1-AIA-CONS-20260727`) — `133` records**:
   - Snapshot ID: `T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715`
   - `records/consolidated_articles_stage4.json`: `119` complete article parents (`article/1`–`article/113` plus `article/4a`, `article/60a`, `article/75a`, `article/75b`, `article/75c`, `article/75d`)
   - `records/consolidated_annexes_stage5.json`: `14` complete annex parents (`annex/I`–`annex/XIV`)
   - Note: Consolidated texts produced by the Publications Office are documentation/reading tools and not independently authentic Official Journal legislation, nor is this snapshot claimed to be current applicable law. Original and consolidated editions remain strictly separated and no active retrieval edition is designated yet.
3. **Charter of Fundamental Rights of the European Union (`T1-CHARTER-OJ-2012`) — `54` records**:
   - Snapshot ID: `T1-CHARTER-OJ-2012@sha256:3457b2dde9d11ac25bdea22e015556e6e499f01f5821f47d2ad10f11a56af685`
   - `records/charter_articles_stage6_v2.json`: `54` complete article parents (`article/1`–`article/54`, parser revision `charter-articles-stage6-v2` superseding `records/charter_articles_stage6.json` after correcting Article 54's end boundary).

---

## 2. Complete Untruncated Review Passages from Selected Records

All passages below are copied verbatim from the selected Stage 4, Stage 5, and Stage 6 v2 JSON records (`legal-whitespace-v1` normalization only, no truncation or summarization).

### Consolidated Article 6

- **Record ID**: `T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/6`
- **Source Snapshot ID**: `T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715`
- **Label**: `Article 6 — Classification rules for high-risk AI systems`
- **Unit Kind / Legal Function**: `article` / `operative`
- **Locator Path**: `article/6`
- **DOM Selector**: `/*/*[2]/*[9]/*[4]/*[4]/*[3]/*[3]`
- **Character Count**: `4848`
- **Text SHA-256**: `b6a58d42b6248038baaf14c5918103289bc0af1aed90da5d974b7ef846a5b5ee`
- **Status**: `validation_status=pending`, `review_status=not_reviewed`, `indexable=False`

Article 6 Classification rules for high-risk AI systems 1. Irrespective of whether an AI system is placed on the market or put into service independently of the products referred to in points (a) and (b), that AI system shall be considered to be high-risk where both of the following conditions are fulfilled: (a) the AI system is intended to be used as a safety component of a product, or the AI system is itself a product, covered by the Union harmonisation legislation listed in Annex I; (b) the product whose safety component pursuant to point (a) is the AI system, or the AI system itself as a product, is required to undergo a third-party conformity assessment, with a view to the placing on the market or the putting into service of that product pursuant to the Union harmonisation legislation listed in Annex I. ▼M1 1a. For the purposes of this Regulation, including paragraph 1 of this Article, AI systems that are solely used for non-safety related aspects of user assistance, performance optimisation, service efficiency, automation or convenience or quality control shall not qualify as safety components. 1b. Notwithstanding paragraph 1a, AI systems the failure or malfunctioning of which would endanger health and safety shall qualify as safety components. 1c. A product that is required to undergo a third-party conformity assessment solely due to risks other than risks to health and safety, in particular risks relating to the distribution of radio spectrum or electromagnetic interference that do not affect health and safety, shall not be considered as fulfilling the condition in paragraph 1, point (b). ▼B 2. In addition to the high-risk AI systems referred to in paragraph 1, AI systems referred to in Annex III shall be considered to be high-risk. 3. By derogation from paragraph 2, an AI system referred to in Annex III shall not be considered to be high-risk where it does not pose a significant risk of harm to the health, safety or fundamental rights of natural persons, including by not materially influencing the outcome of decision making. The first subparagraph shall apply where any of the following conditions is fulfilled: (a) the AI system is intended to perform a narrow procedural task; (b) the AI system is intended to improve the result of a previously completed human activity; (c) the AI system is intended to detect decision-making patterns or deviations from prior decision-making patterns and is not meant to replace or influence the previously completed human assessment, without proper human review; or (d) the AI system is intended to perform a preparatory task to an assessment relevant for the purposes of the use cases listed in Annex III. Notwithstanding the first subparagraph, an AI system referred to in Annex III shall always be considered to be high-risk where the AI system performs profiling of natural persons. 4. A provider who considers that an AI system referred to in Annex III is not high-risk shall document its assessment before that system is placed on the market or put into service. Such provider shall be subject to the registration obligation set out in Article 49(2). Upon request of national competent authorities, the provider shall provide the documentation of the assessment. 5. The Commission shall, after consulting the European Artificial Intelligence Board (the ‘Board’), and no later than 2 February 2026, provide guidelines specifying the practical implementation of this Article in line with Article 96 together with a comprehensive list of practical examples of use cases of AI systems that are high-risk and not high-risk. 6. The Commission is empowered to adopt delegated acts in accordance with Article 97 in order to amend paragraph 3, second subparagraph, of this Article by adding new conditions to those laid down therein, or by modifying them, where there is concrete and reliable evidence of the existence of AI systems that fall under the scope of Annex III, but do not pose a significant risk of harm to the health, safety or fundamental rights of natural persons. 7. The Commission shall adopt delegated acts in accordance with Article 97 in order to amend paragraph 3, second subparagraph, of this Article by deleting any of the conditions laid down therein, where there is concrete and reliable evidence that this is necessary to maintain the level of protection of health, safety and fundamental rights provided for by this Regulation. 8. Any amendment to the conditions laid down in paragraph 3, second subparagraph, adopted in accordance with paragraphs 6 and 7 of this Article shall not decrease the overall level of protection of health, safety and fundamental rights provided for by this Regulation and shall ensure consistency with the delegated acts adopted pursuant to Article 7(1), and take account of market and technological developments.

### Consolidated Annex III

- **Record ID**: `T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::annex/III`
- **Source Snapshot ID**: `T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715`
- **Label**: `Annex III — High-risk AI systems referred to in Article 6(2)`
- **Unit Kind / Legal Function**: `annex` / `operative`
- **Locator Path**: `annex/III`
- **DOM Selector**: `/*/*[2]/*[9]/*[8]`
- **Character Count**: `7350`
- **Text SHA-256**: `533e5a42fcfe7f472c346374f5139b4152aa59a15bbc02068a33cdb751609fdf`
- **Status**: `validation_status=pending`, `review_status=not_reviewed`, `indexable=False`

ANNEX III High-risk AI systems referred to in Article 6(2) High-risk AI systems pursuant to Article 6(2) are the AI systems listed in any of the following areas: 1. Biometrics, in so far as their use is permitted under relevant Union or national law: (a) remote biometric identification systems. This shall not include AI systems intended to be used for biometric verification the sole purpose of which is to confirm that a specific natural person is the person he or she claims to be; (b) AI systems intended to be used for biometric categorisation, according to sensitive or protected attributes or characteristics based on the inference of those attributes or characteristics; (c) AI systems intended to be used for emotion recognition. 2. Critical infrastructure: AI systems intended to be used as safety components in the management and operation of critical digital infrastructure, road traffic, or in the supply of water, gas, heating or electricity. 3. Education and vocational training: (a) AI systems intended to be used to determine access or admission or to assign natural persons to educational and vocational training institutions at all levels; (b) AI systems intended to be used to evaluate learning outcomes, including when those outcomes are used to steer the learning process of natural persons in educational and vocational training institutions at all levels; (c) AI systems intended to be used for the purpose of assessing the appropriate level of education that an individual will receive or will be able to access, in the context of or within educational and vocational training institutions at all levels; (d) AI systems intended to be used for monitoring and detecting prohibited behaviour of students during tests in the context of or within educational and vocational training institutions at all levels. 4. Employment, workers’ management and access to self-employment: (a) AI systems intended to be used for the recruitment or selection of natural persons, in particular to place targeted job advertisements, to analyse and filter job applications, and to evaluate candidates; (b) AI systems intended to be used to make decisions affecting terms of work-related relationships, the promotion or termination of work-related contractual relationships, to allocate tasks based on individual behaviour or personal traits or characteristics or to monitor and evaluate the performance and behaviour of persons in such relationships. 5. Access to and enjoyment of essential private services and essential public services and benefits: (a) AI systems intended to be used by public authorities or on behalf of public authorities to evaluate the eligibility of natural persons for essential public assistance benefits and services, including healthcare services, as well as to grant, reduce, revoke, or reclaim such benefits and services; (b) AI systems intended to be used to evaluate the creditworthiness of natural persons or establish their credit score, with the exception of AI systems used for the purpose of detecting financial fraud; (c) AI systems intended to be used for risk assessment and pricing in relation to natural persons in the case of life and health insurance; (d) AI systems intended to evaluate and classify emergency calls by natural persons or to be used to dispatch, or to establish priority in the dispatching of, emergency first response services, including by police, firefighters and medical aid, as well as of emergency healthcare patient triage systems. 6. Law enforcement, in so far as their use is permitted under relevant Union or national law: (a) AI systems intended to be used by or on behalf of law enforcement authorities, or by Union institutions, bodies, offices or agencies in support of law enforcement authorities or on their behalf to assess the risk of a natural person becoming the victim of criminal offences; (b) AI systems intended to be used by or on behalf of law enforcement authorities or by Union institutions, bodies, offices or agencies in support of law enforcement authorities as polygraphs or similar tools; (c) AI systems intended to be used by or on behalf of law enforcement authorities, or by Union institutions, bodies, offices or agencies, in support of law enforcement authorities to evaluate the reliability of evidence in the course of the investigation or prosecution of criminal offences; (d) AI systems intended to be used by law enforcement authorities or on their behalf or by Union institutions, bodies, offices or agencies in support of law enforcement authorities for assessing the risk of a natural person offending or re-offending not solely on the basis of the profiling of natural persons as referred to in Article 3(4) of Directive (EU) 2016/680, or to assess personality traits and characteristics or past criminal behaviour of natural persons or groups; (e) AI systems intended to be used by or on behalf of law enforcement authorities or by Union institutions, bodies, offices or agencies in support of law enforcement authorities for the profiling of natural persons as referred to in Article 3(4) of Directive (EU) 2016/680 in the course of the detection, investigation or prosecution of criminal offences. 7. Migration, asylum and border control management, in so far as their use is permitted under relevant Union or national law: (a) AI systems intended to be used by or on behalf of competent public authorities or by Union institutions, bodies, offices or agencies as polygraphs or similar tools; (b) AI systems intended to be used by or on behalf of competent public authorities or by Union institutions, bodies, offices or agencies to assess a risk, including a security risk, a risk of irregular migration, or a health risk, posed by a natural person who intends to enter or who has entered into the territory of a Member State; (c) AI systems intended to be used by or on behalf of competent public authorities or by Union institutions, bodies, offices or agencies to assist competent public authorities for the examination of applications for asylum, visa or residence permits and for associated complaints with regard to the eligibility of the natural persons applying for a status, including related assessments of the reliability of evidence; (d) AI systems intended to be used by or on behalf of competent public authorities, or by Union institutions, bodies, offices or agencies, in the context of migration, asylum or border control management, for the purpose of detecting, recognising or identifying natural persons, with the exception of the verification of travel documents. 8. Administration of justice and democratic processes: (a) AI systems intended to be used by a judicial authority or on their behalf to assist a judicial authority in researching and interpreting facts and the law and in applying the law to a concrete set of facts, or to be used in a similar way in alternative dispute resolution; (b) AI systems intended to be used for influencing the outcome of an election or referendum or the voting behaviour of natural persons in the exercise of their vote in elections or referenda. This does not include AI systems to the output of which natural persons are not directly exposed, such as tools used to organise, optimise or structure political campaigns from an administrative or logistical point of view.

### Consolidated Article 113

- **Record ID**: `T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/113`
- **Source Snapshot ID**: `T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715`
- **Label**: `Article 113 — Entry into force and application`
- **Unit Kind / Legal Function**: `article` / `operative`
- **Locator Path**: `article/113`
- **DOM Selector**: `/*/*[2]/*[9]/*[4]/*[14]/*[14]`
- **Character Count**: `957`
- **Text SHA-256**: `0f628e97ddb44755c40162f14950a4bc8072552fda2a3c38773c5a7f30c8bd4d`
- **Status**: `validation_status=pending`, `review_status=not_reviewed`, `indexable=False`

Article 113 Entry into force and application This Regulation shall enter into force on the twentieth day following that of its publication in the Official Journal of the European Union. It shall apply from 2 August 2026. However: ▼M1 (a) Chapters I and II shall apply from 2 February 2025, with the exception of Article 5(1), first subparagraph, points (ba) and (bb), and Article 5(1a) and (1b) which shall apply from 2 December 2026; ▼B (b) Chapter III Section 4, Chapter V, Chapter VII and Chapter XII and Article 78 shall apply from 2 August 2025, with the exception of Article 101; ▼M1 (c) Chapter III, Sections 1, 2, and 3, with the exception of Article 6(5), shall apply from: (i) 2 December 2027 as regards AI systems classified as high-risk pursuant to Article 6(2) and Annex III; and (ii) 2 August 2028 as regards AI systems classified as high-risk pursuant to Article 6(1) and Annex I; ▼M1 (d) Articles 102 to 110 shall apply from 27 July 2026. ▼B

### Charter Article 51

- **Record ID**: `T1-CHARTER-OJ-2012@sha256:3457b2dde9d11ac25bdea22e015556e6e499f01f5821f47d2ad10f11a56af685::article/51`
- **Source Snapshot ID**: `T1-CHARTER-OJ-2012@sha256:3457b2dde9d11ac25bdea22e015556e6e499f01f5821f47d2ad10f11a56af685`
- **Label**: `Charter Article 51`
- **Unit Kind / Legal Function**: `article` / `operative`
- **Locator Path**: `article/51`
- **DOM Selector**: `/*/*[2]/*[14]/*[216] | /*/*[2]/*[14]/*[217] | /*/*[2]/*[14]/*[218] | /*/*[2]/*[14]/*[219]`
- **Character Count**: `697`
- **Text SHA-256**: `45f2c3c2e489cc831de5ba38ee0a174f82324ff980f727a775a1b6c1ed38f1bd`
- **Status**: `validation_status=pending`, `review_status=not_reviewed`, `indexable=False`

Article 51 Field of application 1. The provisions of this Charter are addressed to the institutions, bodies, offices and agencies of the Union with due regard for the principle of subsidiarity and to the Member States only when they are implementing Union law. They shall therefore respect the rights, observe the principles and promote the application thereof in accordance with their respective powers and respecting the limits of the powers of the Union as conferred on it in the Treaties. 2. The Charter does not extend the field of application of Union law beyond the powers of the Union or establish any new power or task for the Union, or modify powers and tasks as defined in the Treaties.

### Charter Article 52

- **Record ID**: `T1-CHARTER-OJ-2012@sha256:3457b2dde9d11ac25bdea22e015556e6e499f01f5821f47d2ad10f11a56af685::article/52`
- **Source Snapshot ID**: `T1-CHARTER-OJ-2012@sha256:3457b2dde9d11ac25bdea22e015556e6e499f01f5821f47d2ad10f11a56af685`
- **Label**: `Charter Article 52`
- **Unit Kind / Legal Function**: `article` / `operative`
- **Locator Path**: `article/52`
- **DOM Selector**: `/*/*[2]/*[14]/*[220] | /*/*[2]/*[14]/*[221] | /*/*[2]/*[14]/*[222] | /*/*[2]/*[14]/*[223] | /*/*[2]/*[14]/*[224] | /*/*[2]/*[14]/*[225] | /*/*[2]/*[14]/*[226] | /*/*[2]/*[14]/*[227] | /*/*[2]/*[14]/*[228]`
- **Character Count**: `1846`
- **Text SHA-256**: `766f4e2727ad89ace1faf80a4afe0abac3865db26f9b37e495947b22ffa1545b`
- **Status**: `validation_status=pending`, `review_status=not_reviewed`, `indexable=False`

Article 52 Scope and interpretation of rights and principles 1. Any limitation on the exercise of the rights and freedoms recognised by this Charter must be provided for by law and respect the essence of those rights and freedoms. Subject to the principle of proportionality, limitations may be made only if they are necessary and genuinely meet objectives of general interest recognised by the Union or the need to protect the rights and freedoms of others. 2. Rights recognised by this Charter for which provision is made in the Treaties shall be exercised under the conditions and within the limits defined by those Treaties. 3. In so far as this Charter contains rights which correspond to rights guaranteed by the Convention for the Protection of Human Rights and Fundamental Freedoms, the meaning and scope of those rights shall be the same as those laid down by the said Convention. This provision shall not prevent Union law providing more extensive protection. 4. In so far as this Charter recognises fundamental rights as they result from the constitutional traditions common to the Member States, those rights shall be interpreted in harmony with those traditions. 5. The provisions of this Charter which contain principles may be implemented by legislative and executive acts taken by institutions, bodies, offices and agencies of the Union, and by acts of Member States when they are implementing Union law, in the exercise of their respective powers. They shall be judicially cognisable only in the interpretation of such acts and in the ruling on their legality. 6. Full account shall be taken of national laws and practices as specified in this Charter. 7. The explanations drawn up as a way of providing guidance in the interpretation of this Charter shall be given due regard by the courts of the Union and of the Member States.

### Charter Article 54 (corrected v2 boundary)

- **Record ID**: `T1-CHARTER-OJ-2012@sha256:3457b2dde9d11ac25bdea22e015556e6e499f01f5821f47d2ad10f11a56af685::article/54`
- **Source Snapshot ID**: `T1-CHARTER-OJ-2012@sha256:3457b2dde9d11ac25bdea22e015556e6e499f01f5821f47d2ad10f11a56af685`
- **Label**: `Charter Article 54`
- **Unit Kind / Legal Function**: `article` / `operative`
- **Locator Path**: `article/54`
- **DOM Selector**: `/*/*[2]/*[14]/*[232] | /*/*[2]/*[14]/*[233] | /*/*[2]/*[14]/*[234]`
- **Character Count**: `314`
- **Text SHA-256**: `ce552ea083a96962e6722f57b5e35d7011d0ff755bae68783cace3e096612a5c`
- **Status**: `validation_status=pending`, `review_status=not_reviewed`, `indexable=False`

Article 54 Prohibition of abuse of rights Nothing in this Charter shall be interpreted as implying any right to engage in any activity or to perform any act aimed at the destruction of any of the rights and freedoms recognised in this Charter or at their limitation to a greater extent than is provided for herein.

---

## 3. Remaining Limitations & Open Gates Before Ingestion

1. **Paragraph & Subpoint Child Decomposition**:
   - Stages 1–6 v2 extract complete parent records only (`article`, `recital`, `annex` with `children=[]`). Numbered paragraphs (including multi-block paragraphs such as consolidated `Article 6(3)` and inserted paragraphs `6(1a)`–`6(1c)`), Article 3 definitions, and numbered/lettered annex points are not yet decomposed into child records.
2. **Table Row/Column Semantics**:
   - While all table-cell text is preserved in source order within the parent `annex` and `article` records (including the 201 1-row list layout tables in OJ Annexes `I`–`XIII`, the 7 subpoint layout tables in Charter Articles `3` and `41`, and the 6 multi-row AIA code tables in Consolidated `Annex XIV`), flattened whitespace-normalized text does not preserve row/column relational structure.
3. **Cross-Reference Resolution**:
   - Every record currently carries `cross_references: []`. Internal cross-references (e.g., `Article 6` to `Annex I`, `Annex III`, `Article 49(2)`, `Article 96`, `Article 97`), cross-instrument references, and recital-to-article links remain explicitly pending.
4. **Footnote & Editorial Marker Handling**:
   - Footnote references and `p.oj-note` / `p.footnote` bodies are not yet expanded or linked. In the consolidated edition (`T1-AIA-CONS-20260727`), inline/block editorial revision markers (`▼M1`, `▼B`, `▼M1 —————`, `►M1`, `◄`) inside article and annex containers remain in-place in the normalized text (`Article 6`, `Article 113`, `Annex I`, `Annex VIII`, etc.).
5. **Amending Act (`T1-AIA-AMEND-2026-1744`) & Corrigendum Verification**:
   - Amending Regulation (EU) 2026/1744 (`T1-AIA-AMEND-2026-1744@sha256:9d754652b867722807e4219c85912ce354233e58a1b4eb8c7752b4d1922993db`, `data/raw/ai-act-amendment-2026-1744-en.xhtml`) has been acquired and checksum-verified, but **has not yet been fully parsed into canonical records or reconciled provision-by-provision with the pinned consolidated text (`T1-AIA-CONS-20260727`)**.
   - Discovered corrigendum candidates in `source_register.json` (`32024R1689R(01)`, `32024R1689R(03)`, `32024R1689R(04)`, `32026R1744R(01)`) and temporal applicability / entry-into-force rules (such as the staggered dates in consolidated `Article 113`) have not yet been audited.
6. **Human Content Review & Edition Selection**:
   - All `493` selected records remain `validation_status="pending"`, `review_status="not_reviewed"`, and `indexable=false`. No active retrieval edition has been selected, and ingestion into Pinecone remains closed.
