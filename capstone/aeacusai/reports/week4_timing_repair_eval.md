# AeacusAI Week 4 timing-repair evaluation

This checkpoint freezes the reviewed F1 comparison for the unsuccessful instruction-only experiment, restores the parent primary-preview instruction, and evaluates one application-owned Timing and scope renderer on the primary ADK path.

It is **not** 20 new live runs, a model-quality improvement, an F1 resolution, or an overall quality pass rate. Source review and ingestion gates stay closed.

Replay label, used exactly:

**Application-layer replay of 20 saved live traces.**

## Accepted F1 comparison

Separate candidate annotations live in `evals/week4/annotations_f1_v2.json`. They cover **F1 only**. Candidate F2 labels were not assigned. Parent F2 labels were not copied. No overall quality pass rate is reported.

Review: AI-assisted observations and proposed labels, accepted by Lily on 2026-10-23. Not independent expert legal adjudication.

Labels are joined to the actual `week4_adk_preview_f1_v2` run IDs.

| Scenario | Candidate run ID | F1 |
| --- | --- | --- |
| TRACE-S01 | `2da3cfd8-b8be-4d2a-8754-a763ba2f21e6` | fail |
| TRACE-S02 | `aaabee81-001c-4b03-a1b6-3ed4e8efa655` | pass |
| TRACE-S03 | `9d315772-3c24-4440-a8c1-c52041b19dc1` | pass |
| TRACE-S04 | `ab268600-0757-44ef-b07f-dfb273ce8871` | fail |
| TRACE-S05 | `2aa618ff-1b1a-4c16-b74b-3ead8d11e71a` | pass |
| TRACE-S06 | `c1388a22-0ce6-49f4-a625-0ed9ecf41f23` | pass |
| TRACE-S07 | `fa38efad-1ad4-4bee-ac24-91ad2442ee9f` | pass |
| TRACE-S08 | `d0eb1005-47c9-44bc-aa5c-eb9c18d3b601` | pass |
| TRACE-S09 | `43b6664b-5b39-47b2-97fb-6e2e2514b9f1` | fail |
| TRACE-S10 | `4e26e322-9f32-408f-a1ea-9ae448554e12` | pass |
| TRACE-S11 | `acaa91b8-95f4-44a5-8825-4a046c29bec2` | pass |
| TRACE-S12 | `9e53160d-b461-45da-9b53-3572bf5b6c13` | pass |
| TRACE-S13 | `4eb39bb8-253c-4c56-aa5f-a1d7dc5ec1bc` | fail |
| TRACE-S14 | `4112acb0-e775-4193-a734-578b0cc99ae2` | pass |
| TRACE-S15 | `0fe52a24-d0c4-4f6d-abe3-e4271e8044fa` | fail |
| TRACE-S16 | `4a7e7395-aaee-4aca-bc5f-b3109c72950d` | pass |
| TRACE-S17 | `4c2809a3-f27d-48b2-bc4a-f8e3efc41cf5` | pass |
| TRACE-S18 | `3bcf7890-78ba-4417-ba06-5d4916bd7ba7` | pass |
| TRACE-S19 | `3386d04f-a9ec-49cf-8af0-57bdcbc1ed76` | pass |
| TRACE-S20 | `39349126-070f-4c7b-bb2f-a05c5ec33ab4` | pass |

Experiment outcome: **unsuccessful**.

| Comparison | IDs |
| --- | --- |
| Parent F1 failures | TRACE-S04, TRACE-S08, TRACE-S09, TRACE-S13, TRACE-S20 |
| Candidate F1 failures | TRACE-S01, TRACE-S04, TRACE-S09, TRACE-S13, TRACE-S15 |
| Recoveries | TRACE-S08, TRACE-S20 |
| Regressions | TRACE-S01, TRACE-S15 |
| Persistent failures | TRACE-S04, TRACE-S09, TRACE-S13 |

Two F1 recoveries, two regressions, three persistent failures. **5/20 F1 failures in both versions.** These counts are not an overall quality pass rate. **F1 remains unresolved.**

Both original trace files, manifests, checkers, scenarios, and existing results were left in place.

