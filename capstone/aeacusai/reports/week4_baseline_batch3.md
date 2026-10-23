# AeacusAI Week 4 baseline batch 3 — capture completeness

This report records TRACE capture completeness for TRACE-S11 through TRACE-S15. It does not assess answer quality, assign failure labels, or calculate pass rates. Human notes, judgments, and scores remain empty.

## Baseline ID and frozen configuration

| Item | Value |
| --- | --- |
| Baseline ID | `week4_adk_preview_v1` |
| Frozen manifest | `evals/week4/baselines/week4_adk_preview_v1/manifest.json` |
| Scenario-file SHA-256 | `02aeb6ae8c7af29864d493c08621ba048c73680e89cd34e466ebe46cd86b2070` |
| Model | `gemini-3.8-flash` |
| Limits | `max_llm_calls=8`, timeout 90 seconds |
| Phase | `batch3` |
| Raw traces | `data/local/traces/week4_adk_preview_v1.jsonl` (gitignored) |

Before this batch, frozen hashes still matched the manifest. The manifest was not updated. TRACE-S01–S10 were already attempted and were not selected. TRACE-S11–S15 had no prior attempts.

## Scenario-to-run-ID mapping (batch 3)

| Scenario | Run ID | Runner session ID |
| --- | --- | --- |
| TRACE-S11 | `a08c00bc-1578-4a20-a2d6-89669e3fc29c` | `f5adc0dc-4cd6-4ea7-8767-8bec3771a118` |
| TRACE-S12 | `e547178d-c70a-4cca-9591-ec733fd01c26` | `ff6770f8-6d83-4e43-9ebe-a43c26eea067` |
| TRACE-S13 | `7ccd9cdd-3612-419a-9cda-b76ce3e901b2` | `6fef5ab0-ddfd-4ea3-9d68-e5b2b1ddf78e` |
| TRACE-S14 | `ab3b0d19-a131-4304-b6af-83a24bd1dabd` | `051f3bb8-d265-4af4-ae22-dce3a690be8c` |
| TRACE-S15 | `305708e0-218e-4c79-88f2-50f226ec7998` | `559f64b8-c64e-48b8-a974-8b06727801f8` |

## Execution status, duration, and trace location

```text
.venv/bin/python run_week4_baseline.py run --scenarios TRACE-S11:TRACE-S15 --phase batch3
```

Shared trace file after this batch: 15 JSONL lines (batches 1–3). Each of these five lines resolves to the run ID above.

| Scenario | Execution status | Elapsed (ms) | Capture saved | Complete original observations |
| --- | --- | --- | --- | --- |
| TRACE-S11 | ok | 41677.555 | yes | yes (1 observe; 8 records with full text, snapshot IDs, hashes) |
| TRACE-S12 | ok | 42277.559 | yes | yes (2 observe events; 16 records with full text, snapshot IDs, hashes) |
| TRACE-S13 | ok | 28315.621 | yes | yes (1 observe; 8 records with full text, snapshot IDs, hashes) |
| TRACE-S14 | ok | 24879.890 | yes | yes (1 observe; 7 records with full text, snapshot IDs, hashes) |
| TRACE-S15 | ok | 43518.048 | yes | yes (1 observe; 8 records with full text, snapshot IDs, hashes) |

Each saved line also contains baseline ID `week4_adk_preview_v1`, phase `batch3`, matching scenario ID, frozen instructions, associated tool call/response IDs, a final visible answer, last-observed usage, empty `human_annotation`, pending review `not_created`, and register open/write `not_observed`.

TRACE-S15 executed once and was saved. That execution is kept in the dataset; it was not replaced.

No scenarios were interrupted. No authentication, quota, or capture-persistence stop occurred.

## Missing fields, interrupted scenarios, or limitations

- TRACE-S16–S20 remain frozen but uncollected after this batch.
- Pending review is `not_created` on this runner; register access was not observed.
- TRACE-S12 made two retrieval calls; both original observation payloads were saved.

This report does not judge whether the drafts are correct. No graders, prompt fixes, dependency changes, corpus changes, ingestion, commits, or pushes were made.
