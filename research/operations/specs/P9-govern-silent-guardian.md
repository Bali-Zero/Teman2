# PEZZO 9 — GOVERN: il guardiano silenzioso (governance per un team di uno)

> **Spec studio (non implementazione).** Ciclo calibrato: reuse-first (disk-state VERIFICATO) +
> council 2-LLM (Gemini red-team / DeepSeek logic). Pezzo 9 di 9 — l'ultimo. Chiude i 9 pezzi.
>
> **Principio-cardine (DeepSeek)**: per un solo-dev, la governance NON può essere "osservazione
> passiva" (più dashboard da guardare). Deve essere un **guardiano silenzioso che interrompe SOLO per
> chiedere una scelta** — zero-attenzione finché tutto va bene, degrada-invece-di-fermarsi, e si
> auto-testa per non decadere come tutto il resto.

---

## 0. La correzione che precede tutto — l'osservatore è il collo di bottiglia, non gli strumenti

Il design iniziale ("aggiungiamo single-pane observability + cost-budget + check") è stato demolito dal
red-team con il colpo più profondo dei 9 pezzi (Gemini #6 FATALE, #5 CRITICA):

> **"Costruire strumenti di osservazione per un osservatore che non ha il tempo materiale di guardare è
> un errore di categoria."** Nessun pannello risolve il fatto che UN umano non può supervisionare un
> loop che gira H24 su 3 nodi. Il design tenta di tenere l'umano in un loop da cui è già stato espulso
> per limiti biologici. E curare un eccesso di strumentazione-ignorata aggiungendo altra strumentazione
> = **"assumere un manager per controllare un manager in un'azienda di 1 persona"** (regressione infinita
> del governance-layer).

**La prova è già sul disco**: il `chronic_failure_digest` invia un Telegram settimanale che (per
ammissione del reuse-first) **nessuno legge**. Aggiungere una dashboard Grafana = "accendere un monitor
4K in una stanza vuota". Il problema non è la *visualizzazione*, è l'*attenzione* (una costante finita
mentre il loop scala).

**Risoluzione (DeepSeek) — il capovolgimento**: la governance per un solo-dev deve funzionare **per
eccezione (push-on-anomaly)**:

> L'operatore non guarda **nulla** finché tutto è entro i limiti. Il sistema invia **un unico segnale**
> SOLO quando una soglia impone una **decisione irreversibile**. E l'alert chiede **la decisione, non
> la diagnosi**: *"Budget proxy al 90%. Degradare a Gemini? [Y/n]"* — non *"ecco 12 grafici, capisci tu
> cosa succede"*. In regime normale, l'attenzione consumata è **zero**.

Questo è il principio che governa tutto il pezzo. Tutto il resto ne discende.

---

## 1. GROUND — reuse-first disk-state VERIFICATO questo turn

DIAGNOSI CENTRALE: **la strumentazione esiste tutta ed è robusta, ma è disaccoppiata dalla governance.**
"Governato alla cieca ma con sensori." (numeri `wc -l`-verificati; l'Explore sottostimava — la
strumentazione è ancora più solida di quanto riportato).

### 1.1 Strumentazione GIÀ-PRONTA (verificata)

| Mattone | Stato | Evidenza verificata |
|---|---|---|
| Cost ledger | **GIÀ-PRONTO + CI-GATE ATTIVO** | `llm_cost_recorder.py` (**364 righe**) triple-write (Prometheus + Postgres `llm_cost_events` + JSONL indistruttibile). 14 file usano `record_llm_call`. **CI gate ATTIVO** (`.github/workflows/tests.yml` → `check_llm_cost_tracking.py`): nessun paid-call shippa senza tracking. Protezione strutturale reale. |
| Observability | **GIÀ-PRONTO ma OPZIONALE** | `core/observability.py` (**266 righe**) Langfuse+OTEL, auto-instrumenta Gemini/DeepSeek/Anthropic. No-op se manca la key → prod senza key = zero trace. |
| Circuit-breaker | **GIÀ-PRONTO ma SOLO NLM** | `circuit_breaker.py` (**544 righe**) FSM 3-breaker, ma solo per NLM deep-research (CB_NLM/SOURCE/INTEGRATION). |
| Organ registry | **GIÀ-PRONTO** | `organs_registry.yaml` (**4930 righe**), enabled/dipendenze/recovery, validato in pre-commit. |
| Chronic-failure digest | **ESISTE-MA-NON-CONSULTATO** | `chronic_failure_digest.py` (**369 righe**), Telegram settimanale. Gira, ma "nessuno lo legge". |

### 1.2 I 4 BUCHI VERIFICATI (governance cieca)

