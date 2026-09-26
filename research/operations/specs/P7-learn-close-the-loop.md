# PEZZO 7 — LEARN: chiudere il loop che impara (oggi NEVER_CLOSED) — in sicurezza

> **Spec studio (non implementazione).** Ciclo calibrato: reuse-first (disk-state + S13-FROZEN
> VERIFICATI) + council 2-LLM (Gemini red-team / DeepSeek logic). Pezzo 7 di 9. **Il più grave**
> (importance 9): il LEARN è il meccanismo che renderebbe il loop ricorsivamente migliore, ed è
> completamente aperto/rotto.
>
> **Tesi-cardine (DeepSeek)**: il fix NON è "riparare evoskill" (1 bug env). È (a) rompere la
> **cascata di starvation** (manca il segnale a monte), e (b) chiudere il loop **IN SICUREZZA** —
> disaccoppiando *proposta* da *applicazione*, perché chiudere un loop con un verifier imperfetto (P1)
> lo rende **più pericoloso**, non solo più attivo.

---

## 0. La correzione che precede tutto — chiudere il loop AMPLIFICA il verifier (il paradosso)

Il design iniziale puntava a "far girare il LEARN". Il council ha rivelato un paradosso che capovolge
la priorità (Gemini #5 CRITICA, DeepSeek #3):

> Un LEARN-loop che si auto-modifica (propone skill/hook/lezioni applicate) è sicuro **solo se il
> verifier che approva le auto-modifiche è forte**. Ma il **Pezzo 1 ha dimostrato che il verifier è
> strutturalmente imperfetto** (errori-LLM correlati, reward-hacking, verifier's paradox non-risolvibile
> all-AI). Quindi: **chiudere il loop amplifica il potere del verifier — se è debole, chiudere il loop
> degrada il sistema mentre crede di migliorarlo** (apprende una lezione sbagliata → la codifica in un
> hook → l'hook blocca cose giuste). **Un LEARN-loop chiuso con verifier debole è più pericoloso di uno
> aperto.**

**La risoluzione (DeepSeek #3) è il cardine del pezzo**: **disaccoppiare PROPOSTA da APPLICAZIONE**. Il
loop può chiudersi nel *generare* proposte, ma l'adozione permanente è **gated + reversibile**
(quarantena/shadow-mode + human-gate + kill-switch). Così il loop apprende, ma il *potere di modifica
effettiva* resta controllato, e un errore-di-apprendimento non diventa danno permanente.

Questo riconnette P7 a P1 (verifier imperfetto), P5 (lint=forma non sostanza), P6 (revocabilità): la
stessa postura — non fidarsi del giudizio AI come gate finale, rendere ogni decisione reversibile.

---

## 1. GROUND — disk-state VERIFICATO (S13-evolution-FROZEN.json reale + find + launchctl)

Anti-hallucination: letto il campo reale `headline_finding` di
`research/agent-library/S13-evolution-FROZEN.json` (l'Explore aveva parafrasato una "headline"
inesistente; e citava log evolver che sono sul Pro, non su questa macchina — corretto).

### 1.1 Il loop NON si è mai chiuso — 3 componenti, tutti P1 (verbatim S13-FROZEN)

> **headline_finding**: "The autonomous agent-evolution loop (Reflexion + Voyager + EvoSkill) has
> NEVER closed. 0 per-agent lessons.md synthesized, 0 Voyager skill drafts proposed, EvoSkill
> auto-evolver FATAL on every run. The only synthesis that exists is the hand-written one-shot
> (2026-05-17). This FROZEN is the manual evolution cycle substituting for the closure that never
> happened."

| Componente | Verdetto S13 | Root cause (verbatim) |
|---|---|---|
| reflexion-synth | **NEVER_CLOSED** (P1) | "Metrics gate STARVATION: wr3-yt-metrics vede 0/3 manifest-con-metriche; wr2-ig-metrics 1/10 pubblicati. Reflexion legge gli episodi (5 esistono) ma non ha mai girato a completamento O ha girato e prodotto nulla perché il segnale override-diffs/human-review è troppo magro." |
| voyager-skill-library | **NEVER_CLOSED** (P1) | "_proposed/ VUOTO (0 draft). Dipende dall'output di reflexion-synth — **starvation a monte cascata**. + <3 episodi graduation-eligible (bootstrap mai uscito)." |
| evoskill-auto-evolver | **FATAL_EVERY_RUN** | "2026-05-31 'FATAL: DEEPSEEK_API_KEY not set after sourcing secrets.env'. Zero run completate. (a) secrets.env env-drift, (b) worktree-coupling con nuzantara-deploy." |

### 1.2 LA SCOPERTA-CHIAVE — cascata di starvation, non rottura puntuale

```
metrics-starvation (0/3, 1/10)  →  reflexion-synth vuoto  →  voyager vuoto
                                    (+ evoskill FATAL, indipendente, env-drift)
```

Il loop **non è rotto in un punto** — è **affamato a monte**. Manca il *segnale da cui imparare* (le
metriche-IG che non arrivano). Riparare i componenti a valle (evoskill) NON chiude nulla: girerebbero a
vuoto. **Prima il segnale, poi i componenti.**

### 1.3 L'unico componente che CHIUDE (verificato) — scar_replay

- `agent-library/scar_replay/scar_replay.py` (**709 righe**, esiste, letto): dato un cicatrix, costruisce
  un probe, genera un antibody via DeepSeek, e lo **propone SOLO se passa un test eseguibile**
  (no-hallucination: codice reale che gira, non prosa). È l'**unico** componente che chiude il ciclo
  cicatrix→antibody-testato.
- `agent-library/03-lessons.md` (**245 righe**, esiste): testo-umano one-shot (2026-05-17), mai
  rigenerato, **ZERO commit "applied lesson X"** → lezioni *ricordate*, non *enforced*.
- **ZERO cron LEARN** caricati in launchctl (verificato: solo Apple system).

### 1.4 La diagnosi degli avversari (S13 next_actions, verbatim)

> "PRIMARY: S13-P6 (fix evolution-loop closure) + S13-P7 (contract-test harness) — **both adversaries
> say enforcement, NOT abstraction, is the real gap**." + "KILLED by adversaries: S13-P3
> review-gate-protocol (homogenizes intentionally-distinct reviewers)." + "DOWNGRADE: skill-prosa →
> codice-eseguibile."

Stesso filo di P5: **enforcement non abstraction**, codice non prosa, e non omogeneizzare i reviewer
diversi (= la regola del council asimmetrico).

---

## 2. I 6 DIFETTI DEL RED-TEAM → risoluzione (DeepSeek)

| # | Difetto (Gemini) | Sev | Risoluzione (DeepSeek) |
|---|---|---|---|
| 1 | auto-referenzialità allucinatoria (impara da cicatrici auto-scritte che allucinano) | **CRITICA** | §3.1: ancorare ogni lezione a un **FATTO OGGETTIVO ESTERNO** (test fallito, build error, revert umano) — NON all'interpretazione dell'agente. Le cicatrici sono *etichette*; il segnale primario è il fallimento *verificabile*. scar_replay già fa così. |
| 2 | riduzionismo (enforcement≠giudizio, perde le lezioni cognitive) | ALTA | §3.2: **DUE classi di lezioni, DUE pipeline**. Meccaniche → regole eseguibili. Di-giudizio → checklist consultiva per verificatore-separato, non hook bloccante. |
| 3 | over-generalizzazione di scar_replay (funziona solo per bug riproducibili) | ALTA | §3.2: scar_replay è la pipeline *meccanica*. Le lezioni di design/architettura vanno nella pipeline *giudizio* (consultiva), non forzate nel pattern cicatrix→antibody. |
| 4 | bootstrap-fantasma (imparare da spec non-validate = segnale tossico) | ALTA | §3.3: il bootstrap-signal deve essere **fatti accaduti** (test storici, revert, cicatrici *verificate da un evento oggettivo*), NON spec speculative. Le 9 spec di questo ciclo sono *proposte*, non segnale di training finché non implementate+validate. |
| 5 | deriva evolutiva catastrofica (loop chiuso + verifier debole degrada) | **CRITICA** | §0 + §3.4: **disaccoppia proposta da applicazione**. Quarantena/shadow-mode + human-gate + kill-switch. Il loop genera, non applica-permanentemente da solo. |
| 6 | over-fit (1 caso → regola permanente, falso-positivo di domani) | ALTA | §3.5: **soglia di ricorrenza ≥3** + clustering cicatrici + test-di-regressione su storico (la regola non scatta finché non dimostra di non bloccare codice legittimo). |

**Convergenza**: i 2 CRITICA (#1 eco-camera, #5 deriva) sono il cuore. DeepSeek li scioglie con
"segnale oggettivo esterno" (#1) e "proposta≠applicazione" (#5).

---

## 3. DESIGN — il LEARN-loop coerente (formulazione DeepSeek a 6 step)

### 3.1 Segnale NON auto-referenziale (difetto #1 CRITICA)

Il processo è innescato da **fallimenti oggettivi**, non da interpretazioni dell'agente:
- **test fallito** (CI rosso), **errore di build/import**, **lint bloccante**, **revert umano** (override
  diff final-vs-draft).
- Le **cicatrici sono allegate solo se verificate da uno di questi eventi**. Una cicatrix che dice
  "file X:Y rotto" entra nel training SOLO se esiste un test/log che lo conferma. → rompe l'eco-camera:
  il segnale primario è il *fatto*, la cicatrix è solo l'*etichetta umana-leggibile*.
- Questo è esattamente il pattern di scar_replay (antibody solo se test indipendente convalida) —
  generalizzato a "lezione solo se evento oggettivo la àncora".

### 3.2 DUE classi di lezioni, DUE pipeline (difetti #2, #3)

| Classe | Esempio | Destino |
|---|---|---|
| **Meccanica** | "asyncpg.InterfaceError mancante nell'except" (W64), "comando mandatory cita file inesistente" (P5) | **Pipeline meccanica**: antibody eseguibile (stile scar_replay) → test → quarantena → enforcement. |
| **Di giudizio** | "verifica i file:line prima di costruire", "non fan-outtare lavoro sequenziale" | **Pipeline giudizio**: avviso/checklist per il verificatore-separato (umano o panel dedicato). Peso **consultivo, non bloccante**. Può entrare in una guida letta dall'agente, non in un hook. |

Il design NON forza le lezioni di giudizio a diventare codice (perderebbe quelle che contano di più).
Le lezioni cognitive restano consultive — ma esplicitamente *tracciate*, non perse.

> Nota sul destino delle lezioni-di-giudizio: il CLAUDE.md/system-prompt è già pieno e l'agente decade
> dopo ~500 righe (cicatrix within-session-decay). Quindi non si accumulano lì illimitatamente. Vanno
> in un corpus consultivo *recuperabile su richiesta* (come le skill-catalog/memory già fanno), non
> iniettate tutte sempre. Residuo onesto §5: l'applicazione di una disciplina cognitiva a un agente non
> è risolta — è il limite del medium.

### 3.3 Bootstrap dall'affamato — solo fatti accaduti (difetto #4)

Per uscire dalla starvation (0 metriche-IG, <3 episodi), il loop impara da segnali **già abbondanti e
oggettivi**, NON dalle metriche-IG che non arrivano:
- le **cicatrici verificate** (ancorate a un evento, §3.1),
- i **commit-revert** (un umano ha annullato → segnale forte),
- i **test-falliti-poi-fixati** (la coppia rosso→verde è una lezione oggettiva),
- **NON** i panel-verdict di spec non-implementate (= ipotesi, segnale tossico — Gemini #4).

Questo rompe la cascata di starvation: reflexion legge le cicatrici-verificate (ricche), non solo le
metriche-IG (magre/starved).

### 3.4 Adozione GATED e reversibile — il cardine (difetto #5 CRITICA)

**Disaccoppiare proposta da applicazione.** Il loop si chiude nel *generare*, l'adozione è controllata:

- **Quarantena / shadow-mode**: ogni nuova regola eseguibile entra in modalità *registra-ma-non-blocca*
  per N commit (o un periodo definito). Logga quante volte SCATTEREBBE e su cosa.
- **Promozione a enforcement** SOLO se: metriche oggettive migliorano AND falsi-positivi = 0 nel periodo
  di shadow.
- **Human-gate obbligatorio** per ogni modifica *permanente* alle regole automatiche (finché il sistema
  non dimostra estrema affidabilità — coerente con Symbiosis Law 5 "Zero ultima istanza").
- **Reversibilità**: ogni regola ha kill-switch + versionamento → rollback immediato se le metriche
  peggiorano.

Così un errore-di-apprendimento è **rilevabile** (shadow logga prima di bloccare) e **reversibile**
(kill-switch) prima di fare danno. Il loop chiuso non degrada il sistema perché il potere-di-modifica è
gated.

### 3.5 Anti-over-fit — soglia di maturità (difetto #6)

- **Soglia di ricorrenza ≥3**: una lezione diventa candidata-regola solo dopo ≥3 occorrenze del pattern
  (clustering delle cicatrici per pattern ripetuti).
- **Test di regressione su storico**: il candidato-antibody deve girare sui commit passati e dimostrare
  di NON bloccare codice legittimo (no falsi-positivi storici) prima di promuovere.
- Una lezione da 1 incidente resta nella pipeline-giudizio (consultiva), non diventa hook.

### 3.6 Riparare i blocchi esistenti (documentato, NON eseguito — fase studio)

I fix puntuali (già nei next_actions S13, pending Antonello) restano necessari MA secondari rispetto al
ridisegno: restore `DEEPSEEK_API_KEY` export in secrets.env; decouple evolver dal worktree
nuzantara-deploy (famiglia W50/W59); bootstrap dei plist in launchd. **Senza il segnale (§3.3) e la
quarantena (§3.4), riparare evoskill farebbe solo girare a vuoto un loop pericoloso.**

---

## 4. GATE FALSIFICABILI (Symbiosis Law 7)

- **G1 — segnale oggettivo** (binario): una lezione candidata DEVE essere ancorata a un evento
  verificabile (test/log/revert). Una lezione senza àncora oggettiva (solo interpretazione-agente) NON
  entra in pipeline. Falsificabile: il record della lezione ha un puntatore a un evento reale o è
  rifiutato.
- **G2 — proposta ≠ applicazione** (binario): una nuova regola NON può passare a enforcement attivo
  senza (shadow ≥N commit) AND (falsi-positivi=0) AND (human-gate). Falsificabile: tentare di attivare
  una regola fresh-proposta direttamente → bloccato.
- **G3 — reversibilità** (binario): ogni regola attiva ha un kill-switch funzionante. Falsificabile:
  disattivare una regola via kill-switch → torna inattiva immediatamente, nessun residuo.
- **G4 — soglia ricorrenza** (numerico): una lezione con <3 occorrenze NON diventa hook (resta
  consultiva). Falsificabile: candidato con count=1 → instradato a pipeline-giudizio, non meccanica.
- **G5 — loop chiude** (numerico, la metrica del pezzo): # lezioni-meccaniche-diventate-codice-attivo /
  # lezioni-meccaniche-sintetizzate. Oggi: reflexion 0/0 (morto), scar_replay è l'unico >0. Target: il
  rapporto sale E i falsi-positivi restano 0 (chiusura *sana*, non solo *attiva*).

---

## 5. RESIDUI ONESTI

1. **Lezioni di giudizio non veramente "applicabili" (Gemini #2)**: una disciplina cognitiva non si
   "installa" in un agente come un hook. Resta consultiva (corpus recuperabile), e l'agente può
   ignorarla (within-session-decay). **Mitigato, non risolto**: alcune diventano hook *indiretti* (es.
   "verifica file:line" → un hook che pre-carica i file citati e segnala i mancanti), ma la disciplina
   pura resta non-enforced. È il limite del medium.
2. **Il verifier resta imperfetto (eredita da P1)**: la quarantena+human-gate *mitigano* la deriva, non
   la azzerano. Un falso-positivo che non scatta durante lo shadow (raro ma esiste) può promuovere una
   regola sbagliata. Il human-gate è l'ultima difesa — fallibile anch'esso. Postura: best-effort
   multi-strato, coerente con P1.
3. **Bootstrap lento**: imparare solo da fatti-oggettivi (test/revert) significa che all'inizio, con
   pochi fallimenti registrati, il loop ha poco da imparare. Cresce con l'uso. Accettato: meglio lento e
   sano che veloce e auto-degradante.
4. **scar_replay è offline/manuale**: l'unico componente sano non è ancora cron — va integrato (ma con
   la quarantena di §3.4, non a-ruota-libera).

---

## 6. DECISIONE (kill gate)

**GO sul ridisegno** (segnale-oggettivo + 2-pipeline + proposta≠applicazione + anti-over-fit), come
formulazione del LEARN-loop sicuro. Generalizza scar_replay (l'unico che chiude) come pipeline
meccanica; aggiunge la pipeline-giudizio consultiva; e mette la quarantena+human-gate come barriera
contro la deriva.

**Priorità (DeepSeek)**: prima il **segnale** (§3.1/3.3, rompe la starvation), poi la **quarantena**
(§3.4, rende sicura la chiusura), poi i **fix puntuali** (§3.6, evoskill/secrets/worktree). L'ordine è
load-bearing: riparare evoskill per primo = far girare a vuoto un loop pericoloso.

**Metrica primaria falsificabile**: G2 + G5. Se una regola fresh-proposta può passare a enforcement
senza shadow+human-gate, il loop è chiuso-ma-pericoloso (fallito). Se G5 sale MA i falsi-positivi
salgono, è chiusura malata (fallito). Successo = G5 sale E falsi-positivi=0.

**DOCUMENTATO non fixato** (fase studio): i 3 blocchi esistenti (DEEPSEEK_API_KEY env-drift,
worktree-coupling, plist non-bootstrapped) restano da riparare in sessione dedicata, ma DOPO il
ridisegno segnale+quarantena.

**Connessione cross-pezzo dichiarata**: questo pezzo è il più dipendente. Usa P1 (il verifier che la
quarantena protegge), P4 (i test oggettivi che sono il segnale), P5 (lezione-meccanica → hook = la spec
come decisione), P6 (revocabilità). Il LEARN sicuro è l'integrale degli altri.

---

## 7. Provenienza

- **Reuse-first**: Explore disk-state (claim load-bearing ri-verificati; 2 correzioni: `headline_finding`
  non `headline`, log evolver sono sul Pro non M5). scar_replay.py 709, 03-lessons.md 245, S13-FROZEN
  letto verbatim, launchctl confermato zero-cron. Memory importance-9.
- **Council 2-LLM asimmetrico** (calibrato):
  - Red-team: **Gemini 3.1 Pro** — 6 difetti, 2 CRITICA (auto-referenzialità, deriva-catastrofica).
    Premiato per distruggere.
  - Logic: **DeepSeek V4 Pro** (`reasoning_effort=high`) — scioglie auto-ref (segnale oggettivo),
    enforceable≠vero (2 pipeline), **il paradosso centrale** (proposta≠applicazione + quarantena),
    over-fit (soglia ≥3). La formulazione a 6 step è sua.
- **Ground autorevole**: `S13-evolution-FROZEN.json` (la diagnosi machine-readable del loop morto, di
  una sessione precedente — verità esterna ai miei priors).
- **Famiglia**: P1 (verifier imperfetto che la quarantena protegge — il legame più stretto), P4 (test
  oggettivi = segnale), P5 (enforcement-non-abstraction, lezione→codice-immutabile), P6 (revocabilità).
  Cicatrici W50/W59/W62 (worktree-coupling che blocca evoskill).

> **Onestà finale**: il LEARN non diventa "il sistema che si auto-migliora liberamente" — quello,
> con un verifier imperfetto, è il modo più veloce per auto-degradarsi credendo di crescere. Diventa
> **"il sistema che propone miglioramenti ancorati a fatti, e li adotta solo dopo quarantena + gate
> umano, in modo reversibile"**. Il salto non è "il loop si chiude" — è "il loop si chiude **senza
> potersi rompere da solo**". E l'ironia onesta: **questo intero ciclo di 9 spec con council è
> esattamente quel LEARN-manuale sicuro** — proposta (le spec) disaccoppiata dall'applicazione (gated da
> Antonello), ancorata a disk-state verificato, con la stessa S13-FROZEN che era "il sostituto manuale
> della chiusura che non è mai avvenuta".
