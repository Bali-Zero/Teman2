# AGENTS.md - Nuzantara Project Context for AI coding agents (Codex · Kimi · Gemini · …)

> Read by every AGENTS.md-standard agent: Codex CLI, **Kimi (kimi-code CLI + Kimi Desktop
> work-mode, whose workspace is this repo)**, Antigravity/agy, and others. "Codex" below
> generalizes to "you, the external agent" unless a rule names a specific tool.

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

## 0.0. External-agent contract (READ FIRST — Kimi/Codex/agy alike)

1. **You build — a Claude session verifies.** Your work product is a branch/diff/artifact
   that an interactive Claude session independently reviews, tests and merges
   (generator≠grader). **Never merge your own work, never push to `main`, never arm
   auto-merge, never deploy.** Prepare; don't ship.
2. **Legge 5 (absolute):** never publish anything outward **on your own initiative** — no
   Instagram, no email, no WhatsApp, no client-facing sends. Drafts you originate stop at
   `drafted` in the review queue; the owner publishes. **One narrow exception, ruled by Zero
   on 2026-09-01:** an EXPLICIT publish order for a News Room article, a WR2 carousel or a
   WR3 video, reaching you through an authenticated channel from Zero or Damar, is not your
   initiative — it is the human's act, executed, and you carry it out. What verifies the
   artefact is its own gate (the News Room fact gate, `approval_state`, `--confirm`), not a
   second human: the gates are unchanged and fail-closed, so an order on an artefact whose
   gate is red publishes nothing. Nothing else widens — you still never merge, arm, deploy,
   or send to a client.
3. **PII boundary (UU PDP / SYMBIOSIS Law 2, non-negotiable):** client PII (KTP, passport,
   NPWP, akta, CRM records, OSINT) must never be transcribed into cloud outputs, logs,
   artifacts or prompts. DB access is read-only (`nuzantara_readonly`); if a task seems to
   need client rows, STOP and surface it.
4. **Worktree discipline applies to YOU** (§0.5): the Claude-side hooks do NOT bind you —
   the convention does. Mutations happen in `.worktrees/<lane>-<task>/`, never in the main
   checkout. Kimi Desktop: ask the operator to point the workspace at a worktree lane.
5. **Off-limits files:** `zantara_core.py` (edit only via its own rules), `fly.toml`,
   `.env*`, `apps/bali-intel-scraper/backend/db/migrations/env.py` (corrected 2026-08-21 — the old
   `alembic/env.py` names no file in this repo), curated datasets (data-plane guard), the WR2 queue JSONs
   (canonical writers only).
