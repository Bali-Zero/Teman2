# Phase 6 — Bali Zero Macro (B5)

> **Prerequisiti**: Phase 1 (Setup Team) + Phase 3 (Tax) preferibili — il dominio macro alimenta cross-domain alert routing.
>
> **Stima**: 5-8 giorni solo-dev.
>
> **Pre-azione richiesta a Antonello**: B5.a (NB-IndonesiaMacro nuova vs estendere NB-8) + B5.b (3 NB-INTEL distinti vs 1 unificato).

---

## PROMPT (drop-in)

Continuiamo il Domain Mesh. Phase 6: implementa il dominio **Bali Zero Macro (B5)** — Indonesia macro intelligence (politica/economia/società/cultura/geo).

Prima di tutto, leggi:

1. `docs/superpowers/specs/2026-05-08-domain-mesh-autonomic-design.md` §6 B5
2. `docs/superpowers/specs/2026-05-08-domain-mesh-research/r6-country-intelligence-id-2026-05-08.md` (R6 SOTA)
3. `apps/mata-garuda/mata_garuda/foundations/bali_calendar.py` (Phase 0 — già implementato, integrare in macro per cross-domain calendar guard)
4. `apps/mata-garuda/mata_garuda/foundations/gdelt_client.py` (Phase 0 — già implementato!)
5. NB-8 Expat Life Bali UUID + MATA GARUDA gov data UUID — cerca in `~/.claude/projects/-Users-nuzantara/memory/reference_notebooklm_arsenal_full.md`

`superpowers:brainstorming` → `writing-plans` → `subagent-driven-development`.

### Scope

