# Next Steps - KBLI 2025 Migration & Content Strategy

**Situation**: ✅ KBLI Batch 2 Articles Published (12/12)

---

## 🎯 Azione Immediata

### 1. Monitoraggio SEO (24-48h)

- Verificare indicizzazione su Google Search Console per i nuovi slug `kbli-2025-*`.
- Controllare impression e click rate per `kbli-2025-foreign-ownership-pma-guide`.

### 2. Social Distribution

- Preparare thread LinkedIn/Twitter basati sugli "AI Snippet" generati nel frontmatter degli articoli.
- Focus su: "Fiktif Positif" (Hospitality) e "Category J vs K" (IT).

---

## 📋 Prossimi Passi

### 1. KBLI Batch 3: Finance & Crypto (Priorità Alta)

- **Tema:** Regolamentazione OJK, Crypto (6619), Fintech, Venture Capital.
- **Obiettivo:** Coprire la migrazione da Bappebti a OJK per asset digitali.
- **Target:** Investitori crypto, fondatori fintech.

### 2. Aggiornamento KBLI Navigator

- Assicurarsi che il tool di ricerca KBLI sulla webapp rimandi ai nuovi articoli pubblicati.
- Integrare link interni negli articoli verso il Navigator.

### 3. Conversation Persistence (Task Precedente)

- Completare integrazione frontend per la persistenza chat (vedi dettagli sotto).

---

## 📊 Stato Attuale

### ✅ Completato

- **KBLI Batch 1 & 2:** 24+ articoli pubblicati, ottimizzati SEO, immagini Nano Banana Pro.
- **Backend Persistence:** Endpoint `/webhook/chat` deployato.
- **Frontend Client:** `WebhookChatApi` implementato.

### ⏳ Da Fare

- Integrazione UI persistenza chat.
- KBLI Batch 3 (Finance).
- Verifica metriche traffico organico.

---

## 🚀 Comando Rapido (Dev)

```bash
# Avvia ambiente dev per verificare link articoli
cd apps/mouth
npm run dev
```
