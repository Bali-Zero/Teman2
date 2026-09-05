"""Every active-policy resolver on the shared retention authority must scope itself.

`public.visa_decision_retention_policies` stopped being "one active row per
environment" when migration 281 added `policy_scope` and widened the exclusion
constraint to partition on it. From that moment the table holds one active row
per (environment, scope), and any reader that resolves "the" active policy with
only `environment = ... AND effective_period @> ...` silently matches every
other data class's policy too.

Four readers were left unscoped and all four broke together in production on
2026-08-26 when the first GARUDA policy went live: the Python evaluate gate
abstained, the two SQL binders would have raised TOO_MANY_ROWS on the first
write, and the retention purge worker refused to run. Behavioural tests did not
catch it because every fixture seeds exactly one policy — the defect is only
visible when a FOREIGN-scope policy coexists, which no test arranged.

This tripwire is therefore structural, not behavioural: it asserts that no
active-policy resolution anywhere in the shipped tree is missing its scope
predicate, so the next reader added against this table cannot repeat the class.
Behavioural coverage lives next to each reader; this file exists to make the
FAMILY, not one instance, impossible to regress.
"""

from __future__ import annotations

import re
from pathlib import Path

from backend.db.migration_base import split_migration_sql

BACKEND_ROOT = Path(__file__).resolve().parents[1]

POLICY_TABLE = "visa_decision_retention_policies"

# `effective_period @> <clock>` is the signature of an active-policy lookup.
# The writer-side guards use `NEW.effective_period @> <row clock>` instead --
# they validate a policy being inserted against existing rows and are a
# different shape, so they are excluded by the `NEW.` prefix.
_ACTIVE_LOOKUP = re.compile(r"(?<!NEW\.)(?<!\w)effective_period\s+@>")
_SCOPE_PREDICATE = re.compile(r"policy_scope\s*(=|IN\b)", re.IGNORECASE)

# The window around a lookup in which its scope predicate must appear. A
# resolution query is a handful of lines; 12 is generous without reaching into
# a neighbouring statement.
_WINDOW = 12

# The census walks the WHOLE backend tree, not an allowlist of directories.
# An allowlist is the same defect one level up: it silently stops covering
# whatever is added next. The first draft here listed `services/`, `scripts/`
# and `db/migrations_v2/`, and an adversarial reviewer showed it was blind to
# `backend/app/` -- 287 shipped Python files including 163 routers, exactly
# where a "retention status" endpoint would plausibly be written. Latent then
# (nothing under `app/` touched the table yet), guaranteed eventually.
_SEARCH_ROOT = BACKEND_ROOT

# Test trees are excluded: a fixture that seeds two scopes on purpose is not a
# defect, and this file's own guilt case would otherwise report itself.
_EXCLUDED_PARTS = ("/tests/", "/.venv/", "/node_modules/")

# Migrations are append-only history: a file that shipped an unscoped resolver
# BEFORE 281 introduced scoping is a historical record, not a live defect, and
# rewriting it would rewrite what production actually ran. Only the CURRENT
# definition of a function matters. 264's two binders are exempted here because
# a later migration redefines both of them with the scope predicate -- an
# exemption that is not taken on trust: `test_the_historical_exemption_is_
# earned` below re-derives it and fails if that later redefinition disappears.
_HISTORICAL_MIGRATIONS = frozenset({"264_visa_decision_retention_policy.sql"})

# The functions 264 defines unscoped and a later migration must re-define with
# the scope predicate for 264's exemption to be honest.
_SUPERSEDED_BINDERS = (
    "bind_visa_decision_retention_policy",
    "bind_visa_evaluate_idempotency_retention_policy",
)

# A migration's own ROLLBACK half deliberately restores the pre-fix bodies --
# that is what a rollback means. Only the forward half is live code. The split
# uses the runner's OWN function rather than a substring search: the marker
# name appears inside header prose in several migrations (289's included), and
# a naive `text.split("-- === ROLLBACK ===")` cuts there instead, which would
# make this probe read a header comment as the entire forward half and pass
# for the wrong reason.


def _live_text(path: Path) -> str:
    """Return the part of the file that describes the CURRENT schema."""

    text = path.read_text(encoding="utf-8")
    if path.suffix != ".sql":
        return text
    forward, _rollback = split_migration_sql(text)
    return forward


def _candidate_files() -> list[Path]:
    found: list[Path] = []
    for suffix in ("*.py", "*.sql"):
        for path in _SEARCH_ROOT.rglob(suffix):
            as_text = str(path)
            if any(part in as_text for part in _EXCLUDED_PARTS):
                continue
            if path.name in _HISTORICAL_MIGRATIONS:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if POLICY_TABLE in content:
                found.append(path)
    return sorted(found)


def _unscoped_lookups(path: Path) -> list[tuple[int, str]]:
    lines = _live_text(path).splitlines()
    offences: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        if not _ACTIVE_LOOKUP.search(line):
            continue
        if line.lstrip().startswith(("--", "#", "*")):
            continue
        window = "\n".join(lines[max(0, index - _WINDOW) : index + _WINDOW])
        if POLICY_TABLE not in window:
            # This active-policy lookup does not resolve against the shared,
            # multi-scope authority table this tripwire protects -- it is a
            # DIFFERENT table's own dedicated, single-purpose policy resolver
            # (own EXCLUDE constraint on `effective_period` alone, no second
            # data class ever shares it). A file can still land in the census
            # via `_candidate_files()`'s file-wide substring check even when
            # POLICY_TABLE only appears far away in prose (e.g. a comment
            # explaining why THIS table is deliberately NOT that one) --
            # 294_visa_oracle_consultant_requests_retention_policy.sql is the
            # concrete case: its two `effective_period @>` lookups both join
            # `visa_oracle_consultant_request_retention_policies`, which has
            # no `policy_scope` column and needs none, while POLICY_TABLE's
            # name appears only in an unrelated comment ~200 lines away. A
            # `policy_scope` predicate would not compile there -- the column
            # does not exist -- so this is a false positive, not a defect.
            continue
        if not _SCOPE_PREDICATE.search(window):
            offences.append((index + 1, line.strip()))
    return offences


