# MANUAL TESTING GUIDE - Chat Streaming

**Data:** 2026-01-13  
**Purpose:** Guida per test manuale chat streaming su produzione

---

## 🧪 TEST MANUALE CHAT STREAMING

### Prerequisiti:

1. Accesso a produzione: https://kita.balizero.com
2. Account utente valido
3. Browser con DevTools aperto

---

## 📋 CHECKLIST TEST

### 1. Preparazione:

- [ ] Aprire browser (Chrome/Firefox/Safari)
- [ ] Aprire DevTools (F12)
- [ ] Andare su tab "Console"
- [ ] Andare su tab "Network"
- [ ] Navigare a: https://kita.balizero.com/chat

### 2. Login:

- [ ] Eseguire login
- [ ] Verificare nessun errore in console
- [ ] Verificare chat page carica correttamente

### 3. Test Streaming Base:

- [ ] Inviare messaggio di test: "Hello, test message"
- [ ] **Verificare:**
  - ✅ Messaggio appare immediatamente (optimistic update)
  - ✅ Risposta inizia a streamare carattere per carattere
  - ✅ Nessun errore JavaScript in console
  - ✅ Network tab mostra richiesta SSE attiva
  - ✅ Connection rimane stabile

### 4. Test Multiple Messages:

- [ ] Inviare primo messaggio: "First message"
- [ ] Attendere completamento streaming
- [ ] Inviare secondo messaggio: "Second message"
- [ ] **Verificare:**
  - ✅ Ogni messaggio streama correttamente
  - ✅ Nessun conflitto tra stream
  - ✅ Stato UI aggiornato correttamente

### 5. Test Error Handling:

- [ ] Disconnettere internet temporaneamente
- [ ] Inviare messaggio
- [ ] **Verificare:**
  - ✅ Errore gestito correttamente
  - ✅ Messaggio di errore mostrato all'utente
  - ✅ Nessun crash dell'applicazione
  - ✅ Riconnessione automatica quando internet torna

### 6. Test Abort:

- [ ] Inviare messaggio lungo
- [ ] Durante streaming, cliccare "Stop" o chiudere tab
- [ ] **Verificare:**
  - ✅ Stream viene abortito correttamente
  - ✅ Nessun errore in console
  - ✅ Stato UI aggiornato

### 7. Test Image Attachments:

- [ ] Selezionare immagine da allegare
- [ ] Inviare messaggio con immagine
- [ ] **Verificare:**
  - ✅ Immagine caricata correttamente
  - ✅ Preview mostra correttamente
  - ✅ Streaming funziona con immagini

### 8. Test TTS (Text-to-Speech):

- [ ] Inviare messaggio
- [ ] Cliccare su icona TTS
- [ ] **Verificare:**
  - ✅ Audio generato correttamente
  - ✅ Playback funziona
  - ✅ Nessun errore in console

---

## 🔍 VERIFICA CONSOLE

### Errori da Cercare:

- ❌ `TypeError`
- ❌ `ReferenceError`
- ❌ `NetworkError`
- ❌ `SSE connection failed`
- ❌ `Streaming error`

### Warnings da Notare:

- ⚠️ `Deprecated API`
- ⚠️ `Performance warning`
- ⚠️ `Memory leak warning`

### Logs Positivi:

- ✅ `Stream started`
- ✅ `Stream completed`
- ✅ `Message sent successfully`

---

## 📊 NETWORK TAB VERIFICA

### Richieste da Verificare:

1. **SSE Connection:**
   - Tipo: `eventsource` o `fetch` con `text/event-stream`
   - Status: `200` o `200 OK`
   - Headers: `Content-Type: text/event-stream`

2. **Message Send:**
   - Endpoint: `/api/chat/stream` o simile
   - Method: `POST`
   - Status: `200` o `201`

3. **Chunk Reception:**
   - Verificare chunks arrivano progressivamente
   - Nessun timeout o interruzione

---

## ✅ EXPECTED BEHAVIOR

### Streaming:

- ✅ Messaggi streamano carattere per carattere
- ✅ Nessun lag o delay eccessivo
- ✅ UI aggiornata in real-time
- ✅ Nessun flickering o glitch

### Error Handling:

- ✅ Errori gestiti gracefully
- ✅ Messaggi di errore chiari
- ✅ Retry automatico quando possibile
- ✅ Nessun crash o freeze

### Performance:

- ✅ Response time < 500ms per primo chunk
- ✅ Streaming smooth senza interruzioni
- ✅ Nessun memory leak
- ✅ CPU usage ragionevole

---

## 📝 REPORT TEMPLATE

### Test Results:

```
Date: [DATA]
Tester: [NOME]
Browser: [BROWSER/VERSIONE]
OS: [OS/VERSIONE]

Results:
- Streaming Base: ✅/❌
- Multiple Messages: ✅/❌
- Error Handling: ✅/❌
- Abort: ✅/❌
- Image Attachments: ✅/❌
- TTS: ✅/❌

Issues Found:
- [Descrizione issue 1]
- [Descrizione issue 2]

Notes:
- [Note aggiuntive]
```

---

## 🚨 ISSUES TO REPORT

### Critical:

- Stream non parte
- App crash durante streaming
- Errori JavaScript non gestiti
- Memory leak evidente

### High Priority:

- Streaming interrotto frequentemente
- Delay eccessivo nel primo chunk
- Errori di rete non gestiti
- UI non aggiornata correttamente

### Medium Priority:

- Performance degradation
- Warnings in console
- UX issues minori

---

**Last Updated:** 2026-01-13
