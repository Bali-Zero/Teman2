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

# Part A — Agent Directives

## 1. Machine & Reachability

Machine table (M5/Pro/Mini) → `~/.claude/CLAUDE.md` (global). Prefix `[Pro]`/`[Mini]`/`[Air]` per `hostname` (`whoami=nuzantara` Pro/Mini, `balizero` M5 — path-aware scripts). SSH `ssh pro`/`mini`/`air`. Air decommissioned 2026-05-05, code refs = archaeology.

## Agent Worktree Discipline

Agent sessions MUST run under `.worktrees/<lane>-<task-id>/` via `scripts/agent_start.py` — `~/nuzantara` read-only (operator/cicatrix hotfix). Kill switch `AGENT_BROKER_ENABLED=false`; runbook `docs/runbooks/agent-worktree-broker.md`. Escalations `shared/escalations_pro.jsonl`+`~/.agent/decisions/claude_tasks/`, HIGH first.

## INDICE — dove sta cosa

> Spostato, non cancellato — lazy dal file target.

- `docs/rules/operations.md` ← Agent PR Contract, §2 Behavior & Autonomous Ops, §6 Anti-Hallucination, §7/§7bis Hooks + Repomap/Branch-cleanup, §13-§14 Critical Operational Rules & Escalations
- `docs/rules/RULINGS.md` ← §5 Agent/LLM Routing & Bans
- `apps/backend-rag/CLAUDE.md` ← §8-§12 Code Golden Rules, Data Invariants, Postgres MCP, Deploy Lifecycle, Operational Channels
- `research/CLAUDE.md` ← §15 Research Capture Convention

## Regole sempre-applicabili

- Ship-lifecycle: sessione fa tutto, review→merge→arm→deploy→prove-live; codeowner non merga/review/deploya (RULED 2026-07-16, eccezione 2026-09-01): `docs/rules/operations.md`.
- Anti-hallucination: mai citare output tool non eseguito in QUESTO turn; 4-LLM panel + generator≠grader: `docs/rules/operations.md`.
- Off-limits: `zantara_core.py`, `fly.toml`, `.env*`, `apps/bali-intel-scraper/backend/db/migrations/env.py` (non `alembic/env.py`, non esiste qui, 2026-08-21): `docs/rules/RULINGS.md`.

## Strumenti

MCP `nuzantara-knowledge` OFF (~−5k tok/sess, via CLI); `.mcp.json` vuoto (backup `.mcp.json.bak-diet-20260904`). Prezzi/KBLI/visa/legal: `curl https://nuzantara-rag.fly.dev/...` (`apps/nuzantara-mcp/nuzantara_mcp/server_knowledge.py`). Docs: WebFetch/WebSearch. GitHub/Fly/PG: `gh`/`fly`/`scripts/pg.sh`. Browser: `claude-in-chrome`. Drive: connector claude.ai (`operator[gui]`).

## 3. Memory (MOS)

SessionStart auto-load ultime 5 memorie (importance ≥7). CLI `~/.claude/scripts/mem`: `recent`/`query "txt"`(FTS5)/`save <type> "txt" <importance>`(decision/discovery/fact/unresolved)/`entities "name"`/`sessions`/`stats`. `mem` prima di `notebook_query` (NLM solo dominio/cross-query). Salvataggio proattivo OBBLIGATORIO — `mem save` subito: decision(8-10), discovery/fact(7-8), unresolved(5-6); non chiedere, salva e basta.

## 4. Language Protocol

User writes colloquial Italian — translate internally, reply Italian. Never ask "what do you mean?", infer from codebase; ambiguous → pick likely + 1-line assumption. Owner: Zero (codename, name PRIVATE); Italian with owner, else client language. Email team: Bahasa Indonesia for `@balizero.com` except `zero@`/`antonellosiano@`; Subhi bahasa default, italiano OK.

---

> Authoritative last update: `git log -1 --format=%cd -- CLAUDE.md` in repo root.
> Maintained by: Bali Zero AI Team.
