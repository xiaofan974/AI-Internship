# LangGraph classification-preview mirror

Generated: 2026-10-22T20:12:17.490022+00:00

This is a separate CLI mirror of `aeacus_preview_agent`. Streamlit, ADK
paths, MCP, the corpus, and the human approval register are unchanged.

## Installed versions

- Python: `3.12.13` (`/Users/aureliemahe/AI-Internship/capstone/aeacusai/.venv-langgraph/bin/python`)
- langgraph: `1.2.16`
- langchain-core: `1.7.0`
- google-adk: `2.12.0`
- google-genai: `2.32.0`
- Model: `gemini-3.8-flash`

## Offline checks (mocked / no live model)

- Unittest: **PASS**
- Default ADK preview agent unchanged: `aeacus_preview_agent`
- Allowlisted tool: `preview_classification_search`
- Limits: 8 model calls, 90s, recursion 24

## Live LangGraph run

- Execution: **failed**
- Status: `failed`
- Model calls: 2
- Register opened: False
- Register written: False

### Graph trace

```
[
  {
    "kind": "act",
    "tool": "preview_classification_search",
    "query": "recruitment candidates filter rank employment",
    "call_id": "call_86217"
  },
  {
    "kind": "observe",
    "call_id": "call_86217",
    "tool": "preview_classification_search",
    "query": "recruitment candidates filter rank employment",
    "status": "ok",
    "match_record_ids": [
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::annex/III/point/4"
    ],
    "context_record_ids": [
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::annex/III",
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/6",
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/113"
    ]
  },
  {
    "kind": "final",
    "chars": 2979
  },
  {
    "kind": "failed",
    "message": "Deterministic citation or quotation checks failed."
  }
]
```

### Observations

```
[
  {
    "call_id": "call_86217",
    "tool": "preview_classification_search",
    "query": "recruitment candidates filter rank employment",
    "status": "ok",
    "match_record_ids": [
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::annex/III/point/4"
    ],
    "context_record_ids": [
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::annex/III",
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/6",
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/113"
    ]
  }
]
```

### Draft

```
### Provisional finding
The AI system is provisionally classified as high-risk under Article 6, specifically pursuant to Article 6(2) and Annex III, point 4, subject to whether the derogation criteria in Article 6(3) are satisfied.

### Why
Annex III, point 4(a) lists:
> "AI systems intended to be used for the recruitment or selection of natural persons, in particular to place targeted job advertisements, to analyse and filter job applications, and to evaluate candidates;"

The submitted facts state that the system is used to analyse and filter job applications and rank candidates for recruiters. Under Article 6(2), AI systems listed in Annex III are classified as high-risk. Although human recruiters make the final hiring decisions, the system's stated functions fall directly within the explicit scope of Annex III, point 4(a).

### What could change this
Under Article 6(3), first subparagraph, an AI system listed in Annex III is not considered high-risk if it does not pose a significant risk of harm to the health, safety, or fundamental rights of natural persons, including by not materially influencing the outcome of decision-making. 

To qualify for this derogation, the system must satisfy at least one condition in Article 6(3), second subparagraph, such as performing a narrow procedural task (point (a)) or performing a preparatory task to an assessment (point (d)). However, this exception is strictly limited by Article 6(3), third subparagraph:
> "Notwithstanding the first subparagraph, an AI system referred to in Annex III shall always be considered to be high-risk where the AI system performs profiling of natural persons."

Furthermore, under Article 6(4), any provider relying on Article 6(3) must document its assessment before the system is placed on the market or put into service.

### Missing facts
Whether an Article 6(3) exception applies cannot be resolved on the available record:
- Functional filtering behavior: The submission does not specify whether the system discards or excludes candidates automatically, or merely assists with organization.
- Material influence: It is unknown to what extent the system's ranking influences or predetermines recruiters' evaluations in practice.
- Profiling: It remains unresolved whether the system conducts profiling of natural persons.
- Documentation: It is unknown whether the provider has prepared and maintained documentation of an Article 6(3) assessment pursuant to Article 6(4).

### Timing and scope
Under Article 113, the Regulation applies generally from 2 August 2026. However, under Article 113(c)(i), Chapter III, Sections 1, 2, and 3—with the exception of Article 6(5)—apply from 2 December 2027 to AI systems classified as high-risk pursuant to Article 6(2) and Annex III. 

This assessment is a provisional reading limited strictly to the classification subset of Article 6, Annex III, and Article 113. It does not address full legal conformity or other provisions of Union law.
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

### Comparison with saved ADK example

Wording and search results are not required to match.

```
{
  "available": true,
  "adk_source": "dual_preview_eval.json",
  "wording_required_identical": false,
  "scope": {
    "langgraph_mentions_subset": true,
    "adk_mentions_subset": true,
    "langgraph_avoids_full_compliance": true,
    "adk_avoids_full_compliance": true
  },
  "evidence_provenance": {
    "langgraph_ids": [
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::annex/III/point/4",
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::annex/III",
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/6",
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/113"
    ],
    "adk_ids": [
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::annex/III/point/4",
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/6/paragraph/3",
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/6/paragraph/6",
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::annex/III/point/6",
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/6/paragraph/4",
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::annex/III",
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/6",
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/113"
    ],
    "langgraph_has_hashes": true,
    "shared_ids": [
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::annex/III/point/4",
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::annex/III",
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/6",
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/113"
    ]
  },
  "citation_validity": {
    "langgraph_checks_ok": false,
    "adk_checks_ok": true
  }
}
```

## Live note

The graph completed two model calls and one real local retrieval. The draft
stayed inside the Article 6 / Annex III / Article 113 subset and did not claim
full compliance. Deterministic quotation checks failed because markdown
blockquotes still wrapped already-quoted statutory text; the inner quotations
themselves appear in the retrieved Annex III point 4 and Article 6 parent
records. That helper is now stripped of wrapping quote marks. This live run
was not repeated.

## Limits

One LangGraph live run is a framework mirror, not legal certification
or approval. Successful drafts remain `review_required`.

