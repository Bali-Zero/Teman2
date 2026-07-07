# NotebookLM Notebook Architecture — Bali Zero / Nuzantara

> Data: 2026-03-24 | Autore: Claude Opus 4.6 (architettura) + Zero (decisioni)
> Dipende da: `NOTEBOOKLM_STRATEGY_4LLM_BRAINSTORM.md`
> Stato: BLUEPRINT — da implementare con script riproducibili

---

## 0. Stato Attuale: 57 Notebook (Audit)

### Notebook da ELIMINARE (38 notebook)

Notebook vuoti, one-shot, duplicati, o non rilevanti per il sistema permanente:

| #   | Titolo                                                  | Fonti | Motivo eliminazione             |
| --- | ------------------------------------------------------- | ----- | ------------------------------- |
| 1   | _(vuoto)_ `3fe8823d`                                    | 0     | Vuoto                           |
| 2   | _(vuoto)_ `e5962e1b`                                    | 0     | Vuoto                           |
| 3   | _(vuoto)_ `d74c6595`                                    | 0     | Vuoto                           |
| 4   | _(vuoto)_ `52d3ef01`                                    | 0     | Vuoto                           |
| 5   | Indonesia Fishery Business `144455a7`                   | 0     | Vuoto                           |
| 6   | Luka di Balik Senar `1bfa04ce`                          | 1     | Non pertinente (poesia)         |
| 7   | Oasi Tropicali `b2c4fd64`                               | 1     | Contenuto editoriale one-shot   |
| 8   | The Dawn of Synthetic Agency `2f4a9cd4`                 | 1     | Non pertinente (AI generico)    |
| 9   | Cronache del Nomadismo `f66ad300`                       | 1     | Contenuto editoriale one-shot   |
| 10  | Ingegneria Massiva dei Dati `bf28a989`                  | 1     | One-shot tecnico                |
| 11  | Cetak Biru Operasional Zantara CRM `eed44281`           | 1     | Obsoleto, assorbito da CRM docs |
| 12  | Indonesian Tax Compliance Margherita Fabiani `520040ea` | 1     | Caso cliente specifico          |
| 13  | Zantara: Evolusi Sistem `41144c80`                      | 2     | Obsoleto (jan 2026)             |
| 14  | Bali Zero: Panduan Solusi `49680934`                    | 2     | Obsoleto (jan 2026)             |
| 15  | The Great Filter KBLI 2025 `0c1c3b83`                   | 1     | Assorbito dal notebook KBLI     |
| 16  | Bali 2026: Ethical Shifts `6f536a0e`                    | 1     | One-shot intel                  |
| 17  | Classificazione Attivita 2025 `0940455a`                | 1     | Duplicato KBLI                  |
| 18  | KBLI 2025 `49d4c6d5`                                    | 1     | Duplicato KBLI                  |
| 19  | Classificazione Attivita 2025 `1ed68bef`                | 3     | Duplicato KBLI                  |
| 20  | Norme Costruzione Civile `84f9ec93`                     | 1     | Assorbito da Property notebook  |
| 21  | Bali's Era of Zero Tolerance `16585f63`                 | 2     | Assorbito da Property notebook  |
| 22  | Due Diligence Cemagi `522e0b18`                         | 1     | Caso cliente specifico          |
| 23  | Moratoria Licenze (3 duplicati)                         | 1-28  | CONSOLIDARE in 1                |
| 24  | Strategie Omnicanale `d28717a6`                         | 1     | Assorbito da Ops notebook       |
| 25  | BPJS Kesehatan `14460b4e`                               | 1     | Assorbito da Tax notebook       |
| 26  | Riforma Lavoro Indonesia `22715172`                     | 1     | Assorbito da Company notebook   |
| 27  | UU Hukum Acara Pidana `0846da0e`                        | 1     | Assorbito da Legal/Company      |
| 28  | UU Nomor 1 2026 Hukum Pidana `60eb93ec`                 | 1     | Assorbito da Legal/Company      |
| 29  | Coretax e NPWP `1e7c26a5`                               | 2     | Assorbito da Tax notebook       |
| 30  | Nuzantara Prime Menjangan `126a1fbc`                    | 2     | Caso progetto specifico         |
| 31  | Indonesian Agri Licensing `3d0345ad`                    | 1     | Assorbito da KBLI notebook      |
| 32  | Forestry & Environmental `dc97b0ef`                     | 4     | Assorbito da KBLI notebook      |
| 33  | Strategie Gelaterie `4ceff9de`                          | 3     | Caso specifico                  |
| 34  | Integrasi Kepatuhan Pajak OSS `5d5b88bb`                | 1     | Assorbito da Tax+Company        |
| 35  | Krisis Regulasi Pariwisata `010b0d52`                   | 1     | Assorbito da Intel              |

### Notebook da RIUSARE (consolidare contenuto nelle fonti dei 7 permanenti)

| Titolo                                                | Fonti    | Destinazione                              |
| ----------------------------------------------------- | -------- | ----------------------------------------- |
| Procedure Avanzate Visti `84375bc3`                   | 18       | **NB-IMMIGRATION** (riusa fonti)          |
| Indonesia Restaurant Investment `9530b58d`            | 22       | **NB-COMPANY** (riusa fonti business)     |
| Indonesian Foreign Investment `7611c112`              | 21       | **NB-COMPANY** + **NB-TAX** (split fonti) |
| Guida LKPM 2025 (2x) `837b620b` + `c1e65a37`          | 6+6      | **NB-TAX** (merge, dedup)                 |
| Moratoria Negozi `e87bb17e` + `e79a4b73` + `224dcaab` | 21+28+16 | **NB-COMPANY** (best sources)             |
| Bali's Villa Apocalypse `8632394c`                    | 2        | **NB-PROPERTY**                           |
| Moltbot/OpenClaw `0c819954`                           | 28       | **NB-CODEBASE** (fonti infra)             |
| Corporate Compliance Zoning `54a7e1d0`                | 3        | **NB-PROPERTY**                           |
| Casa Blanca Compliance `31189cf8`                     | 3        | **NB-PROPERTY** (caso esempio)            |
| BZ Strategia & Core `3e1baa5f`                        | 6        | **NB-OPS**                                |

### Notebook SHARED (non toccare)

| Titolo                              | Fonti | Nota                                 |
| ----------------------------------- | ----- | ------------------------------------ |
| The World Ahead 2025                | 70    | Google demo, shared_with_me          |
| The World Ahead 2026                | 70    | Google demo, shared_with_me          |
| Yellowstone Guide                   | 17    | Google demo, shared_with_me          |
| Genome Guide                        | 36    | Google demo, shared_with_me          |
| Shakespeare                         | 45    | Google demo, shared_with_me          |
| Infrastruttura Nuzantara `f6ecd115` | 16    | Recente, RIUSA come base NB-CODEBASE |
| Indonesia Restaurant `9530b58d`     | 22    | RIUSA fonti in NB-COMPANY            |

---

## 1. I 7 Notebook Permanenti — Specifica Dettagliata

---

### NB-CODEBASE: "Nuzantara Codebase & Architecture"

**Descrizione:** Architettura completa del monorepo, servizi, infrastruttura, pattern di sviluppo, e contesto operativo per agenti AI.

**Tag MCP routing:** `codebase`, `architecture`, `infrastructure`, `deploy`, `technical`, `debug`

**Freshness:** Bi-settimanale (ogni 2 settimane) + on-demand dopo major refactor

**Owner:** Zero (dev lead)

**Fonti (target: 25-30):**

