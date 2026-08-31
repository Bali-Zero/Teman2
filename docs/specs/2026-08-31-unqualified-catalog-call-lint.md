# Spec — detecting unqualified, shadowable catalog calls in preflight SQL

**Status:** DESIGN. Not implemented. Two instruments have been tried; both have
holes, and the second's holes are the reason this file exists rather than a
third attempt.

## The threat, stated precisely

`operational_preflight.py` answers privilege and ownership questions by querying
`pg_catalog`. The role it runs as can `CREATE` in `public`. Under
`search_path = public, pg_catalog`, any unqualified name in those queries can be
shadowed by an object that role creates, and the check answers whatever the
attacker's object returns.

This is not theoretical. On 2026-08-31 `string_agg` was found unqualified in the
`visa:no-dual-capability-login-role` statement — a segregation-of-duties check.
Proven on a throwaway PostgreSQL 17.10:

```sql
CREATE FUNCTION public.forge_sfunc(text, name, text) RETURNS text
  LANGUAGE sql IMMUTABLE AS $$ SELECT NULL::text $$;
CREATE AGGREGATE public.string_agg(name, text) (sfunc = public.forge_sfunc, stype = text);
SET search_path = public, pg_catalog;
```

The shipped query returned empty (forged clean); `pg_catalog.string_agg`
returned the three real roles. **An aggregate is shadowable exactly like a
function.**

## Round 1 — the hand-maintained tuple

`forgeable` in `test_operational_preflight.py`: a literal list of catalog names
that must appear `pg_catalog.`-qualified. It failed the way a hand list always
fails — `string_agg` was not in it, so a real forgeable call sat unqualified and
nothing was red. This is the list-vs-catalog anti-pattern the module's own
`SECURITY_DEFINER_CENSUS_SQL` exists to replace.

Still in place today, with `string_agg` added, because it is better than
nothing. It can only ever catch names someone remembered.

## Round 2 — the "list-free" detector (WITHDRAWN same day)

Intended to invert the polarity: instead of "these names must be qualified"
(a miss is silent), assert "every unqualified call must be declared safe"
(a miss is loud). Three holes, all measured:

1. **It read the wrong half of the file.** SQL was extracted with
   `re.findall(r'"""(.*?)"""', source, re.DOTALL)`. Five of the module's SQL
   statements are single-quoted one-liners — `operational_preflight.py:403, 474,
497, 519, 538` — and were never scanned. Two of the blocks it _did_ scan are
   prose docstrings, not SQL. Demonstrated by appending
   `_NEW_PROBE_SQL = "SELECT array_agg(role.rolname) FROM pg_catalog.pg_roles AS role"`
   (`array_agg` in neither list, shadowable like `string_agg`): **46 passed**.
   The same text inside a `"""` block goes red. It answered "are the
   triple-quoted blocks clean?" while appearing to answer "is the module's SQL
   clean?".
2. **Two allowlist entries were wrong**, disproven on PostgreSQL 17.10:
   `count` IS shadowable (`CREATE AGGREGATE public.count(*)` → unqualified
   `count(*)` returns 0 over five rows; `pg_catalog.count(*)` returns 5); and
   `substring` is grammar-resolved only in its `from … for …` form — the comma
   form `substring('abcdef', 2, 3)` is an ordinary search_path lookup and
   returned `FORGED`. A wrong allowlist entry is the same class of hole as the
   tuple it replaced.
3. **It fired on correct work, and its remedy fed hole 2.** A docstring
   mentioning `connection.fetchval(...)` failed it; so did a legitimate
   `WHERE role.rolcanlogin AND NOT (role.rolsuper OR role.rolbypassrls)`
   (`not` read as a call). The assertion message told the author to add the
   name to the allowlist — making "grow the list that is already wrong" the
   path of least resistance. A guard that fires on correct work teaches people
   to edit the guard.

Verified sound in that allowlist, so the next attempt need not re-derive them:
`trim`, `position`, `extract`, `coalesce`, `least`, `greatest`, `nullif`,
`cast`, `case`, `exists`, `in`, `any`, `all`, `values`, `row`, `array`,
`overlaps` are genuinely grammar/`SystemFuncName`-resolved —
`CREATE FUNCTION public.trim(text)` does not change `trim('  x  ')`, and
`position(a,b)` / `extract(a,b)` are syntax errors.

## Requirements for whatever ships

- **R1. Extract SQL structurally, not lexically.** Parse the module with `ast`
  and take the actual string arguments passed to `connection.fetch`,
  `fetchval`, `fetchrow`, `execute` — including implicit concatenation and
  f-string constants. Never a regex over the source text: hole 1 is
  definitionally impossible once the extractor knows what a SQL argument _is_,
  and prose docstrings stop being scanned because they are not arguments.
- **R2. Every allowlist entry carries an empirical citation.** Not a judgement
  that a name "looks like syntax" — a recorded probe on a real cluster showing
  that `CREATE FUNCTION public.<name>(...)` does NOT change the result. Holes
  2 exists because two entries were reasoned about instead of tested.
- **R3. Distinguish the grammar forms of the same keyword.** `substring(a,b,c)`
  and `substring(a from b for c)` are different resolution paths. An entry that
  cannot express that distinction must not be an entry.
- **R4. Guilt AND innocence, from the real module.** The guilt fixture must be a
  shadowable call in EACH quoting style the module actually uses (triple-quoted
  block and single-quoted one-liner), since hole 1 was invisible to a
  triple-quote-only fixture.
- **R5. A false positive must not be fixable by growing a list.** If the check
  cannot decide, it must say what evidence would decide it — not offer the
  allowlist as the remedy.
- **R6. Consider the cheaper instrument first.** A live-cluster test that
  actually creates a shadowing object in `public` and asserts each check still
  answers correctly proves the property end-to-end and cannot be fooled by any
  extraction bug. It needs a database, which is why a static lint was attempted
  — decide explicitly whether that trade is worth it before writing a parser.

## What is in force meanwhile

The `forgeable` tuple, with `string_agg` added, and the qualification itself.
The gap is tracked in `.claude/skills/modus/PENDING-ARMS.md`.
