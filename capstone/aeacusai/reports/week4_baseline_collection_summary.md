# AeacusAI Week 4 baseline collection summary

Baseline ID: `week4_adk_preview_v1`. Architecture: single-agent ADK classification preview with the direct Python `preview_classification_search` tool. This summary verifies collection completeness only. It does not assess answer quality, assign failure labels, or calculate pass rates. Human notes, judgments, and scores remain empty.

## Frozen provenance

| Item | Value |
| --- | --- |
| Frozen manifest | `evals/week4/baselines/week4_adk_preview_v1/manifest.json` |
| Frozen at | `2026-10-22T20:54:31.585865+00:00` |
| Scenarios | `evals/week4/scenarios_v1.json` (20 IDs, TRACE-S01–S20) |
| Scenario-file SHA-256 | `02aeb6ae8c7af29864d493c08621ba048c73680e89cd34e466ebe46cd86b2070` |
| Model | `gemini-3.8-flash` |
| Generation config | not set on the agent |
| Limits | 8 model calls / 90 seconds |
| Instruction SHA-256 | `6d28bfa7d6d42c8ce1c21211b1e87adf877137ed878b1082c0ec6f36716a7de7` |
| Excluded | `capture_smoke` |
| Mutable run index | `data/local/evals/week4/week4_adk_preview_v1/run_index.json` |
| Raw traces | `data/local/traces/week4_adk_preview_v1.jsonl` |

After all four batches, `verify_no_drift` still reports no mismatch against the frozen manifest. The manifest was never updated. TRACE-S01–S05 were not rerun.

## Exactly one attempted run per scenario

JSONL lines: **20**. Run-index attempts: **20**. Frozen scenario IDs: **20**.

| Check | Result |
| --- | --- |
| One index row per TRACE-S01–S20 | yes |
| Unique run IDs | 20 / 20 |
| Unique runner session IDs | 20 / 20 |
| Unattempted frozen scenarios | none |
| Extra index IDs | none |
| Duplicate JSONL run IDs | none |

## Every attempt resolves to its original saved trace

Each run ID in the index is present exactly once in `week4_adk_preview_v1.jsonl`. User inputs match the frozen scenario file. `capture.complete` is true on every line. No attempt was replaced.

| Scenario | Phase | Run ID | Status | Elapsed (ms) | Complete original observations |
| --- | --- | --- | --- | --- | --- |
| TRACE-S01 | batch1 | `4c969b0c-7046-4409-bca2-f096a5d34c83` | ok | 25162.446 | yes |
| TRACE-S02 | batch1 | `392db6f3-1620-42d1-bf81-b554ee9e1aba` | ok | 22250.687 | yes |
| TRACE-S03 | batch1 | `17017bf1-7aec-4028-8e99-eebc58193325` | ok | 18670.850 | yes |
| TRACE-S04 | batch1 | `b5caecbd-ace2-42c1-88ea-1592d163a6ed` | ok | 37198.622 | yes |
| TRACE-S05 | batch1 | `2bdc75d1-a252-4bec-b287-f21aab2f91de` | ok | 21376.721 | yes |
| TRACE-S06 | batch2 | `8e8d9cef-85de-4cd7-b629-7c307ffa5710` | ok | 35402.712 | yes |
| TRACE-S07 | batch2 | `4b4980c1-3b6d-4e09-b5f4-71eccd9a96ed` | ok | 26968.718 | yes |
| TRACE-S08 | batch2 | `21c988a6-775a-4a2f-8513-8aa29423b18a` | ok | 32296.470 | yes |
| TRACE-S09 | batch2 | `1615192e-ab2a-4e8d-8902-4913644fc746` | ok | 20680.591 | yes |
| TRACE-S10 | batch2 | `22b36ab5-77e2-454f-87e0-320245240b75` | ok | 28547.382 | yes |
| TRACE-S11 | batch3 | `a08c00bc-1578-4a20-a2d6-89669e3fc29c` | ok | 41677.555 | yes |
| TRACE-S12 | batch3 | `e547178d-c70a-4cca-9591-ec733fd01c26` | ok | 42277.559 | yes |
| TRACE-S13 | batch3 | `7ccd9cdd-3612-419a-9cda-b76ce3e901b2` | ok | 28315.621 | yes |
| TRACE-S14 | batch3 | `ab3b0d19-a131-4304-b6af-83a24bd1dabd` | ok | 24879.890 | yes |
| TRACE-S15 | batch3 | `305708e0-218e-4c79-88f2-50f226ec7998` | ok | 43518.048 | yes |
| TRACE-S16 | batch4 | `07fb835c-7dbf-4b71-9aca-06a43c263150` | ok | 28255.930 | yes |
| TRACE-S17 | batch4 | `1fc62262-6590-4429-833a-2e9c269a5928` | ok | 24975.638 | yes |
| TRACE-S18 | batch4 | `74c715ab-7ad1-4fb5-afdf-50acc7f7057b` | ok | 28224.979 | yes |
| TRACE-S19 | batch4 | `fd86e112-fb20-42fa-b9f7-e0a65125342b` | ok | 86721.000 | yes |
| TRACE-S20 | batch4 | `feb73275-7e82-4159-8bb9-1e90cf15edac` | ok | 32209.110 | yes |

All twenty executions completed with status `ok` and a saved final visible answer. There are no failed or timed-out rows in this dataset. If a later run had failed, it would remain in this file rather than being replaced.

## No smoke, historical, or other-architecture runs

| Check | Result |
| --- | --- |
| `capture_smoke` in index or JSONL | no |
| Architectures in JSONL | `adk_single_agent_preview` only |
| Agent names | `aeacus_preview_agent` only |
| Entry points | `evals.week4.baseline.collect_batch` only |
| Baseline IDs | `week4_adk_preview_v1` only |
| MCP / dual-agent / LangGraph traces | not present |
| Prompt-injection historical eval runs | not present |

## Frozen provenance is consistent

- Scenario inputs in every saved trace match `evals/week4/scenarios_v1.json`.
- Frozen instruction text in every saved trace matches current `AEACUS_PREVIEW_INSTRUCTION`.
- Working-tree hashes still match the frozen manifest after batch 4.
- Implementation, corpus, model, and limit fields were not rewritten.

## Missing fields or unattempted scenarios

Unattempted frozen scenarios: **none**.

Fields that are present but recorded as unknown/not applicable, by design:

- `pending_review.status=not_created` (baseline runner does not create a Streamlit pending artifact)
- `register_opened` and `register_written` = `not_observed` (the review database was not opened)
- `generate_content_config` unset on the agent (frozen as `not_set_on_agent`)
- Usage is last-observed, not a summed cost

No capture-persistence failures. No authentication or quota stop.

## Human annotation fields

On all 20 saved traces, `human_annotation` is empty:

```json
{"annotator": null, "notes": null, "labels": [], "scores": {}, "reviewed_at": null}
```

Batch capture reports: `reports/week4_baseline_batch1.md`, `reports/week4_baseline_batch2.md`, `reports/week4_baseline_batch3.md`, `reports/week4_baseline_batch4.md`.

Raw traces remain local and gitignored. No agent, dependency, corpus, ingestion, commit, or push changes were made for this collection.
