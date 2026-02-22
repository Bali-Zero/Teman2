# Arsenale AI - Strategia Nuzantara

**Aggiornato:** 2026-02-22

---

## Inventario Reale (verificato Mac)

### Abbonamenti Attivi

| Provider          | Piano              | Cosa copre                                    |
| ----------------- | ------------------ | --------------------------------------------- |
| **Anthropic**     | Claude MAX 200     | Claude Code + Claude.app (Opus 4.6, 200k ctx) |
| **Google**        | AI Ultra ($249.99) | Gemini CLI + Antigravity IDE (Gemini 3 Pro)   |
| **Cursor**        | Ultra              | IDE AI-first (GPT-5, Sonnet)                  |
| **Windsurf**      | Pro                | Cascade agent IDE                             |
| **Claude Cowork** | —                  | Sessioni ottimizzate, automazioni locali      |
| **Gumloop**       | 60k crediti/mese   | Automazione workflow no-code con AI           |
| **Perplexity**    | Pro                | Ricerca web con citazioni                     |

### CLI Installate

| Tool          | Versione    | Modello Attivo                                |
| ------------- | ----------- | --------------------------------------------- |
| `claude`      | 2.1.50      | Opus 4.6 MAX (200k ctx)                       |
| `opencode`    | 1.2.10      | Dinamico — Google/Cohere/Ollama via env       |
| `openclaw`    | 2026.2.21-2 | Gemini 3 Pro Preview (agent ZAN 🕉️)           |
| `kimi`        | 1.12.0      | kimi-for-coding (262k ctx, thinking ON)       |
| `gemini`      | 0.29.3      | Gemini 3 Pro Preview (AI Ultra, --yolo)       |
| `cursor`      | 2.5.20      | Claude/GPT-5 (Ultra plan)                     |
| `windsurf`    | 1.9552      | Cascade (Pro)                                 |
| `antigravity` | 1.107.0     | Solo launcher GUI (apre l'app) — no agent CLI |
| `ollama`      | 0.15.6      | qwen2.5-coder:32b (locale, 19GB)              |

### App Installate

| App                 | Uso principale                       |
| ------------------- | ------------------------------------ |
| **Claude.app**      | Chat, file upload, research, Cowork  |
| **Cursor.app**      | IDE coding veloce (Ultra)            |
| **Windsurf.app**    | IDE Cascade agent (Pro)              |
| **Antigravity.app** | IDE multi-agent parallelo (AI Ultra) |
| **Perplexity.app**  | Ricerca web con fonti                |
| **Dia.app**         | Browser AI                           |

### Opencode — Provider Attivi (via env, NO Copilot)

| Provider                  | Modelli disponibili  |
| ------------------------- | -------------------- |
| `google` (GEMINI_API_KEY) | Gemini 3 Pro Preview |
| `cohere` (COHERE_API_KEY) | Command-A            |
| `ollama` (locale)         | qwen2.5-coder:32b    |

### Openclaw ZAN — Setup

- **Modello:** Gemini 3 Pro Preview → fallback Claude Sonnet/Opus
- **Canali attivi:** WhatsApp, iMessage, voice-call
- **Plugin:** memory-lancedb, llm-task, kimi-claw, lobster
- **Telegram:** disabilitato
- **RIRI:** non esiste più — ZAN è l'unico agent

### Gumloop — Automazione No-Code

- **60.000 crediti/mese** (valore alto)
- Web-based, drag & drop workflows con AI
- Connettori: Gmail, Google Sheets, Slack, Notion, webhook, HTTP, ecc.
- **Ideale per:** pipeline dati, notifiche automatiche, CRM automation, scraping orchestration

---

## Strategia d'Uso

### Matrice Decisionale

| Scenario                              | Tool              | Perché                                      |
| ------------------------------------- | ----------------- | ------------------------------------------- |
| **Feature complessa multi-file**      | Claude Code       | MCP servers, subagents, skill system        |
| **Coding TUI rapido**                 | Opencode          | TUI fluida, switch modello, PR review       |
| **Coding in IDE**                     | Cursor            | Veloce, agent mode nell'editor              |
| **Refactoring architetturale**        | Antigravity.app   | 8 agent paralleli, planning mode — solo GUI |
| **Cascade multi-step in IDE**         | Windsurf          | Edit mode, cascade sequenziale              |
| **Context enorme (>100k)**            | Kimi CLI          | 262k ctx, thinking ON, gratis               |
| **Q&A istantaneo terminale**          | gemini --yolo     | Risposta immediata, zero interazione        |
| **Coding locale / privacy**           | Opencode + ollama | qwen2.5-coder:32b, zero cloud               |
| **PR review da terminale**            | Opencode          | `opencode pr <n>`                           |
| **Ricerca con fonti**                 | Perplexity.app    | Citazioni verificate                        |
| **Gateway mobile**                    | Openclaw (ZAN)    | WhatsApp/iMessage → Gemini 3 Pro            |
| **Automazione workflow**              | Gumloop           | 60k crediti, no-code, API integrations      |
| **App Google (Gmail, Sheets, Drive)** | Gumloop           | Connettori nativi, automazioni complesse    |

### Regola Pratica

```
Coding da terminale?
  → opencode (TUI, switch modello con Tab)
  → se serve MCP/subagent → claude

Sei in IDE?
  → Cursor (task veloci) | Windsurf (cascade) | Antigravity (parallelo)

Risposta istantanea?
  → gemini --yolo "domanda"

File/context enorme?
  → kimi (262k) oppure claude (200k MAX)

Privacy / offline?
  → opencode + ollama → qwen2.5-coder:32b

Mobile / lontano dal Mac?
  → WhatsApp → ZAN → Gemini 3 Pro

Automazione ripetitiva / workflow?
  → Gumloop (60k crediti, no-code)
```

### Gumloop — Automazioni Utili per Nuzantara

Con 60k crediti/mese puoi automatizzare:

- **CRM alerts:** nuovo cliente in PostgreSQL → notifica WhatsApp a ZAN
- **Intel pipeline:** RSS → Gumloop AI filter → staging area backend
- **Google Sheets → Qdrant:** sync dati prezzi/KBLI aggiornati
- **Gmail → CRM:** email clienti estratte e loggata in PostgreSQL
- **Deploy alerts:** Fly.io webhook → Gumloop → WhatsApp
- **Report settimanale:** query PostgreSQL → Gumloop → Google Sheets formattato

### Workflow Quotidiano

```
Mattina:
  1. opencode (TUI) per tasks del giorno
  2. Cursor/Antigravity per features attive
  3. claude per task complessi con MCP

Durante:
  ├── Analisi veloce    → gemini --yolo
  ├── PR review         → opencode pr <n>
  ├── Context enorme    → kimi
  ├── Privacy/offline   → opencode + ollama
  ├── Parallelismo      → Antigravity
  └── Automazioni       → Gumloop

Mobile:
  → WhatsApp → ZAN → risposta Gemini 3 Pro
```

---

_"The lobster way"_ 🦞
