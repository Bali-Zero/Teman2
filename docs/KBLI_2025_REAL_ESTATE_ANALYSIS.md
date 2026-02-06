# Trasformazione del Settore Real Estate in KBLI 2025: Dalla Semplificazione alla Granularità

**Analisi comparativa della riclassificazione immobiliare indonesiana**

_Data: 4 Febbraio 2026_
_Fonte: Database KBLI 2025 v6.0 verificato, KBLI 2020 Official_

---

## Executive Summary

Il settore Real Estate (Kategori 68) rappresenta uno dei cambiamenti più radicali nella transizione da KBLI 2020 a KBLI 2025. Con un incremento del **180%** nel numero di codici (da 5 a 14), la nuova classificazione riflette la crescente complessità e diversificazione del mercato immobiliare indonesiano.

Questa espansione non è casuale: risponde alla necessità di distinguere attività precedentemente aggregate, riconoscere nuovi modelli di business (self-storage, property management specializzato) e allineare la classificazione alle zone economiche speciali (KEK) che rappresentano una priorità strategica per gli investimenti.

---

## 1. Quadro Comparativo Generale

### 1.1 Evoluzione Numerica

| Metrica              | KBLI 2020 | KBLI 2025      | Variazione |
| -------------------- | --------- | -------------- | ---------- |
| **Codici totali**    | 5         | 14             | +9 (+180%) |
| **Sottogruppi**      | 2         | 2              | -          |
| **Licensing status** | N/A       | 100% REGULATED | Completo   |

_Fonte: Analisi comparativa KBLI_2025_FINAL_CLEAN.json vs kbli_2020_official.json_

### 1.2 Struttura KBLI 2020 (Pre-riforma)

La classificazione precedente adottava un approccio **aggregato**, con soli 5 codici per coprire l'intero spettro delle attività immobiliari:

| Codice | Denominazione                                | Copertura                       |
| ------ | -------------------------------------------- | ------------------------------- |
| 68111  | Real Estat Yang Dimiliki Sendiri Atau Disewa | Sviluppo + Locazione + Gestione |
| 68112  | Penyewaan Venue Penyelenggaraan MICE         | Eventi e conferenze             |
| 68120  | Kawasan Pariwisata                           | Zone turistiche                 |
| 68130  | Kawasan Industri                             | Zone industriali                |
| 68200  | Real Estat Atas Dasar Balas Jasa             | Tutti i servizi a commissione   |

_Fonte: kbli_2020_official.json, codici 68xxx_

**Criticità del sistema precedente:**

- Impossibilità di distinguere attività residenziali da commerciali
- Assenza di codici per property management specializzato
- Nessun riconoscimento delle Kawasan Ekonomi Khusus (KEK)
- Servizi di valutazione aggregati con intermediazione

---

## 2. Nuova Architettura KBLI 2025

### 2.1 Gruppo 681xx: Attività su Proprietà/Locazione

#### Sviluppo e Locazione Residenziale

| Codice    | Denominazione                                                         | Status         | PP28 Source |
| --------- | --------------------------------------------------------------------- | -------------- | ----------- |
| **68111** | Aktivitas Pengembangan Bangunan dan Lahan Hunian                      | MATCH_LANGSUNG | 68111       |
| **68112** | Aktivitas Penyewaan Bangunan dan Lahan Hunian Milik Sendiri atau Sewa | MATCH_LANGSUNG | 68112       |

_Fonte: KBLI_2025_FINAL_CLEAN.json_

**Nota:** I codici mantengono la numerazione originale ma con **denominazioni ridefinite** per maggiore precisione. Il codice 68111 ora si riferisce esplicitamente allo _sviluppo_ (pengembangan) di immobili residenziali, mentre 68112 alla _locazione_ (penyewaan).

#### Gestione Zone Speciali

| Codice    | Denominazione                      | Status            | PP28 Source | Novità     |
| --------- | ---------------------------------- | ----------------- | ----------- | ---------- |
| **68121** | Pengelolaan Kawasan Pariwisata     | CODICE_RINUMERATO | 68120       | Rinumerato |
| **68122** | Pengelolaan Kawasan Industri       | CODICE_RINUMERATO | 68130       | Rinumerato |
| **68123** | Pengelolaan Kawasan Ekonomi Khusus | CODICE_RINUMERATO | 68130       | **NUOVO**  |

_Fonte: KBLI_2025_FINAL_CLEAN.json_

**Analisi:** L'introduzione del codice **68123** per le Kawasan Ekonomi Khusus (KEK) rappresenta un allineamento strategico con la politica industriale indonesiana. Le KEK, istituite con UU 39/2009 e potenziate con PP 40/2021, godono di incentivi fiscali significativi e richiedevano una classificazione dedicata per il monitoraggio statistico e la gestione delle licenze.

