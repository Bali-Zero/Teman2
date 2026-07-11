---
date: 2026-06-19
domain: compliance
client_case: none
status: RESOLVED — 5 forestry/agri needs_review, 2-source verified
---

# 5 forestry/agri `needs_review` — RISOLTI (la presunzione ribaltata)

## Cosa è successo
Lo schema-v2 aveva marcato 5 codici come `TERTUTUP_CANDIDATE` (probabile-chiuso-a-stranieri).
**Erano una MIA presunzione sbagliata** (4 su 5): l'euristica bridge-2020 vedeva `02100 Pengelolaan
Hutan = TERTUTUP` e marcava i forestry vicini per somiglianza-prefisso. Il gate `needs_human_review`
ha impedito che la presunzione diventasse fatto — esattamente lo scopo dello schema a 5 strati.

## Verifica a 2 fonti indipendenti (2026-06-19)
- **NB-3** (Positive Investment List, Perpres 10/2021 + 49/2021)
- **KG live** (`inspect_kbli`)

| Codice | Era (candidato) | Verità verificata | Fonte |
|---|---|---|---|
| 02102 Pemanfaatan Kayu Hutan | TERTUTUP_CANDIDATE | **TERBATAS max 95%** (kemitraan) | NB-3 + KG concordano |
| 02103 Pembenihan Tanaman Kehutanan | TERTUTUP_CANDIDATE | **TERBUKA 100%** | NB-3 |
| 02401 Jasa Lingkungan Hutan | TERTUTUP_CANDIDATE | **TERBUKA 100%** | NB-3 |
| 02402 Jasa Penggunaan Kawasan Kehutanan | TERTUTUP_CANDIDATE | **TERBUKA 100%** | NB-3 |
| 01112 Pertanian Serealia non-Padi/Jagung | TERTUTUP_CANDIDATE | **TERBUKA 100%** (≠01111 Padi) | NB-3 |

## Il vero TERTUTUP forestry/agri (per memoria)
NON questi 5. I chiusi sono: `01111 Padi`, `01119 Serealia Lainnya`, `02100 Pengelolaan Hutan`.

## Effetto
- `needs_review` nello schema: 5 → **0**
- L4 + L2 dei 5 codici aggiornati con provenance HIGH, last_verified 2026-06-19
- Il navigator ora mostrerà questi 5 come registrabili (con il cap 95% per 02102), non come "verify"
