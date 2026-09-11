---
date: 2026-09-11
domain: agent-craft
client_case: none
sources:
  - https://www.anthropic.com/news/claude-science-ai-workbench
  - https://claude.com/docs/claude-science/overview
  - https://claude.com/docs/claude-science/core-concepts
  - https://claude.com/docs/claude-science/the-reviewer
  - https://claude.com/docs/claude-science/artifacts
  - https://claude.com/docs/claude-science/tools-and-environments
  - https://claude.com/docs/claude-science/connectors-and-skills
  - https://claude.com/docs/claude-science/how-claude-science-works-with-your-data
  - https://claude.com/docs/claude-science/command-line-settings
  - https://claude.com/docs/claude-science/monitor-usage
  - https://claude.com/docs/claude-science/changelog
  - https://claude.com/product/claude-science
  - https://support.claude.com/en/articles/16563838-get-started-with-claude-science
  - https://www.the-scientist.com/early-verdicts-on-claude-science-faster-workflows-but-gaps-remain-74745
adversarial_review: codex
---

# Claude Science — cos'è, cosa NON è, e come Nuzantara dovrebbe usarlo

> Ricerca su fonti primarie Anthropic (news + docs + help center) del 2026-09-11, incrociata con
> il nostro unico dato empirico: l'output ricevuto il 2026-09-09. Ogni affermazione non verificata
> è marcata **TO VERIFY** nella sezione finale; i numeri del §5 e del §6 sono etichettati `FACT` / `INFERENCE` / `TO VERIFY` in linea (correzione post review adversarial, §9).

---

## 1. Identità verificata (5 righe)

1. Si chiama esattamente **Claude Science**, presentato da Anthropic come *"an AI workbench for scientists"* e nei docs come *"Anthropic's AI workbench for rigorous science"*.
2. È una **desktop app**, non una modalità di Claude.ai e non una feature di Claude Code: gira sulla tua macchina, in beta su macOS 13+, Windows 11 x64 e Linux x64 (glibc).
3. Annunciata il **30 giugno 2026** in beta; Windows è arrivato con la versione 0.1.47 del **10 settembre 2026**.
4. Inclusa nei piani **Pro, Max, Team, Enterprise** senza costo aggiuntivo di *prodotto* — ma consuma la stessa quota settimanale del seat (§3) e, secondo la review adversarial, può spendere extra usage dopo conferma (**TO VERIFY** sui docs `monitor-usage`); su Team/Enterprise un Owner deve abilitarla in Organization settings.
5. Usa **gli stessi modelli Claude del tuo piano** — non è un modello nuovo né un modello speciale per la biologia.

---

## 2. Meccanica: cosa fa davvero

Dai docs, verbatim:

> "You describe a research task or analysis in plain language; Claude writes and runs Python, R, or shell code in a sandbox, reads the folders you grant it, pulls data from scientific databases through connectors, and saves results as versioned artifacts with a full provenance record. A background reviewer can check Claude's claims against the work that was actually run."

Gli elementi che contano per noi:

- **Sandbox con permission card.** Ogni cartella, ogni host di rete, ogni job remoto passa da una card che approvi. Le concessioni permanenti stanno in Settings > Permissions e si revocano. La rete della sandbox è *deny-by-default*; i package manager e i connettori featured usano allowlist proprie, non una card per host (**TO VERIFY** il dettaglio su `core-concepts`).
- **Esecuzione codice reale.** Python, R e shell in un kernel persistente che mantiene le variabili tra gli step. Il kernel muore dopo ~30 minuti di inattività. Ambienti conda gestiti, pip/CRAN/Bioconductor, niente `sudo` e niente `apt` nella sandbox.
- **Artifact + provenance.** Ogni artifact ha 5 schede: Messages, Code, Execution Log, Environment, Review. E una regola d'oro che è già la nostra: *"The Execution Log is the authoritative record of what ran. If the Code tab and the log disagree, trust the log."*
- **Il reviewer.** Un passo di verifica che rilegge risposte, piano approvato, artifact e execution record e controlla se le affermazioni corrispondono a quello che è girato davvero. Auto-review **ON di default su Max/Team/Enterprise, OFF su Pro**.
- **Specialists.** In Settings > Specialists si personalizza il Reviewer o si creano specialisti propri. I criteri aggiunti entrano in ogni review e — verbatim — *"they can't remove or weaken built-in checks."* Questa è, letteralmente, l'idea dei "role prompt con dentro le nostre regole" che il tool stesso ci ha suggerito il 9 settembre.
- **Delegation.** Split del lavoro in track paralleli, on/off per sessione.
- **Compute remoto.** Può connettersi via SSH a un lab workstation o a un HPC login node, oppure a Modal (compute), oppure a S3/GCS/Azure Blob (storage, non compute). **Sì: può toccare sistemi vivi**, se glielo concedi.
- **Connettori.** Oltre 60 database life-sciences preconfigurati (Ensembl, UniProt, PDB, ClinVar, ChEMBL, GEO, PubChem, openFDA, OpenAlex...). E **custom connector = qualunque server MCP**, Remote HTTPS o comando locale.
- **Skill.** Se ne creano, si importano da GitHub (anche repo privati con token), si distilla una skill da una sessione esistente.

