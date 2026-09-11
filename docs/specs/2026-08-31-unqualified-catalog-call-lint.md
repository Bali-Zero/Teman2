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
   `re.findall(r'"""(.*?)"""', source, re.DOTALL)`. It therefore never saw every `await connection.fetch*("...")` call that passes its SQL as a double-quoted one-liner rather than a triple-quoted block — five of them at the time of writing; cited by SHAPE and not by line number, because the previous citation (`403, 474, 497, 519, 538`) went stale the moment the same commit shifted four of them by +12, which is the third time a line-number citation in this lane has aged into a lie. Two of the blocks it _did_ scan are
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
`cast`, `case`, `exists`, `in`, `any`, `all`, `values`, `row`, `array` are
genuinely grammar/`SystemFuncName`-resolved — `CREATE FUNCTION public.trim(text)`
does not change `trim('  x  ')`, and `position(a,b)` / `extract(a,b)` are syntax
errors.

**`overlaps` was in that list and is WRONG — removed 2026-08-31.** Unlike the
names above, `overlaps` is a REAL `pg_catalog` function, not merely grammar:
only the infix `(a,b) OVERLAPS (c,d)` form is parsed by the grammar, while
`overlaps(a,b,c,d)` is an ordinary name resolved through `search_path` and is
therefore shadowable exactly like `count`. Measured two independent ways: the
gate seat forged it on PG 17.10 (`CREATE FUNCTION public.overlaps(date,date,
date,date) … AS $$ SELECT true $$` made the function form return `true` while
`pg_catalog.overlaps` returned `false`, and the infix form stayed sound); and
against the live cluster read-only, `SELECT count(*) FROM pg_proc WHERE
proname='overlaps'` returns **13** overloads, against a positive control of
**0** for `coalesce`/`nullif`/`case`. The catalogue-presence probe is the
cheaper of the two and needs no write: **provided the SQL spells the name
unquoted**, a name with zero `pg_catalog.pg_proc` rows cannot be shadowed in
function form, and a name with rows can.

That proviso is not decoration, and the sentence was wrong without it. The
property belongs to _(name x spelling)_, not to the name: a quoted identifier
bypasses the grammar entirely and reaches the shadow even at zero catalogue
rows. Measured on PG 17.10 under `search_path = public, pg_catalog`, with
`trim` and `array` — both zero-row entries on the list above:

    CREATE FUNCTION public."trim"(text)  ... AS $$ SELECT 'FORGED' $$;
    "trim"('  x  ')  -> FORGED        trim('  x  ')  -> x
    CREATE FUNCTION public."array"(text) ... AS $$ SELECT 'FORGED' $$;
    "array"('x')     -> FORGED

Not a live hole — this module never quotes an identifier — but an unqualified
absolute in the artifact whose job is to stop unqualified absolutes is the
defect this document exists to name, and it was mine. It sharpens **R1** and
**R3**: an extractor must distinguish the quoted form, which is an ordinary
`search_path` lookup for ANY name, from the bare form, where the grammar can
win.

The full 16-entry sweep, `pg_catalog`-scoped, has since been run: only
`extract` (6 overloads) and `position` (3) have rows, and both were
re-measured rather than inferred — `position('b','abc')` and
`extract('year', date ...)` are syntax errors unquoted, while the grammar forms
`position(a in b)` / `extract(y from d)` resolve to `pg_catalog` with a shadow
installed. Both therefore stay on the list. Controls behaved: `overlaps` 13,
`substring` 8, `count` 2, `string_agg` 2, `array_agg` 2.

That this entry survived is the point of **R2** and **R3** below, not an
exception to them: it was reasoned about ("OVERLAPS is SQL grammar") instead of
tested, which is the same mistake that put `count` and `substring` on the list.
Whatever ships must treat an allowlist entry with no empirical citation as
unproven, and must distinguish a keyword's grammar form from its function form
— they are not the same name.

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
