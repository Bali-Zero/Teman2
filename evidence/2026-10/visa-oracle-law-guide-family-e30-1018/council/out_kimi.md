• VERDICT: SHIP

  Reviewed pr.diff (332/333 migrations, importer, guide, family_e30.json, five Law cards, ITAP.json, tests) against the stated prod shape (code UNIQUE, name NOT NULL, 24 legacy columns, 330/331 already applied).

  Checks that passed:
  - 332: `ADD COLUMN IF NOT EXISTS` (nullable, no default → no table rewrite), IMMUTABLE validator logic is sound: rejects non-arrays, non-objects, extra keys (`choice - 'value' - 'unit' = '{}'`), missing keys (NULL → `IS NOT TRUE`), non-numeric/zero/negative/fractional values, lowercase/unknown units. CHECK addition on 117 NULL rows is instant; lock/statement timeouts protect prod.
  - 333: 26-column INSERT list matches 26 values per row; `ON CONFLICT (code)` updates Law columns only — name, category (insert-only), duration, cost_visa, requirements, metadata never touched. Case-guard DO block runs before the first upsert and `END $guard$;` is valid PL/pgSQL. Dollar-quoting `$j$` is safe: card text contains `$2000` but never `$j$`. Card values are faithful to the verbatim pages: E30A 1/2 YEAR, E30B 1/2/4 YEAR (confirmed independently by PNBP headings), sponsor REQUIRED (`as_stated_boolean: true`), extendable TRUE ("dapat diperpanjang"), entry MULTIPLE, ITAP and totals NULL + TO_VERIFY. NOT_FOUND codes keep everything NULL.
  - Importer: C stays byte-identical (family_c.json gains exactly the previously hardcoded category/permit_class/entry_type); `stay_options` is opt-in per family; rollback clears only Law columns.
  - Tests are real: throwaway-cluster proof (idempotency, legacy preservation, casing-collision failure, 19 invalid shapes), boundary-exact month tests, drift check (`--check`) — none are tautological. No secrets/PII (sha256s of public pages, correctly allowlisted).

  Findings (none blocking):
  1. `guide.py:75` (LOW): `if "stay_options" in visa` is true for E30/E30E/E30F because their value is `null` — if a future question ever routes to a NOT_FOUND code, `sorted(o for o in None)` raises TypeError instead of a verdict. Unreachable today (study_level maps only to E30A/E30B); `visa.get("stay_options")` is safer.
  2. `test_family_e30_postgres.py:115-144` (LOW): the valid/invalid stay_options shape tests silently depend on the first test having populated row E30A (module-scoped cluster, file-order execution). Reordered or `-k`-filtered runs fail spuriously on UPDATE-of-zero-rows. Prod risk: none.

  Dissent: `SET lock_timeout`/`statement_timeout` are session-scoped — if the prod runner splits the file into per-statement executions, the protection silently does not apply; harmless at this table size but worth confirming the runner keeps one session per migration. Validator also permits duplicate options (e.g. two `{1, YEAR}`); harmless, but a uniqueness rule would make the contract tighter.

