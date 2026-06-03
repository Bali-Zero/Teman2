---
date: 2026-06-02
domain: tax
client_case: false
sources:
  - "UU 7/2021 (HPP, Harmonisasi Peraturan Perpajakan) — PPh Badan 22%, scaglioni PPh 21"
  - "UU 36/2008 (PPh) Pasal 23, 26 — withholding domestico e non-residenti (verbatim)"
  - "UU 6/2023 Cipta Kerja — branch profit tax BUT (PPh 26 ayat 4)"
  - "UU 28/2007 (KUP) — procedure fiscali generali"
  - "PMK 81/2024 — implementazione CoreTax (PSIAP), chiusura DJP Online legacy"
  - "PMK 168/2023 — sistema TER (Tarif Efektif Rata-rata) per PPh 21 mensile"
  - "PMK 112/2025 (30 dic 2025) — procedure tax treaty (P3B), anti-abuse PPT/BO/LOB"
  - "PwC Indonesian Pocket Tax Book 2026 — scadenze e penalità"
  - "NB-4 Tax & Fiscal Indonesia (NotebookLM ground-truth, query 2026-06-02)"
verification: "DeepSeek V4 Pro numeric check 2026-06-02 — aliquote/scaglioni/deadline 13/13 OK"
---

# Fiscalità Indonesia oltre la PPN: PPh Badan, Withholding, BUT, CoreTax (2025-2026)

> Estende `fact_pmk_131_2024_ppn_effective_rate` (PPN) con i regimi su redditi e ritenute.
> Ground-truth NB-4 (155 source). **Cambio strutturale 2025**: CoreTax (PMK 81/2024) ha
> sostituito definitivamente DJP Online.

## 1. PPh Badan — corporate income tax 22%

Aliquota standard per WP badan dalam negeri e BUT = **22%** dal tax year 2022. Verbatim
UU 7/2021 (HPP):

> "Wajib Pajak badan dalam negeri dan bentuk usaha tetap sebesar 22% (dua puluh dua persen)
> yang mulai berlaku pada tahun pajak 2022."

**PPh 25 (acconto mensile)**: il PPh Badan non si paga a fine anno ma mensilmente.
`PPh 25 mensile = PPh terutang anno precedente / 12`. Scadenza il **15 del mese successivo**.
Conguaglio: kurang bayar (a debito) entro 30 aprile, lebih bayar (a credito) → rimborso/compensazione.

## 2. Withholding tax — PPh 21 / 23 / 26

### PPh 21 — dipendenti/direttori (residenti SPDN)

Scaglioni progressivi UU 7/2021 (HPP) — **verificati DeepSeek, no gap/overlap**:

| Reddito imponibile (PKP) | Aliquota |
|---|---|
| 0 – 60 mln | 5% |
| 60 – 250 mln | 15% |
| 250 – 500 mln | 25% |
| 500 mln – 5 mld | 30% |
| > 5 mld | 35% |

Dal 2024 (**PMK 168/2023**): calcolo mensile semplificato via sistema **TER** (Tarif Efektif
Rata-rata) con tabelle pre-calcolate; conguaglio annuale a dicembre.

### PPh 23 — servizi/royalty domestici (a residenti)

Verbatim UU 36/2008 Pasal 23(1): dipotong **15%** dari jumlah bruto su dividen, bunga, royalti,
hadiah. **2%** su sewa beni non-immobiliari, jasa teknik/manajemen/konsultan/konstruksi.

| Aliquota | Base |
|---|---|
| **15%** | Dividendi, interessi, royalties, premi (a residenti) |
| **2%** | Servizi tecnici/management/consulenza, affitto attrezzature/veicoli |

### PPh 26 — pagamenti a NON residenti (SPLN)

Verbatim UU 36/2008 Pasal 26:

> "… kepada Wajib Pajak luar negeri, dipotong pajak yang bersifat final sebesar 20% (dua
> puluh persen) dari jumlah bruto …"

