# Week 4 final evidence UI

The existing Streamlit **Week 4 evaluations** workspace now loads frozen judge calibration and validation artifacts, derives metrics from saved predictions and reviewed labels, and keeps those scores separate from the earlier timing, F1-experiment, and S19 findings. Assessment stays idle unless **Run assessment** is clicked. No new inference was run for this UI pass.

## Locations

| Path | Role |
| --- | --- |
| `evals/week4/evaluations_view.py` | Offline bundle, derived judge metrics, no provider calls |
| `streamlit_app.py` | Workspace rendering; Assessment path unchanged |
| `test_week4_evaluations_view.py` | Metric, provenance, mismatch, and isolation tests |
| `test_streamlit_app.py` | Evaluations UI plus assessment/approval regression |
| `WEEK4_SUBMISSION.md` | Concise Week 4 note and screenshot checklist |
| `reports/week4_f1_judge_v1_calibration.json` | Frozen v1 calibration report |
| `reports/week4_f1_judge_v2_calibration.json` | Frozen v2 calibration report |
| `reports/week4_f1_judge_validation.json` | Frozen validation report |
| `data/local/evals/week4/judge/` | Gitignored versioned predictions |
| `data/local/evals/week4/golden/f1_v1/` | Gitignored golden payloads |

## Derived validation (default)

Computed from saved predictions joined to reviewed labels, then checked against the frozen validation report. Not hardcoded.

| Version | TP | FN | TN | FP | TPR | TNR | Coverage |
| --- | --- | --- | --- | --- | --- | --- | --- |
| v1 | 0 | 5 | 15 | 0 | 0/5 (0%) | 15/15 (100%) | 20/20 valid |
| v2 | 0 | 5 | 15 | 0 | 0/5 (0%) | 15/15 (100%) | 20/20 valid |

Confusion-matrix orientation: rows = reviewed F1 failure / reviewed F1 pass; columns = judge fail / judge pass.

Decision shown in the UI:

> Both judges missed every reviewed validation failure. Keep both versions outside detection, approval, and release gates.

100% TNR is labeled as not overall success. No 75% agreement headline is computed.

## Calibration (separate)

| Version | TPR | TNR |
| --- | --- | --- |
| v1 | 0/5 | 15/15 |
| v2 | 2/5 | 15/15 |

v2 examples reused calibration cases. That calibration movement did not transfer to validation. The two splits are not combined into one headline score.

## Golden-dataset provenance (from the frozen manifest)

- 40 original outputs from 20 paired fictional dogfood scenarios
- 10 F1 failures / 30 passes
- Calibration: 10 groups / 20 outputs
- Validation: 10 different groups / 20 outputs
- AI-assisted labels reviewed by Lily
- Same model family for agent and judge
- Validation held out from judge refinement, not unseen capstone scenarios
- Full payloads remain local and gitignored

## Preserved findings

- Timing repair chart: 18/20 raw → 20/20 delivered, described as an application-layer replay of saved traces.
- Unsuccessful F1 prompt experiment: 5/20 → 5/20; parent instructions restored.
- Original TRACE-S19 retrieval-budget failure (6 calls vs budget 2) is unchanged.
- No overall quality or compliance score.

Offline **Run offline checks** may recompute checker/timing metrics and re-derive judge metrics from saved predictions. It does not invoke a judge or collect new traces.

## Verification

```text
.venv/bin/python -m unittest test_week4_evaluations_view test_streamlit_app \
  test_timing_scope test_preview_presentation test_review_register \
  test_week4_codify test_trace_store -q
```

Result: **72 tests, 0 failures.**

Covered:

- confusion-matrix orientation and TPR/TNR denominators
- calibration/validation separation
- empty judge artifacts and report mismatches
- no provider, retrieval, or SQLite access in the evaluations module
- unchanged assessment and approval behaviour

Browser check on `http://127.0.0.1:8501/` (no **Run assessment** click):

- Assessment default: empty system description, **Run assessment** disabled
- Timing chart: 18/20 raw → 20/20 delivered; caption is an application-layer replay of 20 saved traces
- Unsuccessful F1 experiment: 5/20 → 5/20; candidate not adopted
- Original TRACE-S19: 6 calls against budget 2
- Validation (default) v1 and v2: TP=0, FN=5, TN=15, FP=0; TPR 0/5 (0%); TNR 15/15 (100%); coverage 20/20 valid
- Confusion matrices: rows reviewed F1 failure / pass; columns judge fail / pass; cells `[[0, 5], [0, 15]]`
- Decision: both judges missed every reviewed validation failure; keep both versions outside detection, approval, and release gates
- Calibration expander (separate): v1 TPR 0/5, TNR 15/15; v2 TPR 2/5, TNR 15/15; examples reused calibration cases; improvement did not transfer
- Provenance expander: 40 outputs / 20 paired scenarios; 10 fail / 30 pass; 10+10 groups; Lily-reviewed labels; same model family; held out from refinement, not unseen capstone scenarios
- False-negative inspector defaulted to validation / v1 / TRACE-S08 with input, answer excerpt, reviewed fail vs judge pass, judge reason, and source association
- Returned to Assessment idle: empty finding, **Run assessment** still disabled

## Limitations

- This UI reads local frozen files. Missing or mismatched artifacts surface as errors, not success cards.
- Judge validation is a 20-output split with 5 labeled failures. It does not establish a reliable detector.
- Evaluation does not qualify either judge as an approval or release gate.
