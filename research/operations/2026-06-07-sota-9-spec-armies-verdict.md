---
date: 2026-06-07
domain: operations
client_case: internal — meta dev-loop SOTA, verdetto finale a eserciti sui 9 pezzi
sources: 9 spec (research/operations/specs/P1-P9) + report madre (2026-06-06-sota-agentic-dev-workflow.md) + Workflow 17-agenti (7 coerenza + 9 logica + 1 sintesi-potenza, Gemini/DeepSeek/Explore eterogenei) + ri-verifica disk-state diretta
---

# Verdetto finale — i 9 pezzi del workflow agentico, controllati a eserciti

> **Cos'è questo documento.** Chiude il ciclo richiesto da Antonello: studiare il workflow agentico
> più avanzato, scomporlo nei 9 pezzi mancanti, e per ognuno fare deep-research + panel 4-LLM +
> reuse-first → spec. «Alla fine, con gli agenti ad eserciti, controllate logica e coerenza e potenza».
> Questo è quel controllo finale, + il giudizio onesto sull'insieme.
>
> **Metodo del finale**: un Workflow di **17 agenti** (modelli eterogenei) in 3 fasi —
> 7 verificatori di **coerenza cross-pezzo**, 9 avversari di **logica per-pezzo**, 1 **sintesi-potenza**.
> Poi ho ri-verificato io stesso sul disco i finding load-bearing (anti-allucinazione bidirezionale).

---

## 0. La cosa più importante che è successa — gli eserciti hanno dimostrato la tesi che dovevano giudicare

Il cuore dei 9 pezzi è **una sola tesi**: *il verificatore è strutturalmente imperfetto, quindi tutto va
reso osservabile, reversibile e gated sull'umano-solo-per-l'irreversibile* (è il Pezzo 1, e si propaga
negli altri 8).

Nel finale, **i 2 eserciti l'hanno auto-dimostrata**: cacciando allucinazioni nelle spec, **hanno
allucinato loro stessi** 3 file dichiarati "inesistenti" che invece esistono — avevano grepato i path
sbagliati:
- `regulatory-watcher-run.sh` → esiste in `~/scripts/` (l'esercito cercava nel repo).
- il log deep-research di P3 (`wxvwc1vrw.output`) → esiste in `/private/tmp/claude-501/...` (cercava in `/tmp`).
- (confermato invece reale: il cost-breaker *programmatico* in `federation/llm` è davvero assente).

La sintesi-potenza li ha ri-verificati e smontati. **Questo non è un aneddoto: è la prova vivente che
"verificatore imperfetto" vale anche per i verificatori del verificatore — esattamente perché P1/P7/P9
chiedono umano-come-ultima-istanza e gate auto-testanti.** Il finale ha validato il sistema esibendone
il fallimento che il sistema è progettato per gestire.

---

## 1. Verdetti di COERENZA cross-pezzo (7 dipendenze dichiarate)

| Dipendenza | Verdetto | Esito |
|---|---|---|
| **P2 ↔ P3** (confine-PII ↔ sandbox) | **COHERENT** | Divisione netta: P2 = *cosa* redarre (`_redact_pii.py`), P3 = *dove* enforcing (DLP al confine rete). "P3 NON sostituisce P2, lo OSPITA". Dipendenza P2→P3 unidirezionale e ben definita. |
| **P1 ↔ P7** (verifier ↔ learn) | **COHERENT** | Postura sul verifier coerente: entrambi dicono "imperfetto → human-gate". La quarantena di P7 protegge il verifier di P1. |
| **P6 ↔ P4** (parallelize ↔ seam) | **COHERENT** | P6 si appoggia a P4 per il contract-test al merge; P4 ammette di catturare solo il contrattualizzato. Coerenti **a patto di** dichiarare il residuo (vedi sotto). |
| **P3 ↔ P4** (sandbox ↔ seam) | **TENSION** | P4 chiama "il sandbox di P3" il DB-effimero che P3 destina al profilo **TEST**, non **SANDBOX** (confinato). Infrastruttura compatibile, **naming/scopo da allineare**. |
| **P5 ↔ P9** (spec-keystone ↔ govern) | **TENSION** | Coerenti nell'intento (gate-auto-testante = dead-man's switch), divergono nella meccanica. Da unificare il concetto "il gate fa rumore quando muore" in un solo meccanismo. |
| **P7 ↔ P5** (lezione-codificata ↔ spec-immutabile) | **TENSION** | Coerenti nello spirito (enforcement>abstraction), ma "lezione che diventa hook" (P7) vs "spec immutabile che si supersede" (P5) si sovrappongono: una lezione-codificata **è** una spec? Da chiarire il ciclo di vita. |
| **P8 ↔ P2+P3** (genera-app ↔ confine) | **🔴 CONTRADICTION** | Vedi §3 — l'unica vera incoerenza trovata, ed è mia. |

