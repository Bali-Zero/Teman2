---
date: 2026-06-13
domain: operations (cross: visa, tax, company-kbli, property)
client_case: none — internal knowledge-layer audit
sources:
  - 4 parallel read-only extraction subagents (WA bridge canonicals, Postgres prod read-only MCP, mouth pillar pages, KB interna: golden set + generated guides + kb/ + data JSON)
  - 4 parallel Opus verification subagents (web, fonti ufficiali: peraturan.bpk.go.id, bps.go.id, pajak.go.id, kemenimipas.go.id, imigrasi.go.id + secondarie legali convergenti)
  - orchestrator adversarial re-verify dei 4 verdetti load-bearing (PerBKPM 5/2025 Pasal 285(3), Perda Bali 4/2026, Permenkum 49/2025, deadline KBLI 18/06/2026) — tutti confermati indipendentemente
  - production data re-check via mcp__postgres-nuzantara (kbli_documents: divisione 62 rinumerata, 68xxx=14, 56101 presente)
author: Claude Fable 5 (autonomous session, M5)
---

# La TAC della Conoscenza — knowledge-decay audit dello stack di risposte cliente

> Topic eseguito in autonomia su richiesta di Antonello ("un topic che solo tu puoi fare
> qualitativamente e profondamente"), scelto per NON duplicare le due sessioni attive:
> la TAC dell'organismo (2026-06-13, plumbing) e lo sciame fix F/A (codice). Questo audit
> copre il terzo strato, mai auditato: **la conoscenza che Bali Zero vende** — ciò che il
> sito pubblica, ciò che il bot WhatsApp afferma, ciò che il DB serve a `search_kbli` e
> al PricingTool — verificato contro la realtà regolatoria indonesiana di giugno 2026.

## 0. Executive summary

**128 claim regolatori estratti da 4 superfici** (48 bridge WA, 57+4conflitti sito mouth,
13 golden set, 15 generated guides + 5 KB legale, inventario DB prod). **41 verificati
contro fonti esterne** + 4 ri-verificati indipendentemente dall'orchestrator + 3 risolti
su dati di produzione. Risultato:

- **Il bridge WhatsApp è SANO**: tutti i canonical verificati CURRENT (IVA 11/12 PMK
  131/2024, overstay 1M/die PP 28/2019, nominee void UU 25/2007 Pasal 33, crosswalk
  villa 55193→55203, finestre LKPM 1–15 con guard di scadenza). Il lavoro W68–W73 ha
  prodotto un layer canonico che REGGE la verifica esterna.
- **Il sito mouth è il malato**: 8 errori P0 client-facing live, tra cui il guide
  compliance che insegna le deadline LKPM **abrogate** (il 10 del mese — PerBKPM 5/2025
  Pasal 285(3) le ha spostate al 15; **il sito contraddice il bot**, che quelle stesse
  date clobbera come stale), la tabella capital ferma al regime 2021 (paid-up 10B; oggi
  2.5B per Perka BKPM 5/2025 Pasal 26(10)) **in contraddizione con la FAQ della stessa
  pagina**, e un articolo immigration che chiama l'E33G "investor KITAS" e usa codici
  morti (C312, B211A-as-current).
- **Tre falsi-sospetti si sono rivelati REALI** (Permenkum 49/2025, Perda Bali 4/2026,
  deadline KBLI 18/06/2026) e **un verdetto di un verificatore è stato refutato dai dati
  di produzione** (il "data gap 62010" non esiste: KBLI 2025 ha rinumerato la divisione
  62; 62010 è un codice KBLI 2017). Tesi verificatore-imperfetto: riconfermata due volte,
  in entrambe le direzioni.
- **Root cause sistemica**: i tubi di ingresso della freschezza sono morti — delta
  regolatori fermi al 31/05, feeder NB-INTEL in pausa, tabelle `regulatory_changes` /
  `tax_obligations` / `compliance_alerts` VUOTE (0 righe), generated guides congelate al
  27–31/03. Quattro cambi regolatori material (PerBKPM 5/2025, Permenkum 49/2025,
  Perda Bali 4/2026, PP 20/2026) sono entrati nel mondo; solo il bridge li riflette.
- **3 opportunità business a scadenza**: deadline KBLI 18/06 (**5 giorni**), deadline
  RUPS/laporan tahunan 30/06 (**17 giorni**, sanzioni SABH da nov 2026), e i clienti
  tax sul regime 0.5% UMKM da avvisare (PP 20/2026 esclude le PT regolari).

**Terapia shippata in questa sessione**: fix chirurgici dei 3 errori P0 più netti
(date LKPM ×3, tabella capital + InfoCard, sanzione "NIB suspension"→SABH) — PR separata.
Il resto in coda prioritizzata (§8).

## 1. Metodo

1. **Estrazione** (4 subagent read-only paralleli): ogni claim con id, fonte file:funzione,
   dominio, date-sensitivity. Nessuna verità assunta in estrazione.
2. **Spot-check su disco** dell'orchestrator PRIMA della verifica esterna (disciplina
   anti-allucinazione: i report degli agent sono lead, non fatti — META-autopsy scar).
   Tutti i claim load-bearing confermati verbatim su disco.
