#!/usr/bin/env python3
"""No-token smoke test for the Week 1 v2 API."""

import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

from main import DEFAULT_MODEL, AskRequest, AskResponse

WORKDIR = Path(__file__).resolve().parent


def request_contract_is_valid() -> bool:
    """Verify minimal and extended payload defaults without calling OpenAI."""

    minimal = AskRequest.model_validate({"question": "What is RAG?"})
    extended = AskRequest.model_validate(
        {
            "question": "What is RAG?",
            "model": "gpt-4o-mini",
            "force_bad": True,
        }
    )
    expected_response_fields = {
        "answer",
        "tokens_used",
        "model",
        "latency_ms",
        "cost_usd",
        "attempts",
        "retrieved_chunk_ids",
    }

    return (
        minimal.model == DEFAULT_MODEL
        and minimal.force_bad is False
        and extended.model == "gpt-4o-mini"
        and extended.force_bad is True
        and set(AskResponse.model_fields) == expected_response_fields
    )


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_health(base_url: str, timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            response = httpx.get(f"{base_url}/health", timeout=1.0)
            if response.status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(0.3)
    return False


def main() -> int:
    if not request_contract_is_valid():
        print("FAIL: /ask request or response contract is incorrect")
        return 1

    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=WORKDIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        if not wait_for_health(base_url):
            print(f"FAIL: API did not become healthy at {base_url}")
            return 1

        docs_response = httpx.get(f"{base_url}/docs", timeout=2.0)
        if docs_response.status_code != 200:
            print(f"FAIL: /docs returned HTTP {docs_response.status_code}")
            return 1

        print(
            "PASS: minimal and extended /ask contracts, API health, "
            f"and docs are available at {base_url}"
        )
        return 0
    finally:
        proc.terminate()
        proc.wait(timeout=5)


if __name__ == "__main__":
    sys.exit(main())
