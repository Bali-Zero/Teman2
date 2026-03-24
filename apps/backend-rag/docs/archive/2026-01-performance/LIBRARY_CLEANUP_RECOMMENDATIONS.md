# Library Cleanup Recommendations

**Data:** 2026-01-16  
**Library Totale:** 85 GB  
**Obiettivo:** Identificare cosa pulire per liberare spazio

---

## 📊 ANALISI LIBRARY (85 GB)

### Distribuzione per Directory Principale

| Directory               | Dimensione | % Totale | Pulibile?    |
| ----------------------- | ---------- | -------- | ------------ |
| **Application Support** | 61 GB      | 72%      | Parzialmente |
| **Containers**          | 10 GB      | 12%      | Parzialmente |
| **Caches**              | 5.2 GB     | 6%       | ✅ Sì        |
| **Mobile Documents**    | 4.7 GB     | 6%       | ⚠️ Attento   |
| **Altri**               | ~4 GB      | 5%       | Variabile    |

---

## 🗑️ PULIZIA CONSIGLIATA (Priorità Alta)

### 1. Cache Yarn (4.0 GB) ✅ SICURO

**Percorso:** `~/Library/Caches/Yarn`  
**Rischio:** Nessuno  
**Comando:**

```bash
yarn cache clean
```

**Spazio Liberabile:** 4.0 GB

---

### 2. Docker Images Non Usate (4.5 GB) ✅ SICURO

**Percorso:** `~/Library/Containers/com.docker.docker`  
**Rischio:** Nessuno (solo immagini non usate)  
**Comando:**

```bash
docker system prune -a --volumes
```

**Spazio Liberabile:** ~4.5 GB

**Nota:** Questo rimuove solo immagini/container/volumi non usati. I dati attivi rimangono.

---

### 3. Cache Chrome (5.7 GB) ⚠️ ATTENTO

**Percorso:** `~/Library/Application Support/Google/Chrome`  
**Dettaglio:**

- `OptGuideOnDeviceModel`: 4.0 GB (modelli AI Chrome - può essere pulito)
- `Default`: 403 MB (profilo principale - cache)
- Altri profili: ~600 MB

**Rischio:** Basso (cache viene rigenerata)  
**Comando:**

```bash
# Chiudere Chrome prima
rm -rf ~/Library/Application\ Support/Google/Chrome/OptGuideOnDeviceModel/*
rm -rf ~/Library/Application\ Support/Google/Chrome/*/Cache/*
rm -rf ~/Library/Application\ Support/Google/Chrome/*/Code\ Cache/*
```

**Spazio Liberabile:** ~4.5 GB (modelli AI + cache)

**Nota:** I modelli AI vengono scaricati di nuovo quando necessario.

---

### 4. MobileSync Backup (9.0 GB) ⚠️ ATTENTO

**Percorso:** `~/Library/Application Support/MobileSync`  
**Rischio:** Medio (backup iPhone/iPad)  
**Spazio Liberabile:** ~9.0 GB

**Raccomandazione:**

- Verificare se hai backup recenti su iCloud
- Se sì, puoi rimuovere backup vecchi
- Se no, **NON rimuovere** (sono i tuoi backup)

---

### 5. Cache Cursor (3.7 GB) ⚠️ ATTENTO

**Percorso:** `~/Library/Application Support/Cursor`  
**Dettaglio:**

- `User`: 3.2 GB (dati utente - NON rimuovere)
- `logs`: 223 MB (log - può essere pulito)
- `CachedData`: 99 MB (cache - può essere pulito)
- `CachedExtensionVSIXs`: 42 MB (cache estensioni - può essere pulito)
- Altri: ~100 MB

**Rischio:** Basso (solo cache e log)  
**Comando:**

```bash
# Solo cache e log, NON User
rm -rf ~/Library/Application\ Support/Cursor/logs/*
rm -rf ~/Library/Application\ Support/Cursor/CachedData/*
rm -rf ~/Library/Application\ Support/Cursor/CachedExtensionVSIXs/*
rm -rf ~/Library/Application\ Support/Cursor/Cache/*
```

**Spazio Liberabile:** ~400 MB (cache e log)

**Nota:** NON rimuovere la directory `User` (contiene configurazioni).

---

## 🗑️ PULIZIA CONSIGLIATA (Priorità Media)

### 6. Cache pnpm (213 MB) ✅ SICURO

**Percorso:** `~/Library/Caches/pnpm`  
**Comando:**

```bash
pnpm store prune
```

**Spazio Liberabile:** ~200 MB

---

### 7. Cache pip (135 MB) ✅ SICURO

**Percorso:** `~/Library/Caches/pip`  
**Comando:**

```bash
pip cache purge
```

**Spazio Liberabile:** ~135 MB

---

### 8. Cache Playwright (233 MB) ✅ SICURO

**Percorso:** `~/Library/Caches/ms-playwright*`  
**Comando:**

```bash
rm -rf ~/Library/Caches/ms-playwright*
```

**Spazio Liberabile:** ~233 MB

**Nota:** I browser Playwright verranno scaricati di nuovo quando necessario.

