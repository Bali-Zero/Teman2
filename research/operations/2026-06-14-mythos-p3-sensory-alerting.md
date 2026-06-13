---
date: 2026-06-14
domain: compliance
client_case: none
sources:
  - live disk/redis/launchctl inspection on Pro (2026-06-14)
  - 3 read-only fan-out subagents (feeder autopsy / alert-channel trace / token-leak hunt)
  - Gemini 3.5-Flash-High meta-pattern synthesis
  - cicatrici W34/W55/W64/W65/W70/W71, NLM-feeder split-brain 2026-05-06
session: Opus Mythos P3 — sensory + signaling organ
---

# Mythos-P3 — Sistema sensoriale + segnaletico (feeder NLM + canali allarme Telegram)

## §0 Executive

L'organo **sensoriale** (i feeder NotebookLM = gli "occhi" sulla normativa indonesiana) e
**segnaletico** (i watchdog Telegram = i "nervi del dolore") era **cieco e anestetizzato
insieme**: feeder che giravano senza alimentare nulla, e l'allarme P0 più severo muto da
settimane — il tutto invisibile perché l'unico sintomo era un log che cresce e nessuno legge.

**5 malati di primo ordine** (tutti verificati su disco, non dal report dei subagent):

| # | Organo | Stato | Causa-radice (verificata) | Cura | Verifica live |
|---|---|---|---|---|---|
| 1 | matagaruda **intel-bridge** | abortiva ogni 60s, 48MB di 1 riga | `BRIDGE_API_KEY` non in `.nuzantara-secrets.env` (sta in `~/.cell-bridge-state/wa-media.env`) | wrapper sorgia anche quel file | ✅ `Bridge pull: fetched=50 published=50` |
| 2 | **nlm_feeder_stream** | `0/0/0` da 33 giorni | `GARUDA_REDIS_HOST=Mini` (down) mentre 3144 item su Pro localhost; `[ERROR]→[]` maschera il timeout | preflight fail-loud + wrapper fallback localhost | ✅ `alerts 10/10 fed`, lag 22→2; enriched fed, lag 3144→3124 |
| 3 | **gap_scanner** | "morto 9gg" (connectome) | **FALSO** — vivo (crontab, girato 13/06 21:34). 3/7 domini NLM "no response" | — (falso allarme; degrado NLM separato) | n/a |
| 4 | **gap-consumer** | gira ma 0 gap risolti | `claude` non in PATH launchd (sta in `~/.local/bin`) | wrapper PATH += `~/.local/bin` | ✅ `claude` risolve |
| 5 | **wr2_supervisor_watchdog** | SUPERVISOR_DOWN muto | `parse_mode=Markdown` + `_` sbilanciato in `wr2_supervisor` → HTTP 400 ogni invio (15/15) | plain text, no markdown, cooldown gated su consegna | ✅ self-test Telegram HTTP 200 |
| 6 | **token leak** | bot-token in log 26.410× | httpx logga l'URL (token nel path) a INFO | helper redazione + silence httpx + truncate residuo | ✅ helper testato, gate fixato, 48MB→10KB |

2 correzioni al connectome (Mythos: i subagent/connectome sono LEAD, non fatti): **gap_scanner NON
è morto** (crontab vivo), e il 400 del watchdog NON è "muto continuo da 3gg" ma intermittente +
SUPERVISOR_DOWN-specifico + cooldown-suppression.

## §1 Feeder NLM

### 1.1 intel-bridge — secret-store drift (famiglia W65)
`matagaruda-bridge.sh` sorgiava **solo** `~/.nuzantara-secrets.env`; `BRIDGE_API_KEY` era migrato a
`~/.cell-bridge-state/wa-media.env` (0600, già sorgiato da `wa-media-pull-run.sh` +
`intake-gate-pusher-run.sh`). `nerve.py:598` → `if not api_key: logger.error("BRIDGE_API_KEY not
set — aborting bridge cycle"); return`. StartInterval=60 → 1 riga ERROR/60s → 48MB. **Fix**: il
wrapper ora sorgia anche quel file. **Live**: dopo kickstart, `Bridge pull: fetched=50
published=50`, `Bridge push: acked=6` — il nervo ottico ri-pompa dati Fly↔Pro.