**Bilancio**: 3 COHERENT, 3 TENSION (gestibili: naming/meccanica/ciclo-di-vita), 1 CONTRADICTION reale.
Per un sistema di 9 pezzi scritti in sequenza, **la coerenza d'insieme è alta** — i pezzi si rinforzano,
non si contraddicono, tranne un caso.

---

## 2. Verdetti di LOGICA per-pezzo + i MIEI errori reali

Gli avversari hanno trovato difetti veri. Ho **ri-verificato sul disco** i più gravi. Tre sono **miei
errori reali** (la cicatrix W-meta — "i report allucinano file:line" — che ho applicato agli altri 8
pezzi e che ho commesso io stesso):

| Pezzo | Verdetto | Finding load-bearing — **ri-verificato da me** |
|---|---|---|
| **P1** | CONTRADICTION | 🔴 **VERO**: `guardrails-static.py` citato come "deterministico PRONTO" (P1 §1 righe 38,64) **NON ESISTE** (`find` vuoto). 🔴 **VERO**: `hot-zone-pr-gate.yml` citato come barriera ha `continue-on-error: true` su **ogni** step (righe 156/203/233) → **non blocca mai** (il file stesso lo ammette riga 7). + il meta-verificatore re-introduce il paradosso ricorsivo (residuo onesto già nella spec). |
| **P6** | CONTRADICTION | 🔴 **VERO (off-by-one)**: cito `route_after_checkpoint:462`, è a **461**. + il gate A1 è dichiarato problema-reale ma il codice non contiene il flag (corretto: è ciò che la spec *propone* di aggiungere). |
| **P5** | TENSION | ✅ **atteso**: "Preflight SDD genuinely broken, unfixed" — *documentato non fixato* per scelta (fase studio). |
| **P9** | CONTRADICTION→**declassato** | L'esercito diceva "`regulatory-watcher-run.sh` allucinato": **FALSO-POSITIVO**, esiste in `~/scripts/`. Resta vero: cost-breaker programmatico assente (§1.2 corretto). |
| **P3** | TENSION | ✅ **atteso**: `docker-compose.test.yml` non ha ancora `profiles`/`sandbox-agent`/`egress-proxy` (verificato: 0 occorrenze). È spec-studio: "logica corretta, implementazione da scrivere". |
| **P8** | TENSION | ✅ **atteso**: `brand-api/` + `react-docgen` non esistono (verificato). Spec-studio. |
| **P2 / P4 / P7** | TENSION | Debolezze gestibili (alcune citazioni di linee da ri-allineare, "GO" vs residui — già dichiarati nelle spec). |

**Onestà**: il finale ha trovato **errori reali nei miei stessi documenti** (P1 ×2, P6 ×1). Questo è il
risultato *giusto* — il sistema di verifica avversariale funziona anche contro chi l'ha costruito. I 3
errori sono correzioni puntuali (un file-name sbagliato, un gate da non-citare-come-armato, un
off-by-one), non difetti di sostanza: la tesi di ogni pezzo regge. Vanno corretti nelle spec (vedi §5).

---

## 3. L'unica CONTRADICTION reale: P8 promette certezza dove P2/P3 offrono probabilità

Gli eserciti hanno trovato **una** vera incoerenza d'insieme, ed è mia:

> **P8 §3.5 dice "[l'app generata] non è un nuovo posto dove la PII scappa"** (linguaggio assoluto).
> **Ma P2 §0 dice "il confine-PII è STRUTTURALMENTE best-effort"** (FN floor Presidio 16-38%), **e P3 §2
> dimostra che il firewall è logicamente fallace** per la PII che esce via canale *allowlisted* (l'agente
> legge il repo → mette PII in un prompt lecito → esce verso api.anthropic.com autorizzato).

