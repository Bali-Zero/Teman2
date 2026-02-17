# NotebookLM Documents Mapping per Domain

**Strategia:** 1 Notebook NotebookLM = 1 Domain = Set documenti specifici

---

## 📚 Notebook 1: VISA & IMMIGRATION (Person 1)

**NotebookLM Name:** "Nuzantara - Visa & Immigration"

### Documenti Necessari:

#### Priority 1 (CRITICAL):

```
✅ PP 31/2013 - Immigration Law (base regulations)
✅ Permenkumham 28/2024 - E-Visa regulations
✅ PP 34/2021 - IMTA/Work Permits (foreign workers)
```

#### Priority 2 (IMPORTANT):

```
✅ Kemnaker Job Position List 2024-2025
   - Approved foreign worker positions
   - Educational requirements per job
   - Sector quotas

✅ Immigration Circular Letters (Surat Edaran) 2024-2025
   - Latest visa policy updates
   - Processing timelines
   - Fee schedules
```

#### Priority 3 (NICE TO HAVE):

```
□ Provincial immigration variations (Bali, Jakarta)
□ IMTA application forms & checklists
□ Embassy/consulate specific requirements
```

### Dove Trovare:

**Se hai PDFs:**

```bash
# Check project directories
find . -name "*PP*31*2013*" -o -name "*Permenkumham*28*" -o -name "*PP*34*2021*"
```

**Se NON hai PDFs:**

- NotebookLM può usare **general knowledge** se specifichi:
  ```
  "Basandoti sulle ultime normative Indonesia 2024-2025
  (PP 31/2013, Permenkumham 28/2024, PP 34/2021)..."
  ```
- Download da: https://peraturan.bpk.go.id / https://jdih.kemenkumham.go.id

**Kemnaker Job List:**

- Probabilmente Excel/PDF da Kementerian Ketenagakerjaan
- Se non disponibile, chiedi a NotebookLM lista generica job positions approvati

---

## 📚 Notebook 2: KBLI & BUSINESS LICENSING (Person 2)

**NotebookLM Name:** "Nuzantara - KBLI & Licensing"

### Documenti Necessari:

#### Already Available ✅ in `data/kb_sources/`:

```
✅ PP Nomor 28 Tahun 2025.pdf (20MB) - Latest KBLI regulations
✅ KBLI_2025_FINAL_CLEAN.json (7.3MB) - 9,612 business codes
✅ lampiran_1a.pdf (12MB) - KBLI appendix A
✅ lampiran_1b.pdf (22MB) - KBLI appendix B
```

#### Additional Needed:

```
✅ PP 5/2021 - Investment Law (PMA regulations)
✅ Negative Investment List (DNI) 2021-2025
   - Sectors closed to foreign investment
   - Partnership requirements

□ Sector-specific regulations:
   - F&B licensing (Dinkes, BPOM)
   - Construction (IMB, SLF)
   - Tourism (TDUP, star rating)
   - Import/Export (API, NIK)
```

### Action for Person 2:

```bash
# Documents already ready
cd data/kb_sources/
ls -lh
# Upload these 4 files to NotebookLM

# If need more regulations:
# - PP 5/2021: find in project or download
# - DNI list: usually embedded in PP 5/2021
```

**Person 2 ha GIÀ tutto il necessario per iniziare!** ✅

---

## 📚 Notebook 3: TAX & COMPLIANCE (Person 3)

**NotebookLM Name:** "Nuzantara - Tax & Compliance"

### Documenti Necessari:

#### Priority 1 (CRITICAL):

```
✅ UU 7/2021 - Tax Harmonization Law
   - PPh Badan 22% (corporate tax)
   - PPN 11% (VAT) - NOT 12%!
   - All tax rates official

✅ PP 55/2022 - Income Tax Implementation
   - PPh 21 (employee withholding)
   - PPh 23 (service withholding)
   - PPh 26 (foreign withholding)

✅ DJP Guidelines 2024-2025
   - E-Faktur (VAT invoicing)
   - PKP registration (VAT taxpayer)
   - Tax filing deadlines
```

