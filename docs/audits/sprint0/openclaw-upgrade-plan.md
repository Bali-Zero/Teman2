# OpenClaw upgrade v2026.3.31 → v2026.4.29 plan (rollback-safe) — Sprint 0 Track A4

**Date:** 2026-05-02 · **Author:** Sprint 0 Air session (Claude Opus 4.7 1M)
**Reference:** brainstorm 2026-05-02 round 2 § "Upgrade OpenClaw v2026.3.31 → v2026.4.29"
**Owner human:** Antonello Siano · **Status:** **plan only — NOT executed**

## Why upgrade

| Driver | Source | Severity |
|---|---|---|
| **Scheduler frozen since 2026-04-30** | `~/.openclaw/cron/jobs.json` — 24 jobs `status:null, lastRun:null, nextRun:null` | P1 |
| **Knowledge Agents v12.1.0 unused** | `claude-mem` v12.1.0 ships 6 MCP tools (`build_corpus`, `prime_corpus`, `query_corpus`, `list_corpora`, `rebuild_corpus`, `reprime_corpus`) — needed for Sprint 1 HGT coordinator | P2 |
| **Provider enum expansion** | v2026.4.29 supports OpenAI-compatible generic provider (currently we have to fake DeepSeek via openrouter) | P2 |
| **Auth profile system** | v2026.3.31 introduced; not yet enabled — multi-profile failover for cost/quota gating | P3 |
| **Auto-update** | Not configurable below v2026.3.31; manual upgrade is the only mechanism | n/a |

**Non-drivers (NOT a reason to upgrade now):**
- Telegram timeout hardening — already in v2026.3.31, working as expected
- DM pairing security default — already configured (`dmPolicy=open + allowFrom=["*"]`)

## Risk register (4-LLM brainstorm round 2 unanime)

1. **Lobster regression** — 4 active workflows (`autofix-loop.lobster`,
   `nightly-code-quality.lobster`, `weekly-dep-audit.lobster`,
   `nuzantara-dev-pipeline.lobster`) are the **only** production OpenClaw usage.
   If Lobster DSL semantics changed between v2026.3.31 and v2026.4.29, all 4
   break silently.
2. **Telegram menu drift** — see Sprint 0 Track A2. New OpenClaw versions add
   bundled skills which may push `setMyCommands` further over the 100 cap.
   Disable plan from A2 must be applied **before** the upgrade.
3. **Knowledge Agents config-not-found** — v12.1.0 expects a corpus dir; if the
   default is `~/.openclaw/agents/main/agent/corpus/` and we don't create it,
   first invocation may crash the agent.
4. **`claude-code` 3rd agent** — undocumented (see Track A5). Upgrade may break
   it or remove it. Pre-upgrade audit needed.
5. **Cron jobs unfreezing unexpectedly** — 24 frozen jobs may suddenly become
   live mid-upgrade if the scheduler fix lands on first reboot. They overlap
   with `cron-agent-python` strategies (see Track D2 ownership matrix);
   uncoordinated unfreeze = double-execution. Disable jobs in `~/.openclaw/cron/jobs.json`
   before upgrade (Track A5 covers).

## Phased rollout — sandbox first

### Phase 0 — pre-flight (Antonello, ~15 min)

```bash
# 1. Quiesce gateway (avoid mid-upgrade Telegram spam):
ssh pro 'launchctl unload ~/Library/LaunchAgents/ai.openclaw.gateway.plist'

# 2. Snapshot state:
ssh pro 'tar -czf ~/openclaw-backup-2026-05-02.tar.gz \
  ~/.openclaw/openclaw.json \
  ~/.openclaw/extensions/ \
  ~/.openclaw/agents/main/agent/memory.db \
  ~/.openclaw/cron/jobs.json \
  ~/Library/LaunchAgents/ai.openclaw.gateway.plist 2>/dev/null'

# 3. Apply Sprint 0 Track A2 (skill disable) and A5 (frozen jobs disable)
# from this PR's docs first. Each lands in a separate post-merge step.

# 4. Note current binary path + version:
ssh pro 'which openclaw && openclaw --version'
ssh pro 'cat /Users/nuzantara/.openclaw/lib/node_modules/openclaw/package.json | jq .version'
```

Expected: `2026.3.31`.

### Phase 1 — install v2026.4.29 in isolated dir (Antonello, ~10 min)

The strategy is to install the new binary to a **side-by-side path** so a
plist swap restores the old in <2 minutes.

