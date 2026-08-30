# SQUAD F — fleet & security (Mini, slot 5)

Launched: 2026-08-30T01:57:48Z by conductor GO (Zero).
Worktree: `.worktrees/craft-f-fleet-security` on Mini (`~/nuzantara`).
Branch namespace: `agent/mini-pro2/craft-f/...`.
Seat: OAuth slot 5 (`CLAUDE_CODE_OAUTH_TOKEN_5`) — served Squad E until yesterday evening; a
weekly cap is possible, the launch itself is the first live probe.

Lanes in order: **L09** (PR-1 -> PR-2 -> PR-3) -> **L13-PR1** -> **L13-PR2** -> L13-PR3 (waits for
Squad C's L10-PR1 to merge on origin/main before starting — rebases onto L10's change to
`scripts/pending_arms_report.py`).

## Status board — session 1

| Item    | State       | PR  | Note                                                                                                                                                                                                                      |
| ------- | ----------- | --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| L09-PR1 | IN PROGRESS | —   | seat-state ledger + cascade pre-dispatch check; branch `craft-f/seat-state-ledger`                                                                                                                                        |
| L09-PR2 | NOT STARTED | —   | fleet_burst account-sharded headless fan-out (depends on PR-1)                                                                                                                                                            |
| L09-PR3 | UNBLOCKED   | —   | bind dispatch effort to compute_floor. **PR #5048 is MERGED** (commit `daac0da9dd`, present in base `68c513aecd`) — the reported DIRTY conflict on `scripts/seat_build.sh` is resolved; PR-3 extends the post-#5048 file. |
| L13-PR1 | NOT STARTED | —   | seat broker: exec-time minimal env for external LLM dispatch                                                                                                                                                              |
| L13-PR2 | NOT STARTED | —   | tailnet policy drift receptor                                                                                                                                                                                             |
| L13-PR3 | BLOCKED     | —   | waits for Squad C L10-PR1 merged (extends pending_arms_report.py)                                                                                                                                                         |

## NEEDS-RULING (carried from lane specs, not decided here)

- Keychain Proxy Daemon auto-unlock (L09 spec Needs-ruling #1) — not built this wave.
- Default effort for floor-2 diffs (L09-PR3) — ships logged-only/advisory pending Zero's ruling.
- Apply `infra/tailscale/policy.hujson` — operator[GUI], Tailscale admin console.
- Team tailnet expansion GO/NO-GO — business decision.
- Three open rotations (Supabase, Google OAuth client, TP1 key) — operator[secret].
- Chronicle/ChatGPT.app screen recording on M5 — Zero's machine-use decision.
- Canary service choice (external vs self-minted) — Zero's call if applicable.

## Session 1 — grounding findings (verified on disk this turn, not from memory)

1. **`scripts/tests/test_claude_oauth_slot6_coverage.py` does NOT exist on origin/main.** The L09
   spec flagged this as a report claim to verify; confirmed absent at base `68c513aecd`
   (`ls` → No such file). It exists ONLY inside open PRs #4640/#4644/#4645. The global memory's
   claim that it "enforces 5 MAX before slot 6" describes a test that is not yet on main.
   → surfaced to conductor/Zero (see NEEDS-RULING).

2. **`claude-cascade.sh` on origin/main does NOT yet implement "5 MAX before the Team seat".**
   Measured: the dispatch loop is `for index in 1 2 3 4 5`, and slot 5 is labelled
   `claude-token-5-team-env` with `config_dir=$HOME/.claude-zero-team` — i.e. on main the Team seat
   IS slot 5, and there is no slot 6. Open PR #4644 is the PR that renumbers this to
   `1 2 3 4 5 6` (slot 5 → `.claude-kaiser` MAX, slot 6 → Team last-resort).
   → **L09-PR1 must NOT duplicate #4644's renumbering** (one PR one concern + hotspot
   serialization, §5). PR-1's cascade hook is therefore written to be _numbering-agnostic_: it
   consults seat state inside `try_claude()` (a function #4644 does not touch) rather than inside
   the `for index` loop (the exact hunk #4644 rewrites). This keeps the two diffs conflict-free in
   either merge order.

3. **The two state reports carry different keys** (both read this turn):
   - `~/.claude/seat-quota.json` → `{generated_at_epoch, seats:[{account,session_pct,weekly_pct,...}]}`,
     keyed by **account email**. Live copy is from 2026-08-25 — 5 days stale, i.e. the staleness
     path is the _live_ path today, not a hypothetical.
   - `~/.organism/arsenal/last.json` → `{ts, seats:[{seat,status,healthy,...}]}`, keyed by **seat
     name** (`claude`, `kimi`, `tp1-*`), one `claude` row for the whole family — no per-slot rows.
     → Consequence: **there is no slot→account key anywhere in machine-readable state.** CLAUDE.md
     itself warns the slot↔account map is DOCUMENTAL, per-machine divergent, and not derivable from
     a token. PR-1 therefore hardcodes NO map: the caller supplies `CLAUDE_SEAT_ACCOUNT_<N>`, and
     an unresolvable slot yields UNKNOWN (never a skip).
