# Kimi - MCP Integration Guide

**Ultimo aggiornamento:** 2026-02-16

---

## 🎭 Playwright MCP (BROWSER AUTOMATION)

**Stato:** ✅ INSTALLATO E CONFIGURATO

### Configurazione Attuale

```json
{
  "playwright": {
    "type": "stdio",
    "command": "npx",
    "args": ["-y", "@playwright/mcp@latest", "--browser", "chrome"]
  }
}
```

### Tool Disponibili

| Tool                      | Descrizione        | Uso Tipico                      |
| ------------------------- | ------------------ | ------------------------------- |
| `browser_navigate`        | Naviga a un URL    | Andare su kita.balizero.com     |
| `browser_click`           | Clicca un elemento | Cliccare bottoni, link          |
| `browser_type`            | Scrive in input    | Compilare form                  |
| `browser_take_screenshot` | Fa screenshot      | Documentazione, verifica UI     |
| `browser_eval`            | Esegue JavaScript  | Estrarre dati, verificare stato |
| `browser_get_text`        | Estrae testo       | Scraping contenuto              |
| `browser_select`          | Seleziona opzione  | Dropdown menu                   |
| `browser_hover`           | Hover su elemento  | Tooltips, menu a tendina        |
| `browser_close`           | Chiude browser     | Pulizia                         |

### Esempi d'Uso

```javascript
// Naviga e fai screenshot
await browser_navigate({ url: "https://kita.balizero.com" });
await browser_take_screenshot({ path: "homepage.png" });

// Compila form
await browser_type({ selector: "#email", text: "test@example.com" });
await browser_click({ selector: "button[type='submit']" });

// Estrai dati
const title = await browser_eval({ script: "document.title" });
```

---

## 🔧 MCP NATIVI E PERFETTI PER KIMI

### 1. **Filesystem** ⭐ ESSENZIALE

```json
{
  "filesystem": {
    "type": "stdio",
    "command": "npx",
    "args": [
      "-y",
      "@modelcontextprotocol/server-filesystem",
      "/Users/nuzantara"
    ]
  }
}
```

**Tool:** `read_file`, `write_file`, `list_directory`, `search_files`
**Uso:** Lettura/scrittura file nel progetto

### 2. **Playwright** ⭐ BROWSER (già configurato)

Come descritto sopra.

### 3. **Fetch** ⭐ HTTP REQUESTS

```json
{
  "fetch": {
    "type": "stdio",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-fetch"]
  }
}
```

**Tool:** `fetch`
**Uso:** Chiamate HTTP dirette (GET, POST, etc.)

### 4. **Sequential Thinking** 🧠 RAGIONAMENTO

```json
{
  "sequential-thinking": {
    "type": "stdio",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
  }
}
```

**Tool:** `sequentialthinking`
**Uso:** Ragionamento passo-passo, problem solving complesso

### 5. **Memory** 💾 MEMORIA PERSISTENTE

```json
{
  "memory": {
    "type": "stdio",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-memory"]
  }
}
```

**Tool:** `create_entities`, `add_observations`, `search_nodes`
**Uso:** Memoria persistente tra sessioni

### 6. **Context7** 📚 DOCUMENTAZIONE

```json
{
  "context7": {
    "type": "stdio",
    "command": "npx",
    "args": ["-y", "@upstash/context7-mcp"]
  }
}
```

**Tool:** `resolve`, `search`
**Uso:** Ricerca in documentazione tecnica

---

## 🔌 MCP CONDIZIONALI (Solo quando necessario)

### 7. **Brave Search** 🌐 RICERCA WEB

```json
{
  "brave-search": {
    "type": "stdio",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-brave-search"],
    "env": { "BRAVE_API_KEY": "..." }
  }
}
```

**Tool:** `brave_web_search`, `brave_local_search`
**Uso:** Ricerche web, notizie, informazioni aggiornate

### 8. **Perplexity** 🤖 AI SEARCH

```json
{
  "perplexity": {
    "type": "stdio",
    "command": "npx",
    "args": ["-y", "@perplexity-ai/mcp-server"],
    "env": { "PERPLEXITY_API_KEY": "..." }
  }
}
```

**Tool:** `perplexity_search`, `perplexity_chat`
**Uso:** Ricerca con risposte AI-generated

### 9. **GitHub** 🐙 VERSION CONTROL

```json
{
  "github": {
    "type": "stdio",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-github"],
    "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "..." }
  }
}
```

**Tool:** `create_issue`, `create_pull_request`, `search_code`
**Uso:** Operazioni GitHub

### 10. **PostgreSQL** 🐘 DATABASE

```json
{
  "postgres": {
    "type": "stdio",
    "command": "npx",
    "args": [
      "-y",
      "@modelcontextprotocol/server-postgres",
      "postgresql://user:pass@host:5432/db"
    ]
  }
}
```

