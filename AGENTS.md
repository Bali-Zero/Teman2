# AGENTS.md — Nuzantara door for external AI coding agents (Codex · Kimi · Gemini · …)

> Read by every AGENTS.md-standard agent: Codex CLI, **Kimi (kimi-code CLI + Kimi Desktop
> work-mode, whose workspace is this repo)**, Antigravity/agy, and others. "Codex" below
> generalizes to "you, the external agent" unless a rule names a specific tool.
>
> **This file is an INDEX, not a manual** (boot diet, 2026-09-10). What is below is what a
> session must know BEFORE it reads anything else. Everything else moved — nothing was
> deleted — into `docs/agents/` and the canonical docs named in the INDICE. Load a file when
> the task needs it, not at boot.

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
**PARABELLUM narrows that fence; it does not open it** (RULED 2026-09-10,
`docs/rules/RULINGS.md`). On a mission Zero has declared ORANGE, the ONE appointed Dux Sol
session ships its own mission — push, PR-open with auto-merge armed at once, queue merge,
deploy, prove-live — and a FRESH Sol session outside the contribution chain signs the final
on-disk gate, which only signs and never arms or alters the candidate. Every other external
seat — Astra, Kimi, Qwen, GLM, Gemini, and Sol itself whenever it is not the appointed Dux —
stays prepare-only. An undeclared mission is BLUE and the sentence above binds unchanged.

<!-- /CANON:builder-contract -->

---

## 0.0. External-agent contract (READ FIRST — Kimi/Codex/agy alike)

1. **You build — a Claude session verifies.** Your work product is a branch/diff/artifact
   that an interactive Claude session independently reviews, tests and merges
   (generator≠grader). **Never merge your own work, never push to `main`, never arm
   auto-merge, never deploy.** Prepare; don't ship. **The one narrow exception, RULED
   2026-09-10 (PARABELLUM, `docs/rules/RULINGS.md`):** if you are the Sol session that
   Zero and the imperators appointed Dux of a mission declared ORANGE, you release that
   mission yourself — push, PR-open with auto-merge armed at once, queue merge, deploy,
   prove-live — and a FRESH Sol session outside your contribution chain signs the final
   on-disk gate. That authority is per-mission and per-seat: it does not travel to any
   other seat, to a Sol session that was not appointed Dux, or to an undeclared mission,
   which is BLUE and binds you by the sentence above.
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

> Publishing mechanics for a News Room article or a WR2 carousel (destination, caption
> dry-run, live verification): `docs/agents/editorial-publishing-protocol.md`.

---

## 0. Machine identification (IMPORTANT)

**Identify your machine at session start and prefix your first response with it** — `[Pro]`,
`[Mini]` or `[Air-M5]`. Three machines on the Tailscale tailnet `balizero`:

| Machine    | User        | Hostname    | Repo path             | Role                                                              |
| ---------- | ----------- | ----------- | --------------------- | ----------------------------------------------------------------- |
| **Pro**    | `nuzantara` | `Nuzantara` | `~/Desktop/nuzantara` | Workhorse — dev, DB, Qdrant, Ollama, daemon fleet, deploy (48GB)   |
| **Mini**   | `nuzantara` | `Mini-Pro2` | `~/nuzantara`         | Server H24 — dedicated Ollama, heavy cron (24GB)                   |
| **Air-M5** | `balizero`  | `Air-M5`    | `~/nuzantara`         | **THIN-CLIENT** — editing + agents; anything heavy → `ssh pro`     |

SSH between machines (Tailscale): `ssh pro` / `ssh mini` / `ssh air`. On M5 the paths
`/Users/nuzantara/...` are DEAD — different user. Details: `docs/PRO_AIR_CONNECTION.md`.

