# KBLI Navigator — le window per avere l'app PRONTA SULLE NOSTRE MACCHINE

> **rev. 3**, 2026-09-11, M5, sessione `nuzantara-c9`. Terreno: l'audit di readiness di Astra
> (`~/Desktop/kbli-bkpm-readiness-2026-09-11/READINESS.md`), le sue quattro risposte sul taglio,
> le due cure di motore committate oggi, e un panel avversariale a tre seat (Codex `gpt-5.6-sol`,
> Gemini `agy`, Kimi) le cui obiezioni sono state **giudicate una per una** — log in fondo.
> Formato: `.claude/skills/modus/battle-window-spec.md` (sette sezioni).

## SCOPO — ristretto da Zero

**L'app è pronta e funzionante sulle nostre macchine. Nient'altro.**

Fuori dal percorso critico, dichiarati e non dimenticati: Developer ID, notarization, accettazione
Gatekeeper, ciclo account/isolamento su un Mac di terzi, e lo ZIP di distribuzione. Tornano il
giorno in cui il traguardo passa da «pronta da noi» a «installabile da altri».

**La cosa che Zero ha chiesto è UN candidato che gira sulla flotta.** La rev. 2 di questa spec
imponeva onestà rigorosa a ogni window e poi lasciava proprio quel candidato di proprietà di
nessuno — il rilievo più duro del panel, e giusto. Da qui la **Window C**, che è la consegna.

---

## GATE 0 — CHIUSO

Era la condizione per aprire le window: tre rilievi BLOCKER su tre seat diversi nascevano tutti dal
fatto che queste quattro cose erano lasciate aperte. Due le ha decise Zero, due si sono risolte da
sé una volta misurato che il seat vive su M5. **Le window si possono aprire.**

| #       | Da congelare                                                                          | Perché blocca                                                                                                                                                                                                                     |
| ------- | ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **0.1** | ✅ **RULED Zero 2026-09-11: la flotta è M5.** «Comincia su M5.»                       | Un solo marker da emettere, un solo runtime da allineare, un solo host su cui provare il candidato. Una macchina sola: il seat e' stato misurato vivo su M5, quindi Pro e Mini escono del tutto e cade il problema del trasporto. |
| **0.2** | ✅ **RISOLTO: tutto su M5, e il runtime si congela in un percorso dedicato all'app.** | Vedi §Runtime.                                                                                                                                                                                                                    |
| **0.3** | ✅ **RULED (Zero: «fai tu») — Q11 SI CURA. Non si emenda il corpus.**                 | Vedi §Q11: la curabilità è stata **misurata**, non asserita.                                                                                                                                                                      |
| **0.4** | ✅ **RISOLTO: non serve trasporto. Una macchina sola.**                               | Vedi §Runtime.                                                                                                                                                                                                                    |

### §Q11 — RULED: si cura

I floor §8 su **n = 8** strutturate: `⌈0.8 × 8⌉ = 7` corrette; `⌊0.10 × 8⌋ = **0**` astensioni
ingiuste. **Una sola astensione ingiusta = 12,5% = gate ROSSO.** Quindi «P2b verde» e «Q11 rossa»
non possono coesistere.

**Si cura, e non si tocca il corpus.** Q11 è la domanda più realistica del corpus — un cliente che
apre un caffè a Ubud — e 56303 è Bali-bloccato mentre 56101 no: sbagliarla è un difetto di prodotto,
non un artefatto di benchmark. Emendare un requisito dopo averne visto l'esito è ciò che Astra ha
vietato su Q23, e vale identico qui.

**La curabilità è misurata, non promessa.** Regola candidata: _un termine i cui hit stanno TUTTI nel
budget di slot entra per intero, perché una rarità simile esprime l'intento della domanda_
(«kafe» compare in 4 record su 1.559: chi lo digita li vuole tutti). Nessuna costante magica —
la soglia è `maxSearchHits`. Misurato sul corpus congelato:

| soglia                      | recall codici attesi | must-keep persi     | Q11                           |
| --------------------------- | -------------------- | ------------------- | ----------------------------- |
| oggi (nessuna garanzia)     | 6/7                  | nessuno             | 56303 sì, 56101 **no**        |
| ≤ 3                         | 6/7                  | nessuno             | 56101 **no** — troppo stretta |
| ≤ 4                         | **7/7**              | nessuno             | entrambi                      |
| **≤ 5 (= `maxSearchHits`)** | **7/7**              | **nessuno**         | **entrambi**                  |
| ≤ 6 e oltre                 | 6/7                  | **Q26 perde 79122** | inonda gli slot               |

**Window A adotta la soglia = `maxSearchHits`**, ma la costante non è congelata da questa misura:
29 domande non sono un corpus di validazione. A deve costruirle il suo corpus di **colpevolezza e
innocenza** e giustificarla lì. Se non regge, il fallback è il ruling (b) — emendare il corpus con
un nuovo sha e una nota — e **mai** allargare il gate per far passare un numero.

### §Runtime — una macchina sola, e il runtime congelato

La flotta è M5 (ruling 0.1). **Misurato oggi: il seat funziona su M5**, con l'argv esatto di
produzione (`--sandbox read-only --skip-git-repo-check --ephemeral --ignore-user-config
--ignore-rules`, `gpt-5.6-terra` → `SEAT-OK-M5`), su homebrew `0.147.0`.

**Quindi Pro esce di scena.** Codice, benchmark, build e osservazione stanno tutti su M5. Cadono
con lui i tre rilievi BLOCKER del panel sul trasporto fra macchine: la premessa (Window A su Pro)
non esiste più. Il repo, misurato, **non esiste nemmeno su Pro**
(`ssh pro 'ls -d ~/Desktop/logo/kbli-navigator-app'` → _No such file or directory_), e ora non serve
che esista.

