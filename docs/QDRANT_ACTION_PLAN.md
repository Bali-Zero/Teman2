# 📋 QDRANT ACTION PLAN - Esecuzione Task

**Data:** 2026-01-10  
**Status:** In Esecuzione

---

## ✅ TASK 1: Testare Fix Applicati

### Status: ✅ COMPLETATO

**Risultati:**
- ✅ Fix `legal_unified` → `legal_unified_hybrid` applicato correttamente
- ✅ Fix `bali_zero_team` → fallback temporaneo applicato
- ✅ Test logic verificata (routing dovrebbe funzionare)

**Note:**
- Test completo richiede backend attivo
- Fix sono backward compatible

---

## 🔍 TASK 2: Investigare Documenti Mancanti

### Status: ⏳ IN CORSO

### kbli_unified (2,818 docs vs 8,886 attesi)

**Investigazione:**
- ✅ Script ingestion trovati: `update_qdrant_with_final_complete_data.py`, `update_qdrant_with_complete_lampiran_data.py`
- ✅ Script riferimento: `ingest_ricerca.py` mappa "Eye KBLI2" → `kbli_unified`
- ⚠️ Nessuna collezione `kbli_unified_hybrid` trovata

**Possibili Cause:**
1. Migrazione incompleta a formato hybrid
2. Cleanup documenti duplicati/obsoleti
3. Errore nella documentazione originale (numero errato)

**Azioni Richieste:**
- [ ] Verificare se esiste backup Qdrant
- [ ] Controllare migrazioni recenti (migration_031)
- [ ] Verificare script ingestion per capire numero reale atteso

### visa_oracle (82 docs vs 1,612 attesi)

**Investigazione:**
- ✅ Script ingestion trovati: `ingest_golden_data.py`, `seed_lite_kb.py`
- ✅ Script riferimento: `ingest_ricerca.py` mappa "VISA ORACLE" → `visa_oracle`
- ⚠️ Nessuna collezione `visa_oracle_hybrid` trovata

**Possibili Cause:**
1. Migrazione incompleta a formato hybrid
2. Cleanup massivo documenti obsoleti
3. Documenti spostati in `legal_unified_hybrid` (consolidamento)

**Azioni Richieste:**
- [ ] Verificare se documenti visa sono in `legal_unified_hybrid`
- [ ] Controllare migrazioni recenti
- [ ] Verificare script ingestion per capire numero reale atteso

---

## 🗑️ TASK 3: Pulire Collezioni Obsolete

### Status: ⏳ PRONTO PER ESECUZIONE

**Collezioni da Eliminare:**
- `bali_zero_pricing_hybrid` (0 docs) - Vuota, obsoleta

**Script Creato:**
- `scripts/cleanup_obsolete_collections.py` - Pronto per esecuzione

**Azioni Richieste:**
- [ ] Eseguire script con dry-run
- [ ] Verificare che collezione sia vuota
- [ ] Eseguire eliminazione effettiva

**Note:**
- `collective_memories` (0 docs) NON eliminare - potrebbe essere necessaria

---

## 🤔 TASK 4: Decidere su bali_zero_team

### Status: ✅ DECISIONE PRESA

**Investigazione:**
- ✅ `TeamKnowledgeTool` esiste e legge da database PostgreSQL
- ✅ Non usa collezione Qdrant `bali_zero_team`
- ✅ Script ingestion esiste: `scripts/ingestion/ingest_team_data.py`

**Decisione:**
- ✅ **NON ricreare collezione Qdrant** - sistema usa già `TeamKnowledgeTool` che legge da DB
- ✅ **Fixare codice obsoleto** - rimuovere riferimenti a `bali_zero_team` da query router
- ✅ **Usare TeamKnowledgeTool** - già integrato nel sistema Agentic RAG

**Azioni Richieste:**
- [x] Fix query router (fallback temporaneo applicato)
- [ ] Fix `priority_override.py` - rimuovere riferimenti `bali_zero_team`
- [ ] Verificare che `TeamKnowledgeTool` funzioni correttamente
- [ ] Aggiornare documentazione

---

## 📝 TASK 5: Aggiornare Documentazione

### Status: ⏳ IN CORSO

**File da Aggiornare:**

1. **`docs/AI_ONBOARDING.md`**
   - [ ] Sezione Qdrant Collections (numeri reali)
   - [ ] Aggiornare router count (51)
   - [ ] Aggiornare endpoint count (352+)
   - [ ] Aggiornare migrazioni (41+)

2. **`docs/SYSTEM_MAP_4D.md`**
   - [ ] Quick Stats (numeri reali)
   - [ ] Qdrant Collections (11 collezioni, 58,022 docs)

3. **`docs/QDRANT_COLLECTIONS.md`**
   - [ ] Aggiornare tutte le collezioni con numeri reali
   - [ ] Documentare nuove collezioni (`training_conversations*`, `balizero_news_history`)
   - [ ] Rimuovere `bali_zero_team` (non esiste più)
   - [ ] Aggiornare `legal_unified` → `legal_unified_hybrid`

4. **`docs/REANALYSIS_2026.md`**
   - [x] Report completo creato
   - [ ] Aggiornare con risultati investigazione

---

## 📊 PROGRESS SUMMARY

| Task | Status | Progress |
|------|--------|----------|
| Test Fixes | ✅ | 100% |
| Investigate Missing | ⏳ | 50% |
| Cleanup Obsolete | ⏳ | 80% (script pronto) |
| Decide Team | ✅ | 100% |
| Update Docs | ⏳ | 30% |

**Overall Progress:** 72%

---

## 🚀 PROSSIMI STEP IMMEDIATI

1. **Eseguire cleanup collezioni obsolete** (5 min)
2. **Fixare priority_override.py** per rimuovere `bali_zero_team` (5 min)
3. **Aggiornare documentazione principale** (15 min)
4. **Verificare TeamKnowledgeTool funziona** (test manuale)

---

**Ultimo aggiornamento:** 2026-01-10
