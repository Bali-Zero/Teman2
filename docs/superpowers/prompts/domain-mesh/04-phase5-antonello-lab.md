# Phase 5 — Antonello Lab (B4)

> **Prerequisiti**: Phase 0 foundations. Phase 1+ optional ma utile.
>
> **Stima**: 6-9 giorni solo-dev.
>
> **Pre-azione richiesta a Antonello**: decisione su B4.a (4/2/1 NB-INTEL distinti) + B4.b (morning briefing daily/weekly/on-demand).
>
> **Differenza dagli altri domini**: questo è **personale**, non Bali Zero. Lifecycle ottimizzato per Antonello come singolo utente.

---

## PROMPT (drop-in)

Continuiamo il Domain Mesh. Phase 5: implementa il dominio **Antonello Lab (B4)** — research personale (AI papers, code, robotics, frontier science).

Prima di tutto, leggi:

1. `docs/superpowers/specs/2026-05-08-domain-mesh-autonomic-design.md` §5 B4
2. `docs/superpowers/specs/2026-05-08-domain-mesh-research/r5-research-agents-2026-05-08.md` (R5 SOTA)
3. `apps/mata-garuda/mata_garuda/foundations/arxiv_sanity_scorer.py` (Phase 0, già implementato — è la base personalization!)
4. NB-INTEL-AIResearch UUID: cerca in `~/.claude/projects/-Users-nuzantara/memory/reference_notebooklm_arsenal_full.md`

`superpowers:brainstorming` → `writing-plans` → `subagent-driven-development`.

### Scope

