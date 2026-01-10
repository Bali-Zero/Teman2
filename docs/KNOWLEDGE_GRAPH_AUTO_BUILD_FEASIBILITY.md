# 🤔 KNOWLEDGE GRAPH AUTO-BUILD - Fattibilità e Best Practices

**Data:** 2026-01-10  
**Domanda:** È fattibile e best practice rendere il build automatico per popolare il KG?

---

## ✅ RISPOSTA BREVE

**Sì, è fattibile E best practice**, ma con alcune considerazioni importanti:

- ✅ **Fattibile:** Tecnicamente possibile
- ✅ **Best Practice:** Aggiornamenti incrementali sono standard
- ⚠️ **Considerazioni:** Costo LLM, performance, strategia incrementale

---

## 📊 ANALISI FATTIBILITÀ

### 1. Fattibilità Tecnica ✅

**Già Implementato:**
- ✅ `KGPipeline.run_from_qdrant()` - Processa collezioni Qdrant
- ✅ `build_graph_from_collection()` - Processa singola collezione
- ✅ `source_chunk_ids` - Tracking chunk processati
- ✅ Batch processing con controllo concorrenza
- ✅ Coreference resolution e deduplicazione

**Cosa Serve:**
- ⚠️ Modificare scheduler per chiamare pipeline
- ⚠️ Implementare incremental updates
- ⚠️ Gestire errori e retry

**Difficoltà:** 🟢 **Bassa** - Componenti già disponibili

---

### 2. Costo LLM ⚠️

**Stima Costi:**

**Per 58k documenti:**
- **Claude Sonnet 4:** ~$0.003 per 1K tokens input, ~$0.015 per 1K tokens output
- **Media chunk:** ~1,500 caratteri (~400 tokens)
- **Estrazione per chunk:** ~500 tokens input + 200 tokens output = 700 tokens
- **Costo per chunk:** ~$0.0021 (Claude Sonnet 4)

**Totale 58k docs:**
- **Costo full build:** ~$122 (58,000 × $0.0021)
- **Costo incrementale (10% nuovi):** ~$12 per run

**Gemini (alternativa più economica):**
- **Costo per chunk:** ~$0.0005
- **Totale 58k docs:** ~$29 full build
- **Incrementale:** ~$3 per run

**Raccomandazione:**
- ✅ Usare Gemini per estrazione (più economico)
- ✅ Processare solo chunk nuovi/modificati
- ✅ Batch size ottimale: 10-20 chunk

---

### 3. Performance ⏱️

**Tempi Stimati:**

**Per 58k documenti:**
- **Batch size:** 10 chunk
- **Max concurrent:** 5 batch
- **Throughput:** ~50 chunk/minuto
- **Tempo totale:** ~19 ore (full build)

**Ottimizzazioni:**
- ✅ Batch size maggiore: 20 chunk → ~9.5 ore
- ✅ Max concurrent maggiore: 10 batch → ~4.7 ore
- ✅ Incremental: Solo nuovi → minuti/ore

**Raccomandazione:**
- ✅ Incremental updates (solo nuovi chunk)
- ✅ Processare durante ore non di picco
- ✅ Background task con priorità bassa

---

## 🎯 BEST PRACTICES

### 1. Incremental Updates ✅

**Strategia:**
- ✅ Tracciare chunk processati (`source_chunk_ids`)
- ✅ Processare solo chunk nuovi/modificati
- ✅ Evitare rebuild completo

**Implementazione:**
```python
# Verificare chunk già processati
processed_chunks = await get_processed_chunk_ids(collection_name)
new_chunks = await get_new_chunks(collection_name, exclude=processed_chunks)

# Processare solo nuovi
await pipeline.run_from_qdrant(
    collection_name=collection_name,
    chunk_ids=new_chunks,  # Solo nuovi
    persist=True
)
```

**Vantaggi:**
- ✅ Costo ridotto (solo nuovi chunk)
- ✅ Tempo ridotto (minuti invece di ore)
- ✅ Aggiornamento continuo

---

### 2. Frequenza Ottimale ⏰

**Raccomandazioni:**

**Opzione A: Incremental Quotidiano**
- ✅ Ogni 24 ore
- ✅ Processa solo nuovi chunk
- ✅ Costo: ~$3-12/giorno
- ✅ Tempo: ~30-60 minuti

**Opzione B: Incremental Ogni 6 Ore**
- ✅ Più frequente
- ✅ Costo: ~$1.5-6 ogni 6h
- ✅ Tempo: ~15-30 minuti

**Opzione C: Incremental Ogni 4 Ore** (come scheduler attuale)
- ✅ Allineato con altri agent
- ✅ Costo: ~$1-4 ogni 4h
- ✅ Tempo: ~10-20 minuti

**Raccomandazione:**
- ✅ **Incremental ogni 6-12 ore** (bilanciamento costo/frequenza)
- ✅ Processare durante ore non di picco (notte)

---

### 3. Collezioni Prioritarie 🎯

**Non tutte le collezioni hanno stessa priorità:**

**Alta Priorità (aggiornare spesso):**
- `legal_unified_hybrid` (47,959 docs) - Leggi cambiano
- `kbli_unified` (2,818 docs) - Codici business importanti
- `tax_genius_hybrid` (332 docs) - Regolamenti fiscali

**Media Priorità (aggiornare meno spesso):**
- `visa_oracle` (82 docs) - Cambiano raramente
- `bali_zero_pricing` (70 docs) - Aggiornato manualmente

