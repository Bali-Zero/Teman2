# SPEC v2 — `PostgresDocumentStore`: the properties, and the harness that proves them

> **Status: normative.** Supersedes
> `evidence/2026-09/agent-air-m5-backend-rag-voa-store-adapter-51505641/SPEC-PR2b-interleaving.md`,
> which is history and whose R1–R6 are not to be implemented. Written 2026-09-12 by a fresh
> author outside the contribution chain of GARUDA VOA lane W1W (did not build, review or
> refute PR2a). All line citations are against commit `aed342999e8d` for the lane files and
> `origin/main` for the migrations.

## 0. Purpose and status

PR2a («`PostgresDocumentStore` adapter») was SUSPENDED under Imperator decision #34
(`brief.yml:232-233`) after three refuter rounds reopened one class: **a test that pins a FORM
and calls it a PROPERTY**. The record of that class, in the builder's own words
(`brief.yml:236-240`): one truncation cut pinned, then a longer prefix, then every prefix and
no suffix; "no row" called impossible, then re-occupation, and it is neither; a DSN redacted in
the message and left in the exception chain; a limit declared beside a docstring saying the
opposite.

**What is NOT under revision.** The store's behaviour was never contested — Sol O3 raised no
behavioural finding on it, only on prose and on tests (`brief.yml:252`). 50 integration tests
pass on PostgreSQL 17.10 and 15.19; 14 guilt mutations are red on both
(`brief.yml:106-120`, `brief.yml:285-297`). This spec therefore keeps the store's shape and
changes four things:

1. a test-only seam in `commit()` so the collision branch is FORCED under any scheduler (§4);
2. the loser's post-collision state machine, made total and typed (§2);
3. the test suite re-derived from mutation models instead of fixture pairs (§3, §6);
4. every declared limit consolidated into one place (§10).

PR2a-v2 is one PR. It does not wire production (PR3), adds no migration, and touches no
contract.

## 1. `DocumentStorePort` as properties

Each property: the promise, why it matters, the exact observable, the guilt mutation that must
turn it red. Port: `ports.py:39-79`. Every mutation must be red on **both** PG15 and PG17 (§8).

**P1 — Actor scoping is injective, not decorative.** Two actors submitting the same literal
`idempotency_key` hold two distinct bindings. Matters because that key is client-chosen with no
cross-actor uniqueness (`ports.py:31-36`) and the table has a single `key_sha256` PRIMARY KEY
(`304_garuda_documents.sql:68`). _Observable:_ both commits return `True`; row count 2; each
actor's `get_existing` returns its own outcome and the other's returns `None`, not a conflict.
_Guilt:_ `actor_id` replaced by `""` in `_scoped_key_sha256` (`postgres_store.py:114-143`).

**P2 — The storage key is injective on the whole 4-tuple.** §3 is the full statement; P1 is its
special case. _Guilt:_ any member of §3's mutation model.

**P3 — An exact replay returns the committed outcome and creates nothing.** _Observable:_
`get_existing` returns an equal outcome; a second `commit` with identical key and payload
returns `False`; both row counts unchanged. _Guilt:_ the `SELECT ... FOR UPDATE` branch
(`postgres_store.py:296-311`) removed.

**P4 — A different payload under the same (actor, key) is a conflict on BOTH entry points.**
`IdempotencyConflictError` from `get_existing` (`postgres_store.py:250-251`) and from `commit`
(`:306-307`, `:416-417`). Matters because `service.py:92` and `service.py:105` call them on
different paths and must not disagree. _Observable:_ `pytest.raises` on each, row count
unchanged. _Guilt:_ either hash comparison replaced by `True`.

**P5 — At most one `True` per key, ever.** `True` is the permission to fire the at-most-once
work-item hook (`service.py:109-118`). _Observable:_ under §4's forced schedule, exactly one
`True` over N concurrent commits and exactly one row. _Guilt:_ unconditional `return True`
(`postgres_store.py:419`).