**20% flat** sul lordo (dividendi, interessi, royalties, servizi a esteri). Riducibile **solo**
via tax treaty (P3B). Requisiti per beneficiare (**PMK 112/2025**, in vigore 30 dic 2025):
Certificate of Domicile (SKD) + test anti-abuso **Beneficial Ownership + Limitation on
Benefits + Principal Purpose Test (PPT)** + conduit/substance rules.

## 3. BUT (Bentuk Usaha Tetap / Permanent Establishment)

Stabile organizzazione tramite cui un soggetto estero opera in Indonesia → **stessi oneri di
un residente** (PPh Badan 22%). In più, **branch profit tax** sul profitto netto rimpatriato.
Verbatim Pasal 26(4) (post UU Cipta Kerja):

> "Penghasilan Kena Pajak sesudah dikurangi pajak dari suatu bentuk usaha tetap di Indonesia
> dikenai pajak sebesar 20% (dua puluh persen), kecuali penghasilan tersebut ditanamkan
> kembali di Indonesia …"

→ **20% addizionale** sul reddito after-tax, **salvo reinvestimento** in Indonesia. Combinato
con il 22% PPh Badan dà un carico effettivo significativo sul profitto rimpatriato di una branch
vs una PT PMA con dividendi (che pagano comunque PPh 26 20% in uscita salvo treaty).

## 4. Residenza fiscale — SPDN vs SPLN (critico per WNA)

Criteri UU 36/2008 Pasal 2 — un WNA è **WP Dalam Negeri (SPDN)** se:

- dimora abituale in Indonesia, OPPURE
- presenza **> 183 giorni in 12 mesi**, OPPURE
- presenza nell'anno fiscale **+ intenzione di stabilirsi** (es. KITAS/KITAP)

SPDN → tassato su **reddito mondiale** (worldwide), aliquote progressive 5-35%, accesso a
treaty. SPLN → solo reddito di fonte indonesiana via PPh 26, niente treaty benefits salvo SKD.
CoreTax **cross-analizza in tempo reale i dati visti immigrazione** per determinare lo status —
classificazione errata = sanzioni automatiche.

## 5. CoreTax — il cambio strutturale 2025-2026

**PMK 81/2024**: CoreTax (PSIAP) sostituisce **definitivamente** DJP Online (dismesso). Tutto
converge in un'unica piattaforma: registrazione, SPT, e-Billing, **e-Faktur** (PPN), **e-Bupot**
(withholding). Accesso con vecchie credenziali impossibile → re-registrazione obbligatoria.

## 6. Scadenze e penalità

| Adempimento | Scadenza |
|---|---|
| PPh 25 (acconto mensile) | 15 del mese successivo |
| SPT Tahunan Badan (1771) | **fine 4° mese** post-chiusura = **30 aprile** (anno solare) |
| PPN (e-Faktur) | mensile via CoreTax |
| PBB | 6 mesi dal ricevimento SPPT |

Late payment: interesse su tasso mensile MoF + surcharge, max 24 mesi (frazione di mese =
mese pieno). Late/missed filing: sanzione amministrativa per importo (PwC Pocket Tax Book 2026).

Allegati obbligatori SPT Tahunan Badan: laporan keuangan (no revisore obbligatorio se omzet
< 50 mld), daftar nominatif biaya, daftar penyusutan, rekonsiliasi fiskal, laporan ekuitas,
TP doc se applicabile.

## Checklist operativa Bali Zero

- [ ] Determinare status SPDN/SPLN cliente WNA (test 183gg + intent/KITAS) — CoreTax incrocia visti
- [ ] PT PMA: PPh Badan 22%, acconti PPh 25 mensili (15 del mese)
- [ ] Withholding: 15% dividendi/royalty domestici, 2% servizi, 20% a non-residenti (treaty?)
- [ ] BUT: avvisare del branch profit tax 20% addizionale salvo reinvestimento
- [ ] Treaty benefit: richiedere SKD + verificare PPT/BO/LOB (PMK 112/2025)
- [ ] CoreTax onboarding: re-registrazione, e-Faktur/e-Bupot, no DJP Online legacy
- [ ] SPT Tahunan Badan entro 30 aprile + allegati completi
