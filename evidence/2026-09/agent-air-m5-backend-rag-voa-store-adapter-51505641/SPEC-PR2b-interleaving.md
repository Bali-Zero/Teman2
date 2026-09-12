# SPEC — PR2b: make the INSERT-race branch OBSERVABLE, and give "winner vanished" a semantics

Written under Builder Contract 1: a fix-of-a-fix stops at depth 1, and if the correction is
itself wrong the surface is under-specified, so the spec is written instead of a third cure.
Two refuter rounds on PR2a (Sol, `gpt-5.6-sol`, O1 → O2) reopened the same class twice: tests
that pin a SHAPE (one winner, two distinct actors, fields in some order) and not the PROPERTY
(the loser went through the primary-key branch; ANY truncation collides; the order is the
one received). PR2a ships with those three declared as limits. This is what PR2b must do to
turn them into proofs — or, for one of them, why it cannot without a migration.

Imperator decision #29 (2026-09-12) fixes the split: PR2a = adapter with declared limits;
PR2b = this spec plus the two test pairs PR2a's test file already names at its foot.

## 1. The interleaving is not controlled, so the PK branch is not proven

### What is true today (PR2a, head at the time of this file)

`PostgresDocumentStore.commit()` does, inside one transaction: `SELECT ... FOR UPDATE` on
`key_sha256` → if absent, INSERT → on `UniqueViolationError` with `constraint_name ==
garuda_documents_pkey`, raise `_LostRace(payload_checked=False)` → outside the transaction,
re-read the winner on a fresh connection and answer three ways (same payload `False`, other
payload `IdempotencyConflictError`, no row `RuntimeError`).

The two race tests (`test_two_concurrent_commits_same_key_exactly_one_wins`,
`test_lost_race_with_a_different_payload_is_a_conflict_not_a_lost_race`) put an
`asyncio.Barrier(2)` between an EXTERNAL probe ("is the key absent?") and the call to
`commit()`. That coordinates the probes. It does not coordinate the two INTERNAL lookups: A
can run its whole transaction between the barrier opening and B's `SELECT ... FOR UPDATE`,
and B then takes the ordinary replay branch. Sol reproduced that schedule against the
candidate with the whole `UniqueViolationError` handler deleted: both tests PASS, zero
primary-key violations. On M5's own scheduler (PG 17.10 and 15.19, measured 2026-09-12)
the same mutation kills both tests — the race DOES reach the PK here — but "it happened on
this machine" is an observation, not a guarantee. The tests pin the outcome; they do not
pin the branch.

### What PR2b must build

**R1 — a test-only seam between the lookup and the INSERT.** One of:

- (preferred) a constructor keyword on `PostgresDocumentStore`,
  `_after_lookup: Callable[[], Awaitable[None]] | None = None`, awaited exactly once per
  `commit()` between the `SELECT ... FOR UPDATE` and the INSERT, inside the transaction.
  Production wiring (PR3, `service_initializer.py`) never sets it; the default is `None` and
  the call site is `if self._after_lookup is not None: await self._after_lookup()`. The name
  is underscored because it is a seam, not a feature; the docstring says so.
- (alternative) two connections holding an explicit `pg_advisory_xact_lock` on a test-chosen
  key, released by the test at the moment it wants B to proceed. Heavier, no code change in
  the store, but it fixes the schedule only as far as the lock is held — acceptable if R1's
  preferred form is judged to leak a test concern into the store.

**R2 — the race tests coordinate the INTERNAL lookups through the seam.** Both coroutines
await a `Barrier(2)` INSIDE `_after_lookup`, i.e. after each has performed its own
`SELECT ... FOR UPDATE` and found nothing. Only then may either INSERT. Under that schedule
the loser's INSERT MUST hit `garuda_documents_pkey`; there is no other path.

**R3 — the tests assert the branch, not just the outcome.** Observable evidence that the
loser traversed the PK branch, one of:

- a second test-only seam `_on_lost_race: Callable[[_LostRace], None] | None`, invoked
  from the handler with the sentinel, which the test records; or
- asserting, with the handler DELETED (the guilt mutation), that the test goes RED with
  `UniqueViolationError` propagating — and stating in the test docstring that this is the
  mutation which must be red under R2's schedule, so a future scheduler change cannot
  silently turn it green.

