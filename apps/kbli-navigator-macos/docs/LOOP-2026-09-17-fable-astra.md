# KBLI NAVIGATOR — loop prompt Fable ⇄ Astra

> Scritto su M5 il 2026-09-17. Ogni numero qui sotto viene da un comando girato in questa sessione
> sul disco, non da un pack. Obiettivo di Zero, verbatim: **«che la app sia completata, valida»**,
> raggiunto **come una saetta** — determinazione e velocità, nessun giro attorno — e nello stesso
> giro **design portato a un livello UI/UX ultra**.
>
> Consegna del loop: **due workflow script** (Workflow tool) pronti da lanciare.
> Il loop NON costruisce l'app. Il loop scrive i due workflow che la costruiscono.

---

## §0 — STATO MISURATO (2026-09-17, repo `~/Desktop/logo/kbli-navigator-app`)

Repo **standalone**: nessun remote, nessuna CI, nessuna coda di merge. Un commit qui è un'azione
completa, e nessuno la verifica al posto tuo.

| fatto                                                       | misura                                                                                                                                                                                                                              |
| ----------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `master`                                                    | **non contiene nulla** del lavoro 11→14 settembre                                                                                                                                                                                   |
| branch vivi                                                 | `motore/verdict-and-p2b` (HEAD `8275649`), `presentazione/verdict-honesty` (1 commit), `k2/row-identity`, `k2/gamma`, `k2/design-app` (11 commit, **SUSPENDED**)                                                                    |
| working tree                                                | `Resources/KBLI_2025_FINAL_CLEAN.json` modificato non committato (lo rigenera `build.sh`)                                                                                                                                           |
| bundle esistenti                                            | `build/KBLI Navigator - BKPM.app` (19 ago) · `build/KBLI Navigator - INTERNAL.app` (13 set)                                                                                                                                         |
| gate P2b window A                                           | **RED prima e dopo**: (i) fabbricazioni 0/87→**1/87** · (ii) accuratezza 3/8→**4/8** · (iii) astensione ingiusta 2/8→**1/8** · (iv) gap 19/21                                                                                       |
| gate P2b candidato `k2/gamma`                               | **RED**: (i) 0/87 GREEN · (ii) **3/8** · (iii) **1/8** · (iv) 21/21 GREEN                                                                                                                                                           |
| dataset                                                     | **tre hash in disaccordo**: corpus+run `3dafab17…`, file committato `a5721756…`, canonical monorepo `c69a260d…` — e **`c69a260d` è quello che `build.sh` mette nel bundle**, cioè quello che il prodotto spedisce                   |
| suite sul dataset che spedisce (`c69a260d`, base `8275649`) | `verdicttest` **FAIL** (518 attesi, 519 letti) · `packagetest` **FAIL** · `uitest` **FAIL** — identiche a head `1a668d5`                                                                                                            |
| OPEN-1 (HIGH, sospeso)                                      | su **31 record** TERBATAS con cap verificato la sheet dice «Restricted · 49%» e il dossier dice «49% Open» / «Fully open · 49%» — due superfici, due risposte                                                                       |
| council k2/design-app                                       | **quorum NON raggiunto**: kimi 403, tp1-qwen 429, gemini di riserva; nessun `VERDICT: OK`                                                                                                                                           |
| appetite window A                                           | 8 h previste, **~10 h spese**, 5 round di council                                                                                                                                                                                   |
| chat BKPM                                                   | accesa solo con marker; il tool di provisioning esiste (`Tools/kbli-bkpm-provision`, `54772e0`) ma **nessun marker è mai stato emesso né provato**                                                                                  |
| design                                                      | `docs/UIUX-REVIEW-2026-06-24.md`, panel 4-LLM: C1 verdetto contraddittorio (4/4), C3 contrasto notte **2,2–2,9:1** contro minimo 4,5:1, C5 «wall of plates», C7 la roadmap consiglia il percorso che la pagina ha appena invalidato |

---

## §1 — LE BARBARIE, NOMINATE PERCHÉ NON SI RIPETANO

Non sono opinioni: ognuna è la forma di un costo già pagato.

1. **Nessuno possedeva il candidato.** Cinque branch, zero integrazioni, `master` fermo. L'app che
   Zero può aprire oggi non contiene una riga del lavoro di questa settimana.
