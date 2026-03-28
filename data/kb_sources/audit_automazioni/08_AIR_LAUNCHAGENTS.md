# Prompt 8/8: Audit LaunchAgents Air

**Macchina:** Air (`antonellosiano@Nuzantara-9`, via `ssh air`)
**Scope:** 14 LaunchAgent plist
**Durata stimata:** 15-20 minuti
**Rischio:** MEDIO (servizi infrastrutturali Air)

---

## MISSIONE

Verifica la salute dei LaunchAgents su Air. Air è il server H24 (16GB M4) — i servizi devono girare senza interruzione.

## LISTA COMPLETA

```
ai.openclaw.gateway.plist
ai.openclaw.node.plist
com.adobe.ccxprocess.plist
com.claude-max-api.plist
com.cloudflare.cloudflared.plist
com.openclaw.monitor-pro.plist
com.user.disk-space-monitor.plist
com.user.docker-health-check.plist
com.user.git-auto-backup.plist
com.user.ram-monitor.plist
com.user.weekly-cleanup.plist
homebrew.mxcl.ollama.plist
homebrew.mxcl.postgresql@17.plist
homebrew.mxcl.syncthing.plist
```

## ANALISI PER OGNI SERVIZIO

Esegui tutto via SSH:

### Gruppo A: OpenClaw (3)

1. **ai.openclaw.gateway** — Gateway Air

```bash
ssh air 'launchctl list | grep openclaw.gateway'
ssh air 'curl -sf http://localhost:18789/health || echo "Gateway DOWN"'
ssh air 'cat ~/Library/LaunchAgents/ai.openclaw.gateway.plist'
```

- Serve? Air ha un gateway locale? O riceve dal tunnel Pro?
- Se il tunnel Pro:18789→Air:18790 è attivo, Air ha DUE gateway (locale + tunnel)?

2. **ai.openclaw.node** — Node worker Air

```bash
ssh air 'launchctl list | grep openclaw.node'
```

- Quanti task esegue? È l'esecutore dei cron Air?

3. **com.openclaw.monitor-pro** — Monitora Pro da Air

```bash
ssh air 'launchctl list | grep monitor-pro'
ssh air 'cat ~/Library/LaunchAgents/com.openclaw.monitor-pro.plist'
```

- Controlla la salute di Pro (speculare a `monitor-air` su Pro)
- Funziona? Ultimo alert?

### Gruppo B: Infra (3)

4. **homebrew.mxcl.postgresql@17** — PostgreSQL 17

```bash
ssh air 'pg_isready -h localhost -p 5432'
```

- Air ha un DB locale? Per cosa lo usa?
- È una replica di Fly.io? O un DB separato?

5. **homebrew.mxcl.ollama** — Ollama

```bash
ssh air 'curl -sf http://localhost:11434/api/tags | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'"'"'{len(d.get(\"models\",[]))} models'"'"')"'
ssh air 'ollama ps 2>/dev/null'
```

- Quanti modelli? Usati dalle automazioni notturne?
- La finestra cron (01:00-04:00) lo controlla — ma Ollama è KeepAlive?
- Se è KeepAlive → la finestra cron è inutile (Ollama è sempre acceso)

6. **homebrew.mxcl.syncthing** — Syncthing file sync

```bash
ssh air 'launchctl list | grep syncthing'
ssh air 'curl -sf http://localhost:8384/rest/system/status -H "X-API-Key: $(cat ~/.config/syncthing/config.xml 2>/dev/null | grep apikey | head -1 | sed "s/.*<apikey>//;s/<.*//")" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get(\"myID\",\"?\")[:8])" 2>/dev/null || echo "Syncthing unreachable"'
```

- Cosa sincronizza? Pro↔Air? O altro?
- Overlap con `nuzantara-sync.sh` (git sync Pro↔Air)?

### Gruppo C: Monitoring (5)

7. **com.user.disk-space-monitor** — Monitor spazio disco

```bash
ssh air 'cat ~/Library/LaunchAgents/com.user.disk-space-monitor.plist'
```

- Cosa fa quando lo spazio è basso? Alert?

8. **com.user.docker-health-check** — Docker health check

```bash
ssh air 'cat ~/Library/LaunchAgents/com.user.docker-health-check.plist'
ssh air 'docker ps 2>/dev/null || echo "Docker non attivo"'
```

- Air usa Docker? Per cosa?
- Se Docker non gira → questo monitor è inutile → ELIMINARE?

9. **com.user.git-auto-backup** — Git auto backup

```bash
ssh air 'cat ~/Library/LaunchAgents/com.user.git-auto-backup.plist'
```

- Backup git automatico — di cosa? Il repo nuzantara?
- Overlap con `nuzantara-sync.sh` e post-commit hook?

10. **com.user.ram-monitor** — Monitor RAM

```bash
ssh air 'cat ~/Library/LaunchAgents/com.user.ram-monitor.plist'
```

- 16GB Air — il RAM monitor è utile
- Cosa fa quando la RAM è alta? Alert? Kill processi?

11. **com.user.weekly-cleanup** — Pulizia settimanale

```bash
ssh air 'cat ~/Library/LaunchAgents/com.user.weekly-cleanup.plist'
```

- Cosa pulisce? Log vecchi? Cache?

### Gruppo D: Altro (3)

12. **com.claude-max-api** — Claude Max API proxy

```bash
ssh air 'cat ~/Library/LaunchAgents/com.claude-max-api.plist'
ssh air 'launchctl list | grep claude-max'
```

- Serve su Air? O è un duplicato di Pro?
- ANTHROPIC_API_KEY configurato?

13. **com.cloudflare.cloudflared** — Cloudflare tunnel

```bash
ssh air 'launchctl list | grep cloudflared'
ssh air 'cloudflared tunnel list 2>/dev/null || echo "No tunnel info"'
```

- Quale tunnel? Per quale subdomain?

14. **com.adobe.ccxprocess** — Adobe Creative Cloud

```bash
ssh air 'launchctl list | grep adobe'
```

- Residuo Adobe — ELIMINARE? O serve per qualcosa?

## OUTPUT RICHIESTO

### Tabella

| Servizio            | PID | Salute | Utile? | Overlap               | Decisione |
| ------------------- | --- | ------ | ------ | --------------------- | --------- |
| openclaw.gateway    | ?   | ?      | ?      | tunnel da Pro?        | ?         |
| openclaw.node       | ?   | ?      | ?      | —                     | ?         |
| monitor-pro         | ?   | ?      | ?      | speculare monitor-air | ?         |
| postgresql@17       | ?   | ?      | ?      | —                     | ?         |
| ollama              | ?   | ?      | ?      | cron window?          | ?         |
| syncthing           | ?   | ?      | ?      | nuzantara-sync?       | ?         |
| disk-space-monitor  | ?   | ?      | ?      | —                     | ?         |
| docker-health-check | ?   | ?      | ?      | docker attivo?        | ?         |
| git-auto-backup     | ?   | ?      | ?      | sync + hook?          | ?         |
| ram-monitor         | ?   | ?      | ?      | —                     | ?         |
| weekly-cleanup      | ?   | ?      | ?      | —                     | ?         |
| claude-max-api      | ?   | ?      | ?      | Pro ha lo stesso      | ?         |
| cloudflared         | ?   | ?      | ?      | —                     | ?         |
| adobe.ccxprocess    | ?   | ?      | NO     | —                     | ELIMINARE |

### Raccomandazioni

- Quali servizi eliminare per risparmiare RAM su Air (16GB)?
- Quali sono ridondanti con Pro?
- Syncthing + git-auto-backup + nuzantara-sync: servono tutti e 3?