**P6 — `commit` is TOTAL over its failure modes: no raw `asyncpg` exception escapes.** The
contract is `bool` plus named exceptions; a `UniqueViolationError` reaching the caller crashes
`service.py:106`'s `assert winning_outcome is not None`. _Observable:_ §2's four-row table, each
row asserted under a forced schedule. _Guilt:_ the handler deleted
(`postgres_store.py:349-362`). Under §4's seam this is red under ANY scheduler — the point of
§4, and the reason PR2a's version of this mutation carried a "red on M5's scheduler" caveat
(`brief.yml:115`).

**P7 — A loser is told it lost a race only when the payload was actually compared.** On the
`SELECT ... FOR UPDATE` path it was; on the INSERT-collision path it was not, because there was
no row when we looked (`postgres_store.py:282-288`). _Observable:_ schedule B's loser, carrying
a different payload, gets `IdempotencyConflictError`, not `False`. _Guilt:_
`_LostRace(payload_checked=True)` on the INSERT path.

**P8 — The two unique constraints are not interchangeable.** `garuda_documents_pkey` means
"someone won your key"; `garuda_documents_document_id_key` (`304_garuda_documents.sql:71`) means
the minted id exists under ANOTHER key — nobody won this one, and `False` would send
`service.py:106` to its assert. _Observable:_ a commit whose `document_id` duplicates an
existing row's, under a fresh key, propagates `UniqueViolationError`. _Guilt:_ the
`exc.constraint_name != _PK_KEY_SHA256` discrimination removed (`postgres_store.py:360-361`).

**P9 — Fail-closed on retention, against ONE instant.** No row without exactly one active
`GARUDA_DOCUMENT` policy, and the Python guard names the instant the binder uses —
`transaction_timestamp()` (`postgres_store.py:330-333` against `304_garuda_documents.sql:123`),
never `datetime.now(UTC)`. _Observable:_ `commit` under an environment with no policy raises
`PersistencePolicyUnavailable` and persists nothing. _Guilt:_ the check deleted — but note the
asymmetry the builder measured (`brief.yml:322-326`): that mutation goes red via the DATABASE
trigger's `asyncpg.RaiseError`, so the test must assert the ERROR TYPE, otherwise removing the
Python guard is merely differently-red.

**P10 — The PII boundary is an OUTPUT boundary, and the gap is announced, not fabricated.** No
field VALUE is persisted; a replayed `ReadyOutcome` raises `ReadyOutcomeValueNotPersisted`
carrying `document_id` and the structure — names and confirmation flags only (`ports.py:86-116`,
`postgres_store.py:207-218`). _Observable:_ the exception's `document_id` and full
`persisted_fields` tuple equal what was committed. The TYPE alone is not the property:
`ReadyOutcomeValueNotPersisted("0"*32, ())` satisfies `pytest.raises` and is useless (Sol O1
finding 9, `brief.yml:170-171`). _Guilt:_ `_rehydrate` fabricating a valueless `ReadyOutcome`;
and, separately, `persisted_fields` replaced by `()`.

**P11 — Replay order is the CANONICAL order, for every received order.** See §6.

## 2. The loser's state machine after a `UniqueViolation`

After `garuda_documents_pkey` fires, the loser's transaction is dead and cannot read anything.
It re-reads on a fresh pool connection (`postgres_store.py:400-408`). Four outcomes, and the
port's answer for each:

| #   | Observed at re-read                                               | What it means                           | Port result                                             |
| --- | ----------------------------------------------------------------- | --------------------------------------- | ------------------------------------------------------- |
| 1   | row present, same `canonical_payload_sha256`                      | the key is bound to OUR payload         | `return False`                                          |
| 2   | row present, different hash                                       | the key is bound to a DIFFERENT payload | `IdempotencyConflictError`                              |
| 3   | no row                                                            | the key is bound to nothing             | `IdempotencyKeyVanished` (new, typed)                   |
| 4   | row present, but a DIFFERENT generation than the row that beat us | winner purged and key re-occupied       | **not observable by the loser — collapses into 1 or 2** |

**Row 4 is where `WinnerVanished` dies, and it is dropped deliberately.** The loser never saw
the winner's row: the collision is its first and only knowledge that one existed. There is no
instant at which it could capture a generation "before the purge", so no row-version,
`inserted_at` or `document_id` tuple is available to it. Sol O3 finding 7
(`brief.yml:248`) is therefore resolved by REMOVING the requirement, not by satisfying it.

