# Advanced Cleanup Plan

**Data:** 2026-01-16  
**Obiettivo:** Pulire cache Chrome, Cursor, verificare MobileSync e Claude

---

## 📊 ANALISI INIZIALE

### 1. Chrome Cache (~4.5 GB)

- **Status:** ⚠️ Chrome è in esecuzione
- **OptGuideOnDeviceModel:** 4.0 GB (modelli AI)
- **Cache profili:** ~500 MB
- **Azione:** Chiudere Chrome prima di pulire

### 2. Cursor Cache (~373 MB)

- **logs:** 231 MB ✅ Pulibile
- **CachedData:** 99 MB ✅ Pulibile
- **CachedExtensionVSIXs:** 42 MB ✅ Pulibile
- **Cache:** 1.3 MB ✅ Pulibile
- **Totale:** ~373 MB

### 3. MobileSync Backup (~9 GB)

- **Backup attivo:** 9.0 GB (00008140-00011C523C41801C)
- **Backup vecchio:** 0B (00008120-000A5D183A9B401E) ✅ Può essere rimosso
- **Azione:** Verificare se backup attivo è necessario

### 4. Claude vm_bundles (~15 GB)

- **claudevm.bundle:** 15 GB
- **Azione:** Verificare se può essere rigenerato

---

## 🗑️ PIANO DI PULIZIA

### Fase 1: Cursor Cache (Sicura - ~373 MB)

✅ Può essere eseguita immediatamente

### Fase 2: Chrome Cache (~4.5 GB)

⚠️ Richiede chiusura Chrome

### Fase 3: MobileSync Backup Vecchio (0B)

✅ Può essere rimosso immediatamente

### Fase 4: Claude vm_bundles (~15 GB)

⚠️ Verificare prima se può essere rigenerato

---

## ⚠️ AVVERTENZE

1. **Chrome:** Deve essere chiuso completamente prima della pulizia
2. **MobileSync Backup Attivo:** Verificare se necessario prima di rimuovere
3. **Claude vm_bundles:** Potrebbe essere necessario per il funzionamento dell'app

---

**Status:** Analisi completata, pronto per esecuzione