3. **Verifica esterna** (4 subagent Opus paralleli, uno per dominio): web + fonti
   ufficiali, con vincolo esplicito "training data non è current, verifica live o
   dichiara UNVERIFIABLE".
4. **Pass avversariale dell'orchestrator** sui 4 verdetti load-bearing (ri-search
   indipendente) + re-check su DB di produzione per i claim sul catalogo KBLI.
   Esito: 4/4 confermati; 1 verdetto subagent (V2.4) REFUTATO dai dati di produzione.

## 2. Verdetti P0 — WRONG client-facing, live oggi

| # | Errore | Dove (verbatim su disco) | Realtà giugno 2026 | Stato |
|---|---|---|---|---|
| P0-1 | LKPM "Q1 by April 10, Q2 by July 10, Q3 by October 10, Q4 by January 10" | `apps/mouth/src/content/articles/business/pt-pma-first-year-compliance.mdx` righe 45, 275, 356 | Deadline spostate **al 15** da PerBKPM 5/2025 Pasal 285(3) (eff. reporting 2026). Finestra 1–15 del mese post-trimestre. Q2 2026 = 1–15 luglio. Il bridge WA già clobbera "10 april/july/…" come stale marker (`_guard_lkpm_reply`): **il sito insegnava ciò che il bot cancella** | **FIXED (PR fix batch-1)** |
| P0-2 | Tabella "Paid-up Capital: IDR 10 billion (must match total investment now)" + InfoCard "2021 Changes" | `capital-requirements-guide.mdx` righe ~109–120 — in contraddizione con FAQ/seoDescription della STESSA pagina (2.5B) | Paid-up minimo **IDR 2.5 miliardi** da Perka BKPM 5/2025 Pasal 26(10) (ott 2025, lock-in 12 mesi); investimento totale **>10B per KBLI a 5 cifre per location** invariato (Pasal 26(2)) | **FIXED (PR fix batch-1)** |
| P0-3 | "Regulation 49/2025 … failure triggers automatic NIB suspension" | `pt-pma-first-year-compliance.mdx` riga ~75 | Permenkum 49/2025 è REALE (eff. 17/12/2025; obbligo via SABH da 01/06/2026) ma la sanzione è **warning scritto → blocco accesso SABH/AHU** (Pasal 17), NON sospensione NIB (il NIB è OSS, non SABH). Sanzioni operative da **nov 2026**. Deadline RUPS: **30 giugno** | **FIXED (PR fix batch-1)** |
| P0-4 | "E33G **investor** KITAS", "C312 retirement", "B211A … total of 60 days" presentati come permessi correnti; "Second Home introdotta da **Perpres 37/2022**" | `bali-immigration-law-what-expats-need-to-know-in-2026.mdx` righe 46, 50 | E33G = **Remote Worker** (investor = E28A); C312/B211A = nomenclatura pre-2024 ritirata (oggi C1/C2, E33E/E33F); B211A consentiva 60+60+60=180, non "60 totali"; Second Home introdotta da **circolari Imigrasi IMI-0740/IMI-0820 (2022)**, non da un Perpres | QUEUED (rewrite editoriale) |
| P0-5 | Codici KBLI 2020 in articolo live: "hotels (**55110**), villa accommodation (**55120**), restaurants (56101)" | `pt-pma-in-bali-the-legal-vehicle-…mdx` riga 41 | In KBLI 2025: hotel = 55101–55105 (split per stelle), villa = **55203**; 56101 esiste ancora (verificato su catalogo prod). Deadline nazionale di switch: **18/06/2026 — 5 giorni** | QUEUED |
| P0-6 | Retirement KITAS: "USD 1,500/mese, 55+, **no corporate sponsor**, 1 anno" come unica regola | `visa/kitas/page.mdx` righe 37, 76 + DB `visa_types` E33E etichettata "55+" + pricing "Age 60+" | Esistono DUE percorsi: **E33F** (55+, CON guarantor/sponsor, pension ~USD 1.5–3k/mese, 1 anno rinnovabile) ed **E33E "Silver Hair"** (60+, NO sponsor, deposito USD 50k banca statale + ~USD 3k/mese, 5 anni). Le tre superfici li fondono in modi diversi e tutti sbagliati | QUEUED (pagina + riga DB) |
| P0-7 | "Short-term rental operators must hold a valid **Pondok Wisata** license" senza caveat | `balis-airbnb-era-under-pressure…mdx` | Pondok Wisata (KBLI 55130, ≤5 camere) è riservata a **persone fisiche indonesiane** — uno straniero NON può detenerla (e il nominee è sotto crackdown attivo, Perda Bali 4/2026). La via per stranieri è PT PMA + KBLI 55203 via OSS-RBA | QUEUED |
| P0-8 | "Sarbagita moratorium … GPS-coordinate validation via OSS-RDTR; automatic permit rejection" | `kbli-2025-real-estate-property-investment-bali-2026.mdx` (commit 12/06 — ieri) | Il moratorium ESISTE ma: (a) è **istruzioni esecutive del Governatore** + Kepmenko Marves 163/2024, non Perda/Pergub; (b) il framing "Sarbagita" è stale (proposta set-2024, ritirata gen-2025, reintrodotta set-2025 come 6 distretti + ban province-wide su lahan produktif); (c) il meccanismo "GPS auto-rejection" è **UNVERIFIABLE** — nessuna fonte lo conferma | QUEUED |

