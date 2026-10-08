# Week 1 v2: FastAPI RAG Service

This is the Maven AI Engineering Bootcamp Week 1 v2 application, built across Sessions 1
and 2. It is a FastAPI RAG service: documents are ingested, chunked, embedded with OpenAI,
stored in Pinecone, retrieved for a question, and used to generate a grounded answer.

Session 1 structured-output validation, retry, and observability are preserved. `POST /ask`
still returns a Pydantic `Answer`, plus model, tokens, latency, estimated USD cost, and
validation attempts. Session 2 adds retrieval-augmented generation on top of that contract.

Streamlit is a demo client only. Retrieval and generation happen in FastAPI, not in the UI.

## Architecture

```text
document text
  → chunking (RecursiveCharacterTextSplitter, size 800, overlap 100)
  → OpenAI embeddings (text-embedding-3-small)
  → Pinecone (index maven-rag, namespace maven-session2)
  → retrieve top-k chunks
  → grounded generation (gpt-4o-mini by default)
  → server-side citation validation
```

Re-ingesting the same `document_id` deletes that document's existing vectors and replaces
them. Do not reuse `northwind-handbook` unless you intend to replace it.

## API Routes

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/ingest` | Chunk, embed, and upsert a document. Requires `X-Ingest-Key`. |
| `GET` | `/debug/retrieve` | Return retrieved chunks for a query. Requires `X-Ingest-Key`. |
| `POST` | `/ask` | Retrieve context and return a grounded, validated answer. |
| `GET` | `/health` | Liveness check. Does not call OpenAI or Pinecone. |

## Getting Started

Prerequisites: Git, Python 3.12, an OpenAI API key, and a Pinecone API key.

```bash
git clone https://github.com/YOUR-USERNAME/AI-Internship.git
cd AI-Internship/ai-engineering-bootcamp-v2/week-1v2
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On Windows PowerShell, activate with `.\.venv\Scripts\Activate.ps1`.

## Environment Variables

```bash
cp .env.example .env
```

Required:

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | Completions and embeddings |
| `PINECONE_API_KEY` | Vector index access |
| `INGEST_API_KEY` | Shared secret for `/ingest` and `/debug/retrieve` |

Optional / defaults from `.env.example`:

| Variable | Default |
| --- | --- |
| `PINECONE_INDEX_NAME` | `maven-rag` |
| `PINECONE_NAMESPACE` | `maven-session2` |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` |
| `RAG_CHUNK_SIZE` | `800` |
| `RAG_CHUNK_OVERLAP` | `100` |
| `API_BASE_URL` | Streamlit only; see below |

`.env` contains secrets and must never be committed. It is excluded by `.gitignore` and
`.dockerignore`. `.env.example` is safe to commit because it uses empty or placeholder
values.

## Running Locally

All commands run from `ai-engineering-bootcamp-v2/week-1v2`.

Start FastAPI:

```bash
source .venv/bin/activate
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok"}
```

Docs: `http://127.0.0.1:8000/docs`.

### Streamlit demo

`demo_page.py` has two tabs:

- **Ask documents** — `POST /ask`, answer, citations, refusals, and Session 1 metrics.
- **Ingest document** — `POST /ingest` with `X-Ingest-Key` from the local environment.

```bash
source .venv/bin/activate
python -m streamlit run demo_page.py
```

Open `http://localhost:8501`.

API base URL:

1. `API_BASE_URL` if set.
2. Otherwise the existing Render service (`https://ai-internship-5ei0.onrender.com`).
3. Override in the Streamlit sidebar (use `http://127.0.0.1:8000` for a local API).

For ingest, Streamlit reads `INGEST_API_KEY` from `.env` or Streamlit secrets. If the key
is missing, the UI shows a configuration error and does not send an unauthenticated request.
The key is never displayed.

## Example Requests

Ingest a document (replace the header value locally; do not commit it):

```bash
curl -sS -X POST http://127.0.0.1:8000/ingest \
  -H "Content-Type: application/json" \
  -H "X-Ingest-Key: $INGEST_API_KEY" \
  -d '{
    "document_id": "exampleco-remote-work",
    "source": "exampleco-synthetic-policies",
    "text": "ExampleCo employees may work remotely on Tuesday and Thursday only."
  }'
```

Successful response:

```json
{
  "document_id": "exampleco-remote-work",
  "chunks_indexed": 1,
  "status": "success"
}
```

Ask a grounded question. `question` is required. `model` defaults to `gpt-4o-mini`;
`force_bad` defaults to `false` and still demos Session 1 validation retry:

```bash
curl -sS -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"How many days per week can ExampleCo employees work remotely?"}' \
  | python -m json.tool
```

