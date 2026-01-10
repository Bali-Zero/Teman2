# 🔍 INVESTIGAZIONE PROFONDA QDRANT - Report Finale

**Data:** 2026-01-10  
**Metodo:** Analisi API diretta + Codebase analysis  
**Script:** `scripts/deep_qdrant_investigation.py`, `scripts/check_legacy_collections.py`

---

## 📊 EXECUTIVE SUMMARY

### Stato Attuale
- **11 collezioni** attive (vs 7 documentate)
- **58,022 documenti totali** (vs 53,757 documentati)
- **3 gruppi di duplicati** identificati (standard vs hybrid)
- **2 collezioni obsolete** (vuote)
- **1 collezione mancante** (`bali_zero_team`)

### Problemi Critici Identificati

1. ⚠️ **DISCREPANZA MASSIVA**: `legal_unified_hybrid` ha 47,959 docs (vs 5,041 attesi)
2. ⚠️ **DOCUMENTI MANCANTI**: `kbli_unified` ha solo 2,818 docs (vs 8,886 attesi) - **-68%**
3. ⚠️ **DOCUMENTI MANCANTI**: `visa_oracle` ha solo 82 docs (vs 1,612 attesi) - **-95%**
4. ❌ **COLLEZIONE MANCANTE**: `bali_zero_team` non esiste più
5. 🔄 **CODICE OBSOLETO**: Query router fa riferimento a `legal_unified` che non esiste più

---

## 📋 ANALISI DETTAGLIATA COLLEZIONI

### ✅ Collezioni Attive e Funzionanti

| Collezione | Docs | Status | Note |
|------------|------|--------|------|
| `legal_unified_hybrid` | **47,959** | ✅ Active | ⚠️ Contiene molti più documenti del previsto |
| `training_conversations_hybrid` | 3,525 | ✅ Active | 🆕 Nuova collezione non documentata |
| `training_conversations` | 2,898 | ✅ Active | Standard version (migrazione in corso?) |
| `kbli_unified` | 2,818 | ✅ Active | ⚠️ Solo 32% dei documenti attesi |
| `tax_genius_hybrid` | 332 | ✅ Active | Coerente con standard |
| `tax_genius` | 332 | ✅ Active | Standard version |
| `visa_oracle` | 82 | ✅ Active | ⚠️ Solo 5% dei documenti attesi |
| `bali_zero_pricing` | 70 | ✅ Active | ⚠️ Più documenti del previsto (+141%) |
| `balizero_news_history` | 6 | ✅ Active | 🆕 Nuova collezione non documentata |

### 🗑️ Collezioni Obsolete

| Collezione | Docs | Motivo | Azione Consigliata |
|------------|------|--------|-------------------|
| `collective_memories` | 0 | Vuota | Verificare se dovrebbe essere popolata |
| `bali_zero_pricing_hybrid` | 0 | Vuota | Rimuovere o popolare |

---

## 🔄 COLLEZIONI DUPLICATE (Standard vs Hybrid)

### Pattern Identificati

#### 1. `training_conversations` vs `training_conversations_hybrid`
- **Standard**: 2,898 docs
- **Hybrid**: 3,525 docs (+22%)
- **Status**: Migrazione in corso o incompleta
- **Raccomandazione**: Completare migrazione e rimuovere standard

#### 2. `tax_genius` vs `tax_genius_hybrid`
- **Standard**: 332 docs
- **Hybrid**: 332 docs (identici)
- **Status**: Migrazione completata ma standard non rimossa
- **Raccomandazione**: Rimuovere `tax_genius` standard (duplicato)

#### 3. `bali_zero_pricing` vs `bali_zero_pricing_hybrid`
- **Standard**: 70 docs
- **Hybrid**: 0 docs (vuota)
- **Status**: Hybrid creata ma mai popolata
- **Raccomandazione**: Rimuovere `bali_zero_pricing_hybrid` (obsoleta)

---

## ⚠️ DISCREPANZE CRITICHE

### 1. `legal_unified_hybrid` - Aumento Massivo (+851%)