| Artifact | SHA-256 |
| --- | --- |
| `data/local/traces/week4_adk_preview_v1.jsonl` | `29871169b2db5aebeac179cdd254a4700e36f252b2873ea9e05e334400204db1` |
| `data/local/traces/week4_adk_preview_f1_v2.jsonl` | `3b1fa10c5a05a8db61403ddda04d3e6d5ecf0ae06f684daf3cf30392e253f848` |
| `evals/week4/baselines/week4_adk_preview_v1/manifest.json` | `fdd0e4d96b314a4c3e37aea1d7d00b9f67ee3a86337e3000c43b2c35727643e3` |
| `evals/week4/baselines/week4_adk_preview_f1_v2/manifest.json` | `c1a5aaf95b84662f2461f5fb5fedc65acac611bd68a657de89caa20e3b13d97f` |
| `evals/week4/checkers.py` | `330fce7b22fc3d7ff140839dcc20dd811ee6ffef3da00111134674508a484b33` |
| `evals/week4/scenarios_v1.json` | `02aeb6ae8c7af29864d493c08621ba048c73680e89cd34e466ebe46cd86b2070` |
| `evals/week4/annotations_v1.json` | `50bde98943fc656a598e2e449bf6cfaec73387cb04d3f05adadf4a3c90f489ee` |
| `evals/week4/annotations_f1_v2.json` | `c382664896c8b909654dd1628fcb1a61fd1ce75b6be35cf3cd5484e4970a819a` |

## Instruction restore

Only the primary preview instruction text was restored. Whole files were not restored from Git. Unrelated work was not discarded.

| Item | SHA-256 |
| --- | --- |
| Expected parent `AEACUS_PREVIEW_INSTRUCTION` | `6d28bfa7d6d42c8ce1c21211b1e87adf877137ed878b1082c0ec6f36716a7de7` |
| Observed after restore | `6d28bfa7d6d42c8ce1c21211b1e87adf877137ed878b1082c0ec6f36716a7de7` |
| Match | yes |

The candidate instruction hash `20f72d6ea00bb6a052266a9abc79066d93119f321a56a3cea446f556cda9517e` remains recorded with the frozen F1 candidate. It is no longer the live agent instruction.

## Exact repair and provenance

Formatter: `aeacus.timing_scope.v1`, version `1`, in `aeacus_agent/timing_scope.py`.

Integrated into the real primary preview path:

- Streamlit: `finalize_preview_result` replaces Timing and scope before citation presentation. `raw_answer` stays the model text. `displayed_answer` / pending-review `assessment` bind to the delivered text.
- CLI: `run_classification_preview` applies the same formatter after `run_review` and stores `timing_repair` plus `final_output` as delivered.

Model generation, retrieval, tools, and approval requirements are unchanged. MCP, SequentialAgent dual preview, and LangGraph were not modified.

The renderer:

- Drops the model-authored Timing and scope section. It does not append a correction after the original paragraph.
- Verifies the pinned snapshot `T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715`.
- Verifies Article 113 record `…::article/113` and source-text SHA-256 `0f628e97ddb44755c40162f14950a4bc8072552fda2a3c38773c5a7f30c8bd4d`.
- Quotes unique source excerpts: general application from 2 August 2026, and Chapter III Sections 1, 2, and 3 except Article 6(5), distinguishing 2 December 2027 (Article 6(2) / Annex III) from 2 August 2028 (Article 6(1) / Annex I).
- Keeps the provisional classification-subset scope explicit.
- Fails closed on missing evidence, hash mismatch, wrong edition, inconsistent observations, or ambiguous section boundaries. Fail text states that no statutory application dates are given. There is no hardcoded statutory fallback.
- Records raw output, delivered output, formatter id/version, source record ID, and source hash. Hidden thoughts are not stored.

Pending human-review artifacts bind to the exact delivered assessment.

## Offline verification

```text
.venv/bin/python -m unittest test_timing_scope test_preview_presentation \
  test_streamlit_app test_trace_store test_week4_codify test_week4_baseline \
  test_review_register test_prompt_injection test_context_preview -q
```

Result: **78 tests, 0 failures.**

Tests cover valid rendering; missing, tampered, and wrong-edition evidence; source-hash mismatch; ambiguous heading and later-heading boundaries; raw-answer preservation; and pending-review binding to the delivered assessment.

## Application-layer replay of 20 saved live traces

Source: frozen `week4_adk_preview_v1.jsonl`, SHA-256 `29871169…04db1`. Saved observations only. No retrieval. No model calls.

