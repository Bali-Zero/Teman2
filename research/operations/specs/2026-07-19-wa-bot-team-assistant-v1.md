---
date: 2026-07-19
domain: operations
client_case: none
sources:
  - apps/backend-rag/backend/app/routers/whatsapp_chat.py
  - apps/backend-rag/backend/services/integrations/wa_inbox_bot.py
  - apps/backend-rag/backend/services/whatsapp_identity.py
  - apps/backend-rag/backend/services/rag/agentic/prompt_builder.py
  - apps/backend-rag/backend/services/rag/agentic/orchestrator.py
  - apps/backend-rag/backend/services/rag/agentic/orchestrator_core.py
  - apps/backend-rag/backend/services/rag/agentic/orchestrator_context.py
  - apps/backend-rag/backend/services/rag/agentic/context_manager.py
  - apps/backend-rag/backend/app/routers/agentic_rag.py
  - team_members table (live Postgres, read via mcp__postgres-nuzantara__query)
---

# WA bot as team-member assistant — V1 (sender identity wired into the live bot path)

## 0. Why

The Zantara WhatsApp number (+62 821-3465-159) serves two audiences on one
number — clients and the Bali Zero team — but the live bot path never told
the RAG brain WHICH one it was talking to. `wa_inbox_bot.py` built the RAG
payload with `"user_id": f"whatsapp_{phone}"` and no profile
(`wa_inbox_bot.py:220-226`, pre-this-PR), so every WA sender looked identical
to the orchestrator: no owner, no team, no client — always the cold-lead
default. Meanwhile `backend/services/whatsapp_identity.py::resolve_sender_identity`
already classified owner/team/client/unknown correctly — it was just never
called from this path (wired only into a legacy channel). And
`prompt_builder.py` already had CREATOR_PERSONA/TEAM_PERSONA overlays — they
just never activated for WhatsApp senders.

V1 closes that gap: resolve identity, forward it, apply the persona. No new
features (check-in, CRM tools, per-member memory) — those are Phase 2,
parked below.

## 1. Ground (verified this session, file:line — re-verify before extending)

