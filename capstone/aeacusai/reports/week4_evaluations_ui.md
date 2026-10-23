# AeacusAI Week 4 Evaluations view

The Streamlit app now has a second workspace, **Week 4 evaluations**, beside the existing assessment interface. Assessment, approval, and the current visual theme are unchanged. The new view is offline: it does not call a model, retrieve sources, or open the review register.

## How to open the view

1. Start the existing app from `capstone/aeacusai`:

   ```text
   .venv/bin/streamlit run streamlit_app.py --server.port 8501 --server.address 127.0.0.1
   ```

2. Open `http://127.0.0.1:8501/`.
3. The default workspace is **Assessment**. No assessment runs until **Run assessment** is clicked.
4. Select **Week 4 evaluations** in the Workspace control.

The existing Streamlit server on port 8501 was refreshed in place. No assessment was triggered automatically.

## Changed files

| File | Change |
| --- | --- |
| `evals/week4/evaluations_view.py` | New. Loads frozen taxonomy, annotations, assertion results, and timing-repair reports; builds the three findings from actual file contents; reruns frozen checkers and the timing formatter against saved traces. |
| `streamlit_app.py` | Workspace radio; Evaluations rendering; **Run offline checks**. Assessment and approval paths are otherwise unchanged. |
| `test_week4_evaluations_view.py` | New offline tests for counts, provenance, isolation, real replay, and missing/tampered artifacts. |
| `test_streamlit_app.py` | Evaluations UI tests plus a regression that the assessment/approval path still works. |
| `reports/week4_evaluations_ui.md` | This report. |

New evaluation output is written only to `evals/week4/results/offline_recompute/`. Raw traces, manifests, annotations, checkers, and historical reports are not rewritten.

## Findings shown

The view keeps three findings separate. It does not compute an overall quality or compliance percentage. Candidate F2 remains unreviewed.

### A. Timing qualification checks

Read from the frozen parent assertion results and the timing-repair report, not from hardcoded success values.

- Title: Timing qualification checks
- Raw answers: 18/20 passed (90%)
- Delivered after repair: 20/20 passed (100%)
- Change: +10 percentage points
- Description: Application-layer replay of 20 saved live traces. No new model or retrieval calls.
- Checker: `deferred_date_qualifications_v1` in suite `week4_codify_v1`
- Formatter: `aeacus.timing_scope.v1` version `1`
- Unchanged assertion: `s19_retrieval_budget_v1`

A compact before/after bar chart shows the two passed counts.

### B. F1 prompt experiment — unsuccessful

- Human-reviewed F1 failures: 5/20 → 5/20
- Recoveries: TRACE-S08, TRACE-S20
- Regressions: TRACE-S01, TRACE-S15
- Persistent: TRACE-S04, TRACE-S09, TRACE-S13
- The candidate was not adopted; parent instructions were restored
- The timing renderer did not resolve F1
- Candidate F2 remains unreviewed

### C. Retrieval regression check

- Original TRACE-S19: 6 `preview_classification_search` act events against a budget of 2
- Timing repair leaves this unchanged
- Applicability denominator is 1, with 19 excluded
- The rejected F1 candidate’s 1-call TRACE-S19 result is labeled incidental and belonging to that separate experiment

The four-category parent taxonomy is shown with priority weights and human-reviewed failure counts (5 / 5 / 2 / 1). Those counts are not summed into an overall score.

## Scenario inspector

Default scenario: **TRACE-S02**. The selector shows:

- scenario input
- original raw model text
- application-rendered delivered text
- separate human and automated failure reasons
- Article 113 evidence and source provenance (record ID, snapshot, text hash, formatter version)

Full raw and delivered texts stay in expanders.

## Run offline checks

The button reruns the existing frozen assertions and `aeacus.timing_scope.v1` against saved `week4_adk_preview_v1` traces.

- No provider calls, no fresh retrieval, no new agent collection
- Historical traces, manifests, annotations, and reports stay in place
- New output is stored under `evals/week4/results/offline_recompute/` with input hashes, checker hash, formatter id/version, and assertion summaries
- The page labels **loaded historical results** versus **freshly recomputed** results
- Missing files, hash mismatches, and evaluation errors render as error messages, not success cards

## Verification

```text
.venv/bin/python -m unittest test_week4_evaluations_view test_streamlit_app \
  test_timing_scope test_preview_presentation test_review_register \
  test_week4_codify test_trace_store -q
```

Result: **69 tests, 0 failures.**

Covered:

- actual 18/20 and 20/20 timing counts, 5/20 F1 counts, S19 6-vs-2 with denominator 1
- human labels kept separate from automated checkers
- `Run offline checks` calls `replay_parent_traces`
- missing or tampered artifacts surface as errors
- `evaluations_view.py` does not import `review_register`, `preview_agent`, `retrieval`, `sqlite3`, or provider SDKs
- the Evaluations workspace does not invoke the assessment runner
- existing assessment and pending-review binding still pass

Browser check on `http://127.0.0.1:8501/`:

- Assessment is the default workspace; Run assessment stays idle
- Week 4 evaluations shows the three findings, TRACE-S02, raw vs delivered, and provenance
- Run offline checks switches the banner to freshly recomputed and writes a separate JSON file
- Returning to Assessment still shows an empty finding and does not start a run

Frozen parent and candidate traces, annotations, and checkers keep their previous SHA-256 values.

## Limitations

- The Evaluations view reads local frozen files. If those files are missing or hashed incorrectly, it shows errors and does not invent pass rates.
- Offline recomputes can write more than one timestamped JSON file. They do not replace `week4_codify_baseline_v1.json` or `week4_timing_repair_eval.json`.
- F1 remains unresolved. Candidate F2 is unreviewed. Source review and ingestion gates stay closed.
- MCP, SequentialAgent, and LangGraph results are not shown here.