**Bassa Priorità (una volta):**
- `training_conversations_hybrid` (3,525 docs) - Statico
- `balizero_news_history` (6 docs) - Piccolo

**Strategia:**
```python
# Alta priorità: ogni 6h
high_priority = ["legal_unified_hybrid", "kbli_unified", "tax_genius_hybrid"]

# Media priorità: ogni 24h
medium_priority = ["visa_oracle", "bali_zero_pricing"]

# Bassa priorità: una volta (o manuale)
low_priority = ["training_conversations_hybrid"]
```

---

### 4. Error Handling e Retry 🔄

**Best Practices:**
- ✅ Retry con exponential backoff
- ✅ Log errori per debugging
- ✅ Continue on error (non bloccare tutto)
- ✅ Alert su errori critici

**Implementazione:**
```python
async def safe_extract(collection_name: str, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            await pipeline.run_from_qdrant(collection_name)
            return
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Failed after {max_retries} attempts: {e}")
                # Alert admin
            else:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
```

---

## 🚀 IMPLEMENTAZIONE RACCOMANDATA

### Strategia Ibrida

**1. Build Incremental Automatico (ogni 6-12h)**
- Processa solo chunk nuovi/modificati
- Collezioni alta priorità
- Costo: ~$3-12/giorno
- Tempo: ~30-60 minuti

**2. Build Full Manuale (quando necessario)**
- Rebuild completo per collezioni
- Quando ci sono aggiornamenti massivi
- Costo: ~$29-122 (full)
- Tempo: ~5-20 ore

**3. Build Conversazioni Automatico (ogni 4h)**
- Processa conversazioni utenti
- Entità/relazioni reali
- Costo: Basso (poche conversazioni)
- Tempo: ~5-10 minuti

---

## 💡 PROPOSTA IMPLEMENTAZIONE

### Modificare AutonomousScheduler

```python
async def run_knowledge_graph_builder():
    """Build knowledge graph incrementally"""
    # 1. Schema
    await graph_builder.init_graph_schema()
    
    # 2. Conversazioni (sempre)
    await graph_builder.build_graph_from_all_conversations(days_back=7)
    
    # 3. Qdrant Collections (incremental, solo alta priorità)
    high_priority_collections = [
        "legal_unified_hybrid",
        "kbli_unified", 
        "tax_genius_hybrid"
    ]
    
    for collection in high_priority_collections:
        try:
            # Incremental: solo nuovi chunk
            await pipeline.run_incremental(
                collection_name=collection,
                since_last_run=True
            )
        except Exception as e:
            logger.error(f"Failed to process {collection}: {e}")
            # Continue with other collections
```

### Nuovo Metodo Incremental

```python
async def run_incremental(
    self,
    collection_name: str,
    since_last_run: bool = True,
    days_back: int = 1
):
    """Process only new/modified chunks"""
    # Get processed chunk IDs
    processed = await self.get_processed_chunk_ids(collection_name)
    
    # Get new chunks (since last run or days_back)
    new_chunks = await self.get_new_chunks(
        collection_name,
        exclude=processed,
        since=datetime.now() - timedelta(days=days_back) if since_last_run else None
    )
    
    if not new_chunks:
        logger.info(f"No new chunks in {collection_name}")
        return
    
    # Process only new chunks
    await self.run_from_chunks(
        collection_name=collection_name,
        chunk_ids=new_chunks,
        persist=True
    )
```

---

## 📊 COSTI E BENEFICI

### Costi

**Incremental Automatico (ogni 6h):**
- Costo/giorno: ~$6-24 (Gemini-Claude)
- Costo/mese: ~$180-720
- Tempo/giorno: ~1-2 ore

**Full Build Manuale:**
- Costo/run: ~$29-122
- Quando necessario: ~1-4 volte/mese
- Costo/mese: ~$29-488

### Benefici

**✅ Knowledge Graph Aggiornato:**
- Entità/relazioni sempre aggiornate
- Query più accurate
- Migliore comprensione contesto

**✅ Migliori Risposte AI:**
- Context più ricco
- Relazioni strutturate
- Entità validate

**✅ Manutenzione Automatica:**
- Nessun intervento manuale
- Aggiornamento continuo
- Sistema self-healing

---

## ✅ RACCOMANDAZIONE FINALE

### Sì, è Fattibile E Best Practice ✅

**Implementazione Consigliata:**

1. **Build Incremental Automatico**
   - Frequenza: Ogni 6-12 ore
   - Collezioni: Alta priorità solo
   - Strategia: Solo chunk nuovi
   - Costo: ~$6-24/giorno

2. **Build Conversazioni Automatico**
   - Frequenza: Ogni 4 ore (già schedulato)
   - Costo: Basso
   - Beneficio: Entità reali

3. **Build Full Manuale**
   - Quando: Aggiornamenti massivi
   - Frequenza: 1-4 volte/mese
   - Costo: ~$29-122/run

**Best Practices:**
- ✅ Incremental updates (non full rebuild)
- ✅ Processare durante ore non di picco
- ✅ Error handling robusto
- ✅ Monitoring e alerting
- ✅ Costi controllati (Gemini per estrazione)

---

## 🎯 PROSSIMI STEP

1. ✅ Implementare `run_incremental()` method
2. ✅ Modificare scheduler per chiamare incremental
3. ✅ Aggiungere tracking chunk processati
4. ✅ Configurare collezioni prioritarie
5. ✅ Monitoring costi e performance

---

**Conclusione:** ✅ **Fattibile e Best Practice** con implementazione incrementale intelligente!

---

**Documentazione creata:** 2026-01-10
