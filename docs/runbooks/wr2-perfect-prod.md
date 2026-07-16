# Runbook — WR2 carousel pipeline (operatore non-dev)

> Pipeline editoriale: brief → storyboard → layout → critic → Canva → human gate → Instagram. Versione 2026-05-20 dopo Phase B+C+D del piano perfect-production.

## 1. Cosa controllare giornalmente (2 min)

Dashboard `https://kita.balizero.com/admin/observability`, pannello "WR2":

| Spia             | Verde           | Giallo         | Rosso                       |
| ---------------- | --------------- | -------------- | --------------------------- |
| drafts last 24h  | ≥ 1 nuovo draft | 0 nuovi draft  | 0 nuovi draft per 3+ giorni |
| ultimo published | < 7 giorni fa   | 7-14 giorni fa | > 14 giorni fa              |
| critic pass rate | > 80%           | 50-80%         | < 50% — qualità rotta       |
| probe last pass  | < 24h fa        | 24-48h fa      | > 48h fa o `FAILED`         |

WR2 è semi-batch (1 carosello/giorno è normale). Giallo su "drafts last 24h" non è sempre allarme — controlla calendario editoriale.

## 2. Quando arriva alert Telegram

`TELEGRAM_PROBE_CHAT_ID` o `TELEGRAM_OWNER_CHAT_ID` (fallback):

| Alert                                 | Significato                                | Azione                             |
| ------------------------------------- | ------------------------------------------ | ---------------------------------- |
| `🔴 wr2 e2e probe FAILED rc=N`        | Probe sintetico ha fallito una transizione | Vedi §3                            |
| `🔴 wr2 supervisor down`              | Daemon orchestratore morto                 | Vedi §4                            |
| `⚠️ canva-renderer rejected N drafts` | Render fallito ripetutamente               | Antonello — cicatrix template scar |

## 3. Fail-mode "wr2 e2e probe FAILED"

```bash
tail -50 ~/logs/wr2-probe-cron.log
grep "hop[1-6]" ~/logs/wr2-probe-cron.log | tail -10
```

| Hop | Causa probabile                                                 | Azione                                                                               |
| --- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| 1   | DB pool non disponibile / migration 187 non applicata           | Verifica `psql ... -c "SELECT 1"` + `\d intel_items`                                 |
| 2   | `war_room_drafts` table mancante / status enum drift            | Controlla migration recente — Antonello                                              |
| 3   | `patch_json` schema cambiato — colonna `drafts_json` rinominata | Antonello — repository.py changelog                                                  |
| 4   | Critic rubric values forzati < 0.85 (test bug, non prod)        | Probe script bug — non bloccante per produzione                                      |
| 5   | Non può fallire (just a log line)                               | N/A                                                                                  |
| 6   | Probe lasciato dangling                                         | Cleanup: `psql -c "DELETE FROM war_room_drafts WHERE topic LIKE '[PROBE-SANDBOX-%'"` |

## 4. Supervisor down

Antonello-only.

```bash
# Verifica WR2 supervisor
launchctl print gui/$(id -u)/com.balizero.wr2.supervisor | grep -E "state|pid|last exit"
# Atteso: state = running, last exit = 0

# Se morto:
launchctl bootout gui/$(id -u)/com.balizero.wr2.supervisor
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.wr2.supervisor.plist
```

Stato PID supervisor + worktree: vedi cicatrice 2026-05-19 "WR2 zombies" in `.claude/rules/cicatrix-scars.md`.

## 5. Rollback nuclear

Stop tutto il rendering WR2 senza toccare brief/storyboard (mantiene drafts in DB intatti):

```bash
# Stop renderer + supervisor + probes
for label in wr2.supervisor wr2.canva-renderer wr2.e2e-probe.daily; do
    launchctl bootout gui/$(id -u)/com.balizero.${label} 2>/dev/null
done

# DB kill-switch (ferma renderer cron anche se plist riemerge)
psql "${DATABASE_URL}" -c "
    INSERT INTO system_settings (key, value)
    VALUES ('wr2_canva_renderer_enabled', 'false')
    ON CONFLICT (key) DO UPDATE SET value = 'false';
"
```

Re-attivazione: flip kill-switch a `'true'` + re-bootstrap LaunchAgent.

## 6. Riferimenti

- Endpoint: `GET https://nuzantara-rag.fly.dev/api/intel/health/pipeline` (sezione `wr2`)
- Plist: `~/nuzantara/infra/launchagents/com.balizero.wr2.e2e-probe.daily.plist`
- Probe script: `~/nuzantara/scripts/probes/wr2_e2e_probe.py`
- Cleanup emergency: `docs/runbooks/synthetic-probe-cleanup.md`
- Master template (fisso): `DAHJEkWpkzY` (locked dietro master-template-guard CI)
