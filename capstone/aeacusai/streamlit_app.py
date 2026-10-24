"""Streamlit UI for the AeacusAI local classification preview.

Connects only to `aeacus_preview_agent` through the existing bounded
`run_review()` runner. Model calls happen only after an explicit
Run assessment click.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import threading
import uuid
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st
from dotenv import load_dotenv

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parents[1]
GOOGLE_API_KEY_PLACEHOLDER = "your_google_api_key_here"
SAFE_URL_SCHEMES = {"http", "https"}

SAMPLE_PREVIEW_PROMPT = (
    "A company uses an AI system to analyse and filter job applications and rank "
    "candidates for recruiters. Recruiters make the final hiring decision. Give a "
    "provisional classification assessment against the pinned corpus, identify "
    "relevant exceptions, and state which additional facts are needed."
)

MISSING_HEADING_RE = re.compile(
    r"missing facts|additional facts needed|additional information needed",
    re.IGNORECASE,
)
EPISTEMIC_HEADING_RE = re.compile(
    r"^#{1,6}\s*epistemic assessment[^\n]*$",
    re.IGNORECASE | re.MULTILINE,
)
PROVISIONAL_HEADING_RE = re.compile(
    r"^#{1,6}\s*provisional classification assessment[^\n]*$",
    re.IGNORECASE | re.MULTILINE,
)
SECTION_SPLIT_RE = re.compile(r"(?=^#{1,6}\s+)", re.MULTILINE)
INLINE_MISSING_RE = re.compile(
    r"^\s*(?:\*|-)?\s*\*?\*?Missing Facts\*?\*?\s*:?\s*$",
    re.IGNORECASE,
)
RECORD_ID_RE = re.compile(
    r"T1-AIA-[A-Z0-9-]+@sha256:[a-f0-9]+::[A-Za-z0-9/_-]+"
)


def _google_api_key_is_configured() -> bool:
    value = os.getenv("GOOGLE_API_KEY", "").strip()
    return bool(value) and value != GOOGLE_API_KEY_PLACEHOLDER


def _load_local_google_api_key() -> None:
    """Load GOOGLE_API_KEY only. Do not load OpenAI or Pinecone credentials."""
    load_dotenv(THIS_DIR / ".env", override=False)
    if _google_api_key_is_configured():
        return
    bootcamp_env = (
        REPO_ROOT
        / "ai-engineering-bootcamp"
        / "adk-multi-agent-systems"
        / ".env"
    )
    if not bootcamp_env.exists():
        return
    for raw_line in bootcamp_env.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() != "GOOGLE_API_KEY":
            continue
        value = value.strip().strip('"').strip("'")
        if value and value != GOOGLE_API_KEY_PLACEHOLDER:
            os.environ["GOOGLE_API_KEY"] = value
        break


_load_local_google_api_key()

from aeacus_agent.preview_agent import aeacus_preview_agent
from aeacus_agent.project_memory import (
    ACTOR_ROLES,
    ALLOWED_FIELDS,
    ALLOWED_WRITE_CHANNEL,
    LANGUAGES,
    delete_fact,
    generate_workspace_code,
    list_facts,
    open_memory_store,
    replace_fact,
)
from aeacus_agent.review_register import (
    DEFAULT_DB_PATH,
    PENDING_STATUS,
    approve_and_record,
    artifact_matches,
    create_pending_review,
    reject_draft,
)
from aeacus_agent.trace_store import (
    TraceCapture,
    TraceCaptureConfig,
    application_outcome,
    capture_enabled_from_env,
    persist_trace,
    update_application_outcome,
)
from run_review import RUN_TIMEOUT_SECONDS, _redact_sensitive, run_review


def _run_async(coro):
    """Run a coroutine even if Streamlit already has an event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: dict = {}

    def _target() -> None:
        result["value"] = asyncio.run(coro)

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join()
    if "value" not in result:
        raise RuntimeError("Preview runner thread finished without a result.")
    return result["value"]


def _extract_items(body: str) -> list[str]:
    items: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^(\d+[.)]|[-*•])\s+", "", line)
        line = line.replace("**", "").strip()
        if line:
            items.append(line)
    return items