2. **Il cancello era matematicamente impossibile.** P2b si gioca su **n = 8** domande strutturate:
   floor (ii) esige 7/8 e floor (iii) ammette **0** astensioni ingiuste su 8 (una sola = 12,5% > 10%).
   Una risposta storta di un LLM non deterministico = RED. Quel numero ha tenuto fermo il prodotto
   dal 20 agosto.
3. **L'evidenza ha superato il prodotto.** Un solo commit di pack = **+2.857 righe**; il codice di
   prodotto della finestra intera è ~1.100. Cinque round di council per ottenere lo stesso RED.
4. **Il benchmark non misura ciò che l'app spedisce.** Il run è ancorato a `3dafab17`; il bundle
   porta `c69a260d`; sul dataset che spedisce tre suite sono rosse **al base**.
5. **La sospensione ha fermato il prodotto invece della discussione.** OPEN-1 è un difetto vero
   (31 record che si contraddicono) ed è rimasto un difetto vero, su un branch che nessuno apre.
6. **Seat morti trattati come partecipanti.** Quorum non raggiunto, riserve usate come titolari,
   round bruciati per registrarlo.

**Divieti operativi che discendono, validi per il loop e per i due workflow:**

- Mai più di **2 round** di review sulla stessa superficie. Terzo round → si scrive la causa come
  fase del workflow e **si va avanti**. La discussione si sospende, il prodotto no.
- L'evidenza non può superare in righe il codice che prova. Manifest + comando + esito. Basta.
- Nessun cancello di consegna definito da un numero su n = 8.
- Un seat morto è dichiarato in una riga e non sostituito con una riserva promossa a titolare.
- Nessun fix-di-un-fix oltre profondità 1.

---

## §2 — «COMPLETATA E VALIDA»: la definizione operativa

Zero non ha chiesto un benchmark verde. Ha chiesto **un'app**. Quindi valido = **non dice il falso,
e dice quando non sa**; completa = **si apre, risponde, e si consegna**.

| cancello | criterio                                                                                | come si misura                                                                         |
| -------- | --------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| **G1**   | zero fabbricazioni servite                                                              | floor (i) del P2b, assoluto, resta                                                     |
| **G2**   | **una sola semantica**: chat, tabella, scheda, dossier e sheet non si contraddicono mai | probe su **tutti i 1.559** record + mutante che lo fa fallire                          |
| **G3**   | quando il dato manca, lo dice (terzo stato)                                             | 8 `NON_CLASSIFICABILE` non bloccati, 217 senza classe di rischio → «—», mai un default |
| **G4**   | l'app si apre e risponde con una fonte **confrontata col dataset**, non a testo libero  | bundle costruito, domanda reale, locator verificato automaticamente                    |
| **G5**   | accuratezza P2b **misurata e dichiarata**, non cancello                                 | un run sul candidato, numeri scritti, corpus mai emendato                              |

**G5 è la decisione che sblocca tutto**: P2b smette di essere il cancello di consegna e torna a
essere la misura che era. Se il numero non piace, si apre un giro sul cervello — dopo aver
consegnato l'app, non al posto di consegnarla.

---

## §3 — DECISIONI DI ZERO (default già applicato, una riga per ribaltarlo)

- **D1 — il cancello.** G1–G4 bloccano la consegna; **G5 misura e non blocca**.
  _Default: SÌ._ Ribaltarlo significa rimettere il prodotto dietro un numero su 8 domande.
- **D2 — un solo dataset: `c69a260d`** (il canonical del monorepo, quello che `build.sh` spedisce).
  Test, probe e benchmark si riancorano lì; le tre suite rosse si curano **guardando il dato**
  (518 vs 519 si decide sul dato, non spostando un pin). Il corpus P2b non si emenda: il delta
  si dichiara. _Default: SÌ._
- **D3 — ordine di consegna: INTERNAL prima** (la usa il team Bali Zero), **BKPM dopo**, con marker
  emesso dal tool di provisioning e provato nei negativi. _Default: SÌ._

---

## §4 — IL LOOP Fable ⇄ Astra

