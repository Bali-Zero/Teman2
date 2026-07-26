---
date: 2026-07-20
domain: operations
client_case: internal-tooling
sources: 12
status: SHIPPED (flag OFF by default — arm via Fly secret is an operator step)
companion: research/operations/2026-05-23-wa-team-inbox-webapp.md
stacked_on: PR #2872 (agent/air-m5/backend-rag/wa-team-assistant, V1 sender identity)
adversarial_review: glm-5.2
adversarial_review_date: 2026-07-20
adversarial_review_verdict: "CLEAN — no privilege-escalation or authorization-bypass found; 1 NOTED reliability concern independently re-verified as a non-issue (see section below)"
---

# WhatsApp Team-Assistant Phase 2 — CRM scoped tools per member (read-only)

> Bali Zero team members query THEIR OWN clients/practices/deadlines from the Zantara WA
> bot (+62 821-3465-159). Zero GO 2026-07-20, memory
> `decision_wa_team_assistant_phase2_crm_go_2026_07_20.md`.

## 1. Scope

4 deterministic, read-only intents — **not free SQL**:

| # | Intent | Tool name | Source |
|---|---|---|---|
| a | My clients (name + practice count) | `team_my_clients` | `clients` LEFT JOIN `practices` |
| b | My practices + status | `team_my_practices` | `practices` JOIN `clients` |
| c | Expiring deadlines (KITAS/visa/passport/LKPM/SPT) | `team_my_deadlines` | UNION of `client_expiry_alerts_view` + `compliance_alerts` |
| d | Practice detail by client name (fuzzy, in-scope only) | `team_practice_detail` | `practices` JOIN `clients` (ILIKE + assigned_to in the SAME query) |

Out of scope: writes, cross-member lookups, free-text SQL, anything not
covered by these 4 shapes.

## 2. RBAC chain (reuses existing CRM RBAC — no new admin list)

```
WA phone
  -> whatsapp_identity.resolve_sender_identity()   (V1, existing)
     team_members WHERE whatsapp = $1 AND role <> 'client' AND role <> ''
  -> profile = {"role": "team", "email": ..., "name": ...}
              | {"role": "creator"}                (owner numbers)
  -> team_crm_tools.resolve_team_crm_scope(profile)
     - role == "creator"          -> is_admin=True
     - role == "team" AND
       is_crm_admin({"email": e}) -> is_admin=True   (SAME source as REST CRM:
                                                        backend/app/utils/crm_utils.py
                                                        _crm_admin_emails() =
                                                        settings.admin_emails_set
                                                        | CRM_EXTRA_ADMIN_EMAILS)
     - role == "team", not admin  -> is_admin=False, email=<their email>
     - role == "team", no email   -> is_admin=False, email=None -> IDENTITY_UNRESOLVED,
                                       zero DB access (env-override sender,
                                       WHATSAPP_TEAM_NUMBERS, carries no email)
     - anything else / no profile -> None -> tools return NOT_AVAILABLE
  -> SQL: LOWER(assigned_to) = LOWER(email)   [scoped tools]
          or no WHERE clause                 [admin]
```

This is the **exact** filter pattern `backend/services/crm_shared_memory.py`
already uses for the REST CRM surface — no parallel RBAC system introduced.
VASSAL (`tool_authorizer.py`/`team_agent_config.py`) was evaluated and
rejected: it is a separate, Telegram-only allowlist with its own admin
source and no row-level `assigned_to` scoping (`_check_client_scope` is an
explicit Phase-2 no-op scaffold there).

## 3. Trust boundary — inherits the 2026-07-20 security fix, does not duplicate it

An adversarial review on the V1 base (commit `078ade8236`,
`fix(whatsapp): close profile-based persona escalation`) found that
`AgenticQueryRequest.profile` was previously honored from ANY caller of
`/api/agentic-rag/query` — a client could self-declare `role=team` in the
request body. The fix: `agentic_rag.py` now forwards `request.profile` into
`query_kwargs["profile"]` **only** when
`current_user.get("role") in ("internal", "admin")`. The WA bot's own hop
authenticates via `X-Internal-Key` -> `HybridAuthMiddleware` -> pseudo-user
`role="internal"`, so V1's flow (and this Phase 2 extension) both still work.