- `whatsapp_chat.py:1281-1316` — the Zantara Meta-inbox number routes to
  `process_meta_inbox_payload` (background task), which flows through
  `wa_outbox_worker.py` → `wa_inbox_bot.py::generate_bot_reply`. This is
  "Path B", the live path for this number (see `.claude/skills/bot/`
  corner §2 established truth #1).
- `wa_inbox_bot.py:220-226` (pre-PR) — the RAG payload had no profile.
  Post-PR: `generate_bot_reply` now calls
  `resolve_sender_identity(phone, pool)` and, when the role is
  `owner`/`team`, adds a `profile` key to the payload
  (`_profile_from_identity`).
- `whatsapp_identity.py` — `resolve_sender_identity(phone, db_pool)`
  precedence: env `WHATSAPP_OWNER_NUMBERS` → env `WHATSAPP_TEAM_NUMBERS`
  (override) → **NEW: `team_members` DB lookup** → `clients` DB lookup →
  `unknown`. Fail-safe by design: any exception (Postgres/Interface/OS/
  Timeout, or any other `Exception`) resolves to `{"role": "unknown"}`.
- `prompt_builder.py:204-230` (line numbers verified on disk this session;
  the mandate's ground note cited `backend/llm/prompt_builder.py` — that
  path does not exist, the real file is
  `backend/services/rag/agentic/prompt_builder.py`; `backend/llm/` holds
  `prompt_manager.py`, the versioned door `ZANTARA_MASTER_TEMPLATE` comes
  from) — computes `is_creator`/`is_team` from email heuristics
  (`"antonello"|"siano" in email` → creator; `"@balizero.com" in email` or
  `profile.role` contains `"admin"` → team). Persona overlay application at
  `:547-552` (`CREATOR_PERSONA`/`TEAM_PERSONA`, imported from
  `backend.prompts.zantara_core` — off-limits file, read-only, never
  edited by this PR).
- **The plumbing gap this PR had to close**: `context["profile"]` (the
  dict `build_system_prompt` reads) is NOT taken from the request body —
  it comes from `context_manager.get_user_context(db_pool, user_id, ...)`,
  a DB-keyed lookup by `user_id` (`orchestrator_context.py:29-118`,
  `context_manager.py:231-330`). For a WA sender, `user_id =
  f"whatsapp_{phone}"`, which never matches any `user_profiles` row — so a
  `profile` field added only to the wire payload would never reach
  `prompt_builder` without additional plumbing. `AgenticQueryRequest`
  (`agentic_rag.py:249-260`) had no `profile` field, and neither
  `orchestrator.process_query` nor `orchestrator_core.process_query_core`
  accepted one. **This PR threads it through, additively**: router →
  `orchestrator.process_query(profile=...)` →
  `orchestrator_core.process_query_core(profile=...)`, merged into
  `user_context["profile"]` immediately after `prepare_query_context()`
  returns (`orchestrator_core.py`, right after the parallel context/KG
  load, before gates/cache/ReAct). Every existing caller passes
  `profile=None` — fully backward compatible, verified by test
  (`test_process_query_core_no_profile_is_a_no_op`).
- **`team_members` table is overloaded** (verified live via
  `mcp__postgres-nuzantara__query`, 2026-07-19): 495 of its rows are
  portal-client identities with `role = 'client'`. Of those, **488 carry a
  `linked_client_id` and 7 do NOT** — so `linked_client_id IS NULL` is an
  UNSAFE filter (it would let those 7 client rows slip through as "team").
  Conversely, some genuine team rows (2 of 3 "Specialist Advisor" rows)
  DO carry a non-null `linked_client_id` — so the same filter would
  wrongly EXCLUDE real team members too. **Filter chosen:
  `LOWER(COALESCE(role,'')) <> 'client'`** — exact, correct on both sides
  (verified: `client` is the only role value that appears, all other 16
  distinct role strings, e.g. "Tax Lead", "Specialist Advisor", "Founder",
  are real team roles). Added `COALESCE(active, TRUE) IS TRUE` as a
  defense-in-depth filter for any future deactivated staff row (all rows
  are currently `active=true`, so this is a no-op today, not a witnessed
  bug fix).

## 2. What shipped (minimal, identity-gated)

1. **`whatsapp_identity.py`**: added a `team_members` DB lookup (exact
   normalized E.164 match on `whatsapp`, no fuzzy matching — same
   discipline as the existing `clients` lookup), inserted between the env
   team-number override and the `clients` lookup. Returns
   `{"role": "team", "team_member": <name>, "team_member_email": <email>}`
   on a DB hit (env-resolved hits keep the old, email-less shape — no
   behavior change there). Fail-safe behavior unchanged.
2. **`wa_inbox_bot.py`**: `generate_bot_reply` now resolves identity via
   `resolve_sender_identity(phone, pool)` and builds a `profile` dict
   (`_profile_from_identity`): `owner` → `{"role": "creator"}`, `team` →
   `{"role": "team", "name": ..., "email": ...}` (fields present only when
   the identity resolver returned them), `client`/`unknown` → `None`. The
   payload only gains a `"profile"` key when non-`None` — **the innocence
   contract**: client/unknown senders get byte-identical payloads to
   before this PR (proven by
   `test_client_and_unknown_payload_has_no_profile_key`, a full-dict
   equality assertion, and
   `test_identity_db_down_fails_safe_no_profile_key`).
   - **Deliberate scope decision**: `user_id` in the payload stays
     `f"whatsapp_{phone}"` for every identity, including team/owner. The
     task's grounding note said "use the member's email as user identity
     where appropriate" — that intent is satisfied via `profile.email`
     (which `prompt_builder.py` already reads into `user_email` for
     persona/personalization, `:213-215`), NOT by changing the `user_id`
     that keys conversation memory/facts persistence
     (`orchestrator.py::process_query` → `memory_handler.create_save_task`).
     Changing `user_id` would start attributing WA thread history to a
     real personal identity — that's the Phase-2 "per-member persistent
     memory" item below, which needs Zero's GO per the bot corner (F2/F3
     not started). V1 stays additive/reversible: turn off, and every
     sender reverts to exactly today's anonymous-phone behavior.
3. **`prompt_builder.py`**: widened the `is_creator`/`is_team` derivation
   (`:217-230`, post-edit) to check `profile.get("role")` explicitly
   (`"creator"` / `"team"`, case-insensitive) BEFORE falling back to the
   pre-existing email heuristics. When `profile.role` is absent or some
   other value (e.g. `"admin"`, `"Founder"`), the new branch is a no-op and
   every existing caller's behavior is provably unchanged (see innocence
   tests below).
