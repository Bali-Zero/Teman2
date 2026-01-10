# ✅ KNOWLEDGE GRAPH AUTO-BUILD - Raccomandazione Finale

**Data:** 2026-01-10  
**Domanda:** È fattibile e best practice rendere il build automatico per popolare il KG?

---

## ✅ RISPOSTA: SÌ, Fattibile E Best Practice

**Conclusione:** ✅ **Sì, è fattibile E best practice**, con implementazione incrementale intelligente.

---

## 🎯 RACCOMANDAZIONE FINALE

### Strategia Consigliata: Incremental Automatico

**Approccio:**
- ✅ **Build incrementale automatico** ogni 6-12 ore
- ✅ **Solo chunk nuovi/modificati** (non full rebuild)
- ✅ **Collezioni prioritarie** (alta priorità)
- ✅ **Gemini per estrazione** (più economico)
- ✅ **Error handling robusto**

---

## 💰 ANALISI COSTI

### Costo Full Build (58k docs)

**Claude Sonnet 4:**
- Costo/chunk: ~$0.0021
- Totale: ~$122 (full build)
- Tempo: ~19 ore

**Gemini (raccomandato):**
- Costo/chunk: ~$0.0005
- Totale: ~$29 (full build)
- Tempo: ~19 ore

### Costo Incremental (solo nuovi)

**Assumendo 10% nuovi chunk/giorno:**
- Chunk nuovi: ~5,800/giorno
- Costo/giorno: ~$2.90 (Gemini)
- Costo/mese: ~$87

**Assumendo 5% nuovi chunk/giorno:**
- Chunk nuovi: ~2,900/giorno
- Costo/giorno: ~$1.45 (Gemini)
- Costo/mese: ~$43.50

**Raccomandazione:** ✅ **Incremental è 10-20x più economico**

---

## ⏱️ ANALISI PERFORMANCE

### Tempi Stimati

**Full Build (58k docs):**
- Batch size: 10, Concurrent: 5
- Tempo: ~19 ore
- Throughput: ~50 chunk/minuto

**Incremental (5,800 nuovi chunk):**
- Tempo: ~2 ore
- Throughput: ~50 chunk/minuto

**Incremental (2,900 nuovi chunk):**
- Tempo: ~1 ora
- Throughput: ~50 chunk/minuto

**Ottimizzazioni:**
- Batch size: 20 → Tempo: ~0.5-1 ora
- Concurrent: 10 → Tempo: ~0.25-0.5 ore

---

## 🛠️ IMPLEMENTAZIONE

### Script Esistente ✅

**File:** `apps/backend-rag/scripts/kg_incremental_extraction.py`

**Funzionalità:**
- ✅ Traccia chunk processati (`get_processed_chunk_ids()`)
- ✅ Filtra solo chunk nuovi
- ✅ Processa in batch paralleli
- ✅ Usa Gemini (economico)
- ✅ Error handling con retry

**Metodo Chiave:**
```python
async def get_processed_chunk_ids(self) -> set:
    """Get all chunk IDs already in KG."""
    query = "SELECT DISTINCT unnest(source_chunk_ids) as chunk_id FROM kg_nodes WHERE source_chunk_ids IS NOT NULL"
    rows = await self.db_pool.fetch(query)
    return set(r["chunk_id"] for r in rows if r["chunk_id"])
```

**Utilizzo:**
```python
# Filtra solo chunk non processati
unprocessed = [c for c in all_chunks if c["id"] not in processed_ids]
```

---

### Modifiche Necessarie al Scheduler

**File:** `apps/backend-rag/backend/services/misc/autonomous_scheduler.py`

**Modifica Task:**
```python
async def run_knowledge_graph_builder():
    """Build knowledge graph incrementally"""
    # 1. Schema
    await graph_builder.init_graph_schema()
    
    # 2. Conversazioni (sempre)
    await graph_builder.build_graph_from_all_conversations(days_back=7)
    
    # 3. Qdrant Collections (incremental)
    from scripts.kg_incremental_extraction import KGIncrementalExtractor
    
    extractor = KGIncrementalExtractor(
        db_pool=db_pool,
        qdrant_url=settings.qdrant_url,
        qdrant_api_key=settings.qdrant_api_key,
        gemini_client=gemini_client
    )
    
    # Solo collezioni alta priorità
    high_priority = [
        "legal_unified_hybrid",
        "kbli_unified",
        "tax_genius_hybrid"
    ]
    
    await extractor.run(
        collections=high_priority,
        limit=None,  # Tutti i nuovi chunk
        dry_run=False
    )
```

**Frequenza:**
- Ogni 6-12 ore (raccomandato)
- O ogni 4 ore (allineato con altri agent)

---

## 📊 BEST PRACTICES IDENTIFICATE

### 1. Incremental Updates ✅

**Perché:**
- ✅ Costo 10-20x inferiore
- ✅ Tempo 10-20x inferiore
- ✅ Aggiornamento continuo
- ✅ Evita duplicati

**Come:**
- Usa `source_chunk_ids` per tracking
- Filtra chunk già processati
- Processa solo nuovi/modificati

---

### 2. Collezioni Prioritarie ✅

**Alta Priorità (ogni 6-12h):**
- `legal_unified_hybrid` (47,959 docs)
- `kbli_unified` (2,818 docs)
- `tax_genius_hybrid` (332 docs)

**Media Priorità (ogni 24h):**
- `visa_oracle` (82 docs)
- `bali_zero_pricing` (70 docs)