Phase 2 tools introduce **zero new trust surface**. They consume
`state.caller_profile`, which is stamped 1:1 from the SAME
`user_context["profile"]` that already passed through the fix above —
there is no second code path that lets a caller set `profile`/`role`. Two
independent layers enforce this:

1. **Construction-time hard-absence.** `create_agentic_rag()` only appends
   the 4 tools to the orchestrator's fixed tool list when
   `WA_TEAM_CRM_TOOLS_ENABLED` is truthy. The Gemini function-declaration
   schema is built ONCE at construction (no existing per-request filtering
   mechanism was found after tracing `llm_gateway.py::send_message` ->
   `_send_with_fallback` -> `_call_model` -> `_build_config` — introducing
   one was judged out of proportion for a narrowly-scoped feature and was
   NOT done). Flag off = tools do not exist in the schema for **any**
   caller, team or otherwise.
2. **Execution-time self-gate.** When the flag is on, each tool receives a
   server-injected `_caller_profile` kwarg — the same pattern
   `tool_executor.py` already uses for `_user_id` (injected AFTER the
   authorizer runs, never LLM-supplied, never mixed into user-controlled
   arguments). A caller_profile that isn't team/creator (or admin) yields
   `NOT_AVAILABLE`/`IDENTITY_UNRESOLVED` with zero DB access.

## 4. Cache / PII discipline

Team-mode answers must never be written to, or served from, shared cache
(FAQ cache and semantic cache are process-wide, keyed on query text —
a client CRM lookup rendered by one member's cache entry could leak to a
different member or a client-facing surface).

`OrchestratorCore.process_query_core` now computes
`_team_mode = is_team_or_creator_profile(user_context.get("profile"))`
right after the existing gates check, and skips BOTH `check_faq_cache` and
`check_semantic_cache` when `_team_mode` is true. Every other caller
(profile=None, or any other role) is byte-identical to pre-Phase-2
behavior — proven by the innocence test
`test_innocence_no_profile_still_hits_both_caches` and
`test_innocence_client_profile_role_still_hits_both_caches`.

No client name, email, or practice detail is logged — `logger.info` calls
in `team_crm_tools.py` carry only `{"admin_scope": bool, "result_count": int}`.

## 5. Flag

`WA_TEAM_CRM_TOOLS_ENABLED` — env bool, **default OFF**. Read once per
`create_agentic_rag()` call via `is_team_crm_tools_enabled()` (same
truthy-string parsing convention as `WA_INBOX_BOT_AUTOREPLY`). Flag OFF is
proven byte-identical for team senders too (not just client/unknown) by
`test_flag_off_team_crm_tools_are_absent` / `test_flag_unset_defaults_to_absent`.

## 6. Wiring (thread the profile from router to tool)

```
AgenticQueryRequest.profile                      (router, V1, gated by role=internal|admin)
  -> orchestrator.process_query(profile=...)
  -> OrchestratorCore.process_query_core(profile=...)
  -> user_context["profile"] = {**existing, **profile}
  -> state.caller_profile = user_context.get("profile")   [stamped post-routing, NEW]
  -> execute_react_loop(..., caller_profile=getattr(state, "caller_profile", None))
  -> tool_executor.execute_tool(..., caller_profile=...)
  -> arguments["_caller_profile"] = caller_profile          [server-injected, NEW]
  -> tool.execute(**arguments)                              [team_crm_tools.py reads it]
```

Streaming path (`execute_react_loop_stream`,
`orchestrator_streaming_core.py`) deliberately NOT touched — the WA bot
only calls the non-streaming endpoint.

## 7. Data sources grounded against live schema

Verified via read-only Postgres MCP (`nuzantara_readonly`) before writing SQL:

