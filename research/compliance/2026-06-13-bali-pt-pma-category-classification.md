---
date: 2026-06-13
domain: compliance
client_case: false
sources:
  - "BI Bali / BKPM — realisasi investasi Bali 2025 (Rp 42,82T, +17,85% YoY, 97% terziario) — NB-INTEL-Press art. 'BI: Investasi di Bali tetap menarik' (9 giu 2026)"
  - "Balipost — Badung 2025 Rp 22,21T, 72,4% PMA, top sektor perumahan/hotel-restoran (3 feb 2026): https://www.balipost.com/news/2026/02/03/525247/"
  - "Kompas — hotel & restoran settore favorito, ~2.513 progetti PMA: https://www.kompas.com/properti/read/2024/02/08/133000321/"
  - "ANTARA Bali — Bali ajukan PMA risiko rendah ditutup (lettera Governatore 28/1/2026): https://bali.antaranews.com/berita/398242/"
  - "xpnd.co.id — Bali proposes closing 7 KBLI to PMA (68111/70209/79110/77100): https://xpnd.co.id/regulatory/bali-kbli-closure-2026/"
  - "SAS Bali — Bali closes low-risk PT PMA licenses: https://sasbali.com/bali-pt-pma-restrictions-2026/"
  - "LMI Consultancy — Bali restricts new low-risk PMA: https://www.lmiconsultancy.com/bali-restricts-new-foreign-owned-company-pt-pma-registrations-for-low-risk-business-sector/"
  - "Indoned — Permeninves/BKPM 5/2025 capital threshold (paid-up Rp 2,5bn, investimento >Rp 10bn/KBLI): https://www.indoned.id/new-foreign-capital-threshold-for-pt-pma-in-indonesia-under-ministerial-regulation-no-5-2025/"
  - "data.bkpm.go.id — realisasi investasi 2025 per settore/provincia: https://data.bkpm.go.id/visualisasi-detail/data-realisasi-investasi-tahun-2025-berdasarkan-sektor"
  - "NotebookLM NB-3 Company Setup Indonesia 2025 (UUID 933509f9, 283 sources) — catalogo KBLI 'piu frequenti per clienti Bali Zero' + verified note 2026-06-09 sul blocco provinciale 70209"
  - "NotebookLM NB-INTEL-Press (UUID 9d262101, 223 sources) — trend stampa 2026: nominee crackdown, OSS/NIB abuse, Investment Desk Bali"
---

# Classificazione categorie PT PMA/PMDN a Bali — le che coprono ~90% delle societa (giugno 2026)

## Scopo

Domanda dell'operatore (Antonello): incrociando KB/RAG/NLM/Peraturan + news/editoriali, classificare **quali categorie (KBLI/settori) costituiscono concretamente il ~90% delle PT PMA / PT PMDN a Bali**. Output usabile per pricing, contenuti (WR2/WR3), qualificazione lead, e brief cliente.

## Caveat metodologico (onesta sui dati)

- La **distribuzione KBLI per-cliente dalla tabella `companies`** del CRM NON e stata estraibile in questo turn: il tunnel MCP `postgres-nuzantara` verso Fly e caduto a meta query (famiglia cicatrice W75 — Fly tunnel droppa mid-session) e il PG17 locale M5 non ha `nuzantara_dev` popolato. Quindi la classificazione **NON** e una conta empirica del nostro book, ma una **sintesi triangolata** di: (a) dati ufficiali BKPM/BI 2025, (b) il catalogo KBLI di NB-3 che annota esplicitamente i codici "piu frequenti per clienti Bali Zero", (c) stampa 2026 su trend e crackdown.
- Il CRM via API (`get_client_stats`, 1470 clienti) conferma un **book visa-heavy**: le practice company registrate sono poche decine (New Company PT PMA, New PT, Revision Company/Akta Perubahan ~35 in 30gg) vs. centinaia di pratiche visa. Questo NON contraddice la classificazione settoriale — dice solo che le PT che facciamo sono prevalentemente PMA villa/F&B/holding per espatriati, non grandi gruppi.
- Le quote percentuali per-numero-di-societa sono **stime ragionate**, non conta diretta. Le quote per-valore-investimento sono dati BKPM/BI verificati.

