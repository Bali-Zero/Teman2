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