Acceptance for R1–R3: the "handler deleted" mutation is red on PG 17 and PG 15 with the
seam-forced schedule; a mutation that makes `_after_lookup` a no-op must make the race test
itself FAIL TO SET UP (assert the seam fired twice), not pass vacuously.

## 2. "No row after a PK collision" needs a semantics, not a RuntimeError

Migration 304's `guard_garuda_document_mutation` rejects DELETE only while
`clock_timestamp() < OLD.retention_until` (the DELETE branch of the trigger). A row can
therefore legitimately be purged after its retention expires, and the key can be re-occupied
by a third caller. PR2a's re-read after a lost race can then find no row (winner purged) or
the wrong row (key re-taken). PR2a raises `RuntimeError` with a message that says UNHANDLED,
not impossible. Reaching it requires a single `commit()` call to straddle the retention
window — 30 days under the active policy — so it is not an ordinary outcome; but it has no
defined answer, and a raise is the honest placeholder, not the design.

**R4 — choose and implement one:**

- (a) a typed error, `WinnerVanished(idempotency_key)`, raised from the store and mapped
  by `service.py` to the contract's existing error envelope for a non-replayable key (W3C
  owns the contract; if no existing code fits, STOP and ask — do not add one); or
- (b) a bounded retry: re-run the whole `commit()` exactly once, so the caller becomes the
  new winner of a now-free key (or loses again to the re-occupier, which is then an ordinary
  lost race with a row to compare against). Second miss raises the typed error from (a).

Either way, **R5 — a test that produces the case deterministically**: a test policy with
`retention_interval = interval '1 second'` (and `idempotency_retention_interval` equal, to
satisfy 304's CHECK), R1's seam to hold the loser after its collision, a superuser DELETE of
the winner once `clock_timestamp()` has passed `retention_until`, then release. Assert the
chosen semantics, and assert the guilt: with the branch reverted to `RuntimeError`, red.

Also test the re-occupation variant: after the purge, a THIRD commit with a different
payload takes the key; the released loser must get `IdempotencyConflictError` under (b) or
`WinnerVanished` under (a) — never `False`, which would tell it the re-occupier's document is
its own.

## 3. Replay order: canonical, by declaration — received order needs a column

`garuda_document_review_fields` has no ordinal column; the store reads `ORDER BY field_path`
and PR2a restores `PassportReviewFieldName`'s declaration order. For every outcome
`confidence.py` builds today that IS the received order, because it iterates the enum. For a
`LowConfidenceOutcome` assembled in any other order the replay differs from the original.
PR2a's port docstring (`DocumentStorePort.get_existing`) now promises the CANONICAL order
explicitly, so no consumer can infer the stronger one.

**R6 — PR2b does NOT change this.** Preserving the received order means persisting an
ordinal, which is a new column on a table 304 already created in production, which is a
migration, which is a separate concern with its own PR and its own gate. If a consumer is
found that needs the received order, that is the trigger for that PR; until then the
canonical promise stands and PR2b keeps the `_in_canonical_order` cure as is.

## 4. Already-deferred pairs that PR2b carries (from PR2a's test-file foot)

- `test_low_privilege_role_can_insert_thanks_to_the_ownership_transfer` and
  `test_low_privilege_role_insert_fails_once_the_function_is_mis_owned_again` — the
  SECURITY DEFINER ownership-transfer pair on `bind_garuda_document_retention_policy`.
- `test_lost_race_on_a_ready_document_returns_the_committed_body_instead_of_raising` and
  `test_ordinary_sequential_replay_of_a_ready_document_still_raises` — needs
  `service.py::_reconcile_lost_race_ready_replay` to exist first.

## 5. Out of scope for PR2b, named so nobody infers it

No migration (R6 says why). No `service_initializer.py` wiring (PR3). No contract edit
(W3C). No change to the scoped-key hash, whose truncation property PR2a now proves for
every cut 1..31. The two ledger rows for §1 and §3 are parked in `ledger-rows-held.md`
beside this file until `PENDING-ARMS.md` stops racing; PR2b closes the §1 row and leaves the
§3 row open with owner "whoever needs received order".