**Il benchmark deve girare sul runtime che l'app userà**, o il verde non certifica il candidato:
essendo tutto su M5, questo è automatico. Il pin si allinea a **M5**, non a Pro.

**Cambio di host dichiarato, non nascosto.** Il manifest P2b del 20 agosto ancorava il run a Pro;
questo run girerà su M5. Va scritto nel nuovo manifest. Non intacca i floor, che sono **assoluti** e
non comparativi — e il floor (v) «nuovo ≥ vecchio» era già dichiarato soddisfatto in modo banale
contro un cervello vecchio irraggiungibile. Ma un confronto numerico diretto col run di agosto **non
è lecito**: quello era un altro host e un altro runtime. Si confrontano i floor, non i punteggi.

**Il runtime si congela in un percorso dedicato all'app** (`KBLI_CODEX_BIN`, il gancio esiste già).
È l'unica difesa contro la fragilità che Kimi ha nominato: con un pin esatto su
`/opt/homebrew/bin/codex`, un `brew upgrade` spegne la chat il giorno dopo il verde. Con una sola
macchina in flotta, installarlo costa poco ed è la scelta di Astra.

**Il candidato si costruisce una volta sola su M5** e si prova lì. Un bundle costruito altrove e
copiato è esattamente il «test verde su una build diversa» che questa spec vieta.

---

## Stato di partenza — misurato, con il comando accanto

**Già committato oggi in questo repo (`main` locale):**

| commit    | cosa                                                                                                                                     | prova                                                               |
| --------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| `3e4ca59` | `KBLIAnswerGate`: 4 deroghe all'over-match (α codice assente, β clausola-eccezione, γ multi-codice a cap condiviso, δ cifra dell'utente) | replay delle 87 risposte reali: 12/13 kill ribaltati, 0 regressioni |
| `830683a` | `searchHitsFor`: rarità dal `.total` vero (leggeva `hits.count` già troncato a `prefix(8)`) + peso di campo (titolo ≫ prosa)             | 56303 da rank 9 a rank 1; recall 5/7 → 6/7                          |

**Il benchmark NON è stato rigirato. Il gate P2b resta ROSSO** finché non c'è un run vero.

**I «19 artefatti» — il metodo, non solo il numero.** Due seat su tre l'hanno segnato come numero
non provato, e avevano ragione a diffidare: la rev. 2 riportava l'esito senza il criterio. Il
criterio è: per ogni riga che il gate nuovo rifiuta con `unknownCode(c)`, si verifica che `c` fosse
in `package_codes` della riga registrata (package vecchio) e **non** sia nel package ricostruito
oggi. Su 19 righe, 19 soddisfano il criterio e 0 no. **Va rieseguito e allegato**, non citato.
Il replay resta valido solo a retrieval invariato: con il retrieval nuovo solo un run live gradua.

**I difetti di presentazione, riverificati sul disco:**

1. **Verdetto binario, nessuno stato ignoto.** `KBLIRegistryView.swift:241`:
   `let blocked = l4.blocked || nationallyClosed` — tutto ciò che non è _provatamente_ chiuso cade
   in `else` e stampa **«In Bali: open to a PT PMA»**. Il commento a riga 234 documenta che una
   classe di falsi positivi fu già rattoppata il 2026-06-27: stessa forma, e il caso _ignoto_ non fu
   mai aggiunto. Superscar #3 in **UNDER-match**.
2. **Rischio fabbricato.** `KBLIRegistryView.swift:455`:
   `riskLabel(kbli.perSkala.first?.kategoriRisiko ?? "Menengah Rendah")`. 217 record senza categoria.
3. **Sette siti di troncamento, non due** — enumerati con `grep -rn "\.prefix(" Sources/Views/`:
   `KBLIDetailView` **140** (`ruangLingkup.prefix(20)`), **205** (`kewajiban.prefix(8)`);
   `KBLIRegistryView` **375** (`bullets.prefix(3)`), **871** (`relevantPositions.prefix(2)`),
   **894** (`comp.prefix(4)`), **1773** (`items.prefix(8)` + `Text("+N more")` che non è un bottone);
   `KBLIDossierView` **218** (`perSkala.prefix(4)`).

**Il censimento dell'incertezza** (dataset `3dafab17…`), e due conte indipendenti coincidono:

```
NON_CLASSIFICABILE          25
  di cui gia' blocked=true  17   <- restano CHIUSI: la chiusura domina
  di cui NON blocked         8   <- esattamente gli 8 codici dell'audit di Astra
                                    20111 49213 50115 51103 51203 60312 64310 68112
```

**I 518 `blocked=true` non sono un totale di moratoria**: 372 `BLOCCATO_CLASSE_RISCHIO` + 68
`TERTUTUP` (chiusi per ragione **nazionale**) + 48 `CHIUSO_MORATORIA_BALI` + 17 `NON_CLASSIFICABILE`

- 11 sparsi. Né 518 né 48 è la risposta a «quali KBLI sono sotto moratoria».

**Due invarianti del codice che la rev. 2 stava per violare, entrambe trovate dal panel:**

- **`OpenClawRunner` compila sempre.** `ChatView.swift:12` lo istanzia (`legacyRunner`), gated da
  `useLegacyOpenClawBrain = false` (`KBLIBrain.swift:10`). Misurato sul bundle BKPM costruito oggi:
  **77 simboli OpenClaw e 123 KBLICodexRunner, insieme.** Un criterio «nessun simbolo OpenClaw» è
  **insoddisfabile per costruzione** e avrebbe spinto qualcuno a cancellare il path legacy per far
  diventare verde un numero. Il criterio corretto è **irraggiungibilità**, non assenza.
- **Il messaggio offline è fisso e senza vendor.** `KBLIBrain.swift:22-26`: `reason` è una
  **targhetta diagnostica interna, mai mostrata all'utente**; la UI rende sempre lo stesso
  messaggio (design §4). Nessuna window inventa messaggi d'errore nuovi, e **A non aggiunge
  stringhe localizzate** — il che elimina anche la collisione su `Localization.swift` con B.