---

### 9. Cache Homebrew (73 MB) ✅ SICURO

**Percorso:** `~/Library/Caches/Homebrew`  
**Comando:**

```bash
brew cleanup --prune=all
```

**Spazio Liberabile:** ~73 MB

---

### 10. Logs (44 MB) ✅ SICURO

**Percorso:** `~/Library/Logs`  
**Comando:**

```bash
rm -rf ~/Library/Logs/*/*
```

**Spazio Liberabile:** ~44 MB

**Nota:** I log vengono rigenerati automaticamente.

---

## ⚠️ NON RIMUOVERE (Dati Importanti)

### CloudDocs (16 GB)

**Percorso:** `~/Library/Application Support/CloudDocs`  
**Dettaglio:**

- `session`: 16 GB (sessioni iCloud Drive)
  **Contiene:** File iCloud Drive  
  **Azione:** ❌ **NON RIMUOVERE** (sono i tuoi file iCloud)

### Claude (15 GB)

**Percorso:** `~/Library/Application Support/Claude`  
**Dettaglio:**

- `vm_bundles`: 14 GB (bundle VM - cache)
- `local-agent-mode-sessions`: 204 MB (sessioni locali)
- `claude-code-vm`: 203 MB (VM code)
- Altri: ~600 MB

**Contiene:** Dati app Claude AI  
**Azione:** ⚠️ **Verificare prima**

- `vm_bundles` potrebbe essere cache pulibile (~14 GB)
- Sessioni locali potrebbero essere importanti
- **Raccomandazione:** Verificare se `vm_bundles` può essere rigenerato

### FileProvider (6.7 GB)

**Percorso:** `~/Library/Application Support/FileProvider`  
**Contiene:** File provider dati  
**Azione:** ❌ **NON RIMUOVERE**

### Google DriveFS (1.8 GB)

**Percorso:** `~/Library/Application Support/Google/DriveFS`  
**Contiene:** File Google Drive  
**Azione:** ❌ **NON RIMUOVERE**

---

## 📊 RIEPILOGO PULIZIA

### Pulizia Sicura (Totale: ~9 GB)

1. ✅ Cache Yarn: 4.0 GB
2. ✅ Docker non usato: 4.5 GB
3. ✅ Cache pnpm: 213 MB
4. ✅ Cache pip: 135 MB
5. ✅ Cache Playwright: 233 MB
6. ✅ Cache Homebrew: 73 MB
7. ✅ Logs: 44 MB

**Totale Sicuro:** ~9.2 GB

### Pulizia con Verifica (Totale: ~18 GB)

1. ⚠️ Cache Chrome: ~4.5 GB (modelli AI + cache)
2. ⚠️ Cache Cursor: ~400 MB (solo cache, non User)
3. ⚠️ MobileSync: ~9 GB (solo se hai backup su iCloud)
4. ⚠️ Claude vm_bundles: ~14 GB (verificare se cache)

**Totale con Verifica:** ~18-27 GB

---

## 🎯 RACCOMANDAZIONI FINALI

### Pulizia Immediata (Sicura)

```bash
# 1. Cache Yarn
yarn cache clean

# 2. Docker non usato
docker system prune -a --volumes

# 3. Cache pnpm
pnpm store prune

# 4. Cache pip
pip cache purge

# 5. Cache Playwright
rm -rf ~/Library/Caches/ms-playwright*

# 6. Cache Homebrew
brew cleanup --prune=all

# 7. Logs
rm -rf ~/Library/Logs/*/*
```

**Spazio Liberabile:** ~9.2 GB

### Pulizia Chrome Cache (Dopo chiusura Chrome)

```bash
# Chiudere Chrome completamente prima
rm -rf ~/Library/Application\ Support/Google/Chrome/OptGuideOnDeviceModel/*
rm -rf ~/Library/Application\ Support/Google/Chrome/*/Cache/*
rm -rf ~/Library/Application\ Support/Google/Chrome/*/Code\ Cache/*
```

**Spazio Liberabile:** ~4.5 GB

### Pulizia Cursor Cache (Sicura)

```bash
# Solo cache e log, NON User
rm -rf ~/Library/Application\ Support/Cursor/logs/*
rm -rf ~/Library/Application\ Support/Cursor/CachedData/*
rm -rf ~/Library/Application\ Support/Cursor/CachedExtensionVSIXs/*
rm -rf ~/Library/Application\ Support/Cursor/Cache/*
```

**Spazio Liberabile:** ~400 MB

### Pulizia con Verifica (Dopo controllo)

1. Verificare contenuto Chrome cache
2. Verificare contenuto Cursor cache
3. Verificare se hai backup iCloud prima di rimuovere MobileSync

---

## ✅ PROSSIMI PASSI

1. ⏳ Eseguire pulizia sicura (~9 GB)
2. ⏳ Verificare Chrome e Cursor cache
3. ⏳ Decidere su MobileSync backup

---

**Status:** Analisi completata  
**Spazio Liberabile (Sicuro):** ~9.2 GB  
**Spazio Liberabile (Con Verifica):** ~12-15 GB
