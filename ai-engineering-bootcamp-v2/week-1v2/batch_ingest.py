"""Batch-ingest UTF-8 .txt files through the existing FastAPI POST /ingest API.

Does not implement a second ingestion pipeline. Default mode is a dry run.

  python batch_ingest.py sample_docs
  python batch_ingest.py sample_docs --source exampleco-synthetic-policies
  python batch_ingest.py /tmp/batch-demo --live --allow-replace --id-prefix batch-addon5
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx
from dotenv import load_dotenv

THIS_DIR = Path(__file__).resolve().parent
load_dotenv(THIS_DIR / ".env")
load_dotenv(THIS_DIR.parent / ".env")

DEFAULT_LOCAL_API = "http://127.0.0.1:8000"
INGEST_TIMEOUT_SECONDS = 120.0
ID_SAFE = re.compile(r"[^a-z0-9_-]+")


def default_api_base_url() -> str:
    configured = os.getenv("API_BASE_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    return DEFAULT_LOCAL_API


def get_ingest_api_key() -> str:
    return os.getenv("INGEST_API_KEY", "").strip()


def discover_text_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        raise FileNotFoundError(f"Not a directory: {directory}")
    return sorted(path for path in directory.iterdir() if path.is_file() and path.suffix.lower() == ".txt")


def document_id_from_filename(path: Path, prefix: str = "") -> str:
    stem = ID_SAFE.sub("-", path.stem.strip().lower().replace(" ", "-")).strip("-")
    if not stem:
        raise ValueError(f"Cannot derive a document_id from {path.name}.")
    cleaned_prefix = ID_SAFE.sub("-", prefix.strip().lower()).strip("-")
    if cleaned_prefix:
        return f"{cleaned_prefix}-{stem}"
    return stem


def read_utf8_document(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError(f"{path.name} is empty.")
    return text


@dataclass
class PlannedDocument:
    path: Path
    document_id: str
    source: str | None
    text: str | None
    error: str | None = None


def plan_documents(
    directory: Path,
    *,
    prefix: str = "",
    source: str | None = None,
) -> list[PlannedDocument]:
    planned: list[PlannedDocument] = []
    source_value = source.strip() if source and source.strip() else None
    for path in discover_text_files(directory):
        try:
            document_id = document_id_from_filename(path, prefix)
            text = read_utf8_document(path)
        except ValueError as exc:
            planned.append(
                PlannedDocument(
                    path=path,
                    document_id="",
                    source=source_value,
                    text=None,
                    error=str(exc),
                )
            )
            continue
        planned.append(
            PlannedDocument(
                path=path,
                document_id=document_id,
                source=source_value,
                text=text,
            )
        )
    return planned


def build_ingest_payload(item: PlannedDocument) -> dict:
    payload: dict[str, str] = {
        "document_id": item.document_id,
        "text": item.text or "",
    }
    if item.source:
        payload["source"] = item.source
    return payload


def post_ingest(
    base_url: str,
    payload: dict,
    ingest_key: str,
    *,
    timeout: float = INGEST_TIMEOUT_SECONDS,
) -> tuple[int, dict | str]:
    try:
        response = httpx.post(
            f"{base_url.rstrip('/')}/ingest",
            json=payload,
            headers={"X-Ingest-Key": ingest_key},
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        return 0, {"error": str(exc)}
    try:
        return response.status_code, response.json()
    except json.JSONDecodeError:
        return response.status_code, response.text


def format_row(
    item: PlannedDocument,
    *,
    status: str,
    chunks: str = "-",
    outcome: str,
) -> str:
    document_id = item.document_id or "-"
    return (
        f"{item.path.name}\t{document_id}\t{status}\tchunks={chunks}\t{outcome}"
    )


def run_dry_run(planned: list[PlannedDocument]) -> int:
    print("DRY-RUN: no HTTP requests. POST /ingest would replace any existing ID.")
    failures = 0
    for item in planned:
        if item.error:
            failures += 1
            print(format_row(item, status="SKIP", outcome=f"fail: {item.error}"))
            continue
        print(format_row(item, status="DRY-RUN", outcome="would ingest"))
    print(f"Total documents: {len(planned)}  chunks indexed: 0 (dry-run)")
    return 1 if failures else 0


def run_live(
    planned: list[PlannedDocument],
    *,
    base_url: str,
    ingest_key: str,
) -> int:
    print(
        "WARNING: POST /ingest replaces vectors for a colliding document_id. "
        "A unique --id-prefix reduces collision risk but does not make ingest create-only."
    )
    chunks_total = 0
    ingested = 0
    for item in planned:
        if item.error:
            print(format_row(item, status="SKIP", outcome=f"fail: {item.error}"))
            print("Stopped on first failure. No automatic retries.")
            return 1
        status, body = post_ingest(base_url, build_ingest_payload(item), ingest_key)
        if status != 200 or not isinstance(body, dict) or "chunks_indexed" not in body:
            detail = body.get("detail", body) if isinstance(body, dict) else body
            print(format_row(item, status=f"HTTP {status}", outcome=f"fail: {detail}"))
            print("Stopped on first failure. No automatic retries.")
            return 1
        chunks = int(body.get("chunks_indexed") or 0)
        chunks_total += chunks
        ingested += 1
        print(
            format_row(
                item,
                status=f"HTTP {status}",
                chunks=str(chunks),
                outcome=str(body.get("status", "success")),
            )
        )
    print(f"Total documents: {ingested}  chunks indexed: {chunks_total}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ingest top-level .txt files through existing POST /ingest."
    )
    parser.add_argument("directory", type=Path, help="Directory of UTF-8 .txt files (not recursive).")
    parser.add_argument("--live", action="store_true", help="Send real POST /ingest requests.")
    parser.add_argument(
        "--allow-replace",
        action="store_true",
        help="Acknowledge that /ingest replaces existing vectors for the same document_id.",
    )
    parser.add_argument(
        "--id-prefix",
        default="",
        help="Prefix for stable document IDs derived from filenames.",
    )
    parser.add_argument("--source", default=None, help="Optional source label for all files.")
    parser.add_argument(
        "--base-url",
        default=default_api_base_url(),
        help="FastAPI base URL. Defaults to API_BASE_URL or http://127.0.0.1:8000.",
    )
    args = parser.parse_args(argv)

    try:
        planned = plan_documents(
            args.directory,
            prefix=args.id_prefix,
            source=args.source,
        )
    except FileNotFoundError as exc:
        print(str(exc))
        return 2

    if not planned:
        print(f"No .txt files found in {args.directory}")
        return 1

    if not args.live:
        return run_dry_run(planned)

    if not args.allow_replace:
        print(
            "--live requires --allow-replace because POST /ingest replaces "
            "existing vectors when a document_id already exists."
        )
        return 2
    if not args.id_prefix.strip():
        print(
            "--live requires --id-prefix so new IDs are less likely to collide "
            "with ExampleCo, Northwind, or smoke-test documents."
        )
        return 2

    ingest_key = get_ingest_api_key()
    if not ingest_key:
        print("INGEST_API_KEY is missing. Refusing to send an unauthenticated /ingest request.")
        return 2

    print(f"API base URL: {args.base_url.rstrip('/')}")
    return run_live(planned, base_url=args.base_url.rstrip("/"), ingest_key=ingest_key)


if __name__ == "__main__":
    raise SystemExit(main())