---

## 3. Interfacce e rapporto con gli altri prodotti

Esiste una **CLI**, ma è una CLI di *processo*, non di *prompt*:

| Comando | Cosa fa |
|---|---|
| `claude-science serve` | avvia il programma e apre la web app nel browser con un login link monouso |
| `claude-science url` | stampa un login link fresco su stdout (pensato per macchine raggiunte via SSH) |
| `claude-science status` | stato, versione, porta, in JSON |
| `claude-science logs --tail` | segue il log |
| `claude-science stop` / `update` / `import` | gestione del programma e dei dati |

Flag rilevanti: `--detached` (background), `--no-browser`, `--host`, `--port` (default 8000, ascolta su 127.0.0.1). Flag **da vietare per contratto**: `--dangerously-no-sandbox` e `--dangerously-skip-approvals`.

**Non è documentato** al 2026-09-11 — non l'ho trovato in nessuna pagina dei docs, che è assenza di prova e non prova di assenza — un modo non interattivo per passare un prompt e ricevere un risultato, né una modalità schedulata/ricorrente, né un endpoint API "Claude Science". La CLI accende un server; il lavoro lo guida un umano nel browser. **Questo è il fatto architetturale che decide tutto il resto per noi.**

Sul rapporto con Claude Code, Cowork e Agent SDK: **non ho trovato una pagina Anthropic che li confronti esplicitamente**. L'unica relazione documentata in prima persona è sui consumi: *"Claude Science usage counts against each member's standard weekly quota and uses the same seat as the rest of claude.ai."* Quindi (`INFERENCE`: i docs Science parlano di quota del seat claude.ai, non nominano Claude Code) una giornata pesante di Science **mangia la stessa quota** che serve a Claude Code — e il reviewer consuma anche lui.

---

## 4. Dati e PII — la lettura che conta per UU PDP

C'è una trappola nella dicitura "local-first" e va nominata esplicitamente.

Vero: *"Conversation history and artifacts are stored on the member's computer, and Anthropic doesn't sync them"*. I file restano dove sono, letti e scritti in place.

Ma subito dopo, verbatim: *"Anthropic does receive the prompts and responses the app exchanges with Claude, and handles them under its standard retention and Trust & Safety policies."*

Tradotto nella nostra grammatica: **il contenuto di ogni file che il modello legge per rispondere esce dall'Indonesia.** "Local-first" descrive dove vive il database dell'app, non dove vive il testo. Per noi il vincolo è identico a quello di qualunque altro seat cloud: **nessuna cartella con PII cliente può essere concessa**. La permission card per cartella è **un** livello di access control sui path, non un filtro sul contenuto né sull'egress: ciò che il modello legge viaggia comunque nel prompt, e una grant persiste finché non la revochi. Il vincolo si regge quindi su un corpus pre-sanificato, path denylisted, scansione PII dell'output, revisione periodica delle grant e memoria dell'app disattivata per il pilot.

Altri fatti utili: il traffico *dati* verso SSH host / Modal / endpoint propri **non passa da Anthropic** (i prompt e i riassunti che il modello ne deriva sì; i directory connector passano dal servizio hosted Anthropic — **TO VERIFY** su `custom-connectors`); su Enterprise con Compliance API attiva Anthropic conserva i transcript di sessione (default 6 anni); la memoria dell'app è locale e non sincronizzata, ma i fatti richiamati in sessione viaggiano nel prompt. Nessuna dichiarazione trovata su residenza dati per il Sud-est asiatico.

