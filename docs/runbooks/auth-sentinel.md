# auth-sentinel — runbook

> **Cos'è.** Un guardiano che PROVA ogni credenziale della fleet con il suo
> comando reale (mai un proxy), la classifica, e per ciò che richiede davvero un
> gesto umano manda UN alert Telegram azionabile col comando esatto. Nato
> 2026-07-11 dalla richiesta Zero "rendere autonomi i login interattivi umani".
> Elimina la **scoperta-troppo-tardi** (cascata Fly 14/5, IG-190, NLM-expired 6/7):
> il fallimento non lo scopre più il cron che ci sbatte contro, lo scopre il
> sentinel 6h prima.

## Cosa NON fa (e perché)

Il sentinel **non bypassa** i login umani — quella via, per agy/nlm/codex-revoked,
richiederebbe di archiviare una sessione Google riutilizzabile (cookie CDP), che
viola il boundary secret-in-the-clear (scar #4) + SYMBIOSIS Law 2. La decisione
per-arma (2026-07-11) è: **ramo A auto-refresh + verifica; ramo B ridotto a 1
gesto raro con comando pronto; TCC diagnosi + click esatto (mai `tccutil reset`).**

## Le due famiglie + TCC

| Arma | Famiglia | Refresh | Login umano? |
|---|---|---|---|
| claude-oauth ×3 | A | ✅ refresh_token (il probe forza il refresh) | solo weekly-cap |
| fly | A | ✅ token lungo; **serve `-t` esplicito nei wrapper cron** (regression 0.4.49) | no |
| deepseek | A | ✅ chiave statica | no |
| drive-oauth | A | ✅ delegato a `drive_token_watchdog.py` | 1×/90gg |
| codex | B | ⚠️ refresh ok, ma revocabile server-side | solo se `token_revoked` |
| agy | B | ⚠️ sessione Antigravity/Google | solo se muore |
| nlm | B | ⚠️ CDP cookies volatili (`--clear` una-tantum) | solo dopo `--clear` |
| **tcc** | B-hard | ❌ grant OS-level, **non automatizzabile** | sì, System Settings |

## Uso

```bash
python3 scripts/auth_sentinel.py            # probe + alert-quando-serve
python3 scripts/auth_sentinel.py --json     # report machine-readable, no alert
python3 scripts/auth_sentinel.py --no-alert # probe + report, mai Telegram (dry)
python3 scripts/auth_sentinel.py --selftest # verifica salute del sentinel stesso
```

Status: 🟢 OK · ♻️ REFRESHED (rinnovato da solo) · 🟠 WARN (config, workaround noto —
digest, non alert) · 🔴 ACTION (serve gesto umano → alert col comando) · ⚪ SKIP
(non su questa macchina) · 🟡 UNKNOWN (probe non conclusivo → log, mai falso allarme).

**Solo 🔴 ACTION genera alert Telegram.** WARN/OK/SKIP/UNKNOWN = zero rumore (così
gli alert restano credibili — un sentinel che grida sul sano ti riabitua a ignorarlo).

## Install (operator — tocca launchd)

```bash
# 1. copia il wrapper nella dir canon FUORI da ~/Desktop (W84)
cp scripts/auth_sentinel_cron.sh ~/.nuzantara-cron/
chmod +x ~/.nuzantara-cron/auth_sentinel_cron.sh
# 2. installa il plist
cp infra/launchagents/com.balizero.auth-sentinel.daily.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.balizero.auth-sentinel.daily.plist
# 3. verifica (green≠working — leggi il LOG, non l'exit)
launchctl kickstart -k gui/$(id -u)/com.balizero.auth-sentinel.daily
tail -20 ~/.local/state/auth-sentinel/run.log
```

## Il TCC — perché resta operator-only (hard boundary)

`probe_tcc` DIAGNOSTICA il green-but-dead W84 (job con `Operation not permitted`
nel log-err scritto <2h fa → il grant TCC è morto ORA, non una ferita storica) e
i job che girano ancora da `~/Desktop`. Ma la CURA è **solo tua**: System Settings
→ Privacy & Security → Full Disk Access. **`tccutil reset` è VIETATO** (scar
W84-tccutil-recidiva: resetta i grant OS-wide di TUTTE le app, scope opposto al
fix). Nessun comando che tocca lo stato TCC senza scope esplicito va lanciato come
probe. Questo è il senso onesto della richiesta: il TCC NON si può rendere
autonomo — macOS lo protegge per design — ma lo si può rendere **diagnosticato in
anticipo + con il click esatto pronto**, così il gesto è di 10 secondi, non un
debug di mezz'ora.

## Anti-falso-positivo (perché credere agli alert)

Ogni probe è stato tarato contro un caso sano reale il 2026-07-11:
- **fly** OK senza `-t` in shell interattivo → non promuovere ACTION se il probe
  base passa; ACTION solo se il probe base fallisce E `-t` salva (= regression cron).
- **codex** cold-start >60s → timeout 90s per non falsare TIMEOUT un seat vivo.
- **tcc** log-err cumulativo (98 mv-fail STORICHE su wr2.queue-pull) → conta solo
  se il log è stato scritto <2h fa; ferite cicatrizzate = OK.

## Estenderlo

Una credenziale nuova = una funzione `probe_<arm>() -> Probe` + una riga in `PROBES`.
Contratto: ritorna OK/WARN/ACTION/SKIP/UNKNOWN, mai legge/stampa il valore del
segreto (solo exit-code + stringa d'errore nota), mai un comando distruttivo.
```

## Referenze

- scar #2 (esiste≠armato / W84 TCC) · scar #4 (secret-clear) · scar #7 (daemon-cron)
- `lessons_fly_cli_token_regression_cascade` · `runbook_nlm_auth_stability_fix`
- `decision_max3_oauth_fallback_armed_fleet_2026_06_23` (i 3 token MAX)
- alerting: `scripts/sentinel_lib/alerter.py` → `scripts/tg_notify.py` (relay ssh)
