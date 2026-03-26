# INSTALL CHECKLIST — Software da installare ORA

**Data:** 2026-02-14
**Priorita:** Da installare in ordine dall'alto al basso

---

## PRIORITA 1: CRITICO (Oggi)

### Air (MacBook Air M4, 16 GB)

| #   | Software                       | Comando                  | Perche                                        |
| --- | ------------------------------ | ------------------------ | --------------------------------------------- |
| A1  | **launchd plist per OpenClaw** | Vedi sotto               | OpenClaw si riavvia automaticamente se crasha |
| A2  | **qwen2.5:3b su Ollama**       | `ollama pull qwen2.5:3b` | Fallback locale per triage (~2.5 GB)          |

### Pro (MacBook Pro M4 Pro, 48 GB)

| #   | Software                       | Comando                             | Perche                                           |
| --- | ------------------------------ | ----------------------------------- | ------------------------------------------------ |
| P1  | **Ollama**                     | `brew install ollama`               | Non installato sul Pro, serve per modelli locali |
| P2  | **qwen2.5-coder:14b**          | `ollama pull qwen2.5-coder:14b`     | Code generation locale (~10 GB)                  |
| P3  | **qwen2.5:14b**                | `ollama pull qwen2.5:14b`           | General reasoning (~10 GB)                       |
| P4  | **deepseek-r1:7b**             | `ollama pull deepseek-r1:7b`        | Chain-of-thought (~5 GB)                         |
| P5  | **nomic-embed-text:v1.5**      | `ollama pull nomic-embed-text:v1.5` | Embedding backup (~0.5 GB)                       |
| P6  | **launchd plist per OpenClaw** | Vedi sotto                          | Stesso motivo dell'Air                           |
| P7  | **launchd plist per Ollama**   | Vedi sotto                          | Ollama serve sempre in background                |

---

## PRIORITA 2: IMPORTANTE (Questa settimana)

### Air

| #   | Software             | Comando                | Perche                     |
| --- | -------------------- | ---------------------- | -------------------------- |
| A3  | **uptimed**          | `brew install uptimed` | Traccia uptime del Mac     |
| A4  | **jq** (se mancante) | `brew install jq`      | Parse JSON in scripts cron |

### Pro

| #   | Software       | Comando                      | Perche                                                 |
| --- | -------------- | ---------------------------- | ------------------------------------------------------ |
| P8  | **gemini CLI** | Installare via npm/pip       | Per research tasks diretti (non solo tramite OpenClaw) |
| P9  | **Docker**     | `brew install --cask docker` | Per test locali, zan-memory, isolamento                |
| P10 | **uptimed**    | `brew install uptimed`       | Traccia uptime                                         |

---

## PRIORITA 3: NICE TO HAVE (Prossime 2 settimane)

| #   | Mac      | Software         | Comando               | Perche                         |
| --- | -------- | ---------------- | --------------------- | ------------------------------ |
| 11  | Pro      | **cursor CLI**   | Da Cursor.app         | Kodex puo delegare task al Pro |
| 12  | Entrambi | **htop**         | `brew install htop`   | Monitor risorse in real-time   |
| 13  | Entrambi | **bottom (btm)** | `brew install bottom` | htop moderno con grafici       |

---

## COSA NON INSTALLARE

