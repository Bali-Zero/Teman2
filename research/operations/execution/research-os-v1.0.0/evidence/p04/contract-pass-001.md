---
adversarial_review: kimi-k3
---

# P04 Deliverable 4 — Independent contract PASS

- **From**: builder H1, work packet P04 (Research OS v1.0.0, Wave 0)
- **To**: S9-C0 (Conductor)
- **Date**: 2026-08-24
- **State**: `PASS_WITH_LIMITS` — `SESSION-BOARD.md` §9's closed review-flow vocabulary (§1 below);
  corrected from an earlier draft's `conditional_pass_contract_layer`, which was not a member of it
- **Measured at**: 2026-08-24T07:22:20Z, `origin/main` HEAD `e0df8ec86795a6176a85653d760abac64137e454`
  (`docs(secondhome): record the 2026-08-23/24 Studio wave + price-key gotcha (#4763)`, committed
  2026-08-24T03:03:57Z — the merge-base of this worktree with `origin/main`), worktree
  `docs-p04-d4-contract-pass`. **Fourth and final re-pin of this session.** Chain: `17f2457bc` →
  `0545d251d` → `4e2fb20c8ad06ea54809fc74bdab712bb9c126fe` (PR #4615's merge, 2026-08-24T03:08:38Z —
  the SHA an earlier draft of this document pinned to and graded D7 PASS against) → this SHA.
  `git diff --stat 4e2fb20c8... e0df8ec8...` touches exactly one file, `.agents/skills/secondhome/
  SKILL.md`, unrelated to this document's scope — confirmed **empty** in
  `packages/research-os-core/research_os/{models,schemas}/`,
  `apps/backend-rag/backend/db/migrations_v2/`, and `apps/backend-rag/backend/services/research_os/`.
  So D1–D6, D8–D12, Findings 1–2, and §8's board comparison hold unchanged from the prior pin; D1's
  model count (25 files, 187 classes, 187 inheriting `FrozenCoreModel`), D2's schema count (25) and
  `fixtures --check` (`{"checked": 218, "failures": [], "valid": true}`), and the contract suite
  (**349 tests across 23 files**, exit 0) are the prior session's own re-runs at `4e2fb20c8`, carried
  forward by the content-diff proof above, not re-executed a second time by this pass. **D7 (§4) is
  the one exception, and its verdict does not change because of anything that landed between the two
  SHAs — it changes because the prior draft's PASS grade was wrong on its own terms**, found and
  corrected this pass: the raw-dict hash collision cited in §4 was reproduced directly, this session,
  against the code at this pin, not relayed from an earlier report.
  **`origin/main`'s actual current tip is `83f5f61d0`, six commits ahead of this pin** — including
  `65341d886` (P04-D3 slice 2, an ActionIntent adapter under
  `apps/backend-rag/backend/services/research_os/`, inside this document's own §3 D4 scope) and an
  unrelated `secondhome` Studio wave. This document is **not re-pinned to that tip**: this worktree's
  branch is unmerged with it (4 local / 6 remote commits diverged at the time of this pass), and
  pulling in six commits to move the pin is scope this commit does not take on. What this pass *did*
  do, on a second review round: re-ran every declared subtree-absence claim in §§2–9 directly against
  `origin/main`'s current tip via `git grep`/`git ls-tree <SHA> -- <path>` (no checkout needed) rather
  than assume they still held. D3, D8, and D10's absence claims were unaffected — re-run, still zero
  hits. **§3 D4 and §5 Finding 1 were not** — both are corrected in place below, sourced against
  `65341d886` specifically, with the correction marked inline rather than folded in silently. Every
  other claim in this document is still only verified as of this pin, `e0df8ec8`, not `83f5f61d0`.

## 1. Verdict

**Verdict: `PASS_WITH_LIMITS`.** `SESSION-BOARD.md` §9's review-flow protocol defines a closed,
four-token vocabulary for this line — `PASS / PASS_WITH_LIMITS / FAIL / insufficient_evidence`
(line 264) — and this is the one that applies. **Corrected from an earlier draft, which headlined
this "CONDITIONAL PASS on the contract layer": a phrase that is not a member of that set.** The
phrase is not wrong as English and is kept below as a gloss, because it is clear and this document
still wants it said in plain language — but it cannot be the verdict *token*, because §9's own gate
policy pattern-matches on the four-word set, not on prose: `PASS_WITH_LIMITS` "unlocks only what the
receipt explicitly names" — and what this receipt names is §7, nothing more. A verdict spelled
outside the vocabulary gives that downstream gate nothing to match against, which a reader could
reasonably take as an unrestricted PASS. That is exactly the wrong-direction asymmetry the next
paragraph argues against, and exactly the shape the Adversarial-review section elsewhere in this
document calls out in its own gate: an artifact that looks compliant is not the same as one a
mechanical check can actually bind to. **Conditional/limited in the ordinary-English sense too — this
is NOT a P04-complete sign-off** — but that is now the gloss, not the verdict.

**Two different scales are in play here, deliberately, and they do not collapse into each other.**
The packet-level verdict above (`PASS_WITH_LIMITS`, one token, §9's board protocol) grades the whole
deliverable as a unit for the Conductor's review-flow gate. The per-deliverable rubric in §§2–4 below
(PASS / PARTIAL / NOT DELIVERED, twelve separate grades, one per D-item) grades each D1–D12
individually, on this document's own internal scale (defined two paragraphs below). §7's "what
Cohort B may and may not start on" — the exact list `PASS_WITH_LIMITS` unlocks per board policy — is
built from the twelve, not the one; the one packet verdict is what the board's sequence diagram reads.

Every claim below was re-measured in this session against the SHA in the header — by direct file
reads, by running the actual code (not by reading it and assuming), and by executing the repo's own
configured lint where one exists — before being written down. Two of the source brief's claims did
not survive that re-measurement unchanged; both are called out explicitly in §2/§3 rather than
silently corrected, per the discipline this document itself argues for.

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
  backend/tests/services/research_os -q` from `apps/backend-rag` myself this session, at this
  document's final pin: **349 tests across 23 files, exit code 0**, all green — **0 skips as run on
  this worktree this session, all 349/349 executed** (`grep -c SKIPPED` on `-v` output = 0; counts
  independently cross-checked two ways: summing per-file counts from `--collect-only -q` output, and a
  direct file count of `test_*.py` under both directories). The count is 6 tests and 1 file higher than
  earlier in this session (343/22) because PR #4615 (§4 D7 below — graded NOT DELIVERED, not §2)
  landed its own regression suite, `test_hashing_timestamp_parity.py`, between this document's earlier
  pin and this one — re-run in full at the final SHA, not carried forward. That regression suite tests
  only real `UtcDateTime` fields; it is green and blind to the `idempotency_key`-class collision §4
  describes, so its passing is not evidence against that collision.
  **This count is not stable going forward, and that is expected, not a defect in either number —
  but the number this document originally predicted for "after #4781" was wrong, and the correction
  below is itself independently measured, not arithmetic on an old baseline.** An earlier draft of
  this paragraph reasoned that #4781 (§4, §9 condition 8) reverts `test_hashing_timestamp_parity.py`
  along with the fold, so "349 minus 6 tests, minus 1 file" should land back at 343/22 — the number
  cited two sentences above as "earlier in this session." **That subtraction is wrong, because the
  suite is not a static baseline plus one file: other PRs landed tests of their own between this
  document's earlier pin and #4781's merge, and grew the suite faster than one file's removal shrank
  it.** #4781 merged as `9eb328c81` (2026-08-24T07:49:31Z). Measured directly against that exact SHA,
  this session, in an isolated worktree (`git worktree add --detach <path> origin/main`, avoiding any
  need to disturb this branch's own checkout): `PYTHONPATH=. python -m pytest
  backend/tests/unit/research_os backend/tests/services/research_os --collect-only -q`, per-file counts
  summed independently to **360**, and a direct `test_*.py` file count under both directories gives
  **23** — `test_hashing_timestamp_parity.py` is confirmed absent from the collection, so the fold's
  own test genuinely left with the fold, but the surrounding suite outgrew that loss. Cross-checked
  against a second, independent source: `PENDING-ARMS.md` line 1205, written by the revert's own
  lane, separately cites "`pytest backend/tests/unit/research_os backend/tests/services/research_os`
  reports 360 passed / 0 failed" — two independently-produced numbers agree, and neither is this
  document's earlier subtraction. So: **349 tests across 23 files** is the correct, reproducible count
  at this document's own pin (`e0df8ec8`); **360 tests across 23 files** is the correct, reproducible
  count after #4781 (measured, not derived) — the file count coincidentally stays 23 in both cases,
  the test count does not. A reader who reruns this suite post-#4781 and gets 360/23 has reproduced
  this document correctly; a reader expecting 343/22 from an earlier draft's arithmetic will not find
  it, because that number was never actually measured against the post-revert suite.
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
- **D4 (adapters).** **Corrected against `origin/main`'s current tip during this pass's re-verification
  of every declared subtree-absence — not carried forward from this document's own pin (`e0df8ec8`,
  which predates this landing).** A second adapter has landed since the pin: `action_intent_adapter.py`
  (Magazine `ops_intents` → `ActionIntent`, PR #4774 / `65341d886`, P04-D3 slice 2). "Exactly one
  adapter exists" no longer holds — `git ls-tree origin/main -- apps/backend-rag/backend/services/
  research_os/` now returns **seven** files, not six: `__init__.py`, `_core_path.py`,
  `action_intent_adapter.py`, `action_item_adapter.py` (Magazine `ops_intents` → `ActionItem`),
  `legacy_magazine.py`, `loss_report.py` (whose `assert_every_legacy_field_accounted_for()`, line 92,
  is real anti-silent-drop enforcement, unchanged), `synthesis.py`. The directory still contains **no
  file named `shadow.py`**, re-confirmed against `origin/main`'s tip — `action_item_adapter.py:373` and
  `__init__.py:10` still cite it as the (unbuilt) home of the dual-write flag, and the phantom-reference
  finding from the earlier pin (a differently-domained `shadow.py` exists under
  `services/visa_engine/`, not a sibling this package could mean) stands unchanged.

  **The import-graph claim changes materially, not just the file count.** `action_intent_adapter.py`
  composes `action_item_adapter.adapt_ops_intent_to_action_item` by design — its own docstring states
  the reason: the two objects share a cross-object invariant (`action_intent.action_item_ref` must pin
  the sibling `ActionItem`'s exact `object_hash`), and computing the real `ActionItem` first is how it
  satisfies that without re-deriving the same fields a second time. So `adapt_ops_intent_to_action_item`
  now has **one production caller** — `action_intent_adapter.py` — in addition to its own test; the
  earlier pin's claim that its *only* import anywhere in `apps/backend-rag` was
  `test_action_item_adapter.py` is false at `origin/main`'s current tip, confirmed this pass by
  `git grep -n adapt_ops_intent_to_action_item origin/main -- apps/backend-rag/backend`.
  `adapt_ops_intent_to_action_intent` (the new function) has **zero** production callers of its own —
  only `tests/services/research_os/test_action_intent_adapter.py` imports it. `legacy_magazine.py`
  still only *mentions* `action_item_adapter.py` in prose comments, not an import. **What is still
  true, and is the fact Finding 1 (§5) actually depends on: nothing imports either adapter from
  *outside* `apps/backend-rag/backend/services/research_os/`, in either direction** — the new
  composition is an internal cross-import between two siblings in the same unwired package, not a new
  external consumer. "Zero non-test callers" as a bare, absolute claim about `action_item_adapter.py`
  no longer holds and is not repeated here; the narrower, still-true fact (zero callers from outside
  this directory) replaces it.
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
- **D7 — deterministic hashing.** **Corrected from an earlier draft of this document, which graded
  this PASS.** `research_os/hashing.py` exists, imports `rfc8785`, and `object_hash()` is wired into
  25+ model files and `cli.py` — the plumbing an earlier draft's PASS bullet described is real. What
  changes the grade is not the plumbing; it is what PR #4615 did to it.

  **The underlying defect is real, and unreachable in practice with current fixtures.** `hashing.py`
  landed in PR #4586 (`f6a7dfff6`) with a model-path/raw-dict-path disagreement: `UtcDateTime` accepts
  both a trailing `Z` and a trailing `+00:00` for the same instant; the model path re-renders through
  pydantic's `model_dump(mode="json")`, which always normalizes to `Z`, while the raw-dict path did
  not — so a document round-tripped through `cli hash` on the `+00:00` spelling could fail `cli
  validate`'s own re-hash with `object_hash_mismatch`. Every fixture in this packet uses canonical `Z`
  (confirmed this session and the prior one), so this specific failure mode is not live in any shipped
  fixture — it is a latent spec inconsistency (`CONTRACTS.md` §2 demands one hash "identical in every
  implementation" while §3 permits two spellings of one instant), not a wound in production data.

  **PR #4615's cure is disqualified, and was armed in violation of an explicit ledger instruction not
  to.** `.claude/skills/modus/PENDING-ARMS.md` line 1205 SUSPENDED #4615 on 2026-08-23, after a
  cross-family refutation (Kimi K3) and that session's own independent reproduction, stating verbatim
  that the fold "must NOT be armed." The reason: `canonicalize()`'s fold matches any timestamp-*shaped*
  string anywhere in the document tree, with no knowledge of which fields the schema actually types as
  `UtcDateTime` — so a free-text field a real system would mint from a timestamp, e.g.
  `idempotency_key` (`str, min_length=1` on nine model classes, confirmed this session by
  `grep -rl idempotency_key packages/research-os-core/research_os/models/`), collides for two documents
  that differ only in which spelling they used. **Reproduced directly, this session, against the code
  at this document's pin** — not relayed from the ledger or from an earlier report:
  ```
  doc1 = {"contract_version": "1.0.0", "idempotency_key": "2026-01-01T00:01:00Z"}
  doc2 = {"contract_version": "1.0.0", "idempotency_key": "2026-01-01T00:01:00+00:00"}
  canonicalize(doc1) == canonicalize(doc2)  # both render b'..."idempotency_key":"2026-01-01T00:01:00Z"}'
  sha256(canonicalize(doc1)).hexdigest() == sha256(canonicalize(doc2)).hexdigest()
  == "98b552066551671d2f2b32c02672982b83b1f2bf0ddb53620d884e439ace860a"  # True — two different
                                                                          # documents, one hash
  ```
  The fold is applied unconditionally after `model_dump()` inside `canonicalize()`, so this is not
  confined to the raw-dict path: a model instance carrying that same `idempotency_key` collides
  identically on the model path too, and both instances `model_validate` cleanly — no validator
  intercepts it, confirmed by reading `canonicalize()`'s control flow (the fold runs on the dumped
  value regardless of which path produced it). #4615 merged as `4e2fb20c8` at 2026-08-24T03:08:38Z,
  despite the suspension — told in full in the Adversarial review section below. A revert branch,
  `agent/nuzantara/backend-rag/revert-4615-hash-fold` (tip `966b28d372f91d27b85c4e4152217859857c5116`),
  carried a revert commit as of this pin, and **no PR was open for it yet at that point** — checked via
  `gh pr list --state all --head agent/nuzantara/backend-rag/revert-4615-hash-fold` at the time this
  paragraph was written (empty result), not assumed from the branch's existence. **Post-merge
  correction, 2026-08-24: that branch was opened as PR #4781 and has since merged**, as `9eb328c81` at
  2026-08-24T07:49:31Z — see §9 condition 8 for the current state.

  **The real fix is a spec change, not a lane fix.** Per `CONTRACTS.md` §21 this needs a versioned
  freeze-change: PR #4627 landed a *proposal* (merged 2026-08-23T08:18:12Z) to amend §2, declare `Z`
  the single canonical UTC spelling, and normalize at the MODEL layer via a `BeforeValidator` on
  `UtcDateTime` — which cannot reproduce this collision by construction, because pydantic only invokes
  a field's validator chain for that field, never for an unrelated one like `idempotency_key`. The
  proposal is **not yet ratified**: its own frontmatter marks `adversarial_review: pending`, and it
  deliberately leaves two canonical-form sub-options unranked for the Conductor to choose between.
  **D7 is graded NOT DELIVERED, not PARTIAL, because the only code on `origin/main` implementing
  "deterministic hashing" at this pin is the disqualified, suspended, wrongly-armed cure** — reverting
  it, in flight and unmerged as of this pin, **has since merged** (post-merge correction, 2026-08-24:
  PR #4781, `9eb328c81`, 2026-08-24T07:49:31Z — see §9 condition 8), returning the module to the
  pre-#4615 state, which carries the real-but-currently-unreachable spelling-mismatch defect and no
  fold. Owner of the real fix: **S9-C0**, via ratifying the freeze-change (condition 8, §9).
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
**Re-run against `origin/main`'s current tip during this pass, not carried forward from this
document's own pin** — the count changed. Result: the core package **is** imported, by **three**
files — `services/research_os/action_item_adapter.py`, `services/research_os/synthesis.py`, and
`services/research_os/action_intent_adapter.py` (landed via PR #4774 after this document's pin, §3
D4) — all three inside the adapter package itself. Nothing outside `services/research_os/` imports
the core package directly, which is the fact this Finding actually rests on and which the new file
does not change. §3 D4 now independently establishes, by import graph rather than by grep, that
`action_item_adapter.py`'s `adapt_ops_intent_to_action_item` has gained exactly one production caller
— its new sibling `action_intent_adapter.py`, which composes it by design — while
`action_intent_adapter.py` itself, like its sibling before it, has zero callers from outside its own
test. So the chain is now: core package → imported only by two siblings inside the adapter package,
one of which composes the other → neither adapter imported from outside `services/research_os/` except
by tests. The docstring's self-report ("zero non-test consumers repo-wide") is itself one file stale
in the same direction as this document's own earlier pin was — both undercounted by the same landing —
but the conclusion that actually matters, that nothing in the production request path consumes this
layer, is unaffected either way.

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
the closed `ApprovalReceipt` subject/decision matrix and the queue-only `OperationalReceipt` profile
set; the two sanitization/risk-reclassification downgrade validators. **The RFC 8785 canonical hashing
path is deliberately absent from this list** — it was here in an earlier draft; D7 (§4) moved from PASS
to NOT DELIVERED this session, and Cohort B may not rely on it (below). They **may** treat the `research_os_objects` persistence substrate as **schema-ready in
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

They **may not** rely on: **deterministic cross-implementation hashing (D7 — still NOT DELIVERED,
reason corrected post-merge 2026-08-24: PR #4781 reverted #4615's fold, merged `9eb328c81` at
2026-08-24T07:49:31Z — `origin/main` no longer carries the raw-dict/model-path collision §4 describes.
D7 stays NOT DELIVERED because the freeze-change proposal is still unratified (§4, §9 condition 8) and
`hashing.py`, back at its pre-#4615 state, carries the original, real-but-currently-unreachable
UTC-spelling defect with no fold in place; see §4)**; a contract registry (D6 — does not exist);
a phased dual-write/read plan for their own packets (D8 second half — does not exist); any atomic
multi-object repository primitive (D10 — does not exist, and the package's own code says so twice,
independently); an atomic classification-change primitive across objects (D11 — both receipt modules
declare this out of scope by design, not by oversight); or a semantic-version compatibility *registry*
(D3 — only a pairwise schema-diff checker exists). And they must budget for wiring: nothing in `apps/backend-rag`'s
production request path currently imports any of this layer, and the package is not even a declared
dependency of the app that would consume it.

## 8. Corrections to `SESSION-BOARD.md` — measurements, not an edit

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
| D3 absent: "no adapter/dual-write/parity file exists" under `packages/research-os-core/` | `apps/backend-rag/backend/services/research_os/` holds **7** files as of `origin/main`'s current tip (6 at this document's own pin, before PR #4774 landed a second adapter — §3 D4), including two real adapters with anti-silent-drop enforcement (§3 above); the compatibility matrix landed via #4756 (§3, D8) |

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

**A second correction, to a different section of the same board — `SESSION-BOARD.md` §9's Gate
policy, not §0.** Its "Review and integration flow" states, verbatim (line 277): "G1, G2, G3, and G4
require the separate Gear-3 Fable session defined by current Pro topology." That is expired doctrine.
Per `CLAUDE.md` §5 (RULED Zero, 2026-08-20, verbatim: "Togliere Fable 5 dal workflow, lo uso solo io
quando voglio."): Fable 5 is out of the workflow entirely — the Gear-3 final on-disk gate that ruling
used to keep on Fable now closes on **Opus 5** (`xhigh` effort by default per the 2026-08-21
amendment; `max` is opt-in on a declared adjudication, never a default), and "no doctrine, skill,
cron, or script may auto-route to [Fable] — a session must never self-select it." §9's gate policy, as
written, instructs G1–G4 to route to a session the repository's own doctrine forbids auto-routing to.
Not an edit to the board — the same discipline as the §0 table above: measured, cited, left for the
Conductor to reconcile.

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
8. **D7 — freeze-change ratification, `CONTRACTS.md` §2 vs §3's UTC-spelling inconsistency.**
   Owner: **S9-C0**. **Post-merge correction, 2026-08-24: the second half of this condition is now
   DONE.** This condition originally required BOTH the freeze-change ratified AND PR #4615's fold
   reverted out of `canonicalize()`. The revert half closed: PR #4781
   (`agent/nuzantara/backend-rag/revert-4615-hash-fold`) merged as `9eb328c81` at
   2026-08-24T07:49:31Z — confirmed this pass by `grep -c _fold_utc_timestamp_spelling` and
   `grep -c _UTC_TIMESTAMP_HASH_RE` on `hashing.py` (both 0 hits, both exit 1) and by
   `git diff --quiet 868b62322 origin/main -- packages/research-os-core/research_os/hashing.py`
   (exit 0 — byte-identical to the pre-#4615 state). **The condition stays OPEN on its remaining,
   first half only, still owned by S9-C0**: the freeze-change proposal in
   `evidence/p04/freeze-change-proposal-001.md` (landed via PR #4627, 2026-08-23,
   `adversarial_review: pending`) is not yet ratified — `Z` is not yet declared the single canonical
   UTC spelling, and normalization has not moved to the MODEL layer via a `BeforeValidator` on
   `UtcDateTime`. Closes when that ratification lands. Until then, `hashing.py` carries no fold (so
   the collision described in §4 no longer reproduces on `origin/main`) but also carries no
   MODEL-layer normalization — the module's deterministic-hashing guarantee against the original
   `+00:00`/`Z` spelling mismatch still does not formally hold, even though no shipped fixture in this
   packet currently exercises it (every fixture uses canonical `Z`).

**What would move this document's verdict from `PASS_WITH_LIMITS` (§1) to REFUSE**, stated so the Conductor and any
future re-reader know the bar: any of §§2's PASS-graded claims (D1, D2, D9, D12, or the contract
suites) turning out false on independent re-verification; **a reproducible collision in `object_hash`
surviving the revert of PR #4615** (condition 8) — the exact failure mode D7's correction in §4 exists
to flag, so its reappearance after the revert would mean the revert itself is incomplete, not merely
that D7 stays NOT DELIVERED; the migration being applied to any environment while the `TRUNCATE` gap
(condition 7) remains unfixed and unacknowledged; or Cohort B being found to already depend, in a
merged PR, on D6, D7, D10, or D11 as if they existed. None of those is true as of this document's
measurement.

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
  Applied: §2's contract-suites bullet now states an exact count (349 tests across 23 files at this
  document's final pin, up from 343/22 earlier in the session — see the pin note below), exit 0 (cross-checked
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

**Post-Kimi, and the single most consequential finding of this whole review cycle: the session
coordinating this contract-pass review armed a PR against an explicit ledger instruction not to.**
`PENDING-ARMS.md` line 1205 SUSPENDED PR #4615 on 2026-08-23, after a cross-family refutation
(Kimi K3) and that session's own independent reproduction of the collision described in §4 above,
stating verbatim that the cure "must NOT be armed." The coordinating session read the diff, the CI
checks, and the PR body — and armed and merged it anyway, without reading the ledger entry that named
it. It merged as `4e2fb20c8` at 2026-08-24T03:08:38Z. An earlier draft of this document then graded D7
PASS on the strength of that merge having landed: the same failure that put the collision on
`origin/main` also, for one draft of this document, produced the evidence meant to catch exactly this
class of mistake — an unverified "exists" read as "safe." (GitHub's PR timeline records the same actor,
`Balizero1987`, for the arm as for every other action on the PR; it does not distinguish which session
performed which action, so no attribution more specific than "the coordinating session" is available
from that record.)

This is not softened into a process footnote, because the shape is the one this document itself spent
two Findings warning about. Finding 1 and Finding 2 are both instances of esiste≠armato — built is not
wired, proven is not automated — and a document that raises that distinction twice against other
people's work, in the same review cycle, does not get to stay silent about its own gate arming an
explicit suspension. It does not deserve the signature it carries if it does. The one-line rule that
follows, stated so it survives past this paragraph: **before arming any PR, grep the ledger for its
number** — `grep '4615' .claude/skills/modus/PENDING-ARMS.md` would have answered, in this exact case,
in under a second.

**A second, independent repository fact-check was dispatched in parallel with Kimi's text-only
review and had not returned as of this commit.** Its findings, when they arrive, are not represented
in this section and are not claimed here — this paragraph exists so a reader of this commit knows a
second pass is outstanding rather than assuming Kimi's ten findings are the full adversarial record.