## 3. Verdetti P1 — STALE / impreciso / citazione errata

1. **SIUP** richiesto al provider virtual-office (`virtual-offices…mdx` riga 48): SIUP è
   assorbito nel NIB dal regime OSS-RBA (PP 5/2021 → PP 28/2025). Verifica corretta:
   NIB + KBLI + KKPR.
2. **Girik "legally invalid" dal 02/02/2026** (`kbli-2025-real-estate…mdx`): data corretta
   (PP 18/2021 Pasal 96, 5 anni), ma l'effetto preciso è **perde valore come prova di
   proprietà e degrada a "petunjuk"** per la registrazione (Permen ATR 16/2021 Pasal 76A).
   Non diventa automaticamente "state land"; "fully void" è overstatement.
3. **UMKM 0.5%** (generated guide `pph_badan_imposta_reddito_2025.txt`, marzo): **PP 20/2026**
   (22/04/2026) esclude PT/CV/Firma regolari dal regime in avanti (restano individui,
   PT perorangan, koperasi; PT esistenti grandfathered fino a scadenza periodo). Il
   framing "PT 7 anni" non descrive più la legge. **Clienti tax sul 0.5% da avvisare.**
4. **Golden Visa nel DB** (`visa_types` E28B "2.5B", E28F "5B", E28G "5B 10yr"): i tier
   correnti sono denominati in **USD** (passivo: 350k/5yr, 700k/10yr; attivo: 2.5M/5M;
   corporate 25M/50M). Le cifre IDR in tabella non corrispondono ad alcun tier corrente
   — righe da ri-verificare contro evisa.imigrasi.go.id e correggere.
5. **KITAP**: "5 anni" (comparisons page) vs "3 anni" (generated guide) — la regola è
   **per categoria** (coniuge WNI ~2, investor/director ~4, lavoratore ~5). Entrambe le
   superfici sovrasemplificano.
6. **Citazioni stale**: golden set G-12 cita Permen ATR 29/2016 per gli 80 anni Hak Pakai
   (base corrente: **PP 18/2021**); capital guide generated cita Perpres 49/2021 per il
   2.5B (base: **Perka BKPM 5/2025**); soglia prezzo casa Bali 5B va citata da
   **Kepmen ATR/BPN 1241/SK-HK.02/IX/2022**, non Permen 18/2021.
