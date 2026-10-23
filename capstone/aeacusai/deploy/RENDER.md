# Render settings for aeacusai-demo

Create a **new** web service. Do not change `ai-internship-5ei0.onrender.com`.

These settings are prepared only. This document does not deploy, commit, or push.

## Dashboard

| Field | Value |
| --- | --- |
| Service type | Web Service |
| Name | `aeacusai-demo` (subject to availability) |
| Repository | this Git repository, after the capstone files and `deploy/week4_offline/` bundle are committed |
| Branch | `feat/aeacusai-capstone` once it is pushed, or the branch that contains `capstone/aeacusai` |
| Root Directory | `capstone/aeacusai` |
| Runtime | Python 3 |
| Build command | `pip install --upgrade pip && pip install -r requirements.txt` |
| Start command | `bash deploy/start.sh` |
| Instance | Free is enough for a demo; the service will sleep when idle |

The start command materializes the Week 4 bundle into `data/local/`, then runs:

`streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port $PORT --server.headless true`

Python version files in the root directory: `.python-version` and `runtime.txt` (`3.12.13`). If Render rejects that patch, set `PYTHON_VERSION` to the nearest 3.12.x.

## Environment-variable names only

Required for a live Assessment run:

- `GOOGLE_API_KEY`
- `PORT` (set by Render)

Recommended:

- `AEACUS_MODEL`

Keep Langfuse opt-in off unless you later install the separate Langfuse pins:

- `AEACUS_LANGFUSE_TRACING`
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_BASE_URL`

Do not set OpenAI or Pinecone keys on this service. The Week 4 workspace and the lexical classification preview do not use them.

Do not upload `.env`, `.venv*`, or `review_register.sqlite`.
