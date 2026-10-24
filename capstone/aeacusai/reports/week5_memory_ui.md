# Week 5 project memory UI

Verified 2026-10-24 on `feat/aeacusai-memory`. Assessment remains the default workspace. Opening the app does not run the model or write memory. Memory is not wired into the assessment agent; that is the next checkpoint. Human approval and the review register were not written. Frozen Week 4 artifacts were not changed. No dependency upgrades, commits, pushes, or deployments.

This report separates **mocked UI tests** from **real browser / database checks**. Unperformed checks are labelled.

Workspace codes, connection strings, and passwords are not recorded here and were not captured in screenshots.

## What was added

`streamlit_app.py` gained a third workspace, **Project memory**, beside Assessment and Week 4 evaluations.

- Default `ui_view` is still `Assessment`.
- The memory view uses `open_memory_store`, `generate_workspace_code`, `replace_fact`, `list_facts`, and `delete_fact` with `explicit_user_confirmation` and `application_confirmed_user`.
- The UI does not import `memory_postgres` directly. `preview_agent.py` and `review_register.py` still do not import project memory.

### Workspace access

Create a cryptographically random private code, or enter an existing one in a masked field. Copy explains that the code grants access and must be kept privately, and must not appear in URLs, logs, traces, reports, or screenshots. Connecting a different code, or Disconnect workspace, clears recalled facts and last backend results for that session.

### Confirmed writes

Exactly `project_name`, `declared_actor_role`, and `preferred_response_language`. Save project memory requires the confirmation checkbox. The page shows the real backend status (`replaced`, `unchanged`, `rejected`, `memory_unavailable`). Recalled rows show `user_declared`, saved time, and expiry. Delete saved field uses the same write gate.

### Cross-session recall

Recall saved memory calls `list_facts` on the store. Draft form values are not copied into the recalled list. The page states that clearing a tab is not a new process, and that a demo should save in one session, then open a **separate browser session**, enter only the workspace code, and recall.

## Mocked tests

`.venv/bin/python -m unittest test_memory_ui test_project_memory test_streamlit_app test_review_register test_prompt_injection test_week4_evaluations_view -v`

**53/53 passed.** Memory UI cases use `MockedMemoryDatabase` or `UnavailableMemoryStore`. They do not prove a second browser process or restart persistence.

| Check | Result |
| --- | --- |
| Opening the app stays on Assessment and does not write | pass |
| Save without confirmation → `rejected` / `explicit_user_confirmation_required`, no rows | pass |
| Fresh recall ignores stale form values; provenance `user_declared`; delete then recall | pass |
| Two AppTest sessions on one mocked store: isolation; disconnect clears cache | pass |
| Unavailable store shown; save/recall stay `memory_unavailable`; no session fallback | pass |
| Memory view has no Run assessment / approve controls | pass |
| Existing Streamlit, approval, prompt-injection, and Week 4 evaluation tests | pass |

`test_project_memory` still uses an in-process mock for durability policy. Those 15 tests passed after the UI import change (Streamlit may import `project_memory`, not `memory_postgres`).

## Real browser verification

Local Streamlit at `http://127.0.0.1:8501/` (no model click).

**Performed**

- First paint: Assessment radio checked; System description and Execution (“No agent activity yet”); Run assessment present and disabled; no memory write controls.
- After selecting Project memory: workspace-code password field; Create / Use / Disconnect; confirmed-write fields; Save, Delete, and Recall **disabled** until a workspace is connected; copy that memory is not statutory evidence, not classification, not human approval, and not read by the model yet; “Writes target the configured Postgres store when you confirm a save.”; recalled list empty; URL stayed `/` (no workspace code in the query string).

No workspace was created in the browser, so no code appeared on screen or in a screenshot.

**Unperformed**

- Separate-browser Session A save / Session B recall of fictional facts (not run here, to keep the workspace code out of tool arguments, logs, and screenshots). The UI copy describes that demo. Clearing session state in the same tab was not treated as proof.
- Live Postgres write/recall through the Streamlit widgets in this pass.

## Real database (prior checkpoint, not this UI pass)

The Week 5 two-process runner already proved durable recall on the live Railway Postgres proxy after an explicit migration: Process A confirmed three fictional facts and exited; Process B received only the workspace credential and database configuration and retrieved them; another workspace was empty; cleanup removed history. See `reports/week5_memory_postgres_checkpoint.md`. That check did not go through Streamlit.

## README

`README.md` now answers the five memory questions: what is stored, when written, where stored, how retrieved, and when forgotten. Expiry is described as read-time filtering of `expires_at` (default 180 days). The README does not claim a scheduled physical-deletion job.

## Files

- `streamlit_app.py` — Project memory workspace
- `test_memory_ui.py` — focused mocked UI checks
- `test_project_memory.py` — UI may import `project_memory`; agent and review register must not
- `README.md` — five memory questions
- `reports/week5_memory_ui.md`

Preserved: unrelated working-tree files, frozen Week 4 artifacts, review-register SQLite, and the existing Postgres deployment.