7. **E33G "valid 1–2 years"** (articolo e33g + guide K-09): fonti convergono su **1 anno,
   non rinnovabile** (exit + re-apply). Da uniformare.
8. **B211A 60 vs 180 giorni** tra due articoli (CONFLICT-03): la pagina comparisons (180)
   è quella giusta; comunque B211A è nomenclatura morta (cfr. P0-4).
9. **"All 14 real-estate KBLI 68xxx 100% open"**: il conteggio 14 TORNA col catalogo prod
   (68111–68299, inclusi i nuovi 68122/68123/68126), ma "tutti 100% open" è blanket —
   i codici area-management (KEK/industrial) portano condizioni settoriali; vincoli
   pratici (zonizzazione, moratorium, soglie prezzo) restano.

## 4. Dati di produzione — esito re-check

- **Catalogo KBLI prod è genuinamente KBLI 2025-keyed** (1.563 righe, `kode_kbli_2025` su
  tutte, crosswalk `pp28_sources` → codici 2020). Raro nel settore: un asset.
- **Verdetto subagent V2.4 REFUTATO**: "62010 missing = data gap" è FALSO. KBLI 2025 ha
  **rinumerato la divisione 62** (62110 gaming/software, 62191–62199 app/AI, 62201–62209
  cyber/IoT, 62900) con crosswalk dai codici 2020 (62011–62029). 62010 è KBLI **2017**,
  già splittato nel 2020. `search_kbli` NON è cieco sul software.
- **Divisione 45 (auto trade/repair) assente** dal catalogo: 4 sole righe portano source
  45xxx (46611…95320 — redistribuzione trade→46/47, repair→95). Plausibile per design
  KBLI 2025, ma la completezza della redistribuzione va riconciliata contro la **Tabel
  Konversi BPS 22/04/2026** (P3, script una tantum; ufficiale ~1.560 kelompok vs nostri 1.563).
- **Tabelle `regulatory_changes`, `tax_obligations`, `compliance_alerts`: 0 righe.** Lo
  schema dell'osservabilità compliance esiste, non è mai stato alimentato.
- **LKPM prod**: 69 report 2026-Q1 di cui 61 draft / 6 pending / 2 submitted a giugno —
  backlog operativo reale (la deadline Q1 era il 15/04).
- `legal_instruments` (5 righe) è COERENTE con la verifica esterna (Permenkumham 22/2023
  "partially_superseded" ✓ da Permen Imipas 3/2025; UU 63/2024 ✓; ministero Imipas ✓).

## 5. Mappa delle contraddizioni cross-surface (il punto sistemico)

| Fatto | Bridge WA | Sito mouth | DB prod | Guides/Golden |
|---|---|---|---|---|
| Deadline LKPM | 1–15 (CURRENT) | "by the 10th" (WRONG) | finestre 2026-Q1 ok | guide LKPM cita Perka 5/2025 ✓ |
| Paid-up PT PMA | defer ai tool | 10B E 2.5B nella stessa pagina | — | 2.5B ✓ (citazione stale) |
| Retirement | defer | E33F-ish senza sponsor (WRONG mix) | E33E "55+" (mislabel) | E33F 55+ ✓ |
| B211/C-series | legacy framing ✓ | B211A as-current (WRONG) | C-series 2024 ✓ | ✓ |
| Villa KBLI | 55203 + transizione ✓ | 55120 (KBLI 2020) | 55203 ✓ | 55203 ✓ |

Non esiste una **SSOT dei claim regolatori**: ogni superficie è aggiornata da agenti
diversi in momenti diversi. Il bridge è curato (W68–W73), il DB è buono, il sito decade.

## 6. Root cause — i tubi della freschezza sono morti

