# R2 — ENGINE · build spec (the artifact BUILD consumes)

> Authored by the R2 Dux (BLUE, Opus 5 `xhigh`, Gear 3) on 2026-09-11 from
> `research/operations/2026-09-10-fable-max-sessions/R-research-os.md` @ origin/main blob
> `692b70de1e703d8b460f5157dd7969b4e5848717`, read from disk, never from memory.
> Worktree `.worktrees/backend-rag-r2-research-os-naga-engine`, branch
> `agent/nuzantara/backend-rag/r2-research-os-naga-engine`, base
> `ea50eb262f9ed96ce070cb407b55202002b0dae8` (== `origin/main` when measured).
>
> **The implementer builds against THIS FILE, not against the chat.** Every line below that
> says MUST is an acceptance condition; every line that says FORBIDDEN fails the gate.

---

## 0. What is already decided, and may not be re-litigated

| #   | Decision                                                                                                                                                                                    | Source, read on disk               |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------- |
| D2  | Valid-time ordering is repaired **in storage**. The wire form, `_UTC_OFFSET_PATTERN`, the 218 fixtures and Consul's hashes stay **byte-identical**.                                         | spec §0 D2                         |
| D3  | Correction = successor + edge in ONE transaction. Scheduled succession is a SEPARATE family under a shared `subject_key`. Reader returns at most one answer, else abstention or quarantine. | spec §0 D3, `CONTRACTS.md:140-142` |
| D4  | Admission is a DECISION, not a mapping. Zero admissions is a valid outcome.                                                                                                                 | spec §0 D4                         |
| D5  | One store: `research_os_objects`. Plus ONE projection table `research_os_naga_admission`. Hash verified by the API **before** INSERT, never in SQL.                                         | spec §0 D5, migration `279:54`     |
| D10 | Backfill runs from the **Pro checkout through the Fly proxy**, never from the Fly image.                                                                                                    | spec §0 D10                        |

**The "width on the wire" option is FORBIDDEN.** It breaks 76 of 79 accepted fixtures and the
repository's own compatibility checker calls it `compatible: false, major`. Anyone who proposes
it has not read §0.

---

## 1. The sibling contract — R1 is the input, and it is NOT yet merged

R1 (`agent/nuzantara/backend-rag/r1-research-os-design`) is **alive and unmerged** at the time of
writing. Measured, not assumed: `gh pr list --head <r1-branch> --state all` → `[]`,
`git ls-remote origin '*r1-research-os*'` → empty.

- BUILD proceeds **in parallel**, on fixtures of our own under
  `apps/backend-rag/backend/tests/services/research_os/naga/fixtures/`.
- We **do not push, open, arm or release** until R1 is merged AND integrated here by a
  **per-file blob check against `origin/main`** — not by ancestry (`git rev-parse origin/main:<path>`
  vs our own blob, file by file).
- On integration: switch to R1's canonical fixtures, **re-run the full acceptance and the
  adversarial round on the integrated tree**, then release the frozen candidate.
- **FORBIDDEN:** an `xfail` bridge, a post-arm rebase, a queue-position promise.

### 1.1 What R1 hands us, and which parts are contract

From R1's committed HEAD (`research_os_reader_reference.py`, `research_os_admission_reference.py`):

**The instant grammar — this is the one we must agree with byte for byte.**

```python
_INSTANT_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})[Tt](?P<clock>\d{2}:\d{2}:\d{2})"
    r"(?P<fraction>\.\d+)?(?P<zone>Z|z|\+00:00)$"
)
fraction     = (match.group("fraction") or ".0")[1:]
microseconds = int((fraction + "000000")[:6])
key          = moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond:06d}Z"
```

Note `z` lowercase is admitted too — the mandate text names only `t`, the code admits both.
Build against the CODE.

**The admission reason vocabulary is ORDERED and the order is contract.** A record with two
defects reports the FIRST. We may ADD reasons; we may NOT rename these:

```
statement_not_from_source, content_hash_is_url, source_version_missing,
exact_span_missing, intel_event_identity_missing, rights_missing,
retention_missing, classification_missing, review_state_missing
```

**Two R1 blockers found by its own Codex round bind us directly** and must be honoured here
even if R1's cure lands differently:

1. `family_id` on the edge and on the claims must be the SAME spelling. R1 shipped
   `naga.claim_family.bdd…` on the edge and bare `bdd…` on the claims, and the reader silently
   ignored the real edge while tests stayed green over privately-manufactured edges. Our
   persistence API MUST reject an edge whose `family_id` does not equal both members'
   (`graph.py` already calls this `family_identity_mismatch`).
