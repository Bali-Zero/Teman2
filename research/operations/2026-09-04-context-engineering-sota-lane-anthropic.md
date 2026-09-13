---
date: 2026-09-04
domain: operations
client_case: none — raw lane capture for 2026-09-04-context-engineering-sota.md
adversarial_review: exempt-raw-lane-capture-reviewed-via-synthesis
---

# Guidance ufficiale su context management per agenti (Anthropic + confronto OpenAI/Google)
(lane research-anthropic, 2026-09-04)

## 1. Anthropic — "Effective context engineering for AI agents"
Fonte: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents

**Framing**: context engineering è l'evoluzione del prompt engineering — non "trovare le parole giuste" ma "quale configurazione di contesto è più probabile che generi il comportamento desiderato". Principio guida (testuale): **"the smallest possible set of high-signal tokens that maximize the likelihood of your desired outcome"**.

**Attention budget / context rot**: gli LLM hanno un "attention budget" limitato che si esaurisce a ogni token aggiunto. "Context rot" = la capacità di recuperare accuratamente informazioni degrada al crescere dei token. Causa architetturale: relazioni n² tra token nel Transformer → tensione naturale tra dimensione del contesto e focus dell'attenzione.

**System prompt — "right altitude"**: zona Riccioli d'oro tra (a) troppo **brittle** (logica fragile hardcodata) e (b) troppo **vago** (guida alto-livello senza segnali concreti). Operativo: partire da un prompt minimalista sul modello migliore, aggiungere istruzioni SOLO in risposta a fallimenti osservati, mai preventivamente.

**Retrieval: just-in-time vs pre-loading**: JIT = identificatori leggeri (path, query, link) + caricamento dinamico via tool, invece di pre-caricare tutto. Ibrido consigliato: alcuni dati anticipati per velocità + libertà di esplorazione autonoma.

**Tre tecniche per task long-horizon**:
1. **Compaction**: riassumere la cronologia e reinizializzare. L'arte è nella selezione — prima massimizzare il recall, poi iterare sulla precisione. Tecnica leggera: "clearing tool results" (eliminare output grezzi dei tool consumati).
2. **Structured note-taking**: note persistenti fuori dalla window (Claude Code to-do list; "Claude Pokémon" tally su migliaia di step). Memory tool in beta pubblica.
3. **Sub-agent architectures**: agenti con context puliti per task focali; ogni subagente esplora decine di migliaia di token ma restituisce **1.000-2.000 token** di riassunto.

## 2. Anthropic — "Best practices for Claude Code" (versione corrente 2026)
Fonte: https://code.claude.com/docs/en/best-practices (redirect 308 dal post aprile 2025)

**Vincolo fondante (testuale)**: "Most best practices are based on one constraint: Claude's context window fills up fast, and performance degrades as it fills." Un singolo debugging può generare "tens of thousands of tokens". Usare `/context` per ispezionare, status line per tracciare.

**CLAUDE.md — raccomandazioni esatte**:
- Generato con `/init`, raffinato nel tempo. "Keep it short and human-readable".
- **Test di inclusione riga per riga**: *"Would removing this cause Claude to make mistakes? If not, cut it."*
- ✅ Include: bash command non indovinabili, code style non-standard, istruzioni testing, repo etiquette, decisioni architetturali specifiche, quirk env, gotcha non ovvi.
- ❌ Exclude: derivabile dal codice, convenzioni standard, doc API dettagliata (linkare), info che cambiano spesso, tutorial lunghi, descrizioni file-per-file, pratiche ovvie.
- **Diagnostica**: Claude ignora una regola presente → file troppo lungo, la regola si perde nel rumore. Claude chiede cose già scritte → fraseggio ambiguo.
- Enfasi "IMPORTANT" SOLO su una riga alla volta: "If you emphasize many lines, none of them stands out".
- Trattato come codice: "review it when things go wrong, prune it regularly, test changes by observing whether Claude's behavior actually shifts". `/doctor` propone tagli per contenuto derivabile.
- Import con `@path/to/import`.
- **Anti-pattern nominato**: "The over-specified CLAUDE.md" — troppo lungo ⇒ Claude ignora metà del contenuto. Fix: "Ruthlessly prune. If Claude already does something correctly without the instruction, delete it or convert it to a hook."

