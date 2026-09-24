# Week 1: Reliable AI Endpoint

## 1. Project Overview

This project is a small, production-style AI application built for Week 1 of the Maven AI
Engineering Bootcamp. It exposes a typed `POST /ask` API, sends the question to OpenAI,
validates the model's structured response, and returns useful operational metadata.

The learning objective is to turn a basic LLM call into a dependable software component
with:

- predictable request and response schemas;
- Pydantic structured-output validation;
- a validation-and-retry guardrail;
- model and attempt visibility;
- token usage, latency, and estimated USD cost; and
- a Streamlit interface for interactive testing.

## 2. Tech Stack

- **Python 3.12** — application runtime.
- **FastAPI** — HTTP API, request validation, response serialization, and generated docs.
- **Uvicorn** — ASGI server used to run FastAPI.
- **OpenAI Python SDK** — sends prompts to OpenAI and parses structured model output.
- **Pydantic** — defines and validates request, answer, attempt, and response schemas.
- **Streamlit** — browser-based demo UI in `demo_page.py`.
- **httpx** — sends requests from Streamlit and the smoke test to FastAPI.
- **python-dotenv** — loads `OPENAI_API_KEY` from a local `.env` file.
- **Render** — hosts the deployed FastAPI backend.

The default model is `gpt-4o-mini`. The API also accepts `gpt-4o` and `o3-mini`.

## 3. Getting Started

### Prerequisites

- Git
- Python 3.12
- An OpenAI API key

Clone the repository and move into this application:

```bash
git clone https://github.com/YOUR-USERNAME/AI-Internship.git
cd AI-Internship/ai-engineering-bootcamp-v2/week-1v2
```

Create a standard Python virtual environment:

```bash
python3 -m venv .venv
```

Activate it on macOS or Linux:

```bash
source .venv/bin/activate
```

On Windows PowerShell, use:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 4. Environment Variables

Create a local environment file from the committed template:

```bash
cp .env.example .env
```

Open `.env` and set the required variable:

```dotenv
OPENAI_API_KEY=your_openai_api_key_here
```

`.env` contains secrets and must never be committed, shared, logged, or copied into a
container image. It is excluded by both `.gitignore` and `.dockerignore`.

`.env.example` is safe to commit because it documents variable names using empty or
placeholder values and contains no real credentials.

## 5. Running Locally

Run all commands from `ai-engineering-bootcamp-v2/week-1v2`.

### Start the FastAPI backend

```bash
source .venv/bin/activate
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Verify the health endpoint without making an OpenAI request:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

FastAPI's interactive documentation is available at:

```text
http://127.0.0.1:8000/docs
```

### Start the Streamlit UI

Keep FastAPI running and open a second terminal:

```bash
cd AI-Internship/ai-engineering-bootcamp-v2/week-1v2
source .venv/bin/activate
python -m streamlit run demo_page.py
```

Open `http://localhost:8501`. The default **API base URL** is
`http://127.0.0.1:8000`. Enter a deployed API base URL instead if you want the UI to call
Render. Do not append `/ask`; the UI adds the endpoint path automatically.

## 6. Testing the API

Send a request to `POST /ask`:

```bash
curl --fail-with-body --silent --show-error \
  --request POST http://127.0.0.1:8000/ask \
  --header "Content-Type: application/json" \
  --data '{"question":"What is an API in one sentence?","model":"gpt-4o-mini","force_bad":false}'
```

Illustrative response:

```json
{
  "answer": {
    "answer": "An API is a defined interface that allows software systems to communicate.",
    "confidence": 0.95,
    "sources_needed": false
  },
  "tokens_used": 129,
  "model": "gpt-4o-mini",
  "latency_ms": 2824,
  "cost_usd": 0.000038,
  "attempts": [
    {
      "attempt": 1,
      "step": "structured_output",
      "ok": true,
      "message": "Structured output matched the Answer schema.",
      "raw_output": null,
      "validation_error": null
    }
  ]
}
```

Response fields:

- `answer` — validated object containing the answer text, confidence from `0` to `1`, and
  whether the model believes external sources are needed.
- `tokens_used` — total tokens reported by OpenAI across all attempts.
- `model` — model used for the request.
- `latency_ms` — total endpoint processing time in milliseconds.
- `cost_usd` — estimated request cost based on input/output token counts and the
  hardcoded per-model prices in `main.py`.
- `attempts` — validation result for each model call, including retry details when used.

Actual wording, token counts, latency, and cost vary between requests.

## 7. Guardrail Demonstration

Set `force_bad` to `true` to intentionally request malformed JSON on the first attempt:

```bash
curl --fail-with-body --silent --show-error \
  --request POST http://127.0.0.1:8000/ask \
  --header "Content-Type: application/json" \
  --data '{"question":"What is a vector database?","model":"gpt-4o-mini","force_bad":true}'
```