def test_the_probe_can_actually_see_the_defect_it_guards_against() -> None:
    """Guilt case: an unscoped resolution must be reported, or the guard is theatre."""

    guilty = (
        "        SELECT id, retention_interval\n"
        "          INTO STRICT policy\n"
        "          FROM public.visa_decision_retention_policies\n"
        "         WHERE environment = NEW.environment\n"
        "           AND effective_period @> NEW.evaluated_at\n"
    )
    lines = guilty.splitlines()
    hits = [
        line
        for index, line in enumerate(lines)
        if _ACTIVE_LOOKUP.search(line)
        and not _SCOPE_PREDICATE.search(
            "\n".join(lines[max(0, index - _WINDOW) : index + _WINDOW])
        )
    ]
    assert len(hits) == 1, hits


def test_the_probe_does_not_cry_wolf_on_a_scoped_resolution() -> None:
    """Innocence case: the cured shape must pass, or the guard is unusable."""

    innocent = (
        "        SELECT id, retention_interval\n"
        "          INTO STRICT policy\n"
        "          FROM public.visa_decision_retention_policies\n"
        "         WHERE environment = NEW.environment\n"
        "           AND policy_scope = 'VISA_DECISION'\n"
        "           AND effective_period @> NEW.evaluated_at\n"
    )
    lines = innocent.splitlines()
    hits = [
        line
        for index, line in enumerate(lines)
        if _ACTIVE_LOOKUP.search(line)
        and not _SCOPE_PREDICATE.search(
            "\n".join(lines[max(0, index - _WINDOW) : index + _WINDOW])
        )
    ]
    assert hits == []


def test_the_historical_exemption_is_earned_by_a_later_scoped_redefinition() -> None:
    """264 is exempt only because something later fixes what it shipped.

    Without this, removing the superseding migration would make the whole
    family silently pass again on the very functions that caused the outage.
    """

    migrations_dir = BACKEND_ROOT / "db" / "migrations_v2"
    for function_name in _SUPERSEDED_BINDERS:
        # `ALTER FUNCTION ...` mentions the same signature without redefining
        # the body (268 does exactly that), so only CREATE counts here.
        definition = re.compile(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+public\."
            + re.escape(function_name)
            + r"\s*\(\s*\)"
        )
        redefinitions = []
        for path in sorted(migrations_dir.glob("*.sql")):
            if path.name in _HISTORICAL_MIGRATIONS:
                continue
            forward = _live_text(path)
            match = definition.search(forward)
            if match is None:
                continue
            body = forward[match.end() :]
            redefinitions.append((path.name, bool(_SCOPE_PREDICATE.search(body[:3000]))))
        assert redefinitions, (
            f"{function_name} is only defined by an exempted historical migration -- "
            "nothing scopes it, so the exemption hides a live defect"
        )
        # The live definition is the highest-numbered one; earlier ones are
        # themselves history.
        last_file, last_is_scoped = redefinitions[-1]
        assert last_is_scoped, (
            f"the current definition of {function_name} ({last_file}) has no "
            f"policy_scope predicate: {redefinitions}"
        )


def test_the_census_is_not_empty() -> None:
    """A probe that scans nothing passes for the wrong reason."""

    files = _candidate_files()
    assert len(files) >= 5, [str(p) for p in files]


def test_a_lookup_against_a_different_dedicated_policy_table_is_not_an_offence() -> None:
    """A file can enter the census by prose alone; that must not indict it.

    `294_visa_oracle_consultant_requests_retention_policy.sql` mentions
    POLICY_TABLE's name once, in a comment explaining why it is deliberately
    NOT reused, ~200 lines from its own two `effective_period @>` lookups --
    both of which join `visa_oracle_consultant_request_retention_policies`, a
    single-purpose table with its own EXCLUDE constraint on `effective_period`
    alone (never a second data class, so no `policy_scope` column exists or
    is needed there). Guilt on this file would demand a predicate against a
    column that does not exist -- the assertion below is the innocence case
    for `_unscoped_lookups`'s file-selection-vs-resolution-target distinction.
    """

    path = (
        BACKEND_ROOT
        / "db"
        / "migrations_v2"
        / "294_visa_oracle_consultant_requests_retention_policy.sql"
    )
    assert path.exists(), path
    assert POLICY_TABLE in path.read_text(encoding="utf-8")
    assert _unscoped_lookups(path) == []


def test_no_shipped_active_policy_lookup_is_missing_its_scope_predicate() -> None:
    offences = {
        str(path.relative_to(BACKEND_ROOT)): found
        for path in _candidate_files()
        if (found := _unscoped_lookups(path))
    }
    assert offences == {}, (
        "active-policy resolution without a policy_scope predicate -- since "
        "migration 281 this matches every OTHER data class's policy too, which "
        "is the 2026-08-26 Visa Oracle outage: " + repr(offences)
    )