#### Priority 2 (IMPORTANT):

```
✅ Tax Treaties (DTA - Double Taxation Agreements)
   - Indonesia - Italia
   - Indonesia - USA
   - Indonesia - Singapore
   - Indonesia - Australia
   - Others per common expat countries

□ Provincial tax variations
   - PBB (property tax) rates by region
   - Local levies
```

### Dove Trovare:

**Government sources:**

- https://pajak.go.id (DJP - Tax authority)
- https://peraturan.bpk.go.id (search "UU 7/2021", "PP 55/2022")

**Tax Treaties:**

- https://pajak.go.id/id/internasional/tax-treaty

**Alternative:**

- Se non hai PDFs, NotebookLM può usare general knowledge:
  ```
  "Basandoti su UU 7/2021 e PP 55/2022 (Tax Harmonization Law Indonesia),
  spiega aliquota PPh Badan per PT PMA..."
  ```

---

## 📚 Notebook 4: PROPERTY & REAL ESTATE (Person 4)

**NotebookLM Name:** "Nuzantara - Property & Real Estate"

### Documenti Necessari:

#### Priority 1 (CRITICAL):

```
✅ PP 18/2021 - Hak Pakai for Foreigners
   - Foreign property ownership rights
   - 30-year title rules
   - Renewal procedures

✅ UUPA (Undang-Undang Pokok Agraria) - Basic Agrarian Law
   - Hak Milik (ownership - citizens only)
   - Hak Guna Bangunan (building rights)
   - Hak Pakai (usage rights - foreigners)
   - Hak Sewa (lease/rental)
```

#### Priority 2 (IMPORTANT):

```
□ Provincial zoning regulations
   - Bali: tourism zones, foreign ownership restrictions
   - Jakarta: commercial vs residential
   - Other provinces

□ Property tax regulations
   - PBB (Land & Building Tax)
   - BPHTB (Transfer tax 5%)

□ Rental regulations
   - Long-term lease agreements
   - Short-term rental (villa rental licensing)
```

### Dove Trovare:

**Government sources:**

- PP 18/2021: https://peraturan.bpk.go.id
- UUPA: Standard agrarian law (1960, updated)

**Bali-specific:**

- Perda (Provincial regulation) Bali on property
- IMB (building permit) requirements

---

## 📚 Notebook 5: CROSS-DOMAIN LEVEL 2 (Person 5)

**NotebookLM Name:** "Nuzantara - Cross Domain Level 2"

### Documenti Necessari:

#### Strategy: **Upload ALL docs from Notebooks 1-4**

```
From Notebook 1 (Visa):
✅ PP 31/2013
✅ Permenkumham 28/2024
✅ PP 34/2021
✅ Kemnaker Job List

From Notebook 2 (KBLI):
✅ PP 28/2025
✅ KBLI_2025_FINAL_CLEAN.json
✅ Lampiran 1a, 1b
✅ PP 5/2021

From Notebook 3 (Tax):
✅ UU 7/2021
✅ PP 55/2022
✅ DJP Guidelines

From Notebook 4 (Property):
✅ PP 18/2021
✅ UUPA
```

**Total:** ~15-20 documents

**Purpose:** NotebookLM can cross-reference between domains

- Company setup + Visa requirements
- Property purchase + Tax implications
- Business + Immigration + Tax scenarios

---

## 📚 Notebook 6: MULTI-DOMAIN SOTA (Person 6)

**NotebookLM Name:** "Nuzantara - Multi-Domain SOTA"

### Documenti Necessari:

#### Strategy: **Upload EVERYTHING + extras**