4. **Plumbing (discovered necessary during grounding, not in the original
   3-file list, but required for the payload's `profile` to ever reach
   `prompt_builder`)**: `AgenticQueryRequest.profile: dict | None = None`
   (`agentic_rag.py`), forwarded through
   `orchestrator.process_query(profile=...)` →
   `orchestrator_core.process_query_core(profile=...)`, merged into
   `user_context["profile"]` (caller's fields win on key conflict, DB
   lookup's other fields survive). All three are additive/optional —
   confirmed no regression across 160 orchestrator + 33 router + 14
   prompt_builder unit tests (full run, see PR).

## 3. Innocence contract (what must NEVER change)

- `client`/`unknown` senders: RAG payload from `wa_inbox_bot.py` is
  byte-identical to pre-PR (no `"profile"` key at all).
- Identity resolution failure (DB down, any exception): resolves to
  `unknown` (whatsapp_identity.py's existing fail-safe design, unchanged),
  payload stays byte-identical.
- `profile.role` values other than `"creator"`/`"team"` (e.g. `"admin"`,
  `"Founder"`): the new explicit branch in `prompt_builder.py` is a no-op;
  legacy email heuristics run exactly as before.
- Every non-WA caller of `/api/agentic-rag/query` (website, webapp,
  Telegram, Instagram bridges that hit this endpoint): `profile` is absent
  from their request → `None` end-to-end → zero behavior change.
- 24h Meta window logic, `human_handling`, `wa_outbox_worker` claim/fence
  logic: untouched.

## 4. Tests (guilt + innocence, 3 files, all green)

- `backend/tests/unit/services/test_whatsapp_identity.py` (+8 new,
  16 total): team DB hit with email, env-override precedence over DB,
  **overload guard** (`role='client'` + matching `whatsapp` → NOT
  classified team), inactive-row exclusion, DB-miss fallthrough to
  `clients`.
- `backend/tests/unit/services/test_wa_inbox_bot.py` (+5 new, 35 total):
  owner/team env-resolved profile in payload, team DB-resolved profile
  with email, client/unknown byte-identical payload (full-dict equality),
  DB-down fail-safe byte-identical payload.
- `backend/tests/services/rag/agentic/test_prompt_builder.py` (+5 new,
  14 total): explicit `profile.role="creator"`/`"team"` activates the
  right persona (case-insensitive), unrelated `profile.role` value does
  NOT trip the new branch, absent `profile.role` still falls back to the
  pre-existing email heuristic.
- `backend/tests/services/rag/agentic/test_orchestrator_core.py` (+2 new,
  8 total): `process_query_core`'s profile merge (caller wins, DB fields
  survive) and no-op when `profile=None`.
- `backend/tests/unit/services/rag/agentic/test_orchestrator.py` (+2 new):
  `process_query`'s `profile` kwarg forwards unmodified to
  `process_query_core`.
- Full regression run: 160 passed/29 skipped (pre-existing skips,
  orchestrator suite), 33 passed (router suite), 14+162 passed
  (prompt_builder suite family) — zero new failures.

## 5. Phase 2 — parked, needs Zero's GO (NOT in this PR)

- **CRM scoped tools per `assigned_to`**: letting a team member's WA
  session query their own assigned clients/practices via tool-calling.
  Needs an explicit RBAC decision (which tools, what scope) — business
  decision, not an engineering one.
- **Per-member persistent memory**: today `user_id` stays
  `whatsapp_{phone}` even for resolved team members, so conversation
  memory/facts never attach to a real identity. Attaching them (via
  `user_id = member_email`) is a deliberate Phase-2 step, tracked in the
  bot corner (`.claude/skills/bot/SKILL.md` §1: "F2 (team check-in) NOT
  started ... F3 (member profiles) after F2").
- **wa-dashboard RBAC tables**: the operator console
  (`apps/wa-meta-inbox`) surfacing per-member identity/session data —
  no schema changes proposed here.

## 6. PII note

No real team phone numbers, names, or emails appear in this spec, the
diff, the tests, or the PR body — tests use fabricated numbers
(`+62 811-100-XXXX` block) and fabricated names/emails
(`Test Member Alpha`, `alpha.tester@balizero.com`, etc.). The
`team_members` schema/role-distribution facts above are aggregate counts
only (verified via read-only Postgres MCP), never individual identifying
rows.
