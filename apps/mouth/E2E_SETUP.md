# 🎭 Playwright E2E Tests - Setup Completo

## ✅ Installazione Completata

Playwright è stato installato e configurato con successo per il progetto Nuzantara Frontend.

## 📦 Cosa è stato installato

- **@playwright/test** - Framework di testing E2E
- **Browser**: Chromium, Firefox, WebKit installati
- **Configurazione**: `playwright.config.ts` ottimizzato per Next.js

## 📁 Struttura Creata

```
apps/mouth/
├── playwright.config.ts          # Configurazione Playwright
├── e2e/
│   ├── auth/
│   │   └── login.spec.ts         # Test autenticazione
│   ├── chat/
│   │   ├── chat-flow.spec.ts     # Test flusso chat
│   │   └── streaming.spec.ts     # Test streaming SSE
│   ├── crm/
│   │   └── crm-flow.spec.ts      # Test operazioni CRM
│   ├── websocket/
│   │   └── websocket.spec.ts     # Test WebSocket
│   ├── fixtures/
│   │   └── auth.ts               # Fixtures per auth
│   └── utils/
│       └── test-helpers.ts       # Helper functions
└── .github/workflows/
    └── e2e-tests.yml             # CI/CD workflow
```

## 🚀 Comandi Disponibili

```bash
# Esegui tutti i test E2E
npm run test:e2e

# Esegui con UI interattiva (consigliato per sviluppo)
npm run test:e2e:ui

# Debug mode (step-by-step)
npm run test:e2e:debug

# Visualizza report HTML
npm run test:e2e:report

# Esegui test specifici
npx playwright test e2e/auth/login.spec.ts

# Esegui su browser specifico
npx playwright test --project=firefox
```

## 🧪 Test Creati

### 1. **Authentication Tests** (`e2e/auth/login.spec.ts`)
- ✅ Display login form
- ✅ Error handling per credenziali invalide
- ✅ Validazione PIN (lunghezza)
- ✅ Redirect su login successo
- ✅ Persistenza sessione

### 2. **Chat Flow Tests** (`e2e/chat/chat-flow.spec.ts`)
- ✅ Display chat interface
- ✅ Invio messaggio e visualizzazione
- ✅ Risposta AI
- ✅ Conversazione multipla
- ✅ Loading states
- ✅ Gestione messaggi vuoti

### 3. **Streaming Tests** (`e2e/chat/streaming.spec.ts`)
- ✅ Streaming progressivo testo
- ✅ Gestione errori streaming
- ✅ Streaming incompleto
- ✅ Messaggi rapidi successivi

### 4. **WebSocket Tests** (`e2e/websocket/websocket.spec.ts`)
- ✅ Connessione WebSocket
- ✅ Ricezione messaggi
- ✅ Gestione disconnessione
- ✅ Riconnessione automatica
- ✅ Gestione errori

### 5. **CRM Tests** (`e2e/crm/crm-flow.spec.ts`)
- ✅ Estrazione dati CRM da chat
- ✅ Visualizzazione storico conversazioni
- ✅ Ricerca clienti
- ✅ Creazione pratica da chat

## 🔧 Configurazione

### Playwright Config (`playwright.config.ts`)

- **Base URL**: `http://localhost:3000` (configurabile via env)
- **Timeout**: 30s per test
- **Retry**: 2 tentativi su CI
- **Browser**: Chromium, Firefox, WebKit, Mobile Chrome
- **Web Server**: Avvia automaticamente `npm run dev`
- **Screenshots**: Solo su failure
- **Video**: Solo su failure
- **Trace**: Su retry per debugging

### Variabili d'Ambiente

```bash
# Base URL per test (default: http://localhost:3000)
PLAYWRIGHT_BASE_URL=http://localhost:3000

# WebSocket URL (se diverso)
WEBSOCKET_URL=ws://localhost:3000
```

## 🔄 CI/CD Integration

Il workflow GitHub Actions (`.github/workflows/e2e-tests.yml`) esegue automaticamente:

1. ✅ Checkout codice
2. ✅ Setup Node.js 20
3. ✅ Install dependencies
4. ✅ Install Playwright browsers
5. ✅ Build application
6. ✅ Run E2E tests
7. ✅ Upload report e risultati

**Trigger**: 
- Push su `main` o `develop`
- Pull requests
- Manual dispatch

## 📊 Report

Dopo l'esecuzione dei test:

- **HTML Report**: `playwright-report/index.html`
- **JSON Results**: `playwright-report/results.json`
- **Screenshots**: `test-results/` (solo su failure)
- **Videos**: `test-results/` (solo su failure)
- **Traces**: `test-results/` (solo su retry)

## 🐛 Debugging

### 1. UI Mode (Consigliato)
```bash
npm run test:e2e:ui
```
Apre un'interfaccia interattiva dove puoi:
- Vedere i test in tempo reale
- Eseguire test singoli
- Vedere il browser in azione
- Debug step-by-step

### 2. Debug Mode
```bash
npm run test:e2e:debug
```
Apre Playwright Inspector per debugging avanzato.

### 3. Trace Viewer
```bash
npx playwright show-trace test-results/[test-name]/trace.zip
```

### 4. Screenshots e Video
Automaticamente salvati su failure in `test-results/`

## 📝 Best Practices

1. **Mock API Calls**: Usa `page.route()` per mockare le API
2. **Data Test IDs**: Aggiungi `data-testid` agli elementi importanti
3. **Wait Strategies**: Usa `waitFor` invece di `sleep`
4. **Isolation**: Ogni test dovrebbe essere indipendente
5. **Cleanup**: Pulisci lo stato dopo ogni test

## 🔍 Prossimi Passi

1. **Aggiungere data-testid** agli elementi chiave:
   ```tsx
   <button data-testid="send-button">Send</button>
   <textarea data-testid="chat-input" />
   ```

2. **Migliorare selettori** nei test esistenti

3. **Aggiungere più test** per edge cases

4. **Configurare test environment** con backend mock

5. **Aggiungere visual regression tests** (opzionale)

## 📚 Risorse

- [Playwright Documentation](https://playwright.dev)
- [Playwright Best Practices](https://playwright.dev/docs/best-practices)
- [Playwright API Reference](https://playwright.dev/docs/api/class-playwright)

## ⚠️ Note Importanti

- I test richiedono che il backend sia in esecuzione (o completamente mockato)
- Alcuni test WebSocket potrebbero non funzionare in CI senza configurazione aggiuntiva
- I test usano mock delle API per essere più veloci e affidabili
- Per test reali con backend, configurare variabili d'ambiente appropriate

---

**Setup completato il**: $(date)
**Playwright Version**: 1.57.0
**Status**: ✅ Pronto per l'uso

