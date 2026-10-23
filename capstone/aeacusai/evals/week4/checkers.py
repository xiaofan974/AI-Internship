"""Deterministic Week 4 checkers. No model calls and no human labels."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

SEARCH_TOOL = "preview_classification_search"
ACT_KIND = "act"
S19_SCENARIO_ID = "TRACE-S19"
MAX_S19_SEARCH_CALLS = 2
TIMING_HEADING = "Timing and scope"

CHECKER_SUITE_ID = "week4_codify_v1"
DEFERRED_DATE_CHECKER_ID = "deferred_date_qualifications_v1"
S19_BUDGET_CHECKER_ID = "s19_retrieval_budget_v1"

CHECKER_CONFIG = {
    "suite_id": CHECKER_SUITE_ID,
    "uses_human_labels": False,
    "assertions": {
        DEFERRED_DATE_CHECKER_ID: {
            "inspects": TIMING_HEADING,
            "trigger": "December 2027 or August 2028 deferral summary",
            "required_markers": [
                "Chapter III",
                "Sections 1–3 or an equivalent list/range",
                "Article 6(5) exception",
            ],
            "semantic_completeness": False,
            "note": (
                "This checks explicit qualification markers in Timing and "
                "scope, not complete semantic correctness."
            ),
        },
        S19_BUDGET_CHECKER_ID: {
            "scenario_id": S19_SCENARIO_ID,
            "max_preview_classification_search_calls": MAX_S19_SEARCH_CALLS,
            "count": "act events named preview_classification_search",
            "not_counted": ["observe events", "distinct query strings"],
            "scope": (
                "Scenario-specific regression rule, not a universal agent limit."
            ),
        },
    },
}

_HEADING_RE = re.compile(
    r"(?im)^(?:#{1,6}\s*)?(?:\*\*)?Timing and scope(?:\*\*)?\s*$"
)
_NEXT_HEADING_RE = re.compile(r"(?im)^#{1,6}\s+\S+")
_DEC_2027_RE = re.compile(
    r"(?i)\b(?:\d{1,2}(?:st|nd|rd|th)?\s+)?December\s+2027\b"
)
_AUG_2028_RE = re.compile(
    r"(?i)\b(?:\d{1,2}(?:st|nd|rd|th)?\s+)?August\s+2028\b"
)
_CHAPTER_III_RE = re.compile(r"(?i)\bChapter\s+(?:III|3)\b")
_SECTIONS_1_3_RE = re.compile(
    r"(?i)\bSections?\s+"
    r"(?:"
    r"1\s*[–—−-]\s*3"
    r"|1\s*,\s*2\s*,\s*(?:and\s+)?3"
    r"|1\s*,\s*2\s+and\s+3"
    r"|1\s+to\s+3"
    r"|1\s+through\s+3"
    r")\b"
)
_ARTICLE_65 = r"Article\s*6\s*\(\s*5\s*\)"
_ARTICLE_65_EXCEPTION_RE = re.compile(
    rf"(?i)(?:"
    rf"(?:with\s+the\s+)?exception\s+of\s+{_ARTICLE_65}"
    rf"|except(?:ing)?(?:\s+for)?\s+{_ARTICLE_65}"
    rf"|excluding\s+{_ARTICLE_65}"
    rf"|{_ARTICLE_65}\s+exception"
    rf")"
)


@dataclass
class AssertionResult:
    checker_id: str
    scenario_id: str | None
    run_id: str | None
    applicable: bool
    result: str
    reasons: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "checker_id": self.checker_id,
            "scenario_id": self.scenario_id,
            "run_id": self.run_id,
            "applicable": self.applicable,
            "result": self.result,
            "reasons": list(self.reasons),
            "evidence": dict(self.evidence),
        }


def extract_timing_and_scope(text: str | None) -> str | None:
    if not text:
        return None
    match = _HEADING_RE.search(text)
    if not match:
        return None
    rest = text[match.end() :]
    nxt = _NEXT_HEADING_RE.search(rest)
    if nxt:
        rest = rest[: nxt.start()]
    return rest.strip()


def mentions_deferral_date(section: str) -> bool:
    return bool(_DEC_2027_RE.search(section) or _AUG_2028_RE.search(section))


def qualification_markers(section: str) -> dict[str, bool]:
    return {
        "chapter_iii": bool(_CHAPTER_III_RE.search(section)),
        "sections_1_to_3": bool(_SECTIONS_1_3_RE.search(section)),
        "article_6_5_exception": bool(_ARTICLE_65_EXCEPTION_RE.search(section)),
    }


def visible_answer(trace: dict[str, Any]) -> str:
    return str(trace.get("final_output") or "")


def count_preview_classification_search_calls(events: Any) -> int:
    """Count search call events only. Responses and query strings are ignored."""
    count = 0
    for event in events or []:
        if not isinstance(event, dict):
            continue
        if event.get("kind") == ACT_KIND and event.get("tool") == SEARCH_TOOL:
            count += 1
    return count


def check_deferred_date_qualifications(trace: dict[str, Any]) -> AssertionResult:
    scenario_id = trace.get("scenario_id")
    run_id = trace.get("run_id")
    section = extract_timing_and_scope(visible_answer(trace))
    if section is None:
        return AssertionResult(
            checker_id=DEFERRED_DATE_CHECKER_ID,
            scenario_id=scenario_id,
            run_id=run_id,
            applicable=False,
            result="not_applicable",
            reasons=["No Timing and scope section to inspect."],
            evidence={"timing_and_scope_present": False},
        )
    if not mentions_deferral_date(section):
        return AssertionResult(
            checker_id=DEFERRED_DATE_CHECKER_ID,
            scenario_id=scenario_id,
            run_id=run_id,
            applicable=False,
            result="not_applicable",
            reasons=[
                "Timing and scope does not summarize the December 2027 or "
                "August 2028 deferral."
            ],
            evidence={
                "timing_and_scope_present": True,
                "mentions_december_2027": bool(_DEC_2027_RE.search(section)),
                "mentions_august_2028": bool(_AUG_2028_RE.search(section)),
            },
        )
    markers = qualification_markers(section)
    missing = [name for name, present in markers.items() if not present]
    evidence = {
        "timing_and_scope_present": True,
        "mentions_december_2027": bool(_DEC_2027_RE.search(section)),
        "mentions_august_2028": bool(_AUG_2028_RE.search(section)),
        **markers,
        "checks_explicit_markers_only": True,
    }
    if missing:
        readable = {
            "chapter_iii": "Chapter III",
            "sections_1_to_3": "Sections 1–3",
            "article_6_5_exception": "Article 6(5) exception",
        }
        listed = ", ".join(readable[name] for name in missing)
        return AssertionResult(
            checker_id=DEFERRED_DATE_CHECKER_ID,
            scenario_id=scenario_id,
            run_id=run_id,
            applicable=True,
            result="fail",
            reasons=[
                "Timing and scope summarizes a December 2027 or August 2028 "
                f"deferral but omits explicit qualification marker(s): {listed}."
            ],
            evidence=evidence,
        )
    return AssertionResult(
        checker_id=DEFERRED_DATE_CHECKER_ID,
        scenario_id=scenario_id,
        run_id=run_id,
        applicable=True,
        result="pass",
        reasons=[
            "Timing and scope names Chapter III, Sections 1–3, and the "
            "Article 6(5) exception when summarizing the deferral."
        ],
        evidence=evidence,
    )


def check_s19_retrieval_budget(trace: dict[str, Any]) -> AssertionResult:
    scenario_id = trace.get("scenario_id")
    run_id = trace.get("run_id")
    call_count = count_preview_classification_search_calls(trace.get("events"))
    evidence = {
        "search_call_events": call_count,
        "max_allowed_calls": MAX_S19_SEARCH_CALLS,
        "counted": "act events named preview_classification_search",
        "not_counted": ["observe events", "distinct query strings"],
    }
    if scenario_id != S19_SCENARIO_ID:
        return AssertionResult(
            checker_id=S19_BUDGET_CHECKER_ID,
            scenario_id=scenario_id,
            run_id=run_id,
            applicable=False,
            result="not_applicable",
            reasons=[
                f"{S19_BUDGET_CHECKER_ID} applies only to {S19_SCENARIO_ID}."
            ],
            evidence=evidence,
        )
    if call_count > MAX_S19_SEARCH_CALLS:
        return AssertionResult(
            checker_id=S19_BUDGET_CHECKER_ID,
            scenario_id=scenario_id,
            run_id=run_id,
            applicable=True,
            result="fail",
            reasons=[
                f"{S19_SCENARIO_ID} made {call_count} "
                f"{SEARCH_TOOL} call events; at most "
                f"{MAX_S19_SEARCH_CALLS} are allowed."
            ],
            evidence=evidence,
        )
    return AssertionResult(
        checker_id=S19_BUDGET_CHECKER_ID,
        scenario_id=scenario_id,
        run_id=run_id,
        applicable=True,
        result="pass",
        reasons=[
            f"{S19_SCENARIO_ID} made {call_count} {SEARCH_TOOL} "
            f"call event(s), which is within the limit of "
            f"{MAX_S19_SEARCH_CALLS}."
        ],
        evidence=evidence,
    )


def run_deterministic_assertions(trace: dict[str, Any]) -> dict[str, AssertionResult]:
    return {
        DEFERRED_DATE_CHECKER_ID: check_deferred_date_qualifications(trace),
        S19_BUDGET_CHECKER_ID: check_s19_retrieval_budget(trace),
    }
