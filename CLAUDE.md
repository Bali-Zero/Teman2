# CLAUDE.md — Nuzantara Project Context

> **Read `SYMBIOSIS.md` first.** It governs this entire ecosystem.
> **Before building anything new, read `VADEMECUM.md`.** Operative checklist.
> **Atlas:** [`INDEX.md`](INDEX.md) — where every organ/tissue/nerve lives.

---

<!-- CANON:builder-contract -->

## THE BUILDER CONTRACT — identical in every door, compared by machine

This block is the same in `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` and `QWEN.md`, and
`scripts/proprioception.py`'s `door_canon_parity` probe goes RED if any copy drifts from
`CLAUDE.md`'s. "The same" is what the machine actually enforces, not more: the comparison
hashes the block with TRAILING whitespace and line endings normalised away, so an editor that
strips or adds them is not drift — and anything else, including one reworded sentence or one
extra space mid-line, is. It exists because the CI layer already binds every model equally — a gate does
not care which family opened the PR — while the harness layer did not: a seat that BUILDS used
to start with whatever its own door happened to say. **Do not reword this block in one door.**
Fix it in `CLAUDE.md` and copy it outward, or the probe will name your door.

**1 — PR contract.** One PR, one concern, ≤ ~400 net lines where the work allows. Arming means
freezing: after auto-merge is armed, the branch is read-only and every follow-up starts from a
fresh `origin/main`. Never rerun a red check before you know WHY it is red — the right gesture
depends on the cause, and a blind rerun replays a stale merge ref. Serialize PRs that share a
lockfile. Work in a dedicated worktree on an `agent/<host>/<lane>/...` branch. Three reds for
the SAME cause and the PR suspends instead of taking a fourth round; a fix-of-a-fix stops at
depth 1 — if the correction is itself wrong, the surface is under-specified, so write the spec.

**2 — Every PR body carries a `Bites:` line** naming the CONSUMER and the observation that
proves the change is in force. "A future job will run it" is not a consumer: the job ships in
the same PR. Make the observation before reporting the work done — a merged diff is not a live
one, and this repo's scar record is mostly the distance between those two.

**3 — Bans, stated as an ENTITY and not as a spelling.** What is forbidden is reaching a Claude
model through a **paid per-token Anthropic endpoint** — because the subscription is already paid
and a per-token key duplicates it. The sole sanctioned path is the `claude` CLI with
`CLAUDE_CODE_OAUTH_TOKEN`. `from anthropic import Anthropic` and `ANTHROPIC_API_KEY` are the two
shapes that usually carry it, and grepping for them is a useful first pass — but an alias, a
renamed env var, a wrapper library or a Bedrock/Vertex route reaches the same endpoint without
either literal, and is equally banned. Refuse any new tool, MCP server or cron that requires it. Other paid per-token APIs are not banned but are not
yours to install: they need the owner's explicit authorization first. Never `--dangerously-bypass`
a sandbox; never echo, print or commit a credential — `${VAR:+SET}` reports presence,
`${VAR:-default}` prints the value.

**4 — PII boundary, and it is an OUTPUT boundary.** Processing client data under an authorized
lane is allowed; transcribing it is not. No output, memory, log, alert, report, skill, prompt
saved for reuse, or shared artifact may carry client PII or OSINT in cleartext — use a
`client_id`, a hash, a placeholder or a redaction. This binds every vendor identically: there is
no cloud whose terms make cleartext PII acceptable here, and no seat exempt from it.

**5 — Ship sequence.** The session that owns a mandate runs it end to end: review → merge → arm
→ deploy → prove-live. The codeowner does not merge, does not review and does not deploy — by
design. Arm auto-merge at PR-open. Push, create and merge are three SEPARATE commands, never a
compound one. What stays with the human: business decisions, credentials and consents, and
physical/GUI actions. **The one exception both ways:** an external builder seat (`AGENTS.md`,
`GEMINI.md`, `QWEN.md`) prepares and never ships — it does not merge, arm or deploy its own
work, and a Claude session verifies it. Generator is never grader, in either direction.

<!-- /CANON:builder-contract -->

---

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

