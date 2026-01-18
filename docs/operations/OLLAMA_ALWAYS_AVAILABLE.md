# Ollama Always Available - Setup Guide

## 🎯 Obiettivo

**Ollama deve essere SEMPRE disponibile** senza dover lanciare script manualmente.

## 🚀 Setup Una Volta (Permanente)

### Opzione 1: Servizio di Sistema (Raccomandato)

**macOS:**

```bash
./scripts/setup_ollama_service.sh
```

**Linux:**

```bash
sudo ./scripts/setup_ollama_service.sh
```

**Cosa fa:**

- ✅ Configura Ollama come servizio di sistema
- ✅ Avvia automaticamente al boot
- ✅ Riavvia automaticamente se crasha
- ✅ **Nessun intervento manuale necessario**

### Opzione 2: Daemon Manuale

Se preferisci non usare servizi di sistema:

```bash
# Avvia daemon (rimane sempre running)
./scripts/start_ollama_daemon.sh

# Verifica status
./scripts/check_ollama_status.sh

# Ferma daemon (se necessario)
./scripts/stop_ollama_daemon.sh
```

## ✅ Verifica Setup

```bash
./scripts/check_ollama_status.sh
```

Dovresti vedere:

```
✅ Ollama is running
✅ Qwen model is available
✅ Ollama service is configured
```

## 🧪 Uso nei Test

**Dopo il setup, i test funzionano automaticamente:**

```bash
# Nessun setup necessario - Ollama è già running!
./scripts/auto_agent_test.sh
```

Il sistema:

1. ✅ Verifica se Ollama è già running (sì, se hai fatto setup)
2. ✅ Usa Qwen reale per i test
3. ✅ Nessun avvio manuale necessario

## 🔧 Gestione

### Verifica Status

```bash
./scripts/check_ollama_status.sh
```

### Riavvia (se necessario)

**macOS:**

```bash
launchctl unload ~/Library/LaunchAgents/com.ollama.test.plist
launchctl load ~/Library/LaunchAgents/com.ollama.test.plist
```

**Linux:**

```bash
sudo systemctl restart ollama-test.service
```

### Ferma (se necessario)

**macOS:**

```bash
launchctl unload ~/Library/LaunchAgents/com.ollama.test.plist
```

**Linux:**

```bash
sudo systemctl stop ollama-test.service
```

## 📋 Checklist Setup

- [ ] Ollama installato (`brew install ollama` o script Linux)
- [ ] Eseguito `setup_ollama_service.sh` (una volta)
- [ ] Verificato con `check_ollama_status.sh`
- [ ] Modello Qwen disponibile (`ollama pull qwen2.5:latest` se necessario)

## 🎉 Risultato

**Dopo il setup una volta:**

- ✅ Ollama **sempre running** (avvio automatico al boot)
- ✅ **Nessun script da lanciare** manualmente
- ✅ Test funzionano automaticamente con Qwen reale
- ✅ Zero configurazione per ogni esecuzione

## ⚠️ Troubleshooting

### Ollama non parte al boot

```bash
# Verifica servizio
./scripts/check_ollama_status.sh

# Riconfigura
./scripts/setup_ollama_service.sh
```

### Modello Qwen mancante

```bash
ollama pull qwen2.5:latest
```

### Porta già in uso

```bash
# Verifica cosa usa porta 11434
lsof -i :11434

# Ferma processo conflittuale o cambia porta
export OLLAMA_URL="http://localhost:11435"
```
