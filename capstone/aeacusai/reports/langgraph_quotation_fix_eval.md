# LangGraph quotation-check fix verification

Generated: 2026-10-22T20:16:21.147229+00:00

The original failed live report (`langgraph_preview_eval.json`) is unchanged.
This file records offline tests, saved-artifact replay, and one new live run.

## Offline tests

- LangGraph tests (`.venv-langgraph`): **PASS**
- Evidence-check tests (ADK `.venv`): **PASS**
- Dual-preview tests (ADK `.venv`): **PASS**
- Streamlit tests (ADK `.venv`): **PASS**

## Saved-artifact replay

- Source: `langgraph_preview_eval.json`
- Original status: `failed`
- Artifacts sufficient for quotation replay: False
- Provider calls: 0
- Retrieval calls: 0

The original live report preserved the draft, record IDs, hashes, and compact observation metadata, but not complete source text or full tool payloads. Corrected quotation checks were not replayed against reconstructed corpus text.

### Original failure

```
{
  "citation_ids": {
    "ok": true,
    "cited": [],
    "unknown": []
  },
  "provisions": {
    "cited": [
      "Article 6",
      "Article 6(2)",
      "Annex III, point 4",
      "Article 6(3)",
      "Article 6(4)",
      "Article 113",
      "Article 113(c)",
      "Article 6(5)"
    ],
    "unsupported": [],
    "ok": true
  },
  "quotations": {
    "ok": false,
    "checked": [
      "AI systems intended to be used for the recruitment or selection of natural persons, in particular to place targeted job advertisements, to analyse and filter job applications, and to evaluate candidates;",
      "Notwithstanding the first subparagraph, an AI system referred to in Annex III shall always be considered to be high-risk where the AI system performs profiling of natural persons.",
      "\"AI systems intended to be used for the recruitment or selection of natural persons, in particular to place targeted job advertisements, to analyse and filter job applications, and to evaluate candidates;\"",
      "\"Notwithstanding the first subparagraph, an AI system referred to in Annex III shall always be considered to be high-risk where the AI system performs profiling of natural persons.\""
    ],
    "unsupported": [
      "\"AI systems intended to be used for the recruitment or selection of natural persons, in particular to place targeted job advertisements, to analyse and filter job applications, and to evaluate candidates;\"",
      "\"Notwithstanding the first subparagraph, an AI system referred to in Annex III shall always be considered to be high-risk where the AI system performs profiling of natural persons.\""
    ]
  },
  "ok": false
}
```

### Replay (no reconstructed evidence)

```
{
  "citation_ids": {
    "ok": true,
    "cited": [],
    "unknown": []
  },
  "provisions": {
    "cited": [
      "Article 6",
      "Article 6(2)",
      "Annex III, point 4",
      "Article 6(3)",
      "Article 6(4)",
      "Article 113",
      "Article 113(c)",
      "Article 6(5)"
    ],
    "unsupported": [],
    "ok": true
  },
  "quotations": {
    "skipped": true,
    "reason": "Saved records include IDs and hashes but not complete source text, and observations omit full tool payloads. Quotation replay would require reconstructing evidence."
  }
}
```

## New live LangGraph run

- Execution: **ok**
- Status: `review_required`
- Model calls: 2
- Register opened: False
- Register written: False

### Trace

```
[
  {
    "kind": "act",
    "tool": "preview_classification_search",
    "query": "recruitment candidates filter job applications Article 6 Annex III",
    "call_id": "call_26285"
  },
  {
    "kind": "observe",
    "call_id": "call_26285",
    "tool": "preview_classification_search",
    "query": "recruitment candidates filter job applications Article 6 Annex III",
    "status": "ok",
    "match_record_ids": [
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::annex/III/point/4",
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/6/paragraph/3",
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/6/paragraph/6",
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::annex/III/point/6",
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/6/paragraph/4"
    ],
    "context_record_ids": [
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::annex/III",
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/6",
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/113"
    ]
  },
  {
    "kind": "final",
    "chars": 2912
  },
  {
    "kind": "review_required",
    "checks_ok": true
  }
]
```

### Draft

```
### Provisional finding

The AI system provisionally falls within the classification of a high-risk AI system under Article 6(2) and Annex III, point 4(a), subject to the potential application of the derogation under Article 6(3).

### Why

Under Annex III, point 4(a), high-risk AI systems include those intended to be used for the recruitment or selection of natural persons, notably to analyse and filter job applications and to evaluate candidates. The submitted system is described as analysing and filtering job applications and ranking candidates for recruiters. Because these functions align directly with the employment use cases identified in Annex III, point 4(a), the system is considered high-risk under Article 6(2) unless an exception applies. The fact that human recruiters make the final hiring decision does not automatically exclude the tool from Annex III, point 4(a).

### What could change this

Under Article 6(3), an AI system referred to in Annex III is not considered high-risk where it does not pose a significant risk of harm to the health, safety, or fundamental rights of natural persons, including by not materially influencing the outcome of decision-making. To benefit from this derogation, the system must satisfy at least one of four conditions:
- performing a narrow procedural task;
- improving the result of a previously completed human activity;
- detecting decision-making patterns or deviations without replacing or influencing the human assessment without proper human review; or
- performing a preparatory task to an assessment relevant for the use cases listed in Annex III.

However, pursuant to Article 6(3), the system is always considered high-risk if it performs profiling of natural persons. Furthermore, if a provider concludes that a system is not high-risk under Article 6(3), Article 6(4) requires the provider to document its assessment before placing the system on the market or putting it into service.

### Missing facts

To determine whether the system remains high-risk or qualifies for an Article 6(3) derogation, several factual elements must be established:
- The exact operational effect of the AI’s ranking and filtering on recruiter evaluations, including whether low-ranked candidates are de facto excluded from human review;
- The technical design of the tool, including whether its functions are limited to narrow procedural or purely preparatory tasks;
- Whether the candidate evaluation involves profiling of natural persons;
- Whether the provider has documented a non-high-risk assessment pursuant to Article 6(4).

### Timing and scope

This assessment is a provisional reading limited strictly to the pinned classification subset: Article 6, Annex III, and Article 113. Under Article 113(c)(i), high-risk requirements for systems classified under Article 6(2) and Annex III apply from 2 December 2027, with the exception of Article 6(5).
```

### Deterministic checks

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

## Limits

This verification is not legal certification or approval. A successful draft remains `review_required`.