### 1.2 nlm_feeder_stream — split-brain regression + maschera del fallimento silenzioso
Il plist orario imposta `GARUDA_REDIS_HOST=100.93.236.6` (Mini Tailscale). Mini è **down**
(`redis-cli -h 100.93.236.6 ping` → timeout). I producer (scorer/classifier/ner) **non** hanno
override → scrivono **Pro localhost**, dove `garuda:enriched` aveva **lag=3144** (gruppo
`nlm_feeder` fermo a `last-delivered 1778535909186` ≈ 11 maggio) e `garuda:alerts` lag=22.
**Maschera (load-bearing)**: `base_worker.py:76-78` — `result = redis_cmd(*args); if not result or
result.startswith("[ERROR]"): return []`. Un timeout redis-cli (`[ERROR] redis-cli timeout`) è
**indistinguibile** da "stream vuoto" → 33 giorni di cecità riportati come `processed:0`.

**Fix (2 livelli)**: (a) **codice** — `run_nlm_feeder_stream.main()` ora fa un PING redis di
preflight; su `[ERROR]`/no-PONG logga ERROR + emette JSON `redis_unreachable` + exit 3 (mai più
`0/0/0` mascherato come sano). (b) **wrapper** — fallback a `127.0.0.1` se l'host configurato è
irraggiungibile. **Live**: WARN `configured redis 100.93.236.6 unreachable — falling back to
127.0.0.1`; run completo `alerts: processed=10, fed=10`, `enriched: processed=10, fed=1,
skipped=9` → **+11 source a NotebookLM**; `nlm_feeder_alerts` lag 22→2, `nlm_feeder` enriched lag
3144→3124 (drena).

### 1.3 gap_scanner / gap-detector — falso allarme + gap-consumer PATH
`apps/evaluator/.../gap_scanner.py` è **crontab** (girato 13/06 21:34, Layer A) — invisibile a uno
scan launchctl-only → da cui il falso "morto". `com.garuda.gap-detector` (LaunchAgent distinto,
OSINT-Nexus/Neo4j) anch'esso vivo (13/06 18:00, 47 gap, 0 pubblicati perché tutti dedup-skip).
**gap-consumer**: `[CLIRuntime] ... Command not found: claude` — `claude` sta in `~/.local/bin`,
assente dal PATH del plist/wrapper. **Fix**: wrapper PATH += `~/.local/bin`. **Live**: `claude`
risolve. (Risoluzione gap end-to-end verificabile alla finestra cron 06:00-22:00 WITA.)

## §2 Canali allarme Telegram

`wr2_supervisor_watchdog` rileva correttamente `pipeline_frozen` + `success_rate=0.0%`, ma il P0
**SUPERVISOR_DOWN** falliva l'invio **15/15** con `HTTP 400 Bad Request`: `_send_telegram` forzava
`parse_mode=Markdown` e il corpo contiene il letterale `wr2_supervisor` — l'underscore apre
un'entità italic sbilanciata → "can't parse entities". Gli altri 2 alert (markdown-safe, `_`
dentro backtick) passavano 200 ma throttle 24h. Peggio: `_state_set` (cooldown) era armato **anche
su invio fallito** → un 400 sopprimeva il retry per 24h.

**Fix**: plain text (no parse_mode, strip `*`/backtick); `_send_telegram` ritorna `bool`; cooldown
armato **solo su consegna confermata** (retry al tick successivo, non 24h). Log dell'eccezione
`type(e).__name__` (defense-in-depth). **Live**: self-test plain-text (contenente
`wr2_supervisor`) → **HTTP 200** alla chat owner. Canale provato; il Markdown era l'unico blocco.

## §3 Leak token

Classe radice: **secret-in-URL-path + libreria che logga l'URL a INFO**. Telegram richiede il
token nel path (`…/bot<TOKEN>/…`); httpx emette `HTTP Request: <url>` a INFO; root logger a INFO +
httpx non silenziato → `wr2-telegram-gate.error.log` 26.410 righe (amplificate da un loop
`getUpdates` in 409-Conflict = poller duplicato, famiglia W67c active-active). Altri siti stessa
classe: `apps/cell/effectors/telegram.py` (Cell, attivo), `wa-audit-bot/bot.py`,
`bz_content_broadcaster.py`, `codex_tri_llm_review.py`, `wr2_html_render_apply.py`,
`federation_orchestrator.py`. Classe separata (env-dump): `codex_automation_lib.sh` esporta
`TELEGRAM_BOT_TOKEN` nell'env passato a `codex exec`, che lo echeggia nei rollout jsonl.

**Fix (sorgente, perimetro mio)**: nuovo `scripts/_log_redact.py`
(`install_secret_redaction()`: silenzia httpx/httpcore/telegram + filtro root che scruba pattern
bot-token), applicato in `wr2_telegram_publish_gate.py` (la sorgente da 26k — plist già
decommissionato, ma il codice ri-sanguinerebbe se ri-armato). Residuo 48MB del bridge troncato a
10KB. **Residuo NON mio**: rotazione token (compromesso) = Zero; silenziare httpx negli altri siti
(Cell = perimetro M*) = sweep coordinato.

