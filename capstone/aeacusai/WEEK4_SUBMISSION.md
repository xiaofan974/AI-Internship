# AeacusAI — Week 4 submission note

Google ADK classification preview with Streamlit, plus opt-in Langfuse tracing. This is an offline evaluation record from frozen traces. It is not legal certification, not a model-quality improvement claim, and not evidence of a reliable F1 detector.

Labels in this package are AI-assisted judgments accepted by Lily. They are not independent expert legal adjudication.

Langfuse project links may require authorized access. They are not public.

## Stack

- Primary path: Google ADK (`aeacus_preview_agent`) and Streamlit review workspace.
- Tracing: opt-in Langfuse OpenTelemetry export for the primary ADK preview only (`AEACUS_LANGFUSE_TRACING=1` in the smoke process). Default Streamlit and CLI runs do not send traces.
- Local JSONL remains the source of record.

## What is live versus imported

Distinguish these surfaces:

| Kind | What it is | What it is not |
| --- | --- | --- |
| Genuine live Langfuse trace | One recruitment smoke with real model and search-tool observations | Not one of the 20 frozen baseline traces |
| Historical import | Frozen `week4_adk_preview_v1` traces uploaded after the fact | Not new inference |
| Timing comparison | Application-layer replay of saved observations | Not 20 new live runs and not improved model reasoning |
| F1 comparison | Saved parent versus rejected-candidate raw answers | Not a timing repair and not new live executions |
| Judge import | Saved frozen judge predictions replayed onto golden items | Not a new judge run, hosted evaluator, or refinement |

Candidate golden items (`week4_adk_preview_f1_v2`) have no historical Langfuse source associations. Only parent traces were historically imported.

## Baseline traces, taxonomy, and deterministic checks

Twenty original live parent traces (`week4_adk_preview_v1`) were annotated against taxonomy F1–F4. Lily accepted the AI-assisted labels.

| Category | Title | Parent failures |
| --- | --- | --- |
| F1 | Classification relies on an unstated premise or extends to an underspecified product | 5 |
| F2 | Explanation broadens or invents a statutory condition or consequence | 5 |
| F3 | Timing summary omits the specific sections whose application is deferred | 2 |
| F4 | Searches continue after relevant child passages and complete context are available | 1 |

These counts are not an overall quality or compliance score. Candidate F2 remains unreviewed.

Two frozen checkers, no human labels:

- `deferred_date_qualifications_v1` — explicit markers in Timing and scope.
- `s19_retrieval_budget_v1` — TRACE-S19 only; at most two `preview_classification_search` act events.

Original TRACE-S19 remains a failure: 6 search acts against a budget of 2. Timing repair does not change retrieval.

## Timing repair (application-layer replay)

The source-backed formatter `aeacus.timing_scope.v1` was replayed on the 20 saved parent traces. No new model or retrieval calls.

- Raw model text: **18/20** passed the deferred-date checker (fails TRACE-S02, TRACE-S20).
- Delivered after repair: **20/20** passed.
- Label this as a replay of saved traces, not a new live-run improvement.

F1 and original S19 are unchanged by this renderer.

## F1 prompt experiment

One instruction change produced candidate `week4_adk_preview_f1_v2`. Human-reviewed F1 failures stayed **5/20 → 5/20** (recoveries S08, S20; regressions S01, S15; persistent S04, S09, S13). The candidate was rejected. Parent instructions were restored.

## Golden dataset

`week4_f1_golden_v1` / `week4_f1_split_v1`: **40 original outputs from 20 paired scenarios** (parent and F1-candidate versions). This is not 40 independent scenarios. Each split has 20 outputs from 10 paired scenarios: 5 reviewed F1 failures and 15 reviewed passes. Both versions of a scenario stay in the same split.

Labels are AI-assisted judgments accepted by Lily. Full payloads stay local and gitignored. Validation cases were held out from judge-prompt refinement; they are not unseen capstone scenarios.

## Judge calibration and validation (negative result)

Frozen judges v1 and v2 used saved predictions only. No further prompt refinement after validation. Positive class is F1 failure.

**Calibration (not held-out for v2):** v1 TPR 0/5, TNR 15/15; v2 TPR 2/5, TNR 15/15. v2 examples reused calibration cases. That movement did not transfer.

**Validation (20/20 valid each):** both versions TP=0, FN=5, TN=15, FP=0; TPR **0/5**; TNR 15/15. Both judges detected **0/5** reviewed validation failures. 100% TNR is not overall success.

Both judges remain outside detection, approval, and release gates.

## Verified Langfuse links

Taken from the saved import reports. Authorized Langfuse access may be required.

