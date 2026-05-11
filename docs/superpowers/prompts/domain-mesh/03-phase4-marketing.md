# Phase 4 — Marketing Pulse (B3)

> **Prerequisiti**: Phase 1+2 mergiate. Phase 3 (Tax) opzionale ma utile per cross-pollination.
>
> **Stima**: 7-10 giorni solo-dev.
>
> **Pre-azione richiesta a Antonello**: decisione su B3.a (Competitor scraping yes/no) e B3.b (WR2 auto-publish autonomy level).

---

## PROMPT (drop-in)

Continuiamo il Domain Mesh. Phase 4: implementa il dominio **Marketing Pulse (B3)**.

Prima di tutto, leggi:

1. `docs/superpowers/specs/2026-05-08-domain-mesh-autonomic-design.md` §4 B3
2. `docs/superpowers/specs/2026-05-08-domain-mesh-research/r4-marketing-intelligence-2026-05-08.md` (R4 SOTA)
3. `apps/mata-garuda/mata_garuda/domains/setup_team/` (pattern template)
4. `apps/mouth/` (Astro content site esistente)
5. Cerca WR2 references: `grep -rn "wr2\|WR2" apps/backend-rag/backend/services/ docs/wr2/ 2>/dev/null | head -20`
6. NB-7 Editorial NB UUID — cerca in memoria: `~/.claude/projects/-Users-nuzantara/memory/reference_notebooklm_arsenal_full.md`

`superpowers:brainstorming` → `writing-plans` → `subagent-driven-development`.

### Scope

**domains/marketing/** modules:

1. **Feeders (3 NB-INTEL)**:
   - `feeders/nb_intel_press.py`: 14 fonti (tier-1 EN/ID Indonesia + Bali tier-1 + expat verticals)
   - `feeders/nb_intel_trends.py`: HN Algolia API (R4 free zero-cost) + pytrends + Reddit r/bali r/indonesia free tier (10k req/month) + TikTok Creative Center (manual scrape) — **ZERO COST**
   - `feeders/nb_intel_competitor.py` (CONDIZIONALE su decisione B3.a): Wayback Machine CDX API per Emerhub/Cekindo/InvestinAsia cadence tracker

2. **Editorial orchestrator**:
   - `orchestrator.py`: relevance scoring, audience match (expat_it/expat_ru/expat_en/investor/nomad), brief candidates ranking
   - Pattern AscentAI bottom-up: estrai topic atomici da articoli, aggrega frequency, propose brief
   - SQLite `marketing.sqlite` con tabelle `content_items`, `trends`, `competitors`, `brief_candidates`

3. **WR2 integration**:
   - `wr2_brief_generator.py`: trasforma brief candidate in WR2 input format
   - Trigger automatico (CONDIZIONALE su decisione B3.b)
   - Hook su `apps/backend-rag/backend/services/wr2/` (esistente)

4. **C2PA Content Credentials** (R4 quick-win 2026 differentiator):
   - `c2pa_signer.py`: aggiunge content credentials a articoli WR2 prima di publish su mouth
   - Standard C2PA v2.2/v2.3 (R4 verified, OpenAI/Google/Adobe membri)
   - Zero cost (open standard)

5. **AI authenticity** (skip Originality.ai per R4 — 7.3% recall su GPT-5-mini, useless):
   - Use GPTZero (~99% recall) come optional verifier, OR human review hard gate

6. **Reddit organic dispatch** (manuale, NON scraper):
   - `reddit_dispatch_helper.py`: prepara post text + suggested target subreddits, ma NESSUN auto-post
   - Antonello/team posta a mano 2-3x/settimana r/digitalnomad, r/IndoBali

7. **Drone Emprit exploratory** (R4 partnership lead):
   - Spawn `NB-WORKBENCH-DroneEmprit-partnership` (workbench Notion-style markdown in `~/Desktop/nuzantara/research/marketing/`)
   - NO codice automation per ora; solo case file per discussione con Ismail Fahmi

8. **Cron**:
   - `infra/scripts/marketing-pulse-cron.sh`
   - Schedule: 08:00 WITA daily
   - Kill switch: `MARKETING_CRON_ENABLED=false`
   - Sink: morning briefing Telegram `#editorial` (3 brief candidates + 1 competitor signal + 1 trending topic)

### Sink (output)

1. **WR2 brief auto-generation** (autonomy level depends on B3.b decision)
2. **IG carousel suggestion** (NB-INTEL-Trends + NB-7 methodology)
3. **Telegram `#editorial`** alert daily 8am WITA
4. **Newsletter digest Brevo** (R4: Brevo MCP server already exists, integrate)
5. **Mouth dispatch trigger** (article ready → IG + LinkedIn + newsletter orchestrated)
6. **Reddit organic helper** (manual post text generation)

### R4 traps to avoid

- **Sora 2 deprecation 24 settembre 2026** — NO video generation pipeline su Sora 2.
- **Originality.ai 7.3% recall** — NO usare per AI detection. GPTZero solo se serve.
- **Reddit scraping aggressivo** — viola TOS. Solo defensive use (free tier 10k req/month).
- **Trendpop $250+/min, Talkwalker enterprise** — SKIP. Brand24 Individual $99 sufficient se Antonello vuole social listening Bahasa.
- **Anthropic Constitution CC0-licensed** (R4 discovery) — usabile come reference per policy AI editorial interna.

### Regole forti

- mata-garuda CLAUDE.md hard rules invariate
- Lazy imports PEP 562
- TDD: 50+ test attesi
- Cron PATH include `/Users/nuzantara/.local/bin`
- Atomic mv snapshot
- Branch hijack push post commit
- C2PA implementation: usa `c2pa-rs` (Rust binary) o `c2pa-python` se esiste, altrimenti tooling Adobe via subprocess

### Pre-condizioni per merge

- 50+ test green
- WR2 integration smoke test (mock WR2 service, verify brief format)
- Mouth publish step verifica content credentials presenti
- External review wave (3 LLM minimum)

### Pre-azione richiesta a Antonello

**PRIMA di partire**:

1. **B3.a**: NB-INTEL-Competitor (Emerhub/Cekindo/InvestinAsia tracking)?
   - Sì full / Sì weekly digest only / **No** (default consigliato: weekly digest only — competitive awareness senza ansia continua)

2. **B3.b**: WR2 auto-trigger autonomy level?
   - **A** (consigliato): Auto-brief → auto-WR2 → human review pre-publish (low risk, mid latency)
   - B: Auto-brief → auto-WR2 → auto-publish con QA gate (low latency, editorial risk)
   - C: Manuale tutto (safe ma morto)

3. C2PA Content Credentials su mouth — implementarlo?
   - Pro: differentiator EEAT 2026 + content provenance
   - Contro: ~3-5 giorni implementation extra
   - Consigliato: **Sì**, è quick-win zero-cost.

4. Drone Emprit partnership exploration — autorizzi contatto Ismail Fahmi?
   - Solo case file iniziale, no commitment.
   - Consigliato: **Sì**, exploratory.

Procedi quando hai conferma su questi 4 punti.