| #   | Nome fonte                      | Tipo | Dim. stimata | Provenienza                                                                            | P   |
| --- | ------------------------------- | ---- | ------------ | -------------------------------------------------------------------------------------- | --- |
| 1   | `CLAUDE.md`                     | text | ~15K words   | `/CLAUDE.md` (git root)                                                                | P0  |
| 2   | `AI_ONBOARDING.md`              | text | ~5K words    | `/docs/AI_ONBOARDING.md`                                                               | P0  |
| 3   | `backend_app_routers_index`     | text | ~20K words   | Script: lista tutti 88 router con endpoints, metodi, auth                              | P0  |
| 4   | `backend_services_index`        | text | ~25K words   | Script: lista tutti 244 servizi con metodo principale, dipendenze                      | P0  |
| 5   | `backend_models_schemas`        | text | ~15K words   | Script: export Pydantic models + SQLAlchemy models                                     | P0  |
| 6   | `frontend_component_tree`       | text | ~20K words   | Script: component tree mouth/ con props, hooks, routes                                 | P0  |
| 7   | `prompts_zantara_core`          | text | ~8K words    | `/apps/backend-rag/backend/prompts/zantara_core.py` (full)                             | P0  |
| 8   | `collection_registry`           | text | ~2K words    | Qdrant collection registry + physical mappings                                         | P0  |
| 9   | `fly_toml_config`               | text | ~1K words    | `fly.toml` + deploy config                                                             | P0  |
| 10  | `mcp_tool_manifest`             | text | ~12K words   | Script: 109 tools + 10 prompts + 5 resources manifest                                  | P0  |
| 11  | `database_schema_v2`            | text | ~10K words   | Script: pg_dump --schema-only delle tabelle principali                                 | P0  |
| 12  | `cicatrix_scars`                | text | ~5K words    | `/.claude/rules/cicatrix-scars.md`                                                     | P1  |
| 13  | `architecture_decision_records` | text | ~8K words    | `/docs/ARCHITECTURE_DECISION_RECORDS.md`                                               | P1  |
| 14  | `system_map`                    | text | ~5K words    | `/docs/architecture/SYSTEM_MAP_LIVE.md`                                                | P1  |
| 15  | `orchestrator_core`             | text | ~10K words   | `backend/services/rag/agentic/orchestrator.py` + `orchestrator_core.py`                | P1  |
| 16  | `channel_adapters`              | text | ~8K words    | Script: 7 channel adapters (telegram, whatsapp, instagram, web, twitter, gchat, slack) | P1  |
| 17  | `dependency_graph`              | text | ~5K words    | Script: import dependency graph critico (dependencies.py -> router chain)              | P1  |
| 18  | `test_architecture`             | text | ~3K words    | Script: test suite summary (385 files, pass/fail, coverage)                            | P1  |
| 19  | `openclaw_config`               | text | ~3K words    | OpenClaw agent config (Pro + Air)                                                      | P1  |
| 20  | `infra_runbook`                 | text | ~8K words    | `/docs/RUNBOOK.md` + deploy checklist                                                  | P1  |
| 21  | `active_automations`            | text | ~5K words    | `/docs/ACTIVE_AUTOMATIONS.md` + cron schedule                                          | P1  |
| 22  | `vercel_config`                 | text | ~3K words    | `next.config.ts` + `vercel.json` + middleware                                          | P1  |

**Struttura del source pack (header standard):**

```
---
title: [Nome fonte]
domain: codebase
source_type: code_export | config | documentation
generated_at: 2026-03-24T00:00:00Z
generator_script: scripts/nlm_pack_codebase.py
freshness: biweekly
language: EN (code), IT (comments where applicable)
---

[Contenuto]
```

**Query tipo (deve rispondere perfettamente):**

1. "Quali router gestiscono le chiamate CRM e quali dipendenze condividono?"
2. "Mostrami il flusso completo di una query dall'arrivo su WhatsApp alla risposta finale con citazioni"
3. "Quali servizi vengono inizializzati al startup e in che ordine? Cosa succede se Redis e' down?"
4. "Se devo aggiungere un nuovo canale di comunicazione, quali file devo creare e modificare?"
5. "Quali sono le Qdrant collections attive, i loro alias, e quali router le interrogano?"

**Script generatore:** `scripts/nlm_pack_codebase.py`

```bash
# Genera tutte le fonti del notebook NB-CODEBASE
cd /Users/nuzantara/Desktop/nuzantara
python3 scripts/nlm_pack_codebase.py --output tmp_notebooklm/codebase/
# Output: 22 file .txt pronti per source_add
```

---

### NB-IMMIGRATION: "Visa & Immigration Indonesia 2025-2026"

**Descrizione:** Tassonomia completa visti indonesiani (114 codici), normativa imigrasi, procedure KITAS/KITAP, fee governative (PNBP), requisiti documenti, casi pratici.

**Tag MCP routing:** `visa`, `immigration`, `kitas`, `kitap`, `voa`, `permit`, `imigrasi`, `sponsor`

**Freshness:** Mensile + on-demand quando cambia normativa (PP, Permen, circolari Imigrasi)

**Owner:** Team Immigration (Asya lead)

**Fonti (target: 30-35):**

| #   | Nome fonte                       | Tipo | Dim. stimata | Provenienza                                                                                                          | P   |
| --- | -------------------------------- | ---- | ------------ | -------------------------------------------------------------------------------------------------------------------- | --- |
| 1   | `visa_taxonomy_114_codes`        | text | ~25K words   | Script: export da `seed_visa_types_complete_2026.py` — tutti 114 codici con nome EN/ID, categoria, durata, requisiti | P0  |
| 2   | `pp_48_2023_immigration_law`     | text | ~30K words   | Peraturan Pemerintah 48/2023 tentang Keimigrasian — testo completo per capitolo                                      | P0  |
| 3   | `permenkumham_22_2023`           | text | ~20K words   | Peraturan Menteri Hukum dan HAM 22/2023 — implementazione PP 48 per visa/ITAS/ITAP                                   | P0  |
| 4   | `visa_e33g_digital_nomad`        | text | ~6K words    | `training-data/visa/visa_001_e33g_digital_nomad_basic.md`                                                            | P0  |
| 5   | `visa_e28a_investor_kitas`       | text | ~8K words    | `training-data/visa/visa_003_e28a_investor_kitas.md`                                                                 | P0  |
| 6   | `visa_d1_tourism`                | text | ~3K words    | `training-data/visa/visa_004_d1_tourism_multiple_entry.md`                                                           | P0  |
| 7   | `visa_d12_business`              | text | ~5K words    | `training-data/visa/visa_005_d12_business_investigation.md`                                                          | P0  |
| 8   | `visa_e33e_e33f_retirement`      | text | ~3K words    | `training-data/visa/visa_006_retirement_visas_e33e_e33f.md`                                                          | P0  |
| 9   | `visa_imigrasi_series_ABFC`      | text | ~2K words    | `training-data/visa/visa_016_official_imigrasi_series_A_B_F_C.md`                                                    | P0  |
| 10  | `visa_oracle_qdrant_export`      | text | ~40K words   | Script: top 200 documenti da `visa_oracle` Qdrant, score > 0.5, deduplicati                                          | P0  |
| 11  | `immigration_circulars_export`   | text | ~15K words   | Script: export da `immigration_circulars` Qdrant — circolari Imigrasi recenti                                        | P0  |
| 12  | `kitas_application_procedure`    | text | ~8K words    | Procedura step-by-step KITAS: sponsor → RPTKA → IMTA → Telex → Stamping → SKTT                                       | P0  |
| 13  | `kitap_conversion_procedure`     | text | ~5K words    | Conversione KITAS → KITAP: requisiti 4 anni, documenti, timeline                                                     | P0  |
| 14  | `voa_b211_procedure`             | text | ~5K words    | VOA/B211: on arrival, extension, overstay penalties                                                                  | P0  |
| 15  | `pnbp_fee_schedule_immigration`  | text | ~5K words    | Fee PNBP ufficiali Imigrasi: ITAS Rp 2.000.000, telex Rp 100.000, etc.                                               | P0  |
| 16  | `spouse_mixed_marriage`          | text | ~6K words    | `training-data/spouse_mixed_marriage_conversation.md`                                                                | P1  |
| 17  | `kg_visa_entities`               | text | ~15K words   | Script: export KG nodi tipo `visa`, `dokumen`, `persyaratan` con relazioni REQUIRES                                  | P1  |
| 18  | `notebooklm_visa_session1`       | text | ~10K words   | `training-data/visa/visa_010_notebooklm_session1.md`                                                                 | P1  |
| 19  | `notebooklm_visa_session2`       | text | ~5K words    | `training-data/visa/visa_011_notebooklm_session2.md`                                                                 | P1  |
| 20  | `epo_erp_emergency_permits`      | text | ~3K words    | EPO (Exit Permit Only) e ERP (Exit Re-entry Permit) — procedure emergenza                                            | P1  |
| 21  | `overstay_penalties_deportation` | text | ~3K words    | Sanksi overstay: Rp 1.000.000/giorno, max 60 gg, deportazione, blacklist                                             | P1  |
| 22  | `rptka_imta_work_permit`         | text | ~5K words    | RPTKA (Piano Uso Tenaga Asing) + IMTA (Izin Menggunakan Tenaga Asing)                                                | P1  |
| 23  | `sponsor_requirements`           | text | ~4K words    | Requisiti sponsor: PT PMA, individuo, organizzazione — per tipo visa                                                 | P1  |
| 24  | `bali_zero_visa_faq`             | text | ~5K words    | Script: top 50 FAQ dal training conversations su tema visa                                                           | P1  |
| 25  | `country_specific_rules`         | text | ~5K words    | Eccezioni per nazionalita: VOA countries, visa-free 169 paesi, bilateral agreements                                  | P1  |

