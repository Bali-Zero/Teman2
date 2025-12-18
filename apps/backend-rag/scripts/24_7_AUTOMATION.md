# 🤖 NUZANTARA PRIME - 24/7 Automation Guide

Automazioni che girano continuamente per mantenere alta qualità del codice.

## 🚀 Automazioni 24/7 Disponibili

### 1. **Code Watchdog** (`watchdog.py`)

Monitora continuamente il codice per problemi di qualità.

**Funzionalità:**
- ✅ Rileva type hints mancanti
- ✅ Trova print() statements
- ✅ Rileva segreti hardcoded
- ✅ Verifica test mancanti
- ✅ Auto-fix per print() statements

**Uso:**
```bash
# Run una volta
python apps/backend-rag/scripts/watchdog.py --once

# Run continuamente (ogni 5 minuti)
python apps/backend-rag/scripts/watchdog.py --interval 300

# Run come daemon (background)
nohup python apps/backend-rag/scripts/watchdog.py > watchdog.log 2>&1 &
```

**Automated Execution:**
- Eseguito automaticamente ogni 6 ore (se configurato)
- Crea report se trova problemi critici
- Salva report come file locale

---

### 2. **Auto-Fix Script** (`auto_fix.py`)

Corregge automaticamente problemi comuni di qualità codice.

**Funzionalità:**
- ✅ Organizza imports (stdlib → third-party → local)
- ✅ Rimuove trailing whitespace
- ✅ Aggiunge final newline
- ✅ Formatta codice base

**Uso:**
```bash
# Dry run (vedi cosa verrebbe fixato)
python apps/backend-rag/scripts/auto_fix.py --dry-run

# Applica fix
python apps/backend-rag/scripts/auto_fix.py
```

**Integrazione:**
- Eseguito automaticamente in pre-commit hooks
- Eseguito automaticamente ogni 6 ore (dry-run, se configurato)

---

### 3. **Dependency Watcher** (`dependency_watcher.py`)

Monitora dipendenze per vulnerabilità e aggiornamenti.

**Funzionalità:**
- ✅ Controlla vulnerabilità di sicurezza (pip-audit)
- ✅ Rileva pacchetti obsoleti
- ✅ Genera PR description per aggiornamenti

**Uso:**
```bash
# Check dipendenze
python apps/backend-rag/scripts/dependency_watcher.py

# Genera PR description
python apps/backend-rag/scripts/dependency_watcher.py --pr
```

**Setup:**
```bash
# Installa pip-audit
pip install pip-audit
```

---

### 4. **Pre-Commit Hooks** (`.pre-commit-config.yaml`)

Eseguiti automaticamente ad ogni commit.

**Hooks Attivi:**
- ✅ Ruff (linting + formatting)
- ✅ Security checks (detect-private-key)
- ✅ YAML validation
- ✅ Trailing whitespace removal
- ✅ Large files check
- ✅ Sentinel system guardian
- ✅ Backend unit tests (pre-push)

**Setup:**
```bash
# Installa hooks
pre-commit install

# Run manualmente su tutti i file
pre-commit run --all-files
```

---

### 5. **Automated Workflows**

Automazioni CI/CD che girano su ogni push/PR.

**Workflows:**
- ✅ **Code Watchdog** - Ogni 6 ore
- ✅ **Test Automation** - Su ogni push/PR
- ✅ **Security Scan** - Su ogni push/PR
- ✅ **Deploy** - Su push a main
- ✅ **Cleanup** - Ogni domenica

---

## 📋 Setup Completo 24/7

### Step 1: Installa Dipendenze

```bash
cd apps/backend-rag
pip install -r requirements.txt
pip install pip-audit pre-commit
```

### Step 2: Setup Pre-Commit Hooks

```bash
pre-commit install
pre-commit run --all-files
```

### Step 3: Setup Watchdog Locale (Opzionale)

```bash
# Crea systemd service (Linux)
sudo nano /etc/systemd/system/nuzantara-watchdog.service
```

