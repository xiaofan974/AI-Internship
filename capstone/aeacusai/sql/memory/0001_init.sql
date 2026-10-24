-- AeacusAI project memory. Separate from the review-register SQLite file.
-- Apply to external Postgres only. Do not store workspace codes or secrets.

CREATE SCHEMA IF NOT EXISTS aeacus_memory;

CREATE TABLE IF NOT EXISTS aeacus_memory.facts (
    id UUID PRIMARY KEY,
    workspace_id CHAR(64) NOT NULL,
    field TEXT NOT NULL,
    value TEXT NOT NULL,
    status TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    superseded_at TIMESTAMPTZ,
    CONSTRAINT facts_field_allowed CHECK (
        field IN (
            'project_name',
            'declared_actor_role',
            'preferred_response_language'
        )
    ),
    CONSTRAINT facts_status_allowed CHECK (status IN ('active', 'superseded')),
    CONSTRAINT facts_source_user_declared CHECK (source = 'user_declared')
);

COMMENT ON TABLE aeacus_memory.facts IS
    'User-declared project context only. Expiry: 180 days after the confirmed write unless overridden.';

CREATE UNIQUE INDEX IF NOT EXISTS facts_one_active
    ON aeacus_memory.facts (workspace_id, field)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS facts_workspace_field
    ON aeacus_memory.facts (workspace_id, field);