**domains/antonello_lab/** modules:

1. **Feeders (4 NB-INTEL — DECISIONE B4.a, default A=4 distinti)**:
   - `feeders/nb_intel_airesearch.py`: arxiv API (cs.AI/cs.LG/cs.CL/cs.CV/cs.RO) + Hugging Face papers + Anthropic/OpenAI/DeepMind/Meta blogs + LessWrong AI tag + HN AI stories + Karpathy/Simon Willison + Latent Space + The Batch + TLDR AI subscription parser
   - `feeders/nb_intel_code.py`: GitHub Trending (huchenme/github-trending-api free) + Star History slope detection + HF Trending Models + Sourcegraph search clusters
   - `feeders/nb_intel_robotics.py`: Helix Figure blog + π0 Physical Intelligence + Gemini Robotics DeepMind + GR00T NVIDIA + OpenVLA + RT-X + Tesla Optimus + arxiv cs.RO + IROS/ICRA papers
   - `feeders/nb_intel_frontier_science.py`: Nature RSS + Science RSS + Quanta + Astral Codex Ten + Marginal Revolution + Construction Physics + Asterisk + Nautilus

2. **Personal relevance scorer** (R5 zero-cost):
   - **Already in Phase 0**: `arxiv_sanity_scorer.py` (SVM-on-tfidf, calibrated)
   - **Train data**: Antonello tags papers/repos via `/lab tag <id> relevant|not_relevant` slash command
   - Salva in SQLite `antonello_lab.sqlite` table `tagged_items`
   - **Zero LLM cost** scoring (R5 Karpathy pattern)

3. **GitHub trending 4-tier signal** (R5):
   - HN submission >100 pts first 6h on github.com/ URLs (signal 1)
   - TLDR AI / Latent Space / The Batch mentions (signal 2)
   - Star History slope jump 5x daily (signal 3)
   - Sourcegraph search hit cluster (signal 4)
   - Composite scorer: ≥2 signals → high priority

4. **Morning briefing** (DECISIONE B4.b, default A=daily 7am WITA):
   - `briefing.py`: top-5 papers + repos trending + robotics + science + 1 Bali Zero cross-pollination
   - Output: Telegram `#antonello-lab` private channel
   - Format: structured markdown con priority indicators

5. **Deep-read trigger**:
   - `/research deep-read <paper_id>` slash command
   - Spawn `NB-WORKBENCH-Antonello-{paper_topic}` workbench (markdown in `~/Desktop/nuzantara/research/ai/`)
   - Auto-include: paper PDF, related work map, code repo cloned (if any), summary draft

6. **Research session orchestration**:
   - `/research <topic>` slash command
   - gpt-researcher MCP integration (R5: LLM-agnostic, MCP-ready, supports DeepSeek + Ollama)
   - Multi-agent parallel research (3-5 agent)
   - Output consolidato in workbench

7. **Cross-pollination**:
   - Detector: paper letto da Antonello → check rilevanza Bali Zero (es. tax-LLM paper → alert Veronika)
   - Telegram `#antonello-lab` segnala anche al canale del dominio relevant

8. **Long-term KG**:
   - `mem0_integration.py`: Mem0 vector + KG mirror su Mini-Pro2
   - Each deep_read note → entity extraction (NER via Phase 0 ner_extractor) → personal KG
   - Query "what did I read about RAG in past 6 months?" → cross-paper retrieval

9. **Cron**:
   - `infra/scripts/antonello-lab-cron.sh`
   - Schedule: 07:00 WITA daily (briefing pre-work)
   - Kill switch: `ANTONELLO_LAB_CRON_ENABLED=false`

### Feeder updates from R5 (importante)

**REMOVE da feed list**:

- Papers With Code (DEAD July 2025) → use HF Papers Trending instead
- Asimov Press (HIATUS April 2026) → cleared

**ADD R5-validated**:

- HF Papers Trending (PWC replacement, R5 confirmed)
- TLDR AI subscription (1.25M readers, daily digest)
- gpt-researcher OSS via MCP

### R5 quick-wins zero-cost

- **arXiv API rate**: 1 req/3s (rispetta strict)
- **OAI-PMH bulk** per backfill se serve catch-up
- **Semantic Scholar API** 1 req/s con key (gratis)
- **HN API Firebase** no auth, no rate limit
- **arxiv-sanity SVM** già in Phase 0 (ZERO cost personalization)

### R5 architecture pattern (R5 §7)

3-tier "second brain" Antonello:

- **Tier 1 (Obsidian-like)**: notes locali in `~/Desktop/nuzantara/research/`
- **Tier 2 (Readwise-like)**: NB-INTEL-\* aggregator with scoring → SQLite
- **Tier 3 (NotebookLM)**: NB-9 synthesis + workbench deep dives via MCP

Daily Telegram briefing è il "punto di accesso" al sistema, non il sistema stesso.

### Regole forti

- mata-garuda CLAUDE.md hard rules
- Lazy imports per ML (transformers/torch)
- TDD: 40+ test
- Cron PATH `/Users/nuzantara/.local/bin`
- Atomic mv snapshot
- Branch hijack push post commit

### Pre-azione richiesta a Antonello

**PRIMA di partire**:

1. **B4.a**: 4 NB-INTEL distinti (AIResearch+Code+Robotics+FrontierScience)?
   - **A** (default): 4 distinti — max specialization, cron 4×
   - B: 2 (AIRes+Code, Rob+Sci) — mid load
   - C: 1 unificato — min load, max noise
   - D: priority Robotics+Science first (deferra Code a Phase 6)

2. **B4.b**: Morning briefing format?
   - **A** (default): Daily 7am WITA Telegram message
   - B: Weekly Sunday digest (calmo, perdi velocità AI fast-moving)
   - C: On-demand `/research-pulse` (tu controlli, rischio dimenticarlo)

3. gpt-researcher MCP integration — accetti?
   - Pro: research orchestration potente, LLM-agnostic
   - Contro: MCP server da gestire (deps Python, può rompersi)
   - Default consigliato: Sì.

4. Mem0 long-term KG su Mini-Pro2 — accetti?
   - Pro: cross-paper query "cosa ho letto su X negli ultimi 6 mesi"
   - Contro: SQLite + embeddings ~500MB-2GB su Mini disk
   - Default consigliato: Sì.

Procedi quando confermato.