```ini
[Unit]
Description=Nuzantara Code Watchdog
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/nuzantara/apps/backend-rag
ExecStart=/usr/bin/python3 scripts/watchdog.py
Restart=always
RestartSec=300

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable nuzantara-watchdog
sudo systemctl start nuzantara-watchdog
```

### Step 4: Setup Cron Jobs (Alternativa)

```bash
# Aggiungi a crontab
crontab -e
```

```cron
# Code Watchdog ogni 6 ore
0 */6 * * * cd /path/to/nuzantara/apps/backend-rag && python3 scripts/watchdog.py --once >> watchdog.log 2>&1

# Dependency check giornaliero
0 2 * * * cd /path/to/nuzantara/apps/backend-rag && python3 scripts/dependency_watcher.py >> deps.log 2>&1

# Auto-fix settimanale (dry-run)
0 3 * * 0 cd /path/to/nuzantara/apps/backend-rag && python3 scripts/auto_fix.py --dry-run >> autofix.log 2>&1
```

---

## 🔄 Flusso Automatizzato Completo

```
┌─────────────────────────────────────────────────────────┐
│                   24/7 AUTOMATION FLOW                   │
└─────────────────────────────────────────────────────────┘

1. PRE-COMMIT (Ogni commit)
   ├── Ruff linting + formatting
   ├── Security checks
   ├── Sentinel guardian
   └── Auto-fix basic issues

2. PUSH TO REMOTE (if configured)
   ├── Test Automation (if configured)
   ├── Security Scan (if configured)
   └── Code Watchdog (if configured)

3. SCHEDULED (Ogni 6 ore)
   ├── Code Watchdog check
   ├── Dependency check
   └── Auto-fix dry-run

4. WEEKLY (Domenica)
   ├── Cleanup temp files
   ├── Dependency audit completo
   └── Code quality report
```

---

## 📊 Monitoring & Reporting

### Log Files

- `watchdog.log` - Code Watchdog activities
- `deps.log` - Dependency checks
- `autofix.log` - Auto-fix operations

### Reports & Artifacts

- Watchdog reports (saved locally)
- Test coverage reports (saved locally)
- Security scan results (saved locally)

### Notifications

- Local logs per problemi critici
- Test results saved to files
- Deployment notifications (if configured)

---

## 🛠️ Troubleshooting

### Watchdog non parte

```bash
# Verifica Python path
which python3

# Test manuale
python3 apps/backend-rag/scripts/watchdog.py --once

# Verifica log
tail -f watchdog.log
```

### Pre-commit hooks non funzionano

```bash
# Reinstalla hooks
pre-commit uninstall
pre-commit install

# Test manuale
pre-commit run --all-files
```

### Dependency watcher fallisce

```bash
# Installa pip-audit
pip install pip-audit

# Verifica requirements.txt
cat apps/backend-rag/requirements.txt
```

---

## 🎯 Best Practices

1. **Review Auto-Fixes**: Sempre controlla cosa viene auto-fixato
2. **Monitor Logs**: Controlla regolarmente i log per pattern
3. **Update Dependencies**: Review settimanale delle dipendenze
4. **Test Before Deploy**: I pre-commit hooks prevengono deploy di codice rotto
5. **Security First**: I security checks sono critici, non skipparli

---

## 📈 Metriche da Monitorare

- **Code Quality Score**: Type hints coverage, test coverage
- **Security Issues**: Vulnerabilità trovate e risolte
- **Auto-Fixes Applied**: Quanti fix automatici applicati
- **Test Failures**: Tasso di successo dei test
- **Dependency Updates**: Pacchetti obsoleti e vulnerabili

---

## 🚨 Alert Thresholds

- **Critical**: Segreti hardcoded → Blocca commit
- **High**: Vulnerabilità sicurezza → Log error critico
- **Medium**: Type hints < 70% → Warning in PR
- **Low**: Print statements → Auto-fix silenzioso

---

## 📝 Note

- Tutte le automazioni sono **non-blocking** tranne pre-commit hooks
- Auto-fix applica solo fix **sicuri** e **reversibili**
- Watchdog può girare in background senza impatto performance
- Automated workflows possono essere configurati localmente o su piattaforme CI/CD


