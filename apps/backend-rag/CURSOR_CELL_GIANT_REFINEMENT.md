# Cursor Composer: Cell-Giant Architecture Refinement

## Context

Abbiamo implementato l'architettura "Cellula-Gigante" per Zantara AI. La filosofia:

> "Non combattere il Gigante. Cavalcalo. Diventa la sua coscienza."

- **GIANT** = LLM potente (oggi Gemini, domani Claude) - ragiona liberamente
- **CELL** = Nostra KB verificata - calibra, corregge, arricchisce
- **ZANTARA** = L'unica voce che l'utente vede - sintetizza tutto

**REGOLA CRITICA**: MAI menzionare modelli specifici nel codice. Usa solo `client.PRO_MODEL`, `client.FLASH_MODEL`. Il codice deve essere model-agnostic.

---

## Files da Perfezionare

```
backend/services/rag/agentic/cell_giant/
├── __init__.py
├── giant_reasoner.py      # Fase 1: Il Gigante ragiona
├── cell_conscience.py     # Fase 2: La Cellula calibra
└── zantara_synthesizer.py # Fase 3: Zantara sintetizza

backend/services/rag/agentic/orchestrator.py  # Metodo process_query_cell_giant()
backend/app/routers/agentic_rag.py            # Endpoint /query/cell-giant

docs/ARCHITECTURE_CELL_GIANT.md               # Documentazione architettura
```

---

## PASSAGGI DI PERFEZIONAMENTO

### Passaggio 1-3: KNOWN_CORRECTIONS Expansion

In `cell_conscience.py`, espandi `KNOWN_CORRECTIONS` con altri errori comuni che il Giant fa:

```python
# Aggiungi correzioni per:
- "kitas sponsor" - Il Giant spesso dimentica che serve sponsor company per KITAS
- "pt pma 100%" - Il Giant a volte dice che PMA può essere 100% straniera sempre (dipende dal settore DNI)
- "oss automatic" - Il Giant sottovaluta che OSS richiede comunque documenti e verifica
- "freelance legal" - Il Giant a volte suggerisce freelancing come opzione (illegale per stranieri)
- "tourist visa work" - Il Giant a volte non è chiaro che lavorare con visa turistico è illegale
- "bank account easy" - Il Giant sottovaluta la difficoltà di aprire conto bancario PMA
- "lease agreement" - Il Giant dimentica che serve lease agreement notarizzato per NIB
```

Formato da seguire:
```python
"error_key": {
    "trigger_patterns": [r"pattern1", r"pattern2"],
    "correction": "La correzione dettagliata...",
    "source": "Fonte verificata (legge, esperienza)",
    "severity": "critical|high|medium"
}
```

### Passaggio 4-6: PRACTICAL_INSIGHTS Expansion

Espandi `PRACTICAL_INSIGHTS` con più topic e insights reali:

```python
# Aggiungi topic:
- "visa_tourist": insights su VOA, estensioni, trappole comuni
- "property": leasing, Hak Pakai, nominee traps
- "employment": contratti PKWT/PKWTT, BPJS, THR
- "import_export": API-U, NIB requirements, customs
- "restaurant": oltre ghost kitchen - full service restaurant requirements
- "retail": KBLI per retail, limitazioni PMA, e-commerce
```

Ogni topic deve avere 4-6 insights pratici e verificati.

### Passaggio 7-9: BALI_ZERO_SERVICES Expansion

Espandi i servizi Bali Zero con pricing realistico:

```python
# Aggiungi servizi:
- "company_amendment": modifiche atto, cambio direttore, aumento capitale
- "annual_compliance": RUPS, laporan tahunan, tax filing
- "visa_extension": estensione VOA, conversione visa
- "business_license": SIUP, TDP, licenses settoriali
- "notary_services": legalizzazione, apostille, traduzione giurata
- "accounting": bookkeeping, tax reporting, audit
```

### Passaggio 10-12: Giant Reasoner Enhancement

Migliora `giant_reasoner.py`:

1. **Prompt Engineering**: Raffina `GIANT_REASONING_PROMPT` per output più strutturato
2. **Extraction Functions**: Migliora `_extract_key_points`, `_extract_warnings`, `_extract_suggestions` per catturare più informazioni
3. **Error Handling**: Aggiungi retry logic e fallback graceful
4. **Logging**: Aggiungi logging strutturato per debugging

### Passaggio 13-15: Zantara Synthesizer Enhancement

