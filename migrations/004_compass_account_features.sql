-- Additive integration schema; no changes to ASSIST data or existing passwords.
ALTER TABLE pathway_users ADD COLUMN IF NOT EXISTS session_version BIGINT NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS pathway_email_preferences (
    user_id BIGINT PRIMARY KEY REFERENCES pathway_users(user_id) ON DELETE CASCADE,
    daily_events BOOLEAN NOT NULL DEFAULT FALSE,
    verified_at TIMESTAMPTZ,
    confirmation_token_hash TEXT,
    confirmation_expires_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pathway_email_deliveries (
    user_id BIGINT NOT NULL REFERENCES pathway_users(user_id) ON DELETE CASCADE,
    delivery_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, delivery_date)
);

CREATE TABLE IF NOT EXISTS pathway_password_resets (
    token_hash TEXT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES pathway_users(user_id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
