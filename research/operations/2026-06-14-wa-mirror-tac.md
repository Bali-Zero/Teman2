---
date: 2026-06-14
domain: operations
client_case: none
sources:
  - live Pro (ssh pro-lan) launchctl + /tmp/wa-mirror-logs/*.log + bridge/session.ts (2026-06-14 ~03:30 WITA)
  - postgres-nuzantara prod intake_queue read-only (backend-verifier subagent, fly ssh)
  - cicatrix-scars.md W67/W67b/W67c/W68/W72/W73, W50/W51/W52
  - Gemini 3.5 Flash (High) second-order synthesis + DeepSeek V4 Pro refuter (asymmetric panel)
machine: Air-M5 (balizero) auditing Pro (nuzantara) via pro-lan
---

# TAC del sottosistema wa-mirror — referto autonomo L2

> Audit deep/wide via skill `opus-mythos`. Stato verificato **live** sul Pro (macchina canonica),
> non da memoria. Pannello asimmetrico: Gemini (ampiezza) → DeepSeek (refuter) → gate finale Opus
> + ri-verifica on-disk di ogni claim load-bearing.

## §0 — Executive

**wa-mirror è VIVO e sano nei fondamentali.** Le grandi cicatrici recenti (W67 reconnect-storm, il
backlog intake da 1934, la 2ª istanza Mini) sono **chiuse o stale**. Restano **3 finding reali**, tutti
a basso impatto runtime ma rivelatori di un'unica malattia-di-fondo:

1. **deaf-session falso-positivo notturno** — ~50 reconnect a vuoto in una notte, benigni ma rumorosi.
2. **HOME-fork drift** del bridge openclaw — 813 righe di lavoro vivo non committate nel repo (a rischio perdita).
3. **roster anemico** — `WA_MIRROR_SUPERVISED_NAMES` ha i nomi ma nessun campo di stato/lifecycle.

Nessuno dei tre è una emergenza. Tutti e tre sono la **stessa mano**: vedi §Meta-pattern.

## §1 — Bridge Baileys per-account (VIVI, 5/6 connessi)

`ps` sul Pro: supervisor `supervise-launcher.sh` PID 988 (uptime ~1h), e **6 bridge node** vivi:

| Account | PID | RSS | Stato sessione WA | Note |
|---|---|---|---|---|
| adit | 56736 | ~98MB | connected | deaf-reconnect ×8 stanotte |
| sahira | 62388 | ~98MB | connected | ri-linkata via QR dopo W67b |
| krisna | 63016 | ~98MB | connected | +141 clienti da Damar (12/06) |
| surya | 63608 | ~99MB | connected | deaf-reconnect ×8 |
| asya | 65637 | ~99MB | connected | deaf-reconnect ×8 |
| **damar** | 66842 | ~50MB | **logged_out 401 (atteso)** | standby operatore 12/06 |

`+628213454721` (Ari) e `+628213454727` (Vino): directory sessione **vuote (64B)**, non nel roster →
orfani/dismessi. Pending decisione operatore da W67b/c.

**deaf-session — il vero meccanismo (verificato a `session.ts:282`):** un watchdog (issue Baileys
#2491, `DEAF_SESSION_TIMEOUT_MS = 5min`, poll 60s) forza `sock.end()` + reconnect se il bridge non
riceve **nessun `messages.upsert` di tipo `notify` con messaggio reale per 5 minuti** (FIX 6
2026-05-26 esclude correttamente history-sync e read-receipts dal bump). È ben progettato per il bug
che mira (WA flow-control che zittisce il socket pur lasciandolo "open"). **Ma di notte non sa che è
notte.** I 10 forced-reconnect di adit cadono TUTTI tra **02:24 e 03:24 WITA** (notte fonda Bali,
traffico WhatsApp = 0). `silentMs:357249` (~6 min). **50 reconnect a vuoto in una notte su 5 bridge**,
`attempt` counter → 11. Innocuo (riconnette in ~60s, event-replay non perde messaggi) ma è la **fonte
storica degli alert `reconnect_attempt=N`** che hanno ripetutamente allarmato l'operatore (W67/W67c).

## §2 — Supervisor / LaunchAgent (SANO — W67 regge)

`supervise-launcher.sh` PID 988 stabile a ~1h uptime, **nessun churn** (W67 lo aveva trovato come
`exec` one-shot sotto `KeepAlive=true` → launchd riavviava ogni ~22s SIGTERM-killando i bridge sani;
fix W67 = supervisor bloccante). `launchctl list` mostra `com.balizero.wa-mirror-launcher` con PID
vivo e una corona di organi adiacenti sani (`wa-meta-inbox` running, `wa-lid-refresh` idle-0,
`wa-media-pull` idle-0, `intake-worker` running keepalive). **Verde.**

## §3 — Sessioni WhatsApp (connected/logged-out)

- 5/6 **connected** (con il rumore deaf-session di §1).
- **damar: logged_out 401 terminale — STATO ATTESO, non patologia.** Decisione operatore 12/06
  (standby, 141 clienti → Krisna, wa-mirror "tenuto"). Il bridge fa **la cosa giusta**: smette di
  ritentare (W67b regge — 1 solo alert "needs QR re-link", niente spam). DeepSeek (refuter) e il
  grounding concordano: patologizzarlo sarebbe un errore. L'unico costo è cosmetico (una riga di log).

## §4 — Media-intake (SANO, drained)

- **Anello PULL** (`wa-media-pull`, ogni 300s): HTTP 200 `no pending media (since=49731)`. Verde.
- **Queue Postgres `intake_queue`** (prod, verificata read-only via fly ssh): **0 righe**. Il backlog
  ~1934 + ~40 orphan-lease-2h della memoria è **risolto/stale** — oggi il queue è drenato e *flowing*
  (gate counter `intake_gate_doc_counts` scritto ~2 min prima dell'audit, 12 doc pending sani).
- Il pool grande (`whatsapp_export_documents_staging` = 4823 pending) è un **export storico frozen
  24/05** su pipeline separata, NON backlog vivo. Fuori dal verdetto di salute intake.

## §5 — Propagazione Pro↔Mini (Mini IRRAGGIUNGIBILE)

Mini-Pro2 **offline da ~2gg**: timeout su Tailscale `100.93.236.6`, ping 100% loss su LAN `.44` e `.43`,
mDNS `Mini-Pro2.local` non risolve. **Non posso verificare se il `launchctl bootout+disable` di W67c
(che aveva spento l'orphan active-active wa-mirror su Mini) è persistente al reboot.** → §Solo-operatore.

## §6 — Bridge openclaw + guard-family (HOME-FORK DRIFT reale)

Il bridge `openclaw_whatsapp_bridge.py` (Python/GPT-5.5 con 9 `_guard_*` anti-allucinazione) ha due
copie. La regola W68/W72/W73 imponeva di tenerle **byte-identical fixando entrambe**. Oggi:

- repo `scripts/openclaw_whatsapp_bridge.py` = **64KB, 09/06** (HEAD `fb96fc10a`, W73).
- HOME live `~/.openclaw/bin/openclaw_whatsapp_bridge.py` = **85KB, 13/06** (eseguito dal launchagent
  `com.nuzantara.openclaw-whatsapp-bridge`, running).

`diff` reale = **813 righe, TUTTE HOME-only (zero repo-only)**. Funzioni vive-solo-su-HOME, non nel
repo: `_lkpm_window_is_current` / `_lkpm_window_clause` (finestra LKPM **dinamica** — proprio la
fragilità che W73 aveva flaggato!), `_identity_rules`, `_normalize_whatsapp_format`,
`_is_incidental_villa_mention`, `_hak_milik_asserts_foreigner_can_own`, `_apply_reply_guards`. I 9
guard sono identici tra le due copie; il drift è **tutto il resto** (logica nuova).

**Lettura:** lavoro vero (miglioramenti guard + normalizzazione + finestra LKPM dinamica) fatto sulla
copia LIVE per urgenza, **mai promosso al repo**. Se il repo→HOME viene risincronizzato (come avverte
la cicatrice), si perde. È **esattamente** il rischio W50/W51/W52 + W68/W72/W73, realizzato di nuovo.
*(Drift di sessione sibling — leave-dirty intenzionale, non toccato da remoto; → §Solo-operatore.)*

---

## §Meta-pattern — la malattia-delle-malattie

> Pannello: Gemini propose **"Sindrome dello Stato Ombra"** (manca un source-of-truth, il sistema
> deduce lo stato dai sintomi). DeepSeek (refuter) la **bocciò** su 3 punti — e aveva ragione su tutti
> e 3, verificati on-disk: (a) il symlink read-only repo→HOME *contraddice* W68/W72/W73 (la produzione
> deve poter fixare prima); (b) damar-401 NON è patologia; (c) deaf-session e HOME-fork sono *due*
> malattie, non una. Gate finale (Opus, on-disk): il refuter ha il nome migliore, lo affino.

**Gli antibody di wa-mirror nascono senza un loop di retroazione sul proprio contesto.** Ogni cicatrice
ha prodotto una contromisura reattiva — un watchdog, un retry-guard, una 2ª istanza, una guard-substring,
un hotfix-HOME — che soffre di **uno dei due difetti gemelli**:

- **(A) Non sa SPEGNERSI quando il sintomo che cura è benigno o assente.** L'anticorpo resta acceso a
  vuoto. → deaf-session che scatta di notte; KeepAlive (W67) che killava i bridge sani; orphan Mini
  (W67c) che girava "per ridondanza" senza sapere di non dover girare.
- **(B) Non viene mai PROMOSSO da riflesso-locale a struttura dichiarativa.** L'hotfix resta orfano.
  → HOME-fork (813 righe mai committate); guard-substring W68/W72/W73 (riflessi `term in value` mai
  ri-architettati in un detector semantico finché un 8-agent loop non ne trovò 5 in una volta).

Il difetto NON è "manca il source-of-truth" — l'organismo **ha** un roster (`WA_MIRROR_SUPERVISED_NAMES`),
**ha** un DB, **ha** git. Il difetto è che **l'organismo cataloga il trauma in una cicatrice ma non chiude
il loop**: la cura puntuale non diventa mai una regola che (a) conosce il proprio contesto di attivazione
e (b) vive nel piano dichiarativo invece che nel riflesso locale.

**3 evidenze trasversali (verificate):**
1. **deaf-session** (acceso a vuoto): 50 reconnect/notte, tutti 02:24–03:24 WITA, perché il watchdog
   non sa distinguere "socket sordo (bug)" da "notte (silenzio sano)". Antibody senza spegnimento.
2. **HOME-fork** (hotfix non promosso): 813 righe HOME-only. Lavoro vivo che il repo ignora.
3. **roster anemico**: `WA_MIRROR_SUPERVISED_NAMES` ha solo i NOMI; lo stato "attivo" è **dedotto**
   dalla presenza di una directory sessione (`start-all.sh` riga 3), e "standby/decommissioned" non
   esiste come campo → il bridge non *sa* che damar è standby o che Ari/Vino sono dismessi.

### Contromisura strutturale (1, scalata al perimetro reale)

NON "costruire un Control Plane da zero" (Gemini sopravvalutava la portata) e NON "symlink read-only
repo→HOME" (DeepSeek ha dimostrato che è pericoloso e contraddice W68/W72/W73). La cura giusta è
**dare ai due antibody-tipo il loop che gli manca, riusando ciò che già esiste**:

- **Per (A) — spegnimento contestuale:** il deaf-session watchdog deve conoscere il proprio contesto.
  Minimo: elevare `DEAF_SESSION_TIMEOUT_MS` (o disarmare il forced-reconnect) nella finestra 01–06 WITA,
  o meglio gate-arlo su "0 messaggi MA c'erano messaggi nelle ultime N ore" (silenzio anomalo) vs
  "0 messaggi di notte" (silenzio atteso). Stesso principio applicabile a ogni futuro antibody:
  **un watchdog senza condizione-di-spegnimento è un W67 in attesa.**
- **Per (B) — promozione a struttura:** (1) estendere il roster esistente con `expected_status`
  (`ACTIVE | STANDBY | DECOMMISSIONED`) + `assigned_node` — il supervisor, su QUALSIASI macchina,
  fa graceful-exit se `status≠ACTIVE` o `node≠hostname` (sterilizza l'orphan Mini per sempre +
  ammutolisce damar standby + Ari/Vino). (2) un **hook/CI che fallisce se `~/.openclaw/bin/*bridge*.py`
  diverge dal repo oltre soglia** (l'inverso del symlink: NON impedire il fix-HOME-prima, ma rendere
  *rumoroso e visibile* il drift non-promosso, così l'hotfix urgente resta lecito ma il debito è tracciato).

## §Terapia eseguita (in-perimetro, questa sessione)

- ✅ **Cicatrice W77** appesa a `cicatrix-scars.md` (chiude il loop che il meta-pattern denuncia:
  catalogare il trauma è il primo passo della promozione-a-struttura).
- ✅ **Questo report** + `mem save` discovery (importance 8).
- ✅ Verificato che il backlog intake (1934/orphan-lease) è **stale** → memoria aggiornata.

## §Solo-operatore (azione fisica o decisione di Zero)

1. **Mini offline ~2gg** — riaccendere e, al ritorno, **verificare che il `launchctl disable` W67c sia
   persistito** (`launchctl print gui/$UID/com.balizero.wa-mirror` → deve essere disabled/assente).
   Se non persistito → l'orphan active-active si riarma e lo spam Telegram reconnect ricomincia.
2. **Ari / Vino** (`+628213454721` / `+628213454727`) — sessioni orfane vuote, fuori roster.
   Decisione: rimuovere le dir sessione + confermare il decommission, o re-linkare se rientrano.
3. **HOME-fork → repo** — portare le 813 righe HOME-only nel repo via PR **sul Pro** (è lavoro di
   sessione sibling + file di produzione; non propagabile a freddo da M5). `diff` salvato in
   `/tmp/bridge-drift.diff` sul Pro.
4. **deaf-session fix (notturno)** — tocca `bridge/session.ts` + `npm run build` + restart dei 6 bridge
   live di 6 dipendenti reali: sopra la soglia "cura-a-distanza autonoma". Sessione dedicata sul Pro.
