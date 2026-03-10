#!/bin/bash
# Script completo per pulizia memoria e spazio su Mac

set +e  # Non fermarsi su errori

echo "=========================================="
echo "  PULIZIA COMPLETA MEMORIA E SPAZIO MAC"
echo "=========================================="
echo "Data: $(date)"
echo ""

# Colori per output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Funzione per formattare dimensioni
format_size() {
    local size=$1
    if [ $size -lt 1024 ]; then
        echo "${size}B"
    elif [ $size -lt 1048576 ]; then
        echo "$((size/1024))KB"
    elif [ $size -lt 1073741824 ]; then
        echo "$((size/1024/1024))MB"
    else
        echo "$((size/1024/1024/1024))GB"
    fi
}

# 1. STATO INIZIALE
echo -e "${YELLOW}=== STATO INIZIALE ===${NC}"
echo "Spazio disco:"
df -h / | tail -1
echo ""
echo "Memoria RAM:"
vm_stat | awk '/Pages free/ {free=$3*16384/1024/1024} /Pages inactive/ {inactive=$3*16384/1024/1024} END {printf "RAM Libera: %.1f MB\nRAM Inattiva: %.1f MB\n", free, inactive}'
echo ""

# 2. PULIZIA CACHE SISTEMA
echo -e "${GREEN}=== PULIZIA CACHE SISTEMA ===${NC}"

echo "2.1 Cache utente..."
CACHE_SIZE_BEFORE=$(du -sk ~/Library/Caches 2>/dev/null | awk '{print $1}')
find ~/Library/Caches -type f -atime +7 -size +10M -delete 2>/dev/null || true
CACHE_SIZE_AFTER=$(du -sk ~/Library/Caches 2>/dev/null | awk '{print $1}')
FREED=$((CACHE_SIZE_BEFORE - CACHE_SIZE_AFTER))
if [ $FREED -gt 0 ]; then
    echo -e "   ${GREEN}✅ Liberati $(format_size $((FREED*1024)))${NC}"
else
    echo "   ℹ️  Nessun file grande da rimuovere"
fi

echo "2.2 Cache npm..."
if [ -d ~/.npm ]; then
    NPM_SIZE_BEFORE=$(du -sk ~/.npm 2>/dev/null | awk '{print $1}')
    npm cache clean --force 2>/dev/null || true
    rm -rf ~/.npm/_cacache 2>/dev/null || true
    NPM_SIZE_AFTER=$(du -sk ~/.npm 2>/dev/null | awk '{print $1}')
    FREED=$((NPM_SIZE_BEFORE - NPM_SIZE_AFTER))
    if [ $FREED -gt 0 ]; then
        echo -e "   ${GREEN}✅ Liberati $(format_size $((FREED*1024)))${NC}"
    fi
fi

echo "2.3 Cache pip..."
pip cache purge 2>/dev/null && echo "   ✅ Cache pip pulita" || echo "   ℹ️  pip non disponibile"

echo "2.4 Cache Homebrew..."
brew cleanup --prune=all 2>/dev/null && echo "   ✅ Cache Homebrew pulita" || echo "   ℹ️  Homebrew non disponibile"

echo ""

# 3. PULIZIA FILE TEMPORANEI
echo -e "${GREEN}=== PULIZIA FILE TEMPORANEI ===${NC}"

echo "3.1 File temporanei sistema..."
TMP_COUNT=$(find /tmp -type f -mtime +1 2>/dev/null | wc -l | tr -d ' ')
if [ "$TMP_COUNT" -gt 0 ]; then
    find /tmp -type f -mtime +1 -delete 2>/dev/null || true
    echo "   ✅ Rimossi $TMP_COUNT file vecchi"
else
    echo "   ℹ️  Nessun file vecchio da rimuovere"
fi

