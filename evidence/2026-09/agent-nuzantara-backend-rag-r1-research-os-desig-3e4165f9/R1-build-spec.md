# R1 BUILD SPEC — D3 reader and D4 admission as executable rows

Mission R1 (BLUE), base `9304392d1a3c1f50dc6be847e8cd16d29a0c738b`. Authority: the mandate
`research/operations/2026-09-10-fable-max-sessions/R-research-os.md` (§0 D1-D10, Rulings Z1/Z2a/Z3/Z4,
and the `# R1 — DESIGN · battle window` section). This file is the contract the implementer builds
against; BUILD consumes THIS FILE, not chat memory.

## 0. Non-negotiable fences

- Writable ONLY: `apps/backend-rag/backend/tests/unit/research_os/**`,
  `research/operations/execution/research-os-v1.0.0/evidence/p06/ros-v1-p06-naga-prep-b01/**`,
  `research/operations/execution/research-os-v1.0.0/README.md`,
  `research/operations/execution/research-os-v1.0.0/SESSION-BOARD.md`,
  `evidence/2026-09/agent-nuzantara-backend-rag-r1-research-os-desig-3e4165f9/**`.
- FORBIDDEN, no exception: `packages/research-os-core/**` (contract surface stays BYTE-IDENTICAL —
  `git diff --stat origin/main -- packages/research-os-core` must be EMPTY at the end),
  `apps/backend-rag/backend/services/**`, `db/migrations_v2/**`, `apps/backend-rag/backend/services/naga/**`,
  `research/operations/specs/**`, `.claude/skills/modus/PENDING-ARMS.md`, any production write.
- No client PII, no OSINT, no real client identifiers anywhere. Fixtures stay SYNTHETIC and say so.
- Every regulatory figure in a fixture is INVENTED (B4's disposition below). No figure is copied from a
  real instrument unless a public citation is carried beside it — and in this slice we invent instead.
- Tests: no `skip`, no `xfail`, no `pytest.importorskip` on anything but a genuinely optional dependency.
- Run everything with `apps/backend-rag/.venv/bin/python` (3.11.11) and
  `PYTHONPATH=<worktree>/packages/research-os-core`. The repo-root `.venv` (3.14.7) has no `rfc8785`.

## 1. The `subject_key` extension — defined ONCE, here

D3 needs to group the canonical families that answer one domain question. `Claim.claim_family_id`
cannot do it: `CONTRACTS.md:141` requires a UNIQUE terminal member per family and `graph.py:139`
quarantines two edge-less members without ever looking at valid intervals, so two scheduled intervals
cannot live in one family. They are therefore two families joined by an explicit key.

Carried in the Claim's namespaced extension — no contract change, validates against the exported
Claim schema as it stands:

```json
"extensions": {
  "com.balizero.research-os.naga": {
    "extension_version": "1.0.0",
    "payload": {
      "subject_key": "id/permenkumham-22-2025/art-4-para-2",
      "jurisdiction": "id",
      "instrument": "permenkumham-22-2025",
      "provision": "art-4-para-2"
    }
  }
}
```

Rules, each of which gets a test:

1. The namespace is reverse-DNS (`primitives._REVERSE_DNS_RE`); `com.balizero.research-os.naga` passes.
2. `subject_key == "/".join((jurisdiction, instrument, provision))` — derivable and therefore checkable.
   The three parts match `^[a-z0-9][a-z0-9._-]*$`.
3. The payload introduces NO core field name at any depth (`primitives.V1_RESERVED_EXTENSION_FIELD_NAMES`,
   251 names). `subject_key`, `jurisdiction`, `instrument`, `provision` are all outside that set — VERIFIED
   on the base sha; the test re-verifies it rather than trusting this sentence.
4. A Claim carrying the extension still validates against `claim.schema.json` AND round-trips
   `Claim.model_validate`, and its `object_hash` still verifies. (Innocence: the extension is free.)

## 2. D3 — the reader, one signature and one truth table

```python
def read(objects: Corpus, subject_key: str, valid_at: datetime, known_at: datetime) -> ReadResult
```

`ReadResult` is a closed union, never a bare `None`:

| variant      | meaning                                         | carries                                      |
| ------------ | ----------------------------------------------- | -------------------------------------------- |
| `Answer`     | exactly one admissible answer                   | `claim_id`, `object_hash`, `claim_family_id` |
| `Abstain`    | no admissible answer, graph is sound            | `reason`                                     |
| `Quarantine` | the graph or the key is unsound; NEVER a winner | `family_ids`, `reasons` (sorted)             |

`Abstain.reason` ∈ {`no_family_for_subject_key`, `no_version_recorded_by_known_at`,
`no_valid_interval_covers_valid_at`}.
`Quarantine.reasons` ⊇ graph.py's own vocabulary (`fork`, `missing_node`, `hash_mismatch`, `cycle`,
`non_unique_current_member`, `successor_recorded_at_not_later`, `family_identity_mismatch`) plus
`ambiguous_subject_key` and `null_valid_from_on_consequential_claim`.