```bash
# 1. Install side-by-side via npm prefix override:
ssh pro 'mkdir -p ~/.openclaw-v2026.4.29 && \
  npm install --prefix ~/.openclaw-v2026.4.29 openclaw@2026.4.29'

# 2. Verify the new binary works in isolation (does NOT touch live config):
ssh pro '~/.openclaw-v2026.4.29/bin/openclaw --version'

# 3. Smoke check the new release notes paths in the bundled skills:
ssh pro 'ls ~/.openclaw-v2026.4.29/lib/node_modules/openclaw/skills/ | wc -l'
```

If install fails (npm registry offline, network error), STOP and revert to
running on v2026.3.31. There's no need to roll forward in a single session.

### Phase 2 — sandbox test against current config (Antonello, ~30 min)

```bash
# 1. Run the new binary against a copy of openclaw.json in a temp HOME:
ssh pro 'export OC_TEST_HOME=$(mktemp -d -t openclaw-upgrade-test)
  cp -r ~/.openclaw "$OC_TEST_HOME/.openclaw"
  HOME="$OC_TEST_HOME" ~/.openclaw-v2026.4.29/bin/openclaw doctor 2>&1 | tee \
    ~/openclaw-upgrade-test-doctor.log'

# 2. Check the test gateway can boot (DON'T let it bind 18789 — unset port):
ssh pro 'HOME="$OC_TEST_HOME" PORT=27890 \
  ~/.openclaw-v2026.4.29/bin/openclaw gateway start 2>&1 | head -50'

# 3. Verify Lobster workflows compile against the new DSL:
ssh pro 'cd ~/.openclaw/workspace/workflows && for f in *.lobster; do
  HOME="$OC_TEST_HOME" PORT=27891 \
    ~/.openclaw-v2026.4.29/bin/openclaw lobster compile "$f" \
    || echo "FAIL: $f"
done'

# 4. List Knowledge Agents corpora (expect empty but no error):
ssh pro 'HOME="$OC_TEST_HOME" PORT=27892 \
  ~/.openclaw-v2026.4.29/bin/openclaw mcp call claude-mem.list_corpora 2>&1'

# 5. Cleanup the test sandbox:
ssh pro 'rm -rf "$OC_TEST_HOME"'
```

Promotion criteria (ALL must pass):
- `openclaw doctor` exits 0
- All 4 Lobster workflows compile without "unknown opcode" errors
- `mcp call claude-mem.list_corpora` returns `[]` (or any non-error JSON)

