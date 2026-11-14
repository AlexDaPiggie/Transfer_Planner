-- Shared login sessions use this version to reject invalidated sessions.
-- Retains the authentication column from the retired integration migration.
ALTER TABLE pathway_users ADD COLUMN IF NOT EXISTS session_version BIGINT NOT NULL DEFAULT 0;
