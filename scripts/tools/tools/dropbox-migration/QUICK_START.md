# 🚀 Quick Start - Dropbox to Google Drive Migration

**Tempo stimato**: 10 minuti setup + 4-5 ore migrazione (450GB)

---

## Step 1: Setup (5 minuti)

```bash
cd ~/Desktop/nuzantara/tools/dropbox-migration
./setup.sh
```

Se fallisce, segui le istruzioni per ottenere:

- Dropbox API token
- Google Drive credentials
- Database URL (opzionale per fase 1)

---

## Step 2: Test con Dry Run (2 minuti)

```bash
python3 dropbox_to_gdrive_migration.py --dry-run
```

Questo mostra cosa verrà fatto **senza** caricare file realmente.

Output esempio:

```
[DRY RUN] Would migrate:
  ✓ ADITYA/ → 45 files (2.3 GB)
    - Passport_ADITYA.pdf → 01_Immigration/
    - KITAS_scan.pdf → 01_Immigration/
    - PT_Deed.pdf → 02_Company/
  ✓ DAVID/ → 32 files (1.8 GB)
  ...
Total: 1,234 files, 387 GB
```

---

## Step 3: Migrazione Reale (4-5 ore)

```bash
# Migrazione batch (pausa ogni 5 clienti)
python3 dropbox_to_gdrive_migration.py

# Oppure batch più grandi (pausa ogni 10 clienti)
python3 dropbox_to_gdrive_migration.py --batch-size 10

# Oppure tutto in una volta (no pause)
python3 dropbox_to_gdrive_migration.py --no-pause
```

**Output in real-time:**

```
[1/50] Processing: ADITYA
  ✓ Created folder structure in Google Drive
  ✓ Uploading files...
    [=========>      ] 45% (12/25 files)
    - Passport_ADITYA.pdf ✓ (2.1 MB)
    - KITAS_Investor.pdf ✓ (1.8 MB)
    - Skipped: .DS_Store (system file)
  ✓ ADITYA complete (25 files, 12.5 GB)

--- Batch completed (5 clients) ---
Files migrated: 234
Files skipped: 23
Press Enter to continue...
```

---

## Step 4: Verifica (2 minuti)

### Check Google Drive

Apri: https://drive.google.com/

Dovresti vedere:

```
📁 Bali Zero Clients/
   📁 ADITYA/
      📁 01_Immigration/
      📁 02_Company/
      📁 03_Tax/
   📁 DAVID/
   📁 ANGEL/
   ...
```

### Check CRM Database

```bash
cd ~/Desktop/nuzantara
psql $DATABASE_URL -c "
SELECT
    c.full_name,
    COUNT(d.id) as docs
FROM clients c
LEFT JOIN documents d ON d.client_id = c.id
WHERE d.uploaded_by = 'migration_script'
GROUP BY c.full_name
ORDER BY docs DESC
LIMIT 10;
"
```

Output esempio:

```
 full_name  | docs
------------+------
 ADITYA     |   25
 DAVID      |   32
 ANGEL      |   18
```

---

## Step 5: Continuous Sync (background)

```bash
# Avvia in background
nohup python3 continuous_sync_watcher.py &

# Controlla che stia girando
ps aux | grep continuous_sync

# Visualizza log
tail -f continuous_sync.log
```

**Da ora in poi**: Ogni file che aggiungi/modifichi in Dropbox viene automaticamente:

1. Rilevato (ogni 60s)
2. Categorizzato
3. Uploadato su Google Drive
4. Inserito nel CRM database

---

## 🆘 Se Qualcosa Va Storto

### "Dropbox API token invalid"

```bash
# Rigenera token: https://www.dropbox.com/developers/apps
# Aggiorna .env:
nano .env
# DROPBOX_API_TOKEN=nuovo_token
```

### "Google Drive quota exceeded"

```bash
# Controlla spazio disponibile
# Hai 30TB, non dovrebbe succedere
# Verifica: https://drive.google.com/settings/storage
```

### "Client not found in CRM"

```bash
# Opzione 1: Crea il cliente manualmente nel CRM prima

# Opzione 2: Abilita auto-create in .env
AUTO_CREATE_CLIENTS=true
```

### Script si blocca / errori

```bash
# Controlla log
cat migration_*.log | grep ERROR

# Re-run da ultimo batch completato
python3 dropbox_to_gdrive_migration.py --resume
```

---

## 📊 Monitoring Progress

```bash
# Durante migrazione - altro terminale:
watch -n 5 'tail -20 migration_*.log'

# Dopo migrazione - statistiche:
python3 dropbox_to_gdrive_migration.py --report
```

---

## ✅ Checklist Completa

- [ ] `./setup.sh` eseguito con successo
- [ ] Dry run mostra file corretti
- [ ] Migrazione iniziale completata (check log)
- [ ] Verificato su Google Drive (almeno 5 clienti random)
- [ ] Verificato nel database CRM (query sopra)
- [ ] Continuous watcher in background
- [ ] Test: upload file manualmente in Dropbox → check appare in GDrive

---

## 🎯 Next Steps Post-Migration

1. **Update CRM Frontend**: Mostra Google Drive links invece di Dropbox
2. **Enable OCR**: Auto-extract passport data da nuovi upload
3. **Setup Alerts**: Email quando documento scade tra 30 giorni
4. **Team Training**: Mostra nuova struttura al team
5. **Dropbox Cleanup**: Dopo 30 giorni, puoi rimuovere file originali

---

## 📞 Support

- **Log errors**: Tutti salvati in `migration_YYYYMMDD_HHMMSS.log`
- **Questions**: zero@balizero.com
- **Full docs**: `DROPBOX_MIGRATION_README.md`
