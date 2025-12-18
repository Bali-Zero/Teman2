# 🔐 Perché Google Blocca Alcune Chiamate API ma Non Altre?

## 🤔 Il Problema

**Situazione:**
- ✅ Test diretto: `curl "https://generativelanguage.googleapis.com/v1/models?key=..."` → **FUNZIONA**
- ❌ Backend webapp: Chiamate `generate_content` → **403 Leaked**

**Domanda:** Perché Google blocca alcune chiamate ma non altre?

---

## 🎯 Spiegazione Tecnica

### Google Applica **Restrizioni Graduali**

Google **NON blocca immediatamente** tutte le chiamate quando rileva un'API key "leaked". Invece:

1. **Chiamate Semplici (READ-ONLY):** ✅ Continuano a funzionare
   - `GET /v1/models` (listare modelli)
   - `GET /v1/{model}` (info modello)
   - Operazioni di sola lettura

2. **Chiamate Complesse (WRITE/GENERATE):** ❌ Vengono bloccate
   - `POST /v1/{model}:generateContent` (generare contenuto)
   - `POST /v1/{model}:streamGenerateContent` (streaming)
   - Operazioni che consumano risorse/quota

### Perché Questa Strategia?

Google usa questa strategia per:

1. **Proteggere il tuo account** senza bloccarlo completamente
2. **Permettere verifiche** (puoi ancora controllare se l'API key funziona)
3. **Prevenire abusi** (blocca solo operazioni costose)
4. **Darti tempo** per rigenerare l'API key senza perdere accesso totale

---

## 🔍 Cosa Significa "Bloccata per Chiamate Complesse"?

### Chiamate Semplici (✅ Funzionano)

```bash
# Lista modelli - FUNZIONA
curl "https://generativelanguage.googleapis.com/v1/models?key=..."

# Info modello - FUNZIONA  
curl "https://generativelanguage.googleapis.com/v1/models/gemini-2.5-pro?key=..."
```

**Perché funzionano:**
- Non consumano quota significativa
- Non generano contenuto
- Sono operazioni di sola lettura
- Google le permette per verifiche

### Chiamate Complesse (❌ Bloccate)

```python
# Generare contenuto - BLOCCATO
model.generate_content("Ciao, spiegami...")

# Streaming - BLOCCATO
model.generate_content_stream("Domanda...")
```

**Perché sono bloccate:**
- Consumano quota/token
- Generano contenuto (costo per Google)
- Possono essere abusate
- Google le blocca per sicurezza

---

## 🚨 Perché Google Rileva l'API Key come "Leaked"?

### Possibili Cause

1. **Esposizione Pubblica**
   - API key trovata in repository pubblici
   - Screenshot condivisi con API key visibile
   - Log esposti pubblicamente
   - Email/chat con API key visibile

2. **Pattern di Uso Sospetto**
   - Troppe richieste da IP diversi
   - Uso anomalo rispetto al normale pattern
   - Richieste da location sospette

3. **Scanner Automatici**
   - Google usa scanner che cercano API keys nei repository pubblici
   - Anche se il repo è privato ora, se è stato pubblico prima, potrebbe essere stato rilevato

4. **Rate Limiting Aggressivo**
   - Troppe richieste in breve tempo
   - Google potrebbe interpretare come uso non autorizzato

---

## 🔬 Test Pratico: Verifica Diretta

### Test 1: Chiamata Semplice (✅ Dovrebbe Funzionare)

```bash
curl "https://generativelanguage.googleapis.com/v1/models?key=AIza_REDACTED"
```

**Risultato Atteso:** ✅ Lista modelli

### Test 2: Chiamata Complessa (❌ Dovrebbe Essere Bloccata)

```bash
curl -X POST \
  "https://generativelanguage.googleapis.com/v1/models/gemini-2.5-pro:generateContent?key=AIza_REDACTED" \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [{
      "parts": [{
        "text": "Ciao, spiegami cosa sono i requisiti per aprire una PT PMA"
      }]
    }]
  }'
```

**Risultato Atteso:** ❌ `403 Your API key was reported as leaked`

---

## 💡 Perché il Test Diretto Funziona ma il Backend No?

### Differenze tra Test e Backend

1. **Tipo di Chiamata**
   - Test: `GET /v1/models` (semplice, read-only)
   - Backend: `POST /v1/{model}:generateContent` (complessa, write)

2. **Contesto di Uso**
   - Test: Singola chiamata manuale
   - Backend: Chiamate multiple, streaming, operazioni complesse

3. **Rilevamento di Google**
   - Google potrebbe rilevare pattern sospetti solo nelle chiamate complesse
   - Le chiamate semplici sono sempre permesse per verifiche

---

## 🛠️ Soluzioni

### Opzione 1: Rigenerare API Key (Consigliato)

1. **Vai su Google AI Studio:**
   - https://aistudio.google.com/app/apikey

2. **Crea nuova API key:**
   - Clicca "Create API Key"
   - Seleziona progetto `392712292504`
   - Copia nuova key

3. **Aggiorna Fly.io:**
   ```bash
   fly secrets set GOOGLE_API_KEY="nuova-api-key-qui"
   ```

4. **Riavvia:**
   ```bash
   fly deploy
   ```

### Opzione 2: Verificare Rate Limiting

1. **Vai su Google Cloud Console:**
   - https://console.cloud.google.com/apis/api/generativelanguage.googleapis.com/quotas?project=392712292504

2. **Controlla:**
   - Quota giornaliera
   - Rate limiting per minuto
   - Se ci sono limiti raggiunti

### Opzione 3: Contattare Google Support

Se pensi che sia un falso positivo:
- Contatta Google Cloud Support
- Spiega la situazione
- Richiedi revisione dell'API key

---

## 📊 Confronto: Chiamate Semplici vs Complesse

| Tipo Chiamata | Endpoint | Funziona? | Perché |
|--------------|----------|-----------|--------|
| **Semplice** | `GET /v1/models` | ✅ Sì | Read-only, nessun costo |
| **Semplice** | `GET /v1/{model}` | ✅ Sì | Read-only, info modello |
| **Complessa** | `POST /v1/{model}:generateContent` | ❌ No | Genera contenuto, consuma quota |
| **Complessa** | `POST /v1/{model}:streamGenerateContent` | ❌ No | Streaming, consuma quota |
| **Complessa** | `POST /v1/{model}:embedContent` | ❌ No | Embeddings, consuma quota |

---

## 🎯 Conclusione

**Perché Google blocca alcune chiamate ma non altre:**

1. ✅ **Chiamate semplici funzionano** perché:
   - Non consumano risorse significative
   - Permettono verifiche
   - Sono read-only

2. ❌ **Chiamate complesse sono bloccate** perché:
   - Consumano quota/token
   - Possono essere abusate
   - Google le blocca per sicurezza quando rileva API key leaked

**Soluzione:** Rigenera l'API key per sbloccare tutte le funzionalità.

---

## 🔗 Link Utili

- **Google AI Studio:** https://aistudio.google.com/app/apikey
- **Google Cloud Console:** https://console.cloud.google.com/apis/credentials?project=392712292504
- **Documentazione API:** https://ai.google.dev/api

