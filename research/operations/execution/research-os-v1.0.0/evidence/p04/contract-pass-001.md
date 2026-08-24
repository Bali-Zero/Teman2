---
adversarial_review: kimi-k3
---

# P04 Deliverable 4 — Independent contract PASS

- **From**: builder H1, work packet P04 (Research OS v1.0.0, Wave 0)
- **To**: S9-C0 (Conductor)
- **Date**: 2026-08-24
- **State**: `conditional_pass_contract_layer`
- **Measured at**: 2026-08-24T02:46:48Z, `origin/main` HEAD `0545d251d2f9e142b5bd8ae0c9d317e7fc7ae4ed`
  (commit `docs(pending-arms): selftest --selftest corpus is wall-clock-blind on the D3 lanes-absent
  guilt shape (#4772)`), worktree `docs-p04-d4-contract-pass`. Re-pinned from an earlier measurement
  of this same session at `17f2457bc0ca4115f9e0e73594ea7b0237ebc953` (2026-08-24T02:40:15Z) after
  confirming, via `git diff --stat` between the two SHAs, that the single intervening commit touches
  none of `packages/research-os-core/research_os/{models,schemas}/`,
  `apps/backend-rag/backend/db/migrations_v2/`, or `apps/backend-rag/backend/services/research_os/` —
  every claim measured against the earlier SHA in §§2–7 below still holds at this one.

## 1. Verdict

**CONDITIONAL PASS on the contract layer. This is NOT a P04-complete sign-off.** Every claim below
was re-measured in this session against the SHA in the header — by direct file reads, by running
the actual code (not by reading it and assuming), and by executing the repo's own configured lint
where one exists — before being written down. Two of the source brief's claims did not survive that
re-measurement unchanged; both are called out explicitly in §2/§3 rather than silently corrected,
per the discipline this document itself argues for.

Cohort B (P05 Intel Lake, P06 NAGA) is blocked by construction until this lands. Overstating what
is sound here unblocks work that must stay blocked; understating it costs a day. The asymmetry is
deliberate in what follows.

**Voting rubric, stated explicitly** (added on adversarial review — see M4 below): **PASS** means the
deliverable's own packet-defined artifact is complete on its own terms and was independently,
executably verified this session (a test run, a direct function call, a lint run) — not merely read
and trusted. **PARTIAL** means the packet defines two halves for this deliverable and only one is
built, or the artifact is built but fails its own stated packet exit criterion. **NOT DELIVERED**
means no artifact answering the deliverable exists. **"Has this been called from outside
research-os-core?" is deliberately NOT part of this rubric anywhere in §§2–4** — every deliverable in
this document, PASS included, has zero non-test consumers (§5, Finding 1). That fact is real and
important, but it is cross-cutting and is stated once, in Finding 1, applied uniformly to the whole
layer — not smuggled into individual PASS/PARTIAL calls where it would silently penalize some
deliverables and not others for the same true fact.

## 2. PASS — sound and safe for Cohort B to build against

- **D1 — strict typed models.** 25 model files under `packages/research-os-core/research_os/models/`,
  confirmed by directory listing. File-count parity with class-count is not by itself proof of
  inheritance (a file could define zero, one, or several classes, and a per-file `grep` only proves
  *mention* of the class name, not that every model class *inherits* it) — so the check actually run
  this session is class-level introspection, not a count coincidence: imported every module under
  `research_os.models`, enumerated every `pydantic.BaseModel` subclass defined in each (not merely
  imported into it), and checked each against `FrozenCoreModel`. Result: **187 model classes
  defined, 187 inheriting `FrozenCoreModel`, zero exceptions.** `primitives.py` — where
  `FrozenCoreModel` itself is defined — lives at `research_os/primitives.py`, one level above
  `models/`, not inside the `models/` package, so it is not among the 187 and does not inflate the
  count. `primitives.py:346-349`:
  ```
  class FrozenCoreModel(BaseModel):
      """Base configuration for immutable, closed canonical objects."""
      model_config = ConfigDict(extra="forbid", frozen=True)
  ```
  `Extensions` + `validate_extensions()` are wired into every model (`validate_extensions(self.extensions)`
  appears once per model file). The reserved-field guard is real: `primitives.py`'s
  `V1_RESERVED_EXTENSION_FIELD_NAMES` frozenset, counted this session by importing the module and
  calling `len()` on the actual object rather than counting lines — **251 names**, not an
  approximation.
- **D2 — schemas + fixtures.** 25 model files / 25 `*.schema.json` files / 25 fixture kind-directories
  under `packages/research-os-core/fixtures/` — all three counts independently confirmed by directory
  listing. Ran `research_os.cli fixtures --check` directly this session (via the
  `apps/backend-rag/.venv` interpreter, which has the package's `rfc8785` dependency; the bare system
  `python3` does not): output is exactly `{"checked": 218, "failures": [], "valid": true}`. Also
  imported `research_os.schemas` and called both `checked_in_schemas_match()` and
  `validate_schema_artifacts()` directly — both return `()`. Both functions live in
  `research_os.schemas.__init__`, confirmed by `grep`, not in `research_os.cli` — the brief's note on
  that point holds. **Scope delimitation**: "schemas match" here means *static internal consistency*
  — the checked-in `.schema.json` artifacts match what the Pydantic models actually generate, and the
  fixtures validate against those schemas. It is not a claim that the schemas are semantically correct
  against `CONTRACTS.md`'s prose, which is a separate, human-adjudicated question this check cannot
  answer.
