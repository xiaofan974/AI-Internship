# AeacusAI Week 4 baseline batch 2 — capture completeness

This report records TRACE capture completeness for TRACE-S06 through TRACE-S10. It does not assess answer quality, assign failure labels, or calculate pass rates. Human notes, judgments, and scores remain empty.

## Baseline ID and frozen configuration

| Item | Value |
| --- | --- |
| Baseline ID | `week4_adk_preview_v1` |
| Frozen manifest | `evals/week4/baselines/week4_adk_preview_v1/manifest.json` |
| Scenario-file SHA-256 | `02aeb6ae8c7af29864d493c08621ba048c73680e89cd34e466ebe46cd86b2070` |
| Model | `gemini-3.8-flash` |
| Limits | `max_llm_calls=8`, timeout 90 seconds |
| Phase | `batch2` |
| Raw traces | `data/local/traces/week4_adk_preview_v1.jsonl` (gitignored) |

Before this batch, frozen scenario, configuration, implementation, and corpus hashes still matched the manifest. The manifest was not updated. TRACE-S01–S05 were already attempted and were not selected. TRACE-S06–S10 had no prior attempts. A dry-run selected those five IDs and made zero provider calls.

## Scenario-to-run-ID mapping (batch 2)

| Scenario | Run ID | Runner session ID |
| --- | --- | --- |
| TRACE-S06 | `8e8d9cef-85de-4cd7-b629-7c307ffa5710` | `8dc245dd-cee5-4e6e-8153-79df6faf5e8d` |
| TRACE-S07 | `4b4980c1-3b6d-4e09-b5f4-71eccd9a96ed` | `7dd3e91b-3640-4028-ab34-454bd2424684` |
| TRACE-S08 | `21c988a6-775a-4a2f-8513-8aa29423b18a` | `03b16f43-d07e-4b19-afdb-b18c429069ac` |
| TRACE-S09 | `1615192e-ab2a-4e8d-8902-4913644fc746` | `3eedbeb8-b39a-4846-8022-3dad498447af` |
| TRACE-S10 | `22b36ab5-77e2-454f-87e0-320245240b75` | `53c5a601-be5c-4b6d-a1b4-a0b7e9b2e942` |

## Execution status, duration, and trace location

```text
.venv/bin/python run_week4_baseline.py run --scenarios TRACE-S06:TRACE-S10 --phase batch2
```

Shared trace file after this batch: 10 JSONL lines (batches 1–2). Each of these five lines resolves to the run ID above.

| Scenario | Execution status | Elapsed (ms) | Capture saved | Complete original observations |
| --- | --- | --- | --- | --- |
| TRACE-S06 | ok | 35402.712 | yes | yes (2 observe events; 16 records with full text, snapshot IDs, hashes) |
| TRACE-S07 | ok | 26968.718 | yes | yes (1 observe; 8 records with full text, snapshot IDs, hashes) |
| TRACE-S08 | ok | 32296.470 | yes | yes (1 observe; 8 records with full text, snapshot IDs, hashes) |
| TRACE-S09 | ok | 20680.591 | yes | yes (1 observe; 8 records with full text, snapshot IDs, hashes) |
| TRACE-S10 | ok | 28547.382 | yes | yes (1 observe; 4 records with full text, snapshot IDs, hashes) |

Each saved line also contains baseline ID `week4_adk_preview_v1`, phase `batch2`, matching scenario ID, frozen instructions, associated tool call/response IDs, a final visible answer, last-observed usage, empty `human_annotation`, pending review `not_created`, and register open/write `not_observed`.

No scenarios were interrupted. No authentication, quota, or capture-persistence stop occurred.

## Missing fields, interrupted scenarios, or limitations

- TRACE-S11–S20 remain frozen but uncollected after this batch.
- Pending review is `not_created` on this runner; register access was not observed.
- TRACE-S06 made two retrieval calls; both original observation payloads were saved.

This report does not judge whether the drafts are correct. No graders, prompt fixes, dependency changes, corpus changes, ingestion, commits, or pushes were made.