---

## La decisione che struttura tutto: chi possiede il significato

Astra: _«deve esserci una sola regola deterministica, utilizzata da chat e schede. A possiede
quella semantica; B la rappresenta.»_ Oggi quella regola non esiste come cosa sola: è un booleano
dentro una view, e **la chat non la usa affatto** — ha un percorso suo dentro il package. È la
radice comune del difetto del banner _e_ della divergenza chat/schede.

| file                                                                                                                                                 | owner |
| ---------------------------------------------------------------------------------------------------------------------------------------------------- | ----- |
| `Sources/KBLIVerdict.swift` (nuovo), `Models.swift`, `KBLIAnswerGate`, `KBLIContextPackage`, `KBLICodexRunner`, `KBLIBrain*`, `Views/ChatView.swift` | **A** |
| `Views/KBLIRegistryView.swift`, `Views/KBLIDetailView.swift`, `Views/KBLIDossierView.swift`, `Theme.swift`, le localizzazioni                        | **B** |
| `build.sh`, `Info.plist`, il manifest del candidato, l'installazione                                                                                 | **C** |

B **consuma** `KBLIVerdict` e non lo ricalcola. Se B ritiene la semantica sbagliata, apre un punto
e torna da Zero — non la corregge, o tornano due regole divergenti.

**L'accettazione è separata in tre livelli**, perché il panel ha mostrato all'unanimità che nessuna
window può oggi rendere verde un criterio che dipende dall'altra: **A-only**, **B-only**,
**candidato integrato** (Window C). Un criterio che dipende da entrambe **appartiene a C**.

---

# WINDOW A — MOTORE (la semantica)

**1. Mandate.** Missione `KBLI-BKPM-2026-09-11`, window **A**, colore **BLU**, lane `motore`.
Organo: semantica del verdetto + cervello chat. Host: **M5**, unica macchina — codice, benchmark, build e
osservazione. Branch locale `motore/verdict-and-p2b`, base `830683a`. Gear 2.

**2. Owned perimeter.** Scrivibili: i file A della tabella sopra, `Tests/{gatetest,packagetest,
codexrunnertest,benchrunner,verdicttest}`. Nel **monorepo** `~/nuzantara` (che _ha_ remote e PR, a
differenza di questo repo — due repo, due regole): `scripts/kbli_bench/**` via worktree broker e PR
normale. Vietati: tutti i file B e C. `Resources/KBLI_2025_FINAL_CLEAN.json` è rigenerato da
`build.sh`: **non committarlo**. `p2b_corpus.json` non si tocca (salvo ruling 0.3b, con nuovo sha).

**3. Sibling contract — congelato prima di BUILD.** `KBLIVerdict`, assi separati:

```
national: .open(cap:) | .restricted(cap:) | .closed(reason:) | .undetermined(reason:)
bali:     .open       | .blocked(reason:) | .undetermined(reason:)
risk:     .known(String) | .absent            // .absent si rende "—", MAI un default
```

**Precedenza:** una chiusura nazionale accertata **domina** un Bali non determinabile. I 17
`NON_CLASSIFICABILE` già `blocked` restano chiusi; solo gli 8 non-blocked diventano `.undetermined`.
Tutti i consumatori passano dall'**API tipizzata**; l'accesso diretto ai campi grezzi di
classificazione è vietato — un `grep` da solo non prova nulla (rinomini e helper lo aggirano).
A consegna a B un **commit identificato**; B ci si rebasa sopra prima di iniziare il suo punto 1.

**4. Acceptance — A-only, verificabile sul solo branch di A.**

1. `KBLIVerdict` esiste, è puro e testato. **Colpevolezza e innocenza:** i 68 `TERTUTUP` chiusi; i
   17 chiusi; gli 8 `.undetermined`; un campione di aperti resta aperto. Nessun caso senza entrambi.
2. Il **package builder e la chat** leggono `KBLIVerdict` — provato da test, non da `grep`.
3. **Q11 risponde.** Il package di Q11 contiene **sia 56303 sia 56101**, e un test di innocenza
   prova che la regola di garanzia non evince i codici delle domande già corrette. Soglia
   `maxSearchHits`, con corpus di colpevolezza e innocenza **di A** — la misura in §Q11 è una
   prova di curabilità, non una validazione.
4. **Il run esiste.** 87 righe = 29 × 3, ognuna con qid, run id, risposta **non vuota**, parse
   valido, **zero record sintetizzati**; timeout, risposta vuota, parse fallito e rifiuto del
   modello sono **categorie distinte**, non «errore di trasporto». Corpus sha invariato (o quello
   nuovo del ruling 0.3b).
5. **I quattro floor**, calcolati da `score_p2b.py` con **output leggibile a macchina**: denominatori,
   classificazione delle domande e comando canonico scritti nel report. Non «li ho contati».
6. **Q23 come regola di classe**: fonte (`B.27.000/642/PM/DPMPTSP`), data `2026-05-13`, condizioni,
   più la verifica di codici specifici. Criteri di accettazione **espliciti in `score_p2b.py`**, non
   a giudizio. **Non** usare 518 né 48 come totale; senza filtro deterministico sull'intero corpus,
   **si dichiara il gap**.
7. **Il giudice riceve il package che il modello ha visto** (`package_codes`), non `expected.codes`
   (W100: 22 flag di fabbricazione su 30 furono falsi).
