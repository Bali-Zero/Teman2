# CLAUDE.md — Nuzantara Project Context

> **Read `SYMBIOSIS.md` first.** It governs this entire ecosystem.
> **Before building anything new, read `VADEMECUM.md`.** Operative checklist.
> **Atlas:** [`INDEX.md`](INDEX.md) — where every organ/tissue/nerve lives.

---

# Part A — Agent Directives

## 1. Machine & Reachability

| Machine | User | Hostname | Role | RAM |
|---|---|---|---|---|
| **Air-M5** | `balizero` | `Air-M5` | Dev workstation PRINCIPALE interattiva, leggera — no daemon/cron/Ollama H24 | 24GB M5 |
| **Pro** | `nuzantara` | `Nuzantara` | Dev primario, interactive Claude Code; workhorse H24 (176 daemon, modelli 32B) | 48GB M4 Pro |
| **Mini-Pro2** | `nuzantara` | `Mini-Pro2` | Server H24, Ollama dedicato, cron pesanti | 24GB M4 Pro |

- `whoami=nuzantara` su Pro/Mini, `balizero` su M5 (home `/Users/balizero/` — path-aware scripts mandatory); distinguish via `hostname`. SSH alias `ssh pro` / `ssh mini` / `ssh air` (Tailscale `100.93.236.6` for Mini, `100.107.22.111` for Pro from Mini).
- First-response prefix: `[Pro]`, `[Mini]`, or `[Air]`.
- **Air decommissioned 2026-05-05** — handed off to Ari/Bali Zero. Historical references in code/scripts are archaeology, NOT active.

## Agent Worktree Discipline (2026-05-24)

OGNI agent session (subagent dispatch / cron-spawned claude / parallel Claude Code window) DEVE girare sotto `.worktrees/<lane>-<task-id>/` creato via `scripts/agent_start.py`. Il main checkout `~/nuzantara` resta read-only per agent — riservato a operator interactive + cicatrix hotfix.

Quick start: `python scripts/agent_start.py --lane <X> --task-id <Y>` → cd output path → spawn agent. Kill switch `AGENT_BROKER_ENABLED=false`. Runbook: `docs/runbooks/agent-worktree-broker.md`. SOTA panel reference: `research/operations/2026-05-24-sota-multi-agent-repo-architecture-synthesis.md`.

## 2. Behavior & Autonomous Ops

**DO NOT ask the user to write code.** Act first, ask if blocked. Use `Edit`/`Write`/`Bash` without asking permission.