**Fable** (finestra aperta da Zero su M5, Opus 5 `xhigh`) è **console lead**: possiede la missione e
la decisione di integrazione. **Astra** (Codex nativo, console pari per il ruling PR #5821) è
**revisore indipendente**: riceve l'albero congelato e confuta. Poteri pari, generatore mai grader.

**Budget totale: 90 minuti, 3 round, N = 0.**

- **Round 0 — Fable, sola, ≤15 min.** Rimisura §0 sul disco (comando accanto a ogni riga; ciò che
  non gira, non si cita). Non legge nessun evidence pack: legge il repo.
- **Round 1 — Fable propone.** Scrive le **due bozze** di workflow (§5). Le spedisce ad Astra con:
  hash dell'albero, le bozze, i fatti di §0. Nient'altro — non la storia, non i pack.
- **Round 1' — Astra confuta, FIX-FIRST.** Ogni rilievo è `difetto + cura + come si misura che è
vero`. Un rilievo senza misura si scarta senza discussione. Astra non riscrive le bozze.
- **Round 2 — Fable dispone.** Accoglie o rifiuta **per iscritto, con la misura**. Astra rilegge.
- **Round 3 — ultimo.** Se lo stesso difetto torna una terza volta: **non si apre un quarto round**.
  Diventa una fase esplicita del workflow, con il suo criterio, e il loop chiude.
- **Se Astra è morto o senza quota:** Fable lo scrive in una riga e procede da sola. Nessuna riserva
  promossa a titolare.

**Il loop chiude** quando i due file esistono su disco, sono sintatticamente validi e ogni fase
porta il suo comando e il suo atteso. Non quando tutti sono d'accordo.

---

## §5 — I DUE WORKFLOW DA SCRIVERE

Carica prima la skill `workflow-authoring`. Ogni script comincia con `export const meta = {name,
description, phases}` letterale, usa `agent()/parallel()/pipeline()`, e va scritto su disco in
`~/nuzantara/.claude/workflows/`. Ogni fase dichiara **comando** e **atteso**; una fase senza un
comando che qualcuno può rigirare non è una fase.

### WF-1 — `kbli-navigator-candidate` (il prodotto)

1. **UN SOLO ALBERO.** Branch `candidato/2026-09-17`. Integra in quest'ordine: `motore/verdict-and-p2b`
   → `k2/row-identity` → `k2/gamma` → `presentazione/verdict-honesty` → `k2/design-app`. Un conflitto
   su un file di frontiera si **nomina**, non si risolve a occhio.
2. **UN SOLO DATASET** (D2). Riancora suite, probe e bench su `c69a260d`. Le tre suite rosse al base
   diventano verdi curando il dato o il codice — mai spostando un'attesa per far passare un numero.
3. **UNA SOLA SEMANTICA.** `KBLIVerdict` è l'unica sorgente per chat, tabella, scheda, dossier e
   sheet. **OPEN-1 è qui, ed è la prima cura**: una riga di ledger che nomina la proprietà straniera
   è pura proiezione del verdetto (`.open(cap)` → «Open · cap%», `.restricted(cap)` → «Restricted ·
   cap%», `.closed` → «Closed», `.undetermined` → il terzo stato). Probe su 1.559 + mutante.
4. **IL CANDIDATO.** `build.sh --variant internal` e `--variant bkpm`, manifest (§C.4.5), apertura,
   **una domanda vera** con locator confrontato col dataset. Marker BKPM emesso dal tool e i negativi
   provati: assente → chat offline **e pagine vive**; marker di un'altra macchina → offline.
5. **LA MISURA** (G5). Un run P2b sul candidato, numeri dichiarati, corpus invariato. Nessun round
   di council su questo numero.
6. **LA CONSEGNA.** `master` si sposta sul candidato, un tag, e un README di dieci righe: come si
   apre, cosa risponde, cosa non sa. Zero apre l'app.

### WF-2 — `kbli-navigator-ui-ultra` (il design)

Gira **sul candidato**, non su un branch parallelo — la lezione di questa settimana.

1. **BASELINE manifestata.** Render del candidato: 6 bande, giorno+notte, EN+ID, con manifest
   (commit, variante, hash dataset). «Nessuna regressione» senza baseline non è falsificabile.
2. **DIAGNOSI misurata** contro `docs/UIUX-REVIEW-2026-06-24.md` (C1–C7), la skill `design` e
   `bali-zero-brand`. Il contrasto si **calcola** (WCAG ≥ 4,5:1 in entrambi i temi), non si giudica.
3. **UNA direzione**, scelta da Zero **su render**, mai su descrizione. Due proposte al massimo.
4. **APPLICA.** Il verdetto Bali domina la gerarchia (C1); contrasto notte curato (C3); il
   «wall of plates» rotto (C5); i **sette** siti di troncamento diventano azioni raggiungibili, non
   un «+N more» che non è un bottone; stati vuoto/errore/hover/focus; la roadmap non consiglia il
   percorso che la pagina ha appena invalidato (C7).
5. **PROVA.** Re-render contro baseline, probe automatico (nessun badge contraddice il verdetto),
   VoiceOver e Dynamic Type intatti, suite invariata.
6. **FIRMA.** Zero guarda. «Scialba e piatta» non passa (Zero, 28/8).

**Divieti dentro entrambi i workflow:** nessun council oltre 2 round; nessun cancello su n = 8;
nessuna PR sul monorepo salvo `scripts/kbli_bench/**`; nessun emendamento del corpus; nessun
evidence pack più grande del diff che prova.

---

## §6 — PROMPT DA INCOLLARE NELLA FINESTRA FABLE

```
Sei l'imperatore FABLE della missione KBLI-NAVIGATOR-CONSEGNA-20260917, colore ORANGE, host M5,
console lead. Astra è console pari e tuo revisore indipendente: poteri uguali, generatore mai grader.

Leggi PRIMA, interamente:
  ~/Desktop/logo/kbli-navigator-app/docs/LOOP-2026-09-17-fable-astra.md
e solo dopo, se ti serve il terreno storico:
  ~/Desktop/logo/kbli-navigator-app/docs/WINDOWS-2026-09-11-motore-design.md

Zero vuole UNA cosa: l'app KBLI Navigator completata e valida, consegnata come una saetta, e nello
stesso giro il design portato a un livello UI/UX ultra. Il tuo prodotto in questa finestra NON è
l'app: sono i DUE workflow script che la costruiscono (§5), scritti su disco in
~/nuzantara/.claude/workflows/. Carica la skill workflow-authoring prima di scriverli.

Procedura, in quest'ordine e senza girare attorno:
1. Round 0: rimisura §0 sul disco, comando accanto a ogni riga. Non leggere evidence pack.
2. Round 1: scrivi le due bozze. Spedisci ad Astra SOLO hash dell'albero + bozze + fatti di §0.
3. Applica il loop di §4: 3 round, 90 minuti, N=0. Terzo rosso sulla stessa causa → la causa
   diventa una fase del workflow e il loop chiude. Astra morto → lo dichiari e procedi da sola.
4. I default D1/D2/D3 di §3 sono applicati: non riaprirli, segnala solo se una misura li smentisce.
5. Rispetta i divieti di §1 e §5. Sono la diagnosi di questa settimana, non preferenze.

Chiudi con: i due path su disco, le fasi di ognuno in una riga, cosa Astra ha cambiato, e una riga
BUSINESS — cosa avrà in mano il team di Bali Zero quando i due workflow avranno girato.
```

## §7 — MESSAGGIO DI APERTURA PER ASTRA (lo manda Fable, non Zero)

```
Astra, sei console pari su KBLI-NAVIGATOR-CONSEGNA-20260917, ruolo revisore indipendente.
Ricevi: l'hash dell'albero, due bozze di workflow, e i fatti misurati che le giustificano.
Non riscrivere le bozze. Rispondi FIX-FIRST: per ogni rilievo, DIFETTO + CURA + COME SI MISURA che
il difetto è vero. Un rilievo senza misura viene scartato senza discussione, e questo è dichiarato
in partenza per non farti perdere un round.
Contesto che devi avere per non ripetere la settimana appena passata: cinque branch mai integrati,
un cancello matematicamente impossibile su n=8 domande, un evidence pack di 2.857 righe contro 1.100
righe di prodotto, e un benchmark ancorato a un dataset diverso da quello che il bundle spedisce.
Il valore che cerco da te è che i due workflow CONSEGNINO, non che siano inattaccabili.
Massimo 2 round per superficie.
```

---

> Ultimo aggiornamento autoritativo: `git log -1 --format=%cd -- docs/LOOP-2026-09-17-fable-astra.md`.
