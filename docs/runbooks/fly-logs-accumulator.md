# Runbook — Fly logs accumulator (O0-P1)

**Scopo:** Fly.io trattiene i log per pochissimo — dopo un fallimento di un cron
(es. scar KG staging promotion 2026-07-19) la forensics post-hoc è impossibile.
Questo accumulatore segue `fly logs -a nuzantara-rag` in continuo sul **Pro** e
scrive file giornalieri locali con retention 14 giorni.

**Approvazione contrattuale:** Zero, 2026-07-19 (nuovo job schedulato →
conferma esplicita per AUTONOMOUS_OPS L2 "requires confirmation: new cron").

**PII (Law 2):** i log possono contenere PII → restano solo sul disco del Pro
(`~/logs/fly/nuzantara-rag/`). Mai copiarli su M5, mai in cloud.

## File

| Pezzo           | Repo                                                          | Installato sul Pro                        |
| --------------- | ------------------------------------------------------------- | ----------------------------------------- |
| Script follower | `scripts/fly_logs_accumulator.sh`                             | `~/scripts/fly_logs_accumulator.sh`       |
| LaunchAgent     | `infra/launchagents/com.nuzantara.fly-logs-accumulator.plist` | `~/Library/LaunchAgents/`                 |
| Log giornalieri | —                                                             | `~/logs/fly/nuzantara-rag/YYYY-MM-DD.log` |
| Log launchd     | —                                                             | `~/logs/fly-logs-accumulator.launchd.log` |

## Install / update (sul Pro)

```bash
cp scripts/fly_logs_accumulator.sh ~/scripts/fly_logs_accumulator.sh
chmod +x ~/scripts/fly_logs_accumulator.sh
cp infra/launchagents/com.nuzantara.fly-logs-accumulator.plist ~/Library/LaunchAgents/
launchctl bootout gui/$(id -u)/com.nuzantara.fly-logs-accumulator 2>/dev/null || true
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.nuzantara.fly-logs-accumulator.plist
```

## Verifica

```bash
launchctl list | grep fly-logs-accumulator          # job caricato, PID attivo
tail -5 ~/logs/fly/nuzantara-rag/$(date +%F).log    # sta scrivendo
```

## Kill switch

```bash
launchctl bootout gui/$(id -u)/com.nuzantara.fly-logs-accumulator
```

## Note operative

- **Rotazione:** lo script riavvia il follower a mezzanotte (nuovo file giornaliero);
  il prune dei file >14 gg gira a ogni restart del loop.
- **KeepAlive=true è corretto qui:** è un follower long-running, non un one-shot
  (contrasto con W67: KeepAlive su one-shot = crash-loop).
- **Override senza toccare il plist:** env `FLY_LOGS_APP`, `FLY_BIN`, `FLY_LOGS_DIR`.
