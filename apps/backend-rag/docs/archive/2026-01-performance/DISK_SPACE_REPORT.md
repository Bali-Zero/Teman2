# Disk Space Report - Mac

**Data:** 2026-01-16  
**Sistema:** macOS

---

## 💾 SPAZIO DISCO TOTALE

### Disco Principale (/)

- **Filesystem:** /dev/disk3s1s1
- **Dimensione Totale:** 228 GB
- **Spazio Usato:** 11 GB (41%)
- **Spazio Disponibile:** 17 GB
- **Status:** ✅ **SPAZIO SUFFICIENTE**

---

## 📁 SPAZIO PROGETTO NUZANTARA

### Dimensione Totale Progetto

- **Percorso:** ~/Desktop/nuzantara
- **Dimensione:** **8.5 GB**

### Distribuzione Spazio per Directory

| Directory       | Dimensione | % Totale |
| --------------- | ---------- | -------- |
| `apps/`         | 2.5 GB     | 29%      |
| `backups/`      | 1.5 GB     | 18%      |
| `node_modules/` | 1.3 GB     | 15%      |
| `logs/`         | 27 MB      | <1%      |
| Altri           | ~3.2 GB    | 38%      |

---

## 📂 ANALISI DETTAGLIATA

### Directory Apps (2.5 GB)

- `apps/backend-rag/` - Backend Python
- `apps/mouth/` - Frontend Next.js
- `apps/zantara-media/` - Media service
- Altri servizi

### Backend RAG Specifico

- `.venv/` - **588 MB** (virtual environment Python)
- Altri file backend

### Frontend Next.js

- `.next/` - **135 MB** (build cache)
- `node_modules/` - Dependencies

---

## 🗑️ CACHE E TEMPORANEI

### Cache Sistema (~7.5 GB totali)

#### Cache Library (~7.5 GB)

- **Yarn Cache:** 4.0 GB
- **Google Cache:** 2.6 GB
- **pnpm Cache:** 213 MB
- **pip Cache:** 135 MB
- **Playwright Cache:** 233 MB (ms-playwright-go + ms-playwright)
- Altri: ~300 MB

#### Cache Home (~1.3 GB)

- **Puppeteer Cache:** 1.0 GB
- **HuggingFace Cache:** 174 MB
- **Prisma Cache:** 78 MB
- **Node Cache:** 25 MB

---

## 🐳 DOCKER

### Docker System

- **Images:** 5.1 GB (20 immagini, 18 attive)
  - Reclaimable: 4.5 GB (88%)
- **Containers:** 1.4 MB (47 container, 28 attivi)
  - Reclaimable: 455 KB (32%)
- **Volumes:** 1.3 GB (23 volumi, 14 attivi)
  - Reclaimable: 486 MB (37%)

**Totale Docker:** ~6.4 GB  
**Reclaimable:** ~5.0 GB (78%)

---

## 📊 RIEPILOGO SPAZIO

### Spazio Usato per Categoria

| Categoria              | Dimensione | % Totale |
| ---------------------- | ---------- | -------- |
| **Progetto Nuzantara** | 8.5 GB     | 35%      |
| **Cache Sistema**      | ~7.5 GB    | 31%      |
| **Docker**             | ~6.4 GB    | 26%      |
| **Altri**              | ~2.0 GB    | 8%       |
| **TOTALE**             | ~24.4 GB   | 100%     |

---

## 💡 RACCOMANDAZIONI PER LIBERARE SPAZIO

### 1. Cache Yarn (4.0 GB) - Alta Priorità

```bash
yarn cache clean
```

**Risparmio potenziale:** ~4.0 GB

### 2. Docker Images Non Usate (4.5 GB) - Alta Priorità

```bash
docker system prune -a --volumes
```

**Risparmio potenziale:** ~4.5 GB

### 3. Cache Google (2.6 GB) - Media Priorità

```bash
# Pulizia manuale da ~/Library/Caches/Google
```

**Risparmio potenziale:** ~2.6 GB

### 4. Cache Puppeteer (1.0 GB) - Media Priorità

```bash
rm -rf ~/.cache/puppeteer
```

**Risparmio potenziale:** ~1.0 GB

### 5. Backups Progetto (1.5 GB) - Bassa Priorità

```bash
# Verificare se backups sono necessari
# Se non necessari, rimuovere ~/Desktop/nuzantara/backups
```

**Risparmio potenziale:** ~1.5 GB

### 6. Docker Volumes Non Usati (486 MB) - Media Priorità

```bash
docker volume prune
```

**Risparmio potenziale:** ~486 MB

---

## ✅ STATUS ATTUALE

### Spazio Disponibile

- **Disponibile:** 17 GB
- **Usato:** 11 GB (41%)
- **Status:** ✅ **SPAZIO SUFFICIENTE**

### Raccomandazioni

- ✅ **Spazio attuale sufficiente** per continuare il lavoro
- ⚠️ **Cache pulibili** se necessario (~7.5 GB)
- ⚠️ **Docker cleanup** se necessario (~5.0 GB)

---

## 🎯 AZIONI CONSIGLIATE

### Se Spazio < 10 GB Disponibile

1. Pulire cache Yarn (4.0 GB)
2. Pulire Docker images non usate (4.5 GB)
3. Pulire cache Google se non necessaria (2.6 GB)

### Se Spazio < 5 GB Disponibile

1. Tutte le azioni sopra
2. Pulire cache Puppeteer (1.0 GB)
3. Verificare e rimuovere backups non necessari (1.5 GB)

### Comandi Rapidi per Pulizia

```bash
# Pulizia completa cache e Docker
yarn cache clean
docker system prune -a --volumes
rm -rf ~/.cache/puppeteer

# Totale spazio liberabile: ~10 GB
```

---

**Status:** ✅ Spazio sufficiente (17 GB disponibili)  
**Raccomandazione:** Nessuna azione immediata necessaria
