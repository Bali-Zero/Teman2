---
date: 2026-06-14
domain: operations
client_case: false
organ: intake-pipeline (digestive apparatus)
session: Opus Mythos M4 (M5)
sources:
  - Postgres nuzantara_dev (Pro, read-only via 192.168.0.20)
  - apps/backend-rag/backend/services/intake/{worker,stages,validate_rules,preprocess,classify}.py
  - scripts/wa_mirror_{session_janitor,intake_sweeper}.py
  - empirical OCR measurement (qwen2.5vl:7b / qwen3-vl:8b, synthetic non-PII docs)
  - Gemini 3.5 Flash High (meta-pattern synthesis, meta-data only)
  - DeepSeek V4 Pro (adversarial refuter, meta-data only)
  - memories fix_wa_intake_p1_p3_done_p2_ocr_diagnosed_2026_06_09, decision_intake_catalog_v2_rollout, decision_smistamento_drive_crm, fix_intake_review_ui_shipped
verdict_method: 4-LLM asymmetric panel (subagent fan-out → Gemini synthesis → DeepSeek refute → Opus gate ×2)
---

# Mythos M4 — TAC dell'apparato digerente (pipeline intake documenti)

## §0 — Executive

**Tesi di partenza:** "l'apparato mastica ma non digerisce" — worker che abbandonano job,
OCR che fallisce 1 pagina su 3, backlog che cresce inutile.

**Verdetto:** la tesi è **superata dai fatti**. Il malato-primario delle memorie (lease-orphan,
backlog 1934 stuck) è **strutturalmente curato** (PR #1299). La coda è SANA: 1694 done, 0
processing, 0 lease orfani. L'OCR **non fallisce** sul modello (misurato: 0/5 empty su doc pulito
E degradato). Il backlog è **drenato**.

Ma sotto la salute apparente c'è il vero reperto — un **meta-pattern di 2° ordine** (§Meta-pattern):
l'organismo **degrada in silenzio e non rende osservabile la divergenza tra ciò che la config
dichiara e ciò che la realtà fisica è**. Non "mastica ma non digerisce" — piuttosto *"digerisce
bene, ma se smettesse di farlo non te ne accorgeresti"*.

**Cosa è stato curato in questa sessione** (PR su `agent/air-m5/cell/mythos-m4-intake`):
1. **Antibody dead-bridge alarm** — chiude il buco "intake cieco indistinguibile da linea quieta".
2. **opencv-python-headless** in requirements — mantiene una promessa che il codice già si faceva.

**Cosa NON è stato fatto (confine operatore, §Solo-operatore):** armare il watcher Drive (backfill
ancora in corso), flippare `INTAKE_WRITER_ENABLED`, rimuovere `INTAKE_CONCURRENCY=3` dal plist HOME
del Pro, re-link QR di bridge loggati-out.

---

## §1 — Organo A: Worker / lease (la peristalsi) — FIXED

Memoria 2026-06-09: il worker abbandonava job in `processing`, lease_owner vuoto, 40 stuck, nessun
reclaim → backlog mai drenato. **Era il malato-primario.**

**Verificato ORA (disco + PG, 2 round):** strutturalmente curato da **PR #1299** (`b24c64ce3`,
"flow v2 — lease-only worker"). sha256 deploy worker.py == main (`d4d727ee…`).
- **Claim** (`worker.py:560-599`): l'`UPDATE` scrive SOLO `lease_owner`+`lease_expires_at`. Lo
  `status` resta il cursore-di-stage, mai toccato dal claim. `FOR UPDATE SKIP LOCKED`.
- **Reclaim intrinseco** (`worker.py:578`): il predicato del claim include
  `(lease_owner IS NULL OR lease_expires_at < now())` → un lease scaduto è auto-ri-claimabile allo
  stesso stage. TTL 900s + heartbeat 120s → finestra orfano ≤15min, zero janitor necessario.
- **Live:** 0 processing, 0 righe con lease, 1694 done. Boot-remap (`remap_legacy_statuses`) ha
  ritirato gli status legacy v1.

**Caveat (non bug di correttezza):** `INTAKE_CONCURRENCY=3` nel plist HOME del Pro è **config morta**
— zero consumer nel backend (grep verificato da me), `flock` single-instance → drena **serialmente,
1 job alla volta**. Il `3` mente sul parallelismo. → §Solo-operatore.

---

## §2 — Organo B: OCR (gli enzimi) — il "fallimento" era LATENZA, non rottura

Memorie: primario qwen3-vl:8b "fallisce con errore vuoto" → cascata a qwen2.5vl:7b (~170s/job);
empty-page ~30%; cv2 mancante.

