#!/usr/bin/env python3
"""
Migration 126: Data-hygiene fix for the live `visa_types` row `code = 'E28D'`
(CF-13, `research/visa/doctrine-factory/e28-consumer-map.md`, PR #4259).

Problem: the live row for E28D still says "Investor KITAS (Bonds)" / "Investor
obligasi pemerintah, Surat berharga negara" — WRONG TOPIC entirely. E28D is
the flagship Golden Visa for a director/commissioner of a branch or
subsidiary company, not a government-bond investor visa.

This is E28F's sibling code and the same class of defect migration_125 fixed
for E28F on 2026-07-19 (PR #2859) — but E28D itself was never touched. The
correct law-aligned text has existed since before this conflict was logged,
independently, in THREE places that never got armed onto the live DB row:

  - `backend/migrations/scripts/seed_visa_types_complete_2026.py` — canonical
    `name`: "Investor Visa Pendirian Cabang atau Anak Perusahaan Golden Visa"
    (verified on disk in this PR, unchanged — already correct, no edit made
    to the seed script).
  - `backend/services/visa_engine/contracts/packs/rulepack-prod-007.source.json`
    — product label "Investor Golden Visa — Branch or Subsidiary (E28D)",
    `covered_purposes: ["INVESTMENT"]`, prohibited activity "operational work
    outside of managing the subsidiary".
  - `research/visa/2026-07-24-w2-factbase-e28-full.md` — independent factbase,
    cites Kepmen M.IP-08.GR.01.01/2025 directly: eligibility requires
    `applicant_role IN [DIRECTOR, COMMISSIONER]` + `investment_type ==
    CORPORATE_SUBSIDIARY`, i.e. exactly E28F's shape minus the IKN-location
    constraint (E28D is the general/non-IKN branch-or-subsidiary Golden
    Visa; E28F is its IKN-specific twin, already fixed).

Ground truth for the `allowed_activities` text below: E28F's own migration_125
fix (mirrored, dropping the IKN-specific clause) + the factbase eligibility
rules above. This migration deliberately does NOT encode the numeric
investment thresholds (USD 25M/50M) or the parent-company global-turnover
requirement (USD 100M, "subject to official discretion" per the factbase)
into the `restrictions` text column — those are eligibility/underwriting
facts that belong in the RulePack's rule engine (already present there,
`review.e28d.usd-threshold-turnover-manual`), not in a free-text column a
client-facing endpoint echoes verbatim. Encoding an unverified/discretionary
numeric threshold into client-facing prose is exactly the class of overclaim
migration_125's own "explicitly OUT of scope" section warned against.
`restrictions` is therefore left `[]`, matching E28F's own fixed value.

Explicitly OUT of scope (verified, not touched):
  - `seed_visa_types_complete_2026.py`'s E28D entry — already law-aligned
    (name + description), no edit needed. Verified by direct read in this
    session, not assumed from the consumer map.
  - The `description` column — migration_125 did not touch it for E28F or
    any of its other 7 codes either (despite its docstring listing
    "description" as a touched field, none of its `VISA_FIXES` entries
    actually included that key). `knowledge_visa.py`'s `VisaTypeBase`
    Pydantic model does not expose `description` on any API response, so
    there is no live consumer to verify against; following the ACTUAL
    migration_125 code pattern (not its docstring) rather than guessing at
    an unverified field.

Note on this migration's numbering system: this file lives in
`backend/migrations/` (the `migration_NNN_*.py` ad-hoc data-hygiene
convention), NOT `backend/db/migrations_v2/*.sql` (the Squawk-linted,
auto-applied SQL runner — see `backend/db/migration_manager.py`, which only
discovers `*.sql` files under `migrations_v2/`). migration_125 itself is the
same kind of file and was run manually via `fly ssh console`, not through
the automatic pipeline — this migration follows that exact, real pattern
rather than the `migrations_v2/*.sql` framework.

Idempotent: the UPDATE is guarded by `WHERE code = 'E28D' AND name !=
<target name>` — re-running this script after it has already applied is a
no-op (0 rows affected), safe to re-run.

Run (prod, via the deployed container which already has DATABASE_URL):
    cat migration_126_fix_e28d_investor_visa.py | \
      fly ssh console -a nuzantara-rag -C "python3 -"

Cache: `visa_types` reads are cached under `zantara:knowledge_visa:*`
(`backend/app/routers/knowledge_visa.py:334,435` — the router's own
create/update endpoints invalidate this namespace, but a direct SQL/asyncpg
UPDATE like this one does NOT go through those endpoints, so it does NOT
auto-invalidate the cache). After this migration is applied in prod, the
namespace `zantara:knowledge_visa:*` must be explicitly invalidated
(`await invalidate_cache("zantara:knowledge_visa:*")` from a shell with
access to the same Redis, or an equivalent `redis-cli --scan` + `DEL`) or
stale E28D data will keep being served from cache until natural TTL expiry.
This migration does NOT perform that invalidation itself — deploy/apply is
the orchestrator's job per CLAUDE.md ship-lifecycle ownership, not this
script's.
"""

