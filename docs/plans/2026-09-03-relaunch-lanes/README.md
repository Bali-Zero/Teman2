# Relaunch lanes — 2026-09-03

> Seven lanes, one file each, allocated to the machine that can actually prove the work.
> Written 2026-09-03 from `origin/main` (`c4d48071a7`), 22 open PRs, 8 live worktrees, the
> PENDING-ARMS rows opened 2026-08-24 → 2026-09-02, and the corner skills' LIVE STATE sections.
> Every lane file is a **prompt**: paste it as the first message of a fresh session. Every fact in
> it was measured when written and is a lead, not a truth — re-measure before building on it.

## Allocation

| Lane | File | Machine | Why this machine |
|---|---|---|---|
| A | `LANE-A-garuda-voa.md` | **M5** | Browser prove-live of the staff surface, TS + Python, Zero within reach for the step-5 decision |
| B | `LANE-B-mouth-closeout.md` | **M5** | TypeScript typecheck (Mini cannot — ledger row 2026-08-24), Vercel-served surfaces, WR3 worktree lives here |
| C | `LANE-C-visa-oracle.md` | **Mini** (+ one `ssh pro` step) | Python-only, pack signing, long replays; the freshness sentinel installs on Pro |
| D | `LANE-D-kbli-kg.md` | **Mini** | Postgres / Qdrant / KG lots, local Ollama, long runs; no TS |
| E | `LANE-E-bot-wa.md` | **Pro** | The WA runtime lives on Pro (outbox, codex daemon); real-thread batteries with Damar |
| F | `LANE-F-ci-truth.md` | **Mini** | GitHub-side only, no local build; keeps M5/Pro seats free |
| G | `LANE-G-fleet-align.md` | **each machine** | Live copies are per-machine; the hook refreshes are `operator[control-plane]` |
| — | `ZERO-DECISIONS.md` | Zero | Nine Legge-5 / operator items that no session may decide |

Order inside a machine: **M5** A then B (B has no dependency on A; run B first if Zero has not
decided step 5 yet). **Mini** C, then D, F as short ticks in between. **Pro** E only — Pro is
saturated (memory 2026-08-31: a fork can report `completed` in 4 s with zero tool uses); one
interactive seat, no fan-out.

## Session contract (applies to every lane)

1. **Fix the model before turn 1**: `claude --model claude-opus-5` (effort `xhigh` from settings).
   Never `/model` mid-session — a switch rewrote a 121k-token startup cache once ($3.65 measured).
   Fable 5 only if Zero selects it himself; no session self-selects it.
2. **Fresh worktree, always**: `python3 scripts/agent_start.py --lane <lane> --task-id <id>` →
   `cd` the printed path. The main checkout is read-only for agents.
3. **Budget**: one session ≤ ~150 requests or ≤ 3 h (memory 2026-09-02: the cost knee is ~200
   requests; 8 sessions >24 h were 48.6 % of Claude spend). At the budget, write the lane file's
   `## LIVE STATE` block (what is proven, what is next, PR numbers, SHAs), ship it as a docs PR,
   and END. The next session starts from disk.
4. **Read order**: this README → the lane file → the corner skill it names →
   `docs/factory/ASSEMBLY-LINE.md` for product lanes (where it overlaps `modus`, ASSEMBLY-LINE wins).
5. **Seat check first**: `python3 scripts/claude_seat_quota.py --read` (Pro publishes). Slot 6
   (Team) is last resort. Kimi K3 was 403 (weekly cap) on 2026-09-01 — probe before counting it.
6. **Rule 8**: three rounds red for the same cause → SUSPEND with one PENDING-ARMS row, move on.
   A fix-of-a-fix stops at depth 1: write the spec instead of the third PR.
