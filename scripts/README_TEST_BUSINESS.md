# Script Test Business Questions

Script Python per testare automaticamente 40 domande business su Zantara AI e generare report dettagliato.

## Prerequisiti

```bash
pip install aiohttp
```

Oppure se usi requirements.txt del progetto:

```bash
cd apps/backend-rag
pip install -r requirements.txt
```

## Configurazione

### Opzione 1: Variabili d'ambiente (consigliato)

```bash
export NUZANTARA_API_URL="https://nuzantara-rag.fly.dev"
export NUZANTARA_API_KEY="your-api-key-here"  # Opzionale ma consigliato
export TEST_USER_EMAIL="test@balizero.com"
export AUTH_TOKEN="your-bearer-token"  # Opzionale
```

### Opzione 2: Modifica script direttamente

Apri `scripts/test_business_questions.py` e modifica le variabili in cima:

```python
BACKEND_URL = "https://nuzantara-rag.fly.dev"
API_KEY = "your-api-key"
TEST_USER_EMAIL = "test@balizero.com"
```

## Esecuzione

```bash
cd /Users/antonellosiano/Desktop/nuzantara
python scripts/test_business_questions.py
```

## Output

Lo script genera:

1. **JSON Results**: `test_results/business_test_results_YYYYMMDD_HHMMSS.json`
   - Dati strutturati per analisi programmatica

2. **Markdown Report**: `test_results/business_test_report_YYYYMMDD_HHMMSS.md`
   - Report dettagliato con tutte le risposte
   - Statistiche per categoria
   - Metriche di performance

## Domande Testate

- **Immigrazione & Visa**: 8 domande (IT, EN, ID, ES)
- **Tasse & Perpajakan**: 8 domande (IT, EN, ID, ES)
- **KBLI & Business Setup**: 10 domande (IT, EN, ID, ES)
- **Legal & Compliance**: 8 domande (IT, EN, ID)
- **Property & Real Estate**: 4 domande (IT, EN)
- **General Business**: 2 domande (IT, EN)
- **Edge Cases**: 5 domande bonus

**Totale**: 46 domande

## Metriche Raccolte

Per ogni domanda:

- ✅ Success/Failure
- ⏱️ Tempo di risposta
- 🎨 Tone Jaksel applicato (da analisi response)
- 🌍 Lingua rilevata
- 🤖 Model usato (gemma-9b-jaksel / gemini-fallback)
- 📝 Risposta completa

## Troubleshooting

### Timeout Error

Se vedi molti timeout, aumenta il timeout nello script:

```python
timeout=aiohttp.ClientTimeout(total=180)  # 3 minuti
```

### Authentication Error

Verifica che `NUZANTARA_API_KEY` sia configurato correttamente o che `AUTH_TOKEN` sia valido.

### Connection Error

Verifica che `BACKEND_URL` sia corretto e che il backend sia raggiungibile:

```bash
curl https://nuzantara-rag.fly.dev/health
```

## Note

- Lo script fa una pausa di 1 secondo tra ogni domanda per non sovraccaricare il server
- Il test completo richiede ~15-20 minuti (46 domande × ~20s medio)
- Le risposte sono salvate complete nel report per analisi manuale




