**No phantom operator lane** (Zero, 2026-07-06: *"io sono te — non c'è nessun operatore"*). Sessions ARE the operator for all repo/infra work, on every machine. Never park work behind a waiting-for-human fence: investigate dirty/anomalous state (whose is it? runtime-state? live sibling? residue?) and handle it — "alive" is verified (processes, mtime, file nature), never presumed. The ONLY true operator-only categories are: physical device actions, GUI-only surfaces (interactive logins, GitHub settings, external-UI paste), TCC grants, consents/credentials only the human holds, `~/.claude/hooks/` control-plane one-liners (host_boundary stays hard by design), and business decisions (Legge 5). In the PENDING-ARMS ledger these MUST be declared as `operator[<category>]`; any bare `operator` owner is flagged PHANTOM-OPERATOR by `scripts/pending_arms_report.py` (CI-enforced: `immune-enforcement.yml` strict-phantom gate + `test_real_ledger_has_zero_phantom_operator`). Sibling discipline (#5) still holds toward LIVE sessions' work. Reference: memory `feedback_no_operator_lane_io_sono_te_2026_07_06`.

**⚡ SHIP-LIFECYCLE OWNERSHIP (HARD RULE — Zero, 2026-07-16: *"tu mergi fai review armi deploy testi. il codeowner non lo fa, non lo sa fare"*).** **THE SESSION DOES IT ALL: REVIEW → MERGE → ARM → DEPLOY → PROVE-LIVE. THE CODEOWNER DOES NOT MERGE, DOES NOT REVIEW, DOES NOT DEPLOY — BY DESIGN.** Never park a PR on "waiting for the codeowner's review/merge"; never end a mandate at "attende merge". Concretely: (1) arm `gh pr merge --auto --squash` at PR-open on every L2 feature PR — "client-facing/sensitive data" is NOT an exception: sensitivity raises the rigor of the ADVERSARIAL gate (generator≠grader — the diff's author never gates its own diff), it never moves the merge to a human; (2) post-merge, the session runs the deploy and apply steps itself (dry-run → apply → verify), per §11; (3) "done" is declared only after PROVE-LIVE on EVERY consuming surface (consumer-map first — memory `feedback_merged_is_not_live_consumer_map_first_2026_07_16`); (4) the codeowner keeps ONLY: business decisions (Legge 5), consents/credentials only the human holds, physical/GUI/TCC actions; (5) the auto-merge-OFF exceptions (guardrail hooks, DB migrations, force-push class — per `feedback_arm_automerge_default_not_leave_to_operator`) still get merged by the SESSION after their specific gates, never by the codeowner. Reference: memory `feedback_session_owns_full_ship_lifecycle_2026_07_16`.

**Master loop (2026-07-02)**: skill **`modus`** (`.claude/skills/modus/`) governs every non-trivial mandate end-to-end — TRIAGE gears (1 liscio / 2 standard / 3 profondo) → GROUND → DESIGN → BUILD → VERIFY → SHIP+ARM → PROVE-LIVE → ALIGN-FLEET → CLEAN → CAPTURE. It absorbs `stadio-zero` (entry gate) and `sota-architecture-loop` (design) as stages; **`opus-mythos` is superseded** (its deep/wide TAC patterns = modus Gear 3). W81 ledger: `.claude/skills/modus/PENDING-ARMS.md` · loop scar-file: `AMENDMENTS.md` · self-refinement: `infra/workflows/modus-bench.js` (operator-gated, on demand).

Read `AUTONOMOUS_OPS.md` (L2 active 2026-04-21) before: `git push`, PR ops, deploy, `fly ssh`, shared-state changes. Check "active since" date — if stale >30 days, conservative fallback. **User's veto is NOT the safety layer** — guardrails in that file are.

**Federation Orchestrator triggers** (`python scripts/federation_orchestrator.py "task"`):

| Trigger | Dispatch | Why |
|---|---|---|
| KBLI, visa, normativa | Gemini `search` | Claude hallucinates regulations |
| Refactor 3+ app | Gemini `explore` | 1M ctx maps dependencies |
| Grounding / Oracolo | NotebookLM `oracolo` | NB-1 ground truth |
| Alembic migration | Codex `sandbox` | Tests upgrade+downgrade |
| Pre-deploy Fly.io | Gemini `redteam` | Mai deploy senza red team |
| Fix dependencies.py / service_initializer | Codex `sandbox` | Import chain SPOF |

**Preflight SDD**: 3+ file/L1 · dependencies.py + migration + KBLI/visa + pre-deploy/L2 · auth/billing/RAG/L3.
`./scripts/ai-dispatch.sh preflight-{l1,l2,l3} "desc"`. Escape `SKIP_PREFLIGHT=1`.

**Escalations**: check `shared/escalations_pro.jsonl` + `~/.agent/decisions/claude_tasks/` at session start. HIGH first.

## 3. Memory (MOS — Memory Operating System)

SessionStart hook auto-loads last 5 memories (importance ≥7). Manual CLI `~/.claude/scripts/mem`:

| Cmd | Use |
|---|---|
| `mem recent` | Ultimi entry importanti |
| `mem query "txt"` | FTS5 search |
| `mem save <type> "txt" <importance>` | Save (types: decision/discovery/fact/unresolved) |
| `mem entities "name"` | Cerca entità |
| `mem sessions` / `mem stats` | History/metrics |

**Regola**: `mem` PRIMA di `notebook_query`. NLM solo per dominio o cross-query.

**Salvataggio proattivo (OBBLIGATORIO)** — `mem save` IMMEDIATAMENTE quando: decision (importance 8-10) · discovery/fact (7-8) · unresolved (5-6). **NON chiedere all'utente. Salva e basta.**

## 4. Language Protocol

User writes **colloquial Italian** — translate to precise technical action internally, respond in Italian. Never ask "what do you mean?" — infer from codebase. Ambiguous? Pick most likely + state assumption in 1 line.

**Owner**: Zero (codename). Real name PRIVATE. Italian with owner, client's language otherwise.

**Email language to team**: Bahasa Indonesia for all `@balizero.com` except `zero@`/`antonellosiano@`. Subhi: bahasa default, italiano OK fallback.

## 5. Agent/LLM Routing & Bans

**Claude 5 routing (2026-07-02; interactive default amended 2026-07-25)**: interactive sessions = **Opus 5** (`claude-opus-5`, architect/orchestrator, `xhigh` effort) — ratified by Zero on 2026-07-25, superseding the previous Fable-5 interactive default. **The final on-disk gate is NOT part of that amendment: it remains unconditionally Fable at max effort, it never cascades to a weaker model, and window dead → task SUSPENDS.** Implementer subagents/workflows = **Sonnet 5** (`claude-sonnet-5`, `model:"sonnet"`); grunt = Haiku 4.5. Cron tier-1: repo-side pins migrated to `claude-sonnet-5` on 2026-07-03 after per-agent probes (see `research/operations/2026-07-03-sonnet5-cron-migration.md`); LIVE HOME wrappers (`~/scripts/`) still on `claude-sonnet-4-6` until the operator applies the diffs in that doc (tracked in modus PENDING-ARMS). Exception: the nb-agents slug micro-prompt stays 4-6 (probe wobble). Full arsenal routing: `.claude/skills/modus/SKILL.md` §Arsenal.

**Opus 5 roster update (2026-07-25) — additive, changes no rule.** **Claude Opus 5** (`claude-opus-5`) shipped and is the current Opus tier: a drop-in successor to Opus 4.8 at the *same* price ($5/$25 per MTok, 1M context, 128K output), strongest on agentic coding and long-horizon work. Everywhere this repo names **Opus 4.8 as the capable non-Fable seat** — the Fable-paid contingency below, the `modus` §Arsenal fallback rows, cascade tier-1 synthesis — read **Opus 5**; 4.8 stays a valid pin, it is not deprecated. **This does NOT touch the final on-disk gate**, which remains unconditionally Fable per the paragraph above and the guarded note below. Canonical roster — use the alias exactly as written, never invent a date suffix: `claude-fable-5` · `claude-opus-5` · `claude-opus-4-8` · `claude-sonnet-5` · `claude-sonnet-4-6` · `claude-haiku-4-5`. Haiku 4.5 is the only one that also has a real dated full ID (`claude-haiku-4-5-20251001`, used by existing pins) — both resolve; the 5-family has aliases only.

> ✅ **RULED 2026-07-25 (Zero): the interactive default is Opus 5.** The 2026-07-02 clause declared Fable 5 while the harness actually reported `claude-opus-5` — a doctrine describing a state that did not exist. Three reasons, in order of weight: **(1)** a rule that lies is worse than either option, because the next session reads it and builds on it; **(2)** it *protects* the Fable invariant rather than eroding it — on the Team-Premium seat Fable is included only up to **50% weekly** and past that it is credits (= paying, barred by the 2026-07-12 contingency), so spending the allowance on ordinary interactive turns is exactly how the final gate ends up with none left; **(3)** the organism's own corrected blind A/B (`research/operations/2026-07-11-fable-paywall-routing.md` §0.5) found Fable and Opus-4.8 measured-indistinguishable on real grounded/structured work (KBLI, 10/14 ties, 0 factual errors either side), and Opus 5 is the drop-in successor to 4.8 at the same price.
>
> **The final on-disk gate is untouched and stays unconditionally Fable** — no classifier, no novelty check, no task-shape logic may ever be placed in front of it, and this ruling is not a precedent for doing so. Declared residual risk, deliberately NOT special-cased: the one shape the report flagged as plausibly Fable-favouring (novel, uncatalogued brand-voice judgment — WR2 lane-3) remains untested; it gets no exception here.

**What actually changes with the 5-family** (non-obvious, load-bearing on cron budgets and cost baselines):

- **Opus 5 thinks by default.** Omitting `thinking` now thinks (on 4.8/4.7 it meant *no* thinking), and `max_tokens` caps thinking **plus** answer — a route sized tightly around its answer can now truncate. `thinking:{type:"disabled"}` is accepted **only at effort ≤ `high`**; pairing it with `xhigh`/`max` returns 400. With thinking off, Opus 5 can also emit a tool call as **plain visible text** — the call silently never runs, no error. To cut cost, lower `effort`; do not disable thinking.
- **Sonnet 5 uses a new tokenizer: ~30% more tokens for the same text** (per-token price unchanged). Every `max_tokens`, compaction trigger and cost baseline tuned on Sonnet 4.6 must be re-measured with `count_tokens` — never apply a blanket multiplier. Relevant to `scripts/cost_baseline.py`, still on the 4.x price table.
- `effort` spans five levels on both (`low`→`max`); **`xhigh` is the sweet spot for coding/agentic**. On Opus 5, `low`/`medium` punch far above their weight — they are the primary cost/latency lever.
- Minimum cacheable prompt drops to **512 tokens on Opus 5** (1024 on Opus 4.8): prompts previously written off as uncacheable now cache with no code change.
- **Opus 5 draws on a rate-limit bucket separate** from the combined Opus 4.x pool — moving traffic neither inherits nor frees headroom.
- Removed across the whole 5-family (400 if sent): `temperature` / `top_p` / `top_k` and `budget_tokens`. No last-assistant-turn prefill. Use `output_config.effort` and `output_config.format`.
- Both Fable 5 and Opus 5 carry **elevated cybersecurity safeguards**: a declined request returns HTTP **200** with `stop_reason: "refusal"` — check `stop_reason` *before* reading `content`, or `content[0]` throws.

**Kimi seat (added 2026-07-19, Zero GO)**: Moonshot **Kimi K3** + **kimi-for-coding 2.7** via `kimi` CLI (`~/.kimi-code/bin/kimi`, Allegro flat subscription, OAuth device-code login — no API key). Invocation: `kimi -p "..." -m kimi-code/k3` (reasoning/refuter) · `-m kimi-code/kimi-for-coding` (coding) · `-m kimi-code/kimi-for-coding-highspeed` (grunt). Cross-family council/second-opinion seat and flat-quota implementation relief; probed by `scripts/arsenal_probe.py` (seat `kimi`). Armed on all three machines 2026-07-19. Never the final gate.

> **Fable-paid contingency — ACTIVE (Zero decision 2026-07-12: "non voglio pagare")** (research:
> `research/operations/2026-07-11-fable-paywall-routing.md`, report + blind A/B, Codex adversarial
> review). Scope is ONLY non-final-gate interactive work — architecture/red-team/council synthesis and
> the general "which model answers this session" choice. **It does not touch, narrow, gate, condition,
> or in any way apply to the final on-disk gate.** The final gate (line above: "the final gate never
> cascades to a weaker model; window dead → task SUSPENDS") remains unconditionally Fable, with zero
> classifier, novelty-check, or task-shape logic ever inserted in front of it — full stop, no exception
> clause. **Rule for everything else: if/when Fable-5 becomes a metered/paid endpoint, do NOT pay for it
> — route non-final-gate work to Sonnet+scaffold (or Opus-4.8 where Sonnet alone is thin) instead.** This
> is a hard preference, not a cost/quality tradeoff to weigh case by case: the corrected A/B (§0.5 of the
> report) found Fable and Opus-4.8 measured-indistinguishable on a real grounded/structured shape (KBLI,
> 10/14 ties, 0 factual errors either side) — evidence that paying rarely buys anything on this class of
> work, which is why "just don't pay" is a safe default rather than a corner being cut. The one shape the
> report flagged as still-unproven-but-plausibly-Fable-favoring (WR2 lane-3, novel/uncatalogued
> brand-voice judgment) is deliberately NOT special-cased here: use Sonnet/Opus-4.8+scaffold there too: no
> exploration of a paid-Fable path for it. (An earlier draft edit to modus §Arsenal's final-gate row was
> struck by adversarial review for breaching the invariant — do not reintroduce it in any form, including
> indirect "narrows which shapes get X" phrasing.)

**Anthropic SDK BANNED.** Never `from anthropic import Anthropic` or `ANTHROPIC_API_KEY`. Sole path: shell out to `claude` CLI with `CLAUDE_CODE_OAUTH_TOKEN` (MAX-plan quota). Refuse any new tool/MCP/cron requiring `ANTHROPIC_API_KEY`. Reference: `apps/backend-rag/backend/llm/claude_oauth_client.py`.

**Other paid per-token APIs (OpenRouter, OpenAI direct, Together, Fireworks, etc.) — require Zero's explicit authorization** (rule changed 2026-06-04, see `~/.claude/CLAUDE.md §Cost constraint`). Free-first by default (local Ollama → OAuth → free tier). Never install a paid key autonomously "to test" — surface to Antonello with cost + rationale, wait for explicit yes. **PII boundary absolute even when authorized**: LLM processing may use authorized operational context, but outputs, memories, logs, reports, skills, prompts saved for reuse, and shared artifacts must never transcribe client PII/OSINT in cleartext; use `client_id`, hashes, placeholders, or redaction (SYMBIOSIS Law 2 / UU PDP overrides cost). Pre-authorized non-PII: ChatGPT Pro Codex (unlimited). (DeepSeek V4 Pro RETIRED 2026-07-19 — pre-auth REVOKED, never top up; refuter seat → Kimi K3.)

**Antigravity IDE — autonomous arm, Claude Code verifies** (modello fissato 2026-06-23). Antigravity = braccio agentico autonomo per lavoro "largo ma verificabile" (gira su AI Ultra quota, no MAX). Claude Code = cervello che decide + ancora ai fatti + VERIFICA. Workflow 6-step: (1) Claude Code scopa il bug + ancora ai file:line reali + scrive il prompt → (2) Zero crea worktree FRESCO da origin/main + lancia Antigravity → (3) Antigravity fix+test+run (Sonnet 4.6 coding / Opus 4.6 DB) → (4) **Claude Code VERIFICA INDIPENDENTE — rilegge diff, RI-ESEGUE i test, controlla scope+reward-hacking (NON-NEGOZIABILE)** → (5) Claude Code commit+push+PR → (6) Zero merge a CI verde. Antigravity SEMPRE in `.worktrees/ops-*`, MAI sul main (sibling-race #5). MAI auto-merge dall'IDE. NON gli diamo: architettura, processing PII su dati reali, deploy autonomo, scelta di QUALI bug contano. Dettaglio: memory `decision_how_we_use_antigravity_ide_2026_06_23`.

**MCP servers**: see `.mcp.json` for inventory. Default browser MCP: `mcp__claude-in-chrome__*` (NEVER `mcp__playwright__*` unless ordered). Text-first: `get_page_text`/`find`/`javascript_tool` before screenshot.

**Off-limits files** (top-level hard boundary): `zantara_core.py`, `fly.toml`, `.env*`, `alembic/env.py`.

**Codex sandbox**: `--sandbox read-only|workspace-write` only. NEVER `--dangerously-bypass`.

## 6. Anti-Hallucination

> Errare è umano, allucinare è diabolico. (Antonello, 2026-05-13)

**Mai citare output di un tool senza averlo eseguito in QUESTO turn.** Full discipline in `~/.claude/CLAUDE.md §Anti-hallucination` (5 rules). Load-bearing on every tool call. When in doubt "ho letto X o lo sto inventando?" → tool call adesso.

**4-LLM panel mandatory pre-approval** per spec architetturale, quote cliente, pre-deploy critical path: Gemini agy + Codex GPT-5.6 family (`sol` xhigh/max for red-team; full arsenal routing `.claude/skills/modus/SKILL.md` §Arsenal) + Kimi K3 (`kimi -m kimi-code/k3 -p`; DeepSeek seat RETIRED 2026-07-19) + opzionale NB-1. Cost: flat-sub only, ~2min wall. Reference: `feedback_always_review_spec_with_4_llm.md`. **Reusable workflow (generator≠grader as default)**: `infra/workflows/verify-template.js` — a gather→adversarial-refute→synthesize Workflow script promoted to a citable artifact (self-loop Ring A4). For any research/audit/critical-finding, run it via `Workflow({scriptPath:"infra/workflows/verify-template.js", args:<question>})` so the refuter-on-fresh-context pattern is the path of least resistance, not a thing to remember. (The `sota-architecture-loop` skill STEP-3/6 is its doctrine; this file is the runnable default.) **Terminology note (2026-06-28):** the A1-A4 rings are a *self-HEALING / reliability* loop (catch regressions, restart dead organs, verify findings) — **NOT** the recursive self-improvement (RSI) Amodei describes ("models building better models"; Anthropic "we are not there yet"). A4 is a safety primitive a safe RSI would need first, not RSI itself. Don't call it "self-improvement".

## 7. Hooks enforce what prompts cannot

Hooks (`~/.claude/hooks/`) sono il backstop quando il system prompt non basta. Active 2026-05-23:

- **`stop_verify.py`** (T2.6): blocca Stop con git dirty + no intent marker. Override `STOP_VERIFY_ALLOW_DIRTY=1` o intent marker in transcript (WIP/checkpoint/leave dirty).
- **`dispatch_nudge.py`** (T1.1): reminder dispatch subagent quando transcript >500 lines + zero Agent.
- **Guardrails daemon** (T1.2): blocca MCP destructive patterns (`drop_*`, `delete_*`, `truncate_*`, `wipe_*`, `purge_*`).
- **SessionStart repomap inject** (SOTA L4, 2026-05-24): se `~/.nuzantara-repomap.txt` esiste e ha age <30min, viene auto-iniettato in context all'inizio sessione. Riduce esplorazione iniziale di ~50 tool calls. Stale >30min skipped (no inject). Kill switch: rimuovi entry da `~/.claude/settings.json`.
- **`pre-commit lease-check`** (SOTA L2, 2026-05-24): blocca commit su hot-zone (LaunchAgent wrappers, migrations, auth/billing/pricing, .github/workflows/, sentinel/dlq scripts) se file ha lease attivo da altro agent task. Backend Redis `agent_lock:<resource>` con TTL + heartbeat. Override `AGENT_LEASE_ENFORCEMENT=false`. Graceful degradation se Redis down → pass-through con WARN log (mai blocco per outage Redis). Runbook: `docs/runbooks/redis-lease-registry.md`. SOTA panel reference: `research/operations/2026-05-24-sota-multi-agent-repo-architecture-synthesis.md`.

**Principio**: se una regola critica è violabile, scrivi un hook. Documentazione non basta.

## 7bis. Repomap + Branch cleanup (SOTA L4 2026-05-24)

- **Repomap cron** (`com.nuzantara.repomap.15min`): aggiorna `~/.nuzantara-repomap.txt` ogni 15min via `scripts/build_repomap.sh` (strategia aider tree-sitter, ~8KB / 264 righe, signatures only). SessionStart hook injetta in context se age <30min. Kill switch: `REPOMAP_ENABLED=false` nell'env del plist.
- **Branch cleanup weekly** (`com.nuzantara.branch-cleanup.weekly`, lunedi 08:00 WITA): genera report `~/logs/branch-cleanup-YYYYMMDD.md` via `scripts/branch_graveyard_cleanup.sh`. Default dry-run (REPORT ONLY). Apply solo categoria "merged & deletable" via `--apply`. Categorie zombie `claude/*` >30d e stale >90d sono REPORT-ONLY (mai auto-cancel). Kill switch: `BRANCH_CLEANUP_ENABLED=false`.
- **Install**: `bash infra/launchagents/install_repomap_cron.sh`. Runbook: `docs/runbooks/repomap-and-branch-cleanup.md`.

---

# Part B — Project Invariants

## 8. Code Golden Rules (ENFORCE STRICTLY)

1. **Virtualenv Mandatory** — `apps/backend-rag/.venv/`. Never system Python.
2. **No Root Execution** — `PYTHONPATH=. python -m backend.module`
3. **Path Discipline** — Absolute imports: `from backend.core import config`
4. **Async First** — `httpx` not `requests`. All I/O async.
5. **Type Hints** — Full annotations on every function.
6. **No Hardcoded Secrets** — env vars or secrets manager.
7. **Data/Logic Separation** — Business logic ≠ data access.
8. **Clean Logging** — `logger` never `print()`.
9. **Verify Sources** — Never presume, verify against actual data.
10. **Async HTTP Clients** — NEVER `httpx.AsyncClient()` in methods/loops. Persistent `_get_client`, close in `lifespan`.
11. **PricingTool Only** — All prices from `PricingTool`. Never hardcode.
12. **Commit discipline** — atomic per fix, `feat|fix|chore|refactor|docs(scope):` convention. Co-author `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` (matches what the harness itself appends; historical commits keep whatever model authored them — never rewrite them). Never `--no-verify`/`--amend` on pushed.

## 9. Data Invariants (NEVER VIOLATE)

- **Embedding model FROZEN**: `text-embedding-3-small` (1536 dims). Changing invalidates 93,283 vectors. NEVER change without re-indexing plan.
- **KBLI flat payload — Qdrant collection ONLY**: the KBLI Qdrant collection payload (built by `reindex_kbli_2025_final.py::build_payload`, its own comment calls this the "KBLI flat-payload golden rule") is flat — `kode_kbli`, `judul`, `content`/`text`, `sektor`/`section`, `pma_status`, `kategori_risiko`, `scales`, etc. Never nested. **This does NOT describe the separate Postgres `kbli_documents` table** (feeds `chat_kbli`'s LLM context, seeded 2026-02-18 out-of-band, no migration/ORM model): that table has exactly 6 columns — `kode_kbli`, `judul`, `content`, `metadata` (jsonb), `created_at`, `updated_at` — with business fields (`sektor_id`, `pma_status`, `per_skala`, ...) nested INSIDE `metadata`, actively evolving under the kbli-navigator lane's cure work; `kategori_risiko` does not exist on this table at all (Qdrant-only concept). Corrected 2026-07-21 (lever #8, `research/operations/2026-07-19-balizero-kb-activation-plan.md`) — the old wording conflated the two stores and was never true for the Postgres one. Tripwire: `test_kbli_documents_queries_read_metadata_not_flat_business_columns` in `test_data_invariant_tripwires.py`.
- **Evidence scoring thresholds**: NOT one number — **5 NAMED gates, one SSOT** (`backend/services/rag/agentic/_abstain_policy.py`; domanda #31 CLOSED 2026-07-05). GENERATION gate flat `0.15` (reasoning.py, strict `<`) · LABEL gate per-domain `tax:0.10 / visa:0.12 / kbli:0.20 / pricing,default:0.15` (orchestrator_response.py; env `DOMAIN_ABSTAIN_THRESHOLDS`, values clamped to [0,1]) · CONFIDENCE zone edges `0.15/0.60` (streaming) · CONTEXT_QUALITY_MIN `0.15`. The generation≠label VALUE divergence is **intentional and panel-ruled** (2026-06-14: per-domain in generation = tax advice at 0.11 evidence = safety regression) — do NOT "tidy" it into one value; tripwire tests in `test_abstain_threshold_convergence.py` + golden matrix in `test_abstain_policy_hardening.py` enforce this.
- **Vision model**: `qwen2.5vl:7b` ONLY for OCR/vision (qwen3.5 Q4_K_M strips vision weights). API: `"images": [base64]`.
- **Ollama `think:false`** REQUIRED for Qwen 3.5 client (`backend/llm/ollama_client.py`).
- **Cache invalidation**: `await invalidate_cache("zantara:namespace:*")` after EVERY mutation. Namespaces: `crm_clients_stats`, `crm_practices`.

## 10. Postgres MCP — Read-Only Access

`postgres-nuzantara` MCP (`mcp__postgres-nuzantara__*`) connects via `nuzantara_readonly` role on Fly Postgres (T3.2 shipped 2026-05-23). **Defense-in-depth**: 255 SELECT grants, ZERO INSERT/UPDATE/DELETE/CREATE. Use `query` tool for ad-hoc data inspection. For mutations: backend code only, NEVER MCP. Password in Keychain (`nuzantara-postgres-readonly`).

## 11. Deploy Lifecycle

**Fly.io 2 apps**: `nuzantara-rag` (shared-2x, 2GB, always-on, EventBus) + `nuzantara-postgres` (postgres-flex 17.7, `repmgr` HA — NOT Stolon; rolling-upgraded 17.2→17.7 on 2026-08-09 after an isolated restore proof; backup → Tigris daily — WAL archiving re-enabled same day: a legacy override had disabled it, so "DONE" backups were not actually restorable). Frontend on Vercel (auto-deploy on `git push origin main`).

**Pre-deploy** (run sequentially):
```bash
git diff --name-only HEAD -- apps/backend-rag/backend/
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('OK')"
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_langgraph.py backend/tests/services/rag/test_kg_subgraphs.py backend/tests/services/rag/test_confidence.py -q
```

**Deploy** — run from the monorepo ROOT, not from `apps/backend-rag` (corrected 2026-07-24, PR #3062 ship:
the Dockerfile's `COPY` paths are repo-root-relative — `apps/backend-rag/backend`, `packages/cell-core`,
`apps/crm-cell/crm_cell` — so a build invoked with cwd=`apps/backend-rag` fails with `"apps/backend-rag/backend": not found`.
The local `fly` shell-function wrapper on Pro/Mini also hardcodes that wrong cwd regardless of caller
location — bypass it with a direct `ssh pro`/`ssh mini` call when deploying):
```bash
cd ~/Desktop/nuzantara  # repo root, NOT apps/backend-rag
fly deploy --config apps/backend-rag/fly.toml --dockerfile apps/backend-rag/Dockerfile --strategy rolling -a nuzantara-rag
```

**Migration PRs** touching `migrations_v2/*.sql` auto-run Squawk lint (PR #306). Bypass: `-- squawk-ignore: <rule>`.

**Post-deploy QA OBBLIGATORIO**: wait curl 200/307 → screenshot via `mcp__claude-in-chrome__*` → verify colors/logo/no broken → fix/redeploy → final report. URLs: `kita`/`my`/`prime`/`calendar`/`mail`/`drive`/`knowledge`/`zantara`.balizero.com.

## 12. Operational Channels

4 live (see `apps/backend-rag/backend/channels/`):

- **WhatsApp** ✅ Fly.io (Gemini 3 Flash + RAG)
- **Telegram** ✅ Pro OpenClaw (Opus 4.6 + SOUL.md)
- **Instagram** ✅ Fly.io
- **Web Chat** ✅ Fly.io

Twitter (CRC broken), Google Chat (scaffold), Slack (scaffold) quarantined `.disabled-2026-04-30/`.

## 13. Critical Operational Rules

- **Email sending** (REGOLA FISSA): always `from=zantara@balizero.com` via Brevo `/api/notifications/send-email` + `X-API-Key: <NOTIFICATIONS_API_KEY>` (the literal `REDACTED-ROTATED-KEY` was a public-repo admin key — rotated + revoked 2026-07-12; read the key from the env, never hardcode it). Never `notifications@`/`subhi@`/personal addresses.
- **CRM RBAC**: Admin (`zero@`, `antonellosiano@`, `asya@balizero.com`) = all access. Team = only `assigned_to` matches.
- **Team perimeter rule**: full roster in memory `reference_bali_zero_team.md`. **Subhi — WHOLE-SYSTEM code access (widened 2026-07-16 by Zero: "eliminiamo il perimetro no-backend-rag, allarghiamo all'intero sistema"; probation 90gg 2026-04-30 → 2026-07-29 unchanged).** The old `apps/mouth/**`-only perimeter + "NO backend RAG" ban is LIFTED: he may work anywhere in the codebase (backend RAG, organs_registry.yaml, migrations included). **The ban existed because there was no safe verification for his backend diffs; there is now** — so the perimeter is replaced by a VERIFICATION model, not a path fence:
  - **Verification = MACHINE + AI, NEVER human review** (the codeowner cannot review — [[feedback_session_owns_full_ship_lifecycle_2026_07_16]]). Every PR (his or anyone's) must pass the required CI gates (test suite, `actionlint`, RAG data-invariant tripwires `test_data_invariant_tripwires.py`, migration Squawk, R1 adversarial-review gate, …). Backend/sensitive PRs ALSO get the Layer-2 AI-review Action (`.github/workflows/ai-pr-review.yml`) + a SESSION's independent verification (generator≠grader — Subhi never grades his own diff; sensitivity raises the rigor of the adversarial gate, it never moves the merge to a human).
  - **The grader self-protects** (this is what makes widening safe): Subhi cannot disarm a check — `.github/workflows/` + `CODEOWNERS` are CODEOWNERS-TIER1, actionlint-gated, and meta-verifier-protected. A diff that weakens a gate fails CI by construction.
  - **Still ❌ (credential/infra, NOT code-perimeter)**: Fly secrets / `fly ssh`, direct prod-DB writes, Actions secrets, repo/branch-protection settings, secret rotation. These are operator actions, not reviewable diffs.
  - RBAC detail (self-merge on green, GA4 Editor, CRM read-only) in memory `subhi-rbac-permissions.md`.
- **OCR multi-page**: ALWAYS all pages — directors typically page 2-3 of akta. Timeout 120s for >3 pages. Vision: `qwen2.5vl:7b` ONLY.
- **Drive OAuth** (corrected 2026-08-06 — the old "90d expiry, watchdog alerts 7d before" described a model this codebase never had): `google_drive_tokens.expires_at` is the **one-hour access token** (`google_drive_service.py:163` sets `now + expires_in`; `:230` refreshes lazily on use, 5-min buffer). Measured on both live rows, `expires_at - updated_at == 1h` exactly — **no column anywhere records the refresh token's validity**, so no query against this table can distinguish a live credential from a revoked one. Proven the hard way: on 2026-08-05 Google answered `invalid_grant: Token has been expired or revoked` to the GARUDA indexer while the row looked fully populated. The only thing that knows is an actual refresh attempt, and the consumers make one every time they run — so **the ground truth is a consumer's failure, not a watchdog's countdown**. `scripts/drive_token_watchdog.py` therefore alerts on the two states the table CAN express (no row / no `refresh_token`) and never on a day count; anything that reintroduces a day-scale reading of `expires_at` is unreachable at best and a nightly false CRITICAL at worst. Live Drive traffic does **not** use this table at all — 16 production files go through `ServiceAccountDriveService` (domain-wide delegation), and `_refresh_token` deliberately refuses to refresh the `SYSTEM` row since 2026-05-10. Re-auth `https://kita.balizero.com/settings/integrations`.
- **GitHub Secrets** (Actions + cron alerts): `FLY_API_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_OWNER_CHAT_ID=1125336968` (Zero's `@zero0101010101010` chat with `@Balizerobot`, verified live 2026-04-07). Never commit, never log. Rotation via `gh secret set`.
- **WR2 image-generator backend** (`WR2_IMAGE_BACKEND` env): `auto` (default, FlowKit primary + Playwright fallback) / `flowkit` / `playwright`. See `docs/wr2/flowkit-integration.md`.

## 14. Escalations & Continuity

- **Session start**: check `shared/escalations_pro.jsonl` + `~/.agent/decisions/claude_tasks/` HIGH first. Delete file after fix + verify with `test_cmd`.
- **PII/OSINT output boundary**: il vincolo non e' "nessun LLM vede contesto operativo"; il vincolo e' che nessun output, memoria, skill, report, log, alert o artefatto condiviso trascriva PII/OSINT in chiaro (non-negoziabile — UU PDP Art. 67-68). **Cloud/transito alleggerito 2026-06-20**: UU PDP non impone data-localization per agenzie private; il transito PII su cloud estero e' lecito sotto Art. 56 con safeguard (Workspace DPA) + consenso esplicito. Il *processing* PII resta locale-sovrano sul Pro (cloud_vision_gate fail-closed); il mirror raw resta Pro-bound per scelta operativa (onere-della-prova), non per divieto assoluto. Reference SYMBIOSIS.md Law 2.
- **Local sovereignty** (Law 6): organismo vive su macchine Zero. Disconnessione internet NON è guasto — è stato naturale.

## 15. Research Capture Convention

Ricerche sostanziose (≥400 parole + ≥3 fonti + checklist + dominio in {property, visa, tax, hr, compliance} + client-case) → `~/nuzantara/research/<domain>/YYYY-MM-DD-slug.md`.

**Frontmatter obbligatorio**: `date`/`domain`/`client_case`/`sources`.

**Proposta save**: *"Questa mi sembra da salvare in `research/<domain>/` — procedo? (y/n)"*

Su y: write file + append 1-line to `~/.claude/projects/-Users-nuzantara/memory/MEMORY.md` under `## Research Captures`. Solo se `domain=property`: push body as NB-5 text source (`d9438180-5e63-4e2a-a473-6061101f6a8d`) via `mcp__notebooklm-mcp__source_add`. Altri domini: non toccare NB curati.

**NEVER auto-promote** to `apps/backend-rag/backend/kb/` (that's curated). Research stays ad-hoc auditable.

---

> Authoritative last update: `git log -1 --format=%cd -- CLAUDE.md` in repo root.
> Maintained by: Bali Zero AI Team.