1. **Trace non visti**: Langfuse/OTEL raccolgono → cloud non consultato. Zero dashboard. + opzionale
   (dimenticabile).
2. **Cost tracciato ma NON limitato** (il più pericoloso): token contati, MA **ZERO cost-breaker** su
   Claude-OAuth / Gemini / DeepSeek (verificato: grep cost-breaker su `federation_orchestrator.py` +
   `llm/` = vuoto). Un agente autonomo può spendere illimitato. `cost_advisor` esiste ma **non
   invocato** da nessun cron.
3. **Registro ≠ realtà**: `organs_registry.yaml` ha 5+ `enabled`, ma `launchctl list` su M5 mostra **1**
   cron. Divergenza (famiglia W50/W59).
4. **Law 7 non enforced**: "numeri prima" è cultura, zero lint/CI che impone before/after.

---

## 2. I 6 DIFETTI DEL RED-TEAM → risoluzione (DeepSeek)

| # | Difetto (Gemini) | Sev | Risoluzione (DeepSeek) |
|---|---|---|---|
| 1 | breaker su Claude-OAuth = placebo (quota-MAX opaca, non misurabile) | **CRITICA** | §3.2: breaker su **PROXY misurabile** (token locali nella finestra) + **DEGRADO GRACEFUL** (non stop → cascata al tier successivo). Non serve misurare la quota esatta: si degrada *prima*, conservativamente. |
| 2 | dashboard-theater (monitor-4K in stanza vuota; problema è attenzione non visualizzazione) | ALTA | §0 + §3.1: NIENTE dashboard nuova. Governance **push-on-anomaly**: zero da guardare, un segnale solo per decisione. |
| 3 | allucinazione single-node del registro (M5 thin-client, divergenza attesa) | ALTA | §3.3: registro **PER-NODO** (organo dichiara nodo-target), riconciliazione **locale** (verifica solo gli organi assegnati a quel nodo). La divergenza attesa non è più falso-positivo. |
| 4 | teatro delle metriche Law 7 (campo before/after → fuffa) | MEDIA | §5 residuo onesto (identico a P5/P4): il campo è pavimento sintattico, non garanzia semantica. Mitigazione: collegarlo ai numeri OGGETTIVI già nel cost-ledger dove possibile (es. token before/after sono misurati, non scritti a mano). Per il resto resta consultivo. |
| 5 | regressione infinita governance (chi governa il governance? decade come il preflight) | **CRITICA** | §3.4: governance **MINIMALE + AUTO-TESTANTE**. UN watchdog + **dead-man's switch** ("governance muta" se manca il segnale-vivo). Meno componenti = meno decadimento; si accorge da solo di essersi spento. |
| 6 | collo di bottiglia umano (strumenti per chi non ha tempo = errore di categoria) | **FATALE** | §0: il capovolgimento. Governance = guardiano silenzioso che interrompe solo per una SCELTA, non osservazione passiva. Zero-attenzione default. |

