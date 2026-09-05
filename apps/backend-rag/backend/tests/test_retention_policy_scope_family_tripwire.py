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

import io
import re
import tokenize
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

# Entity resolution, not a text window (SCAR family #3 -- a guard must judge
# the ENTITY a lookup reads, not a substring/proximity heuristic around it).
# A statement is the text between the previous `;` and the next `;`: SQL
# statements are semicolon-delimited, so this isolates exactly the query the
# lookup lives in without assuming anything about its length or shape.
_TABLE_REF = re.compile(
    r"(?:FROM|JOIN|UPDATE|INSERT\s+INTO|MERGE\s+INTO)\s+(?:public\.)?(\w+)",
    re.IGNORECASE,
)
_WITH_KEYWORD = re.compile(r"\bWITH\b", re.IGNORECASE)
# Matches one `<name> AS (` CTE head at the current scan position, optionally
# preceded by the comma that separates it from a prior CTE in the same
# `WITH` clause. `re.Pattern.match(string, pos)` anchors at `pos`, so
# advancing `pos` past a CTE's matched close-paren and re-matching here is
# what walks a `WITH a AS (...), b AS (...) SELECT ...` list; the loop stops
# the moment the text at `pos` is the main query instead of another CTE head.
_CTE_HEAD = re.compile(r"\s*,?\s*(\w+)\s+AS\s*\(", re.IGNORECASE)

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


def _extract_ctes(statement: str) -> dict[str, str]:
    """Return {cte_name: cte_body} for every `WITH ... AS (...)` head in `statement`.

    Only the CTE list itself is parsed (walking `,`-separated `name AS (`
    heads immediately after `WITH`); the main query after the list is not a
    CTE head and naturally fails `_CTE_HEAD`'s match, which is what ends the
    walk. Nesting inside a CTE body (parentheses, sub-selects) is handled by
    depth-counting rather than a second regex, since a body's own parens are
    unbounded in shape.
    """

    with_match = _WITH_KEYWORD.search(statement)
    if with_match is None:
        return {}

    ctes: dict[str, str] = {}
    pos = with_match.end()
    while True:
        head = _CTE_HEAD.match(statement, pos)
        if head is None:
            break
        name = head.group(1)
        body_start = head.end()
        depth = 1
        idx = body_start
        while idx < len(statement) and depth > 0:
            char = statement[idx]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            idx += 1
        if depth != 0:
            # Unbalanced parens -- stop rather than misparse the remainder.
            break
        ctes[name] = statement[body_start : idx - 1]
        pos = idx
    return ctes


def _resolve_tables(
    statement: str, ctes: dict[str, str], seen: frozenset[str] = frozenset()
) -> set[str]:
    """Resolve every table `statement` actually reads, recursing through CTEs.

    A `FROM`/`JOIN` target that names a CTE defined in the same statement is
    not itself a table -- it is an alias for whatever that CTE's OWN body
    reads, which may be the shared authority table several CTE layers away
    from the `effective_period @>` predicate that ultimately depends on it
    (the entity that matters), regardless of how many source lines separate
    them (the text-window heuristic this replaces).
    """

    tables: set[str] = set()
    for match in _TABLE_REF.finditer(statement):
        name = match.group(1)
        if name in ctes:
            if name in seen:
                continue  # cyclic CTE reference; nothing further to resolve
            tables |= _resolve_tables(ctes[name], ctes, seen | {name})
        else:
            tables.add(name)
    return tables


def _line_start_offsets(text: str) -> list[int]:
    """Return the char offset where each 1-indexed source line begins."""

    offsets = [0]
    for line in text.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    return offsets