8. **Il marker BKPM, con emittente separato dal validatore.** Oggi `KBLIBKPMMarker.isValid()` è uno
   stub che ritorna **sempre `false`** (`KBLIBrain.swift:12-13`), quindi la chat BKPM è spenta per
   costruzione ovunque. Serve: un **tool di provisioning separato dall'app** (l'app **non** può
   auto-emettere il proprio marker — un controllo che si auto-concede non controlla nulla),
   un identificatore di macchina stabile, un percorso di archiviazione, e la validazione.
   **Negativi obbligatori**, con un hook di test per poterli girare: marker **assente** → chat
   `.offline` **e le pagine funzionano**; marker di **un'altra macchina** → `.offline`; **un seat
   valido non sostituisce mai un marker** (`KBLIBrain.swift:32`). La **scadenza è fuori scope in
   questo giro** e va dichiarata come gap: la rev. 2 la pretendeva nell'accettazione mentre il
   prompt vietava di inventarla, ed era una mia contraddizione.
   Il messaggio all'utente **non cambia**: resta quello fisso e senza vendor; `reason` resta interno.
9. **Il path legacy è IRRAGGIUNGIBILE**, non assente. `useLegacyOpenClawBrain == false` e nessun
   altro percorso di chiamata raggiunge `OpenClawRunner` — provato da test. **Non** si asserisce
   l'assenza dei simboli: misurato, il bundle ne contiene 77 accanto a 123 di `KBLICodexRunner`, ed
   è corretto così finché P2c non cancella il path.
10. **`--variant internal` continua a costruire e ad aprirsi**: A riscrive gate/package/runner/brain,
    e nessuno oggi la ricontrolla.

**5. Team.** Dux: Claude Opus 5. Refutatore: **Codex sol**, refute-stance, con accesso al JSONL —
mai la stessa famiglia che ha generato (W100). Gate: sessione Claude fresca fuori dalla catena.
_Nota dichiarata:_ Dux e gate finale restano famiglia Claude; l'indipendenza qui è di **sessione e
di catena**, non di famiglia — il refutatore di famiglia diversa è Codex. Release owner: Zero.

**6. Appetite.** 8 ore, N = 0, tre rossi stessa causa → sospensione, fix-di-un-fix a profondità 1.
Seat esaurito → **sospendi e dichiara**: non pagare, non sostituire il seat (sarebbe un altro
prodotto).

**7. Evidence.** `docs/gates/2026-09-11-window-a/` in questo repo + evidence pack nel monorepo per
la parte bench. `Bites:` `KBLIVerdict` letto dal package builder nel bundle, provato dal test §4.2.

---

# WINDOW B — PRESENTAZIONE

**1. Mandate.** Window **B**, colore **BLU**, lane `presentazione`. Host **M5** (gli occhi stanno
qui). Branch locale `presentazione/verdict-honesty`, base `830683a`. Gear 2.

**2. Owned perimeter.** Scrivibili: i file B della tabella, `Tests/uitest/`. Vietati: perimetro A
e C, **incluso `KBLIVerdict.swift`**. **D1→D4d si conserva**: si aggiunge uno stato e un'azione,
non si ridisegna.

**3. Sibling contract.** `KBLIVerdict` congelato. **B non parte sul punto 1** finché A non ha
consegnato il commit identificato; **i punti 2 e 3 sono indipendenti e partono subito.** Il clock
di B parte alla consegna di quel commit, non prima.

**4. Acceptance — B-only, sulle superfici di B.**

1. **Terzo stato esplicito.** Sugli 8 codici il banner dice, in entrambe le lingue,
   **«Applicabilità in Bali non determinabile dai dati disponibili»** più una spiegazione breve del
   dato mancante. **Variante neutra: né spunta verde né simbolo di divieto.** Posizione, dimensioni
   e gerarchia D1→D4d invariate. Nascondere il banner **non** è la cura: renderebbe invisibile
   proprio l'informazione che serve.
2. **L'incertezza non cancella una chiusura.** I 17 restano chiusi con la loro ragione; i 68
   `TERTUTUP` restano chiusi; un codice aperto resta aperto. Colpevolezza **e** innocenza.
3. **Propagazione sulle superfici di B**: banner, badge, riepilogo. _(La propagazione alla chat è di
   A; la coerenza chat-vs-scheda è del candidato — B non può implementarla né provarla.)_
4. **Rischio assente = «—»**, e un test **sull'intero dataset** verifica che nessun consumatore di B
   fabbrichi un valore dove il dato manca: si cura la classe, non la singola riga 455.
5. **Tutti e sette i siti di troncamento** sono raggiungibili in-app, più una ricerca statica che
   prova che non ne restano altri in `Sources/Views/`. Un `Text("+N more")` non è un'azione.
6. **Nessuna regressione D1→D4d**, contro una **baseline identificata**: screenshot di riferimento
   catturati **prima** della cura, con hash, e confronto dichiarato. «Nessuna regressione» senza
   baseline non è falsificabile.
7. **Evidenza con manifest** (vedi §Evidenza sotto).

**5. Team.** Dux: Claude Opus 5 su M5. Refutatore: seat esterno di famiglia diversa. Gate: sessione
Claude fresca. Release owner: Zero.

**6. Appetite.** 5 ore dalla consegna del commit di A, N = 0, tre rossi → sospensione. Se una cura
richiede di cambiare un **dato** o la **semantica**: fermarsi, è un'altra window.

**7. Evidence.** `docs/gates/2026-09-11-window-b/`. `Bites:` `verdictBanner`/`riskSummary`/le liste
nel bundle costruito, provati dagli screenshot manifestati.

---

# WINDOW C — IL CANDIDATO (la consegna)

> Esiste perché il panel ha detto all'unanimità la stessa cosa: l'unico artefatto che Zero ha
> chiesto non era di nessuno. **Questa window è la risposta alla domanda «l'app è pronta?».**

**1. Mandate.** Window **C**, colore **BLU**, lane `candidato`. Host: la macchina nominata in 0.1
come costruttore. Apre **dopo** che A e B hanno chiuso. Obiettivo: **un** candidato, costruito una
volta, installato e provato su ogni macchina della flotta.