**Normativa indonesiana — dettaglio chunking:**

| Regolamento                   | Articoli chiave                                                                                    | Chunking                                   |
| ----------------------------- | -------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| **PP 48/2023** (Keimigrasian) | Art. 1-10 (Definizioni), Art. 39-78 (Visa), Art. 79-120 (ITAS/ITAP), Art. 180-210 (Sanksi)         | Per BAB (capitolo), ~2-5K words/chunk      |
| **Permenkumham 22/2023**      | Art. 1-15 (Jenis Visa), Art. 16-40 (Persyaratan), Art. 41-60 (Tata Cara), Lampiran I-IV (Formulir) | Per BAB + Lampiran separati                |
| **Inmendagri 27/2024**        | Surat Edaran su SKTT per WNA                                                                       | Documento singolo (~2K words)              |
| **PP 31/2013** (RPTKA)        | Art. 1-20 (Penggunaan TKA)                                                                         | Per BAB, focus Art. 3-10 (RPTKA procedure) |

**Lingua:** Indonesiano per testo normativo, Inglese per spiegazioni e procedure, Italiano per FAQ clienti.

**Manifest (README_manifest.md):**

```
# NB-IMMIGRATION Manifest
- Notebook ID: [da assegnare post-creazione]
- Versione fonti: 2026-03-24
- Totale fonti: 25
- Copertura: 114 codici visa, PP 48/2023, Permenkumham 22/2023
- ESCLUSIONI: Prezzi Bali Zero (usare PricingTool), dati PII clienti
- AGGIORNAMENTO: Mensile, script scripts/nlm_pack_immigration.py
- NOTA: Fee PNBP sono fee GOVERNATIVE, NON prezzi Bali Zero
```

**Query tipo:**

1. "Quali sono i requisiti per convertire un KITAS E28A investitore in KITAP? Documenti e timeline?"
2. "Un cittadino australiano vuole restare 6 mesi a Bali per lavorare da remoto. Quali opzioni visa?"
3. "Qual e' la differenza tra E33G (digital nomad) e D12 (business visit)? Pro e contro?"
4. "Il mio KITAS scade tra 30 giorni. Cosa succede se non rinnovo? Procedura di emergenza?"
5. "Quali sono le fee PNBP governative per una nuova ITAS? (NON i prezzi Bali Zero)"

---

### NB-COMPANY: "Company Formation & KBLI Indonesia 2025"

**Descrizione:** Tutto cio' che serve per aprire e gestire un'azienda in Indonesia: PT PMA, PT Lokal, CV, UD, KBLI 2025 (1.563 codici), OSS-RBA, NIB, licensing, negative investment list, capital requirements.

**Tag MCP routing:** `company`, `kbli`, `pt_pma`, `pt_lokal`, `oss`, `nib`, `business`, `investment`, `formation`, `license`

**Freshness:** Mensile + on-demand su nuovi PP/Perpres DNI

**Owner:** Zero + Asya

**Fonti (target: 30-35):**

| #   | Nome fonte                       | Tipo | Dim. stimata | Provenienza                                                                                            | P   |
| --- | -------------------------------- | ---- | ------------ | ------------------------------------------------------------------------------------------------------ | --- |
| 1   | `kbli_2025_sectors_A_to_F`       | text | ~80K words   | Script: export KBLI 2025 settori A-F (Agri, Mining, Manufacturing) con uraian + perizinan              | P0  |
| 2   | `kbli_2025_sectors_G_to_L`       | text | ~80K words   | Script: export settori G-L (Trade, Transport, Accommodation, IT, Finance, Real Estate)                 | P0  |
| 3   | `kbli_2025_sectors_M_to_U`       | text | ~60K words   | Script: export settori M-U (Professional, Admin, Edu, Health, Arts, Other)                             | P0  |
| 4   | `pp28_2025_risk_classification`  | file | ~20MB (PDF)  | `data/source_documents/PP Nomor 28 Tahun 2025.pdf` — Klasifikasi Risiko                                | P0  |
| 5   | `perban_bps_7_2025`              | text | ~500 words   | `data/source_documents/perban_bps_7_2025_extract.txt` — Peraturan BPS sulla KBLI                       | P0  |
| 6   | `perpres_10_2021_dni`            | text | ~15K words   | Peraturan Presiden 10/2021 — Daftar Negatif Investasi (Negative List) per BAB                          | P0  |
| 7   | `perpres_49_2021_amendement_dni` | text | ~5K words    | Amandemen DNI — sektor terbuka/tertutup per PMA                                                        | P0  |
| 8   | `oss_rba_procedure`              | text | ~10K words   | Procedura OSS-RBA: registrasi NIB → KBLI selection → risk classification → perizinan                   | P0  |
| 9   | `pt_pma_setup_complete`          | text | ~15K words   | `training-data/business/business_001_pt_pma_core_setup.md` + `business_028_pt_pma_restaurant_setup.md` | P0  |
| 10  | `pt_lokal_vs_pt_pma`             | text | ~12K words   | `training-data/business/business_032_pt_lokal_vs_pt_pma.md`                                            | P0  |
| 11  | `kbli_foreign_ownership`         | text | ~10K words   | `training-data/business/business_033_kbli_foreign_ownership.md`                                        | P0  |
| 12  | `pt_pma_villa_rental`            | text | ~8K words    | `training-data/business/business_029_pt_pma_villa_rental.md`                                           | P0  |
| 13  | `restaurant_best_practices`      | text | ~2K words    | `training-data/business/business_002_restaurant_best_practices.md`                                     | P0  |
| 14  | `capital_requirements_table`     | text | ~5K words    | Script: tabella requisiti capitale per settore — Rp 10M (mikro) to Rp 10B (besar)                      | P0  |
| 15  | `licensing_slhs_npbbkc`          | text | ~7K words    | `training-data/licenses/` — 4 file (SLHS hygiene + NPBBKC alcohol)                                     | P0  |
| 16  | `customs_import_duty`            | text | ~10K words   | `training-data/customs/customs_040_import_duty_basics.md`                                              | P1  |
| 17  | `legal_labor_dispute`            | text | ~8K words    | `training-data/legal/legal_055_labor_dispute_resolution.md`                                            | P1  |
| 18  | `legal_ip_basics`                | text | ~13K words   | `training-data/legal/legal_058_intellectual_property_basics.md`                                        | P1  |
| 19  | `kbli_2017_to_2025_mapping`      | text | ~3K words    | `data/source_documents/KBLI_2017_TO_2025_MAPPING.json` (12 mappings)                                   | P1  |
| 20  | `moratoria_toko_modern_bali`     | text | ~10K words   | Instruksi Gubernur Bali 2024 — moratoria izin toko modern + analisi impatto                            | P1  |
| 21  | `kg_company_entities`            | text | ~15K words   | Script: export KG nodi tipo `kbli`, `undang_undang`, `persyaratan` con REQUIRES, PART_OF               | P1  |
| 22  | `ahu_online_procedure`           | text | ~5K words    | Prosedur AHU Online: pendirian PT → pengesahan akta → SK Menkumham                                     | P1  |
| 23  | `legal_unified_qdrant_top200`    | text | ~40K words   | Script: top 200 docs da `legal_unified_hybrid_hybrid` Qdrant                                           | P1  |
| 24  | `bali_zero_company_faq`          | text | ~5K words    | Script: top 50 FAQ dal training conversations su tema company/KBLI                                     | P1  |
| 25  | `riforma_lavoro_2025`            | text | ~5K words    | UU Cipta Kerja (Omnibus Law) — impatti su ketenagakerjaan per PMA                                      | P1  |

