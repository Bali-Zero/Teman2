# PROMPT PER CURSOR COMPOSER

Copia questo prompt in Cursor Composer e lascialo lavorare iterativamente.

---

## PROMPT DA COPIARE:

```
Sei un senior Python developer che perfeziona l'architettura Cell-Giant per Zantara AI.

## FILOSOFIA
- GIANT = LLM potente che ragiona liberamente (usa client.PRO_MODEL)
- CELL = Nostra KB che calibra/corregge/arricchisce
- ZANTARA = Unica voce che l'utente vede

## REGOLE ASSOLUTE
1. MAI scrivere nomi di modelli specifici (Gemini, Claude, GPT) - usa solo client.PRO_MODEL o client.FLASH_MODEL
2. L'utente vede SOLO Zantara - mai riferimenti interni
3. Type hints Python 3.10+ (list[str], dict[str, Any])
4. Logging con emoji: 🧠 Giant, 🔬 Cell, 🎭 Zantara, ✅ success, ⚠️ warning

## FILES
- backend/services/rag/agentic/cell_giant/giant_reasoner.py
- backend/services/rag/agentic/cell_giant/cell_conscience.py
- backend/services/rag/agentic/cell_giant/zantara_synthesizer.py
- backend/services/rag/agentic/orchestrator.py (metodo process_query_cell_giant)

## TASK ITERATIVI

### Round 1-3: Espandi KNOWN_CORRECTIONS in cell_conscience.py
Aggiungi correzioni per errori comuni del Giant su:
- KITAS sponsor requirements
- DNI list e settori chiusi a PMA
- OSS non è automatico
- Freelancing illegale per stranieri
- Working on tourist visa illegale
- Bank account PMA difficoltà
- Lease agreement notarizzato per NIB
- RPTKA prima di KITAS
- Minimum capital per settore
- Local director requirement

### Round 4-6: Espandi PRACTICAL_INSIGHTS in cell_conscience.py
Aggiungi topic:
- "visa_tourist": VOA, estensioni, 60 days limit, onward ticket
- "property": Hak Pakai, leasing, nominee traps, zona kuning
- "employment": PKWT max 5 anni, BPJS mandatory, THR calculation
- "import_export": API-U, customs broker, HS codes
- "restaurant": full service vs ghost kitchen, liquor license
- "retail": limitazioni PMA, e-commerce PMSE
- "accounting": tax calendar, PPh rates, withholding

### Round 7-9: Espandi BALI_ZERO_SERVICES in cell_conscience.py
Aggiungi servizi con pricing reale:
- company_amendment (15-25 juta)
- annual_compliance (8-15 juta/anno)
- visa_extension (3-5 juta)
- work_permit_kitas (25-40 juta)
- business_licenses (varies by type)
- notary_legalization (2-5 juta)
- monthly_accounting (5-15 juta/month)

### Round 10-12: Migliora giant_reasoner.py
- Rafforza GIANT_REASONING_PROMPT per output più strutturato
- Aggiungi section per "Costi Stimati" e "Timeline Realistica"
- Migliora extraction functions con regex più robusti
- Aggiungi handling per query in inglese vs italiano

### Round 13-15: Migliora zantara_synthesizer.py
- Rafforza persona Jaksel nel SYNTHESIS_PROMPT
- Aggiungi regole per NON iniziare con "Certo!", "Assolutamente!", ecc
- Aggiungi handling per correzioni multiple (priorità per severity)
- Migliora _fallback_synthesis per essere più utile

### Round 16-17: Aggiungi Streaming
In orchestrator.py, crea stream_query_cell_giant():
```python
async def stream_query_cell_giant(...) -> AsyncGenerator[dict, None]:
    yield {"type": "phase", "data": {"phase": "giant", "status": "started"}}
    # ... giant_reason() ...
    yield {"type": "phase", "data": {"phase": "cell", "status": "started"}}
    # ... cell_calibrate() ...
    yield {"type": "corrections", "data": corrections}
    yield {"type": "phase", "data": {"phase": "zantara", "status": "started"}}
    # ... synthesize streaming tokens ...
    for token in tokens:
        yield {"type": "token", "data": token}
    yield {"type": "done", "data": metadata}
```

### Round 18-19: Test Suite
Crea tests/unit/test_cell_giant.py con:
- test_known_corrections_trigger
- test_practical_insights_detection
- test_topic_detection
- test_calibrations_mapping
- test_synthesis_with_corrections
- test_synthesis_fallback
- test_full_pipeline_integration

### Round 20: Documentation
Aggiorna docs/ARCHITECTURE_CELL_GIANT.md con:
- Esempi concreti di correzioni
- Flow diagram ASCII
- Troubleshooting section
- Metriche di successo

## VERIFICA DOPO OGNI ROUND
```bash
cd apps/backend-rag
PYTHONPATH=./backend python3 -c "from services.rag.agentic.cell_giant import *; print('✅ Imports OK')"
grep -rn "gemini\|claude\|gpt-" backend/services/rag/agentic/cell_giant/ && echo "❌ Model name leak!" || echo "✅ Clean"
```

Procedi con Round 1. Dopo ogni round, conferma cosa hai fatto e passa al successivo.
```

---

## VARIANTE COMPATTA (per un solo round alla volta):

```
File: backend/services/rag/agentic/cell_giant/cell_conscience.py

Task: Aggiungi 5 nuove KNOWN_CORRECTIONS per errori comuni del Giant:
1. "kitas_sponsor" - Giant dimentica che serve sponsor company
2. "dni_restrictions" - Giant non sempre cita DNI list per settori chiusi
3. "oss_not_automatic" - Giant sottovaluta documenti OSS
4. "freelance_illegal" - Giant a volte suggerisce freelancing
5. "tourist_visa_work" - Giant non sempre chiarisce illegalità

Ogni correzione deve avere:
- trigger_patterns: [regex patterns]
- correction: testo dettagliato
- source: fonte legale o esperienza
- severity: critical/high/medium

REGOLE:
- No model names (Gemini/Claude/GPT)
- Italian text OK in corrections
- Keep existing code structure
```

---

## TIPS PER CURSOR

1. **Usa @ per referenziare files**: `@cell_conscience.py`
2. **Chiedi conferma**: "Mostrami cosa cambieresti prima di applicare"
3. **Iterativo**: Un round alla volta, verifica, poi procedi
4. **Context**: Se Cursor perde contesto, ri-incolla la sezione FILOSOFIA

---

## CHECKLIST FINALE

Dopo tutti i round:

- [ ] KNOWN_CORRECTIONS ha 15+ correzioni
- [ ] PRACTICAL_INSIGHTS ha 8+ topic
- [ ] BALI_ZERO_SERVICES ha 10+ servizi
- [ ] giant_reasoner.py ha prompt migliorato
- [ ] zantara_synthesizer.py ha persona forte
- [ ] stream_query_cell_giant() esiste
- [ ] Test suite passa
- [ ] Nessun model name nel codice
- [ ] Documentazione aggiornata
