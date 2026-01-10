# ⚠️ GOOGLE AI STUDIO - CHIARIMENTO COSTI

**Data:** 2026-01-11  
**Obiettivo:** Chiarire esattamente quando Google AI Studio è gratis e quando costa

---

## ✅ QUANDO È GRATIS

### Free Tier Limits (Gratis fino a questi limiti)

**Gemini 2.5 Flash-Lite:**
- ✅ **1,000 RPD** (richieste al giorno) - GRATIS
- ✅ **15 RPM** (richieste al minuto) - GRATIS
- ✅ **$0.00** fino a questi limiti

**Gemini 2.5 Pro:**
- ✅ **100 RPD** (richieste al giorno) - GRATIS
- ✅ **5 RPM** (richieste al minuto) - GRATIS
- ✅ **$0.00** fino a questi limiti

**Gemini 2.0 Flash:**
- ⚠️ **NON chiaro se ha free tier** (da verificare)
- Potrebbe essere sempre a pagamento

---

## ⚠️ QUANDO COSTA

### Dopo aver Superato i Limiti Free Tier

**Se superi i limiti del free tier:**
- ❌ **Paghi per TUTTE le richieste**, non solo quelle oltre il limite
- ❌ Oppure le richieste oltre il limite vengono rifiutate (rate limit)

**Esempio:**
- Free tier: 1,000 RPD gratis
- Se fai 1,500 richieste:
  - Opzione A: Paghi per tutte le 1,500 richieste
  - Opzione B: Solo le prime 1,000 sono gratis, paghi per le altre 500

**⚠️ IMPORTANTE:** Dipende dal modello e dal piano!

---

## 💰 COSTI DOPO FREE TIER

### Gemini 2.0 Flash (Se non ha free tier o dopo limite)

**Pricing:**
- Input: **$0.075 per 1M tokens**
- Output: **$0.30 per 1M tokens**

**Per Knowledge Graph Extraction:**
- ~500 tokens input per chunk
- ~200 tokens output per chunk
- **Costo per chunk:** ~$0.0000525 (input) + $0.00006 (output) = **~$0.00011 per chunk**

**Esempio:**
- 1,500 chunk: ~$0.165
- 58k chunk: ~$6.38

---

## 🚨 ATTENZIONE: LIMITI RECENTI

### Google ha Ridotto i Limiti Free Tier

**Causa:** Elevata domanda per Gemini 3 Pro

**Impatto:**
- ⚠️ Limiti possono variare in base alla domanda
- ⚠️ Alcuni modelli potrebbero non avere più free tier
- ⚠️ Limiti possono cambiare senza preavviso

**Fonte:** [Android Central - Gemini 3 Pro Limits](https://www.androidcentral.com/apps-software/insane-gemini-3-pro-demand-forces-google-to-cap-access)

---

## 📊 COSA STIAMO USANDO

### Modello Attuale

**Script:** `apps/backend-rag/scripts/kg_incremental_extraction.py`
- Usa: **Gemini 2.0 Flash**

**Problema:**
- ⚠️ **NON chiaro se Gemini 2.0 Flash ha free tier**
- Potrebbe essere sempre a pagamento

---

## ✅ RACCOMANDAZIONE

### Per Essere Sicuri che sia Gratis

**Opzione 1: Usa Gemini 2.5 Flash-Lite**
- ✅ Ha free tier confermato: 1,000 RPD gratis
- ✅ 15 RPM gratis
- ✅ $0.00 fino a questi limiti

**Opzione 2: Verifica Limiti Attuali**
- ✅ Controlla [Google AI Studio Pricing](https://ai.google.dev/pricing)
- ✅ Verifica limiti per Gemini 2.0 Flash
- ✅ Monitora utilizzo per evitare costi imprevisti

**Opzione 3: Usa Vertex AI**
- ✅ Nessun limite free tier (usa crediti)
- ✅ Costi chiari: $5.66 per full build
- ✅ Usa crediti Google Cloud (~$320 disponibili)

---

## 🎯 CONCLUSIONE

### È Gratis?

**SÌ, MA SOLO SE:**
- ✅ Usi un modello con free tier (es. Gemini 2.5 Flash-Lite)
- ✅ Rispetti i limiti (1,000-1,500 RPD, 15 RPM)
- ✅ Non superi i limiti giornalieri

**NO, SE:**
- ❌ Usi un modello senza free tier (es. Gemini 2.0 Flash potrebbe non averlo)
- ❌ Superi i limiti del free tier
- ❌ Le richieste oltre il limite vengono addebitate

### Cosa Fare

1. ✅ **Verifica quale modello stiamo usando** (Gemini 2.0 Flash)
2. ✅ **Verifica se ha free tier** (non chiaro)
3. ✅ **Monitora utilizzo** per evitare costi imprevisti
4. ✅ **Considera Gemini 2.5 Flash-Lite** se vuoi essere sicuro del free tier

---

**⚠️ IMPORTANTE:** I limiti e i costi possono cambiare. Verifica sempre la documentazione ufficiale!

**Documentazione creata:** 2026-01-11
