# 🎯 PIANO OPERAZIONE TKA - VERSIONE CORRETTA

**Nota:** Dopo analisi approfondita dello stato PMA, il target reale è **1,524 KBLI** (non 1,563).

---

## 📊 ANALISI CORRETTA ELEGIBILITÀ TKA

### Distribuzione PMA Status

| Stato PMA                 | # KBLI | %     | TKA Applicable?                    |
| ------------------------- | ------ | ----- | ---------------------------------- |
| **TERBUKA (Open)**        | 1,512  | 96.7% | ✅ SÌ - 100% foreign ownership     |
| **TERBATAS (Restricted)** | 12     | 0.8%  | ⚠️ SÌ - Con limitazioni/condizioni |
| **TERTUTUP (Closed)**     | 39     | 2.5%  | ❌ NO - 0% foreign ownership       |
| **TOTAL**                 | 1,563  | 100%  | **1,524 elegibili**                |

### I 39 KBLI CLOSED (NO TKA POSSIBILE)

Questi KBLI **non avranno TKA info** perché completamente chiusi a investimento straniero:

**Settore C - Manufacturing (2):**

- `11010` - Industria distillazione alcolici
- `11020` - Industria vino da fermentazione
- `20119` - Industria chimica base anorganica

**Settore O - Public Administration (26):**

- `84111-84119` - Lembaga Legislatif, Eksekutif, dll.
- `84121-84149` - Administrasi pelayanan pemerintah
- `84210` - Hubungan luar negeri

**Settore D - Defense (8):**

- `84221-84224` - Angkatan Bersenjata (Darat, Udara, Laut)
- `84231` - Kepolisian
- `84232-84234` - Pertahanan sipil, Peradilan

**Altri (3):**

- `01287` - Pertanian tanaman narkotika
- `92000` - Aktivitas perjudian dan pertaruhan
- `99000` - Aktivitas badan internasional

**Per questi 39 KBLI:**

- ✅ **KEDUA provision applicabile** (Direttori/Commissionari possono lavorare senza essere in jabatan)
- ❌ **NO TKA positions** (non possono assumere lavoratori stranieri)
- 📝 **Nota informativa:** "This KBLI is CLOSED to foreign investment. Only Indonesian nationals can hold positions. Foreigners can only be Directors/Commissioners under KEDUA provision."

---

### I 12 KBLI RESTRICTED (TKA CON LIMITAZIONI)

Questi KBLI possono avere TKA ma con restrizioni specifiche:

| KBLI    | Judul                            | Restrizione TKA                                    |
| ------- | -------------------------------- | -------------------------------------------------- |
| `02101` | Pengelolaan Hutan                | Forestry - limited positions                       |
| `02102` | Pemanfaatan Kayu Hutan           | Timber - limited positions                         |
| `03110` | Penangkapan ikan laut            | Fishing - crew restrictions                        |
| `03120` | Penangkapan ikan perairan        | Fishing - crew restrictions                        |
| `47111` | Perdagangan eceran swalayan      | Retail - may have local content reqs               |
| `47221` | Perdagangan minuman beralkohol   | Alcohol - special permits needed                   |
| `47222` | Perdagangan minuman non-alkohol  | Beverage - may have restrictions                   |
| `50111` | Angkutan laut domestik penumpang | Shipping - crew nationality rules                  |
| `50112` | Angkutan laut domestik perintis  | Shipping - crew nationality rules                  |
| `50121` | Angkutan laut domestik barang    | Shipping - crew nationality rules                  |
| `73100` | Aktivitas periklanan             | Advertising - local partner may be required        |
| `79110` | Aktivitas agen perjalanan        | Travel agency - may have equity caps affecting TKA |

**Per questi 12 KBLI:**

- TKA info presente con **WARNING notes**
- Indicazione delle **limitazioni specifiche**
- Link a **regolamenti aggiuntivi** (es. UU Perkapalan, UU Kehutanan)

---

## 🎯 TARGET FINALE