**Chunking KBLI 2025 (1.563 codici):**

Il dataset completo (`KBLI_2025_FINAL_CLEAN.json`, 9.3MB, 138K righe) e' troppo grande per una singola fonte (limite 500K parole). Split per settore:

| Pack             | Settori                                                                                       | Codici stimati | Parole stimate |
| ---------------- | --------------------------------------------------------------------------------------------- | -------------- | -------------- |
| `sectors_A_to_F` | A (Agri), B (Mining), C (Manufacturing), D (Electricity), E (Water), F (Construction)         | ~650           | ~80K           |
| `sectors_G_to_L` | G (Trade), H (Transport), I (Accommodation), J (IT/Comms), K (Finance), L (Real Estate)       | ~550           | ~80K           |
| `sectors_M_to_U` | M (Professional), N (Admin), O (Government), P (Education), Q (Health), R (Arts), S-U (Other) | ~363           | ~60K           |

Ogni entry include: `kode_kbli_2025`, `judul`, `uraian` (media 438 chars), `per_skala` (rischio + perizinan per scala usaha).

**Normativa chiave — dettaglio:**

| Regolamento                                        | Focus                                            | Chunking                                                              |
| -------------------------------------------------- | ------------------------------------------------ | --------------------------------------------------------------------- |
| **PP 28/2025** (Klasifikasi Risiko)                | Mappatura KBLI → rischio → perizinan             | PDF caricato direttamente (NotebookLM legge PDF)                      |
| **Perpres 10/2021** (DNI)                          | Lista settori aperti/chiusi/condizionati per PMA | Per BAB: Lampiran I (tertutup), II (persyaratan tertentu), III (UMKM) |
| **UU 6/2023** (Cipta Kerja)                        | Omnibus law — semplificazione perizinan          | Solo Bab V (Kemudahan Investasi) + Bab IV (Ketenagakerjaan)           |
| **PP 5/2021** (Perizinan Berusaha Berbasis Risiko) | Implementazione OSS-RBA                          | Per BAB, focus Art. 7-20 (risk classification)                        |

**Lingua:** Indonesiano per normativa, Inglese per spiegazioni, Italiano per FAQ.

**Query tipo:**

1. "Voglio aprire un ristorante a Canggu come straniero. Quale KBLI, che tipo di PT, requisiti capitale?"
2. "Qual e' la differenza tra rischio Rendah, Menengah Rendah, Menengah Tinggi, Tinggi per il KBLI 56101?"
3. "Un australiano puo' possedere il 100% di una PT PMA nel settore IT (KBLI 62019)?"
4. "Come funziona la procedura OSS-RBA dall'inizio alla fine? Step by step con documenti necessari"
5. "Il KBLI 55110 (hotel bintang) richiede SLHS? Qual e' la procedura per ottenere la licenza igienica?"

---

### NB-TAX: "Tax Compliance Indonesia 2025-2026"

**Descrizione:** Sistema fiscale indonesiano per stranieri e PT PMA: PPh 21/23/25/26, PPN (VAT), Coretax DJP, NPWP, SPT, LKPM, BPJS, transfer pricing, tax treaty.

**Tag MCP routing:** `tax`, `pph`, `ppn`, `vat`, `npwp`, `spt`, `lkpm`, `bpjs`, `coretax`, `fiscal`

**Freshness:** Trimestrale (regolamenti fiscali cambiano ogni trimestre) + on-demand su nuove PMK

**Owner:** Team Tax (Asya lead)

**Fonti (target: 25-30):**

| #   | Nome fonte                     | Tipo | Dim. stimata | Provenienza                                                                               | P   |
| --- | ------------------------------ | ---- | ------------ | ----------------------------------------------------------------------------------------- | --- |
| 1   | `pph21_individual_indonesian`  | text | ~7K words    | `training-data/tax/tax_016_pph21_individual_indonesian.md`                                | P0  |
| 2   | `pph21_foreign_employees`      | text | ~5K words    | `training-data/tax/tax_024_pph21_foreign_employees.md`                                    | P0  |
| 3   | `ppn_vat_full_cycle`           | text | ~12K words   | `training-data/tax/tax_019_ppn_vat_full_cycle.md`                                         | P0  |
| 4   | `bpjs_insurance`               | text | ~1K words    | `training-data/tax/tax_020_bpjs_insurance.md`                                             | P0  |
| 5   | `npwp_registration`            | text | ~1K words    | `training-data/tax/tax_021_npwp_registration.md`                                          | P0  |
| 6   | `spt_annual_tax`               | text | ~1K words    | `training-data/tax/tax_022_spt_annual_tax.md`                                             | P0  |
| 7   | `lkpm_investment_report`       | text | ~1K words    | `training-data/tax/tax_023_lkpm_investment_report.md`                                     | P0  |
| 8   | `tax_pph_ppn_conversation`     | text | ~6K words    | `training-data/tax_pph_ppn_conversation.md`                                               | P0  |
| 9   | `uu_hpp_7_2021`                | text | ~20K words   | UU 7/2021 Harmonisasi Peraturan Perpajakan — tarif PPh baru, PPN 12%, threshold PKP       | P0  |
| 10  | `pp_55_2022_pph`               | text | ~15K words   | PP 55/2022 — PPh: tarif progresif, PPh Final UMKM 0.5%, withholding                       | P0  |
| 11  | `pmk_66_2023_ppn`              | text | ~10K words   | PMK 66/2023 — PPN: faktur pajak, PKP, objek PPN, PPN 11% → 12%                            | P0  |
| 12  | `coretax_djp_guide`            | text | ~10K words   | Guida Coretax DJP: registrasi, faktur elektronik, pelaporan online                        | P0  |
| 13  | `tax_genius_qdrant_top200`     | text | ~40K words   | Script: top 200 docs da `tax_genius_hybrid` Qdrant, deduplicati                           | P0  |
| 14  | `lkpm_complete_guide`          | text | ~10K words   | Merge da 2 notebook LKPM esistenti: procedure, form, deadline, sanksi                     | P0  |
| 15  | `transfer_pricing_basics`      | text | ~8K words    | Transfer pricing per PT PMA: arm's length, TP doc, local file, master file, CbCR          | P1  |
| 16  | `tax_treaty_indonesia`         | text | ~8K words    | P3B (Perjanjian Penghindaran Pajak Berganda) — paesi con treaty, tarif ridotti WHT        | P1  |
| 17  | `pph_23_26_withholding`        | text | ~5K words    | PPh 23 (residente) e 26 (non-residente): tarif, objek, pemotongan                         | P1  |
| 18  | `bpjs_ketenagakerjaan_details` | text | ~5K words    | BPJS TK: JHT, JKK, JKM, JP — contributi, benefit, registrasi WNA                          | P1  |
| 19  | `bpjs_kesehatan_wna`           | text | ~3K words    | BPJS Kesehatan per WNA: obbligo, kelas, iuran, faskes                                     | P1  |
| 20  | `kg_tax_entities`              | text | ~10K words   | Script: export KG nodi tipo `pajak`, `biaya`, `undang_undang` con HAS_FEE                 | P1  |
| 21  | `spt_filing_calendar`          | text | ~3K words    | Calendario scadenze fiscali: SPT Tahunan (31 Mar), SPT Masa (20/mese), LKPM (trimestrale) | P1  |
| 22  | `tax_penalties_sanctions`      | text | ~3K words    | Sanksi perpajakan: denda keterlambatan, bunga, pidana pajak                               | P1  |
| 23  | `bali_zero_tax_faq`            | text | ~5K words    | Script: top 50 FAQ dal training conversations su tema tax                                 | P1  |

