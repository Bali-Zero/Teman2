# 🔍 ANALISI CONFIGURAZIONE MODELLI GEMINI - SPECIFICA E DETTAGLIATA

**Data**: 2025-12-04  
**Piano Utente**: Google AI Ultra (non Pro)  
**Obiettivo**: Verificare configurazione modelli Gemini 2.5 Flash e 2.5 Pro nel free tier

---

## 📊 FREE TIER GOOGLE AI STUDIO - LIMITI SPECIFICI

### Gemini 2.5 Flash (Free Tier)
- **Richieste al minuto (RPM)**: 10
- **Token al minuto (TPM)**: 250,000
- **Richieste al giorno (RPD)**: 250
- **Finestra di contesto**: 32,000 token
- **Deep Research**: 5 rapporti al mese
- **Audio Overviews**: Fino a 20 al giorno

### Gemini 2.5 Pro (Free Tier)
- **Richieste al minuto (RPM)**: 5
- **Token al minuto (TPM)**: 125,000
- **Richieste al giorno (RPD)**: 100
- **Finestra di contesto**: 32,000 token
- **Deep Research**: 5 rapporti al mese
- **Audio Overviews**: Fino a 20 al giorno

### Google AI Ultra (Piano Utente - $250/mese)
- **Richieste al giorno**: 500
- **Finestra di contesto**: 1,000,000 token
- **Deep Research**: 200 rapporti al giorno
- **Deep Think**: 10 richieste al giorno
- **Video Veo 3**: 5 creazioni al giorno
- **Modelli disponibili**: Gemini Ultra + tutti i modelli free tier

---

## 🔍 ANALISI CODICE BACKEND

### 1. `services/gemini_service.py` ❌ **PROBLEMA CRITICO**

**Riga 14**: 
```python
def __init__(self, model_name: str = "gemini-1.5-flash"):
```

**Problema**: 
- Usa `gemini-1.5-flash` che **NON ESISTE PIÙ** nell'API v1beta
- Questo è il servizio principale usato da `intelligent_router.py` per le chat
- Causa errore: `404 models/gemini-1.5-flash is not found`

**Correzione Richiesta**:
```python
def __init__(self, model_name: str = "gemini-2.5-flash"):
```

**Formato API**:
- Google Generative AI SDK accetta: `"gemini-2.5-flash"` (senza "models/")
- Non `"models/gemini-2.5-flash"` (quello è per REST API)

### 2. `llm/zantara_ai_client.py` ✅ **CORRETTO**

**Riga 81**:
```python
self.model = model or "gemini-2.5-pro"
```

**Status**: ✅ Corretto - usa `gemini-2.5-pro`
**Nota**: Questo client non è usato per le chat principali (usa `gemini_jaksel`)

### 3. `app/routers/oracle_universal.py` ✅ **CORRETTO**

**Riga 185**:
```python
def get_gemini_model(self, model_name: str = "models/gemini-2.5-flash"):
```

**Status**: ✅ Corretto - usa `models/gemini-2.5-flash` (formato REST API)
**Nota**: Questo è per Oracle queries, non per chat principali

### 4. `services/smart_oracle.py` ✅ **CORRETTO**

**Riga 155**:
```python
model = genai.GenerativeModel("gemini-2.5-flash")
```

**Status**: ✅ Corretto - usa `gemini-2.5-flash` (formato SDK corretto)

---

## 🎯 NOMI MODELLI CORRETTI PER API

### Google Generative AI SDK (Python)
```python
import google.generativeai as genai

# Formato CORRETTO (senza "models/")
model = genai.GenerativeModel("gemini-2.5-flash")
model = genai.GenerativeModel("gemini-2.5-pro")
model = genai.GenerativeModel("gemini-ultra")  # Solo per piano Ultra
```

### REST API (HTTP)
```
POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent
POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent
POST https://generativelanguage.googleapis.com/v1beta/models/gemini-ultra:generateContent
```

