# AeacusAI Week 4 baseline batch 1 — capture completeness

This report records TRACE capture completeness for the first five frozen scenarios. It does not assess answer quality, assign failure labels, or calculate pass rates. Human notes, judgments, and scores remain empty.

## Baseline ID and frozen configuration

| Item | Value |
| --- | --- |
| Baseline ID | `week4_adk_preview_v1` |
| Architecture | `adk_single_agent_preview` (`aeacus_preview_agent`, direct Python `preview_classification_search`) |
| Frozen manifest | `evals/week4/baselines/week4_adk_preview_v1/manifest.json` |
| Frozen scenarios | `evals/week4/scenarios_v1.json` |
| Scenario-file SHA-256 | `02aeb6ae8c7af29864d493c08621ba048c73680e89cd34e466ebe46cd86b2070` |
| Model | `gemini-3.8-flash` |
| Generation config | Not set on the agent (`generate_content_config_status: not_set_on_agent`) |
| RunConfig | `max_llm_calls=8` |
| Timeout | 90 seconds |
| Instruction SHA-256 | `6d28bfa7d6d42c8ce1c21211b1e87adf877137ed878b1082c0ec6f36716a7de7` |
| Excluded from this baseline | `capture_smoke` |
| Mutable run index | `data/local/evals/week4/week4_adk_preview_v1/run_index.json` (gitignored) |
| Raw traces | `data/local/traces/week4_adk_preview_v1.jsonl` (gitignored) |

The frozen scenario file contains exactly 20 unique IDs (`TRACE-S01` … `TRACE-S20`) with non-empty inputs extracted verbatim from `reports/week4_trace_audit.md`. No expected answers, classifications, failure labels, or scores were added. Extraction was unambiguous.

Before this batch, drift verification compared the working tree to the frozen manifest. No drift was reported. The manifest was not updated.

## Offline verification

```text
.venv/bin/python -m unittest test_week4_baseline test_trace_store \
  test_streamlit_app test_review_register -v
```

Result: **38 tests, 0 failures.**

`test_week4_baseline` covered explicit scenario selection, 20 unique non-empty inputs, verbatim S01/S05 text, exclusion of `capture_smoke`, dry-run with zero provider calls, mocked sequential collection with distinct session IDs, preservation of a failed run in JSONL, duplicate-attempt blocking, persist-failure stop, and drift stop without rewriting the manifest.

CLI dry-run after freeze:

```text
.venv/bin/python run_week4_baseline.py run --scenarios TRACE-S01:TRACE-S05 --phase batch1 --dry-run
```

Selected `TRACE-S01` … `TRACE-S05` and made zero provider calls.

## Scenario-to-run-ID mapping (batch 1)

| Scenario | Run ID | Runner session ID |
| --- | --- | --- |
| TRACE-S01 | `4c969b0c-7046-4409-bca2-f096a5d34c83` | `aee56c96-f678-4a2d-9dca-9c70ccda2292` |
| TRACE-S02 | `392db6f3-1620-42d1-bf81-b554ee9e1aba` | `de25a7ba-3ce6-40e8-b47b-55130cce26fd` |
| TRACE-S03 | `17017bf1-7aec-4028-8e99-eebc58193325` | `9231c07c-ba5a-4bcc-8308-1075a350a3f6` |
| TRACE-S04 | `b5caecbd-ace2-42c1-88ea-1592d163a6ed` | `c595d9a2-9617-4e3c-bab5-6d7111dca4ea` |
| TRACE-S05 | `2bdc75d1-a252-4bec-b287-f21aab2f91de` | `1786fa9e-c092-472b-be0b-464fb9dab4cf` |

`capture_smoke` is not in this mapping. TRACE-S06 through TRACE-S20 were not run.

## Execution status, duration, and trace location

Live command (one attempt each, sequential, no harness retries):

```text
.venv/bin/python run_week4_baseline.py run --scenarios TRACE-S01:TRACE-S05 --phase batch1
```

Shared trace file: `data/local/traces/week4_adk_preview_v1.jsonl` (5 JSONL lines).

| Scenario | Execution status | Elapsed (ms) | Capture saved | Complete original observations |
| --- | --- | --- | --- | --- |
| TRACE-S01 | ok | 25162.446 | yes | yes (1 observe; 4 records with full text, snapshot IDs, hashes) |
| TRACE-S02 | ok | 22250.687 | yes | yes (1 observe; 7 records with full text, snapshot IDs, hashes) |
| TRACE-S03 | ok | 18670.850 | yes | yes (1 observe; 4 records with full text, snapshot IDs, hashes) |
| TRACE-S04 | ok | 37198.622 | yes | yes (1 observe; 8 records with full text, snapshot IDs, hashes) |
| TRACE-S05 | ok | 21376.721 | yes | yes (1 observe; 8 records with full text, snapshot IDs, hashes) |

Each saved line also contains:

- `baseline.id=week4_adk_preview_v1`, `baseline.phase=batch1`, matching `scenario_id`
- Frozen instruction text matching current `AEACUS_PREVIEW_INSTRUCTION`
- Ordered visible events `act` / `observe` / `final` (no thought parts)
- Tool call/response association via `trace_call_1` and a provider call ID
- Final visible answer (`execution_status=ok`)
- Last-observed usage metadata (not summed)
- Empty `human_annotation`
- `pending_review.status=not_created` (this runner does not create a Streamlit pending artifact)
- `register_opened` and `register_written` = `not_observed` (the review database was not opened or written)

No scenarios were interrupted. No authentication, quota, or capture-persistence stop occurred.

## Missing fields, interrupted scenarios, or limitations

- TRACE-S06–TRACE-S20 are frozen but uncollected.
- The baseline CLI path does not create a session-local pending review; pending status is `not_created`, not a Streamlit `review_required` artifact.
- Register open/write remain `not_observed` by design.
- `generate_content_config` is unset on the agent; that absence is frozen rather than invented.
- Usage is last-observed, not a summed cost.
- This report does not judge whether the drafts are correct.

Agent instructions, retrieval, corpus, execution limits, Streamlit, and approval controls were not changed for this batch. No graders, prompt fixes, dependency changes, corpus changes, ingestion, commits, or pushes were made.
