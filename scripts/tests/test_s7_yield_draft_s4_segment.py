"""scripts/s7_yield_draft_local.py -- S4 segment restriction (relationship-history
gate for the "quick check-in" pitch).

Team-lead mandate 2026-08-21: S4 ("active client, no contact 120d+") pulled 501
clients with the un-restricted clause, but only 124 of them (25%) had ever had a
practice on file. `last_interaction_date` is written in one place only
(crm_interactions.py, on a manual team-member log) -- NULL means "nobody logged
an interaction", not "we went quiet on a relationship that existed". Sending the
"a quick check-in on their current status" pitch to a client with zero practice
history would be a first-ever contact disguised as a follow-up. The fix adds
`AND EXISTS (SELECT 1 FROM practices p WHERE p.client_id = c.id)` -- ANY practice
status counts (open/completed/cancelled all prove a service relationship existed).

Test strategy -- CTE-shadow against the live read-only role, ZERO real data touched:
Postgres lets a `WITH clients AS (...)` / `WITH practices AS (...)` clause SHADOW
the real tables for the scope of one query. We take SEGMENTS["S4"]["sql"]
byte-for-byte from the module (no re-derivation -- W114-class bug: two sides that
never agreed on the same logic is its own cicatrix) and wrap it with a fixture of
two literal, non-existent client rows (id 1 = no practice, id 2 = one closed
practice). The query never reads a single row of `clients` or `practices` --
`nuzantara_readonly` only ever needs SELECT on literals here, and the fixture
carries no PII (synthetic ids only). Skips cleanly if the DB/Keychain is
unreachable (CI has neither) -- this is an integration proof, not a unit test
duplicating the SQL in Python (duplicating it would drift from the real query,
exactly the class of bug this file exists to avoid).

Mutation proof (team-lead mandate step 4, performed live 2026-08-21, see PR body):
the SAME fixture run against the SQL with the EXISTS clause stripped returns BOTH
client 1 and client 2 -- i.e. the guilt test below (client 1 must be absent) goes
red the moment the restriction is removed. Not re-encoded as a permanent pytest
mutant (a standing mutant would defeat the real gate, matching the documented
convention in test_yield_optimizer_pitch_gate.py) -- verified once, by hand,
before shipping, and recorded here in prose per that same convention.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO / "scripts" / "s7_yield_draft_local.py"
PG_SH = REPO / "scripts" / "pg.sh"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("s7_yield_draft_local", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


s7 = _load_module()

# Synthetic fixture -- ids 1/2 never exist in the real table (client ids are
# sequential from a live production sequence, and these two rows are shadowed
# CTEs, never inserted anywhere). No name/contact/PII: literal placeholders only.
_FIXTURE = """
    WITH clients AS (
        SELECT * FROM (VALUES
            (1, 'Client A'::varchar, 'Test'::varchar, 'owner@balizero.com'::varchar,
             'active'::varchar, NULL::timestamptz, (now() - interval '200 days')::timestamptz),
            (2, 'Client B'::varchar, 'Test'::varchar, 'owner@balizero.com'::varchar,
             'active'::varchar, NULL::timestamptz, (now() - interval '200 days')::timestamptz)
        ) AS t(id, full_name, nationality, assigned_to, status, deleted_at, last_interaction_date)
    ),
    practices AS (
        SELECT * FROM (VALUES
            (100, 2, 'completed'::varchar, 'paid'::varchar)
        ) AS t(id, client_id, status, payment_status)
    )
"""


def _run_sql(sql: str) -> list[str]:
    """Execute `sql` via scripts/pg.sh against the live READ-ONLY role and
    return the returned client ids (col 1) as strings. Raises RuntimeError if
    the DB/Keychain is unreachable -- callers translate that into a skip."""
    proc = subprocess.run(
        [str(PG_SH), "-tA", "-c", sql],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "pg.sh failed")
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


@pytest.fixture(scope="module")
def s4_ids_with_restriction() -> list[str]:
    """The REAL S4 query (SEGMENTS["S4"]["sql"], untouched) run against the
    synthetic fixture. Skips if the readonly DB/Keychain isn't reachable."""
    sql = _FIXTURE + s7.SEGMENTS["S4"]["sql"]
    try:
        rows = _run_sql(sql)
    except (RuntimeError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        pytest.skip(f"readonly Postgres unreachable, skipping integration proof: {e}")
    # pg.sh -tA on a multi-column SELECT prints '|'-joined rows; the id is the
    # first field.
    return [row.split("|", 1)[0] for row in rows]


# ---------------------------------------------------------------------------
# Guilt: silent 200d, ZERO practices -> excluded from S4.
# ---------------------------------------------------------------------------


def test_client_with_no_practice_never_ever_contacted_is_excluded(
    s4_ids_with_restriction,
):
    assert "1" not in s4_ids_with_restriction, (
        "client_id=1 (active, silent 200d, NO practice on file) must NOT enter "
        "S4 -- the 'quick check-in' pitch presupposes a relationship the CRM "
        "cannot document for this client"
    )


# ---------------------------------------------------------------------------
# Innocence: silent 200d, WITH a (closed) practice -> still included.
# ---------------------------------------------------------------------------


def test_client_with_a_closed_practice_still_enters_s4(s4_ids_with_restriction):
    assert "2" in s4_ids_with_restriction, (
        "client_id=2 (active, silent 200d, ONE completed practice) must still "
        "enter S4 -- the restriction proves a relationship existed, it must not "
        "additionally require the practice to be currently OPEN"
    )


def test_only_the_documented_relationship_survives(s4_ids_with_restriction):
    """Exact-membership guard: the fixture has exactly one client that should
    survive the restriction. If a future edit widens the EXISTS clause (e.g.
    to also implicitly admit undocumented clients via an OR), this catches it
    even if the two tests above would individually still pass."""
    assert s4_ids_with_restriction == ["2"]


# ---------------------------------------------------------------------------
# Mutation-proof scaffold (not run automatically -- see module docstring):
# the same fixture against the SQL with the EXISTS clause stripped. Kept here,
# skipped by default, so a future session can re-verify the mutation without
# hand-editing the shipped module (which would itself be the mutant the repo's
# guard-conformance doctrine warns never to leave standing).
# ---------------------------------------------------------------------------


@pytest.mark.skip(
    reason=(
        "manual mutation-proof, not a standing CI mutant (see module "
        "docstring / test_yield_optimizer_pitch_gate.py precedent) -- run "
        "with `-m ''` to re-verify by hand"
    )
)
def test_mutation_without_exists_clause_both_clients_appear():
    unrestricted_sql = s7.SEGMENTS["S4"]["sql"].replace(
        "AND EXISTS (SELECT 1 FROM practices p WHERE p.client_id = c.id)\n", ""
    )
    try:
        rows = _run_sql(_FIXTURE + unrestricted_sql)
    except (RuntimeError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        pytest.skip(f"readonly Postgres unreachable: {e}")
    ids = sorted(row.split("|", 1)[0] for row in rows)
    assert ids == ["1", "2"], (
        "with the restriction stripped, BOTH the undocumented client (1) and "
        "the documented one (2) must reappear -- proving the guilt test above "
        "is actually exercising the EXISTS clause, not a coincidence of the "
        "fixture"
    )
