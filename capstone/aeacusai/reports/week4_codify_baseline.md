# AeacusAI Week 4 annotation freeze and deterministic baseline

This checkpoint freezes the approved failure taxonomy and scores the unchanged `week4_adk_preview_v1` traces. It does **not** change the agent, rerun scenarios, or claim a before/after improvement. Assertion failures are evaluation findings, not harness errors.

## Source verification

| Item | Value |
| --- | --- |
| Traces | `data/local/traces/week4_adk_preview_v1.jsonl` |
| Expected SHA-256 | `29871169b2db5aebeac179cdd254a4700e36f252b2873ea9e05e334400204db1` |
| Observed SHA-256 | `29871169b2db5aebeac179cdd254a4700e36f252b2873ea9e05e334400204db1` |
| Match | yes |
| Lines | 20 |
| Unattempted scenarios | none |
| Missing required fields | none |

The raw baseline and the frozen collection manifest were not modified. Original `human_annotation` fields remain empty.

## Provenance

- Review date: 2026-10-23
- Accepted by: Lily
- Method: AI-assisted observations and proposed labels reviewed and accepted by Lily in the conversation.
- Not: independent expert legal adjudication
- Acceptance time: not recorded

These are AI-assisted observations and proposed labels reviewed and accepted by Lily in the conversation. They are not independent expert legal adjudication.

## Frozen taxonomy

Separate files:

- `evals/week4/taxonomy_v1.json`
- `evals/week4/annotations_v1.json`

| ID | Title | Priority weight | Failures |
| --- | --- | --- | --- |
| F1 | Classification relies on an unstated premise or extends to an underspecified product. | 3 | 5 |
| F2 | Explanation broadens or invents a statutory condition or consequence. | 3 | 5 |
| F3 | Timing summary omits the specific sections whose application is deferred. | 2 | 2 |
| F4 | Searches continue after relevant child passages and complete context are available. | 1 | 1 |

Weights are prioritization weights, not answer-quality ratings. The first improvement target remains **F1**, which breaks its priority tie with F2.

Category failure counts: **5 / 5 / 2 / 1**. Distinct failing traces: **12**. Summed category frequencies (13) are not an overall failure count.

Overall pass requires all four category passes: **8** pass, **12** fail, out of 20.

Failing IDs:

- F1: TRACE-S04, TRACE-S08, TRACE-S09, TRACE-S13, TRACE-S20
- F2: TRACE-S05, TRACE-S11, TRACE-S12, TRACE-S16, TRACE-S18
- F3: TRACE-S02, TRACE-S20
- F4: TRACE-S19

## Human-reviewed results by trace

| Scenario | Run ID | F1 | F2 | F3 | F4 | Overall |
| --- | --- | --- | --- | --- | --- | --- |
| TRACE-S01 | `4c969b0c-7046-4409-bca2-f096a5d34c83` | pass | pass | pass | pass | pass |
| TRACE-S02 | `392db6f3-1620-42d1-bf81-b554ee9e1aba` | pass | pass | fail | pass | fail |
| TRACE-S03 | `17017bf1-7aec-4028-8e99-eebc58193325` | pass | pass | pass | pass | pass |
| TRACE-S04 | `b5caecbd-ace2-42c1-88ea-1592d163a6ed` | fail | pass | pass | pass | fail |
| TRACE-S05 | `2bdc75d1-a252-4bec-b287-f21aab2f91de` | pass | fail | pass | pass | fail |
| TRACE-S06 | `8e8d9cef-85de-4cd7-b629-7c307ffa5710` | pass | pass | pass | pass | pass |
| TRACE-S07 | `4b4980c1-3b6d-4e09-b5f4-71eccd9a96ed` | pass | pass | pass | pass | pass |
| TRACE-S08 | `21c988a6-775a-4a2f-8513-8aa29423b18a` | fail | pass | pass | pass | fail |
| TRACE-S09 | `1615192e-ab2a-4e8d-8902-4913644fc746` | fail | pass | pass | pass | fail |
| TRACE-S10 | `22b36ab5-77e2-454f-87e0-320245240b75` | pass | pass | pass | pass | pass |
| TRACE-S11 | `a08c00bc-1578-4a20-a2d6-89669e3fc29c` | pass | fail | pass | pass | fail |
| TRACE-S12 | `e547178d-c70a-4cca-9591-ec733fd01c26` | pass | fail | pass | pass | fail |
| TRACE-S13 | `7ccd9cdd-3612-419a-9cda-b76ce3e901b2` | fail | pass | pass | pass | fail |
| TRACE-S14 | `ab3b0d19-a131-4304-b6af-83a24bd1dabd` | pass | pass | pass | pass | pass |
| TRACE-S15 | `305708e0-218e-4c79-88f2-50f226ec7998` | pass | pass | pass | pass | pass |
| TRACE-S16 | `07fb835c-7dbf-4b71-9aca-06a43c263150` | pass | fail | pass | pass | fail |
| TRACE-S17 | `1fc62262-6590-4429-833a-2e9c269a5928` | pass | pass | pass | pass | pass |
| TRACE-S18 | `74c715ab-7ad1-4fb5-afdf-50acc7f7057b` | pass | fail | pass | pass | fail |
| TRACE-S19 | `fd86e112-fb20-42fa-b9f7-e0a65125342b` | pass | pass | pass | fail | fail |
| TRACE-S20 | `feb73275-7e82-4159-8bb9-1e90cf15edac` | fail | pass | fail | pass | fail |

