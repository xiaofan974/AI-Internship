# Week 5 durable memory Postgres checkpoint

Verified 2026-10-24 on `feat/aeacusai-memory`. Streamlit, agent instructions, retrieval, the review register, frozen Week 4 artifacts, and unrelated working-tree files were not changed. No model calls, commits, pushes, or application deployments.

This report separates **mocked offline tests** from **real Postgres integration**. It retains the first unsuccessful attempt (unresolved Railway template, no public TCP proxy) and the later successful attempt after creating exactly one public proxy on the live project.

Credentials, full URLs, workspace codes, and environment dumps are not recorded here.

## Attempt 1 — unsuccessful (template, no public endpoint)

Inspected `AEACUS_MEMORY_DATABASE_URL` as metadata only.

| Check | Result |
| --- | --- |
| `AEACUS_MEMORY_DATABASE_URL` in `.env` | present (length 114) |
| Value kind | unresolved Railway `${{ }}` template |
| `sslmode` in the stored URL | missing |
| Companion `PG*` / `RAILWAY_*` keys in `.env` and the process environment | absent |
| `DATABASE_URL` auto-read | not used |
| `AEACUS_MEMORY_SCHEMA` | `aeacus_memory` |
| `AEACUS_MEMORY_TTL_DAYS` | 180 |
| `prepare_connect_dsn` | `unresolved_database_url` |
| `open_memory_store()` | `UnavailableMemoryStore` (`durable=False`) |

TLS policy (unchanged): only `sslmode=require`, `verify-ca`, or `verify-full` are accepted. A missing `sslmode` is appended as `require`. `disable`, `allow`, and `prefer` return `tls_required`. Unresolved `${{ }}` templates and unparseable or host-less URLs return `unresolved_database_url`. Week 5 runners load `.env` with `interpolate=False`.

Official Railway CLI inspection of the live project found **0 TCP proxies**. `DATABASE_PUBLIC_URL`, `RAILWAY_TCP_PROXY_DOMAIN`, and `RAILWAY_TCP_PROXY_PORT` were absent. `DATABASE_URL` on the service was a resolved **private** `*.railway.internal:5432` host only. The dashboard `:5432` was the internal target port, not a public proxy.

Driver: `psycopg[binary]==3.3.6` installed into `.venv` and pinned in `requirements.txt`. No other dependency changes.

Real apply (`python run_week5_memory_schema.py`):

```json
{
  "ok": false,
  "status": "memory_unavailable",
  "reason": "unresolved_database_url",
  "applied": false
}
```

Two-process check: Process A was not started. Orchestrator returned `memory_unavailable` / `unresolved_database_url`, `fresh_process_recall: false`. No test facts were written.

## Attempt 2 — public proxy and real persistence

Targeted only the verified live project. The same-name Redis project with `deletedAt` was excluded.

| Selector | Value |
| --- | --- |
| Project | `aeacusai-memory` `d1d6d077-ef5c-4109-bc97-5aa7bce444cb` |
| Environment | `production` `8859bf95-d797-4bf0-9584-dc35e72b4489` |
| Postgres service | `a60ca2ee-5382-484e-8b3f-1b0e1efddb35` |

Recheck: `railway tcp-proxy list` → `proxies: []`. Created exactly one proxy:

`railway tcp-proxy create --port 5432 --project d1d6d077-ef5c-4109-bc97-5aa7bce444cb --environment production --service a60ca2ee-5382-484e-8b3f-1b0e1efddb35`

Read-back (`list` and `status`, id `8a5121d7-5c68-4cf0-b189-653c20841514`):

| Field | Value |
| --- | --- |
| Public hostname | `switchback.proxy.rlwy.net` |
| Assigned external port | `26668` |
| Internal target port | `5432` |
| Endpoint | `switchback.proxy.rlwy.net:26668` |
| Sync status | `ACTIVE` |
| Proxy count after create | 1 |