**Normativa chiave — dettaglio:**

| Regolamento                           | Articoli chiave                                                              | Chunking                   |
| ------------------------------------- | ---------------------------------------------------------------------------- | -------------------------- |
| **UU 7/2021** (HPP)                   | Bab II (PPh), Bab III (PPN), Bab IV (KUP)                                    | Per BAB, ~5-7K words/chunk |
| **PP 55/2022** (PPh)                  | Art. 1-30 (Objek PPh), Art. 56-68 (PPh Final UMKM), Art. 69-80 (Withholding) | Per BAB                    |
| **PMK 66/2023** (PPN)                 | Art. 1-20 (Faktur Pajak), Art. 21-40 (PKP), Art. 41-60 (Tarif)               | Per BAB                    |
| **PP 35/2021** (PKWT/Ketenagakerjaan) | Art. 1-15 (Kontrak Kerja WNA)                                                | Documento singolo          |

**NOTA CRITICA:** Le fee governative nel KG (relazioni HAS_FEE) sono fee DJP/PNBP, NON prezzi Bali Zero. I prezzi Bali Zero sono ESCLUSIVAMENTE nel PricingTool.

**Query tipo:**

1. "Sono un dipendente straniero con KITAS. Come si calcola il PPh 21? Quali deduzioni posso applicare?"
2. "La mia PT PMA ha fatturato sotto i 4.8 miliardi. Posso usare il PPh Final 0.5%? Per quanto tempo?"
3. "Quali sono le scadenze fiscali per una PT PMA nel Q2 2026? SPT, PPN, LKPM?"
4. "Come funziona il sistema Coretax DJP? Come faccio la fattura elettronica?"
5. "Un freelancer italiano a Bali con E33G deve pagare tasse in Indonesia? Come?"

---

### NB-PROPERTY: "Property, Zoning & Real Estate Bali 2025"

**Descrizione:** Diritti reali in Indonesia (HGB, Hak Pakai, Hak Milik), zonizzazione Bali, procedure acquisto/costruzione, IMB/PBG, tata ruang, RTRW/RDTR.

**Tag MCP routing:** `property`, `real_estate`, `zoning`, `land`, `hgb`, `hak_pakai`, `villa`, `construction`, `imb`, `pbg`

**Freshness:** Trimestrale + on-demand su nuovi Perda

**Owner:** Zero

**Fonti (target: 20-25):**

| #   | Nome fonte                   | Tipo | Dim. stimata | Provenienza                                                                                   | P   |
| --- | ---------------------------- | ---- | ------------ | --------------------------------------------------------------------------------------------- | --- |
| 1   | `realestate_buying_property` | text | ~13K words   | `training-data/realestate/realestate_046_indonesian_buying_property.md`                       | P0  |
| 2   | `uupa_5_1960_land_law`       | text | ~15K words   | UU 5/1960 (Undang-Undang Pokok Agraria) — Hak Milik, HGB, Hak Pakai, Hak Sewa                 | P0  |
| 3   | `pp_18_2021_hak_pengelolaan` | text | ~10K words   | PP 18/2021 — Hak Atas Tanah, Satuan Rumah Susun, Pendaftaran Tanah                            | P0  |
| 4   | `bali_zoning_codes`          | text | ~5K words    | Script: export da `master_building_codes_complete.json` — 23 zone codes (C-1, K-1, R-2, etc.) | P0  |
| 5   | `bali_rdtr_overview`         | text | ~10K words   | RDTR (Rencana Detail Tata Ruang) aree strategiche Bali: Canggu, Seminyak, Ubud, Sanur         | P0  |
| 6   | `imb_pbg_procedure`          | text | ~8K words    | Transizione IMB → PBG (Persetujuan Bangunan Gedung): procedura, SLF, SIMBG                    | P0  |
| 7   | `foreigner_property_rights`  | text | ~8K words    | Hak Pakai per WNA: durata (30+20+30), requisiti, limitazioni, nominee arrangement risks       | P0  |
| 8   | `villa_apocalypse_report`    | text | ~5K words    | Da notebook esistente "Bali's Villa Apocalypse" — analisi crackdown 2026                      | P0  |
| 9   | `prime_zoning_export`        | text | ~10K words   | Script: export PostGIS `bali_zoning_layers` — zone principali con coordinate e regole         | P0  |
| 10  | `construction_permit_flow`   | text | ~5K words    | Flusso completo: tanah → sertifikat → PBG → konstruksi → SLF → operasional                    | P0  |
| 11  | `bphtb_pph_property_tax`     | text | ~5K words    | BPHTB (5%) e PPh Final (2.5%) su transazioni immobiliari                                      | P1  |
| 12  | `strata_title_rumah_susun`   | text | ~5K words    | SHMSRS (Sertifikat Hak Milik Satuan Rumah Susun) per apartemen/condominium                    | P1  |
| 13  | `leasehold_vs_freehold`      | text | ~5K words    | Confronto: Hak Sewa vs Hak Pakai vs HGB — pro/contro per investor straniero                   | P1  |
| 14  | `casa_blanca_compliance`     | text | ~3K words    | Caso studio: compliance zoning per villa commerciale                                          | P1  |
| 15  | `notarized_deed_procedure`   | text | ~5K words    | Akta PPAT: jual beli, hibah, tukar menukar — procedura notarile                               | P1  |
| 16  | `kg_property_entities`       | text | ~8K words    | Script: export KG nodi tipo `properti`, `tanah`, `izin` con relazioni                         | P1  |
| 17  | `bali_spatial_plan_rtrw`     | text | ~8K words    | RTRW Kabupaten Badung/Gianyar/Tabanan — zone protette, agricole, turistiche                   | P1  |
| 18  | `nominee_arrangement_risks`  | text | ~5K words    | Rischi legali nominee agreement: UU 5/1960 Art. 26, nullita', sanksi pidana                   | P1  |
| 19  | `agrarian_reform_updates`    | text | ~5K words    | Aggiornamenti reforma agraria 2025-2026: digital cadastre, PTSL                               | P1  |
| 20  | `bali_zero_property_faq`     | text | ~5K words    | Script: top 50 FAQ da training conversations su tema property                                 | P1  |

