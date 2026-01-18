# VERCEL ANALYTICS MONITORING GUIDE

**Data:** 2026-01-13  
**Purpose:** Guida per monitorare performance metrics su Vercel Analytics

---

## 📊 OVERVIEW

Vercel Analytics fornisce metriche dettagliate su performance, traffico e Core Web Vitals.

---

## 🔍 ACCESSO ANALYTICS

### Dashboard:

1. Accedere a: https://vercel.com/dashboard
2. Selezionare progetto: `nuzantara-2026` o `mouth`
3. Tab "Analytics" o "Speed Insights"

---

## 📈 METRICHE DA MONITORARE

### 1. Core Web Vitals

#### Largest Contentful Paint (LCP):

- **Target:** < 2.5s
- **Warning:** 2.5s - 4.0s
- **Critical:** > 4.0s
- **Monitorare:** Trend settimanale

#### First Input Delay (FID):

- **Target:** < 100ms
- **Warning:** 100ms - 300ms
- **Critical:** > 300ms
- **Monitorare:** Trend settimanale

#### Cumulative Layout Shift (CLS):

- **Target:** < 0.1
- **Warning:** 0.1 - 0.25
- **Critical:** > 0.25
- **Monitorare:** Trend settimanale

### 2. Performance Metrics

#### Time to First Byte (TTFB):

- **Target:** < 200ms
- **Warning:** 200ms - 500ms
- **Critical:** > 500ms

#### First Contentful Paint (FCP):

- **Target:** < 1.8s
- **Warning:** 1.8s - 3.0s
- **Critical:** > 3.0s

#### Time to Interactive (TTI):

- **Target:** < 3.8s
- **Warning:** 3.8s - 7.3s
- **Critical:** > 7.3s

### 3. Traffic Metrics

#### Page Views:

- Monitorare trend giornaliero/settimanale
- Identificare picchi anomali
- Correlare con deployment

#### Unique Visitors:

- Monitorare crescita
- Identificare pattern

#### Bounce Rate:

- **Target:** < 50%
- **Warning:** 50% - 70%
- **Critical:** > 70%

---

## 📋 DAILY MONITORING CHECKLIST

### Ogni Giorno:

- [ ] Verificare Core Web Vitals
- [ ] Verificare error rate
- [ ] Verificare response times
- [ ] Verificare traffic trends
- [ ] Identificare anomalie

### Cosa Cercare:

- ❌ Degradazione performance
- ❌ Errori aumentati
- ❌ Traffico anomalo
- ⚠️ Regressioni dopo deployment

---

## 📊 WEEKLY REVIEW

### Analisi Trends:

1. **Performance Trends:**
   - LCP trend (miglioramento/degradazione)
   - FID trend
   - CLS trend
   - TTFB trend

2. **Traffic Trends:**
   - Page views trend
   - Unique visitors trend
   - Bounce rate trend

3. **Error Trends:**
   - Error rate trend
   - Error types
   - Error pages

### Report Template:

```
WEEKLY ANALYTICS REVIEW
Date: [DATA]
Period: [SETTIMANA]

Core Web Vitals:
- LCP: [VALORE] (Trend: ↑/↓/→)
- FID: [VALORE] (Trend: ↑/↓/→)
- CLS: [VALORE] (Trend: ↑/↓/→)

Performance:
- TTFB: [VALORE]
- FCP: [VALORE]
- TTI: [VALORE]

Traffic:
- Page Views: [VALORE] (Trend: ↑/↓/→)
- Unique Visitors: [VALORE] (Trend: ↑/↓/→)
- Bounce Rate: [VALORE] (Trend: ↑/↓/→)

Findings:
- [Finding 1]
- [Finding 2]

Actions:
- [Action 1]
- [Action 2]
```

---

## 🚨 ALERTING

### Critical Alerts:

- LCP > 4.0s
- FID > 300ms
- CLS > 0.25
- Error rate > 1%
- Uptime < 99%

### Warning Alerts:

- LCP > 2.5s
- FID > 100ms
- CLS > 0.1
- Error rate > 0.5%
- Performance degradation > 20%

---

## 🔧 OPTIMIZATION ACTIONS

### Se LCP Alto:

- ✅ Ottimizzare immagini (WebP/AVIF)
- ✅ Implementare lazy loading
- ✅ Preload risorse critiche
- ✅ Ottimizzare CSS/JS

### Se FID Alto:

- ✅ Ridurre JavaScript execution time
- ✅ Code splitting
- ✅ Lazy load non-critical JS
- ✅ Ottimizzare event handlers

### Se CLS Alto:

- ✅ Specificare dimensioni immagini
- ✅ Evitare inserimenti dinamici sopra viewport
- ✅ Usare font-display: swap
- ✅ Preload fonts

---

## 📝 DOCUMENTATION

### Logging:

- Documentare metriche settimanali
- Documentare regressioni
- Documentare ottimizzazioni applicate
- Documentare risultati

### Location:

- `docs/ai/WEEKLY_REPORT_YYYYMMDD.md` - Include analytics
- `docs/ai/PERFORMANCE_METRICS_YYYYMMDD.md` - Dettagli performance

---

## 🔗 LINKS UTILI

- Vercel Analytics: https://vercel.com/analytics
- Vercel Speed Insights: https://vercel.com/speed-insights
- Core Web Vitals: https://web.dev/vitals/
- Web Vitals Extension: https://chrome.google.com/webstore/detail/web-vitals/ahfhijdlegdabablpippeagghigmibma

---

## ✅ SUCCESS CRITERIA

### Daily:

- ✅ Core Web Vitals verificati
- ✅ Nessuna regressione critica
- ✅ Error rate stabile

### Weekly:

- ✅ Trends analizzati
- ✅ Regressioni identificate
- ✅ Ottimizzazioni pianificate

### Monthly:

- ✅ Performance migliorata o stabile
- ✅ Error rate ridotto o stabile
- ✅ User experience ottimizzata

---

**Last Updated:** 2026-01-13  
**Next Review:** Weekly
