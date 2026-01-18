# Piano Pulizia Processi Zombie e Nascosti

**Data:** 2026-01-17  
**Problemi Trovati:** 20 zombie, 1 stuck, 4+ anomali

---

## 🚨 PROBLEMI IDENTIFICATI

### 1. Processi Zombie (20) 🔴

**Causa:** Cursor Helper (PID 1133) non gestisce correttamente la terminazione dei processi figlio

**Zombie Trovati:**

- Tutti con PPID 1133 (Cursor Helper extension-host)
- PID: 1892, 1704, 2795, 3032, 3033, 1469, 1340, 2039, 1682, 1663, 1656, 1644, 1643, 1598, 1388, 1338, 1337, 1336, 11467, 11424

**Impatto:**

- Occupano slot nella tabella processi
- Indicano bug in Cursor
- Non consumano risorse ma possono accumularsi

---

### 2. Processo Stuck (1) ⚠️

**Processo:** `bird` (PID 55790)

- **Tipo:** iCloudDriveCore (Apple)
- **CPU:** 38.7%
- **MEM:** 44 MB
- **Runtime:** 33:16
- **Stato:** stuck (running ma marcato come stuck)

**Impatto:** Processo iCloud Drive potrebbe essere bloccato

---

### 3. Processi Anomali (4+) ⚠️

**Processi con CPU Alta ma Stato Sleeping:**

| PID   | Processo      | CPU   | MEM  | Problema             |
| ----- | ------------- | ----- | ---- | -------------------- |
| 64262 | Google Chrome | 78.8% | 3.3% | CPU alta ma sleeping |
| 625   | iTerm2        | 46.0% | 2.1% | CPU alta ma sleeping |
| 48324 | Claude        | 17.6% | 2.8% | CPU alta ma sleeping |
| 64197 | Google Chrome | 10.7% | 1.2% | CPU alta ma sleeping |

**Impatto:** Consumano CPU inutilmente

---

## ✅ PIANO DI AZIONE

### Priorità Alta 🔴

#### 1. Risolvere Processi Zombie

**Opzione A: Riavviare Cursor (Consigliato)**

- Chiudere Cursor completamente
- Riaprire Cursor
- I processi zombie verranno rimossi automaticamente

**Opzione B: Terminare Extension-Host**

```bash
kill 1133
```

- Cursor riavvierà automaticamente extension-host
- I processi zombie verranno rimossi

**Opzione C: Riavviare Sistema**

- Riavviare Mac rimuove tutti i processi zombie

---

### Priorità Media ⚠️

#### 2. Risolvere Processo Stuck

**Processo:** `bird` (PID 55790)

**Opzione A: Riprendere Processo**

```bash
kill -CONT 55790
```

**Opzione B: Terminare Processo**

```bash
kill 55790
```

- Si riavvierà automaticamente se necessario

---

#### 3. Risolvere Processi Anomali

**Chrome (PID 64262):**

- Chiudere tab Chrome non necessarie
- Oppure riavviare Chrome completamente

**iTerm2 (PID 625):**

- Verificare se ci sono script in esecuzione
- Riavviare iTerm2 se necessario

**Claude (PID 48324):**

- Chiudere Claude se non necessario
- Considerare reinstallazione (molti processi in path temporaneo)

---

## 🗑️ COMANDI PULIZIA

### Pulizia Automatica Zombie

```bash
# Verificare zombie
ps aux | awk '$8 ~ /Z/ {print "Zombie PID: " $2 " - PPID: " $3}'

# Terminare extension-host di Cursor (rimuove zombie)
kill 1133
```

### Pulizia Processo Stuck

```bash
# Riprendere
kill -CONT 55790

# Terminare
kill 55790
```

### Pulizia Processi Anomali

```bash
# Terminare Chrome pesante
kill 64262

# Riavviare iTerm2
kill 625
# Poi riaprire iTerm2

# Chiudere Claude
killall Claude
```

---

## 📊 RISULTATI ATTESI

### Dopo Pulizia Zombie

- **Processi Zombie:** Da 20 a 0
- **Slot Processi:** Liberati
- **Sistema:** Più stabile

### Dopo Pulizia Stuck

- **Processo Stuck:** Risolto
- **iCloud Drive:** Funzionante

### Dopo Pulizia Anomali

- **CPU Usage:** Ridotto significativamente
- **Performance:** Migliorata

---

## ⚠️ AVVERTENZE

- **Cursor:** Riavviare Cursor è sicuro (salva lavoro prima)
- **bird:** Terminare è sicuro (si riavvierà se necessario)
- **Chrome/iTerm2:** Verificare che non ci sia lavoro importante prima di chiudere

---

**Status:** Piano creato  
**Prossimo Passo:** Eseguire pulizia