**The observable that replaces it.** The port promises a function of _the row that holds the
key at re-read time_, not of the row that beat us. Whether that row belongs to the original
winner or to a third caller who re-occupied the key after a legitimate purge is immaterial:
in case 1 the caller's subsequent `get_existing` (`service.py:105`) reads that same row and it
agrees with the caller's payload; in case 2 the caller is told the truth. Row 4 is not a fifth
answer, it is 1 or 2 with an irrelevant provenance. **The spec states this as the contract**, so
that no future test tries to assert an identity the store cannot see.

**Case 3 is real and is not corruption.** `guard_garuda_document_mutation`
(`304_garuda_documents.sql:241-259`) rejects DELETE only while
`clock_timestamp() < OLD.retention_until` (`:248`), so a row legitimately leaves after its
retention expires. `RuntimeError` (`postgres_store.py:409-415`) is replaced by a typed
`IdempotencyKeyVanished(idempotency_key)` on `ports.py`, beside the other two port exceptions
and for the same reason (`ports.py:93-96`): a storage-agnostic caller must catch it without
importing a concrete store.

**No retry.** The old spec's R4(b) bounded retry is rejected: re-running `commit()` re-enters
a loop an adversarial re-occupier controls, and reaching case 3 at all requires a single
`commit()` call to straddle the retention window — 30 days under the active policy. One typed
error, raised once, is the whole semantics. What `service.py` does with it is PR3's concern
and is named in §9.

## 3. Storage-key injectivity, and how the test is DERIVED

**The property (P2).** The map
`(actor_id, operation, environment, idempotency_key) -> key_sha256` is INJECTIVE over the whole
4-tuple, up to a sha256 collision. Not "safe against truncation", not "prefix-preserving":
injective. Any distinct tuple yields a distinct digest.

**The encoding that provides it.** Each UTF-8 component is preceded by its own big-endian
uint32 byte length (`postgres_store.py:138-143`), so no component's content can be reread as a
length prefix or as another component's boundary.

**Why the PR2a tests were not this property.** They pinned witnesses. O1 pinned one cut; O2's
cure pinned a 16-character shared prefix and `actor_id[:17]` walked past it; O3's cure
parametrized every cut 1..31 (`test_postgres_store.py:665-666`) and every SUFFIX `actor_id[n:]`
walked past THAT, because the fixture pair differs in its last character — as does
`actor_id[1::2]` (Sol O3 finding 1, `brief.yml:242`). Each round chose a witness pair first and
described a property afterwards.

**The derivation rule, which is the actual fix.** The test never hand-picks a pair. It declares
a **mutation model** — a set of lossy encoders — and for each encoder COMPUTES a witness pair
that the encoder collapses, then asserts the real key distinguishes it. Parametrization is over
the MODEL, not over a range of one integer.

```
E = { prefix_n      : s -> s[:n]          for n in 1..L-1
      suffix_n      : s -> s[n:]          for n in 1..L-1
      stride_k_o    : s -> s[o::k]        for k in 2..4, o in 0..k-1
      drop_i        : s -> s[:i] + s[i+1:] for i in 0..L-1
      swap_case     : s -> s.swapcase()
      strip_sep     : s -> s.replace(sep, "") for sep in the separator set
      join_sep      : tuple -> sep.join(tuple)  for sep in the separator set }
```

For each `e in E`, the test builds `(t1, t2)` with `t1 != t2` and `e(t1) == e(t2)` — by
construction, e.g. for `suffix_n` two ids differing only inside `[0:n]`, for `drop_i` the pair
`"...a a b..."` / `"...a b b..."` around index `i`, for `join_sep` two tuples whose components
carry the separator and render identically. It then asserts
`_scoped_key_sha256(*t1) != _scoped_key_sha256(*t2)`. A witness the model fails to construct is
a test ERROR, not a skip: an encoder with no collision pair is a bug in the model.

**Cross-component coverage is part of the model.** `swap_components` moves a byte across the
actor/operation and operation/environment boundaries — the case
`test_postgres_store.py:603` already exercises by hand, now generated.