def _string_literal_spans(text: str) -> list[tuple[int, int]]:
    """Return (start, end) char-offset spans for every STRING token in `text`.

    A `.py` candidate is source code, not SQL -- the file-wide statement
    isolation below (previous `;` to next `;`) is a SQL-only notion and, run
    over Python source that has no semicolons at all, degenerates to "the
    whole file is one statement": a scoped query anywhere in the file would
    then satisfy `_SCOPE_PREDICATE` for an UNRELATED unscoped query elsewhere
    in the same file, which is exactly the family-#3 UNDER-match this guard
    exists to prevent. The fix is to resolve the ENTITY a `.py` lookup
    actually lives in first -- the enclosing Python string literal that
    carries the SQL text -- and only then apply `;`-delimited statement
    isolation, bounded to that literal.

    Malformed/incomplete Python (fixtures are sometimes bare snippets) simply
    yields no spans here; the caller falls back to whole-file bounds in that
    case, which is never worse than the pre-fix behaviour.
    """

    spans: list[tuple[int, int]] = []
    offsets = _line_start_offsets(text)
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type != tokenize.STRING:
                continue
            start_row, start_col = tok.start
            end_row, end_col = tok.end
            start_offset = offsets[start_row - 1] + start_col
            end_offset = offsets[end_row - 1] + end_col
            spans.append((start_offset, end_offset))
    except (tokenize.TokenizeError, SyntaxError, IndentationError, ValueError):
        return []
    return spans


def _enclosing_span(
    spans: list[tuple[int, int]], offset: int
) -> tuple[int, int] | None:
    for start, end in spans:
        if start <= offset < end:
            return start, end
    return None


def _unscoped_lookups(path: Path) -> list[tuple[int, str]]:
    text = _live_text(path)
    is_python = path.suffix == ".py"
    string_spans = _string_literal_spans(text) if is_python else []
    offences: list[tuple[int, str]] = []
    for match in _ACTIVE_LOOKUP.finditer(text):
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end())
        if line_end == -1:
            line_end = len(text)
        line = text[line_start:line_end]
        if line.lstrip().startswith(("--", "#", "*")):
            continue

        # For `.py` candidates, bound the statement search to the ENCLOSING
        # STRING LITERAL -- never the whole file (see `_string_literal_spans`
        # docstring). For `.sql` files there is no enclosing-literal notion,
        # so the bound is the whole file, matching prior behaviour.
        if is_python:
            span = _enclosing_span(string_spans, match.start())
            bound_start, bound_end = span if span is not None else (0, len(text))
        else:
            bound_start, bound_end = 0, len(text)

        # Isolate the STATEMENT this lookup lives in -- SQL statements are
        # `;`-delimited, so the text between the previous `;` and the next
        # one (or the enclosing bound, for a fixture/literal with no
        # trailing `;`) is exactly the query to resolve, never a
        # neighbouring statement's -- and, for `.py`, never a neighbouring
        # string literal's either.
        found_start = text.rfind(";", bound_start, match.start())
        stmt_start = found_start + 1 if found_start != -1 else bound_start
        found_end = text.find(";", match.end(), bound_end)
        stmt_end = found_end if found_end != -1 else bound_end
        statement = text[stmt_start:stmt_end]

        ctes = _extract_ctes(statement)
        tables = _resolve_tables(statement, ctes)
        if tables and POLICY_TABLE not in tables:
            # This active-policy lookup does not resolve against the shared,
            # multi-scope authority table this tripwire protects -- entity
            # resolution over its OWN statement shows it reads a DIFFERENT
            # table's own dedicated, single-purpose policy resolver (own
            # EXCLUDE constraint on `effective_period` alone, no second data
            # class ever shares it). A file can still land in the census via
            # `_candidate_files()`'s file-wide substring check even when
            # POLICY_TABLE only appears far away in prose (e.g. a comment
            # explaining why THIS table is deliberately NOT that one) --
            # 294_visa_oracle_consultant_requests_retention_policy.sql is the
            # concrete case: its two `effective_period @>` lookups both join
            # `visa_oracle_consultant_request_retention_policies`, which has
            # no `policy_scope` column and needs none, while POLICY_TABLE's
            # name appears only in an unrelated comment ~200 lines away, in a
            # DIFFERENT statement. A `policy_scope` predicate would not
            # compile there -- the column does not exist -- so this is a
            # false positive, not a defect.
            #
            # An EMPTY resolved table set (no `tables`) is deliberately NOT
            # this branch: a lookup this guard cannot resolve to any table at
            # all is not evidence of innocence, it is evidence the census
            # could not see far enough -- fail CLOSED (fall through to the
            # scope-predicate check below) rather than silently exempt it.
            continue
        if not _SCOPE_PREDICATE.search(statement):
            offences.append((text.count("\n", 0, match.start()) + 1, line.strip()))
    return offences


