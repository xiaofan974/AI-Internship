# AeacusAI Week 4 baseline batch 4 — capture completeness

This report records TRACE capture completeness for TRACE-S16 through TRACE-S20. It does not assess answer quality, assign failure labels, or calculate pass rates. Human notes, judgments, and scores remain empty.

## Baseline ID and frozen configuration

| Item | Value |
| --- | --- |
| Baseline ID | `week4_adk_preview_v1` |
| Frozen manifest | `evals/week4/baselines/week4_adk_preview_v1/manifest.json` |
| Scenario-file SHA-256 | `02aeb6ae8c7af29864d493c08621ba048c73680e89cd34e466ebe46cd86b2070` |
| Model | `gemini-3.8-flash` |
| Limits | `max_llm_calls=8`, timeout 90 seconds |
| Phase | `batch4` |
| Raw traces | `data/local/traces/week4_adk_preview_v1.jsonl` (gitignored) |

Before this batch, frozen hashes still matched the manifest. The manifest was not updated. TRACE-S01–S15 were already attempted and were not selected. TRACE-S16–S20 had no prior attempts.

## Scenario-to-run-ID mapping (batch 4)

| Scenario | Run ID | Runner session ID |
| --- | --- | --- |
| TRACE-S16 | `07fb835c-7dbf-4b71-9aca-06a43c263150` | `64f51260-7b86-4d0d-8711-2b112810a443` |
| TRACE-S17 | `1fc62262-6590-4429-833a-2e9c269a5928` | `fa065747-fd35-4ca0-a67b-a1373114f98e` |
| TRACE-S18 | `74c715ab-7ad1-4fb5-afdf-50acc7f7057b` | `f1c8167b-e637-469e-a168-405b2a3d9982` |
| TRACE-S19 | `fd86e112-fb20-42fa-b9f7-e0a65125342b` | `704ea954-7b71-4140-9e80-790645c059dc` |
| TRACE-S20 | `feb73275-7e82-4159-8bb9-1e90cf15edac` | `cc0def64-7458-4c40-b304-121b1dbcc809` |

## Execution status, duration, and trace location

```text
.venv/bin/python run_week4_baseline.py run --scenarios TRACE-S16:TRACE-S20 --phase batch4
```

Shared trace file after this batch: 20 JSONL lines (batches 1–4). Each of these five lines resolves to the run ID above.

| Scenario | Execution status | Elapsed (ms) | Capture saved | Complete original observations |
| --- | --- | --- | --- | --- |
| TRACE-S16 | ok | 28255.930 | yes | yes (1 observe; 8 records with full text, snapshot IDs, hashes) |
| TRACE-S17 | ok | 24975.638 | yes | yes (1 observe; 6 records with full text, snapshot IDs, hashes) |
| TRACE-S18 | ok | 28224.979 | yes | yes (1 observe; 8 records with full text, snapshot IDs, hashes) |
| TRACE-S19 | ok | 86721.000 | yes | yes (6 observe events; 48 records with full text, snapshot IDs, hashes) |
| TRACE-S20 | ok | 32209.110 | yes | yes (1 observe; 8 records with full text, snapshot IDs, hashes) |

Each saved line also contains baseline ID `week4_adk_preview_v1`, phase `batch4`, matching scenario ID, frozen instructions, associated tool call/response IDs, a final visible answer, last-observed usage, empty `human_annotation`, pending review `not_created`, and register open/write `not_observed`.

No scenarios were interrupted. No authentication, quota, or capture-persistence stop occurred.

## Missing fields, interrupted scenarios, or limitations

- Pending review is `not_created` on this runner; register access was not observed.
- TRACE-S19 made six retrieval calls within the existing 8-call / 90-second limits (elapsed 86.7s). All six original observation payloads were saved. That execution was not replaced.

This report does not judge whether the drafts are correct. No graders, prompt fixes, dependency changes, corpus changes, ingestion, commits, or pushes were made.
