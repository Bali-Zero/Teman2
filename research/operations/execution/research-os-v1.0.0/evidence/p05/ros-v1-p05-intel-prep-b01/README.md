---
date: 2026-08-26
domain: operations
adversarial_review: kimi-k3
---

# P05 Intel Lake / MATA GARUDA — preparation bundle

**Lane:** B1 · `intel` · task `ros-v1-p05-intel-prep-b01` · Wave 1, Cohort B
**Packet:** [`05-intel-lake-v2-mata-consolidation.md`](../../../../../specs/evidence-to-action-freeze-2026-08-15/work-packets/05-intel-lake-v2-mata-consolidation.md)
**Nature:** preparation only — read-only inventory, design, and scoping. **No implementation
readiness is claimed.** No Intel/MATA runtime file, migration, queue consumer, NB feeder, flag,
scheduler, DB row, or stream was edited to produce this bundle.

## What this bundle is

Five documents, each independently re-derivable from the commands/greps/reads cited inline
(anti-hallucination discipline: every claim below carries the command or `file:line` that
produced it; nothing is carried over from a prior document without being re-measured):

1. **[CONTRACT-MAP.md](CONTRACT-MAP.md)** — the lossless producer/consumer topology of Intel
   Lake + MATA GARUDA as they exist on disk today, and a field-by-field mapping from the
   existing Postgres schema onto the 25 frozen `research-os-core` typed models Cohort B is
   authorized to build against (`IntelEvent`, `StoryCluster`, receipts).
2. **[PROTECTED-DATA-BOUNDARY.md](PROTECTED-DATA-BOUNDARY.md)** — what is and is not OSINT/PII
   in this pipeline, the existing enforcement (or absence of it), and the boundary this bundle
   itself observed while being written (no real row content is quoted anywhere in this bundle).
3. **[METRICS-AND-GOLDEN-SET.md](METRICS-AND-GOLDEN-SET.md)** — candidate metrics mapped to the
   packet's exit criteria, a `MetricProfile` design, and the golden-set design (labels, strata,
   counts) for the dedup/story-cluster benchmark the packet requires be frozen before any
   semantic layer is inspected.
4. **[IMPLEMENTATION-SCOPE.md](IMPLEMENTATION-SCOPE.md)** — the exact future file list (new +
   touched), a lease list for the hot-zone pre-commit gate, and the packet's 9-step sequence
   re-expressed against files that actually exist today.
5. **[UNKNOWNS.md](UNKNOWNS.md)** — everything this session could not close, what was
   deliberately not checked, and two corrections to frozen/dispatched documents found while
   grounding this bundle (beyond the two the dispatching session had already found).

## One-line orientation for the reviewer

Intel Lake (`apps/backend-rag/backend/services/intel/`, Postgres `intel_items` /
`intel_observations`, migration `168`) is a live, flat, single-canonicalization pipeline with
**no** lineage, no idempotency contract, no sensitivity classification, and **no** story-cluster
concept — it dedups by exact `canonical_url` string match only. MATA GARUDA
(`apps/mata-garuda/`) is a separate, OSINT-blindato Redis-stream organism that already produces
a `intel.research_dossier` envelope meant for WR2, but the shared bridge consumer
(`apps/mata-garuda/mata_garuda/bridge/nerve.py`) does not recognize that envelope type and
silently ACKs-to-drop it (confirmed by direct read, not inferred — see CONTRACT-MAP.md §2.2 and
§2.3; an earlier revision of this line miscited §3, which is the NotebookLM feed). The
frozen `IntelEvent`/`StoryCluster` contracts from Packet 04 (`packages/research-os-core/
research_os/models/`) are considerably richer than either live system (`object_hash`,
`classification.sensitivity`, `lineage.pipeline_run_id`, discriminated payload references) —
none of that richness exists in the live schema today. Closing that gap correctly, without
retiring either live path, is the actual size of Packet 05.

## What this bundle explicitly does NOT do

- Does not claim any number as a live production count. The `postgres-nuzantara-local` MCP
  query tool returned `Command failed with no output` on `SELECT 1` in this session (tool
  infrastructure failure, not a data question) — see UNKNOWNS.md §1. Every quantitative claim
  in this bundle is either a static code/schema fact (file exists, column exists, function
  count) or explicitly marked "not measured this session."
- Does not touch, quote, or reproduce any real Intel Lake row, MATA GARUDA OSINT payload, or
  client/CRM record. All examples are schema-level or drawn from code comments already on disk.
- Does not open, edit, or reserve a migration file. Migration numbering is discussed in
  IMPLEMENTATION-SCOPE.md as a fact to re-measure at integration time, never as a number to bind
  now.


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