| Check | Result |
| --- | --- |
| Traces replayed | 20 |
| Formatter status | 20 ok, 0 failed |
| Prefix outside Timing and scope unchanged | 20/20 |
| Prefix mismatches | none |

### Unchanged-check before / after

Checker file SHA-256 unchanged: `330fce7b22fc3d7ff140839dcc20dd811ee6ffef3da00111134674508a484b33`.

Raw-output assertions match the saved `week4_codify_baseline_v1` results.

| Assertion | Denominator | Raw (before) | Delivered (after) |
| --- | --- | --- | --- |
| `deferred_date_qualifications_v1` | 20 | 18 pass / 2 fail (`TRACE-S02`, `TRACE-S20`) | 20 pass / 0 fail |
| `s19_retrieval_budget_v1` | 1 | 0 pass / 1 fail (`TRACE-S19`) | 0 pass / 1 fail (`TRACE-S19`) |

Newly passing on delivered A: TRACE-S02, TRACE-S20. No new A failures. S19 still fails because retrieval was not changed (6 `preview_classification_search` act events on the saved parent trace).

This is an application-layer effect on saved live traces. It is not 20 new live runs and not a model-quality improvement.

## Raw versus delivered

On every replayed parent trace the formatter status was `ok`, the source record and text hash matched the pins, and the delivered Timing and scope quoted both deferred dates from Article 113. Raw answers remain stored separately under `timing_repair.raw_output`.

Several raw answers mentioned December 2027 without August 2028. Delivered answers always include both dates from the verified source. The original timing paragraph is not left in the delivered answer.

## Replay versus live smoke

| Item | Replay | Live smoke |
| --- | --- | --- |
| What it is | Application-layer replay of 20 saved live traces | One new TRACE-S02 invocation |
| Model / retrieval | none | one live run, existing 8/90 limits, no retries |
| Dataset | frozen `week4_adk_preview_v1` | `data/local/traces/timing_repair_smoke.jsonl` |
| Added to either frozen 20-run set | no (reads only) | no |
| Review register | not opened | not opened |

Do not combine these into one 21-run score.

## Live TRACE-S02 integration smoke

Ran once after offline checks. Stored separately.

| Item | Value |
| --- | --- |
| Scenario stored as | `timing_repair_smoke` |
| Source scenario | TRACE-S02 |
| Run ID | `fb634225-74e4-4ad8-ae5f-5a7cc52087ae` |
| Execution | ok, 27550 ms, 1 tool call, limits 8/90 |
| Formatter | `aeacus.timing_scope.v1` / `1`, status `ok` |
| Source record | `T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/113` |
| Source text SHA-256 | `0f628e97ddb44755c40162f14950a4bc8072552fda2a3c38773c5a7f30c8bd4d` |
| Smoke JSONL SHA-256 | `f490a1fd0d90840a0fb16f26bcdbeae52e7fb32bc7a191d7c43962cc330dc56d` |

`deferred_date_qualifications_v1` on this smoke: raw **pass**, delivered **pass**. The live raw already named Chapter III Sections 1–3 and the Article 6(5) exception for the December 2027 date it mentioned. It omitted 2 August 2028. The checker only requires markers for dates that appear, so raw passed. Delivered quotes both deferred dates from the verified source. This is not evidence that the frozen TRACE-S02 raw was correct, and it is not a 20-run result.

Complete raw and delivered texts are in `reports/week4_timing_repair_eval.json` (`live_smoke.raw_output` / `live_smoke.delivered_output`) and in the smoke JSONL `timing_repair` object.

## Failures and limitations

- F1 remains unresolved: 5/20 failures on both parent and candidate.
- Candidate F2 labels were not assigned. No overall quality pass rate is reported.
- Source review and ingestion gates stay closed. Corpus and dependencies were not changed. No commits or pushes.
- `s19_retrieval_budget_v1` still fails on replayed parent TRACE-S19.
- `deferred_date_qualifications_v1` only inspects dates that are mentioned. Omitting 2 August 2028 is not itself a fail if December 2027 is qualified. The formatter still inserts both deferred dates from the verified source.
- Formatter success on these 20 traces required a complete Article 113 observation in the saved events. Missing, tampered, or wrong-edition evidence fails closed and states no statutory dates.
- MCP, SequentialAgent dual preview, and LangGraph paths were not modified and were not collected.

Machine-readable companion: `reports/week4_timing_repair_eval.json`.
