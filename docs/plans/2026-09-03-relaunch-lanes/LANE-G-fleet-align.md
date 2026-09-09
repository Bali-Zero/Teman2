# LANE G — Fleet align: the cures that are on main and not live

**Machine:** each of Pro, Mini, M5 — the live copies are per-machine (scar family #1 HOME-fork).
Run this lane ON the machine it aligns; never align Mini from Pro by copying HOME → HOME.
**Contract:** `README.md` here. **Ledger rows:** grep `origin/main`'s PENDING-ARMS for
`CURED ON MAIN`, `NOT LIVE`, `NEVER INSTALLED`, `home-fork` opened 2026-08-30 → 2026-09-02.

Rule: copy REPO → HOME, verify with sha256, then `python3 scripts/lint_home_fork.py` must report
the pair clean. Editing a HOME copy directly is temporary and spawns a healer session (memory
2026-09-02). Anything under `~/.claude/hooks/` is `operator[control-plane]`: print the exact
one-liner into `ZERO-DECISIONS.md` item 8 and stop.

## Pro (`ssh pro`, repo `~/Desktop/nuzantara`, main checkout has 134 uncommitted files — do NOT pull it; work from a worktree)

- 5 Pro-node organs BUILT + COMMITTED (plists in `infra/launchagents/`) and NEVER INSTALLED —
  one is the only `critical` organ (ledger 2026-08-31). Install, `bootout`+`bootstrap`, heartbeat.
- `infra.ollama_pro` label repoint merged, not live: the LaunchAgent runs a HOME copy of
  `launchagent-state-bridge.py`. Refresh the declared pair.
- `regulatory-watcher-run.sh` live-copy sync gap (Pro AND M5).
- `pro.visa_freshness_sentinel` install (Lane C2 owns it — coordinate, do not double-install).
- Team seat slot 6 merged, not live until the checkout that runs cascades is refreshed — verify
  `infra/launchagents/wrappers/claude-cascade.sh` on disk has the numbered slot-6 branch.
- WR2: 33 launchd WR2 jobs are OFF by Zero's order (2026-09-01); `plist-watchdog` used to re-copy
  them every 15 min — confirm it stays off. Never re-arm.

## Mini (`ssh mini`, repo `~/nuzantara` — `~/Desktop/nuzantara` does not exist there)

- `~/.claude/agents/regulatory-watcher.md` diverged after #5560 (frontmatter trim) — refresh the
  declared pair, then check `declared-pairs.json` vs `host_boundary` for `.claude/agents/*`
  (ledger #5581 names the mismatch).
- `mini.iqoo_radar_relay` retry-storming the same capsule every 60 s for 42 h with `status: ok`
  in its own heartbeat: stop the storm (bound retries, mark the capsule dead), fix the heartbeat
  to report the real outcome. `pro/mini.iqoo_radar_relay` are built and intentionally not armed —
  leave them so.
- L13-PR3 operator[secret] ager digest is built and proven; wire its delivery to the existing
  Mini digest cron (`tg_notify.py`, family key), prove one real send by status word.
- Mini's 5-minute main sync runs a SECOND puller with the same rename-blindness as the Pro one —
  the collision matrix spec (#5497) owns the cure; here only confirm which copy runs.

## M5 (this machine)

- `regulatory-watcher-run.sh` pair (see Pro).
- Residue on the main checkout: `.agents/skills/subhi/SKILL.md` (2026-08-12 handoff, not on main)
  and two PENDING-ARMS rows (#5337 veto SUSPENDED; `resolve_evidence_path` fail-closed on five
  packs) — ship as one docs PR from a worktree; `route.ts` local diff is already on main (#5478),
  drop it. Untracked `visa-oracle-adjudication/`, `visa-oracle-blueprint/`, `drafts/` (7.6 MB):
  decide keep-as-research-capture or delete, per `CLAUDE.md` §15.
- Reap worktrees whose PR is MERGED and content is on main by CONTENT: `fix-practice-types-isolation`
  (#5555), `ops-qwen-quorum-align` (#5518 — one extra prettier commit, confirm it is no-op),
  `ops-voa-cc` (#5533), `ops-voa-router` (#5549). Keep `ops-voa-store-wiring` (Lane A3) and
  `wr3-zantara-video-factory-v3` (Lane B4).

## All three — hooks (operator[control-plane], Zero runs the line)

- `host_boundary.py` credentials fail-open and `worktree_isolation.py` newline bypass are CURED ON
  MAIN and STILL LIVE on all three machines; `model_routing_gate.py` on M5 cannot refresh from its
  own checkout. Emit, per machine, the `cp <repo-path> ~/.claude/hooks/<name>` line from the pair
  entry in `infra/home-fork/declared-pairs.json` and the sha256 to expect. Do not run it.

## LIVE STATE (update before ending the session, one block per machine)

- 2026-09-03 Pro: not started. Mini: not started. M5: not started.
