# AeacusAI Week 4 F1 candidate collection

Candidate ID: `week4_adk_preview_f1_v2`. Parent baseline: `week4_adk_preview_v1`. This report records an instruction-only candidate, capture completeness, and unchanged deterministic assertions. It does **not** measure F1 before/after. Candidate `human_annotation` fields are empty. Baseline F1/F2 labels were not copied onto candidate answers. No model judge and no keyword matching were used as proof of F1 improvement.

## Instruction change and provenance

One general operating rule was added to `AEACUS_PREVIEW_INSTRUCTION` on the primary direct-Python `aeacus_preview_agent`. The existing five-heading format, citation rules, subset-scope restrictions, word guidance, date/quote rule, and search-refinement rule were left in place. The prompt contains no scenario IDs, baseline answers, failure labels, or case-specific exceptions.

Exact diff: `evals/week4/baselines/week4_adk_preview_f1_v2/instruction.diff`

```diff
--- week4_adk_preview_v1/AEACUS_PREVIEW_INSTRUCTION
+++ week4_adk_preview_f1_v2/AEACUS_PREVIEW_INSTRUCTION
@@ -30,3 +30,9 @@
 5. Scope of the reading:
    - This is a provisional reading against the pinned classification subset only.
    - Do not make full-compliance, regulatory conformity, or “not prohibited” conclusions. This tool does not cover the whole EU AI Act.
+6. Specific system and unresolved facts:
+   - Assess only the specific system and deployment described. Do not extend a finding to another vendor product or a downstream system without sufficient deployment facts.
+   - Distinguish stated facts from assumptions. Retrieved legislation establishes rules, not facts about the submitted system.
+   - Do not convert an omitted fact into a negative assertion. For example, silence about an identity claim does not establish that none exists.
+   - When applying a classification provision depends on an unresolved material fact, make that dependency explicit in the Provisional finding and in Why. Listing the fact under Missing facts alone is insufficient.
+   - Preserve useful supported conclusions. Do not refuse all classification merely because additional technical details could be requested.
```

| Instruction artifact | SHA-256 |
| --- | --- |
| Parent `AEACUS_PREVIEW_INSTRUCTION` | `6d28bfa7d6d42c8ce1c21211b1e87adf877137ed878b1082c0ec6f36716a7de7` |
| Candidate `AEACUS_PREVIEW_INSTRUCTION` | `20f72d6ea00bb6a052266a9abc79066d93119f321a56a3cea446f556cda9517e` |
| Instruction diff file | `8037f2f99c1fffef2ad48063ed913cd93673627aabf950fa0822f10ca341a3f5` |

Hashes are also stored in `evals/week4/baselines/week4_adk_preview_f1_v2/instruction_hashes.json`. Baseline traces still store the parent instruction text. That stored text was not rewritten.

MCP, dual-agent, and LangGraph definitions import the same instruction constant. Those architectures were not collected.

## Candidate manifest

Frozen before the first candidate invocation at `evals/week4/baselines/week4_adk_preview_f1_v2/manifest.json`. Linked to `week4_adk_preview_v1` and the same scenario-file hash.

| Item | Parent | Candidate |
| --- | --- | --- |
| Collection ID | `week4_adk_preview_v1` | `week4_adk_preview_f1_v2` |
| Scenario file SHA-256 | `02aeb6ae8c7af29864d493c08621ba048c73680e89cd34e466ebe46cd86b2070` | same |
| Model | `gemini-3.8-flash` | same |
| Tool definitions SHA-256 | `2a41a31f0f9020030b72f550421eee0a7ca700087817c3af2d0d113d5855c894` | same |
| Corpus snapshot | `T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715` | same |
| Generation config | not set on the agent | same |
| Limits | 8 model calls / 90 seconds | same |
| Instruction SHA-256 | `6d28bfa7…7de7` | `20f72d6e…517e` (intentional) |

Unchanged-from-parent checks at freeze: model, tools, corpus, generation, limits, and `scenarios.sha256` all matched. The freeze refused unless the instruction hash changed.

The parent manifest was not updated. After the instruction and collection-support edits, `verify_no_drift` on `week4_adk_preview_v1` reports the expected mismatch: `instructions`, `implementation_files`. Drift protection was left enabled.

Parent artifacts still match their original hashes:

