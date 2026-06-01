---
date: 2026-06-02
domain: legal
client_case: false
sources:
  - "PP 28/2025 (sostituisce PP 5/2021) — Penyelenggaraan Perizinan Berusaha Berbasis Risiko (OSS-RBA), in vigore 5 giugno 2025"
  - "Permen Investasi/BKPM 5/2025 — Pedoman dan Tata Cara Penyelenggaraan PBBR (sostituisce BKPM 3/2021, 4/2021, 5/2021)"
  - "UU 25/2007 Penanaman Modal Pasal 33 (anti-nominee), come modificata da UU 6/2023 Cipta Kerja"
  - "Perka BKPM 13/2017 Pasal 12 ayat (6) — divieto perjanjian nominee verbatim"
  - "Perpres 10/2021 + Perpres 49/2021 — Bidang Usaha Penanaman Modal (Positive Investment List)"
  - "Perda Provinsi Bali 4/2026 (24 feb 2026, Gov. Koster) — criminalizzazione nominee"
  - "NB-3 Company Setup Indonesia 2025 (NotebookLM ground-truth, query 2026-06-02)"
verification: "DeepSeek V4 Pro numeric/contradiction check 2026-06-02 — 12/13 claim OK; 1 caveat soglia >10B (vedi §2)"
---

# PT PMA, divieto nominee e sistema BKPM/OSS-RBA — stato regolatorio 2025-2026

> Ground-truth verbatim da NB-3 (193 source). Il quadro è stato **trasformato dall'Omnibus
> Law** (UU 6/2023, consolida UU 11/2020): PP 28/2025 sostituisce PP 5/2021 e Permen BKPM
> 5/2025 sostituisce BKPM 3/2021+4/2021+5/2021. Numeri pre-2025 (es. "modal disetor 10mld")
> sono **stale** e vanno corretti.

## 1. Capitale: la distinzione che quasi tutti sbagliano

Esistono **due soglie distinte** che vanno tenute separate:

| Concetto | Valore 2025 | Fonte | Note |
|---|---|---|---|
| **Modal ditempatkan/disetor** (capitale versato) | ≥ **IDR 2.500.000.000** per PT | BKPM 5/2025 Pasal 26(10) | Ridotto drasticamente vs passato |
| **Nilai investasi** (investimento totale) | **> IDR 10.000.000.000** per KBLI 5-digit per location | PP 28/2025 Pasal 212(2) | Esclude tanah+bangunan (salvo settori immobiliari) |

Verbatim Pasal 26(10) BKPM 5/2025:

> "Ketentuan minimum permodalan bagi PMA … merupakan modal ditempatkan/disetor paling
> sedikit Rp2.500.000.000,00 (dua miliar lima ratus juta Rupiah) per perseroan terbatas,
> kecuali ditentukan lain berdasarkan ketentuan peraturan perundang-undangan."

**Lock-up 12 mesi** sul capitale versato — Pasal 27(1) BKPM 5/2025:

> "Modal ditempatkan/disetor … tidak dapat dipindahkan dari rekening badan usaha untuk
> waktu paling singkat 12 (dua belas) bulan terhitung sejak ditempatkan/disetor, kecuali
> dalam rangka pembelian aset, pembangunan bangunan gedung, dan/atau operasional badan
> usaha."

## 2. Investimento totale > 10 miliardi

Verbatim PP 28/2025 Pasal 212(2):

> "Ketentuan minimum investasi bagi Penanaman Modal Asing … per bidang usaha KBLI 5 (lima)
> digit per lokasi usaha harus lebih besar dari Rp10.000.000.000,00 (sepuluh miliar
> rupiah), di luar tanah dan bangunan."