Algorithm, in this order — the order IS the specification:

1. **Group.** Families whose members carry `subject_key` in the extension. Zero → `Abstain(no_family_for_subject_key)`.
2. **Integrity, per family, BEFORE any temporal filter.** Mirror `graph.py`'s reasons over the family's
   members and its successor edges. Any reason → the family is QUARANTINED. A quarantined family is
   REPORTED, never silently dropped: if any family under the key quarantines, the whole read returns
   `Quarantine` — bypassing the graph by answering from the sound families is exactly the failure
   `CONTRACTS.md:141` forbids.
3. **System-time selection, per family.** Candidate versions are those with `recorded_at <= known_at`.
   A candidate is CURRENT AT `known_at` when it has no outgoing successor edge, or its successor's
   `recorded_at > known_at`. Zero candidates in every family → `Abstain(no_version_recorded_by_known_at)`.
   More than one current-at-S inside ONE family → `Quarantine(non_unique_current_member)`.
4. **Valid-time filter.** For each family's current member: admissible iff
   `valid_from <= valid_at < valid_to`, with `valid_to is None` meaning open. Half-open, always:
   `valid_at == valid_from` is IN, `valid_at == valid_to` is OUT.
   A finite `valid_to` is NEVER extended by succession — the successor's interval is its own and the
   predecessor's end stands as written.
   `valid_from is None` on a consequential claim (a numeric/regulatory claim, `CONTRACTS.md:266`) is
   INADMISSIBLE → `Quarantine(null_valid_from_on_consequential_claim)`.
5. **Across families.** 0 admissible → `Abstain(no_valid_interval_covers_valid_at)`. Exactly 1 → `Answer`.
   ≥2 → `Quarantine(ambiguous_subject_key)`. Two families answering the same (T, S) is a modelling
   defect, and the reader must say so rather than rank them.

**Instant comparison.** The reader compares PARSED instants, never raw text. The test module carries a
cross-representation table proving the parse folds the spellings the published schema admits —
`Z` == `+00:00`, `t` == `T`, `.1Z` == `.100000Z`, `.1Z` < `.11Z`, `.000000Z` == no-fraction — and a
row proving the RAW TEXT order disagrees with the chronological order (`.` 0x2E < `Z` 0x5A), which is
ledger row 21's defect and D2's reason to exist. R2's SQL key must agree with this table.

**Where it lives.** R1 may not write under `packages/research-os-core/**` or `services/**`. The reader is
therefore a REFERENCE implementation inside the test tree:
`apps/backend-rag/backend/tests/unit/research_os/research_os_reader_reference.py`, imported by the test
module. It is the executable form of the specification R2 implements against `research_os_objects`;
its docstring says exactly that, and says it is not the production reader.

### 2b. The temporal case list — every row EXECUTED, none skipped