**Differenza chiave**:
- **SDK Python**: `"gemini-2.5-flash"` (senza "models/")
- **REST API**: `"models/gemini-2.5-flash"` (con "models/")

---

## 🔧 CORREZIONI RICHIESTE

### 1. Correggere `services/gemini_service.py`

**File**: `apps/backend-rag/backend/services/gemini_service.py`

**Cambiamento**:
```python
# PRIMA (ERRATO)
def __init__(self, model_name: str = "gemini-1.5-flash"):
    """
    Args:
        model_name: "gemini-1.5-flash" (Fast/Cheap) or "gemini-1.5-pro" (High Quality)
    """

# DOPO (CORRETTO)
def __init__(self, model_name: str = "gemini-2.5-flash"):
    """
    Args:
        model_name: "gemini-2.5-flash" (Fast/Unlimited on Ultra) or "gemini-2.5-pro" (High Quality)
    """
```

**Motivazione**:
- `gemini-1.5-flash` non esiste più nell'API v1beta
- `gemini-2.5-flash` è disponibile nel free tier (250 RPD)
- Con piano Ultra, Flash è illimitato per uso normale

---

## 📋 VERIFICA COMPLETA MODELLI NEL CODICE

| File | Modello Configurato | Status | Formato |
|------|-------------------|--------|---------|
| `services/gemini_service.py` | `gemini-1.5-flash` | ❌ **ERRATO** | SDK |
| `llm/zantara_ai_client.py` | `gemini-2.5-pro` | ✅ Corretto | SDK |
| `app/routers/oracle_universal.py` | `models/gemini-2.5-flash` | ✅ Corretto | REST |
| `services/smart_oracle.py` | `gemini-2.5-flash` | ✅ Corretto | SDK |

---

## 🎯 RACCOMANDAZIONE PER PIANO ULTRA

Con **Google AI Ultra** ($250/mese), hai accesso a:

1. **Gemini Ultra**: 500 RPD, 1M token context
2. **Gemini 2.5 Flash**: Illimitato (per uso normale)
3. **Gemini 2.5 Pro**: Illimitato (per uso normale)

**Raccomandazione**:
- **Chat principali**: Usa `gemini-2.5-flash` (veloce, illimitato)
- **Analisi complesse**: Usa `gemini-2.5-pro` (migliore qualità)
- **Task critici**: Usa `gemini-ultra` (massima qualità, 500 RPD)

---

## ✅ AZIONI IMMEDIATE

1. **🔴 CRITICO**: Correggere `services/gemini_service.py` da `gemini-1.5-flash` a `gemini-2.5-flash`
2. **🟡 VERIFICARE**: Che `GOOGLE_API_KEY` sia configurato in Fly.io secrets
3. **🟡 TESTARE**: Endpoint chat dopo correzione

---

## 📊 CONFRONTO MODELLI

| Caratteristica | Gemini 2.5 Flash | Gemini 2.5 Pro | Gemini Ultra |
|----------------|------------------|----------------|--------------|
| **Velocità** | ⚡⚡⚡ Molto veloce | ⚡⚡ Veloce | ⚡ Media |
| **Qualità** | ⭐⭐⭐ Buona | ⭐⭐⭐⭐ Ottima | ⭐⭐⭐⭐⭐ Eccellente |
| **Free Tier RPD** | 250 | 100 | 0 (solo Ultra) |
| **Ultra Plan RPD** | Illimitato* | Illimitato* | 500 |
| **Context Window** | 32K (free) / 1M (Ultra) | 32K (free) / 1M (Ultra) | 1M |
| **Uso Consigliato** | Chat, risposte rapide | Analisi complesse | Task critici |

*Illimitato per uso normale, soggetto a fair use policy

---

**Report generato**: 2025-12-04  
**Piano Utente**: Google AI Ultra  
**Status**: ⚠️ **CORREZIONE RICHIESTA** in `services/gemini_service.py`