## Deterministic assertions

Checker suite `week4_codify_v1`. Automated results are read from original `final_output` and `events` only. Human labels are not used to decide an automated result.

### A. Deferred-date qualifications

Inspects **Timing and scope**. When that section summarizes the December 2027 or August 2028 deferral, it requires Chapter III, Sections 1–3, and the Article 6(5) exception. Range and list variants are accepted. This checks explicit qualification markers, not complete semantic correctness.

| Item | Value |
| --- | --- |
| Applicable / denominator | 20 |
| Pass | 18 |
| Fail | 2 |
| Not applicable | 0 |
| Failures | TRACE-S02, TRACE-S20 |

### B. S19 retrieval budget

Applies only to TRACE-S19. Requires no more than two `preview_classification_search` **call** events. Response events and distinct query strings are not counted. Other scenarios are not applicable and are excluded from the denominator. This is a scenario-specific regression rule, not the agent’s 8-call limit.

| Item | Value |
| --- | --- |
| Applicable / denominator | 1 |
| Pass | 0 |
| Fail | 1 |
| Not applicable | 19 |
| Failures | TRACE-S19 |

## Per-trace assertion reasons

| Scenario | Deferred-date | S19 budget | Deferred-date reason | S19 budget reason |
| --- | --- | --- | --- | --- |
| TRACE-S01 | pass | not_applicable | Timing and scope names Chapter III, Sections 1–3, and the Article 6(5) exception when summarizing the deferral. | s19_retrieval_budget_v1 applies only to TRACE-S19. |
| TRACE-S02 | fail | not_applicable | Timing and scope summarizes a December 2027 or August 2028 deferral but omits explicit qualification marker(s): Chapter III, Sections 1–3. | s19_retrieval_budget_v1 applies only to TRACE-S19. |
| TRACE-S03 | pass | not_applicable | Timing and scope names Chapter III, Sections 1–3, and the Article 6(5) exception when summarizing the deferral. | s19_retrieval_budget_v1 applies only to TRACE-S19. |
| TRACE-S04 | pass | not_applicable | Timing and scope names Chapter III, Sections 1–3, and the Article 6(5) exception when summarizing the deferral. | s19_retrieval_budget_v1 applies only to TRACE-S19. |
| TRACE-S05 | pass | not_applicable | Timing and scope names Chapter III, Sections 1–3, and the Article 6(5) exception when summarizing the deferral. | s19_retrieval_budget_v1 applies only to TRACE-S19. |
| TRACE-S06 | pass | not_applicable | Timing and scope names Chapter III, Sections 1–3, and the Article 6(5) exception when summarizing the deferral. | s19_retrieval_budget_v1 applies only to TRACE-S19. |
| TRACE-S07 | pass | not_applicable | Timing and scope names Chapter III, Sections 1–3, and the Article 6(5) exception when summarizing the deferral. | s19_retrieval_budget_v1 applies only to TRACE-S19. |
| TRACE-S08 | pass | not_applicable | Timing and scope names Chapter III, Sections 1–3, and the Article 6(5) exception when summarizing the deferral. | s19_retrieval_budget_v1 applies only to TRACE-S19. |
| TRACE-S09 | pass | not_applicable | Timing and scope names Chapter III, Sections 1–3, and the Article 6(5) exception when summarizing the deferral. | s19_retrieval_budget_v1 applies only to TRACE-S19. |
| TRACE-S10 | pass | not_applicable | Timing and scope names Chapter III, Sections 1–3, and the Article 6(5) exception when summarizing the deferral. | s19_retrieval_budget_v1 applies only to TRACE-S19. |
| TRACE-S11 | pass | not_applicable | Timing and scope names Chapter III, Sections 1–3, and the Article 6(5) exception when summarizing the deferral. | s19_retrieval_budget_v1 applies only to TRACE-S19. |
| TRACE-S12 | pass | not_applicable | Timing and scope names Chapter III, Sections 1–3, and the Article 6(5) exception when summarizing the deferral. | s19_retrieval_budget_v1 applies only to TRACE-S19. |
| TRACE-S13 | pass | not_applicable | Timing and scope names Chapter III, Sections 1–3, and the Article 6(5) exception when summarizing the deferral. | s19_retrieval_budget_v1 applies only to TRACE-S19. |
| TRACE-S14 | pass | not_applicable | Timing and scope names Chapter III, Sections 1–3, and the Article 6(5) exception when summarizing the deferral. | s19_retrieval_budget_v1 applies only to TRACE-S19. |
| TRACE-S15 | pass | not_applicable | Timing and scope names Chapter III, Sections 1–3, and the Article 6(5) exception when summarizing the deferral. | s19_retrieval_budget_v1 applies only to TRACE-S19. |
| TRACE-S16 | pass | not_applicable | Timing and scope names Chapter III, Sections 1–3, and the Article 6(5) exception when summarizing the deferral. | s19_retrieval_budget_v1 applies only to TRACE-S19. |
| TRACE-S17 | pass | not_applicable | Timing and scope names Chapter III, Sections 1–3, and the Article 6(5) exception when summarizing the deferral. | s19_retrieval_budget_v1 applies only to TRACE-S19. |
| TRACE-S18 | pass | not_applicable | Timing and scope names Chapter III, Sections 1–3, and the Article 6(5) exception when summarizing the deferral. | s19_retrieval_budget_v1 applies only to TRACE-S19. |
| TRACE-S19 | pass | fail | Timing and scope names Chapter III, Sections 1–3, and the Article 6(5) exception when summarizing the deferral. | TRACE-S19 made 6 preview_classification_search call events; at most 2 are allowed. |
| TRACE-S20 | fail | not_applicable | Timing and scope summarizes a December 2027 or August 2028 deferral but omits explicit qualification marker(s): Chapter III, Sections 1–3. | s19_retrieval_budget_v1 applies only to TRACE-S19. |

