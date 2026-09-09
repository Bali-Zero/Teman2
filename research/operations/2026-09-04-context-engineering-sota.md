---
date: 2026-09-04
domain: operations
client_case: none — internal context-engineering study (sessione M5, mandato Zero)
adversarial_review: codex
sources: 3 lane di ricerca parallele (Karpathy/thought-leader · Anthropic ufficiale · repo SOTA), ~30 fonti primarie/secondarie fetchate; raw delle lane accanto a questo file (suffissi -lane-karpathy/-lane-anthropic/-lane-repos)
---

# Context Engineering SOTA — come i migliori gestiscono il contesto, e dove sta Nuzantara

> Mandato: Zero, 2026-09-04 — "verifica come i migliori al mondo gestiscono questo contesto,
> controlla i repo migliori e i migliori dev come Karpathy, e così studiamo il report".
> Innesco: pannello `/context` di una sessione M5 al 60% (297.6k/500k), overhead fisso ~137k.

---

## 0. Executive summary

1. **Il campo ha un consenso, ed è quasi unanime**: il context window è RAM scarsa (Karpathy), l'attention budget degrada al crescere dei token ("context rot", Anthropic), e la regola d'oro è *"the smallest possible set of high-signal tokens"*. Nessuna fonte SOTA difende il pattern "carica tutto sempre".
2. **Nuzantara è già SOTA su architettura** (skills progressive-disclosure, memoria index+corpi tipo Letta, subagent fan-out, stato durevole su file, budget armati da test) **ma anti-SOTA su un punto preciso**: i due CLAUDE.md. Sono l'anti-pattern che Anthropic chiama per nome — *"The over-specified CLAUDE.md"* — con il sintomo diagnostico esatto che documentiamo da mesi nelle cicatrici: *"se Claude ignora una regola presente, il file è troppo lungo e la regola si perde nel rumore"*.
3. **La leva più grande è una sola**: dieta dei due CLAUDE.md (misurati su disco: 78,7KB ≈ ~20-25k token stimati, circa metà dei 52k di memory files; il resto è superscar, MEMORY.md e corpi iniettati) spostando storia/rulings superati in file on-demand, con un budget armato da test come già facciamo per superscar (≤14KB) e MEMORY.md (≤24,4KB). Il resto (system tools 40k, MCP 18k) è harness o loadout, leve minori.
4. La disciplina delle sessioni corte con stato su file — che abbiamo già scoperto a nostre spese (scar 💸: 8 sessioni >24h = 48,6% della spesa) — è esattamente la best practice ufficiale: *"A clean session with a better prompt almost always outperforms a long session with accumulated corrections."*

---

## 1. Il consenso SOTA — i principi ad ampia convergenza

Tre corpi di evidenza (thought-leader, vendor ufficiale, repo open-source — con parziale sovrapposizione di fonti tra le lane) arrivano agli stessi principi di base; i disaccordi reali sono elencati sotto, non nascosti.

| Principio | Karpathy / thought-leader | Anthropic ufficiale | Repo SOTA |
|---|---|---|---|
| **Contesto = RAM scarsa, non buffer infinito** | LLM OS: pesi=CPU, window=RAM, resto=disco | attention budget, context rot (n² del Transformer) | correttezza cala già a ~32k token su alcuni modelli (Databricks via Breunig) |
| **Minimo set di token ad alto segnale** | "esattamente le informazioni giuste per il passo successivo" (tweet fondativo) | "smallest possible set of high-signal tokens" (testuale) | Aider: repomap 1k token di signatures, mai file interi |
| **Progressive disclosure / lazy load** | context builders (Gitingest, DeepWiki) | Skills: ~100 token finché non triggerate, <5k al trigger, risorse a costo 0 | OpenHands microagents trigger-based; SKILL.md a 3 livelli |
| **Stato durevole su FILE, non in window** | — | memory tool, pattern "initializer session" | Manus filesystem-as-context; Cline Memory Bank; MemGPT core/recall/archival |
| **Isolamento sub-task (quarantine)** | Breunig: context quarantine | subagent = riassunto 1-2k token contro decine di migliaia esplorati | LangGraph "Isolate"; pattern universale "fan-out pulito → report sintetico" |
| **Compaction gestita, mai subita** | pruning/summarization/offloading attivi | "il recall prima, la precisione poi"; /clear tra task | 7 agent, 7 formule di soglia esplicite (50%→99%); checklist pre-compaction = +49% copertura del summary (misurata come lunghezza, 1.643→2.455 token — non qualità end-task) |
| **Cache-stability del prefix** | Manus: KV-cache hit rate = metrica #1 (10x costo cached/uncached) | statico prima del dinamico, cache_control sull'ultimo blocco statico | Codex `_summary` anti-loop; append-only context |