7. **Judge artifacts, never reports**: `gh pr list --head <branch>`, `git log`,
   `git show origin/main:<file> | grep -c <marker>`. A builder's "fixed" is half a fix until you
   read every branch of the diff (#5584 lesson).
8. **Ship**: one PR one concern, ≤ 400 net lines; `gh pr merge --auto --squash` at open; after
   merge `bash scripts/mq.sh handoff`; `bash scripts/mq.sh watch <pr>` while it queues.
   Count the checks with `gh api --paginate` — never read the summary colour; ~62-80 is a full
   battery, 3 means the battery never started.
9. **Merging any `apps/backend-rag/**` PR is the deploy** (`fly-deploy.yml` on push to main,
   `release_command` applies migrations forward-only). The queue batches 4 PRs / 15 min = one
   deploy. Migrations in the evening until Zero withdraws that rule.
10. **PII**: no client PII in outputs, logs, packs, memories. OCR/vision only `qwen2.5vl:7b` local.

## Team recipe (workhorse-first, Zero 2026-08-15)

| Role | Seat | How |
|---|---|---|
| Orchestrator + final on-disk gate | **Opus 5 xhigh** (interactive) | Designs, dispatches, gates. Never implements a builder's unit itself when a builder can. |
| Builders | **Sonnet 5** | `Agent(subagent_type:"general-purpose", model:"sonnet")` — one builder per PR, each in its own worktree; brief = the lane file section + acceptance test named in advance. The `model_routing_gate` hook blocks an Agent call without `model`. |
| Grunt (format, rename, mechanical edits) | **Haiku 4.5** | `model:"haiku"`. |
| Refuter #1 (adversarial, every PR) | **Codex `gpt-5.6-sol` xhigh** | `codex exec -m gpt-5.6-sol -c model_reasoning_effort="xhigh" --sandbox read-only --skip-git-repo-check "<brief with diff path>" < /dev/null`. **Never `scripts/codex-spalla.sh`** — it exits 0 when codex never ran (ledger 2026-09-01). |
| Refuter #2 (cross-family, Gear 3) | **Qwen 3.8 Max** | `python3 scripts/tp1_call.py --model qwen3.8-max --effort high --task-file <file>` — task ≤ 4 KB, streamed; a 194 s answer is not a dead seat. |
| Width / long context | **Gemini 3.1 Pro** | `agy -p "<prompt>" --print-timeout 5m` — prompt as the ARGUMENT, never on stdin; judge the output, never the exit code. |
| Third cross-family (if alive) | **Kimi K3** | `kimi -p PONG -m kimi-code/k3` first; if 403, declare the panel 2 seats — a seat that did not run is not a seat that agreed. |
| PII-bearing work | **Ollama local** | Mini/Pro only. |

Generator ≠ grader: the builder never gates its own diff. Gear-3 verdicts are on-disk (evidence
pack in `evidence/2026-09/<lane>/`), posted as a commit status — a verdict that exists only in
prose is not in force (memory 2026-08-29).

## Launch (copy per lane)

```bash
# on the lane's machine, from the repo root
WT=$(python3 scripts/agent_start.py --lane ops --task-id <lane-id> | awk '/WORKTREE_READY/{print $2}')
cd "$WT" && git fetch -q origin && git log -1 --format='%h %s' origin/main
claude --model claude-opus-5 "$(cat docs/plans/2026-09-03-relaunch-lanes/LANE-<X>-*.md)"
```

`<lane-id>` examples: `garuda-voa-0903`, `mouth-closeout-0903`, `visa-oracle-0903`, `kbli-kg-0903`,
`bot-wa-0903`, `ci-truth-0903`, `fleet-align-<host>-0903`.

## Loop protocol

- **No `/loop` on a whole lane** — a lane is a sequence of short sessions, not one long one.
- Inside a session, `/loop 10m bash scripts/mq.sh status` is fine while PRs queue.
- Lane F may run as headless ticks on Mini (`claude -p --model claude-sonnet-5 --allowedTools
  Bash,Read,Grep "$(cat LANE-F-ci-truth.md)"`) at most every 4 h — set `CLAUDE_CONFIG_DIR` to an
  isolated profile (memory 2026-09-01: a verifier that inherits `~/.claude` answers the mailbox).
- Handoff between sessions and machines is the lane file's `## LIVE STATE` on `origin/main` — the
  twin-session protocol of `.claude/skills/workflow/SKILL.md` §4 (disjoint lanes, durable artifacts,
  ledger handoff). Two lanes never share a file: if they must, the second one waits.