**Normativa chiave:**

| Regolamento                      | Focus                                                                    | Chunking                     |
| -------------------------------- | ------------------------------------------------------------------------ | ---------------------------- |
| **UU 5/1960** (UUPA)             | Hak atas tanah: Milik (Art. 20-27), HGB (Art. 35-40), Pakai (Art. 41-43) | Per jenis hak (tipo diritto) |
| **PP 18/2021**                   | Pendaftaran tanah, jangka waktu HGB/Hak Pakai                            | Per BAB                      |
| **UU 28/2002** (Bangunan Gedung) | IMB/PBG requirements                                                     | Focus Art. 7-15 (perizinan)  |
| **Perda Badung** (Tata Ruang)    | Zonasi Canggu, Seminyak                                                  | Per zona                     |

**Query tipo:**

1. "Posso comprare una villa a Canggu come straniero? Quali diritti sulla terra ho?"
2. "Qual e' la differenza tra HGB e Hak Pakai? Quale conviene per un investor PMA?"
3. "Ho un terreno zona R-2 a Canggu. Posso costruire una villa commerciale? Che permessi servono?"
4. "Come funziona il passaggio da IMB al nuovo sistema PBG? Il mio vecchio IMB e' ancora valido?"
5. "Quali sono le tasse su una transazione immobiliare? BPHTB, PPh, notaio?"

---

### NB-OPS: "Bali Zero Operations & Platform"

**Descrizione:** Operations interne, workflow team, metriche, monitoring, competitor intelligence, processi CRM, automazioni.

**Tag MCP routing:** `operations`, `ops`, `monitoring`, `team`, `workflow`, `crm`, `competitor`, `automation`

**Freshness:** Settimanale (operations cambiano velocemente)

**Owner:** Zero

**Fonti (target: 20-25):**

| #   | Nome fonte                     | Tipo | Dim. stimata | Provenienza                                                                         | P   |
| --- | ------------------------------ | ---- | ------------ | ----------------------------------------------------------------------------------- | --- |
| 1   | `runbook`                      | text | ~8K words    | `/docs/RUNBOOK.md` — procedure operative                                            | P0  |
| 2   | `active_automations`           | text | ~5K words    | `/docs/ACTIVE_AUTOMATIONS.md` + cron schedule Pro + Air                             | P0  |
| 3   | `crm_workflow_mapping`         | text | ~8K words    | `/docs/CRM_WORKFLOW_MAPPING.md` — lifecycle pratiche                                | P0  |
| 4   | `crm_complete`                 | text | ~10K words   | `/docs/CRM_COMPLETE.md` — architettura CRM                                          | P0  |
| 5   | `competitor_intelligence_2026` | text | ~15K words   | Report competitivo: Emerhub, InCorp, LMI, Seven Stones                              | P0  |
| 6   | `team_members_config`          | text | ~2K words    | `backend/data/team_members.json` — struttura team, ruoli, specializzazioni          | P0  |
| 7   | `bz_strategia_core`            | text | ~5K words    | Da notebook "BZ Strategia & Core 2026" (fonti esistenti)                            | P0  |
| 8   | `deploy_checklist`             | text | ~3K words    | `/docs/operations/DEPLOY_CHECKLIST.md`                                              | P0  |
| 9   | `monitoring_guide`             | text | ~5K words    | `/docs/operations/MONITORING_GUIDE_2026-03-02.md`                                   | P0  |
| 10  | `channel_ownership`            | text | ~3K words    | 7 canali: chi gestisce cosa, adapter, webhook, stato                                | P0  |
| 11  | `whatsapp_strategy`            | text | ~5K words    | `/docs/WHATSAPP_STRATEGY_2026.md`                                                   | P1  |
| 12  | `intel_pipeline_guide`         | text | ~5K words    | `/docs/INTEL_PIPELINE_COMPLETE.md` — scraper → validator → publisher                | P1  |
| 13  | `sla_compliance_rules`         | text | ~3K words    | SLA per tipo servizio: visa 24h response, company 48h, tax 72h                      | P1  |
| 14  | `lead_assignment_agent`        | text | ~8K words    | `/docs/LEAD_ASSIGNMENT_AGENT.md` — workflow LangGraph                               | P1  |
| 15  | `omnichannel_spec`             | text | ~8K words    | `/docs/OMNICHANNEL_2_0_SPEC.md`                                                     | P1  |
| 16  | `pro_air_connection`           | text | ~3K words    | `/docs/PRO_AIR_CONNECTION.md` — federation Pro+Air                                  | P1  |
| 17  | `pricing_categories`           | text | ~3K words    | Script: export categorie pricing (7 cat, 66 items) SENZA prezzi specifici           | P1  |
| 18  | `client_journey_templates`     | text | ~5K words    | Journey templates: new_client, visa_renewal, company_setup, compliance_check        | P1  |
| 19  | `kpi_dashboard_metrics`        | text | ~3K words    | Metriche: response time, resolution rate, client satisfaction, revenue per practice | P1  |
| 20  | `escalation_protocol`          | text | ~2K words    | Da `zantara_core.py` — ESCALATION_PROTOCOL + CRASH_PROTOCOL                         | P1  |

**Query tipo:**

1. "Qual e' il workflow completo quando arriva un nuovo lead da WhatsApp? Chi lo prende, come viene assegnato?"
2. "Quanto tempo ci mette mediamente una pratica KITAS dall'apertura alla chiusura? Dove sono i bottleneck?"
3. "Quali automazioni girano su Pro vs Air? A che ora? Cosa succede se Air e' offline?"
4. "Come si confronta Bali Zero con Emerhub su pricing e servizi? Dove siamo piu' forti?"
5. "Quali metriche devo monitorare per capire se il team sta performando bene?"

---

### NB-EDITORIAL: "Bali Zero Editorial & Content"

**Descrizione:** Contenuti editoriali per blog, SEO, social media: articoli intel, guide, analisi settoriali, best practices per content creation. Feed per il pipeline scraper → composer → publisher.

**Tag MCP routing:** `editorial`, `content`, `blog`, `article`, `seo`, `intel`, `news`

**Freshness:** Settimanale (intel digest) + on-demand per nuovi articoli

**Owner:** Zero

**Fonti (target: 20-25):**