## §Meta-pattern — perché i tubi della freschezza muoiono in silenzio

> **La malattia-delle-malattie: l'organismo equipara la *sopravvivenza del processo* (exit-0, il
> loop gira, il log cresce) al *funzionamento* (throughput, consegna). Non legge i propri output e
> non ha un segnale che distingua "ha girato" da "ha funzionato".**

Un feeder che gira-ma-non-alimenta (1,2) e un alert che scatta-ma-non-consegna (5), e un secret
che cola in un log che nessuno legge (6), leggono tutti come "sano". 3 evidenze trasversali
(convergenza indipendente Gemini + Opus):

1. **Zero-throughput mascherato (1,2)**: un fallimento d'integrazione (chiave mancante, timeout
   verso un peer down) viene inghiottito → "idle", non "starved". `[ERROR]→[]` è la maschera
   fisica.
2. **Telemetria write-only (3,5,6)**: i log si scrivono, non si leggono — 48MB di un errore e 26k
   righe di token sarebbero stati catturati se qualcuno (o qualcosa) leggesse; un 400 di consegna
   arma persino il cooldown di soppressione.
3. **Blindspot di isolamento (4)**: si assume parità env/PATH tra shell utente e daemon launchd,
   senza validazione di loopback che il comando dispatchato sia DAVVERO eseguito.

**Contromisura strutturale — dead-man's switch dei feeder** (proposta, non shippata in questa
sessione — confine): ogni feeder/cron scrive un *pulse* `{ts, throughput:N, status:OK|ABORT}` a
fine ciclo (Redis key `pulse:<organ>` o file). Un watchdog indipendente (orario) allarma se
`now-ts > 2×intervallo` OPPURE `status≠OK` OPPURE `throughput cumulativo == 0 per >Xh mentre la
coda sorgente è non-vuota` (= il caso esatto del feeder: lag>0 + fed=0). **Escape**: l'allarme
bypassa lo stack di messaggistica standard — **strict plain text**, raw POST diretto, fallback
`osascript`/`wall` — così non muore della stessa soppressione/parsing che ha nascosto gli
originali. Questo avrebbe preso 1, 2 e 4 al giorno 1, non al giorno 33. Famiglia cicatrici W70
(`log_tail` falso-amico), W71 (green cron ≠ working), W64 (`esistere ≠ armato`).

## §Terapia eseguita (verificata live)

- **PR repo** (3 commit, worktree `infra-mythos-p3-sensory`): preflight fail-loud feeder (+2 test);
  un-mute watchdog (+4 test, +fix debito test W46); helper redazione + silence httpx (+5 test).
  Tutti i test verdi (mata-garuda 38 passed; watchdog+redact 25 passed).
- **Wrapper HOME** (fuori repo, live): `matagaruda-bridge.sh` (sorgia cell-bridge-state),
  `matagaruda-nlm-feeder-stream.sh` (fallback localhost), `matagaruda-gap-consumer.sh` (PATH).
- **Verifiche live**: bridge `fetched=50 published=50`; feeder `fed 11 source`, lag 22→2 / 3144→3124;
  `claude` risolve; self-test Telegram **HTTP 200**; bridge log 48MB→10KB.

## §Solo-operatore (confine — NON eseguito)

1. **Rotazione `TELEGRAM_BOT_TOKEN`** (@BotFather) — il token è stato world-readable in log per
   settimane = compromesso. Cascata: ~40 shell, i siti Python §3, `~/.nuzantara-secrets.env`, Fly
   secrets, env LaunchAgent. **Prerogativa Zero.**
2. **P2 (coordina)**: droppare `GARUDA_REDIS_HOST` dal plist
   `com.matagaruda.nlm-feeder-stream.hourly` → il feeder defaulta a localhost come i producer
   (chiude il residuo "Mini torna su-ma-vuoto" che il mio fallback-reachability non copre).
   Verificare se `scorer` ha lo stesso override Mini (lag=3036 su localhost = sintomo gemello).
3. **Mini-Pro2 down** — riaccendere/ripristinare rete (infra). Finché down, il fallback localhost
   regge.
4. **Sweep token-leak residuo** (coordina M*/Cell): applicare `install_secret_redaction()` a
   `apps/cell/effectors/telegram.py` (bleeder attivo) + gli altri siti §3; fix `codex_automation_lib.sh`
   env-dump; troncare i log residui.
5. **Dead-man's switch feeder** (§Meta-pattern) — design proposto, da implementare.