**One legitimate FORM pin, labelled as such.** `key_sha256` is a persisted PRIMARY KEY: changing
the encoding orphans every production row. The suite therefore also carries ONE golden vector
(a fixed tuple and its expected hex digest) marked explicitly as a
**backward-compatibility pin, not a property**. That label is the difference between this pin
and the defect this spec exists to close.

_Guilt mutations for §3:_ each encoder in `E` substituted into `_scoped_key_sha256` must turn
its own parametrized case red. The suite asserts the count of model cases is non-zero, so an
empty model fails to set up.

## 4. Test harness: the disposable database, the seam, and the forced schedules

**4.1 Disposable database per test.** Unchanged in principle from
`test_postgres_store.py:200-296`: a uuid-suffixed database and two uuid-suffixed cluster roles,
migration 304's real forward SQL with `visa_ledger_owner` substituted
(`test_postgres_store.py:184-198`), everything dropped in teardown, `nuzantara_dev` and
`nuzantara_test` never touched. The redaction defect in it is §5.

**4.2 The seam.** `PostgresDocumentStore.__init__` gains one keyword-only, underscore-named
parameter:

```python
def __init__(self, pool, *, environment: str, _hooks: "_CommitHooks | None" = None) -> None
```

`_CommitHooks` is a frozen dataclass with two optional awaitables, both defaulting to `None`:

| hook                            | signature             | call site                                                                                                                                   | fires                       |
| ------------------------------- | --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------- |
| `after_lookup`                  | `async (ctx) -> None` | inside the transaction, after the `SELECT ... FOR UPDATE` (`postgres_store.py:296-304`) and before the policy check (`:330`)                | exactly once per `commit()` |
| `after_collision_before_reread` | `async (ctx) -> None` | after `_LostRace(payload_checked=False)` unwinds the transaction (`postgres_store.py:375`) and BEFORE the fresh-connection re-read (`:400`) | once per INSERT collision   |

`ctx` carries the key digest and a monotonic call counter. It never carries a payload, an
outcome or an actor id. The second hook is the control point Sol O3 finding 6
(`brief.yml:247`) showed the superseded spec lacked: `after_lookup` fires before the INSERT and
cannot hold a loser after its collision.

**Production guard.** `_hooks` is keyword-only, underscore-named, defaults to `None`, and the
class docstring states it is a test seam that production must never set. PR2a-v2 ships
`test_the_default_constructor_has_no_hooks`, asserting `store._hooks is None` for a store built
the way a production factory builds one. **Carried obligation:** PR3, which writes
`service_initializer.py`, adds the assertion at the factory itself and names it in its own
brief. Recorded here so it is inherited rather than forgotten.

**4.3 Schedule A — exactly one winner, and the loser DID traverse the PK branch.**
Two stores, `store_a` and `store_b`, on the same pool, both built with hooks whose
`after_lookup` awaits a shared `asyncio.Barrier(2)`. Both call `commit()` concurrently on the
same absent key.

1. Each performs its own `SELECT ... FOR UPDATE`. The key is absent, so **no row is locked**.
2. Each blocks in `after_lookup`. The barrier releases only when BOTH have observed absence
   inside their own transaction.
3. Whichever INSERTs first commits. The other INSERTs on the same primary key: it either
   collides immediately or BLOCKS on the uncommitted row and collides when the winner commits.

**Why this is forced under ANY scheduler, which the `asyncio.Barrier` around the external
probes at `test_postgres_store.py:479` was not:** after the barrier, neither transaction can
have committed, because neither had left its lookup when the barrier closed. So neither can
take the replay branch — that branch requires seeing a row that cannot yet exist. The collision
is structural, not scheduling luck.

_Assertions:_ exactly one `True` and one `False`; exactly one row; `after_lookup` counter == 2;
**`after_collision_before_reread` counter == 1** — that last is the branch assertion, the thing
the PR2a tests could not make (`brief.yml:298-305`).
_Setup guard:_ if either counter is off, the test FAILS with a setup message. A no-op seam makes
the test fail to set up rather than pass vacuously.
_Guilt:_ the `UniqueViolationError` handler deleted → red on PG15 and PG17, no caveat.

