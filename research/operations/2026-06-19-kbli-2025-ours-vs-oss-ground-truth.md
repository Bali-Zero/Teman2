---
date: 2026-06-19
domain: compliance
client_case: none
sources:
  - OSS RBA iOS app API (gw.oss.go.id/v2/portal/kbli, id_version fff4053d = KBLI 2025), extracted 2026-06-19
  - data/source_documents/KBLI_2025_FINAL_CLEAN.json (our v8.0-final, 1563 codes)
  - data/source_documents/KBLI_2025_OSS_GROUND_TRUTH.json (sha256 5d207ede, 2422 records / 1559 5-digit)
---

# KBLI 2025 - Nostro JSON vs OSS ground-truth: quanto ci siamo avvicinati al vero

**Domanda (Antonello):** "in primis si parte da quello che OSS dice, perche noi abbiamo presunto
in molti casi. Quindi la mia curiosita e quanto ci siamo avvicinati al vero."

OSS = verita. Noi = KBLI_2025_FINAL_CLEAN.json (presunto/arricchito). Confronto sui SOLI campi
condivisi (kode, judul, uraian).

## Verdetto sintetico

| Dimensione | Risultato | Giudizio |
|---|---|---|
| Copertura codici | 1559/1563 reali (99.7%) - 0 buchi - 4 fantasma | quasi perfetta |
| Judul fedeli | 1185/1559 (76%) esatti/normalizzati | 337 troncati + 4 sbagliati |
| Uraian fedeli | 1408/1559 (90.3%) sim >=0.80 - media 0.937 | molto alta |

Ci siamo avvicinati MOLTO al vero sui contenuti (uraian sim media 0.94); copertura quasi perfetta.
I difetti sono concentrati e identificabili, non diffusi.

## 1. Copertura - 99.7%
- 0 buchi: ogni KBLI 5-digit OSS 2025 e presente da noi.
- 4 codici fantasma (nostri, ASSENTI da OSS 2025, probabilmente solo KBLI 2020): 26120 (Chips/IC),
  60111 (Siaran Radio Pemerintah), 82920 (Aktivitas Pengemasan), 85598 (Jasa Pendidikan Swasta YTDL).
  AZIONE: verificare se rimuovere o marcare deprecati-2020.

## 2. Judul - 76% fedeli; il 24% divergente si scompone:
- 337 = nostro TRONCATO (titolo tagliato). Cosmetico. AZIONE: rigenerare da OSS.
- 30 = solo EN aggiunto da noi (arricchimento, non errore).
- 4 = JUDUL SBAGLIATO su uraian giusta (il vero difetto):
  | Kode | Nostro (SBAGLIATO) | OSS (vero) |
  |---|---|---|
  | 02102 | Seed Collection / Pengambilan Benih Hutan | Pemanfaatan Kayu Hutan |
  | 02103 | Forest Tree Nursery / Pembibitan Tanaman Hutan | Pembenihan Tanaman Kehutanan |
  | 02401 | Forestry Support Services / Jasa Penunjang Kehutanan | Jasa Lingkungan Hutan |
  | 02402 | Timber Harvesting Support / Jasa Penunjang Pemanenan Kayu | Jasa Penggunaan Kawasan Kehutanan |
  Pattern: cluster forestale 02xxx, titoli ereditati da mappatura KBLI 2020; uraian gia allineata
  al 2025 (nostra=OSS). OSS ha riassegnato i codici, noi non l'abbiamo recepito nei titoli.
  AZIONE: correggere i 4 judul da OSS.

## 3. Uraian - sim media 0.937
- 43.1% identici, 19.4% quasi(>=0.95), 27.8% alti(0.80-0.95) = 90.3% fedeli.
- Solo 14 (0.9%) sotto 0.50: NON divergenze di significato, ma testi nostri SPORCHI (parole-extra
  di codici vicini incollate, troncamenti). Es. 46752 ha "...46753 perdagangan bes" appeso.
  AZIONE: pulire 14 uraian da OSS.

## Azioni proposte (priorita)
1. [P1] Correggere 4 judul forestali 02xxx (errore di significato, impatta ricerche cliente).
2. [P2] Decidere sui 4 codici fantasma (rimuovere o marcare deprecati-2020).
3. [P3] Rigenerare 337 judul troncati da OSS.
4. [P3] Pulire 14 uraian sporchi.
5. I nostri arricchimenti (per_skala, PMA, intel_2026, baliContext) NON sono toccati da questo
   confronto: restano il nostro valore aggiunto sopra il ground-truth.

Report dati: /tmp/kbli_compare_report.json. Metodo: join kode 5-digit, NFKC+lowercase+whitespace
normalize, Jaccard token-sim. Vedi [[discovery_oss_rba_kbli_api_extraction_2026_06_19]].