| Parent artifact | SHA-256 |
| --- | --- |
| `data/local/traces/week4_adk_preview_v1.jsonl` | `29871169b2db5aebeac179cdd254a4700e36f252b2873ea9e05e334400204db1` |
| `evals/week4/baselines/week4_adk_preview_v1/manifest.json` | `fdd0e4d96b314a4c3e37aea1d7d00b9f67ee3a86337e3000c43b2c35727643e3` |

## Collection-support change

`BaselinePaths.baseline_id` and `run_week4_baseline.py --id` / `--parent` select the manifest, run index, and JSONL. Default ID remains `week4_adk_preview_v1`. Execution is still `run_review` with `aeacus_preview_agent`, the direct Python tool, 8/90 limits, one attempt, no harness retries, and no review-register access. Offline tests covering that behavior still pass.

## Offline verification

Ran existing suites only. No new tests that look for prompt phrases.

```text
.venv/bin/python -m unittest test_week4_baseline test_week4_codify \
  test_preview_presentation test_trace_store test_streamlit_app \
  test_context_preview test_review_register test_prompt_injection -q
```

Result: **68 tests, 0 failures.**

## Collection

Same TRACE-S01–S20 inputs, sequential batches of five, freeze-then-collect, drift check before each batch. Fresh session and one attempt per scenario. Failures and timeouts would have been kept; none occurred. The review register was not opened.

| Batch | Scenarios | Command |
| --- | --- | --- |
| 1 | TRACE-S01–S05 | `run_week4_baseline.py run --id week4_adk_preview_f1_v2 --scenarios TRACE-S01:TRACE-S05 --phase batch1` |
| 2 | TRACE-S06–S10 | same, `TRACE-S06:TRACE-S10 --phase batch2` |
| 3 | TRACE-S11–S15 | same, `TRACE-S11:TRACE-S15 --phase batch3` |
| 4 | TRACE-S16–S20 | same, `TRACE-S16:TRACE-S20 --phase batch4` |

JSONL lines: **20**. Unique run IDs: **20**. Unique runner sessions: **20**. Unattempted scenarios: **none**. `capture_smoke`, MCP, dual-agent, and LangGraph traces: **not present**. Every index run ID resolves to one candidate JSONL line. Inputs match `evals/week4/scenarios_v1.json`. Candidate instruction hash is `20f72d6e…517e` on every line.

### Scenario-to-run mapping and capture completeness

| Scenario | Phase | Run ID | Status | Elapsed (ms) | Search call events | Complete original observations |
| --- | --- | --- | --- | --- | --- | --- |
| TRACE-S01 | batch1 | `2da3cfd8-b8be-4d2a-8754-a763ba2f21e6` | ok | 28590.586 | 1 | yes |
| TRACE-S02 | batch1 | `aaabee81-001c-4b03-a1b6-3ed4e8efa655` | ok | 26113.494 | 1 | yes |
| TRACE-S03 | batch1 | `9d315772-3c24-4440-a8c1-c52041b19dc1` | ok | 23751.592 | 1 | yes |
| TRACE-S04 | batch1 | `ab268600-0757-44ef-b07f-dfb273ce8871` | ok | 28020.268 | 1 | yes |
| TRACE-S05 | batch1 | `2aa618ff-1b1a-4c16-b74b-3ead8d11e71a` | ok | 19944.190 | 1 | yes |
| TRACE-S06 | batch2 | `c1388a22-0ce6-49f4-a625-0ed9ecf41f23` | ok | 29736.253 | 1 | yes |
| TRACE-S07 | batch2 | `fa38efad-1ad4-4bee-ac24-91ad2442ee9f` | ok | 27259.804 | 1 | yes |
| TRACE-S08 | batch2 | `d0eb1005-47c9-44bc-aa5c-eb9c18d3b601` | ok | 35396.318 | 1 | yes |
| TRACE-S09 | batch2 | `43b6664b-5b39-47b2-97fb-6e2e2514b9f1` | ok | 42726.463 | 1 | yes |
| TRACE-S10 | batch2 | `4e26e322-9f32-408f-a1ea-9ae448554e12` | ok | 31733.313 | 1 | yes |
| TRACE-S11 | batch3 | `acaa91b8-95f4-44a5-8825-4a046c29bec2` | ok | 33337.373 | 1 | yes |
| TRACE-S12 | batch3 | `9e53160d-b461-45da-9b53-3572bf5b6c13` | ok | 31636.736 | 1 | yes |
| TRACE-S13 | batch3 | `4eb39bb8-253c-4c56-aa5f-a1d7dc5ec1bc` | ok | 44099.806 | 2 | yes |
| TRACE-S14 | batch3 | `4112acb0-e775-4193-a734-578b0cc99ae2` | ok | 30315.542 | 2 | yes |
| TRACE-S15 | batch3 | `0fe52a24-d0c4-4f6d-abe3-e4271e8044fa` | ok | 78284.857 | 1 | yes |
| TRACE-S16 | batch4 | `4a7e7395-aaee-4aca-bc5f-b3109c72950d` | ok | 39639.181 | 1 | yes |
| TRACE-S17 | batch4 | `4c2809a3-f27d-48b2-bc4a-f8e3efc41cf5` | ok | 23511.339 | 1 | yes |
| TRACE-S18 | batch4 | `3bcf7890-78ba-4417-ba06-5d4916bd7ba7` | ok | 23992.152 | 1 | yes |
| TRACE-S19 | batch4 | `3386d04f-a9ec-49cf-8af0-57bdcbc1ed76` | ok | 29718.976 | 1 | yes |
| TRACE-S20 | batch4 | `39349126-070f-4c7b-bb2f-a05c5ec33ab4` | ok | 26891.558 | 1 | yes |

