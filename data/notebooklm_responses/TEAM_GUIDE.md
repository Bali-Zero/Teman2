# Team Guide - NotebookLM Q&A per Golden Seeds

**Obiettivo:** Generare 500-800 conversazioni validated usando NotebookLM + team manuale

**Workflow:** NotebookLM Q&A → File .txt → Damar validation → Redis cache

---

## 👥 Team Roles & Responsabilità

### Person 1: **VISA SPECIALIST**

- **Focus:** Tutti i visa types + Kemnaker job positions
- **Target:** 100-120 domande basic
- **Notebook:** "Nuzantara - Visa & Immigration"
- **Directory:** `data/notebooklm_responses/visa/`

### Person 2: **KBLI SPECIALIST**

- **Focus:** KBLI codes (priorità Tier 1 granitici) + business licenses
- **Target:** 150-200 domande basic
- **Notebook:** "Nuzantara - KBLI & Licensing"
- **Directory:** `data/notebooklm_responses/kbli/`

### Person 3: **TAX SPECIALIST**

- **Focus:** Tutti i tax types (PPh, PPN, treaties)
- **Target:** 40-50 domande basic
- **Notebook:** "Nuzantara - Tax & Compliance"
- **Directory:** `data/notebooklm_responses/tax/`

### Person 4: **PROPERTY SPECIALIST**

- **Focus:** Property titles + foreign ownership rules
- **Target:** 30-40 domande basic
- **Notebook:** "Nuzantara - Property & Real Estate"
- **Directory:** `data/notebooklm_responses/property/`

### Person 5: **CROSS-DOMAIN COORDINATOR**

- **Focus:** Scenari 2-topic (company+visa, visa+property, etc.)
- **Target:** 100-150 domande level 2
- **Notebook:** "Nuzantara - Cross Domain Level 2"
- **Directory:** `data/notebooklm_responses/cross_domain/`

### Person 6: **SOTA ARCHITECT**

- **Focus:** Scenari multi-domain complessi (3+ topics)
- **Target:** 50-80 domande level 3
- **Notebook:** "Nuzantara - Multi-Domain SOTA"
- **Directory:** `data/notebooklm_responses/multi_domain/`

---

## 📝 Workflow Step-by-Step (per ogni persona)

### Step 1: Setup NotebookLM Notebook

1. Vai a: https://notebooklm.google.com
2. Crea notebook con nome specifico (es: "Nuzantara - Visa & Immigration")
3. Upload documenti per il tuo dominio (vedi sotto)
4. Aspetta indexing (3-5 min)

### Step 2: Prepara Lista Domande

Ogni persona ha un file `questions_list.md` nella sua directory:

```bash
# Person 1 (Visa)
cp data/notebooklm_responses/visa/questions_template.md \
   data/notebooklm_responses/visa/MY_QUESTIONS.md

# Edita MY_QUESTIONS.md con le tue domande
```

### Step 3: Fai Domande a NotebookLM

**Per ogni domanda:**

1. Copia domanda da `MY_QUESTIONS.md`
2. Incolla in NotebookLM chat
3. Aspetta risposta (30-60 secondi)
4. **IMPORTANTE:** Leggi risposta per verificare qualità
5. Copia risposta completa

### Step 4: Salva Risposta in File

**Naming convention:**

```
data/notebooklm_responses/{domain}/{id}_{topic}.txt

Esempi:
visa/001_kitas_investor.txt
kbli/045_restaurant_56101.txt
tax/012_pph_badan_corporate.txt
```

**Formato file .txt:**

```
## Query
[La tua domanda]

## Response
[Risposta completa di NotebookLM con citazioni]

## Metadata
- Domain: visa_immigration
- Complexity: basic
- Date: 2026-02-09
- Validated: pending
```

### Step 5: Gestione Risposte Lunghe

**Se risposta > 1000 parole, splitta in parti:**

```
visa/001_kitas_investor_part1.txt  (Definizione + Requisiti)
visa/001_kitas_investor_part2.txt  (Processo + Timeline)
visa/001_kitas_investor_part3.txt  (Costi + FAQ)
```

**Aggiungi header in ogni parte:**

```
## Query
[Domanda completa]

## Response - Part 1/3: Definizione e Requisiti
[Contenuto parte 1]

---
Continua in: 001_kitas_investor_part2.txt
```

### Step 6: Tracking Progress

Ogni persona mantiene `PROGRESS.md`:

```markdown
# VISA Domain - Progress

**Total Questions:** 120
**Completed:** 45
**In Progress:** 10
**Pending:** 65

## Completed (45)

- [x] 001_kitas_investor.txt
- [x] 002_kitas_work.txt
- [x] 003_e33g_digital_nomad.txt
      ...

## In Progress (10)

- [ ] 046_kemnaker_job_software_engineer.txt
- [ ] 047_kemnaker_job_chef.txt
      ...

## Issues / Notes

- KITAS renewal process: NotebookLM cita PP 31/2013, verificare aggiornamenti 2024
- E-Visa timeline: risposta vaga "7-14 giorni", chiedere more specific
```

---

## 📚 Documenti per NotebookLM (per dominio)

**STRATEGIA HYBRID (RACCOMANDATO):**

- **KBLI domain (Person 2):** Use PDFs già pronti in `data/kb_sources/` ✅
- **Altri domains (Person 1, 3, 4):** Use NotebookLM general knowledge + regulation citations
- **Cross/Multi-domain (Person 5, 6):** Combina PDFs KBLI + general knowledge altri domini

**Perché hybrid?**

- KBLI specialist può iniziare SUBITO con documenti completi
- Altri specialists non bloccati cercando PDFs
- NotebookLM general knowledge è accurata se specifichi regulation numbers
- Se PDFs diventano disponibili dopo, possono essere aggiunti

---

### VISA SPECIALIST (Person 1)

**APPROCCIO:** General knowledge + regulation citations

In ogni domanda, specifica i regolamenti:

```
"Basandoti su PP 31/2013 (Immigration Law),
Permenkumham 28/2024 (E-Visa), e PP 34/2021 (IMTA),
spiega cos'è KITAS Investor e requisiti completi..."
```

**Optional PDFs** (se disponibili):

- PP 31/2013 (Immigration Law)
- Permenkumham 28/2024 (E-Visa)
- PP 34/2021 (IMTA/Work Permits)
- Kemnaker Job Position List

**Se trovi PDFs:** Carica su NotebookLM per citazioni più precise

### KBLI SPECIALIST (Person 2)

**APPROCCIO:** ✅ PDFs completi READY TO USE

Upload questi 4 files (già in `data/kb_sources/`):

```
✅ PP Nomor 28 Tahun 2025.pdf (20MB)
✅ KBLI_2025_FINAL_CLEAN.json (7.3MB)
✅ lampiran_1a.pdf (12MB)
✅ lampiran_1b.pdf (22MB)
```

**Person 2 può iniziare SUBITO!** 🚀

**Per KBLI Tier 2 (in attesa BKPM):**

Aggiungi questo prompt suffix:

```
Se questo KBLI code è ancora in attesa di clarification da BKPM,
indica chiaramente:

"⚠️ ATTENZIONE: KBLI [code] è IN ATTESA di clarification ufficiale da BKPM.
La risposta seguente è basata su interpretazione preliminare di PP 28/2025
e può essere soggetta a modifiche.

[Risposta provvisoria con citazioni disponibili]

Consiglio: Verificare con BKPM prima di procedere con registrazione business."
```

### TAX SPECIALIST (Person 3)

**APPROCCIO:** General knowledge + regulation citations

In ogni domanda, specifica:

```
"Basandoti su UU 7/2021 (Tax Harmonization Law)
e PP 55/2022 (Income Tax Implementation),
spiega aliquota PPh Badan per PT PMA..."
```

**CRITICAL:** Sempre verificare:

- PPN rate: 11% (NOT 12%)
- PPh Badan: 22%
- Cite UU 7/2021 in ogni risposta

**Optional PDFs** (se disponibili):

- UU 7/2021 (Tax Harmonization)
- PP 55/2022 (Income Tax)
- DJP Guidelines 2024-2025

### PROPERTY SPECIALIST (Person 4)

**APPROCCIO:** General knowledge + regulation citations

In ogni domanda, specifica:

```
"Basandoti su PP 18/2021 (Hak Pakai for foreigners)
e UUPA (Basic Agrarian Law),
spiega requisiti per stranieri comprare property..."
```

**CRITICAL:** Sempre menzionare:

- Hak Pakai (foreigners) vs Hak Milik (Indonesians only)
- KITAS requirement
- Provincial minimums (Bali Rp 1-2B, Jakarta Rp 3-5B)
- Nominee risks (ILLEGAL)

**Optional PDFs** (se disponibili):

- PP 18/2021 (Hak Pakai)
- UUPA (Agrarian Law 1960)

### CROSS-DOMAIN (Person 5)

Upload:

```
✅ TUTTI i documenti di Person 1-4
```

### MULTI-DOMAIN (Person 6)

Upload:

```
✅ TUTTI i documenti disponibili
✅ Case studies se disponibili
```

---

## ✅ Quality Gates (self-check)

Prima di salvare risposta, verifica:

### Checklist Minima:

- [ ] **Citazioni:** Almeno 2 citazioni `[Source: PP XX/YEAR, Article Y]`
- [ ] **Lunghezza:** 200-600 parole (basic), 800-1200 (complex)
- [ ] **Struttura:** Headings (##) e bullet points presenti
- [ ] **Accuratezza:** Numeri e date sembrano corretti
- [ ] **Warnings:** KBLI Tier 2 ha disclaimer appropriato

### Red Flags (da controllare):

- ❌ "Circa", "approssimativamente" senza citation
- ❌ Numeri molto generici ("10-20 milioni IDR")
- ❌ "Secondo le normative" (quale normativa?)
- ❌ Contraddizioni interne

### Se trovi Red Flags:

**Opzione A:** Fai follow-up a NotebookLM:

```
"Nella risposta precedente hai menzionato 'circa 10 milioni IDR'.
Puoi citare la fonte esatta con numero di articolo?"
```

**Opzione B:** Annota in `PROGRESS.md` per review successiva

---

## 🔄 Daily Workflow Template

### Morning (2 hours):

1. Review `PROGRESS.md`
2. Prioritize 10-15 questions for today
3. Open NotebookLM notebook
4. Batch Q&A (10-15 questions)
5. Save responses to `.txt` files

### Afternoon (1 hour):

6. Self-check responses (quality gates)
7. Split long responses if needed
8. Update `PROGRESS.md`
9. Flag issues for team review

### Estimated Output:

- **Per person per day:** 10-15 validated responses
- **Per person per week:** 50-75 responses
- **Full team per week:** 300-450 responses
- **Timeline to 800 total:** ~2-3 weeks

---

## 🚨 Common Issues & Solutions

### Issue 1: NotebookLM risposta troppo generica

**Soluzione:** Riformula domanda con più contesto:

```
Invece di:
"Cos'è KITAS Investor?"

Usa:
"Cos'è KITAS Investor per stranieri che aprono PT PMA in Indonesia?
Includi requisiti di investimento minimo, durata, processo application,
e differenze vs KITAS Work. Cita PP 31/2013 articoli rilevanti."
```

### Issue 2: NotebookLM non cita documenti caricati

**Soluzione:** Esplicita nella domanda:

```
"Basandoti sui documenti caricati (PP 28/2025 e KBLI 2025 JSON),
spiega quali codici KBLI permettono investimenti stranieri nel settore F&B."
```

### Issue 3: Risposta contraddittoria o obsoleta

**Soluzione:** Flag in `PROGRESS.md`:

```
## Issues / Notes
- 023_vitas_211.txt: NotebookLM menziona VITAS 211, ma è OBSOLETO dal 2022
  → Sostituito da E-Visa. Rigenerare domanda con context aggiornato.
```

### Issue 4: Risposta troppo lunga (>2000 parole)

**Soluzione:** Split e specifica scope:

```
Domanda 1: "KITAS Investor - Parte 1: Definizione e requisiti base"
Domanda 2: "KITAS Investor - Parte 2: Processo application step-by-step"
Domanda 3: "KITAS Investor - Parte 3: Renewal e FAQ comuni"
```

---

## 📊 Consolidation (dopo Phase 1)

**Quando il team completa basic questions:**

Ogni person passa i suoi `.txt` files al coordinator che:

1. Valida format consistency
2. Checks quality gates
3. Consolida in `data/golden_seeds.json`
4. Passa a Damar per validation finale

**Script di consolidation:**

```bash
python scripts/caching/consolidate_team_responses.py \
  --input data/notebooklm_responses/ \
  --output data/golden_seeds_all.json
```

---

## 🎯 Success Metrics

**Per Person:**

- [ ] 100% domande assegnate completate
- [ ] 90%+ pass quality self-check
- [ ] `PROGRESS.md` aggiornato daily

**Per Team:**

- [ ] 500-800 responses totali
- [ ] 80%+ Damar validation pass rate
- [ ] Timeline: 2-3 settimane

---

## 📞 Team Communication

**Daily Standup (15 min):**

- Ognuno: "Ieri: X done, Oggi: Y planned, Issues: Z"
- Sync su cross-domain dependencies

**Weekly Review:**

- Quality check campione casuale (10%)
- Adjust templates se needed
- Celebrate progress! 🎉

---

**Ready to start!** 🚀

Ogni persona inizia con Step 1: Setup NotebookLM per il proprio dominio.
