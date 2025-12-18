# 📊 Monitoring Workflow - Guida Completa

## Overview

Questo documento descrive il workflow completo per il monitoraggio continuo delle conversazioni lunghe in produzione.

## 🔄 Workflow Settimanale

### 1. Monitoraggio Continuo (Giornaliero)

#### Console Browser

Apri l'app e la console del browser per vedere alert in tempo reale:

```javascript
// Quick commands nella console
monitoringHelpers.summary(); // Mostra summary
monitoringHelpers.alerts(); // Mostra alert attivi
monitoringHelpers.export(); // Esporta metriche
monitoringHelpers.clear(60); // Pulisci sessioni vecchie
```

#### Alert Automatici

Il sistema genera automaticamente alert per:

- **LONG_CONVERSATION**: Dopo 15+ turni
- **MULTIPLE_ERRORS**: Dopo 3+ errori
- **MULTIPLE_TIMEOUTS**: Dopo 2+ timeout
- **RATE_LIMIT_ISSUES**: Dopo 2+ rate limit hits

**Cosa fare:**

- Controlla la console regolarmente
- Prendi nota degli alert
- Analizza pattern comuni

### 2. Test Periodici (Settimanale)

#### Test Manuali

Esegui test manuali ogni settimana:

```bash
cd apps/mouth
./scripts/test-manual-10-turns.sh
```

**Checklist:**

- ✅ 10 messaggi inviati senza problemi
- ✅ Input sempre abilitato
- ✅ Nessun errore nella console
- ✅ Performance accettabile

#### Test E2E Automatici

Esegui test E2E dopo ogni deploy:

```bash
cd apps/mouth
PLAYWRIGHT_BASE_URL=https://nuzantara-mouth.fly.dev \
npm run test:e2e -- e2e/chat/multi-turn-conversation.spec.ts
```

### 3. Analisi Metriche (Settimanale)

#### Genera Report Settimanale

```bash
cd apps/mouth
./scripts/weekly-monitoring-report.sh
```

**Processo:**

1. Apri l'app nel browser
2. Esegui `monitoringHelpers.export()` nella console
3. Salva l'output JSON nel file di report
4. Analizza i dati per identificare:
   - Conversazioni più lunghe
   - Pattern di errori
   - Trend nel tempo

#### Metriche Chiave da Monitorare

```javascript
const summary = window.conversationMonitor.getSummary();

// Metriche target:
// - activeSessions: < 100 (troppe sessioni attive = problema)
// - totalTurns: Media > 10 per sessione
// - totalErrors: < 1% dei turni totali
// - totalTimeouts: < 0.5% dei turni totali
// - totalRateLimitHits: < 0.1% dei turni totali
```

### 4. Raccolta Feedback (Continuo)

#### Feedback Widget

Il widget appare automaticamente dopo 8+ messaggi:

- **Positivo**: Cosa funziona bene
- **Negativo**: Problemi riscontrati
- **Bug**: Segnalazione bug specifici

#### Analisi Feedback

```bash
cd apps/mouth
./scripts/analyze-feedback.sh
```

**Processo:**

1. Esporta feedback da localStorage:
   ```javascript
   JSON.parse(localStorage.getItem('conversationFeedback') || '[]');
   ```
2. Analizza pattern comuni
3. Identifica problemi ricorrenti
4. Genera raccomandazioni

## 📈 Dashboard Monitoring

### Accesso Dashboard

```javascript
// Nella console del browser
window.monitoringDashboard.showSummary();
window.monitoringDashboard.showAlerts();
window.monitoringDashboard.showSessionDetails('session-id');
```

### Widget Visivo

Il widget di monitoring appare automaticamente in sviluppo.
Per abilitarlo in produzione:

```javascript
localStorage.setItem('showMonitoringWidget', 'true');
```

## 🎯 Metriche Target

### Performance

- **Turni medi**: > 10 per conversazione
- **Tasso di errore**: < 1%
- **Timeout rate**: < 0.5%
- **Rate limit hits**: < 0.1%

### Qualità

- **Input sempre abilitato**: 100%
- **Risposte coerenti**: > 95%
- **Soddisfazione utente**: > 4/5

## 📋 Checklist Settimanale

### Lunedì - Review Settimanale

- [ ] Genera report settimanale
- [ ] Analizza metriche della settimana precedente
- [ ] Identifica trend e pattern
- [ ] Pianifica miglioramenti

### Mercoledì - Test Manuali

- [ ] Esegui test manuali (10+ turni)
- [ ] Verifica che tutto funzioni correttamente
- [ ] Controlla alert nella console
- [ ] Documenta eventuali problemi

### Venerdì - Analisi Feedback

- [ ] Esporta feedback utenti
- [ ] Analizza feedback raccolto
- [ ] Identifica problemi comuni
- [ ] Aggiorna roadmap miglioramenti

## 🚨 Alert e Azioni

### LONG_CONVERSATION (15+ turni)

**Azione**:

- ✅ Normale - conversazione produttiva
- ⚠️ Monitora per performance issues

### MULTIPLE_ERRORS (3+ errori)

**Azione**:

- 🔍 Analizza tipo di errori
- 📝 Documenta pattern
- 🐛 Fix se bug identificato

### MULTIPLE_TIMEOUTS (2+ timeout)

**Azione**:

- 🔍 Verifica problemi di rete/server
- ⚙️ Controlla configurazione timeout
- 📊 Analizza performance backend

### RATE_LIMIT_ISSUES (2+ hits)

**Azione**:

- ⚙️ Verifica configurazione rate limit
- 📈 Analizza traffico
- 🔧 Aggiusta limiti se necessario

## 📊 Report Template

```json
{
  "reportDate": "2025-12-11",
  "summary": {
    "activeSessions": 10,
    "totalTurns": 150,
    "totalErrors": 2,
    "totalTimeouts": 1,
    "totalRateLimitHits": 0
  },
  "sessions": [...],
  "alerts": [...],
  "recommendations": [
    "Monitorare conversazioni > 20 turni",
    "Investigare errori tipo TIMEOUT"
  ]
}
```

## 🔗 Risorse

- **Monitoring Guide**: `MONITORING_GUIDE.md`
- **Deploy Checklist**: `DEPLOY_CHECKLIST.md`
- **Scripts**: `scripts/` directory
- **Components**: `src/components/MonitoringWidget.tsx`, `FeedbackWidget.tsx`

## 💡 Best Practices

1. **Monitora regolarmente**: Controlla console almeno una volta al giorno
2. **Testa manualmente**: Esegui test settimanali
3. **Analizza trend**: Confronta metriche settimana per settimana
4. **Raccogli feedback**: Usa widget feedback per capire esperienza utente
5. **Documenta problemi**: Mantieni log di problemi e soluzioni