- **D7 — deterministic hashing.** `research_os/hashing.py` exists and imports `rfc8785` (the package
  literally named for RFC 8785, JSON Canonicalization Scheme) alongside `object_hash()`. The module is
  referenced from 25+ model files and `cli.py`, consistent with every canonical kind routing through
  one hashing path.
- **D9 — sanitization + risk-reclassification validation.** Two separate model files,
  `sanitization_receipt.py` and `risk_reclassification_receipt.py`, each declaring its own guard logic
  (no shared `validators/` directory — the "two separate modules" in the source brief means these two
  files, not a dedicated validators package, and that reading is consistent with what's on disk).
  Both explicitly scope out what a single-document validator cannot check: `sanitization_receipt.py`
  states in its module docstring, verified this session with a plain `grep`, that "no
  persistence/repository module exists anywhere under `packages/research-os-core`" — the same fact
  independently load-bearing for D10 below (§4), self-consistently derived twice in the codebase.
- **D12 — closed ApprovalReceipt subject/decision matrix + queue-only OperationalReceipt profiles.**
  `approval_receipt.py:110-146` implements a closed subject/decision pair check that raises when
  `self.decision not in allowed` and again when the `(subject.kind, decision)` pair fails a second,
  narrower check — a fail-closed, enumerate-and-reject shape, not an allow-list-with-an-escape-hatch.
  `operational_receipt.py` defines a queue-only literal set (`queue.triage`, `queue.rejected`,
  `queue.snoozed`, `queue.split`, `queue.merge_duplicate`, `queue.evidence_requested`) with an explicit
  comment that `queue.closed` is deliberately unregistered. Git history for `approval_receipt.py` shows
  exactly one commit touching the file, `2568e41ed`, dated **2026-08-23T07:00:00Z** — consistent with
  "hardened 2026-08-23"; the fail-closed shape observed on disk is what that commit landed (there is no
  separate later fix commit to point to — the hardening happened inside that commit's own review
  cycle before merge, not as a follow-up).
- **Contract suites.** Ran `PYTHONPATH=. .venv/bin/python3 -m pytest backend/tests/unit/research_os
  backend/tests/services/research_os -q` from `apps/backend-rag` myself this session: **343 tests
  across 22 files, exit code 0**, all green — **0 skips as run on this worktree this session, all
  343/343 executed** (`grep -c SKIPPED` on `-v` output = 0; counts independently cross-checked two
  ways: summing per-file counts from `--collect-only -q` output, and a direct file count of
  `test_*.py` under both directories, and re-confirmed a second time by a fresh subagent run).
  **Environment-conditional, stated precisely rather than as a single global fact**: the suite
  contains one skip-gated test, `test_prettier_json_matches_real_prettier_across_shape_table`
  (`test_schemas.py`), whose `pytest.mark.skipif` fires only when `node` is absent or this repo's own
  `node_modules/prettier/index.mjs` is not installed. It ran (not skipped) here because that file
  exists in this worktree (confirmed via `ls -la`, 644274 bytes) — a second reviewer's fact-check pass
  correctly observed 1 skip in its own environment. **Neither measurement is wrong; the divergence has
  a mechanism, and it favors treating the skip as expected, not the run as suspect**:
  `node_modules` is repo-gitignored (`.gitignore:234`, confirmed by `git ls-files node_modules`
  returning empty) and therefore untracked. The fact-check's own methodological rigor — building a
  clean, disposable worktree specifically to avoid contaminating what it measured — is exactly what
  produced the divergence: a fresh worktree cannot carry an untracked, gitignored directory, so a
  clean-room reproduction of this suite will always see this one test skip, the same way CI will.
  **A clean-room run is a *different* environment, not a neutral one** — for anything gated on an
  untracked local install, it is the *less* representative of the two, not the more rigorous one.
  So: "0 skips" or "1 skip" as a bare document-wide claim would each be wrong depending on where it's
  read; a reader who reproduces this suite in a fresh worktree or in CI and gets 342/343 should read
  that as a correct reproduction, not as a discovered regression. A green suite proves the tests and the
  code agree with each other, at the cases the tests happen to cover — it is not, by itself, proof the
  contracts are correct against `CONTRACTS.md`'s prose or against every case that matters; the
  schema/fixture and hashing checks above are a second, independent form of verification for exactly
  that reason.

## 3. PARTIAL — state both halves, never round up

- **D3 (compatibility).** The checker is real: `version.py:159` defines `check_compatibility()`, wired
  into `cli.py`'s `compat` subcommand (`--old`/`--new` schema paths, returns 0/1 on compatibility).
  The semantic-version **registry** is not built. Correction from adversarial review (R4): the first
  grep I ran, `grep -rn "producer_version|consumer_version|deprecat"`, is unanchored to
  extended-regex mode — without `-E` that pattern searches for the *literal* string including the pipe
  characters, and would return zero hits in any codebase regardless of whether the terms exist,
  proving nothing. Re-run correctly this session: `git grep -nE
  'producer_version|consumer_version|deprecat' -- packages/research-os-core/
  apps/backend-rag/backend/services/research_os/` → **exit 1, zero hits**. The underlying claim holds;
  the first command just never tested it.
- **D4 (adapters).** Exactly one adapter exists, `apps/backend-rag/backend/services/research_os/
  action_item_adapter.py` (Magazine `ops_intents` → `ActionItem`), alongside `loss_report.py`, whose
  `assert_every_legacy_field_accounted_for()` (line 92) is real anti-silent-drop enforcement. The
  directory `apps/backend-rag/backend/services/research_os/` holds exactly six files — `__init__.py`,
  `_core_path.py`, `action_item_adapter.py`, `legacy_magazine.py`, `loss_report.py`, `synthesis.py` —
  **none named `shadow.py`**, confirmed by direct listing this session. `action_item_adapter.py:373`
  and `__init__.py:10` both cite `shadow.py` as the home of the (unbuilt) dual-write flag. One added
  precision beyond the source brief: a file literally named `shadow.py` **does** exist in the repo, at
  `apps/backend-rag/backend/services/visa_engine/shadow.py` — but it is a completely unrelated module
  in a different domain (the visa engine's write-substrate shadow-match logic), not a sibling the
  research_os package could plausibly mean. The phantom-reference finding stands; only the "does
  `shadow.py` exist anywhere in the repo" framing needed narrowing to "does it exist as a sibling of
  the file that cites it."
  Import-graph check (not just string grep): the only actual `import` of
  `adapt_ops_intent_to_action_item` anywhere in `apps/backend-rag` is in
  `tests/services/research_os/test_action_item_adapter.py`. `legacy_magazine.py` and `synthesis.py`
  only *mention* `action_item_adapter.py` in prose comments — they do not import it, and nothing
  imports either of *them* from outside this same directory. **Zero non-test callers, confirmed by
  import graph, not by substring match.**
- **D5 (persistence).** `apps/backend-rag/backend/db/migrations_v2/279_research_os_contract_core.sql`
  exists: one generic, additive, polymorphic table `public.research_os_objects` (`BIGSERIAL` id,
  `object_kind`, `object_hash CHAR(64)`, `payload jsonb`, GIN index on `payload jsonb_path_ops`), with
  a `BEFORE UPDATE OR DELETE ... FOR EACH ROW` trigger (`research_os_objects_immutable` →
  `reject_research_os_objects_mutation()`) that unconditionally rejects both operations, confirmed by
  reading the trigger body. (No application code reads or writes this table yet — that fact is Finding
  1's, applying to the whole layer per the rubric above, not a reason on its own for D5's grade; D5 is
  PARTIAL because of Finding 2's unmet exit criterion, not because of consumer count.)

  **Code defect found this session, adversarial review M1 — the table is not append-only, it is
  row-mutation-rejecting.** A `BEFORE ... FOR EACH ROW` trigger fires per row and cannot intercept
  `TRUNCATE`, which is statement-level and requires its own separate `BEFORE TRUNCATE ... FOR EACH
  STATEMENT` trigger. `grep -ci truncate` against the migration file returns **0** — no such trigger
  exists. So `UPDATE`/`DELETE` on individual rows are correctly rejected, but anyone holding the
  `TRUNCATE` privilege on the table can empty it in one statement, bypassing the row-level guard
  entirely. "Append-only" is corrected to "row-mutation-rejecting" everywhere in this document. **Not
  just reasoned — measured, twice, independently, on real PostgreSQL 15.19 in a throwaway database**
  (the same instance used for the apply/rollback proof in §6):
  ```
  INSERT   → rc 0, 1 row
  UPDATE   → rc 1, blocked: "ERROR: research_os_objects is append-only" (the trigger's OWN error
             text still says "append-only" — the same overclaim this document is correcting)
             CONTEXT: PL/pgSQL function reject_research_os_objects_mutation() line 3 at RAISE
  TRUNCATE → rc 0, "TRUNCATE TABLE", row count after = 0
  ```
  A `PENDING-ARMS.md` line is opened in this same commit with this exact reproduction; proof-of-armed
  is the same `TRUNCATE` sequence rejecting once a `BEFORE TRUNCATE ... FOR EACH STATEMENT` trigger
  exists.
- **D8.** **The field-level compatibility matrix IS delivered and present at this document's own
  measured HEAD** — `evidence/p04/compatibility-matrix-001.md`, confirmed this session by
  `git show <this-HEAD>:.../compatibility-matrix-001.md`, not by directory listing alone (a listing
  taken from a different, stale worktree during this session's own setup returned "file not found" —
  the file is real at the correct SHA; the earlier miss was a stale-checkout artifact on my end, not a
  fact about `origin/main`). Its own frontmatter reads `adversarial_review: kimi-k3` and it re-pins
  itself to `33377a0325e3` (dated 2026-08-23T21:50:12Z, "a delta pass, not a rewrite"). **Correction,
  adversarial review M3**: an earlier draft of this section called that an "later" SHA than this
  document's own measurement — that was wrong, and checkable directly:
  `git merge-base --is-ancestor 33377a0325e35707639bae8a3174a848d4162bcf <this-document's-HEAD>`
  exits 0, meaning `33377a032` is an **ancestor** — earlier, not later — of both SHAs this document has
  measured against. The word was simply mis-set; there is no temporal impossibility to explain away.
  What was true either way: it is evidence *about* the contract layer, landed via its own
  separately-reviewed PR (#4756), and its own pin (earlier than or equal to this document's) does not
  change what is or isn't built as of *this* document's measurement.
  The **phased dual-write/read plan for Packets 05–15 is still not built** — grepped `dual-write`,
  `dual write`, `dual-read`, `phased.*plan` across `evidence/p04/`: zero hits.

## 4. NOT DELIVERED — plainly, not softened into "partial"

- **D6 — contract registry** (owning system, producer/consumer versions, risk rules, receipt types,
  revocation behaviour, deprecation state). `grep -rn "registry"` across
  `packages/research-os-core/` returns 33 hits, confirmed this session; every one inspected is the
  unrelated **closed-enum-registry** concept (e.g. `enums.py:1`: `"""Frozen closed enum registry for
  Research OS v1.0.0."""`) or prose referencing that concept. None is a contract registry in the D6
  sense.
- **D10 — atomic side-effect-free `RequestedActionSpec` → `ActionItem` + `ActionIntent` repository
  primitive**, and its NEXUS containment adapter. No persistence/repository module exists anywhere
  under `packages/research-os-core` — confirmed both by directory search (`*repositor*`, `*persist*`:
  zero matches) and by the package's own docstring in `sanitization_receipt.py:28` and
  `risk_reclassification_receipt.py:21`, which independently states the identical fact for its own,
  different reason.
- **D11 — atomic classification-change primitive with deferred cross-object constraints.** Both
  `sanitization_receipt.py` and `risk_reclassification_receipt.py` document this as a **DECLARED
  LIMIT**. One methodological note, kept because it is itself a small instance of the anti-hallucination
  discipline this document is applying throughout: a first single-line `grep -n "DECLARED LIMIT"` found
  the string in `risk_reclassification_receipt.py` **five times (lines 20, 35, 42, 57, 115)** but
  returned nothing for `sanitization_receipt.py`. That absence was the tool, not the world — the phrase
  is line-wrapped there (`...rolls back the entire bundle." DECLARED` at end of one line,
  `LIMIT, verified rather than assumed:` starting the next), and a wrap-tolerant read confirms it is
  present, with the same verified-not-assumed framing as the other module.

  **This exact paragraph mis-stated its own count, and that is the more instructive failure of the
  two.** An earlier draft said "seven times" here, not five. The count was wrong **inside the very
  passage arguing that a naive tool can lie about a count** — one lying instrument (the single-line
  grep, diagnosed) sat beside a second, undiagnosed one (a wrong number, asserted with the same
  confidence as the corrected claim next to it), in the same sentence, and it took a second reviewer's
  independent recount — three concordant methods: `grep -c`, `grep -o | wc -l`, and direct line
  citation — to catch it. Recorded rather than smoothed away: a document that argues for recounting
  and then miscounts, and says so plainly when caught, is more credible than one that has never
  visibly been wrong. The count above is now correct, verified the same three ways. A wrap-tolerant
  read of `sanitization_receipt.py` confirms it makes the same verified-not-assumed framing as the
  other module: "the only existing multi-object primitive in this package,
  `research_os.graph.select_current_member`, is a pure in-memory selector/quarantine function ... and
  no persistence/repository module exists anywhere under `packages/research-os-core` to check against
  (confirmed by listing the package: ...)". Both receipt modules genuinely make this claim, and both
  verify it the same way.

## 5. Finding 1 — the layer is unwired

Essentially the entire research-os-core layer — models, schemas, adapters, migration — has **zero
non-test consumers in production code**. `research-os-core` is not a declared dependency of
`apps/backend-rag`: `grep` for `research-os-core`/`research_os_core` across
`apps/backend-rag/pyproject.toml` and its `requirements*.txt` returns nothing. It is reached instead
through a `sys.path` bootstrap, `apps/backend-rag/backend/services/research_os/_core_path.py`, whose
docstring states, verbatim, confirmed this session by direct read:

> `packages/research-os-core` is a standalone, installable package (`pyproject.toml`, setuptools) but
> it is not yet declared as a dependency of `apps/backend-rag` anywhere (grepped: zero non-test
> consumers repo-wide as of this writing).

That quote is the package's own self-report; adversarial review (M2) correctly asked for the docstring
to be checked against an independent import grep rather than taken on trust, and for the two
same-named packages to be told apart — the standalone core `research_os` (from
`packages/research-os-core`) and `backend.services.research_os` (the adapter package under
`apps/backend-rag`, §3 D4). Run this session:
`grep -rn "^from research_os\|^import research_os\b" apps/backend-rag/backend | grep -v /tests/`.
Result: the core package **is** imported, by exactly two files —
`services/research_os/action_item_adapter.py` and `services/research_os/synthesis.py` — both inside
the adapter package itself. Nothing outside `services/research_os/` imports the core package
directly. And §3 D4 already independently established, by import graph rather than by grep, that
`action_item_adapter.py` itself has zero non-test callers. So the chain closes: core package →
imported only by the adapter → adapter imported only by its own test. The docstring's self-report and
this independent import-graph check agree, and now the document shows the check rather than only the
claim.

Deliverables graded PASS in §2 are real and sound as *contracts* — but they are built in isolation.
Nothing in the request-serving path calls them. A contract layer nothing calls is a contract layer
whose real integration cost is still entirely unmeasured. Cohort B should plan for that cost, not
assume it away because the contracts themselves are solid.

## 6. Finding 2 — the migration's apply/rollback proof exists but is not armed as a test

No test names `279` or `contract_core` (verified by file name and by content — `grep -rl` across
`apps/backend-rag/backend/tests/db/` for either string returns zero matches). The file that most
resembles a sweep of `migrations_v2/`, `test_legacy_promotion_migrations.py`, iterates a hardcoded
tuple of eight named migrations (`LEGACY_PROMOTION_FILES`, line 42: `142_legacy_user_profiles.sql`,
`143_legacy_conversations.sql`, `132_legacy_lkpm_reports.sql`, `133_legacy_system_settings.sql`,
`134_legacy_notification_log.sql`, `135_legacy_notification_prefs.sql`,
`136_clients_drive_columns_and_defaults.sql`, `137_team_members_legacy_columns_and_defaults.sql`) and
never had scope over the whole directory — `279` appears zero times in that file, confirmed this
session by `grep -c`. So the absence of `279` there is not an omission by that test; it is
confirmation that **no generic mechanism exists from which `279` could have been forgotten**. That
distinction matters for the Conductor: "a sweep skipped it" is a bug in the sweep; "no sweep exists"
is a structural gap — and the second is what this repository has. Named sibling migrations (`107`,
`114_115_116`, `139`, `149` through `153`) each have their own dedicated per-migration test file in
the same directory, confirmed by listing — 279 has none. **No *automated* test in this repository
proves migration 279 applies and rolls back against an isolated database.**

**The packet's exit criterion has since been met by hand, on the correct PostgreSQL version, and
independently reproduced — but it is still not armed as an automated test (adversarial review R1,
revised after a second reviewer closed the PG15 gap with a real proof).** This changes what kind of
decision is left for the Conductor: the earlier open question was "does the proof exist at all";
that is now closed. What remains is "proven once by hand → armed as CI," the same esiste≠armato shape
as everywhere else in this document, not "never proven."

**Reproduced twice, independently, on real PostgreSQL 15.19** (a second reviewer's session ran it
first, on a throwaway `postgres:15` Docker container on a non-production port, removed after; this
session reproduced the identical sequence independently, on its own fresh throwaway container, before
writing this paragraph):
```
APPLY    → rc 0 — table created, exactly 4 indexes (pkey, kind_recorded_idx,
           object_id UNIQUE, payload_gin_idx — confirmed via \d), trigger present
ROLLBACK → rc 0 — 0 tables, 0 functions remaining (drops the trigger function too)
RE-APPLY → rc 0 — table restored
```
**Declared limit, stated rather than hidden**: this proof applied the migration to an **empty**
database. Production, if this migration is ever applied there, carries 278 pre-existing migrations
already. The proof shows the SQL is valid and reversible in isolation — which is what "isolated
database" in the packet's exit criterion actually asks for — **not** that it composes cleanly against
the existing production schema, which this proof does not and cannot claim.

Two options for the Conductor, narrower than before because the proof itself is no longer in
question:
1. **Accept the manual, twice-reproduced PG15.19 proof as satisfying the exit criterion's substance**,
   and treat "convert it into a permanent, automated CI test" as follow-up work rather than a blocking
   gap — condition 6 in §9 reflects this framing.
2. **Hold D5 at its current PARTIAL grade** until that manual proof is captured as a permanent,
   automated test in this repository (matching the shape of the `107`/`114_115_116`/`139`/`149`–`153`
   sibling tests), and treat that test's existence as the precondition for calling D5 done.
This document does not pick between them. It is recorded as condition 5 in §9 below.

**Squawk and the construct-level PG15 checks below were independently re-verified this session and
remain unaffected by the above** — they establish that the migration's SQL is PG15-compatible by
construction; the paragraphs above establish that it also runs correctly on a real PG15 instance.

What I *did* independently re-verify, and where the source brief's phrasing needed a correction: the
brief stated "`squawk --pg-version=15.0` reports zero issues." Run bare, that is **false** — I ran
`squawk 279_research_os_contract_core.sql --pg-version=15.0` myself with no other flags and got **10
warnings, exit 1** (missing `IF NOT EXISTS`, `BIGSERIAL` vs `IDENTITY`, `CHAR` vs `varchar`, missing
lock/statement timeouts, missing `CONCURRENTLY` on two index creates, banned bare `DROP TABLE` in the
rollback section). None of the 10 concern PG15 feature availability — they are generic migration-
safety style rules. Reading `.github/workflows/migration-lint.yml:211-226`, this repo's CI does not
invoke squawk bare: it excludes 13 specific rules repo-wide as pre-existing, documented, legitimate
suppressions (`prefer-robust-stmts`, `prefer-identity`, `ban-char-field`,
`require-concurrent-index-creation`, `require-timeout-settings`, `ban-drop-table`, and seven more).
Re-running squawk with exactly those 13 excludes, byte-for-byte matching the CI workflow file:
**`Found 0 issues in 1 file 🎉`, exit 0.** So the underlying claim is true — but only as "zero issues
under this repo's actual configured CI invocation," not as a bare, flag-less run. I've stated it that
way here rather than repeat the shorthand.

The independent construct-level PG15-compatibility claim holds on its own terms: the only opclass used
in the migration is `jsonb_path_ops` (line 250), a GIN opclass present since PG9.4 — confirmed by direct
read of the SQL, with the migration's own header comment (line 152) independently noting the same fact.

**A real, separate hazard, found while producing the marker-collision check the brief flagged**: the
literal string `-- === ROLLBACK ===` appears **exactly twice** in migration 279, confirmed by
`grep -n`: line 169, inside a prose comment explaining the marker convention, and line 273, the actual
delimiter. The **production splitter is safe** — `migration_base.py:29-31` defines
`ROLLBACK_MARKER_RE = re.compile(r"^\s*--\s*===\s*ROLLBACK\s*===\s*$", re.IGNORECASE | re.MULTILINE)`,
anchored to match a whole line, so the prose mention at line 169 (embedded mid-sentence, not alone on
its line) cannot match. But `apps/backend-rag/backend/tests/db/test_llm_cost_sql_migrations.py:57`
uses an unanchored `sql.split("-- === ROLLBACK ===")[1]` inside `test_117_rollback_is_drop_chain` —
confirmed by direct read of that exact line. It is harmless today only because migration 117 happens
not to mention the marker string in its own prose. It is latent, not live: the day some future
migration's comments discuss the marker convention the way 279's does, this specific test's `[1]`
index will silently grab prose instead of rollback SQL. Recorded as a nearby observation, not a
blocker on this PASS.

## 7. What Cohort B may and may not start on

P05 (Intel Lake) and P06 (NAGA) **may** build against: the 25 typed models and their `Extensions`/
reserved-field guard; the 25 schema artifacts and fixture sets (`fixtures --check` passing at 218/218);
the RFC 8785 canonical hashing path; the closed `ApprovalReceipt` subject/decision matrix and the
queue-only `OperationalReceipt` profile set; the two sanitization/risk-reclassification downgrade
validators. They **may** treat the `research_os_objects` persistence substrate as **schema-ready in
the strict sense only**: the migration file exists, is additive, carries a real rollback section, and
its apply → rollback → re-apply cycle has been run successfully against a throwaway database. **It is
applied in no environment.** `research_os_objects` is absent from all 89 local databases on this
machine — confirmed this session by querying every one of them
(`to_regclass('public.research_os_objects')`, 89/89 reached successfully, 0 unreachable, 0 containing
the table), a full census rather than a partial scan that could silently conflate "queried and absent"
with "never queried." This document makes no claim about production. No query against that table will
succeed anywhere until the migration is applied. This is the correct state for a migration at this
point in the packet — additive, reversible, and unapplied is not a defect — but it is a state Cohort B
must be told, not one they should infer from the word "exist."

They **may not** rely on: a contract registry (D6 — does not exist); a phased dual-write/read plan for
their own packets (D8 second half — does not exist); any atomic multi-object repository primitive
(D10 — does not exist, and the package's own code says so twice, independently); an atomic
classification-change primitive across objects (D11 — both receipt modules declare this out of scope
by design, not by oversight); or a semantic-version compatibility *registry* (D3 — only a pairwise
schema-diff checker exists). And they must budget for wiring: nothing in `apps/backend-rag`'s
production request path currently imports any of this layer, and the package is not even a declared
dependency of the app that would consume it.

## 8. Corrections to `SESSION-BOARD.md` §0 — measurements, not an edit

`SESSION-BOARD.md` §0 declares itself "measured 2026-08-23 by the Conductor" and warns, in its own
text, "Re-measure before trusting it — a board is a snapshot, and this one decays." It has decayed,
and it has decayed in exactly the row a downstream reader would use to decide whether to start:
"Cohort B (P05 Intel Lake, P06 NAGA) remains blocked by construction until D4's independent PASS is
handed to the Conductor." That sentence sits beside — and is not updated by — this PASS. Read
together, unannounced, the two documents contradict each other with no signal for which is newer.

**This section is measurements handed to the Conductor, not an edit.** `SESSION-BOARD.md` is not
touched by this PR — the board stays the Conductor's artifact, updated by the Conductor, which is the
only property that makes "measured by the Conductor" mean anything. All rows below were re-verified
in this document's own session, at this document's own measured HEAD
(`0545d251d2f9e142b5bd8ae0c9d317e7fc7ae4ed`), independent of anything reported to me and independent
of the board's own text — by directory listing, `git show`, `grep -c`, and (for the migration head)
a direct file-existence check, not by re-reading the board's claims and taking them on faith.

| Board §0 says (measured 2026-08-23) | Measured now, this session |
|---|---|
| `research_os/models/` holds 2 models (`successor_edge`, `revocation_receipt`) | **25** model files (26 with `__init__.py`) |
| `research_os/schemas/` holds 2 schemas | **25** `.schema.json` artifacts |
| "the remaining ~23 object kinds are still to land" | **zero** remaining — all 25 landed |
| D2 absent: "no file matching `research_os` or `contract` exists" in `migrations_v2/` | `279_research_os_contract_core.sql` present; head moved `278` → **`279`** |
| D3 absent: "no adapter/dual-write/parity file exists" under `packages/research-os-core/` | `apps/backend-rag/backend/services/research_os/` holds 6 files, including a real adapter with anti-silent-drop enforcement (§3 above); the compatibility matrix landed via #4756 (§3, D8) |

Two things follow from this table, and only the first is actionable by anyone other than the
Conductor:

1. **The board is stale in the direction of understatement**, not overstatement — it reports less
   than exists, not more. That is the safe direction for correctness and the costly direction for
   time: Cohort B could sit idle on foundations that already exist, which is precisely the waste this
   PASS exists to prevent. A PASS that only lists what's missing and stays silent about what's already
   solid does half its job.
2. **The specific sentence that gates Cohort B's start is the one now contradicted by this document.**
   Whoever reads the board without also reading this PASS is deciding on numbers a day old. This
   section exists so that gap is stated by us, not discovered independently by a reader holding two
   documents that disagree.

## 9. Conditions on this PASS

**Added on adversarial review (R2): "conditional pass" is not a conditional pass without stated
conditions.** A CONDITIONAL PASS that lists no conditions is functionally a PASS with a hedge word —
it gives the Conductor nothing to track. The conditions below are what closes this from CONDITIONAL to
unconditional; each has an owner and a closure test.

1. **D6 — contract registry.** Owner: next P04 builder or a Conductor-assigned lane. Closes when: a
   registry module exists mapping, per canonical kind, owning system, producer/consumer versions, risk
   rules, receipt types, and revocation/deprecation state — verified against `CONTRACTS.md`, not
   assumed from naming.
2. **D8 — phased dual-write/read plan.** Owner: Conductor-assigned lane covering Packets 05–15.
   Closes when: a document exists specifying the dual-write/dual-read rollout sequence those packets
   will follow against `research_os_objects`.
3. **D10 — atomic `RequestedActionSpec`→`ActionItem`+`ActionIntent` repository primitive, and its
   NEXUS containment adapter.** Owner: next P04 builder. Closes when: a persistence/repository module
   exists under `packages/research-os-core` (or an explicit architectural decision records that it
   lives elsewhere) implementing the write atomically — or the Conductor rules the primitive out of
   P04's scope entirely, which is also a valid closure.
4. **D11 — atomic classification-change primitive with deferred cross-object constraints.** Owner:
   next P04 builder. Closes when: the DECLARED LIMIT documented in `sanitization_receipt.py` and
   `risk_reclassification_receipt.py` is replaced by an actual cross-object atomic guard, or the
   Conductor formally accepts the declared limit as permanent scope for v1.0.0.
5. **R1 — whether the twice-reproduced manual PG15.19 proof (§6) satisfies the exit criterion's
   substance, or only an automated CI test does.** Owner: **S9-C0**, not a builder. Closes when: one
   of the two options in §6 is chosen and recorded in this ledger. **Narrower than at this document's
   first draft**: the proof itself now exists and has been independently reproduced twice on the
   correct PostgreSQL version — the open question is only whether that satisfies the letter of "tests
   in an isolated database," not whether the migration actually works on PG15.
6. **A permanent, automated PG15 apply/rollback test for migration 279, converting the manual proof
   in §6 into CI.** Owner: next P04 builder. Closes when: a dedicated test file exists (matching the
   shape of the sibling tests for `107`, `114_115_116`, `139`, `149`–`153`) proving apply and rollback
   against `postgres:15` in CI. Declared, not hidden: neither the manual proof nor this future
   automated test composes against production's existing 278 migrations — both apply to an empty
   schema, which is what "isolated database" means, not a staging-parity claim.
7. **The `TRUNCATE` gap on `research_os_objects` (§3, M1).** Owner: next P04 builder. Closes when:
   a `BEFORE TRUNCATE ... FOR EACH STATEMENT` trigger exists and a `TRUNCATE` attempt against the
   table in a throwaway database is proven rejected — tracked in `PENDING-ARMS.md` alongside this
   commit.

**What would move this document from CONDITIONAL PASS to REFUSE**, stated so the Conductor and any
future re-reader know the bar: any of §§2's PASS-graded claims (D1, D2, D7, D9, D12, or the contract
suites) turning out false on independent re-verification; the migration being applied to any
environment while the `TRUNCATE` gap (condition 7) remains unfixed and unacknowledged; or Cohort B
being found to already depend, in a merged PR, on D6, D10, or D11 as if they existed. None of those
is true as of this document's measurement.

## Adversarial review

**Kimi K3 — verdict: REFUSE.** The Claude-authored document (this one, an earlier draft) received an
independent cross-family review with no access to the repository — text-only adjudication of claims,
reproducers, and internal consistency. Ten findings were returned. The dispatching session did not
accept the verdict at face value: every finding was independently re-verified against the actual
repository before being applied, because a refuter can hallucinate exactly as any other model can.
**Eight findings held and are applied below; two did not hold as formulated and are recorded refuted,
verbatim-in-substance, rather than silently dropped** — a document that reports only the findings that
survived would hide from the reader how much scrutiny the surviving ones actually received.

**Confirmed and applied:**

- **R1 — the original verdict asserted a claim that contradicted the packet's own stated exit
  criterion for D5 (the PG15 apply/rollback test) without naming that as a decision only the
  Conductor can make.** Applied: §6 states the PG15/apply-rollback gap explicitly as a decision
  for S9-C0, with two named options, resolved by neither this document nor its author. **Revised a
  second time, after the finding itself moved**: between this review and this commit, the PG15 gap
  was independently closed by manual proof — twice, by two different sessions, on real
  PostgreSQL 15.19 in a throwaway database — while remaining unarmed as an automated test. §6 and §9
  condition 5 are rewritten to reflect the narrower question that remains (does a twice-reproduced
  manual proof satisfy the exit criterion's substance, versus does only an automated test) rather than
  the wider one R1 originally addressed (does any proof exist at all).
- **R2 — "conditional pass" was asserted with no stated conditions.** Applied: new §9 lists seven
  numbered conditions, each with an owner and a closure test, plus an explicit list of what would move
  this document to REFUSE.
- **R3 — as formulated, false; the underlying principle correct, and the finer check it demanded gives
  stronger evidence than the original.** Kimi hypothesized `primitives.py` lives inside `models/` and
  inflates the 25-file model count. It does not — `research_os/primitives.py`, one level above
  `models/`, confirmed by `find`. But the principle behind the finding — file-count parity with
  class-count is not proof of inheritance; mention is not inheritance; per-file is not per-class — is
  correct, and the class-level introspection it implicitly demands was run: **187 model classes, 187
  inheriting `FrozenCoreModel`, zero exceptions.** §2 D1 now cites this instead of the original
  file-count coincidence. Recorded here as refuted-as-formulated rather than omitted, because the
  mechanism Kimi guessed at was wrong even though the resulting check is an improvement.
- **R4 — the reproducer command in D3 was broken and would return zero hits in any codebase.**
  `grep -rn "producer_version|consumer_version|deprecat"` without `-E` searches for the literal
  string including pipe characters, not alternation. Applied: §3 D3 now cites the corrected command,
  `git grep -nE 'producer_version|consumer_version|deprecat' -- packages/research-os-core/
  apps/backend-rag/backend/services/research_os/`, independently re-run this session (exit 1, zero
  hits) — the underlying claim survives; only the broken reproducer is replaced.
- **M1 — confirmed, and it is a defect in the code, not in the document.** `research_os_objects`'s
  trigger is `BEFORE UPDATE OR DELETE ... FOR EACH ROW`; row-level triggers do not fire on `TRUNCATE`,
  and `grep -ci truncate` against migration 279 returns 0 — no statement-level trigger exists. Applied:
  "append-only" is corrected to "row-mutation-rejecting" throughout, §3 D5 documents the gap in full,
  and a `PENDING-ARMS.md` line is opened in this same commit with a stated proof-of-armed.
- **M2 — Finding 1 rested on the package's own self-reported docstring rather than an independent
  check.** Applied: §5 now also cites a direct import grep
  (`grep -rn "^from research_os\|^import research_os\b" apps/backend-rag/backend | grep -v /tests/`),
  disambiguating the standalone core `research_os` package from the same-named
  `backend.services.research_os` adapter package, and shows the two-file import chain (core →
  imported only by the adapter → adapter imported only by its own test) that makes the docstring's
  claim independently checkable rather than merely quoted.
- **M4 — the PASS/PARTIAL rubric was never stated, and D5's "zero application consumers" language
  looked like a PARTIAL-discriminating fact when the identical fact is true of everything graded PASS
  in §2.** Applied: an explicit rubric paragraph now precedes §2, stating that consumer-count is
  Finding 1's cross-cutting observation, not a per-deliverable discriminator, and §3 D5's wording was
  rewritten so its PARTIAL grade is attributed to Finding 2 (unmet exit criterion), not to consumer
  count.
- **M5 — the contract-suite claim needed an exact count and an epistemic caveat on what "green" proves.**
  Applied: §2's contract-suites bullet now states **343 tests across 22 files**, exit 0 (cross-checked
  by summing `--collect-only` per-file counts, by direct file count, and by a fresh subagent re-run),
  plus a sentence that a green suite proves tests and code agree at the covered cases, not that the
  contracts are correct against every case that matters. **One correction to M5's own supporting
  measurement, caught during this session's follow-up**: a fact-check pass reported "no skips" as
  false and cited 1 skip — that count is real on the environment it was measured in, but is not a
  document-wide fact. `test_prettier_json_matches_real_prettier_across_shape_table` skips only when
  this repo's own `node_modules/prettier` is absent; it is present in this worktree, so the test runs
  here (confirmed twice, including via a fresh subagent). §2 now states the skip as a property of the
  test and its environment-conditional guard, not as a fixed count that would be wrong to state
  identically everywhere.
- **M6 — "schemas match" needed a scope delimitation.** Applied: §2 D2 now states explicitly that
  schema/fixture parity is static internal consistency (checked-in artifacts match what the models
  generate), not a semantic-correctness claim against `CONTRACTS.md`'s prose.

**Refuted as formulated (recorded, not omitted):**

- **R3** — see above; the hypothesized mechanism (`primitives.py` inside `models/`) is false, but the
  finding is recorded here under "confirmed and applied" rather than under a separate refuted list,
  because the principle it argued for held even though its premise did not, and the stronger check it
  prompted is now load-bearing evidence in this document.
- **M3 — false.** The original draft described `compatibility-matrix-001.md`'s self-re-pin to
  `33377a0325e3` as a "later" SHA than this document's own measurement, implying a temporal
  inconsistency worth flagging. `git merge-base --is-ancestor 33377a0325e35707639bae8a3174a848d4162bcf
  0545d251d2f9e142b5bd8ae0c9d317e7fc7ae4ed` exits 0 — `33377a032` (2026-08-23T21:50:12Z) is an
  **ancestor**, i.e. earlier, of this document's measured HEAD (2026-08-24T02:35:39Z). There was no
  impossibility to explain; the word "later" in the original draft was simply wrong. §3 D8 now says
  "earlier / ancestor commit" and cites the `--is-ancestor` check that proves it, downgraded to a
  minor wording fix rather than a substantive finding.

**A second, independent repository fact-check was dispatched in parallel with Kimi's text-only
review and had not returned as of this commit.** Its findings, when they arrive, are not represented
in this section and are not claimed here — this paragraph exists so a reader of this commit knows a
second pass is outstanding rather than assuming Kimi's ten findings are the full adversarial record.
