---
date: 2026-04-25
type: sota-research
domain: notebooklm
sources: 42
---

# NotebookLM — State of the Art, April 2026

> Dossier operativo. Copre capability reali, integrazioni, API surface, pattern enterprise, limiti noti, orchestrazione multi-notebook, ruolo come backend agent, roadmap. Pensato per essere caricato in NotebookLM stesso come source.

## 1. Capabilities core 2026 — cosa NLM fa davvero oggi

Da ottobre 2024 (lancio Audio Overview) ad aprile 2026, NotebookLM è passato da "quadernino AI con podcast" a **piattaforma di research-to-artifact completa**, con un pattern ricorrente: ogni quarter Google aggiunge sia un nuovo artifact type sia un nuovo chat-engine upgrade.

### Sorgenti supportate (caps Q2 2026)

- **Formati**: PDF, DOCX, TXT, Markdown, CSV, PPTX, **EPUB** (nuovo 2026), Google Docs/Sheets/Slides via Drive, URL pubblici, YouTube con trascrizione auto o user-uploaded, audio (MP3, WAV, AAC, M4A, AIFF, Opus, 3GP, MP4, AMR, OGG, etc.) (Google Workspace Updates, marzo 2026; NotebookLM Help, aprile 2026).
- **Size limits per source**: 500.000 parole o 200MB, comune a tutti i tier (igmGuru, DigitalOcean).
- **Count limits**: Free 50 / Plus 300 / Pro 300 / Ultra 600 sources per notebook (Elephas, xda-developers). Total notebooks per user: 200 (Plus), 500 (Pro).
- **YouTube quirk**: solo trascrizione testuale importata, no frame analysis; richiede captions disponibili (auto o user-provided).
- **Audio sources**: trascrizione server-side automatica, poi trattate come text source per retrieval. Non c'è ancora speaker diarization persistita.

### Chat grounding + custom personas

- **Context window**: l'intero 1M-token Gemini context è esposto in NotebookLM chat da febbraio 2026, across tutti i plan (Jeff Su; WebProNews). Prima era troncato a ~125K.
- **Custom personas / Goals** (rollout 2026 Q1): 10.000 caratteri di custom instructions per notebook — 20× il limite precedente. Pattern standard: multi-persona (academic strict / creative strategist / skeptical reviewer) nello stesso prompt, il chat engine switcha tra loro (blog.google "Custom personas engine upgrade"; Chromeunboxed).
- **Conversation memory**: da marzo 2026 le chat sono auto-persistite per notebook, resumable. Questo elimina lo stateless-every-session vecchio.
- **6× multi-turn memory** rispetto a chat pre-Gemini-3.1 (febbraio 2026).

### Artifacts generati ("Studio")

Otto tipologie live ad aprile 2026:

1. **Audio Overview** — 4 formati: Deep Dive (podcast 2-host, default), Brief (bite-size), Critique (recensione), Debate (due voci contrastanti) (TechCrunch, 2025-09).
2. **Interactive Mode** — si "alza la mano" durante il podcast e si interrompono gli host via microfono (NotebookLM Help, 2026).
3. **Video Overview** — slide narrate + voiceover.
4. **Cinematic Video Overview** — marzo 2026, Gemini 3 + Nano Banana Pro + Veo 3, animazioni fluide documentary-style. 20/day cap su Ultra only. English only, 18+ only (blog.google, Fonearena 2026).
5. **Mind Map** — node graph interattivo sources↔concepts, utile con 100+ sources (NotebookLM Help).
6. **Briefing Doc / Study Guide / Timeline / FAQ** — pre-existing, consolidati nel pannello Studio (xda-developers).
7. **Flashcards + Quizzes** — con progress save "Got it / Missed it", shuffle, delete card, tutor mode "Learning Guide" (Chromeunboxed, 2025-09; Workspace Updates).
8. **Reports + Data Tables** — formato arbitrario via custom instructions, export PDF/PPTX/MD (exploreaitogether).

### Novità rispetto 2024 e 2025