**2. Owned perimeter.** Scrivibili: `build.sh`, `Info.plist`, `docs/gates/2026-09-11-candidato/`,
il branch di integrazione `candidato/2026-09-11`. Vietati: la logica di A e B — C **integra e
prova**, non corregge. Un difetto trovato qui torna alla window che lo possiede.

**3. Sibling contract.** Integra i due branch in quest'ordine: **A prima** (produce il contratto),
**B poi** (lo consuma). Un conflitto sui file di frontiera è un errore di perimetro, non un merge
da risolvere a occhio: si nomina e si torna dall'owner.

**4. Acceptance — solo qui, perché solo qui esistono entrambe le metà.**

1. **La semantica è UNA.** Chat e scheda danno lo **stesso** verdetto sugli 8 codici incerti, sui 17
   chiusi e su un campione di aperti — test automatico sul candidato, non a occhio.
2. **Il benchmark è verde SUL CANDIDATO**, non su un branch: stesso commit, stesso dataset, stesso
   runtime. Il bench vive nel monorepo e non esercita la app costruita — quindi **oltre** al bench
   serve il punto 3, o si arriva a «bench verde, app rotta».
3. **La app costruita risponde online, su ogni macchina della flotta.** Aprire il bundle **BKPM**,
   porre a mano una domanda del corpus, ottenere una risposta con una **fonte verificabile**: un
   locator presente nel package e **confrontato automaticamente col dataset** — non una citazione a
   testo libero, che una risposta fabbricata soddisferebbe.
4. **La barra globale**, che nella rev. 2 non aveva proprietario: 1.559 identità raggiungibili; due
   PDF e 13 capitoli presenti; zero occorrenze `balizero.com` nelle risorse della variante BKPM;
   matrice di percorso nativa senza difetti bloccanti. Ogni riga con il suo comando e il suo atteso.
5. **Il manifest del candidato**, schema minimo, generato da uno script e verificato contro il
   bundle: `commit`, `dataset_sha256`, `runtime_path`, `runtime_version`, `variant`,
   `marker_fingerprint`, `bundle_sha256`, `built_on`, `built_at`.
6. **Installazione dichiarata e provata per host**: si dice se si esegue dalla directory di build o
   si copia in `/Applications`, e nel secondo caso si prova l'apertura con l'attributo di quarantena
   che la copia comporta. La firma ad-hoc basta su macchine nostre — ma «basta» va **provato**, non
   assunto.
7. **`--variant internal`** costruisce e si apre.

**5. Team.** Dux: Claude Opus 5. Refutatore: famiglia diversa. **Gate finale: sessione Claude fresca,
fuori dalla catena di contribuzione di A, B e C.** Release owner: Zero.

**6. Appetite.** 4 ore. N = 0.

**7. Evidence e release.** `docs/gates/2026-09-11-candidato/` con il manifest, gli screenshot
manifestati e i log dei comandi. **Rollback:** i tre branch restano; `main` si sposta solo quando C
è verde. Nessun deploy, nessuno zip.

## §Evidenza — la regola che vale per tutte e tre le window

Uno screenshot da solo non prova nulla: può mostrare il bundle sbagliato, dati vecchi o una risposta
preesistente. **Ogni evidenza visiva porta con sé il manifest del §C.4.5** — commit, variante, hash
del dataset, path e versione del runtime, impronta del marker, timestamp — o non è evidenza.

---

## I tre prompt, da incollare così come sono

> Nessuno dei tre si lancia prima che il **Gate 0** sia congelato. Il prompt di ogni window comincia
> con le sue quattro righe: colore, ruolo, mandate id, worktree.

### Prompt WINDOW A — motore

