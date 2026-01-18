# 🚀 Quick Test Guide - Performance Fixes

**Per testare rapidamente i fix applicati**

---

## ⚡ Quick Test (5 minuti)

### 1. Verifica Build

```bash
cd apps/mouth
npm run build
```

✅ **Expected:** Build completato senza errori

### 2. Verifica Virtualizzazione

**Test Rapido:**

1. Avvia dev server: `npm run dev`
2. Vai a `/clients`
3. Assicurati di avere 30+ clienti
4. Apri Chrome DevTools → Elements tab
5. Cerca `ClientCard` nel DOM
6. Scrolla la lista

✅ **Expected:** Solo ~6-12 `ClientCard` nel DOM (non tutti i 30+)

### 3. Verifica Memoizzazione

**Test Rapido:**

1. Vai a `/dashboard`
2. Apri React DevTools → Components
3. Seleziona un `StatsCard`
4. Abilita "Highlight updates"
5. Modifica qualcosa non correlato (es. apri menu)

✅ **Expected:** StatsCard NON si evidenziano (non re-renderizzano)

---

## 🔍 Verifica INP (Chrome DevTools)

1. Apri Chrome DevTools → Performance tab
2. Click "Record" (⚫)
3. Interagisci con `/clients` (scroll, click, hover)
4. Stop dopo 10 secondi
5. Guarda "Interaction to Next Paint" nel summary

✅ **Expected:** INP < 500ms (idealmente < 200ms)

---

## 📊 Verifica Memory

1. Apri Chrome DevTools → Memory tab
2. Vai a `/clients` con 100+ clienti
3. Heap snapshot prima scroll
4. Scrolla per 30 secondi
5. Heap snapshot dopo scroll

✅ **Expected:** Memory stabile, non aumenta durante scroll

---

## ✅ Checklist Rapida

- [ ] Build compila senza errori
- [ ] Virtualizzazione attiva con >30 clienti
- [ ] Solo items visibili nel DOM
- [ ] StatsCard non re-renderizzano inutilmente
- [ ] ClientCard non re-renderizzano inutilmente
- [ ] Drag & drop funziona in Kanban
- [ ] Scroll smooth (60fps)
- [ ] INP < 500ms
- [ ] Memory stabile

---

## 🐛 Se Qualcosa Non Funziona

1. **Virtualizzazione non attiva:**
   - Verifica di avere >20 clienti (Kanban) o >30 (Grid)
   - Controlla console per errori
   - Verifica che `@tanstack/react-virtual` sia installato

2. **Memoizzazione non funziona:**
   - Verifica React DevTools installato
   - Controlla che componenti siano esportati correttamente
   - Verifica che props non cambino ad ogni render

3. **Build errors:**
   - Verifica che tutte le dipendenze siano installate
   - Controlla TypeScript errors
   - Verifica import paths

---

**Tempo stimato:** 5-10 minuti  
**Difficoltà:** Media
