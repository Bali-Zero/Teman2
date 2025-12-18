# 📊 Monitoring Guide - Long Conversations

## Overview

Il sistema di monitoring traccia le conversazioni lunghe e identifica potenziali problemi in produzione.

## Funzionalità

### 1. Tracking Automatico

Il monitoring viene attivato automaticamente quando usi `useChat` hook:

- **Turni di conversazione**: Conta ogni messaggio inviato
- **Errori**: Traccia errori per tipo (TIMEOUT, QUOTA_EXCEEDED, etc.)
- **Timeout**: Conta i timeout durante lo streaming
- **Rate Limit**: Traccia quando viene raggiunto il rate limit

### 2. Alert Automatici

Il sistema genera alert quando:

- **15+ turni**: Conversazione molto lunga
- **3+ errori**: Multiple errori nella stessa conversazione
- **2+ timeout**: Multiple timeout indicano problemi di rete/server
- **2+ rate limit hits**: Problemi con rate limiting

### 3. Metriche Disponibili

```typescript
import { conversationMonitor } from '@/lib/monitoring';

// Ottieni metriche per una sessione
const metrics = conversationMonitor.getMetrics(sessionId);

// Ottieni tutte le sessioni attive
const activeSessions = conversationMonitor.getActiveSessions();

// Ottieni statistiche aggregate
const summary = conversationMonitor.getSummary();
```

## Uso in Produzione

### Console Logs

In produzione, gli alert vengono loggati nella console del browser:

```
[MONITORING ALERT] LONG_CONVERSATION: {
  sessionId: "session-123",
  turnCount: 15,
  duration: 1200000
}
```

### Integrazione con Sentry (Opzionale)

Per inviare alert a Sentry, modifica `monitoring.ts`:

```typescript
if (window.Sentry) {
  window.Sentry.captureMessage(`Conversation Alert: ${type}`, {
    level: 'warning',
    extra: data,
  });
}
```

## Test Manuali

### Script di Test

Esegui il test manuale per verificare conversazioni lunghe:

```bash
./scripts/test-manual-10-turns.sh
```

Lo script:
1. Verifica che l'app sia raggiungibile
2. Apre il browser automaticamente
3. Fornisce una checklist per ogni turno
4. Guida attraverso 10 messaggi di test

### Checklist Manuale

Per ogni messaggio, verifica:

- ✅ Input abilitato prima di inviare
- ✅ Messaggio inviato correttamente
- ✅ Risposta AI ricevuta
- ✅ Input riabilitato dopo risposta
- ✅ Nessun errore nella console

### Problemi da Segnalare

- ❌ Input disabilitato permanentemente
- ❌ Messaggio non inviato
- ❌ Risposta non ricevuta
- ❌ Errori nella console
- ❌ Timeout dopo 8+ turni

## Debugging

### Verifica Metriche

Apri la console del browser e esegui:

```javascript
// Ottieni tutte le sessioni attive
window.conversationMonitor?.getActiveSessions()

// Ottieni statistiche
window.conversationMonitor?.getSummary()
```

### Log Dettagliati

Per vedere log dettagliati, modifica `monitoring.ts`:

```typescript
private logAlert(type: string, data: Record<string, unknown>): void {
  console.log(`[MONITORING] ${type}:`, data); // Sempre logga
  // ... resto del codice
}
```

## Best Practices

1. **Monitora regolarmente**: Controlla gli alert nella console
2. **Testa manualmente**: Esegui test manuali dopo ogni deploy
3. **Raccogli feedback**: Chiedi agli utenti di segnalare problemi
4. **Analizza pattern**: Identifica pattern comuni negli errori

## Metriche Chiave

- **Turni medi per conversazione**: Target > 10
- **Tasso di errore**: Target < 1%
- **Timeout rate**: Target < 0.5%
- **Rate limit hits**: Target < 0.1%