If any criterion fails, revert: keep `~/.openclaw-v2026.4.29/` for diagnostics
(don't `rm -rf` it), file an issue, postpone upgrade.

### Phase 3 — flip to new binary (Antonello, ~5 min)

```bash
# 1. Backup the old install:
ssh pro 'mv ~/.openclaw ~/.openclaw-v2026.3.31-backup-2026-05-02'

# 2. Atomic rename:
ssh pro 'mv ~/.openclaw-v2026.4.29 ~/.openclaw'

# 3. Restore the live state (config + extensions + memory + cron):
ssh pro 'cp ~/.openclaw-v2026.3.31-backup-2026-05-02/openclaw.json ~/.openclaw/
  cp -r ~/.openclaw-v2026.3.31-backup-2026-05-02/extensions ~/.openclaw/
  cp -r ~/.openclaw-v2026.3.31-backup-2026-05-02/agents ~/.openclaw/
  cp ~/.openclaw-v2026.3.31-backup-2026-05-02/cron/jobs.json ~/.openclaw/cron/
  cp -r ~/.openclaw-v2026.3.31-backup-2026-05-02/workspace ~/.openclaw/'

# 4. Restart gateway:
ssh pro 'launchctl load ~/Library/LaunchAgents/ai.openclaw.gateway.plist'

# 5. Watch boot log:
ssh pro 'tail -F ~/.openclaw/logs/gateway.log' &
sleep 30   # wait for boot
```

Expected: gateway boots cleanly, `setMyCommands` succeeds (count was reduced
in Track A2 first), Telegram bot responds to `/start`. If anything errors,
proceed to phase 4 immediately.

### Phase 4 — rollback (only if phase 3 fails)

```bash
# 1. Stop the broken new install:
ssh pro 'launchctl unload ~/Library/LaunchAgents/ai.openclaw.gateway.plist'

# 2. Atomic swap back:
ssh pro 'mv ~/.openclaw ~/.openclaw-v2026.4.29-failed-2026-05-02 && \
  mv ~/.openclaw-v2026.3.31-backup-2026-05-02 ~/.openclaw'

# 3. Restart with the known-good binary:
ssh pro 'launchctl load ~/Library/LaunchAgents/ai.openclaw.gateway.plist'

# 4. Verify Telegram works:
# (manual: send `/start` in @Balizerobot, expect response)

# 5. File diagnostic from the failed install:
ssh pro 'tar -czf ~/openclaw-v2026.4.29-diagnostics.tar.gz \
  ~/.openclaw-v2026.4.29-failed-2026-05-02/logs/'
```

The whole rollback completes in ~2 minutes. The old binary lives in the same
HOME and the launchd plist points at `/usr/local/bin/openclaw` (or wherever
the OS-level symlink resolves) — atomic mv at the `~/.openclaw` level is
sufficient because the binary uses `__dirname`-relative paths.

### Phase 5 — post-upgrade verification (Antonello, ~30 min, monitor 24h)

```bash
# 1. Telegram menu count check:
ssh pro 'grep "setMyCommands" ~/.openclaw/logs/gateway.log | tail -3'
# Expect: "accepted N commands" with N < 80 (post Track A2 disable)

# 2. Cron scheduler thaw check:
ssh pro 'cat ~/.openclaw/cron/jobs.json | jq ".[].lastRun" | sort | uniq'
# Expect: at least one job with a lastRun timestamp newer than 2026-05-02
# (proof scheduler unfroze). If any job overlaps cron-agent-python, ensure
# Track A5 disable was applied first.

# 3. Knowledge Agents smoke:
ssh pro 'mcporter call claude-mem list_corpora'
# Expect: `[]` (no corpora yet — Sprint 1 will create the first)

# 4. Lobster sanity:
ssh pro 'tail -F ~/.openclaw/logs/gateway.log' &
sleep 5
# Expect: next nightly autofix-loop runs cleanly (visible in log via "agent coder" lines)

# 5. 24h soak watch — observe dashboards:
#    - heartbeat_monitor (every 1h)
#    - login-healthcheck (every 30m)
#    - Sentinel telemetry
```

If after 24 hours all is green → ship a follow-up commit:
`chore: confirm OpenClaw v2026.4.29 stable on Pro` documenting the
verification window in the cicatrix log.

If anything degrades, rollback per Phase 4 and re-investigate in a fresh
sandbox.

## Out-of-scope today

- Webhook-based Telegram polling (mentioned by 07_openclaw_deep_research.md
  as a future workaround for ETIMEDOUT/EHOSTUNREACH on Bali geographic
  latency). v2026.4.29 changelog doesn't mention webhook support; revisit
  for v2026.5.x.
- A2A subagent pattern via `bindings[]`. Out of scope until Sprint 5
  (OpenClaw insertions WR2).
- Migrating Lobster DSL to a newer OpenClaw plugin layer (no urgency,
  current 4 workflows are stable).

## Application order summary (post-merge by Antonello)

| Step | Owner | When |
|---|---|---|
| 1. Apply Track A2 (Telegram skill disable) | Antonello | Day 0 |
| 2. Apply Track A5 (24 frozen jobs disable + claude-code review) | Antonello | Day 0 |
| 3. Apply Track A3 (mcporter idle disable) | Antonello | Day 1 |
| 4. **Run Phase 0+1+2 (sandbox upgrade test)** | Antonello | Day 2 |
| 5. **Run Phase 3 (atomic flip)** | Antonello | Day 2 (off-peak, ~22:00 WITA) |
| 6. **Run Phase 5 (24h soak)** | Antonello | Day 2-3 |

Total elapsed: 2-3 days from PR merge to verified upgrade live.

Escalation: Pro auto-failover doesn't exist (single-host); during the upgrade
window, Telegram messages may queue at OpenClaw side for up to 2-5 minutes.
Notify team via Slack/Telegram before starting Phase 3.

## References

- `~/.openclaw/lib/node_modules/openclaw/package.json` (current version)
- `~/.openclaw/cron/jobs.json` (24 frozen jobs)
- `~/.openclaw/extensions/claude-mem/` (Knowledge Agents v12.1.0)
- `~/.openclaw/workspace/workflows/*.lobster` (4 production workflows)
- `docs/audits/2026-05-02-cell-openclaw-brainstorm/07_openclaw_deep_research.md` (3500-word OpenClaw research)
- `docs/audits/sprint0/openclaw-telegram-skills.md` (Track A2 — must apply first)
- `docs/audits/sprint0/openclaw-frozen-jobs.md` (Track A5 — must apply first)