On every line: `capture.complete=true`, `pending_review.status=not_created`, `register_opened=not_observed`, `register_written=not_observed`, and empty `human_annotation`.

## Deterministic assertions (unchanged checkers)

Checker suite `week4_codify_v1`. `evals/week4/checkers.py` SHA-256 is still `330fce7b22fc3d7ff140839dcc20dd811ee6ffef3da00111134674508a484b33`. Checker-config hash is still `4423834db6d0360ecdfe426c29df0686780b89dcbcbd00a4a8c8ef2ef59519cc`. Thresholds were not changed. Automated results use original candidate `final_output` and `events` only.

### A. Deferred-date qualifications

Denominator: **20** applicable (all candidate Timing and scope sections summarize December 2027 or August 2028).

| Set | Fail IDs | Pass | Fail |
| --- | --- | --- | --- |
| Parent baseline | TRACE-S02, TRACE-S20 | 18 | 2 |
| Candidate | TRACE-S02, TRACE-S03, TRACE-S05, TRACE-S06, TRACE-S12, TRACE-S16 | 14 | 6 |

- Still failing: TRACE-S02
- Newly failing (regressed from parent pass): TRACE-S03, TRACE-S05, TRACE-S06, TRACE-S12, TRACE-S16
- Newly passing: TRACE-S20

Candidate fail reasons: S02 omits Chapter III, Sections 1–3, and the Article 6(5) exception; S03, S06, S12, and S16 omit Chapter III and Sections 1–3; S05 omits the Article 6(5) exception.

This checkpoint did not target F3. The five new A failures are assertion regressions, not harness errors. S20’s new A pass is incidental and is not an F3 or F1 measurement.

### B. S19 retrieval budget

Denominator: **1** (TRACE-S19 only). The other 19 scenarios are not applicable and are excluded.

| Set | Fail IDs | Pass | Fail |
| --- | --- | --- | --- |
| Parent baseline | TRACE-S19 (6 call events) | 0 | 1 |
| Candidate | none (1 call event) | 1 | 0 |

TRACE-S19 now passes the unchanged ≤2-call rule. This checkpoint did not target F4. The change is incidental and is not proof of an F4 or F1 improvement.

## F1 measurement status

**F1 before/after measurement awaits reviewed labels.**

This checkpoint does not assign candidate F1/F2/F3/F4 judgments, does not reuse parent taxonomy labels as candidate labels, and does not treat assertion movement as an F1 result.

## Candidate trace locations

| Artifact | Path | SHA-256 |
| --- | --- | --- |
| Candidate JSONL | `data/local/traces/week4_adk_preview_f1_v2.jsonl` | `3b1fa10c5a05a8db61403ddda04d3e6d5ecf0ae06f684daf3cf30392e253f848` |
| Candidate run index | `data/local/evals/week4/week4_adk_preview_f1_v2/run_index.json` | gitignored mutable index |
| Candidate manifest | `evals/week4/baselines/week4_adk_preview_f1_v2/manifest.json` | `c1a5aaf95b84662f2461f5fb5fedc65acac611bd68a657de89caa20e3b13d97f` |
| Assertion results | `evals/week4/results/week4_adk_preview_f1_v2_assertions.json` | machine-readable, no human labels |

Raw traces remain local and gitignored. No dependency, corpus, ingestion, commit, or push changes were made.