echo "3.2 File .DS_Store nel progetto..."
DS_COUNT=$(find . -name ".DS_Store" -type f 2>/dev/null | wc -l | tr -d ' ')
if [ "$DS_COUNT" -gt 0 ]; then
    find . -name ".DS_Store" -delete 2>/dev/null || true
    echo "   ✅ Rimossi $DS_COUNT file .DS_Store"
fi

echo "3.3 File Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
echo "   ✅ Cache Python rimossa"

echo ""

# 4. PULIZIA LOG
echo -e "${GREEN}=== PULIZIA LOG ===${NC}"
LOG_COUNT=$(find ~/Library/Logs -type f -mtime +30 2>/dev/null | wc -l | tr -d ' ')
if [ "$LOG_COUNT" -gt 0 ]; then
    find ~/Library/Logs -type f -mtime +30 -delete 2>/dev/null || true
    echo "   ✅ Rimossi $LOG_COUNT log vecchi"
else
    echo "   ℹ️  Nessun log vecchio da rimuovere"
fi
echo ""

# 5. PULIZIA TRASH
echo -e "${GREEN}=== PULIZIA TRASH ===${NC}"
TRASH_SIZE=$(du -sk ~/.Trash 2>/dev/null | awk '{print $1}')
if [ "$TRASH_SIZE" -gt 1024 ]; then  # >1MB
    rm -rf ~/.Trash/* 2>/dev/null || true
    echo -e "   ${GREEN}✅ Trash svuotato ($(format_size $((TRASH_SIZE*1024))))${NC}"
else
    echo "   ℹ️  Trash già vuoto"
fi
echo ""

# 6. ANALISI FILE GRANDI NEL PROGETTO
echo -e "${YELLOW}=== ANALISI FILE GRANDI ===${NC}"
echo "File più grandi nel progetto (>50MB):"
find . -type f -size +50M ! -path "./.git/*" ! -path "./node_modules/*" -exec ls -lh {} \; 2>/dev/null | \
    awk '{print "   " $5 " - " $9}' | head -10 || echo "   Nessun file grande trovato"
echo ""

# 7. ANALISI NODE_MODULES
echo -e "${YELLOW}=== ANALISI NODE_MODULES ===${NC}"
echo "Cartelle node_modules:"
find . -name "node_modules" -type d -prune -exec du -sh {} \; 2>/dev/null | \
    sort -h | head -10 || echo "   Nessuna cartella node_modules trovata"
echo ""

# 8. LIBERAZIONE MEMORIA RAM
echo -e "${GREEN}=== LIBERAZIONE MEMORIA RAM ===${NC}"
echo "⚠️  Per liberare memoria RAM inattiva, esegui:"
echo "   sudo purge"
echo "   (richiede password amministratore)"
echo ""

# 9. STATO FINALE
echo -e "${YELLOW}=== STATO FINALE ===${NC}"
echo "Spazio disco:"
df -h / | tail -1
echo ""
echo "Memoria RAM:"
vm_stat | awk '/Pages free/ {free=$3*16384/1024/1024} /Pages inactive/ {inactive=$3*16384/1024/1024} END {printf "RAM Libera: %.1f MB\nRAM Inattiva: %.1f MB\n", free, inactive}'
echo ""

# 10. SUGGERIMENTI
echo -e "${YELLOW}=== SUGGERIMENTI ===${NC}"
echo "Per liberare più spazio:"
echo "1. Analizza il Desktop (50GB):"
echo "   du -sh ~/Desktop/* | sort -h | tail -10"
echo ""
echo "2. Analizza Downloads:"
echo "   du -sh ~/Downloads/* | sort -h | tail -10"
echo ""
echo "3. Rimuovi node_modules non necessari:"
echo "   find . -name node_modules -type d -prune -exec du -sh {} \; | sort -h"
echo ""
echo "4. Libera memoria RAM:"
echo "   sudo purge"
echo ""

echo -e "${GREEN}✅ Pulizia completata!${NC}"
