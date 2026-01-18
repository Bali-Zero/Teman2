# Ollama Cron Window - Spiegazione Semplice

## 🎯 Cosa Fa Questo Sistema?

**In sintesi:** Ollama (Qwen locale) viene avviato alle 3:25am (5 min prima dei test), rimane attivo solo durante i test (~10 minuti), e viene fermato alle 3:35am subito dopo.

## 📋 Step by Step

### 1. Setup (Una Volta)

```bash
./scripts/setup_ollama_cron.sh
```

**Cosa fa:**

- Aggiunge 2 cron jobs al tuo crontab:
  1. `25 3 * * *` → Avvia Ollama alle 3:25 AM (5 min prima dei test)
  2. `35 3 * * *` → Ferma Ollama alle 3:35 AM (5 min dopo, quando test finiscono)

**Risultato:** Dopo questo setup, Ollama si gestisce da solo.

### 2. Cosa Succede Ogni Notte

#### ⏰ 3:25 AM - Ollama Si Avvia

```
Cron → esegue → ollama_cron_window.sh start
                ↓
          Avvia Ollama in background
                ↓
          Ollama serve Qwen locale
                ↓
          Ollama è RUNNING ✅
```

**Ollama ora è disponibile per i test (5 min prima).**

#### ⏰ 3:30 AM - Agent Tests

```
auto_agent_test.sh viene eseguito
        ↓
Verifica: Ollama è running? SÌ (avviato alle 3:25am)
        ↓
Usa Qwen REALE per i test ✅
        ↓
Esegue test con LLM reale invece di mock
        ↓
Test durano pochi minuti
```

**I test usano Qwen reale, non mock!**

#### ⏰ 3:35 AM - Ollama Si Ferma

```
Cron → esegue → ollama_cron_window.sh stop
                ↓
          Ferma Ollama
                ↓
          Ollama è STOPPED ✅
```

**Ollama fermo dopo ~10 minuti = massima efficienza.**

### 3. Fuori Finestra (tutto il giorno tranne 3:25-3:35am)

Durante il giorno:

- ❌ Ollama è FERMO
- ⚠️ Test manuali usano MOCK
- ✅ Zero consumo risorse (Ollama running solo ~10 minuti al giorno)

## 🔄 Diagramma Completo

```
Giorno (tutto tranne 3:25-3:35am):
  Ollama: STOPPED ❌
  Test:   MOCK ⚠️

Notte (3:25-3:35am):
  3:25 AM → Ollama START ✅
  3:30 AM → Agent Tests con Qwen REALE ✅
  3:35 AM → Ollama STOP ❌

Durata totale: ~10 minuti al giorno
```

## 🎯 Vantaggi

### Automatico

- ✅ Nessun intervento manuale
- ✅ Cron gestisce tutto
- ✅ Setup una volta, funziona sempre

### Efficiente

- ✅ Ollama running solo quando serve (1am-6am)
- ✅ Stop automatico dopo i test
- ✅ Risparmio risorse durante il giorno

### Test Realistici

- ✅ Test notturni usano Qwen reale
- ✅ Comportamento reale degli agenti
- ✅ Coverage completo

## 📝 Esempio Pratico

**Scenario:** Esegui `./scripts/auto_agent_test.sh` alle 3:30 AM

```
1. Script controlla: che ora è? → 3:30 AM
2. Siamo tra 1am-6am? → SÌ ✅
3. Ollama è running? → SÌ (avviato alle 1am) ✅
4. Usa Qwen REALE per i test ✅
5. Test eseguiti con LLM reale
```

**Scenario:** Esegui `./scripts/auto_agent_test.sh` alle 10:00 AM (sviluppo manuale)

```
1. Script controlla: Ollama è running? → NO
2. Avvia Ollama automaticamente ✅
3. Ollama resta RUNNING (per il tuo sviluppo)
4. Usa Qwen REALE per i test ✅
5. Test eseguiti con LLM reale
6. Ollama resta running (puoi continuare a testare)
```

**Quando finisci:**

```bash
./scripts/ollama_cron_window.sh stop  # Ferma Ollama manualmente
```

## 🔧 Comandi Utili

### Per Sviluppo/Test Manuali

**Avvia Ollama per sviluppo (resta running):**

```bash
./scripts/start_ollama_dev.sh
```

Ollama resta running finché non lo fermi manualmente.

**Esegui test con Ollama:**

```bash
./scripts/auto_agent_test.sh
```

Se Ollama è running, usa Qwen reale. Altrimenti avvia Ollama automaticamente.

**Ferma Ollama quando finisci:**

```bash
./scripts/ollama_cron_window.sh stop
```

### Verifica Status

```bash
./scripts/ollama_cron_window.sh status
```

### Verifica Cron Jobs

```bash
crontab -l | grep ollama
```

## ❓ FAQ

**Q: Devo lanciare qualcosa ogni volta?**
A: NO! Dopo `setup_ollama_cron.sh`, tutto è automatico.

**Q: Cosa succede se eseguo test durante il giorno?**
A: Usano mock (Ollama è fermo per risparmiare risorse).

**Q: Posso forzare Ollama durante il giorno?**
A: Sì, `./scripts/ollama_cron_window.sh start` per avviarlo manualmente.

**Q: Ollama si ferma da solo?**
A: Sì, alle 6:05 AM via cron.

**Q: Cosa succede se Ollama crasha durante la finestra?**
A: I test useranno mock (fallback automatico).