### I 4 modi in cui il contesto fallisce (tassonomia Breunig, ormai canonica)

- **Poisoning**: un'allucinazione entra nel contesto e viene ri-referenziata (il nostro equivalente: famiglia scar #6 phantom citations).
- **Distraction**: il contesto lungo fa sovra-affidare il modello alla cronologia invece che al ragionamento (Gemini 2.5 oltre 100k ripeteva azioni invece di pianificare).
- **Confusion**: contenuto superfluo degrada la risposta — **ogni modello testato peggiora con >1 tool disponibile**; oltre ~20 tool il degrado è misurato (Berkeley FCL).
- **Clash**: informazioni accumulate in conflitto — prompt "sharded" su più turni: −39% medio, o3 crolla da 98,1 a 64,1.

### I punti di disaccordo (unico vero dibattito)

**Multi-agente sì/no.** Anthropic (multi-agent research system): orchestrator-worker batte il singolo Opus del 90,2% sulle ricerche breadth-first, MA costa ~15× i token e *"most coding tasks involve fewer truly parallelizable tasks than research"*. Cognition (Walden Yan, "Don't Build Multi-Agents"): sub-agenti a contesto parziale prendono decisioni implicite in conflitto — *"actions carry implicit decisions, and conflicting decisions carry bad results"*. La sintesi onesta: **fan-out per LETTURE indipendenti; scritture parallele solo se disaccoppiate e isolate (worktree/ownership), mai accoppiate sullo stesso stato condiviso** — che è esattamente la regola modus "fan-out for READS, funnel-in for WRITES". Su questo siamo già allineati al punto di equilibrio del dibattito.

Seconda tensione, minore: Manus dice "keep the errors in" (le tracce fallite migliorano la recovery), Anthropic dice `/clear` dopo >2 correzioni fallite. Si concilia distinguendo l'errore-segnale DENTRO un tentativo (tienilo) dagli approcci falliti accumulati TRA tentativi (pulisci e riprompta).

---

## 2. I tre corpi di evidenza (sintesi; raw nei file di lane accanto)

### 2a. Karpathy (e la traiettoria 2025→2026)

- **27 giu 2025**: tweet fondativo — "context engineering" sostituisce "prompt engineering"; l'arte di riempire la finestra con esattamente ciò che serve al passo successivo.
- **Software 3.0 / LLM OS**: window=RAM, pesi=CPU, storage esterno=disco che richiede load esplicito. Gli agenti soffrono di "anterograde amnesia": la window è l'unico luogo dove ricordare entro la sessione.
- **Sequoia Ascent (30 apr 2026)**: distinzione **vibe coding** (alza il floor, "prompt and pray") vs **agentic engineering** (alza il ceiling: spec design, diff review, eval loop, guardrail, permessi). Ricetta: definisci contesto → tool → feedback loop → guardrail → poi lascia lavorare l'agente. Autonomy slider, non binario.
- **19 mag 2026**: Karpathy entra nel team pre-training di Anthropic. Nessun nuovo scritto pubblico sul context engineering dopo questa data (verificato dalla lane).
- Tendenza 2026 segnalata (fonte secondaria): Prompt Engineering → Context Engineering → **Harness Engineering** — l'attenzione si sposta all'impalcatura di strumenti/loop attorno all'agente.
- **Manus (Yichao Ji)** — il post più operativo del campo: KV-cache hit rate metrica #1 (input:output ~100:1, 10x il differenziale cached/uncached); append-only, mai modificare il passato; **mask don't remove** (mascherare i logit dei tool, mai rimuoverli — invalida la cache); filesystem come contesto esterno reversibile (scarta il contenuto, tieni l'URL); **recitation** (todo.md ri-scritto verso la coda del contesto contro il lost-in-the-middle); **keep the errors in** (le tracce fallite migliorano la recovery); evitare il few-shot rut. Manus ha ricostruito il framework 4 volte — disciplina empirica, non teorica.