```
Sei la window A della missione KBLI-BKPM-2026-09-11, colore BLU, lane motore, Dux di te stessa.
Leggi .claude/skills/modus/SKILL.md e la spec:
~/Desktop/logo/kbli-navigator-app/docs/WINDOWS-2026-09-11-motore-design.md
Dichiara colore, ruolo, mandate id e worktree prima del primo Edit.
NON PARTIRE se il Gate 0 della spec non e' congelato: flotta, allineamento runtime, ruling su
Q11, trasporto. Se manca, fermati e chiedi a Zero.

Il repo ~/Desktop/logo/kbli-navigator-app e' standalone, NESSUN remote. Il repo ~/nuzantara e'
un altro repo, CON remote e coda di merge: due repo, due regole. Base 830683a.
TUTTO SU M5: codice, benchmark, build, osservazione. Il seat e' stato misurato vivo su M5 con
l'argv esatto di produzione (SEAT-OK-M5, gpt-5.6-terra, homebrew 0.147.0), quindi Pro NON serve
e il repo la' non esiste nemmeno. Due cure sono gia' dentro (3e4ca59, 830683a): non rifarle
senza una misura contraria.

TU POSSIEDI IL SIGNIFICATO. La window B lo rappresenta soltanto.

1. Estrai la semantica in Sources/KBLIVerdict.swift. Oggi la regola e' un booleano DENTRO UNA
   VIEW (KBLIRegistryView.swift:241) e la chat non la usa affatto: e' la radice comune del
   difetto del banner E della divergenza chat/schede. Assi separati, come da spec §3.
   PRECEDENZA: una chiusura nazionale accertata DOMINA un Bali non determinabile. I 17
   NON_CLASSIFICABILE gia' blocked restano CHIUSI; solo gli 8 non-blocked diventano
   .undetermined (20111 49213 50115 51103 51203 60312 64310 68112).
   Ogni condizione ha corpus di COLPEVOLEZZA e di INNOCENZA: i 68 TERTUTUP chiusi, i 17 chiusi,
   un aperto resta aperto. E' la cicatrice famiglia #3 e in questo prodotto e' gia' costata due
   volte. Tutti i consumatori passano dall'API tipizzata: un grep non prova nulla, lo aggirano
   un rinomino o un helper.
2. Il pin e il runtime. MISURA IL PATH ASSOLUTO, NON IL NOME: il runner risolve
   /opt/homebrew/bin/codex (KBLICodexRunner.swift:58-60). Su M5 c'e' anche un codex mise a
   0.154.0 che ombreggia homebrew nel PATH interattivo e che il runner NON usa. Misurato oggi:
   M5 homebrew 0.147.0, pin 0.148.0.
   RULING GIA' PRESO, non riaprirlo: pin ESATTO, niente ">=", niente intervallo.
   La flotta e' M5, quindi il pin si allinea a M5 - non a Pro.
   INSTALLA il percorso runtime DEDICATO all'app (l'override KBLI_CODEX_BIN esiste gia') e
   pinna QUELLO: senza, un "brew upgrade" spegne la chat il giorno dopo il verde. Con una sola
   macchina costa poco ed e' la scelta di Astra.
2bis. CURA Q11 - ruled, e la curabilita' e' gia' stata misurata (vedi §Q11 della spec).
   Oggi 56101 non entra nel package di Q11 e una sola astensione ingiusta su n=8 fa 12,5%,
   cioe' gate ROSSO. Regola: un termine i cui hit stanno TUTTI nel budget di slot entra per
   intero ("kafe" e' in 4 record su 1559: chi lo digita li vuole tutti). Soglia = maxSearchHits,
   NON una costante scelta a mano. Misurato: 7/7 recall, zero must-keep persi. MA 29 domande non
   sono un corpus di validazione: costruisci TU il corpus di colpevolezza e innocenza. Se non
   regge, torna da Zero - NON allargare il gate per far passare un numero.
3. Il giudice va nutrito col package che il modello ha VISTO (package_codes), non con
   expected.codes: senza, 22 flag di fabbricazione su 30 furono FALSI (W100). score_p2b.py sta
   nel monorepo: worktree via scripts/agent_start.py, PR normale.
4. Il run: 29 x 3 SU M5, corpus congelato. 87 righe, ognuna con qid, run id, risposta NON
   VUOTA, parse valido, ZERO record sintetizzati. Timeout, risposta vuota, parse fallito e
   rifiuto del modello sono CATEGORIE DISTINTE, non "errore di trasporto". Sonda il seat con UNA
   chiamata prima di lanciarne 87. I floor li calcola score_p2b.py con output leggibile a
   macchina: denominatori e comando canonico nel report, non "li ho contati".
   Q23: regola di classe con fonte B.27.000/642/PM/DPMPTSP, data 2026-05-13 e condizioni, piu'
   la verifica di codici specifici. NON usare 518 ne' 48 come totale (i 518 includono 68
   TERTUTUP, chiusi per ragione NAZIONALE). Senza filtro deterministico: DICHIARA IL GAP.
5. Il marker. KBLIBKPMMarker.isValid() e' uno stub che ritorna SEMPRE false
   (KBLIBrain.swift:12-13): la chat BKPM e' spenta per costruzione ovunque, anche da noi.
   L'EMITTENTE E' SEPARATO DAL VALIDATORE: l'app non puo' auto-emettere il proprio marker, o il
   controllo non controlla niente. Servono tool di provisioning fuori dall'app, identificatore
   di macchina stabile, archiviazione, validazione, e un hook di test per girare i negativi.
   NEGATIVI: marker assente -> chat offline MA LE PAGINE FUNZIONANO; marker di un'altra macchina
   -> offline; un seat valido NON sostituisce MAI un marker (KBLIBrain.swift:32).
   La SCADENZA e' FUORI SCOPO in questo giro: dichiarala come gap, non inventarla.
   NON cambiare il messaggio all'utente: KBLIBrain.swift:22-26 dice che "reason" e' una targhetta
   diagnostica INTERNA e la UI rende sempre lo stesso messaggio fisso e senza vendor. Tu non
   aggiungi stringhe localizzate: quel file e' di B.
6. Il path legacy dev'essere IRRAGGIUNGIBILE, non assente. NON asserire "nessun simbolo
   OpenClaw": misurato, il bundle ne contiene 77 accanto a 123 di KBLICodexRunner, ed e' corretto
   cosi' finche' P2c non lo cancella. Prova l'irraggiungibilita' con un test.
7. Riverifica che --variant internal costruisca e si apra: tu riscrivi gate/package/runner/brain
   e nessuno oggi la ricontrolla.

VIETATO scrivere nei file di B (KBLIRegistryView, KBLIDetailView, KBLIDossierView, Theme,
localizzazioni) e di C (build.sh, Info.plist). NON committare
Resources/KBLI_2025_FINAL_CLEAN.json. NON toccare p2b_corpus.json salvo ruling 0.3b.
La tua accettazione e' SOLO quella A-only della spec: i criteri che dipendono anche da B
appartengono alla window C, non a te. Non inseguirli.
Appena KBLIVerdict compila ed e' testato, consegna a B un COMMIT IDENTIFICATO e avvisala: il suo
clock parte li'.

Se un floor resta rosso NON allargare il gate: e' gia' stato curato una volta oggi per
over-match, e allargarlo per inseguire un numero e' come si costruisce un prodotto che mente.
Tre rossi stessa causa: sospendi e scrivi. Seat esaurito: sospendi e dichiara, non pagare e non
sostituire il seat. Ogni evidenza visiva porta il manifest (commit, variante, hash dataset,
runtime, marker, timestamp) o non e' evidenza. Non firmare il tuo lavoro.
```

### Prompt WINDOW B — presentazione

