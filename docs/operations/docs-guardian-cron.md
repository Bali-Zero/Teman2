# docs-guardian Cron

**Host:** Pro (`nuzantara@Nuzantara`)
**Schedule:** Sunday 05:00 WITA (= Saturday 21:00 UTC)
**Script:** `/Users/nuzantara/Desktop/nuzantara/scripts/docs_guardian.sh`
**Log:** `~/logs/docs-guardian.log`

Weekly guardian that:
1. Runs `scripts/docs_sync.py` (best-effort DOCSYNC marker sync).
2. Runs `scripts/docs_audit.py` to regenerate `docs/DOCS_INVENTORY.md`.
3. Sends a Telegram alert via `~/.claude/scripts/hotfix-notify.sh` only when the audit reports a delta (exit code ≠ 0). No delta = silent run.

## Install

```bash
mkdir -p ~/logs
( crontab -l 2>/dev/null; echo "0 5 * * 0 /Users/nuzantara/Desktop/nuzantara/scripts/docs_guardian.sh >> $HOME/logs/docs-guardian.log 2>&1" ) | crontab -
crontab -l | grep docs-guardian
```

## Verify

```bash
# After the first Sunday run:
tail -50 ~/logs/docs-guardian.log

# Manual run (any day):
bash /Users/nuzantara/Desktop/nuzantara/scripts/docs_guardian.sh
echo "exit=$?"
```

Expected behavior:
- **No delta** → no output, exit 0, no Telegram.
- **Delta** (new STALE / broken / orphan) → Telegram alert with summary, `docs/DOCS_INVENTORY.md` updated.

## Uninstall

```bash
crontab -l | grep -v docs-guardian | crontab -
```

## Related automation

- `docs/DOCS_INVENTORY.md` — auto-generated output.
- `docs/AUTOMATIONS_REFERENCE.md` — complementary live-system-health snapshot (different cron, `com.nuzantara.automations-reference` LaunchAgent, nightly 23:15 WITA).
- `.github/workflows/docs-guardian.yml` — CI counterpart running `docs_audit.py --check` on PRs touching `docs/**`.
