---
date: 2026-06-02
domain: legal
client_case: false
sources:
  - "Perpres 10/2021 — Bidang Usaha Penanaman Modal (Positive Investment List, abolisce DNI)"
  - "Perpres 49/2021 — Perubahan atas Perpres 10/2021 (Pasal 2 verbatim)"
  - "Perpres 14/2024 + BPS 7/2025 — riclassificazioni KBLI (es. advertising 73100)"
  - "PP 28/2025 + BKPM 5/2025 — quadro OSS-RBA che opera la lista"
  - "NB-3 Company Setup Indonesia 2025 (NotebookLM ground-truth, query 2026-06-02)"
verification: "DeepSeek V4 Pro check 2026-06-02 — claim KBLI/ownership OK"
---

# Positive Investment List e proprietà straniera per KBLI — 2025-2026

> L'Omnibus Law ha **abolito la Daftar Negatif Investasi (DNI)** sostituendola con una
> "Lista Positiva" molto più permissiva (Perpres 10/2021, emendata da Perpres 49/2021).
> Ground-truth NB-3.

## 1. Principio generale: tutto aperto salvo eccezioni

Verbatim Perpres 49/2021 Pasal 2(1):

> "Semua Bidang Usaha terbuka bagi kegiatan Penanaman Modal, kecuali Bidang Usaha:
> a. yang dinyatakan tertutup untuk Penanaman Modal; atau
> b. untuk kegiatan yang hanya dapat dilakukan oleh Pemerintah Pusat."

Quattro categorie effettive:

| Categoria | Descrizione | Impatto PT PMA |
|---|---|---|
| **TERBUKA** | 100% proprietà WNA ammessa | Controllo pieno + diritti di rimpatrio |
| **TERBATAS** | Tetto % proprietà straniera (49%/67%/70%…) | Richiede socio locale WNI |
| **TERTUTUP** | Vietato agli stranieri | Riservato WNI/UMKM/statali |
| **Priority Sector** | Eligibile incentivi (tax holiday, dazi) | Solo settori strategici |

## 2. TERBATAS — i cap percentuali (e gli errori comuni)

| KBLI | Attività | Cap WNA | Nota |
|---|---|---|---|
| 73100 | Aktivitas Periklanan (advertising) | **MAX 49%** (⚠️ NON groundato NB) | ⚠️ Spesso citato erroneamente come TERBUKA. Fonte attribuita BPS 7/2025 + Perpres 14/2024 (TERBATAS, obbligo kemitraan locale). **Verifica 2026-06-03**: il cap 49% NON è confermato dalle fonti curate NB-3 (KBLI) — il NB conferma 68111 Real Estate 100% TERBUKA ma non riporta la % per 73100. VERIFICARE sul testo Perpres 10/2021 lampiran + Perpres 14/2024 prima di citarlo a un cliente |
| 41011 | Costruzioni edili | MAX 67% | |
| 86102 | Klinik (clinica) | MAX 67% | Risiko Tinggi |
| 55120 / 55111 | Accommodation/hotel | ~67% (verificare lista corrente) | Tourism — può richiedere partner |
| 74200 | Fotografia commerciale | TERBATAS | |

## 3. TERTUTUP — vietati al capitale straniero

Riservati esclusivamente a WNI/UMKM. Le PT PMA sono per legge classificate *Usaha Besar*
(grandi imprese) e **non possono** operarvi. Esempi:

- KBLI 01111 Pertanian Padi (riso), 01119 altri cereali
- KBLI 02100 Pengelolaan Hutan (foreste)
- KBLI 47111 Minimarket (< 400m²), 47112 Supermarket, 47191 department store sotto soglia
- KBLI 52221 Kepelabuhanan (porti)
- KBLI 84130 Regulasi Kegiatan Usaha, 89000 media/broadcasting nazionali

⚠️ Usare un nominee per operare in un KBLI TERTUTUP **costituisce reato penale** (vedi
`legal/2026-06-02-pt-pma-nominee-ban-bkpm-oss.md` §3).

## 4. TERBUKA — 100% WNA (esempi frequenti Bali Zero)

- KBLI 62010 Sviluppo Software
- KBLI 70201 Konsultasi Bisnis
- KBLI 55194 Vila (property-focused, terra+edifici contano verso i 10mld)
- KBLI 68111 Real Estate
- KBLI 41012 / 68200 sviluppo e gestione immobiliare

## Checklist operativa

- [ ] Identificare KBLI 5-digit primario + secondari
- [ ] Verificare categoria su lista corrente (TERBUKA/TERBATAS/TERTUTUP) — fonte aggiornata,
      NON solo Perpres 10/2021 (riclassificazioni BPS 7/2025 + Perpres 14/2024)
- [ ] Advertising (73100): trattare come **TERBATAS 49%**, non TERBUKA
- [ ] Se TERTUTUP → struttura PT PMA impossibile, no workaround nominee (penale a Bali)
- [ ] Se TERBATAS → predisporre socio WNI con quota richiesta + waarmerking notarile
      anti-nominee (Perka BKPM 13/2017 Pasal 12(7))
