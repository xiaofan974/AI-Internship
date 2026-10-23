# MCP-backed classification preview checkpoint

Generated: 2026-10-22T19:45:37.393512+00:00

The Streamlit demo and `aeacus_preview_agent` remain on the direct Python tool.
This checkpoint uses a separate MCP-only agent.

## Installed versions

- Python: `3.12.13` (`/Users/aureliemahe/AI-Internship/capstone/aeacusai/.venv/bin/python`)
- google-adk: `2.12.0`
- mcp: `1.25.0`
- google-genai: `2.32.0`
- Model: `gemini-3.8-flash`

## Server launch method

- Command: `/Users/aureliemahe/AI-Internship/capstone/aeacusai/.venv/bin/python`
- Args: `['-m', 'aeacus_agent.mcp_server']`
- Working directory: `/Users/aureliemahe/AI-Internship/capstone/aeacusai`
- Connection timeout: 15.0s
- Call/read timeout: 30.0s

## Protocol checks (no model calls)

- Initialize: **PASS**
- List tools: `['preview_classification_search']`
- Recruitment parity: **PASS**
- Empty-query parity: **PASS**
- Subprocess cleanup: **PASS**

```
{
  "initialize": {
    "ok": true,
    "protocolVersion": "2025-11-25",
    "server": {
      "name": "aeacus-classification-preview",
      "title": null,
      "version": "1.25.0",
      "websiteUrl": null,
      "icons": null
    },
    "spawned_pids": [
      90815
    ]
  },
  "list_tools": {
    "ok": true,
    "names": [
      "preview_classification_search"
    ],
    "count": 1
  },
  "recruitment_call": {
    "ok": true,
    "query": "recruitment job applications filter candidates workers",
    "isError": false,
    "mcp_status": "ok",
    "mcp_match_ids": [
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::annex/III/point/4",
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::annex/III/point/7"
    ],
    "mcp_context_ids": [
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::annex/III",
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/6",
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/113"
    ],
    "direct_match_ids": [
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::annex/III/point/4",
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::annex/III/point/7"
    ],
    "direct_context_ids": [
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::annex/III",
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/6",
      "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/113"
    ],
    "parity": true
  },
  "empty_query": {
    "ok": true,
    "mcp_status": "error",
    "mcp_error": {
      "category": "invalid_query",
      "message": "Search query cannot be empty."
    },
    "direct_status": "error",
    "direct_error": {
      "category": "invalid_query",
      "message": "Search query cannot be empty."
    },
    "parity": true
  },
  "cleanup": {
    "ok": true,
    "spawned_pids": [
      90815
    ],
    "leftover_pids": []
  }
}
```

## Live MCP-only assessment

- Execution: **ok**
- Live invocations used: 1
- Register opened: False

### Tool calls

1. `preview_classification_search` query='recruitment filter job applications rank candidates employment'

### Observed evidence IDs

The live ADK observation wrapped MCP JSON as text content, so IDs were not in the compacted tool_log. These IDs were recovered by calling the same MCP tool with the live-chosen query, without another model call.

```
[
  "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::annex/III/point/4",
  "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::annex/III/point/7",
  "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::annex/III",
  "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/6",
  "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715::article/113"
]
```

### Final answer

```
### Provisional finding

The AI system is provisionally classified as high-risk under Article 6(2) in conjunction with Annex III, point 4, subject to the potential application of the derogation under Article 6(3).

### Why

Under Annex III, point 4(a), high-risk use cases include AI systems intended to be used for the recruitment or selection of natural persons, “in particular to place targeted job advertisements, to analyse and filter job applications, and to evaluate candidates”. The stated facts indicate that the system analyses and filters job applications and ranks candidates. Under Article 6(2), AI systems referred to in Annex III are classified as high-risk. Although human recruiters retain final hiring authority, candidate filtering and ranking fall directly within the recruitment activities identified in Annex III, point 4(a).

### What could change this

Under Article 6(3), first subparagraph, an AI system referred to in Annex III is not considered high-risk if it does not pose a significant risk of harm to the health, safety, or fundamental rights of natural persons, including by not materially influencing the outcome of decision-making. To rely on this derogation, the system must fulfill at least one condition in Article 6(3), second subparagraph:
- performing a narrow procedural task;
- improving the result of a previously completed human activity;
- detecting decision-making patterns or deviations from prior patterns without replacing or influencing the human assessment without proper human review; or
- performing a preparatory task to an assessment relevant for the Annex III use cases.

However, pursuant to Article 6(3), third subparagraph, the system is always considered high-risk if it performs profiling of natural persons. Where a provider considers the system not high-risk pursuant to Article 6(3), Article 6(4) requires documenting that assessment before placing the system on the market or putting it into service.

### Missing facts

To determine whether an Article 6(3) derogation could apply, the following facts are required:
- How the filtering and ranking outputs affect recruiter workflows, including whether they materially influence recruitment decisions or exclude candidates from human review.
- Whether the system’s processing involves profiling of candidates.
- The exact technical scope of the AI task, such as whether it performs purely administrative sorting or substantive candidate evaluation.

### Timing and scope

Pursuant to Article 113, the Regulation generally applies from 2 August 2026. However, under Article 113(c)(i), Chapter III, Sections 1, 2, and 3—with the exception of Article 6(5)—apply from 2 December 2027 for AI systems classified as high-risk pursuant to Article 6(2) and Annex III. This assessment is provisional and limited exclusively to the classification subset of Article 6, Annex III, and Article 113, and does not evaluate general regulatory conformity.
```

### Cleanup

{
  "ok": true,
  "leftover_child_pids": []
}

## Limits

One MCP-backed live run is not a general MCP security or reliability proof.

