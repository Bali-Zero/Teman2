---
date: 2026-05-23
domain: operations
client_case: NB automations hardening — W28 organism supervisor FLY_API_TOKEN gap close
sources: 5
---

# W28: organism supervisor FLY_API_TOKEN gap (W27 follow-up)

## Background

W27 Path A wired Cell→Organism auto-heal pipeline end-to-end. Empirical smoke
test confirmed `cell_pulse_sustained_red` event flows correctly through
PG→Redis→Organism dispatcher, hits the yaml rule, dispatches
`fly_machines_start` actuator. **But actuator failed at runtime** because
the organism supervisor's plist ProgramArguments called `python3` directly
with no env-loading wrapper, so `FLY_API_TOKEN` was absent.

## Fix shipped

1. **New wrapper `~/scripts/organism-supervisor-wrapper.sh`** (50 lines, gitignored
   path). TCC-safe pattern from W19/W20/W21: no `zsh -l`, explicit PATH,
   sources `~/.nuzantara-secrets.env` (set -a / . / set +a), exec'd python3.
   Defensive: emits WARNING to stderr if `FLY_API_TOKEN` missing post-source.

2. **Plist patched** via `plistlib`: `ProgramArguments` reduced from
   `[python3, -m, organism.supervisor.daemon]` to `[wrapper.sh]`. Plist
   archived at `~/Library/LaunchAgents/.archive-2026-05-23/com.nuzantara.organism.supervisor.plist.pre-w28`.
   Plist mode kept at 0400 (W21 hardening preserved).

3. **TCC dead-end discovered**: tried fallback wrapper that sources
   `apps/cell/.env` (where Cell daemon currently holds the token) but
   launchd TCC sandbox blocks reads from ~/Desktop:
   ```
   /Users/nuzantara/Desktop/nuzantara/apps/cell/.env:.:32: operation not permitted
   ```
   Reverted. Token MUST live in `~/.nuzantara-secrets.env` (0600 vault, HOME).

## Remaining manual operator action

`~/.nuzantara-secrets.env` does NOT yet contain `FLY_API_TOKEN`. Operator
needs to append:

```bash
# Append the same FlyV1 token from apps/cell/.env to canonical secrets vault
grep "^FLY_API_TOKEN" /Users/nuzantara/Desktop/nuzantara/apps/cell/.env \
    >> ~/.nuzantara-secrets.env
chmod 0600 ~/.nuzantara-secrets.env
launchctl kickstart -k gui/$(id -u)/com.nuzantara.organism.supervisor
```

Verification post-add:

```bash
SUPER_PID=$(launchctl print gui/$(id -u)/com.nuzantara.organism.supervisor \
    | grep "pid =" | head -1 | awk '{print $3}')
ps eww -p $SUPER_PID | tr ' ' '\n' | grep "^FLY_API_TOKEN"
# Should output FLY_API_TOKEN=FlyV1...
```

Until operator adds the token:

- Wrapper logs WARNING on every restart (visible in supervisor.err)
- Pipeline ships everything except final actuator step
- W27 sustained-red event still emits + dispatches; FlyMachinesStart.execute()
  fails with auth error (already does in current state)

## Empirical post-restart smoke

| Check                              | Result                                        |
| ---------------------------------- | --------------------------------------------- |
| Wrapper executable                 | ✅ `chmod +x`                                 |
| Plist `plutil -lint`               | ✅ OK                                         |
| Supervisor `state = running`       | ✅ PID 68609                                  |
| `TELEGRAM_BOT_TOKEN` in env        | ✅ inherited from secrets.env                 |
| `FLY_API_TOKEN` in env             | ❌ missing (expected, not yet added to vault) |
| Wrapper WARNING log                | ✅ fires correctly                            |
| TCC sandbox `apps/cell/.env` block | ✅ documented, fallback reverted              |

## Architectural lesson

The W27 Path A 5-file change accomplished ~80% of auto-heal. The remaining
20% is one-line config edit to canonical secrets vault. Pattern: cross-cutting
runtime concerns (auth tokens, API keys) need a single-source-of-truth file
that all services read; coupling Cell .env to supervisor.env creates
maintenance debt.

## Sources

1. `apps/cell/.env` (Cell-only token currently)
2. `~/.nuzantara-secrets.env` (canonical vault, missing token)
3. `~/scripts/organism-supervisor-wrapper.sh` (W28 wrapper)
4. `~/Library/LaunchAgents/com.nuzantara.organism.supervisor.plist` (W28 plist)
5. TCC sandbox empirical: `~/Desktop` blocked from launchd file ops
