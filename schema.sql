-- CampusFind database schema for Supabase (PostgreSQL)
-- Run this in: Supabase dashboard > SQL Editor > New query > paste > Run.
-- The backend can also create these tables by itself on first start (create_all),
-- so this file is optional. Use it if you want to see or control the tables yourself.

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    full_name     VARCHAR(120) NOT NULL,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(30)  NOT NULL DEFAULT 'student',
    created_at    TIMESTAMP    NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);

CREATE TABLE IF NOT EXISTS lost_reports (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER      NOT NULL REFERENCES users (id),
    title       VARCHAR(160) NOT NULL,
    category    VARCHAR(80)  NOT NULL,
    brand       VARCHAR(100),
    model       VARCHAR(100),
    color       VARCHAR(80),
    lost_date   VARCHAR(30),
    lost_time   VARCHAR(30),
    location    VARCHAR(160),
    description TEXT,
    image_url   TEXT,
    status      VARCHAR(50)  NOT NULL DEFAULT 'SEARCHING',
    created_at  TIMESTAMP    NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_lost_reports_user_id ON lost_reports (user_id);

CREATE TABLE IF NOT EXISTS found_reports (
    id            SERIAL PRIMARY KEY,
    finder_id     INTEGER      NOT NULL REFERENCES users (id),
    title         VARCHAR(160) NOT NULL,
    category      VARCHAR(80)  NOT NULL,
    brand         VARCHAR(100),
    model         VARCHAR(100),
    color         VARCHAR(80),
    found_date    VARCHAR(30),
    found_time    VARCHAR(30),
    location      VARCHAR(160),
    description   TEXT,
    image_url     TEXT,
    status        VARCHAR(50)  NOT NULL DEFAULT 'PROTECTED',
    privacy_until TIMESTAMP,
    created_at    TIMESTAMP    NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_found_reports_finder_id ON found_reports (finder_id);

-- A found item that the admin has physically received at the desk
CREATE TABLE IF NOT EXISTS items (
    id               SERIAL PRIMARY KEY,
    found_report_id  INTEGER     NOT NULL UNIQUE REFERENCES found_reports (id),
    item_code        VARCHAR(60) NOT NULL UNIQUE,
    storage_location VARCHAR(160),
    physical_status  VARCHAR(40) DEFAULT 'STORED'
);
CREATE INDEX IF NOT EXISTS ix_items_item_code ON items (item_code);

-- Secret details only the real owner would know (never shown to users)
CREATE TABLE IF NOT EXISTS evidence (
    id            SERIAL PRIMARY KEY,
    item_id       INTEGER     NOT NULL REFERENCES items (id),
    evidence_type VARCHAR(60) NOT NULL,
    secret_value  TEXT        NOT NULL,
    base_weight   DOUBLE PRECISION,
    is_active     BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS matches (
    id              SERIAL PRIMARY KEY,
    lost_report_id  INTEGER NOT NULL REFERENCES lost_reports (id),
    found_report_id INTEGER NOT NULL REFERENCES found_reports (id),
    score           DOUBLE PRECISION NOT NULL,
    status          VARCHAR(40) DEFAULT 'SUGGESTED',
    created_at      TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_lost_found_match UNIQUE (lost_report_id, found_report_id)
);

CREATE TABLE IF NOT EXISTS claims (
    id              SERIAL PRIMARY KEY,
    claim_code      VARCHAR(60) NOT NULL UNIQUE,
    claimant_id     INTEGER NOT NULL REFERENCES users (id),
    lost_report_id  INTEGER NOT NULL REFERENCES lost_reports (id),
    found_report_id INTEGER NOT NULL REFERENCES found_reports (id),
    status          VARCHAR(50) DEFAULT 'VERIFICATION_PENDING',
    created_at      TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_claims_claim_code ON claims (claim_code);

CREATE TABLE IF NOT EXISTS verification_results (
    id           SERIAL PRIMARY KEY,
    claim_id     INTEGER NOT NULL REFERENCES claims (id),
    evidence_id  INTEGER NOT NULL REFERENCES evidence (id),
    similarity   DOUBLE PRECISION NOT NULL,
    contribution DOUBLE PRECISION NOT NULL,
    level        VARCHAR(30) NOT NULL,
    created_at   TIMESTAMP DEFAULT NOW()
);

-- One row per ownership check, used for the 3-tries limit
CREATE TABLE IF NOT EXISTS verification_attempts (
    id         SERIAL PRIMARY KEY,
    claim_id   INTEGER NOT NULL REFERENCES claims (id),
    score      DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_verification_attempts_claim_id ON verification_attempts (claim_id);

CREATE TABLE IF NOT EXISTS private_messages (
    id         SERIAL PRIMARY KEY,
    claim_id   INTEGER NOT NULL REFERENCES claims (id),
    sender_id  INTEGER NOT NULL REFERENCES users (id),
    message    TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS notifications (
    id                SERIAL PRIMARY KEY,
    user_id           INTEGER NOT NULL REFERENCES users (id),
    title             VARCHAR(160) NOT NULL,
    message           TEXT NOT NULL,
    notification_type VARCHAR(50) DEFAULT 'INFO',
    is_read           BOOLEAN DEFAULT FALSE,
    created_at        TIMESTAMP DEFAULT NOW()
);

-- Lost reports with no match yet; checked again when new items are found
CREATE TABLE IF NOT EXISTS lost_watch (
    id             SERIAL PRIMARY KEY,
    lost_report_id INTEGER NOT NULL UNIQUE REFERENCES lost_reports (id),
    active         BOOLEAN DEFAULT TRUE,
    created_at     TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES users (id),
    action      VARCHAR(100) NOT NULL,
    entity_type VARCHAR(60)  NOT NULL,
    entity_id   INTEGER,
    details     TEXT,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Password reset codes (stored hashed, expire after 10 minutes)
CREATE TABLE IF NOT EXISTS password_resets (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users (id),
    code_hash  VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    attempts   INTEGER DEFAULT 0,
    used       BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_password_resets_user_id ON password_resets (user_id);

-- SECURITY: Supabase exposes tables through its public REST API.
-- Our backend connects directly with the database password, so we switch Row Level
-- Security ON with no policies. That blocks the public API from reading these tables
-- (the backend is not affected).
ALTER TABLE users                ENABLE ROW LEVEL SECURITY;
ALTER TABLE lost_reports         ENABLE ROW LEVEL SECURITY;
ALTER TABLE found_reports        ENABLE ROW LEVEL SECURITY;
ALTER TABLE items                ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence             ENABLE ROW LEVEL SECURITY;
ALTER TABLE matches              ENABLE ROW LEVEL SECURITY;
ALTER TABLE claims               ENABLE ROW LEVEL SECURITY;
ALTER TABLE verification_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE verification_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE private_messages     ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications        ENABLE ROW LEVEL SECURITY;
ALTER TABLE lost_watch           ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs           ENABLE ROW LEVEL SECURITY;
ALTER TABLE password_resets      ENABLE ROW LEVEL SECURITY;
