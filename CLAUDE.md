# CLAUDE.md — Nuzantara Project Context

> **Read `SYMBIOSIS.md` first.** It governs this entire ecosystem.
> **Before building anything new, read `VADEMECUM.md`.** Operative checklist.
> **Atlas:** [`INDEX.md`](INDEX.md) — where every organ/tissue/nerve lives.

---

# Part A — Agent Directives

## 1. Machine & Reachability

| Machine | User | Hostname | Role | RAM |
|---|---|---|---|---|
| **Pro** | `nuzantara` | `Nuzantara` | Dev primario, interactive Claude Code | 48GB M4 Pro |
| **Mini-Pro2** | `nuzantara` | `Mini-Pro2` | Server H24, Ollama dedicato, cron pesanti | 24GB M4 Pro |

- `whoami=nuzantara` on both; distinguish via `hostname`. SSH alias `ssh pro` / `ssh mini` (Tailscale `100.93.236.6` for Mini, `100.107.22.111` for Pro from Mini).
- First-response prefix: `[Pro]` or `[Mini]`.
- **Air decommissioned 2026-05-05** — handed off to Ari/Bali Zero. Historical references in code/scripts are archaeology, NOT active.

## Agent Worktree Discipline (2026-05-24)

OGNI agent session (subagent dispatch / cron-spawned claude / parallel Claude Code window) DEVE girare sotto `.worktrees/<lane>-<task-id>/` creato via `scripts/agent_start.py`. Il main checkout `~/Desktop/nuzantara` resta read-only per agent — riservato a operator interactive + cicatrix hotfix.

Quick start: `python scripts/agent_start.py --lane <X> --task-id <Y>` → cd output path → spawn agent. Kill switch `AGENT_BROKER_ENABLED=false`. Runbook: `docs/runbooks/agent-worktree-broker.md`. SOTA panel reference: `research/operations/2026-05-24-sota-multi-agent-repo-architecture-synthesis.md`.

## 2. Behavior & Autonomous Ops

**DO NOT ask the user to write code.** Act first, ask if blocked. Use `Edit`/`Write`/`Bash` without asking permission.

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

**Escalations**: check `shared/escalations.json` + `~/.agent/decisions/claude_tasks/` at session start. HIGH first.

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

**Anthropic SDK BANNED.** Never `from anthropic import Anthropic` or `ANTHROPIC_API_KEY`. Sole path: shell out to `claude` CLI with `CLAUDE_CODE_OAUTH_TOKEN` (MAX-plan quota). Refuse any new tool/MCP/cron requiring `ANTHROPIC_API_KEY`. Reference: `apps/backend-rag/backend/llm/claude_oauth_client.py`.

**Other paid per-token APIs (OpenRouter, OpenAI direct, Together, Fireworks, etc.) — require Zero's explicit authorization** (rule changed 2026-06-04, see `~/.claude/CLAUDE.md §Cost constraint`). Free-first by default (local Ollama → OAuth → free tier). Never install a paid key autonomously "to test" — surface to Antonello with cost + rationale, wait for explicit yes. **PII boundary absolute even when authorized**: no client PII (KTP/passport/NPWP/akta/credentials/OSINT) to any third-party paid endpoint (SYMBIOSIS Law 2 / UU PDP overrides cost). Pre-authorized non-PII: DeepSeek V4 Pro ($0.01/q), ChatGPT Pro Codex (unlimited).

**MCP servers**: see `.mcp.json` for inventory. Default browser MCP: `mcp__claude-in-chrome__*` (NEVER `mcp__playwright__*` unless ordered). Text-first: `get_page_text`/`find`/`javascript_tool` before screenshot.

**Off-limits files** (top-level hard boundary): `zantara_core.py`, `fly.toml`, `.env*`, `alembic/env.py`.

**Codex sandbox**: `--sandbox read-only|workspace-write` only. NEVER `--dangerously-bypass`.

## 6. Anti-Hallucination

> Errare è umano, allucinare è diabolico. (Antonello, 2026-05-13)

**Mai citare output di un tool senza averlo eseguito in QUESTO turn.** Full discipline in `~/.claude/CLAUDE.md §Anti-hallucination` (5 rules). Load-bearing on every tool call. When in doubt "ho letto X o lo sto inventando?" → tool call adesso.

**4-LLM panel mandatory pre-approval** per spec architetturale, quote cliente, pre-deploy critical path: Gemini agy + Codex GPT-5.5 + DeepSeek V4 Pro + opzionale NB-1. Cost ~$0.01/section, ~2min wall. Reference: `feedback_always_review_spec_with_4_llm.md`.

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
12. **Commit discipline** — atomic per fix, `feat|fix|chore|refactor|docs(scope):` convention. Co-author `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`. Never `--no-verify`/`--amend` on pushed.

## 9. Data Invariants (NEVER VIOLATE)