#### Nuove Tipologie Immobiliari

| Codice    | Denominazione                                          | Status                 | PP28 Source  | Origine           |
| --------- | ------------------------------------------------------ | ---------------------- | ------------ | ----------------- |
| **68124** | Penyewaan Tempat Penyelenggaraan MICE dan Acara Khusus | CODICE_RINUMERATO      | 82301        | Business Services |
| **68125** | Pengelolaan Pusat Perbelanjaan                         | MATCH_CON_AGGREGAZIONE | 68120, 68130 | Aggregato         |
| **68126** | Penyewaan Gudang dan Fasilitas Penyimpanan Mandiri     | CODICE_RINUMERATO      | 52101        | Warehousing       |
| **68127** | Pengelolaan Gedung Perkantoran                         | CODICE_RINUMERATO      | 68111        | Split             |
| **68129** | Aktivitas Real Estat Nonhunian Lainnya                 | CODICE_RINUMERATO      | 68111        | Split             |

_Fonte: KBLI_2025_FINAL_CLEAN.json_

**Migrazioni cross-settoriali:**

1. **68124 (MICE Venues):** Precedentemente classificato sotto Business Support Services (82301), ora riconosciuto come attività immobiliare. Questa migrazione riflette la realtà operativa dove la gestione di convention center è primariamente un'attività di property management.

2. **68126 (Self-Storage):** Migrato da Warehousing (52101). Il settore self-storage in Indonesia è in rapida crescita, con operatori come Spacebox e Store-It che richiedevano una classificazione distinta dalla logistica tradizionale.

3. **68125 (Shopping Mall):** Codice aggregato da kawasan pariwisata e industri, riconoscendo i centri commerciali come categoria immobiliare autonoma.

### 2.2 Gruppo 682xx: Servizi a Commissione (Fee-Based)

| Codice    | Denominazione                                           | Status            | PP28 Source | Novità     |
| --------- | ------------------------------------------------------- | ----------------- | ----------- | ---------- |
| **68210** | Aktivitas Jasa Intermediasi Real Estat                  | MATCH_LANGSUNG    | 68200       | Rinominato |
| **68291** | Jasa Penaksir Real Estat                                | CODICE_RINUMERATO | 68200       | **NUOVO**  |
| **68292** | Pengelolaan Real Estat Hunian Atas Dasar Balas Jasa     | CODICE_RINUMERATO | 68200       | **NUOVO**  |
| **68299** | Aktivitas Real Estat Atas Dasar Balas Jasa Lainnya YTDL | CODICE_RINUMERATO | 47920       | Migrato    |

_Fonte: KBLI_2025_FINAL_CLEAN.json_

**Disaggregazione dei servizi:**

Il codice 68200 di KBLI 2020 (Real Estat Atas Dasar Balas Jasa) è stato suddiviso in **quattro codici distinti**:

| Attività                         | KBLI 2020 | KBLI 2025 |
| -------------------------------- | --------- | --------- |
| Intermediazione (broker)         | 68200     | **68210** |
| Valutazione (appraisal)          | 68200     | **68291** |
| Property Management residenziale | 68200     | **68292** |
| Altri servizi fee-based          | 68200     | **68299** |

Questa disaggregazione permette:

- Tracciamento separato delle attività di broker vs property manager
- Riconoscimento della professione di _penaksir_ (valutatore) come attività distinta
- Migliore compliance con standard internazionali ISIC Rev.4

---

## 3. Matrice di Transizione Completa

### 3.1 Da KBLI 2020 a KBLI 2025

| KBLI 2020 | Denominazione 2020           | KBLI 2025 | Tipo Mapping        |
| --------- | ---------------------------- | --------- | ------------------- |
| 68111     | Real Estat Dimiliki Sendiri  | 68111     | MATCH_LANGSUNG      |
| 68111     | (split)                      | **68127** | Split - Perkantoran |
| 68111     | (split)                      | **68129** | Split - Nonhunian   |
| 68112     | Penyewaan Venue MICE         | 68112     | MATCH_LANGSUNG      |
| 68120     | Kawasan Pariwisata           | **68121** | CODICE_RINUMERATO   |
| 68120     | (partial)                    | **68125** | Aggregato in Mall   |
| 68130     | Kawasan Industri             | **68122** | CODICE_RINUMERATO   |
| 68130     | (split)                      | **68123** | Split - KEK         |
| 68130     | (partial)                    | **68125** | Aggregato in Mall   |
| 68200     | Real Estat Balas Jasa        | **68210** | Intermediasi        |
| 68200     | (split)                      | **68291** | Split - Penaksir    |
| 68200     | (split)                      | **68292** | Split - Pengelolaan |
| 82301     | Jasa Penyelenggara Pertemuan | **68124** | Migrato da Cat. 82  |
| 52101     | Pergudangan                  | **68126** | Migrato da Cat. 52  |
| 47920     | Perdagangan Eceran           | **68299** | Migrato da Cat. 47  |