P8 inoltre (a) non cita la dipendenza **P2→P3** come prerequisito della sua promessa di confinamento,
(b) assume `_redact_pii.py` funzioni mentre P2 documenta 3 bug da fixare prima, (c) omette il gate
**G1-DLP** di P3 (il gate che valida proprio il confinamento che P8 rivendica).

**È una contraddizione di POSTURA**: P8 eredita un confine *probabilistico* e lo comunica come
*garanzia*. La correzione (in §5) è riallineare il linguaggio di P8 a quello di P2/P3 — "riduce
l'esfiltrazione, non l'azzera; eredita un confine best-effort multi-strato condizionato a P2-fixato +
P3-Tier1-deployato + G1-DLP-passato". Nessun cambio di design, un cambio di onestà.

---

## 4. Il giudizio sull'INSIEME (sintesi-potenza)

### (a) L'anello mancante — 3 buchi d'insieme

1. **STADIO 0 — STUDY non ha un pezzo.** Il più grave. Il GROUND a monte (memory-hits + file-caldi +
   rischi-PII + criteri-accettazione prima di partire) è precisamente ciò che previene la classe di
   errore — *allucinazione di file:line* — che 6 pezzi pagano a valle e che **i miei 2 eserciti hanno
   appena commesso**. È l'anello a leva più alta non scritto.
2. **CRITICO-2 (burst-to-cloud per capability) è SPARITO.** Il report madre lo marcava "verità scomoda
   verificata 3×: lo stack 100%-locale non regge da solo per coding complesso". I 9 pezzi instradano
   per *sicurezza-PII* (P2) ma nessuno affronta *quando il task è troppo difficile per Ollama* né il
   mini-benchmark che direbbe *quanto* burst serve. **L'intera potenza del loco poggia su
   un'assunzione mai misurata.**
3. **ARCH e SHIP esistono solo come infra, non come pezzi gated.** I due punti (decidere-se-council,
   merge-effettivo) restano dipendenti dall'operatore-che-si-ricorda — la fragilità (gate
   opt-in/dimenticato) che P1/P5/P9 dichiarano nemica.

### (b) Il filo rosso — DUE intrecciati, e la loro fusione È il sistema

- **Filo 1 — «la strumentazione esiste già; è disarmata, scollegata o cieca».** Ogni pezzo, nel suo
  GROUND, scopre il 70-90% del mattone già presente ma non cablato: P1 (`stop_verify` disarmato), P2
  (redattore wired solo all'evolver), P4 (test non-gating), P5 (preflight morto), P6 (fan-out
  incondizionato), P7 (LEARN mai chiuso), P9 (cost-breaker assente). È la firma di un organismo
  costruito a strati da sessioni diverse, dove ogni strato fu *shippato ma mai armato*. *Enforcement ≠
  existence.*
- **Filo 2 — «il verificatore è imperfetto → tutto gated + reversibile + auto-testante».** È il teorema
  di P1 che si propaga: P5 (lint=pavimento, panel=soffitto, gate-che-fa-rumore), P6 (ipotesi revocabile),
  P7 (proposta≠applicazione + quarantena), P8 (critic consultivo), P9 (push-on-anomaly + dead-man's
  switch).

**La fusione**: poiché lo strumento esiste-ma-è-disarmato (Filo 1) E il verificatore che lo armerebbe è
imperfetto (Filo 2), la risposta non è "più strumenti" ma «**rendi osservabile quando un gate è spento,
rendi ogni decisione reversibile, tieni l'umano come ultima istanza solo sull'irreversibile**».
Non 9 pezzi scollegati: **9 applicazioni dello stesso teorema a 9 stadi del loop.** Prova di coerenza:
P9 si dichiara "la governance del loop intero" e mappa ogni sua proprietà su un pezzo precedente; P7
osserva che **questo stesso ciclo di 9 spec È il LEARN-loop sicuro** (proposta=spec,
applicazione=gated-da-Antonello). Il sistema è auto-descrittivo.

### (c) Il rischio sistemico più grande — il decadimento entropico inosservabile

Non è un rischio dei singoli pezzi; emerge dall'insieme:

1. **Tutto è STUDY, niente è armato. Il sistema anti-decadimento è oggi decaduto.** `stop_verify`
   disarmato, preflight morto, evoskill FATAL, cost-breaker assente — tutti "documentato non fixato".
2. **L'insieme aggiunge ~15 nuovi gate/hook/watchdog.** Ognuno è un nuovo candidato a
   "esistere-ma-disarmarsi" — la patologia (Filo 1) che il sistema diagnostica. **W64 lo dimostra già
   accaduto**: un fix re-introdusse il bug che doveva prevenire perché il lint non era in CI.