## I numeri di cornice (Bali 2025, fonti ufficiali)

- Investimento realizzato PMA+PMDN provincia Bali: **Rp 42,82 trilioni** (+17,85% YoY)
- **97% settore terziario**, **88% concentrato nel Sud** (Badung Rp 22,21T, Denpasar Rp 10,61T, Gianyar Rp 4,96T, Tabanan Rp 2,04T)
- Top 3 per **valore**: real estate, accommodation, F&B (BI Bali, giu 2026)
- Per **numero di progetti**, hotel & ristoranti e il primo settore (~2.513 progetti PMA censiti, Kompas)
- Badung 2025: 72,4% PMA / 27,6% PMDN; top settori = perumahan/kawasan industri/perkantoran (Rp 7,07T) -> hotel-restoran (Rp 6,77T) -> jasa lainnya (Rp 4,31T) -> trasporti/telecom (Rp 1,91T) -> perdagangan/reparasi (Rp 1,80T)
- Paesi investitori top: Australia (Rp 3,89T), Singapore + Russia (Rp 3T ciascuno), Francia (Rp 1,95T), Olanda (Rp 1,41T)

## La classifica — categorie che fanno il ~90%

### Fascia A — il cuore (~70% delle societa)

| # | Categoria | KBLI tipici | Quota stimata (per n societa) | Status PMA 2026 |
|---|---|---|---|---|
| 1 | **Accommodation / villa & ospitalita** | 55193 (villa), 55194 (aparthotel), 55110/55120 (hotel) | ~30% | Terbuka 100%. **55130 pondok wisata TERTUTUP** (solo WNI, max 5 camere, owner-residente) |
| 2 | **F&B — ristoranti, cafe, bar, beach club** | 56101 (restoran), 56102 (rumah makan), 56103 (bar), 56210/56211 (catering) | ~15-18% | Terbuka 100% + TDUP + Halal/sanitarie (risk Menengah-Tinggi verified) |
| 3 | **Real estate & development** | 68111 (sviluppo edifici/lotti residenziali), 68200 (property mgmt c/terzi) | ~15% | Terbuka 100% MA **68111 sotto sorveglianza/moratoria proposta** (abuso per affitti brevi al posto di 55193) |
| 4 | **Costruzioni** | 41011 (konstruksi gedung) + specialistiche 43xxx | ~6-8% | **TERBATAS max 67% WNA** + partner locale + IUJK (PUPR) |

### Fascia B — la coda che completa il 90% (~20%)

| # | Categoria | KBLI tipici | Quota | Status PMA 2026 |
|---|---|---|---|---|
| 5 | **Consulenza / management** | 70209, 70201 | ~6-8% storico | CHIUSO a nuove PMA in Bali (lettera Governatore 28/1/2026, primo dei 7 codici approvato). Terbuka 100% a livello NAZIONALE ma bloccato provincia Bali (low-risk) |
| 6 | **Wellness, sport, education** | 93139 (gym/wellness), 93199 (surf/yoga), 96121-2 (spa), 85493 (corsi/yoga teacher training) | ~5% | Terbuka 100% |
| 7 | **Travel & servizi turistici** | 79120 (jasa perjalanan wisata), 79110 (agen perjalanan), 79900 | ~3-4% | Terbuka MA **79110 nella lista di chiusura proposta** |
| 8 | **Trade: ingrosso + retail "grande"** | 46494 (ingrosso gioielli), 47630 (accessori), 47762 (batik/artigianato), 47914/4791x (retail online) | ~4% | Ingrosso low-risk **bloccato dal blocco provinciale**; **minimarket 47111/47112 TERTUTUP**; retail "grande" terbuka solo se Usaha Besar |
| 9 | **IT / digitale / creativo** | 62011/62019 (software), 63122 (portal/piattaforme digitali), agenzie creative | ~3-4% | **63122 HIGH-RISK a scala Besar -> passa il blocco Bali**; retail online puro 4791x low-risk -> bloccato. Richiede SIUPMSE + PSE/Kominfo |

### Fascia C — il residuo (~10%)

