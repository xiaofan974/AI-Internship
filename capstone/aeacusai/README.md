# AeacusAI — EU AI Act Classification Preview (Week 3)

> **“When a reviewer submits an AI system description, AeacusAI searches a curated EU AI Act corpus, decides whether further evidence is needed, and drafts a cited preliminary review with explicit unknowns.”**

AeacusAI is a bounded agent because the model chooses a retrieval query, observes tool evidence and decides whether to refine its search before producing a cited assessment.

This Week 3 demo is a single-agent Google ADK preview over a pinned classification subset. It is not a full-Act review and does not grant compliance, conformity, or “not prohibited” conclusions.

---

## Stack

- **Google Agent Development Kit (ADK)** — one preview agent, no sub-agents
- **Configured Gemini model** — `gemini-3.8-flash` by default (`AEACUS_MODEL` may override)
- **Streamlit** — local UI (`streamlit_app.py`)
- **Bounded runner** — `run_review.py` (`max_llm_calls=8`, 90-second timeout)

OpenAI embeddings and Pinecone are **not** used on this demonstrated path. A separate `aeacus_review_agent` with `search_legal_sources` exists in the same package and is left unchanged; it is not required to run the preview.

---

## Demonstrated tool

`aeacus_preview_agent` has exactly one tool: `preview_classification_search(query: str) -> dict`.

That tool is a **read-only lexical search** over local statutory JSON:

- Ranks the 19 pending Article 6 paragraph / Annex III area children
- Expands **complete** same-snapshot parent and temporal context (Article 6, Annex III, Article 113)
- Returns structured `ok` / `no_matches` / `error` observations
- Makes no network, embedding, or Pinecone calls
- Does not change review or indexable flags and does not ingest records

---

## Pinned corpus scope

- Consolidated EU AI Act edition dated **27 July 2026**
- Snapshot: `T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715`
- Local files:
  - `records/classification_children_stage9.json` (19 children)
  - `records/consolidated_articles_stage4.json` (Article 6 and Article 113 parents)
  - `records/consolidated_annexes_stage5.json` (Annex III parent)

Coverage is limited to that Article 6 / Annex III classification subset plus Article 113 timing context. A missing match does not mean no legal obligation exists.

---

## Remaining limitations

- Records remain pending / not reviewed / not indexable.
- Original and consolidated editions stay separate; this preview uses the pinned consolidated subset only.
- The UI validates citations against records returned in the current run; it does not prove live-model grounding.
- Prompt instructions treat submitted and retrieved text as untrusted evidence. That is not a completed prompt-injection evaluation.
- This tool does not cover the whole EU AI Act (including prohibitions, provider/deployer duties outside classification, and other annexes).

---

## Preview setup

Only **`GOOGLE_API_KEY`** is required for a live Streamlit or CLI preview. OpenAI and Pinecone credentials are not required for this path.

```bash
cd capstone/aeacusai
cp .env.example .env   # set GOOGLE_API_KEY; leave OpenAI/Pinecone unused
```

Use the project virtualenv at `capstone/aeacusai/.venv` (Python 3.12) with the pins in `requirements.txt`.

Offline checks (no Gemini calls):

```bash
.venv/bin/python -m unittest \
  test_context_preview.py \
  test_preview_presentation.py \
  test_streamlit_app.py \
  test_retrieval.py
```

---

## UI entry point

From `capstone/aeacusai/`:

```bash
.venv/bin/streamlit run streamlit_app.py
```

Local URL: `http://127.0.0.1:8501/`

Model calls start only after **Run assessment**. Load the recruitment example, then run once. The visible trace is THINK / ACT / OBSERVE / FINAL. Evidence expanders show complete returned source text, labels, record IDs, and source URLs.

CLI equivalent (also live Gemini, optional):

```bash
.venv/bin/python run_classification_preview.py
```

---

## Project layout (preview path)

```text
capstone/aeacusai/
├── README.md
├── WEEK3_SUBMISSION.md
├── requirements.txt
├── .env.example
├── aeacus_agent/
│   ├── preview_agent.py      # Week 3 single-agent demo
│   ├── context_preview.py    # local lexical search + parent expansion
│   ├── agent.py              # separate Pinecone agent (not this demo)
│   └── retrieval.py          # Pinecone tool (not this demo)
├── streamlit_app.py
├── run_review.py
├── run_classification_preview.py
├── records/classification_children_stage9.json
├── records/consolidated_articles_stage4.json
├── records/consolidated_annexes_stage5.json
├── test_context_preview.py
├── test_preview_presentation.py
├── test_streamlit_app.py
└── test_retrieval.py
```
