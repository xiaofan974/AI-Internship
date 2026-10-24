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

The UI opens on **Assessment**. Model calls start only after **Run assessment**. Load the recruitment example, then run once. The visible trace is THINK / ACT / OBSERVE / FINAL. Evidence expanders show complete returned source text, labels, record IDs, and source URLs. Opening the app does not write project memory.

---

## Project memory

The **Project memory** workspace stores user-declared context for a private workspace. It is not statutory evidence, not a classification, and not human approval. The model cannot write memory or approve a review.

When a workspace is connected, **Run assessment** freshly retrieves unexpired facts and supplies the three allowed fields to the primary ADK preview as structured user-declared context. The no-workspace path is unchanged. `project_name` is untrusted data, not instructions. `declared_actor_role` is a declaration, not verified legal status. Current explicit form preferences override stored values for that run only and are shown as conflicts; stored facts are not overwritten. A French language preference applies to explanatory prose while the English timing headings and original statutory quotations stay in place. Mandatory retrieval, execution limits, and approval controls are unchanged. Unavailable memory is disclosed; cached recall is never used as a fallback. Switching or disconnecting a workspace clears assessment and pending-review state for that session.

1. **What is stored.** Only `project_name`, `declared_actor_role` (`provider` / `deployer` / `both` / `unknown`), and `preferred_response_language` (`English` / `French`). Source is always `user_declared`. Credentials, tool dumps, legal conclusions, and approvals are rejected.

2. **When it is written.** Only after an explicit UI confirmation and **Save project memory**. The application supplies `application_confirmed_user`. Model answers, retrieved documents, and the review register cannot write memory.

3. **Where it is stored.** External Postgres (`AEACUS_MEMORY_DATABASE_URL`, schema `aeacus_memory`). If that store is unconfigured or unavailable, the UI returns `memory_unavailable`. Streamlit session state and local files are not a substitute.

4. **How it is retrieved.** **Recall saved memory** reads Postgres for the connected workspace. The UI is written so a later session that enters only the private workspace code can recall the same facts. Clearing session state in the same tab is not a new process. **Run assessment** performs its own fresh `list_facts` read and does not reuse the recalled session list.

5. **When it is forgotten.** Explicit **Delete saved field** removes that field, including superseded history. Active facts also stop being returned once `expires_at` has passed (default 180 days, `AEACUS_MEMORY_TTL_DAYS`). Expiry is enforced at read time. There is no scheduled job that physically deletes expired rows.

The workspace code is a cryptographically random private credential. Keep it privately. Do not put it in URLs, logs, traces, reports, or screenshots.

**Verified, process-level only.** Two separate Python processes wrote and recalled the three facts on live Postgres. A later two-process run supplied those facts to one assessment through the same integration path as Streamlit **Run assessment**. Isolated browser Session A / Session B and any application deployment were **not** performed. Details: `reports/week5_memory_postgres_checkpoint.md`, `reports/week5_memory_ui.md`, `reports/week5_memory_agent_integration.md`.

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
