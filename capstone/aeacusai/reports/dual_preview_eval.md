# Two-agent SequentialAgent preview checkpoint

Generated: 2026-10-22T20:04:10.487743+00:00

This is a separate CLI demo. The Streamlit app, direct Python preview
tool, single-agent MCP path, and human approval register are unchanged.
The critic verdict is automated evidence critique, not legal certification.

## Installed versions

- Python: `3.12.13` (`/Users/aureliemahe/AI-Internship/capstone/aeacusai/.venv/bin/python`)
- google-adk: `2.12.0`
- mcp: `1.25.0`
- google-genai: `2.32.0`
- Model: `gemini-3.8-flash`

## Offline checks (mocked / no live model)

- Unittest: **PASS**
- Orchestration: SequentialAgent `aeacus_dual_preview` with `aeacus_classifier` then `aeacus_evidence_critic`
- Classifier tools: `['preview_classification_search']` through MCP
- Critic tools: none
- Fabricated citations and altered statutory quotations fail deterministic checks

## Live two-agent run

- Execution: **ok**
- Invocations used: 1
- Register opened: False
- Handoff ok: True
- Handoff error: None

### Two-agent trace

1. `aeacus_classifier` -> `preview_classification_search` query='recruitment candidate filtering rank job applications Annex III Article 6'

- Observation statuses: `[{"call_id": "call_147357", "tool": "preview_classification_search", "query": "recruitment candidate filtering rank job applications Annex III Article 6", "status": "ok"}]`

### Classifier draft

```
### Provisional finding
The AI system is provisionally classified as high-risk pursuant to Article 6(2) and Annex III, point 4, subject to whether an exception under Article 6(3) is substantiated.

### Why
Annex III, point 4(a) specifically covers AI systems intended to be used for the recruitment or selection of natural persons, particularly to analyse and filter job applications and evaluate candidates. Under Article 6(2), systems listed in Annex III are considered high-risk. The stated core functionalities—analysing applications, filtering candidates, and ranking them for recruiters—fall squarely within the use case described in Annex III, point 4(a).

### What could change this
Under Article 6(3), an AI system referred to in Annex III is not considered high-risk if it does not pose a significant risk of harm to the health, safety, or fundamental rights of natural persons, including by not materially influencing the outcome of decision-making, provided it meets at least one of four specific conditions:
1. It is intended to perform a narrow procedural task;
2. It is intended to improve the result of a previously completed human activity;
3. It is intended to detect decision-making patterns or deviations without replacing or influencing a previously completed human assessment without proper human review; or
4. It is intended to perform a preparatory task to an assessment.

The fact that recruiters make the final hiring decision does not in itself exempt the system. If the AI system materially influences recruiter decisions or screens candidates out, it would not meet the threshold of not materially influencing the outcome. Moreover, under Article 6(3), if the system performs profiling of natural persons, it remains high-risk regardless of any other conditions. If an exception under Article 6(3) is claimed, Article 6(4) mandates documenting the assessment before placing the system on the market or putting it into service.

### Missing facts
To conclude whether an exception applies, several facts are required:
- Whether the system carries out profiling of natural persons;
- The operational workflow between the AI outputs and the recruiter (for instance, whether low-ranked or filtered applications are completely excluded from human review or merely ordered on a screen);
- The technical scope of the analysis (such as basic administrative pre-checks versus substantive scoring of skills and personality);
- The legal role of the company (provider or deployer) and whether provider documentation under Article 6(4) exists.

### Timing and scope
This provisional reading is strictly limited to the classification subset of Article 6, Annex III, and Article 113, and does not determine overall compliance or prohibitions under the broader framework. Under Article 113(c)(i), Chapter III, Sections 1, 2, and 3—with the exception of Article 6(5)—apply from 2 December 2027 to AI systems classified as high-risk under Article 6(2) and Annex III.
```

### Critic verdict (model)

- Verdict: `supported`
- Parse ok: True

```
[]
```

Scope note: Assessment is confined to the retrieved classification subset of Article 6, Annex III (specifically point 4), and Article 113. This automated critique verifies evidence alignment and does not constitute legal certification or approval.

### Deterministic checks (application-owned, separate from the model)

```
{
  "citation_ids": {
    "ok": true,
    "cited": [],
    "unknown": []
  },
  "provisions": {
    "cited": [
      "Article 6(2)",
      "Annex III, point 4",
      "Article 6(3)",
      "Article 6(4)",
      "Article 6",
      "Article 113",
      "Article 113(c)",
      "Article 6(5)"
    ],
    "unsupported": [],
    "ok": true
  },
  "quotations": {
    "ok": true,
    "checked": [],
    "unsupported": []
  },
  "ok": true
}
```

### Evidence IDs captured from this run's MCP observations

```
[
  "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::annex/III/point/4",
  "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/6/paragraph/3",
  "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/6/paragraph/6",
  "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::annex/III/point/6",
  "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/6/paragraph/4",
  "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::annex/III",
  "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/6",
  "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/113"
]
```

### Cleanup

```
{
  "ok": true,
  "leftover_child_pids": [],
  "close_error": null
}
```

## Limits

One SequentialAgent live run is not independent legal certification,
approval, or readiness for registration. `supported` means only that the
draft was supported within the supplied evidence and limited subset.