**Problema:**
- Documentazione: 5,041 docs
- Reale: **47,959 docs**
- Differenza: **+42,918 docs** (+851%)

**Possibili Cause:**
1. ✅ **Consolidamento**: Collezione contiene anche `legal_unified` (non più esistente)
2. ✅ **Migrazione incompleta**: Documenti da altre collezioni legali consolidate qui
3. ✅ **Ingestione massiva**: Nuovi documenti legali aggiunti senza documentazione

**Verifica:**
- ✅ `legal_unified` standard **NON ESISTE PIÙ** (verificato)
- ✅ Query router fa ancora riferimento a `legal_unified` (codice obsoleto)

**Azione Richiesta:**
1. Aggiornare query router: `legal_unified` → `legal_unified_hybrid`
2. Verificare origine dei 47,959 documenti
3. Aggiornare documentazione con numero reale

---

### 2. `kbli_unified` - Riduzione Massiva (-68%)

**Problema:**
- Documentazione: 8,886 docs
- Reale: **2,818 docs**
- Differenza: **-6,068 docs** (-68%)

**Possibili Cause:**
1. ⚠️ **Migrazione incompleta**: Documenti spostati a `kbli_unified_hybrid` (non trovata)
2. ⚠️ **Cleanup**: Documenti duplicati/obsoleti rimossi
3. ⚠️ **Errore documentazione**: Numero originale errato

**Verifica:**
- ❌ `kbli_unified_hybrid` **NON ESISTE** (verificato)
- ✅ Collezione esiste ma con meno documenti

**Azione Richiesta:**
1. Verificare se esiste backup o collezione legacy con documenti mancanti
2. Controllare migrazioni recenti per `kbli_unified`
3. Aggiornare documentazione con numero reale

---

### 3. `visa_oracle` - Riduzione Massiva (-95%)

**Problema:**
- Documentazione: 1,612 docs
- Reale: **82 docs**
- Differenza: **-1,530 docs** (-95%)

**Possibili Cause:**
1. ⚠️ **Migrazione incompleta**: Documenti spostati a `visa_oracle_hybrid` (non trovata)
2. ⚠️ **Cleanup massivo**: Documenti obsoleti rimossi
3. ⚠️ **Errore documentazione**: Numero originale errato

**Verifica:**
- ❌ `visa_oracle_hybrid` **NON ESISTE** (verificato)
- ✅ Collezione esiste ma con pochissimi documenti

**Azione Richiesta:**
1. Verificare se esiste backup o collezione legacy con documenti mancanti
2. Controllare migrazioni recenti per `visa_oracle`
3. Investigare perché solo 82 documenti rimasti
4. Aggiornare documentazione con numero reale

---

### 4. `bali_zero_team` - Collezione Mancante

**Problema:**
- Documentazione: 22 docs
- Reale: **NON ESISTE**

**Possibili Cause:**
1. ⚠️ **Rimossa**: Collezione eliminata ma documentazione non aggiornata
2. ⚠️ **Rinominata**: Collezione rinominata in altro nome
3. ⚠️ **Mai esistita**: Errore nella documentazione originale

**Verifica:**
- ❌ Collezione **NON TROVATA** in Qdrant
- ✅ Query router fa ancora riferimento a `bali_zero_team` (codice obsoleto)

**Azione Richiesta:**
1. Verificare se dati team sono in altra collezione
2. Rimuovere riferimento da query router se non più necessaria
3. Aggiornare documentazione

---

## 🔧 PROBLEMI NEL CODICE

### Query Router - Riferimenti Obsoleti

**File:** `apps/backend-rag/backend/services/routing/query_router.py`

**Problemi trovati:**
1. Linea 572, 580: Riferimento a `legal_unified` (non esiste più)
   - **Dovrebbe essere:** `legal_unified_hybrid`
   
2. Linea 595: Riferimento a `bali_zero_team` (non esiste più)
   - **Azione:** Rimuovere o verificare alternativa

**Impatto:**
- Query legali potrebbero fallire o usare fallback
- Query team potrebbero fallire