**Skills vs CLAUDE.md**: CLAUDE.md caricato OGNI sessione → solo cose sempre applicabili. Conoscenza di dominio/workflow occasionali → skills on-demand.

**/clear e /compact**:
- Auto-compact vicino ai limiti, preservando codice e decisioni.
- `/clear` **frequente tra task non correlati**.
- `/compact <istruzioni>` per controllo fine. `Esc+Esc`/`/rewind` per riassumere solo una parte.
- CLAUDE.md può istruire la compaction (es. "When compacting, always preserve the full list of modified files and any test commands").
- `/btw` per domande usa-e-getta fuori cronologia.
- **>2 correzioni fallite sullo stesso problema → contesto "polluted"** → `/clear` + riprompt. "A clean session with a better prompt almost always outperforms a long session with accumulated corrections."

**Subagents**: "Since context is your fundamental constraint, use subagents to keep research out of it." Riportano solo riassunti. Anche per adversarial review (reviewer fresh-context vede solo diff + criteri).

**Multi-Claude workflow**: worktree paralleli; cross-session messaging; Writer/Reviewer su due sessioni (context fresco = review non biased); `/batch` fan-out 5-30 subagent con worktree+PR ciascuno.

**Anti-pattern elencati**: kitchen sink session · correcting over and over (>2 → /clear) · over-specified CLAUDE.md · trust-then-verify gap · infinite exploration (→ scope narrow o subagent).

## 3. Anthropic — "How we built our multi-agent research system"
Fonte: https://www.anthropic.com/engineering/built-multi-agent-research-system

**Orchestrator-worker**: lead coordina, delega a subagenti paralleli con istruzioni dettagliate (obiettivo, formato output, guida tool/fonti, confini).

**Token economics**:
- Single-agent: **~4×** token di una chat. Multi-agente: **~15×**.
- **"token usage alone explains 80% of the variance in performance"**.
- Multi-agente (Opus 4 lead + Sonnet 4 subagenti) **supera un singolo Opus 4 del 90.2%** (su research eval).

**Quando conviene**: breadth-first parallelizzabile, alto valore, ricerche oltre una singola window. **Quando NO**: contesto condiviso/dipendenze forti — "most coding tasks involve fewer truly parallelizable tasks than research."

## 4. Anthropic — Memory tool e Context editing (docs API)
Fonte: https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool

**Memory tool** (Claude 4+): client-side, operazioni file (`view`, `create`, `str_replace`, `insert`, `delete`, `rename`) sotto `/memories`. JIT context retrieval: l'agente registra ciò che apprende e lo rilegge on-demand. Con memory tool attivo l'API inietta: "IMPORTANT: ALWAYS VIEW YOUR MEMORY DIRECTORY BEFORE DOING ANYTHING ELSE."

**Context editing vs compaction**: context editing ripulisce tool result client-side; compaction riassume l'intera conversazione server-side. Per agenti long-running: entrambi — "compaction keeps the active context small without client-side bookkeeping, and memory preserves the information that must survive summarization."

**Pattern "Multisession software development"**: sessione initializer scrive progress log + feature checklist PRIMA del lavoro; ogni sessione successiva riparte leggendo quei file; "completa" solo dopo verifica end-to-end.

(Caveat: soglie di context editing citate da fonti terze — 60% window, ultimi 5 tool use — NON ri-verificate su fonte primaria.)

## 5. Claude Code — Agent Skills / progressive disclosure (docs ufficiali)
Fonte: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview

| Livello | Quando caricato | Costo token | Contenuto |
|---|---|---|---|
| 1: Metadata | Sempre, all'avvio | **~100 token per Skill** | `name`+`description` YAML |
| 2: Instructions | Al trigger | **<5k token** | corpo SKILL.md |
| 3+: Resources | Solo se referenziati | 0 finché non acceduti | file bundlati, script (solo l'OUTPUT entra in context) |

La `description` deve dire **cosa fa E quando usarla** — è il testo di matching. Vincoli: name max 64 char; description max 1024 char.

## 6. Confronto — OpenAI (AGENTS.md) e Google (GEMINI.md)
(Caveat: ricerca aggregata, fonti primarie NON fetchate direttamente.)

**OpenAI AGENTS.md**: "the most important context management tool for Codex". Governance passata alla **Agentic AI Foundation sotto Linux Foundation** — standard cross-tool multi-vendor. Regole di team obbligatorie in AGENTS.md checked-in; memorie conversazionali come layer di recall locale, non fonte unica.

**Google GEMINI.md**: gerarchia 3 livelli (`~/.gemini/GEMINI.md` globale → `./GEMINI.md` progetto → `./src/GEMINI.md` subdirectory). Tutti i file trovati **concatenati eager a OGNI prompt** — nessun lazy load nativo. `/memory show` e `/memory reload`. Import modulari `@file.md`.

**Differenza chiave**: solo Anthropic Skills = progressive disclosure vera (lazy, ~100 token finché non triggerata); GEMINI.md = concatenazione eager; AGENTS.md = standardizzazione cross-vendor più che caricamento incrementale.

## 7. Materiale 2026

- Prompt caching (fetch diretto platform.claude.com): minimo cacheable **512 token per Fable 5.1/Mythos 5.1/Opus 5/Fable 5/Mythos 5** (1.024 per Opus 4.8 e Sonnet 5/4.6/4.5; 4.096 per Opus 4.6/4.5 e Haiku 4.5). Max 4 cache breakpoint (400 oltre). TTL default 5 min (reset a ogni hit); TTL 1h a 2× cache-write (vs 1.25× per 5 min). Cache read **0.1× input base** (0.025× per Fable 5.1/Mythos 5.1). Lookback window 20 blocchi → su conversazioni lunghe servono 2 breakpoint.
- "Best practices" 2026 include: plan mode Shift+Tab, checkpoint/rewind Esc+Esc, `/goal` gate deterministico via evaluator separato, Stop hook (override dopo 8 blocchi), auto mode con classifier, `/batch` 5-30 subagent, Agent teams (sperimentale).

## Principi operativi estraibili

- **Test del taglio-riga su CLAUDE.md**: "la sua rimozione causerebbe errori?" — se no, tagliare. [best-practices]
- **Niente in CLAUDE.md di derivabile dal codice o che cambia spesso** — skill on-demand invece. [best-practices]
- **"IMPORTANT" solo su UNA riga** — enfasi diffusa = zero enfasi. [best-practices]
- **`/clear` tra task non correlati, sempre**. [best-practices]
- **>2 correzioni fallite → `/clear` + riprompt specifico**. [best-practices]
- **Esplorazione delegata a subagent** (riassunto 1-2k token vs decine di migliaia esplorati). [effective-context-engineering; multi-agent-research]
- **Review adversariale in context fresco** (solo diff + criteri). [best-practices]
- **Multi-agente SOLO per breadth-first ad alto valore** (~15× token; il coding parallelizza poco). [multi-agent-research]
- **Compaction: recall prima, precisione poi**. [effective-context-engineering]
- **Memory tool / pattern initializer-session** per stato che sopravvive a compaction/reset. [memory-tool docs]
- **Skill description = cosa + quando** (unico costo ~100 token finché non triggera). [agent-skills docs]
- **Caching: statico prima del dinamico**, `cache_control` sull'ultimo blocco statico. [prompt-caching docs]
- **System prompt "right altitude"**: minimale, poi regole solo su fallimenti osservati. [effective-context-engineering]
- **Cross-vendor**: Skills Anthropic = lazy (più efficiente all'avvio); GEMINI.md = eager; AGENTS.md = standard cross-tool. [aggregato, da verificare]