> ⚠️ **peer-unreachable is NOT a license to go local.** On Air-M5 the peer is the Pro, and
> `ssh pro` is the *destination* for all heavy work, not merely a git-sync peer. "UNREACHABLE"
> means sync is **unverified**; it does NOT mean "do the heavy task locally on M5 instead".
> If `ssh pro` itself fails, **STOP and tell the operator** — never fall back to a local
> install. (The #1 failure mode of the M5 thin-client audit, 2026-06-02.)

Session-start check command, HARD RULES R1–R7 (what may never be installed on M5, where models,
DB, vectors, deploy, memory and heavy render live), the MCP-from-M5 table and the git-sync
architecture: **`docs/agents/m5-thin-client-routing.md`**.

---

## 0.5. Agent worktree discipline (L5.1, 2026-05-25) — MANDATORY

**Any session that mutates code in this repo works in a dedicated worktree, never in the main
checkout.** 5+ Claude sessions, Codex and agy share one checkout; concurrent mutation produced
32+ sibling-orphan stashes in 24h.

```bash
python3 scripts/agent_start.py --lane <wr2|infra|backend-rag|ops|docs|…> --task-id <slug>
# → WORKTREE_READY <repo>/.worktrees/<lane>-<task-id>
cd <that path> && codex exec --sandbox workspace-write "…"
```

`codex exec` inherits cwd from its spawner, so `cd` FIRST — spawning from the main checkout
creates an orphan there. The Claude-side PreToolUse hooks do **not** bind you: the convention
does. Kill switch, emergency/hotfix/cicatrix-fix only: `export AGENT_WORKTREE_ENFORCEMENT=false`.

Wrong/right `codex exec` patterns, the active hooks, the L1 broker, the L2 lease registry and the
L5.1 spec: **`docs/agents/worktree-discipline.md`** · `docs/runbooks/agent-worktree-broker.md`.

---

## 17.1 Conductor is a ROLE, not a model

- Zero may start the interactive session with **any frontier orchestrator**: Claude (Fable/Opus/Sonnet), Codex (Sol/Terra/Luna), agy/Antigravity, Kimi. Whoever conducts inherits the **same law**: this file, the harness (gears, Evidence Pack, verdicts), CLAUDE.md invariants. Same law, different door.
- The conductor **orchestrates and dispatches** agents per `FLEET_TOPOLOGY.json` role chains, assembles the Evidence Pack, and prepares the mechanical ship path: PR → required checks → armed auto-merge → `fly-deploy.yml` on `main`. Arming is the act of the mission's release owner — an authorized Claude session on BLUE, the appointed Dux Sol session on ORANGE (RULED 2026-09-10); every other external conductor (Codex/agy/Kimi) prepares and hands over, it never arms (Builder Contract 5). **No conductor hand-merges around checks.**
- Generator≠grader lifts to family level: the **Gear-2 verdict comes from a different family than the main builder**. The final on-disk gate is an **assignment to a qualified independent verifier outside the contribution chain, on the mission colour's gate seat — a fresh Claude session on Opus 5 xhigh in BLUE, a fresh Sol xhigh session in ORANGE — never cascading and never crossing colour, at every gear**, regardless of who conducts (RULED 2026-09-06→08 and 2026-09-10, `docs/rules/RULINGS.md`; supersedes the permanent-Opus reviewer of 2026-08-20). Work built by a seat that is not the mission's appointed Dux is always verified by that gate (Builder Contract 5). Fable 5.1 is never auto-spent: it enters only as the imperator window Zero opens with `--model`.
- **Two imperators, equal (Fable 5.1, Astra) · two generals, equal (Opus 5, Sol) · one temporary Dux per mission, appointed by the imperators** — ranks, chain of communication, boot packets and bootstrap prompts in `docs/architecture/dual-consul/army-map.md`. Parity widens no permission: outside a declared ORANGE mission, no external seat merges, arms or deploys, and even inside one the authority belongs to the single appointed Dux Sol session and to nobody else (RULED 2026-09-10). **Door line, binding on every battle-window session:** before executing, read `.claude/skills/modus/SKILL.md` and the window spec you were assigned, then state your mission's colour, your Dux role, the mandate id and your worktree path.
- Client-facing outputs (quotes, comms) remain **Anthropic-interactive-only**. PII remains **local-only**. Legge 5 unchanged.
- **REVIEW-È-INVOCABILE** (ruling Zero 2026-08-10, `research/operations/2026-08-10-fleet-order-spec.md` §3.2/§4): "serve review" is a dispatch instruction, never a parking state — "chi conduce non aspetta i grader: li convoca". The conductor invokes the grader per the role chains (§17.2 below / `FLEET_TOPOLOGY.json`) the moment a diff exists to judge; a PR is never parked on "waiting for review" without the grader having been dispatched.


Continuity ladder, account-lane mapping and spend order (§17.2–§17.4):
**`docs/agents/fleet-continuity.md`**. Roster and seats: `MODEL_ROSTER.md` ·
`FLEET_TOPOLOGY.json` · `docs/architecture/dual-consul/army-map.md`.

---

## Language protocol and owner privacy

- Zero writes **colloquial Italian**. Translate intent into precise technical action internally,
  reply in Italian. Never ask "what do you mean?" — infer from the codebase. If two readings are
  possible, take the narrowest, state the assumption in one line, and act.
- **Owner:** Zero (internal codename). The real name is **PRIVATE** — never reveal it in client
  communications. Italian with the owner, the client's language with everyone else.
- Worked examples of the Italian→engineering mapping: `docs/agents/language-protocol.md`.

## Anti-hallucination, PII and secrets — one line each

- **Anti-hallucination:** never cite the output of a tool you did not run in THIS turn, and never
  build on a path you have not just verified on disk. → `docs/rules/operations.md` §6.
- **PII is an OUTPUT boundary** (Builder Contract 4 · SYMBIOSIS Law 2 · UU PDP): processing under
  an authorized lane is allowed, transcribing it is not — no cleartext client PII or OSINT in any
  output, log, memory, report, alert or saved prompt. → `SYMBIOSIS.md`.
- **Secrets:** never echo, print or commit a credential. `${VAR:+SET}` reports presence,
  `${VAR:-default}` prints the value. → Builder Contract 3.

---

## INDICE — dove sta cosa

> Moved, not deleted. Open a line's file only when the task needs it.

**Moved out of this file on 2026-09-10 — all under `docs/agents/`:**

- `m5-thin-client-routing.md` ← session-start check, HARD RULES R1–R7, MCP-from-M5, repo sync
- `worktree-discipline.md` ← full §0.5: `codex exec` patterns, active hooks, broker/lease/spec
- `editorial-publishing-protocol.md` ← News Room + WR2 publish protocol (Damar/Zero orders)
- `project-overview.md` ← monorepo map, architecture, tech stack, frozen embedding model
- `behavior-and-golden-rules.md` ← act-don't-ask rules + the 10 Golden Rules
- `dev-commands.md` ← backend/frontend/deploy commands, testing, pre-deploy checklist
- `critical-paths.md` ← backend tree, prompt SSOT (`zantara_core.py`), frontend tree
- `domain-knowledge.md` ← KBLI flat payload, PricingTool rule, evidence scoring, resources
- `mcp-and-deployment.md` ← MCP inventory, production stack, required env vars
- `code-style.md` ← Python/TypeScript patterns, common pitfalls
- `anthropic-api-practices.md` ← §15, 4.6-era (stale; the paid-endpoint ban still binds)
- `memory-mos.md` ← where project memory lives, how to read it
- `fleet-continuity.md` ← §17 SSOT files, continuity ladder, account lanes, spend order
- `language-protocol.md` ← worked Italian→engineering examples

**Canonical docs this door defers to:**

- `SYMBIOSIS.md` ← the laws · `VADEMECUM.md` ← checklist before building · `INDEX.md` ← atlas
- `docs/rules/operations.md` ← PR contract, autonomous ops, anti-hallucination, hooks, escalations
- `docs/rules/RULINGS.md` ← every RULED decision, incl. PARABELLUM (2026-09-10) and routing bans
- `.claude/skills/modus/SKILL.md` ← gears + battle-window doctrine; `PENDING-ARMS.md` ← parked work
- `apps/backend-rag/CLAUDE.md` ← backend rules, data invariants, Postgres MCP, deploy lifecycle
- `MODEL_ROSTER.md` ← models × efforts · `FLEET_TOPOLOGY.json` / `MODEL_TOPOLOGY.json` ← fleet SSOT
- `docs/architecture/dual-consul/army-map.md` ← ranks, chain of communication, boot packets
- `.claude/rules/cicatrix-superscar.md` ← the 10 scar families; body via `scar query "<theme>"`

---

**Maintained by:** Bali Zero AI Team.
**Authoritative last update:** `git log -1 --format=%cd -- AGENTS.md` in the repo root.