Inspect retrieved chunks:

```bash
curl -sS "http://127.0.0.1:8000/debug/retrieve?q=ExampleCo%20remote%20work&top_k=5" \
  -H "X-Ingest-Key: $INGEST_API_KEY"
```

## Citations and Refusals

Grounded answers cite retrieved chunk IDs such as `exampleco-remote-work:0`. The API
validates citations against retrieved chunks and does not accept fabricated IDs.

If the retrieved context does not contain enough evidence, `/ask` returns exactly:

```text
I don't have enough information to answer that.
```

Refusals must not include citations. Example unsupported question: "Does ExampleCo offer a
paid sabbatical after five years?"

Session 1 observability is still present on every `/ask` response: `model`, `tokens_used`,
`latency_ms`, `cost_usd`, and `attempts`. RAG responses also include `retrieved_chunk_ids`.

## Ingesting New Documents

1. Choose a new `document_id`. Reusing an existing ID replaces that document's vectors.
2. Send `POST /ingest` with `text`, `document_id`, optional `source`, and `X-Ingest-Key`.
3. Or use the Streamlit **Ingest document** tab with the same fields.
4. Confirm with `GET /debug/retrieve` or a grounded `/ask` question.

Sample files live in `sample_docs/`. Do not re-ingest `northwind-handbook`.

## ExampleCo Sample Corpus

`sample_docs/` is a synthetic demonstration corpus for a fictional company named
**ExampleCo**. It is not official Northwind material and not Maven course content.

Five policies were ingested as separate documents (`exampleco-remote-work`,
`exampleco-annual-leave`, `exampleco-expenses`, `exampleco-it-equipment`,
`exampleco-information-security`) so retrieval quality can be tested with known facts and
known refusals. See `sample_docs/README.md` for the question set.

## Retrieval Baseline

Measured on five synthetic-policy questions with the current 800/100 chunking:

| Metric | Result |
| --- | --- |
| Recall@5 | 80% |
| Hit@1 | 60% |
| MRR | 0.70 |

**Known limitation:** for the unused production-access question, the supporting evidence
ranked seventh (`exampleco-information-security:2`) under the current chunking
configuration, so it is outside the default top-5 retrieval window.

## Deploying to Render

The repository is a monorepo. Render must build from this subdirectory.

1. Push to GitHub without committing `.env`.
2. Create a **Web Service** and connect the repository.
3. **Runtime:** Python 3.
4. **Root Directory:** `ai-engineering-bootcamp-v2/week-1v2`
5. **Build Command:** `pip install --upgrade pip && pip install -r requirements.txt`
6. **Start Command:** `python -m uvicorn main:app --host 0.0.0.0 --port $PORT`
7. Set secret environment variables in Render: `OPENAI_API_KEY`, `PINECONE_API_KEY`,
   `INGEST_API_KEY`. Optionally set the Pinecone/RAG names from `.env.example`.
8. Optional health-check path: `/health`.

```bash
curl --fail-with-body --silent --show-error \
  https://YOUR-SERVICE.onrender.com/health
```

Point the local Streamlit **API base URL** at the Render origin (no `/ask` suffix).

`POST /ask` is public. `/ingest` and `/debug/retrieve` require `INGEST_API_KEY`.

## Tests

Mocked tests do not call OpenAI or Pinecone:

```bash
source .venv/bin/activate
python -m unittest -v test_ingest.py test_retrieve.py test_ask_rag.py test_demo_page.py
python smoke_test.py
```

`smoke_test.py` starts the API and checks `/health` and `/docs` without paid provider calls.

## Project Structure

```text
week-1v2/
├── README.md
├── main.py              # FastAPI: /ask, /ingest, /debug/retrieve
├── rag.py               # Chunking, embeddings, Pinecone
├── demo_page.py         # Streamlit Ask + Ingest client
├── test_demo_page.py    # Mocked Streamlit helper tests
├── test_ingest.py
├── test_retrieve.py
├── test_ask_rag.py
├── smoke_test.py
├── sample_docs/         # Synthetic ExampleCo policies
├── requirements.txt
├── .env.example
└── stages/              # Session 1 teaching stages
```

## Troubleshooting

- **Cannot reach the API:** start FastAPI, or point Streamlit at Render.
- **Missing keys:** set them in local `.env` or Render. Never print the values.
- **401 on `/ingest`:** `INGEST_API_KEY` on the client must match the API.
- **Render cannot find `requirements.txt`:** set the root directory to
  `ai-engineering-bootcamp-v2/week-1v2`.
- **Replaced the wrong document:** ingest uses replace-by-`document_id`. Use a new ID
  unless replacement is intended.