def test_the_probe_can_actually_see_the_defect_it_guards_against(
    tmp_path: Path,
) -> None:
    """Guilt case: an unscoped resolution must be reported, or the guard is theatre."""

    guilty = (
        "        SELECT id, retention_interval\n"
        "          INTO STRICT policy\n"
        "          FROM public.visa_decision_retention_policies\n"
        "         WHERE environment = NEW.environment\n"
        "           AND effective_period @> NEW.evaluated_at;\n"
    )
    path = tmp_path / "guilty.sql"
    path.write_text(guilty, encoding="utf-8")
    assert len(_unscoped_lookups(path)) == 1


def test_the_probe_does_not_cry_wolf_on_a_scoped_resolution(tmp_path: Path) -> None:
    """Innocence case: the cured shape must pass, or the guard is unusable."""

    innocent = (
        "        SELECT id, retention_interval\n"
        "          INTO STRICT policy\n"
        "          FROM public.visa_decision_retention_policies\n"
        "         WHERE environment = NEW.environment\n"
        "           AND policy_scope = 'VISA_DECISION'\n"
        "           AND effective_period @> NEW.evaluated_at;\n"
    )
    path = tmp_path / "innocent.sql"
    path.write_text(innocent, encoding="utf-8")
    assert _unscoped_lookups(path) == []


def test_a_lookup_through_a_cte_far_from_its_from_clause_is_still_reported(
    tmp_path: Path,
) -> None:
    """Statement-wide entity resolution must not depend on line proximity.

    The CTE's `FROM public.visa_decision_retention_policies` sits ~20 lines
    above the `effective_period @>` predicate that resolves through the CTE
    alias -- the retired ±12-line text window would have missed this entirely
    (the FROM and the predicate are further apart than the window ever
    looked); resolving the STATEMENT's tables, however deep the CTE nesting,
    catches it regardless of distance.
    """

    padding = "\n".join(f"               -- padding line {i}" for i in range(20))
    guilty = (
        "        WITH active_policy AS (\n"
        "            SELECT id, retention_interval, effective_period\n"
        "              FROM public.visa_decision_retention_policies\n"
        "             WHERE environment = NEW.environment\n"
        f"{padding}\n"
        "        )\n"
        "        SELECT id, retention_interval\n"
        "          INTO STRICT policy\n"
        "          FROM active_policy AS ap\n"
        "         WHERE ap.effective_period @> NEW.evaluated_at;\n"
    )
    path = tmp_path / "guilty_cte.sql"
    path.write_text(guilty, encoding="utf-8")
    offences = _unscoped_lookups(path)
    assert len(offences) == 1, offences


def test_statement_isolation_on_py_files_does_not_degrade_to_the_whole_file(
    tmp_path: Path,
) -> None:
    """A `.py` file has no `;` between queries -- bounding must be per-literal.

    `services/visa_engine/retention.py` already ships one correctly-scoped
    query. Appending a SECOND, unscoped query in its own string literal must
    be reported on its own merits: file-wide `;`-delimited isolation (the
    SQL-only notion) degenerates on ordinary Python with no semicolons at all
    to "the whole file is one statement", so the appended lookup would
    wrongly inherit the FIRST query's `policy_scope` predicate and its own
    `FROM public.visa_decision_retention_policies` table resolution too --
    the exact family-#3 UNDER-match this test pins shut.
    """

    source_path = (
        BACKEND_ROOT / "services" / "visa_engine" / "retention.py"
    )
    original = source_path.read_text(encoding="utf-8")
    assert "policy_scope = 'VISA_DECISION'" in original
    assert original.count("effective_period @>") == 1

    appended = original + (
        "\n\n"
        "async def _unscoped_extra_lookup(db_pool, *, environment, evaluated_at):\n"
        "    async with db_pool.acquire() as conn:\n"
        "        return await conn.fetchval(\n"
        '            """\n'
        "            SELECT count(*)\n"
        "            FROM public.visa_decision_retention_policies\n"
        "            WHERE environment = $1\n"
        "              AND effective_period @> $2::timestamptz\n"
        '            """,\n'
        "            environment,\n"
        "            evaluated_at,\n"
        "        )\n"
    )
    path = tmp_path / "retention_copy.py"
    path.write_text(appended, encoding="utf-8")
    offences = _unscoped_lookups(path)
    assert len(offences) == 1, offences