| #   | Nome fonte                        | Tipo | Dim. stimata | Provenienza                                                                       | P   |
| --- | --------------------------------- | ---- | ------------ | --------------------------------------------------------------------------------- | --- |
| 1   | `article_composer_guide`          | text | ~8K words    | `/docs/ARTICLE_COMPOSER_API.md` + best practices                                  | P0  |
| 2   | `blog_100_articles_plan`          | text | ~5K words    | `/docs/BLOG_100_ARTICLES_PLAN.md` — piano editoriale                              | P0  |
| 3   | `intel_latest_digest`             | text | ~10K words   | Script: export `intel_output_latest.json` — articoli + digest                     | P0  |
| 4   | `seo_action_plan`                 | text | ~8K words    | `data/analysis/SEO_ACTION_PLAN_REAL_DATA.json`                                    | P0  |
| 5   | `balizero_news_qdrant_top100`     | text | ~25K words   | Script: top 100 docs da `intel_authoritative_sources` Qdrant                      | P0  |
| 6   | `zantara_persona_guidelines`      | text | ~5K words    | Da `zantara_core.py` — tone of voice, closing phrases, language protocol          | P0  |
| 7   | `geo_aeo_seo_strategy`            | text | ~5K words    | GEO pipeline: answerSnippet, entityMentions, faqSchema, AI frontmatter            | P0  |
| 8   | `kbli_gold_content_246`           | text | ~30K words   | Script: 246 gold content entries per KBLI codes (contenuto arricchito editoriale) | P0  |
| 9   | `article_composer_best_practices` | text | ~5K words    | `/docs/ARTICLE_COMPOSER_BEST_PRACTICES_2026.md`                                   | P1  |
| 10  | `blog_layout_guide`               | text | ~3K words    | `/docs/BLOG_LAYOUT_GUIDE.md`                                                      | P1  |
| 11  | `intel_scraper_analysis`          | text | ~5K words    | `/docs/INTEL_SCRAPER_ANALYSIS_REPORT.md`                                          | P1  |
| 12  | `servizi_consulenza_bali`         | text | ~5K words    | `/docs/SERVIZI_CONSULENZA_BALI_2026.md` — catalogo servizi in italiano            | P1  |
| 13  | `content_calendar_template`       | text | ~3K words    | Template calendario editoriale: Lun intel, Mer deep dive, Ven trending            | P1  |
| 14  | `training_conversations_top50`    | text | ~20K words   | Script: top 50 da `training_conversations_hybrid` Qdrant — conversazioni esempio  | P1  |
| 15  | `kbli_articles_archive`           | text | ~15K words   | 7 articoli KBLI dal archive: strategy, compliance, nuove regole, leva fiscale     | P1  |
| 16  | `competitor_content_analysis`     | text | ~5K words    | Analisi contenuti competitor: Emerhub blog (300+ posts), InCorp guides            | P1  |
| 17  | `llms_txt_balizero`               | text | ~2K words    | `llms.txt` per AI citation / GEO optimization                                     | P1  |

**Query tipo:**

1. "Genera un outline per un articolo su 'Come aprire un ristorante a Bali nel 2026' ottimizzato SEO"
2. "Quali sono i top 5 temi che dovremmo coprire questo mese basandoci sui trend intel?"
3. "Scrivi l'introduzione di un articolo sulla moratoria toko modern a Bali — tono Zantara, 200 parole"
4. "Quali keyword KBLI stanno performando meglio su Google? Dove siamo indicizzati vs dove no?"
5. "Confronta il nostro approccio editoriale con Emerhub. Dove siamo piu' deboli?"

---

## 2. I 3 Template Temporanei

### TMPL-INTEL-WEEKLY: "Intel Weekly {YYYY-MM-DD}"

**Trigger:** Cron lunedi' 08:00 WITA via OpenClaw
**Lifecycle:** Attivo 90 giorni, poi `notebook_delete`
**Fonti:** 5-10 fonti (articoli della settimana da intel scraper + digest)
**Tag:** `intel_weekly`, `news`, `trend`
**Script:** `scripts/nlm_create_intel_weekly.py`

### TMPL-REG-WATCH: "Regulation Watch {YYYY-MM}"

**Trigger:** Primo del mese + quando `research_start` trova nuova normativa
**Lifecycle:** Attivo fino al mese successivo
**Fonti:** 5-15 fonti (nuovi PP, Permen, Perpres del mese + analisi impatto)
**Tag:** `reg_watch`, `normativa`, `update`
**Script:** `scripts/nlm_create_reg_watch.py`

### TMPL-CASE: "Case {client_type}: {description}"

**Trigger:** On-demand per casi complessi high-stakes
**Lifecycle:** Attivo fino a chiusura caso
**Fonti:** 5-20 fonti (evidenze caso + normativa rilevante + precedenti)
**Tag:** `case`, `high_stakes`, `consultation`
**Nota:** MAI PII nel titolo o nelle fonti. Solo: tipo business, KBLI, nazionalita', tipo pratica.
**Script:** `scripts/nlm_create_case.py --type investor_visa --kbli 56101 --nationality AU`

---

## 3. Strategia Multilingue

### Principio: Source Language = Authority Language

| Tipo contenuto                         | Lingua fonte                                          | Motivazione                                                      |
| -------------------------------------- | ----------------------------------------------------- | ---------------------------------------------------------------- |
| Normativa indonesiana (UU, PP, Permen) | **Indonesiano**                                       | Testo ufficiale, nessuna traduzione altera il significato legale |
| Procedure operative Bali Zero          | **Inglese**                                           | Lingua di lavoro interna                                         |
| Training conversations                 | **Inglese + Italiano**                                | Rispecchiano le lingue dei clienti                               |
| FAQ clienti                            | **Inglese** (primario), **Italiano**, **Indonesiano** | Top 3 lingue clienti                                             |
| Codice sorgente                        | **Inglese**                                           | Standard                                                         |

### Gestione nel source pack

Ogni fonte ha un campo `language` nell'header. NotebookLM gestisce il multilingual nativamente (Gemini 2.5 Pro backend).

Per le query: il client puo' chiedere in qualsiasi lingua. NotebookLM risponde nella lingua della query, citando fonti nella lingua originale. Il routing MCP aggiunge un parametro `response_language` se il canale lo richiede.

### Pattern per normativa bilingue

Per leggi critiche (PP 48/2023, UU 7/2021), carichiamo:

