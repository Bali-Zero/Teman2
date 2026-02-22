# 🔄 Cache Clearing Instructions

## ⚠️ PROBLEMA: La card mostra ancora "High Risk"

**Causa**: Il tuo browser sta mostrando la versione OLD in cache.

**Soluzione**: Devi fare un **hard refresh** per forzare il browser a ricaricare il file aggiornato.

---

## 🖥️ Come fare Hard Refresh

### Su Mac:

```
Cmd + Shift + R
```

oppure

```
Cmd + Option + R
```

### Su Windows/Linux:

```
Ctrl + Shift + R
```

oppure

```
Ctrl + F5
```

---

## ✅ Verifica che funziona

Dopo il hard refresh, testa questi codici:

1. **Search "01111"** → Dovrebbe mostrare badge **Medium Risk** (non High)
2. **Search "62191"** → Dovrebbe mostrare badge **Medium Risk** (non High)
3. **Search "56101"** → Dovrebbe mostrare badge **High Risk** (corretto)

4. **Code Finder filters**:
   - Low Risk: (425) codes
   - Medium Risk: (386) codes
   - High Risk: (751) codes

---

## 🔧 Se Hard Refresh non funziona

### Opzione 1: Clear Browser Cache Manualmente

**Chrome/Edge**:

1. Apri DevTools (F12)
2. Right-click sul pulsante Refresh
3. Scegli "Empty Cache and Hard Reload"

**Safari**:

1. Safari → Settings → Advanced
2. Check "Show Develop menu"
3. Develop → Empty Caches
4. Poi refresh (Cmd+R)

**Firefox**:

1. Ctrl+Shift+Delete (Cmd+Shift+Delete su Mac)
2. Select "Cached Web Content"
3. Click "Clear Now"

### Opzione 2: Apri in Incognito/Private Window

1. Apri finestra incognito/private
2. Trascina il file HTML nella finestra
3. Testa i codici sopra

---

## 📊 Database VERIFICATO Corretto

Il database è stato verificato con script Python:

- ✅ Totale: 1,562 codici
- ✅ Low Risk: 425 (27.2%)
- ✅ Medium Risk: 386 (24.7%)
- ✅ High Risk: 751 (48.1%)

Spot checks:

- ✅ 01111 (Agricultura) → Medium Risk
- ✅ 62191 (IT E-commerce) → Medium Risk
- ✅ 56101 (Restaurant) → High Risk

Il problema è SOLO la cache del browser!

---

**File verificati**:

- `/app/kbli-navigator-premium.html` ✅
- `/deploy/ready-to-deploy/index.html` ✅

Entrambi hanno il database corretto.
