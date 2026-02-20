# 🎯 PIANO OPERAZIONE TKA - ARRICCHIMENTO 1,563 KBLI

**Progetto:** Mappatura completa Tenaga Kerja Asing (TKA) per KBLI Navigator  
**Fonte dati:** Kepmenaker 228/2019 + KBLI 2025 (BPS + PP28)  
**Target:** 1,563 KBLI con TKA info esatta al 100%  
**Output:** JSON arricchito, LangGraph Collections, Knowledge Graph, KBLI Navigator

---

## 📊 SITUAZIONE ATTUALE

| Metrica                    | Valore    | %         |
| -------------------------- | --------- | --------- |
| KBLI totali                | 1,563     | 100%      |
| Con TKA mapping            | 104       | 6.7%      |
| **Da arricchire**          | **1,459** | **93.3%** |
| Categorie Kepmen 228       | 18        | -         |
| Jabatan totali disponibili | ~2,100    | -         |

---

## 🏗️ ARCHITETTURA DEL PIANO

### FASE 1: PREPARAZIONE DATI (Settimana 1)

#### 1.1 Analisi struttura Kepmen 228/2019

```
18 Categorie → 45+ Sub-categorie → 2,100+ Jabatan

Esempio struttura:
Category 1: Konstruksi
├── 1.1: Konstruksi Gedung (57 jabatan)
│   ├── Manajer Konstruksi (ISCO: 1323)
│   ├── Ahli Teknik Sipil (ISCO: 2142)
│   └── ...
├── 1.2: Konstruksi Bangunan Sipil (50 jabatan)
└── 1.3: Konstruksi Khusus (74 jabatan)
```

#### 1.2 Mappatura Settore KBLI ↔ Kategori Kepmen

| Settore KBLI           | Codici | Kategori Kepmen                  | Jabatan Relevanti |
| ---------------------- | ------ | -------------------------------- | ----------------- |
| A (Agriculture)        | ~90    | 5 (Agriculture)                  | 8 jabatan         |
| B (Mining)             | ~113   | 14 (Mining)                      | 592 jabatan       |
| C (Manufacturing)      | ~480   | 4 (Manufacturing)                | 239 jabatan       |
| D (Electricity)        | ~75    | 15 (Electricity)                 | 40 jabatan        |
| F (Construction)       | ~400   | 1 (Construction)                 | 181 jabatan       |
| G (Trade)              | ~200   | 16 (Trade)                       | 48 jabatan        |
| I (Accommodation/F&B)  | ~84    | 8 (Accommodation/F&B)            | 12 jabatan        |
| J (IT/Communication)   | ~200   | 12,13 (Media/IT)                 | 254 jabatan       |
| K (Finance)            | ~60    | 11 (Financial)                   | 32 jabatan        |
| L (Real Estate)        | ~35    | 2 (Real Estate)                  | 6 jabatan         |
| M (Professional)       | ~200   | 18 (Professional)                | 20 jabatan        |
| N (Admin/Support)      | ~100   | 10 (Rental), 17 (Other Services) | 11 jabatan        |
| P (Education)          | ~50    | 3 (Education)                    | 143 jabatan       |
| Q (Health)             | ~50    | 6 (Healthcare)                   | 20 jabatan        |
| R (Arts/Entertainment) | ~70    | 7 (Arts/Entertainment)           | 57 jabatan        |
| S (Other Services)     | ~80    | 17 (Other Services)              | 8 jabatan         |

---

### FASE 2: STRATEGIA DI MAPPING (Settimana 2)

#### 2.1 Metodologia di Assegnazione TKA

Per ogni KBLI, determiniamo:

```javascript
{
  "kode_kbli": "68111",
  "judul": "AKTIVITAS PENGEMBANGAN BANGUNAN DAN LAHAN HUNIAN",
  "tka_info": {
    "category_id": 2,                    // Da Kepmen 228
    "category_name_en": "Real Estate",
    "category_name_id": "Real Estat",
    "total_jabatan_in_category": 6,      // Totale posizioni disponibili
    "relevant_positions": [              // Sottoinsieme specifico per KBLI
      {
        "title_en": "Property Development Manager",
        "title_id": "Manajer Pengembangan Properti",
        "isco": "1223",
        "priority": "high",              // Alta rilevanza per questo KBLI
        "kedua_eligible": true           // Può essere Direttore
      },
      {
        "title_en": "Real Estate Project Manager",
        "title_id": "Manajer Proyek Real Estat",
        "isco": "1321",
        "priority": "high",
        "kedua_eligible": false
      }
    ],
    "insight": "Kepmen 228/2019 lists 6 TKA-eligible positions in Real Estate. For residential development, the most relevant are Property Development Manager and Project Manager. Directors not managing HR can work without RPTKA.",
    "kedua_note": "Directors and Commissioners who do NOT manage personalia (HR/staffing) can work without being listed in the jabatan — standard path for foreign owners holding Director positions.",
    "dkptka_fee_usd": 100,               // $100/jabatan/person/month
    "rptka_required": true,              // Work permit required
    "restriction_notes": null            // Null se nessuna restrizione
  }
}
```

