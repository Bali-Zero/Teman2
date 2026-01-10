# 📊 Qdrant Statistics - Verifica Reale 2026-01-10

**Data Verifica:** 2026-01-10  
**Metodo:** API diretta a Qdrant Cloud  
**Script:** `scripts/verify_qdrant_stats.py`

---

## 📈 Statistiche Generali

| Metrica | Valore |
|---------|--------|
| **Collezioni totali** | 11 |
| **Documenti totali** | **58,022** |
| **Status generale** | ✅ Healthy (tutte le collezioni in stato "green") |

---

## 📋 Dettaglio Collezioni

| Collezione | Documenti | Status | Vector Size | Note |
|------------|-----------|--------|-------------|------|
| `legal_unified_hybrid` | **47,959** | ✅ green | unknown | ⚠️ Aumento massivo vs doc (5,041) |
| `training_conversations_hybrid` | **3,525** | ✅ green | unknown | 🆕 Nuova collezione |
| `training_conversations` | **2,898** | ✅ green | 1536 | 🆕 Nuova collezione |
| `kbli_unified` | **2,818** | ✅ green | unknown | ⚠️ Riduzione vs doc (8,886) |
| `tax_genius_hybrid` | **332** | ✅ green | unknown | 🆕 Nuova collezione |
| `tax_genius` | **332** | ✅ green | 1536 | ✅ Coerente con range doc (332-895) |
| `visa_oracle` | **82** | ✅ green | unknown | ⚠️ Riduzione significativa vs doc (1,612) |
| `bali_zero_pricing` | **70** | ✅ green | 1536 | ⚠️ Aumento vs doc (29) |
| `balizero_news_history` | **6** | ✅ green | unknown | 🆕 Nuova collezione |
| `collective_memories` | **0** | ✅ green | 1536 | ℹ️ Esiste ma vuota |
| `bali_zero_pricing_hybrid` | **0** | ✅ green | unknown | ℹ️ Esiste ma vuota |

---

## 🔍 Confronto con Documentazione

### Collezioni Documentate vs Reali

| Collezione | Documentazione | Reale | Differenza | Status |
|------------|----------------|-------|------------|--------|
| `kbli_unified` | 8,886 | 2,818 | **-6,068** | ⚠️ Riduzione 68% |
| `legal_unified_hybrid` | 5,041 | 47,959 | **+42,918** | ⚠️ Aumento 851% |
| `visa_oracle` | 1,612 | 82 | **-1,530** | ⚠️ Riduzione 95% |
| `tax_genius` | 332-895 | 332 | -563 (vs max) | ✅ Coerente (minimo range) |
| `bali_zero_pricing` | 29 | 70 | **+41** | ⚠️ Aumento 141% |
| `bali_zero_team` | 22 | **N/A** | Non trovata | ❌ Non presente |

### Totale Documenti

| Metrica | Valore |
|---------|--------|
| **Documenti totali (doc)** | 53,757 |
| **Documenti totali (reale)** | 58,022 |
| **Differenza** | **+4,265** (+7.9%) |

---

## 🆕 Collezioni Non Documentate

### Nuove Collezioni Trovate

1. **`training_conversations_hybrid`** (3,525 docs)
   - Collezione per training conversazioni con formato hybrid
   - Status: ✅ Active

2. **`training_conversations`** (2,898 docs)
   - Collezione per training conversazioni standard
   - Vector size: 1536 (OpenAI embeddings)
   - Status: ✅ Active

3. **`tax_genius_hybrid`** (332 docs)
   - Versione hybrid di tax_genius
   - Status: ✅ Active

4. **`balizero_news_history`** (6 docs)
   - Storia news Bali Zero
   - Status: ✅ Active (piccola collezione)

5. **`collective_memories`** (0 docs)
   - Memoria collettiva (vuota)
   - Vector size: 1536
   - Status: ✅ Active ma vuota

6. **`bali_zero_pricing_hybrid`** (0 docs)
   - Versione hybrid di pricing (vuota)
   - Status: ✅ Active ma vuota

---

## ⚠️ Discrepanze Significative

### 1. `legal_unified_hybrid` - Aumento Massivo

**Problema:** 47,959 documenti invece di 5,041 (+851%)

**Possibili cause:**
- Consolidamento di più collezioni legali
- Migrazione da collezioni legacy
- Ingestione massiva di nuovi documenti

**Azione richiesta:**
- Verificare origine documenti
- Controllare se contiene anche `legal_unified` (non hybrid)
- Aggiornare documentazione

### 2. `kbli_unified` - Riduzione Significativa

**Problema:** 2,818 documenti invece di 8,886 (-68%)

**Possibili cause:**
- Migrazione a formato hybrid (`kbli_unified_hybrid`?)
- Cleanup/rimozione documenti duplicati
- Migrazione a nuova collezione

**Azione richiesta:**
- Verificare se esiste `kbli_unified_hybrid`
- Controllare migrazioni recenti
- Aggiornare documentazione

### 3. `visa_oracle` - Riduzione Massiva

**Problema:** 82 documenti invece di 1,612 (-95%)

**Possibili cause:**
- Migrazione a formato hybrid (`visa_oracle_hybrid`?)
- Rimozione documenti obsoleti
- Errore nella documentazione originale

**Azione richiesta:**
- Verificare se esiste `visa_oracle_hybrid`
- Controllare migrazioni recenti
- Verificare se documenti sono stati spostati

### 4. `bali_zero_team` - Non Trovata

**Problema:** Collezione non presente

**Possibili cause:**
- Rinominata in altra collezione
- Rimossa/consolidata
- Mai esistita (errore documentazione)

**Azione richiesta:**
- Cercare collezioni simili (`team_*`, `bali_zero_*`)
- Verificare se dati sono in altra collezione
- Aggiornare documentazione

---

## 📝 Raccomandazioni

### Priorità Alta

1. **Aggiornare documentazione principale:**
   - `docs/AI_ONBOARDING.md` - Sezione Qdrant Collections
   - `docs/SYSTEM_MAP_4D.md` - Statistiche Qdrant
   - `docs/QDRANT_COLLECTIONS.md` - Dettaglio collezioni

2. **Verificare migrazioni recenti:**
   - Controllare se ci sono state migrazioni a formato "hybrid"
   - Verificare consolidamento collezioni

3. **Investigare discrepanze:**
   - `legal_unified_hybrid`: Perché così tanti documenti?
   - `kbli_unified`: Dove sono finiti i 6,068 documenti mancanti?
   - `visa_oracle`: Dove sono finiti i 1,530 documenti mancanti?

### Priorità Media

4. **Documentare nuove collezioni:**
   - `training_conversations*` - Scopo e uso
   - `tax_genius_hybrid` - Differenza con `tax_genius`
   - `balizero_news_history` - Scopo e uso

5. **Verificare collezioni vuote:**
   - `collective_memories` - Perché vuota? Dovrebbe essere popolata?
   - `bali_zero_pricing_hybrid` - Perché vuota? È un placeholder?

---

## 🔄 Prossimi Step

1. ✅ Verifica completata via API
2. ⏳ Aggiornare documentazione con dati reali
3. ⏳ Investigare discrepanze significative
4. ⏳ Documentare nuove collezioni
5. ⏳ Verificare migrazioni recenti

---

**Script di verifica:** `scripts/verify_qdrant_stats.py`  
**Endpoint API:** `https://nuzantara-qdrant.fly.dev`  
**Data verifica:** 2026-01-10