| #   | case                                 | fixture                   | expected                                                                         |
| --- | ------------------------------------ | ------------------------- | -------------------------------------------------------------------------------- |
| 1   | lower boundary                       | scheduled pair            | `T == valid_from` → `Answer` (the interval that starts)                          |
| 2   | upper boundary                       | scheduled pair            | `T == valid_to` → `Answer` (the NEXT interval), never the closing one            |
| 3   | zero microseconds                    | `.000000Z` vs no-fraction | same instant, same answer                                                        |
| 4   | non-zero microseconds                | `.500000Z`                | ordered strictly after `.000000Z`, and `.1Z` < `.11Z`                            |
| 5   | unknown upper bound                  | `valid_to: null`          | open interval, answers for every `T >= valid_from`                               |
| 6   | correction recorded BEFORE discovery | `bitemporal/01`           | at `S` before the correction's `recorded_at`, the OLD version answers            |
| 7   | correction recorded AFTER discovery  | `bitemporal/01`           | at `S` after it, the NEW version answers, the old one is not mutated             |
| 8   | scheduled change known in advance    | `bitemporal/03`           | two families, one `subject_key`, one answer per `T`, both known at the same `S`  |
| 9   | existing finite expiry               | `bitemporal/02` shape     | `T` past a finite `valid_to` with no successor → `Abstain`                       |
| 10  | no answer                            | any                       | `Abstain` with the reason named, never a `None` a caller can mistake for a value |
| 11  | quarantined fork                     | forked pair               | two successors for one predecessor → `Quarantine(fork)`, no winner               |

## 3. D4 — admission as an executable predicate

```python
def admit(record: LegacyRecord, source: SourceSnapshot) -> AdmissionDecision
```

`AdmissionDecision` is `Admitted(family_id, claim_id, evidence_id, …)` or `Excluded(reason)`. Rules are
ORDERED; the FIRST failing rule names the reason, so a record with two defects reports one deterministic
reason. Nothing is ever defaulted silently: a missing classification is an EXCLUSION, not a default.

| order | reason                         | predicate                                                                                                       |
| ----- | ------------------------------ | --------------------------------------------------------------------------------------------------------------- |
| 1     | `statement_not_from_source`    | the statement triple is not derivable from the exact quoted span (`02:59` — no fabricated triples)              |
| 2     | `content_hash_is_url`          | `document_content_hash == sha256(document_id)`, i.e. the URL string was hashed instead of the body (`02:83-84`) |
| 3     | `source_version_missing`       | no `document_version_id` for this `(document_id, body hash)`                                                    |
| 4     | `exact_span_missing`           | `source_span` lacks `locator` or `quote_hash`, or `quote_hash != sha256(quoted text)`                           |
| 5     | `intel_event_identity_missing` | no `source_event_ref` resolving to a real `IntelEvent` (`02:87`)                                                |
| 6     | `rights_missing`               | `classification.rights` absent or empty                                                                         |
| 7     | `retention_missing`            | `retention.retention_class` absent                                                                              |
| 8     | `classification_missing`       | `risk_class` or `sensitivity` not explicitly assigned                                                           |
| 9     | `review_state_missing`         | `review.state` absent                                                                                           |
| 10    | `family_identity_unresolvable` | no stable family id assignable from the admission manifest                                                      |