6. **Scope tightly, don't improvise.** If the task is ambiguous, state your assumption in
   one line and take the narrowest reading — do NOT invent adjacent work (this is aimed
   especially at K3's known over-proactivity).

## 0. Machine Identification (IMPORTANT)

**You MUST identify which machine you are running on at session start.**

**Three machines** exist on the local network (Tailscale tailnet `balizero`):

| Machine    | User        | Hostname    | Role                                                              |
| ---------- | ----------- | ----------- | ----------------------------------------------------------------- |
| **Pro**    | `nuzantara` | `Nuzantara` | Workhorse — dev, DB, Qdrant, Ollama, 224 daemon, deploy (48GB)    |
| **Mini**   | `nuzantara` | `Mini-Pro2` | Server H24 — Ollama dedicato, cron pesanti (24GB)                 |
| **Air-M5** | `balizero`  | `Air-M5`    | **THIN-CLIENT dev** — editing + agenti; pesante → `ssh pro`       |

**At every session start, run this check:**

```bash
echo "Machine: $(whoami)@$(hostname)" && \
case "$(hostname)" in Nuzantara) OTHER=mini ;; Mini-Pro2) OTHER=pro ;; Air-M5) OTHER=pro ;; *) OTHER=pro ;; esac && \
ssh -o ConnectTimeout=3 $OTHER 'echo "Peer: $(whoami)@$(hostname)"' 2>/dev/null || echo "Peer: UNREACHABLE" && \
LOCAL_HEAD=$(git log --oneline -1 2>/dev/null) && \
REMOTE_HEAD=$(ssh -o ConnectTimeout=3 $OTHER 'cd ~/nuzantara 2>/dev/null; git log --oneline -1' 2>/dev/null) && \
if [ "$LOCAL_HEAD" = "$REMOTE_HEAD" ]; then echo "Git sync: OK ($LOCAL_HEAD)"; else echo "Git sync: OUT OF SYNC! Local=$LOCAL_HEAD Remote=$REMOTE_HEAD"; fi
```

This tells you:

- `whoami=nuzantara`, `hostname=Nuzantara` → you are on **Pro** (workhorse)
- `hostname=Mini-Pro2` → you are on **Mini** (server)
- `whoami=balizero`, `hostname=Air-M5` → you are on **Air-M5** (**thin-client** — see §0.1 below, it changes everything)
- Whether the peer machine is reachable, and whether both repos are on the same commit

**Always prefix your first response with which machine you're on**, e.g. "[Pro]", "[Mini]", or "[Air-M5]".

> ⚠️ **CRITICAL — peer-unreachable is NOT a license to go local.** On Air-M5 the peer is the **Pro**, and `ssh pro` is the *destination* for all heavy work, not just a git-sync peer. If the session-start git-sync check reports the peer "UNREACHABLE", that means **sync is unverified** — it does **NOT** mean "do the heavy task locally on M5 instead". Heavy work that needs the Pro still routes via `ssh pro`; if `ssh pro` itself fails, **STOP and tell the operator**, do not fall back to a local install. (This was the #1 failure mode in the M5 thin-client audit, 2026-06-02.)

**SSH between machines:** `ssh mini` / `ssh pro` (from any node) — uses Tailscale. From Air-M5: `ssh pro` (alias for `nuzantara@100.107.22.111`).
See `docs/PRO_AIR_CONNECTION.md` for full details.

---

## 0.1. Air-M5 Thin-Client Routing Map (READ if `hostname=Air-M5`)

**Air-M5 is a THIN-CLIENT.** You edit code, run agents, commit, and do light research **locally** on M5. Everything heavy — inference, vector DB, SQL, rendering, deploy, the 224-daemon fleet — **lives on the Pro** and is reached via `ssh pro` (or `ssh mini`). M5 deliberately does **not** have Ollama, Postgres, Qdrant, `fly`, or the daemon stack.

### HARD RULE R1 — Heavy tools are NEVER installed on M5

Do **NOT** `brew install` / `ollama pull` / compile / `docker run` heavy tooling on M5 — **not even as an "option B" / alternative / fallback.** Route to the Pro.

| Asked to… | ❌ WRONG (FAIL) | ✅ CORRECT |
| --- | --- | --- |
| use **ffmpeg** (video concat/render) | `brew install ffmpeg` on M5 | `ssh pro 'bash -lc "ffmpeg …"'` (Pro has the full ffmpeg) |
| compile C/C++ (**cmake/make**) heavy build | build locally on M5 | `ssh pro` for the build; only trivial builds stay local |
| **cloudflared** tunnel | install + launchd on M5 | tunnels live on Pro → `ssh pro` |
| **ghostscript** / heavy PDF batch | `brew install ghostscript` on M5 | `ssh pro` for the processing |
| **Playwright** mass scrape (100s of pages) | run headless chromium on M5 | `ssh pro` (heavy compute) |
| compile **torch / CUDA / MPS** from source | build on M5 | `ssh pro`/`ssh mini` (M5 = thin) |
| **docker** containers (>~1GB) | `docker run` on M5 | `ssh pro` |

> If a tool is genuinely lightweight (`jq`, `ripgrep`, `eza`, a pip dep in the local `.venv`) installing it on M5 is fine. The line is **heavy compute / persistent services**, which always belong on the Pro.

### HARD RULE R2 — LLM models & Ollama: Pro/Mini only

M5 has **no `ollama`** by design. Never `ollama pull` or `brew install ollama` on M5 — not even a smaller fallback model.

| Asked to… | ✅ CORRECT |
| --- | --- |
| run/`pull` any model (`deepseek-r1`, `qwen3.5`, `qwen2.5vl`) | `ssh pro 'bash -lc "ollama run <model>"'` (Pro/Mini hold the models) |
| OCR / vision (`qwen2.5vl`) | `ssh pro` — Ollama binds `127.0.0.1:11434`, **closed** to M5 |
| embed batch (`bge-m3`) | `ssh pro` / `ssh mini` |

Lightweight **cloud** LLM clients **are** fine on M5 (they're already set up): `agy` (Gemini), `codex`, `kimi` (`~/.kimi-code/bin/kimi`, armed M5+Pro+Mini), `nlm` (NotebookLM). Use them directly. (DeepSeek API RETIRED 2026-07-19 — never route to it; local `deepseek-r1:32b` Ollama weights on Pro/Mini are unrelated and stay.)

### HARD RULE R3 — DB & vector store: exact access per service

The DB and vectors live on the Pro. M5 reaches them — it does **NOT** install or replicate them.

| Service | From M5 | Command / value |
| --- | --- | --- |
| **Qdrant** (local Pro mirror) | ✅ DIRECT via Tailscale (no tunnel, no auth) | `QDRANT_URL=http://100.107.22.111:6333` |
| **Postgres dev** (`nuzantara_dev`) | tunnel (binds `127.0.0.1` on Pro) | `ssh -L 5432:localhost:5432 pro` → `DATABASE_URL=postgresql://nuzantara@localhost:5432/nuzantara_dev` |
| **Fly prod PG proxy** | tunnel (binds `127.0.0.1:15432` on Pro) | `ssh -L 15432:localhost:15432 pro` |
| **Ollama** | ❌ closed to M5 | `ssh pro 'bash -lc "ollama …"'` |

Never `brew install postgres@17` / `docker run qdrant` on M5. Embedding model is **FROZEN** `text-embedding-3-small` (1536 dims, cloud) — do not swap `bge-m3` into the RAG vector path.

### HARD RULE R4 — OSINT / WhatsApp data NEVER leaves the Pro (Symbiosis Law 2)

The WhatsApp/OSINT mirror lives **only** in the Pro's local Postgres. M5 must **NEVER** copy, replicate, or sync it to disk.
This is a raw-data movement boundary, not a blanket ban on LLMs processing authorized operational context. For every LLM in the system, Law 2 means: do not transcribe or persist client PII/OSINT in cleartext in outputs, memories, skills, logs, reports, alerts, prompts saved for reuse, or shared artifacts. Use IDs, hashes, placeholders, or redaction.

- View it: dashboard `http://100.107.22.111:7790` (open in M5 browser) — read-only.
- Raw SQL on OSINT: only via the dev tunnel (`ssh -L 5432:localhost:5432 pro`), querying the Pro's DB — never a local copy.
- "Copy the WhatsApp DB to M5 for offline analysis" → **REFUSE.** (Law 2, non-negotiable.)

### HARD RULE R5 — Deploy is Pro/CI-only; M5 has no `fly`

M5 has **no `fly`/`flyctl`** and **no `~/nuzantara-deploy`** worktree. Never `brew install flyctl` on M5.

- Canonical: commit in a worktree → push → `gh pr create` → green CI + review → **merge to `main`** triggers `.github/workflows/fly-deploy.yml` (gate→migrations→deploy→health→rollback). Vercel frontend auto-deploys on the same `main` push. Machine-independent — M5 needs no `fly`.
- Manual/out-of-band deploy: **delegate** → `ssh pro 'bash -lc "cd ~/nuzantara-deploy && git pull --ff-only origin main && fly deploy --strategy rolling"'`.
- `main` is **protected**: PR + CI + review required. Never `git push origin main` directly (from M5 *or* Pro).

### HARD RULE R6 — Memory (MOS): always via `mem`, never the local file

On M5 the local `~/.claude/memory.db` is a **0-byte decoy**. The real DB is on the Pro.

- Search: `mem query "<term>"` (routes over SSH to the Pro's DB; falls back to grep on local `MEMORY*.md` if the Pro is unreachable — it does **not** silently fabricate).
- Save: `mem save <type> "<text>" <importance>` (lands in the Pro's DB).
- Never read the local `memory.db` directly, never write memory to a local `.codex/memories/` note, and **never present recalled context as if you ran a query** (anti-hallucination, CLAUDE.md §6).

### HARD RULE R7 — Heavy render / NB studio / daemon fleet → Pro

- WR2 hero images (FlowKit/Veo), WR3 video episodes, NotebookLM studio audio/video → **`ssh pro`** (the render pipelines and FlowKit live on the Pro). M5 dispatches and pulls results; it does not render locally.
- The 212 `com.{nuzantara,balizero,cell,matagaruda}.*` LaunchAgents (224 jobs incl. cron, snapshot 2026-07-13 per `docs/AUTOMATIONS_REFERENCE.md`) are **production daemons** — they run on Pro/Mini only. Never load/install them on M5.

### MCP servers from M5

| MCP | On M5 | Note |
| --- | --- | --- |
| `notebooklm-mcp`, `nuzantara-fetch`, `playwright`, `ocr-tesseract` | ✅ local | work directly |
| `nuzantara-mcp`, `nuzantara-mcp-advanced`, `github` | 🔧 light remote clients | need their small venv + env tokens |
| `postgres-nuzantara` | ➡️ **route via Pro** | needs Fly proxy `:15432` + Keychain `nuzantara-postgres-readonly`, neither on M5 |
| `ga4-analytics` | ⚠️ sovereignty | uses a **prod** service-account JSON — prefer Pro, or confirm with operator |

---

### Git Sync Architecture (updated 2026-05-25)

Both machines work on `main` branch only. Sync is **automatic** via husky post-commit hooks:

- **Pro commits** → Mini auto-pulls (`git pull pro main --ff-only`)
- **Mini commits** → Mini auto-pushes to Pro (`git push pro main`)
- **GitHub** is updated by Pro only via `git push origin main`

**Never** create an `air` or `mini` branch. **Never** push from Mini to `origin`. Log: `~/.openclaw/logs/git-sync.log`.

---

## 0.5. Agent Worktree Discipline (L5.1, 2026-05-25)

**MANDATORY for any Codex session that mutates code in this repo.**

This repo is shared with 5+ Claude sessions + occasional Gemini agy on the same Pro machine. All processes default to `cwd=/Users/nuzantara/nuzantara` (main checkout). Concurrent file mutations have produced 32+ sibling-orphan stash in 24h. To prevent:

### Before any mutation

```bash
# Create dedicated worktree
python scripts/agent_start.py --lane <wr2|infra|backend-rag|ops|...> --task-id <slug>
# Output: WORKTREE_READY /Users/nuzantara/nuzantara/.worktrees/<lane>-<task-id>
cd <output-path>
# Now spawn codex exec HERE, not in main checkout
```

### For codex exec invocations

`codex exec` inherits cwd from spawner. Wrong pattern:

```bash
# Wrong (creates orphan in main):
codex exec --sandbox workspace-write "fix bug X"
```

Right pattern:

```bash
WT=$(python scripts/agent_start.py --lane infra --task-id codex-bug-x | tail -1)
cd "$WT" && codex exec --sandbox workspace-write "fix bug X"
```

### Hooks active

PreToolUse hook `~/.claude/hooks/worktree_isolation.py` blocks Claude Code Bash git ops in main checkout. `~/.claude/hooks/worktree_file_write_check.py` blocks Claude Code Edit|Write|MultiEdit in main. These hooks are CLAUDE-SIDE only — Codex CLI runs in its own sandbox and is NOT subject to them. **Discipline relies on Codex authors following this convention manually.**

### Kill switch

```bash
export AGENT_WORKTREE_ENFORCEMENT=false
```

Use only for emergency / hotfix / cicatrix-fix.

### Reference

- L1 broker: `docs/runbooks/agent-worktree-broker.md`
- L2 lease: `docs/runbooks/redis-lease-registry.md`
- L5.1 spec: `research/operations/specs/L5.1-agent-worktree-enforcement-2026-05-25.md`
- Panel synthesis: `research/operations/specs/L5.1-panel-synthesis-2026-05-25.md`

---

## 1. Project Overview

**Name:** Nuzantara (Zantara)  
**Version:** 5.2.0  
**Type:** Production AI-powered business intelligence platform for Bali Zero  
**URL:** https://kita.balizero.com

### Architecture

**Monorepo structure:**

- `apps/mouth/` - Next.js frontend (Vercel)
- `apps/backend-rag/` - Python FastAPI RAG backend (Fly.io)
- `apps/admin-dashboard/` - Admin UI
- `apps/webapp/` - Web application
- `apps/bali-intel-scraper/` - Intelligence gathering
- `apps/nuzantara-mcp/` - MCP server v2.1 (inspect the server for its live capability inventory)
- `apps/nuzantara-mcp-advanced/` - Advanced MCP (Fly.io ops, diagnostics)
- `apps/nuzantara-mcp-browser/` - Browser automation MCP
- `apps/graph-engine/` - Graph processing engine
- `apps/kbli-voice/` - KBLI voice interface
- `apps/evaluator/` - Quality assurance
- `apps/zantara-media/` - Editorial content system
- `packages/core/` - Core libraries

### Tech Stack

- **Backend:** Python 3.11+, FastAPI. Live counts: `python3 scripts/docs_sync.py --json`
- **Frontend:** Next.js, TypeScript, Tailwind CSS
- **Databases:** PostgreSQL (relational), Qdrant (vector), Redis (cache)
- **Infrastructure:** Fly.io (backend), Vercel (frontend)
- **Knowledge Graph:** live counts are generated, not stored in this file
- **Vector Collections:** canonical registry: `backend/core/collection_registry.py`; live counts: `python3 scripts/docs_sync.py --json`
- **Embedding Model:** `text-embedding-3-small` (1536 dims) — **NEVER CHANGE**

## 2. Agent Behavior Rules (IMPORTANT)

**DO NOT ask the user to write code.** You are authorized to edit, write, and execute code directly.

- Use `Edit`, `Write`, `Bash` without asking permission
- `defaultMode: acceptEdits` means act first, ask if blocked
- Only ask if you genuinely need user input (e.g., choosing between multiple valid approaches)
- **NEVER** ask "should I write this?" or "do you want me to...?" — just do it

**Exception:** Only ask for decisions on:

- Architecture choices with trade-offs (use `AskUserQuestion`)
- Production deployments (use risk/reversibility judgment)
- Destructive operations (rm, git reset --hard, etc.)

## 4. Golden Rules (ENFORCE STRICTLY)

1. **Virtualenv Mandatory** - Never use system Python. Always activate venv first.
2. **No Root Execution** - Use `PYTHONPATH=. python -m backend.module`, never run modules directly.
3. **Path Discipline** - Absolute imports only: `from backend.core import config`, never relative.
4. **Async First** - Use `httpx` for HTTP, never `requests`. All I/O must be async.
5. **Type Hints Required** - Every function must have full type annotations.
6. **No Hardcoded Secrets** - Use environment variables or secrets manager.
7. **Data/Logic Separation** - Business logic separate from data access layer.
8. **Clean Logging** - Use `logger`, never `print()` statements.
9. **Quality Standards** - Tests, error handling, graceful degradation required.
10. **Verify Sources** - Never presume, always verify against actual data sources.

## 5. Development Commands

### Backend (FastAPI)

```bash
# Activate virtualenv
source venv/bin/activate  # or: . venv/bin/activate

# Run backend locally
cd apps/backend-rag
PYTHONPATH=. python -m uvicorn backend.main:app --reload --port 8000

# Run tests
PYTHONPATH=. pytest tests/ -v
PYTHONPATH=. pytest tests/test_specific.py::test_function -v

# Type checking
mypy backend/

# Linting
ruff check backend/
ruff format backend/

# Database migrations (custom SQL system — NOT Alembic)
# Create: backend/db/migrations_v2/NNN_name.sql with mandatory `-- === ROLLBACK ===` marker
PYTHONPATH=. python -m backend.db.migrate apply-all
PYTHONPATH=. python -m backend.db.schema_audit
```

### Frontend (Next.js)

```bash
cd apps/mouth
npm run dev        # Development server
npm run build      # Production build
npm run start      # Production server
npm run lint       # ESLint
npm run test       # Jest tests
```

### Deployment

```bash
# Backend to Fly.io
fly deploy --config apps/backend-rag/fly.toml --app nuzantara-rag

# Frontend to Vercel (auto-deploy on git push to main)
vercel --prod
```

## 4. Critical Paths

### Backend Structure

```
apps/backend-rag/
├── backend/
│   ├── app/              # FastAPI app
│   │   ├── routers/      # API endpoints (live inventory: docs_sync.py --json)
│   │   ├── services/     # App-level services (CRM, auth, metrics)
│   │   ├── setup/        # app_factory, router_registration, service_initializer
│   │   ├── dependencies.py  # ⚠️ Imported by ALL routers — test before deploy
│   │   └── main.py       # Entrypoint (alias for main_cloud.py)
│   ├── services/         # Core business logic
│   ├── core/             # Config, security, logging
│   ├── prompts/          # ⭐ Prompt Single Source of Truth (see below)
│   ├── channels/         # 7 channels (whatsapp, telegram, instagram, etc.)
│   ├── llm/              # LLM clients (Gemini, Ollama, OpenRouter)
│   └── migrations/       # custom SQL (legacy 001→124 py; live v2 092→246 sql in backend/db/migrations_v2/)
├── tests/                # Unit and integration tests
├── .venv/                # ⚠️ ALWAYS .venv on Pro and Mini
└── fly.toml
```

**IMPORTANT:** Routers in `backend/app/routers/`, NOT `backend/routers/`. Services in both `backend/services/` and `backend/app/services/`.

### Prompt Architecture (Single Source of Truth)

```
backend/prompts/
├── __init__.py              # Re-exports ZANTARA_MASTER_TEMPLATE, CREATOR_PERSONA, TEAM_PERSONA
├── zantara_core.py          # ⭐ THE file — all prompt sections as composable constants
├── channel_overlays.py      # Per-channel config (word limits, markdown, emoji)
├── few_shot_examples.py     # Consolidated few-shot examples
├── zantara_persona.py       # Backward compat wrapper → imports from zantara_core
├── whatsapp_persona.py      # Dynamic builder for WhatsApp context → imports from zantara_core
└── zantara_prompt_builder.py # Legacy builder → imports from zantara_core
```

**Rule:** To add/edit ANY Zantara prompt rule, edit ONLY `zantara_core.py`. All consumers import from it.

**Sections in `zantara_core.py`:**
`SECURITY_BOUNDARY` · `TOOL_USAGE_POLICY` · `SYSTEM_INSTRUCTIONS` · `KNOWLEDGE_GOVERNANCE` ·
`LANGUAGE_PROTOCOL` · `GREETING_RULES` · `CITATION_RULES` · `INTERNAL_MONOLOGUE` ·
`ESCALATION_PROTOCOL` · `CRASH_PROTOCOL` · `CLOSING_PHRASES` · `CREATOR_PERSONA` ·
`TEAM_PERSONA` · `ZANTARA_MASTER_TEMPLATE`

### Frontend Structure

```
apps/mouth/
├── app/              # Next.js App Router
├── components/       # React components
├── lib/              # Utilities
├── public/           # Static assets
└── styles/           # Tailwind CSS
```

## 5. Domain-Specific Knowledge

### KBLI (Indonesian Business Classification)

**Storage:** Qdrant vector collection  
**Format:** **FLAT payload structure**, NOT nested  
**Fields:** `code`, `title_id`, `title_en`, `description`, `category`, `section`

❌ **WRONG:**

```json
{
  "code": "47911",
  "details": {
    "title": "...",
    "description": "..."
  }
}
```

✅ **CORRECT:**

```json
{
  "code": "47911",
  "title_id": "Perdagangan Eceran...",
  "title_en": "Retail Sale...",
  "description": "...",
  "category": "G",
  "section": "Perdagangan"
}
```

### Pricing System

**CRITICAL:** All prices MUST come from `PricingTool`.  
**Never:** Hardcode, guess, or cache prices outside the tool.  
**Files:** Reference only `PRICING_REFERENCE.md` and `VISA_TYPES_REFERENCE.md`.

### Evidence Scoring System

Classification confidence thresholds:

- **< 0.15:** `ABSTAIN` - Insufficient confidence, refuse to answer
- **0.15 - 0.60:** `CAUTIOUS` - Provide answer with clear uncertainty disclaimer
- **> 0.60:** `NORMAL` - Confident answer

### Embedding Model

**Model:** `text-embedding-3-small` (OpenAI)  
**Dimensions:** 1536  
**CRITICAL:** This model is FROZEN. Changing it would invalidate the existing vector index.
**Never:** Switch to another model without explicit authorization and full re-indexing plan.

## 6. MCP Servers

**Primary:** `apps/nuzantara-mcp/` (v2.1, FastMCP, stdio transport)
**Capabilities:**

- **115 Tools** across 24 modules (CRM, portal, intel, content, analytics, knowledge, comms, drive, sheets, workflows, admin, health, google_bridge, journey, pricing, invoicing, compliance, memory, langsmith, legal, prime, federation, naga, heartbeat)
- **10 Prompts** for guided workflows
- **5 Resources** for knowledge base access
- **8 Workflow Chains** for deterministic automation (daily_ops_autopilot, new_client_onboarding, practice_lifecycle_check, intel_pipeline, weekly_report, client_health_monitor, compliance_autopilot, journey_accelerator)

**Additional MCP servers:**

- `apps/nuzantara-mcp-advanced/` — Fly.io ops, deployment readiness, code search, diagnostics
- `apps/nuzantara-mcp-browser/` — Browser automation

## 7. Deployment Architecture

### Production Stack

- **Frontend:** Vercel (CDN, Edge Functions)
- **Backend:** Fly.io `nuzantara-rag` (Asia region)
- **Databases:**
  - PostgreSQL: Fly.io managed
  - Qdrant: Fly.io app
  - Redis: Upstash or Fly.io

### Environment Variables

**Required:**

- `OPENAI_API_KEY` - For embeddings
- `DATABASE_URL` - PostgreSQL connection
- `QDRANT_URL`, `QDRANT_API_KEY` - Vector DB
- `REDIS_URL` - Cache
- `JWT_SECRET` - Authentication
- `FLY_API_TOKEN` - Deployment (CI/CD)

## 8. Testing Strategy

```bash
# Unit tests (fast)
PYTHONPATH=. pytest tests/unit/ -v

# Integration tests (slower)
PYTHONPATH=. pytest tests/integration/ -v

# E2E tests (slowest)
PYTHONPATH=. pytest tests/e2e/ -v

# Coverage report
PYTHONPATH=. pytest --cov=backend --cov-report=html tests/
```

**Standards:**

- Unit tests: > 80% coverage
- Critical paths: 100% coverage
- All new features: tests required before merge

## 9. Code Style & Patterns

### Python (Backend)

```python
# Good: Async, typed, clean logging, persistent client
from typing import Optional
from backend.core.logging import logger

async def fetch_kbli_data(code: str) -> Optional[dict]:
    """Fetch KBLI data from Qdrant."""
    try:
        result = await qdrant.search(
            collection_name="kbli",
            query_vector=embedding,
            limit=1
        )
        logger.info(f"KBLI search successful: {code}")
        return result[0] if result else None
    except Exception as e:
        logger.error(f"KBLI search failed: {code}", exc_info=True)
        raise
```

### TypeScript (Frontend)

```typescript
// Good: Type-safe, error handling
interface KBLIResponse {
  code: string;
  title_en: string;
  description: string;
}

async function fetchKBLI(code: string): Promise<KBLIResponse | null> {
  try {
    const response = await fetch(`/api/kbli/${code}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error("KBLI fetch failed:", error);
    return null;
  }
}
```

## 10. Common Pitfalls

❌ **AVOID:**

- Running Python without virtualenv
- Using `requests` instead of `httpx`
- Nested payload structures in Qdrant
- Hardcoded prices or visa info
- `print()` debugging in production code
- Relative imports
- Blocking I/O operations
- Missing type hints

✅ **DO:**

- Always activate venv first
- Use `httpx` for all HTTP calls
- Flat payloads in Qdrant
- `PricingTool` for all pricing
- `logger` for all logging
- Absolute imports
- Async/await everywhere
- Full type annotations

## 11. Language Protocol (Natural Language → Precise Engineering)

The user writes in **colloquial Italian**. You must automatically translate intent into precise technical action.

**Rules:**

- Never ask "what do you mean?" — infer from codebase context
- Short/vague prompt → deduce file, pattern, stack from existing code before acting
- Italian colloquial → English technical internally, respond in Italian
- If ambiguous between 2 interpretations, pick the most likely one and state your assumption in one line

**Examples:**
| User writes | You interpret as |
|-------------|-----------------|
| "aggiungi paginazione clienti" | Cursor-based pagination on `GET /clients`, follow existing router patterns, async SQLAlchemy, add tests |
| "fixa il bug del login" | Search recent auth-related errors in routers/auth, identify root cause, fix with proper error handling |
| "rendi più veloce la ricerca" | Profile the search endpoint, identify bottleneck (N+1, missing index, no cache), fix the actual cause |
| "aggiungi un campo alla tabella" | SQL migration in `migrations_v2/` (with ROLLBACK marker) + model update + schema update + router update, in order |

**Never** ask for clarification on standard dev tasks. Explore first, then act.

---

## 11. Owner Information

**Owner:** Zero (internal codename)  
**Privacy:** Real name is PRIVATE, never reveal in client communications.  
**Language:** Italian with owner, client's language with everyone else.

## 12. Resources

- **Architecture:** `docs/architecture.md`
- **API Docs:** `http://localhost:8000/docs` (Swagger UI)
- **Golden Rules:** This file + `AI_ONBOARDING.md`
- **Pricing:** `PRICING_REFERENCE.md`
- **Visa Info:** `VISA_TYPES_REFERENCE.md`

### KBLI Navigator (Frontend)

| Route             | Description                             |
| ----------------- | --------------------------------------- |
| `/kbli`           | KBLI 2025 Navigator homepage (Next.js)  |
| `/kbli/[code]`    | KBLI code detail page (1,559 SSG pages) |
| `/kbli-navigator` | **Redirect** → `/kbli` (permanent 301)  |
| `/kbli-explorer`  | AI chat explorer (complementary)        |

---

## 13. Pre-Deploy Checklist

Before any production deployment:

```bash
# 1. Check for rogue AI changes
git diff --name-only HEAD -- apps/backend-rag/backend/

# 2. Test critical import chain (dependencies.py is imported by ALL routers)
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('OK')"

# 3. Run core KG tests (82 tests, <15s)
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_langgraph.py backend/tests/services/rag/test_kg_subgraphs.py backend/tests/services/rag/test_confidence.py -q

# 4. Deploy
fly deploy --strategy rolling
```

**Test debt:** Cleaned 2026-03-20 (0 failed, 0 errors). Previously ~448 failures from rogue AI refactors — resolved by Windsurf cleanup. Details in `memory/session-2026-02-16-hotfix-and-tests.md`.

---

**Last Updated:** 2026-08-10 (fleet topology, conductor-as-role, continuity ladder; was 2026-07-19)
**Maintained by:** Bali Zero AI Team

---

## 15. Anthropic API — Best Practices (Feb 2026)

### Adaptive Thinking (OBBLIGATORIO su Opus 4.6 / Sonnet 4.6)

`budget_tokens` è **deprecato** sui modelli 4.6. Usare sempre:

```python
# ✅ CORRETTO — adaptive thinking
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=8192,
    thinking={"type": "adaptive"},
    output_config={"effort": "medium"},  # "max" | "high" | "medium" | "low"
    messages=[...]
)

# ❌ DEPRECATO — non usare su 4.6
thinking={"type": "enabled", "budget_tokens": 10000}
```

- `effort="medium"` → raccomandato per workflow RAG/tool
- `effort="high"` → default, per query complesse
- `effort="max"` → solo per i problemi più difficili (solo Opus 4.6)
- L'interleaved thinking (tra tool call) è **automatico** su Opus 4.6 con adaptive

### Prompt Caching KBLI / Knowledge Base (-90% costo)

Ogni volta che scrivi chiamate API che includono il knowledge base KBLI, system prompt largo,
o definizioni di tool che non cambiano, usa `cache_control`:

```python
# ✅ System prompt con cache (risparmio 90% su letture successive)
system=[
    {
        "type": "text",
        "text": KBLI_SYSTEM_PROMPT_OR_KNOWLEDGE,
        "cache_control": {"type": "ephemeral", "ttl": 3600}  # 1 ora per batch
    }
]

# Monitoraggio cache
print(response.usage.cache_read_input_tokens)     # token da cache
print(response.usage.cache_creation_input_tokens)  # token scritti in cache
```

Prezzi Sonnet 4.6: scrittura 5min $3.75/MTok, scrittura 1h $6.00/MTok, **lettura $0.30/MTok**.
Minimo cacheable: 1.024 token.

### Batch API per elaborazioni massive (50% sconto)

Per test suite, analisi bulk KBLI, valutazioni:

```python
# Stacking: Batch 50% off + cache reads 90% off = costi minimi
batch = client.messages.batches.create(requests=[...])
```

### Tool Use — pattern corretti

```python
# Strict schema per produzione
tools = [{"name": "...", "strict": True, "input_schema": {...}}]

# Fine-grained streaming per tool con output grande
tools = [{"name": "kbli_search", "eager_input_streaming": True, ...}]

# Tool result caching per documenti grandi
{"type": "tool_result", "content": [{"type": "text", "text": doc, "cache_control": {"type": "ephemeral"}}]}
```

### Modelli consigliati per Nuzantara

| Uso                       | Modello                    | Perché                                       |
| ------------------------- | -------------------------- | -------------------------------------------- |
| RAG complesso, reasoning  | `claude-sonnet-4-6`         | Knowledge cutoff gen 2026, adaptive thinking |
| Routing / classificazione | `claude-haiku-4-5-20251001` | $1/$5 MTok, velocissimo                      |
| Task critici              | `claude-opus-4-6`           | 128K output, effort=max                      |
| Spiegazioni KBLI          | `claude-haiku-4-5-20251001` | Già configurato in kbli_notebook.py          |

---

## 16. Memory (MOS) — dove leggere la conoscenza di progetto

La memoria di progetto (decisioni, scoperte, fatti, lessons) vive come file Markdown qui:

- **Pro**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/*.md` (388+ file)
- **Air-M5**: `~/.claude/projects/-Users-balizero-Desktop-nuzantara/memory/*.md` (sincronizzati dal Pro via hub-daemon)
- **Indice**: `MEMORY.md` nella stessa dir — leggi questo PRIMA per orientarti (1 riga per memory).

Per interrogarla:

- Comando `mem query "<termine>"` (FTS5 sul DB `memory.db`). Su **Pro** funziona diretto. Su **Air-M5** `mem` usa SSH-al-Pro per il DB ricco, con fallback grep sui `.md` locali se il Pro è irraggiungibile.
- In alternativa (sempre disponibile, zero dipendenze): leggi i `.md` direttamente col path sopra, o `grep -rl "<termine>" <memory-dir>/*.md`.

Codex NON carica la memory in automatico (a differenza di Claude che ha i SessionStart hook): leggi `MEMORY.md` + i `.md` rilevanti col path quando ti serve contesto storico del progetto.

## 17. Fleet, Conductor & Continuity (2026-08-09)

Binding roster + corrections: research/operations/2026-08-10-fleet-order-spec.md

**SSOT files:** cloud fleet = `FLEET_TOPOLOGY.json` (repo root) · local Ollama = `MODEL_TOPOLOGY.json` (unchanged) · rationale + four-groups study = `research/operations/2026-08-09-quattro-gruppi-e-continuita.md` · roles roster = FLOTTA-LLM doc referenced there.

**Full model roster × strengths × efforts: `MODEL_ROSTER.md`** — read it before choosing seats (Zero ruling 2026-08-14). Every conductor door (claude/codex/agy/kimi/qwen) reads `AGENTS.md`, so this is the shared denominator.

### 17.1 Conductor is a ROLE, not a model

- Zero may start the interactive session with **any frontier orchestrator**: Claude (Fable/Opus/Sonnet), Codex (Sol/Terra/Luna), agy/Antigravity, Kimi. Whoever conducts inherits the **same law**: this file, the harness (gears, Evidence Pack, verdicts), CLAUDE.md invariants. Same law, different door.
- The conductor **orchestrates and dispatches** agents per `FLEET_TOPOLOGY.json` role chains, assembles the Evidence Pack, and arms the mechanical ship path: PR → required checks → armed auto-merge → `fly-deploy.yml` on `main`. **No conductor hand-merges around checks.**
- Generator≠grader lifts to family level: the **Gear-2 verdict comes from a different family than the main builder**. Gear-3 verdict = **Opus 5 xhigh-effort check, no exceptions**, regardless of who conducts. **RULED 2026-08-20 (supersedes the 2026-08-19 gear split): Fable is out of the workflow entirely — Opus 5 reviews every gear now, Gear-3 and Gear 1-2 alike. Fable is never auto-spent anywhere; Zero may still select it manually.**
- Client-facing outputs (quotes, comms) remain **Anthropic-interactive-only**. PII remains **local-only**. Legge 5 unchanged.
- **REVIEW-È-INVOCABILE** (ruling Zero 2026-08-10, `research/operations/2026-08-10-fleet-order-spec.md` §3.2/§4): "serve review" is a dispatch instruction, never a parking state — "chi conduce non aspetta i grader: li convoca". The conductor invokes the grader per the role chains (§17.2 below / `FLEET_TOPOLOGY.json`) the moment a diff exists to judge; a PR is never parked on "waiting for review" without the grader having been dispatched.

### 17.1a Two consuls (RULED Zero 2026-09-06)

- **Fable 5.1** (Anthropic, Zero's interactive seat) and **GPT Astra** (OpenAI, ChatGPT desktop / Codex) are the two consuls of a campaign, with **full and equal powers**: merge, deploy, every authorization. **Each consul's work is reviewed by the other before it ships** — generator≠grader stays, lifted to consul level.
- Supersedes, for the consul seat only, the 2026-08-20 "Fable out of the workflow" ruling: Fable is still never auto-routed by any script, cron or role chain; Zero opens it by hand. Supersedes, for the Codex consul only, "no external seat ever merges or deploys": ship stays mechanical (PR → required checks → armed auto-merge → `fly-deploy.yml`), "merge" means arming that path, never a hand-merge around checks.
- Every mechanical required check still runs on consul PRs (CI, harness verdicts, R9 quorum). The cross-consul review is added on top of the machine gates, it does not replace one. Whether the Opus 5 xhigh on-disk gate stays mandatory for consul-shipped work is OPEN (PENDING-ARMS 2026-09-06) — default yes until Zero rules.
- Zero-only gates unchanged: ENFORCE, pack activation, sales opening, prices, refunds, GARUDA D-vs-E, public claims, budget.
- Non-consul seats get their fronts from the generals exam (`research/operations/generals-exam/EXAM.md`), never by self-declaration. Coordination protocol between consuls and generals: single-writer board, one append-only outbox per seat with a heartbeat line, TESTAMENT file per seat for succession (the 2026-09-05 consuls session is the precedent: `.worktrees/ops-visa-consuls-claude/.agent/consoli/BOARD.md`).

### 17.2 Continuity ladder — no line ever stops

When a seat hits quota or dies, escalate IN ORDER and log each hop in the task evidence:

1. **Rotate account, same model** (zero quality loss): Anthropic ×4 via OAuth profile swap (cswap-style), OpenAI ×2 via `CODEX_HOME=~/.codex-o2`.
2. **Substitute model within the role** per `FLEET_TOPOLOGY.json` chain (builder: sonnet→codex→glm · refuter: sol→k3→gemini · grunt: haiku→local…).
3. **Cross-family fallback**, marked `degraded_execution: true` in the Evidence Pack (the gate sees it).
4. **Queue, never silent-stop**: chain fully dead → park in PENDING-ARMS with reason + timestamp.

**Carve-outs (special ladders):**
- **Gear-3 harness gate (RULED 2026-08-20, supersedes the 2026-08-09 ruling):** **Opus 5 `effort=xhigh`**, rotating across ALL Anthropic accounts (AZ→A2→A3→A1). No fallback tier below it — Fable is out of the workflow, so there is no `gate_degraded: fable→opus` to record anymore. All Anthropic accounts dead → queue. Never pay per-token to unblock.
- **WR2 on-disk content gate (RULED 2026-08-20):** **Opus 5 `effort=xhigh`** — was unconditionally Fable; no fallback either way, window dead → SUSPEND.
- PII lanes = local models only → queue. Client-facing = Anthropic interactive only.

### 17.3 Account-lane mapping (lanes with borrowing, not round-robin)

Lanes are **home assignments, not fences**: each lane drains its home account first, then borrows automatically from the least-loaded other account — nothing sits idle, no line ever stops. Mapping (see `FLEET_TOPOLOGY.json` → `accounts`): **A1** antonellosiano interactive/architect · **A2** kaiser1987… subagents/build+Cowork · **A3** applevisionpro1987 cron/batch, **designated donor** (cron auto-pauses to free its window when the gate calls) · **AZ** zero (Team seat Premium) **gate primary** — the dedicated allowance for the final on-disk gate lives here (Opus 5 xhigh effort, RULED 2026-08-20; was Fable's dedicated weekly allowance) · **O1** antonellosiano (ChatGPT Pro) refuter-primary · **O2** zero (ChatGPT Pro) builders+refuter-backup.

### 17.4 Spend order

Flat subscriptions → Token Plan credits → local. Anything per-token (incl. Google overage credits) requires Zero's explicit GO (CLAUDE.md §5). Note: §15 above is 4.6-era; for 5-family API gotchas (thinking on by default, `max_tokens` covers thinking+answer, no temperature knob, min-cacheable 512, tokenizer ≈+30%) see CLAUDE.md §«5-family» and the fleet research doc.
