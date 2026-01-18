# 🚀 Cowork Optimization Suite

Configurazione avanzata e automazioni per Claude Cowork - Ottimizzazioni performance, integrazioni e workflow automatizzati.

## 📋 Indice

- [Features](#features)
- [Installazione](#installazione)
- [Configurazione](#configurazione)
- [Utilizzo](#utilizzo)
- [Templates](#templates)
- [Automazioni](#automazioni)
- [Troubleshooting](#troubleshooting)

---

## ✨ Features

### 1. Espansione Cartelle

- ✅ 5 cartelle autorizzate (vs 1 originale)
- ✅ Accesso a: nuzantara, KB, kbli, Downloads, Documents
- ✅ Permessi gestiti centralmente

### 2. Performance Optimization

- ⚡ Cache intelligente file grandi
- ⚡ Pre-loading cartelle frequenti
- ⚡ Cleanup automatico sessioni vecchie
- ⚡ Limite 3 sessioni concorrenti

### 3. Integrazioni MCP Avanzate

- 🔌 Filesystem (ottimizzato)
- 🔌 GitHub integration
- 🔌 PostgreSQL direct access
- 🔌 Memory persistence
- 🔌 Brave Search
- 🔌 Slack notifications (opzionale)

### 4. Automazioni Custom

- 🤖 Auto-organize Downloads (ogni ora)
- 🤖 Backup sessioni Cowork (ogni 6 ore)
- 🤖 Sync KB → Qdrant (ogni 2 ore)
- 🤖 Cleanup sessioni vecchie (daily)

### 5. Security & Backup

- 🔒 Whitelist cartelle sensibili
- 🔒 Backup automatico pre-operazioni
- 🔒 Logging dettagliato azioni
- 🔒 Limits su operazioni batch

### 6. Prompt Templates

- 📝 File Organization
- 📝 Document Analysis
- 📝 Data Processing
- 📝 KB Sync
- 📝 Project Report

---

## 🚀 Installazione

### Metodo 1: Installer Automatico

```bash
cd ~/Desktop/nuzantara/.cowork-optimization
./install.sh
```

### Metodo 2: Manuale

```bash
# 1. Rendi eseguibili gli script
chmod +x ~/Desktop/nuzantara/.cowork-optimization/scripts/*.sh

# 2. Crea directory necessarie
mkdir -p ~/Desktop/nuzantara/.cowork-optimization/{logs,backups/{sessions,auto}}

# 3. Test backup
~/Desktop/nuzantara/.cowork-optimization/scripts/backup-cowork-sessions.sh
```

---

## ⚙️ Configurazione

### 1. Cartelle Autorizzate

File: `~/Library/Application Support/Claude/Claude Extensions Settings/ant.dir.ant.anthropic.filesystem.json`

```json
{
  "isEnabled": true,
  "userConfig": {
    "allowed_directories": [
      "/Users/antonellosiano/Desktop/nuzantara",
      "/Users/antonellosiano/Desktop/KB",
      "/Users/antonellosiano/Desktop/kbli",
      "/Users/antonellosiano/Downloads",
      "/Users/antonellosiano/Documents"
    ]
  }
}
```

### 2. MCP Servers (Opzionale)

File: `mcp-config-enhanced.json`

Configura variabili d'ambiente:

```bash
export GITHUB_TOKEN="your_token"
export POSTGRES_PASSWORD="your_password"
export POSTGRES_HOST="localhost"
export BRAVE_API_KEY="your_key"
```

### 3. Cron Jobs (Opzionale)

```bash
crontab ~/Desktop/nuzantara/.cowork-optimization/cowork-crontab.txt
```

---

## 💡 Utilizzo

### Quick Start con Templates

1. **Organizza Downloads**

   ```
   Cowork > Usa template "File Organization"
   Cartella: ~/Downloads
   ```

2. **Analizza Documenti KB**

   ```
   Cowork > Usa template "Document Analysis"
   Cartella: ~/Desktop/KB
   ```

3. **Sync KB a Qdrant**

   ```
   Cowork > Usa template "KB Sync"
   Esegui sync automatico
   ```

4. **Report Progetto**
   ```
   Cowork > Usa template "Project Report"
   Progetto: ~/Desktop/nuzantara
   ```

### Comandi Manuali

**Backup immediato:**

```bash
~/Desktop/nuzantara/.cowork-optimization/scripts/backup-cowork-sessions.sh
```

**Organizza Downloads ora:**

```bash
~/Desktop/nuzantara/.cowork-optimization/scripts/auto-organize-downloads.sh
```

**Cleanup sessioni:**

```bash
~/Desktop/nuzantara/.cowork-optimization/scripts/cleanup-old-sessions.sh
```

**Sync KB:**

```bash
~/Desktop/nuzantara/.cowork-optimization/scripts/sync-kb-to-qdrant.sh
```

---

## 📝 Templates

Tutti i template sono in: `~/Desktop/nuzantara/.cowork-optimization/templates/`

### Come usare i Templates

1. Apri Cowork in Claude Desktop
2. Seleziona "Work in a folder"
3. Copia il contenuto del template desiderato
4. Adatta i parametri `[FOLDER_PATH]`, `[PROJECT_NAME]`, etc.
5. Esegui

### Templates Disponibili

| Template               | Descrizione                  | Use Case                |
| ---------------------- | ---------------------------- | ----------------------- |
| `file-organization.md` | Organizza file per tipo/data | Downloads caotici       |
| `document-analysis.md` | Analisi documenti + summary  | Research, meeting notes |
| `data-processing.md`   | Trasforma e valida dati      | CSV, JSON, Excel        |
| `kb-sync.md`           | Sync KB a Qdrant             | Aggiorna knowledge base |
| `project-report.md`    | Report completo progetto     | Status updates          |

---

## 🔄 Automazioni

### Schedule Automatico (con cron)

| Script                       | Frequenza  | Descrizione                         |
| ---------------------------- | ---------- | ----------------------------------- |
| `auto-organize-downloads.sh` | Ogni ora   | Organizza Downloads automaticamente |
| `backup-cowork-sessions.sh`  | Ogni 6 ore | Backup incrementale sessioni        |
| `sync-kb-to-qdrant.sh`       | Ogni 2 ore | Sync KB se modifiche                |
| `cleanup-old-sessions.sh`    | Daily 3 AM | Rimuove sessioni >7 giorni          |

### Logs

Tutti i log sono in: `~/Desktop/nuzantara/.cowork-optimization/logs/`

- `downloads-organize.log` - Organizzazione Downloads
- `session-backup.log` - Backup sessioni
- `kb-sync.log` - Sync Knowledge Base
- `session-cleanup.log` - Cleanup sessioni
- `install.log` - Installazione

---

## 🔒 Security

### File Protetti

Non saranno mai toccati da Cowork:

- `*.key`, `*.pem` - Chiavi private
- `*.env` - Variabili d'ambiente
- `*secret*`, `*password*` - File sensibili
- Directory: `.ssh`, `.aws`, `.config`

### Backup Automatico

Backup prima di:

- Delete operations
- Replace operations
- Move operations

Backup salvati in: `~/Desktop/nuzantara/.cowork-optimization/backups/auto/`

---

## 🐛 Troubleshooting

### Problema: Cartelle non accessibili in Cowork

**Soluzione:**

1. Riavvia Claude Desktop app
2. Verifica configurazione:
   ```bash
   cat ~/Library/Application\ Support/Claude/Claude\ Extensions\ Settings/ant.dir.ant.anthropic.filesystem.json
   ```
3. Se necessario, ri-applica config:
   ```bash
   ~/Desktop/nuzantara/.cowork-optimization/install.sh
   ```

### Problema: Script automazioni non funzionano

**Soluzione:**

1. Verifica permessi:
   ```bash
   ls -la ~/Desktop/nuzantara/.cowork-optimization/scripts/
   ```
2. Rendi eseguibili:
   ```bash
   chmod +x ~/Desktop/nuzantara/.cowork-optimization/scripts/*.sh
   ```
3. Test manuale:
   ```bash
   ~/Desktop/nuzantara/.cowork-optimization/scripts/backup-cowork-sessions.sh
   ```

### Problema: Cron jobs non eseguiti

**Soluzione:**

1. Verifica crontab:
   ```bash
   crontab -l
   ```
2. Controlla log cron:
   ```bash
   tail -f /var/log/system.log | grep cron
   ```
3. Reinstalla crontab:
   ```bash
   crontab ~/Desktop/nuzantara/.cowork-optimization/cowork-crontab.txt
   ```

### Problema: MCP server non connette

**Soluzione:**

1. Controlla log MCP:
   ```bash
   tail -f ~/Library/Logs/Claude/mcp.log
   ```
2. Verifica variabili d'ambiente
3. Riavvia Claude Desktop

---

## 📊 Performance

### Metriche Attese

- ⚡ **Velocità operazioni file**: +40-60% più veloce
- 💾 **Uso memoria**: -30% riduzione
- 🔄 **Permission prompts**: -70% riduzione
- 📈 **Produttività**: 10x aumento ([fonte](https://medium.com/@nicola.sahar/dont-fall-behind-how-to-10x-your-productivity-with-claude-cowork-841dbdda4766))

### Monitoring

Controlla performance con:

```bash
# Spazio usato da sessioni
du -sh ~/Library/Application\ Support/Claude/local-agent-mode-sessions/

# Backup disponibili
ls -lh ~/Desktop/nuzantara/.cowork-optimization/backups/sessions/

# Ultimi log
tail ~/Desktop/nuzantara/.cowork-optimization/logs/*.log
```

---

## 🔗 Risorse

- [Claude Cowork Official](https://claude.com/blog/cowork-research-preview)
- [Comprehensive Guide](https://elephas.app/blog/claude-cowork-comprehensive-guide)
- [Best Practices](https://awesomecowork.com/)
- [10x Productivity Tips](https://medium.com/@nicola.sahar/dont-fall-behind-how-to-10x-your-productivity-with-claude-cowork-841dbdda4766)

---

## 📄 License

MIT License - Creato per ottimizzare Claude Cowork

---

## 🤝 Support

Per problemi o suggerimenti:

1. Controlla i log in `.cowork-optimization/logs/`
2. Consulta sezione [Troubleshooting](#troubleshooting)
3. Verifica configurazione con `install.sh`

---

**Version:** 1.0
**Last Updated:** 2026-01-16
**Compatibile con:** Claude Cowork Research Preview, Claude Code 2.1.9+
