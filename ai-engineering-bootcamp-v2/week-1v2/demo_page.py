"""Minimal Streamlit UI for the Week 1 v2 RAG `/ask` and `/ingest` demo.

Run:
  streamlit run demo_page.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import streamlit as st
from dotenv import load_dotenv

THIS_DIR = Path(__file__).resolve().parent
load_dotenv(THIS_DIR / ".env")
load_dotenv(THIS_DIR.parent / ".env")

WORKDIR_CMD = "ai-engineering-bootcamp-v2/week-1v2"
MODELS = ["gpt-4o-mini", "gpt-4o", "o3-mini"]
DEFAULT_LOCAL_API = "http://127.0.0.1:8000"
DEFAULT_DEPLOYED_API = "https://ai-internship-5ei0.onrender.com"
REFUSAL_ANSWER = "I don't have enough information to answer that."
ASK_TIMEOUT_SECONDS = 120.0
INGEST_TIMEOUT_SECONDS = 120.0
HEALTH_TIMEOUT_SECONDS = 10.0


def default_api_base_url() -> str:
    configured = os.getenv("API_BASE_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    return DEFAULT_DEPLOYED_API.rstrip("/")


def get_ingest_api_key() -> str:
    key = os.getenv("INGEST_API_KEY", "").strip()
    if key:
        return key
    try:
        value = st.secrets.get("INGEST_API_KEY", "")
    except Exception:
        return ""
    return str(value or "").strip()


def build_payload(question: str, model: str, force_bad: bool) -> dict:
    return {
        "question": question,
        "model": model,
        "force_bad": force_bad,
    }


def is_refusal_answer(data: dict | str) -> bool:
    if not isinstance(data, dict):
        return False
    answer = data.get("answer")
    if isinstance(answer, dict):
        text = str(answer.get("answer") or "").strip()
    else:
        text = str(answer or "").strip()
    return text == REFUSAL_ANSWER


def call_json(
    method: str,
    url: str,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = ASK_TIMEOUT_SECONDS,
) -> tuple[int, dict | str]:
    try:
        if method == "POST":
            response = httpx.post(url, json=payload, headers=headers, timeout=timeout)
        else:
            response = httpx.get(url, headers=headers, timeout=timeout)

        try:
            return response.status_code, response.json()
        except json.JSONDecodeError:
            return response.status_code, response.text
    except httpx.ConnectError:
        return 0, {"error": f"Cannot reach {url}. Check the API base URL."}
    except httpx.TimeoutException:
        return 0, {"error": f"Timed out calling {url}."}
    except httpx.HTTPError as exc:
        return 0, {"error": str(exc)}


def render_curl(base_url: str, payload: dict) -> str:
    body = json.dumps(payload)
    return (
        f'curl -s -X POST {base_url.rstrip("/")}/ask '
        f'-H "Content-Type: application/json" '
        f"-d '{body}'"
    )


def render_attempts(data: dict | str) -> None:
    if not isinstance(data, dict):
        return

    attempts = data.get("attempts", [])
    if not attempts:
        return

    st.markdown("### Attempts")
    for attempt in attempts:
        status = "passed" if attempt.get("ok") else "failed"
        title = f"Attempt {attempt.get('attempt')}: {attempt.get('step')} ({status})"
        with st.expander(title, expanded=False):
            st.write(attempt.get("message"))
            if attempt.get("raw_output"):
                st.markdown("**Raw model output**")
                st.code(attempt["raw_output"], language="json")
            if attempt.get("validation_error"):
                st.markdown("**Validation error**")
                st.code(attempt["validation_error"], language="text")


def render_observability(data: dict) -> None:
    metric_cols = st.columns(4)
    metric_cols[0].metric("Model", str(data.get("model", "-")))
    metric_cols[1].metric("Tokens", str(data.get("tokens_used", "-")))
    metric_cols[2].metric("Latency", f"{data.get('latency_ms', '-')} ms")
    metric_cols[3].metric("Cost", f"${data.get('cost_usd', '-')}")


def render_ask_response(status: int, data: dict | str) -> None:
    st.markdown(f"**HTTP {status}**" if status else "**Request failed**")
    if not isinstance(data, dict):
        st.error("Unexpected response from the API.")
        st.code(str(data))
        return
    if "error" in data and "answer" not in data:
        st.error(data.get("error"))
        return
    if status and status >= 400:
        st.error(data.get("detail", "The API returned an error."))
        st.json(data)
        return

    answer = data.get("answer")
    answer_text = ""
    citations: list = []
    if isinstance(answer, dict):
        answer_text = str(answer.get("answer") or "")
        citations = answer.get("citations") or []
    elif isinstance(answer, str):
        answer_text = answer

    if is_refusal_answer(data):
        st.warning("Refusal: the retrieved documents do not contain enough evidence.")
        st.markdown(f"### {answer_text}")
    else:
        st.markdown("### Answer")
        st.write(answer_text)

    if citations:
        st.markdown("**Citations**")
        for citation in citations:
            st.markdown(f"- `{citation}`")
    elif not is_refusal_answer(data):
        st.caption("No citations were returned.")

    render_observability(data)
    render_attempts(data)

    retrieved = data.get("retrieved_chunk_ids") or []
    with st.expander("Technical details"):
        st.markdown("**Retrieved chunk IDs**")
        if retrieved:
            st.code("\n".join(str(item) for item in retrieved))
        else:
            st.caption("No retrieved chunk IDs were returned.")
        if isinstance(answer, dict):
            st.caption(
                f"confidence: {answer.get('confidence')} | "
                f"sources_needed: {answer.get('sources_needed')}"
            )
        st.markdown("**Raw JSON**")
        st.json(data)


def render_ingest_response(status: int, data: dict | str) -> None:
    st.markdown(f"**HTTP {status}**" if status else "**Request failed**")
    if not isinstance(data, dict):
        st.error("Unexpected response from the API.")
        st.code(str(data))
        return
    if "error" in data and "document_id" not in data:
        st.error(data.get("error"))
        return
    if status == 200:
        st.success("Document ingested.")
        st.write(f"**document_id:** `{data.get('document_id', '-')}`")
        st.write(f"**chunks_indexed:** {data.get('chunks_indexed', '-')}")
        st.write(f"**status:** {data.get('status', '-')}")
        return
    if status == 401:
        st.error("Ingestion was rejected. Check INGEST_API_KEY in your local environment.")
        return
    st.error(data.get("detail", "Document ingestion failed."))


def main() -> None:
    st.set_page_config(page_title="ExampleCo RAG Demo", layout="centered")
    st.title("Session 2: Ask documents")
    st.caption(
        "This page calls the FastAPI backend. Retrieval and generation happen on the API, "
        "not in Streamlit."
    )

    default_url = default_api_base_url()
    base_url = st.sidebar.text_input("API base URL", default_url).strip().rstrip("/")
    st.sidebar.caption("Override `API_BASE_URL` here if you need a different backend.")
    if st.sidebar.button("Check API health"):
        status, data = call_json(
            "GET",
            f"{base_url}/health",
            timeout=HEALTH_TIMEOUT_SECONDS,
        )
        st.sidebar.markdown(f"**HTTP {status}**" if status else "**Not connected**")
        st.sidebar.json(data)

    ask_tab, ingest_tab = st.tabs(["Ask documents", "Ingest document"])

    with ask_tab:
        with st.form("ask_form"):
            question = st.text_area(
                "Question",
                "How many days per week can ExampleCo employees work remotely?",
                height=100,
            )
            model = st.selectbox("Model", MODELS, index=0)
            force_bad = st.checkbox(
                "Force a bad first response to demo validation + retry",
                value=False,
            )
            submitted = st.form_submit_button("Ask", type="primary")

        payload = build_payload(question, model, force_bad)
        with st.expander("Equivalent curl"):
            st.code(render_curl(base_url, payload), language="bash")

        if submitted:
            if not question.strip():
                st.error("Enter a question before calling /ask.")
            else:
                with st.spinner("Calling /ask..."):
                    status, data = call_json(
                        "POST",
                        f"{base_url}/ask",
                        payload,
                        timeout=ASK_TIMEOUT_SECONDS,
                    )
                render_ask_response(status, data)

    with ingest_tab:
        st.info(
            "Re-ingesting the same document ID replaces that document's existing vectors. "
            "Do not reuse `northwind-handbook` unless you intend to replace it."
        )
        with st.form("ingest_form"):
            document_id = st.text_input("document_id", placeholder="exampleco-remote-work")
            source = st.text_input(
                "source (optional)",
                placeholder="exampleco-synthetic-policies",
            )
            text = st.text_area("Document text", height=220)
            ingest_submitted = st.form_submit_button("Ingest", type="primary")

        if ingest_submitted:
            if not document_id.strip():
                st.error("document_id cannot be empty.")
            elif not text.strip():
                st.error("Document text cannot be empty.")
            else:
                ingest_key = get_ingest_api_key()
                if not ingest_key:
                    st.error(
                        "INGEST_API_KEY is not configured. Add it to your local .env "
                        "or Streamlit secrets. The key is not sent from this page if missing."
                    )
                else:
                    ingest_payload = {
                        "document_id": document_id.strip(),
                        "text": text,
                    }
                    if source.strip():
                        ingest_payload["source"] = source.strip()
                    with st.spinner("Calling /ingest..."):
                        status, data = call_json(
                            "POST",
                            f"{base_url}/ingest",
                            ingest_payload,
                            headers={"X-Ingest-Key": ingest_key},
                            timeout=INGEST_TIMEOUT_SECONDS,
                        )
                    render_ingest_response(status, data)


if __name__ == "__main__":
    main()
