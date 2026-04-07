# VASSAL Phase 2 → Phase 3 Handoff

**Date:** 2026-04-07
**Author:** Phase 2 implementer (Opus 4.6 1M)
**Reader:** Phase 3 implementer (fresh session)
**Plan reference:** `~/Desktop/VASSAL_PLAN_V8.md`
**Memory rule active:** `feedback_no_pragmatic_divergence` — read it before any "accept divergence for now" decision.

---

## (a) Phase 2 discoveries that differ from v8 plan

1. **Critical gap vs v7/v8 §4.2:** the agentic ReAct loop registry has only **9 tools** (`vector_search`, `pricing`, `team_knowledge`, `knowledge_graph`, `calculator`, `vision`, `image_generation`, `web_search`, `timesheet`). Zero CRM tools. The plan's `CLIENT_ID_TOOLS` list (`get_client`, `update_client`, etc.) targets the `nuzantara-mcp/` stdio package — NOT the agentic loop. Phase 2 was scoped as "Strada B" (scaffolding only) precisely because of this.
2. **`team_agent_config` was misaligned with the runtime**: the original allowlists named MCP CRM tools but never the runtime tools. Without the Phase 2 v8 fix, enforcing the authorizer naively would have denied EVERY tool to non-admin users (Damar/Adit). See "Decisions" §1 below.
3. **Two source of truth for "admin"** is real: `crm_utils.CRM_ADMIN_EMAILS` (used by REST CRM routers) and `team_agent_config.TEAM_AGENTS` (used by the agentic loop) disagree on who is admin. Damar is `CRM_ADMIN_EMAILS` admin but `team_agent_config` `ROLE_VISA_SPECIALIST` (`scope=assigned`). Asya/Ruslana are in `PRACTICES_FULL_VIEW_EMAILS` but absent from `TEAM_AGENTS` (so `get_agent_role` returns None and they get 403 on `/workspace-stream`). Tracked for resolution in **VASSAL_PLAN_V8 Phase 7** ("Policy Source Unification via shared YAML"). Phase 3 must NOT extend this divergence.
4. **`TimeSheetTool` accepts user-supplied `email`**: an authorized agent can technically clock in/out for ANY team member by passing a different email. Out of scope for Phase 2 (in-tool scope, not in authorizer). Annotated in `team_agent_config.py` next to the executive_consultant entry. Hardening planned for Phase 6.

## (b) Architectural decisions Phase 3 MUST respect