2. **Integrity runs BEFORE any temporal filter.** A structurally invalid family whose duplicate
   terminal members sit in the future must return **Quarantine**, never Abstain. The ORDER IS
   THE SPECIFICATION.

---

## 2. Deliverable 1 — migration `310_research_os_naga_claims.sql`

Number measured `max+1` in `apps/backend-rag/backend/db/migrations_v2/` (309 is head;
**re-measure at integration**, the sequence is not dense and other lanes are landing migrations).

### 2.1 `research_os_instant_key(text) RETURNS text`

```
IMMUTABLE, STRICT, LANGUAGE sql (or plpgsql), SET search_path = pg_catalog, pg_temp
```

- **Pure regexp/substring. No cast.** `text::timestamptz` routes through `timestamptz_in`, which
  PostgreSQL marks **STABLE** (it reads `DateStyle`/`TimeZone` GUCs). Declaring a STABLE cast
  IMMUTABLE is on the mandate's FORBIDDEN list and is how this lane failed in 2026-08.
- Grammar, mirroring §1.1 exactly: separator `T` or `t`; terminator `Z`, `z` or `+00:00`;
  fraction optional, any width.
- Output: `YYYY-MM-DDTHH:MM:SS.ffffffZ` — **exactly 27 bytes**, fraction right-padded with zeros
  when shorter, **truncated** when longer. Declared precision policy: _the key is exact to the
  microsecond; sub-microsecond differences are not orderable by it._
- **Non-matching input returns NULL**, it does not raise. Rationale, and this is a decision not an
  accident: the function is an INDEX expression over a table other writers already populate
  (`consul_executor.py` emits optional fractions). A raising index expression would turn a
  malformed legacy row into a failed INSERT on an unrelated path. Strictness belongs to the
  WRITER (§3), which rejects before INSERT. A test MUST pin the NULL return for at least:
  empty string, a date without a zone, a `+07:00` offset, and a non-instant string.
- Comparison and indexing under **`COLLATE "C"`**.

### 2.2 Two expression indexes

```sql
CREATE INDEX research_os_objects_valid_from_key_idx ON public.research_os_objects
    ((research_os_instant_key(payload->'time'->>'valid_from')) COLLATE "C");
CREATE INDEX research_os_objects_valid_to_key_idx   ON public.research_os_objects
    ((research_os_instant_key(payload->'time'->>'valid_to'))   COLLATE "C");
```

`Claim.time` is a `ClaimTime` (`valid_from: UtcDateTime | None`, `valid_to: UtcDateTime | None`,
`recorded_at: UtcDateTime`) — verified in `models/claim.py`, so `payload->'time'` is the right
path. **No `CREATE INDEX CONCURRENTLY`** (migration 279's header says it cannot run inside the
transaction the runner uses).

### 2.3 Projection table `research_os_naga_admission`

Columns: legacy claim id, family id, canonical claim/evidence ids and hashes, source snapshot
hash, decision, reason, run id, `recorded_at`.

- Its own **append-only guard**, built the way `280` did it: **reuse 279's
  `public.reject_research_os_objects_mutation()` verbatim** — no `ALTER FUNCTION`, no second
  `CREATE FUNCTION`, no `CREATE OR REPLACE FUNCTION`. (280 is the precedent; read it before
  writing this.)
- A `-- === ROLLBACK ===` section, per this repo's migration-runner convention.
- **The 279/280 triggers are NOT touched.** Any diff against them fails the gate.

### 2.4 Migration acceptance

- Applies and rolls back cleanly against a throwaway `postgres:15` in CI, and **re-applies** from
  clean a second time.
- `pg_proc.provolatile = 'i'` for `research_os_instant_key`, asserted by query, not by reading SQL.
- Both indexes exist, asserted by `pg_indexes`.
- Test file: `apps/backend-rag/backend/tests/migrations/test_migration_310_research_os_naga_claims.py`.

---

## 3. Deliverable 2 — `services/research_os/naga_persistence.py`

Import the core through `_core_path` (the existing bridge; `packages/research-os-core` is NOT a
declared dependency of `apps/backend-rag` and this slice does NOT change packaging).

**Every rule below rejects BEFORE the INSERT, with a zero-write test asserting the table is
untouched after the rejection.**