import asyncio
import logging
import os

import asyncpg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Kept as a literal string (not a shared constant) so this dict stays a pure
# literal — `ast.literal_eval`-parseable by
# test_visa_types_seed_vs_migration_tripwire.py, which reads VISA_FIXES
# straight off disk without importing/executing this module.
VISA_FIXES = {
    "E28D": {
        "name": "Investor Visa Pendirian Cabang atau Anak Perusahaan Golden Visa",
        "allowed_activities": [
            "Menjabat sebagai direksi atau komisaris pada perusahaan cabang/anak "
            "perusahaan yang didirikan di Indonesia",
            "Berinvestasi dan melakukan aktivitas bisnis terkait pendirian "
            "perusahaan cabang/anak perusahaan",
            "Melakukan pembahasan, negosiasi, dan/atau menandatangani perjanjian "
            "bisnis",
        ],
        "restrictions": [],
    },
}


async def run_migration() -> bool:
    """Returns True iff every code in VISA_FIXES ended in a known-good state
    (updated this run, or already-applied). False on ANY error or missing
    row — the caller turns that into a non-zero exit code so a `fly ssh`
    run that silently failed does not look identical to success (the
    "SKIP: not found, or already at target" ambiguity migration_125 itself
    had — this version distinguishes the two and treats "not found" as an
    error, not a routine skip: a missing row means a typo'd code or the
    wrong database, and staying quiet about that is exactly the kind of gap
    this migration exists to close for E28D).
    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set")
        return False

    conn = await asyncpg.connect(db_url)
    logger.info("Connected to database")

    updated = 0
    already_applied = 0
    errors = 0
    try:
        for code, data in VISA_FIXES.items():
            # allowed_activities/restrictions/name are native Postgres
            # text[]/varchar columns (same schema migration_125 verified
            # live 2026-07-19) — asyncpg maps Python list -> text[]
            # directly, no jsonb cast needed.
            set_clauses = []
            values = []
            idx = 1
            for field, value in data.items():
                set_clauses.append(f"{field} = ${idx}")
                values.append(value)
                idx += 1
            set_clauses.append("last_updated = NOW()")

            # Idempotency guard: touch the row if ANY of the fields we set
            # still differs from its target value — not just `name`. A
            # name-only guard would silently skip a row that has the right
            # name but stale allowed_activities/restrictions (e.g. a prior
            # partial hand-fix), which is the same "looks fixed, wasn't"
            # shape this migration exists to close.
            distinct_clauses = [f"{field} IS DISTINCT FROM ${i + 1}" for i, field in enumerate(data)]
            code_idx = idx
            values.append(code)

            query = f"""
                UPDATE visa_types
                SET {", ".join(set_clauses)}
                WHERE code = ${code_idx} AND ({" OR ".join(distinct_clauses)})
                RETURNING code, name
            """
            try:
                row = await conn.fetchrow(query, *values)
                if row:
                    logger.info(f"OK {code}: {row['name']}")
                    updated += 1
                else:
                    exists = await conn.fetchval(
                        "SELECT 1 FROM visa_types WHERE code = $1", code
                    )
                    if exists:
                        logger.info(
                            f"NO-OP {code}: row already matches every target field "
                            "(idempotent re-run)"
                        )
                        already_applied += 1
                    else:
                        logger.error(
                            f"MISSING {code}: no row in visa_types for this code — "
                            "typo'd code, wrong database, or the row was deleted. "
                            "This is NOT the routine no-op case."
                        )
                        errors += 1
            except Exception as e:
                logger.error(f"ERROR {code}: {e}")
                errors += 1
    finally:
        await conn.close()

    logger.info(
        f"Migration complete: {updated} updated, {already_applied} already-applied, "
        f"{errors} error(s) out of {len(VISA_FIXES)} code(s)"
    )
    return errors == 0


if __name__ == "__main__":
    import sys

    ok = asyncio.run(run_migration())
    sys.exit(0 if ok else 1)
