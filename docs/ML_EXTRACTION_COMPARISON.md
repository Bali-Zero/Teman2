# ML vs Pattern Extraction - Confronto Risultati

## Test Eseguiti

### kbli_unified

**Pattern Extraction:**
- Campi estratti: 3
- kbli_code: 12345
- kbli_description: "KBLI Code: 12345" (raw)
- risk_level: MEDIUM

**ML Extraction:**
- Campi estratti: 7
- kbli_code: 12345
- kbli_description: "Construction of residential buildings" (pulito!)
- category: None
- Altri campi strutturati

**Vantaggio ML**: Descrizione più pulita e comprensibile, più campi estratti.

### visa_oracle

**Pattern Extraction:**
- Campi estratti: 4
- visa_type: C7
- entry_type: single
- duration: 3 weeks
- fee_usd: 100.0

**ML Extraction:**
- Bloccato da safety filters (contenuto "visa" può triggerare filtri)
- Fallback a pattern

**Nota**: Safety filters possono bloccare contenuti legali/immigrazione. Pattern più affidabile per questo caso.

## Raccomandazioni

### Usa Pattern quando:
- ✅ Contenuti standardizzati (visa, codici)
- ✅ Performance critica
- ✅ Budget limitato
- ✅ Safety filters potrebbero bloccare

### Usa ML quando:
- ✅ Descrizioni testuali complesse
- ✅ Struttura variabile
- ✅ Necessità alta accuratezza
- ✅ Contenuti non sensibili

### Usa Hybrid quando:
- ✅ Vuoi best of both worlds
- ✅ Pattern come fallback sicuro
- ✅ ML per migliorare accuratezza

## Costi

- **Pattern**: Gratis
- **ML**: ~$0.0000675 per documento
- **25k docs**: ~$1.72 totale

## Conclusione

**Pattern è sufficiente per la maggior parte dei casi** (70-100% success rate).

**ML aggiunge valore per**:
- Descrizioni più pulite
- Campi aggiuntivi
- Casi edge complessi

**Strategia ottimale**: Pattern-first con ML per documenti dove Pattern fallisce o produce risultati incompleti.