**Fix Richiesto:**
```python
# Da:
collection = "legal_unified"

# A:
collection = "legal_unified_hybrid"
```

---

## 📝 RACCOMANDAZIONI PRIORITARIE

### Priorità CRITICA (Immediata)

1. **Fix Query Router**
   - Sostituire `legal_unified` → `legal_unified_hybrid`
   - Rimuovere o fixare `bali_zero_team`
   - Testare routing dopo fix

2. **Investigare Documenti Mancanti**
   - Verificare backup Qdrant per `kbli_unified` e `visa_oracle`
   - Controllare migrazioni recenti (migration_031)
   - Verificare se documenti sono in altre collezioni

3. **Pulizia Collezioni Obsolete**
   - Rimuovere `bali_zero_pricing_hybrid` (vuota)
   - Decidere su `collective_memories` (vuota ma potrebbe essere necessaria)

### Priorità ALTA (Questa settimana)

4. **Completare Migrazioni**
   - Decidere se mantenere `tax_genius` standard o rimuoverla
   - Completare migrazione `training_conversations` → hybrid
   - Rimuovere collezioni standard se migrazione completata

5. **Aggiornare Documentazione**
   - `docs/AI_ONBOARDING.md` - Statistiche Qdrant
   - `docs/SYSTEM_MAP_4D.md` - Quick Stats
   - `docs/QDRANT_COLLECTIONS.md` - Dettaglio collezioni
   - Documentare nuove collezioni (`training_conversations*`, `balizero_news_history`)

### Priorità MEDIA (Questo mese)

6. **Verificare Origine Documenti**
   - Investigare perché `legal_unified_hybrid` ha così tanti documenti
   - Verificare se contiene anche documenti da altre collezioni
   - Documentare struttura e origine

7. **Ottimizzazione**
   - Valutare se mantenere duplicati standard/hybrid
   - Consolidare collezioni dove possibile
   - Implementare cleanup automatico per collezioni vuote

---

## 📊 STATISTICHE FINALI

### Collezioni per Stato

| Stato | Count | Documenti Totali |
|-------|-------|------------------|
| ✅ Active (popolate) | 9 | 58,016 |
| 📭 Empty (obsolete?) | 2 | 0 |
| **TOTALE** | **11** | **58,016** |

### Collezioni per Tipo

| Tipo | Count | Note |
|------|-------|------|
| Standard | 5 | Alcune potrebbero essere obsolete |
| Hybrid | 4 | Formato moderno con BM25 |
| New/Unknown | 2 | `balizero_news_history`, `collective_memories` |

---

## 🔄 PATTERN MIGRAZIONE IDENTIFICATI

### Migrazione Hybrid (Migration 031)

**Pattern trovato:**
- `tax_genius` → `tax_genius_hybrid` ✅ Completata (identici)
- `training_conversations` → `training_conversations_hybrid` ⚠️ In corso (+22%)
- `bali_zero_pricing` → `bali_zero_pricing_hybrid` ❌ Fallita (hybrid vuota)

**Status generale:** Migrazione parzialmente completata

**Raccomandazione:** Completare migrazione e rimuovere collezioni standard obsolete

---

## 📁 FILE DI REPORT

- **JSON Report:** `docs/QDRANT_INVESTIGATION_REPORT.json`
- **Script Investigazione:** `scripts/deep_qdrant_investigation.py`
- **Script Legacy Check:** `scripts/check_legacy_collections.py`
- **Report Statistiche:** `docs/QDRANT_STATS_REAL_2026.md`

---

## ✅ PROSSIMI STEP

1. ✅ Investigazione completata
2. ⏳ Fix query router (codice obsoleto)
3. ⏳ Verificare documenti mancanti (backup/migrazioni)
4. ⏳ Pulizia collezioni obsolete
5. ⏳ Aggiornare documentazione

---

**Investigazione completata:** 2026-01-10  
**Investigatore:** AI Assistant + Scripts automatizzati  
**Versione Qdrant:** Cloud (nuzantara-qdrant.fly.dev)
