# Ollama Cron Window (1am-6am)

## 🎯 Obiettivo

Ollama viene avviato **solo durante la finestra test (1am-6am)** e fermato automaticamente dopo.

## ⏰ Schedule

- **3:25 AM** - Ollama START (5 minuti prima dei test)
- **3:30 AM** - Agent Tests (durano pochi minuti)
- **3:35 AM** - Ollama STOP (5 minuti dopo, quando test finiscono)

**Ollama running solo ~10 minuti (3:25-3:35)**

## 🚀 Setup

### 1. Setup Cron Jobs

```bash
./scripts/setup_ollama_cron.sh
```

Questo aggiunge automaticamente i cron jobs per:

- Avviare Ollama alle 3:25 AM (5 min prima dei test)
- Fermare Ollama alle 3:35 AM (5 min dopo, quando test finiscono)

### 2. Verifica

```bash
# Verifica cron jobs
crontab -l | grep ollama

# Verifica status Ollama
./scripts/ollama_cron_window.sh status
```

## 🔧 Gestione Manuale

### Avvia Ollama (se necessario)

```bash
./scripts/ollama_cron_window.sh start
```

### Ferma Ollama

```bash
./scripts/ollama_cron_window.sh stop
```

### Verifica Status

```bash
./scripts/ollama_cron_window.sh status
```

## 📋 Comportamento Automatico

### Alle 3:30 AM - Agent Tests

**Test automatici:**

- ✅ `auto_agent_test.sh` viene eseguito alle 3:30am
- ✅ Verifica se Ollama è running (dovrebbe essere, avviato alle 3:25am)
- ✅ Usa Qwen reale per i test
- ✅ Test durano pochi minuti
- ✅ Cron ferma Ollama alle 3:35am (automatico)

**Se Ollama non è running:**

- ⚠️ Script prova ad avviarlo (fallback)
- ✅ Usa Qwen se avvio riuscito
- ⚠️ Usa mock se avvio fallito

### Fuori Finestra Test

**Test manuali:**

- ⚠️ Ollama è fermo (running solo 3:25-3:35am)
- ⚠️ Usa mock (Ollama non disponibile)
- ✅ Nessun consumo risorse

## 🎯 Vantaggi

### Massima Efficienza

- ✅ Ollama running solo ~10 minuti (3:25-3:35am)
- ✅ Stop automatico subito dopo i test
- ✅ Zero consumo fuori dalla finestra

### Automatico

- ✅ Avvio automatico alle 1am
- ✅ Stop automatico alle 6:05am
- ✅ Nessun intervento manuale necessario

### Test Realistici

- ✅ Test durante finestra usano Qwen reale
- ✅ Comportamento reale degli agenti
- ✅ Coverage completo

## 📊 Timeline Completa

```
1:00 AM  → DB Backup
2:00 AM  → Scribe
3:00 AM  → Sentinel
3:25 AM  → Ollama START (5 min prima)
3:30 AM  → Agent Tests (con Ollama Qwen reale)
3:35 AM  → Ollama STOP (dopo test completati)
4:00 AM  → Intel Scraper + Visa Agent
5:00 AM  → KB Ingest
```

## 🔍 Troubleshooting

### Ollama non parte alle 1am

```bash
# Verifica cron
crontab -l | grep ollama

# Verifica log
tail -f logs/ollama_cron.log

# Test manuale
./scripts/ollama_cron_window.sh start
```

### Ollama non si ferma alle 6:05am

```bash
# Verifica cron
crontab -l | grep ollama

# Stop manuale
./scripts/ollama_cron_window.sh stop
```

### Test fuori finestra vogliono Ollama

```bash
# Avvia manualmente se necessario
./scripts/ollama_cron_window.sh start

# Oppure usa mock (comportamento di default)
```

## 📝 Logs

- **Ollama cron**: `logs/ollama_cron.log`
- **Agent tests**: `logs/agent_test.log`

## ✅ Checklist

- [ ] Eseguito `setup_ollama_cron.sh` (una volta)
- [ ] Verificato cron jobs: `crontab -l | grep ollama`
- [ ] Testato avvio: `./scripts/ollama_cron_window.sh start`
- [ ] Testato stop: `./scripts/ollama_cron_window.sh stop`
- [ ] Verificato durante finestra: `./scripts/auto_agent_test.sh`