- `client_expiry_alerts_view` — Postgres VIEW unioning
  `clients.passport_expiry`, `client_family_members` (passport/visa), and
  `documents.expiry_date`. Columns used: `entity_name`, `client_id`,
  `client_name`, `document_type`, `expiry_date`, `days_until_expiry`,
  `alert_color`, `assigned_to`.
- `compliance_alerts` — columns `alert_id`, `client_id`, `category`,
  `severity`, `status`, `deadline`, `days_until`, `message_en`. Joined to
  `clients c ON c.id = ca.client_id` for the `assigned_to` filter (no
  `assigned_to` column on the table itself); filtered `status <> 'resolved'`.

Both are the same services `backend/app/routers/crm_enhanced_alerts.py` and
`backend/app/routers/compliance_alerts.py` already query for the REST CRM
surface — reused, not reinvented.

## 8. Edge cases (guilt/innocence tested)

- **Fuzzy lookup cannot escape scope**: `team_practice_detail` puts
  `c.full_name ILIKE $1` and `LOWER(c.assigned_to) = $2` in the SAME query
  — a member searching a colleague's client by name gets zero rows, not an
  error (matches the "not found" shape a legitimate zero-result search
  would also produce — no scope-probing oracle).
- **Team sender with no email** (resolved via `WHATSAPP_TEAM_NUMBERS` env
  override, which carries no email): fails safe to
  `IDENTITY_UNRESOLVED`, zero DB access — never "show everything" or crash.
- **Admin** (`zero@balizero.com`, `antonellosiano@gmail.com` /
  `antonellosiano@balizero.com`, `asya@balizero.com`, plus
  `CRM_EXTRA_ADMIN_EMAILS`): unscoped query, same as REST CRM admin path.
- **Client/unknown sender**: V1's `_profile_from_identity` already omits
  the `profile` key entirely for these — `resolve_team_crm_scope(None)`
  returns `None`, tool replies `NOT_AVAILABLE`. Also unreachable in
  practice because of layer 1 (flag) and layer 2 (self-gate) above.
- **Flag OFF**: no tool present in the schema — team sender's query is
  answered exactly as V1 would answer it (no Phase-2 behavior at all).

## 9. Tests (66 new/updated, `apps/backend-rag/backend/tests/unit/services/rag/agentic/`)

- `test_team_crm_tools.py` — scope resolution (pure logic), per-tool
  guilt+innocence (SQL text + params contain the right scope), the fuzzy
  cross-member guilt fixture, PII-in-logs check via `caplog`.
- `test_create_agentic_rag_team_crm_flag_gate.py` — flag off/unset/on,
  and flag-on innocence (pre-existing tools still present).
- `test_tool_executor.py` (+3) — `_caller_profile` injection only when
  non-empty.
- `test_process_query_core_team_crm_wiring.py` — cache-skip for
  team/creator, cache-hit innocence for everyone else, `state.caller_profile`
  stamped correctly.

All green post-rebase onto `078ade8236` (131 tests across the Phase 2 files
+ `test_whatsapp_identity.py` + `test_agentic_rag_optional_auth.py`, the
security-fix's own coverage).

## 10. Rollout plan

1. **Ship** (this PR): flag OFF by default. Merges with zero behavior
   change for any caller — verified by the flag-off/unset tests.
2. **Deploy**: `fly deploy --strategy rolling` on `nuzantara-rag`. No
   migration, no schema change — pure application code.
3. **Prove-live** (flag still OFF): confirm the WA bot answers exactly as
   before for Zero's own number and a client-role sender (regression check,
   not a new-feature check).
4. **Arm** (operator step — Zero/Antonello only, credential-adjacent):
   `fly secrets set WA_TEAM_CRM_TOOLS_ENABLED=true -a nuzantara-rag`. This
   is the ONE step this PR does not self-execute — flipping a Fly secret is
   an operator action per CLAUDE.md §13 (credential/infra, not a
   reviewable diff), NOT a business-decision veto on the code itself.
5. **Prove-live** (flag ON): Zero's own WA number (`creator` role, admin
   scope) queries "quali sono i miei clienti" -> gets the full list;
   a pilot team member's number queries the same -> gets only their
   `assigned_to` rows. Verify a cross-member client name returns "not
   found", not another member's data.