### 2b. Anthropic ufficiale (fetch diretto delle pagine, 2026)

- **CLAUDE.md**: test riga per riga — *"Would removing this cause Claude to make mistakes? If not, cut it."* Escludere: tutto ciò che è derivabile dal codice, info che cambiano spesso, tutorial, descrizioni file-per-file. **"IMPORTANT" su UNA sola riga** — enfasi diffusa = zero enfasi. Anti-pattern nominato: over-specified CLAUDE.md → *"Ruthlessly prune… or convert it to a hook."* (Il principio "hooks enforce what prompts cannot" ce l'abbiamo già — CLAUDE.md §7.)
- **Skills vs CLAUDE.md**: CLAUDE.md è pagato OGNI sessione → solo regole sempre applicabili; il resto in skill on-demand (~100 token/skill finché non triggera, <5k al trigger, risorse a costo 0).
- **Sessioni**: `/clear` tra task non correlati; >2 correzioni fallite sullo stesso tema = contesto avvelenato → `/clear` + riprompt. `/compact <istruzioni>` per controllo fine; CLAUDE.md può istruire la compaction ("preserva sempre la lista dei file modificati e i comandi di test"). `/btw` per domande usa-e-getta.
- **Subagent**: "context is your fundamental constraint, use subagents to keep research out of it"; review adversariale in contesto fresco (solo diff + criteri, mai il ragionamento che ha prodotto la modifica) — il nostro generator≠grader.
- **Memory tool** (API): pattern initializer-session — scrivi progress-log + checklist PRIMA del lavoro, ogni sessione riparte da lì; compaction server-side + memory client-side insieme.
- **Caching 2026** (fetch diretto): minimo cacheable 512 token su Opus 5/Fable 5 (0.1× input alla lettura); max 4 breakpoint; TTL 5min/1h; lookback 20 blocchi.
- Caveat dichiarato dalla lane: sezione OpenAI/Google solo da ricerca aggregata (AGENTS.md ora sotto Linux Foundation/Agentic AI Foundation; GEMINI.md = concatenazione eager gerarchica, NON lazy).

### 2c. Repo SOTA (meccanismi, con numeri)

- **Aider**: repomap tree-sitter + PageRank biased sulla chat — solo signatures, budget default **1.000 token**, fitting per binary search. (Il nostro `build_repomap.sh` dichiara la stessa strategia.)
- **SWE-agent (Princeton, NeurIPS 2024)**: l'interfaccia conta quanto il prompt (ACI). File viewer a **100 righe** (ottimo empirico, non "tutto il file"); search che elenca solo i file con match; messaggi espliciti su output vuoto. +64% relativo vs shell-only.
- **OpenHands**: event stream append-only + Condenser — trigger a **120 eventi**, preserva i primi 4, target 60 post-condensazione, eventi "dimenticati" tracciati (`forgotten_event_ids`), mai cancellati. Senza condenser il costo scala quadraticamente, con condenser linearmente.
- **MemGPT/Letta**: core memory (sempre in window, self-editing) / recall (storico ricercabile) / archival (knowledge strutturata su vector DB) — paging OS-like via tool call. **La nostra MEMORY.md (indice) + corpi .md è questo pattern.**
- **Soglie di auto-compact a confronto** (7 agent): Gemini CLI ~50% · Roo ~86-92% · **Claude Code ~89%** (`window − min(maxOutput,20k) − 13k`) · Codex ~90% · OpenCode ~96-99% · OpenHands event-based. Claude Code ha 5 difese (microcompact, clearing tool output, summarization, cache reuse, compact manuale).
- **Costo compaction misurato**: ~$0.40 su 125k token (≈21 turni cache-hit); checklist pre-compaction su 7 categorie (path, decisioni, errori, firme, test, env var, task) = **summary +49% più ricco** (misurato come lunghezza/copertura, non qualità end-task) a costo trascurabile. "Il modello è al suo punto meno intelligente proprio durante l'auto-compact" — gestirla prima, mai subirla.
- **Cline Memory Bank**: file markdown letti a inizio di OGNI task (activeContext.md, progress.md) — persistenza dichiarativa cross-sessione.

---

## 3. Nuzantara vs SOTA — la diagnosi sul pannello reale

Pannello misurato (sessione M5, 500k window): overhead fisso ~137k (27,5%) = system prompt 7k + system tools 40k + MCP 18k + custom agents 10,3k + **memory files 52k** + skills 10k; messages 161k; autocompact buffer 33k.

### Dove siamo GIÀ allineati alle pratiche documentate dalle fonti

| Pratica SOTA | Implementazione Nuzantara | Giudizio |
|---|---|---|
| Progressive disclosure | skills corner (`/bot`, `/kbli-navigator`, …), skill-catalog on-demand | ✅ pattern Skills fatto bene |
| Memoria a livelli (Letta) | MEMORY.md indice ≤24,4KB + corpi .md + MEMORY_ARCHIVE | ✅ core/recall/archival de facto |
| **Budget armato da TEST** | superscar ≤14KB (`test_superscar_budget.py`), MEMORY.md cap misurato | ✅ pratica assente in TUTTE le fonti esaminate (nessuna impone il budget via CI) |
| Stato durevole su file | PENDING-ARMS ledger, spec su disco, handoff via file (ruling 💸) | ✅ = memory tool pattern |
| Quarantine/subagent | fan-out READS, funnel-in WRITES; worktree per agent | ✅ = punto di equilibrio Anthropic/Cognition |
| Recitation (Manus) | recap-on-wake, dense recap block di modus | ✅ |
| Keep the errors in | cicatrici/scar system — gli errori sono LA memoria | ✅ filosoficamente identico |
| Hooks > prompt | CLAUDE.md §7 "hooks enforce what prompts cannot" | ✅ = "convert it to a hook" ufficiale |
| Repomap | `build_repomap.sh` tree-sitter, inject se <30min | ✅ = Aider |
| Sessioni corte + stato via file | scar 💸 (ginocchio ~200 richieste, splitta) | ✅ già pagato col sangue, ora confermato ufficiale |

### Dove DIVERGIAMO dal consenso

1. **I due CLAUDE.md violano il test del taglio-riga.** Sono la parte dominante dei 52k di memory files e contengono esattamente ciò che la guida ufficiale esclude: **storia** (catene di ruling superseded tenute inline: 2026-07-25 → 08-19 → 08-20 sul modello del gate, tre blocchi per dire "oggi è Opus 5 xhigh"), **duplicazioni** (i quirk della famiglia 5 compaiono sia nel CLAUDE.md globale sia in quello repo, quasi verbatim), **info che cambiano spesso** (roster seats, stati "PENDING/probation", snapshot datati), **narrativa lunga** dove servirebbe una riga + puntatore. Il sintomo previsto dalla diagnostica ufficiale — regole ignorate perché sepolte nel rumore — è documentato nelle nostre stesse cicatrici.
2. **L'enfasi è satura.** Decine di righe 🔴/HARD RULE/⚡ in entrambi i file: per la guida ufficiale questo equivale a zero enfasi ("if you emphasize many lines, none of them stands out").
3. **Ogni subagent ri-paga l'iniezione.** Superscar lo dice da solo ("ciò che aggiungi lo paga tutta la flotta, per sempre") — ma il principio vale per TUTTO il blocco iniettato, non solo superscar: 52k × ogni subagent × ogni sessione.
4. **Tool loadout non gestito.** 40k system tools + 18k MCP sempre caricati; la ricerca misura degrado oltre ~20 tool attivi. I deferred tools mitigano già in parte; i 4 MCP server (Drive, Chrome, knowledge, context7) pesano anche quando la sessione non li usa.
5. **Compaction subita, non istruita.** Nessuna istruzione di compaction nei CLAUDE.md; la checklist pre-compaction (7 categorie) è un +49% di qualità misurato a costo quasi nullo.

---

## 4. Raccomandazioni (in ordine di leva, da studiare — nessuna eseguita)

| # | Azione | Leva | Effort | Note |
|---|---|---|---|---|
| R1 | **Dieta dei due CLAUDE.md** col test ufficiale riga-per-riga ("la rimozione causerebbe errori?"). Storia/ruling superseded → un file `RULINGS.md` (o memory files) on-demand; nel CLAUDE.md resta solo lo stato VIGENTE in 1 riga + puntatore. Target: −50-60% dei due file (misurati 78,7KB ≈ ~20-25k token) | ~10-15k token/sessione stimati, × ogni subagent | Medio (1 sessione dedicata, Gear 3: tocca doctrine) | Il precedente interno esiste già: superscar è nato così (99 scar → 10 famiglie ponte). Stesso gesto, applicato ai CLAUDE.md |
| R2 | **Budget armato da test sui CLAUDE.md** (pattern `test_superscar_budget.py`): cap in byte, CI rossa se sfora | Impedisce la ricrescita — la dieta senza budget si rimangia | Basso | Senza R2 la dieta si rimangia (precedente interno: MEMORY.md ha un cap perché la coda veniva scartata in silenzio quando cresceva) |
| R3 | **De-duplicare i blocchi gemelli** globale↔repo (quirk famiglia 5, roster, cost constraint): una sola casa + puntatore | ~5-8k (stima, non misurata) | Basso | Attenzione: il globale è un HOME-fork dichiarato (3 copie, scar 📄🍴) — la cura va applicata a tutte le copie |
| R4 | **Istruzioni di compaction in CLAUDE.md** ("When compacting, always preserve: file modificati, comandi test, decisioni, PENDING-ARMS aperti") | summary più ricco (+49% copertura misurata altrove; proxy di lunghezza, non di qualità), costo ~0 | Minimo | Una riga |
| R5 | **Razionalizzare l'enfasi**: 🔴 riservato alle sole righe che governano azioni distruttive (la regola c'è già in MEMORY.md ma non è applicata ai CLAUDE.md) | Restituisce significato all'enfasi residua | Basso | |
| R6 | **MCP loadout per-sessione**: valutare quali dei 4 server servono di default su M5 (Drive? context7?) e spostare gli altri su attivazione esplicita | ~8-12k (stima sui 18k MCP del pannello; il benchmark sul degrado riguarda il numero di TOOL attivi, non di server) | Basso | Deferred tools già mitigano; qui si taglia la definizione |
| R7 | Mantenere e rinforzare ciò che è già SOTA: sessioni corte + stato via file, fan-out READS, budget armati. **Nessun cambio.** | — | — | Il report conferma le scelte, non le smentisce |

