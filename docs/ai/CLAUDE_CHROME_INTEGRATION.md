# Claude Code + Chrome Integration — Guida Completa

## Requisiti

| Componente | Versione Minima |
|------------|-----------------|
| Claude Code | 2.0.73+ |
| Chrome Extension | 1.0.36+ |
| Browser | Solo Google Chrome (no Brave, Arc, altri Chromium) |
| Sistema | Mac/Linux (WSL non supportato) |

---

## Setup Passo-Passo

### 1. Aggiorna Claude Code

```bash
npm install -g @anthropic-ai/claude-code@latest
# oppure se hai usato il native installer, si aggiorna automaticamente

# Verifica versione
claude --version
```

### 2. Installa l'estensione Chrome

1. Vai su [Chrome Web Store](https://chromewebstore.google.com/detail/claude/fcoeoabgfenejglbffodgkkbkcdhcgfn)
2. Clicca "Add to Chrome"
3. Accedi con le credenziali Claude
4. Riavvia Chrome (necessario per il native messaging host)

### 3. Avvia l'integrazione

**Opzione A — Da linea di comando:**
```bash
claude --chrome
```

**Opzione B — Da sessione esistente:**
```bash
claude
# poi dentro la sessione:
/chrome
```

### 4. Verifica connessione

```bash
/chrome  # mostra status e impostazioni
```

Se vedi "Chrome extension not detected":
- Verifica che Chrome sia aperto
- Verifica che l'estensione sia abilitata
- Riavvia Chrome

---

## Capacità Principali

| Funzione | Descrizione |
|----------|-------------|
| **Navigazione** | Apre pagine, clicca link, compila form |
| **Console Logs** | Legge errori, network requests, DOM state |
| **Screenshot** | Cattura schermate delle pagine |
| **GIF Recording** | Registra interazioni browser come GIF |
| **Login State** | Usa le tue sessioni già autenticate |
| **Multi-tab** | Apre nuove tab (non prende quelle esistenti) |

---

## Comandi e Prompt Utili

### Test Rapido
```
Open https://google.com, click the search field, type "Claude AI",
and tell me what autocomplete suggestions appear
```

### Debug Frontend (per Zantara!)
```
Open localhost:3000, submit the contact form with invalid data,
and check the console for any JavaScript errors
```

### Verifica Rendering
```
Open my staging site, take a screenshot of the homepage,
and compare it to the Figma mock I uploaded
```

### Test RAG Response
```
Open the Zantara app, search for "PT PMA requirements",
and verify the response includes proper document citations
```

### Monitor Network
```
Open localhost:3000/api/search, monitor network requests
when I submit a query, and report any 4xx or 5xx errors
```

### Registra GIF Demo
```
Record a GIF of me navigating from homepage to visa consultation form,
filling it out, and submitting
```

---

## Configurazione Avanzata

### Abilitare Chrome di default
```bash
/chrome
# Seleziona "Enabled by default"
```

> **Nota:** Aumenta il consumo di context tokens

### Permessi Estensione Chrome

| Permesso | Uso |
|----------|-----|
| `sidePanel` | Claude appare come pannello laterale |
| `scripting` | Legge testo dalle pagine |
| `debugger` | Controlla il browser (click, typing, screenshot) |
| `tabs` | Apre/chiude/cambia tab |
| `tabGroups` | Organizza tab in gruppi colorati |
| `nativeMessaging` | Comunica con Claude Code CLI |
| `notifications` | Avvisa quando task completato |
| `downloads` | Scarica file durante workflow |

---

## Limitazioni & Best Practices

### Limitazioni
- **No headless mode** — serve finestra browser visibile
- **Modal dialogs bloccano** — alert/confirm JS interrompono il flusso
- **Solo Chrome** — Brave, Arc, altri non supportati
- **No WSL** — Windows Subsystem for Linux non funziona

### Best Practices

1. **Filtra console output**
   ```
   Check console for errors containing "TypeError" or "NetworkError"
   ```
   Non chiedere "tutti i log" — troppo verboso

2. **Usa tab fresche**
   ```
   If the tab becomes unresponsive, please open a new tab
   ```

3. **Gestisci blocchi manualmente**
   - CAPTCHA → risolvilo tu, poi di' a Claude di continuare
   - Login → inserisci credenziali tu, oppure di' a Claude di inserirle

4. **Siti sensibili**
   - Evita banking, pagamenti, dati sensibili
   - L'estensione blocca già alcune categorie ad alto rischio

---

## Workflow Tipico per Sviluppo

```
Terminal (Claude Code)          Browser (Chrome)
        │                              │
        │  claude --chrome             │
        ├──────────────────────────────┤
        │                              │
        │  "Build login form"          │
        │  [scrive codice]             │
        │                              │
        │  "Open localhost:3000        │
        │   and test the form"         │
        │              ────────────────► [apre pagina]
        │                              │  [compila form]
        │                              │  [legge console]
        │              ◄────────────────  [report errori]
        │                              │
        │  "Fix the validation error"  │
        │  [modifica codice]           │
        │                              │
        │  "Verify fix in browser"     │
        │              ────────────────► [ri-testa]
        │              ◄────────────────  [OK ✓]
        │                              │
        └──────────────────────────────┘
```

---

## Troubleshooting

| Problema | Soluzione |
|----------|-----------|
| "Extension not detected" | Riavvia Chrome, verifica versioni |
| Tab non risponde | Chiedi a Claude di aprire nuova tab |
| Modal blocca esecuzione | Dismissalo manualmente, poi di' "continue" |
| Errori permessi | Riavvia Chrome dopo prima installazione |
| Consumo token alto | Disabilita "Enabled by default" se non serve |

---

## Link Utili

- **Docs ufficiali:** https://code.claude.com/docs/en/chrome
- **Chrome Extension:** https://chromewebstore.google.com/detail/claude/fcoeoabgfenejglbffodgkkbkcdhcgfn
- **Safety Guide:** https://support.claude.com/en/articles/12902428-using-claude-in-chrome-safely
- **Troubleshooting:** https://support.claude.com/en/articles/12902405-claude-in-chrome-troubleshooting

---

## Confronto: Chrome Extension vs Playwright MCP

| Aspetto | Chrome Extension | Playwright MCP |
|---------|------------------|----------------|
| **Autenticazione** | Usa sessioni utente | Nessuna (headless) |
| **CSP Blocking** | Può essere bloccato | Bypassa CSP |
| **Automazione** | Interattiva | Schedulabile |
| **Siti Gov** | Spesso bloccato | Funziona |
| **Uso ideale** | Dev workflow quotidiano | Scraping, testing E2E |

### Quando usare cosa:
- **Chrome Extension**: Debug frontend, test con login, workflow interattivo
- **Playwright**: Intel Scan automatico, scraping gov sites, CI/CD testing
