# Analisi Processi Zombie e Nascosti

**Data:** 2026-01-17  
**Obiettivo:** Trovare processi zombie, nascosti o sospetti

---

## 🔍 RICERCA PROCESSI ZOMBIE

### Processi Zombie (Stato Z)

**Stato:** Processi terminati ma ancora nella tabella processi

**Comando:**

```bash
ps aux | awk '$8 ~ /Z/ {print "ZOMBIE: PID " $2 " - " $11}'
```

**Risultato:** Analisi in corso...

---

## 🔍 RICERCA PROCESSI STUCK

### Processi Stuck (Stato T)

**Stato:** Processi sospesi/fermati

**Comando:**

```bash
ps aux | awk '$8 ~ /T/ {print "STUCK: PID " $2 " - " $11}'
```

**Risultato:** Analisi in corso...

---

## 🔍 RICERCA PROCESSI SOSPETTI

### Processi con Path Temporanei

**Indicatori:**

- Path in `/tmp/`, `/var/tmp/`
- Path in `/private/var/folders/.../T/`
- Nome con molti numeri
- Script `.sh`, `.py`, `.pl`

**Comando:**

```bash
ps aux | awk '$11 ~ /\/tmp\/|\/var\/tmp\/|\/private\/var\/folders\/.*\/T\// {print "TEMP: PID " $2 " - " $11}'
```

---

### Processi con PPID Strano

**Indicatori:**

- PPID molto alto (>100000)
- PPID = 1 (orfani)
- PPID non esistente

---

### Processi con Risorse Anomale

**Indicatori:**

- CPU alta ma stato sleeping
- Threads molto alti (>50)
- VSIZE molto alto (>1 GB)
- Runtime molto lungo (>100 ore)

---

## 📊 STATISTICHE

### Totale Processi

Analisi in corso...

---

## ✅ AZIONI CONSIGLIATE

### Se Trovati Processi Zombie

1. **Identificare PPID:**

   ```bash
   ps -p <PID> -o ppid=
   ```

2. **Terminare PPID:**

   ```bash
   kill <PPID>
   ```

3. **Se necessario, force kill:**
   ```bash
   kill -9 <PPID>
   ```

### Se Trovati Processi Stuck

1. **Riprendere processo:**

   ```bash
   kill -CONT <PID>
   ```

2. **Terminare se non necessario:**
   ```bash
   kill <PID>
   kill -9 <PID>  # Se necessario
   ```

---

**Status:** Analisi in corso...