| Capability | 2024 (lancio) | 2025 | 2026 Q1-Q2 |
|---|---|---|---|
| Audio Overview | 1 host 2-voice deep-dive fisso | +4 formati (Brief/Critique/Debate), 80 lingue | Interactive Mode stabile, tone customization |
| Video Overview | Assente | Narrated slide (luglio 2025) | Cinematic Veo 3 (marzo 2026) |
| Context window | ~125K | ~250K | **1M token full** (febbraio 2026) |
| Custom prompt | ~500 char | ~500 char | **10.000 char** persona |
| Sources cap (Free) | 50 | 50 | 50 (invariato) |
| Source formats | PDF/TXT/URL/YT | + audio/docx/md | + EPUB, Google Sheets, Drive native |
| Deep Research | Assente | **Lancio 2025-11-13** | File-type expansion, proof-driven |
| Studio export | PDF | PDF + PPTX (febbraio 2026) | PNG, Anki, Obsidian-compatible MD |

---

## 2. Gemini 3 Pro integration

- **Chat engine underlying**: Gemini 3.1 Pro è live dentro NotebookLM da febbraio 2026. Dichiara "50% jump in response quality" e "6× greater multi-turn conversation memory" vs engine pre-upgrade (felloai; webpronews).
- **Context window**: 1M token input / 64K output — identico al Gemini 3.1 Pro API standalone (llm-stats blog "Gemini 3.1 Pro Launch"). NotebookLM sfrutta l'intero 1M, non lo riduce. Questo è l'unico consumer product Google dove il 1M è esposto a Free tier.
- **Multimodal reasoning**: Gemini 3 Pro aziona sia chat che Cinematic Video Overview pipeline (Gemini 3 = "creative director", Nano Banana Pro = visual gen, Veo 3 = video rendering). Il reasoning visuale è quindi disponibile indirettamente — ma la chat NON consuma immagini dai PDF come vision input (solo OCR/text extraction), a differenza di Gemini app standalone.
- **Reasoning vs Gemini app**: dentro NLM il reasoning è gated su source-grounding (non può andare off-source). Dentro Gemini app puro, Gemini 3.1 Pro fa deep reasoning libero. Combo: Gemini app + linked NotebookLM (vedi §4) = reasoning libero + source-grounded retrieval on demand.

---

## 3. API / automation surface 2026

### Official API status (duale)

**Consumer NotebookLM**: NESSUNA API pubblica ad aprile 2026. Google NotebookLM X account ha confermato "one is in the works" ma zero waitlist, zero timeline (autocontentapi, web-clipper-for-notebooklm blog 2026).

**NotebookLM Enterprise**: HA API ufficiale via **Discovery Engine API**, con feature set ridotto ma reale:

- Endpoint: `https://ENDPOINT_LOCATION-discoveryengine.googleapis.com/v1alpha/projects/PROJECT_NUMBER/locations/LOCATION/notebooks/NOTEBOOK_ID/sources:batchCreate` (docs.cloud.google.com).
- Methods: `notebooks.create`, `notebooks.sources.batchCreate`, listing, delete. Supporta Google Drive IDs, plain text, URL, YouTube.
- Limitazioni critiche: **l'API Enterprise NON espone chat queries, NON espone Studio artifact generation, NON espone Deep Research**. È essenzialmente notebook management + source ingestion.
- Requisito organizzativo: non è self-serve developer, serve Google Cloud Enterprise contract, VPC-SC setup.

### Workaround non-ufficiali (community, undocumented)

