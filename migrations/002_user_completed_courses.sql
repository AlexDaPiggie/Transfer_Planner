-- Apply to the same authorized PostgreSQL database as pathway_users.
-- This creates a new account-specific table; it does not modify Assist course data.
CREATE TABLE IF NOT EXISTS user_completed_courses (
    user_id BIGINT NOT NULL REFERENCES pathway_users(user_id) ON DELETE CASCADE,
    source_id BIGINT NOT NULL,
    course_code VARCHAR(120) NOT NULL,
    completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, source_id, course_code)
);
