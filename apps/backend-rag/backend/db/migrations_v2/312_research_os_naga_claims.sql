-- Migration 312: research_os_naga_claims
-- (Research OS v1.0.0, R2 ENGINE slice -- the NAGA claim ledger's D2 storage-side ordering
-- fix plus the D5 admission projection table).
--
-- INTEGER BOUND LATE, AT INTEGRATION TIME, same rule 279/280 document (scar W40 -- TOCTOU on
-- a shared mutable counter): a packet reserves a SYMBOLIC name, never an integer; the integer
-- is bound at commit time by the committing session, re-measured fresh, never copied from a
-- prompt or a document.
--
-- Measurement (fresh in this turn, immediately before writing this file):
--   * `git -C <worktree> rev-parse origin/main HEAD` -> origin/main 2a4681b0b88a291b4ed4d0c
--     8885bc1a5990ec8ed; worktree HEAD 8a61d3d27fef93569495a0b6337c22554bd9c0b8 (rebased onto
--     that origin/main, never pushed).
--   * `ls apps/backend-rag/backend/db/migrations_v2/*.sql | sort` -> highest present is 311
--     (311_practice_types_open_inquiry.sql).
--   -> next available integer: 312. The R2 build spec (`R2-build-spec.md` section 2) names
--   310 -- that number was measured before 310 and 311 landed from other, concurrently
--   dispatching lanes. 312 is the freshly re-measured integer, not the spec's stale one.
--
-- Purpose
-- -------
-- Two things, additive only, per R2-build-spec.md sections 2 and 4.1:
--
--   (a) research_os_instant_key(text): an IMMUTABLE, pure-regexp/integer-arithmetic key
--       function that repairs valid-time ORDERING in storage (D2). The wire form, R1's
--       `_UTC_OFFSET_PATTERN`, the 218 published fixtures and Consul's hashes stay
--       byte-identical -- only a SQL-side sort key is added, because the raw text of an
--       optional-fraction UTC instant does not order the way the instants themselves do
--       ('.' 0x2E sorts before 'Z' 0x5A, so a microsecond-zero instant with no fraction sorts
--       AFTER one with a fraction, even though it is chronologically earlier or equal). No
--       cast to date/timestamp/timestamptz/interval anywhere: those route through
--       `timestamptz_in`, which PostgreSQL marks STABLE (it reads the DateStyle/TimeZone
--       GUCs) -- declaring a STABLE cast IMMUTABLE is exactly how this lane failed in
--       2026-08 and is FORBIDDEN by the build spec. Domain parity with R1's
--       `instant_sort_key` (`research_os_reader_reference.py`, unmerged sibling branch, read
--       from disk) is asserted by a dedicated test
--       (`test_migration_312_instant_key_parity.py`), never by inspection alone.
--
--   (b) research_os_naga_admission: the ONE projection table D5 authorises beyond
--       `research_os_objects` for this slice. Records NAGA's legacy-claim admission
--       decisions (D4: admission is a DECISION, not a mapping -- zero admissions is a valid
--       outcome). Hash verification happens in the API before it is stored (migration 279
--       line 54's rule: RFC 8785 JCS is a Python-side responsibility, never re-implemented in
--       SQL) -- this migration does not compute or verify any hash, it only constrains their
--       SHAPE.
--
-- Append-only guard reuses 279's function VERBATIM
-- --------------------------------------------------
-- `public.reject_research_os_objects_mutation()`'s entire body is:
--     RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
-- It references only the built-in `TG_TABLE_NAME` trigger variable -- never `NEW`/`OLD`,
-- never a schema-qualified lookup of any kind -- so the SAME function is already valid,
-- unchanged, for a BEFORE UPDATE OR DELETE ROW trigger on any table, exactly as migration
-- 280 established for a second event on `research_os_objects` itself. This migration binds
-- it to a second table the same way: no ALTER FUNCTION, no second CREATE FUNCTION, no CREATE
-- OR REPLACE FUNCTION -- only one new CREATE TRIGGER statement pointing at the existing
-- function. The raised message is identical in shape to 279/280's:
-- `research_os_naga_admission is append-only`.
--
-- Statement-level wipe guard, exactly as 280 established it
-- ---------------------------------------------------------
-- PostgreSQL never fires ROW-level triggers for the wipe-everything-at-once statement
-- (280's header proves it), so the row trigger alone would leave this whole table erasable
-- in one statement. The same function is therefore bound a second time, to a STATEMENT-level
-- BEFORE trigger on that event, named `research_os_naga_admission_no_wipe` -- 280's shape.
-- Two earlier generations of this file could not write that statement: the local guardrails
-- daemon's SQL-content pattern matched the wipe verb followed by ANY word, including the
-- keyword ON of this protective DDL (superscar family #3, guard over-match). Zero authorized
-- the cure at the source; the pattern now carries a negative lookahead for ON/OR. The cure
-- then sat ON DISK AND UNARMED for hours -- the daemon had compiled the old pattern at start
-- and the static fallback copy was never patched (superscar family #2 sitting on top of #3)
-- -- so a generation that read the cured file still had its write refused. It was armed on
-- 2026-09-12 by reloading the daemon and bringing the static mirror to byte-parity, and only
-- then was this statement written. Guilt was re-probed after arming and still blocks every
-- genuinely destructive shape; no bypass was used at any point.
--
-- PostgreSQL 15 compatibility -- the same feature set 279/280 already used on this same
-- server target (BIGSERIAL, TEXT, TIMESTAMPTZ, CHAR(64), TEXT[], CHECK with a POSIX regex
-- operator, expression indexes, a BEFORE UPDATE OR DELETE trigger). Nothing here is
-- `CREATE INDEX CONCURRENTLY` (migration 279's header already established that this cannot
-- run inside the transaction `backend/db/migration_base.py::BaseMigration.apply()` wraps
-- every forward-SQL execute() in) and nothing here is PG16+-only. Applied on a real
-- `postgres:15` container as part of this PR's own test
-- (`tests/migrations/test_migration_312_research_os_naga_claims.py`).
--
-- Additive only. Migrations 279 and 280 -- their table, function, and both existing
-- triggers -- are byte-untouched by this file.
--
-- Rollback marker convention, and how this file's rollback came to be written
-- ---------------------------------------------------------------------------
-- Per `backend/db/migration_base.py:29`, the `-- === ROLLBACK ===` marker below is mandatory
-- for migrations numbered > 111 (this one is) and the runner's `split_migration_sql()`
-- executes ONLY the forward portion above the marker. `BaseMigration.__init__` requires
-- `rollback_sql` to be non-None for such migrations, and an EMPTY string satisfies that check
-- -- marker present, no statements after it. That was this file's state for most of its life,
-- and it is a check passing on a promise: the migration was formally reversible and in practice
-- was not. The section is now executable, and two tests in
-- `backend/tests/migrations/test_migration_312_research_os_naga_claims.py` assert both halves of
-- it (that it REFUSES while the admission table holds rows, and that it otherwise rolls back and
-- re-applies cleanly).
--
-- One correction to what an earlier draft of this very comment asserted, because it was measured
-- to be wrong rather than merely reworded: it claimed none of the removal statements a rollback
-- needs are shapes this repository's guardrail treats as destructive. The `DROP TABLE` line IS
-- such a shape, and the guardrail refused it -- correctly. That is a TRUE positive on
-- destructive DDL, NOT the over-match on protective `BEFORE TRUNCATE` DDL that was cured
-- separately, and the two must not be conflated: the first should keep refusing forever. The
-- body below was therefore written into this file by the operator of record under Zero's
-- authorisation, and was never routed around the check, never committed with `--no-verify`.

-- ---------------------------------------------------------------------------
-- (a) research_os_instant_key -- D2's storage-side ordering repair.
-- ---------------------------------------------------------------------------
-- Grammar mirrors `research_os_reader_reference.py::_INSTANT_RE` exactly:
--   date        [0-9]{4}-[0-9]{2}-[0-9]{2}
--   separator   T | t
--   clock       [0-9]{2}:[0-9]{2}:[0-9]{2}
--   fraction    (\.[0-9]+)?            -- optional, any width
--   terminator  Z | z | +00:00
-- `[0-9]`, never `\d` -- `\d`'s digit class can be locale/collation-sensitive, `[0-9]` is an
-- unambiguous ASCII range regardless of the expression index's own `COLLATE "C"`.
--
-- Calendar validity (month 1-12, day-in-month including Gregorian leap years, hour <= 23,
-- minute/second <= 59, year <> 0) is checked by INTEGER ARITHMETIC ONLY -- no date/timestamp
-- construction anywhere in this function, no cast. Non-matching input AND calendar-invalid
-- input both return NULL, never raise: strictness belongs to the WRITER (a later slice's
-- `naga_persistence.py`), not to an index expression sitting over a table other writers
-- already populate with occasionally-malformed legacy text -- a raising index expression
-- would turn one bad row into a failed insert on an unrelated path.
--
-- Output is always exactly 27 bytes, `YYYY-MM-DDTHH:MM:SS.ffffffZ`: the key is exact to the
-- microsecond, right-padded with zeros when the input fraction is shorter than 6 digits and
-- truncated when longer; sub-microsecond differences are not orderable by it.
CREATE FUNCTION public.research_os_instant_key(instant_text text)
RETURNS text
LANGUAGE plpgsql
IMMUTABLE
STRICT
PARALLEL SAFE
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    m           text[];
    y_text      text;
    mo_text     text;
    d_text      text;
    h_text      text;
    mi_text     text;
    s_text      text;
    frac_group  text;
    frac_digits text;
    y  int;
    mo int;
    d  int;
    h  int;
    mi int;
    s  int;
    is_leap       boolean;
    days_in_month int;
BEGIN
    m := regexp_match(
        instant_text,
        '^([0-9]{4})-([0-9]{2})-([0-9]{2})[Tt]([0-9]{2}):([0-9]{2}):([0-9]{2})(\.[0-9]+)?(Z|z|\+00:00)$'
    );
    IF m IS NULL THEN
        RETURN NULL;
    END IF;

    y_text := m[1]; mo_text := m[2]; d_text := m[3];
    h_text := m[4]; mi_text := m[5]; s_text := m[6];
    frac_group := m[7];

    y  := y_text::int;  mo := mo_text::int; d := d_text::int;
    h  := h_text::int;  mi := mi_text::int; s := s_text::int;

    -- Year 0000 does not exist in the proleptic Gregorian calendar R1's
    -- `datetime.fromisoformat` uses (Python's `MINYEAR` is 1) -- measured by running R1's
    -- reference implementation on this exact input, not assumed.
    IF y = 0 THEN
        RETURN NULL;
    END IF;
    IF mo < 1 OR mo > 12 THEN
        RETURN NULL;
    END IF;
    IF h > 23 THEN
        RETURN NULL;
    END IF;
    IF mi > 59 THEN
        RETURN NULL;
    END IF;
    IF s > 59 THEN
        RETURN NULL;
    END IF;

    is_leap := (y % 4 = 0 AND y % 100 <> 0) OR (y % 400 = 0);
    days_in_month := (ARRAY[
        31, CASE WHEN is_leap THEN 29 ELSE 28 END, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31
    ])[mo];
    IF d < 1 OR d > days_in_month THEN
        RETURN NULL;
    END IF;

    IF frac_group IS NULL THEN
        frac_digits := '';
    ELSE
        frac_digits := substring(frac_group FROM 2);  -- strip the leading '.'
    END IF;

    RETURN y_text || '-' || mo_text || '-' || d_text || 'T'
        || h_text || ':' || mi_text || ':' || s_text || '.'
        || rpad(left(frac_digits, 6), 6, '0') || 'Z';
END;
$$;

COMMENT ON FUNCTION public.research_os_instant_key(text) IS
    'D2 storage-side ordering key for an optional-fraction UTC instant. Pure '
    'regexp/integer arithmetic, no date/timestamp cast (those route through a '
    'STABLE input function). NULL on any non-matching or calendar-invalid '
    'input, never raises. Domain parity with '
    'research_os_reader_reference.instant_sort_key is asserted by '
    'test_migration_312_instant_key_parity.py.';

-- ---------------------------------------------------------------------------
-- (b) Expression indexes over research_os_objects.payload->'time'.
-- ---------------------------------------------------------------------------
-- `Claim.time` is a `ClaimTime` (`valid_from`/`valid_to`: `UtcDateTime | None`,
-- `recorded_at`: `UtcDateTime`) -- verified in
-- `packages/research-os-core/research_os/models/claim.py` -- so
-- `payload->'time'->>'valid_from'` / `...valid_to` is the right path. `COLLATE "C"`: byte
-- order over the 27-byte key must agree with chronological order over the parsed instant, and
-- "C" is the one collation that promises byte order rather than a locale-dependent one. Not
-- CONCURRENTLY -- see the header note on migration 279's transaction constraint.
CREATE INDEX research_os_objects_valid_from_key_idx ON public.research_os_objects
    ((public.research_os_instant_key(payload->'time'->>'valid_from')) COLLATE "C");

CREATE INDEX research_os_objects_valid_to_key_idx ON public.research_os_objects
    ((public.research_os_instant_key(payload->'time'->>'valid_to')) COLLATE "C");

-- ---------------------------------------------------------------------------
-- (c) research_os_naga_admission -- the ONE projection table D5 authorises.
-- ---------------------------------------------------------------------------
-- CROSS-LANE CONTRACT: other R2 lanes (`naga_persistence.py`, `naga_backfill.py`, dispatched
-- in parallel with this one) write to this table by these exact names and types -- do not
-- rename or retype a column here without re-checking every writer.
CREATE TABLE public.research_os_naga_admission (
    id BIGSERIAL PRIMARY KEY,

    -- The backfill manifest hash. Deterministic per manifest, so a replay of the same
    -- manifest conflicts on (run_id, legacy_claim_id) instead of duplicating a decision.
    run_id TEXT NOT NULL,

    legacy_claim_id TEXT NOT NULL,
    family_id TEXT,

    -- Canonical identity once admitted. NULL on an excluded record.
    claim_object_id TEXT,
    claim_object_hash CHAR(64),
    evidence_object_ids TEXT[] NOT NULL DEFAULT '{}',
    evidence_object_hashes TEXT[] NOT NULL DEFAULT '{}',

    -- Provenance of the legacy source snapshot this decision was made against.
    source_snapshot_hash CHAR(64) NOT NULL,

    decision TEXT NOT NULL,
    reason TEXT,

    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT research_os_naga_admission_run_legacy_key
        UNIQUE (run_id, legacy_claim_id),

    CONSTRAINT research_os_naga_admission_decision_vocabulary
        CHECK (decision IN ('admitted', 'excluded')),

    -- D4: admission is a DECISION. An admitted record carries no reason and DOES carry
    -- canonical claim identity.
    CONSTRAINT research_os_naga_admission_admitted_has_identity_no_reason
        CHECK (
            decision <> 'admitted'
            OR (
                reason IS NULL
                AND claim_object_id IS NOT NULL
                AND claim_object_hash IS NOT NULL
            )
        ),

    -- An excluded record carries a non-empty reason.
    CONSTRAINT research_os_naga_admission_excluded_has_reason
        CHECK (decision <> 'excluded' OR (reason IS NOT NULL AND reason <> '')),

    CONSTRAINT research_os_naga_admission_run_id_format
        CHECK (run_id ~ '^[0-9a-f]{64}$'),

    CONSTRAINT research_os_naga_admission_source_snapshot_hash_format
        CHECK (source_snapshot_hash ~ '^[0-9a-f]{64}$'),

    CONSTRAINT research_os_naga_admission_claim_object_hash_format
        CHECK (claim_object_hash IS NULL OR claim_object_hash ~ '^[0-9a-f]{64}$'),

    CONSTRAINT research_os_naga_admission_evidence_arity_matches
        CHECK (cardinality(evidence_object_ids) = cardinality(evidence_object_hashes))
);

COMMENT ON TABLE public.research_os_naga_admission IS
    'D5 projection: NAGA legacy-claim admission decisions '
    '(Admitted | Excluded(reason)), one row per (run_id, legacy_claim_id). '
    'Append-only guard: row UPDATE/DELETE rejected and the whole-table wipe '
    'statement rejected, both binding migration 279''s function verbatim '
    '(migrations 279/280 precedent).';

-- Append-only guard, reusing 279's function verbatim (see header). Two bindings of the SAME
-- function, because one event class alone does not close the table:
--   * FOR EACH ROW on UPDATE/DELETE -- the per-row mutation path;
--   * FOR EACH STATEMENT on the wipe-everything-at-once event, which PostgreSQL never fires a
--     ROW-level trigger for (migration 280 proved this on research_os_objects itself). Without
--     it the row guard above would leave the whole table erasable in a single statement.
CREATE TRIGGER research_os_naga_admission_immutable
BEFORE UPDATE OR DELETE ON public.research_os_naga_admission
FOR EACH ROW EXECUTE FUNCTION public.reject_research_os_objects_mutation();

CREATE TRIGGER research_os_naga_admission_no_wipe
BEFORE TRUNCATE ON public.research_os_naga_admission
FOR EACH STATEMENT EXECUTE FUNCTION public.reject_research_os_objects_mutation();

-- === ROLLBACK ===
-- Local/CI teardown, not a production rollback step (R-research-os.md R2 s7: production DROP and
-- trigger removal are not rollback steps). It REFUSES on a non-empty admission table, so a
-- rollback can never destroy appended admission decisions: preserve and inventory them first.
DO $$
DECLARE
    has_rows boolean := false;
BEGIN
    IF to_regclass('public.research_os_naga_admission') IS NOT NULL THEN
        EXECUTE 'SELECT EXISTS (SELECT 1 FROM public.research_os_naga_admission)' INTO has_rows;
    END IF;
    IF has_rows THEN
        RAISE EXCEPTION 'research_os_naga_admission holds admission decisions; rollback refused';
    END IF;
END;
$$;
DROP TRIGGER IF EXISTS research_os_naga_admission_no_wipe ON public.research_os_naga_admission;
DROP TRIGGER IF EXISTS research_os_naga_admission_immutable ON public.research_os_naga_admission;
DROP TABLE IF EXISTS public.research_os_naga_admission;
DROP INDEX IF EXISTS public.research_os_objects_valid_to_key_idx;
DROP INDEX IF EXISTS public.research_os_objects_valid_from_key_idx;
DROP FUNCTION IF EXISTS public.research_os_instant_key(text);
