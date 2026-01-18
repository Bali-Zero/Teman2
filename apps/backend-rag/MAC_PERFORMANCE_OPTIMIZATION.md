# Mac Performance Optimization

**Data:** 2026-01-16  
**Sistema:** macOS 26.2 (Darwin 25.2.0)  
**Hardware:** 10-core CPU, 16 GB RAM

---

## 📊 ANALISI PERFORMANCE

### Stato Attuale

| Metrica          | Valore                        | Status               |
| ---------------- | ----------------------------- | -------------------- |
| **CPU Usage**    | 63% user, 33% sys, 3.6% idle  | ⚠️ ALTO              |
| **Load Average** | 5.79, 5.91, 7.30              | ⚠️ ALTO (su 10 core) |
| **RAM Usata**    | 11.2 GB / 11.3 GB (99%)       | 🔴 CRITICO           |
| **RAM Libera**   | 98 MB                         | 🔴 CRITICO           |
| **Compressor**   | Attivo (~15.4 GB compressi!)  | 🔴 CRITICO           |
| **Spazio Disco** | 10 GB disponibili (54% usato) | ✅ OK                |

---

## 🚨 PROBLEMI IDENTIFICATI

### 1. RAM Critica (94% usata) 🔴

**Problema:**

- Solo 98 MB RAM libera (99% usata!)
- ~15.4 GB compressi (swap massivo!)
- Sistema in crisi di memoria

**Processi che Consumano Più RAM:**

- `com.apple.Virtualization.VirtualMachine` (PID 48375): ~4.1 GB + compressi
- `com.apple.Virtualization.VirtualMachine` (PID 2026): ~6.5 GB
- `Cursor Helper`: 709 MB
- 25 processi npm/node attivi: ~2-3 GB
- Altri processi: ~2-3 GB

**Impatto:** Sistema molto lento, swap massivo, possibili freeze, applicazioni che crashano

---

### 2. CPU Alta (96% utilizzata) ⚠️

**Problema:**

- Solo 3.6% CPU idle
- Load average alto (5.79-7.30 su 10 core)

**Top Processi CPU:**

- `VirtualMachine` (PID 2026): 196% CPU
- `npm` (PID 61132): 77.9% CPU
- `npm` (PID 61144): 75.9% CPU
- `npm` (PID 61154): 72.2% CPU
- `cursor-agent`: 60.6% CPU
- `Claude`: 55.3% CPU
- `VirtualMachine` (PID 48375): 42.8% CPU

**Impatto:** Sistema responsivo ma sotto carico

---

### 3. Processi npm Multipli ⚠️

**Problema:**

- **25 processi npm/node attivi!**
- 3 processi npm principali consumano 70-80% CPU ciascuno
- Probabilmente build/test in esecuzione o processi zombie

**Impatto:** CPU saturata, batteria consumata rapidamente, RAM consumata

**Azione Urgente:** Verificare e terminare processi npm non necessari

---

### 4. Virtual Machine Attive (2 VM) ⚠️

**Problema:**

- 2 VM attive contemporaneamente
- Consumano ~10.6 GB RAM totale
- Una VM "stuck" (PID 48375)

**Impatto:** Consumo massivo di RAM e CPU

---

## ✅ OTTIMIZZAZIONI IMMEDIATE

### 1. Liberare RAM (Priorità Alta) 🔴

#### A. Chiudere VM Non Necessarie

```bash
# Verificare VM attive
ps aux | grep VirtualMachine

# Se necessario, chiudere VM non usate
# (Chiudere manualmente dall'app Virtualization o Activity Monitor)
```

**Spazio Liberabile:** ~10 GB RAM

#### B. Pulizia Memoria (Richiede sudo)

```bash
# Purge memoria (richiede password)
sudo purge
```

**Effetto:** Libera memoria compressa e cache

#### C. Chiudere App Non Necessarie

- Claude (55% CPU, ~700 MB RAM)
- Processi npm non necessari
- Chrome/Safari con molte tab aperte

---

### 2. Gestire Processi npm ⚠️

#### A. Identificare Processi npm

```bash
ps aux | grep npm | grep -v grep
```

#### B. Terminare Processi Non Necessari

```bash
# Se sono build/test completati
kill <PID>
```

**Spazio Liberabile:** ~225% CPU (3 processi)

---

### 3. Ottimizzare Launch Agents

#### Launch Agents Attivi:

- `com.user.docker-health-check`
- `com.user.ram-monitor`
- `com.user.disk-space-monitor`
- `com.user.git-auto-backup`
- `com.user.weekly-cleanup`
- `com.cloudflare.cloudflared`
- `us.zoom.updater`
- `com.dropbox.DropboxUpdater.wake`

