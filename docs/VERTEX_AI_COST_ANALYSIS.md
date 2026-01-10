# 💰 GOOGLE AI STUDIO / VERTEX AI - Analisi Costi per Knowledge Graph Extraction

**Data:** 2026-01-11  
**Obiettivo:** Calcolare costi Google AI Studio e Vertex AI per build knowledge graph

**⚠️ IMPORTANTE:** Stiamo usando **Google AI Studio** con ADC (`gemini /auth`), non Vertex AI!

---

## 📊 PREZZI GOOGLE AI STUDIO / VERTEX AI (2026)

**⚠️ NOTA:** Google AI Studio e Vertex AI hanno lo stesso pricing dopo il free tier!

### Google AI Studio Free Tier

**Limiti Gratuiti:**
- ✅ **15 RPM** (richieste al minuto)
- ✅ **1,500 RPD** (richieste al giorno)
- ✅ **$0.00** fino a questi limiti

**Dopo Free Tier:**
- Stesso pricing di Vertex AI

### Gemini Models Pricing (Dopo Free Tier)

**Gemini 3 Flash Preview:**
- **Input:** $0.00 per 1M tokens (GRATIS durante preview)
- **Output:** $0.00 per 1M tokens (GRATIS durante preview)
- **Status:** Preview gratuito

**Gemini 2.0 Flash** (fallback):
- **Input:** $0.075 per 1M tokens
- **Output:** $0.30 per 1M tokens

**Gemini 2.5 Flash GA**:
- **Input:** $0.30 per 1M tokens
- **Output:** $2.50 per 1M tokens

**Gemini 2.5 Pro**:
- **Input:** $1.25 per 1M tokens (fino a 200k), $2.50 per 1M (oltre 200k)
- **Output:** $10.00 per 1M tokens (fino a 200k), $15.00 per 1M (oltre 200k)

**Fonte:** [Google Cloud Vertex AI Pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing)

---

## 🔢 CALCOLO COSTI PER KNOWLEDGE GRAPH

### Token Usage per Chunk

**Per ogni chunk:**
- Prompt: ~500 tokens (testo chunk + istruzioni estrazione)
- Output: ~200 tokens (entità e relazioni JSON)
- **Totale:** ~700 tokens per chunk

### Costi per Run Completo (58k chunk)

**Google AI Studio Free Tier:**
- ⚠️ **Limite:** 1,500 richieste/giorno
- ⚠️ **58k chunk supera limite** (serve 58k richieste)
- **Costo:** $0.00 per primi 1,500 chunk ✅
- **Costo:** Stesso di Vertex AI per chunk oltre 1,500

**Gemini 3 Flash Preview** (se disponibile):
- Input: 58,000 × 500 = 29,000,000 tokens (29M)
- Output: 58,000 × 200 = 11,600,000 tokens (11.6M)
- **Costo:** $0.00 (GRATIS durante preview) ✅

**Gemini 2.0 Flash** (se preview finisce):
- Input: 29M × $0.075/1M = **$2.175**
- Output: 11.6M × $0.30/1M = **$3.48**
- **Totale:** **$5.655** per full build

**Gemini 2.5 Flash GA**:
- Input: 29M × $0.30/1M = **$8.70**
- Output: 11.6M × $2.50/1M = **$29.00**
- **Totale:** **$37.70** per full build

---

## 📈 COSTI INCREMENTALI (Giornalieri)

### Scenario Realistico

**Assumendo 50-200 chunk nuovi/giorno:**

**Gemini 3 Flash Preview:**
- **Costo/giorno:** $0.00 ✅
- **Costo/mese:** $0.00 ✅

**Gemini 2.0 Flash:**
- 100 chunk/giorno: 70k tokens/giorno
- Input: 50k × $0.075/1M = $0.00375
- Output: 20k × $0.30/1M = $0.006
- **Costo/giorno:** ~$0.01
- **Costo/mese:** ~$0.30

**Gemini 2.5 Flash GA:**
- 100 chunk/giorno: 70k tokens/giorno
- Input: 50k × $0.30/1M = $0.015
- Output: 20k × $2.50/1M = $0.05
- **Costo/giorno:** ~$0.065
- **Costo/mese:** ~$1.95

---

## 💳 CREDITI GOOGLE CLOUD DISPONIBILI

**Dal tuo account:**
- **Credito disponibile:** ~5 milioni IDR
- **Scadenza:** 6 febbraio 2026
- **Conversione:** ~$320 USD (circa)

**Con Gemini 3 Flash Preview (gratis):**
- ✅ Nessun costo fino a fine preview
- ✅ Crediti conservati per altri servizi

**Con Gemini 2.0 Flash:**
- Full build (58k chunk): $5.66
- Incremental (100 chunk/giorno): ~$0.30/mese
- **Durata crediti:** ~53 mesi di incremental o ~56 full build

---

## 🎯 CONFRONTO COSTI

### Full Build (58k chunk)

| Modello | Costo Full Build |
|---------|------------------|
| Gemini 3 Flash Preview | **$0.00** ✅ |
| Gemini 2.0 Flash | **$5.66** |
| Gemini 2.5 Flash GA | **$37.70** |
| Google AI Studio Free Tier | **$0.00** (limite 1,500 RPD) |