Rental veicoli (**77100 — proposto chiuso**, di fatto terreno PMDN/abusivo WNA), saloni/barbershop (riservati UMKM, sotto crackdown), event organizer, produzione media, piccola manifattura F&B, trasporti/logistica (52292 max 49% WNA). Piu i settori riservati UMKM dove vive la zona grigia nominee.

## Tre overlay 2026 load-bearing

1. **Il blocco provinciale ridisegna la mappa.** Da gennaio 2026 DPMPTSP Provinsi Bali blocca le nuove PT PMA su KBLI a rischio **Basso / Medio-Basso** (lettera Governatore 28/1/2026). **70209 gia formalmente chiuso**; proposti per chiusura: 68111 (real estate), 79110 (travel agency), 77100 (motorbike rental). Effetto: la domanda dei solopreneur si sposta verso codici **high-risk legittimi** (63122 piattaforme, 56101 F&B, 55193 villa). NB-3 documenta gia la strategia 63122 per e-commerce.

2. **Per valore != per numero.** Real estate + accommodation + F&B = ~57-60% del *valore*; ma per *numero di societa* la stessa triade + consulenza/wellness copre l'80%+. La **PT PMA mediana a Bali** e una villa company, un ristorante, o (fino al 2025) una consulting mono-socio.

3. **Soglie capitale (Permeninves/BKPM 5/2025 + PP 28/2025).** Ogni PT PMA e per legge *Usaha Besar*: paid-up min **Rp 2,5 mld** (ridotto da 10 mld) MA piano investimento **>Rp 10 mld per ogni KBLI a 5 cifre per location**, esclusi terreni/edifici. Questo e cio che taglia fuori i micro-business e spinge verso il nominee abusivo.

## Status PMA — quick reference (codici chiusi/limitati nei top settori)

- **TERTUTUP (0% WNA):** 55130 pondok wisata . 47111/47112 minimarket/supermarket . 69100 jasa hukum . 86904 praktik dokter mandiri . 01111/01119 agricoltura . 02100 foreste
- **TERBATAS (cap %):** 41011 costruzioni (max 67%) . 52292 cargo/freight (max 49%) . 69200 akuntan publik (max 20%) . 86102 klinik (max 67%)
- **CHIUSO PROVINCIA BALI (low-risk block, naz. terbuka):** 70209 (gia formale) + proposti 68111, 79110, 77100 + ingrosso low-risk (es. 46494)
- **TERBUKA 100%:** 55193/55194/55110/55120 . 56101/56102/56103 . 68200 . 93139/93199 . 85493 . 63122 (high-risk, passa blocco) . 79120

## Checklist operativa (per pricing/lead/contenuti)

- [ ] Quando un lead chiede "PT PMA per [attivita]" -> mappare a KBLI 5-cifre -> verificare status NAZIONALE (Perpres 10/2021) E status PROVINCIA BALI (low-risk block) — sono due filtri distinti.
- [ ] Se attivita low/medium-low-risk a indirizzo Bali -> avvertire del blocco; valutare codice high-risk legittimo (no fiction, OSS field inspection da giugno 2026 revoca NIB per mismatch).
- [ ] Verificare soglia Rp 10 mld investimento/KBLI — sotto soglia = no PMA legittima.
- [ ] Villa short-rental -> 55193 (TDUP, pink zone) NON 68111 (sotto audit) NON 55130 (vietato WNA).
- [ ] Virtual office BANNATO per domicilio PMA Bali — serve indirizzo commerciale reale.
- [ ] Nominee land/shares -> ILLEGALE e nullo (agrarian law), sotto audit attivo 2026 — mai consigliare.

## Da rifare quando il Postgres torna

Conta empirica reale della distribuzione KBLI nel nostro book:
```sql
-- quando mcp__postgres-nuzantara torna O nuzantara_dev locale e popolato:
SELECT <kbli_col>, COUNT(*) FROM companies GROUP BY 1 ORDER BY 2 DESC;
-- + join clients.company_name / practices company_pt_pma per cross-check
```
Questo trasformerebbe le stime di quota (Fascia A/B/C) in numeri verificati del book Bali Zero.
