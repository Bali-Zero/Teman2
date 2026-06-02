---
date: 2026-06-03
domain: visa
session: ONDA-3 S9 client-case-dossier
client_case: marc-buckner-content-creator-3mo-bali
status: DRAFT — NEEDS-ANTONELLO (income proof + foreign-employer-contract structure + barter-deal disclosure pending)
pricing_source: bali_zero_official_prices_2026.json (version 2026.1, effective 2026-01-01) via PricingTool source-of-truth
devils_advocate: PASS-after-fix (Codex flagged NEEDS-FIX x3, 2 accolti + fix applicati, see section Devils-Advocate)
eligibility_source: research/visa/2026-05-31-marc-buckner-c5a-e33g-barter-case.md (NB-2 Kepmen M.IP-08.GR.01.01/2025 verbatim + 7 web sources convergent)
author: S9 orchestrator (Claude Opus 4.8) — eligibility from S6/Marc-case ground truth, cost from PricingTool
---

# Dossier cliente — Marc Buckner (Content Creator, 3 mesi Bali)

> **STATUS: BOZZA — NON SEND-READY.** Eligibility verde e cost da PricingTool verde, ma due input cliente mancanti bloccano la quote finale: (1) prova reddito estero >= USD 60k/anno, (2) natura dei deal con hotel (barter informale vs contrattualizzabile via entita estera). Vedi sezione Documenti mancanti.

## 1. Profilo cliente

- **Nome**: Marc Buckner (IG @marcbuckner)
- **Nazionalita**: Sudafricana (WNA)
- **Audience**: 2M+ follower — travel/lifestyle/fitness/motivation/technology/animals
- **Soggiorno**: ~3 mesi Bali, giugno–settembre 2026 (hotel + ville)
- **Reddito**: brand partnership sudafricane + internazionali (fonte estera)
- **Lead**: arrivato tramite influencer contatto di Antonello (Meta Business Suite)

## 2. Eligibility (ground-truth NB-2, Kepmen M.IP-08.GR.01.01/2025 verbatim)

| Visto | Eleggibile per Marc | Verdetto |
|---|---|---|
| **E33G Remote Worker KITAS** | Si — copre SOLO la creazione di contenuti pagata dall'estero, no sponsor | UNICA VIA SENSATA per la GAMBA reddito-estero (vedi caveat contratto sotto) |
| **C5A** (content creator) | Definito legalmente MA non selezionabile sul portale evisa (Data Belum Tersedia 11+ mesi); vieta barter ("atau sejenisnya") | NON OPERATIVO — non vendere (panel 3-LLM 2026-05-28: WAIT) |
| **C7/C7C** (arti/cultura) | NO — copre performance/chef-demo, non travel/lifestyle | categoria sbagliata |
| **E23** (lavoro sponsorizzato) | Tecnicamente si se hotel fa da sponsor (RPTKA + DKP-TKA) | economicamente assurdo per 3 mesi |
| **E28A** (investor PT PMA) | Si ma modal IDR 10 mld + capital lock 12 mesi | fuori scope 3 mesi |

**Requisiti E33G**: reddito >= **USD 60.000/anno** da fonte estera + saldo **USD 2.000** + **contratto con datore di lavoro estero** + assicurazione. NO sponsor. Validita 1 anno (estendibile, max 2). Apply online evisa.

**CAVEAT BLOCCANTE — gate "contratto datore estero" per un creator autonomo** (devils-advocate finding, S9): E33G e' costruito attorno a un *remote worker* con un *employment contract* presso un'azienda estera. Marc e' un creator **autonomo** (brand partnership multiple, non un singolo datore). Va verificato come la sua struttura reddituale soddisfa il requisito "contratto datore estero": (a) tramite la sua entita/societa estera che lo "impiega", oppure (b) contratti di servizio con i brand documentabili come rapporto di lavoro estero. Se nessuna delle due regge, l'E33G NON e' automaticamente concedibile e va rivalutata la struttura (es. PT PMA self-sponsor, fuori scope 3 mesi). **Questo e' un secondo blocco oltre alla soglia reddito — non solo "income + barter docs".**

**Vincolo critico barter** (NB-2 source_id 09d6e396, RESTRIZIONI CRITICHE verbatim): E33G VIETA di lavorare per aziende indonesiane e generare reddito da fonti locali. Il barter "camera-per-promo" con hotel di Bali = lavoro non autorizzato indipendentemente dal pagamento in natura ("atau sejenisnya" copre il compenso in natura). La triangolazione estera (hotel paga la societa SA) riduce ma NON elimina il rischio — NB-2 declina di dichiararla sicura (zona grigia ad alto rischio per profilo 2M follower).

