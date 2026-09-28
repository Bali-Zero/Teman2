-- Internal synthetic experiment only. Never stores applicant/client records.
CREATE TABLE visa_oracle_test_slots (
    slot TEXT PRIMARY KEY CHECK (slot IN ('T01','T02','T03','T04','T05','T06')),
    member_id TEXT UNIQUE,
    reviewer BOOLEAN NOT NULL DEFAULT FALSE
);
INSERT INTO visa_oracle_test_slots (slot)
SELECT 'T0' || n FROM generate_series(1,6) n;

CREATE TABLE visa_oracle_test_runs (
    assignment_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    plan_version TEXT NOT NULL,
    slot TEXT NOT NULL REFERENCES visa_oracle_test_slots(slot),
    member_id TEXT NOT NULL,
    assigned_day DATE NOT NULL,
    scenario JSONB NOT NULL,
    expected JSONB NOT NULL,
    result JSONB,
    screenshot BYTEA CHECK (octet_length(screenshot) <= 614400),
    review JSONB,
    status TEXT NOT NULL DEFAULT 'started' CHECK (status IN ('started','submitted')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_at TIMESTAMPTZ,
    CHECK ((status = 'submitted') = (submitted_at IS NOT NULL)),
    CHECK (review IS NULL OR status = 'submitted')
);
CREATE INDEX visa_oracle_test_runs_slot_day ON visa_oracle_test_runs(slot, assigned_day);

-- === ROLLBACK ===
DROP TABLE IF EXISTS visa_oracle_test_runs;
DROP TABLE IF EXISTS visa_oracle_test_slots;
