# Mac Performance - Azioni Eseguite e Manuali

**Data:** 2026-01-16  
**Status:** ✅ Pulizia Automatica Completata

---

## ✅ AZIONI AUTOMATICHE ESEGUITE

### 1. Pulizia Cache ✅

| Cache            | Dimensione | Status    |
| ---------------- | ---------- | --------- |
| CloudKit         | 265 MB     | ✅ Pulita |
| ms-playwright-go | 127 MB     | ✅ Pulita |
| us.zoom.xos      | 73 MB      | ✅ Pulita |
| node-gyp         | 64 MB      | ✅ Pulita |
| Homebrew         | 52 MB      | ✅ Pulita |

**Totale Cache Pulita:** ~580 MB

---

## ⚠️ AZIONI MANUALI RICHIESTE

### 1. Chiudere VM Non Necessarie 🔴 PRIORITÀ ALTA

**Problema:** 2 VM attive consumano ~10.6 GB RAM

**VM Attive Identificate:**

- PID 2026: ~6.5 GB RAM, 196% CPU
- PID 48375: ~4.1 GB RAM, 42.8% CPU (stuck)

**Azione:**

1. Apri **Activity Monitor** (Applicazioni > Utility)
2. Cerca "VirtualMachine" nella barra di ricerca
3. Seleziona le VM non necessarie
4. Clicca "Forza Termina" (Force Quit)

**Spazio Liberabile:** ~10 GB RAM

**Alternativa (Terminale):**

```bash
# Verificare VM attive
ps aux | grep VirtualMachine | grep -v grep

# Se necessario, terminare (ATTENZIONE: solo se sicuro)
# kill <PID>
```

---

### 2. Purge Memoria 🔴 PRIORITÀ ALTA

**Problema:** ~15.4 GB di memoria compressa (swap massivo)

**Azione:**

```bash
sudo purge
```

**Effetto:** Libera memoria compressa e cache sistema

**Nota:** Richiede password amministratore

**Verifica Dopo:**

```bash
vm_stat | grep "Pages free"
```

---

### 3. Terminare Processi npm Non Necessari ⚠️

**Problema:** 25 processi npm/node attivi, alcuni consumano 70-80% CPU

**Azione:**

```bash
# Vedere processi npm attivi
ps aux | grep npm | grep -v grep

# Verificare quale processo è quale
ps aux | grep npm | grep -v grep | awk '{print $2, $11}'

# Terminare processo specifico (solo se sicuro che non è necessario)
kill <PID>

# Force kill se necessario (ATTENZIONE)
kill -9 <PID>
```

**Raccomandazione:**

- Verificare che non siano build/test importanti prima di terminare
- Se sono processi di sviluppo, potrebbero essere necessari

---

### 4. Chiudere App Non Necessarie ⚠️

**App Pesanti Identificate:**

- Claude: 55% CPU, ~700 MB RAM
- Cursor Helper: 60% CPU, 709 MB RAM
- Chrome/Safari: Se con molte tab aperte

**Azione:**

- Chiudere app non necessarie manualmente
- Chiudere tab browser non necessarie

---

## 📊 VERIFICA RISULTATI

### Comandi di Verifica

```bash
# Memoria
vm_stat | grep "Pages free"
top -l 1 -o mem | head -10

# CPU
top -l 1 -o cpu | head -10
uptime

# Processi pesanti
ps aux | awk '{if ($3 > 10.0) print $3"% CPU - "$11}' | sort -rn | head -10
ps aux | awk '{if ($4 > 5.0) print $4"% MEM - "$11}' | sort -rn | head -10
```

### Risultati Attesi

| Metrica      | Prima       | Dopo (Atteso) |
| ------------ | ----------- | ------------- |
| RAM Libera   | 98 MB       | 10+ GB        |
| CPU Idle     | 3.6%        | 30-40%        |
| Load Average | 5.79-7.30   | 2-3           |
| Swap Attivo  | Sì (~15 GB) | No            |

---

## 🎯 PRIORITÀ AZIONI

### 🔴 CRITICO (Eseguire Subito)

1. ✅ Purge memoria (`sudo purge`)
2. ✅ Chiudere VM non necessarie

**Effetto Atteso:** Liberare ~10 GB RAM immediatamente

### ⚠️ IMPORTANTE (Eseguire Presto)

3. Terminare processi npm non necessari
4. Chiudere app non necessarie

**Effetto Atteso:** Ridurre CPU usage e RAM

---

## 📝 NOTE

- **VM:** Chiudere solo se non necessarie (potrebbero essere VM di sviluppo)
- **npm:** Verificare che non siano build importanti prima di terminare
- **sudo purge:** Sicuro da eseguire, libera solo memoria non utilizzata
- **App:** Chiudere solo se non in uso

---

**Status:** Pulizia automatica completata  
**Prossimo Passo:** Eseguire azioni manuali critiche
