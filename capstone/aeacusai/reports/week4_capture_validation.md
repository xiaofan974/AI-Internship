# AeacusAI Week 4 TRACE capture validation

Primary ADK classification preview capture is now implemented. Capture is opt-in on `run_review(capture=...)` and is enabled only for `aeacus_preview_agent` with the direct Python `preview_classification_search` tool. MCP, dual-agent, and LangGraph paths were not modified. No graders, failure taxonomy, scoring, annotations, dependency upgrades, corpus changes, ingestion, register writes, commits, or pushes were made.

## Changed files

| File | Role |
| --- | --- |
| `aeacus_agent/trace_store.py` | **New.** JSONL schema, redaction, file locking, Git/code/corpus hashes, empty annotation fields |
| `run_review.py` | Optional `capture=` argument (default off). Records timestamps, usage if present, provider call IDs, association keys, full observations. Does not change the returned answer string |
| `streamlit_app.py` | Enables capture on the live preview path; persists after session-local pending review is created; does not query SQLite for outcome |
| `run_classification_preview.py` | Same writer for the CLI entry point; `--scenario-id` for `capture_smoke` |
| `test_trace_store.py` | **New.** Offline synthetic-event tests |

Traces write to `data/local/traces/adk_preview.jsonl` (already gitignored via `data/local/`). Override with `AEACUS_TRACE_PATH`. Disable with `AEACUS_TRACE_CAPTURE=0`. Other agents passed to `run_review()` are skipped and are not written to this baseline.

## Offline results

Command:

```text
.venv/bin/python -m unittest test_trace_store test_streamlit_app \
  test_preview_presentation test_review_register test_prompt_injection \
  test_context_preview -v
```

Result: **45 tests, 0 failures.**

Covered in `test_trace_store.py`:

- Full tool-response text survives JSONL serialization
- Tool calls and responses remain associated (`trace_call_N`; provider ID stays `null` when absent)
- Hidden thought events/fields and secret values are excluded; statutory text is not truncated
- Successful, failed, and timed-out invocations are recorded; failures do not store a successful `final_output`
- Missing usage remains `unknown`; observed usage is last-seen, not summed
- Consecutive and concurrent writes produce 8 valid independent JSONL records
- Wrong agent names are not written to the baseline
- Persist failures set `saved=false` and `capture.complete=false`
- Application outcome records register open/write as `not_observed`
- Existing `finalize_preview_result`, Streamlit UI, approval, and retrieval tests still pass

## Live execution and persistence

Exactly one live capture smoke test. No retries. Existing limits (`max_llm_calls=8`, `timeout_seconds=90`). TRACE-S01 through TRACE-S20 were not run.

```text
.venv/bin/python run_classification_preview.py --scenario-id capture_smoke
```

| Item | Result |
| --- | --- |
| Offline configuration check | passed (`aeacus_preview_agent`, single direct Python tool, Pinecone agent unchanged) |
| Execution | `ok` |
| Persistence | `TRACE capture saved` |
| Tool | one `preview_classification_search` call, status `ok` |
| Visible answer | provisional classification draft returned |

This smoke is labeled `capture_smoke` and is **not** part of the future 20-run baseline.

## Trace location and run ID

| Field | Value |
| --- | --- |
| Path | `capstone/aeacusai/data/local/traces/adk_preview.jsonl` |
| JSONL lines | 1 |
| `run_id` | `59aad88e-36bc-4d41-b760-2871f8e6f168` |
| `scenario_id` | `capture_smoke` |
| `entry_point` | `run_classification_preview.main` |
| `architecture` | `adk_single_agent_preview` |
| `agent_name` | `aeacus_preview_agent` |
| `model` | `gemini-3.8-flash` |
| `started_at` | `2026-10-22T20:44:33.063375+00:00` |
| `ended_at` | `2026-10-22T20:44:56.089687+00:00` |
| `elapsed_ms` | `23026.144` |
| `capture.complete` | `true` |

Inspected completeness of this smoke line:

- Frozen `AEACUS_PREVIEW_INSTRUCTION` matches current `preview_agent.py` (`instructions.status=observed`)
- User input is the existing recruitment example
- Exposed tool definition: `preview_classification_search(query: 'str') -> 'dict[str, Any]'`, backend `direct_python`
- Git commit `22afd0d2773bc7a0635ebbbc72bc391d12fb6fed`, `dirty=true` (uncommitted capture work)
- Source-file hashes and corpus snapshot/artifact hashes present
- Ordered visible events: `act`, `observe`, `final` (no `think`, no thought parts)
- Provider tool-call ID `call_236637` on both act and observe; association key `trace_call_1`
- Complete retrieved text: 5 matches (622–1708 chars) and 3 context records (957–7350 chars), including Annex III point 4 recruitment wording, plus `record_id`, `source_snapshot_id`, and `text_sha256`
- Final visible answer present (`execution_status=ok`, 2912 characters)
- Usage metadata present on this run (`last_observed_not_summed`; prompt 10287, total 12860). Not invented; not summed across the two usage events
- Application outcome: pending review `not_created` (CLI does not create a pending artifact); `register_opened` and `register_written` are `not_observed` (register was not queried)
- Human annotation fields empty
- No API-key material in the JSONL

## Missing fields or limitations

- CLI smoke cannot observe a Streamlit session-local pending `run_id`. That field is populated only on the Streamlit entry point after `create_pending_review`.
- Register open/write remain `not_observed` by design. Capture does not open SQLite to infer an outcome.
- If a future ADK event omits `usage_metadata`, `usage.status` stays `unknown`. This smoke happened to include it.
- If a provider call ID is absent, it stays `null` and pairing uses `association_key`. This smoke had a provider ID.
- Git `dirty=true` means the commit hash alone does not identify this exact code. Source-file hashes are also stored.
- Streamlit live capture was not exercised in this smoke (mocked Streamlit tests were).
- TRACE-S01–TRACE-S20 were not run.

## Agent and retrieval behavior unchanged

- Preview instruction text was not edited
- `preview_classification_search` retrieval code and corpus files were not edited
- Execution limits remain 8 LLM calls and 90 seconds
- Streamlit presentation and approval controls remain the same; capture is an additional persist step
- Pinecone `aeacus_review_agent` is unchanged and is excluded from this JSONL baseline
- MCP, SequentialAgent, and LangGraph runners were not edited
- Offline configuration check and existing retrieval/UI/approval tests passed after the capture change
