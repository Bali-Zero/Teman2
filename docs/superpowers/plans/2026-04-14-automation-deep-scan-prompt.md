# Automation Deep Scan — Prompt per prossima sessione

> Copia-incolla questo come primo messaggio dopo `/clear`

---

## Prompt

Riprendi il lavoro della sessione precedente. Leggi prima:

- `docs/AUTOMATION_MODEL_MAP.md` — mappa 188 automazioni attuale
- `docs/automations-inventory.xlsx` — Excel auto-generato
- `scripts/automation_catalog.json` — catalogo umano-verificato
- `scripts/generate_automations_excel.py` — generatore con auto-discovery

Poi fai uno scan ESAUSTIVO di TUTTE le categorie di automazione nel sistema che NON sono ancora tracciate nelle 188 entries. Cerca in tutto il codebase (`~/Desktop/nuzantara/`, `~/scripts/`, `~/Library/LaunchAgents/`, Air via SSH).

### Categorie da cercare:

```bash
# 1. Redis pub/sub listeners (persistent subscribers)
grep -rn "subscribe\|pubsub\|on_message" apps/ packages/ --include="*.py" | grep -v __pycache__ | grep -v test | grep -v .worktree

# 2. PostgreSQL LISTEN/NOTIFY (PG event listeners)
grep -rn "LISTEN\|pg_notify\|add_listener" apps/ --include="*.py" | grep -v __pycache__ | grep -v test

# 3. Webhook endpoints (receive external events)
grep -rn "@app.post.*webhook\|@router.post.*webhook\|@router.post.*callback\|@router.post.*hook" apps/ --include="*.py" | grep -v __pycache__ | grep -v test

# 4. FastAPI BackgroundTasks (fire-and-forget)
grep -rn "BackgroundTasks\|background_tasks.add_task\|add_task(" apps/ --include="*.py" | grep -v __pycache__ | grep -v test

# 5. File watchers (fsevents, watchdog)
grep -rn "watchdog\|inotify\|fsevents\|FileSystemEventHandler\|watchfiles" apps/ scripts/ --include="*.py" | grep -v __pycache__

# 6. GitHub Actions workflows
ls -la .github/workflows/ 2>/dev/null && cat .github/workflows/*.yml | grep -E "^name:|schedule:|cron:"

# 7. Claude Code hooks
python3 -c "import json; d=json.load(open('$HOME/.claude/settings.json')); [print(f'{k}: {len(v)} hooks — {[h.get(\"matcher\",\"*\") for h in v]}') for k,v in d.get('hooks',{}).items()]"

# 8. Vercel cron
grep -rn "crons\|schedule" apps/mouth/vercel.json 2>/dev/null

# 9. Docker services (Air)
ssh air 'cat ~/Projects/nuzantara/docker-compose*.yml 2>/dev/null'

# 10. Timer decorators
grep -rn "repeat_every\|@scheduler\|@periodic\|@crontab" apps/ --include="*.py" | grep -v __pycache__

# 11. OpenClaw skills/plugins con scheduling
find ~/.openclaw/skills ~/.openclaw/extensions -name "*.js" -o -name "*.json" 2>/dev/null | head -20

# 12. npm scripts
grep -rn "\"watch\"\|\"cron\"\|\"schedule\"\|\"worker\"" apps/*/package.json packages/*/package.json 2>/dev/null

# 13. Background tasks in apps/ non esplorati
for app in graph-engine war-room kbli-navigator kbli-voice zantara-media admin-dashboard calendar drive knowledge mail web; do
  echo "=== apps/$app/ ==="
  grep -rn "create_task\|background\|schedule\|cron\|loop\|worker" apps/$app/ --include="*.py" --include="*.ts" --include="*.js" 2>/dev/null | grep -v __pycache__ | grep -v node_modules | head -5
done

# 14. ~/scripts/ fuori dal repo
diff <(ls ~/Desktop/nuzantara/scripts/*.sh ~/Desktop/nuzantara/scripts/*.py 2>/dev/null | xargs -I{} basename {}) <(ls ~/scripts/*.sh ~/scripts/*.py 2>/dev/null | xargs -I{} basename {}) | grep "^>" | head -20

# 15. Cell e Mata Garuda tasks extra
grep -rn "create_task\|schedule\|periodic\|timer" apps/cell/ apps/mata-garuda/ --include="*.py" | grep -v __pycache__ | grep -v test | head -20
```

### Cosa fare con i risultati:

1. Per ogni automazione trovata, classifica: tipo, sistema (Garuda/Cell/NLM/SEO/CRM/Sentinel/Olympus/Ops), schedule, stato (attivo/disabilitato/zombie)
2. Aggiungile a `scripts/automation_catalog.json` nella sezione appropriata
3. Rigenera `docs/automations-inventory.xlsx`
4. Manda la lista a Gemini CLI, Codex CLI, DeepSeek API per validazione
5. Voto finale: schedule, keep-manual, o delete per ogni nuova trovata
6. Esegui le azioni e committa

### Contesto della sessione precedente:

- 14 commit in questa sessione
- 188 automazioni (Pro 107, Air 60, Backend 21)
- Sentinel: Tier 2.5 Codex implementato e testato
- OpenClaw: riconfigurato Ollama-first (qwen3.5:9b Pro, qwen3:4b Air)
- Excel si rigenera ogni notte alle 23:15 con auto-discovery
- NB-1 ha snapshot vecchio (2026-03-23) — non fidarsi per file nuovi
- Codex e' l'agente piu' preciso (leggeva codice reale, 0 allucinazioni)
