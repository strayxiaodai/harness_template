CREATE TABLE IF NOT EXISTS agent_audit_log (
    id            BIGSERIAL PRIMARY KEY,
    thread_id     TEXT NOT NULL,
    round_number  INT NOT NULL,
    node          TEXT NOT NULL,
    event_type    TEXT NOT NULL,
    payload       JSONB NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_thread ON agent_audit_log(thread_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON agent_audit_log(created_at);