**4.4 Schedule B — the loser carries a different payload.** Schedule A with `store_b`'s
`payload_hash` differing. The loser's re-read finds row-with-different-hash: outcome 2.
_Assertions:_ `IdempotencyConflictError`, collision counter == 1, one row, the winner's payload
is the one persisted.
_Guilt:_ `payload_checked=True` on the INSERT path (P7) → red.

**4.5 Schedule C — the key vanished (outcome 3).** A short-retention policy: the test policy row
is inserted with `retention_interval = INTERVAL '2 seconds'` and
`idempotency_retention_interval = INTERVAL '2 seconds'`, which satisfies migration 264's
`idempotency_retention_interval <= retention_interval`
(`264_visa_decision_retention_policy.sql:44-45`) and 304's binder, which refuses a deadline
already elapsed at INSERT time. Then: run schedule A; hold the loser inside
`after_collision_before_reread`; from a SUPERUSER connection outside the store's pool, wait
until `clock_timestamp() > retention_until`, `DELETE` the winner's row — permitted by
`304_garuda_documents.sql:248` — and assert the delete affected exactly 1 row before releasing
the hook.
_Assertion:_ `IdempotencyKeyVanished`. Asserting the delete's row count first means a timing
flake becomes a loud failure with a diagnosis, never a silent pass.
_Guilt:_ the typed error reverted to `RuntimeError` → red.

**4.6 Schedule D — re-occupation (outcome 4 collapsing into 1 and 2).** Schedule C, but after
the DELETE a THIRD commit takes the now-free key. Two cases, both asserted: same payload as the
held loser → `False`; different payload → `IdempotencyConflictError`. Never the reverse, and
never `IdempotencyKeyVanished`. This is the test that pins §2's ruling that provenance is not
observable and not promised.

**4.7 Pool sizing, which schedule A can deadlock without.** The re-read at
`postgres_store.py:400` acquires a DIFFERENT pool connection from the dead transaction's, and
at the moment it runs, two commits are holding connections. The PR2a pool is
`max_size=4` (`test_postgres_store.py:298-303`). Race fixtures must build a pool with
`min_size=4, max_size=8` and the race tests must assert the pool has spare capacity before
starting, so an exhausted pool fails as a setup error rather than hanging. The superuser
connection used by schedules C and D is opened outside the store's pool, as it needs a
different role anyway.

## 5. Report-level redaction — a property of the REPORT, not of a message

**H1.** No secret carried by any DSN this suite builds appears ANYWHERE in pytest's output —
at any `--tb` level, in a chained `__context__`/`__cause__`, in a rendered frame, or in the
JUnit XML.

**Why the PR2a form is not that property.** `_redacted` (`test_postgres_store.py:88-100`)
redacts the MESSAGE. `pytest.fail`/`pytest.skip` raised inside an `except`
(`test_postgres_store.py:222-247`) keep the original as `__context__`, and `--tb=long` renders
the chain including the `asyncpg.connect(_ADMIN_URL)` frame. The per-database connects at
`test_postgres_store.py:256` and `:284` are outside the redaction entirely (Sol O3 finding 3,
`brief.yml:244`).

**What the code must do.** (a) Every connect in the module goes through one helper that catches
`BaseException`, and raises the redacted failure **`from None`**, severing the chain — this is
the load-bearing change, because `from None` is what stops a `--tb=long` renderer from printing
the original. (b) `pytest.fail(..., pytrace=False)` on every fixture failure path. (c) The
helper takes no DSN argument, so no rendered frame carries one.

**The observable, and it is a subprocess.** A test writes a minimal standalone test module to a
tmp dir, then runs `pytest --tb=long --junit-xml=<tmp>.xml` on it in a SUBPROCESS with
`CI=1` and `GARUDA_DOCUMENTS_TEST_DSN=postgresql://sentinel_user:SENTINEL_PW_<uuid4>@127.0.0.1:1/nope`.
It asserts: the sentinel password substring is absent from stdout, stderr AND the JUnit XML;
the subprocess exit code is non-zero; and the redaction marker `***` IS present. The last two
assertions exist so a subprocess that merely failed to collect cannot pass vacuously.
_Guilt:_ drop `from None` → sentinel appears → red. Return the DSN unchanged from `_redacted` →
red. Move a connect outside the helper → red.

