---
date: 2026-06-06
domain: compliance
client_case: false
sources:
  - apps/backend-rag/backend/app/routers/crm_clients.py (create L429, update L883, ensure-drive-folder L809-878)
  - apps/backend-rag/backend/middleware/hybrid_auth.py (internal-key L369-385, get_current_user_or_internal L41-76)
  - apps/backend-rag/backend/app/core/config.py (wa_mirror_internal_key L878)
  - ~/scripts/wa-mirror-auto-promote-leads.py (INSERT clients L691, UPDATE clients L652)
  - ~/scripts/wa-mirror-strategic-recap-updater.py (UPDATE clients.strategic_recap L203)
  - mem decision_wa_mirror_local_only_cutover_2026_05_24
status: DRAFT — pending 4-LLM panel + Antonello deploy approval
---

# Spec: wa-mirror CRM writes via backend API (read-local / write-Fly)

## Problem

After the 2026-05-24 wa-mirror→local cutover, `WA_MIRROR_DATABASE_URL` points at local
`nuzantara_dev` (trust). Two downstream consumers write CRM records:

- `wa-mirror-auto-promote-leads.py` — INSERT new leads + ENRICH archived clients (notes).
- `wa-mirror-strategic-recap-updater.py` — UPDATE `clients.strategic_recap` (Ollama-local summary).

They had a vestigial `re.sub(@host → @localhost:15432/)` (Fly proxy) that sent local
trust creds (no password) to Fly → `InvalidPasswordError` (broken since cutover day).
**Fixed 2026-06-06** by removing the rewrite → they now write LOCAL `nuzantara_dev`.

But the CRM of record is **Fly** (`clients` 11,720 rows; `kita.balizero.com` + team read it).
Local `clients` (11,470) is a read-mostly mirror with 0 wa-promoted leads. So post-fix the
promoted leads + recaps land local-only, invisible to the team.

**Antonello decision 2026-06-06: option B — writes must reach the Fly CRM.**
"senza oscurare nulla, tanto kita.balizero è internal" → CRM-derived records (lead record,
strategic_recap summary) MAY go to Fly. Raw wa-corpus stays local (Law 2).

## Constraints

- **Law 2 (OSINT)**: raw WhatsApp messages NEVER leave Pro. Only DERIVED, sanitized records
  (lead full_name/phone/notes-recap, 2-3 sentence strategic summary) go to Fly. The scripts
  already write only sanitized data (docstrings: "never raw snippets/log text", "no raw
  messages leave Pro").
- **No raw Fly Postgres password** (rotated; not held; must not invent). → write via backend API.
- **CLAUDE.md §9**: cache invalidation after every mutation → the backend API path already does
  `invalidate_cache` on create/update; direct-DB writes would skip it. API path is REQUIRED for
  correctness, not just auth.
- **No paid Anthropic** / standard bans unaffected.

## Backend gap

`POST /api/crm/clients` (create) and `PATCH /api/crm/clients/{id}` (update) require **JWT only**
(`Depends(get_current_user)`). Only `POST /api/crm/clients/{id}/ensure-drive-folder` accepts the
internal key via `Depends(get_current_user_or_internal)`. The wa-mirror scripts have the internal
key (`WA_MIRROR_INTERNAL_KEY`) but it cannot create/update clients.

## Design

### Part 1 — Backend: extend internal-key to create + update (auth change, L3)

1. Swap `Depends(get_current_user)` → `Depends(get_current_user_or_internal)` on:
   - `POST /api/crm/clients` (create_client)
   - `PATCH /api/crm/clients/{client_id}` (update_client)
2. When actor is internal (`auth_method == "internal_key"`, email `wa-mirror-internal@balizero.com`):
   - `created_by` / `updated_by` = `wa-mirror-internal@balizero.com` (clean audit trail).
   - **Bypass RBAC** on update (same as ensure-drive-folder already does for internal) — internal
     service is trusted; it must update any client it promotes/recaps.
3. **strategic_recap source fix (load-bearing):** the update endpoint currently hardcodes
   `strategic_recap_source = 'manual'` whenever `strategic_recap` is in the payload (L970-973).
   For the internal/automated actor this is WRONG — it would mark Ollama summaries as human-edited
   and break the "human edit takes precedence" rule. Change: when actor is internal, set
   `strategic_recap_source = 'automated'` (or accept an explicit `strategic_recap_source` field
   limited to internal callers, default 'automated'); keep 'manual' for JWT human actors.
4. **Human-precedence guard:** when actor is internal AND target row already has
   `strategic_recap_source = 'manual'`, the endpoint SKIPS the strategic_recap overwrite (returns
   the row unchanged for that field). Protects human edits regardless of script-side checks.
5. Behind a config flag `WA_MIRROR_INTERNAL_WRITE_ENABLED` (default **false**) so the auth surface
   only opens when explicitly enabled — reversible kill-switch.

### Part 2 — Scripts: read-Fly-state, write-Fly (consistency)

The read-local/write-Fly split has consistency hazards (dedup against stale local; manual-precedence
against stale local). Resolve by sourcing CRM STATE from Fly:

- **auto-promote**: read wa-corpus from LOCAL (Law 2) for candidate detection; but dedup/phone-match
  against **Fly** clients (via a read: backend `GET /api/crm/clients?phone=` or the read-only
  postgres-nuzantara MCP path is not available to a cron — use a backend search endpoint). Then
  CREATE/ENRICH via `POST /api/crm/clients` (internal key). Drive folder already via
  ensure-drive-folder (unchanged).
- **strategic-recap**: read wa-corpus + candidate clients from LOCAL for generation; write the recap
  via `PATCH /api/crm/clients/{id}` (internal key). The backend human-precedence guard (Part 1.4)
  is the real protection; the script's local "skip if manual" becomes best-effort.
- HTTP: `httpx` async, base `NUZANTARA_BACKEND_URL` (default https://nuzantara-rag.fly.dev), header
  `X-Internal-Key: $WA_MIRROR_INTERNAL_KEY`, timeout 30s, ret/backoff on 5xx, fail-soft per-row
  (one bad row must not abort the batch; audit jsonl records per-row outcome).
- The client `id` to PATCH: auto-promote returns the created/matched id; strategic-recap must map a
  local candidate to its **Fly** id (match by phone via the same search endpoint) — local id ≠ Fly id.

### Open question for panel

- Is a backend **search-by-phone** endpoint already internal-key-accessible, or do we need to extend
  one too? (auto-promote dedup + strategic-recap id-mapping both need read-by-phone from Fly.)
  Fallback: extend `GET /api/crm/clients` search to accept internal key (read-only, low risk).

## Rollout

1. Backend change behind `WA_MIRROR_INTERNAL_WRITE_ENABLED=false` → deploy (gate: import smoke +
   crm_clients pytest + rolling). No behavior change while flag off.
2. Refactor scripts; test against Fly with flag ON in a controlled single-row run (one known lead).
3. Flip flag ON; watch audit jsonl + Fly clients delta + cache.
4. Kill-switch: flag OFF reverts auth surface; scripts fall back to local-only (the 2026-06-06 fix).

## Risks

- **Auth surface**: internal key can now create/modify any client. Bounded: server-side Fly secret,
  internal CRM, audit actor tagged, flag-gated. If key leaks → mass client mutation (same leak
  surface as today, larger blast radius). Accept per Antonello (internal tool).
- **Duplicate leads** if dedup reads stale state — mitigated by reading Fly state for phone-match.
- **Overwriting human recaps** — mitigated by backend human-precedence guard (Part 1.4).
- **Cache staleness** — solved by using API path (invalidate_cache fires).