- **`notebooklm-py`** (teng-lin, GitHub): Python SDK + CLI. Reverse-engineering del protocollo Google **batchexecute RPC con obfuscated method IDs**. v0.3.2 al 26 gennaio 2026. 5.6k+ stars. Esegue: notebook CRUD, source add, chat query, research agent trigger, sharing control, TUTTI gli Studio artifacts incluso audio/video/slides/quizzes/flashcards. **Capability UNDOCUMENTED**: espone "capabilities the web UI doesn't expose" — cioè il backend ha feature che non sono ancora esposte in UI. Fonte: [teng-lin/notebooklm-py CLAUDE.md](https://github.com/teng-lin/notebooklm-py/blob/main/CLAUDE.md).
- **`nblm-rs`** (K-dash, GitHub): Rust core + Python SDK per NotebookLM Enterprise. Più solido di notebooklm-py per Enterprise use cases.
- **`open-notebook`** (lfnovo): open-source clone, non proxy — usarlo come alternativa, non come API.
- **AutoContentAPI**: servizio commerciale che replica NotebookLM-style generation (audio overview in particolare) via API a pagamento.

### Legalità / ToS

- Google ToS applica, copyright policies strette. Non-affiliazione = rischio breakage (Google può cambiare batchexecute method IDs senza notice).
- **Per Workspace/Workspace Edu**: upload/query/response **non** usati per training, no human review. Safe per contesti regolati.
- **ToS scraping**: nessuna clausola esplicita contro reverse-engineering nel ToS consumer NotebookLM. La policy generica di Google `developers.google.com/terms` vieta "access the services through any automated means" — quindi notebooklm-py è grey area. Usalo per lavoro interno, evitalo per SaaS che rivendi a clienti esterni.

---

## 4. Share & Enterprise

### Sharing consumer

- Link sharing con permission Viewer/Editor per notebook. Shared notebooks conservano source list, chat è NON condivisa (ogni user ha la propria chat session).
- **Usage analytics** su notebook condivisi solo su Plus+ (conteggio view, unique viewer, tempo medio).

### Enterprise (lancio dicembre 2024, mature 2026)

- **VPC Service Controls**: data perimeter garantito, nessun traffico fuori dal tenant.
- **IAM granulare**: per-notebook role (owner/editor/viewer/commenter) con group inheritance da Workspace.
- **Audit logs**: log per user/timestamp/event/resource impactato, sia admin che user actions. Integrabile in SIEM via Cloud Logging export (docs.cloud.google.com; Baytech Consulting).
- **Public sharing DISABLED** automaticamente per Workspace Enterprise/Education tenants — non si può bypassare lato utente.
- **Compliance**: SOC 2, ISO 27001, GDPR, HIPAA (via BAA separata su Enterprise). Modello zero-training hard-coded.
- **Data residency**: controllabile via VPC-SC + regional data store (EU/US/Asia).

### Workspace core service

Da febbraio 2025 NotebookLM è **core Workspace service**, non più "additional service", con data protection enterprise-grade by default per tutti i paid Workspace. Attivazione per-OU via admin console (Workspace Updates blog).

### Gemini for Workspace integration

Da aprile 2026 (rollout 2026-04-08): Notebooks in Gemini app = knowledge base bidirezionalmente sync con NotebookLM. Aggiunti in un posto, appaiono nell'altro. Chat history "Chats from Gemini" persistita per notebook. Rollout: Google AI Ultra/Pro/Plus web prima, poi mobile, poi Workspace Enterprise/Education (blog.google "Notebooks in Gemini"; Notebookcheck).

---

## 5. Deep Research — native + pattern operativo

### Feature nativa NLM

Lanciata **13 novembre 2025**, rollout completo entro una settimana. Transizione da pure-RAG a "Agentic Researcher" (winbuzzer; medium/kombib).

Pipeline interna documentata:

1. **Query decomposition**: agente spezza la domanda in N sub-questions.
2. **Parallel execution**: cerca simultaneamente sul web PUBLIC (non solo nelle sources caricate) e nel corpus privato del notebook.
3. **Synthesis + gap analysis**: compila findings, identifica missing info, genera nuove query per i gap.
4. **Proof-driven output**: ogni claim ha citation al source (web o user-uploaded) con click-to-jump.

### Modes

- **Fast Research**: quick scan, 30-60s, output sintetico.
- **Deep Research**: 5-15 minuti, multi-step, output report lungo.

### Caps (aprile 2026)

- Free: N/A (non disponibile su Free tier).
- Plus/Pro: ~20-50 Deep Research sessions/day.
- Ultra: 200/day (xda-developers).

### Analogie e confronto con Perplexity / ChatGPT / You.com

| Dim | NotebookLM Deep Research | Perplexity Deep Research | ChatGPT Deep Research |
|---|---|---|---|
| Sources | web + **user corpus privato** | web pubblico only | web + file upload sessione |
| Citation density | alta, granular page-level | alta | media, claim-level |
| Output format | report + Studio artifact (podcast/video) | report conversational | report markdown |
| Web search depth | ~10-30 sources medi | 100+ sources | 50+ sources |
| Velocità | 5-15 min | 2-5 min | 10-30 min |
| Hallucination rate | ~13% (base NLM) | ~15-20% stimato | ~20-25% |
| Best for | corpus privato + contesto dominio | breaking news, broad scan | general analytical deep-dive |

**Verdetto operativo** (Tom's Guide, Elephas, OpenAIToolsHub test 2026): NLM vince quando la domanda tocca **corpus privato controllato**. Perplexity vince su "ultime notizie, what's trending". ChatGPT Deep Research vince su analytical framework building su web pubblico.

### Pattern "feed NLM → query" (agent loop)

Pattern enterprise comune 2026:
1. Agent esterno (Claude Code, Codex, Gemini CLI) fa ricerca web multi-step grezza.
2. Dump markdown consolidato upload come source in NLM dedicato.
3. NLM Deep Research ri-synthesizza con retrieval grounding cross-referencing.
4. Output finale = Studio artifact (briefing doc / audio overview) per stakeholder non-tech.

Questo pattern è descritto nei workshop di Hacks/Hackers 2026 AI x Journalism Summit (hackshackers.com) e nelle analisi di Jeff Su 2026.

---

## 6. Pattern avanzati community / enterprise 2026

### Legal discovery
- **"Case Notebook"** pattern (AltPraxis, LLRX, Attorney at Work): più attorneys uploadano depositions/pleadings/discovery, NLM produce chronology, contradictions map, theme extraction. Particularly forte su large document sets perché si può interrogare a ogni iteration senza re-uploadare.
- Workflow tipico: upload entire case file → generate Timeline + Briefing Doc → use chat per cross-referencing depositions → export to Word per court filing. Wisblawg (UW Madison Law 2025-06) descrive questo come "small hammer for big document problems".

### Academic literature review
- Semantic Scholar / Elicit per paper discovery → dump 30-50 PDF in NLM → Deep Research mode ri-synthesizza con "strict academic" persona → export study guide + FAQ. Pattern documentato in ListenLabs "AI Research Assistant" 2026 guide e The Effortless Academic.
- Trucco: usare un NLM separato per ogni sub-topic, poi un NLM "meta" che contiene i briefing doc dei precedenti come sources (gerarchia).

### Codebase Q&A
- Pattern "junior developer mental model" (xda-developers "I fed my entire codebase...", Tushar Kanjariya blog): upload tutti i file .ts/.py come plain text + README + folder-structure.md. Ask questions come faresti a un nuovo hire. Funziona meglio su projects piccoli/stabili (<200 files), non su monorepo attivi — serve refresh manuale dopo ogni merge.
- Security review pattern (javatechonline, clickup blog): NLM highlighta injection points, unsanitized inputs, dependency vulns, ma senza eseguire SAST — quindi complementare a Semgrep/Snyk, non replacement.

### Podcast personalization
- Audio Overview con custom persona ("parla come se fossi un professore di filosofia morale, tono socratic") + Interactive Mode. Usato in onboarding aziendale (Prezent review 2026) e K-12 tutoring (Google for Education expansion aprile 2026, Workspace Updates).

### Educational tutoring
- "Learning Guide" persona mode (lancio settembre 2025): tutor-style Socratic questioning su uploaded textbooks. Workspace Enterprise Education Plus expansion aprile 2026 rende feature disponibile a K-12 students sotto 18 (bloccata prima per safety). Flashcards + Quizzes con progress save e shuffle (Workspace Updates 2026-04).

### Investigative journalism
- Hacks/Hackers Summit 2026 (13-16 maggio): 9 workflow documentati. "Reverse-argument analysis" (carica whitepaper, chiedi persona "skeptical reviewer" di demolirlo). "Perspective shifts" (stesso corpus interrogato come policy analyst / affected community / opposing advocate). Quintype report 2026 descrive newsroom workflow: press release ingest → fact-check vs sources → tailored summary per beat reporter.

### Intelligence analysis
- Use case OSINT: upload dossier di report open-source, attiva Deep Research per web expansion cross-grounded, esporta timeline + mind map per briefing. Limite: pubblica cloud (non classified/TS). Per ambienti regolati serve NotebookLM Enterprise con VPC-SC e on-premise data store.

---

## 7. Limiti reali noti 2026

### Hallucination rate

- **~13% baseline** (vs ChatGPT ~40%), dato consolidato da studio ArXiv 2509.25498 "Not Wrong, But Untrue" 2025 e review Medium/Tisankan Jeyakumaar gennaio 2026.
- **Interpretive drift**: la modalità di hallucination NLM è diversa — non inventa entità/numeri, ma **aggiunge caratterizzazioni non supportate** dal source, trasforma opinioni attribuite in statement generali ("according to Smith" → "it is widely known that").
- **Audio Overview hallucination più alto** del text chat: report su Reddit r/notebooklm di "fabricated contract clauses", "invented script characters". Cause: truncation su long docs dove il pipeline audio-generation usa solo subset del corpus. LinkedIn Kassorla report "major hallucination in NotebookLM" 2025-03.
- **Trend 2026**: rate percepito in aumento. Hypothesis community: daily throughput caps → quality degradation on tier-free heavy users.

### Latency

- **Chat**: 2-8 secondi tipico, ~15s con full 1M context caricato.
- **Audio Overview Deep Dive**: 3-8 minuti per notebook medio.
- **Cinematic Video**: "a few minutes" dichiarato (Google blog), community measure ~5-12 min per video 2-3min.
- **Deep Research**: 5-15 minuti. Fast Research 30-90s.

### Source update freshness

- Google Drive sources: **auto-sync opt-in** (AutoSync extension + native da Q1 2026). Ma default è **stale** — il source è snapshotted at ingestion time. Questo è un gotcha classico.
- URL sources: refresh manuale. No auto re-crawl.
- YouTube: trascrizione ingest one-shot, nuovi commenti/revisioni video NON propagano.

### Retrieval quality

- Query rewriting / phrasing alternation: meno robusto di Perplexity. Se l'utente usa terminologia diversa da quella del source, retrieval miss (ArXiv analysis NotebookLM RAG).
- Multi-hop reasoning through graph relationships: NLM usa vector similarity (ScaNN backed), NON graph-RAG. Quindi "connect entity X in doc A to entity Y in doc Z via intermediate concept" può fallire.

### Response length / truncation

- Chat output soft-capped a ~8K token (non 64K del Gemini 3.1 Pro standalone). Per response lunghe serve "genera report" artifact.
- Audio Overview hard cap ~25-30 minuti dialogo.

### Fonti contraddittorie

- Handling ancora weak: tende a compromise-summary invece di flaggare il contradiction esplicitamente. Best practice: prompt esplicito "identify contradictions between sources and list them".

### Stateless → conversational

Fino a febbraio 2026 era stateless per chat session. Da marzo 2026 conversation memory persistente, ma **non trasferibile tra notebook**. Ogni NB ha il proprio chat history silo.

---

## 8. Multi-notebook orchestration

### Default: isolation hard-coded

NotebookLM è **architetturalmente isolato**: nessun cross-notebook retrieval, no global search, no cross-NB links, no shared entities across NBs (Medium/kombib "Isolated Notebooks", nlmtools.com, xda-developers).

### Workaround per cross-notebook reasoning

1. **Gemini attach multiple notebooks** (disponibile da dicembre 2025 web, gennaio 2026 mobile, febbraio 2026 Workspace): attacca fino a 10 NB a una singola chat Gemini. Gemini legge sources da tutti, cita, cross-referenzia. È il pattern Google-endorsed per ora.
2. **Notebook gerarchico** (meta-NB): crea NB "index" che contiene come sources i briefing doc dei NB sottostanti. Second-order reasoning ma loses granular citation al source originale.
3. **NotebookLM Tools Chrome ext**: feature "Copy/Move Sources Between Notebooks" per consolidation manuale.
4. **Via notebooklm-py**: `cross_notebook_query` tool (disponibile nel MCP wrapper, vedi §9).

### Quando splittare vs unificare

**Split in NB piccoli quando**:
- Sources per dominio >50 (avvicinando free cap) o >200 (Pro cap).
- Personas/goal molto diverse (legal review vs marketing vs R&D nello stesso corpus è rumore).
- Access control granulare (team A vede NB1, team B vede NB2).
- Retrieval precision > recall (corpus focalizzato = citation più precise).

**Unificare in un grande NB quando**:
- Cross-referencing forte (tutti i docs si parlano, e.g. depositions + pleadings + discovery dello stesso case).
- <300 sources (cap Pro).
- Single persona/goal stabile.
- Recall > precision (vuoi il modello sappia che esiste un documento X anche se la domanda non lo menziona).

### Cost/perf tradeoffs

Cap chat per-day sono per-user non per-notebook, quindi splittare NON riduce costi. Ma splittare **migliora precision retrieval** (meno dilution). Rule of thumb community 2026: max 100-150 sources per NB per mantenere citation quality alta.

---

## 9. NLM come backend di agent — quando ha senso

### NLM vs custom vector DB (Qdrant, pgvector, Weaviate)

| Criterio | NotebookLM | Custom Qdrant/pgvector |
|---|---|---|
| Setup | zero (web app) | alto (deploy, embedding pipeline) |
| Source cap | 50-600 per NB | illimitato |
| Formati | 8 + audio | qualunque (serve parser upstream) |
| Chat UI | built-in, polished | da costruire |
| Citation | automatiche, page-level | da implementare |
| Multi-hop / graph | no | possibile con graph RAG |
| Cost | subscription flat | infra + compute |
| API access | no (consumer), limited (Enterprise) | full control |
| Latency | 2-15s | tunable (1-5s possible) |
| Privacy/tenancy | Google cloud (Enterprise isolabile via VPC-SC) | on-prem/self-hosted possibile |
| Artifact generation | native (audio/video/slides/mind-map) | da integrare separatamente |

**Use NLM as backend quando**:
- Team non tech, serve UI user-friendly out-of-the-box.
- <300 sources stabili (post-research collection, non active indexing).
- Output = human-readable artifact (briefing, podcast) più che query programmatiche.
- Sufficienti budget Plus/Pro/Ultra, no custom infra da mantenere.

**Evita NLM as backend quando**:
- Retrieval programmatico high-throughput (>100 query/min).
- Custom embedding / re-ranker fine-tuned.
- Multi-tenancy con per-user vector namespace (ogni client = own DB).
- Need sub-second latency.
- Real-time ingestion (docs cambiano ogni minuto).

### Audio Overview come artefatto interno

Pattern 2026 Nuzantara-style: usare Audio Overview come **briefing auto per team**. Esempi concreti visti nei blog Quintype, Prezent, Department of Product:
- Monday briefing: NLM con sources = report settimana precedente → Audio Overview 10min → team lo ascolta in commuting.
- Onboarding nuovo hire: NB con company docs + process playbook → podcast 30min "your first week" via Learning Guide persona.
- Post-mortem incident: upload ticket+logs+runbook → Audio Overview "what went wrong, what we changed" → shareable link.

Questi pattern sfruttano il fatto che l'audio è **asimmetricamente meno skippable** del testo: il team lo "subisce" in background. Rischio: hallucination nel podcast più alta che in chat (vedi §7) — serve fact-check umano prima di shipping a clienti.

### MCP integration (scoperta Nuzantara)

Il wrapper **`notebooklm-mcp`** espone tool MCP-compatibili: `notebook_create`, `source_add`, `notebook_query`, `studio_create`, `research_start`, **`cross_notebook_query`**, `notebook_share_batch`. Questo è il layer che permette a un agent (Claude Code, Codex) di usare NLM come tool, orchestrando: ingestion → query → artifact download. Stato undocumented per Google ma community-supported.

---

## 10. Futuro prossimo — roadmap 2026 Q2-Q3

### Feature annunciate / rollout in corso

- **Lecture format** per Audio Overview (leaks fine 2025, rollout previsto Q2 2026): single-host structured monologue 30min, no banter. Target academic / formal enterprise briefing (Medium/jimmisound "Cognitive Engine Analysis").
- **Cinematic Video expansion**: non-English rollout, age 13+ access su Edu tenant, day cap raise (fonte: probable Google I/O 2026 annunci).
- **Slide editing full inline**: rollout parziale febbraio 2026, full parity con Google Slides features target Q3 2026 (Alai Blog 2026).
- **Consumer API**: "in the works" confermato, no timeline. Speculation: annuncio I/O 2026 maggio, rollout H2 2026 con pricing separato da Workspace.
- **Deep Research expansion**: più file types, proof-driven mode migliorato (Windows Forum 2026 analysis).
- **Personal Intelligence**: test in Labs (Revolgy 2026), pattern "NLM che impara dai tuoi uploads passati cross-notebook" — questo è ROMPEREBBE l'isolation hard rule, da osservare.

### Leaks / easter eggs

- Code strings ispezionati nel front-end (reddit r/notebooklm discoveries gennaio 2026): references a "collaboration mode" real-time multi-user editing, "agent mode" con tool-use, "canvas mode" (drawing/diagramming input).
- Android Police "5 features that would make it unstoppable" 2026 lista features attese: vero offline mode, source encryption client-side, graph-RAG layer, custom model selection (Gemini 3 Pro vs Flash), cross-notebook semantic search.

### Competitor response

- **Perplexity Spaces**: analogo NLM ma web-first, API pubblica, lancio Q1 2026.
- **ChatGPT Projects** con file upload + memory: competizione diretta, ma debole su audio/video artifact.
- **Claude Projects**: più debole su source count (~200K char) ma più forte su reasoning quality. Nessun audio artifact.
- **Microsoft Copilot Notebooks** (rumored Q3 2026 via M365): integrazione Teams/SharePoint + tenant-level, threat principale in enterprise regolato.

### Bet operativo 2026 H2

1. L'API consumer arriverà, probabile pricing usage-based ($ per artifact gen).
2. Consumer NLM e Gemini app si fondono sempre di più — "Notebook" diventa proto-project/agent container unificato.
3. Enterprise mantiene traiettoria separata, diverging feature set (security > novità).
4. Audio Overview resta the killer artifact, con lecture+debate modes che coprono 80% casi professionali.

---

## Fonti citate (42)

1. [Google Workspace Updates — New ways to customize NotebookLM, marzo 2026](https://workspaceupdates.googleblog.com/2026/03/new-ways-to-customize-and-interact-with-your-content-in-NotebookLM.html)
2. [DigitalOcean — What Is NotebookLM 2026](https://www.digitalocean.com/resources/articles/what-is-notebooklm)
3. [Jeff Su — NotebookLM in 2026: What Changed](https://www.jeffsu.org/notebooklm-changed-completely-heres-what-matters-in-2026/)
4. [Medium jimmisound — Cognitive Engine evolution 2023-2026](https://medium.com/@jimmisound/the-cognitive-engine-a-comprehensive-analysis-of-notebooklms-evolution-2023-2026-90b7a7c2df36)
5. [Elephas — NotebookLM Limits Free/Plus/Ultra](https://elephas.app/blog/notebooklm-source-limits)
6. [xda-developers — source limit biggest problem](https://www.xda-developers.com/notebooklms-source-limit-is-its-biggest-problem/)
7. [NotebookLM Help FAQ](https://support.google.com/notebooklm/answer/16269187?hl=en)
8. [igmGuru NotebookLM 2026](https://www.igmguru.com/blog/notebooklm)
9. [Google Cloud — NotebookLM Enterprise overview](https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/overview)
10. [Workspace Updates — Expanded NotebookLM Education Plus aprile 2026](https://workspaceupdates.googleblog.com/2026/04/expanded-notebooklm-capabilities-for-Education-Plus-and-Teaching-and-Learning-add-on-customers.html)
11. [Gemini release notes](https://gemini.google/release-notes/)
12. [blog.google — Notebooks in Gemini, aprile 2026](https://blog.google/innovation-and-ai/products/gemini-app/notebooks-gemini-notebooklm/)
13. [llm-stats — Gemini 3.1 Pro pricing/context](https://llm-stats.com/blog/research/gemini-3.1-pro-launch)
14. [Notebookcheck — Gemini+NLM deep integration](https://www.notebookcheck.net/Google-Gemini-gains-deep-NotebookLM-integration-in-new-update.1269924.0.html)
15. [blog.google — Chat in NotebookLM custom personas](https://blog.google/technology/google-labs/notebooklm-custom-personas-engine-upgrade/)
16. [Chromeunboxed — massive chat power boost Goals](https://chromeunboxed.com/notebooklms-chat-just-got-a-massive-power-boost-and-custom-goals-feature/)
17. [WebProNews — 1M Token context upgrade](https://www.webpronews.com/google-notebooklm-upgrade-1m-token-context-for-smarter-ai/)
18. [aigazine — NotebookLM 10000 char custom prompt](https://aigazine.com/industry/notebooklm-expands-custom-prompts-to-10000-characters--v)
19. [Google Cloud — API notebooks](https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/api-notebooks)
20. [Google Cloud — API sources batchCreate](https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/api-notebooks-sources)
21. [GitHub — teng-lin/notebooklm-py](https://github.com/teng-lin/notebooklm-py)
22. [notebooklm-py CLAUDE.md (undocumented features)](https://github.com/teng-lin/notebooklm-py/blob/main/CLAUDE.md)
23. [GitHub — K-dash/nblm-rs](https://github.com/K-dash/nblm-rs)
24. [AutoContentAPI — NotebookLM API alternative](https://autocontentapi.com/notebooklm-api)
25. [Google AI Developers Forum — NLM API thread](https://discuss.ai.google.dev/t/how-to-access-notebooklm-via-api/5084)
26. [Medium Baytech — NotebookLM Enterprise security](https://medium.com/google-cloud/notebooklm-enterprise-security-d49f70784621)
27. [Workspace Updates — NotebookLM core Workspace service 2025-02](https://workspaceupdates.googleblog.com/2025/02/notebooklm-and-notebooklm-plus-now-workspace-core-service.html)
28. [Google Workspace Admin — Turn NotebookLM on/off](https://knowledge.workspace.google.com/admin/users/access/turn-notebooklm-on-or-off-for-users)
29. [Baytech — B2B executive guide NotebookLM](https://www.baytechconsulting.com/blog/b2b-executive-guide-google-notebooklm)
30. [Tom's Guide — NotebookLM vs Perplexity deep research test](https://www.tomsguide.com/ai/i-tested-notebooklm-vs-perplexity-for-deep-research-with-5-difficult-prompts-heres-the-clear-winner)
31. [Winbuzzer — Deep Research launch 13 novembre 2025](https://winbuzzer.com/2025/11/13/googles-notebooklm-gets-deep-research-ai-and-broader-file-support-xcxwbn/)
32. [Medium kombib — Deep Research workflow](https://medium.com/@kombib/notebooklm-deep-research-enhancing-the-research-process-9d4e1ac55344)
33. [LLRX — NotebookLM for lawyers](https://www.llrx.com/2025/12/notebooklm-for-lawyers-ai-that-focuses-on-your-documents/)
34. [Attorney at Work — NotebookLM for lawyers small hammer](https://www.attorneyatwork.com/notebooklm-for-lawyers/)
35. [xda-developers — entire codebase into NotebookLM](https://www.xda-developers.com/entire-codebase-in-notebooklm-experiment/)
36. [ArXiv 2509.25498 — Not Wrong But Untrue LLM overconfidence](https://arxiv.org/html/2509.25498v1)
37. [Medium Tisankan — NotebookLM Hype real but limits](https://medium.com/@tisankan/the-notebooklm-hype-is-real-but-so-are-its-limits-9eee519ec3c1)
38. [Medium kombib — Isolated Notebooks two ways to connect](https://medium.com/@kombib/notebooklm-isolated-notebooks-two-ways-to-finally-connect-them-12485a79ac47)
39. [ArXiv 2504.09720 — NotebookLM LLM with RAG collaborative tutoring](https://arxiv.org/html/2504.09720v2)
40. [blog.google — Cinematic Video Overviews](https://blog.google/innovation-and-ai/products/notebooklm/generate-your-own-cinematic-video-overviews-in-notebooklm/)
41. [Fonearena — Cinematic Video Gemini 3 Veo 3](https://www.fonearena.com/blog/476852/notebooklm-cinematic-video-overviews-gemini-3-veo-3.html)
42. [Hacks/Hackers — 2026 AI x Journalism Summit program](https://www.hackshackers.com/summit-2026-program/)

---

*Dossier compilato 2026-04-25. Prossima revisione target Q3 2026 (post Google I/O 2026).*