3. **Il decadimento è silenzioso e composto.** Se il meta-verificatore (P1) si disarma, il dead-man's
   switch (P9) lo nota; ma se il dead-man's switch si disarma (P9 §5.3 «anch'esso può morire»), l'unico
   sensore è Zero — non-dev, a cui il sistema ha *detto di non guardare* (P9 §0, zero-attenzione).
   **C'è un punto cieco dove il guardiano-del-guardiano muore in silenzio.** Il pattern-killer "test
   verdi + sistema rotto" elevato ad architettura.

   *Prova che è reale, non teorico*: questa sessione + il memo
   `decision_guardrail_liveness_sentinel_spec_2026_06_06` l'hanno esibito **4 volte** (stop_verify
   wired-ma-disabilitato, verify_mcp_integrity assente, Pro+Mini offline ignorati, panel Codex appeso
   su token morto) — più i 2 eserciti che hanno allucinato mentre cacciavano allucinazioni.

### (d) Ordine di implementazione — la sequenza valore/rischio

Dipendenze verificate: P2→P3 · P1-strato4→P2→P3 · P4→P3 · P8→P2+P3+P4 · P7→P1+P4+P5+P6 · P6→P4 · P9→tutti.

- **FASE 0 — IL FONDAMENTO (prima di QUALUNQUE pezzo-feature).** Riarmare il rotto + costruire il
  sensore-di-decadimento: `stop_verify` riarmato + `hot-zone-gate` flip-a-enforcement; preflight-morto
  risolto (P5 opzione C: check generale dei comandi-mandatory); **meta-verificatore P1 + dead-man's
  switch P9 costruiti per primi e resi immutabili** (firma-hash + CI CODEOWNERS-only); **STADIO-0 STUDY**
  costruito come gate d'ingresso. *Razionale: costruire i pezzi prima del sensore-di-disarmo = costruire
  su un sensore spento.*
- **FASE 1 — sostrato**: P3-Tier1 (sblocca P2, P1-strato4, P4, P8). Gate: G1-DLP passa.
- **FASE 2 — confine**: P2 (fix-prima i 3 bug di `_redact_pii.py`).
- **FASE 3 — verifica (cardine)**: P1 completo + P4 in parallelo.
- **FASE 4 — parallelismo**: P6 (usa P4).
- **FASE 5 — arricchimento**: P8 (ha P2+P3+P4 pronti).
- **FASE 6 — apprendimento**: P7 **per ultimo** — «chiudere il LEARN prima che P1 sia solido =
  amplificare un verificatore debole = degradare credendo di migliorare». Invertirlo è *attivamente
  pericoloso*.
- **Trasversale**: P9 (la parte cost-breaker + dead-man's switch va in Fase 0).
- **P5 non è una fase**: è il *formato* (ogni spec di questo ciclo è già un ADR-rafforzato à la P5).

### (e) Il verdetto onesto sulla potenza reale

**«Il workflow più potente al mondo» è la domanda sbagliata.** La cosa più potente che questi 9 pezzi
fanno è rispondere a quella giusta: **«il workflow più potente che un solo-dev-non-dev può fidarsi di
non vedere rompersi in silenzio».**

**Cosa l'insieme È (e perché è raro)**: non un collage, un sistema con UNA tesi coerente applicata a 9
stadi. L'originalità non è nei tool (sono tutti SOTA noti: testmon, sqlc, mutmut, microsandbox,
openapi-typescript, Presidio) — è **nell'aver capito che per un non-dev il collo di bottiglia non è la
generazione ma la verifica, e nell'aver progettato l'intero loop attorno al decadimento dei verificatori
invece che attorno alla velocità.** Quasi tutti i framework "potenti" ottimizzano la velocità; questo
ottimizza la *fiducia osservabile*. Converge con l'essay Anthropic citato nel report madre («code review
diventa il collo di bottiglia»). Questo è genuinamente avanguardia.

**Cosa manca per renderlo VERO (non aspirazionale)** — 4 cose, per gravità:
1. **Tutto è STUDY, niente armato. Il sistema anti-decadimento è oggi decaduto.** Finché la Fase 0 non
   è fatta, il loco è un documento, non un sistema. (Leva alta, sforzo piccolo.)