```
Sei la window B della missione KBLI-BKPM-2026-09-11, colore BLU, lane presentazione, Dux di te
stessa, host M5 (gli occhi stanno qui).
Leggi .claude/skills/modus/SKILL.md e la spec:
~/Desktop/logo/kbli-navigator-app/docs/WINDOWS-2026-09-11-motore-design.md
Dichiara colore, ruolo, mandate id e worktree prima del primo Edit.
NON PARTIRE se il Gate 0 non e' congelato.

Repo standalone, nessun remote. Base 830683a. TU RAPPRESENTI il verdetto: lo LEGGI da
KBLIVerdict, non lo calcoli. Se ritieni la semantica sbagliata NON correggerla qui: apri un
punto e torna da Zero, o tornano due regole divergenti.

SEQUENZA: i punti 2 e 3 sono indipendenti, PARTONO SUBITO. Il punto 1 aspetta che la window A ti
consegni un commit identificato con KBLIVerdict; ci si rebasa sopra. Il tuo clock parte li'. Non
anticiparlo reimplementando la regola: sarebbe la seconda regola, cioe' il difetto che curiamo.

1. TERZO STATO ESPLICITO. Oggi KBLIRegistryView.swift:241 e' binario e tutto cio' che non e'
   provatamente chiuso stampa "In Bali: open to a PT PMA". Nascondere il banner NON e' la cura:
   renderebbe invisibile proprio l'informazione che serve.
   Testo, in entrambe le lingue: "Applicabilita' in Bali non determinabile dai dati disponibili",
   piu' una spiegazione breve del dato mancante. Variante NEUTRA: ne' spunta verde ne' simbolo di
   divieto. Posizione, dimensioni e gerarchia D1->D4d INVARIATE: aggiungi uno stato, non
   ridisegnare.
   REGOLA CHE NON SI NEGOZIA: l'incertezza si riferisce all'ASSE INCERTO. Un Bali non
   determinabile NON cancella una chiusura nazionale accertata. NON_CLASSIFICABILE sono 25, ma 17
   sono GIA' blocked e restano CHIUSI con la loro ragione; solo gli 8 non-blocked cambiano.
   Colpevolezza E innocenza: i 68 TERTUTUP chiusi, i 17 chiusi, un aperto resta aperto.
   Propaga a banner, badge e riepilogo. La CHAT non e' tua: e' di A.
2. KBLIRegistryView.swift:455 - riskLabel(... ?? "Menengah Rendah") FABBRICA una classe di
   rischio governativa dove il dato manca (217 record). Rischio assente si rende "—". Ma non
   curare solo la riga 455: scrivi un test SULL'INTERO DATASET che nessun consumatore tuo
   fabbrichi un valore dove il dato manca. Si cura la classe, non la riga.
3. SETTE siti di troncamento, non due - enumerati col grep, verificali tu:
   KBLIDetailView 140 (ruangLingkup.prefix(20)) e 205 (kewajiban.prefix(8));
   KBLIRegistryView 375 (bullets.prefix(3)), 871 (relevantPositions.prefix(2)),
   894 (comp.prefix(4)), 1773 (items.prefix(8) + un Text("+N more") che NON e' un bottone);
   KBLIDossierView 218 (perSkala.prefix(4)).
   Curali tutti e aggiungi una ricerca statica che provi che non ne restano altri in
   Sources/Views/.
4. BASELINE PRIMA DELLA CURA: cattura gli screenshot di riferimento D1->D4d ADESSO, con hash,
   altrimenti "nessuna regressione" non e' falsificabile e non potrai dimostrarla dopo.

VIETATO scrivere in KBLIVerdict.swift, Models.swift, KBLIAnswerGate, KBLIContextPackage,
KBLICodexRunner, KBLIBrain, ChatView (window A) e in build.sh/Info.plist (window C).
Se una cura richiede di cambiare un DATO, fermati: e' un'altra window e un'altra classe di
rischio. NON committare Resources/KBLI_2025_FINAL_CLEAN.json.

CHIUDI CON GLI OCCHI: costruisci, apri, e cattura 20111 in EN/light e ID/dark col verdetto
neutro, UNO dei 17 che resta chiuso, e una lista lunga espansa. Usa eventi NATIVI del mouse: la
selezione via Accessibility NON innesca in modo affidabile gli onTapGesture di SwiftUI (misurato
da Astra). Ogni screenshot porta il manifest (commit, variante, hash dataset, runtime, marker,
timestamp) o non e' evidenza. Non firmare il tuo lavoro.
```

### Prompt WINDOW C — il candidato