#### 2.2 Algoritmo di Matching

**Step 1: Categorizzazione KBLI**

- Estrai settore dai primi 2-3 digit del codice KBLI
- Verifica keyword nel titolo (es. "Hotel", "Software", "Construction")
- Mappa a Categoria Kepmen 228

**Step 2: Selezione Jabatan Relevanti**

- Dalla categoria, filtra jabatan per rilevanza semantica
- Priorità basata su:
  - Keyword matching (titolo KBLI vs titolo jabatan)
  - ISCO code appropriateness
  - Seniority level (Manager per KBLI complessi, Technician per operativi)

**Step 3: Validazione**

- Cross-check con gold_codes esistenti (104 già validati)
- Verifica consistenza settore
- Controllo KEDUA provision applicability

---

### FASE 3: IMPLEMENTAZIONE (Settimane 3-6)

#### 3.1 Approccio Ibrido: Automated + Human-in-the-loop

```
┌─────────────────────────────────────────────────────────────┐
│                    WORKFLOW TKA ENRICHMENT                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ KBLI     │───→│ AI       │───→│ Human    │              │
│  │ Input    │    │ Matching │    │ Review   │              │
│  │ (1,563)  │    │ (Auto)   │    │ (Zero)   │              │
│  └──────────┘    └──────────┘    └──────────┘              │
│        │              │               │                     │
│        ↓              ↓               ↓                     │
│   ┌────────────────────────────────────────┐               │
│   │     QUALITY GATES                      │               │
│   ├────────────────────────────────────────┤               │
│   │  ✓ High confidence (>90%): Auto-accept │               │
│   │  ⚠ Medium (70-90%): Human review       │               │
│   │  ✗ Low (<70%): Manual mapping          │               │
│   └────────────────────────────────────────┘               │
│                         │                                   │
│                         ↓                                   │
│   ┌────────────────────────────────────────┐               │
│   │     OUTPUT: kbli-2025-enriched.json    │               │
│   │     - All 1,563 KBLI with TKA          │
│   │     - Confidence scores                │
│   │     - Source attributions              │
│   └────────────────────────────────────────┘               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### 3.2 Batch Processing

| Batch | Settore                     | # KBLI | Settimana | Metodo               |
| ----- | --------------------------- | ------ | --------- | -------------------- |
| 1     | L (Real Estate)             | 35     | W3        | Manual (alto valore) |
| 2     | I (Accommodation/F&B)       | 84     | W3        | Hybrid               |
| 3     | J (IT/Communication)        | 200    | W4        | AI-assisted          |
| 4     | F (Construction)            | 400    | W4-W5     | AI-assisted          |
| 5     | C (Manufacturing)           | 480    | W5-W6     | AI-assisted          |
| 6     | G (Trade)                   | 200    | W6        | AI-assisted          |
| 7     | Altri (A,B,D,K,M,N,P,Q,R,S) | 164    | W6        | Manual/AI            |

---

### FASE 4: VALIDAZIONE E QUALITÀ (Settimana 7)

#### 4.1 Checklist Qualità

Per ogni KBLI arricchito:

- [ ] Almeno 1 jabatan con priority "high"
- [ ] ISCO code valido (4-6 digit)
- [ ] KEDUA note presente se applicabile
- [ ] Insight specifico per settore
- [ ] DKPTKA fee indicata ($100/person/month)
- [ ] RPTKA requirement chiaro
- [ ] Cross-check con 104 gold codes esistenti

#### 4.2 Testing

```python
# Test Suite
def test_tka_completeness():
    assert len(enriched_kbli) == 1563
    assert all(k['tka_info'] for k in enriched_kbli)

def test_tka_consistency():
    # Verifica che 104 gold codes non siano cambiati
    for code in existing_gold_codes:
        assert enriched[code] == existing[code]

def test_jabatan_validity():
    # Verifica ISCO codes validi
    for kbli in enriched_kbli:
        for pos in kbli['tka_info']['relevant_positions']:
            assert len(pos['isco']) in [4, 6]
