# ✅ Deploy Checklist - Multi-Turn Conversation Fix

## Pre-Deploy ✅

- [x] Codice committato e pushato
- [x] Test unitari passati (88/88)
- [x] Type checking passato
- [x] Linting passato

## Deploy 🚀

- [x] Deploy avviato su Fly.io
- [ ] Deploy completato (verificare con `flyctl status`)
- [ ] App raggiungibile (https://nuzantara-mouth.fly.dev)

## Post-Deploy Testing 🧪

### 1. Test E2E

```bash
cd apps/mouth
PLAYWRIGHT_BASE_URL=https://nuzantara-mouth.fly.dev \
npm run test:e2e -- e2e/chat/multi-turn-conversation.spec.ts --project=chromium
```

**Risultati attesi:**

- ✅ 4/6 test passano (i 2 con problemi di selettori sono stati fixati)
- ✅ Input non si disabilita permanentemente
- ✅ Rate limiting gestito correttamente
- ✅ Timeout gestiti correttamente

### 2. Verifica Monitoraggio

```bash
cd apps/mouth
./scripts/check-monitoring.sh
```

**Nella console del browser:**

1. Apri DevTools (F12)
2. Vai alla tab Console
3. Invia 10+ messaggi
4. Cerca alert: `[MONITORING ALERT]`
5. Verifica metriche: `window.conversationMonitor.getSummary()`

**Alert attesi:**

- `LONG_CONVERSATION` dopo 15 turni
- `MULTIPLE_ERRORS` dopo 3 errori
- `MULTIPLE_TIMEOUTS` dopo 2 timeout
- `RATE_LIMIT_ISSUES` dopo 2 rate limit hits

### 3. Test Manuali

```bash
cd apps/mouth
./scripts/test-manual-10-turns.sh
```

**Checklist per ogni messaggio:**

- ✅ Input abilitato prima di inviare
- ✅ Messaggio inviato correttamente
- ✅ Risposta AI ricevuta
- ✅ Input riabilitato dopo risposta
- ✅ Nessun errore nella console

**Messaggi di test (10 turni):**

1. Ciao, sono Paolo, un imprenditore italiano
2. Voglio aprire un bar a Bali
3. Il mio budget è 200 milioni IDR
4. Ho già un socio indonesiano
5. Lui ha esperienza nel settore
6. Preferisco una location a Seminyak
7. Quanto tempo ci vuole per aprire?
8. E per i permessi del personale?
9. Riassumi tutto quello che abbiamo discusso
10. Grazie per le informazioni

## Verifica Finale ✅

### Funzionalità Core

- [ ] Conversazioni di 10+ turni funzionano senza blocchi
- [ ] Input non si disabilita permanentemente
- [ ] Safety timeout funziona (130s)
- [ ] Rate limiting non blocca conversazioni lunghe
- [ ] Error handling corretto per tutti i tipi di errore

### Monitoraggio

- [ ] Alert appaiono nella console per conversazioni lunghe
- [ ] Metriche disponibili via `window.conversationMonitor`
- [ ] Errori tracciati correttamente
- [ ] Timeout tracciati correttamente

### Performance

- [ ] Nessun memory leak dopo conversazioni lunghe
- [ ] Performance accettabile anche con 15+ turni
- [ ] Nessun crash o freeze

## Problemi Conosciuti ⚠️

1. **E2E Test Selectors**: Alcuni test potrebbero fallire se la struttura HTML cambia
   - **Fix**: Usare selettori più robusti basati su logo Zantara
   - **Status**: ✅ Fixato

2. **Monitoring in Development**: Alert non appaiono in dev mode
   - **Fix**: Usare `[DEV MONITORING]` prefix in sviluppo
   - **Status**: ✅ Implementato

## Rollback Plan 🔄

Se necessario, rollback con:

```bash
cd apps/mouth
flyctl releases
flyctl releases rollback <release-id>
```

## Contatti 📞

Per problemi o domande:

- Check logs: `flyctl logs`
- Check status: `flyctl status`
- Check metrics: `flyctl metrics`
