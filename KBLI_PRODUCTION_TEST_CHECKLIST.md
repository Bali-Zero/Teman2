# ✅ KBLI Navigator - Production Test Checklist

**Date:** 2026-02-16
**Deployment:** Commit `254c009f5` pushed to production
**Site:** https://zantara.balizero.com/kbli-navigator/

---

## 🧪 Test di Ricerca (Immediate)

### Test Inglese

Apri: **https://zantara.balizero.com/kbli-navigator/**

**Test Set 1 - Food & Hospitality:**

1. Cerca: `"restaurant"`
   - ✅ Dovrebbe trovare: **56101** (AKTIVITAS PENYEDIAAN MAKANAN)
   - ✅ Keywords dovrebbero includere: restaurant, cafe, dining, eatery

2. Cerca: `"hotel"`
   - ✅ Dovrebbe trovare: **55101** (AKTIVITAS HOTEL)
   - ✅ Keywords dovrebbero includere: hotel, accommodation, lodging

3. Cerca: `"cafe"`
   - ✅ Dovrebbe trovare: **56101** o codici simili
   - ✅ Risultati multipli con "cafe" nelle keywords

**Test Set 2 - Technology:** 4. Cerca: `"software"`

- ✅ Dovrebbe trovare: **62013** (AKTIVITAS PEMROGRAMAN KOMPUTER)
- ✅ Keywords dovrebbero includere: software, development, programming, coding

5. Cerca: `"IT"`
   - ✅ Dovrebbe trovare codici tech (62xxx)
   - ✅ Keywords dovrebbero includere: IT, technology, computer

6. Cerca: `"app development"`
   - ✅ Dovrebbe trovare: **62013** e codici correlati
   - ✅ Keywords dovrebbero includere: app, application, development

**Test Set 3 - Construction:** 7. Cerca: `"construction"`

- ✅ Dovrebbe trovare: **41001** e codici 41xxx
- ✅ Keywords dovrebbero includere: construction, building

8. Cerca: `"building"`
   - ✅ Dovrebbe trovare codici 41xxx
   - ✅ Risultati multipli nel settore costruzioni

**Test Set 4 - Business Services:** 9. Cerca: `"consulting"`

- ✅ Dovrebbe trovare codici 70xxx, 62xxx
- ✅ Keywords dovrebbero includere: consulting, advisory

10. Cerca: `"accounting"`
    - ✅ Dovrebbe trovare: **69200** (AKTIVITAS AKUNTANSI)
    - ✅ Keywords dovrebbero includere: accounting, bookkeeping

### Test Indonesiano (Verifica che non si è rotto)

11. Cerca: `"restoran"`
    - ✅ Dovrebbe trovare: **56101**
    - ✅ Risultati identici a prima

12. Cerca: `"teknologi"`
    - ✅ Dovrebbe trovare codici tech
    - ✅ Risultati identici a prima

13. Cerca: `"konstruksi"`
    - ✅ Dovrebbe trovare codici 41xxx
    - ✅ Risultati identici a prima

### Test Bilingue (Nuovo!)

14. Cerca: `"restaurant makanan"`
    - ✅ Dovrebbe trovare: **56101**
    - ✅ Match su entrambe le lingue

15. Cerca: `"software programming"`
    - ✅ Dovrebbe trovare: **62013**
    - ✅ Match su keywords inglesi combinate

---

## 🔍 Verifica Console (Immediate)

### Chrome DevTools

1. Apri: https://zantara.balizero.com/kbli-navigator/
2. Premi: `F12` (apri DevTools)
3. Vai su tab: **Console**

**Verifica:**

- ✅ **NESSUN errore rosso** (no `Uncaught Error`, `TypeError`, `ReferenceError`)
- ✅ Eventuali warnings gialli sono OK se pre-esistenti
- ✅ Verifica che `K array` sia caricato: digita `K.length` in console
  - Dovrebbe restituire: **1562**
- ✅ Verifica sample: digita `K[0]` in console
  - Dovrebbe mostrare array con 8 elementi: `["codice", "titolo", "sezione", ...]`

### Network Tab

1. Tab: **Network**
2. Ricarica pagina (`Ctrl+R` / `Cmd+R`)

**Verifica:**

- ✅ `index.html` caricato: Status **200**
- ✅ Dimensione file: ~**920KB** (non >2MB)
- ✅ Tempo caricamento: <**3s** per 4G
- ✅ No errori 404 o 500

---

## ⚡ Test Performance (Immediate)

### Search Speed Test

1. Apri console: digita questo codice e premi Enter:

```javascript
// Test velocità ricerca
const testSearch = (query) => {
  const start = performance.now();
  const results = K.filter(
    (item) => item[7] && item[7].toLowerCase().includes(query.toLowerCase()),
  );
  const end = performance.now();
  console.log(
    `Query: "${query}" | Results: ${results.length} | Time: ${(end - start).toFixed(2)}ms`,
  );
};

// Run tests
testSearch("restaurant");
testSearch("software");
testSearch("construction");
testSearch("hotel");
testSearch("restoran");
```

**Verifica:**

- ✅ Ogni ricerca dovrebbe essere: **<50ms**
- ✅ Risultati trovati per ogni query (>0)

### File Size Check

```javascript
// Verifica dimensione K array in memoria
const kbliDataSize = JSON.stringify(K).length;
console.log(`K array size: ${(kbliDataSize / 1024).toFixed(2)} KB`);
```

**Verifica:**

- ✅ Dimensione: **<2000 KB** (sotto 2MB)

---

## 📊 Metriche Attese

| Test           | Prima          | Dopo             | Status |
| -------------- | -------------- | ---------------- | ------ |
| "restaurant"   | ❌ 0 risultati | ✅ 56101 + altri | 🎯     |
| "software"     | ❌ 0 risultati | ✅ 62013 + altri | 🎯     |
| "hotel"        | ❌ 0 risultati | ✅ 55101 + altri | 🎯     |
| "construction" | ❌ 0 risultati | ✅ 41xxx         | 🎯     |
| "restoran"     | ✅ 56101       | ✅ 56101         | ✅     |
| "teknologi"    | ✅ Codici tech | ✅ Codici tech   | ✅     |
| Search speed   | -              | <50ms            | ⚡     |
| File size      | 810KB          | ~920KB           | ✅     |

---

## 📝 Report Risultati

Dopo aver completato i test, rispondi a queste domande:

### ✅ Tutto OK?

- [ ] Tutti i 15 test di ricerca passano
- [ ] Nessun errore in console
- [ ] Performance <50ms per ricerca
- [ ] File size <2MB

### ⚠️ Problemi Trovati?

Se qualcosa non funziona:

1. Nota quale test è fallito
2. Screenshot dell'errore in console
3. Controlla `Network` tab per verificare che `index.html` sia la versione nuova
4. Prova `Ctrl+Shift+R` (hard refresh) per bypassare cache browser

### 📸 Evidence (Opzionale)

- Screenshot di 2-3 ricerche inglesi funzionanti
- Screenshot console senza errori
- Screenshot Network tab con file size

---

## 🕐 Monitoring 24-48h (Short-term)

### Vercel Logs

1. Vai a: https://vercel.com/dashboard
2. Seleziona progetto: `mouth` (frontend)
3. Tab: **Logs**

**Monitora:**

- ✅ No errori 500 (Server Error)
- ✅ No picchi di errori 404
- ✅ Response time stabile (<3s)

### User Feedback

Raccogli feedback da:

- 🧪 Team interno che testa
- 👥 Early adopters / beta users
- 📊 Analytics (se disponibile)

**Domande chiave:**

- Le ricerche inglesi funzionano?
- Ci sono termini inglesi che non trovano risultati?
- La velocità è accettabile?
- Ci sono errori visualizzati?

### Performance Monitoring

Controlla (se disponibili):

- Google Analytics: Bounce rate su `/kbli-navigator/`
- Search queries più frequenti
- Tempo medio sulla pagina
- Device breakdown (mobile vs desktop)

---

## ✅ Success Criteria

**Deployment OK se:**

1. ✅ Almeno 12/15 test di ricerca passano
2. ✅ 0 errori critici in console
3. ✅ Performance search <50ms (media)
4. ✅ File caricato correttamente (920KB)
5. ✅ Funzionalità indonesiana intatta

**Metriche target 24-48h:**

- ✅ English search success rate: >90%
- ✅ User feedback positivo
- ✅ No bug reports critici
- ✅ Vercel logs puliti

---

## 🚨 Troubleshooting

### Problema: Keywords inglesi non presenti

**Causa:** Cache CDN non ancora propagata
**Fix:** Aspetta altri 5-10 min, poi hard refresh (`Ctrl+Shift+R`)

### Problema: Errore "K is not defined"

**Causa:** JavaScript non caricato correttamente
**Fix:** Verifica Network tab, ricarica pagina

### Problema: Search troppo lenta (>100ms)

**Causa:** Array troppo grande o browser lento
**Fix:** Verifica su device diversi, considera ottimizzazione algoritmo

### Problema: Ricerche indonesiane rotte

**Causa:** Keywords sovrascrittemal formatted
**Fix:** ROLLBACK immediato! Contatta team

---

**Prepared by:** Claude Sonnet 4.5
**Test Duration:** ~15-20 minuti
**Priority:** HIGH - Completare entro 1 ora dal deployment

**🎯 Obiettivo: Confermare che il deployment è 100% funzionante prima di dichiarare vittoria!**