**Misurato empiricamente (Law 2: doc sintetici non-PII, OCR locale sul Pro):**
- Doc **pulito**, 5×: qwen2.5vl:7b → **0/5 empty, 0 errori** (~5s/call). qwen3-vl:8b → **0/5 empty,
  0 errori** (~25-46s/call). → "qwen3-vl fails" **FALSIFICATO** su input pulito.
- Il vero motivo per cui qwen2.5vl è primario: **latenza 5×**, non un guasto. Il deploy
  MODEL_TOPOLOGY ha già `ocr_vision=qwen2.5vl:7b` (= il "v2.2-ocrfix" runtime, non un commit git).
- Doc **degradato** (skew 7°, contrasto -45%, blur 1.2px — peggio di una foto WA media):
  qwen2.5vl RAW (senza cv2) → **score 5/5 token chiave**. Il VLM moderno fa internamente ciò che
  cv2 deskew+threshold faceva per Tesseract.

**Conclusione OCR:** l'empty-page ~30% reale è **(B) scansioni genuinamente illeggibili/vuote**
(retro bianchi, foto fuori fuoco oltre il recuperabile) — un problema di *input upstream*, non
dell'enzima. **cv2 è quasi-cosmetico** per l'intake (nessun path Tesseract nell'intake — verificato;
solo in `core/parsers.py` e crm_guardian, fuori dal path intake). Lo installo come **hedge
low-effort** che mantiene la promessa del docstring (`preprocess.py:18` dichiara verbatim
"opencv-python-headless *already in the venv*" — promessa rotta, ora mantenuta), **non** come fix
load-bearing.

---

## §3 — Organo D: Backfill (il bolo arretrato) — RUNNING, non finito

- **Dropbox→Drive copy-only backfill (527 GiB):** rclone **PID 2781 vivo** (verificato 2 volte),
  ~47% di un denominatore ancora in crescita (`--fast-list` sta ancora scoprendo il corpus), retry
  pass dopo 22k errori transienti (Google rate-limit sotto bwlimit 4M). L'ETA "oggi" era ottimista.
- **Dead job (1):** id 2127, `intake-v1` legacy, morto in `validate` su
  `RuntimeError('QDRANT_URL/API_KEY not set; cannot validate KBLI')`. Lo stage validate **è ancora
  vivo in v2** (`stages.py:67`), ma i 1694 done v2 non muoiono lì → QDRANT *è* settato in prod; è un
  tombstone legacy, non un incendio attivo.
- **6 review_pending:** fixtures `test-5b` (source=drive, doc_type=npwp), attempts=0, mai actionate
  da adit. Rumore di test, non stuck.

---

## §4 — Organo E: Watcher Drive (una nuova bocca) — NON armare (confine operatore)

- Watcher `com.balizero.drive-intake-drain` **non armato** (plist assente — corretto by-design).
- Fail-safe verificati nel codice: `drive_adapter.py:153-159` rifiuta senza
  `INTAKE_DRIVE_SCOPE_FOLDER_ID`; il cursor si semina a "now" (`get_start_page_token`) → arma SOLO i
  file NUOVI da arm-time. **Ma durante il backfill, ogni file copiato È un nuovo change Drive** → il
  fail-safe NON protegge: armare ora = flood storico (~170s/job = mesi).
- **Scope folder id risolto:** `1LjJjBdJZ115Iyu_Bthl-PVC2XKlXRDrF` (`Dropbox-Intake/`).
- **Verdetto: WAIT.** Armare quando: `ps aux | grep '[r]clone copy dropbox-bayu'` vuoto + un tick
  delta-only `copied=0` + `dropbox_intake.last.json status:ok`. → §Solo-operatore.

---

## §Meta-pattern — la malattia-delle-malattie (il vero topic)

**Convinzione difettosa che genera l'intera famiglia:**

> *L'organismo degrada in silenzio e tratta la divergenza tra config-dichiarata e realtà-fisica come
> non-osservabile. Ogni organo "mente per omissione": fa una promessa (config, docstring, status DB)
> che la realtà contraddice, senza renderlo visibile all'operatore — che vive in un modello mentale
> falso dello stato vero della pipeline.*

**3 evidenze trasversali (organi diversi, stessa cecità):**
1. **Worker:** `INTAKE_CONCURRENCY=3` promette parallelismo 3× che il `flock` rende seriale (1×). La
   config mente, in silenzio.
2. **OCR:** `preprocess.py:18` dichiara "opencv-python-headless *already in the venv*" — ma manca. Il
   codice asserisce come fatto qualcosa di falso; il fallback graceful inghiotte la discrepanza con
   un `logger.warning` che nessuno legge.
