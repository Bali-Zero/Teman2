# Spec — the static lint for SECURITY DEFINER ledger-lockers

**Status:** DESIGN. Not implemented. FOUR implementation attempts have been made
and all four shipped a hole; this file exists because the fifth is forbidden
until the surface is specified.

**Why this file and not a fourth patch.** `CLAUDE.md` §Agent PR Contract rule 8:
_"A fix-of-a-fix chain stops at depth 1: if the correction is itself wrong, the
surface is under-specified — write the spec, do not open the third PR."_ That is
exactly where this is:

| round | attempt                                                                   | how it failed                                                            |
| ----- | ------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| 1     | dollar-tag-only body reading                                              | skipped legacy `AS '...'` bodies entirely                                |
| 2     | polarity correction — report a DEFINER function whose body cannot be read | the accompanying prose promised it while the code still skipped          |
| 3     | `LINE_COMMENT = re.compile(r"--[^\n]*")` to strip comments                | ate real SQL out of string literals, deleting `FOR SHARE` to end of line |
| 4     | character scanner tracking `'...'` (with `''`) and `$tag$...$tag$`        | **also unsound — two holes below**, so it is not shipping                |

Round 4 was mine, and it is the one that makes this a spec rather than a fifth
patch: the correction to round 3 was itself wrong, in the same direction.

## What the lint must decide

Given the forward section of every `migrations_v2/*.sql`: **is there a
`SECURITY DEFINER` function that takes a row lock on
`visa_decision_retention_policies` and is never transferred to
`visa_ledger_owner`?**

A miss is a silent production 500 — the shape that kept GARUDA VOA magic-link
issuance dead for weeks with zero tokens ever minted. So the two detectors have
DELIBERATELY OPPOSITE polarity, and this is the part every round got wrong
somewhere:

- the **offender** detector is PERMISSIVE — a `SECURITY DEFINER` function whose
  body it cannot read is REPORTED, not skipped;
- `_transfers_in` is STRICT and FAILS CLOSED — anything it cannot prove is a
  transfer is not one.

## The measured holes

Both reproduced by the Gear-3 gate and then independently by the session, on
disk, not argued:

1. **`E'...'` escape strings.** Postgres ends `E'\''` at the backslash escape;
   the scanner sees `''`, reads it as an escaped quote, and stays "inside" a
   literal for the rest of the file. Everything after is emitted un-stripped, so
   a commented-out `-- ALTER FUNCTION ... OWNER TO visa_ledger_owner;` is read
   as a REAL transfer. Laundering, against a detector whose whole point is to
   fail closed. Verified: `"ALTER FUNCTION public.bad()" in _forward(sql)` →
   `True`.
2. **An unclosed dollar tag.** `closing == -1` → `end = n` → the entire
   remainder of the file is emitted un-stripped, with the same laundering
   result. Verified the same way → `True`.

And two holes that PREDATE round 4, in the body-binding and the section split
rather than the stripper:

3. **`DOLLAR_TAG.search(sql, match.end())` is unbounded** — it does not stop at
   the end of the `CREATE FUNCTION` statement. For a legacy `AS '...'` body it
   finds the dollar tag of a LATER statement and binds the body to that, so
   `LEDGER_TABLE in body` is false and a real offender goes unreported. The test
   that claims to cover this, `test_a_body_with_no_dollar_quoting_is_still_read`,
   is green for the wrong reason: its fixture contains no dollar tag anywhere,
   which is true of no real migration in this tree.
4. **`ROLLBACK_MARKER.split` runs on RAW sql, before stripping.** A line
   starting `-- === ROLLBACK ===` inside a dollar-quoted body truncates the
   forward section and everything after it becomes invisible. Contrived, but a
   miss.

## The shape of a sound implementation

The common cause of rounds 3 and 4 is that both tried to answer a
**statement-structure** question with **character or regex scanning**. Comment
stripping, literal boundaries, body binding and statement boundaries are all
one problem — the lexical structure of the file — and solving them one regex at
a time produces a new hole per round.

Requirements for whatever ships:

- **R1. One lexer, not four detectors.** Produce a token/segment stream that
  classifies every byte as CODE / LINE-COMMENT / BLOCK-COMMENT /
  SINGLE-QUOTED / E-STRING / DOLLAR-QUOTED(tag) / IDENTIFIER-QUOTED, and derive
  every later question from THAT. No detector may re-scan raw text.
- **R2. Statement boundaries are part of the lexer's output.** Body binding must
  search only within the statement it started in — hole 3 is definitionally
  impossible once this holds.
- **R3. Unterminated constructs fail CLOSED for the transfer detector and OPEN
  for the offender detector.** An unclosed dollar tag or literal means the file
  is not understood; the correct response is to REPORT a possible offender and
  REFUSE to credit a transfer — never the reverse, which is what rounds 3 and 4
  both did.
- **R4. Every construct the lexer claims to handle carries a guilt test built
  from a REAL migration in this tree, not a hand-written fixture.** The round-4
  fixture argument — "a body with no dollar quoting" — described a file that
  does not exist in `migrations_v2/`.
- **R5. A corpus test.** Run the finished lexer over every file in
  `migrations_v2/` and assert the offender set equals a checked-in expected set.
  A change in the lexer that silently empties that set must be loud.
- **R6. Consider not writing it at all.** The catalog-driven
  `SECURITY_DEFINER_CENSUS_SQL` (PR #5309) answers the same question by asking
  Postgres instead of parsing text, and cannot be evaded by quoting. The static
  lint's only advantage is that it runs without a database. Decide explicitly
  whether that advantage is worth a hand-written SQL lexer before writing one —
  the honest answer may be that a live-cluster integration test is the right
  instrument and the static lint should not exist.

## What ships without it

PR #5302 lands the cure (migration 301) and the preflight inventory extension,
which is what makes the LIVE owner check see the two GARUDA functions. That
check is catalog-driven and is not affected by any of the holes above.

The recurrence protection this lint was meant to add is therefore NOT in force,
and that is stated rather than assumed. It is tracked in
`.claude/skills/modus/PENDING-ARMS.md` — in a row added by the same commit as
this file, because an earlier draft of this line asserted the row existed when
it did not. A standing net claimed in prose that nothing implements is the
disease this spec is about, one level up.
