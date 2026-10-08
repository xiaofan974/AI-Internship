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
| `GET` | `/debug/retrieve` | Return retrieved chunks. Optional `source` / `document_id` filters. Requires `X-Ingest-Key`. |
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

# Optional metadata filters (server-built; not raw Pinecone JSON)
curl -sS "http://127.0.0.1:8000/debug/retrieve?q=ExampleCo%20remote%20work&top_k=5&source=exampleco-synthetic-policies" \
  -H "X-Ingest-Key: $INGEST_API_KEY"
curl -sS "http://127.0.0.1:8000/debug/retrieve?q=ExampleCo%20remote%20work&top_k=5&document_id=exampleco-remote-work" \
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

## Session 2 optional add-ons

The basic RAG assignment is deployed: ingest, retrieve, grounded `/ask`, Streamlit, and
the Render service. The six add-ons below are mostly **local experiments**. Only metadata
filtering is part of the FastAPI debug API. Hybrid search and reranking are **not** wired
into `POST /ask`.

The evaluation corpus is small and synthetic (five ExampleCo policies plus two refusal
questions). Results are exploratory, not statistically significant.

| Add-on | Status | Notes |
| --- | --- | --- |
| 1. Golden-set evaluation | Experiment (`eval_rag.py`) | Not deployed |
| 2. Chunking A/B | Experiment (`chunking_experiment.py`) | Production kept 800/100 |
| 3. Hybrid BM25 + RRF | Experiment (`hybrid_experiment.py`) | Not wired into `/ask` |
| 4. Metadata filtering | Deployed on authenticated `GET /debug/retrieve` | `/ask` remains unfiltered |
| 5. Batch ingest | CLI (`batch_ingest.py`) | Dry-run by default; uses existing `/ingest` |
| 6. Cross-encoder reranking | Experiment (`rerank_experiment.py`) | Not wired into `/ask` |

**Golden-set evaluation**

| Metric | Result |
| --- | --- |
| Retrieval hit | 80% (4/5 factual) |
| Answer correctness | 80% (4/5 factual) |
| Heuristic faithfulness | 86% (6/7); lexical overlap only, not a definitive grounding score |
| Citation validity | 86% (6/7) |
| Refusal success | 100% (2/2) |

**Chunking A/B** (isolated test namespaces)

| Condition | Recall@5 | Hit@1 | MRR |
| --- | --- | --- | --- |
| 800/100 | 80% | 60% | 0.70 |
| 600/100 | 80% | 60% | 0.67 |

Retained 800/100.

**Hybrid search** (experimental only)

| Condition | Recall@5 | Hit@1 | MRR |
| --- | --- | --- | --- |
| Dense | 80% | 60% | 0.70 |
| BM25 | 80% | 80% | 0.80 |
| Hybrid RRF | 100% | 60% | 0.77 |

**Metadata filtering:** optional `source` and `document_id` on authenticated
`/debug/retrieve`. Filters are built server-side (no raw Pinecone JSON). Verified against
Pinecone. `POST /ask` does not accept or apply filters.

**Batch ingest:** dry-run by default. Live mode requires `X-Ingest-Key`, `--allow-replace`,
and `--id-prefix`. One successful live test ingested `batch-addon5-helpdesk`.

**Cross-encoder reranking** (optional `sentence-transformers` / PyTorch; not production)

| Condition | Recall@5 | Hit@1 | MRR |
| --- | --- | --- | --- |
| Dense | 80% | 60% | 0.70 |
| Reranked | 100% | 60% | 0.77 |

The 60-day security chunk moved from rank 7 to rank 1. Average local reranking latency was
180.5 ms.

### Safe experiment commands

Default is dry-run: no OpenAI, Pinecone, or model-download calls. Pass `--live` only after
explicit authorization.

```bash
# 1. Golden-set
python eval_rag.py
python eval_rag.py --live

# 2. Chunking A/B (live writes only to isolated test namespaces)
python chunking_experiment.py
python chunking_experiment.py --live

# 3. Hybrid RRF — optional: pip install rank-bm25
python hybrid_experiment.py
python hybrid_experiment.py --live

# 4. Metadata filters (authenticated debug API; not /ask)
curl -sS "http://127.0.0.1:8000/debug/retrieve?q=ExampleCo%20remote%20work&top_k=5&source=exampleco-synthetic-policies" \
  -H "X-Ingest-Key: $INGEST_API_KEY"

# 5. Batch ingest — live needs --allow-replace and --id-prefix
python batch_ingest.py sample_docs --source exampleco-synthetic-policies
python batch_ingest.py /tmp/batch-demo --live --allow-replace --id-prefix batch-addon5 --source exampleco-batch-demo

# 6. Cross-encoder rerank — optional: pip install sentence-transformers
python rerank_experiment.py
python rerank_experiment.py --live
```

Do not re-ingest `northwind-handbook` or the production ExampleCo document IDs. Chunking
`--live` must not target `maven-session2`. Batch ingest `--id-prefix` exists to avoid
colliding with those IDs.

`rank-bm25` and `sentence-transformers` / PyTorch are **optional local experiment
dependencies**. They are not in production `requirements.txt`, so a Render build can start
FastAPI without them. Hybrid tests that exercise BM25 need `rank-bm25` installed locally.

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
python -m unittest -v \
  test_ingest.py test_retrieve.py test_ask_rag.py test_demo_page.py \
  test_eval_rag.py test_chunking_experiment.py test_hybrid_experiment.py \
  test_batch_ingest.py test_rerank_experiment.py
python smoke_test.py
```

`smoke_test.py` starts the API and checks `/health` and `/docs` without paid provider calls.

## Project Structure

```text
week-1v2/
├── README.md
├── main.py                 # FastAPI: /ask, /ingest, /debug/retrieve
├── rag.py                  # Chunking, embeddings, Pinecone, optional metadata filters
├── demo_page.py            # Streamlit Ask + Ingest client
├── batch_ingest.py         # CLI client for POST /ingest (dry-run default)
├── eval_rag.py             # Golden-set evaluation (add-on 1)
├── chunking_experiment.py  # 800 vs 600 A/B (add-on 2)
├── hybrid_experiment.py    # Dense + BM25 + RRF (add-on 3)
├── rerank_experiment.py    # Cross-encoder rerank (add-on 6)
├── eval_cases.json
├── sample_docs/
├── requirements.txt        # Production FastAPI + Streamlit only
└── stages/
```

## Troubleshooting

- **Cannot reach the API:** start FastAPI, or point Streamlit at Render.
- **Missing keys:** set them in local `.env` or Render. Never print the values.
- **401 on `/ingest`:** `INGEST_API_KEY` on the client must match the API.
- **Render cannot find `requirements.txt`:** set the root directory to
  `ai-engineering-bootcamp-v2/week-1v2`.
- **Replaced the wrong document:** ingest uses replace-by-`document_id`. Use a new ID
  unless replacement is intended.
