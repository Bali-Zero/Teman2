# TEST MANUALE CHECKLIST - Deploy Consolidamento Streaming SSE

**Data:** 2026-01-13  
**Deploy ID:** `dpl_5VdjGD2zPVcVGiztCaTQwpT6Jfb7`  
**URL:** https://zantara.balizero.com

---

## ✅ PRE-TEST VERIFICA

### Status Deploy:
- ✅ Deploy completato: `3ba0a46c`
- ✅ Status: Ready (Production)
- ✅ Build: Success (1m)
- ✅ URL attivo: https://zantara.balizero.com

---

## 🧪 TEST MANUALE - CHAT STREAMING

### 1. Accesso e Login
- [ ] Accedere a https://zantara.balizero.com
- [ ] Verificare redirect a `/login` funziona
- [ ] Login con credenziali valide
- [ ] Verificare redirect a dashboard/chat

### 2. Chat Streaming - Test Base
- [ ] Aprire pagina chat (`/chat`)
- [ ] Verificare UI carica correttamente
- [ ] Inviare messaggio semplice (es: "Hello")
- [ ] Verificare streaming funziona:
  - [ ] Messaggio appare istantaneamente (optimistic update)
  - [ ] Risposta streama token per token
  - [ ] Nessun errore console
  - [ ] Risposta completa ricevuta

### 3. Chat Streaming - Test Avanzati
- [ ] Test con immagini:
  - [ ] Attaccare immagine
  - [ ] Inviare messaggio con immagine
  - [ ] Verificare vision funziona
- [ ] Test con conversazione lunga:
  - [ ] Inviare 3-4 messaggi sequenziali
  - [ ] Verificare context mantenuto
  - [ ] Verificare session_id funziona
- [ ] Test cancellazione:
  - [ ] Iniziare streaming
  - [ ] Cancellare durante streaming
  - [ ] Verificare abort funziona

### 4. Logger Strutturato - Verifica
- [ ] Aprire DevTools Console
- [ ] Inviare messaggio chat
- [ ] Verificare logs strutturati:
  - [ ] Logs hanno formato strutturato
  - [ ] Context presente (component, action)
  - [ ] Metadata presente
  - [ ] Nessun `console.log/warn/error` raw

### 5. Error Handling - Test
- [ ] Simulare errore network:
  - [ ] Disabilitare network in DevTools
  - [ ] Inviare messaggio
  - [ ] Verificare messaggio errore user-friendly
  - [ ] Verificare error handling centralizzato funziona
- [ ] Test timeout:
  - [ ] Inviare query complessa
  - [ ] Verificare timeout gestito correttamente
  - [ ] Verificare messaggio timeout user-friendly

---

## 📊 MONITORING LOGS

### Comandi Vercel:

```bash
# Status deploy
cd apps/mouth
vercel ls

# Logs runtime (ultimi 5 minuti)
vercel logs https://mouth-77xuogi1i-nuzantara-2026.vercel.app

# Inspect deploy
vercel inspect https://mouth-77xuogi1i-nuzantara-2026.vercel.app
```

### Cosa Cercare nei Logs:

#### ✅ Logs Attesi (Normali):
- `[INFO] Stream completed` - Streaming completato con successo
- `[INFO] Message received successfully` - Messaggio ricevuto
- `[DEBUG] Loading user profile` - Caricamento profilo

#### ⚠️ Logs da Monitorare:
- `[ERROR] Stream error` - Errori durante streaming
- `[ERROR] Failed to load` - Errori caricamento
- `[WARN]` - Warning vari

#### ❌ Logs da Evitare:
- `console.log` raw (dovrebbero essere sostituiti)
- `console.error` raw (dovrebbero essere logger.error)
- Errori di type safety
- Errori di import

---

## 📈 VERIFICA PERFORMANCE

### Metriche da Controllare:

1. **Build Performance:**
   - Build time: ~1m ✅
   - Bundle size: Verificare non aumentato significativamente
   - Chunks: Verificare ottimizzati

2. **Runtime Performance:**
   - TTFB (Time to First Byte): < 500ms
   - Streaming latency: < 1s al primo token
   - Error rate: < 1%

3. **Vercel Dashboard:**
   - Accedere a: https://vercel.com/nuzantara-2026/mouth
   - Verificare:
     - [ ] Deploy success rate
     - [ ] Function execution time
     - [ ] Error rate
     - [ ] Bandwidth usage

---

## 🔍 REGRESSIONI DA VERIFICARE

### Funzionalità Esistenti:
- [ ] Login funziona correttamente
- [ ] Dashboard carica correttamente
- [ ] Chat funziona come prima
- [ ] Altri endpoint API funzionano

### Nuove Funzionalità:
- [ ] Logger strutturato attivo
- [ ] Error handling migliorato
- [ ] Type safety migliorata

### Performance:
- [ ] Nessun degrado performance
- [ ] Bundle size non aumentato
- [ ] Load time simile o migliore

---

## 🐛 BUG DA VERIFICARE

### Bug Potenziali:
- [ ] Streaming si interrompe prematuramente
- [ ] Errori durante streaming
- [ ] Logs duplicati o eccessivi
- [ ] Error handling non funziona
- [ ] Type errors in console

### Fix da Verificare:
- [ ] `useOptimisticChat` rimosso correttamente
- [ ] `sendMessageStream` non più utilizzato
- [ ] Logger strutturato sostituisce console
- [ ] Error handler centralizzato funziona

---

## ✅ CHECKLIST FINALE

### Test Funzionalità:
- [ ] Chat streaming funziona
- [ ] Logger strutturato attivo
- [ ] Error handling funziona
- [ ] Nessun errore console

### Monitoring:
- [ ] Logs Vercel verificati
- [ ] Performance metriche OK
- [ ] Nessuna regressione

### Documentazione:
- [ ] Test completati
- [ ] Risultati documentati
- [ ] Issue risolte verificate

---

## 📝 NOTE TEST

### Ambiente:
- Browser: _______________
- OS: _______________
- Network: _______________

### Risultati:
- Test completati: ___/___
- Errori trovati: ___
- Performance: ☐ OK ☐ Degradata

### Issue Trovate:
1. _______________
2. _______________
3. _______________

---

**Test Started:** _______________  
**Test Completed:** _______________  
**Status:** ☐ Pass ☐ Fail ☐ Partial
