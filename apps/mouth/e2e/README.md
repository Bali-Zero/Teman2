# E2E Tests con Playwright

Test end-to-end per il frontend Nuzantara usando Playwright.

## Struttura

```
e2e/
├── auth/              # Test di autenticazione
│   └── login.spec.ts
├── chat/              # Test di chat
│   ├── chat-flow.spec.ts
│   └── streaming.spec.ts
├── crm/               # Test CRM
│   └── crm-flow.spec.ts
├── websocket/         # Test WebSocket
│   └── websocket.spec.ts
├── fixtures/         # Fixtures riutilizzabili
│   └── auth.ts
└── utils/            # Helper functions
    └── test-helpers.ts
```

## Comandi

```bash
# Esegui tutti i test E2E
npm run test:e2e

# Esegui test con UI interattiva
npm run test:e2e:ui

# Debug test
npm run test:e2e:debug

# Visualizza report
npm run test:e2e:report
```

## Scrivere nuovi test

1. Crea un nuovo file `.spec.ts` nella cartella appropriata
2. Usa le fixtures e helper esistenti quando possibile
3. Mock le API calls quando necessario
4. Usa selettori data-testid quando possibile

## Best Practices

- **Isolamento**: Ogni test dovrebbe essere indipendente
- **Mocking**: Mock le API calls per test più veloci e affidabili
- **Selettori**: Usa `data-testid` invece di selettori CSS fragili
- **Attese**: Usa `waitFor` invece di `sleep`
- **Cleanup**: Pulisci lo stato dopo ogni test

## CI/CD

I test E2E vengono eseguiti automaticamente su:
- Push su `main` o `develop`
- Pull requests
- Manualmente tramite `workflow_dispatch`

## Debugging

1. **UI Mode**: `npm run test:e2e:ui` - Esegui test con UI interattiva
2. **Debug Mode**: `npm run test:e2e:debug` - Step-through debugging
3. **Trace Viewer**: I trace vengono salvati automaticamente su failure
4. **Screenshots**: Screenshot automatici su failure

## Note

- I test richiedono che il backend sia in esecuzione (o mockato)
- Alcuni test potrebbero richiedere variabili d'ambiente specifiche
- I test WebSocket potrebbero essere limitati in ambiente CI