Migliora `zantara_synthesizer.py`:

1. **Persona Consistency**: Rafforza il prompt per mantenere consistenza Jaksel
2. **Correction Integration**: Migliora come le correzioni vengono integrate (non devono sembrare "patch")
3. **Length Control**: Aggiungi controllo lunghezza risposta (min/max)
4. **Fallback Quality**: Migliora `_fallback_synthesis` per casi senza LLM

### Passaggio 16-17: Streaming Support

Aggiungi supporto streaming per Cell-Giant:

1. In `orchestrator.py`, crea `stream_query_cell_giant()` che yielda eventi:
   - `{"type": "phase", "data": "giant"}` - Inizio fase Giant
   - `{"type": "phase", "data": "cell"}` - Inizio fase Cell
   - `{"type": "correction", "data": {...}}` - Correzione applicata
   - `{"type": "token", "data": "..."}` - Token risposta finale
   - `{"type": "done", "data": {...}}` - Completamento

2. In `agentic_rag.py`, aggiungi endpoint `/stream/cell-giant`

### Passaggio 18-19: Testing & Validation

Crea test suite in `tests/unit/test_cell_giant.py`:

```python
# Test cases:
- test_giant_reason_basic_query
- test_giant_reason_complex_legal_query
- test_cell_calibrate_triggers_correction
- test_cell_calibrate_no_correction_needed
- test_cell_calibrate_multiple_corrections
- test_zantara_synthesis_with_corrections
- test_zantara_synthesis_without_corrections
- test_zantara_fallback_synthesis
- test_full_pipeline_ghost_kitchen
- test_full_pipeline_pt_pma
- test_full_pipeline_kitas
```

### Passaggio 20: Documentation & Examples

Aggiorna `docs/ARCHITECTURE_CELL_GIANT.md`:

1. Aggiungi diagramma di flusso dettagliato
2. Aggiungi esempi di input/output per ogni fase
3. Documenta le correzioni note e perché esistono
4. Aggiungi sezione troubleshooting
5. Aggiungi metriche di successo misurabili

---

## Regole per Ogni Passaggio

1. **NO MODELLI SPECIFICI**: Mai scrivere "Gemini", "Claude", "GPT" nel codice
2. **ZANTARA È L'UNICA VOCE**: L'utente non deve mai vedere riferimenti interni
3. **CORREZIONI HANNO PRIORITÀ**: Se Cell dice X e Giant dice Y, vince Cell
4. **ITALIANO NEL PROMPT**: I prompt possono essere in italiano (Zantara parla italiano/inglese mix)
5. **LOGGING STRUTTURATO**: Usa `logger.info/warning/error` con prefissi emoji consistenti
6. **TYPE HINTS**: Usa type hints Python 3.10+ (`list[str]`, `dict[str, Any]`)

---

## Comando per Cursor

Per ogni passaggio, usa questo formato:

```
Passaggio N: [TITOLO]

File: [path/to/file.py]

Task: [Descrizione specifica]

Constraints:
- No model names in code
- Keep existing structure
- Add, don't replace
- Test imports after changes
```

---

## Verifica Finale

Dopo tutti i passaggi, verifica:

```bash
# 1. Imports
cd apps/backend-rag
PYTHONPATH=./backend python3 -c "from services.rag.agentic.cell_giant import *; print('OK')"

# 2. No model names leaked
grep -r "gemini\|claude\|gpt" backend/services/rag/agentic/cell_giant/ || echo "Clean!"

# 3. Run tests
pytest tests/unit/test_cell_giant.py -v
```

---

## Note Architetturali

### Perché Questa Architettura?

Il Giant (LLM) sa TUTTO vagamente. Noi sappiamo POCO precisamente.

Esempio Ghost Kitchen:
- **Giant sa**: Art. 212 esiste, KBLI 56101/56102/56104, Central Kitchen strategy
- **Giant NON sa**: 56102 è riservato UMKM, prezzo Bali Zero 45M, timeline reale 8 settimane

La Cell corregge e calibra. Zantara presenta.

### Evoluzione Biologica

- **Fase 1 (ORA)**: Parassita - Ci attacchiamo al Giant
- **Fase 2 (2025-26)**: Simbionte - Relazione mutuale
- **Fase 3 (2027+)**: Organo - Infrastruttura indispensabile

Ogni passaggio di perfezionamento ci avvicina alla Fase 2.

---

*"Non costruire un gigante. Diventa la coscienza di uno che esiste già."*