**Enforcement context**: Operasi Dharma Dewata (lanciata 15 apr 2026): 62 WNA fermati in ~20 giorni, target esplicito influencer/content creator, ban re-entry 5y/10y/a-vita. Profilo Marc = target diretto Tim Pora.

## 3. Cost — PricingTool (Bali Zero Official Prices 2026, version 2026.1)

> Prezzi da `bali_zero_official_prices_2026.json` (source-of-truth dichiarata in `pricing_service.py:4,30-31`). NESSUN prezzo da DeepSeek o user-input.

| Voce | Configurazione | Prezzo Bali Zero (IDR) |
|---|---|---|
| **E33G Remote Worker KITAS** | Offshore (apply da fuori IDN, raccomandato per nuovo ingresso) | **13.000.000** |
| E33G Remote Worker KITAS | Altus/Onshore (se gia in Indonesia) | 14.000.000 |
| E33G Remote Worker — Extend | (non rilevante per singolo soggiorno 3 mesi) | 10.000.000 |

**Quote raccomandata**: E33G Offshore = **IDR 13.000.000** (fee servizio Bali Zero, listino pacchetto 2026). Per 3 mesi NON serve extend.

Costo verde MA quote non send-ready finche income docs non confermano la soglia USD 60k (vedi sezione 5).

## 4. Timeline

- **E33G Offshore**: apply online evisa → approvazione e-VITAS → ingresso → conversione KITAS onshore. Avviare la pratica PRIMA dell'ingresso (offshore) per non entrare con visto turistico e dover convertire onshore (piu caro: 14M). Il listino 2026 non pubblica SLA esplicito; per urgenza esistono pacchetti Urgent 1-3 giorni a parte.
- **Finestra cliente**: giugno–settembre 2026.

## 5. Risk + documenti mancanti (BLOCCANTI per send)

| Rischio | Mitigazione |
|---|---|
| **Barter hotel = lavoro non autorizzato** | Tenere TUTTI i deal hotel FUORI Indonesia: contrattualizzare + pagare l'entita estera di Marc. MAI barter locale informale. |
| **Profilo alto = target Dharma Dewata** | E33G corretto + zero attivita locale visibile in pagamento-natura. |
| **Soglia reddito non provata** | Richiedere prova reddito estero >= USD 60k/anno (brand contract / payslip / Payoneer 3-6 mesi). |
| **Saldo non provato** | Richiedere conferma saldo USD 2.000. |

**Documenti da richiedere a Marc (pre-quote send)**:
1. Prova reddito da fonte non-indonesiana (>= USD 60k/anno).
2. Conferma saldo USD 2.000.
3. **Struttura contrattuale del rapporto di lavoro estero** (entita/societa che lo impiega O contratti brand documentabili) — necessaria per soddisfare il gate "contratto datore estero" E33G per un creator autonomo.
4. Quadro deal hotel: barter informale o contrattualizzabile via entita estera?

## 6. Deliverable

- Questo dossier (`research/visa/clients/2026-06-03-marc-buckner-S9-dossier.md`).
- Documento cliente brand A4 gia esistente: `2026-05-31-marc-buckner-visa-guidance.pdf` (2 pagine).
- Quote E33G IDR 13.000.000 — da finalizzare a documenti ricevuti.

## Devils-Advocate (gate pre-output)

Prima passata Codex read-only: **NEEDS-FIX** (3 finding). Adjudicazione + fix applicati:

1. *"E33G framing troppo netto come soluzione del caso intero"* — ACCOLTO: tabella eligibility e verdetto ora chiariscono che E33G copre SOLO la gamba reddito-estero, non il barter ne risolve l'intero caso.
2. *"gate contratto-datore-estero non trattato come blocco"* — ACCOLTO (finding piu importante): aggiunto CAVEAT BLOCCANTE — Marc e' un creator autonomo, il requisito "contratto datore estero" E33G va verificato e puo non essere automatico. Aggiunto come doc mancante #3.
3. *"triangolazione hotel-estero troppo pulita"* — PARZIALE: il testo gia diceva "riduce ma NON elimina... zona grigia ad alto rischio". Lasciato com'e (gia conforme alla source NB-2 che declina di dichiararla sicura).

**Verdetto post-fix: PASS** (con 2 blocchi NEEDS-ANTONELLO espliciti: soglia reddito + struttura contrattuale datore estero). Cost esclusivamente da PricingTool; C5A escluso come non-operativo; nessun KBLI richiesto (caso visa puro). Math n/a per questo caso.