```
All docs from Notebooks 1-5 PLUS:

✅ Case studies (se disponibili)
   - Real PT PMA setup examples
   - Family relocation scenarios
   - Complex business structures

✅ Provincial variations
   - Bali-specific regulations
   - Jakarta regulations
   - Tourism zone rules

✅ Expert interpretations
   - Legal opinions
   - BKPM clarifications
   - Immigration office memos

✅ Cross-reference indices
   - How domains interact
   - Common pitfalls
   - Best practices
```

**Total:** 20-30+ documents

**Purpose:** Most comprehensive knowledge base per SOTA queries

---

## 🗂️ Document Preparation Checklist

### For YOU (Setup):

```bash
# 1. Check existing documents
cd /Users/antonellosiano/Projects/nuzantara
find . -name "*.pdf" | grep -E "(PP|UU|Permen)" | head -20

# 2. Organize by domain
mkdir -p data/notebooklm_docs/{visa,kbli,tax,property,cross,multi}

# 3. Copy KBLI docs (already done)
ls data/kb_sources/
# ✅ PP 28/2025, KBLI JSON, Lampiran 1a/1b

# 4. Find other regulations
# Person 1 needs: PP 31/2013, Permenkumham 28/2024, PP 34/2021
# Person 3 needs: UU 7/2021, PP 55/2022
# Person 4 needs: PP 18/2021, UUPA
```

### For TEAM:

**Option A: You provide all PDFs**

- Team just uploads to NotebookLM
- Fastest, most consistent

**Option B: Team finds their own docs**

- You provide list + sources
- Each person downloads for their domain
- More flexible but slower

**Option C: Hybrid (RECOMMENDED)**

- You provide critical docs (PP 28/2025, etc.) ✅ Already done
- Team uses NotebookLM general knowledge per other regulations
- Specify regulation numbers in prompts

---

## 📋 Document Status Matrix

| Domain       | Critical Docs        | Status   | Location           |
| ------------ | -------------------- | -------- | ------------------ |
| **KBLI**     | PP 28/2025 + JSON    | ✅ READY | `data/kb_sources/` |
| **KBLI**     | Lampiran 1a, 1b      | ✅ READY | `data/kb_sources/` |
| **Visa**     | PP 31/2013           | ⚠️ FIND  | TBD                |
| **Visa**     | Permenkumham 28/2024 | ⚠️ FIND  | TBD                |
| **Visa**     | PP 34/2021           | ⚠️ FIND  | TBD                |
| **Visa**     | Kemnaker Job List    | ⚠️ FIND  | TBD                |
| **Tax**      | UU 7/2021            | ⚠️ FIND  | TBD                |
| **Tax**      | PP 55/2022           | ⚠️ FIND  | TBD                |
| **Property** | PP 18/2021           | ⚠️ FIND  | TBD                |
| **Property** | UUPA                 | ⚠️ FIND  | TBD                |

---

## 🎯 Next Actions

### Immediate:

1. **Search for missing PDFs:**

```bash
# Search project for regulations
find . -type f -name "*.pdf" | xargs grep -l "PP.*2013\|PP.*2021\|UU.*2021" 2>/dev/null

# Or check if you have regulation repository
ls ~/Documents/Indonesia_Regulations/ 2>/dev/null || echo "Create regulation folder"
```

2. **Decision Point:**

**A) Hai i PDFs?**
→ Organizziamo in `data/notebooklm_docs/{domain}/`
→ Team fa upload

**B) NON hai PDFs?**
→ Team usa NotebookLM general knowledge
→ Specifica regulation numbers in ogni prompt
→ Example: "Basandoti su PP 31/2013..."

**C) Hybrid?** (RACCOMANDATO)
→ KBLI domain: Use PDFs (già pronti) ✅
→ Altri domains: NotebookLM general knowledge
→ Quality ancora ottima con regulation citations

### Domanda per te:

**Vuoi che:**

A) **Cerco i PDFs mancanti** nel progetto/online?
B) **Procediamo senza PDFs** (NotebookLM general knowledge)?
C) **Team trova i propri PDFs** (io do solo link fonti)?

Dimmi e organizzo! 🚀