def test_a_py_lookup_scoped_within_its_own_string_literal_is_not_reported(
    tmp_path: Path,
) -> None:
    """Innocence case for `.py`: the scoped literal must not be flagged."""

    innocent = (
        "async def active_policy_available(db_pool, *, environment, evaluated_at):\n"
        "    async with db_pool.acquire() as conn:\n"
        "        return await conn.fetchval(\n"
        '            """\n'
        "            SELECT count(*)\n"
        "            FROM public.visa_decision_retention_policies\n"
        "            WHERE environment = $1\n"
        "              AND policy_scope = 'VISA_DECISION'\n"
        "              AND effective_period @> $2::timestamptz\n"
        '            """,\n'
        "            environment,\n"
        "            evaluated_at,\n"
        "        )\n"
    )
    path = tmp_path / "innocent.py"
    path.write_text(innocent, encoding="utf-8")
    assert _unscoped_lookups(path) == []


def test_table_ref_recognises_update_target_without_from_or_join(
    tmp_path: Path,
) -> None:
    """`UPDATE <table> SET ...` reaches the shared table with no `FROM`/`JOIN`.

    The original `_TABLE_REF` only matched `FROM`/`JOIN`, so an `UPDATE`
    statement against `POLICY_TABLE` resolved to an EMPTY table set and was
    exempted by the (then) "no tables => innocent" branch -- a second
    UNDER-match on the very table this tripwire exists to protect.
    """

    guilty = (
        "UPDATE public.visa_decision_retention_policies "
        "SET effective_period = tstzrange(now(), null) "
        "WHERE environment = 'prod' AND effective_period @> now();"
    )
    path = tmp_path / "update_guilty.sql"
    path.write_text(guilty, encoding="utf-8")
    offences = _unscoped_lookups(path)
    assert len(offences) == 1, offences


def test_a_lookup_with_no_resolvable_table_is_reported_by_default(
    tmp_path: Path,
) -> None:
    """Fail-closed: an unresolvable table set is a defect, not an exemption.

    A statement with no `FROM`/`JOIN`/`UPDATE`/`INSERT INTO`/`MERGE INTO`
    target at all resolves to an EMPTY table set. The pre-fix code treated
    "no tables" the same as "some OTHER table" and silently exempted it --
    but an empty set is evidence the census could not see far enough, not
    evidence of innocence, so the guard must fall through to the ordinary
    scope-predicate check instead of exempting it outright.
    """

    guilty = "SELECT effective_period @> now() AS is_active;"
    path = tmp_path / "no_table_guilty.sql"
    path.write_text(guilty, encoding="utf-8")
    offences = _unscoped_lookups(path)
    assert len(offences) == 1, offences


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
    for `_unscoped_lookups`'s entity resolution: the comment mention lives in
    a different STATEMENT than either lookup, so it never enters either
    lookup's resolved table set.
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


def test_a_294_lookup_rewritten_onto_the_shared_table_is_reported(
    tmp_path: Path,
) -> None:
    """294's exemption is earned by the TABLE a lookup reads, not by the file.

    A copy of 294 where the purge function's JOIN target is swapped from the
    per-class `visa_oracle_consultant_request_retention_policies` table to
    the shared `visa_decision_retention_policies` authority (with no
    `policy_scope` predicate added -- 294 has none anywhere) must NOT enjoy
    294's exemption: entity resolution is per-lookup, and this lookup now
    genuinely reads the shared, multi-scope table the tripwire protects.
    """

    source_path = (
        BACKEND_ROOT
        / "db"
        / "migrations_v2"
        / "294_visa_oracle_consultant_requests_retention_policy.sql"
    )
    original = source_path.read_text(encoding="utf-8")
    assert "policy_scope" not in original
    target = "public.visa_oracle_consultant_request_retention_policies AS p"
    assert original.count(target) == 2
    rewritten = original.replace(
        target, "public.visa_decision_retention_policies AS p", 1
    )
    assert rewritten != original

    path = tmp_path / "294_rewritten.sql"
    path.write_text(rewritten, encoding="utf-8")
    offences = _unscoped_lookups(path)
    assert len(offences) == 1, offences


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