```
┌─────────────────────────────────────────────────────────────────┐
│                    TKA ENRICHMENT TARGET                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  🟢 GRUPPO A: TKA Standard (1,512 KBLI)                        │
│     └── PMA TERBUKA - Mappatura TKA completa                   │
│                                                                 │
│  🟡 GRUPPO B: TKA con Limitazioni (12 KBLI)                    │
│     └── PMA TERBATAS - TKA + warning notes                     │
│                                                                 │
│  🔴 GRUPPO C: NO TKA (39 KBLI)                                 │
│     └── PMA TERTUTUP - Solo KEDUA note, no positions           │
│                                                                 │
│  📊 TOTALE DA PROCESSARE: 1,524 KBLI                           │
│     (1,512 + 12 con TKA / 39 con note KEDUA)                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🏗️ SCHEMA DATI TKA PER GRUPPO

### Gruppo A (TERBUKA) - 1,512 KBLI

```json
{
  "kode_kbli": "68111",
  "pma_status": "TERBUKA",
  "tka_info": {
    "applicable": true,
    "category_id": 2,
    "category_name": "Real Estate",
    "relevant_positions": [
      {
        "title_en": "Property Development Manager",
        "title_id": "Manajer Pengembangan Properti",
        "isco": "1223",
        "priority": "high",
        "kedua_eligible": true
      }
    ],
    "total_in_category": 6,
    "dkptka_fee_usd": 100,
    "rptka_required": true,
    "restriction_notes": null,
    "insight": "...",
    "kedua_note": "Directors not managing HR can work without RPTKA"
  }
}
```

### Gruppo B (TERBATAS) - 12 KBLI

```json
{
  "kode_kbli": "47221",
  "pma_status": "TERBATAS",
  "pma_condition": "Requires special alcohol distribution license",
  "tka_info": {
    "applicable": true,
    "warning": "RESTRICTED SECTOR - Additional permits required",
    "category_id": 16,
    "category_name": "Wholesale & Retail Trade",
    "relevant_positions": [...],
    "restriction_notes": "Alcohol retail TKA subject to SKP-A (Surat Keterangan Pengecer) requirements. Local partnership may be required for certain positions.",
    "additional_permits": ["SKP-A", "NPI (Nomer Pengenal Importir)"],
    "dkptka_fee_usd": 100
  }
}
```

### Gruppo C (TERTUTUP) - 39 KBLI

```json
{
  "kode_kbli": "11010",
  "pma_status": "TERTUTUP",
  "pma_max_asing": 0,
  "tka_info": {
    "applicable": false,
    "reason": "CLOSED to foreign investment - 0% foreign ownership allowed",
    "relevant_positions": [],
    "total_in_category": 0,
    "restriction_notes": "This KBLI is completely closed to foreign investment under Positive Investment List (DNI). No TKA positions available.",
    "kedua_note": "Foreigners can ONLY serve as Directors or Commissioners under KEDUA provision, provided they do NOT manage HR/staffing (personalia). They cannot hold any operational positions.",
    "alternative_codes": [
      {
        "code": "56301",
        "description": "Bar operation - OPEN to PMA, can serve alcohol"
      },
      {
        "code": "46201",
        "description": "Alcohol wholesale distribution - check PMA status"
      }
    ]
  }
}
```

---

## 📅 TIMELINE AGGIORNATA (7 settimane)

### Settimana 1: Preparazione e Classificazione

- **Giorno 1-2:** Analisi Kepmen 228/2019 completa
- **Giorno 3:** Classificazione 1,563 KBLI per gruppo (A/B/C)
- **Giorno 4-5:** Definizione algoritmi matching per Gruppo A
- **Giorno 6-7:** Setup database e strutture dati

### Settimana 2: Setup Automazione

- **Giorno 1-3:** AI matching engine per Gruppo A (1,512 KBLI)
- **Giorno 4:** Gestione casi speciali Gruppo B (12 KBLI)
- **Giorno 5:** Template Gruppo C (39 KBLI)
- **Giorno 6-7:** Testing su batch pilota (100 KBLI)

### Settimane 3-6: Processing per Batch

**Batch 1 (Settore I - Accommodation/F&B):** 84 KBLI

- 80 TERBUKA → TKA standard
- 4 TERTUTUP (se presenti) → NO TKA

**Batch 2 (Settore L - Real Estate):** 35 KBLI

- Tutti TERBUKA → TKA standard

**Batch 3 (Settore J - IT/Communication):** 200 KBLI

- Tutti TERBUKA → TKA standard (AI-assisted)

**Batch 4 (Settore F - Construction):** 400 KBLI

- 395 TERBUKA → TKA standard
- 5 potenzialmente RESTRICTED → Verifica

**Batch 5 (Settore C - Manufacturing):** 480 KBLI

- 475 TERBUKA → TKA standard
- 2 TERTUTUP (11010, 11020, 20119) → NO TKA
- 3 RESTRICTED → TKA con limitazioni

**Batch 6 (Settore G - Trade):** 200 KBLI

- 193 TERBUKA → TKA standard
- 7 RESTRICTED (inclusi 47111, 47221, 47222) → TKA con warning

**Batch 7 (Altri settori):** ~125 KBLI

- Misto A/B/C

### Settimana 7: Validazione Finale

- Quality check su tutti 1,524 KBLI
- Verifica coerenza con 104 gold codes esistenti
- Testing integrazione

---

## ✅ CHECKLIST QUALITÀ PER GRUPPO

### Gruppo A (TERBUKA)

- [ ] Almeno 1 jabatan con priority "high"
- [ ] ISCO code valido
- [ ] KEDUA note presente
- [ ] DKPTKA fee indicata ($100)
- [ ] RPTKA requirement chiaro

### Gruppo B (TERBATAS)

- [ ] Warning "RESTRICTED SECTOR" in evidenza
- [ ] Restriction_notes dettagliate
- [ ] Additional permits elencati
- [ ] Link a regolamenti specifici

### Gruppo C (TERTUTUP)

- [ ] Flag "applicable: false" chiaro
- [ ] Reason: "CLOSED to foreign investment"
- [ ] KEDUA note esplicita (unica via per stranieri)
- [ ] Alternative codes suggeriti (se esistono)
- [ ] No jabatan list (vuota)

---

## 📊 OUTPUT ATTESO

| Gruppo    | # KBLI    | Output TKA        | Note                |
| --------- | --------- | ----------------- | ------------------- |
| A         | 1,512     | TKA completo      | Standard enrichment |
| B         | 12        | TKA + warning     | Limited enrichment  |
| C         | 39        | NO TKA + KEDUA    | Minimal enrichment  |
| **Total** | **1,563** | **1,524 con TKA** | **97.5% coverage**  |

---

## 💡 VANTAGGI DELLA NUOVA APPROCCIO

1. **Accuratezza legale:** Non suggeriamo TKA dove è impossibile
2. **User experience:** Utenti vedono chiaramente cosa è possibile e cosa no
3. **Alternative paths:** Per KBLI closed, suggeriamo codici alternativi open
4. **Compliance:** Rispettiamo esattamente DNI (Daftar Negatif Investasi)

---

**Documento versione 2.0 - Corretto con analisi PMA**