1. **Opzione E (explicit role expansion)** chosen over Opzione P (permissive fallback): the runtime tools are now listed explicitly in `ROLE_VISA_SPECIALIST` and `ROLE_EXECUTIVE_CONSULTANT` allowlists with comments `# Phase 2 v8: ...`. **Opzione P was rejected** because `KNOWN_TO_CONFIG ∩ runtime_tools = ∅` would have made the authorizer a no-op end-to-end (Codex's "scaffolding vuoto = worst of both worlds" critique from v8 brainstorming). Phase 3 should not regress this — adding new runtime tools must update the explicit allowlists.
2. **Propagation pattern: `state.agent_role` (Opzione 2)**, NOT contextvars and NOT extra params on every signature. The router sets `state.agent_role` via the chain `agentic_rag.py → orchestrator.stream_query(agent_role=...) → stream_query_core → prepare_react_execution → state.agent_role = agent_role`. The 2 `execute_tool` call sites in `reasoning.py` read `getattr(state, "agent_role", None)` and forward. Phase 3 confirmation gates must extend this same pattern, not introduce a parallel propagation channel.
3. **Backward compat is contractual**: `agent_role=None` is legacy `/stream` (auth-optional) and MUST always passthrough as ALLOWED. Phase 3 confirmation gates must respect the same convention — `None` agent_role never asks for confirmation.
4. **Authorizer is async-only**: `ToolAuthorizer.authorize()` is `async def` even though Phase 2 has no `await` inside. This is intentional infrastructure: Phase 3 needs to await Redis state and `asyncio.Future` for confirmation, and we wanted to avoid a second refactor of `tool_executor.execute_tool()` signature.
5. **`workspace_page` injection moved inside `[AGENT CONTEXT]` block** in `_inject_agent_context_prefix` (Phase 2 hardening). It is no longer concatenated as a leading sentence to the user query — that was prompt-injectable. Phase 3 MUST NOT revert this.
6. **`crm_utils` is intentionally untouched**: the authorizer lane is the agentic ReAct loop only. Phase 3 must not import `crm_utils.is_crm_admin` or duplicate `verify_client_access` logic into the authorizer. Resolution belongs to Phase 7 unification.

## (c) tool_authorizer state — interface contract for Phase 3

**Module:** `backend/services/agents/tool_authorizer.py` (304 lines)

**Public surface (Phase 3 MUST NOT break):**

```python
class AuthDecision(str, Enum):
    ALLOWED = "allowed"
    DENIED = "denied"
    NEEDS_CONFIRMATION = "needs_confirmation"

@dataclass(frozen=True)
class AuthResult:
    decision: AuthDecision
    reason: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    @property
    def is_allowed(self) -> bool: ...
    @property
    def is_denied(self) -> bool: ...
    @property
    def needs_confirmation(self) -> bool: ...
    @classmethod
    def allow(cls, args=None) -> AuthResult: ...
    @classmethod
    def deny(cls, reason: str, args=None) -> AuthResult: ...
    @classmethod
    def confirm(cls, reason: str, args=None) -> AuthResult: ...

class ToolAuthorizer:
    def __init__(self) -> None: ...   # Phase 3: add confirmation_service param here
    async def authorize(
        self,
        user_email: str | None,
        agent_role: AgentRole | None,
        tool_name: str,
        args: dict[str, Any],
    ) -> AuthResult: ...
```

**Current `NEEDS_CONFIRMATION` handling:**
- `AuthResult.confirm()` exists as a classmethod
- `_check_requires_confirmation()` is a no-op stub returning `None` (AgentRole has no `requires_confirmation` field yet — Phase 3 must add it)
- `tool_executor.execute_tool()` defensively handles `auth_result.needs_confirmation` by treating it as DENIED with a clear error message ("confirmation gates are not active yet"). When Phase 3 wires the real confirmation service, that branch must replace the defensive deny with the actual `await confirmation_service.request_and_wait(...)` call.

**Audit log format (downstream log shippers grep this):**
```
tool_authz decision={allow|deny} user={email} role={role_id} scope={client_scope} tool={tool_name} reason={text}
```
Stable. Don't change without coordinating downstream consumers.

## (d) Files Phase 3 MUST read as baseline

Required reads in this order:

1. **`backend/services/agents/tool_authorizer.py`** — full module, especially the docstring and the `_check_requires_confirmation` stub
2. **`backend/services/agents/team_agent_config.py`** — `AgentRole` dataclass + `ROLE_*` constants. Phase 3 will add `requires_confirmation: list[str]` field here
3. **`backend/services/rag/agentic/tool_executor.py`** — the `execute_tool()` chokepoint and how it currently handles the defensive `needs_confirmation` branch
4. **`backend/services/tools/definitions.py`** — `AgentState.agent_role` (typed `Any | None` to avoid coupling)
5. **`backend/services/rag/agentic/reasoning.py:373-380` and `:1197-1205`** — the 2 `execute_tool` call sites that pass `agent_role=getattr(state, "agent_role", None)`. Phase 3 must NOT bypass these
6. **`backend/app/routers/agentic_rag.py:_inject_agent_context_prefix` and `stream_workspace_agent`** — the workspace endpoint and how it sets `agent_role` on the orchestrator chain
7. **`backend/tests/unit/agents/test_tool_authorizer.py`** — 24 tests covering the contract above. Phase 3 should add tests for confirmation flow without breaking these
8. **`~/Desktop/VASSAL_PLAN_V8.md` §16.4** — pragmatic divergence anti-pattern callout
9. **MOS memory `feedback_no_pragmatic_divergence`** — apply BEFORE accepting any "for now" decision

## (e) Hooks prepared for Phase 3

These exist already and Phase 3 should use them (don't refactor them):

- **`AuthDecision.NEEDS_CONFIRMATION`** + **`AuthResult.confirm()`** — full enum value and helper, ready
- **`ToolAuthorizer._check_requires_confirmation(user_email, agent_role, tool_name, args) -> AuthResult | None`** — empty stub, ready to fill in. Returns `None` today; Phase 3 fills it with `if tool_name in agent_role.requires_confirmation: return AuthResult.confirm(...)`
- **`AgentState.agent_role`** — already carries the `AgentRole` from router → react loop. Phase 3 confirmation service can use the same vehicle for confirmation correlation IDs (or, better, add a separate `state.confirmation_request_id` field next to it)
- **`tool_executor.execute_tool` defensive `needs_confirmation` branch** (lines around 219–230 in current file) — drop-in replacement point. Replace the "treating as DENIED" log + return with the actual await
- **`AuthResult.args`** — already plumbed through to `tool.execute(**args)` after the authorizer call. Phase 3 confirmation flow can mutate args if the user approves with modifications
- **Stateless authorizer instance `_authorizer = ToolAuthorizer()`** at module level in `tool_executor.py`. Phase 3 will replace this with a per-app singleton built in `service_initializer.py` that takes `confirmation_service` as a constructor arg. The migration is one line.

## (f) Tech debt to remember

1. **`test_get_orchestrator_reuses_existing` is preexisting failing on main** — not Phase 2's fault, was already broken in Phase 1. Coroutine never awaited (`get_orchestrator` is async but the test calls it sync). Phase 3 CI may flag it. Don't fix as part of Phase 3 scope unless directly asked.
2. **`test_trimodal_rrf::test_empty_all` preexisting failing** — `HybridSearchService` lacks `reciprocal_rank_fusion_trimodal` method (only has `reciprocal_rank_fusion`). Test/code drift, not Phase 2's fault.
3. **TimeSheetTool email spoofing** — see (a)4. Phase 6 hardening item, not Phase 3.
4. **Two source of truth for "admin"** (`crm_utils` vs `team_agent_config`) — Phase 7 unification. Phase 3 must not extend it.
5. **Working tree pollution from parallel sessions**: at the time of Phase 2 closing, the working tree contained 50+ files modified by other parallel Claude sessions (LLM tweaks, NLM evaluator state, visa-oracle, lkpm, war-room). Phase 3 MUST run `git status --short <specific_file>` on every Phase 2/3 file before editing, to verify integrity. Do NOT use `git stash` to "isolate" — tried it once during Phase 2, it stashed my actual Phase 2 changes by accident.
6. **Operational lesson — verify before catastrophizing**: during Phase 2 implementation I once hallucinated that all my modifications had been reverted by a parallel session, when in reality they were all live in the working tree. Always run `git status --short <file>` and `grep -n <marker> <file>` directly before assuming a recovery is needed. Don't construct a recovery narrative from indirect signals.
7. **Phase 2 v8 entries in `team_agent_config.py`**: each runtime tool added to non-admin allowlists has a `# Phase 2 v8: ...` comment. Phase 6 should sweep these and decide whether to keep them or move them into a YAML policy file (Phase 7).

---

## Phase 2 deliverables — final state

| Item | Location | Status |
|---|---|---|
| `tool_authorizer.py` | `backend/services/agents/` | ✅ 304 LOC |
| `tool_executor.py` integration | `backend/services/rag/agentic/` | ✅ Authorizer chokepoint, defensive NEEDS_CONFIRMATION branch |
| `state.agent_role` propagation | `definitions.py`, `orchestrator*.py`, `reasoning.py` | ✅ End-to-end wired |
| Allowlist explicit expansion | `team_agent_config.py` ROLE_VISA + ROLE_EXEC | ✅ 7 read + 1 write tool added per role |
| `workspace_page` prompt-injection fix | `agentic_rag.py:_inject_agent_context_prefix` | ✅ Embedded inside [AGENT CONTEXT] block |
| Unit tests | `tests/unit/agents/test_tool_authorizer.py` | ✅ 24/24 pass |
| Phase 1 regression | `test_confidence.py` + `test_agentic_rag_optional_auth.py` | ✅ 26/26 pass (50 total Phase 1+2) |

**Diff stat (Phase 2 only, excluding parallel-session pollution):**
- 1 new file: `tool_authorizer.py` (304 LOC)
- 1 new test file: `test_tool_authorizer.py` (~330 LOC)
- 7 modified files for authorizer wiring + workspace_page hardening + role allowlist expansion

Estimate v7 was ~400-500 LOC for Phase 2. Actual: ~700 LOC including tests. ~1.5x — within the "expect 1.5-2x v7 estimates" projection from Phase 1 review.
