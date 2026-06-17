---
date: 2026-06-11
purpose: handoff prompt per Fable 5 (effort Extra) — conferma-su-codice + PR atomiche dell'audit UI/UX kita
audit_input: research/operations/2026-06-11-kita-uiux-audit.md
coordinates_verified: 2026-06-11 (grep su repo)
---

# Prompt di handoff → Fable 5 (effort Extra)

Copia tutto il blocco sotto in una sessione che gira **su Fable 5 effort Extra**
(model picker Cowork, oppure subagent con override `fable`).

---

Sei nel monorepo Nuzantara in `~/Desktop/nuzantara`. Prima di agire leggi `SYMBIOSIS.md`,
`CLAUDE.md`, `VADEMECUM.md`. **Anti-allucinazione (load-bearing): non citare un file:line senza
averlo aperto in QUESTO turn.** Lingua: italiano con l'owner, inglese per codice/commit/PR.
Costo free-first, mai `ANTHROPIC_API_KEY`. Nessun dato cliente (PII) verso cloud. Git: commit
atomici convenzionali, co-author Claude, PR obbligatoria su main, mai `--no-verify`/`--amend` su
pushati, rispetta off-limits (`zantara_core.py`, `fly.toml`, `.env*`, `alembic/env.py`) e la
worktree discipline (`scripts/agent_start.py`).

## Missione
Un audit **lato-UI** di kita.balizero.com (`research/operations/2026-06-11-kita-uiux-audit.md`,
leggilo tutto) ha individuato problemi UX i cui fix dovrebbero **ridurre** il codice. Il tuo compito:
**confermare ogni finding sul codice reale**, quantificare le righe eliminabili, e produrre **PR
atomiche** partendo da P0.2 e P0.3. Metrica guida: throughput operatore (più clienti per persona).
Vincolo: semplificare, non complicare — net costo-codice ≤ 0. **Dove un finding NON si conferma sul
codice, dillo e scartalo** — non forzarlo (il report contiene inferenze lato-UI da verificare, non verità).

## Coordinate (verificate 2026-06-11 via grep)
- Frontend kita = **`apps/mouth`** (Next.js App Router, route group `(workspace)`).
- Sidebar/nav: `apps/mouth/src/types/navigation.ts` · header `apps/mouth/src/components/workspace/Header.tsx`
- Dashboard: `apps/mouth/src/app/(workspace)/dashboard/` · widget `apps/mouth/src/components/dashboard/`
  (`TeamActivityPanel.tsx`, `FinancialRealityWidget.tsx`)
- Team Performance (backend): `apps/backend-rag/backend/services/analytics/team_analytics_service.py`
  + `apps/backend-rag/backend/app/routers/admin_team_activity.py`
- Clients: `apps/mouth/src/app/(workspace)/clients/page.tsx`
- Process: `apps/mouth/src/app/(workspace)/process/page.tsx`
- HR: `apps/mouth/src/app/(workspace)/hr/page.tsx` (+ employees/bonuses/payroll/leave/settings/owner-cashout)
- LKPM: `apps/mouth/src/app/(workspace)/lkpm/page.tsx` · Partners: `apps/mouth/src/app/(workspace)/partners/`
- Intelligence: `apps/mouth/src/app/(workspace)/intelligence/{page,layout}.tsx`
  + `.../intelligence/article-composer/page.tsx`
- Valuta (duplicazione candidata): canonico `packages/core/utils/currency.ts`; altri formatter in
  `apps/osint-nexus-ui/src/lib/format.ts`, `apps/backend-rag/portal-ui-components/lib/formatters.ts`,
  `apps/mouth/src/app/(workspace)/clients/[id]/components/utils.ts` — e ~60 file usano
  `Intl.NumberFormat`/`toLocaleString`. Mappa chi usa il canonico vs chi formatta inline.

## Evidenza live (osservata sul rendered UI il 2026-06-11, da confermare sul codice)
- Dashboard guidata da hero "news"; "50 documents waiting for your review" + KPI + Team Performance sotto la piega.
- KPI "CLIENTI registrati" **vuoto** in dashboard mentre /clients mostra **1.481 total**.
- Tabella Team Performance: 11 colonne, **6 a zero per tutti i ~16 membri** (CONVOS, MESSAGES, EMAILS OUT, EMAILS IN, KB VIEWS, KB DL).
- Valuta in 4 formati: dashboard `Rp 1.15B`/`Rp 45.2M` · clients `Rp 45,2 jt`/`Rp 1,1 M` · process `Rp 800 rb`/`Rp 2 jt` · HR `Rp 1.850.000`.
- Sub-nav diversa per modulo: HR sub-sidebar verticale · Intelligence sub-tab · Clients/Process filter-chip · Partners dropdown nativi.
- Microcopy IT/EN mischiato: KPI `Revenue/Outstanding`(EN)+`Clienti/Processi/Fatture`(IT); Article Composer label EN + placeholder `Incolla contenuto…`/`Es. New KITAS Rules…`(IT).
- /intelligence hub mostra 2 tool (News Room, Article Composer) ma il sub-nav interno ne ha 3 (compare Visa Oracle).
- News Room: ~10 card con accento colore per-card + un bottone Publish per card; checkbox di multiselezione già presenti ma niente azione bulk.
- Partners TIER reso come `10.0000 %`.

