---
adversarial_review: gemini
date: 2026-07-23
domain: visa
client_case: none
author: Kimi (Air-M5) — W1 implementation brief (Track A chain, fires after W4 merge)
status: READY FOR IMPLEMENTER — requirements adjudicated by panel + Fable (deltas 1-4)
---

# W1 brief — evidence machinery: migration 256 + evaluate read-path API

Serial Track A chain, ONE lane, after PR #3034 (W4) merges. Everything here is already
adjudicated — do not re-litigate; gate deltas at the Fable gate.

## Item 1 — migration 256 `visa_decisions.traffic_source`

- New nullable column `traffic_source TEXT` with CHECK in
  (`real`, `synthetic_gold`, `synthetic_driver`) — NULL = legacy rows (same roll-forward
  pattern as 255; never backfill guesses). Mandatory `-- === ROLLBACK ===` marker.
- Index on `(traffic_source, created_at)` (collector scans windows by source class).
- Precedent to mirror: migration 187's probe-sandbox isolation flag (Fable delta 1).
- Collector (`shadow_evidence.py`) update: G-a reports real vs synthetic volume separately
  (Fable delta 2 — `G-a-vol` real-only; `G-a-breadth` synthetic-corpus, honestly labeled).
  Synthetic classes never count toward `G-a-vol`.

## Item 2 — evaluate read-path API (P0-3)

Public, exact, rate-limited endpoint (working name `POST /api/visa-oracle/evaluate`):

- **In:** canonical `ApplicantFacts` (validated against `applicant-facts.schema.json`;
  unknowns carry explicit reasons — never reject thin facts, the engine abstains).
- **Out:** `{mode: "ENGINE"|"CURATED", decision: Decision, sources: SourceRecordDTO[],
  display: pack-backed candidate display data}` — display model fields (name/tagline/
  timeline/requirements/checklist) are PINNED HERE (design-seat P2-2; Track C 4a consumes
  this contract). `Decision.public_id` is the shareable pointer (feeds E-g WhatsApp receipt).
- **Persistence:** every evaluation writes `visa_decisions` with full-fact provenance +
  `traffic_source` (migration 256) + `request_category` (Fable delta 3 — see Item 3).
- **Abuse controls (Codex red-team, binding):** schema validation, body-size cap, IP/session
  -hash rate limit (dedicated bucket, tighter than the generic 120/min — propose 30/min,
  confirm at gate), no raw PII logs (fingerprints only, per migration 255 pattern), no broad
  service impersonation, registered in `public_endpoints.py` exactly (W0a pattern).
- **CORS note** (web seat): same-origin today; if partner embeds are a goal, add explicit
  preflight handling for this path only.
- **SHADOW/ENFORCE flags:** the endpoint evaluates audit-only in SHADOW (response discarded
  server-side? NO — the v2 UI needs the response in CURATED mode for rendering while the
  engine verdict is audit-only; the `mode` envelope is what keeps that honest). The ENFORCE
  flip is out of scope here (separate gate).

## Item 3 — category mapping ruling (Fable delta 3; proposal, gate with Fable)

v2 interview has 10 tiles; `request_category` enum has 8 values. Proposal: **extend the enum
in migration 256** to 10: add `business` and `diaspora`, keep `other`:

| v2 tile | request_category |
|---|---|
| tourism | long_tourism |
| work | work_employee |
| remote | work_remote |
| invest | investor |
| business | business (NEW) |
| family | family |
| retirement | retirement |
| study | student |
| diaspora | diaspora (NEW) |
| other | other |

Collector `REQUIRED_INTERVIEW_CATEGORIES`: currently 7 substantive (= Purpose − OTHER).
After the extension, rule: the 7 legacy categories stay REQUIRED; `business`/`diaspora` are
REPORTED but not required for G-a-breadth until their behavioral trees exist (Track B FASE 2
order: they are lanes 2 and 6). Alternative (enum untouched, both map to `other`) silently
miscounts — rejected per Fable.

## Item 4 — gold-persona breadth extension (G-a-breadth corpus)

Extend the canonical persona fleet from 20 to cover the 30 priority codes / 7 categories
(E28/E33/BVK/Bridging mandated, Gemini correction 2). Personas replay through the REAL
evaluator via the W4 CLI with `traffic_source=synthetic_gold` semantics documented. This is
the G-a-breadth evidence artifact — corpus-driven, honestly labeled.

## Acceptance (lane done when)

- Migration 256 applied-pattern compliant (v2 SQL + ROLLBACK marker + schema_audit clean).
- Endpoint live behind flag in SHADOW mode on staging; one synthetic request → one
  `visa_decisions` row with `traffic_source` + `request_category` + full grounding summary.
- Collector emits the G-a-vol / G-a-breadth split.
- Suite: new tests guilt+innocence per item; full visa_engine suite green.
- Fable gate on the PR(s).

## Adversarial review

Gemini R1 pass (2026-07-24): P2 arithmetic error (8 existing + 2 new = 10 enum values, not 11) — FIXED. None survived, 1 raised.