| Software                      | Perche NO                                                                                           |
| ----------------------------- | --------------------------------------------------------------------------------------------------- |
| **PM2**                       | Process manager Node.js. NON serve: OpenClaw e gia un daemon, launchd e nativo macOS ed e superiore |
| **Supervisor**                | Process manager Python. Stessa ragione: launchd e meglio su macOS                                   |
| **Grafana/Prometheus locale** | Overkill per 2 Mac. I metrics sono gia su Fly.io. Usa `fly metrics` e `fly logs`                    |
| **Redis locale**              | Il backend usa Redis su Fly.io. Locale non serve (non c'e cache locale)                             |
| **Modelli >14B**              | qwen2.5:32b richiederebbe ~24 GB. Il Pro deve restare stabile per altre apps                        |
| **LM Studio**                 | UI inutile: Ollama fa tutto via CLI, piu leggero, integrabile                                       |
| **codex CLI**                 | Abbonamento OpenAI chiuso. CLI installata ma inutile                                                |

---

## LAUNCHD PLIST — Auto-restart per OpenClaw

### Air: `/Library/LaunchDaemons/com.openclaw.gateway.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.openclaw.gateway</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Users/antonellosiano/.npm-global/bin/openclaw</string>
        <string>gateway</string>
        <string>--force</string>
    </array>

    <key>UserName</key>
    <string>antonellosiano</string>

    <key>WorkingDirectory</key>
    <string>/Users/antonellosiano</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>

    <key>ThrottleInterval</key>
    <integer>30</integer>

    <key>StandardOutPath</key>
    <string>/tmp/openclaw/gateway.log</string>

    <key>StandardErrorPath</key>
    <string>/tmp/openclaw/gateway-error.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/Users/antonellosiano/.npm-global/bin</string>
        <key>HOME</key>
        <string>/Users/antonellosiano</string>
    </dict>
</dict>
</plist>
```

**Installazione:**

```bash
# Creare directory log
mkdir -p /tmp/openclaw

# Copiare il plist
sudo cp com.openclaw.gateway.plist /Library/LaunchDaemons/

# Caricare
sudo launchctl load /Library/LaunchDaemons/com.openclaw.gateway.plist

# Verificare
sudo launchctl list | grep openclaw
```

### Pro: Stessa struttura, cambiare:

- `UserName` → `nuzantara`
- `WorkingDirectory` → `/Users/nuzantara`
- `HOME` → `/Users/nuzantara`
- `PATH` → includere `/Users/nuzantara/.npm-global/bin`
- Porta: 18789 (gia configurata in openclaw.json del Pro)

### Ollama come LaunchAgent (Pro):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ollama.serve</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/ollama</string>
        <string>serve</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>/tmp/ollama.log</string>

    <key>StandardErrorPath</key>
    <string>/tmp/ollama-error.log</string>
</dict>
</plist>
```

```bash
# Installare come LaunchAgent (user-level, non root)
cp com.ollama.serve.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.ollama.serve.plist
```

---

## VERIFICA POST-INSTALLAZIONE

```bash
# === AIR ===
# 1. OpenClaw running?
pgrep -f "openclaw gateway" && echo "OK" || echo "FAIL"

# 2. Ollama models?
ollama list
# Deve mostrare: deepseek-r1:1.5b, qwen2.5:3b

# 3. launchd caricato?
sudo launchctl list | grep openclaw

# === PRO (via SSH) ===
ssh nuzantara@192.168.0.17 "
  pgrep -f 'openclaw gateway' && echo 'OpenClaw: OK' || echo 'OpenClaw: FAIL';
  ollama list 2>/dev/null || echo 'Ollama: NOT INSTALLED';
  echo 'Disk:'; df -h / | tail -1;
  echo 'RAM:'; vm_stat | head -5;
"
```

---

## STIMA TEMPO INSTALLAZIONE

| Fase                       | Durata      | Note                     |
| -------------------------- | ----------- | ------------------------ |
| P1: Install Ollama su Pro  | 2 min       | `brew install ollama`    |
| P2-P5: Pull modelli su Pro | ~30 min     | Download ~25 GB          |
| A1+P6: launchd plists      | 10 min      | Copy + load              |
| A2: Pull qwen2.5:3b su Air | 5 min       | Download ~2.5 GB         |
| P7: Ollama launchd su Pro  | 5 min       |                          |
| **Totale Priorita 1**      | **~50 min** |                          |
| Priorita 2                 | ~15 min     | uptimed, jq, gemini CLI  |
| Priorita 3                 | ~20 min     | cursor CLI, htop, bottom |
| **Totale completo**        | **~85 min** |                          |
