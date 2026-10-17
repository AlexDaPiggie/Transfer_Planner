-- Run against the same PostgreSQL database used by Pathway authentication.
CREATE TABLE IF NOT EXISTS pathway_student_profiles (
    user_id BIGINT PRIMARY KEY REFERENCES pathway_users(user_id) ON DELETE CASCADE,
    year VARCHAR(40) NOT NULL DEFAULT '',
    major VARCHAR(160) NOT NULL DEFAULT '',
    interests JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