## Disagreements with reviewed labels

Compared only where an assertion overlaps a reviewed category (A with F3, B with F4).

None. On this baseline, deferred-date failures are TRACE-S02 and TRACE-S20, matching reviewed F3. Both of those Timing and scope sections mention a December 2027 deferral and an Article 6(5) exception, but they do not name Chapter III or Sections 1–3. The S19 retrieval-budget failure is TRACE-S19 with six search call events, matching reviewed F4. F1 and F2 have no automated counterpart, so they are not treated as assertion disagreements.

## Configuration and version hashes

| Artifact | SHA-256 |
| --- | --- |
| Source traces | `29871169b2db5aebeac179cdd254a4700e36f252b2873ea9e05e334400204db1` |
| Taxonomy | `336f5f3e6fe9ab7042b83bf1869161be1e86aaee4c718d9e9b0738f7808d7718` |
| Annotations | `50bde98943fc656a598e2e449bf6cfaec73387cb04d3f05adadf4a3c90f489ee` |
| Checker config | `4423834db6d0360ecdfe426c29df0686780b89dcbcbd00a4a8c8ef2ef59519cc` |
| `evals/week4/checkers.py` | `330fce7b22fc3d7ff140839dcc20dd811ee6ffef3da00111134674508a484b33` |
| `evals/week4/codify.py` | `4a7ea41d17a576b39d85c002fd505d93777d5051e77b92710401dcadb849ee05` |
| Scenarios | `02aeb6ae8c7af29864d493c08621ba048c73680e89cd34e466ebe46cd86b2070` |
| Collection manifest | `fdd0e4d96b314a4c3e37aea1d7d00b9f67ee3a86337e3000c43b2c35727643e3` |

Evaluated at `2026-10-22T21:30:33.657632+00:00`. Result ID `week4_codify_baseline_v1`.

## Limitations

- Deferred-date checking looks for explicit qualification markers in Timing and scope. It does not prove complete semantic correctness.
- The S19 rule counts call events only. It does not itself prove that relevant child passages and complete context were already available.
- F1 and F2 are reviewed labels only in this checkpoint.
- Reviewed labels are not independent expert legal adjudication.
- Original JSONL `human_annotation` fields were not populated.
- This checkpoint contains baseline results only.

Machine-readable results: `evals/week4/results/week4_codify_baseline_v1.json`.
