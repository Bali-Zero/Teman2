# Test Semantic Deduplication - Guida Completa

## 🎯 Obiettivo

Verificare che la deduplicazione semantica con Qdrant funzioni correttamente prima di integrarla nella pipeline di produzione.

---

## ✅ Test 1: Verifica Struttura (Senza Chiavi)

**Test rapido che verifica solo la struttura del codice:**

```bash
cd apps/bali-intel-scraper/scripts
python test_dedup_dry_run.py
```

**Risultato atteso:** ✅ Tutti gli imports OK

---

## 🔐 Test 2: Test Completo (Richiede Chiavi)

### Opzione A: Test Locale (con .env)

1. **Aggiungi le chiavi al `.env`:**
   ```bash
   cd apps/bali-intel-scraper
   echo "QDRANT_API_KEY=your_key_here" >> .env
   echo "OPENAI_API_KEY=your_key_here" >> .env
   ```

2. **Inizializza la collezione Qdrant:**
   ```bash
   cd scripts
   python init_news_collection.py
   ```

3. **Esegui il test completo:**
   ```bash
   python test_complete_setup.py
   ```

### Opzione B: Test su Fly.io (Raccomandato)

Le chiavi sono già configurate su Fly.io. Esegui il test direttamente lì:

```bash
# Connetti al container Fly.io
fly ssh console -a nuzantara-rag

# Nel container
cd /app
python apps/bali-intel-scraper/scripts/init_news_collection.py
python apps/bali-intel-scraper/scripts/test_complete_setup.py
```

---

## 📊 Cosa Verifica il Test

1. ✅ **Collezione Qdrant:** Esiste o viene creata correttamente
2. ✅ **Embedding Generation:** OpenAI genera vettori correttamente
3. ✅ **Duplicate Detection:** Rileva duplicati esatti (URL match)
4. ✅ **Semantic Detection:** Rileva duplicati semantici (stesso concetto, parole diverse)
5. ✅ **Save Article:** Salva correttamente in Qdrant
6. ✅ **Pipeline Integration:** La pipeline usa correttamente il deduplicator

---

## 🧪 Test Cases

### Test Case 1: Articolo Nuovo
- **Input:** Articolo mai visto prima
- **Expected:** `is_duplicate = False`

### Test Case 2: Duplicato Esatto (URL)
- **Input:** Stesso URL già salvato
- **Expected:** `is_duplicate = True` (URL match)

### Test Case 3: Duplicato Semantico
- **Input:** Articolo con stesso significato ma parole diverse
- **Expected:** `is_duplicate = True` (similarity > 0.88)

### Test Case 4: Articolo Simile ma Diverso
- **Input:** Articolo su argomento correlato ma non identico
- **Expected:** `is_duplicate = False` (similarity < 0.88)

---

## 🐛 Troubleshooting

### Errore: "Collection not found"
**Soluzione:** Esegui `python init_news_collection.py` prima del test.

### Errore: "OPENAI_API_KEY not set"
**Soluzione:** Aggiungi la chiave al `.env` o esegui il test su Fly.io.

### Errore: "Qdrant connection failed"
**Soluzione:** Verifica che `QDRANT_URL` e `QDRANT_API_KEY` siano corretti.

### Test passa ma duplicati non rilevati
**Possibili cause:**
- Threshold troppo alto (0.88) → Abbassa a 0.85 per test
- Collezione vuota → Salva prima alcuni articoli
- Embedding non generato → Verifica OPENAI_API_KEY

---

## 📈 Risultati Attesi

Dopo il test completo, dovresti vedere:

```
✅ Collezione pronta
✅ Articolo unico (Score: 0.00)
✅ Articolo salvato
✅ Duplicato rilevato correttamente! (Score: 1.00)
✅ Pipeline rileva duplicato correttamente!
```

---

## 🚀 Prossimi Passi

Una volta che il test passa:

1. ✅ La pipeline userà automaticamente la deduplicazione
2. ✅ Gli articoli approvati verranno salvati in Qdrant
3. ✅ I duplicati verranno filtrati PRIMA di chiamare Claude (risparmio $$$)

**La configurazione è pronta per la produzione!**