1. **Hash check in Python, never in SQL.** Recompute `object_hash(payload)` via
   `research_os.hashing` (RFC 8785 JCS, omission set `{object_hash} | TRANSPORT_METADATA_FIELDS`)
   and refuse when it differs from the payload's own `object_hash`. Migration `279:54` refuses a
   database re-implementation of RFC 8785; `sha256(payload::text)` is FORBIDDEN.
2. **Successor + edge in ONE transaction.** A crash between them leaves NEITHER. Test by
   injecting a failure between the two statements and asserting both absent.
3. **A second successor for the same predecessor is REJECTED** — fork goes to quarantine, never
   "a winner" (`CONTRACTS.md:140`).
4. **Classification-lowering successors are REJECTED.** `RiskClass` is ordered
   `green < amber < red`; `Sensitivity` is ordered
   `public < internal < confidential < restricted_osint < client_pii` (declaration order in
   `enums.py`, which is the only ordering the contract gives). A successor whose `risk_class` OR
   `sensitivity` is lower than its predecessor's requires its receipts in the same transaction
   (`CONTRACTS.md:142`) — and those receipt kinds are **not in Z2b**. So: reject, zero rows.
5. **Instant strictness on the write path:** more than six fractional digits, or a lowercase
   separator, is REJECTED. (The READER folds them; the WRITER refuses them. This asymmetry is
   D2's, deliberate, and must be stated in the module docstring so the next reader does not
   "fix" it.)
6. **`family_id` identity:** edge `family_id` MUST equal both members'. See §1.1 blocker 1.
7. **Replay of the same manifest writes 0 rows** and the predecessor row is **byte-identical
   before and after**, `object_hash` unchanged (RULING B1: `superseded` is derived at read from
   the edge, never stored on the object).
8. **Consul's tests still pass.** `tests/unit/services/autonomous_lab/**` and
   `tests/integration/test_dual_consul_postgres.py`. Run them with the **repo root on
   `PYTHONPATH`** — R1 measured that a core-only `PYTHONPATH` makes `test_consul_native_broker`
   die on `ModuleNotFoundError: scripts.conductor`, which would manufacture a false
   stop-and-escalate. **Before escalating any red, re-run it with the invocation changed and
   nothing else.**

---

## 4. Deliverable 3 — `services/research_os/naga_bitemporal_reader.py`

`read(subject_key, valid_at, known_at) -> Answer | Abstain | Quarantine`.

Order of operations, and the order IS the specification:

