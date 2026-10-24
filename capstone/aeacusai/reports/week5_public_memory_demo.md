# Week 5 public-browser memory demonstration

Recorded 2026-10-24 on `feat/aeacusai-memory`. This note documents a **manual** public-browser check only. It is not a process-level runner result and not a live-model assessment. No workspace code, connection string, or password is recorded here.

Public URL: `https://aeacusai-demo.onrender.com`

## What this is not

| Earlier check | What it proved | What it did not prove |
| --- | --- | --- |
| `reports/week5_memory_postgres_checkpoint.md` | Two Python processes wrote and recalled facts on live Postgres | A public browser session |
| `reports/week5_memory_agent_integration.md` | One live-model assessment used a fresh Postgres read of stored facts | A second isolated browser |
| `reports/week5_memory_ui.md` | Local Streamlit first paint and Project memory copy | Separate-browser save / recall |

Those earlier notes labelled isolated browser Session A / Session B as unperformed. This demonstration is that missing public-browser step.

## Manual evidence

A normal browser on the public URL created a private workspace, confirmed a save of the three allowed fields, and recalled them from Postgres.

A fresh Chrome Guest window then opened the same public URL with an empty session, entered only the workspace code, and used **Recall saved memory**. Draft form values and Streamlit session state were not treated as stored facts.

Recalled values in both sessions:

| Field | Value |
| --- | --- |
| `project_name` | Harbour Hiring Demo |
| `declared_actor_role` | deployer |
| `preferred_response_language` | French |

Source on every row: `user_declared`.

Original saved timestamps were identical in both sessions:

| Field | `created_at` (UTC) |
| --- | --- |
| `project_name` | `2026-10-24T14:53:12.944183+00:00` |
| `declared_actor_role` | `2026-10-24T14:53:15.807770+00:00` |
| `preferred_response_language` | `2026-10-24T14:53:16.326949+00:00` |

Expiry on each row was 180 days after that saved time. The Guest recall therefore used the original write, not a later rewrite.

## Screenshots

Desktop captures (not committed):

| File | Session |
| --- | --- |
| `Capture d’écran 2026-10-24 à 18.54.17.png` | Normal browser after confirmed save and recall; backend `listed`; three facts and original timestamps |
| `Capture d’écran 2026-10-24 à 18.58.12.png` | Chrome Guest (`Invité`) on `aeacusai-demo.onrender.com`; same three facts and the same original timestamps |

Neither capture is used as a statutory source. The workspace code does not appear in the address bar.

## Limits

This check did not run **Run assessment**, did not approve a review, and did not open the review register. It does not change frozen Week 4 artifacts.
