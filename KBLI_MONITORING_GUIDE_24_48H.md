# 📊 KBLI Phase 1 - Monitoring Guide (24-48h)

**Date:** 2026-02-16
**Duration:** 24-48 hours post-deployment
**Status:** MONITORING ACTIVE

---

## 📈 Vercel Dashboard Monitoring

### Setup

1. Vai a: **https://vercel.com/dashboard**
2. Login con account Bali Zero
3. Seleziona project: **mouth** (Nuzantara frontend)
4. Bookmark questa pagina per accesso rapido

### Metriche da Monitorare

#### 1. Deployments Tab

**URL:** `https://vercel.com/[username]/mouth/deployments`

**Verifica:**

- ✅ Latest deployment: Commit `254c009f5`
- ✅ Status: **Ready** (verde)
- ✅ Domain: `zantara.balizero.com`
- ✅ Build time: Normale (~2-5 min)

**Alert se:**

- ❌ Status: Failed (rosso)
- ❌ Build errors nel log
- ❌ Deployment rolled back

#### 2. Logs Tab

**URL:** `https://vercel.com/[username]/mouth/logs`

**Monitora ogni 6-8 ore:**

**Filtri da usare:**

```
Status: All
Time: Last 24 hours
```

**Cerca pattern problematici:**

```
❌ "Error: Failed to fetch"
❌ "TypeError"
❌ "500 Internal Server Error"
❌ "Out of memory"
❌ "KBLI" + "error"
❌ "undefined is not a function"
```

**Accettabili (ignora):**

```
✅ "404" per asset non critici
✅ "Warning" non bloccanti
✅ Bot/crawler requests
```

**Azioni:**

- Se 0-5 errori/ora: ✅ OK, continua monitoring
- Se 6-20 errori/ora: ⚠️ Investiga pattern
- Se >20 errori/ora: 🚨 ALERT - possibile problema

#### 3. Analytics Tab (se abilitato)

**URL:** `https://vercel.com/[username]/mouth/analytics`

**Metriche chiave:**

| Metric              | Target   | Alert if        |
| ------------------- | -------- | --------------- |
| Requests/hour       | 10-1000+ | <5 (site down?) |
| 2xx Success %       | >95%     | <90%            |
| 4xx Client Errors % | <3%      | >10%            |
| 5xx Server Errors % | 0%       | >1%             |
| Avg Response Time   | <2s      | >5s             |

**Focus su:**

- `/kbli-navigator/` route specificamente
- Device breakdown (mobile vs desktop)
- Geography (Indonesia traffic)

---

## 🐛 Error Pattern Detection

### Daily Check (ogni 24h)

**Script di ricerca (Vercel Logs):**

```bash
# Se hai Vercel CLI installato:
vercel logs --app mouth --since 24h | grep -i "error\|exception\|failed"
```

**Oppure via Dashboard:**

1. Logs tab
2. Filter: "Last 24 hours"
3. Search box: `error OR exception OR failed`

### Classificazione Errori

#### 🔴 CRITICAL (Fix immediato richiesto)

- JavaScript errors che bloccano search
- "K is not defined"
- "Cannot read property of undefined" in search function
- 50x errors in produzione
- Complete site down

**Azione:** Rollback immediato o hotfix entro 1 ora

#### 🟡 WARNING (Monitora e pianifica fix)

- Slowdown performance (>200ms per search)
- Specific keyword searches failing
- 40x errors su risorse non critiche
- Browser-specific errors (solo IE, etc.)

**Azione:** Create GitHub issue, fix entro 24-48h

#### 🟢 INFO (Log normale, no action)

- Crawler/bot 404s
- Asset cache misses
- Deprecation warnings
- Analytics tracking fails

**Azione:** None, continua monitoring

---

## 👥 User Feedback Collection

### Fonti Feedback

#### 1. Direct Channels

- **Email:** support@balizero.com
- **WhatsApp:** Team Bali Zero
- **Slack:** #nuzantara-feedback (se disponibile)

#### 2. Analytics (indiretti)

