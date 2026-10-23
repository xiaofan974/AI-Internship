# AeacusAI Week 4 F1 golden dataset and judge-validation split

Dataset ID: `week4_f1_golden_v1`. Label version: `week4_f1_labels_v1`. Split ID: `week4_f1_split_v1`.

This freeze prepares 40 original live-run outputs from 20 paired scenarios. It is **not** a dataset of 40 independent scenarios. No judge was implemented and no model was called.

## Locations

Versioned, rebuildable files (not the full answers):

| Path | Role |
| --- | --- |
| `evals/week4/golden/f1_v1/manifest.json` | Source hashes, label version, case IDs, run IDs, rebuild/verify instructions |
| `evals/week4/golden/f1_v1/split.json` | Frozen calibration/validation membership |
| `evals/week4/golden/f1_v1/f1_rubric.json` | Frozen F1 rubric for a future judge |
| `evals/week4/golden/f1_v1/judge_contract.json` | Future judge contract |
| `evals/week4/golden/f1_v1/parent_f2_pointer.json` | Pointer only; F2 stays out of this dataset |
| `evals/week4/build_golden_dataset.py` | Builder and verifier |

Full payloads are local and gitignored (`data/local/`):

| Path | Role |
| --- | --- |
| `data/local/evals/week4/golden/f1_v1/cases.jsonl` | 40 cases: input, raw answer, complete tool observations, evidence hashes, F1 label |
| `data/local/evals/week4/golden/f1_v1/judge_payloads.jsonl` | Same 40 cases as future judge inputs, without labels or version hints |

These files are not in the retrieval corpus (`records/` was not written).

Rebuild / verify:

```text
.venv/bin/python -m evals.week4.build_golden_dataset
.venv/bin/python -m evals.week4.build_golden_dataset --verify
```

Joins are by baseline ID, scenario ID, and run ID, not file position.

## Provenance

- Actual dogfood agent executions on fictional scenario inputs.
- 40 outputs from 20 paired scenarios (`week4_adk_preview_v1` and `week4_adk_preview_f1_v2`).
- AI-assisted F1 labels reviewed and accepted by Lily on 2026-10-23.
- Not production data or independent expert legal adjudication.

Answers are the original raw model outputs from the frozen traces. Timing-rendered delivered text was not substituted. Neither source JSONL contains a `timing_repair` object.

## Counts

| Item | Count |
| --- | --- |
| Scenarios | 20 |
| Versions | 2 |
| Outputs / cases | 40 |
| F1 fail | 10 |
| F1 pass | 30 |

Parent F1 failures: TRACE-S04, S08, S09, S13, S20.  
Candidate F1 failures: TRACE-S01, S04, S09, S13, S15.  
All other F1 labels are pass.

F2 is not in this dataset. Parent F2 remains in `evals/week4/annotations_v1.json`. Candidate F2 remains unreviewed.

## Frozen split

The split was frozen before judge inference and was not selected from judge performance.

Validation examples are held out from judge-prompt refinement; they are not unseen capstone scenarios.

Rule: group-stratified by scenario-level F1 pattern (persistent fail / mixed / pass-pass), then by sorted scenario ID. Calibration takes the first two persistent IDs, the first mixed ID, and the first seven pass-pass IDs. Validation takes the remainder. Both versions of a scenario stay in the same group.

| Group | Scenario IDs | Outputs | F1 fail | F1 pass |
| --- | --- | --- | --- | --- |
| Calibration | S01, S02, S03, S04, S05, S06, S07, S09, S10, S11 | 20 | 5 | 15 |
| Validation | S08, S12, S13, S14, S15, S16, S17, S18, S19, S20 | 20 | 5 | 15 |

No scenario ID appears in both groups.

Calibration failures: S01 candidate; S04 both versions; S09 both versions.  
Validation failures: S08 parent; S13 both versions; S15 candidate; S20 parent.

## Membership