---

## 5. Limiti dichiarati e failure mode osservati

Anthropic mette il disclaimer nella pagina di overview, verbatim:

> "Claude can make mistakes. The reviewer reduces, but doesn't eliminate, errors. It checks claims against the execution record and doesn't re-run analyses. Verify results before relying on them in research, publication, or downstream decisions."

Il reviewer, per ammissione dei docs, **non rigira le analisi** e **non giudica se il metodo fosse quello giusto** per la domanda. Cattura le allucinazioni di *resoconto* (un risultato dichiarato calcolato quando non è girato niente, una citazione che non sostiene la tesi, un DOI che punta a un altro articolo, uno step del piano non completato). Non cattura le allucinazioni di *premessa*.

Da utenti early (The Scientist, tre ricercatori citati per nome): il lavoro accelera e la provenance piace; ma Jerome Lecoq riporta che l'AI *"occasionally made mistakes, requiring researchers to carefully check them"* e che il modello fatica a valutare la **qualità** di un paper. La sua frase è la sintesi migliore di tutto il documento: *"It's not about predicting the next token anymore. It's about doubting the next token."* Stephen Francis segnala guardrail biosecurity troppo aggressivi su temi legittimi. Un cambelog del 27 agosto conferma il problema opposto: le sessioni su Claude Opus 5 producevano *"unrequested analyses, figures, and sub-agents"*, ora ridotti.

### Il nostro dato empirico, che vale più di ogni recensione