**Escalations**: check `shared/escalations_pro.jsonl` + `~/.agent/decisions/claude_tasks/` at session start. HIGH first.

## INDICE — dove sta cosa

> Contenuto specialistico spostato (mai cancellato) fuori dalla radice — caricato da Claude
> Code in modo nativo/lazy quando si lavora nella cartella pertinente, o su richiesta.

| Contenuto (era) | Stato vigente | Dove |
|---|---|---|
| Agent PR Contract (Merge-OS v2 Wave 0) | 8 regole PR agent-produced, vigenti | `docs/rules/operations.md` |
| §2 Behavior & Autonomous Ops | no-phantom-operator, ship-lifecycle esteso, master loop modus, product assembly line, federation orchestrator, preflight SDD | `docs/rules/operations.md` |
| §5 Agent/LLM Routing & Bans | routing Claude 5, i 3 RULED 07-25/08-19/08-20, roster, Fable contingency (moot), Kimi seat, fleet order, DeepSeek due porte, Antigravity, SDK ban, MCP servers, off-limits files (dettaglio), Codex sandbox | `docs/rules/RULINGS.md` |
| §6 Anti-Hallucination (corpo intero) | 4-LLM panel + workflow generator≠grader | `docs/rules/operations.md` |
| §7/§7bis Hooks + Repomap/Branch-cleanup | hook attivi, repomap cron, branch cleanup weekly | `docs/rules/operations.md` |
| §8 Code Golden Rules · §9 Data Invariants · §10 Postgres MCP · §11 Deploy Lifecycle · §12 Operational Channels | golden rules backend-rag, embedding/KBLI/thresholds frozen, deploy Fly.io, 4 canali live | `apps/backend-rag/CLAUDE.md` |
| §13 Critical Operational Rules · §14 Escalations & Continuity | email/RBAC/team-perimeter/OCR/Drive-OAuth/GitHub-secrets · PII/OSINT output boundary (Legge 2) | `docs/rules/operations.md` |
| §15 Research Capture Convention | soglia ≥400 parole+3 fonti, frontmatter, mai auto-promote a kb/ | `research/CLAUDE.md` |

## Regole sempre-applicabili

- **Ship-lifecycle**: la sessione fa tutto — review → merge → arm → deploy → prove-live. Il codeowner non merga, non review, non deploya. Storia e dettaglio (RULED 2026-07-16 + eccezione editorial-delegation 2026-09-01): `docs/rules/operations.md`.
- **Anti-hallucination**: mai citare output di un tool senza averlo eseguito in QUESTO turn. 4-LLM panel + workflow generator≠grader: `docs/rules/operations.md`.
- **Off-limits files** (top-level hard boundary): `zantara_core.py`, `fly.toml`, `.env*`, `apps/bali-intel-scraper/backend/db/migrations/env.py`. Correzione 2026-08-21 (il vecchio `alembic/env.py` non esiste in questo repo) + dettaglio: `docs/rules/RULINGS.md`.

## Strumenti (MCP→CLI, dieta 2026-09-04)

Il server MCP `nuzantara-knowledge` è staccato dal contesto di default (~−5k token/sessione) — stessi dati via API; `.mcp.json` locale tiene `mcpServers` vuoto (backup `.mcp.json.bak-diet-20260904`).

| Serve | Usa |
|---|---|
| Prezzi / KBLI / visa / legal (PII-free) | `curl https://nuzantara-rag.fly.dev/...` — è il backend che l'MCP wrappava (`apps/nuzantara-mcp/nuzantara_mcp/server_knowledge.py`); per una sessione che vuole i tool MCP: ripristina il backup di `.mcp.json` |
| Docs librerie/framework | WebFetch / WebSearch (plugin context7 disinstallato) |
| GitHub · Fly · Postgres | `gh` · `fly` · `scripts/pg.sh` |
| Browser QA post-deploy | MCP `claude-in-chrome` (resta, deferred) |
| Google Drive | connector claude.ai on-demand (`operator[gui]`) |

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

---

> Authoritative last update: `git log -1 --format=%cd -- CLAUDE.md` in repo root.
> Maintained by: Bali Zero AI Team.
