---
date: 2026-08-26
domain: operations
adversarial_review: kimi-k3
---

# Open questions this bundle could not close, and corrections found in frozen documents

## Corrections found in frozen documents this session (re-measured, not taken on faith)

1. **Packet spec `06-naga-claim-ledger.md` line 16, "Migration `273` is reserved for this
   packet"** — FALSE. Measured: `273_wa_broker_completion_digest.sql` exists and belongs to the
   WhatsApp broker (270-274 are a contiguous `wa_broker_*` block). The real migration head is
   `287_garuda_practices.sql`; the sequence has a gap at `282` (jumps `281_garuda_voa_retention.sql`
   → `283_wa_reply_claims.sql`). Command run: `ls apps/backend-rag/backend/db/migrations_v2/ |
   sort | tail -20` plus a targeted `grep -E '^27[0-9]|^28[0-9]'` pass, both from the main
   checkout, both this session. This matches the correction already supplied in the dispatch
   prompt — I re-verified it independently rather than trusting the prompt's own claim, per this
   session's standing anti-hallucination rule ("verify with a second independent tool call before
   citing critical results").
2. **`WAVE-0-DISPATCH.md` line 327, "applying or creating migration 273 in the preparation
   branch"** — read literally this forbids nothing relevant (273 is not this packet's). Read as
   intended (per the dispatch prompt's own correction, independently accepted here because it is
   the only reading consistent with the packet's actual migration-273 claim being wrong): forbids
   creating/editing/applying ANY migration file, any number, in this branch. Verified compliance:
   `git -C <worktree> status` before writing this bundle showed a clean tree at
   `origin/main`, and no file under `apps/backend-rag/backend/db/migrations_v2/` or
   `apps/backend-rag/backend/migrations/` was written by this lane (this bundle's own write
   perimeter, `research/operations/execution/research-os-v1.0.0/evidence/p06/**`, does not
   overlap either path).
3. **No correction found in `contract-pass-001.md §7` itself** — I treated its PASS_WITH_LIMITS
   verdict and its explicit allow/deny lists as authoritative for this session, per the dispatch
   prompt's own instruction to read §7 directly rather than a paraphrase, and did read it
   directly (quoted extensively in `02-p04-adapter-mapping.md` with line-anchored claims, not
   summarized from memory).

## Open questions this bundle raises but does not resolve (each needs a decision from someone with authority this lane does not have)

1. **`claim_family_id` minting** (`02-p04-adapter-mapping.md` §1, first row) — new UUID at first
   canonical write vs. derived from `claim_key`. Recommends new UUID; not decided here.
2. **`review_status: 'auto_extracted'` → P04 `review.state` mapping** (§1, `review_status` row) —
   `unreviewed` (conservative, recommended) vs. `machine_checked` (more accurate to what
   `claim_scorer.py` actually does). Not decided here.
3. **Aggregate `status` derivation function** (§1, `claim_status` row, gap G4) — the specific
   rule ("any contradicts → contradicted; all-support-high-confidence → supported; mixed/thin →
   inconclusive") is proposed, with one worked fixture
   (`fixtures/contradiction/02_partial_contradiction_mixed_evidence.json`), but is not specified
   to the level a build lane could implement without further design (e.g. what confidence
   threshold counts as "high"? Does a single low-tier `contradicts` outweigh three high-tier
   `supports`?).
4. **`classification.sensitivity` assignment policy** (§1, new-field row) — no NAGA source exists
   for this at all; a domain-based default heuristic is sketched but explicitly flagged as
   needing "an explicit policy, not a default guess." This gates the entire shadow/canary phase
   (packet: "Dual-write one public domain first") and this bundle cannot pick which domain is
   "public" — that is a business/compliance call.
5. **`retention.retention_class` / `legal_hold` policy for claims** — flagged as needing its own
   ruling, explicitly not inherited from the unrelated 5-year conversation-retention doctrine
   already in this repo (`decision_conversation_retention_five_years_never_delete` governs
   conversations, not claims — a different object class with different legal grounding).
6. **G6 — `Evidence.source_event_ref` requires an `IntelEvent` (P05 concept), and NAGA sources
   are not `IntelEvent`s today.** This is a genuine cross-lane dependency on sibling lane B1's
   (P05 Intel Lake) own preparation output, which per the dispatch's own scoping ("B1 and B2
   share one active preparation ceiling; this lane remains queued while B1 is active") this lane
   does not have visibility into beyond the shared P04 contract both lanes read. **I did not read
   B1's worktree or evidence directory** — that would be outside this lane's write/read
   discipline (the dispatch grants read access to the shared frozen contract, not to a sibling
   lane's in-progress preparation). A placeholder-`IntelEvent` fallback is proposed but explicitly
   marked as needing to be swappable once P05's real adapter exists.
7. **G7 — `ApprovalReceipt.subject.kind` has no `claim` member**, and the enum is closed
   (verified by reading the schema directly, not inferred). Recommends routing claim review
   through `OperationalReceipt` instead of requesting a contract widening, since widening a P04
   contract type is outside this lane's mandate and outside any Cohort B lane's authority per
   `contract-pass-001.md §7`'s own framing (Cohort B "may build against," not "may modify"). Not
   decided whether the eventual P06 build lane should instead formally request the widening from
   whoever owns the P04 contract's evolution — that's a process question, not a technical one.
8. **`research_os_objects`'s actual column shape was not read this session** — `03-migration-
   design-notes.md` explicitly flags that its recommendation (shared generic object table vs.
   two bespoke tables) depends on this and cannot be finalized without reading
   `279_research_os_contract_core.sql` directly, which this lane chose not to do (see next
   section for why).

## Why some obviously-relevant files were deliberately NOT read this session

- `279_research_os_contract_core.sql` and `280_research_os_objects_truncate_guard.sql` — these
  are P04's own migration files. The packet's file-ownership boundary says "Own additive NAGA
  models/repositories/services... Do not own Intel ingestion, NEXUS entity merging, Qdrant
  retrieval, WR2/WR3 content, or Action Inbox UI" — P04's migration internals are not explicitly
  listed as forbidden, but reading them in enough depth to commit to a table-shape design would
  have meant asserting a claim about another packet's implementation detail that this lane cannot
  independently re-verify was still true by the time a build lane acts on it (P04 is presumably
  still evolving on `origin/main` after this session, as `contract-pass-001.md §8`'s own
  correction-of-`SESSION-BOARD.md` demonstrates documents in this exact packet chain go stale
  within a day). Recommending "read it yourself, at build time" is more honest than restating a
  possibly-already-stale column list here.
- `services/naga/quality/{claim_scorer,dedup,expiry}.py`, `orchestrator.py`, `gateway.py`,
  `actions/action_engine.py` — grep-confirmed as consumers (baseline §6) but not read line-by-line.
  `persist.py` was read in full because it is the sole write path and therefore the ground truth
  for "what data shape actually reaches the tables"; the quality/orchestration files describe
  *how* claims get scored/enriched before that write, which matters for a build lane but was not
  necessary to produce the schema-level adapter mapping this bundle delivers. Explicitly flagged
  in the README as unread, repeated here for visibility.
- Any live database. No query was run against `naga_claims`, `research_os_objects`, or any other
  table. Every quantitative claim in this bundle about live state (e.g. "0/89 databases contain
  research_os_objects") is attributed to `contract-pass-001.md §7`'s own session, not
  re-measured by this one.
- `apps/nuzantara-mcp/nuzantara_mcp/tools/naga.py` and `server_lite.py` — confirmed as consumers
  via grep, not opened. Their exact call shape into the NAGA tables is unknown beyond "they
  reference the table/model names" and is flagged as a gap for whoever wires the shadow-read path
  in `06-future-file-list.md`'s consumer-facing section.

## Self-check: what would make this bundle's central recommendation wrong

The bundle's central architectural recommendation (`02-p04-adapter-mapping.md` §0) is: build a
new, additive, immutable canonical object stream that an adapter populates by reading NAGA's
existing mutable rows, rather than mutating `naga_claims` in place to add bitemporal columns.
This would be **wrong** if: (a) `research_os_objects`'s real column shape (unread, per above)
turns out to already enforce a schema that makes a from-scratch stream redundant with something
simpler already built, or (b) the packet's "extend NAGA's existing foundations; do not build a
third claim system" instruction is meant more literally than this bundle reads it — i.e. meant to
forbid a structurally new persistence layer even if additive, not just forbid a
*parallel-and-uncoordinated* claim system. Both are real risks a build lane should weigh, not
resolved here. I flag this because a preparation bundle whose central recommendation is wrong and
un-flagged is worse than one that is honestly uncertain.

---

## BLOCKING — raised by the cross-family adversarial review, 2026-08-26

These were found by Kimi K3 against a frozen head and re-verified on disk by the gating session.
They are recorded here rather than patched, because patching either one means CHOOSING an answer
this bundle has no authority to choose.

### B1. Supersession needs two coupled writes, and the atomic primitive is forbidden

`05-test-matrix.md`'s transition row requires that every `ObjectSuccessorEdge` predecessor "is
marked `superseded` and is excluded from 'current claim' queries." But `02-p04-adapter-mapping.md`
§0 states the packet's own rule verbatim: canonical versions are immutable and intervals are
"never closed by mutating a prior object." These cannot both hold.

Verified on disk: `Claim` carries a **required** `object_hash` (`claim.schema.json`, required
array line 603, `object_hash` at line 618), and every pointer at a claim is a
`ClaimRef {claim_id, object_hash}` — a pinned revision. So "marking the predecessor superseded"
changes the predecessor's content, hence its hash, hence invalidates the very `predecessor_ref`
the successor edge points at. No UPDATE is possible in the immutable model; writing a new
predecessor revision mints a hash nobody references.

The supersession flow therefore depends on **two objects changing together** — successor written
AND predecessor re-marked — with no atomicity and no stated crash-between-steps semantics.
`contract-pass-001.md` §7 forbids Cohort B from relying on **D10** (atomic repo primitive) and
**D11** (atomic classification-change). This is exactly a design that works only under one.

The "belt and suspenders" argument in §3 does not cover it: that argument covers a *missing edge*
(reconstructible from `supersedes_claim_ref`). A **stale predecessor status** is the other half of
the write pair, and it has no reconstruction rule at all.

**Needs a ruling before any P06 build lane starts:** either (a) predecessor state is derived at
read time from successor edges and never stored, or (b) supersession waits for D10/D11. Do not
let a build lane pick silently.

### B2. The two supersession fixtures encode contradictory conventions — RESOLVED by RULING B1 (2026-08-26)

Re-verified on disk. `bitemporal/01`'s predecessor `claim_v1` keeps `status: "supported"` and
`valid_to: null`; `supersession/01`'s predecessor `claim_v1_original` carries
`status: "superseded"` with `valid_to` closed at the successor's boundary. Both objects play the
identical role — "predecessor of a `supersedes_claim_ref`" — and give consumers no single answer.

Worse, `bitemporal/01`'s two revisions share the same `valid_from` (`2026-01-15`) and both leave
`valid_to` open, so the pure valid-time query `05-test-matrix.md` specifies returns **both** rows
for any instant ≥ 2026-01-15 — verbatim the "FALSE if" condition of that file's own
temporal-exclusion row. The fixtures fail the bundle's own test plan unless the implementation
mutates the predecessor, i.e. unless B1 is resolved in the direction the doctrine forbids.

**RULED 2026-08-26 (Zero, Legge 5).** Supersession state is derived at read from the successor
edge and never written onto the predecessor -- *«il vecchio resta intatto»*. Authority: memory
`decision_research_os_b1_supersession_derived_at_read_2026_08_26.md`, which carries Zero's
verbatim `ok`. Applied here as a consequence, not as a new decision:

- `supersession/01`'s predecessor is restored to `status: "supported"`, `valid_to: null`, matching
  `bitemporal/01`. Both writes went, not just the status: the closed `valid_to` was also set as a
  *consequence of the amendment*, which is the thing the ruling forbids.
- **The ruling does not rescue the fixtures from the test matrix — it convicts the matrix.** With
  predecessors left intact, the pure valid-time query `05-test-matrix.md` specified genuinely does
  return both rows. That was never the fixture's fault: `bitemporal/01`'s own `expected_behavior`
  already said the *system-time* cutoff must gate the answer. Both temporal rows of `05` are
  restated so the query under test is the composite one (valid-time AND system-time AND
  no-successor), and the transition row no longer demands the predecessor "is marked `superseded`"
  -- wording that required precisely the forbidden write.

**Residual, NOT decided by B1 and deliberately left open:** may a predecessor's `valid_to` ever be
written when the amending instrument states an explicit cessation date as a fact in its own right?
B1 forbids writing it *as a consequence of succession*; it is silent on writing it as an
independently sourced fact. Two coherent answers exist -- (a) never write it, the cessation date
lives on the successor claim and readers derive the predecessor's end from the edge; (b) write it
only when a cited source states it, which reintroduces a predecessor write and therefore needs the
immutability argument redone. This bundle takes (a) by default because it is the one B1's wording
supports; whoever builds P06 should raise (b) as a real question rather than inherit the default.

### B3. `bitemporal/03` conflates correction with calendared succession

Fixture 03 models a rate change (IDR 2.0M valid Jan–Jul, IDR 2.5M valid from Jul) using
`supersedes_claim_ref`. But revision 1 is not *wrong* — it is the fixture's own expected correct
answer for 2026-03-15. Applying supersession semantics uniformly ("predecessor excluded from
current queries") would either suppress the correct March answer or mark a still-true claim
`superseded`. The bundle never distinguishes "supersede = correction" from "supersede = next
scheduled interval", and the edge-reconstruction rule would mechanically mint successor edges for
mere calendar sequences, poisoning the transition graph the invalidation logic consumes.

### B4. The "100% invented" purity claim is overstated — CORRECTED 2026-08-26 in `04`

`04` says the fixtures are "not 'real data with names changed' — invented from the category
description." The supersession fixture embeds the **real** IDR 2,500,000,000 PMA paid-up figure
and the IDR 10B exception threshold (self-attributed to a repo memory); the scope fixture embeds
a real "paling lambat 7 hari" finding. The notes are transparent and none of it is client PII, so
this is not deception — but the blanket claim is false, and the result is the worst of both: a
file stamped "SYNTHETIC — do not treat as regulatory fact" now carries a real regulatory figure
that this session did NOT re-verify. Whoever builds the golden set must either strip these to
invented numbers or re-ground them against the live corpus. Do not cite them as validated.


## Adversarial review

**Seat:** Kimi K3 (`kimi -m kimi-code/k3`), cross-family — neither the model that wrote this
bundle nor the session that gated it. Run 2026-08-26 against a FROZEN diff (head `bb6d9ceb9`):
the generator was dead before the refuter was dispatched.

**Verdict: DEFECTIVE.** The bundle is unusually honest about what it did not do, and its two
load-bearing corrections (migration numbering, the G7 `ApprovalSubjectKind` gap) check out
independently. But its fixture set was internally inconsistent in exactly the D11 area the review
was aimed at, and its central baseline claim rested on one search pattern. Every finding was
re-verified against disk by the gating session before acceptance — the refuter is not trusted
either (superscar #6). That re-verification made finding 1 **worse** than reported.

| # | Finding | Verified | Disposition |
|---|---|---|---|
| 1 | "`persist.py` is the only writer" came from an `INSERT INTO naga_` grep, blind to UPDATE by construction | TRUE, **and worse** | **FIXED** — four UPDATE writers named (`dedup.py:144`, `claim_scorer.py:202`, `expiry.py:58`, `:174`). The gating session also found the cited INSERT grep is *itself* wrong: `dedup.py:155` and `expiry.py:154` insert into `naga_claim_transitions`, one of the same 5 tables, and `persist.py` never writes it. Five writers across three files, not one |
| 2 | "`quality_score` written once" contradicted by two post-insertion UPDATEs | TRUE | **FIXED** — written *first*, not once |
| 3 | §2 point 5's open mystery ("what moves a claim out of `active`") is answered in a file it listed but never searched | TRUE | **FIXED** — `expiry.py:58` / `dedup.py:144`. The `review_status` half STANDS: nothing moves a claim out of `auto_extracted`, so the human-review gate has no exit path in code |
| 4 | Supersession requires two coupled writes on an immutable content-hashed object; D10/D11 forbidden by §7 | TRUE (`object_hash` required, `claim.schema.json:618`) | **RULED 2026-08-26 (Zero, Legge 5)** — supersession derived at read from the successor edge, never written on the predecessor; `object_hash` intact, no D10/D11 needed. Authority: memory `decision_research_os_b1_supersession_derived_at_read_2026_08_26.md` (verbatim `ok`). Originally raised as BLOCKING in `07` §B1. Patching it means choosing an answer this bundle has no authority to choose |
| 5 | `bitemporal/01` and `supersession/01` encode contradictory predecessor conventions; `bitemporal/01` trips the test matrix's own "FALSE if" | TRUE | **RESOLVED as a consequence of B1** — `supersession/01`'s predecessor restored to `supported`/`valid_to: null`. The ruling did not rescue the fixtures from the matrix, it convicted the matrix: both temporal rows of `05` are restated (composite valid-time AND system-time AND no-successor), and the transition row no longer demands the forbidden write. One residual left OPEN in `07` §B2 |
| 6 | `bitemporal/03` uses `supersedes_claim_ref` for calendared succession, not correction | TRUE | **RAISED** (`07` §B3) |
| 7 | `invalidation/01` withdraws evidence `...e7` and asserts it affects claim `...0030` — a citation that exists nowhere in the fixture set | TRUE | **FIXED** — trigger now withdraws `...e2`, which `0030` genuinely cites. A PASS on the original data would have proven nothing |
| 8 | "one or more per adversarial category" false — case 6 (sanitization boundary) had no fixture | TRUE (14 files, 8 dirs, no sanitization) | **FIXED** — fixture added; 15 files. This was the one category where a missing negative control costs most |
| 9 | Evidence adapter mapping is four required fields short: `evidence_family_id`, `review_state`, `classification.rights`, `times.recorded_at` | TRUE (0 grep hits each; all four in the schema's required sets) | **FIXED** — §2's completeness claim corrected; closing them is a build precondition |
| 10 | "Fixtures validate directly against the schemas" — they would fail today (extraneous `note`, most required fields absent, `additionalProperties: false` throughout) | TRUE | **FIXED** — restated as behaviour specs; the old hedge covered "we did not run it", not "it would fail" |
| 11 | "100% invented, not real-data-renamed" overstated — real PMA capital figures embedded | TRUE | **CORRECTED 2026-08-26 in `04`** (`07` §B4) — transparent, no PII, but a synthetic-stamped file now carries an unverified real figure |
| 12 | G5 attributes a URL hash to "the migration" (it is `persist.py:102`), and omits the `[:16]` / `[:32]` truncations | TRUE, low severity | **ACCEPTED AS LIMIT** — substance (hash of URL, not content) is correct |

**Not a finding** (refuter checked, found sound): migration numbering — `273` is WhatsApp-broker,
head is 287, 282 absent, symbolic name correct; the G7 `ApprovalSubjectKind` closed-enum gap;
`ObjectSuccessorEdge` and `OperationalReceipt` required-field claims; the abstention fixture's
`reasoning.py` attribution (re-exported from `reasoning_utils.py`); and implementation-readiness,
which is disclaimed consistently throughout.

**Bottom line:** usable as an inventory and a gap list. **UPDATED 2026-08-26:** the two conditions
this line gated on are discharged — §B1 is ruled (supersession derived at read) and §B2 resolved as
its consequence, with the fixture and both temporal rows of `05` corrected to match. What is still
NOT discharged, and what a build lane must read first: §B2's residual on writing a predecessor's
`valid_to` from an independently sourced cessation date, §B3 (`bitemporal/03` conflates correction
with calendared succession), and §B4's consequence — the fixtures carry real, unverified regulatory
figures under a SYNTHETIC stamp and must be re-grounded or replaced before they are cited as fact.
