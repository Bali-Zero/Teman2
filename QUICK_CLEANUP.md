# Quick Cleanup Guide - Mac

## 🚀 Esegui Subito

Apri un terminale e esegui:

```bash
cd /Users/antonellosiano/Desktop/nuzantara
chmod +x cleanup_complete.sh
./cleanup_complete.sh
```

Oppure usa Python:

```bash
python3 cleanup.py
```

## ⚡ Comandi Rapidi

### Libera RAM (richiede password)

```bash
sudo purge
```

### Verifica spazio disco

```bash
df -h /
```

### Analizza Desktop (50GB)

```bash
du -sh ~/Desktop/* | sort -h | tail -10
```

### Pulisci cache npm

```bash
npm cache clean --force
```

### Pulisci cache pip

```bash
pip cache purge
```

### Pulisci Homebrew

```bash
brew cleanup --prune=all
```

## ✅ Già Completato

- ✅ Cache npm pulita (~1.7GB)
- ✅ Cache utente pulita (~532MB)
- ✅ Backup PostgreSQL rimossi (~1.5GB)
- ✅ Cache Python rimossa
- ✅ File temporanei puliti

**Totale liberato: ~4.3GB**

## 📋 Prossimi Passi

1. Esegui `sudo purge` per liberare RAM
2. Analizza il Desktop per trovare file grandi
3. Rimuovi node_modules non necessari se non li usi
4. Pulisci cache Docker se installato: `docker system prune -af`