**Caveat numerico (DeepSeek flag #3)**: la soglia è *"lebih besar dari"* (maggiore di)
10 miliardi, **non** uguale. Il gap residuo dopo i 2.5mld versati è quindi `> 7.5mld`
(non esattamente 7.5mld), da realizzare progressivamente via capex/opex (macchinari,
attrezzature, costi costruzione, capitale circolante).

**Eccezione settore immobiliare/ricettivo**: per KBLI 68111 (Real Estate, TERBUKA) o
55194 (Vila, TERBUKA) il **valore di terra+edifici conta** verso la soglia 10mld — beneficio
significativo per PT PMA property-focused. Eccezioni quantitative per perdagangan besar
(4-digit KBLI) e jasa makanan/minuman (2-digit KBLI per location) ex Pasal 212(3).

## 3. Divieto nominee — base normativa e sanzioni 2026

Il divieto nasce da **UU 25/2007 Penanaman Modal Pasal 33** e ribadito verbatim nella
**Perka BKPM 13/2017 Pasal 12 ayat (6)**:

> "Penanam modal dilarang membuat perjanjian dan/atau pernyataan yang menegaskan bahwa
> kepemilikan saham dalam perseroan terbatas untuk dan atas nama orang lain, sesuai dengan
> peraturan perundang-undangan."

Conseguenze (cumulative):

- **Civile**: accordo nominee *legally void* (nullo di pieno diritto), perdita totale dei
  diritti sugli asset societari, nessuna tutela in giudizio (dottrina "unclean hands").
- **Penale (NUOVO, Bali)**: Perda Bali 4/2026 (firmata 24 feb 2026 dal Gov. Wayan Koster)
  **criminalizza** i trasferimenti nominee — fino a **5 anni di reclusione + multa fino a
  IDR 1 miliardo** (riferimento UU 41/2009 + KUHP). Colpisce **sia lo straniero sia il
  nominee indonesiano**, più intermediari/facilitatori. **Nessun grandfathering** per accordi
  esistenti.

> Vedi anche `research/property/2026-06-02-foreign-property-rights-hak-pakai-hgb-leasehold.md`
> per il nominee sul *Hak Milik* (UU 5/1960 Pasal 26(2)).

## 4. BKPM e sistema OSS-RBA (Risk-Based Approach)

PP 28/2025 trasforma OSS in **OSS-RBA**. Verbatim Pasal 1(1):

> "Perizinan Berusaha Berbasis Risiko yang selanjutnya disingkat PBBR adalah perizinan
> berusaha yang menggunakan pendekatan berbasis risiko yang diperoleh dari hasil analisis
> risiko setiap kegiatan usaha."

4 livelli di rischio → licenze richieste:

| Livello | Licenza | Esempi KBLI |
|---|---|---|
| Risiko Rendah | solo NIB | 70201 consulenza, 62010 software, 74300 traduzioni |
| Risiko Menengah Rendah | NIB + Sertifikat Standar autodichiarato | 56101 ristorante, 55130 pondok wisata, 93139 yoga |
| Risiko Menengah Tinggi | NIB + Sertifikat Standar verificato | (verifica DPMPTSP, 3-14gg) |
| Risiko Tinggi | NIB + Izin formale preventiva | 86102 clinica (TERBATAS max 67% WNA) |

Novità PP 28/2025: modello di **compliance continua** (non licensing one-off), PBG+SLF
obbligatori prima che il NIB sia efficace, KKPR auto-approvazione 25 giorni lavorativi
(fiktif positif).

**LKPM (Laporan Kegiatan Penanaman Modal)**: report trimestrale obbligatorio per tutte le
PT PMA via OSS. La mancata presentazione è **la causa n.1 di sospensione del NIB nel 2026**.

## Checklist operativa Bali Zero

- [ ] Verificare modal disetor ≥ 2.5mld versato + lock-up 12 mesi rispettato
- [ ] Pianificare realizzazione investimento totale > 10mld (gap > 7.5mld via capex/opex)
- [ ] Verificare classe rischio KBLI per determinare licenze (NIB / Sertifikat Standar / Izin)
- [ ] **MAI** proporre struttura nominee — void civile + penale a Bali (Perda 4/2026)
- [ ] Calendarizzare LKPM trimestrale (sospensione NIB se omesso)
- [ ] Per property: valutare se terra+edifici contano verso i 10mld (KBLI 68xxx/55xxx)