**This harness also closes an untestable branch.** The same subprocess runner, pointed at an
unreachable DSN with `CI=1`, asserts exit != 0 and the "must not be skipped" text — which gives
a behavioural test to the CI-fails-instead-of-skips branch the builder declared untestable
(`brief.yml:173-185`, cures O1-6 and O2-5). PR2a-v2 must close that declaration.

## 6. Field order and rehydration

**P11.** For ANY order in which a `LowConfidenceOutcome`'s `uncertain_fields` were received,
`get_existing` returns them in `PassportReviewFieldName`'s declaration order.
`ORDER BY field_path` (`postgres_store.py:252-259`) is deterministic but alphabetical;
`_in_canonical_order` (`postgres_store.py:178-184`) restores the canonical one; the port
promises exactly and only that (`ports.py:48-57`).
_Observable:_ parametrize over `itertools.permutations` of the enum, commit each permutation
under its own key, assert every replay returns the SAME canonical tuple. That is the property;
one fixture order was the form.
_Guilt:_ `_in_canonical_order` dropped, SQL order kept.
Same treatment for the `ReadyOutcomeValueNotPersisted.persisted_fields` tuple (P10).

**Received order stays impossible, and that is a migration.** Preserving it means persisting an
ordinal, which is a new column on a table migration 304 already created in production — a
separate concern, a separate PR, a separate gate. Nothing in PR2a-v2 changes it. The parked
ledger row (`ledger-rows-held.md:18`) stays open with owner `operator[product]`.

## 7. Policy window and migration 304's retention, split by who guarantees what

**The store may assume nothing about wall-clock time.** It asks the database for its own
`transaction_timestamp()` (`postgres_store.py:330-333`), the same instant the binder compares
`NEW.created_at` against (`304_garuda_documents.sql:123`). One instant, two readers.

**Only the DB guarantees the invariant.** `bind_garuda_document_retention_policy`
(`304_garuda_documents.sql:113-166`) resolves the single active policy `FOR SHARE`, raises on
zero or many, rejects a non-`CREATED_AT` anchor and an already-elapsed deadline, and ASSIGNS
`retention_policy_id` and `retention_until`. The store writes neither column and reads neither.
The Python guard is defence in depth: a store that forgot it still cannot write an unprotected
row (`brief.yml:322-326`).

**Rows are immutable, DELETE is conditional.** `guard_garuda_document_mutation`
(`304_garuda_documents.sql:241-259`) raises on every UPDATE, and on DELETE only while
`clock_timestamp() < OLD.retention_until` (`:248`). Expiry-then-purge is legal, which is what
makes §2's outcome 3 reachable and §4.5 constructible.

**Correction of record.** The CHECK `idempotency_retention_interval <= retention_interval`
belongs to **migration 264** (`264_visa_decision_retention_policy.sql:44-45`), not to 304, and
it is `<=`, not equality. The superseded spec said otherwise (Sol O3 finding 8,
`brief.yml:249`). Any test policy sets both intervals respecting `<=`.

## 8. CI matrix

CI gives the backend shards a PostgreSQL **15** service container and exports
`INTAKE_TEST_DSN`, the suite's second fallback (`test_postgres_store.py:66-71`,
`brief.yml:272-284`); production is PG17. Migration 304's privilege bracket is exactly where
the two diverge (`SET` on >= 16 vs `MEMBER` on 15), so one version is not evidence for the
other. Requirements:

1. The suite is version-agnostic and must pass on PG15 and PG17.
2. Under `CI`, all three degraded cases FAIL and never skip: unreachable server, connecting
   role not a superuser, DSN rejected by asyncpg's parser before any socket. Now behaviourally
   tested via §5's subprocess runner.
3. Every guilt mutation in the brief is measured on BOTH versions, with the exact
   `server_version` string recorded — not "PG15" and "PG17" as labels.
4. PG17 coverage in CI is a workflow change and therefore a different PR (§9). Until it lands,
   PG17 is a measured local run recorded in `brief.yml` with its `server_version`, and the brief
   says plainly that CI proves PG15 only.