- **Embedding model FROZEN**: `text-embedding-3-small` (1536 dims). Changing invalidates 93,283 vectors. NEVER change without re-indexing plan.
- **KBLI flat payload**: fields `kode_kbli`, `judul`, `content`, `sektor_id`, `pma_status`, `skala_usaha`, `kategori_risiko`. Never nested.
- **Evidence scoring thresholds**: NOT a single flat 0.15 — the codebase has **two live abstain paths** (verified 2026-06-11, domanda #31). Global default `<0.15` ABSTAIN · `0.15-0.60` CAUTIOUS · `>0.60` NORMAL (`constants.py:96 ABSTAIN_THRESHOLD=0.15`, used by `reasoning.py` at ~11 sites). BUT the orchestrator path (`orchestrator_response.py:90`) uses **per-domain** `get_abstain_threshold(query)` from `reasoning_utils.py` — `tax:0.10`, `kbli:0.20`, `default:0.15` (overridable via env `DOMAIN_ABSTAIN_THRESHOLDS`). `reasoning.py` has ZERO refs to the domain fn → same query can abstain differently per path. SSOT consolidation = open (domanda #31).
- **Vision model**: `qwen2.5vl:7b` ONLY for OCR/vision (qwen3.5 Q4_K_M strips vision weights). API: `"images": [base64]`.
- **Ollama `think:false`** REQUIRED for Qwen 3.5 client (`backend/llm/ollama_client.py`).
- **Cache invalidation**: `await invalidate_cache("zantara:namespace:*")` after EVERY mutation. Namespaces: `crm_clients_stats`, `crm_practices`.

## 10. Postgres MCP — Read-Only Access

`postgres-nuzantara` MCP (`mcp__postgres-nuzantara__*`) connects via `nuzantara_readonly` role on Fly Postgres (T3.2 shipped 2026-05-23). **Defense-in-depth**: 255 SELECT grants, ZERO INSERT/UPDATE/DELETE/CREATE. Use `query` tool for ad-hoc data inspection. For mutations: backend code only, NEVER MCP. Password in Keychain (`nuzantara-postgres-readonly`).

## 11. Deploy Lifecycle

**Fly.io 2 apps**: `nuzantara-rag` (shared-2x, 2GB, always-on, EventBus) + `nuzantara-postgres` (Stolon HA, backup → Tigris daily). Frontend on Vercel (auto-deploy on `git push origin main`).

**Pre-deploy** (run sequentially):
```bash
git diff --name-only HEAD -- apps/backend-rag/backend/
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('OK')"
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_langgraph.py backend/tests/services/rag/test_kg_subgraphs.py backend/tests/services/rag/test_confidence.py -q
fly deploy --strategy rolling
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

- **Email sending** (REGOLA FISSA): always `from=zantara@balizero.com` via Brevo `/api/notifications/send-email` + `X-API-Key: REDACTED-ROTATED-KEY`. Never `notifications@`/`subhi@`/personal addresses.
- **CRM RBAC**: Admin (`zero@`, `antonellosiano@`, `asya@balizero.com`) = all access. Team = only `assigned_to` matches.
- **Team perimeter rule**: full roster in memory `reference_bali_zero_team.md`. Subhi probation 90gg (2026-04-30 → 2026-07-29), perimeter `apps/mouth/(blog|marketing|kbli|visa|property|tax-calendar)/**` + GA4/GSC only. NO backend RAG, NO secrets, NO organs_registry.yaml.
- **OCR multi-page**: ALWAYS all pages — directors typically page 2-3 of akta. Timeout 120s for >3 pages. Vision: `qwen2.5vl:7b` ONLY.
- **Drive OAuth**: token in `google_drive_tokens` table, 90d expiry. Watchdog `scripts/drive_token_watchdog.py` alerts 7d before. Re-auth `https://kita.balizero.com/settings/integrations`.
- **GitHub Secrets** (Actions + cron alerts): `FLY_API_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_OWNER_CHAT_ID=1125336968` (Zero's `@zero0101010101010` chat with `@Balizerobot`, verified live 2026-04-07). Never commit, never log. Rotation via `gh secret set`.
- **WR2 image-generator backend** (`WR2_IMAGE_BACKEND` env): `auto` (default, FlowKit primary + Playwright fallback) / `flowkit` / `playwright`. See `docs/wr2/flowkit-integration.md`.

## 14. Escalations & Continuity

- **Session start**: check `shared/escalations.json` + `~/.agent/decisions/claude_tasks/` HIGH first. Delete file after fix + verify with `test_cmd`.
- **OSINT sovereignty**: dati intelligence non escono mai dal Pro. Mai frontend, mai cloud, mai team. Skill condivise contengono conoscenza operativa, non dati. Reference SYMBIOSIS.md Law 2.
- **Local sovereignty** (Law 6): organismo vive su macchine Zero. Disconnessione internet NON è guasto — è stato naturale.

## 15. Research Capture Convention

Ricerche sostanziose (≥400 parole + ≥3 fonti + checklist + dominio in {property, visa, tax, hr, compliance} + client-case) → `~/Desktop/nuzantara/research/<domain>/YYYY-MM-DD-slug.md`.

**Frontmatter obbligatorio**: `date`/`domain`/`client_case`/`sources`.

**Proposta save**: *"Questa mi sembra da salvare in `research/<domain>/` — procedo? (y/n)"*

Su y: write file + append 1-line to `~/.claude/projects/-Users-nuzantara/memory/MEMORY.md` under `## Research Captures`. Solo se `domain=property`: push body as NB-5 text source (`d9438180-5e63-4e2a-a473-6061101f6a8d`) via `mcp__notebooklm-mcp__source_add`. Altri domini: non toccare NB curati.

**NEVER auto-promote** to `apps/backend-rag/backend/kb/` (that's curated). Research stays ad-hoc auditable.

---

> Authoritative last update: `git log -1 --format=%cd -- CLAUDE.md` in repo root.
> Maintained by: Bali Zero AI Team.
