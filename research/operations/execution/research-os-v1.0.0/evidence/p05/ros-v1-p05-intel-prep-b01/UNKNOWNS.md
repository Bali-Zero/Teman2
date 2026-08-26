---
date: 2026-08-26
domain: operations
adversarial_review: kimi-k3
---

# Explicit unknowns, what was not checked, and corrections found

## 1. Live database access was unavailable this session — no live counts anywhere in this bundle

`mcp__postgres-nuzantara-local__query` returned `Command failed with no output` on three
successive attempts, including the trivial `SELECT 1;`. This is a tool/infrastructure failure,
not a "no rows" result — per this repo's own anti-hallucination discipline ("a grep that returns
nothing may mean your grep is broken, not that the world is empty"), the correct read of a
broken tool is "unknown," not "zero." Consequence: **every quantitative claim in this bundle is
a static code/schema fact (a file exists, a column exists, a function is or isn't defined), never
a live count.** The packet's own "Live baseline to refresh" section asks for producer counts,
event counts, unique-URL counts, review rate, duplicates, outbox pending/abandoned, consumer
lag, unknown-message-ACK counts, NB submission counts — **none of these were obtained**. This is
the single largest gap in this bundle relative to the packet's ask, and it is a tooling gap, not
a scoping choice: this lane's dispatch explicitly allows "aggregate, redacted live counts
obtained on Pro when the manifest explicitly permits" — the attempt was made, in-scope, and
failed at the tool layer.

Whoever picks this up next should retry the same MCP tool (it may be a transient session issue)
or fall back to a direct `psql`/`fly ssh` read-only session — this bundle does not diagnose why
the tool failed beyond confirming it failed identically on a query with zero table dependency.

## 2. Not checked, deliberately, given the read-only/no-implementation scope of this lane

- **The full producer registry.** (Wording corrected 2026-08-26: §1.3's two named items are
  `scripts/intel-lake-outbox-drain/` and `intel_radar.py` — and §1.3 itself says `intel_radar`
  writes `asset_provenance` by a path SEPARATE from Intel Lake's `record_observation()`, so
  calling both "Intel Lake producer entrypoints" overstates it.) CONTRACT-MAP.md §1.3 found the two in-monorepo producer
  entrypoints (outbox-drain's SQLite source, whatever writes to it) but did not walk `~/scripts/`
  (outside the repo, a live-Pro filesystem path, not something a worktree-scoped read-only lane
  should be inventorying without the live-count access described in §1 anyway) to enumerate every
  process that ultimately posts to `POST /api/intel/lake/observations`. Deliverable #1's
  "verified producer registry" needs this and this bundle does not close it.
- **`packages/research-os-core/research_os/models/metric_profile.py` and `decision_packet.py`**
  were listed by `find` (confirmed present) but not read line-by-line. METRICS-AND-GOLDEN-SET.md
  §2's proposed profile field names are therefore a **proposal to check against the frozen
  model**, not a claim that they already match it.
- **Whether any file in `apps/backend-rag` imports `research_os.models.intel_event` or
  `research_os.models.story_cluster`.** CONTRACT-MAP.md §5.3 states no adapter file exists to
  import them from (confirmed, directory listing), but did not run an exhaustive
  `grep -r "models.intel_event\|models.story_cluster"` across the whole tree — flagged rather
  than asserted as zero.
- **Tigris bucket ACLs / actual object-storage backend for a future `DurablePayloadReference`.**
  PROTECTED-DATA-BOUNDARY.md §5.3 names this as unverified.
- **This repo's standard feature-flag mechanism**, referenced in IMPLEMENTATION-SCOPE.md §5 step
  2 as something the eventual builder needs to locate — not inventoried here because it is a
  BUILD-phase concern, not a preparation-phase one, and inventorying it without a concrete flag
  to wire would be speculative.
- **`intel-lake-router-a2/intel-lake-routing-rules.json`'s actual rule content** (58 lines,
  confirmed present via `wc -l`, not read) — relevant to deliverable #1's "event types" column
  but reading and transcribing 58 lines of routing rules did not seem load-bearing enough to
  justify given the tool-call cost measured this session (§4).

## 3. Two corrections found this session, beyond the two the dispatching prompt already supplied

The dispatching prompt supplied two corrections up front (the "272" migration mislabel, and the
resulting scope-of-prohibition correction). Independently re-verifying rather than trusting them
(CONTRACT-MAP.md §1.2, IMPLEMENTATION-SCOPE.md §1) confirmed both. Two further corrections
surfaced during this session's own grounding work, not supplied by any prior document:

1. **`intel_lake_service.py`'s own docstring contradicts its own SQL.** The module docstring
   (line 10) states "Content drift → INSERT new row (separate canonical version)." The actual
   `record_observation()` SQL (`ON CONFLICT (canonical_url) DO UPDATE SET last_seen_at = NOW()`)
   only ever updates `last_seen_at`; it never inserts a second row for the same
   `canonical_url`, drift or not. `is_content_drift` is computed and logged as a warning
   (`intel_lake_service.py:217-224`) but has no persistence consequence. This is a live
   discrepancy in a file this packet explicitly owns — flagged for the eventual builder, not
   fixed here (out of a preparation lane's remit).
2. **`intel_lake_router.py`'s Tier-2 claim is aspirational, not implemented — confirmed by
   function enumeration, not by trusting the packet's Live Baseline prose.** CONTRACT-MAP.md
   §1.4 lists every function defined in the file; none calls an LLM. This independently confirms
   (rather than merely repeats) the packet's own claim ("no working Tier-2 enrichment path"),
   which matters because this lane's discipline requires re-verifying inherited claims, not
   relaying them.

Additionally, one **duplicate-truth-path** was found that neither the packet's prose nor the
dispatching prompt named: **two independent, functionally identical Tier-1 routing
implementations exist** — the Fly-side `intel_lake_router.py` (dormant, gated behind an
unrelated `DISABLE_BACKGROUND_WORKERS=1` kill-switch from an unrelated 2026-04-12 incident,
per that script's own docstring) and the Pro-side `intel-lake-router-cron-standalone.py` (live,
5-minute cron). CONTRACT-MAP.md §1.4 has the detail. This is exactly the class of "parallel
truth path" the packet's mission statement targets and should be in scope for whoever designs
the real consolidation, even though the packet's own file-ownership list only names the Fly-side
file by path.

## 4. A note on session conditions, for calibration of this bundle's thoroughness

This session ran under continuous, high-volume cross-machine fleet-mailbox traffic (dozens of
messages per tool call, injected via the harness's PostToolUse hook) concerning **other lanes'**
merge-queue mechanics (PR #4640/#4664/#4706/#4717/#4768/#4803/#4885/#4963/#4974/#4977/#4978,
none of which are this lane's), none of which bears on Intel Lake or MATA GARUDA. None of it was
acted on (correctly — it was not addressed to this lane, and this lane's write perimeter forbids
touching any of those files regardless). It is noted here only because it capped the number of
investigative tool calls this session could spend efficiently, which is the direct cause of §2's
scope cuts — those cuts were a deliberate trade against a real cost, not an oversight.

## 5. Summary verdict for the Conductor

This bundle is a **contract map and design proposal**, not a readiness claim. The single largest
blocker to a real build starting is **not** anything architectural — CONTRACT-MAP.md's gap
analysis is complete enough to start from — it is that **no live measurement of the current
Intel Lake/MATA GARUDA state was possible this session** (§1). The next session (this one's
successor, per the dispatch's "fresh successor manifest and worktree... after P04 integration"
instruction) should treat restoring live Postgres access as its first action, not an
afterthought, because deliverable #1 ("verified producer registry... health") and the packet's
entire "Live baseline to refresh" section depend on it and neither can be honestly closed
without it.


## Adversarial review

**Seat:** Kimi K3 (`kimi -m kimi-code/k3`), cross-family — neither the model that wrote this
bundle nor the session that gated it. Run 2026-08-26 against a FROZEN diff (head `2807f50e9`):
the generator was dead before the refuter was dispatched, so nothing moved under it.

**Verdict: DEFECTIVE on method, sound on its two headline findings.** The bridge ACK-drop and the
`intel_lake_service.py` docstring-vs-SQL drift both check out on independent re-read. The
systematic defect is a *class*: single-search results stated with more precision than the search
supports. Every finding below was re-verified against disk by the gating session before it was
accepted — the refuter is not trusted either (superscar #6).

| # | Finding | Verified | Disposition |
|---|---|---|---|
| 1 | D7 dependency unflagged: `object_hash` + MATA-side hash reconciliation need the same digest in two implementations, but `apps/mata-garuda` caps deps at `pydantic>=2` | TRUE (`grep D7` → 0 hits in bundle) | **FIXED** — §5.1 now flags it as a §7-forbidden primitive; do not design that reconciliation until D7 lands |
| 2 | "Enumerated every function" used `^def ` — blind to indented sync methods; missed `__init__` (267) and `_classify` (387), the actual rules engine | TRUE | **FIXED** — §1.4 restated; conclusion survives on a re-read, not on the enumeration |
| 3 | "7 files" while listing 8 names in the same sentence | TRUE (`ls` → 8) | **FIXED** |
| 4 | Migration list from a literal-string grep, misses `205_cockpit_intents.sql` (`intel_items`); and `171` is listed as found by a pattern that does not return it | TRUE | **FIXED** — list relabelled a lower bound, both gaps named |
| 5 | Line counts off: 306→305, 230→229, `WR2_ENVELOPE_TYPE` line 34→36 | TRUE | **FIXED** — re-measured |
| 6 | "No file in `apps/backend-rag` imports `intel_event`/`story_cluster`" — false, a test file imports both | TRUE (hedged in-sentence and in UNKNOWNS §2) | **FIXED** — restated; substantive point (importer is a test, no adapter) stands |
| 7 | "89 local databases" is a count carried from a prior session, contradicting this bundle's own "no live counts anywhere" | TRUE | **FIXED** — marked carried-over, not a confirmation |
| 8 | §3.4 arithmetic defeats itself: needs >100, sets the two safety-critical strata to exactly 100; 1/100 = 1.00%, not < 1% | TRUE | **FIXED** — >=101 required, 810 total moves |
| 9 | README cites §3 (NotebookLM feed) for the ACK-drop finding, which lives in §2.2/§2.3 | TRUE | **FIXED** |
| 10 | UNKNOWNS §2 "two producer entrypoints" vs §1.3, which says `intel_radar` writes by a SEPARATE path | PARTIAL | **FIXED** — wording corrected, overstatement removed |
| 11 | "Every dossier envelope has been ACKed-and-dropped since the producer was written" is a live-traffic history claim provable only from code paths | TRUE (overreach) | **ACCEPTED AS LIMIT** — the drop PATH is proven by direct read; whether the producer ever ran with traffic is unknowable without the live stream this bundle could not reach (UNKNOWNS §1) |

**Not a finding** (refuter checked, found sound): migration numbering — head 287, 282 absent,
`272_wa_broker_package_text.sql` WhatsApp-broker-owned; the bundle correctly refuses to bind an
integer. Readiness claims — disclaimed consistently across README and UNKNOWNS §5.