**Convergenza**: i 3 colpi più gravi (#6 FATALE, #1 #5 CRITICA) sono sciolti dallo stesso principio —
**meno, non più**: meno attenzione richiesta (push-on-anomaly), meno componenti (un watchdog
auto-testante), e degradare invece di stoppare-rigido.

---

## 3. DESIGN — il guardiano silenzioso (4 proprietà)

### 3.1 Zero-attenzione fino all'anomalia (difetti #2, #6)

- **Nessuna dashboard da consultare proattivamente.** La governance non è qualcosa che l'operatore
  *guarda*; è qualcosa che lo *interrompe* solo quando serve.
- **Un solo canale push** (il Telegram a Zero, già esistente — Symbiosis Law 5).
- L'interruzione arriva **solo per una decisione irreversibile** che esula dall'autonomia predefinita, e
  chiede **la scelta, non la diagnosi**: `"Budget proxy Claude al 90% nella finestra 5h. [D]egrada a
  Gemini / [P]ausa / [C]ontinua?"`. L'operatore risponde con 1 tasto, non apre 12 grafici.
- Tutto ciò che oggi è "dashboard da guardare" (cost, liveness, chronic) resta come *dato accumulato*
  (per audit a-posteriori), ma **non** richiede attenzione attiva in regime normale.

### 3.2 Breaker su PROXY + degrado graceful (difetto #1 CRITICA)

Il limite Claude-OAuth quota-MAX è opaco (non sai i token residui). Quindi:
- Il breaker NON misura la quota reale (impossibile). Misura un **proxy**: i token *che TU hai speso*
  nella finestra rolling (conteggio locale, dal cost-ledger già esistente).
- Soglia **conservativa** (es. 80-90% di una stima prudente della quota).
- Al superamento, **NON ferma → CASCATA** al tier successivo (Gemini → Codex → Ollama-locale). **Il
  cascade-fallback ESISTE GIÀ** (`regulatory-watcher-run.sh` è la reference impl, citata nel CLAUDE.md).
  Il breaker non è un nuovo "stop", è il *trigger automatico* del cascade già scritto.
- **Stop completo solo se tutti i tier sono esauriti** → allora (e solo allora) push-decision all'umano.

Questo trasforma il "breaker-placebo" (non puoi misurare la quota) in "degradazione automatica" (non
*serve* misurare la quota — degradi prima, e se sbagli la soglia, degradi un po' presto = un fastidio,
non un crash sul rate-limit invisibile).

### 3.3 Registro PER-NODO (difetto #3 ALTA)

- `organs_registry.yaml` evolve: ogni organo dichiara il **nodo-target** (`node: pro` / `node: mini` /
  `node: pro,mini`). M5 = thin-client → quasi nessun organo assegnato.
- La riconciliazione è **locale e per-nodo**: su ogni macchina, un check confronta `launchctl list` con
  *solo gli organi assegnati a QUEL nodo*. Su M5 verifica gli (pochi) organi M5, non quelli di Pro.
- La divergenza attesa (M5 non ha i cron pesanti) non è più un falso-positivo — è *correttezza*. Solo un
  organo *assegnato-a-questo-nodo-ma-non-caricato* fa rumore.

### 3.4 Governance MINIMALE + auto-testante (difetto #5 CRITICA)

La causa-radice della "governance che decade" (il preflight di P5 morto, il chronic-digest non letto):
gli strumenti di governance sono soggetti allo **stesso decadimento** che dovrebbero prevenire.

- **UN solo watchdog locale** racchiude le verifiche (budget-proxy, liveness-per-nodo, registro). Non 5
  meccanismi separati che decadono indipendentemente.
- **Dead-man's switch**: il watchdog emette periodicamente un segnale "vivo". Se il segnale **manca** per
  un intervallo critico → un secondo meccanismo minimale (o l'assenza-stessa rilevata da Zero) genera
  l'allarme **"governance muta"**. È il `preflight-self-test` di P5 generalizzato: la governance "fa
  rumore quando muore".
- **Meno componenti = meno superficie di decadimento.** La governance giusta per un solo-dev è 1
  guardiano auto-testante, NON 5 dashboard.

---

## 4. GATE FALSIFICABILI (Symbiosis Law 7)

- **G1 — zero-attenzione default** (binario): in regime normale (tutto entro i limiti), il numero di
  segnali push all'operatore = **0**. Falsificabile: se la governance manda notifiche di routine "tutto
  ok", ha fallito il principio (è rumore).
- **G2 — degrado non stop** (binario): un agente che supera il budget-proxy DEVE cascatare al tier
  successivo automaticamente, NON fermarsi né spendere cieco. Falsificabile: superare la soglia → il
  prossimo call va a Gemini, non a Claude né errore.
- **G3 — alert = decisione non diagnosi** (binario): quando la governance interrompe, il messaggio
  contiene una **scelta** (opzioni [Y/n] / [D/P/C]), non un dump di metriche. Falsificabile: un alert
  senza opzioni-d'azione è un alert mal-formato.
- **G4 — registro per-nodo** (binario): la riconciliazione su M5 NON flagga gli organi assegnati a
  Pro/Mini. Falsificabile: zero falsi-positivi su un nodo per organi non-suoi.
- **G5 — governance fa rumore quando muore** (binario, il più importante): se il watchdog si ferma, il
  dead-man's switch genera "governance muta" entro l'intervallo critico. Falsificabile: uccidere il
  watchdog → arriva l'allarme-assenza. *(Questo è il gate che il preflight di P5 non aveva.)*
- **G6 — cost-breaker copre tutti i provider** (numerico): # provider con budget-breaker / # provider
  paganti-o-quota. Oggi 1/N (solo NLM). Target: ogni provider (Claude-OAuth, Gemini, DeepSeek) ha il suo
  proxy-breaker.

---

## 5. RESIDUI ONESTI

1. **Soglia del proxy è una stima (Gemini #1 residuo)**: non misurando la quota-MAX reale, la soglia
   conservativa può degradare un po' presto (fastidio) o tardi (raro crash sul rate-limit). Il degrado
   graceful rende il costo dell'errore *basso* (cascata, non crash), ma la soglia resta una stima, non
   una misura. Onestà: è "abbastanza buono", non preciso.
2. **Law 7 semantica non-lintabile (Gemini #4, identico a P4/P5)**: il campo before/after misura la
   forma. Dove i numeri sono nel cost-ledger (token, latency) si può ancorare a dati oggettivi; per le
   metriche di qualità resta consultivo. Pavimento, non garanzia.
3. **Il dead-man's switch ha bisogno di un secondo punto** (chi rileva l'assenza del watchdog?): se è un
   altro processo locale, anch'esso può morire (regressione di 2° livello, ma molto più stretta). Per un
   solo-dev, il backstop ultimo è Zero che nota l'assenza del segnale-vivo atteso. Non azzera la
   regressione, la rende *finita e stretta* (1 watchdog + 1 segnale-vivo atteso, non 5 sistemi).
4. **L'attenzione umana resta finita (Gemini #6 residuo)**: push-on-anomaly *minimizza* il consumo di
   attenzione, ma se le anomalie sono frequenti, l'operatore è di nuovo sommerso. La governance funziona
   solo se il loop è per lo più sano (poche anomalie). Se il loop è caotico, nessuna governance lo salva
   — va sistemato il loop, non la governance. Onestà: la governance gestisce le eccezioni, non sostituisce
   un sistema rotto.

---

## 6. DECISIONE (kill gate)

**GO sul guardiano silenzioso** (push-on-anomaly + breaker-su-proxy-con-degrado + registro-per-nodo +
watchdog-auto-testante). Riusa il cost-ledger, il cascade-fallback, l'organs_registry, il canale Telegram
— tutto esistente. NON aggiunge dashboard (il difetto FATALE). Aggiunge il *layer di decisione*, non di
osservazione.

**Priorità (per leva)**: (1) cost-breaker-su-proxy che triggera il cascade già esistente [il buco più
pericoloso: spesa cieca]; (2) registro-per-nodo [elimina i falsi-positivi che ucciderebbero la fiducia];
(3) watchdog unico auto-testante + dead-man's switch [contro il decadimento]; (4) push-on-anomaly come
unico canale [zero-attenzione].

**Metrica primaria falsificabile**: G1 (zero segnali in regime normale) + G5 (governance fa rumore quando
muore). Se la governance manda notifiche di routine, è rumore (fallito #6). Se può morire in silenzio
come il preflight, è teatro (fallito #5).

**Connessione cross-pezzo dichiarata**: G5 è il `preflight-self-test` di P5; il degrado-graceful è la
revocabilità di P6; il watchdog-minimale eredita "enforcement non abstraction" di P7; il push-decision-
non-diagnosi è il human-gate di P1/P7. Questo pezzo è la *governance dell'intero loop dei 9*.

---

## 7. Provenienza

- **Reuse-first**: Explore disk-state (numeri ri-verificati `wc -l`, l'Explore sottostimava). cost-ledger
  364 + CI-gate attivo, observability 266, circuit_breaker 544 (solo NLM), organs_registry 4930,
  chronic_digest 369. Cost-breaker su Claude/Gemini confermato ASSENTE. organs_registry 5+ vs launchctl-M5
  1 (divergenza verificata). Memory importance-9.
- **Council 2-LLM asimmetrico** (calibrato):
  - Red-team: **Gemini 3.1 Pro** — 6 difetti, 2 CRITICA + 1 FATALE (collo-di-bottiglia-umano,
    regressione-infinita, breaker-placebo). Premiato per distruggere.
  - Logic: **DeepSeek V4 Pro** (`reasoning_effort=high`) — il capovolgimento push-on-anomaly,
    breaker-su-proxy-con-degrado, registro-per-nodo, watchdog-auto-testante. Il principio "guardiano
    silenzioso" è suo.
- **Famiglia**: TUTTI i pezzi (è la governance del loop intero). P5 (gate-che-fa-rumore = G5 dead-man's
  switch). P6 (degrado-graceful = revocabilità). P7 (enforcement-minimale + human-gate). P1 (push-
  decision = human-gate). Cascade-fallback CLAUDE.md (il breaker lo triggera). Symbiosis Law 5 (Zero
  ultima istanza = il destinatario del push) + Law 7 (numeri).

> **Onestà finale**: la governance NON rende il loop "sorvegliato" — un solo umano non può sorvegliare
> H24 su 3 nodi, ed è giusto così (è stato espulso dal loop per limiti biologici, dice il red-team).
> Diventa **"un guardiano silenzioso che lascia l'operatore in pace finché non c'è una scelta da fare,
> e quando c'è gli porta la scelta — non il problema"**. Il salto non è "vedere di più" — è **vedere
> NIENTE finché non serve, e quando serve ricevere una decisione-da-prendere in 1 tasto, non una
> diagnosi-da-fare in 12 grafici**. E il guardiano stesso fa rumore quando muore, così non diventa il
> prossimo preflight-morto. Questa è l'unica governance che scala per un team di uno.