2. **CRITICO-2 va ri-misurato, non assunto.** Serve un 10° pezzo (o P2 esteso): router task→modello per
   *difficoltà* + mini-benchmark locale come ground-truth. Senza questo numero, la potenza è un'ipotesi.
3. **Lo STADIO-0 STUDY va scritto.** L'anello mancante che previene a monte ciò che 6 pezzi pagano a valle.
4. **Serve una regola anti-ipertrofia esplicita**: «NON aggiungere il gate N+1 finché i gate 1..N non
   sono tutti verde-armati e osservati dal meta-verificatore». Altrimenti la Fase 6 arriva con 15 gate
   di cui metà già silenziosamente morti.

**Giudizio finale, senza elogio**: l'architettura è eccellente E onesta (ogni pezzo dichiara i residui,
nessuno promette garanzie, tutti dicono "best-effort multi-strato"). Ma è **potenza potenziale, non
realizzata**: oggi 9 spec-studio sopra un'infrastruttura i cui guardiani sono per metà disarmati.
Diventa potenza VERA solo se: **Fase-0 (riarmo + meta-verificatore immutabile + STUDY) PRIMA dei
pezzi-feature**, **CRITICO-2 ri-misurato**, e **una regola che impedisca all'insieme di diventare il
prossimo strato di strumenti-che-nessuno-arma**. Senza questi tre, è il workflow più *sofisticato* del
mondo che decade in silenzio — esattamente il fallimento che è stato progettato per prevenire.

---

## 5. Azioni correttive sulle spec (dal finale)

Correzioni puntuali emerse dagli eserciti (da applicare in una sessione di implementazione, NON ora —
restiamo in fase studio; qui le registro come debito tracciato):

1. **P1**: rimuovere/correggere `guardrails-static.py` (non esiste — è il "Guardrails daemon" in
   `~/.claude/hooks/`, nome diverso); declassare `hot-zone-pr-gate.yml` da "barriera" a "barriera in
   monitor-mode (`continue-on-error:true`), da armare in Fase 0".
2. **P6**: `route_after_checkpoint:462` → **461**.
3. **P8**: riallineare il linguaggio da assoluto ("la PII non scappa") a probabilistico/condizionato
   (best-effort eredita P2 + dipende da P3-Tier1 + G1-DLP); citare esplicitamente la dipendenza P2→P3
   e il gate G1-DLP.
4. **P3↔P4**: allineare il naming — il DB-effimero usato da P4 è il profilo **TEST**, non SANDBOX.
5. **P5↔P9**: unificare "gate-che-fa-rumore-quando-muore" (preflight-self-test ≡ dead-man's switch) in
   un solo concetto.
6. **P7↔P5**: chiarire il ciclo di vita di una "lezione-codificata" vs "spec immutabile".

Nessuna di queste tocca la *sostanza* dei pezzi — sono correzioni di precisione, naming e onestà del
linguaggio. La logica e la coerenza d'insieme reggono.

---

## 6. Chiusura

Il ciclo richiesto è completo: **9 pezzi, ognuno con deep-research/disk-state + panel multi-LLM
asimmetrico + reuse-first + spec con gate falsificabili**, poi **controllati a eserciti** (17 agenti) per
logica, coerenza e potenza, **e ri-verificati a mano** sul disco.

Il risultato non è "ecco il sistema perfetto". È più utile: **una mappa onesta di un loop avanguardia,
con i suoi 3 buchi (STUDY, CRITICO-2, anti-ipertrofia), il suo filo rosso coerente (verificatore
imperfetto → tutto osservabile/reversibile), il suo rischio massimo (decadimento silenzioso dei
guardiani), l'ordine giusto per costruirlo (Fase-0 riarmo PRIMA), e i 3 errori che persino questo
processo ha commesso e corretto.** L'ultima riga è la più importante: il valore di questo loop non è che
non sbaglia — è che **rende i propri sbagli osservabili**. Il finale lo ha dimostrato sbagliando, e
accorgendosene.

> Provenienza completa: `research/operations/specs/P1-P9*.md` (9 spec), report madre
> `research/operations/2026-06-06-sota-agentic-dev-workflow.md`, Workflow `wf_8cc6e1c5-a63` (17 agenti),
> memory `discovery FINALE eserciti 9-spec 2026-06-06/07`. Tutti i commit su branch
> `agent/air-m5/docs/meta-dev-loop-sota`.