`DATABASE_PUBLIC_URL` remained absent after proxy creation. The local memory URL was constructed programmatically from the verified proxy endpoint plus the existing resolved `PGUSER` / `PGPASSWORD` / `PGDATABASE` values, with credentials URL-encoded and `sslmode=require`. Only `AEACUS_MEMORY_DATABASE_URL` in `capstone/aeacusai/.env` was replaced. Other keys were left unchanged.

| Post-update check | Result |
| --- | --- |
| Value kind | resolved `postgresql` URL (length 110) |
| Host | `switchback.proxy.rlwy.net` |
| External port | 26668 |
| `sslmode` | `require` |
| Template markers | none |
| User / password / database | set |
| `prepare_connect_dsn` | ready |
| `open_memory_store()` | `PostgresMemoryStore` (`durable=True`) |

Database, volume, credentials, and the existing `SUCCESS` Postgres deployment were not redeployed or rewritten.

### Real integration (Postgres)

Explicit migration (`python run_week5_memory_schema.py`):

```json
{
  "ok": true,
  "status": "applied",
  "reason": null,
  "applied": true,
  "schema_present": true
}
```

Limited to `aeacus_memory`. Import still does not migrate.

Two-process persistence (`python run_week5_memory_persistence_check.py`):

| Integration check | Result |
| --- | --- |
| Process A confirmed writes (`project_name` superseded then replaced, `declared_actor_role=deployer`, `preferred_response_language=French`) | `replaced` × 4, `durable=True`, `mocked=False` |
| Process A exit, then Process B recall | `fresh_process_recall: true` |
| Retrieved values match expected fictional facts | yes (`Fictional Harbour Pilot`, `deployer`, `French`) |
| Different workspace empty | yes |
| Cleanup including superseded history | `history_rows_remaining: 0`, active values cleared |
| Overall | `ok: true` |

Process B received only the workspace credential and inherited database configuration. Expected values were not passed through arguments, fixtures, session state, or local value files. Credentials were not placed on command arguments.

### Mocked offline tests (not persistence)

Command: `.venv/bin/python -m unittest test_project_memory -v`

**15/15 passed** in 0.005s after the real integration. These use `MockedMemoryDatabase` or policy/unavailable checks and do not by themselves prove restart persistence.

| Class | What it covers |
| --- | --- |
| `MemoryPolicyTests` | three fields and closed enums; reserved workspace names; write-gate rejects model/retrieval/unconfirmed; UI/agent/review-register do not import memory; schema apply is not imported by the store; `0001_init.sql` is scoped to `aeacus_memory` |
| `MockedDatabaseTests` | confirmed replace/list/get; identical save does not duplicate; replace then delete removes history; foreign channel does not write; workspaces cannot read each other |
| `UnavailableAndSanitizedFailureTests` | unconfigured store; TLS and template rejection; parameterized queries on a mocked cursor; workspace code and DSN redaction |
| `ExistingSafeguardPresenceTests` | review redaction still covers known secret names |

## Files

- `aeacus_agent/project_memory.py` — TLS and unresolved-URL gate
- `aeacus_agent/memory_postgres.py` — explicit connect only
- `aeacus_agent/memory_schema.py` — explicit apply, scoped to `aeacus_memory`
- `sql/memory/0001_init.sql`
- `run_week5_memory_schema.py`
- `run_week5_memory_persistence_check.py`
- `test_project_memory.py`
- `requirements.txt` — `psycopg[binary]==3.3.6` only
- `.env.example` — resolved TLS URL note
- `AGENTS.md`
- `capstone/aeacusai/.env` — `AEACUS_MEMORY_DATABASE_URL` only (not committed)
- `reports/week5_memory_postgres_checkpoint.md`

Preserved and not staged here: `ai-engineering-bootcamp/adk-multi-agent-systems/demo1_routing.py` and `capstone/AeacusAI_Week3_Submission.zip`.
