#!/bin/bash

echo "=== PULIZIA CONTINUA ==="
echo "Data: $(date)"
echo ""

# 1. Verifica spazio disco
echo "1. Spazio disco attuale:"
df -h / | tail -1

# 2. Rimuovi backup tar.gz
echo ""
echo "2. Rimozione backup tar.gz..."
rm -rf ./.cowork-optimization/backups/sessions/*.tar.gz 2>/dev/null
echo "   ✅ Backup tar.gz rimossi"

# 3. Trova file grandi
echo ""
echo "3. File grandi nel progetto (>50MB):"
find . -type f -size +50M ! -path "./.git/*" ! -path "./node_modules/*" -exec ls -lh {} \; 2>/dev/null | head -10

# 4. Analizza node_modules
echo ""
echo "4. Analisi node_modules:"
du -sh apps/*/node_modules 2>/dev/null | sort -h

# 5. Analizza .next
echo ""
echo "5. Analisi cartelle .next:"
find . -type d -name ".next" -exec du -sh {} \; 2>/dev/null | sort -h

# 6. Analizza cache utente
echo ""
echo "6. Cache utente più grandi:"
du -sh ~/Library/Caches/* 2>/dev/null | sort -h | tail -10

# 7. Analizza Downloads
echo ""
echo "7. File più grandi in Downloads:"
du -sh ~/Downloads/* 2>/dev/null | sort -h | tail -10

# 8. Pulizia cache Python globale
echo ""
echo "8. Pulizia cache pip globale..."
pip cache purge 2>/dev/null || echo "   ℹ️  pip non disponibile"

# 9. Pulizia cache Homebrew (se presente)
echo ""
echo "9. Pulizia cache Homebrew..."
brew cleanup --prune=all 2>/dev/null || echo "   ℹ️  Homebrew non disponibile"

# 10. Verifica spazio finale
echo ""
echo "=== STATO FINALE ==="
df -h / | tail -1

echo ""
echo "=== MEMORIA RAM ==="
vm_stat | awk '/Pages free/ {free=$3*16384/1024/1024} /Pages inactive/ {inactive=$3*16384/1024/1024} END {print "RAM Libera: " free " MB"; print "RAM Inattiva: " inactive " MB"}'