def split_assessment_and_missing_facts(answer: str) -> tuple[str, list[str]]:
    """Separate missing-fact bullets from the visible assessment text."""
    if not answer or not str(answer).strip():
        return "", []

    text = str(answer).strip()
    missing_items: list[str] = []
    assessment_parts: list[str] = []

    chunks = SECTION_SPLIT_RE.split(text) if text.startswith("#") else [text]
    if len(chunks) == 1 and not text.startswith("#"):
        chunks = SECTION_SPLIT_RE.split(text)

    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        first_line = chunk.splitlines()[0]
        if MISSING_HEADING_RE.search(first_line):
            body = "\n".join(chunk.splitlines()[1:]).strip()
            missing_items.extend(_extract_items(body))
            continue

        kept_lines: list[str] = []
        in_inline_missing = False
        for line in chunk.splitlines():
            if INLINE_MISSING_RE.match(line.strip()):
                in_inline_missing = True
                continue
            if in_inline_missing:
                if line.strip().startswith("#"):
                    in_inline_missing = False
                    kept_lines.append(line)
                    continue
                if line.strip():
                    missing_items.extend(_extract_items(line))
                continue
            kept_lines.append(line)

        cleaned = "\n".join(kept_lines).strip()
        cleaned = EPISTEMIC_HEADING_RE.sub("", cleaned)
        cleaned = PROVISIONAL_HEADING_RE.sub("Classification", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        if cleaned:
            assessment_parts.append(cleaned)

    return "\n\n".join(assessment_parts).strip(), missing_items


_SECTION_HEADINGS = (
    (
        "finding",
        re.compile(
            r"^(?:#{1,6}\s+)?(?:\*\*)?(?:provisional finding|classification)"
            r"(?:\*\*)?\s*$",
            re.IGNORECASE,
        ),
    ),
    (
        "why",
        re.compile(r"^(?:#{1,6}\s+)?(?:\*\*)?why(?:\*\*)?\s*$", re.IGNORECASE),
    ),
    (
        "what_could_change",
        re.compile(
            r"^(?:#{1,6}\s+)?(?:\*\*)?what could change this(?:\*\*)?\s*$",
            re.IGNORECASE,
        ),
    ),
    (
        "timing",
        re.compile(
            r"^(?:#{1,6}\s+)?(?:\*\*)?timing(?: and scope)?(?:\*\*)?\s*$",
            re.IGNORECASE,
        ),
    ),
)


def parse_assessment_sections(assessment: str) -> dict[str, str]:
    """Split a displayed assessment into known sections without rewriting body text."""
    if not assessment or not str(assessment).strip():
        return {}

    buckets: dict[str, list[str]] = {"preamble": []}
    current = "preamble"
    for line in str(assessment).splitlines():
        matched = None
        stripped = line.strip()
        for name, pattern in _SECTION_HEADINGS:
            if pattern.match(stripped):
                matched = name
                break
        if matched:
            current = matched
            buckets.setdefault(current, [])
            continue
        buckets.setdefault(current, []).append(line)

    preamble = "\n".join(buckets.get("preamble") or []).strip()
    finding = "\n".join(buckets.get("finding") or []).strip()
    sections: dict[str, str] = {}
    if finding and preamble:
        sections["finding"] = f"{preamble}\n\n{finding}".strip()
    elif finding:
        sections["finding"] = finding
    elif preamble:
        sections["finding"] = preamble
    else:
        sections["finding"] = str(assessment).strip()

    for name in ("why", "what_could_change", "timing"):
        body = "\n".join(buckets.get(name) or []).strip()
        if body:
            sections[name] = body
    return sections


def _safe_source_url(record: dict) -> str | None:
    location = record.get("source_location")
    url = None
    if isinstance(location, dict):
        url = location.get("url")
    elif isinstance(location, str):
        url = location
    if not isinstance(url, str):
        return None
    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme.lower() not in SAFE_URL_SCHEMES or not parsed.netloc:
        return None
    return url


def build_citation_index(evidence: list[dict]) -> dict:
    """Deterministic label ↔ record_id index from this run’s observations."""
    by_id: dict[str, str] = {}
    ordered: list[dict[str, str]] = []
    for card in evidence or []:
        record_id = str(card.get("record_id") or "").strip()
        label = str(card.get("label") or "").strip() or record_id
        if not record_id or record_id in by_id:
            continue
        by_id[record_id] = label
        ordered.append({"label": label, "record_id": record_id})
    return {"by_id": by_id, "ordered": ordered}


def _replace_known_record_id(text: str, record_id: str, label: str) -> str:
    """Map one observed record ID to its short label. Unknown IDs are untouched."""
    escaped_id = re.escape(record_id)
    escaped_label = re.escape(label)
    text = re.sub(
        rf"({escaped_label})\s*[\(（]\s*`?{escaped_id}`?\s*[\)）]",
        r"\1",
        text,
    )
    text = re.sub(rf"`{escaped_id}`", label, text)
    return text.replace(record_id, label)


def present_citations(raw_answer: str, evidence: list[dict]) -> dict:
    """Show short labels in the answer while keeping full IDs for inspection.

    Known IDs from this run are mapped to their observed labels. Unknown IDs
    are left in the displayed text and listed separately. This does not strip
    identifiers with a catch-all delete.
    """
    raw_answer = str(raw_answer or "")
    index = build_citation_index(evidence)
    displayed = raw_answer
    found_ids = list(dict.fromkeys(RECORD_ID_RE.findall(raw_answer)))
    known_ids = sorted(
        [record_id for record_id in found_ids if record_id in index["by_id"]],
        key=len,
        reverse=True,
    )
    for record_id in known_ids:
        displayed = _replace_known_record_id(
            displayed, record_id, index["by_id"][record_id]
        )
    unknown_references = [
        record_id
        for record_id in dict.fromkeys(RECORD_ID_RE.findall(displayed))
        if record_id not in index["by_id"]
    ]
    return {
        "displayed_answer": displayed,
        "raw_answer": raw_answer,
        "citation_map": index["ordered"],
        "unknown_references": unknown_references,
    }


def finalize_preview_result(raw_answer: str, evidence: list[dict]) -> dict:
    """Attach citation presentation and the application-owned timing section."""
    from aeacus_agent.timing_scope import apply_timing_repair, records_from_evidence

    repair = apply_timing_repair(raw_answer, records_from_evidence(evidence))
    presentation = present_citations(repair.delivered_output, evidence)
    assessment, missing_facts = split_assessment_and_missing_facts(
        presentation["displayed_answer"]
    )
    return {
        "ok": True,
        "failure": None,
        "assessment": assessment or presentation["displayed_answer"],
        "missing_facts": missing_facts,
        "evidence": evidence,
        "raw_answer": raw_answer,
        "displayed_answer": presentation["displayed_answer"],
        "citation_map": presentation["citation_map"],
        "unknown_references": presentation["unknown_references"],
        "timing_repair": repair.to_dict(),
    }


def evidence_from_observe_payload(payload: dict) -> list[dict]:
    """Build evidence cards from a preview-tool observation."""
    if not isinstance(payload, dict):
        return []
    retrieval_mode = payload.get("retrieval_mode") or "local_lexical_preview"
    corpus_scope = payload.get("corpus_scope") or (
        "Article 6 and Annex III classification subset"
    )
    notice = payload.get("scope_and_review_notice") or (
        "Local lexical preview over the pinned Article 6 and Annex III subset only. "
        "A missing match does not establish that no legal obligation exists."
    )
    cards: list[dict] = []
    for role, records_key in (("match", "matches"), ("context", "context_records")):
        for record in payload.get(records_key) or []:
            if not isinstance(record, dict):
                continue
            cards.append(
                {
                    "role": role,
                    "label": record.get("label") or "Untitled record",
                    "record_id": record.get("record_id") or "",
                    "source_snapshot_id": record.get("source_snapshot_id") or "",
                    "text": record.get("text") or "",
                    "text_sha256": record.get("text_sha256") or "",
                    "url": _safe_source_url(record),
                    "retrieval_mode": retrieval_mode,
                    "corpus_scope": corpus_scope,
                    "notice": notice,
                }
            )
    return cards


def _persist_streamlit_trace(
    capture: TraceCapture | None,
    *,
    execution_status: str,
    visible_answer: str | None,
    failure_message: str | None,
    pending_review: dict | None,
) -> None:
    if capture is None or not capture.config.enabled or capture.record is None:
        st.session_state.trace_persistence = None
        return
    update_application_outcome(
        capture,
        application_outcome(
            execution_status=execution_status,
            visible_answer=visible_answer,
            failure_message=failure_message,
            pending_review=pending_review,
            pending_review_observed=True,
        ),
    )
    capture.config.persist = True
    st.session_state.trace_persistence = persist_trace(capture)


def _preview_trace_capture() -> TraceCapture | None:
    if os.getenv("AEACUS_UI_DISABLE_LIVE") == "1":
        return None
    if not capture_enabled_from_env(default=True):
        return None
    scenario = os.getenv("AEACUS_TRACE_SCENARIO_ID", "").strip() or None
    return TraceCapture(
        config=TraceCaptureConfig(
            enabled=True,
            persist=False,
            scenario_id=scenario,
            entry_point="streamlit_app.run_preview_assessment",
        )
    )


def run_preview_assessment(system_description: str, on_event) -> dict:
    """Run the preview agent through the existing bounded runner."""
    from aeacus_agent.langfuse_preview import PreviewLangfuseSession, attach_status

    evidence: list[dict] = []
    capture = _preview_trace_capture()

    def _callback(event: dict) -> None:
        if event.get("kind") == "observe":
            evidence.extend(evidence_from_observe_payload(event.get("payload") or {}))
        if on_event is not None:
            on_event(event)

    session = PreviewLangfuseSession(
        run_id=None if capture is None else capture.run_id,
        entry_point="streamlit_app.run_preview_assessment",
        verify_remote=False,
    )
    failed_result = None
    result = None
    with session:
        answer = _run_async(
            run_review(
                system_description,
                agent=aeacus_preview_agent,
                timeout_seconds=RUN_TIMEOUT_SECONDS,
                on_event=_callback,
                capture=capture,
            )
        )
        if isinstance(answer, str) and answer.startswith("[FAILED]"):
            session.complete(
                capture,
                raw_answer=answer,
                delivered_answer=None,
                timing_repair=None,
                error=answer,
            )
            failed_result = {
                "ok": False,
                "failure": answer,
                "assessment": None,
                "missing_facts": [],
                "evidence": evidence,
                "raw_answer": None,
                "displayed_answer": None,
                "citation_map": [],
                "unknown_references": [],
            }
        else:
            result = finalize_preview_result(str(answer or ""), evidence)
            session.complete(
                capture,
                raw_answer=str(answer or ""),
                delivered_answer=result.get("displayed_answer"),
                timing_repair=result.get("timing_repair"),
            )
    attach_status(capture, session.status)
    if failed_result is not None:
        failed_result["trace_capture"] = capture
        failed_result["langfuse"] = session.status
        return failed_result
    result["trace_capture"] = capture
    result["langfuse"] = session.status
    return result


def _init_session_state() -> None:
    defaults = {
        "description": "",
        "running": False,
        "pending_run": False,
        "trace": [],
        "assessment": None,
        "missing_facts": [],
        "evidence": [],
        "failure": None,
        "invocation_count": 0,
        "raw_answer": None,
        "displayed_answer": None,
        "citation_map": [],
        "unknown_references": [],
        "pending_review": None,
        "review_session_id": str(uuid.uuid4()),
        "reviewer_label": "",
        "review_error": None,
        "trace_persistence": None,
        "langfuse_export": None,
        "ui_view": "Assessment",
        "eval_scenario": "TRACE-S02",
        "eval_recompute": None,
        "eval_recompute_error": None,
        "eval_judge_fn_split": "validation",
        "eval_judge_fn_version": "v1",
        "memory_workspace_code": "",
        "memory_recalled_facts": [],
        "memory_last_results": [],
        "memory_last_action": None,
        "memory_run_context": None,
        "memory_role_explicit": False,
        "memory_language_explicit": False,
        "memory_name_explicit": False,
        "memory_explicit_project_name": "",
        "memory_explicit_role": "",
        "memory_explicit_language": "",
        "memory_widgets_ready": False,
        "memory_run_snapshot": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _clear_outputs() -> None:
    st.session_state.trace = []
    st.session_state.assessment = None
    st.session_state.missing_facts = []
    st.session_state.evidence = []
    st.session_state.failure = None
    st.session_state.raw_answer = None
    st.session_state.displayed_answer = None
    st.session_state.citation_map = []
    st.session_state.unknown_references = []
    st.session_state.pending_review = None
    st.session_state.review_error = None
    st.session_state.trace_persistence = None
    st.session_state.langfuse_export = None


def _load_example() -> None:
    st.session_state.description = SAMPLE_PREVIEW_PROMPT


def _queue_clear() -> None:
    if st.session_state.running:
        return
    _clear_outputs()


def _selected_runner():
    injected = st.session_state.get("preview_runner")
    if injected is not None:
        return injected
    if os.getenv("AEACUS_UI_DISABLE_LIVE") == "1":
        raise RuntimeError(
            "Live preview runner is disabled. Inject session_state['preview_runner']."
        )
    return run_preview_assessment


def _record_refs(records) -> list[dict]:
    refs: list[dict] = []
    for record in records or []:
        if not isinstance(record, dict):
            continue
        refs.append(
            {
                "label": record.get("label"),
                "record_id": record.get("record_id"),
            }
        )
    return refs


def _compact_event_payload(event: dict) -> dict:
    compact: dict = {}
    for key, value in (event or {}).items():
        if key == "payload" and isinstance(value, dict):
            compact[key] = {
                inner_key: inner_value
                for inner_key, inner_value in value.items()
                if inner_key not in {"matches", "context_records"}
            }
            compact[key]["matches"] = _record_refs(value.get("matches"))
            compact[key]["context_records"] = _record_refs(value.get("context_records"))
            continue
        compact[key] = value
    return compact


def _render_trace(events: list[dict]) -> None:
    if not events:
        st.caption("No agent activity yet.")
        return
    for event in events:
        kind = event.get("kind")
        if kind == "think":
            st.write(f"**THINK:** {event.get('action') or 'selected next action'}")
        elif kind == "act":
            st.write(f"**ACT:** `{event.get('tool') or 'unknown_tool'}`")
            query = event.get("query")
            if query:
                st.caption(f"Query: {query}")
        elif kind == "observe":
            status = event.get("status") or "unknown"
            matches = ", ".join(event.get("match_labels") or []) or "none"
            context = ", ".join(event.get("context_labels") or []) or "none"
            st.write(f"**OBSERVE:** status `{status}`")
            st.caption(f"Matched labels: {matches}")
            st.caption(f"Context labels: {context}")
        elif kind == "final":
            st.write("**FINAL:** Assessment ready")
        elif kind == "failed":
            st.write(f"**FAILED:** {event.get('message') or 'The run failed.'}")
        elif kind == "review_required":
            st.write(
                "**REVIEW_REQUIRED:** Human review of this exact draft is "
                "required before recording."
            )
        elif kind == "approved":
            st.write(
                "**APPROVED:** The self-declared reviewer accepted this exact draft."
            )
        elif kind == "rejected":
            st.write("**REJECTED:** The draft was not recorded.")
        elif kind == "recorded":
            st.write("**RECORDED:** The reviewed assessment was saved locally.")
            run_id = event.get("run_id")
            if run_id:
                st.caption(f"Run ID: {run_id}")

    with st.expander("Technical event details", expanded=False):
        st.caption("Raw event payloads from this run. Source text remains in Evidence.")
        persistence = st.session_state.get("trace_persistence") or {}
        if persistence.get("error"):
            st.caption(
                "TRACE capture did not save a complete record: "
                f"{persistence.get('error')}"
            )
        langfuse_export = st.session_state.get("langfuse_export") or {}
        if langfuse_export.get("attempted") and not langfuse_export.get("exported"):
            st.warning(
                "Langfuse export failed. The assessment and approval outcome "
                "are unchanged."
            )
            if langfuse_export.get("error"):
                st.caption(langfuse_export.get("error"))
        elif langfuse_export.get("flushed"):
            st.caption(
                "Langfuse flush completed. Remote retrieval is verified only "
                "by the dedicated connection smoke."
            )
        for event in events:
            kind = event.get("kind") or "event"
            st.caption(kind)
            st.code(
                json.dumps(_compact_event_payload(event), default=str, indent=2),
                language="json",
            )


def _render_evidence(cards: list[dict]) -> None:
    if not cards:
        st.caption("No retrieved evidence yet.")
        return

    st.caption(
        "Local lexical preview over the pinned Article 6, Annex III, and "
        "Article 113 classification subset."
    )
    for card in cards:
        role = "Search match" if card.get("role") == "match" else "Expanded context"
        label = card.get("label") or "Untitled record"
        st.markdown(f"**{role}** · {label}")
        with st.expander(f"{role}: {label}", expanded=False):
            st.caption(card.get("notice") or "")
            st.caption(
                f"Retrieval: {card.get('retrieval_mode')} · "
                f"Scope: {card.get('corpus_scope')}"
            )
            st.text(card.get("text") or "")
            record_id = card.get("record_id") or ""
            if record_id:
                st.caption("Record ID")
                st.code(record_id, language=None)
            url = card.get("url")
            if url:
                st.caption("Source URL")
                st.text(url)


def _execute_pending_run() -> None:
    description = (st.session_state.description or "").strip()
    using_test_runner = "preview_runner" in st.session_state
    if not description:
        st.session_state.running = False
        st.session_state.pending_run = False
        st.session_state.failure = (
            "[FAILED] Enter a system description before running an assessment."
        )
        return
    if not using_test_runner and not _google_api_key_is_configured():
        st.session_state.running = False
        st.session_state.pending_run = False
        st.session_state.failure = (
            "[FAILED] GOOGLE_API_KEY is not configured. The assessment cannot run."
        )
        return

    trace_slot = st.empty()

    def on_event(event: dict) -> None:
        st.session_state.trace.append(event)
        with trace_slot.container():
            _render_trace(st.session_state.trace)

    runner = _selected_runner()
    model_input = _prepare_assessment_user_message(description)
    try:
        result = runner(model_input, on_event)
    except Exception as exc:
        failure = (
            f"[FAILED] Provider/execution failure ({type(exc).__name__}): "
            f"{_redact_sensitive(str(exc))}"
        )
        on_event({"kind": "failed", "message": failure})
        result = {
            "ok": False,
            "failure": failure,
            "assessment": None,
            "missing_facts": [],
            "evidence": [],
            "raw_answer": None,
            "citation_map": [],
            "unknown_references": [],
        }

    capture = None
    langfuse_export = None
    if isinstance(result, dict):
        capture = result.pop("trace_capture", None)
        langfuse_export = result.pop("langfuse", None)
    st.session_state.langfuse_export = langfuse_export

    st.session_state.invocation_count = int(st.session_state.invocation_count) + 1
    st.session_state.running = False
    st.session_state.pending_run = False

    if result.get("ok"):
        st.session_state.failure = None
        st.session_state.assessment = result.get("assessment")
        st.session_state.missing_facts = result.get("missing_facts") or []
        st.session_state.evidence = result.get("evidence") or []
        st.session_state.raw_answer = result.get("raw_answer")
        st.session_state.displayed_answer = (
            result.get("displayed_answer") or result.get("assessment")
        )
        st.session_state.citation_map = result.get("citation_map") or []
        st.session_state.unknown_references = result.get("unknown_references") or []
        delivered = (
            result.get("displayed_answer")
            or result.get("assessment")
            or ""
        )
        pending = create_pending_review(
            session_id=st.session_state.review_session_id,
            system_description=description,
            assessment=delivered,
            evidence=result.get("evidence") or [],
            memory_used=st.session_state.get("memory_run_snapshot"),
        )
        st.session_state.pending_review = pending
        on_event(
            {
                "kind": "review_required",
                "run_id": pending["artifact"]["run_id"],
            }
        )
        if capture is not None and capture.record is not None:
            capture.record["timing_repair"] = result.get("timing_repair")
            capture.record["final_output"] = delivered
        _persist_streamlit_trace(
            capture,
            execution_status="ok",
            visible_answer=delivered,
            failure_message=None,
            pending_review=pending,
        )
        return

    st.session_state.assessment = None
    st.session_state.missing_facts = []
    st.session_state.evidence = result.get("evidence") or []
    st.session_state.raw_answer = result.get("raw_answer")
    st.session_state.citation_map = result.get("citation_map") or []
    st.session_state.unknown_references = result.get("unknown_references") or []
    st.session_state.pending_review = None
    st.session_state.failure = result.get("failure") or "[FAILED] The run failed."
    _persist_streamlit_trace(
        capture,
        execution_status="failed"
        if "timed out" not in str(st.session_state.failure).lower()
        else "timed_out",
        visible_answer=None,
        failure_message=st.session_state.failure,
        pending_review=None,
    )


MEMORY_WORKSPACE_CACHE_KEYS = (
    "memory_workspace_code",
    "memory_recalled_facts",
    "memory_last_results",
    "memory_last_action",
)


def _memory_store():
    injected = st.session_state.get("memory_store")
    if injected is not None:
        return injected
    return open_memory_store()


def _clear_memory_workspace_cache() -> None:
    """Drop workspace-bound recall and write results. Do not treat as durable memory."""
    st.session_state.memory_workspace_code = ""
    st.session_state.memory_recalled_facts = []
    st.session_state.memory_last_results = []
    st.session_state.memory_last_action = None
    st.session_state.memory_run_context = None
    st.session_state.memory_role_explicit = False
    st.session_state.memory_language_explicit = False
    st.session_state.memory_name_explicit = False
    st.session_state.memory_explicit_project_name = ""
    st.session_state.memory_explicit_role = ""
    st.session_state.memory_explicit_language = ""
    st.session_state.memory_widgets_ready = False
    st.session_state.memory_run_snapshot = None


def _clear_workspace_bound_assessment() -> None:
    _clear_outputs()
    st.session_state.memory_run_context = None
    st.session_state.memory_run_snapshot = None
    st.session_state.review_session_id = str(uuid.uuid4())


def _create_memory_workspace() -> None:
    _clear_workspace_bound_assessment()
    _clear_memory_workspace_cache()
    code = generate_workspace_code()
    st.session_state.memory_workspace_entry = code
    st.session_state.memory_workspace_code = code


def _connect_memory_workspace() -> None:
    entered = str(st.session_state.get("memory_workspace_entry") or "").strip()
    previous = str(st.session_state.get("memory_workspace_code") or "").strip()
    if entered != previous:
        _clear_workspace_bound_assessment()
        st.session_state.memory_recalled_facts = []
        st.session_state.memory_last_results = []
        st.session_state.memory_last_action = None
        st.session_state.memory_role_explicit = False
        st.session_state.memory_language_explicit = False
        st.session_state.memory_name_explicit = False
        st.session_state.memory_explicit_project_name = ""
        st.session_state.memory_explicit_role = ""
        st.session_state.memory_explicit_language = ""
        st.session_state.memory_widgets_ready = False
        st.session_state.memory_run_snapshot = None
    st.session_state.memory_workspace_code = entered


def _disconnect_memory_workspace() -> None:
    _clear_workspace_bound_assessment()
    _clear_memory_workspace_cache()
    st.session_state.memory_workspace_entry = ""


def _memory_widgets_accept_overrides() -> bool:
    return bool(st.session_state.get("memory_widgets_ready"))


def _mark_memory_name_explicit() -> None:
    if not _memory_widgets_accept_overrides():
        return
    st.session_state.memory_name_explicit = True
    st.session_state.memory_explicit_project_name = str(
        st.session_state.get("memory_project_name") or ""
    ).strip()


def _mark_memory_role_explicit() -> None:
    if not _memory_widgets_accept_overrides():
        return
    st.session_state.memory_role_explicit = True
    st.session_state.memory_explicit_role = str(
        st.session_state.get("memory_actor_role") or ""
    )


def _mark_memory_language_explicit() -> None:
    if not _memory_widgets_accept_overrides():
        return
    st.session_state.memory_language_explicit = True
    st.session_state.memory_explicit_language = str(
        st.session_state.get("memory_language") or ""
    )


def _explicit_memory_preferences() -> dict[str, str]:
    explicit: dict[str, str] = {}
    if st.session_state.get("memory_name_explicit"):
        name = str(st.session_state.get("memory_explicit_project_name") or "").strip()
        if name:
            explicit["project_name"] = name
    if st.session_state.get("memory_role_explicit"):
        role = str(st.session_state.get("memory_explicit_role") or "").strip()
        if role:
            explicit["declared_actor_role"] = role
    if st.session_state.get("memory_language_explicit"):
        language = str(st.session_state.get("memory_explicit_language") or "").strip()
        if language:
            explicit["preferred_response_language"] = language
    return explicit


def _prepare_assessment_user_message(system_description: str) -> str:
    from aeacus_agent.memory_context import (
        prepare_assessment_input,
        public_memory_run_view,
    )

    message, context, snapshot = prepare_assessment_input(
        system_description,
        store=_memory_store(),
        workspace_code=st.session_state.get("memory_workspace_code"),
        explicit=_explicit_memory_preferences(),
    )
    st.session_state.memory_run_context = public_memory_run_view(context)
    st.session_state.memory_run_snapshot = snapshot
    return message


def _result_payload(result) -> dict:
    payload = result.as_dict() if hasattr(result, "as_dict") else dict(result)
    payload.pop("value", None)
    return {
        "ok": payload.get("ok"),
        "status": payload.get("status"),
        "reason": payload.get("reason"),
        "field": payload.get("field"),
        "durable": payload.get("durable"),
        "mocked": payload.get("mocked"),
        "unavailable": payload.get("unavailable"),
        "fact_count": len(payload.get("facts") or []),
    }


def _save_project_memory() -> None:
    store = _memory_store()
    code = str(st.session_state.get("memory_workspace_code") or "")
    confirmed = st.session_state.get("memory_confirm_save") is True
    pairs = (
        ("project_name", st.session_state.get("memory_project_name")),
        ("declared_actor_role", st.session_state.get("memory_actor_role")),
        ("preferred_response_language", st.session_state.get("memory_language")),
    )
    results = []
    for field, value in pairs:
        if not str(value or "").strip():
            continue
        result = replace_fact(
            store,
            workspace_code=code,
            field=field,
            value=str(value),
            explicit_user_confirmation=confirmed,
            channel=ALLOWED_WRITE_CHANNEL,
        )
        results.append(_result_payload(result))
    st.session_state.memory_last_action = "save"
    st.session_state.memory_last_results = results


def _recall_project_memory() -> None:
    store = _memory_store()
    code = str(st.session_state.get("memory_workspace_code") or "")
    result = list_facts(store, workspace_code=code)
    st.session_state.memory_last_action = "recall"
    st.session_state.memory_last_results = [_result_payload(result)]
    if result.ok and not result.unavailable:
        st.session_state.memory_recalled_facts = list(result.facts)
    else:
        st.session_state.memory_recalled_facts = []


def _delete_project_memory_field() -> None:
    store = _memory_store()
    code = str(st.session_state.get("memory_workspace_code") or "")
    confirmed = st.session_state.get("memory_confirm_delete") is True
    field = str(st.session_state.get("memory_delete_field") or "")
    result = delete_fact(
        store,
        workspace_code=code,
        field=field,
        explicit_user_confirmation=confirmed,
        channel=ALLOWED_WRITE_CHANNEL,
    )
    st.session_state.memory_last_action = "delete"
    st.session_state.memory_last_results = [_result_payload(result)]
    st.session_state.memory_recalled_facts = []


def _render_memory_backend_results() -> None:
    action = st.session_state.get("memory_last_action")
    results = st.session_state.get("memory_last_results") or []
    if not action:
        return
    st.markdown("**Backend result**")
    if not results:
        st.info("No fields were submitted.")
        return
    for item in results:
        status = item.get("status") or "unknown"
        reason = item.get("reason")
        field = item.get("field")
        label = f"{field}: {status}" if field else str(status)
        if item.get("unavailable") or status == "memory_unavailable":
            st.error(f"{label} — memory is unavailable. Session state is not a substitute.")
        elif item.get("ok"):
            extra = " · not durable (mocked store)" if item.get("mocked") else ""
            if status == "unchanged":
                st.info(f"{label} — identical confirmed value left in place.{extra}")
            else:
                st.success(f"{label}{extra}")
        else:
            st.warning(f"{label}" + (f" ({reason})" if reason else ""))


def _render_recalled_facts() -> None:
    facts = st.session_state.get("memory_recalled_facts") or []
    st.markdown("**Recalled from Postgres**")
    st.caption(
        "This list is filled only by Recall saved memory. Draft form values "
        "and Streamlit session state are not treated as stored facts."
    )
    if not facts:
        st.caption("No recalled facts in this workspace.")
        return
    for fact in facts:
        st.write(f"**{fact.get('field')}** — {fact.get('value')}")
        st.caption(
            f"source: {fact.get('source') or 'user_declared'} · "
            f"saved: {fact.get('created_at') or 'unknown'} · "
            f"expires: {fact.get('expires_at') or 'unknown'}"
        )


def _render_project_memory_workspace() -> None:
    store = _memory_store()
    connected = bool(str(st.session_state.get("memory_workspace_code") or "").strip())
    with st.container(border=True):
        st.subheader("Project memory")
        st.caption(
            "User-declared project context only. Memory is not statutory evidence, "
            "not a classification, and not human approval. When a workspace is "
            "connected, Run assessment supplies these facts as user-declared "
            "context. Only a confirmed Save project memory writes memory."
        )
        if getattr(store, "durable", False) is False:
            reason = getattr(store, "reason", "unconfigured")
            st.warning(
                f"Durable memory is unavailable ({reason}). "
                "Nothing is written to session state or local files as a substitute."
            )
        else:
            st.caption("Writes target the configured Postgres store when you confirm a save.")

    with st.container(border=True):
        st.markdown("**Workspace access**")
        st.caption(
            "A private workspace code grants access to that workspace's facts. "
            "Keep it privately. Do not put it in URLs, logs, traces, reports, or screenshots. "
            "Create a new cryptographically random code, or enter an existing one."
        )
        st.text_input(
            "Workspace code",
            key="memory_workspace_entry",
            type="password",
        )
        create_col, use_col, leave_col = st.columns(3)
        with create_col:
            st.button(
                "Create private workspace",
                key="create_memory_workspace",
                on_click=_create_memory_workspace,
            )
        with use_col:
            st.button(
                "Use this workspace",
                key="use_memory_workspace",
                on_click=_connect_memory_workspace,
            )
        with leave_col:
            st.button(
                "Disconnect workspace",
                key="disconnect_memory_workspace",
                on_click=_disconnect_memory_workspace,
            )
        if connected:
            st.caption("Workspace connected. Recalled facts stay isolated to this code.")
        else:
            st.caption("No workspace connected.")

    with st.container(border=True):
        st.markdown("**Confirmed writes**")
        st.text_input(
            "Project name",
            key="memory_project_name",
            on_change=_mark_memory_name_explicit,
        )
        st.selectbox(
            "Declared actor role",
            options=list(ACTOR_ROLES),
            key="memory_actor_role",
            on_change=_mark_memory_role_explicit,
        )
        st.selectbox(
            "Preferred response language",
            options=list(LANGUAGES),
            key="memory_language",
            on_change=_mark_memory_language_explicit,
        )
        st.checkbox(
            "I confirm these values should be stored as user-declared project memory",
            key="memory_confirm_save",
        )
        save_clicked = st.button(
            "Save project memory",
            key="save_project_memory",
            type="primary",
            disabled=not connected,
        )
        if save_clicked:
            _save_project_memory()
        delete_col, confirm_col = st.columns([1.4, 1.0])
        with delete_col:
            st.selectbox(
                "Field to delete",
                options=list(ALLOWED_FIELDS),
                key="memory_delete_field",
            )
        with confirm_col:
            st.checkbox(
                "Confirm deletion",
                key="memory_confirm_delete",
            )
        delete_clicked = st.button(
            "Delete saved field",
            key="delete_memory_field",
            disabled=not connected,
        )
        if delete_clicked:
            _delete_project_memory_field()

    with st.container(border=True):
        st.markdown("**Cross-session recall**")
        st.caption(
            "Recall saved memory reads Postgres for this workspace. "
            "Clearing this browser tab is not a new process. For a demo, "
            "save in one session, then open a separate browser session, "
            "enter only the workspace code, and recall."
        )
        recall_clicked = st.button(
            "Recall saved memory",
            key="recall_saved_memory",
            disabled=not connected,
        )
        if recall_clicked:
            _recall_project_memory()
        _render_memory_backend_results()
        _render_recalled_facts()
    st.session_state.memory_widgets_ready = True


def _render_header() -> None:
    title_col, meta_col = st.columns([2.2, 1.3], vertical_alignment="bottom")
    with title_col:
        st.title("AeacusAI")
        st.caption("Evidence-backed AI risk classification")
    with meta_col:
        st.badge("Classification preview", color="primary")
        st.caption("Pinned edition 27 July 2026")
    with st.expander("Coverage and limits"):
        st.markdown(
            "This tool gives a provisional classification reading against the pinned "
            "EU AI Act classification subset (Article 6, Annex III, and Article 113) "
            "from the consolidated edition dated 27 July 2026. It is not a review of "
            "the whole Act."
        )
    st.radio(
        "Workspace",
        options=["Assessment", "Week 4 evaluations", "Project memory"],
        horizontal=True,
        key="ui_view",
    )


def _render_system_description(*, running: bool, can_submit: bool) -> bool:
    with st.container(border=True):
        st.subheader("System description")
        st.caption(
            "Describe the AI system in plain language. The agent searches only "
            "the pinned classification subset and does not issue a legal decision."
        )
        st.text_area(
            "System description",
            key="description",
            height=160,
            disabled=running,
            placeholder="Describe the AI system in plain language.",
            label_visibility="collapsed",
        )
        load_col, run_col, clear_col = st.columns([1.4, 1.2, 1.0])
        with load_col:
            st.button(
                "Load recruitment example",
                key="load_example",
                on_click=_load_example,
                disabled=running,
            )
        with run_col:
            run_clicked = st.button(
                "Run assessment",
                key="run_assessment",
                type="primary",
                disabled=not can_submit,
            )
        with clear_col:
            st.button(
                "Clear results",
                key="clear_results",
                on_click=_queue_clear,
                disabled=running,
            )
    return bool(run_clicked)


def _render_execution_panel(*, running: bool) -> None:
    with st.container(border=True):
        st.subheader("Execution")
        if running:
            st.info("Running assessment…")
        _render_trace(st.session_state.trace)


def _explicit_review_status() -> str | None:
    pending = st.session_state.get("pending_review") or {}
    status = pending.get("status")
    if status in {PENDING_STATUS, "recorded", "rejected"}:
        return status
    return None


def _render_assessment_body(assessment: str) -> None:
    st.badge("Provisional", color="gray")
    st.subheader("Provisional finding")
    sections = parse_assessment_sections(assessment)
    finding = sections.get("finding") or assessment
    st.markdown(finding, unsafe_allow_html=False)

    if sections.get("why"):
        st.markdown("**Why**")
        st.markdown(sections["why"], unsafe_allow_html=False)
    if sections.get("what_could_change"):
        st.markdown("**What could change this**")
        st.markdown(sections["what_could_change"], unsafe_allow_html=False)

    st.markdown("**Missing facts**")
    if st.session_state.missing_facts:
        for item in st.session_state.missing_facts:
            st.write(f"- {item}")
    else:
        st.caption("The assessment did not list additional facts.")

    if sections.get("timing"):
        st.markdown("**Timing and scope**")
        st.markdown(sections["timing"], unsafe_allow_html=False)


def _render_source_panel() -> None:
    st.subheader("Source evidence")
    _render_evidence(st.session_state.evidence)
    if st.session_state.unknown_references:
        st.warning(
            "Unknown source references were found in the answer. "
            "They were not among the records returned in this run."
        )
        for record_id in st.session_state.unknown_references:
            st.code(record_id, language=None)
    if st.session_state.citation_map:
        with st.expander("Observed source map", expanded=False):
            st.caption(
                "Short labels in the answer map to the full record IDs returned "
                "in this run."
            )
            for item in st.session_state.citation_map:
                st.write(f"**{item.get('label') or 'Untitled record'}**")
                st.code(item.get("record_id") or "", language=None)
    if st.session_state.raw_answer:
        with st.expander("Raw answer and full identifiers", expanded=False):
            st.text(st.session_state.raw_answer)


def _render_memory_run_disclosure() -> None:
    connected = bool(str(st.session_state.get("memory_workspace_code") or "").strip())
    ctx = st.session_state.get("memory_run_context")
    if connected and not ctx:
        st.caption(
            "A workspace is connected. Unexpired user-declared memory will be "
            "retrieved freshly when you run an assessment. Cached recall is not used."
        )
    if not ctx:
        return
    if ctx.get("unavailable"):
        st.warning(
            "Project memory was unavailable for this run "
            f"({ctx.get('reason') or 'memory_unavailable'}). "
            "No cached facts were used."
        )
        return
    if ctx.get("conflicts"):
        st.warning(
            "This run used current explicit preferences that differ from stored "
            "memory. Stored facts were not overwritten."
        )
        for item in ctx.get("conflicts") or []:
            st.caption(
                f"{item.get('field')}: stored {item.get('stored')} · "
                f"this run {item.get('used')}"
            )
    elif ctx.get("effective"):
        st.info(
            "This run included freshly retrieved user-declared project context. "
            "Memory is not statutory evidence and does not replace retrieval."
        )


def _render_assessment_workspace() -> None:
    if st.session_state.failure:
        st.error(st.session_state.failure)
        st.caption("No assessment is shown for a failed run.")
        return

    if not st.session_state.assessment:
        with st.container(border=True):
            st.subheader("Assessment")
            st.caption(
                "Enter a system description and run an assessment to produce a "
                "provisional classification reading. No finding, sources or "
                "review state are shown until a run completes."
            )
        return

    assess_col, evidence_col = st.columns(
        [1.35, 1],
        gap="medium",
        vertical_alignment="top",
    )
    with assess_col:
        with st.container(border=True):
            _render_assessment_body(st.session_state.assessment)
    with evidence_col:
        with st.container(border=True):
            _render_source_panel()


def _percent_label(value: float | None) -> str:
    if value is None:
        return "n/a"
    if float(value) == int(value):
        return f"{int(value)}%"
    return f"{value}%"


def _fraction_label(summary: dict) -> str:
    passed = summary.get("pass")
    denom = summary.get("denominator")
    if passed is None or denom is None:
        return "unavailable"
    return f"{passed}/{denom} passed ({_percent_label(summary.get('percent'))})"


def _timing_bar_label(name: str, summary: dict) -> str:
    passed = summary.get("pass")
    denom = summary.get("denominator")
    if passed is None or denom is None:
        return f"{name}: unavailable"
    return f"{name}: {passed}/{denom} ({_percent_label(summary.get('percent'))})"


def timing_comparison_bars(timing: dict) -> dict:
    """Two separate bars from saved assertion results. Not a stacked total."""
    raw = timing.get("raw") or {}
    delivered = timing.get("delivered") or {}
    rows = [
        {
            "layer": "Raw answers",
            "label": _timing_bar_label("Raw answers", raw),
            "passed": 0 if raw.get("pass") is None else int(raw["pass"]),
            "denominator": raw.get("denominator"),
        },
        {
            "layer": "Delivered after repair",
            "label": _timing_bar_label("Delivered after repair", delivered),
            "passed": 0 if delivered.get("pass") is None else int(delivered["pass"]),
            "denominator": delivered.get("denominator"),
        },
    ]
    denoms = [
        int(row["denominator"])
        for row in rows
        if row.get("denominator") is not None
    ]
    return {
        "rows": rows,
        "axis_max": max(denoms) if denoms else 0,
        "stacked": False,
    }


def _evaluations_loader():
    injected = st.session_state.get("evaluations_loader")
    if injected is not None:
        return injected
    import importlib

    from evals.week4 import evaluations_view as evaluations_view_module

    importlib.reload(evaluations_view_module)
    return evaluations_view_module.load_evaluations_view


def _offline_check_runner():
    injected = st.session_state.get("offline_check_runner")
    if injected is not None:
        return injected
    from evals.week4 import evaluations_view as evaluations_view_module

    return evaluations_view_module.run_offline_checks


def _render_eval_errors(errors: list) -> None:
    st.error(
        "Week 4 evaluation artifacts are missing, mismatched, or failed to "
        "evaluate. These are not success results."
    )
    for item in errors:
        if isinstance(item, dict):
            label = item.get("label") or item.get("code") or "error"
            path = item.get("path") or ""
            detail = item.get("detail") or json.dumps(item)
            st.error(f"{label}: {detail}" + (f" ({path})" if path else ""))
        else:
            st.error(str(item))


def _render_timing_comparison_chart(timing: dict) -> None:
    import altair as alt
    import pandas as pd

    spec = timing_comparison_bars(timing)
    rows = spec["rows"]
    axis_max = spec["axis_max"]
    frame = pd.DataFrame(rows)
    labels = [row["label"] for row in rows]
    tick_values = list(range(0, int(axis_max) + 1)) if axis_max else [0]
    chart = (
        alt.Chart(frame)
        .mark_bar()
        .encode(
            x=alt.X(
                "passed:Q",
                scale=alt.Scale(domain=[0, axis_max], nice=False, clamp=True),
                axis=alt.Axis(title="Passed count", values=tick_values),
            ),
            y=alt.Y(
                "label:N",
                sort=labels,
                title=None,
                axis=alt.Axis(labelLimit=0, labelPadding=8),
            ),
        )
        .properties(height=160)
        .configure_axisY(labelLimit=0)
    )
    st.altair_chart(chart, width="stretch")


def _render_timing_finding(timing: dict) -> None:
    raw = timing.get("raw") or {}
    delivered = timing.get("delivered") or {}
    with st.container(border=True):
        st.subheader(timing.get("title") or "Timing qualification checks")
        st.caption(timing.get("description") or "")
        st.markdown(f"Raw answers: {_fraction_label(raw)}")
        st.markdown(f"Delivered after repair: {_fraction_label(delivered)}")
        change = timing.get("change_pp")
        change_label = "n/a" if change is None else f"{change:+g} percentage points"
        st.markdown(f"Change: {change_label}")
        cols = st.columns(3)
        with cols[0]:
            st.metric("Raw answers", _fraction_label(raw))
        with cols[1]:
            st.metric("Delivered after repair", _fraction_label(delivered))
        with cols[2]:
            st.metric("Change", change_label)
        st.caption("Passed counts from the actual assertion results. Not a quality score.")
        _render_timing_comparison_chart(timing)
        st.caption(
            f"Checker: `{timing.get('checker_id')}` · suite `{timing.get('checker_suite')}`"
        )
        st.caption(
            f"Formatter: `{timing.get('formatter_id')}` version "
            f"{timing.get('formatter_version')}"
        )
        st.caption(
            "Unchanged assertion: "
            f"`{timing.get('unchanged_assertion_id')}` still uses the frozen "
            "retrieval-budget rule. Timing repair does not change retrieval."
        )
        if raw.get("fail_ids"):
            st.caption("Raw failures: " + ", ".join(raw["fail_ids"]))
        if delivered.get("fail_ids"):
            st.caption("Delivered failures: " + ", ".join(delivered["fail_ids"]))
        else:
            st.caption("Delivered failures: none")


def _render_f1_finding(finding: dict) -> None:
    n = finding.get("n_traces") or 0
    parent = finding.get("parent_fail_count")
    candidate = finding.get("candidate_fail_count")
    with st.container(border=True):
        st.subheader(finding.get("title") or "F1 prompt experiment — unsuccessful")
        st.markdown(
            f"Human-reviewed F1 failures: **{parent}/{n} → {candidate}/{n}**."
        )
        st.markdown(
            "Two recoveries, two regressions, three persistent failures."
        )
        st.caption(finding.get("note") or "")
        cols = st.columns(3)
        with cols[0]:
            st.caption("Recoveries")
            st.write(", ".join(finding.get("recoveries") or []) or "none")
        with cols[1]:
            st.caption("Regressions")
            st.write(", ".join(finding.get("regressions") or []) or "none")
        with cols[2]:
            st.caption("Persistent failures")
            st.write(", ".join(finding.get("persistent_failures") or []) or "none")
        st.info(
            "The candidate was not adopted. Parent instructions were restored. "
            "The timing renderer did not resolve F1. Candidate F2 remains unreviewed."
        )
        st.caption(
            f"Parent `{finding.get('parent_baseline_id')}` · "
            f"rejected candidate `{finding.get('candidate_baseline_id')}`"
        )


def _render_retrieval_finding(finding: dict) -> None:
    with st.container(border=True):
        st.subheader(finding.get("title") or "Retrieval regression check")
        calls = finding.get("parent_search_call_events")
        budget = finding.get("budget")
        denom = finding.get("denominator")
        excluded = finding.get("excluded")
        st.markdown(
            f"Original **{finding.get('scenario_id')}**: **{calls}** calls against "
            f"its scenario-specific budget of **{budget}**."
        )
        st.markdown("Timing repair leaves this unchanged.")
        st.caption(
            f"Applicability denominator is {denom}, with {excluded} excluded."
        )
        incidental = finding.get("f1_candidate_s19") or {}
        if incidental.get("search_call_events") is not None:
            st.caption(
                f"Rejected F1 candidate `{incidental.get('experiment')}` recorded "
                f"{incidental.get('search_call_events')} call on {finding.get('scenario_id')}. "
                "That result is incidental and belongs to that separate experiment."
            )


def _render_confusion_matrix(block: dict) -> None:
    matrix = block.get("confusion_matrix") or {}
    rows = matrix.get("row_labels") or []
    cols = matrix.get("column_labels") or []
    cells = matrix.get("cells") or []
    st.caption(
        "Confusion matrix: rows = reviewed F1 failure / reviewed F1 pass; "
        "columns = judge fail / judge pass. Failure is the positive class."
    )
    if len(rows) == 2 and len(cols) == 2 and len(cells) == 2:
        st.dataframe(
            {
                "": rows,
                cols[0]: [cells[0][0], cells[1][0]],
                cols[1]: [cells[0][1], cells[1][1]],
            },
            hide_index=True,
            width="stretch",
        )


def _render_judge_version(title: str, block: dict) -> None:
    st.markdown(f"**{title}**")
    st.markdown(
        f"TP={block.get('TP')} · FN={block.get('FN')} · "
        f"TN={block.get('TN')} · FP={block.get('FP')}"
    )
    st.markdown(f"TPR={(block.get('TPR') or {}).get('label')}")
    st.markdown(f"TNR={(block.get('TNR') or {}).get('label')}")
    coverage = block.get("coverage") or {}
    extra = " valid" if block.get("valid_n") == block.get("expected_n") else ""
    st.markdown(f"Coverage={coverage.get('label')}{extra}")
    if block.get("valid_response_only"):
        st.caption(
            "Rates are valid-response-only and do not cover every case in this split."
        )
    _render_confusion_matrix(block)
    st.caption(
        "100% TNR is not overall success. This is not an agreement headline."
    )


def _render_fn_inspector(judge: dict) -> None:
    st.markdown("**False-negative inspector**")
    split = st.radio(
        "Inspector split",
        options=["validation", "calibration"],
        horizontal=True,
        key="eval_judge_fn_split",
        index=0,
    )
    version = st.radio(
        "Inspector judge",
        options=["v1", "v2"],
        horizontal=True,
        key="eval_judge_fn_version",
        index=0,
    )
    rows = ((judge.get(split) or {}).get(version) or {}).get("false_negatives") or []
    if not rows:
        st.caption("No false negatives on this split and version.")
        return
    labels = [
        f"{row.get('scenario_id')} / {row.get('evaluation_id')}" for row in rows
    ]
    chosen = st.selectbox("False negative", options=labels, key="eval_judge_fn_case")
    row = rows[labels.index(chosen)]
    st.markdown("**Input**")
    st.write(row.get("input") or "")
    st.markdown("**Answer excerpt**")
    st.write(row.get("answer_excerpt") or "")
    st.markdown(
        f"Reviewed label: `{row.get('reviewed_label')}` · "
        f"Judge verdict: `{row.get('judge_verdict')}`"
    )
    st.markdown("**Judge reason**")
    st.write(row.get("judge_reason") or "")
    st.caption(
        "Source association: "
        f"scenario `{row.get('scenario_id')}` · "
        f"evaluation `{row.get('evaluation_id')}` · "
        f"case `{row.get('case_id')}` · "
        f"baseline `{row.get('baseline_id')}` · "
        f"run `{row.get('run_id')}`"
    )


def _render_judge_findings(judge: dict) -> None:
    with st.container(border=True):
        st.subheader("F1 judges — validation (default)")
        v1 = (judge.get("validation") or {}).get("v1") or {}
        v2 = (judge.get("validation") or {}).get("v2") or {}
        if judge.get("errors") or v1.get("TP") is None or v2.get("TP") is None:
            st.error(
                "Judge artifacts are missing, mismatched, or failed to evaluate. "
                "These are not success results."
            )
            for item in judge.get("errors") or []:
                if isinstance(item, dict):
                    st.error(item.get("detail") or json.dumps(item))
                else:
                    st.error(str(item))
            if v1.get("TP") is None or v2.get("TP") is None:
                st.error(
                    "Derived validation metrics are unavailable. "
                    "The view will not invent pass rates."
                )
            return
        st.warning(judge.get("decision") or "")
        st.caption(
            "Default split is validation. Calibration is shown separately below "
            "and is not mixed into one headline score."
        )
        left, right = st.columns(2)
        with left:
            _render_judge_version("Judge v1", (judge.get("validation") or {}).get("v1") or {})
        with right:
            _render_judge_version("Judge v2", (judge.get("validation") or {}).get("v2") or {})
        calibration = judge.get("calibration") or {}
        with st.expander("Calibration (separate from validation)", expanded=False):
            st.caption(
                "v2 prompt examples reused calibration cases. "
                "Calibration improvement did not transfer to validation."
                if not calibration.get(
                    "calibration_improvement_transferred_to_validation"
                )
                else "Calibration is still not a held-out result."
            )
            if calibration.get("v2_examples_reused_calibration_cases"):
                st.caption("v2 examples reused calibration cases.")
            cal_left, cal_right = st.columns(2)
            with cal_left:
                _render_judge_version("Calibration v1", calibration.get("v1") or {})
            with cal_right:
                _render_judge_version("Calibration v2", calibration.get("v2") or {})
        provenance = judge.get("provenance") or {}
        with st.expander("Golden-dataset provenance", expanded=False):
            st.markdown(
                f"- {provenance.get('n_outputs')} original outputs from "
                f"{provenance.get('n_paired_scenarios')} paired fictional dogfood scenarios"
            )
            st.markdown(
                f"- {provenance.get('f1_fail')} F1 failures / "
                f"{provenance.get('f1_pass')} passes"
            )
            st.markdown(
                f"- Calibration: {provenance.get('calibration_groups')} groups / "
                f"{provenance.get('calibration_outputs')} outputs"
            )
            st.markdown(
                f"- Validation: {provenance.get('validation_groups')} different groups / "
                f"{provenance.get('validation_outputs')} outputs"
            )
            if provenance.get("overlap"):
                st.error("Calibration and validation scenario groups overlap.")
            st.markdown(f"- {provenance.get('labels')}")
            st.markdown("- Same model family for agent and judge")
            st.markdown(
                "- Validation held out from judge refinement, not unseen capstone scenarios"
            )
            st.caption(
                "Full payloads remain local and gitignored at "
                f"`{provenance.get('payloads_path')}`."
            )
        _render_fn_inspector(judge)


def _render_taxonomy(taxonomy: dict) -> None:
    with st.container(border=True):
        st.subheader("Failure taxonomy")
        st.caption(taxonomy.get("priority_note") or "")
        st.caption(taxonomy.get("counting_rule") or "")
        rows = taxonomy.get("categories") or []
        if rows:
            for item in rows:
                st.markdown(
                    f"**{item.get('id')}** · priority {item.get('priority_weight')} · "
                    f"{item.get('fail_count')} failures  \n"
                    f"{item.get('title')}"
                )
        st.caption(
            f"First improvement target: {taxonomy.get('first_improvement_target')}. "
            "These are human-reviewed parent labels, not automated scores."
        )


def _render_scenario_inspector(model: dict) -> None:
    ids = model.get("scenario_ids") or []
    if not ids:
        st.warning("No scenarios are available.")
        return
    selected = st.session_state.get("eval_scenario") or "TRACE-S02"
    if selected not in ids:
        selected = ids[0]
        st.session_state.eval_scenario = selected
    st.selectbox("Scenario", options=ids, key="eval_scenario")
    detail = model.get("scenario") or {}
    if not detail.get("ok"):
        st.error(detail.get("error") or "Scenario detail is unavailable.")
        return
    failure = detail.get("failure_reason") or {}
    human_fails = failure.get("human_failures") or []
    raw_fails = failure.get("raw_automated_failures") or []
    delivered_fails = failure.get("delivered_automated_failures") or []
    st.caption(
        f"Parent run `{detail.get('parent_run_id')}` · "
        "Human labels and automated checkers are shown separately."
    )
    st.markdown("**Input**")
    st.write(detail.get("input") or "")
    st.markdown("**Failure reason**")
    if human_fails:
        for item in human_fails:
            st.write(
                f"- Human-reviewed {item.get('category')}: {item.get('title')}"
            )
    else:
        st.caption("No human-reviewed parent category failure on this scenario.")
    if raw_fails:
        for item in raw_fails:
            st.write(
                f"- Automated on raw model text (`{item.get('checker_id')}`): "
                + "; ".join(item.get("reasons") or [])
            )
    else:
        st.caption("No automated failure on the raw model text.")
    if delivered_fails:
        for item in delivered_fails:
            st.write(
                f"- Automated on delivered text (`{item.get('checker_id')}`): "
                + "; ".join(item.get("reasons") or [])
            )
    else:
        st.caption("No automated failure on the application-rendered text.")
    repair = detail.get("repair") or {}
    evidence = detail.get("article_113") or {}
    st.markdown("**Source provenance**")
    st.caption(
        f"Formatter `{repair.get('formatter_id')}` v{repair.get('formatter_version')} · "
        f"status `{repair.get('status')}`"
    )
    if repair.get("source_record_id"):
        st.code(repair.get("source_record_id"), language=None)
    if repair.get("source_text_sha256"):
        st.caption(f"Source text SHA-256: {repair.get('source_text_sha256')}")
    if repair.get("source_snapshot_id"):
        st.caption(f"Snapshot: {repair.get('source_snapshot_id')}")
    raw_col, delivered_col = st.columns(2)
    with raw_col:
        st.markdown("**Original raw answer**")
        st.caption("Raw model text. Not the delivered assessment.")
        preview = (detail.get("raw_output") or "")[:500]
        st.text(preview + ("…" if len(detail.get("raw_output") or "") > 500 else ""))
        with st.expander("Full raw model text", expanded=False):
            st.text(detail.get("raw_output") or "")
    with delivered_col:
        st.markdown("**Delivered answer**")
        st.caption("Application-rendered text after the timing formatter.")
        preview = (detail.get("delivered_output") or "")[:500]
        st.text(preview + ("…" if len(detail.get("delivered_output") or "") > 500 else ""))
        with st.expander("Full application-rendered text", expanded=False):
            st.text(detail.get("delivered_output") or "")
    with st.expander("Article 113 evidence", expanded=False):
        if not evidence:
            st.warning("No Article 113 observation was found on this saved trace.")
        else:
            st.write(evidence.get("label") or "Article 113")
            st.caption(f"Record ID: {evidence.get('record_id')}")
            st.caption(f"Snapshot: {evidence.get('source_snapshot_id')}")
            st.caption(f"Text SHA-256: {evidence.get('text_sha256')}")
            st.text(evidence.get("text") or "")


def _render_evaluations_view() -> None:
    st.subheader("Week 4 evaluations")
    st.caption(
        "Offline findings from frozen traces. This view does not call a model, "
        "retrieve sources, or open the review register."
    )
    if st.session_state.get("eval_recompute_error"):
        st.error(st.session_state.eval_recompute_error)

    loader = _evaluations_loader()
    try:
        model = loader(
            scenario_id=st.session_state.get("eval_scenario") or "TRACE-S02",
            recompute=st.session_state.get("eval_recompute"),
        )
    except Exception as exc:
        _render_eval_errors(
            [
                {
                    "code": "evaluation_error",
                    "label": "loader",
                    "path": "",
                    "detail": f"{type(exc).__name__}: {exc}",
                }
            ]
        )
        return

    if not isinstance(model, dict):
        _render_eval_errors(
            [{"code": "evaluation_error", "label": "loader", "path": "", "detail": "Loader returned no view model."}]
        )
        return

    source = model.get("source")
    if source == "recomputed":
        st.info(
            "Showing freshly recomputed offline checks. Historical reports were not overwritten."
        )
        if model.get("recompute_output_path"):
            st.caption(f"Stored separately at `{model.get('recompute_output_path')}`.")
    else:
        st.caption("Showing loaded historical results.")

    review = model.get("review") or {}
    if review:
        st.caption(
            f"Review: accepted by {review.get('accepted_by') or 'n/a'} on "
            f"{review.get('date') or 'n/a'}. Not: {review.get('not') or 'n/a'}"
        )
    st.caption(
        f"Baseline `{model.get('parent_baseline_id')}` · "
        f"F1 candidate `{model.get('candidate_baseline_id')}`"
    )
    st.caption(
        "These findings are separate. They are not an overall quality or "
        "compliance percentage. Candidate F2 remains unreviewed. "
        "Calibration and validation judge scores are not combined."
    )

    errors = model.get("errors") or []
    if errors or not model.get("ok"):
        _render_eval_errors(errors or [
            {
                "code": "evaluation_error",
                "label": "bundle",
                "path": "",
                "detail": "Evaluation bundle is not usable.",
            }
        ])
        run_col, _ = st.columns([1.2, 2])
        with run_col:
            if st.button("Run offline checks", key="run_offline_checks"):
                _execute_offline_checks()
                st.rerun()
        return

    _render_timing_finding(model.get("timing") or {})
    _render_f1_finding(model.get("f1") or {})
    _render_retrieval_finding(model.get("retrieval") or {})
    _render_judge_findings(model.get("judge") or {})
    _render_taxonomy(model.get("taxonomy") or {})
    with st.container(border=True):
        st.subheader("Scenario inspector")
        _render_scenario_inspector(model)
    with st.container(border=True):
        st.subheader("Offline checks")
        st.caption(
            "Rerun the frozen assertions and timing formatter against saved "
            "baseline traces. This does not collect new agent runs."
        )
        if st.button("Run offline checks", key="run_offline_checks"):
            _execute_offline_checks()
            st.rerun()


def _execute_offline_checks() -> None:
    runner = _offline_check_runner()
    try:
        result = runner()
    except Exception as exc:
        st.session_state.eval_recompute = None
        st.session_state.eval_recompute_error = (
            f"Offline checks failed ({type(exc).__name__}): {exc}"
        )
        return
    if not isinstance(result, dict) or not result.get("ok"):
        st.session_state.eval_recompute = result if isinstance(result, dict) else None
        errors = (result or {}).get("errors") if isinstance(result, dict) else []
        if errors:
            st.session_state.eval_recompute_error = "; ".join(
                item.get("detail") if isinstance(item, dict) else str(item)
                for item in errors
            )
        else:
            st.session_state.eval_recompute_error = (
                "Offline checks did not complete."
            )
        return
    st.session_state.eval_recompute = result
    st.session_state.eval_recompute_error = None


def main() -> None:
    st.set_page_config(
        page_title="AeacusAI — Classification Preview",
        layout="wide",
    )
    _init_session_state()

    running = bool(st.session_state.running)
    using_test_runner = "preview_runner" in st.session_state
    key_configured = _google_api_key_is_configured()
    description_ready = bool((st.session_state.description or "").strip())
    can_submit = description_ready and not running and (
        key_configured or using_test_runner
    )

    _render_header()

    if st.session_state.get("ui_view") == "Week 4 evaluations":
        _render_evaluations_view()
        return

    if st.session_state.get("ui_view") == "Project memory":
        _render_project_memory_workspace()
        return

    if not key_configured and not using_test_runner:
        st.warning(
            "GOOGLE_API_KEY is not configured. The assessment cannot run until "
            "that environment variable is set."
        )

    run_clicked = _render_system_description(
        running=running, can_submit=can_submit
    )
    _render_memory_run_disclosure()

    if run_clicked and not running:
        _clear_outputs()
        st.session_state.running = True
        st.session_state.pending_run = True
        st.rerun()

    if st.session_state.running and st.session_state.pending_run:
        _execute_pending_run()
        st.rerun()

    _render_execution_panel(running=bool(st.session_state.running))
    _render_assessment_workspace()
    _render_human_review(running=bool(st.session_state.running))


def _review_db_path() -> Path:
    injected = st.session_state.get("review_db_path")
    if injected:
        return Path(injected)
    return DEFAULT_DB_PATH


def _delivered_assessment() -> str:
    return (
        st.session_state.get("displayed_answer")
        or st.session_state.get("assessment")
        or ""
    )


def _pending_is_valid() -> bool:
    pending = st.session_state.get("pending_review")
    if not pending or pending.get("status") != PENDING_STATUS:
        return False
    return artifact_matches(
        pending,
        session_id=st.session_state.review_session_id,
        system_description=(st.session_state.description or "").strip(),
        assessment=_delivered_assessment(),
        evidence=st.session_state.evidence or [],
    )


def _apply_approval() -> None:
    pending = st.session_state.get("pending_review")
    result = approve_and_record(
        pending,
        session_id=st.session_state.review_session_id,
        reviewer_label=st.session_state.get("reviewer_label") or "",
        current_system_description=(st.session_state.description or "").strip(),
        current_assessment=_delivered_assessment(),
        current_evidence=st.session_state.evidence or [],
        db_path=_review_db_path(),
    )
    if not result.get("ok"):
        st.session_state.review_error = result.get("status") or "not_recorded"
        return
    st.session_state.review_error = None
    st.session_state.trace.append({"kind": "approved", "run_id": result.get("run_id")})
    st.session_state.trace.append(
        {
            "kind": "recorded",
            "run_id": result.get("run_id"),
            "digest": result.get("digest"),
        }
    )
    if pending:
        pending["status"] = "recorded"
        st.session_state.pending_review = pending


def _apply_rejection() -> None:
    pending = st.session_state.get("pending_review")
    result = reject_draft(
        pending, session_id=st.session_state.review_session_id
    )
    if not result.get("ok"):
        st.session_state.review_error = result.get("status") or "not_rejected"
        return
    st.session_state.review_error = None
    st.session_state.trace.append({"kind": "rejected", "run_id": result.get("run_id")})
    if pending:
        pending["status"] = "rejected"
        st.session_state.pending_review = pending


def _render_bound_artifact(pending: dict, *, expanded: bool) -> None:
    artifact = pending.get("artifact") or {}
    with st.expander("Exact draft and bound evidence", expanded=expanded):
        st.caption(f"Run ID: {artifact.get('run_id')}")
        st.caption("This is the exact text bound to the pending review digest.")
        st.markdown("**Original input**")
        st.text(artifact.get("system_description") or "")
        st.markdown("**Delivered answer**")
        st.markdown(artifact.get("assessment") or "", unsafe_allow_html=False)
        memory_used = artifact.get("memory_used")
        st.markdown("**User-declared memory used for this assessment**")
        if not memory_used:
            st.caption("No workspace memory was bound to this draft.")
        else:
            st.caption(
                "Immutable snapshot from the fresh read used for this run. "
                "Approval does not reload memory."
            )
            for item in memory_used.get("fields") or []:
                st.write(f"**{item.get('field')}** — {item.get('value')}")
                st.caption(
                    f"source: {item.get('source') or 'user_declared'} · "
                    f"saved: {item.get('created_at') or 'unknown'} · "
                    f"expires: {item.get('expires_at') or 'unknown'} · "
                    f"origin: {item.get('origin') or 'stored'}"
                )
        bound = artifact.get("evidence") or []
        if not bound:
            st.caption("No evidence identities were bound to this draft.")
            return
        st.markdown("**Evidence identities bound to this draft**")
        for item in bound:
            st.write(item.get("record_id") or "")
            st.caption(
                f"Snapshot: {item.get('source_snapshot_id') or 'n/a'} · "
                f"Text hash: {item.get('text_sha256') or 'n/a'}"
            )


def _render_human_review(*, running: bool) -> None:
    pending = st.session_state.get("pending_review")
    assessment_ok = bool(st.session_state.assessment) and not st.session_state.failure
    if not assessment_ok and not pending:
        return

    review_status = _explicit_review_status()
    with st.container(border=True):
        st.subheader("Human review")

        if st.session_state.failure:
            st.caption("A failed assessment cannot be approved or recorded.")
            return

        if review_status == "recorded":
            st.badge("Recorded", color="green")
            st.success("This draft was recorded in the local review register.")
            _render_bound_artifact(pending, expanded=False)
            return
        if review_status == "rejected":
            st.badge("Rejected", color="gray")
            st.warning("This draft was rejected. Nothing was recorded.")
            _render_bound_artifact(pending, expanded=False)
            return

        st.info(
            "Recording marks this provisional assessment as human-reviewed. "
            "It is not a legal certification or conformity decision. "
            "Pending approval lives only in this browser session and is not a login."
        )

        valid = _pending_is_valid()
        if pending and not valid:
            st.warning(
                "The current input, assessment or evidence no longer matches the "
                "draft waiting for review. Run the assessment again to create a "
                "new draft."
            )
            return
        if not pending:
            return

        st.badge("Pending human review", color="orange")
        st.caption("This draft is waiting for a self-declared human decision.")
        _render_bound_artifact(pending, expanded=True)

        st.text_input(
            "Reviewer label (self-declared)",
            key="reviewer_label",
            disabled=running,
            help="A name or initials you declare for this local review. Not an account.",
        )
        if st.session_state.review_error:
            st.error(f"Recording was not completed ({st.session_state.review_error}).")

        approve_col, reject_col = st.columns(2)
        label_ready = bool((st.session_state.get("reviewer_label") or "").strip())
        with approve_col:
            approve_clicked = st.button(
                "Approve and record",
                key="approve_and_record",
                type="primary",
                disabled=running or not valid or not label_ready,
            )
        with reject_col:
            reject_clicked = st.button(
                "Reject draft",
                key="reject_draft",
                disabled=running or not valid,
            )

        if approve_clicked:
            _apply_approval()
            st.rerun()
        if reject_clicked:
            _apply_rejection()
            st.rerun()


def _should_render() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
    except Exception:
        return False
    return get_script_run_ctx() is not None


if _should_render():
    main()