```
Sei la window C della missione KBLI-BKPM-2026-09-11, colore BLU, lane candidato, Dux di te
stessa. Apri SOLO dopo che A e B hanno chiuso.
Leggi .claude/skills/modus/SKILL.md e la spec:
~/Desktop/logo/kbli-navigator-app/docs/WINDOWS-2026-09-11-motore-design.md
Dichiara colore, ruolo, mandate id e worktree prima del primo Edit.

TU SEI LA CONSEGNA. Zero ha chiesto una cosa sola: l'app pronta e funzionante sulle nostre
macchine. Le window A e B curano meta' del problema ciascuna; tu sei l'unica che risponde alla
domanda "l'app e' pronta?". Esisti perche' un panel avversariale ha notato all'unanimita' che
quell'artefatto non era di nessuno.

Integri e PROVI, non correggi: un difetto trovato qui torna alla window che lo possiede.
Un conflitto sui file di frontiera e' un errore di perimetro, non un merge da risolvere a
occhio: nominalo e torna dall'owner.

1. Integra nell'ordine: A PRIMA (produce il contratto), B POI (lo consuma). Branch
   candidato/2026-09-11.
2. Costruisci UN candidato, UNA volta sola, sulla macchina nominata nel Gate 0.1. Un bundle
   costruito altrove e copiato e' esattamente il "test verde su una build diversa" che questa
   spec vieta.
3. LA SEMANTICA E' UNA: test automatico che chat e scheda diano lo STESSO verdetto sugli 8
   codici incerti, sui 17 chiusi e su un campione di aperti. Non a occhio.
4. Il benchmark dev'essere verde SUL CANDIDATO: stesso commit, stesso dataset, stesso runtime.
   ATTENZIONE: il bench vive nel monorepo e NON esercita la app costruita - "bench verde, app
   rotta" e' uno stato raggiungibile. Per questo serve anche il punto 5.
5. La app costruita risponde ONLINE su OGNI macchina della flotta: apri il bundle BKPM, fai una
   domanda del corpus a mano, e ottieni una risposta con una FONTE VERIFICABILE - un locator
   presente nel package e confrontato AUTOMATICAMENTE col dataset. Una citazione a testo libero
   non basta: una risposta fabbricata la soddisferebbe, e questo prodotto esiste per non
   fabbricare.
6. La barra globale, con comando e atteso per ogni riga: 1.559 identita' raggiungibili; due PDF
   e 13 capitoli; ZERO occorrenze balizero.com nelle risorse della variante BKPM; matrice di
   percorso nativa senza difetti bloccanti.
7. Il MANIFEST, generato da script e verificato contro il bundle: commit, dataset_sha256,
   runtime_path, runtime_version, variant, marker_fingerprint, bundle_sha256, built_on, built_at.
8. INSTALLAZIONE dichiarata e PROVATA per host: di' se si esegue dalla directory di build o si
   copia in /Applications, e nel secondo caso prova l'apertura con l'attributo di quarantena che
   la copia comporta. La firma ad-hoc basta su macchine nostre, ma "basta" va PROVATO.
9. --variant internal costruisce e si apre.

Developer ID, notarization, Gatekeeper su pacchetto di terzi e lo ZIP di distribuzione sono
FUORI SCOPO per ruling di Zero: non inseguirli e non ricostruire lo zip.
main si sposta solo quando sei verde. Nessun deploy.
Ogni evidenza visiva porta il manifest o non e' evidenza. Non firmare il tuo lavoro: il gate
finale e' una sessione Claude fresca, fuori dalla catena di A, B e te.
```

## Log del panel — cosa ho piegato e cosa ho rifiutato

Tre seat, refute-stance, sulla rev. 2. Nessuna obiezione è stata accettata perché autorevole:
ognuna è stata verificata.

**Piegate perché verificate sul disco:**

- _Il repo non esiste su Pro / nessun trasporto definito fra le macchine_ (Gemini, Codex, Kimi:
  tre BLOCKER indipendenti) — **confermato**, e peggio di come lo dicevano: il repo su Pro non c'è
  proprio. **Poi il ruling di Zero l'ha dissolto invece di risolverlo**: flotta = M5, e misurando
  si è visto che il seat vive su M5. Niente due macchine, niente trasporto, niente rsync. Il
  rilievo era giusto e la cura migliore è stata togliere la premessa.
- _Simboli OpenClaw_ (Kimi) — **confermato**: 77 OpenClaw e 123 KBLICodexRunner nello stesso bundle.
  Il criterio della rev. 2 era insoddisfabile e induceva a cancellare codice per far verde un numero.
- _Il messaggio offline è fisso_ (Kimi) — **confermato** a `KBLIBrain.swift:22-26`. Elimina anche la
  collisione su `Localization.swift`.
- _Sette siti di troncamento, non due_ (Gemini, Codex, Kimi) — **confermato** col grep, enumerati.
- _Il marker si auto-emetterebbe_ (Codex) — il rilievo migliore del panel. Emittente separato dal
  validatore.
- _Contraddizione «scaduto» vs «non inventare la scadenza»_ (Codex) — era mia. Scadenza fuori scope,
  dichiarata come gap.
- _Q11 vs i floor_ (Codex, Kimi) — l'incompatibilità è aritmetica: → Gate 0.3, ruling di Zero.
- _Accettazione che dipende dall'altra window_ (tutti e tre) — da qui i tre livelli e la Window C.
- _L'integrazione non ha proprietario_ (Kimi, Codex) — **il rilievo più duro, e giusto**: Window C.
- _Screenshot senza manifest, run senza definizione di errore, floor senza denominatori, «nessuna
  regressione» senza baseline, fonte non definita_ (Codex, Kimi) — tutte piegate.
- _`--variant internal` non riverificata_ (Kimi) — piegata.

**Rifiutate, con la ragione:**

- **Gemini: sostituire il marker legato alla macchina con un flag statico**, perché «roba da
  distribuzione a terzi». **No.** Cancellerebbe una proprietà di sicurezza deliberata
  (`KBLIBrain.swift:32`) perché è scomoda, e contraddice il ruling di Astra sui tre controlli
  distinti. Codex la smentisce nella stessa tornata, e ha ragione lui. Piegata solo la metà giusta:
  il meccanismo era sottospecificato.
- **Gemini: cancellare i riferimenti al monorepo e alle PR.** Fondato su un errore: `score_p2b.py`
  vive davvero in `~/nuzantara`, che _ha_ remote e coda di merge. Lo scopo ristretto vale per il
  repo dell'app, non per il monorepo. Piegata la parte giusta: la spec ora dice esplicitamente che
  i repo sono due, con regole diverse.
- **Gemini: «i 19 artefatti sono un'assunzione non validata».** Falso: erano stati verificati uno
  per uno. Ma la rev. 2 riportava il numero senza il criterio, e due seat su tre hanno diffidato —
  il che è di per sé un difetto. Piegata la metà giusta: ora c'è il metodo, ed è da rieseguire.

**Cosa resta fuori scope, dichiarato.** Developer ID, notarization, Gatekeeper, terzi. E la north
star di Astra vale sopra tutto: **rifinire la GUI e vincere un benchmark da 29 domande non
certifica un corpus da 1.559 codici.** Ogni affermazione su rischio, licenze, proprietà estera e
Bali deve avere provenienza governativa con locator e vintage, oppure dichiarare il proprio gap.