## 9. Out of scope, deferred, and what would need a migration

**Of the four tests deferred at `test_postgres_store.py:699-708`, PR2a-v2 absorbs NONE.**
(The brief says that block sits "at the foot" of the file; it is at line 699 of 851 — minor,
corrected here.)

- `test_low_privilege_role_can_insert_thanks_to_the_ownership_transfer` and
  `test_low_privilege_role_insert_fails_once_the_function_is_mis_owned_again` — these test the
  MIGRATION's `SECURITY DEFINER` ownership transfer (`304_garuda_documents.sql:169-217`), not
  the adapter. They move to a migration-test PR, unchanged in name.
- `test_lost_race_on_a_ready_document_returns_the_committed_body_instead_of_raising` and
  `test_ordinary_sequential_replay_of_a_ready_document_still_raises` — these need
  `service.py::_reconcile_lost_race_ready_replay`, which does not exist and is not in this PR's
  one concern. Deferred, and **renamed** to §2's vocabulary:
  `test_ready_replay_after_outcome_1_returns_the_committed_body` and
  `test_sequential_ready_replay_still_raises_value_not_persisted`.

Also out of scope: production wiring (PR3, `service_initializer.py`); any contract edit (W3C
owns it); a PG17 CI shard; and the ordinal column for received field order (§6) — the only item
in this lane that would need a migration.

`service.py`'s mapping of the new `IdempotencyKeyVanished` to an HTTP envelope is PR3's. Until
then it propagates, exactly as `ReadyOutcomeValueNotPersisted` does today.

## 10. Acceptance checklist for PR2a-v2

- [ ] **One concern:** the adapter's properties and the harness that proves them. Store changes
      are the two hooks, the typed error and its export — roughly 50 net lines. The test file is
      a rewrite; measure the floor with `evidence_pack_lint.py --print-floor` rather than
      guessing it, and record the VERDICT, not a self-referential total (`brief.yml:11-21`).
      Expect gear 2 again; do not raise above the measured floor.
- [ ] Every property P1–P11 plus H1 has a named test AND a named guilt mutation, each measured
      red on PG15 and PG17, in `brief.yml: guilt_mutations`.
- [ ] Schedule A's collision counter assertion is present; the "handler deleted" mutation is red
      with NO scheduler caveat. If a caveat is still needed, the seam is wrong — stop.
- [ ] §3's mutation model is enumerated in code and its case count asserted non-zero.
- [ ] **Limits live in ONE place:** a `limits:` block in `brief.yml` with ids `L1..Ln`. Every
      docstring that mentions a limit CITES its id and states nothing stronger or weaker. No
      docstring contradicts its neighbour (Sol O3 finding 4). Tests assert what they prove and
      say what they do not.
- [ ] The three parked ledger rows (`ledger-rows-held.md:17-19`): row 1 (race branch) CLOSES
      with this PR; rows 2 and 3 stay parked, verbatim, with their owners.
- [ ] Refuter: `codex exec --sandbox read-only --skip-git-repo-check -m gpt-5.6-sol -c
model_reasoning_effort=xhigh`. The `-m` is explicit and the `model:` header is read FROM
      THE LOG after the run and recorded with `model_id_source` — never copied from the mandate
      (`brief.yml:121-132`).
- [ ] PR body carries, literally:
      `Bites: backend test shard in .github/workflows/tests.yml — test_postgres_store.py runs against the PG15 service container via INTAKE_TEST_DSN and the collision-counter assertion in schedule A is green in that job's log.`
- [ ] Push, create and merge are three separate commands. Auto-merge armed at PR-open; the
      branch is frozen afterwards.

## 11. Open questions

None requiring Zero. Two decisions are taken here by this spec rather than escalated, and are
flagged as assumptions of record: **(i)** `WinnerVanished` is dropped as unimplementable and
replaced by `IdempotencyKeyVanished` with no retry (§2); **(ii)** PG17 stays out of CI in this
PR and is carried as a measured local run plus a named follow-up PR (§8). Either can be
overturned by ruling without invalidating the rest of this document.