1. **Testo originale indonesiano** (autorita' legale)
2. **Summary in inglese** (per query in EN/IT — NotebookLM fa bridge)

NON carichiamo traduzioni complete: rischio di alterare il significato legale.

---

## 4. Script di Generazione Source Pack

Ogni notebook ha uno script riproducibile:

```
scripts/
├── nlm_pack_codebase.py          # NB-CODEBASE
├── nlm_pack_immigration.py       # NB-IMMIGRATION
├── nlm_pack_company_kbli.py      # NB-COMPANY
├── nlm_pack_tax.py               # NB-TAX
├── nlm_pack_property.py          # NB-PROPERTY
├── nlm_pack_ops.py               # NB-OPS
├── nlm_pack_editorial.py         # NB-EDITORIAL
├── nlm_create_intel_weekly.py    # TMPL-INTEL-WEEKLY
├── nlm_create_reg_watch.py       # TMPL-REG-WATCH
├── nlm_create_case.py            # TMPL-CASE
└── nlm_bootstrap_all.py          # Orchestratore: crea tutti i 7 permanenti
```

### Header standard fonte (tutti gli script)

```python
SOURCE_HEADER_TEMPLATE = """---
title: {title}
domain: {domain}
notebook: {notebook_id}
source_type: {source_type}  # regulation | training_data | qdrant_export | kg_export | documentation | code_export | faq
generated_at: {timestamp}
generator: {script_name}
language: {language}  # EN | ID | IT | MIXED
freshness_policy: {freshness}
word_count: {word_count}
priority: {priority}  # P0 | P1
---

{content}
"""
```

### Pattern export Qdrant

```python
async def export_qdrant_collection(
    collection: str,
    limit: int = 200,
    min_score: float = 0.5,
    deduplicate: bool = True
) -> str:
    """Export top documents from Qdrant collection as source pack text."""
    # 1. Scroll collection, take top N by score
    # 2. Deduplicate by content hash (first 500 chars)
    # 3. Format as markdown sections with metadata
    # 4. Return concatenated text with headers
```

### Pattern export KG

```python
async def export_kg_entities(
    entity_types: list[str],
    relationship_types: list[str],
    limit: int = 500
) -> str:
    """Export Knowledge Graph entities and relationships as source pack."""
    # 1. Query PostgreSQL kg_nodes + kg_edges
    # 2. Filter by entity_type and relationship_type
    # 3. Format as: "Entity: {name} ({type}) -> {relationship} -> {target}"
    # 4. Group by entity type
```

---

## 5. Routing MCP per Cross-Notebook Query

Il routing usa i tag per decidere quali notebook interrogare:

```python
NOTEBOOK_ROUTING = {
    # Query patterns -> notebook tags
    "visa|immigration|kitas|kitap|permit|sponsor": ["immigration"],
    "company|kbli|pt_pma|oss|nib|formation": ["company"],
    "tax|pph|ppn|npwp|spt|lkpm|bpjs|coretax": ["tax"],
    "property|zoning|land|villa|hgb|construction": ["property"],
    "code|architecture|deploy|debug|technical": ["codebase"],
    "operations|team|workflow|monitoring|competitor": ["ops"],
    "article|blog|seo|content|editorial": ["editorial"],

    # Multi-domain patterns -> fan-out
    "restaurant.*bali|open.*business.*bali": ["company", "property", "tax", "immigration"],
    "investor.*visa.*company": ["immigration", "company", "tax"],
    "freelancer.*tax.*visa": ["immigration", "tax"],
    "villa.*rental.*license": ["property", "company", "tax"],
}
```

### Fan-out/Fan-in Pattern

```
Query: "Australiano vuole aprire ristorante a Canggu con KITAS investitore"

1. Router classifica: multi-domain [company, immigration, property, tax]
2. Fan-out: cross_notebook_query su 4 notebook in parallelo
3. Fan-in: Gemini CLI sintetizza con citazioni da tutti e 4
4. Output: risposta unificata con sezioni per dominio
```

---

## 6. Manifest per ogni Notebook (README_manifest.md)

Ogni notebook contiene come prima fonte un `README_manifest.md` che dice a NotebookLM:

```markdown
# Manifest: {NOTEBOOK_NAME}

## Identita'

- **Sistema:** Bali Zero / Nuzantara AI Platform
- **Dominio:** {domain}
- **Versione fonti:** {date}
- **Totale fonti:** {count}
- **Parole totali stimate:** {total_words}

## Istruzioni per l'AI

- Rispondi SOLO basandoti sulle fonti caricate in questo notebook
- Per domande su PREZZI Bali Zero: rispondi "I prezzi devono essere verificati tramite PricingTool"
- Per domande FUORI dominio: rispondi "Questa domanda riguarda il dominio {other_domain}, non e' coperta da questo notebook"
- Cita SEMPRE la fonte specifica (titolo e sezione)
- Se una normativa e' in indonesiano, cita l'articolo originale e fornisci una spiegazione in inglese

## Esclusioni esplicite

- Prezzi e tariffe Bali Zero (usare PricingTool)
- Dati PII clienti (nomi, email, telefoni, passaporti)
- Credenziali, API keys, secrets
- Consigli legali definitivi (disclaimer: "consult a qualified attorney")

## Fonti caricate

{lista_fonti_con_tipo_e_lingua}

## Ultima rigenerazione

- Script: {script_name}
- Data: {timestamp}
- Commit: {git_hash}
```

---

## 7. Piano di Migrazione

### Fase 1: Cleanup (giorno 1)

```bash
# Elimina i 38 notebook identificati come da eliminare
python3 scripts/nlm_cleanup.py --delete-empty --delete-oneshot --dry-run
python3 scripts/nlm_cleanup.py --delete-empty --delete-oneshot --confirm
```

### Fase 2: Script Pack (giorno 1-2)

```bash
# Crea gli script di generazione (uno per notebook)
# Testa ogni script localmente
python3 scripts/nlm_pack_immigration.py --output tmp_notebooklm/immigration/ --dry-run
# Verifica: ls tmp_notebooklm/immigration/ → 25 file .txt
```

### Fase 3: Bootstrap 7 Permanenti (giorno 2-3)

```bash
# Crea e popola tutti i 7 notebook
python3 scripts/nlm_bootstrap_all.py --confirm
# Per ogni notebook:
#   1. notebook_create con titolo
#   2. source_add per ogni fonte (con retry e rate limit)
#   3. tag con MCP routing tags
#   4. Verifica notebook_describe per conferma fonti
```

### Fase 4: Normativa Indonesiana (giorno 3-5)

Fonti normative richiedono preparazione manuale:

1. Download PDF da peraturan.go.id per PP/UU/Permen non ancora in repo
2. Extract testo con OCR per PDF scanned
3. Chunk per BAB/capitolo
4. Upload come source_add type=text (non PDF per testi lunghi — migliore chunking)

**Fonti da scaricare:**

| Regolamento                     | URL                                         | Stato        |
| ------------------------------- | ------------------------------------------- | ------------ |
| PP 48/2023 (Keimigrasian)       | peraturan.go.id/pp/48/2023                  | Da scaricare |
| Permenkumham 22/2023            | peraturan.go.id                             | Da scaricare |
| UU 7/2021 (HPP)                 | peraturan.go.id/uu/7/2021                   | Da scaricare |
| PP 55/2022 (PPh)                | peraturan.go.id                             | Da scaricare |
| PMK 66/2023 (PPN)               | peraturan.go.id                             | Da scaricare |
| PP 5/2021 (Perizinan Risiko)    | peraturan.go.id                             | Da scaricare |
| Perpres 10/2021 (DNI)           | peraturan.go.id                             | Da scaricare |
| PP 18/2021 (Hak Tanah)          | peraturan.go.id                             | Da scaricare |
| UU 5/1960 (UUPA)                | peraturan.go.id                             | Da scaricare |
| PP 28/2025 (Klasifikasi Risiko) | **GIA' IN REPO** (`data/source_documents/`) | OK           |

### Fase 5: Validazione (giorno 5-6)

```bash
# Per ogni notebook, esegui le 5 query tipo e verifica risposte
python3 scripts/nlm_validate_all.py --queries queries/validation_queries.json
# Output: report con score qualita' per notebook
```

### Fase 6: Integrazione MCP (giorno 6-7)

Aggiornare il routing in `apps/nuzantara-mcp/` per usare `cross_notebook_query` con i nuovi notebook ID.

---

## 8. Budget e Limiti

| Risorsa                    | Limite                      | Nostro uso stimato                       |
| -------------------------- | --------------------------- | ---------------------------------------- |
| Notebook per account       | 100 (Free), 500 (Ultra)     | 7 permanenti + ~5-10 temporanei = ~17    |
| Fonti per notebook         | 50 (Free/Plus), 300 (Ultra) | Max 35 per notebook = sotto limite       |
| Parole per fonte           | 500.000                     | Max ~80K per fonte KBLI = sotto limite   |
| Parole totali per notebook | ~25M (Ultra)                | Max ~500K = sotto limite                 |
| Query rate                 | ~20/min (stimato)           | Fast path bypassa NLM per simple queries |

---

## 9. Metriche di Successo

| Metrica                          | Target              | Come misurare                         |
| -------------------------------- | ------------------- | ------------------------------------- |
| Query accuracy (dominio singolo) | >90%                | 5 query tipo per notebook, human eval |
| Query accuracy (cross-domain)    | >80%                | 10 query multi-dominio, human eval    |
| Latenza media notebook_query     | <8s                 | Monitoring via MCP logs               |
| Copertura normativa              | 100% PP/UU critiche | Checklist nel manifest                |
| Freshness compliance             | <30gg stale         | Script check settimanale              |
| Fonti attive / limite            | <70%                | notebook_describe per conteggio       |

---

> Documento generato da Claude Opus 4.6 su Pro.
> Prossimo step: approvazione Zero, poi implementazione script Fase 2.
