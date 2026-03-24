# Processi Zombie e Nascosti - Report Completo

**Data:** 2026-01-17  
**Status:** Analisi Completata

---

## 🚨 RISULTATI ANALISI

### Processi Zombie Trovati: **20**

**Lista Processi Zombie:**

- PID 1892, 1704, 2795, 3032, 3033, 1469, 1340, 2039, 1682, 1663, 1656, 1644, 1643, 1598, 1388, 1338, 1337, 1336, 11467, 11424

**Stato:** Tutti con nome `<defunct>`

**Problema:** Processi terminati ma ancora nella tabella processi (non rilasciano risorse)

---

### Processi Stuck Trovati: **1**

**Processo Stuck:**

- **PID 55790:** `bird` (Cloudflare)
  - CPU: 0.0%
  - MEM: 28 MB
  - Runtime: 33:08
  - Stato: stuck

**Problema:** Processo sospeso/fermato

---

## ⚠️ PROCESSI ANOMALI

### Processi con CPU Alta ma Stato Sleeping

| PID   | Processo      | CPU   | MEM  | Note       |
| ----- | ------------- | ----- | ---- | ---------- |
| 64262 | Google Chrome | 78.8% | 3.3% | ⚠️ Anomalo |
| 625   | iTerm2        | 46.0% | 1.9% | ⚠️ Anomalo |
| 64197 | Google Chrome | 10.7% | 1.2% | ⚠️ Anomalo |
| 64238 | Google Chrome | 9.5%  | 0.5% | ⚠️ Anomalo |

**Problema:** Processi in stato "sleeping" ma consumano molta CPU

---

### Processi con Path Temporanei

**Claude AppTranslocation:**

- Molti processi Claude in `/private/var/folders/.../T/AppTranslocation/`
- Path temporaneo indica app non installata correttamente
- Processi multipli dello stesso tipo

**Raccomandazione:** Reinstallare Claude correttamente

---

## 🔍 ANALISI PROCESSI ZOMBIE

### Cosa Sono i Processi Zombie?

Processi che sono stati terminati ma il processo padre non ha chiamato `wait()` per rimuoverli dalla tabella processi. Occupano slot nella tabella processi ma non consumano risorse.

### Analisi Zombie Trovati

**Tutti i 20 zombie hanno PPID 1133:**

- **PPID 1133:** Cursor Helper (Plugin): extension-host
- **Problema:** Cursor non sta gestendo correttamente la terminazione dei processi figlio

**Lista Zombie:**

- PID 1892, 1704, 2795, 3032, 3033, 1469, 1340, 2039, 1682, 1663, 1656, 1644, 1643, 1598, 1388, 1338, 1337, 1336, 11467, 11424

### Perché Sono un Problema?

1. **Occupano slot** nella tabella processi (limite: ~4096 processi)
2. **Indicano bug** in Cursor (non gestisce correttamente terminazione)
3. **Possono accumularsi** nel tempo

### Come Risolvere?

**Metodo 1: Riavviare Cursor**

- Chiudere e riaprire Cursor
- Rimuove automaticamente i processi zombie

**Metodo 2: Terminare Processo Padre (PPID 1133)**

```bash
# Terminare extension-host di Cursor
kill 1133
# Cursor lo riavvierà automaticamente
```

**Metodo 3: Riavviare Sistema**

- Riavviare Mac rimuove tutti i processi zombie

---

## 🔍 ANALISI PROCESSO STUCK

### Processo Stuck: `bird` (PID 55790)

**Dettagli:**

- **Nome:** bird (iCloudDriveCore - Apple)
- **CPU:** 38.7%
- **MEM:** 44 MB
- **Runtime:** 33:16
- **Stato:** stuck (running ma marcato come stuck)

**Problema:** Processo iCloud Drive che potrebbe essere bloccato

**Azione:**

```bash
# Riprendere processo
kill -CONT 55790

# Oppure terminare se non necessario (si riavvierà automaticamente)
kill 55790
```

---

## ⚠️ PROCESSI CON CPU ALTA MA SLEEPING

### Chrome (PID 64262)

**Problema:** 78.8% CPU ma stato sleeping

**Azione:**

- Chiudere tab Chrome non necessarie
- Oppure riavviare Chrome

### iTerm2 (PID 625)

**Problema:** 46.0% CPU ma stato sleeping

**Azione:**

- Verificare se ci sono script in esecuzione
- Riavviare iTerm2 se necessario

---

## 📊 STATISTICHE

### Totale Processi

- **Processi Totali:** ~479
- **Processi Zombie:** 20
- **Processi Stuck:** 1
- **Processi Anomali:** 4+ (CPU alta ma sleeping)

---

## ✅ AZIONI CONSIGLIATE

### Priorità Alta

1. **Risolvere Processi Zombie**
   - Identificare PPID
   - Terminare PPID o riavviare sistema

2. **Risolvere Processo Stuck**
   - Riprendere o terminare `bird` (PID 55790)

### Priorità Media

3. **Risolvere Processi Anomali**
   - Chiudere Chrome tab non necessarie
   - Verificare iTerm2

4. **Reinstallare Claude**
   - Rimuovere processi da AppTranslocation
   - Reinstallare Claude correttamente

---

## 🗑️ COMANDI PER PULIZIA

### Terminare Processi Zombie

```bash
# Lista zombie
ps aux | awk '$8 ~ /Z/ {print $2}'

# Trovare PPID e terminare
ps aux | awk '$8 ~ /Z/ {print $2}' | while read pid; do
  ppid=$(ps -p $pid -o ppid= 2>/dev/null | tr -d ' ')
  if [ -n "$ppid" ]; then
    echo "Zombie PID $pid - PPID $ppid"
    # kill $ppid  # Solo se sicuro
  fi
done
```

### Risolvere Processo Stuck

```bash
# Riprendere
kill -CONT 55790

# Terminare
kill 55790
```

---

**Status:** Analisi completata  
**Problemi Trovati:** 20 zombie, 1 stuck, 4+ anomali