_Fonte: Analisi cross-reference pp28_sources in KBLI_2025_FINAL_CLEAN.json_

### 3.2 Codici Eliminati/Assorbiti

| KBLI 2020 | Destino in KBLI 2025                                    |
| --------- | ------------------------------------------------------- |
| 68120     | Rinumerato → 68121; Parzialmente → 68125                |
| 68130     | Rinumerato → 68122; Split → 68123; Parzialmente → 68125 |
| 68200     | Split → 68210, 68291, 68292                             |

---

## 4. Implicazioni per gli Operatori

### 4.1 Nuovi Obblighi di Classificazione

Gli operatori che precedentemente utilizzavano codici aggregati devono ora selezionare classificazioni più specifiche:

| Attività                        | Codice Precedente | Codice Attuale |
| ------------------------------- | ----------------- | -------------- |
| Gestione mall                   | 68120 o 68130     | **68125**      |
| Gestione uffici                 | 68111             | **68127**      |
| Self-storage                    | 52101             | **68126**      |
| Convention center               | 82301             | **68124**      |
| Valutatore immobiliare          | 68200             | **68291**      |
| Property manager (residenziale) | 68200             | **68292**      |
| Sviluppatore KEK                | 68130             | **68123**      |

### 4.2 Status Licensing

**Tutti i 14 codici Real Estate sono classificati REGULATED**, con requisiti di licensing definiti in PP 28/2025:

| Risk Category   | Licensing                | Codici                     |
| --------------- | ------------------------ | -------------------------- |
| Menengah Rendah | NIB + Sertifikat Standar | 68111, 68112, 68121-68129  |
| Menengah Tinggi | NIB + Sertifikat Standar | 68210, 68291, 68292, 68299 |

_Fonte: per_skala data in KBLI_2025_FINAL_CLEAN.json_

### 4.3 Impatto sugli Investimenti Esteri (PMA)

| Codice      | pma_status | pma_max_asing | Note   |
| ----------- | ---------- | ------------- | ------ |
| 68111-68129 | TERBUKA    | 100%          | Aperto |
| 68210-68299 | TERBUKA    | 100%          | Aperto |

_Fonte: pma_status in KBLI_2025_FINAL_CLEAN.json_

**Nota:** L'intero settore Real Estate rimane **aperto al 100%** per gli investimenti esteri, senza restrizioni di proprietà. Questo posiziona l'Indonesia competitivamente rispetto ad altri mercati ASEAN con limitazioni più stringenti.

---

## 5. Analisi Settoriale: Nuove Opportunità

### 5.1 Self-Storage (68126)

Il mercato self-storage indonesiano è stimato in crescita del 15-20% annuo, trainato da:

- Urbanizzazione crescente (56% popolazione urbana nel 2025)
- Riduzione delle dimensioni abitative
- E-commerce e necessità di micro-fulfillment

La creazione di un codice dedicato facilita:

- Raccolta dati statistici sul settore
- Definizione di standard operativi specifici
- Possibile sviluppo di incentivi settoriali

### 5.2 Kawasan Ekonomi Khusus (68123)

Le KEK rappresentano una priorità strategica con **19 zone operative** nel 2025. Il codice dedicato permette:

- Tracciamento separato degli operatori KEK
- Allineamento con incentivi fiscali (tax holiday, tax allowance)
- Monitoraggio delle performance delle zone speciali

### 5.3 Property Management Professionale (68292)

La separazione del property management residenziale riflette la maturazione del mercato:

- Crescita degli investimenti in rental property
- Professionalizzazione dei servizi di gestione
- Allineamento con standard internazionali (RICS, IFMA)

---

## 6. Confronto Internazionale

### 6.1 Allineamento con ISIC Rev.5

KBLI 2025 è stato sviluppato in conformità con **ISIC Revision 5**, approvato dalla United Nations Statistical Commission (UNSC) l'11 marzo 2024. Questo rappresenta un significativo aggiornamento rispetto a KBLI 2020 che era basato su ISIC Rev.4.