**Raccomandazione:**

- Disabilitare agent non critici se non necessari
- Verificare frequenza di esecuzione

---

### 4. Pulizia Cache

#### Cache da Pulire:

| Cache            | Dimensione | Azione   |
| ---------------- | ---------- | -------- |
| CloudKit         | 265 MB     | Pulibile |
| ms-playwright-go | 127 MB     | Pulibile |
| us.zoom.xos      | 73 MB      | Pulibile |
| node-gyp         | 64 MB      | Pulibile |
| Homebrew         | 52 MB      | Pulibile |

**Totale:** ~580 MB

**Comando:**

```bash
rm -rf ~/Library/Caches/CloudKit/*
rm -rf ~/Library/Caches/ms-playwright-go/*
rm -rf ~/Library/Caches/us.zoom.xos/*
rm -rf ~/Library/Caches/node-gyp/*
brew cleanup --prune=all
```

---

### 5. Ottimizzazioni Sistema

#### A. Power Management

**Stato Attuale:**

- Sleep: 0 (prevenuto da Electron, nsurlsessiond, powerd)
- Display Sleep: 30 minuti
- Disk Sleep: 0

**Raccomandazione:**

- Verificare perché sleep è prevenuto
- Considerare impostare sleep più aggressivo se non necessario

#### B. File System

**Stato:** ✅ OK (10 GB disponibili, 54% usato)

---

## 🎯 PIANO DI OTTIMIZZAZIONE

### Fase 1: Azioni Immediate (Liberare RAM)

1. ✅ Chiudere VM non necessarie (~10 GB RAM)
2. ✅ Terminare processi npm non necessari (~225% CPU)
3. ✅ Chiudere app non necessarie (Claude, Chrome tab extra)
4. ⏳ Eseguire `sudo purge` (richiede password)

**Risultato Atteso:**

- RAM libera: Da 403 MB a ~10+ GB
- CPU idle: Da 3.6% a ~30-40%
- Load average: Da 5.79 a ~2-3

---

### Fase 2: Pulizia e Manutenzione

1. ⏳ Pulire cache applicazioni (~580 MB)
2. ⏳ Verificare Launch Agents non necessari
3. ⏳ Ottimizzare power management

**Risultato Atteso:**

- Cache ridotte
- Meno processi in background
- Migliore gestione batteria

---

### Fase 3: Monitoraggio Continuo

1. ⏳ Monitorare RAM usage
2. ⏳ Monitorare CPU usage
3. ⏳ Verificare processi pesanti

---

## 📋 COMANDI UTILI

### Monitoraggio Performance

```bash
# CPU e RAM in tempo reale
top -l 1 -o cpu
top -l 1 -o mem

# Memoria dettagliata
vm_stat

# Processi per CPU
ps aux | awk '{if ($3 > 10.0) print $3"% CPU - "$11" - "$2}' | sort -rn

# Processi per Memoria
ps aux | awk '{if ($4 > 5.0) print $4"% MEM - "$11" - "$2}' | sort -rn

# Load average
uptime
```

### Pulizia Memoria

```bash
# Purge memoria (richiede sudo)
sudo purge

# Verificare memoria dopo purge
vm_stat
```

### Gestione Processi

```bash
# Trovare processi pesanti
ps aux | sort -rk 3,3 | head -10  # CPU
ps aux | sort -rk 4,4 | head -10  # Memoria

# Terminare processo
kill <PID>
kill -9 <PID>  # Force kill
```

---

## ⚠️ AVVERTENZE

1. **VM Attive:** Chiudere solo se non necessarie
2. **Processi npm:** Verificare che non siano build importanti prima di terminare
3. **sudo purge:** Richiede password, ma è sicuro
4. **Launch Agents:** Disabilitare solo se sicuri che non servono

---

## ✅ RISULTATI ATTESI

Dopo ottimizzazioni:

| Metrica          | Prima       | Dopo (Atteso)  |
| ---------------- | ----------- | -------------- |
| **RAM Libera**   | 403 MB      | 10+ GB         |
| **CPU Idle**     | 3.6%        | 30-40%         |
| **Load Average** | 5.79-7.30   | 2-3            |
| **Swap Attivo**  | Sì (4.1 GB) | No             |
| **Performance**  | Lenta       | Normale/Veloce |

---

**Status:** Analisi completata, pronto per ottimizzazioni  
**Priorità:** 🔴 ALTA (RAM critica)
