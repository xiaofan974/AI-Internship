# Week 4 Langfuse connection

Opt-in OpenTelemetry export for the primary single-agent ADK / direct-Python classification preview. Frozen Week 4 datasets, annotations, prompts, experiments, evaluation results, the timing renderer, and human approval controls were not modified. Other architectures were not instrumented. No historical traces, datasets, or hosted judges were uploaded.

## Dependency versions and environment

Separate environment: `capstone/aeacusai/.venv-langfuse`  
Python: 3.12.13  
Pins: `requirements-langfuse.txt`

Verified 2026-10-23:

| Package | Version |
| --- | --- |
| langfuse | 4.15.6 |
| openinference-instrumentation-google-adk | 1.0.4 |
| openinference-instrumentation | 0.1.71 |
| openinference-semantic-conventions | 0.1.41 |
| opentelemetry-api | 1.42.1 |
| opentelemetry-sdk | 1.42.1 |
| google-adk | 2.12.0 |
| google-genai | 2.32.0 |

Existing ADK and Gemini pins were not changed. The original `.venv` was not upgraded. Integration follows the current Langfuse ADK docs: `get_client()` / `Langfuse(...)`, `GoogleADKInstrumentor().instrument()`, `propagate_attributes`, `start_as_current_observation`, `flush()`, and Observations API v2 `api.observations.get_many(trace_id=...)`. The obsolete v2 client (`trace()`, `span()`, `generation()`, `api.trace.list`) was not used.

## Configuration status

Loaded from `capstone/aeacusai/.env` by project path, without overriding process environment variables. `.env` was not overwritten. `.env.example` has placeholders plus `AEACUS_LANGFUSE_TRACING=0`.

| Name | Status |
| --- | --- |
| LANGFUSE_PUBLIC_KEY | configured |
| LANGFUSE_SECRET_KEY | configured |
| LANGFUSE_BASE_URL | configured |
| AEACUS_LANGFUSE_TRACING | missing in `.env`; set to `1` only in the smoke process |
| GOOGLE_API_KEY | configured |
| AEACUS_MODEL | configured |

Export is opt-in. Streamlit reruns reuse a single instrumentor instance.

## Offline results

```text
.venv/bin/python -m unittest test_langfuse_preview test_streamlit_app \
  test_trace_store test_timing_scope test_preview_presentation \
  test_review_register -q
```

Result: **58 tests, 0 failures.**

`.venv-langfuse/bin/python -m unittest test_langfuse_preview -q`: **9 tests, 0 failures.**

Covered: placeholder/missing vs configured names, opt-in default off, secret redaction, hidden-thought filtering, calibration of confusion-matrix-unrelated assessment/approval tests, idempotent instrumentation, no MCP/dual/LangGraph/SQLite/provider imports in the exporter.

Read-only `auth_check()`: ok.

Frozen source hashes unchanged:

- `week4_adk_preview_v1.jsonl` SHA-256 prefix `29871169…04db1`
- `week4_adk_preview_f1_v2.jsonl` SHA-256 prefix `3b1fa10c…f848`
- `evals/week4/checkers.py` SHA-256 prefix `330fce7b…84b33`

## Live recruitment smoke

One run. Existing limits: `max_llm_calls=8`, `timeout_seconds=90`. No retries. Review register not opened. Outside both frozen 20-run datasets.

| Field | Value |
| --- | --- |
| Local run ID | `ecbc749c-cf24-4f05-b25e-a6983880302a` |
| Execution status | ok |
| Langfuse trace ID | `cfb48c13fe76b05429e204373c2ff73e` |
| Langfuse URL | https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/cfb48c13fe76b05429e204373c2ff73e |
| Flushed | true |
| Retrieved | true |
| Local JSONL | `data/local/traces/week4_langfuse_connection_smoke.jsonl` |

The first Observations API poll after flush returned only `preview_classification_search` and `call_llm` (ingestion lag). A follow-up read of the **same** trace ID, with no new model call, returned 9 observations and none of the required application names were missing.

Follow-up observation names:

- `aeacus-adk-preview` (AGENT) — input, instruction/config provenance, delivered output
- `application-evidence` (RETRIEVER) — retrieved matches/context and evidence hashes
- `timing-renderer` (SPAN) — raw model answer vs delivered timing-rendered answer
- `preview_classification_search` (TOOL)
- `call_llm` (GENERATION), twice
- `invoke_agent aeacus_preview_agent` (AGENT)
- `agent_run [aeacus_preview_agent]` (AGENT)
- `invocation [aeacusai_review]` (CHAIN)

Local JSONL capture also saved. A Langfuse export failure is surfaced in Streamlit/CLI without changing the assessment or approval outcome.

## Captured / missing observations and limitations

Captured on the verified trace: user input; frozen instruction and configuration provenance; actual model calls; search tool calls; retrieved context with text SHA-256 hashes; raw model answer; timing-renderer activity and delivered answer; ADK usage on generation spans.

Not claimed here: token usage completeness beyond what ADK/OpenInference emitted; hidden-thought filtering inside ADK generation payloads beyond Langfuse `mask` / `mask_otel_spans`; legal certification; model-quality improvement.

Limitations:

- Export is opt-in (`AEACUS_LANGFUSE_TRACING`). Default Streamlit/CLI runs do not send traces.
- OpenTelemetry ingestion can lag; a non-empty first poll is not a complete observation set.
- MCP, SequentialAgent dual, and LangGraph paths are not instrumented in this checkpoint.
- Application-layer observations are redacted and thought-filtered before export. ADK/OpenInference spans are masked for known secrets and thought-named attributes, but the instrumentor still owns model I/O shape.
- This checkpoint does not import historical traces, upload datasets, enable hosted judges, or rerun the 20 frozen scenarios.