**Bassa Priorità (manuale):**
- `training_conversations_hybrid` (statico)
- `balizero_news_history` (piccolo)

---

### 3. Gemini per Estrazione ✅

**Perché:**
- ✅ 4x più economico di Claude
- ✅ Performance simili per estrazione
- ✅ Rate limit più alti (60+ RPM)

**Configurazione:**
```python
extractor_type: str = "gemini"  # Invece di "claude"
model: str = "gemini-1.5-flash"  # Economico e veloce
```

---

### 4. Error Handling ✅

**Best Practices:**
- ✅ Retry con exponential backoff
- ✅ Continue on error (non bloccare tutto)
- ✅ Log dettagliato
- ✅ Alert su errori critici

**Implementazione:**
```python
try:
    await extractor.run(collections=high_priority)
except Exception as e:
    logger.error(f"KG extraction failed: {e}")
    # Alert admin ma non bloccare scheduler
```

---

### 5. Monitoring e Alerting ✅

**Metriche da Tracciare:**
- Chunk processati per run
- Entità/relazioni estratte
- Costo LLM per run
- Tempo esecuzione
- Errori e retry

**Alert:**
- Costo giornaliero > threshold
- Errori consecutivi > 3
- Tempo esecuzione > 2 ore

---

## 🚀 PIANO IMPLEMENTAZIONE

### Step 1: Verificare Script Incremental ✅

**File:** `apps/backend-rag/scripts/kg_incremental_extraction.py`

**Status:** ✅ Già esistente e funzionante

**Verifiche:**
- ✅ Traccia chunk processati
- ✅ Filtra chunk nuovi
- ✅ Usa Gemini (economico)
- ✅ Error handling

---

### Step 2: Modificare Scheduler

**File:** `apps/backend-rag/backend/services/misc/autonomous_scheduler.py`

**Modifiche:**
1. Importare `KGIncrementalExtractor`
2. Modificare `run_knowledge_graph_builder()`
3. Aggiungere estrazione incrementale Qdrant
4. Configurare collezioni prioritarie

**Frequenza:**
- Ogni 6-12 ore (raccomandato)
- O ogni 4 ore (allineato con altri agent)

---

### Step 3: Configurazione

**Variabili Ambiente:**
- `GEMINI_API_KEY` - Per estrazione economica
- `KG_AUTO_BUILD_ENABLED` - Enable/disable
- `KG_COLLECTIONS_PRIORITY` - Collezioni da processare

**Configurazione Pipeline:**
```python
config = PipelineConfig(
    extractor_type="gemini",  # Economico
    batch_size=20,  # Ottimale
    max_concurrent=5,  # Bilanciato
    use_coreference=False,  # Risparmia costo
    min_confidence=0.6
)
```

---

### Step 4: Testing

**Test Incremental:**
1. Eseguire dry-run
2. Verificare chunk filtrati correttamente
3. Testare estrazione su sample
4. Verificare persistenza

**Test Scheduler:**
1. Verificare task eseguito
2. Monitorare costi
3. Verificare errori
4. Testare retry

---

## 📈 BENEFICI ATTESI

### Benefici Tecnici

**✅ Knowledge Graph Aggiornato:**
- Entità/relazioni sempre aggiornate
- Query più accurate
- Migliore comprensione contesto

**✅ Performance:**
- Query strutturate più veloci
- Context più ricco per AI
- Relazioni validate

### Benefici Business

**✅ Migliori Risposte AI:**
- Context più ricco
- Relazioni strutturate
- Entità validate

**✅ Manutenzione Automatica:**
- Nessun intervento manuale
- Aggiornamento continuo
- Sistema self-healing

---

## ⚠️ RISCHI E MITIGAZIONI

### Rischio 1: Costo LLM

**Mitigazione:**
- ✅ Incremental (solo nuovi chunk)
- ✅ Gemini invece di Claude
- ✅ Batch size ottimale
- ✅ Monitoring costi

### Rischio 2: Performance

**Mitigazione:**
- ✅ Processare durante ore non di picco
- ✅ Batch processing parallelo
- ✅ Timeout e retry
- ✅ Background task

### Rischio 3: Errori

**Mitigazione:**
- ✅ Error handling robusto
- ✅ Retry con backoff
- ✅ Continue on error
- ✅ Alert e monitoring

---

## ✅ CONCLUSIONE

### È Fattibile? ✅ SÌ

**Motivi:**
- ✅ Componenti già disponibili
- ✅ Script incremental esistente
- ✅ Scheduler già configurato
- ✅ Tracking chunk implementato

### È Best Practice? ✅ SÌ

**Motivi:**
- ✅ Incremental updates standard
- ✅ Aggiornamento continuo
- ✅ Costi controllati
- ✅ Performance ottimale

### Raccomandazione Finale

**✅ IMPLEMENTARE build automatico incrementale:**

1. **Frequenza:** Ogni 6-12 ore
2. **Strategia:** Incremental (solo nuovi chunk)
3. **Collezioni:** Alta priorità solo
4. **Modello:** Gemini (economico)
5. **Costo stimato:** ~$1.5-3/giorno (~$45-90/mese)

**Benefici:**
- ✅ Knowledge Graph sempre aggiornato
- ✅ Costi controllati
- ✅ Performance ottimale
- ✅ Manutenzione automatica

---

**Documentazione creata:** 2026-01-10  
**Raccomandazione:** ✅ **IMPLEMENTARE**
