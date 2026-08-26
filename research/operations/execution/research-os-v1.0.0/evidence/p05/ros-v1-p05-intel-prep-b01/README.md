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
silently ACKs-to-drop it (confirmed by direct read, not inferred — see CONTRACT-MAP.md §3). The
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