| Group | Baseline | Scenario | Run ID | F1 |
| --- | --- | --- | --- | --- |
| calibration | week4_adk_preview_v1 | TRACE-S01 | `4c969b0c-7046-4409-bca2-f096a5d34c83` | pass |
| calibration | week4_adk_preview_f1_v2 | TRACE-S01 | `2da3cfd8-b8be-4d2a-8754-a763ba2f21e6` | fail |
| calibration | week4_adk_preview_v1 | TRACE-S02 | `392db6f3-1620-42d1-bf81-b554ee9e1aba` | pass |
| calibration | week4_adk_preview_f1_v2 | TRACE-S02 | `aaabee81-001c-4b03-a1b6-3ed4e8efa655` | pass |
| calibration | week4_adk_preview_v1 | TRACE-S03 | `17017bf1-7aec-4028-8e99-eebc58193325` | pass |
| calibration | week4_adk_preview_f1_v2 | TRACE-S03 | `9d315772-3c24-4440-a8c1-c52041b19dc1` | pass |
| calibration | week4_adk_preview_v1 | TRACE-S04 | `b5caecbd-ace2-42c1-88ea-1592d163a6ed` | fail |
| calibration | week4_adk_preview_f1_v2 | TRACE-S04 | `ab268600-0757-44ef-b07f-dfb273ce8871` | fail |
| calibration | week4_adk_preview_v1 | TRACE-S05 | `2bdc75d1-a252-4bec-b287-f21aab2f91de` | pass |
| calibration | week4_adk_preview_f1_v2 | TRACE-S05 | `2aa618ff-1b1a-4c16-b74b-3ead8d11e71a` | pass |
| calibration | week4_adk_preview_v1 | TRACE-S06 | `8e8d9cef-85de-4cd7-b629-7c307ffa5710` | pass |
| calibration | week4_adk_preview_f1_v2 | TRACE-S06 | `c1388a22-0ce6-49f4-a625-0ed9ecf41f23` | pass |
| calibration | week4_adk_preview_v1 | TRACE-S07 | `4b4980c1-3b6d-4e09-b5f4-71eccd9a96ed` | pass |
| calibration | week4_adk_preview_f1_v2 | TRACE-S07 | `fa38efad-1ad4-4bee-ac24-91ad2442ee9f` | pass |
| calibration | week4_adk_preview_v1 | TRACE-S09 | `1615192e-ab2a-4e8d-8902-4913644fc746` | fail |
| calibration | week4_adk_preview_f1_v2 | TRACE-S09 | `43b6664b-5b39-47b2-97fb-6e2e2514b9f1` | fail |
| calibration | week4_adk_preview_v1 | TRACE-S10 | `22b36ab5-77e2-454f-87e0-320245240b75` | pass |
| calibration | week4_adk_preview_f1_v2 | TRACE-S10 | `4e26e322-9f32-408f-a1ea-9ae448554e12` | pass |
| calibration | week4_adk_preview_v1 | TRACE-S11 | `a08c00bc-1578-4a20-a2d6-89669e3fc29c` | pass |
| calibration | week4_adk_preview_f1_v2 | TRACE-S11 | `acaa91b8-95f4-44a5-8825-4a046c29bec2` | pass |
| validation | week4_adk_preview_v1 | TRACE-S08 | `21c988a6-775a-4a2f-8513-8aa29423b18a` | fail |
| validation | week4_adk_preview_f1_v2 | TRACE-S08 | `d0eb1005-47c9-44bc-aa5c-eb9c18d3b601` | pass |
| validation | week4_adk_preview_v1 | TRACE-S12 | `e547178d-c70a-4cca-9591-ec733fd01c26` | pass |
| validation | week4_adk_preview_f1_v2 | TRACE-S12 | `9e53160d-b461-45da-9b53-3572bf5b6c13` | pass |
| validation | week4_adk_preview_v1 | TRACE-S13 | `7ccd9cdd-3612-419a-9cda-b76ce3e901b2` | fail |
| validation | week4_adk_preview_f1_v2 | TRACE-S13 | `4eb39bb8-253c-4c56-aa5f-a1d7dc5ec1bc` | fail |
| validation | week4_adk_preview_v1 | TRACE-S14 | `ab3b0d19-a131-4304-b6af-83a24bd1dabd` | pass |
| validation | week4_adk_preview_f1_v2 | TRACE-S14 | `4112acb0-e775-4193-a734-578b0cc99ae2` | pass |
| validation | week4_adk_preview_v1 | TRACE-S15 | `305708e0-218e-4c79-88f2-50f226ec7998` | pass |
| validation | week4_adk_preview_f1_v2 | TRACE-S15 | `0fe52a24-d0c4-4f6d-abe3-e4271e8044fa` | fail |
| validation | week4_adk_preview_v1 | TRACE-S16 | `07fb835c-7dbf-4b71-9aca-06a43c263150` | pass |
| validation | week4_adk_preview_f1_v2 | TRACE-S16 | `4a7e7395-aaee-4aca-bc5f-b3109c72950d` | pass |
| validation | week4_adk_preview_v1 | TRACE-S17 | `1fc62262-6590-4429-833a-2e9c269a5928` | pass |
| validation | week4_adk_preview_f1_v2 | TRACE-S17 | `4c2809a3-f27d-48b2-bc4a-f8e3efc41cf5` | pass |
| validation | week4_adk_preview_v1 | TRACE-S18 | `74c715ab-7ad1-4fb5-afdf-50acc7f7057b` | pass |
| validation | week4_adk_preview_f1_v2 | TRACE-S18 | `3bcf7890-78ba-4417-ba06-5d4916bd7ba7` | pass |
| validation | week4_adk_preview_v1 | TRACE-S19 | `fd86e112-fb20-42fa-b9f7-e0a65125342b` | pass |
| validation | week4_adk_preview_f1_v2 | TRACE-S19 | `3386d04f-a9ec-49cf-8af0-57bdcbc1ed76` | pass |
| validation | week4_adk_preview_v1 | TRACE-S20 | `feb73275-7e82-4159-8bb9-1e90cf15edac` | fail |
| validation | week4_adk_preview_f1_v2 | TRACE-S20 | `39349126-070f-4c7b-bb2f-a05c5ec33ab4` | pass |