The first model call is instructed to return `"confidence": "very high"`, which violates
the Pydantic requirement that confidence be a number between `0` and `1`. The API records
the validation error, retries with OpenAI structured output, and returns the valid second
answer. The `attempts` array shows the failed first attempt and successful second attempt;
`tokens_used` and `cost_usd` include both calls.

The same demonstration is available through the Streamlit checkbox labeled **Force a bad
first response to demo validation + retry**.

## 8. Deploying to Render

The repository is a monorepo, so Render must build from the Week 1 v2 subdirectory.

1. Push the repository to GitHub without committing `.env`.
2. In Render, choose **New → Web Service** and connect the GitHub repository.
3. Select the branch to deploy.
4. Set **Runtime** to **Python 3**.
5. Set **Root Directory** to:

   ```text
   ai-engineering-bootcamp-v2/week-1v2
   ```

6. Set **Build Command** to:

   ```bash
   pip install --upgrade pip && pip install -r requirements.txt
   ```

7. Set **Start Command** to:

   ```bash
   python -m uvicorn main:app --host 0.0.0.0 --port $PORT
   ```

8. In Render's environment-variable settings, add `OPENAI_API_KEY` with the real key as
   its secret value. Never commit the key or upload a local `.env` file.
9. Optionally set the health-check path to `/health`, then deploy.

Test the deployed health endpoint:

```bash
curl --fail-with-body --silent --show-error \
  https://YOUR-SERVICE.onrender.com/health
```

Test the deployed AI endpoint:

```bash
curl --fail-with-body --silent --show-error \
  --request POST https://YOUR-SERVICE.onrender.com/ask \
  --header "Content-Type: application/json" \
  --data '{"question":"What is an API in one sentence?","model":"gpt-4o-mini","force_bad":false}'
```

To use the local Streamlit UI with Render, enter
`https://YOUR-SERVICE.onrender.com` in its **API base URL** field.

## 9. Model Choice and Cost

I chose gpt-4o-mini as the default model because it offers a good balance of response
quality, low latency, and cost-efficiency for a lightweight, structured-output API. My
live tests cost approximately $0.000038 per call (129–130 tokens), equivalent to roughly
$0.038 per 1,000 similar requests.

Actual costs vary with input and output token usage. The application calculates an
estimate using OpenAI's reported prompt and completion tokens plus the hardcoded prices
in `main.py`; confirm current provider pricing before using these estimates in production.

## Teaching Stages

`main.py` and `demo_page.py` are the final student application. The optional stage files
show how the endpoint develops:

| Stage | File | Teaching point |
| --- | --- | --- |
| 1 | `stages/stage_1_bare_ask.py` | Smallest typed `/ask`: question in, string answer out. |
| 2 | `stages/stage_2_structured_output.py` | Add the Pydantic `Answer` schema and OpenAI structured output. |
| 3 | `stages/stage_3_guardrails_and_observability.py` | Add validation retry, model selection, latency, and cost. |

Run one stage at a time:

```bash
python -m uvicorn stages.stage_1_bare_ask:app --host 127.0.0.1 --port 8000 --reload
python -m uvicorn stages.stage_2_structured_output:app --host 127.0.0.1 --port 8000 --reload
python -m uvicorn stages.stage_3_guardrails_and_observability:app --host 127.0.0.1 --port 8000 --reload
```

## Smoke Test

This test starts the final API and verifies `/health` and `/docs` without calling OpenAI:

```bash
source .venv/bin/activate
python smoke_test.py
```

## Project Structure

```text
week-1v2/
├── README.md
├── main.py                         # Final FastAPI application
├── demo_page.py                    # Streamlit UI
├── smoke_test.py                   # No-token startup check
├── requirements.txt                # Python dependencies
├── .env.example                    # Safe environment-variable template
├── .gitignore                      # Excludes .env and local Python artifacts
├── .dockerignore                   # Excludes secrets from Docker builds
├── Dockerfile                      # Python 3.12 API container
└── stages/
    ├── stage_1_bare_ask.py
    ├── stage_2_structured_output.py
    └── stage_3_guardrails_and_observability.py
```

## Troubleshooting

- **Cannot reach `http://127.0.0.1:8000`:** start FastAPI in the first terminal.
- **Missing `OPENAI_API_KEY`:** confirm `.env` exists locally or the variable is configured
  in Render. Never print the value while debugging.
- **Address already in use:** stop the process using port `8000` or choose another port.
- **Streamlit cannot reach the API:** verify its **API base URL** and do not include `/ask`.
- **Render cannot find `requirements.txt`:** set Render's root directory to
  `ai-engineering-bootcamp-v2/week-1v2`.