### Incremental (100 chunk/giorno)

| Modello | Costo/Giorno | Costo/Mese |
|---------|--------------|-------------|
| Gemini 3 Flash Preview | **$0.00** ✅ | **$0.00** ✅ |
| Gemini 2.0 Flash | $0.01 | $0.30 |
| Gemini 2.5 Flash GA | $0.065 | $1.95 |

---

## ✅ RACCOMANDAZIONE

### Per Knowledge Graph Extraction

**Opzione 1: Google AI Studio Free Tier (ATTUALE - `gemini /auth`)**
- ✅ **GRATIS** fino a 1,500 RPD
- ✅ **GRATIS** fino a 15 RPM
- ✅ Nessun costo per incremental (100 chunk/giorno)
- ⚠️ Limite: 1,500 richieste/giorno (non sufficiente per full build veloce)
- ✅ Perfetto per build incrementali

**Opzione 2: Gemini 3 Flash Preview (Se disponibile)**
- ✅ **GRATIS** durante preview
- ✅ Nessun costo
- ✅ Nessun limite di chiamate
- ⚠️ Preview potrebbe finire (data non nota)

**Opzione 3: Vertex AI con Service Account**
- ✅ Nessun limite free tier
- ✅ Usa crediti Google Cloud (~$320 disponibili)
- ✅ Molto economico: $5.66 per full build
- ✅ Incremental: ~$0.30/mese
- ✅ Perfetto per full build veloce

---

## 💡 STRATEGIA COSTI

### Fase 1: Usa Google AI Studio Free Tier (ORA - `gemini /auth`)

**Vantaggi:**
- ✅ Completamente gratis fino a 1,500 RPD
- ✅ Nessun costo per incremental (100 chunk/giorno)
- ✅ Perfetto per build incrementali

**Limiti:**
- ⚠️ 1,500 richieste/giorno (non sufficiente per full build veloce)
- ⚠️ 15 richieste/minuto

**Durata:** Gratis finché rispetti i limiti

### Fase 2: Passa a Vertex AI per Full Build

**Vantaggi:**
- ✅ Nessun limite free tier
- ✅ Usa crediti Google Cloud (~$320 disponibili)
- ✅ Molto economico ($5.66 per full build)
- ✅ Incremental: ~$0.30/mese

**Costi stimati:**
- Full build: $5.66 (una tantum)
- Incremental: ~$0.30/mese
- **Durata crediti:** ~53 mesi di incremental

### Fase 3: Monitora Costi

**Metriche da tracciare:**
- Token input/output per run
- Costo per run
- Costo mensile totale
- Utilizzo crediti Google Cloud

---

## 📊 COSTI TOTALI STIMATI

### Scenario Ottimistico (Google AI Studio Free Tier)

**Full Build:**
- ⚠️ Supera limite (1,500 RPD)
- Costo primi 1,500 chunk: **$0.00** ✅
- Costo chunk oltre 1,500: Stesso di Vertex AI

**Incremental (100 chunk/giorno):**
- Costo/giorno: **$0.00** ✅ (entro limite 1,500 RPD)
- Costo/mese: **$0.00** ✅
- Costo/anno: **$0.00** ✅

### Scenario Realistico (Vertex AI con Crediti)

**Full Build:**
- Costo: **$5.66** (una tantum)

**Incremental (100 chunk/giorno):**
- Costo/giorno: **$0.01**
- Costo/mese: **$0.30**
- Costo/anno: **$3.60**

**Con crediti disponibili (~$320):**
- ✅ Sufficienti per ~56 full build
- ✅ Sufficienti per ~1066 mesi di incremental (~89 anni)

---

## 🎯 CONCLUSIONE

### Costi Google AI Studio / Vertex AI

**Attualmente (Google AI Studio Free Tier con `gemini /auth`):**
- ✅ **$0.00** - Completamente gratis fino a 1,500 RPD
- ✅ **$0.00** - Incremental (100 chunk/giorno) rientra nel limite
- ⚠️ Full build (58k chunk) supera limite free tier

**Vertex AI (con crediti):**
- Full build: **$5.66** (una tantum)
- Incremental: **~$0.30/mese**
- ✅ Nessun limite free tier

**Confronto:**
- Google AI Studio Free: Limite 1,500 RPD, gratis ma limitato
- Vertex AI: Nessun limite, costi bassi, usa crediti

### Raccomandazione Finale

**✅ Usa Google AI Studio Free Tier per Incremental:**
- ✅ Gratis fino a 1,500 RPD
- ✅ Perfetto per build incrementali (100 chunk/giorno)
- ✅ Nessun costo aggiuntivo

**✅ Usa Vertex AI per Full Build:**
- ✅ Nessun limite free tier
- ✅ Costi molto bassi ($5.66 per full build)
- ✅ Usa crediti disponibili (~$320 USD)

**Crediti disponibili:** ~$320 USD sufficienti per anni di utilizzo!

---

**Documentazione creata:** 2026-01-11