- **Bounce rate:** Alta su `/kbli-navigator/` = problema
- **Time on page:** Bassa = ricerca non funziona
- **Search queries:** Pattern di ricerche fallite

#### 3. Internal Testing

Chiedi a 3-5 colleghi di testare:

- "Prova a cercare [tech/food/construction] terms in inglese"
- "C'è qualcosa che non funziona?"
- "Velocità accettabile?"

### Domande Chiave per Users

**Template messaggio:**

```
Ciao! 👋

Abbiamo aggiornato KBLI Navigator con supporto inglese.

Puoi testare e darci feedback?
🔗 https://zantara.balizero.com/kbli-navigator/

Test rapido:
1. Cerca "software" o "restaurant"
2. Funziona? Veloce?
3. Problemi?

Grazie! 🙏
```

### Feedback Log

Registra in: `apps/mouth/scripts/PHASE_1_USER_FEEDBACK.txt`

**Format:**

```
Date: 2026-02-16 15:30
User: [Nome/ID]
Feedback: [Cosa dice]
Category: [BUG / FEATURE / PRAISE / QUESTION]
Priority: [HIGH / MEDIUM / LOW]
Action: [Fix needed / Note for future / Resolved]
```

---

## ⚡ Performance Monitoring

### Response Time Tracking

**Metodo 1: Vercel Analytics**

- Vai su Analytics tab
- Filtra per `/kbli-navigator/` route
- Verifica "Time to First Byte" (TTFB)

**Target:**

- ✅ TTFB: <500ms (p50)
- ✅ TTFB: <2s (p95)
- ⚠️ Se >3s: investiga (cache? size? server?)

**Metodo 2: Browser DevTools (spot check)**

```javascript
// In console su https://zantara.balizero.com/kbli-navigator/
performance.timing.loadEventEnd - performance.timing.navigationStart;
```

**Target:** <3000ms (3 secondi)

### Client-Side Search Performance

**Test manuale (ogni 24h):**

1. Apri site in produzione
2. Apri console
3. Run:

```javascript
// Performance test
const perfTest = () => {
  const queries = ["restaurant", "software", "hotel", "construction", "cafe"];
  queries.forEach((q) => {
    const start = performance.now();
    const results = K.filter(
      (item) => item[7] && item[7].toLowerCase().includes(q.toLowerCase()),
    );
    const time = performance.now() - start;
    console.log(`${q}: ${results.length} results in ${time.toFixed(2)}ms`);
  });
};
perfTest();
```

**Target:**

- ✅ <50ms per query (average)
- ✅ >0 results per query testata

**Alert se:**

- ⚠️ >100ms per query
- ❌ 0 results per query comune

### File Size Check

**Vercel Dashboard:**

- Deployments > Latest > Function Logs
- Cerca "Static file size" o simile

**Browser Check:**

```javascript
// Console in produzione
fetch("/kbli-navigator/")
  .then((r) => r.text())
  .then((html) => {
    console.log(`HTML size: ${(html.length / 1024).toFixed(2)} KB`);
  });
```

**Target:** 800-1000 KB (accettabile)
**Alert se:** >2000 KB (troppo grande)

---

## 📊 Success Metrics Dashboard

### Create Tracking Sheet

**Google Sheets o simile:**

| Date       | Time  | Vercel Errors | User Reports | Avg Response | Search Performance | Notes             |
| ---------- | ----- | ------------- | ------------ | ------------ | ------------------ | ----------------- |
| 2026-02-16 | 14:00 | 0             | 0            | 1.2s         | 35ms               | Initial deploy ✅ |
| 2026-02-16 | 20:00 | ?             | ?            | ?            | ?                  | Evening check     |
| 2026-02-17 | 09:00 | ?             | ?            | ?            | ?                  | Morning check     |
| 2026-02-17 | 20:00 | ?             | ?            | ?            | ?                  | 24h post-deploy   |
| 2026-02-18 | 09:00 | ?             | ?            | ?            | ?                  | 48h check         |

### Traffic Patterns

**Expected:**

- **Day 1:** Normal traffic, early adopters testing
- **Day 2:** Potential increase if word spreads
- **Week 1:** Stable patterns emerge