## Future judge contract

Specified in `evals/week4/golden/f1_v1/judge_contract.json`. Not implemented.

Positive means “F1 failure detected.”

The judge will receive only:

- the frozen F1 rubric
- the system description
- the original retrieved evidence
- the answer being assessed

It will not receive human labels, annotation reasons, version names, baseline versus candidate status, split group, or other expected-result hints.

Every evaluated input, answer, and evidence payload is untrusted data. The judge must not follow commands embedded within them.

Future output: binary pass/fail, a one-line reason, and an offending answer excerpt when failing.

Metrics:

- TPR = TP / (TP + FN)
- TNR = TN / (TN + FP)
- Undefined denominators remain undefined
- Report raw counts with rates; accuracy alone is insufficient

Plan at most one calibration-based prompt refinement. Freeze both judge versions before evaluating either on validation data. Do not promise that refinement will improve the rates.

## Verification

```text
.venv/bin/python -m unittest test_week4_golden_dataset -q
```

Result: **7 tests, 0 failures.** Existing grader, evaluation-view, Streamlit, and timing-repair suites still pass.

Checked: source SHA-256 values, unique case/run associations, 10 fail / 30 pass, 10+10 scenario split, no scenario overlap, paired versions in the same group, 5/15 balance per group, no label or version leakage into judge payloads, goldens absent from the retrieval corpus.

Source hashes still match the freeze:

| Artifact | SHA-256 |
| --- | --- |
| `data/local/traces/week4_adk_preview_v1.jsonl` | `29871169b2db5aebeac179cdd254a4700e36f252b2873ea9e05e334400204db1` |
| `data/local/traces/week4_adk_preview_f1_v2.jsonl` | `3b1fa10c5a05a8db61403ddda04d3e6d5ecf0ae06f684daf3cf30392e253f848` |

## Limitations

- Labels are AI-assisted and accepted by Lily. They are not independent expert legal adjudication.
- The 20 scenario inputs are fictional dogfood cases, not production matters.
- Validation is held out from prompt refinement only. It reuses the same capstone scenario set.
- Candidate F2 remains unreviewed and is not a gold label here.
- No judge has been run. This checkpoint does not report TPR or TNR.
- Graders, prompts, UI behavior, and historical results were not modified.