## Lavoro (in ordine — ogni voce = una PR atomica)

**PR 1 — P0.2 (colonne morte + KPI Clienti rotto).** In `TeamActivityPanel.tsx` individua le colonne
renderizzate; in `team_analytics_service.py`/`admin_team_activity.py` verifica se quei campi sono mai
popolati o sempre 0. Se morti: rimuovili (più il data-plumbing relativo) o feature-flag nascosti finché
non strumentati. Trova il KPI "Clienti" della dashboard e collegalo alla stessa fonte di /clients;
documenta il mismatch di sorgente. Quantifica LOC rimosse.

**PR 2 — P0.3 (un solo formato valuta).** Conferma il canonico `packages/core/utils/currency.ts`,
inventaria i punti che formattano IDR inline, standardizza un unico `formatIDR` + componente `<Money>`,
sostituisci gli inline, cancella i duplicati. Elenca i file toccati + LOC delta (atteso negativo).

**Poi (follow-up, dopo P0.2/P0.3):** P0.1 riordino dashboard (azione sopra/news sotto) ·
P1.1 sub-nav unica · P1.2 scaffolding lista condiviso (`<ListPageHeader>/<FilterBar>/<SearchBox>/<StatChips>`) ·
P1.3 dizionario stringhe + lingua unica · P1.4 hub Intelligence allineato (o eliminato) ·
P1.5 News Room accento per-stato + bulk-publish · P2 (TIER `10%`, persistenza vista, CTA stati vuoti).

## Traccia creativa — PIENA LIBERTÀ (palette, effetti, motion, tipografia)
Oltre alle PR di consolidamento hai **mandato creativo pieno** per elevare il linguaggio visivo:
sistema-colore/palette, profondità, effetti, micro-interazioni/motion, gerarchia tipografica.
- **Base TUTTO su ricerca deep e ATTUALE (giugno 2026), non sul training.** Prima di proporre,
  fai web search a ventaglio sui migliori esempi al mondo OGGI: ops/SaaS console e dashboard premiate
  (Awwwards/CSS Design Awards e simili del 2026), design system di riferimento, dark-UI di classe,
  trend correnti di palette/effetti/motion/tipografia. I trend si muovono e la tua memoria è ferma →
  **cerca, leggi, cita le fonti** (allega un mini-rapporto con i link a supporto di ogni scelta).
  Sintetizza nell'anima Bali Zero: **ispirazione, non copia** — nessun clone di UI altrui (originalità/IP).
- **Ancòrati all'anima esistente, non cancellarla**: dark UI, estetica "raw stone + oro fuso",
  display serif, payoff "Order from the raw / NILAI", logo 3ALI ZERO. **Eleva, non resettare.**
- **Risolvi la tensione con "semplifica il codice" consegnando tutto come token/theme layer**
  (colore, spaziatura, elevazione, raggi, ombre, durate/easing motion in un'unica fonte di verità):
  così la creatività ALLO STESSO TEMPO centralizza e **cancella i colori/effetti inline sparsi**
  (si salda con P0.3 e P1.2 — un solo posto da cui cambiare tutto).
- **Vincoli da console ops 8h/giorno**: contrasto e leggibilità (WCAG AA min), niente effetti che
  danneggiano perf o distraggono dal lavoro, performance budget su blur/shadow/animazioni,
  rispetta `prefers-reduced-motion`. Bello ma che non rallenti chi macina pratiche.
- **Punto di partenza già nel repo (verificato 2026-06-11)**: `docs/design-palettes/SESSION-SUMMARY.md`,
  `docs/design-palettes/bz-pages-draft.html`, `docs/research/2026-04-14-design-system-sota.md`,
  `docs/superpowers/plans/2026-03-13-intelligence-center-redesign.md`. Leggili e costruisci sopra.
- **Output**: proposta di **design token** + 2–3 mockup before/after delle schermate chiave
  (dashboard, clients, una kanban) con razionale. **Genera più direzioni, critica le tue, converge**
  (è esattamente la forma effort Extra). NON imporre un reskin totale: proponi, l'owner sceglie.

## Deliverable per ogni PR
(a) conferma del finding con evidenza file:line; (b) LOC delta (atteso negativo); (c) diff/PR;
(d) screenshot/test dove serve; (e) gate frontend (lint/test) verdi. Ri-verifica le TUE citazioni
file:line prima di asserire — questo è un pass profondo e auto-validante, non un giro veloce.
