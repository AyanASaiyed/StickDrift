-- Stick Drift schema for Tiger Data (TimescaleDB / PostgreSQL).
-- Apply with: psql "$DATABASE_URL" -f schema.sql
-- Safe to re-run.

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Resident profiles. Pseudonyms only: never store real names here.
CREATE TABLE IF NOT EXISTS participants (
    participant_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alias           TEXT NOT NULL UNIQUE CHECK (length(alias) BETWEEN 1 AND 40),
    dominant_hand   TEXT NOT NULL CHECK (dominant_hand IN ('left', 'right', 'unknown')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per play session. Only completed assessment sessions with good
-- quality feed the personal baseline; free play never does.
CREATE TABLE IF NOT EXISTS sessions (
    session_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    participant_id    UUID NOT NULL REFERENCES participants (participant_id) ON DELETE CASCADE,
    mode              TEXT NOT NULL CHECK (mode IN ('assessment', 'free_play')),
    protocol_version  TEXT NOT NULL,
    controller_id     TEXT,
    connection        TEXT CHECK (connection IN ('usb', 'bluetooth', 'simulated', 'unknown')),
    placement         TEXT CHECK (placement IN ('hands', 'table', 'lap', 'other')),
    status            TEXT NOT NULL DEFAULT 'in_progress'
                      CHECK (status IN ('in_progress', 'completed', 'abandoned')),
    quality           TEXT CHECK (quality IN ('good', 'flagged', 'invalid')),
    is_synthetic      BOOLEAN NOT NULL DEFAULT false,
    started_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at      TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS sessions_participant_started_idx
    ON sessions (participant_id, started_at DESC);

-- Per-session results, computed from responses. Counts keep their
-- denominators so accuracy is never shown without context.
CREATE TABLE IF NOT EXISTS session_summaries (
    session_id               UUID PRIMARY KEY REFERENCES sessions (session_id) ON DELETE CASCADE,
    left_median_latency_ms   REAL,
    right_median_latency_ms  REAL,
    left_correct             SMALLINT,
    left_valid               SMALLINT,
    right_correct            SMALLINT,
    right_valid              SMALLINT,
    both_correct             SMALLINT,
    both_valid               SMALLINT,
    lr_gap_ms                REAL,
    bimanual_gap_ms          REAL,
    enjoyment                SMALLINT CHECK (enjoyment BETWEEN 1 AND 5),
    code_version             TEXT NOT NULL,
    computed_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Prompt schedule as shown to the resident.
CREATE TABLE IF NOT EXISTS trials (
    session_id    UUID NOT NULL REFERENCES sessions (session_id) ON DELETE CASCADE,
    trial_id      SMALLINT NOT NULL,
    block         TEXT NOT NULL CHECK (block IN ('practice', 'left', 'right', 'both')),
    hand          TEXT NOT NULL CHECK (hand IN ('left', 'right', 'both')),
    direction_l   TEXT CHECK (direction_l IN ('up', 'down', 'left', 'right')),
    direction_r   TEXT CHECK (direction_r IN ('up', 'down', 'left', 'right')),
    cue_onset_ms  DOUBLE PRECISION NOT NULL,
    deadline_ms   DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (session_id, trial_id)
);

-- Detected response for each trial.
CREATE TABLE IF NOT EXISTS responses (
    session_id    UUID NOT NULL,
    trial_id      SMALLINT NOT NULL,
    outcome       TEXT NOT NULL
                  CHECK (outcome IN ('correct', 'wrong_direction', 'omission', 'false_start', 'invalid')),
    detected_l    TEXT,
    detected_r    TEXT,
    cross_l_ms    DOUBLE PRECISION,
    cross_r_ms    DOUBLE PRECISION,
    latency_ms    DOUBLE PRECISION,
    code_version  TEXT NOT NULL,
    PRIMARY KEY (session_id, trial_id),
    FOREIGN KEY (session_id, trial_id) REFERENCES trials (session_id, trial_id) ON DELETE CASCADE
);

-- Raw stick samples (~60 Hz from the Gamepad API). This is the time-series
-- table, so it is a hypertable partitioned on `time`.
CREATE TABLE IF NOT EXISTS raw_samples (
    time        TIMESTAMPTZ NOT NULL,
    session_id  UUID NOT NULL REFERENCES sessions (session_id) ON DELETE CASCADE,
    seq         INTEGER NOT NULL,
    t_ms        DOUBLE PRECISION NOT NULL,  -- performance.now() in the browser
    lx          REAL NOT NULL,
    ly          REAL NOT NULL,
    rx          REAL NOT NULL,
    ry          REAL NOT NULL,
    connected   BOOLEAN NOT NULL
);
SELECT create_hypertable('raw_samples', by_range('time'), if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS raw_samples_session_idx ON raw_samples (session_id, time);