Output del 2026-09-09 su corpus Nuzantara (provenienza da Claude Science **TO VERIFY**, §8.1; i numeri sotto sono `TO VERIFY` finché non esiste un manifest redatto con SHA base, comando di conteggio e disposizione per finding). **Vero e già shippato**: 527 link interni rotti, 71 redirect legacy, 100 articoli che citano PP 5/2021 come norma viva quando è abrogata, un buco di copertura nelle automations (root-caused e chiuso). **Falso**: un allarme soft-404 (c'erano `noindex` + `notFound`), una lista di dead code gonfiata su moduli realmente importati, 33 LaunchAgent chiamati "orphans" ma vivi e installati fuori dal repo, un'ipotesi "repo Teman2" inventata.

Il pattern è netto e coincide con la meccanica del prodotto: **eccellente in ampiezza sul corpus, cieco sul sistema vivo.** Circa metà dei finding è sopravvissuta alla verifica in vivo (`INFERENCE` da un solo run, senza numeratore/denominatore pubblicati: non è una misura di precisione, è un'impressione da formalizzare con il ledger di §6.3). Non è un difetto del modello: è che gli abbiamo dato uno snapshot di repo e nessun accesso alle macchine, e lui ha risposto sul repo trattandolo come se fosse il mondo. È la cicatrice **#2 Esiste≠Armato** vista dal lato opposto: là il verde mascherava il morto, qui il file mascherava il vivo.

---

## 6. Proposta operativa per Nuzantara

### 6.1 Dove dovrebbe battere Claude Code e Codex (ipotesi da misurare)

Su tutto ciò che è **censimento statistico su corpus grande con artefatto riproducibile**. Concretamente:

- censimento dei ~3.400 MDX × 5 lingue (conteggio da pinnare a un SHA con comando esplicito): FAQ/`answerSnippet` vs corpo per la coerenza schema.org;
- **currency delle citazioni regolamentari** contro una lista canonica di norme vive (il caso PP 5/2021 è la prova che funziona);
- drift di traduzione: troncamenti, language-mismatch, sezioni mancanti tra locale;
- codici KBLI fantasma citati nei contenuti e assenti dal corpus canonico;
- inventario `STATIC-CANDIDATE-ONLY` del backend (~1.400 moduli, conteggio da pinnare) e del catalogo plist: candidati statici che richiedono verifica live separata, mai una "risk map";
- integrità dei link interni e dei redirect.

Il vantaggio ipotizzato non è l'intelligenza: è la provenance integrata e la UX del reviewer. Claude Code e Codex producono anch'essi CSV, script e log versionati — il confronto va **misurato** su tempo-a-finding-verificato, precisione, recall, quota e sforzo operatore contro uno script deterministico nostro.

### 6.2 Dove non deve mai agire

Mai merge, mai deploy, mai arm. Mai una diagnosi su qualcosa che è **vivo**: LaunchAgent, cron, processi, stato Fly, DB di produzione. Mai `--dangerously-skip-approvals`, mai `--dangerously-no-sandbox`, mai un SSH host concesso verso Pro o Mini. Mai una cartella con dati cliente, mai `.env*`, mai `shared/`, mai il CRM. Concessione cartelle **read-only** sullo snapshot repo, e basta.

### 6.3 La pipeline, in una riga

**Science produce candidati → Claude Code verifica in vivo → cura in worktree → gate → ledger.**

In dettaglio:

1. **Input**: un checkout pulito di `origin/main` in una cartella dedicata, concessa read-only. Nessun secret, nessun PII, nessun dato cliente. Mai il worktree di lavoro.
2. **Brief** (da salvare come skill riusabile dentro Science, così le sessioni future la ereditano):
   - nessun numero senza fonte primaria citata con `file:line`;
   - tutto ciò che non è verificato in questo run si etichetta **TO VERIFY**, non si asserisce;
   - termini bilingui (KITAS, PT PMA, KBLI, hak pakai, NPWP) restano verbatim in Bahasa;
   - **nessun PII in output**, nemmeno se lo trovi nel corpus: `client_id` o redazione;
   - **non diagnosticare processi, daemon o servizi**: non li vedi. Se un finding dipende dallo stato runtime, marcalo `RUNTIME-UNVERIFIABLE` e fermati lì.
3. **Output in schema fisso**, un CSV per famiglia di finding: `finding_id, family, file, line, claim, confidence, runtime_dependent(bool), suggested_fix`. **Nessun `evidence_excerpt`**: l'estratto grezzo può trascinare PII/OSINT dal corpus nel ledger committato (boundary di output, CLAUDE.md §4); si cita `file:line` e un hash del passaggio, e l'evidenza grezza resta in uno store locale ignorato da git. Prima del commit gira uno scanner PII/OSINT fail-closed sul CSV. Niente prosa come deliverable primario.
4. **Specialist "Nuzantara Auditor"** in Settings > Specialists con i punti sopra come criteri di review aggiunti — non sostituiscono i check nativi, si sommano.
5. **Verifica in vivo**: una sessione Claude Code prende il CSV — una sola famiglia per volta, volume di candidati con tetto, ricontrolli deterministici dove esistono e campionamento stratificato altrove — e verifica sul disco e sulle macchine, marca `CONFIRMED` / `REFUTED` / `NEEDS-RUNTIME`, e cura solo i confermati in un worktree via broker. Ship con gate e `Bites:` che nomina il consumer.
6. **Ledger**: il CSV originale + il CSV verificato finiscono in `research/agent-craft/` come coppia diffabile, con un **run manifest** obbligatorio: SHA del repo, versione di Claude Science, modello e reasoning setting, versione di specialist/skill, reviewer on/off, configurazione permessi, hash di input e output. È così che la precisione diventa misurabile.

### 6.4 Cadenza, punteggio, kill criterion

**Gate di decisione prima di qualunque cadenza**: (a) Science abilitata sul nostro piano, (b) disponibilità in Indonesia confermata, (c) rotta approvata sotto la regola anti-endpoint-a-consumo (abbonamento, mai API key), (d) corpus pilot sanificato pronto, (e) extra usage disattivato e tetto quota fissato. Solo dopo:

**Cadenza**: censimento completo del corpus **mensile**, più un run *ad hoc* prima di ogni campagna editoriale o dopo ogni cambio normativo maggiore. Non più spesso: consuma la stessa quota settimanale di Claude Code, e la verifica in vivo costa più della generazione.

**Punteggio**: per ogni run si registra `precision = CONFIRMED / (CONFIRMED + REFUTED)` per famiglia, **più** il recall contro un set etichettato congelato, i conteggi per famiglia con esclusioni e duplicati dichiarati, e il costo per finding confermato. Sotto la soglia minima di campione il verdetto è `INSUFFICIENT_EVIDENCE`, non un numero. Baseline stimata il 2026-09-09 (`INFERENCE`, non riproducibile): **~50%**, con una spaccatura netta — precisione alta sulle famiglie "corpus" (link, citazioni, coerenza), precisione bassa o nulla sulle famiglie "runtime" (dead code, orphan daemon, ipotesi di architettura).

**Kill criterion**, esplicito: si smette di usarlo per una famiglia se in **due run consecutivi** la precisione di quella famiglia sta sotto il 60%, oppure se il tempo di verifica supera il tempo che sarebbe servito a fare il censimento con uno script nostro. Le famiglie runtime, sulla base del dato del 9 settembre, **non vanno nemmeno chieste**: si tolgono dal brief.

### 6.5 Innesto nel tessuto LaunchAgent — la risposta onesta

**Non si innesta.** Non esiste una modalità headless o schedulata: `claude-science serve --detached` accende solo il server, e il lavoro richiede un umano che approvi le permission card nel browser. Mettere un run mensile in un LaunchAgent **oggi non ha una via supportata o documentata**, quindi Nuzantara non lo automatizza.

L'equivalente in casa esiste già e va usato per la parte ricorrente: run non interattivi `claude -p` con ruolo (RAG-QA analyst, KBLI validator, SEO analyst, Ops auditor) che scrivono CSV in `research/`, dentro la cascata di quota esistente. Claude Science resta la **sessione manuale mensile** dove serve la provenance riproducibile e il reviewer; i `claude -p` restano il cron.

Nota di piano da chiarire prima di installare qualunque cosa: la pagina prodotto e l'annuncio parlano di un Team plan con seat **scontati** per lab accademici e nonprofit (la landing dice *"at no cost to start"*; il prezzo effettivo non è pubblicato). Bali Zero è un'agenzia commerciale: quel canale non ci riguarda, e l'accesso passa dal piano a pagamento che già abbiamo.

---

## 7. Fonti

- Annuncio: https://www.anthropic.com/news/claude-science-ai-workbench
- Overview docs: https://claude.com/docs/claude-science/overview
- Core concepts (sandbox, permission card, delegation, memoria): https://claude.com/docs/claude-science/core-concepts
- The reviewer / Specialists: https://claude.com/docs/claude-science/the-reviewer
- Artifacts e provenance: https://claude.com/docs/claude-science/artifacts
- Tools and environments (kernel, pacchetti, GPU): https://claude.com/docs/claude-science/tools-and-environments
- Connectors and skills (MCP custom, import da GitHub): https://claude.com/docs/claude-science/connectors-and-skills
- Dati e retention: https://claude.com/docs/claude-science/how-claude-science-works-with-your-data
- CLI: https://claude.com/docs/claude-science/command-line-settings
- Consumi e Admin API: https://claude.com/docs/claude-science/monitor-usage
- Changelog: https://claude.com/docs/claude-science/changelog
- Pagina prodotto: https://claude.com/product/claude-science
- Help center: https://support.claude.com/en/articles/16563838-get-started-with-claude-science
- Verdetti early user: https://www.the-scientist.com/early-verdicts-on-claude-science-faster-workflows-but-gaps-remain-74745
- Copertura stampa lancio: https://www.technologyreview.com/2026/06/30/1139987/claude-science-is-anthropics-newest-flagship-product/ · https://techcrunch.com/2026/06/30/anthropics-claude-science-bets-on-workflow-not-a-new-model-to-win-over-scientists/ · https://www.statnews.com/2026/06/30/anthropic-release-claude-science-ceo-dario-amodei/

---

## 8. Non verificato (TO VERIFY)

1. **Che l'output del 2026-09-09 venga da Claude Science.** Non ho modo di confermarlo dal web. La forma (report + CSV + patch + script generato) è compatibile con il modello artifact/provenance del prodotto, ma la provenienza va confermata guardando la cartella ricevuta.
2. **Limite "5 ore" oltre a quello settimanale.** I docs dichiarano solo *"standard weekly quota"* e *"same seat"*. La finestra 5-ore condivisa con Claude Code e Cowork compare solo su fonti secondarie non Anthropic.
3. **Disponibilità regionale in Indonesia.** Nessuna pagina trovata che elenchi paesi supportati o esclusi.
4. **Tetto di durata di un singolo run.** Documentato solo il timeout del kernel (~30 minuti di idle). Nessun cap dichiarato sulla sessione.
5. **Endpoint API o SDK "Claude Science".** Non trovato. Assenza di prova, non prova di assenza.
6. **Confronto ufficiale con Claude Code / Cowork / Agent SDK.** Nessuna pagina Anthropic trovata che li metta a confronto; l'unica relazione documentata è la quota condivisa.
7. **Se il nostro piano attuale ha Claude Science abilitato** e, su Team/Enterprise, se l'Owner l'ha attivato in Organization settings.
8. **Prezzo per uso commerciale oltre l'abbonamento.** Nessun listino trovato; le uniche cifre pubbliche sono i grant (fino a $30.000 in crediti per max 50 progetti selezionati, più fino a $2.000 di compute Modal, scadenza domande 15 luglio 2026) e il Team plan scontato per accademici/nonprofit (prezzo effettivo non pubblicato).
9. **Extra usage.** Codex sostiene che l'app possa spendere extra usage dopo conferma; nella pagina `monitor-usage` letta il 2026-09-11 non ho trovato la frase. Da confermare prima del pilot, e comunque da disattivare.
10. **Politica di sicurezza e ciclo di vita del pilot**: installazione pacchetti, connettori featured, gruppi di rete in uscita, auto-update, telemetria, retention e cancellazione degli artifact locali. Non coperti da questa nota; vanno scritti come profilo "locked-down" prima dell'installazione.

---

## Adversarial review

**Seat**: `codex` (GPT-5.6, `codex exec --sandbox read-only`), 2026-09-11, 18 finding, verdetto iniziale **REJECT**. Disposizione:

| # | Sev | Finding | Esito |
|---|---|---|---|
| 1 | P0 | `evidence_excerpt` nel CSV committato contraddice il boundary PII/OSINT di output (CLAUDE.md §4) | **Accolto** — colonna rimossa, `file:line` + hash, scanner fail-closed pre-commit, evidenza grezza in store locale ignorato (§6.3) |
| 2 | P1 | "ogni affermazione non verificata è TO VERIFY" era falso per 4 claim nel corpo | **Accolto** — etichette `FACT`/`INFERENCE`/`TO VERIFY` in linea |
| 3 | P1 | Team plan "gratuito" → Anthropic dice *discounted* | **Accolto** — verificato su product page e annuncio: "discounted seats", landing "at no cost to start", prezzo non pubblicato |
| 4 | P1 | "non esiste headless" → assenza di documentazione, non prova di impossibilità | **Accolto** — riformulato (§3, §6.5) |
| 5–7 | P1 | numeri del 9/9 e conteggi corpus non riproducibili né pinnati | **Accolto** — tutti `TO VERIFY`, richiesto manifest redatto con SHA e comando |
| 8 | P1 | permission card ≠ enforcement del PII: è access control sui path | **Accolto** — §4 riscritto, aggiunte le 5 misure compensative |
| 9, 14 | P1 | cadenza mensile proposta prima di verificare abilitazione, regione, costo, quota | **Accolto** — gate di decisione a 5 condizioni prima della cadenza (§6.4) |
| 10 | P1 | "batte Claude Code/Codex" asserito, non misurato | **Accolto** — §6.1 declassato a ipotesi con benchmark |
| 11 | P1 | "risk map" e riconciliazione plist scivolano nel runtime | **Accolto** — rinominati `STATIC-CANDIDATE-ONLY` |
| 12 | P1 | verifica "ogni riga" senza stima di costo | **Accolto** — una famiglia per volta, tetto volume, campionamento (§6.3) |
| 13 | P1 | kill criterion su sola precisione a 2 run | **Accolto** — aggiunti recall, soglie di campione, costo per finding, `INSUFFICIENT_EVIDENCE` |
| 15 | P2 | rete sandbox / connettori / storage vs compute confusi | **Accolto in parte** — corretti storage≠compute, allowlist package manager, directory connector via Anthropic; tabella data-flow completa rinviata |
| 16 | P2 | "stessa quota di Claude Code" è inferenza | **Accolto** — etichettato `INFERENCE` |
| 17 | P2 | manca run manifest | **Accolto** — §6.3 punto 6 |
| 18 | P2 | manca politica sicurezza/lifecycle | **Registrato** — §8.10, da scrivere prima dell'installazione |

Non accolto: nulla. La nota resta una ricerca con proposta; il pilot è subordinato al gate di §6.4.

