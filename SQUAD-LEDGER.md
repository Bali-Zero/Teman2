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

## Session 1 — L13 pre-grounding (read-only, done while L09-PR1 built)

- `infra/llm-credentials/declared.json` — `{_comment, credentials}`; entries carry
  `sha256(credential_uid)[:16]`, never the uid. L13-PR1's `seat-env.json` follows the same
  value-free discipline (names only).
- `infra/tailscale/policy.hujson` — 422 lines, HuJSON (JSON + `//` comments). Header states
  STATUS: PROPOSED, not applied; live packet filter measured 2026-08-11 and re-confirmed
  2026-08-29 as ONE allow-all rule. `acls[]` entries are `{action, src[], dst[]}` with
  `dst` elements shaped `host:port`. So the drift comparison is host:port rule-shape, and the
  allow-all fixture is trivially divergent from it. `tailscale` CLI IS present at
  `/usr/local/bin/tailscale` on Mini — but PR-2 ships fixture-mode as the tested path; a live
  call is never required to go green.
- `scripts/proprioception.py` — `run_wrap()` (~line 874) dispatches on `entry["parse"]` with
  existing modes `exit_code` / `findings_list` / `category_counts`, each returning
  `(verdict, n_findings, evidence)` where verdict ∈ {RECONCILED, DIVERGED, UNPROBEABLE}.
  Adding `tri_state_exit` is a purely ADDITIVE branch in that dispatch: rc 0→RECONCILED,
  1→DIVERGED, 2→UNPROBEABLE. `DEFAULT_REGISTRY` (~line 924) entries are dicts with
  `id/type/target/class/boundary/machines/tags/timeout_sec/severity/fix_hint`.
- Battle-plan §2 orders the `proprioception.py` chain **L13-PR2 → L02-PR1 → L10-PR2 → L05-PR2**;
  L13-PR2 is FIRST, so it waits on nobody.

## Session 1 — L09-PR1 build in flight

- Claim commit `f8a094cc74` on `agent/mini-pro2/craft-f/seat-state-ledger` (base `68c513aecd` == origin/main).
- **Pre-change regression baseline captured this turn** (so the cascade edit is judged against a
  measured number, not a memory): `python3 -m pytest scripts/tests/test_claude_cascade_shell.py -q`
  → **62 passed** in 80.7s. `bash scripts/tests/test_cron_agent_oauth_cascade.sh` → PASS (13 checks).
  `bash scripts/tests/test_claude_seat_helper.sh` → PASS.
- Note for anyone re-running the harness locally: the default `python3` on Mini has **no `pyyaml`**,
  so `scripts/evidence_pack_lint.py` dies on `import yaml`. `/usr/bin/python3` (3.9.6) and
  `apps/backend-rag/.venv/bin/python` (3.11.15) both have it — use one of those.
- Evidence pack path for this branch (`scripts/ci/evidence_paths.py --ref`):
  `evidence/2026-08/agent-mini-pro2-craft-f-seat-state-ledger-ec549b00/`.
- Refuter availability probed: `codex` on PATH (codex-cli 0.148.0); `kimi` NOT on PATH but present
  and executable at `~/.kimi-code/bin/kimi` — invoke by absolute path.

## L09-PR1 — built, gated, refuted twice (session 1)

**Deterministic floor is 3, not the spec's Gear 2** — `evidence_pack_lint.py --print-floor-source`
says `path`: the diff touches `infra/launchagents/wrappers/claude-cascade.sh`, a hot-zone
LaunchAgent wrapper. CI recomputes this, so it is not negotiable. Consequences honoured: brief
declares gear 3, evidence pack carries a `council_run` journal with two distinct non-Anthropic
review seats, and the PR will need the `harness/fable-gate` status on its head SHA (§5).

**Two adversarial rounds, both non-Anthropic, 8 confirmed defects.** Round 1 Kimi K3 on the diff;
round 2 Codex GPT-5.6 sol pointed at the FIXES with an explicit instruction not to re-report round

1. Every finding was reproduced on this machine before being fixed — a refuter claim is a lead, not
   a fact (W65). Round 2's two findings could not have existed in round 1: one of them was created by
   round 1's own fix (W94 — the cure for an over-match births the under-match twin).

| #   | Defect                                                                            | Polarity        | Status |
| --- | --------------------------------------------------------------------------------- | --------------- | ------ |
| K1  | future-dated report reads fresh forever -> skips a live seat                      | wrong SKIP      | fixed  |
| K2  | non-strict JSON (Infinity/NaN) forces a skip                                      | wrong SKIP      | fixed  |
| K3  | timezone-less timestamp read in local time (measured 28800s phantom age on UTC+8) | wrong staleness | fixed  |
| K4  | probe sentinel exported -> one probe per process TREE                             | staleness       | fixed  |
| K5  | unvalidated report values reach the output line                                   | hygiene         | fixed  |
| K6  | wiring guard asserted kill-switch PRESENCE, never POLARITY                        | guard theater   | fixed  |
| C1  | JSON `1e400` overflows to inf, bypassing the K2 fix -> skip                       | wrong SKIP      | fixed  |
| C2  | removing the export (K4's fix) opened unbounded probe re-entrancy (26 runs)       | hang risk       | fixed  |

Three of my own new GUARDS were wrong on the first attempt and are recorded rather than quietly
corrected: the sentinel case used a LIVE fixture that never reached the probe branch; the
sanitisation case asserted field COUNT when an unsanitised tab TRUNCATES rather than adds; the
label case grepped only for labels already shaped `claude-token-*`, so a rename vanished from its
own input set. Each was found by mutation, not by reading.

**Gate evidence (all re-run this turn, never from memory):** corpus 26/26 · **20/20 mutants killed
at real code sites** · cascade regression 62 passed == the pre-change baseline measured before any
file was touched · library sources and runs under `set -uo pipefail` in BOTH zsh and bash · 7
crafted injection labels across both shells all return the safe polarity and write no sentinel.

**NOT armed, and said so plainly:** measured against the real reports, both are stale right now
(quota ~4.86 days, arsenal ~11.3h), so the pre-check resolves UNKNOWN and skips nothing today. And
the arsenal source cannot answer on the cascade path at all — that path resolves an account e-mail
while arsenal is keyed by seat name. Two PENDING-ARMS rows, not a shipped win.
