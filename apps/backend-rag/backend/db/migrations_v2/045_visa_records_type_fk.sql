-- Migration 045: Replace hardcoded visa_type CHECK with FK to visa_types table
-- visa_records currently has 0 rows and a CHECK listing 9 fixed types.
-- visa_types has 117 types (A1, B1, C1..E28A etc.) — proper reference table.
-- Safe: table is empty, rename old constraint, add FK.

ALTER TABLE visa_records
    DROP CONSTRAINT IF EXISTS chk_visa_records_visa_type;

ALTER TABLE visa_records
    ADD CONSTRAINT fk_visa_records_visa_type
    FOREIGN KEY (visa_type) REFERENCES visa_types(code)
    ON UPDATE CASCADE
    ON DELETE RESTRICT
    DEFERRABLE INITIALLY DEFERRED;