| Surface | Kind | Link |
| --- | --- | --- |
| Live smoke trace | Genuine live tracing (model + search-tool observations) | https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/cfb48c13fe76b05429e204373c2ff73e |
| Timing comparison | Historical raw 18/20 vs application-layer replay 20/20 | https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/datasets/cmvl38qq70005ad0n1jlmyvuk/compare?runs=22a7a562-ddc9-41ae-9829-1c4fb94d6c09&runs=0559cdda-847b-4f3b-9727-8f4b53620820 |
| F1 comparison | Historical parent vs rejected candidate; both 5/20 F1 | https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/datasets/cmvl38qq70005ad0n1jlmyvuk/compare?runs=f69dda5b-a214-442a-9a69-9354f7854f59&runs=f7082e56-ac7c-4119-8ee7-cc6dc2550d78 |
| Calibration judges | Historical replay of frozen v1 vs v2 predictions | https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/datasets/cmvl5jrmj0010ad0kobcprfob/compare?runs=c7ec1923-ad05-4b60-9585-d6c4923e02be&runs=922aa4d2-ac70-4747-b117-930d7613a7e5 |
| Validation judges | Historical replay; both TPR 0/5 | https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/datasets/cmvl5js41002nad0jjxk3p587/compare?runs=1cda5b79-62ee-4d4f-9939-b8791039eedf&runs=6ac6dabb-a6df-4deb-82c7-2da5e75296b4 |

Supporting dataset URLs:

- Baseline dataset `week4_adk_preview_v1`: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/datasets/cmvl38qq70005ad0n1jlmyvuk
- Calibration `week4_f1_calibration_v1`: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/datasets/cmvl5jrmj0010ad0kobcprfob
- Validation `week4_f1_validation_v1`: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/datasets/cmvl5js41002nad0jjxk3p587

Source reports: `reports/week4_langfuse_connection.md`, `reports/week4_langfuse_timing_comparison.md`, `reports/week4_langfuse_f1_comparison.md`, `reports/week4_langfuse_judge_import.md`.

## Still unresolved

- F1: 5 parent failures remain; the instruction candidate and both judges failed to resolve them.
- F2: 5 parent failures; candidate F2 unreviewed.
- Original TRACE-S19 retrieval-budget failure remains.

## Screenshot checklist

1. Genuine live Langfuse trace showing model and search-tool observations — use the smoke trace above (`call_llm` and `preview_classification_search`). This is the only genuine live tracing screenshot.
2. Langfuse timing comparison showing 18/20 versus 20/20 — use the timing comparison link. Say that this is application-layer replay, not new inference.
3. Existing Streamlit evaluations workspace showing results and provenance — **Week 4 evaluations**; do not click **Run assessment**.
4. Judge validation evidence showing TPR 0/5 and the rejection decision — Streamlit evaluations and/or the validation comparison. Both judges missed every reviewed validation failure and remain outside detection, approval, and release gates.

Optional: F1 comparison showing the unsuccessful prompt experiment (5/20 → 5/20; candidate rejected).

## Maven submission note

Copy below.

```text
AeacusAI Week 4 — Google ADK + Streamlit classification preview, with opt-in Langfuse tracing.

20 original baseline traces, reviewed F1–F4 taxonomy, and two deterministic checks. Labels are AI-assisted judgments accepted by Lily, not independent expert legal adjudication.

Timing repair: 18/20 raw → 20/20 delivered. Application-layer replay of saved traces; no new model or retrieval calls.

F1 prompt experiment: 5/20 failures → 5/20. Candidate rejected; parent instruction restored.

Golden dataset: 40 outputs from 20 paired scenarios (not 40 independent scenarios). Candidate golden items have no historical Langfuse source associations.

Both frozen judges detected 0/5 reviewed validation failures (TPR 0/5). They remain outside detection, approval, and release gates. Calibration improvement did not transfer.

Verified Langfuse links (authorized access may be required):
- Live smoke (genuine tracing): https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/cfb48c13fe76b05429e204373c2ff73e
- Timing 18/20 vs 20/20: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/datasets/cmvl38qq70005ad0n1jlmyvuk/compare?runs=22a7a562-ddc9-41ae-9829-1c4fb94d6c09&runs=0559cdda-847b-4f3b-9727-8f4b53620820
- F1 comparison: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/datasets/cmvl38qq70005ad0n1jlmyvuk/compare?runs=f69dda5b-a214-442a-9a69-9354f7854f59&runs=f7082e56-ac7c-4119-8ee7-cc6dc2550d78
- Calibration judges: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/datasets/cmvl5jrmj0010ad0kobcprfob/compare?runs=c7ec1923-ad05-4b60-9585-d6c4923e02be&runs=922aa4d2-ac70-4747-b117-930d7613a7e5
- Validation judges: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/datasets/cmvl5js41002nad0jjxk3p587/compare?runs=1cda5b79-62ee-4d4f-9939-b8791039eedf&runs=6ac6dabb-a6df-4deb-82c7-2da5e75296b4

Not legal certification. Not a model-quality or reliable-F1-detector claim.
```

## Reproduce (offline)

```text
cd capstone/aeacusai
.venv/bin/python -m unittest test_week4_evaluations_view test_streamlit_app \
  test_week4_f1_judge_v1 test_week4_f1_judge_v2 test_week4_f1_judge_validation -q
.venv/bin/streamlit run streamlit_app.py --server.port 8501 --server.address 127.0.0.1
```

Open **Week 4 evaluations**. Do not click **Run assessment**.
