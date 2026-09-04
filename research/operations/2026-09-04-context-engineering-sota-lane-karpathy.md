# Report: Context Engineering secondo Karpathy e i thought-leader del settore

## 1. Andrej Karpathy

**Origine del termine (giugno 2025).** Il 27 giugno 2025 Karpathy pubblica su X il tweet che ha coniato/consacrato il termine "context engineering", proponendolo come sostituto di "prompt engineering". La sua tesi: "prompt" evoca nell'immaginario comune una breve istruzione digitata in una chat, mentre nelle applicazioni LLM industriali il vero lavoro è l'arte e scienza delicata di riempire la finestra di contesto con esattamente le informazioni giuste per il passo successivo — includendo descrizioni del task, few-shot examples, RAG, dati multimodali, tool e cronologia. ([x.com/karpathy](https://x.com/karpathy/status/1937902205765607626); ricostruzione via [MindStudio](https://www.mindstudio.ai/blog/software-3-0-explained-karpathy-context-window-ram-model-weights-cpu), [thecontextgraph.co](https://thecontextgraph.co/memos/context-engineering-2026-from-tweet-to-infrastructure))

**LLM come CPU / "LLM OS".** Nel framework più ampio di Karpathy (elaborato nel talk "Software 3.0", presentato in varie sedi nel 2025 e ripreso a Y Combinator/Latent Space) l'LLM non è un'applicazione ma un nuovo tipo di sistema operativo: i pesi del modello funzionano come CPU/processore fisso, il context window funge da RAM/working memory, e tutto ciò che sta fuori dal contesto (vector store, documenti, cronologia) è "disco" — storage passivo che richiede un'operazione esplicita di load per influenzare il ragionamento. Il prompting diventa quindi "programmazione": il context window è il "codice" scritto in linguaggio naturale che governa il computer neurale. ([Latent Space "Software 3.0"](https://www.latent.space/p/s3); [MindStudio](https://www.mindstudio.ai/blog/software-3-0-explained-karpathy-context-window-ram-model-weights-cpu); [aibuilderclub](https://www.aibuilderclub.com/blog/karpathy-software-3-0))

**"Anterograde amnesia".** Karpathy descrive gli agenti attuali come affetti da un problema simile all'amnesia anterograda: nessun consolidamento di conoscenza a lungo termine dopo il training, solo una memoria a breve termine limitata (il context window). Paragona questa condizione a un collega che non accumula mai competenze durature — un limite strutturale che rende la context window l'unico "luogo" dove l'agente può "ricordare" qualcosa entro una sessione. ([thegenios.com](https://thegenios.com/blog/karpathy-on-memory-and-context/))

**Sequoia Ascent 2026 (30 aprile 2026, dal suo blog personale).** Qui Karpathy formalizza la distinzione tra **vibe coding** ("alza il floor" — chiunque può costruire software senza capire la sintassi, modalità "prompt and pray") e **agentic engineering** ("alza il ceiling" — i professionisti vanno più veloci senza sacrificare qualità: spec design, diff review, eval loop, guardrail espliciti, gestione permessi). Sul contesto, la sua ricetta operativa condensata è: definire il contesto, definire gli strumenti, definire il feedback loop, definire i guardrail, e solo allora lasciare lavorare l'agente. Immagina anche uno scenario futuro di "computer completamente neurali" dove la rete neurale è il processo host e le CPU tradizionali diventano coprocessori. Nello stesso talk cita "context builders" come Gitingest e DeepWiki (Cognition) come strumenti che strutturano informazioni leggibili dagli agenti, e nota che l'HTML è poco parsabile per gli LLM — da cui l'emergere di formati alternativi tipo `llms.txt`. ([karpathy.bearblog.dev/sequoia-ascent-2026](https://karpathy.bearblog.dev/sequoia-ascent-2026/); riassunto [MindStudio](https://www.mindstudio.ai/blog/karpathy-sequoia-talk-5-predictions-agentic-engineering))

**Sviluppo recente (maggio 2026).** Il 19 maggio 2026 Karpathy ha annunciato di essersi unito al team di pre-training di Anthropic, guidato da Nicholas Joseph, con l'obiettivo dichiarato di costruire un gruppo che usi Claude per accelerare la ricerca sul pre-training stesso. Non risulta, nelle fonti raccolte, un nuovo scritto pubblico specifico sul context engineering datato dopo questo passaggio. ([TechCrunch](https://techcrunch.com/2026/05/19/openai-co-founder-andrej-karpathy-joins-anthropics-pre-training-team/); [Let's Data Science](https://letsdatascience.com/blog/karpathy-joins-anthropic-pretraining-team-may-19-2026))

**Autonomy slider.** Concetto correlato: dare agli utenti un cursore di autonomia variabile invece di un binario "manuale/automatico" — esempi citati sono Cursor (Tab → Cmd+K → Agent mode), Perplexity (search → research → deep research) e Tesla Autopilot (livelli 1-4). La logica: una demo richiede solo che *una* traiettoria funzioni, un prodotto richiede che funzionino *tutte*. ([MindStudio](https://www.mindstudio.ai/blog/karpathy-sequoia-talk-5-predictions-agentic-engineering))

---

## 2. Drew Breunig — tassonomia dei fallimenti del contesto

Fonte primaria: "How Long Contexts Fail" (22 giugno 2025) di Drew Breunig. ([dbreunig.com](https://www.dbreunig.com/2025/06/22/how-contexts-fail-and-how-to-fix-them.html))

| Fallimento | Definizione | Esempio empirico citato |
|---|---|---|
| **Context Poisoning** | Un'allucinazione o un errore entra nel contesto e viene ripetutamente ri-referenziato | Nel playthrough di Pokémon con Gemini 2.5, l'agente allucinava durante il gioco contaminando la sezione "goals" con stato di gioco errato, producendo strategie insensate ripetute verso un obiettivo irraggiungibile |
| **Context Distraction** | Il contesto diventa così lungo che il modello se ne sovra-affida, trascurando ciò che ha appreso durante il training | Gemini 2.5 Pro (1M+ token) oltre i 100k token tendeva a ripetere azioni dalla cronologia invece di sintetizzare nuovi piani; uno studio Databricks trova che la correttezza cala già intorno ai 32k token per Llama 3.1 405B, e prima ancora per modelli più piccoli |
| **Context Confusion** | Contenuto superfluo nel contesto viene usato dal modello e degrada la qualità della risposta | Berkeley Function-Calling Leaderboard: ogni modello testato peggiora quando riceve più di un tool disponibile; su GeoEngine (46 tool) un Llama 3.1 8B quantizzato fallisce con tutti i 46 tool ma riesce con solo 19 |
| **Context Clash** | Nuove informazioni/tool accumulati nel contesto entrano in conflitto con informazioni già presenti | Studio Microsoft/Salesforce su prompt "sharded" (distribuiti su più turni): calo medio del 39% nelle prestazioni; il modello o3 crolla da un punteggio di 98,1 a 64,1. I modelli fanno assunzioni premature nei primi turni e non si riprendono se imboccano la strada sbagliata |

**Mitigazioni** (elaborate nel seguito, "How to Fix Your Context", ripreso e sistematizzato anche da Simon Willison):
- **RAG (retrieval selettivo)** — invece di stipare tutto, recuperare dinamicamente solo ciò che serve
- **Tool loadout** — selezionare un sottoinsieme di tool attivi per il task corrente: la ricerca citata mostra che oltre ~20 tool disponibili confonde alcuni modelli
- **Context quarantine** — isolare sotto-contesti in thread dedicati separati (pattern usato da Claude Code e dal sistema multi-agente di ricerca di Anthropic)
- **Context pruning** — rimuovere attivamente informazioni superflue accumulate
- **Context summarization** — condensare un contesto lungo in un riassunto quando si avvicina ai limiti
- **Context offloading** — spostare informazioni fuori dal context window verso storage esterno (note tool, file `plan.md` negli agenti di coding)

Fonti: [dbreunig.com/2025/06/22](https://www.dbreunig.com/2025/06/22/how-contexts-fail-and-how-to-fix-them.html), [simonwillison.net/2025/Jun/29](https://simonwillison.net/2025/Jun/29/how-to-fix-your-context/)

---

## 3. Simon Willison e swyx/Latent Space

**Simon Willison** (27 giugno 2025, "Context engineering") sostiene che "context engineering" è un termine migliore di "prompt engineering" perché la sua definizione inferita è molto più vicina al lavoro reale — costruire con cura e competenza il contesto giusto per ottenere buoni risultati da un LLM — mentre "prompt engineering" nell'opinione pubblica è ridotto a "digitare cose in una chatbot". Willison cita anche Tobi Lutke (CEO Shopify), che descrive la pratica come l'arte di fornire tutto il contesto necessario perché il task sia plausibilmente risolvibile dall'LLM, e riprende la definizione di Karpathy. Nel post successivo "How to Fix Your Context" (29 giugno 2025) Willison sistematizza le mitigazioni di Breunig (vedi tabella sopra) e conclude che il contesto non è gratuito: ogni token influenza il comportamento del modello, e finestre di contesto ampie non giustificano negligenza nella gestione. ([simonwillison.net/2025/jun/27](https://simonwillison.net/2025/jun/27/context-engineering/), [simonwillison.net/2025/Jun/29](https://simonwillison.net/2025/Jun/29/how-to-fix-your-context/))

**swyx / Latent Space.** Non ho trovato un post/episodio dedicato esclusivamente a una posizione originale di swyx sul tema (le fonti indicano soprattutto il ruolo di Latent Space come piattaforma che ospita la discussione). Un episodio del podcast Latent Space (settembre 2025, con Alessio Fanelli e swyx come host) ha ospitato Lance Martin (LangChain) proprio su "Context Engineering for Agents", discutendo la distinzione prompt engineering vs context engineering e le sfide di gestire il contesto generato dalle tool call negli agenti — ma il contenuto specifico delle affermazioni di Martin non è stato recuperato in questa ricerca (fonte trovata solo come metadato di episodio, non fetchata). swyx descrive comunque il 2025 come "l'anno dei coding agent" e il 2026 come l'anno in cui i coding agent "rompono il contenimento" per fare tutto il resto, nel quadro più ampio "Software 3.0" che Latent Space ha adottato come cornice editoriale. ([podwise.ai — episodio](https://podwise.ai/dashboard/episodes/5181174), [latent.space/p/2026](https://www.latent.space/p/2026))

---

## 4. Manus — "Context Engineering for AI Agents: Lessons from Building Manus" (Yichao "Peak" Ji, 18 luglio 2025)

Fonte: [manus.im/blog](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus)

- **KV-cache hit rate = metrica #1.** Nel profilo computazionale di un agente in produzione il rapporto token input:output è ~100:1 in Manus. Con Claude Sonnet, i token in cache costano 0,30 USD/MTok contro 3 USD/MTok per quelli non cachati — un differenziale di **10x**. Pratiche per massimizzare il cache hit: prefix del prompt stabile, contesto **append-only** (mai modificare azioni/osservazioni passate), serializzazione deterministica dell'output (es. ordinamento stabile delle chiavi JSON), evitare timestamp nel system prompt.
- **Mask, don't remove.** Rimuovere dinamicamente dei tool a runtime invalida la KV-cache e può generare violazioni di schema quando azioni passate referenziano tool non più definiti. Manus mantiene stabile la definizione dei tool e maschera invece i logit dei token candidati durante il decoding, tramite una state machine context-aware con response prefill, per vincolare quali azioni sono disponibili senza toccare la cache.
- **Filesystem come contesto esterno.** Il filesystem è trattato come il "contesto definitivo": illimitato in dimensione, persistente per natura, direttamente operabile dal modello stesso (lettura/scrittura). Le strategie di compressione applicate al contesto in-memory restano reversibili — ad esempio si può scartare il contenuto di una pagina web mantenendone l'URL, in modo che possa essere ri-recuperato se necessario.
- **Recitation (todo.md).** Manus crea e aggiorna continuamente un file `todo.md` durante task complessi, "recitando" il piano/obiettivo verso la parte finale (più recente) del contesto. Questo contrasta il problema "lost-in-the-middle" e riduce il goal drift mantenendo il piano nell'area di massima attenzione del modello.
- **Keep the errors in.** Conservare errori e tracce fallite nel contesto (invece di ripulirle) permette al modello di aggiornare le proprie "credenze" interne e migliora la capacità di recovery — considerata un indicatore chiave di comportamento agentivo robusto.
- **Few-shot rut.** Contesti troppo uniformi (esempi ripetitivi, stessa struttura) inducono il modello a ripetere pattern ciecamente, causando drift o allucinazioni; la mitigazione è introdurre variazione strutturata controllata nella serializzazione, fraseologia e ordinamento.
- Nota di processo: Manus ha ricostruito il proprio framework agentico **quattro volte**, ogni volta scoprendo un modo migliore di plasmare il contesto — un dato che sottolinea quanto questa disciplina sia empirica e iterativa più che teorica.

---

## 5. Cognition — "Don't Build Multi-Agents" (Walden Yan, giugno 2025)

Fonte: [cognition.com/blog/dont-build-multi-agents](https://cognition.com/blog/dont-build-multi-agents) (redirect da cognition.ai)

Il principio cardine di Yan, riassunto senza citazione diretta estesa (nel rispetto del limite di una sola citazione breve per risposta): al centro dell'affidabilità di un agente sta il context engineering, e questo implica condividere non solo i messaggi individuali ma le tracce complete dell'agente tra sotto-agenti.

- **Il rischio dei sub-agenti a contesto parziale.** Yan illustra il problema con un esempio concreto: costruendo un clone di Flappy Bird tramite sub-agenti paralleli, un sub-agente fraintende il proprio sotto-task e inizia a costruire uno sfondo in stile Super Mario Bros invece che coerente col resto del gioco — perché non vede il contesto/le decisioni implicite prese dagli altri sub-agenti in parallelo.
- **Decisioni implicite in conflitto.** La formulazione chiave: azioni distinte portano con sé decisioni implicite, e decisioni in conflitto tra loro producono risultati scadenti (`"actions carry implicit decisions, and conflicting decisions carry bad results"` — questa è l'unica citazione diretta riportata in questo report, sotto le 15 parole, attribuita a Walden Yan/Cognition). Anche condividendo un contesto iniziale identico, sub-agenti che lavorano in parallelo senza visibilità reciproca sulle azioni altrui producono output visivamente/logicamente incoerenti (nell'esempio, uno stile grafico disomogeneo nel gioco).
- **Context compression con modelli dedicati.** Per task molto lunghi che eccedono comunque la finestra di contesto, Yan propone un LLM specializzato che comprima la storia di azioni e conversazione in dettagli chiave, eventi e decisioni — segnalando però esplicitamente che questo è difficile da ottenere bene, al punto da suggerire il fine-tuning di modelli più piccoli dedicati a questa sola funzione.

Il contrasto editoriale notato dalle fonti secondarie: Cognition pubblica "Don't Build Multi-Agents" più o meno nello stesso periodo in cui Anthropic dettaglia il proprio sistema di ricerca multi-agente — due filosofie architetturali opposte pubblicate in parallelo, entrambe però convergenti sul punto che il context engineering è la leva decisiva per l'affidabilità. ([Medium — recap del dibattito](https://medium.com/@maureesewilliams/the-agent-architecture-wars-why-two-ai-giants-completely-disagree-on-multi-agent-systems-d19a53364200))

---

## 6. Materiale 2026 più recente

- **Karpathy → Anthropic pretraining team (19 maggio 2026)**, già coperto sopra: passaggio di ruolo datato e verificato, non ancora accompagnato (nelle fonti raccolte) da un nuovo scritto pubblico dedicato al context engineering.
- **Karpathy, Sequoia Ascent (30 aprile 2026)**: la sintesi più recente e organica del suo pensiero su agentic engineering, con la formalizzazione vibe-coding/agentic-engineering e la ricetta "definisci contesto → tool → feedback loop → guardrail → lascia lavorare l'agente". ([karpathy.bearblog.dev](https://karpathy.bearblog.dev/sequoia-ascent-2026/))
- **Evoluzione del paradigma 2022-2026**: una fonte secondaria (bits-bytes-nn, aprile 2026) descrive una progressione in tre fasi — Prompt Engineering → Context Engineering → **Harness Engineering** — come lettura dello stato dell'arte più recente, dove l'attenzione si sposta dal "cosa mettere nel contesto" al "che impalcatura di strumenti/loop circonda l'agente". Non è chiaro dalle fonti se questo termine sia stato coniato o solo ripreso da Karpathy stesso. ([bits-bytes-nn.github.io](https://bits-bytes-nn.github.io/insights/agentic-ai/2026/04/05/evolution-of-ai-agentic-patterns-en.html))
- Un paper accademico del 2026, "Context Engineering 2.0: The Context of Context Engineering" (arXiv, ottobre 2025/2026), segnala che il campo sta già producendo tentativi di sistematizzazione teorica del termine coniato da Karpathy — non ho fetchato il full text, solo il titolo/abstract dai risultati di ricerca. ([arxiv.org/pdf/2510.26493](https://arxiv.org/pdf/2510.26493))

**Pagine non raggiungibili**: il fetch diretto del tweet originale di Karpathy (x.com) ha restituito HTTP 402 (Payment Required) — il testo del tweet è stato ricostruito solo tramite gli estratti riportati nei risultati di ricerca, non da lettura diretta della pagina.

---

## Principi operativi estraibili

- **Trattare il context window come RAM scarsa, non come un buffer infinito** — riempirlo solo con ciò che serve al passo successivo, non con tutto ciò che è disponibile (Karpathy).
- **Ottimizzare per il KV-cache hit rate come prima metrica di costo/latenza**: contesto append-only, prefix stabile, niente timestamp nel system prompt, serializzazione deterministica — differenziale di costo osservato 10x tra token cachati e non (Manus/Yichao Ji).
- **Mascherare i tool invece di rimuoverli dinamicamente**, per non invalidare la cache e non rompere la coerenza schema/azioni passate (Manus).
- **Usare il filesystem (o altro storage esterno persistente) come estensione del contesto**, mantenendo riferimenti recuperabili (es. URL) anche quando si scarta il contenuto pieno (Manus).
- **"Recitare" periodicamente l'obiettivo/piano** (es. un file todo.md aggiornato) per contrastare il "lost-in-the-middle" e il goal drift nei task lunghi (Manus).
- **Non ripulire gli errori dal contesto**: le tracce fallite sono segnale utile per la recovery del modello (Manus).
- **Evitare la monotonia strutturale (few-shot rut)** introducendo variazione controllata nella forma degli esempi, per prevenire drift da imitazione cieca del pattern (Manus).
- **Limitare il numero di tool attivi contemporaneamente** — oltre ~20 il degrado di performance è misurato empiricamente su più benchmark (Breunig/Willison).
- **Isolare sotto-contesti in thread dedicati (context quarantine)** quando i task sono davvero indipendenti, invece di sovraccaricare un unico contesto condiviso (Breunig, pattern usato da Claude Code).
- **Potare, riassumere e scaricare (pruning/summarization/offloading)** attivamente il contesto man mano che cresce, anche con finestre molto ampie — perché la correttezza cala ben prima del limite tecnico dichiarato (già a ~32k token su alcuni modelli, secondo lo studio Databricks citato da Breunig).
- **Nel multi-agente, condividere tracce complete, non solo messaggi**: le decisioni implicite di un agente devono essere visibili agli altri, o si generano incoerenze/conflitti (Cognition/Walden Yan).
- **Se serve comprimere una storia lunga per un sub-agente, farlo con un modello dedicato a quel solo compito**, accettando che è un problema difficile da risolvere bene, non una funzione banale (Cognition).
- **Distinguere "vibe coding" da "agentic engineering"**: la seconda richiede spec design esplicito, diff review, eval loop verificabili e guardrail — non semplice delega cieca all'agente (Karpathy, Sequoia Ascent 2026).
