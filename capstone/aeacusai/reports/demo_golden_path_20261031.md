# Demo Day golden-path observation — 31 October 2026

Recorded 2026-10-31 on `feat/aeacusai-memory`. This note documents a **manual public-browser assessment** of the existing recruitment example. It is not an automated test artifact, not a process-level runner result, and not a statistical reliability claim.

No workspace code, connection string, or password is recorded here. Frozen Week 4 traces were not rewritten. Project memory was not created, saved, deleted, or recalled.

Public URL: `https://aeacusai-demo.onrender.com/`

## What this is

One approved live **Run assessment** click on the deployed Streamlit app, with the loaded recruitment example and no Project memory connected. The observation was reported from the browser session, not from a saved JSONL harness file.

## What this is not

| Claim | Status |
| --- | --- |
| Automated TRACE / unittest artifact | no |
| Reliability rate or repeated-run score | no |
| Independent deployment SHA verification | no |
| Human approval or rejection | not performed |
| Memory write, delete, or recall | not performed |
| Additional paid retries | none |

## Input

| Field | Value |
| --- | --- |
| Date | 2026-10-31 |
| Workspace | Assessment |
| Project memory | none connected; pending draft later showed `No workspace memory was bound to this draft.` |
| Trigger | **Load recruitment example**, then exactly one **Run assessment** |
| System description | `A company uses an AI system to analyse and filter job applications and rank candidates for recruiters. Recruiters make the final hiring decision. Give a provisional classification assessment against the pinned corpus, identify relevant exceptions, and state which additional facts are needed.` |

## Outcome

**PASS.** Visible execution ended `FINAL: Assessment ready` and `REVIEW_REQUIRED`. No `FAILED` banner, no unknown-source warning, no `GOOGLE_API_KEY` warning.

| Field | Observed |
| --- | --- |
| Run ID | `8be8bb04-f8b6-4dcb-aca6-3ad491fb7c4f` |
| Duration | **78 seconds** click-to-FINAL (click `2026-10-31T14:22:21Z`, FINAL visible `2026-10-31T14:23:39Z`) |
| Runner limit | 90 seconds; this run finished inside that bound |
| Retries | none |

## Agent activity

Exactly one observed `preview_classification_search` cycle:

1. **THINK:** call tool `preview_classification_search`
2. **ACT:** `preview_classification_search`  
   Query: `recruitment candidate filtering ranking employment Annex III Article 6`
3. **OBSERVE:** status `ok`
4. **FINAL:** Assessment ready
5. **REVIEW_REQUIRED:** Human review of this exact draft is required before recording

### Retrieved labels

Search matches:

- Annex III, point 4
- Article 6(3)
- Article 6(6)
- Annex III, point 6
- Article 6(4)

Expanded context:

- Annex III — High-risk AI systems referred to in Article 6(2)
- Article 6 — Classification rules for high-risk AI systems
- Article 113 — Entry into force and application

Article 6(6) and Annex III, point 6 were retrieved and not used in the visible finding.

## Classification

Provisional high-risk finding under Article 6(2) and Annex III, point 4, subject to whether the Article 6(3) derogation applies. Human recruiters making the final hiring decision was not treated as removing the system from Annex III, point 4.

Exceptions considered: Article 6(3) (including the profiling override) and Article 6(4) documentation if a provider claims the system is not high-risk.

Missing facts listed in the UI:

- Whether filtering or ranking automatically rejects applicants or materially influences recruiter choices
- The nature of recruiter review (human review of every application is neither necessary nor sufficient for Article 6(3))
- Whether the system performs profiling of natural persons

## Evidence

Annex III, point 4, Article 6(3), and Article 113 expanders were opened. Quoted clauses matched the returned records. No “Unknown source references” warning. Bound identities used snapshot `T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715`.

## Human review

The post-run **Human review** panel appeared (`Pending human review`, Exact draft and bound evidence, reviewer label, **Approve and record**, **Reject draft**). **Approve and record** stayed disabled with an empty reviewer label. Neither approval nor rejection was clicked.

## Memory and deployment

No memory write, delete, or recall. The pending draft stated that no workspace memory was bound.

The public deployment SHA was not independently verified. Render `Last-Modified` (`2026-10-24T15:04:45Z`) was consistent with local HEAD `59c895b` at observation time, not a cryptographic match.

## Limits

This is **one observed run**. It does not change frozen Week 4 artifacts, does not prove live-model grounding beyond records returned in this run, and is not legal certification.