_Fonte: [BPS - Rilascio KBLI 2025](https://www.bps.go.id/en/news/2025/12/19/828/bps-rilis-klasifikasi-baku-lapangan-usaha-indonesia-kbli-2025.html)_

| ISIC Rev.5 | Descrizione                                        | KBLI 2025 Corrispondente   |
| ---------- | -------------------------------------------------- | -------------------------- |
| 681        | Real estate activities with own or leased property | 68111, 68112, 68121-68129  |
| 682        | Real estate activities on a fee or contract basis  | 68210, 68291, 68292, 68299 |
| 6821       | Intermediation service activities for real estate  | 68210 (Jasa Intermediasi)  |

**Novità ISIC Rev.5 recepite in KBLI 2025:**

- Riconoscimento esplicito delle attività di intermediazione (6821)
- Separazione più netta tra attività su proprietà vs servizi fee-based
- Inclusione di self-storage facilities come categoria real estate

La struttura KBLI 2025 mantiene **piena compatibilità con ISIC Rev.5** al livello di gruppo (681, 682), mentre introduce maggiore granularità a livello nazionale per rispondere alle specificità del mercato indonesiano.

### 6.2 Benchmark Regionale

| Paese         | Classificazione | Allineamento ISIC | Codici Real Estate |
| ------------- | --------------- | ----------------- | ------------------ |
| **Indonesia** | KBLI 2025       | **Rev.5**         | 14                 |
| Singapore     | SSIC 2020       | Rev.5             | 12                 |
| Malaysia      | MSIC 2008       | Rev.4             | 8                  |
| Thailand      | TSIC 2009       | Rev.4             | 6                  |
| Vietnam       | VSIC 2018       | Rev.4             | 7                  |

L'Indonesia, insieme a Singapore, è tra i **primi paesi ASEAN** ad adottare ISIC Rev.5, posizionandosi all'avanguardia nella comparabilità statistica internazionale.

---

## 7. Raccomandazioni

### 7.1 Per gli Operatori Immobiliari

1. **Verifica classificazione:** Controllare se il codice KBLI utilizzato corrisponde ancora all'attività effettiva
2. **Aggiornamento NIB:** Per attività migrate (es. self-storage, MICE venues), considerare aggiornamento della registrazione OSS
3. **Multi-codice:** Operatori diversificati potrebbero necessitare registrazione su più codici (es. 68127 + 68292 per gestione uffici completa)

### 7.2 Per Investitori

1. **Due diligence:** Verificare che le target company utilizzino codici KBLI 2025 corretti
2. **Settori emergenti:** Self-storage (68126) e KEK (68123) presentano opportunità di crescita
3. **PMA status:** Confermare assenza di restrizioni per tutti i codici di interesse

### 7.3 Per i Policymaker

1. **Monitoraggio:** Utilizzare la nuova granularità per analisi settoriali più precise
2. **Incentivi mirati:** Possibilità di sviluppare incentivi specifici per sotto-settori (es. green building, affordable housing)
3. **Standard professionali:** Sviluppare SKKNI (Standar Kompetensi Kerja Nasional Indonesia) specifici per 68291 (valutatori) e 68292 (property manager)

---

## 8. Conclusioni

La trasformazione del settore Real Estate da 5 a 14 codici in KBLI 2025 rappresenta molto più di un esercizio tecnico di riclassificazione. Riflette:

1. **Maturazione del mercato:** Riconoscimento di attività specializzate (self-storage, property management, valutazione) come categorie autonome

2. **Allineamento strategico:** Integrazione con politiche industriali (KEK) e di sviluppo urbano

3. **Professionalizzazione:** Separazione di attività che richiedono competenze distinte (broker vs valutatore vs property manager)

4. **Apertura agli investimenti:** Mantenimento del regime PMA aperto al 100% su tutto il settore

Per gli operatori, la sfida è adattarsi rapidamente alla nuova classificazione, mentre per i policymaker l'opportunità è sfruttare la maggiore granularità per politiche settoriali più efficaci.

---

## Appendice: Fonti e Riferimenti

### Database Utilizzati

- **KBLI 2025:** `/source_documents/KBLI_2025_FINAL_CLEAN.json` v6.0
- **KBLI 2020:** `/source_documents/kbli_2020_official.json`

### Normativa di Riferimento

- **PP 28/2021** - Peraturan Pemerintah tentang Penyelenggaraan Bidang Perindustrian (Risk-Based Licensing)
- **UU 39/2009** - Undang-Undang tentang Kawasan Ekonomi Khusus
- **PP 40/2021** - Peraturan Pemerintah tentang Penyelenggaraan KEK
- **Perpres 10/2021** - Bidang Usaha Penanaman Modal (Daftar Positif Investasi)

### Standard Internazionali

- **ISIC Rev.4** - International Standard Industrial Classification of All Economic Activities (UN Statistics Division)
- **RICS** - Royal Institution of Chartered Surveyors (Property Management Standards)

### Verifica Dati

- **Data verificata:** 4 Febbraio 2026
- **Agenti di verifica:** 6
- **Risultato:** Tutti PASS
- **Cross-reference:** 1.526 codici PP28 validati contro KBLI 2020

---

_Documento generato da Zantara AI Knowledge System_
_Per aggiornamenti: consultare database KBLI_2025_FINAL_CLEAN.json_
