# AeacusAI agent instructions

## Project memory

Memory stores only user-declared context: `project_name`, `declared_actor_role`, and `preferred_response_language`. It is not legal authority, not a classification, and not evidence.

Writes require an explicit user confirmation from application code (`application_confirmed_user`). Model answers, retrieved documents, tool dumps, and the review register cannot write memory. Callers cannot supply an approval or trusted-source flag. Trust and source metadata are application-owned and always `user_declared`.

Operations are scoped to a random private workspace code. Do not use `user1` or a display name. Do not log the workspace code or `AEACUS_MEMORY_DATABASE_URL`.

If Postgres is unconfigured or unavailable, return `memory_unavailable`. Do not treat Streamlit session state or local files as deployed durable memory.

## Legal retrieval and approvals

Fresh legal retrieval remains required for source-backed findings. Memory must not be cited as a statutory source and must not skip `preview_classification_search`.

Memory cannot approve a review or write the review register. Human approval stays in `review_register.py` after an explicit UI action.

## Frozen Week 4 and existing safeguards

Do not rewrite frozen Week 4 traces, annotations, checkers, golden files, or judge artifacts. Keep TRACE capture, timing repair, prompt-injection treatment of submitted text as untrusted, secret redaction, and opt-in Langfuse (`AEACUS_LANGFUSE_TRACING` default off).