1. `research/regulatory/*-delta.json`: ultimo delta **2026-05-31** (13 giorni di buio;
   regulatory-watcher non verificabile da M5 — Pro irraggiungibile via SSH al momento
   dell'audit).
2. Feeder NB-INTEL Immigration/Regulation/Tax **PAUSED** (stale-alarm 22/06, cfr. TAC).
3. Tabelle compliance del DB **mai alimentate** (0 righe).
4. Generated guides **congelate al 27–31/03** (66 file) — pre-PP 20/2026.
5. Golden set S18 congelato al 02/06 (13 coppie — regge ancora, 1 citazione stale).

Nel frattempo il mondo ha prodotto: Perka BKPM 5/2025 (ott), Permenkum 49/2025 (dic),
Perda Bali 4/2026 (feb), PP 20/2026 (apr), tabel konversi KBLI (apr). **Decay rate
osservato: ~1 cambio material/mese; superficie pubblica aggiornata: solo in parte.**
Famiglia W74/"green-but-empty": gli organi esistono, non sono nutriti.

## 7. Cosa è sano (credito dove dovuto)

- **Bridge WA: 100% dei canonical verificati CURRENT** — incluse le scelte difensive
  (finestra LKPM con auto-scadenza al 30/04, transizione KBLI esplicitata, nominee
  "illegal and void" confermato da UU 25/2007 Pasal 33 + Perda Bali 4/2026 reale).
- Golden set S18: 12/13 reggono pienamente; G-05 (Perda Bali 4/2026) CONFERMATO reale.
- Pricing: DB `practice_types` ↔ `bali_zero_official_prices_2026.json` coerenti.
- VAT 11/12 (PMK 131/2024), overstay 1M/die (PP 28/2019), PPh brackets/22%/PKP 4.8B,
  Coretax full-2026 (con KEP-55/PJ/2026 relief FY2025): tutti CURRENT.

## 8. Coda di correzione prioritizzata

**Shippato ora (PR fix batch-1, 2 file)**: P0-1 date LKPM ×3 · P0-2 tabella capital +
InfoCard · P0-3 sanzione SABH (non NIB).

**P0 restanti (rewrite editoriali, ~1 sessione mouth)**: P0-4 paragrafo immigration
(E33G/C312/B211A/Perpres) · P0-5 codici hotel/villa KBLI 2025 · P0-6 split E33E/E33F
(pagina + riga DB `visa_types`) · P0-7 caveat Pondok Wisata · P0-8 moratorium (forma,
scope, rimuovere GPS-claim).

**P1**: SIUP→NIB/KKPR · girik nuance · alert clienti 0.5% (PP 20/2026) + rigenerare
`pph_badan` guide · Golden Visa rows DB · KITAP per-categoria · citazioni (G-12,
capital guide, soglia 1241/2022) · E33G 1 anno · dedup B211A.

**P2 (strutturale)**: (a) **knowledge-freshness sentinel** — riusare il claim-ledger di
questo audit come baseline: ogni delta del regulatory-watcher diffa contro il ledger e
apre item di correzione per superficie (chiude il loop che oggi non esiste); (b) estendere
il golden set S18 con i claim qui verificati (LKPM 15, paid-up 2.5B, Permenkum 49/2025,
PP 20/2026, E33E/E33F) — da 13 a ~25 coppie; (c) riconciliazione KBLI vs Tabel Konversi
BPS (P3).

**Business (a scadenza)**: campagna clienti **KBLI 18/06** (5 giorni; messaggio onesto:
conversione automatica se nessun cambio di sostanza — niente allarmismo, ma le pratiche
con cambio scope vanno adeguate) · campagna **RUPS/laporan tahunan 30/06** (Permenkum
49/2025; sanzioni SABH da nov 2026 — servizio nuovo potenziale) · outreach clienti tax
su **PP 20/2026**.

## 9. Meta — il verificatore imperfetto, due volte

1. I miei sospetti "Permenkum 49/2025 fabbricato" e "Perda Bali 4/2026 sospetta" erano
   SBAGLIATI: entrambi reali (il primo con sanzione mis-citata dall'articolo — l'errore
   c'era, ma altrove).
2. Il verdetto del subagent "62010 data gap" era SBAGLIATO: refutato dal crosswalk di
   produzione. Senza il re-check orchestrator avrei pubblicato un finding falso.
   Regola confermata: **nessun verdetto load-bearing entra nel report senza una seconda
   verifica indipendente** (W65; META-autopsy; "errare è umano, allucinare è diabolico").

## 10. Azioni solo-operatore

1. Decidere le 3 campagne a scadenza (§8 Business) — finestra utile: questa settimana.
2. Review/merge delle 2 PR (report + fix batch-1) e assegnare la coda P0 restante
   (mouth è perimetro condiviso con SubBZ/sancho — coordinare).
3. Far ripartire i feeder regolatori (delta + NB-INTEL) — senza, questo audit scade
   come tutto il resto: la fotografia è di oggi, il decay continua.