**Family identity supersedes `02-p04-adapter-mapping.md:58`.** The stable family id is minted at first
canonical write and persisted in the ADMISSION MANIFEST (D5's `research_os_naga_admission`). It is NEVER
written back into legacy NAGA. `:58`'s "persisted back into NAGA (e.g. a new nullable column)" is
superseded by D4 and the bundle says so.

**Three counts, reported separately, and they DIFFER on the mixed set.** A test asserts all three are
pairwise different, so collapsing any two is a red:

- `documented_mapping_coverage` — required canonical paths §2 documents (32/32 after this PR);
- `available_source_information` — of those, the ones the legacy record carries ANY source information for;
- `admissible_records` — records passing every predicate.

**Zero admitted is a valid outcome.** A dry-run over legacy-shaped records that admits nothing, reported
honestly with a reason per record, is a PASS, not a failure. A test asserts exactly that on a
legacy-shaped cohort (URL hashes, no spans, no IntelEvent identity → 0 admitted, every exclusion named).

## 4. The mapping guard — rewritten, not renumbered

`apps/backend-rag/backend/tests/unit/research_os/test_naga_evidence_mapping_preconditions.py`.

DELETE: `test_the_bundles_own_correction_undercounts_the_gap`'s `assert len(absent) == 15` and
`assert named < absent`. Those pin a GAP; once §2 documents all 32 paths the gap is closed and a number
that measures its width is a number about a document that no longer exists. Flipping `15` to `0` would be
the renumbering the mandate forbids.

KEEP, unchanged: `test_the_baseline_fixture_is_genuinely_valid`, `test_a_corrupted_object_hash_is_refused`
(the guilt control — it is the only thing in the module that proves the hash is recomputed),
`test_the_section_extractor_actually_reads_the_section`,
`test_each_field_named_by_the_correction_is_independently_required`,
`test_the_published_schema_agrees_with_the_model`.

REPLACE the gap assertions with:

1. `test_section_two_documents_every_required_path` — `_never_named_in_section_two()` is now EMPTY, and
   `len(_required_paths(_schema())) == 32`. The failure message says "§2 must document all 32; missing: …".
2. `test_the_documented_mapping_produces_a_schema_valid_evidence` — the mapping §2 documents is EXECUTED
   over one canonical NAGA-shaped fixture (the fixture is R1's, synthetic, under
   `.../fixtures/seed_public_regulatory/`), producing an `Evidence` payload that
   (a) `Evidence.model_validate`s, (b) passes `jsonschema.validate` against `evidence.schema.json`,
   (c) has a self-consistent `object_hash`. This is the test the module never had: the old one proved
   four fields were load-bearing, never that the mapping produces a valid object.
3. `test_the_executed_mapping_covers_every_required_path` — the produced payload carries all 32 required
   paths, derived from the schema, never hardcoded.
4. The module docstring's correction 1 is REWRITTEN to record the history truthfully: the gap WAS fifteen,
   it was closed by R1 on <base sha>, and the guard now pins coverage instead of the gap. It does not
   pretend the gap never existed.

## 5. The P06 bundle

### 5a. `02-p04-adapter-mapping.md`

- §2 completed so every one of the 32 required Evidence paths is named with its mapping or its explicit
  "no NAGA source → EXCLUDED with reason `<name>`". The four the correction named
  (`evidence_family_id`, `review_state`, `classification.rights`, `times.recorded_at`) get real rows.
- A new §2b carrying D4's three counts and the rule that they are reported separately.
- The `:104` caveat ("three writes happen as separate, individually committed steps") is SUPERSEDED in
  place by D3's atomic rule: successor + edge commit in ONE transaction (`CONTRACTS.md:142`, `:267`).
  The old text stays visible, struck through as superseded, with the date and the authority — the bundle
  records what it used to say, per this repo's habit.
- `:58` superseded per §3 above (manifest, never write-back).

### 5b. Fixtures made canonical

Every fixture under `fixtures/` becomes a full canonical object set that validates against the EXPORTED
schemas, with EXACT, CONSISTENT references: a `ClaimRef`'s `object_hash` is the real
`research_os.hashing.object_hash` of the object it names, computed, not typed. A helper
`fixtures/_recompute_hashes.py` (in the bundle, synthetic-only) regenerates them so nobody hand-types a
hash again — the current `"4444…"` placeholders are precisely the "placeholder references presented as
provenance" the mandate forbids.

- `bitemporal/03` → REWRITTEN as **two families under one `subject_key`**, each with a unique current
  member and NO successor edge between them. The scheduled July rate change is not a supersession: revision
  1 is not wrong. Its `expected_behavior` says so and names `CONTRACTS.md:141` / `graph.py:139` as the
  reason. The two `queries` keep their answers (2026-03-15 → the first interval, 2026-08-15 → the second)
  and the system-time query keeps its abstention.
- `supersession/01` → REWRITTEN as **one atomic correction**: successor + edge in one transaction, ONE
  exact predecessor hash. Today `:49` and `:60` bind the same predecessor to TWO different hashes; the
  fixture carries the computed hash in both places and a test asserts they are equal and correct.
  The predecessor keeps `status: "supported"` and `valid_to: null` (RULING B1 — the old stays intact).
- `invalidation/01` stays DEFERRED and says so at `:24`; it is not made canonical in this slice and no
  test claims it is.

### 5c. `fixtures/seed_public_regulatory/**` — the Z2 seed cohort

Fully sourced canonical fixtures: body hash (of an invented document body carried beside it, so the hash
is REPRODUCIBLE from the fixture), exact span with a `quote_hash` computed from the quoted text, valid
time, rights, retention, classification, review state, IntelEvent identity. Every figure INVENTED and
stamped `"synthetic": true`. If a fixture would need a figure that cannot be sourced from a public
document, STOP and escalate — do not invent a figure and present it as sourced. (Inventing a figure and
saying it is invented is fine; inventing one and calling it sourced is the thing that is forbidden.)
Size: enough to exercise D4's admitted path and the reader's answer path — ≥3 and ≤20 claims (Z2b's
recommended ceiling), no more.

### 5d. `07-open-questions-and-corrections.md` — dispositions

- **§B2 residual** (may a predecessor's `valid_to` be written when the amending instrument states a
  cessation date as an independently sourced fact?) → DISPOSED as **(a), never write it**, promoted from
  "default" to DECIDED for this tranche: RULING B1's derivation rule plus `CONTRACTS.md:267`
  ("the predecessor is never updated") leave no room for (b). The cessation date lives on the successor,
  and the reader derives the predecessor's end from the edge. Recorded as a decision with its authority,
  not as an inherited default.
- **§B3** → CLOSED by the `bitemporal/03` rewrite: calendared succession is not supersession, and the
  bundle now says which mechanism applies when.
- **§B4** → CLOSED by stripping the real IDR figures out of the fixtures. Every number in every fixture is
  invented; the "SYNTHETIC" stamp becomes true instead of aspirational.

## 6. Control room (D9)

- `README.md:7` — `**Program state:** prepared_not_dispatched` is FALSE and becomes the real state, naming
  `research/operations/2026-09-10-fable-max-sessions/R-research-os.md` as the authority and this tranche
  (P06 slice 2) as what is running.
- `SESSION-BOARD.md` §5's head line (`:192`, "The real head is **`287`**") → "measure `max+1`; **309** on
  2026-09-11" with the sequence-is-not-dense note preserved. **Deviation, named:** R1 §4 asks for "308 on
  2026-09-11"; 308 was true when the staff room measured at 01:55 WITA and migration `309_client_obligations.sql`
  landed at 20:52Z (b2b2ceac76). We write the number we measured. The staff room confirmed this at 21:20:13Z.
- `SESSION-BOARD.md` §13 — new, carrying the 2026-09-11 measurement of §0: what Cohort B actually did,
  the ledger row 21 owner question, the production read (0 rows in `research_os_objects`, 3,119 in
  `naga_claims`), the Consul consumer, and this tranche's shape. Counts and paths only; no PII.

## 7. Acceptance — run all of it, paste the output

```
V=/Users/nuzantara/nuzantara/apps/backend-rag/.venv/bin/python
WT=/Users/nuzantara/nuzantara/.worktrees/backend-rag-r1-research-os-design
cd "$WT" && PYTHONPATH="$WT/packages/research-os-core" $V -m research_os.cli fixtures --check
    # MUST still print {"checked": 218, "failures": [], "valid": true}
cd "$WT" && git diff --stat origin/main -- packages/research-os-core   # MUST be empty
cd "$WT/apps/backend-rag/backend" && PYTHONPATH="$WT/packages/research-os-core" $V -m pytest \
    tests/unit/research_os tests/db/test_research_os_valid_time_is_not_text_orderable.py
cd "$WT/apps/backend-rag/backend" && PYTHONPATH="$WT:$WT/packages/research-os-core" $V -m pytest \
    tests/unit/services/autonomous_lab   # Consul's tests still pass
```

**CORRECTION, g3 2026-09-11, and it is the kind that stops a window for nothing.** The Consul leg above
carried `PYTHONPATH="$WT/packages/research-os-core"` — the core only. Run that way it reports
`1 failed, 272 passed`: `test_consul_native_broker.py::test_rpc_usage_projection_survives_native_checkpoint_and_broker_validation`
dies on `ModuleNotFoundError: No module named 'scripts.conductor'`, because the repo root is not on the
path. "Consul's tests go red" is a STOP-and-escalate condition in the mandate (R1 §6), so this command
manufactures the one red that ends the mission — a red that belongs to the invocation, not to the branch.
Measured both ways on the same sha: with `PYTHONPATH="$WT:$WT/packages/research-os-core"` the same single
test passes, and the full leg reads `274 passed, 17 skipped` (the skips are the DSN-gated
`test_dual_consul_postgres.py` integration cases, gated on `DUAL_CONSUL_TEST_DSN`, pre-existing and not
this branch's). The general rule this window learned: before escalating a red, re-run it with the
invocation changed and nothing else — a red that moves when only the command moves was never the code's.

Plus: every fixture in the P06 bundle validates against its exported schema (a test does this, so CI
carries the Bites observation before R2 exists).