**domains/bali_macro/** modules:

1. **Authority NB**:
   - DECISIONE B5.a: NB-IndonesiaMacro NEW (default consigliato, R6 conferma) vs estendere NB-8
   - Se nuova: bootstrap con CSIS Indonesia 2026 + ISEAS Perspective + Lowy Indonesia + World Bank IEU + IMF Article IV + ADB CPS + BPS Statistical Yearbook (~30 seed sources)

2. **Feeders (3 NB-INTEL — DECISIONE B5.b, default A=3 distinti)**:
   - `feeders/nb_intel_indonesia_policy.py`: setkab cabinet decisions + kemenkeu press + Bank Indonesia press + OJK press + Twitter @prabowo @gibran (verified) + CSIS commentary + ISEAS Indonesia briefs + Lowy Interpreter Indonesia tag
   - `feeders/nb_intel_indonesia_economy.py`: BPS WebAPI (R2 confirmed REST endpoint) + Bank Indonesia REST + World Bank Indonesia API + IMF Indonesia + ADB Indonesia + Bisnis.com macro + Kontan macro + Asia Nikkei Indonesia
   - `feeders/nb_intel_indonesia_social.py`: Drone Emprit pers.droneemprit.id (R6: free public releases, NO partnership needed) + Indonesia Indicator periodic + X trends24.in/indonesia + TikTok Indonesia trends manual scrape + Reddit r/indonesia top weekly

3. **Already in Phase 0 — integrate**:
   - `foundations/gdelt_client.py`: `search_indonesia(query, max_results)` ready to use
   - `foundations/bali_calendar.py`: Galungan/Kuningan integration

4. **R6 lifecycle 5-layer mapping** (adopt as-is from §6.2 design):
   - Layer 0 raw signal (15min-daily): GDELT + ACLED + Antara RSS + BPS WebAPI
   - Layer 1 curated press (daily): Tempo + Kompas.id + Jakarta Post + Project Multatuli + Tirto + NusaBali
   - Layer 2 thinktank (weekly): CSIS + ISEAS + Lowy + New Mandala + FULCRUM + Habibie + TII + FKP
   - Layer 3 social pulse (weekly digest): Drone Emprit + Indonesia Indicator + trends24 + TikTok + Reddit
   - Layer 4 business quarterly: World Bank API + IMF Article IV + ADB CPS + OJK SJK Public + chambers (BritCham/EuroCham/AmCham/IABC)

5. **PolicyEvent entity tracking**:
   - SQLite `bali_macro.sqlite` table `policy_events`
   - Schema R6-extended: date, type, regulator, sectors_affected, stakeholders_named, **asta_cita_alignment** (1-8 priority missions), **geopolitical_context**, **dissent_posture_change**, indicator_signal
   - Cross-domain trigger: PolicyEvent → route to relevant domain orchestrator (Setup Team / Tax / Marketing)

6. **EconomicIndicator tracking**:
   - GDP, CPI, BI rate, Rupiah, PMI Manufacturing
   - Drift detector: BI rate hike, CPI spike, Rupiah > 17000/USD → auto-spawn workbench "Indonesia Q-X mid-quarter update"

7. **Bali calendar integration cross-domain**:
   - `bali_calendar_module.py`: query function `get_balinese_date(gregorian_date) → {saka_year, pawukon_day, ceremonies_today}`
   - Cross-domain expose: setup-team skip PBG/SLF appointments, tax filing slow window, marketing content "Galungan for expats" 1 week before, CRM "we are closed [DATE]" template

8. **Quarterly outlook auto-draft** (R6 sink 1):
   - Last week of quarter → auto-generate "Indonesia Outlook Q-X" 8-page PDF from workbench
   - Antonello reviews then optional publish to clients (newsletter premium)

9. **Cross-domain alert dispatcher** (R6 sink 2):
   - PolicyEvent classified → route:
     - Kemenkeu PMK → tax domain
     - Kemenkumham → setup-team
     - Kemenparekraf → marketing (tourism vertical)
     - Bank Indonesia → macro outlook update

10. **Cron**:
    - `infra/scripts/bali-macro-cron.sh`
    - Schedule: 09:00 WITA daily
    - Kill switch: `BALI_MACRO_CRON_ENABLED=false`

### R6 quick-wins

- **GDELT API gratis** (Phase 0 already done!) — 15-min cadence Indonesia FIPS-2 = ID
- **BPS WebAPI free token-auth** — economic data REST endpoint documented
- **Drone Emprit pers.droneemprit.id** — free public releases (NO partnership commercial needed for this)
- **Bali calendar 2026 verified**: Galungan 17 Jun, Kuningan 27 Jun (Phase 0 hardcoded + verified)
- **Coconuts Bali DEAD post-2023** — remove from any feed list

### R6 geopolitical timeline 2026 anchor (seed)

| Date        | Event                                |
| ----------- | ------------------------------------ |
| 2026-01-07  | BRICS membership effective           |
| 2026-01-21  | IMF Article IV publ.                 |
| 2026-02-19  | US-Indonesia ART signed $33B         |
| 2026-02-20  | SCOTUS shakes ART                    |
| 2026-02 mid | Jakarta Treaty (Australia)           |
| 2026-04-15  | Prabowo Moscow + new US defense pact |
| 2026-05-05  | CSIS militarization warning          |
| 2026-06-17  | Galungan                             |
| 2026-06-27  | Kuningan                             |

Pre-popola `policy_events` table con questi.

### Sink (output)

1. Quarterly outlook PDF auto-draft
2. Cross-domain alert dispatcher
3. Mouth long-form analysis (multi-month framework articles)
4. Telegram `#bali-macro` weekly strategic alerts (NOT daily — strategic timing)
5. NB cross-pollination

### Regole forti

- mata-garuda CLAUDE.md
- Lazy imports
- TDD: 40+ test
- Cron PATH
- Atomic mv
- Branch hijack push post commit

### Pre-azione richiesta a Antonello

**PRIMA di partire**:

1. **B5.a**: NB-IndonesiaMacro nuova vs estendere NB-8?
   - **A** (default, R6 conferma): nuova NB-IndonesiaMacro — separata da NB-8 lifestyle
   - B: estendere NB-8 — meno overhead ma mix lifestyle + strategic

2. **B5.b**: 3 NB-INTEL Macro distinti (Policy + Economy + Social) vs 1?
   - **A** (default, R6 conferma): 3 distinti — feeder + cadenza + scorer diversi
   - B: 1 unificato — meno NB ma mix segnale

3. Quarterly outlook PDF — accettazione publish a clienti?
   - Solo internal / newsletter premium opt-in / blog pubblico
   - Default consigliato: internal-first, decision Antonello dopo Q1 draft

4. Cross-domain alert dispatcher unified vs domain-specific channels?
   - NLM W1 ground-truth: bot @Balizerobot unificato — usa lui, NO new channels
   - Default consigliato: routing all'unico bot esistente.

Procedi quando confermato.