**Ordine consigliato**: R2 prima di R1 (arma il budget, poi dimagrisci dentro il budget — altrimenti è una dieta senza bilancia). R3-R5 dentro la stessa PR di R1. R6 indipendente.

## §Solo-operatore

- Decidere SE e QUANDO eseguire R1-R6 (tocca doctrine = Legge 5; R1 è un cambio di CLAUDE.md, self-doctrine → PR con review, mai auto-merge disinvolto).
- Il CLAUDE.md globale (`~/.claude/CLAUDE.md`) è fuori repo e HOME-fork su 3 macchine: l'allineamento delle copie è gesto di flotta da pianificare.

## Limiti di questo report

- Le sezioni OpenAI/Google della lane Anthropic derivano da ricerca aggregata, non da fetch delle pagine primarie (dichiarato dalla lane).
- Il tweet originale di Karpathy non è fetchabile direttamente (X → HTTP 402); testo ricostruito da fonti secondarie concordi.
- I numeri delle soglie di compaction dei 7 agent provengono da un'unica fonte comparativa (codex.danielvaughan.com, apr 2026) — buona ma singola.

## Fonti principali

- Karpathy: x.com/karpathy/status/1937902205765607626 · karpathy.bearblog.dev/sequoia-ascent-2026 · latent.space/p/s3
- Breunig: dbreunig.com/2025/06/22/how-contexts-fail-and-how-to-fix-them.html · simonwillison.net/2025/Jun/29/how-to-fix-your-context/
- Manus: manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus
- Cognition: cognition.com/blog/dont-build-multi-agents
- Anthropic: anthropic.com/engineering/effective-context-engineering-for-ai-agents · code.claude.com/docs/en/best-practices · anthropic.com/engineering/built-multi-agent-research-system · platform.claude.com/docs (memory-tool, agent-skills, prompt-caching)
- Repo: aider.chat/2023/10/22/repomap.html · swe-agent.com/latest/background/aci · docs.openhands.dev/sdk/arch/condenser · letta.com/blog/agent-memory · langchain.com/blog/context-engineering-for-agents · codex.danielvaughan.com/2026/04/10/context-compaction-showdown-coding-agents/