**Tool:** `query`, `execute`
**Uso:** Query database Nuzantara

---

## 🎨 MCP CUSTOM (Creati per Nuzantara)

### 11. **Nuzantara RAG** 🏛️ (già esistente)

```json
{
  "nuzantara-rag": {
    "type": "stdio",
    "command": "npx",
    "args": ["-y", "nuzantara-mcp"]
  }
}
```

**Tool:** `search_kbli`, `inspect_kbli`, `ask_legal`, `check_health`
**Uso:** Interrogazione backend Nuzantara

### 12. **Nuzantara Advanced** 🔧 (creato da noi)

```json
{
  "nuzantara-advanced": {
    "type": "stdio",
    "command": "npx",
    "args": ["-y", "nuzantara-mcp-advanced"]
  }
}
```

**Tool:** `check_fly_status`, `run_backend_tests`, `search_codebase`
**Uso:** Operazioni DevOps per Nuzantara

---

## 🛠️ SKILL PER KIMI

### Skill Nuzantara (Create)

| Skill                          | Path                                 | Descrizione                     |
| ------------------------------ | ------------------------------------ | ------------------------------- |
| **kimi-nuzantara**             | `skills/kimi-nuzantara/`             | Identità e conoscenza Nuzantara |
| **nuzantara-domain-knowledge** | `skills/nuzantara-domain-knowledge/` | Conoscenza dominio Bali Zero    |
| **git-commit-helper**          | `skills/git-commit-helper/`          | Helper per commit Git           |

### Skill System (Disponibili)

| Skill             | Path             | Descrizione           |
| ----------------- | ---------------- | --------------------- |
| **kimi-cli-help** | Skill di sistema | Aiuto per Kimi CLI    |
| **skill-creator** | Skill di sistema | Creazione nuovi skill |

---

## 🔌 PLUGIN E CONFIGURAZIONI

### VS Code (Consigliati)

Configurati in `.vscode/`:

| Plugin              | ID                           | Utilità                 |
| ------------------- | ---------------------------- | ----------------------- |
| Python              | `ms-python.python`           | Python language support |
| Pylance             | `ms-python.vscode-pylance`   | Type checking           |
| Ruff                | `charliermarsh.ruff`         | Linting e formatting    |
| MyPy                | `matangover.mypy`            | Type checking           |
| Tailwind CSS        | `bradlc.vscode-tailwindcss`  | CSS support             |
| Prettier            | `esbenp.prettier-vscode`     | Code formatting         |
| ESLint              | `dbaeumer.vscode-eslint`     | JS/TS linting           |
| GitLens             | `eamodio.gitlens`            | Git integration         |
| Markdown All-in-One | `yzhang.markdown-all-in-one` | MD support              |
| Todo Tree           | `gruntfuggly.todo-tree`      | TODO tracking           |

### Configurazione IDE

- **`.vscode/settings.json`** - Impostazioni VS Code ottimizzate
- **`.vscode/extensions.json`** - Lista extensioni consigliate

---

## 📋 RIEpilogo MCP Prioritari per Nuzantara

### Tier 1: Essenziali (Sempre attivi)

1. ✅ **filesystem** - File operations
2. ✅ **playwright** - Browser automation
3. ✅ **nuzantara-rag** - Backend Nuzantara
4. ✅ **nuzantara-advanced** - DevOps Nuzantara

### Tier 2: Importanti (Caricati spesso)

5. 🔄 **fetch** - HTTP requests
6. 🔄 **sequential-thinking** - Problem solving
7. 🔄 **memory** - Memoria persistente

### Tier 3: Specializzati (Caricati on-demand)

8. ⚡ **brave-search** - Web search
9. ⚡ **perplexity** - AI search
10. ⚡ **github** - Git operations
11. ⚡ **postgres** - Database queries
12. ⚡ **context7** - Documentation

---

## 🚀 Come Aggiungere un Nuovo MCP

1. **Installa il pacchetto:**

```bash
npm install -g @nome/pacchetto-mcp
```

2. **Aggiungi a `~/.claude.json`:**

```json
{
  "mcpServers": {
    "nome-server": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@nome/pacchetto-mcp"],
      "env": { "API_KEY": "..." }
    }
  }
}
```

3. **Riavvia Kimi**

---

## 🔗 Link Utili

- [MCP Registry](https://github.com/modelcontextprotocol/servers)
- [Playwright MCP](https://github.com/microsoft/playwright-mcp)
- [Nuzantara MCP](apps/nuzantara-mcp/)
- [Nuzantara Advanced MCP](apps/nuzantara-mcp-advanced/)

---

_Configurazione mantenuta da Kimi - Nuzantara AI Team_ 🤖
