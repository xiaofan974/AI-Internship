# AeacusAI — Week 3 submission draft

## What it does

AeacusAI takes a plain-language AI system description, searches a pinned EU AI Act classification subset, and returns a cited **provisional** reading with missing facts called out. It does not certify compliance.

## Stack and demonstrated tool

- **Stack:** Google ADK, configured Gemini (`gemini-3.8-flash` unless `AEACUS_MODEL` is set), Streamlit UI.
- **Agent:** `aeacus_preview_agent` — one agent, no sub-agents.
- **Tool:** `preview_classification_search` — read-only lexical search over local statutory JSON, with complete parent-context expansion (Article 6, Annex III, Article 113).
- **Live preview needs** `GOOGLE_API_KEY` only. OpenAI/Pinecone credentials are not required for this path.

## Think / Act / Observe / Final

The bounded runner (`max_llm_calls=8`, 90s timeout) streams observable events:

- **THINK** — selected next action only (no hidden model thoughts)
- **ACT** — tool name and the query the model chose
- **OBSERVE** — tool status, matched labels, context labels
- **FINAL** or **FAILED**

The Streamlit app shows that trace as it happens, then the provisional finding, missing facts, and expandable complete sources.

## Why an agent is appropriate

AeacusAI is a bounded agent because the model chooses a retrieval query, observes tool evidence and decides whether to refine its search before producing a cited assessment. A fixed one-shot prompt cannot choose, inspect, and optionally refine retrieval against the returned records.

## Classification-subset limitation

This demo covers only the pinned consolidated classification subset dated 27 July 2026 (19 Article 6 / Annex III children, plus complete Article 6, Annex III, and Article 113 context). It is not a whole-Act review. A missing match does not mean no obligation exists. Full-compliance, conformity, and “not prohibited” conclusions are out of scope.

## Stretch items (implemented and tested only)

Claimed because they exist in code and were checked offline/mocked:

- Local lexical retrieval with complete parent/context expansion (`test_context_preview.py`)
- Citation display: short labels in the answer, full IDs in evidence, unknown IDs flagged not deleted (`test_preview_presentation.py`, `test_streamlit_app.py`)
- Streamlit session behaviour: no model call until Run, result preserved on rerun, failure does not keep the previous answer (`test_streamlit_app.py`)
- Bounded runner safeguards in `run_review.py` (call limit, timeout, hidden-thought filtering, redaction)

**Not claimed**

- Prompt-injection resistance — instructions treat submitted/retrieved text as untrusted evidence. Instructions alone are not a successful injection test.
- Live Gemini format/grounding after the later presentation and citation-UI changes — one earlier live recruitment preview was run; it is separate from the offline/mocked checks below. No additional model calls were made for this submission pack.
- Pinecone / OpenAI retrieval — present in the package, not the demonstrated Week 3 path, and not required to reproduce this demo.

## Reproduce

```bash
cd capstone/aeacusai
# GOOGLE_API_KEY in .env for a live UI run only
.venv/bin/python -m unittest test_context_preview.py test_preview_presentation.py test_streamlit_app.py test_retrieval.py
.venv/bin/streamlit run streamlit_app.py
```
