# Audit 08: Air LaunchAgents — Risultati e Azioni

**Data:** 2026-03-16
**Eseguito da:** Claude Opus 4.6
**Macchina:** Air (antonellosiano@Nuzantara-9) via SSH

## Azioni Eseguite

### Disabilitati 6 LaunchAgents

| Servizio             | Motivo                                               | RAM liberata |
| -------------------- | ---------------------------------------------------- | ------------ |
| `syncthing`          | CPU 185%, ridondante con post-commit hook Pro→Air    | ~98 MB + CPU |
| `cloudflared`        | Crash loop (exit 1), nessun tunnel configurato       | 0 (crashato) |
| `git-auto-backup`    | Ridondante + pericoloso (`git stash` su repo attivo) | trasc.       |
| `disk-space-monitor` | 216 GB liberi, inutile                               | trasc.       |
| `ram-monitor`        | Marginale con monitor-pro attivo                     | trasc.       |
| `adobe.ccxprocess`   | 407 MB RAM su server H24, nessun uso grafico         | ~407 MB      |

**Metodo:** `launchctl unload` + plist spostati in `~/Library/LaunchAgents/_disabled/`

### Servizi rimasti attivi (8)

| Servizio                       | Ruolo                         |
| ------------------------------ | ----------------------------- |
| `ai.openclaw.gateway`          | Gateway AI principale         |
| `ai.openclaw.node`             | Node worker cron/task         |
| `com.openclaw.monitor-pro`     | Failover monitoring           |
| `homebrew.mxcl.postgresql@17`  | DB locale bali-intel          |
| `homebrew.mxcl.ollama`         | LLM locale (deepseek-r1:1.5b) |
| `com.user.docker-health-check` | Restart Docker se down        |
| `com.user.weekly-cleanup`      | Pulizia cache dom 02:00       |
| `com.claude-max-api`           | Da verificare                 |

### Da verificare (prossima sessione)

- **claude-max-api**: capire cosa fa, possibile overlap con OpenClaw gateway
- **Ollama su Air**: solo deepseek-r1:1.5b, valutare se serve
- **bali-intel-api**: container Docker up ma API non risponde

## Ripristino

Se servisse riabilitare un servizio:

```bash
ssh air 'mv ~/Library/LaunchAgents/_disabled/NOME.plist ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/NOME.plist'
```