3. **Mouth:** un bridge WhatsApp morto e una linea quieta producono il **sintomo identico** ("no new
   media"). La pipeline non ha modo di distinguere "non arriva cibo" da "la bocca è paralizzata".

**Raffinamento dal panel (asimmetrico, non consenso):** Gemini ha proposto come meta-pattern
"silent degradation" + cura "halt at boot / ban graceful continuation". **DeepSeek (refuter) l'ha
demolito**, e io ho confermato a gate-2: (a) la "silent degradation" del cv2 NON è la malattia — è
un fallback *corretto* (5/5 raw misurato); lumarlo cogli altri è *category inflation*; (b) la cura
"halt at boot" **viola Law 6** (sovranità locale: la disconnessione è stato naturale, non guasto) —
un boot-assert sull'upstream trasformerebbe ogni blip di rete in un kill totale del nodo.

**Contromisura strutturale corretta (NON "halt"):** *rendere ESPLICITE e MONITORABILI le divergenze
config↔realtà, senza sacrificare il degraded-mode quando è sicuro.* Concretamente:
- divergenza config↔codice (concurrency) → o si cabla o si rimuove l'env che mente;
- dipendenza opzionale mancante (cv2) → fallback graceful + dichiararlo nei requirements;
- canale esterno morto (bridge) → **runtime probe + alarm osservabile**, MAI boot-halt.

---

## §Terapia eseguita (cura-mentre-diagnostico — verificata live)

**PR `agent/air-m5/cell/mythos-m4-intake` (commit 92bf5f536):**

1. **`scripts/wa_mirror_bridge_liveness_alarm.py`** (NUOVO, 265 righe) — l'antibody mouth.
   Runtime probe Law-6-safe (NON boot-assert): allerta l'operatore via Telegram SOLO quando un
   bridge che il DB crede `connected` ha il processo morto **AND** stale oltre 20min di grace
   **AND** è orario di lavoro WITA (8-20). Cooldown 120min/account anti-spam. Riusa il pattern
   PID-liveness di `wa_mirror_session_janitor.py` + il pattern Telegram di `drive_token_watchdog.py`.
   **Verificato live sul Pro:** gira contro il DB reale (1 bridge `sahira` connected+vivo → 0 falsi
   positivi); logica testata ramo-per-ramo (business-hours True@11h/False@3h, liveness su processo
   inesistente=False, config corretta). Chiude esattamente il buco "intake cieco = linea quieta".
   → **Da installare** come LaunchAgent (StartInterval 300, parità sweeper) — §Solo-operatore.

2. **`opencv-python-headless>=4.10.0`** in `apps/backend-rag/requirements.txt` — mantiene la
   promessa di `preprocess.py:18`. Hedge low-effort; entra nel deploy venv al prossimo build.

**NON curato di proposito (declassato dal panel):**
- cv2 come fix dell'empty-page → l'A/B prova che NON muove l'ago (5/5 raw). Cosmetico.
- preflight env-var hard-fail QDRANT → DeepSeek lo indicava #1, ma il gate-2 mostra che in prod
  QDRANT *è* settato (1694 done v2) → guardia difensiva, non emergenza. Lasciato come nota.

---

## §Solo-operatore (il confine — azione fisica / decisione Zero)

1. **Armare il watcher Drive** — solo quando il backfill 527GiB è finito (oggi NO, rclone PID 2781
   vivo). Comando, sul Pro: `cd ~/Desktop/nuzantara && bash infra/launchagents/install_drive_intake.sh 1LjJjBdJZ115Iyu_Bthl-PVC2XKlXRDrF` + fire-test E2E (drop doc → kita/review). Re-check giornaliero.
2. **Installare l'antibody dead-bridge** come LaunchAgent sul Pro (StartInterval 300) +
   `TELEGRAM_BOT_TOKEN` nell'env del plist. La PR porta lo script; l'install è runtime Pro.
3. **`INTAKE_CONCURRENCY=3`** nel plist HOME del Pro (`~/Library/LaunchAgents/com.nuzantara.intake-worker.plist`)
   — config che mente. Decisione: o cablare un vero pool (rischio: parallelismo non testato), o
   **rimuovere l'env** (più sicuro: allinea promessa a realtà seriale). Non in repo, è drift Pro-only.
4. **`INTAKE_WRITER_ENABLED`** resta OFF (dry-run) finché Adit valida il review flow — decisione Zero.
5. **Re-link QR** bridge loggati-out (sahira è tornato connected; vino/ari deferred) — azione fisica.

---

> Metodo: subagent fan-out (4, 1 morto su session-limit→rifatto) → gate-Opus round 1 → Gemini 3.5
> Flash High synthesis (meta-data only) → DeepSeek V4 Pro refuter (meta-data only) → gate-Opus round
> 2 → cura verificata live. Zero contenuto-documento è uscito dal Pro (Law 2). OCR misurato in locale.