**Anomalies da notare:**

- Spike inatteso (viral? bug exploit?)
- Drop improvviso (site down? search broken?)
- Geographic anomalies (all from one country?)

---

## 🚨 Alert Thresholds

### RED ALERT 🔴 (Immediate Action)

Trigger se:

- > 50 errors/hour in Vercel logs
- Complete search failure (JavaScript error)
- Site down (DNS/server error)
- > 5 critical user reports in 2 hours

**Action:**

1. Immediate rollback consideration
2. Alert team lead
3. Debug priority #1
4. Status page update (if public-facing)

### YELLOW ALERT 🟡 (Investigate Soon)

Trigger se:

- 10-50 errors/hour
- Search performance degraded (>100ms avg)
- 2-5 user bug reports
- Specific browser issues

**Action:**

1. Log issue in GitHub
2. Schedule fix within 24-48h
3. Continue monitoring
4. Notify team

### GREEN STATUS ✅ (All Good)

Indicators:

- <10 errors/24h
- 0 user complaints
- Performance within targets
- Normal traffic patterns

**Action:**

- Continue routine monitoring
- Document success
- Celebrate! 🎉

---

## 📝 Daily Report Template

**Send to team ogni 24h:**

```markdown
## KBLI Phase 1 - Daily Report [Date]

### Status: ✅ GREEN / 🟡 YELLOW / 🔴 RED

### Metrics (Last 24h)

- Vercel Errors: [X] (target: <10)
- User Reports: [X bugs, Y feedback] (target: <3 bugs)
- Avg Response Time: [X]s (target: <2s)
- Search Performance: [X]ms (target: <50ms)
- Traffic: [X] requests (baseline: [Y])

### Issues Found

1. [Issue description] - Priority: [H/M/L] - Status: [Open/Fixed]
2. ...

### User Feedback Highlights

- [Positive feedback summary]
- [Feature requests]
- [Bug reports]

### Actions Taken

- [Any fixes deployed]
- [Investigations started]
- [Issues closed]

### Next 24h Plan

- [Monitoring continues]
- [Scheduled checks]
- [Pending fixes]

### Overall Assessment

[2-3 sentences summary: Is Phase 1 stable? Any concerns? Recommendations?]

---

Report by: [Your Name]
Next report: [Date + Time]
```

---

## ✅ 48h Completion Checklist

**Dopo 48 ore, verifica:**

- [ ] Zero errori critici in Vercel logs
- [ ] <10 errori totali (di qualsiasi tipo)
- [ ] Zero user reports di search non funzionante
- [ ] Performance media <50ms search
- [ ] Response time <2s (p95)
- [ ] Traffic patterns normali
- [ ] Almeno 5 feedback positivi raccolti
- [ ] Nessun rollback richiesto
- [ ] Team satisfied con risultati

**Se tutti checkbox ✅:**
→ **PHASE 1 OFFICIALLY SUCCESS!** 🎉
→ Chiudi monitoring intensivo
→ Switch a routine monitoring (weekly)

**Se qualche checkbox ❌:**
→ Estendi monitoring di 24-48h
→ Fix issues trovati
→ Re-valuta dopo fix

---

## 📚 Resources

**Vercel Docs:**

- Logs: https://vercel.com/docs/observability/logging
- Analytics: https://vercel.com/docs/analytics
- Monitoring: https://vercel.com/docs/observability/monitoring

**Internal:**

- KBLI Guide: `FASE_1_ENGLISH_KEYWORDS_GUIDE.md`
- Test Checklist: `KBLI_PRODUCTION_TEST_CHECKLIST.md`
- Scripts: `apps/mouth/scripts/`

**Contacts:**

- Team Lead: [Name/Email]
- DevOps: [Contact]
- Support: support@balizero.com

---

**Prepared by:** Claude Sonnet 4.5
**Monitoring Start:** 2026-02-16 (deployment date)
**Monitoring End:** 2026-02-18 (48h later)

**🎯 Goal: Confirm stable production deployment with zero critical issues!**
