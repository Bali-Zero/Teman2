-- Migration 257: permit explicit acknowledgement outcomes for compliance alerts.
--
-- The compliance-alert status constraint has accepted `acknowledged` since
-- migration 114, but migration 115's outcome audit constraint only accepts
-- dismissed, acted, and expired. The INTAKE deadline gate records the distinct
-- `acknowledged` intent before moving an alert out of the blocking pending/sent
-- statuses, so both constraints must represent the same transition.
--
-- DROP IF EXISTS + ADD makes a retry converge on the intended definition.
-- Existing dismissed/acted/expired rows remain valid and unchanged.

ALTER TABLE alert_outcomes
    DROP CONSTRAINT IF EXISTS ck_alert_outcomes_outcome;

ALTER TABLE alert_outcomes
    ADD CONSTRAINT ck_alert_outcomes_outcome
    CHECK (outcome IN ('dismissed', 'acted', 'expired', 'acknowledged'))
    NOT VALID;

ALTER TABLE alert_outcomes
    VALIDATE CONSTRAINT ck_alert_outcomes_outcome;

-- === ROLLBACK ===
-- The old schema cannot represent the explicit acknowledgement. Preserve the
-- audit row and map only that new value to its closest pre-257 state before
-- restoring the original constraint; acted/dismissed/expired rows are untouched.
UPDATE alert_outcomes
   SET outcome = 'dismissed'
 WHERE outcome = 'acknowledged';

ALTER TABLE alert_outcomes
    DROP CONSTRAINT IF EXISTS ck_alert_outcomes_outcome;

ALTER TABLE alert_outcomes
    ADD CONSTRAINT ck_alert_outcomes_outcome
    CHECK (outcome IN ('dismissed', 'acted', 'expired'))
    NOT VALID;

ALTER TABLE alert_outcomes
    VALIDATE CONSTRAINT ck_alert_outcomes_outcome;