```

---

### FASE 5: INTEGRAZIONE MULTI-SISTEMA (Settimana 8)

#### 5.1 Output Generati

| Sistema             | Formato                   | Contenuto                   |
| ------------------- | ------------------------- | --------------------------- |
| **KBLI Navigator**  | `kbli-gold-content.ts`    | TKA per 246 Gold codes      |
| **KB (Backend)**    | `kbli-2025-enriched.json` | Tutti 1,563 KBLI con TKA    |
| **LangGraph**       | Vector embeddings         | TKA info nelle collections  |
| **Knowledge Graph** | Nodes/Edges               | Relazioni KBLI↔Jabatan↔ISCO |
| **API**             | `/api/kbli/{code}`        | TKA in risposta API         |

#### 5.2 Schema JSON Finale

```json
{
  "metadata": {
    "version": "v9.0-tka-complete",
    "source": "BPS_7_2025 + PP28_2024 + Kepmen_228_2019",
    "total_codes": 1563,
    "tka_coverage": "100%",
    "enriched_date": "2026-03-XX"
  },
  "data": [
    {
      "kode_kbli_2025": "68111",
      "judul": "AKTIVITAS PENGEMBANGAN BANGUNAN DAN LAHAN HUNIAN",
      "uraian": "...",
      "per_skala": [...],
      "tka_enrichment": {
        "category_id": 2,
        "category_name": "Real Estate",
        "relevant_positions": [...],
        "insight": "...",
        "kedua_note": "...",
        "dkptka_fee_usd": 100,
        "mapping_confidence": 0.95,
        "mapped_by": "ai+human",
        "mapped_date": "2026-02-XX"
      }
    }
  ]
}
```

---

## 📅 TIMELINE DETTAGLIATA

```
SETTIMANA 1: PREPARAZIONE
├── Giorno 1-2: Analisi Kepmen 228/2019 completa
├── Giorno 3-4: Analisi KBLI 2025 per settore
└── Giorno 5-7: Definizione algoritmi matching

SETTIMANA 2: SETUP AUTOMATION
├── Giorno 1-3: Sviluppo AI matching engine
├── Giorno 4-5: Setup quality gates
└── Giorno 6-7: Test su batch pilota (50 KBLI)

SETTIMANE 3-6: PROCESSING BATCH
├── Batch 1-2 (Settore L, I): 119 KBLI - Manuale
├── Batch 3-4 (Settore J, F): 600 KBLI - AI-assisted
├── Batch 5-6 (Settore C, G): 680 KBLI - AI-assisted
└── Batch 7 (Altri): 164 KBLI - Hybrid

SETTIMANA 7: VALIDAZIONE
├── Giorno 1-3: Quality review
├── Giorno 4-5: Testing integrazione
└── Giorno 6-7: Fix e refinimenti

SETTIMANA 8: DEPLOYMENT
├── Giorno 1-2: Generazione output multi-formato
├── Giorno 3-4: Deploy su LangGraph
├── Giorno 5-6: Deploy su KG
└── Giorno 7: Final testing e release
```

---

## 🛠️ RISORSE NECESSARIE

### Team

| Ruolo                    | FTE | Durata      |
| ------------------------ | --- | ----------- |
| AI/ML Engineer           | 1   | 8 settimane |
| Data Curator (Zero)      | 0.5 | 8 settimane |
| Domain Expert (Legal/HR) | 0.3 | 4 settimane |
| QA Engineer              | 0.5 | 3 settimane |

### Tools

- **AI Matching:** Claude/GPT-4 API per semantic matching
- **Database:** PostgreSQL per staging
- **Validation:** Python + Pydantic
- **Versioning:** Git con tracking changes

### Stima Costi

- AI API calls: ~$500 (1,459 KBLI × multiple prompts)
- Human review time: ~80 ore
- **Totale stimato:** $2,000-3,000

---

## ✅ CRITERI DI SUCCESSO

1. **Coverage:** 100% dei 1,563 KBLI con TKA info
2. **Accuracy:** >95% confidence score su mapping
3. **Consistency:** Zero regression su 104 gold codes esistenti
4. **Completeness:** Tutti i campi TKA popolati
5. **Performance:** Query TKA <100ms in produzione

---

## 🚀 PROSSIMI PASSI

1. **Approvazione piano** da Zero
2. **Setup ambiente** di sviluppo
3. **Inizio Fase 1** (Preparazione dati)
4. **Checkpoint** a fine ogni settimana

---

_Documento versione 1.0 - Pronto per review_
