---
date: 2026-07-18
domain: operations
client_case: none (GARUDA-FILIERA Batch A pre-registration)
sources:
  - "workflow: research/operations/2026-07-16-kbli-garuda-filiera-workflow.md (§1-§8, red-teamed)"
  - "methodology: research/operations/2026-07-16-kbli-filiera-methodology.md (P1-P9, G13-G17)"
  - "GO: Zero 2026-07-17 ~23:00 WITA ('go', Batch A per workflow §8)"
  - "enumeration: live on KBLI_2025_FINAL_CLEAN.json 2026-07-17 post-cure-4"
---

# Batch A plan — pre-registration (authored BEFORE extraction, per D-protocol)

> Conductor: Fable session (M5). This plan is the pre-registered contract: acceptance criteria
> are fixed HERE, before any lane extracts anything. Changing a criterion mid-batch requires a
> logged amendment in this file (append-only §7), never a silent shift.

## 1. Scope (deterministic enumeration, 2026-07-17)

Batch A = the **221 no-scope codes** (`_l2_status: no_oss_risk` OR per_skala present with no
`_l2_source`), split into two waves by live harm:

- **Wave A-serving — 114 codes**: still SERVE PP28-derived `per_skala` rows in production
  (living collision risk). Priority.
- **Wave A-empty — 107 codes**: per_skala already `[]`/detached (includes the 8 cured pilot
  codes). No active harm; the work is closing the gap with true licensing where it exists.

(The workflow doc's "119" was the 2026-07-16 pre-cure enumeration of the serving set; today's
114 + already-detached codes reconcile it by content. The enumerated code lists are in the
conductor's batch record; the enumeration script is 3 lines against the canonical and is
re-runnable by any seat.)

Ordering: taxonomy order (division/group) within each wave, A-serving first — maximizes
prompt-cache reuse and groups similar lampiran pages.

## 2. Preconditions (no extraction before ALL are true)

1. **Vault manifest pinned**: LANE-B0 has committed `data/kbli-filiera/manifest/` with sha256
   for: BPS conversion table (Vol.1+2), PP28 lampiran renders (300-dpi, BPK ids 394930-394950),
   OSS re-snapshot (version uuid fff4053d…), Perpres 10/49-2021 annexes. A batch pins ONE
   manifest revision; mid-batch refreshes never change evidence under a running lot.
2. This plan is on `main`.
3. Leases: every dossier claim goes through `agent_lock:kbli-dossier:<code>` (Redis). No lease,
   no touch.

## 3. Per-fact acceptance criteria (what "certified" means in Batch A)

A fact (risk tier, license row, authority, scale, obligation) is **CERTIFIED** only if ALL:

- **A1 Provenance**: carries (source id from the pinned manifest, page/row locator, vintage
  tag). A fact without a locator is not a fact.
- **A2 Vintage legality**: any KBLI-2020-vintage source (PP28, Perpres 10/49) reaches a
  KBLI-2025 code ONLY through a BPS-crosswalk row adjudicated at D1 (uraian-equivalence for
  1-to-1; full semantic adjudication for splits/merges). Bare-digit joins are auto-QUARANTINE.
- **A3 Image verification**: any digit/row read from a scanned lampiran is extracted from the
  300-dpi RENDER with the D2 self-confirming protocol (extractor re-states the code string +
  neighboring rows' codes from the image). pdftotext is never evidence of digits.
- **A4 Blind agreement**: the D5 refuter (family ≠ extractor) re-extracts blind (render + code,
  never the extractor's answer); compiler diff must MATCH. Divergence → QUARANTINE, never
  averaged or picked.
- **A5 Absence is earned**: an ABSENT/gap verdict requires the D0 rule — endpoint inventory
  complete, ≥3 attempts over ≥72h, AND a negative control (known-present code) returning data
  in the same crawl window — plus one independent corroboration (e.g. absence on the lampiran
  image). Otherwise the fact is `abstained(pending-evidence)`, not ABSENT.
- **A6 Honest fallback**: where the true row cannot be certified, the code gets the pilot's
  honest-gap pattern (detach + disputed-key + _data_note + editorial/l4 NON_CLASSIFICABILE) —
  never a plausible value. The 8 cured codes are the template AND the gold-set nursery.

## 4. Quarantine + sampling regime (Batch A specifics)

- 100% conductor review of every certified licensing fact (Batch A is the gold-set nursery).
- Quarantine auto-triage: `schema_error` → back to compiler lane; `logic_conflict`/`semantic`
  → conductor queue. Quarantine is a STATE with owner + resolution criteria, not a parking lot.
- Control limits (measured on pilot A1 as baseline): certification rate, refutation categories,
  extractor/refuter IAA, tokens/dossier. A control-limit breach pauses the lane and requires a
  signed resume note in this file (§7).
- Hidden gold-set: the 8 cured codes are seeded into lane inputs unmarked; a lane result that
  contradicts their certified state halts the lot.

## 5. Seats + lanes (session topology)

| Window | Role | Machine | Model | Reads | Writes |
|---|---|---|---|---|---|
| CONDUCTOR (this) | plan, adjudication, D6 gate, canonical emit | M5 | Fable | everything | batch record, quarantine resolutions, canonical delta PR |
| LANE-B0 | vault bootstrap (running) | Mini | any impl. | gov endpoints | vault blobs + manifest |
| LANE-E1 | D0-D4 extraction, wave A-serving | Pro | Sonnet | pinned vault, this plan | dossiers JSONL (leased) |
| LANE-V | D5 blind re-extraction | Mini | ≠ extractor family (GLM/DeepSeek/Codex cascade) | pinned vault + code list only | verification events (leased) |
| TRACK-P | product redesign (independent) | any | Sonnet | — | apps/mouth only |

Disk is the only inter-lane channel (dossiers, quarantine ledger, this file). No chat handoffs.
M5 hosts no fleet (2026-07-17 lesson: fleet load kills gates). One canonical emitter: conductor.

## 6. Deliverables + definition of batch-done

1. Dossier JSONL per code (hash-chained events D0→D5) for all Wave A-serving codes.
2. Conductor-signed batch report: censuses, per-fact verdicts (certified/quarantined/abstained),
   IAA, gold-set hits, measured service times + token burn (the cadence basis for Batch B).
3. Canonical vNext delta PR(s): certified rows land with provenance; uncertifiable codes get
   the honest-gap pattern. Every negative finding becomes a permanent sentinel/registry test.
4. Consumer-map executed per emit (canonical → mouth/gold/KG/Qdrant/native app) — no surface
   left stale (merged ≠ live).
5. Wave A-empty follow-up scoped from the measured report.

## 7. Amendments (append-only)

- (none yet)
