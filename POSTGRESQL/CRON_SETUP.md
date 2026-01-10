# Setup Aggiornamento Automatico Excel

## Opzione 1: macOS Cron (Locale)

Il Mac deve essere acceso all'ora schedulata.

```bash
# Apri crontab
crontab -e

# Aggiungi (ogni giorno alle 6:00 AM):
0 6 * * * /Users/antonellosiano/Desktop/nuzantara/POSTGRESQL/update_with_proxy.sh >> /tmp/postgresql_export.log 2>&1

# Verifica
crontab -l

# Log
tail -f /tmp/postgresql_export.log
```

## Opzione 2: macOS LaunchAgent (Più Affidabile)

Crea il file `~/Library/LaunchAgents/com.nuzantara.excel-export.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.nuzantara.excel-export</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/antonellosiano/Desktop/nuzantara/POSTGRESQL/update_with_proxy.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>6</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/postgresql_export.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/postgresql_export.log</string>
</dict>
</plist>
```

Attiva:
```bash
launchctl load ~/Library/LaunchAgents/com.nuzantara.excel-export.plist
```

## Opzione 3: GitHub Actions (Cloud)

Non richiede Mac acceso, ma i file vanno committati su Git.

Crea `.github/workflows/excel-export.yml`:

```yaml
name: PostgreSQL Excel Export

on:
  schedule:
    - cron: '0 6 * * *'  # Ogni giorno alle 6:00 UTC
  workflow_dispatch:      # Esecuzione manuale

jobs:
  export:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: superfly/flyctl-actions/setup-flyctl@master

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install pandas openpyxl asyncpg

      - name: Export to Excel
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
        run: |
          cd POSTGRESQL
          ./update_with_proxy.sh

      - name: Commit updated files
        run: |
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          git add POSTGRESQL/*.xlsx POSTGRESQL/README.md
          git diff --staged --quiet || git commit -m "chore: update PostgreSQL Excel export [skip ci]"
          git push
```

Richiede:
1. Aggiungere `FLY_API_TOKEN` ai secrets del repo
2. Dare permessi write al workflow

## Esecuzione Manuale

```bash
cd /Users/antonellosiano/Desktop/nuzantara/POSTGRESQL
./update_with_proxy.sh
```

## Troubleshooting

**Errore "machine not running":**
```bash
fly machine start -a nuzantara-rag
```

**Errore "connection refused":**
```bash
# Il proxy potrebbe non essere partito, riprova
./update_with_proxy.sh
```

**Verificare log:**
```bash
cat /tmp/postgresql_export.log
```