6. **Rollback**: `fly secrets set WA_TEAM_CRM_TOOLS_ENABLED=false` — no
   redeploy required, tools vanish from the schema on next process
   restart/cold-start (Fly secrets trigger a restart).

## Adversarial review

Reviewer: GLM 5.2 (`claude-sonnet-4-6-glm`, cross-family, R1 gate — Codex was
quota-exhausted at review time, `retry Jul 25 2026`; cascade fell through to
the next seat per CLAUDE.md §5, `GLM 5.2 → Kimi K3 → Codex`), 2026-07-20.

Given the full content of `team_crm_tools.py` plus the diff for
`tool_executor.py`/`orchestrator_core.py`/`reasoning.py`/`__init__.py`, and
explicitly told to apply the same scrutiny that found the real
privilege-escalation bug on the V1 PR (#2872), instructed to actively try to
break the access control rather than summarize what the code claims to do.

**Verdict: CLEAN.** Findings by category:

1. **LLM/caller influence on RBAC scope — CLEAN.** `parameters_schema` for
   all 4 tools exposes only `limit`/`status`/`days_ahead`/`client_name` —
   never `email`/`assigned_to`/`is_admin`/`profile`. Traced the full server
   side of the chain: `orchestrator_core.py` stamps `AgentState.
   caller_profile` from `user_context["profile"]` (itself only populated
   for `current_user.role in ("internal", "admin")` per the V1 fix) →
   `reasoning.py` forwards it into `execute_tool(caller_profile=...)` →
   `tool_executor.py` injects it as `_caller_profile` into `arguments`
   AFTER the authorizer runs (never mixed with LLM-supplied args, mirrors
   the existing `_user_id` pattern) → `_scope_from_kwargs()` reads it from
   kwargs only, never from `parameters_schema`.
2. **SQL `assigned_to` filter on all 4 tools — CLEAN.** Every tool's
   `execute()` guards the filter with `if not scope.is_admin:` before
   adding `LOWER(c.assigned_to) = $N` (or unqualified `LOWER(assigned_to)`
   for the single-table `client_expiry_alerts_view` query) to the SQL.
3. **Feature-flag re-evaluation — CLEAN.** `is_team_crm_tools_enabled()` is
   read once at `create_agentic_rag()` construction time (tools absent from
   the Gemini schema entirely when off) AND re-checked defensively inside
   `_scope_from_kwargs()` per call — the second check is stricter, not a
   bypass path.
4. **Fuzzy ILIKE in `team_practice_detail` — CLEAN.** The `ILIKE` clause and
   the `assigned_to` filter are combined in the SAME query — a non-admin's
   fuzzy search can only ever match their own rows; a colleague's client
   simply returns empty, not leaked data.
5. **Other injection/authorization gaps — CLEAN.** All queries parameterized
   (`asyncpg` `$N` placeholders, no string concatenation); cache-skip for
   team/creator senders confirmed in the diff; tool descriptions don't leak
   system internals.

**NOTED (re-verified independently, found to be a non-issue — not a
bug):** GLM flagged the expiry-alert query's `LOWER(assigned_to)` (no table
alias) as a potential "column ambiguous or missing" reliability risk. Traced
this myself: the query selects `FROM client_expiry_alerts_view` alone (no
join, no alias in that branch) — `assigned_to` is unambiguous there by
construction. Confirmed the view exposes `assigned_to` as a real column by
reading its `CREATE OR REPLACE VIEW` definition (`apps/backend-rag/scripts/
apply_migration_033.py:210-292`, four branches of the view's UNION each
select `c.assigned_to`). Not a bug — GLM's own report already correctly
scoped this as non-exploitable (worst case: a query error, never excess
access); the independent trace additionally rules out even the reliability
concern.

No CONFIRMED findings. No code changes made as a result of this review —
the implementation as committed already closes every angle this review
checked, including the exact class of bug (caller-influenced persona/scope)
that a prior review on the stacked V1 PR found real and exploitable.