*Raw completi delle 3 lane: file gemelli `2026-09-04-context-engineering-sota-lane-{karpathy,anthropic,repos}.md` in questa directory.*

## Adversarial review

Seat: **codex** (GPT-5.6, cross-family, sonda live PONG ~39s prima del dispatch; sandbox read-only, effort high). 9 finding, disposizione:

| # | Finding | Verdetto | Disposizione |
|---|---|---|---|
| 1 | "+49% qualità summary" — la fonte misura LUNGHEZZA (1.643→2.455 token), non qualità | CONFERMATO | Rietichettato in tutte le occorrenze come copertura/lunghezza |
| 2 | Target "52k→20-25k / −30k a sessione" non derivato | CONFERMATO | Misurato su disco: i due CLAUDE.md = 78.741B ≈ ~20-25k token (≈ metà dei 52k); leva corretta a ~10-15k stimati |
| 3 | R3 ~5-8k senza provenance (quote del finding imprecisa, punto valido) | PARZIALE | Etichettato "stima, non misurata" |
| 4 | Attribuzione "IMPORTANT su una riga sola" sarebbe falsa | **REFUTATO con prova** | La frase "If you emphasize many lines, none of them stands out" esiste VERBATIM nella pagina Anthropic, ri-fetchata in questo turno dal gate. Il refuter ha allucinato un negativo (classe W65) |
| 5 | "TUTTE le fonti convergono" contraddetto dal testo stesso | CONFERMATO | Header ammorbidito; aggiunta la seconda tensione (errors-in vs /clear) con conciliazione |
| 6 | Stima MCP ~8-12k: il benchmark riguarda i TOOL, non i server | CONFERMATO | Etichettata stima + scope del benchmark precisato |
| 7 | "Senza R2, R1 dura 3 mesi" fabbricato | CONFERMATO | Sostituito con il precedente interno non numerico (cap MEMORY.md) |
| 8 | "mai scritture accoppiate" sovra-esteso | CONFERMATO | Precisato: scritture parallele ok se disaccoppiate/isolate (worktree), mai sullo stesso stato condiviso |
| 9 | "SOTA/oltre SOTA" senza benchmark esterno | CONFERMATO | Riformulato come "allineato alle pratiche documentate dalle fonti esaminate" / "pratica assente in tutte le fonti" |

Bilancio: 7 confermati (curati nel testo), 1 parziale, 1 refutato con prova indipendente. Il round dimostra entrambe le metà della disciplina: il generator sbaglia (etichette e stime non marcate), e anche il refuter allucina (finding 4) — la verifica indipendente del gate resta non delegabile.
