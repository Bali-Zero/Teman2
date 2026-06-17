# WR3-F21 — reflexion cron is theater: a declared stub exits 0 every Sunday, synthesizing nothing

> **Status: SPEC READY — NOT EXECUTED.** Docs-only finding. The fix (port the
> real WR2 reflexion implementation) is an operator decision — no code/cron
> change is shipped by this spec.
>
> Date: 2026-06-12 · Family: WR3 feature-debt (sibling: WR3-F18, WR3-F20) ·
> Audit source: Fable-5 system audit 2026-06-11 (finding F21) ·
> Index: `WR3-DEBT-INDEX.md`.

## 1. Context

The WR3 reflexion-synthesis weekly cron is **green every Sunday and does
nothing** — it runs a declared placeholder stub that reads nothing, writes
nothing, and `sys.exit(0)`s. This is the canonical "green cron ≠ working"
trap.

Verified on disk:

- **Plist** (Pro, **NOT versioned in-repo**):
  `~/Library/LaunchAgents/com.balizero.wr3.reflexion.weekly.plist`,
  Sunday 02:30 WITA, runs
  `apps/war-room/.venv/bin/python3
  ~/.claude/skills/bali-zero-brand/wr3/_reflexion-synthesis.py`.
- **Root cause** — that target script is an **816-byte DECLARED STUB**:
  - line 4: `"PLACEHOLDER (S7.3 stub) — full implementation lands at S7.5."`
  - lines 21-22: `print("S7.3 stub — full implementation S7.5",
    file=sys.stderr)` then `sys.exit(0)`.
  - It reads nothing, writes nothing, exits 0 → **cron green every Sunday,
    synthesizes nothing.** The script's own docstring describes the intended
    reads (`apps/war-room/output/episode/<recent-7-days>/*`,
    `output/queue/wr3-human-review-queue.json`) and writes
    (`wr3/<agent>/lessons.md`, `wr3/_proposed/<date>-<slug>.md`) — none of which
    it actually performs.
- **Contrast — the WR2 sibling is REAL:**
  `~/.claude/skills/bali-zero-brand/_reflexion-synthesis.py` is a genuine
  314-line implementation. The WR3 file is a 816-byte stub that was never
  upgraded past S7.3.
- **Outputs confirm theater:** `wr3/_proposed/` is **empty**, and there is **no
  `lessons.md` anywhere under `wr3/`**. Twelve+ Sundays of green crons; zero
  lessons, zero skill drafts.
- **Contract** `docs/wr3/contracts/reflexion-synth.yaml` —
  `model: sonnet`, `lifecycle_tier: scheduled`, weekly Sun 02:30, declares
  outputs `agent_lessons` (`wr3/<agent>/lessons.md`) + `skill_drafts`
  (`wr3/_proposed/<date>-<slug>.md`), `≤10 lessons/week`, cascade
  Sonnet→Gemini→defer. The contract describes a real agent; the script behind it
  is a stub.

## 2. Why this matters

A weekly self-improvement loop that has exited 0 with zero output for 12+ weeks
is **green-cron theater** — the operator's mental model is "WR3 is learning from
its episodes each week", while in reality the synthesizer is a hard-coded
`sys.exit(0)`. This is the same "armed but inactive / green but empty" disease
as F20, and (per the cross-cutting note) it shares the same upstream blocker:
the dead WR3 supervisor.

## 3. Fix options (operator picks; nothing shipped here)

- **(a) Port the WR2 314-line pattern** — implement the WR3 stub to actually:
  - read `apps/war-room/output/episode/<last-7d>/*` +
    `output/queue/wr3-human-review-queue.json`;
  - synthesize **≤10 lessons** → `wr3/<agent>/lessons.md`;
  - write skill drafts → `wr3/_proposed/<date>-<slug>.md`;
  - cascade **Sonnet → Gemini** on quota-exhaust (per CLAUDE.md Multi-LLM
    cascade and the contract's declared failure modes).
- **(b) Version the plist** into `infra/launchagents/` so the schedule stops
  living only on the Pro's `~/Library/LaunchAgents/` (it is currently
  unversioned — a fleet/rebuild would lose it).

## 4. Guardrails — the CAVEAT is load-bearing

- **Do NOT execute autonomously.** Porting a 314-line synthesizer + wiring a
  cascade is real code, reviewed before it runs against episode artifacts.
- **The supervisor must be fixed FIRST.** `com.balizero.wr3.supervisor` is
  **FAILED, exit=78**, and there have been **zero new episodes in 12 days**.
  That means **reflexion has NO input corpus even once implemented** — porting
  the real synthesizer now would produce a faithful implementation that still
  emits nothing, because there is nothing to synthesize from. Reviving the
  supervisor (so episodes flow again) is the prerequisite; the reflexion port is
  downstream of it.
- This makes F21 a **second-order** fix gated on the same upstream blocker as
  F20 — see the cross-cutting note in `WR3-DEBT-INDEX.md`.

## 5. Reference

- Stub: `~/.claude/skills/bali-zero-brand/wr3/_reflexion-synthesis.py`
  (816 bytes, "PLACEHOLDER (S7.3 stub)", `sys.exit(0)` at lines 21-22).
  (Pro/M5 runtime host path — verify on the cron host.)
- Real sibling to port from:
  `~/.claude/skills/bali-zero-brand/_reflexion-synthesis.py` (314 lines).
- Plist: `~/Library/LaunchAgents/com.balizero.wr3.reflexion.weekly.plist`
  (Sun 02:30 WITA, unversioned — to land in `infra/launchagents/`).
- Contract: `docs/wr3/contracts/reflexion-synth.yaml`.
- Empty outputs: `wr3/_proposed/` (empty), no `lessons.md` under `wr3/`.
- Shared upstream blocker: `com.balizero.wr3.supervisor` exit=78 (see
  `WR3-DEBT-INDEX.md`).
- Audit: Fable-5 system audit 2026-06-11, finding F21.