1. Group the families under `subject_key` (R1's `subject_key_of`, a namespaced extension).
2. **Integrity first** — `hash_mismatch`, `family_identity_mismatch`,
   `successor_recorded_at_not_later`, `fork`, `cycle`, `non_unique_current_member`. Any of these
   → **Quarantine**, regardless of `known_at`. This is R1 blocker 2.
3. Then system-time: members with `recorded_at <= known_at`, successor edge absent or
   `successor.recorded_at > known_at`.
4. Then valid-time: `valid_from <= T < valid_to`, `null` end = open. **A finite `valid_to` is
   never extended by succession.** A `null` `valid_from` on a consequential claim is not
   admissible (`CONTRACTS.md:266`).
5. At most ONE admissible answer. Otherwise explicit **Abstain** (with R1's reason vocabulary) or
   **Quarantine**. **Never "exactly one per family".** A quarantined family is REPORTED, never
   filtered away to bypass the graph.

Every case in the mandate's temporal list is a test **executed on `postgres:15` in CI**: both
interval boundaries; zero and non-zero microseconds; unknown bounds; a correction recorded before
and after discovery; a scheduled change known in advance; an existing finite expiry; a no-answer
result; a quarantined fork. **No skip. No xfail.**

### 4.1 The cross-implementation parity test (this is the load-bearing one)

For every admitted spelling, the SQL `research_os_instant_key` and R1's Python
`instant_sort_key` MUST return the **identical string**, and byte order over the key MUST agree
with chronological order over the parsed instant. Drive it from a table of spellings that
includes `.1Z` vs `.100000Z`, `.1Z` vs `.11Z`, `Z` vs `+00:00`, `t` vs `T`, `z` vs `Z`, absent
fraction vs `.000000Z`, and a >6-digit fraction. **If the two disagree, one implementation is
wrong and the test names the pair that proves it.**

This closes ledger row 21: for two canonical instants inside one second,
`research_os_instant_key($1) < research_os_instant_key($2)` agrees with
`$1::timestamptz < $2::timestamptz`, and a half-open `valid_from <= T` predicate over the KEY
returns the row the raw-text predicate dropped.

---

## 5. Deliverable 4 — `services/research_os/naga_admission.py`

D4 rules over the legacy shape, producing `Admitted | Excluded(reason)` with R1's ordered
vocabulary. **Presence is not resolution, and resolution is not binding** — this is the family
R1's adversarial round found three times:

- A `document_version_id` that is merely non-empty is NOT "the version FOR this document".
- A `source_event_ref.event_id` that resolves to SOME valid IntelEvent is NOT provenance unless
  that event is bound to **this record's own document**.
- `statement.derived_from_span: true` is a caller's PROMISE, not a derivation — verify the span.
- A locator that is never resolved against the document is not an exact span.

Three counts are reported **separately** and MUST be able to differ on a mixed set:
documented mapping coverage / available source information / admissible records.

**Nothing is defaulted silently.** A missing classification is `classification_missing`, never a
silent `internal`.

---

## 6. Deliverable 5 — `services/research_os/naga_backfill.py`

- `--dry-run` is the **default**. `--apply` requires an explicit `--manifest <hash>`.
- Prints, per kind: `eligible / inserted / already_present / excluded / rejected`, plus the
  manifest hash.
- `--apply` **refuses if the source snapshot drifted** since the dry-run, writes exactly
  `eligible − already_present` rows, prints ids and hashes. A second `--apply` writes 0 rows.
- Runs from the **Pro checkout through the Fly proxy** (D10). Never from the Fly image. No
  `Dockerfile` change in this tranche.

### 6.1 Z2b, as it actually stands today

Z2b authorises at most 20 R1-prepared **fully sourced public regulatory** seed claims plus
whatever the legacy dry-run admits, 40 rows total. **R1 has since declared its seed cohort
EMPTY until sourced** — its `seed_public_regulatory` fixtures are synthetic
(`permenkumham-synth-*`) and therefore a TEST cohort, not a production one (R1 g3 checkpoint 3,
accepted by the imperator).

**Consequence for this build, and it must be stated in the PR body:** `--apply` may write only
what the legacy admission dry-run admits — **expected 0**, because legacy rows carry URL hashes,
no spans and no IntelEvent identity. Not one row of the synthetic fixture file is
production-eligible. A zero-admission dry-run is a **valid, honestly reported outcome** (D4).

**Until Zero hands over the write credential we stop at `--dry-run` and write 0 rows.** We never
ask a peer session for that credential; we ask Zero, through the imperator.

---

## 7. Perimeter

**Writable:** the four `services/research_os/naga_*.py` modules; the migration and its test;
`apps/backend-rag/backend/tests/services/research_os/naga/**`; this slice's evidence directory
(`evidence/2026-09/agent-nuzantara-backend-rag-r2-research-os-naga-49641b51/`) and
`research/operations/execution/research-os-v1.0.0/evidence/p06/ros-v1-p06-naga-engine-b02/**`
(counts and hashes only — **never claim text**).

**FORBIDDEN — a diff touching any of these fails the gate:** `packages/research-os-core/**`;
`apps/backend-rag/backend/services/naga/**` (legacy runtime; **no identity write-back**);
`app/routers/**`; `nuzantara_mcp/**`; `Dockerfile`; `fly.toml`; `specs/**`; the P06 bundle
(R1's); feature flags defaulting ON; any write to a table other than `research_os_objects` and
`research_os_naga_admission`.

**Also forbidden, from the tranche-wide list:** fabricated statements; URL-as-content hashes;
placeholder references presented as provenance; silent approval or classification defaults;
declaring a STABLE cast IMMUTABLE; production `DELETE`/`DROP`/`TRUNCATE` or trigger removal.

---

## 8. Stop and escalate — do not decide these alone

Checkpoint to the imperator (`nuzantara-0d`) and STOP if:

- admission needs a canonical field the contract lacks → write the freeze-change proposal, stop;
- legacy data needs a statement transformation that is **not a pure mapping** (that is the
  atomizer, and it is deferred);
- the backfill would write **anywhere else**;
- D7 cross-implementation hashing turns out to be required;
- a frozen path appears in a diff;
- a check is red **three times for the same cause**;
- the write credential is needed → finish at dry-run and say so.

A seat that does not answer is **not** a suspend: retry twice, check the invocation (absolute
binary path — mise shadows homebrew —, exact roster model id, flags, active account, network),
fall back inside the same role, and suspend only when the whole cascade is exhausted, written in
the ledger with time and exact error.
