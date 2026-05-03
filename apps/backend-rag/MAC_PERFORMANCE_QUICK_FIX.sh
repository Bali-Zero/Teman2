#!/bin/bash
# Mac Performance Quick Fix Script
# Data: 2026-01-16
# Obiettivo: Liberare RAM e CPU immediatamente

set -e

echo "=== MAC PERFORMANCE QUICK FIX ==="
echo ""

# 1. Mostrare stato attuale
echo "1. Stato Attuale:"
echo "   RAM Libera:"
vm_stat | grep "Pages free" | awk '{print "     " $3*16384/1024/1024 " MB"}'
echo "   Processi npm/node:"
ps aux | grep -E "npm|node" | grep -v grep | wc -l | awk '{print "     " $1 " processi"}'
echo "   VM Attive:"
ps aux | grep VirtualMachine | grep -v grep | wc -l | awk '{print "     " $1 " VM"}'
echo ""

# 2. Pulire cache
echo "2. Pulizia Cache..."
rm -rf ~/Library/Caches/CloudKit/* 2>/dev/null && echo "   ✅ CloudKit cache pulita"
rm -rf ~/Library/Caches/ms-playwright-go/* 2>/dev/null && echo "   ✅ Playwright cache pulita"
rm -rf ~/Library/Caches/us.zoom.xos/* 2>/dev/null && echo "   ✅ Zoom cache pulita"
rm -rf ~/Library/Caches/node-gyp/* 2>/dev/null && echo "   ✅ node-gyp cache pulita"
brew cleanup --prune=all 2>/dev/null && echo "   ✅ Homebrew cache pulita" || echo "   ⚠️  Homebrew non disponibile"
echo ""

# 3. Mostrare processi npm pesanti
echo "3. Processi npm/node attivi (top 10 per CPU):"
ps aux | grep -E "npm|node" | grep -v grep | awk '{if ($3 > 1.0) print "   PID " $2 ": " $3 "% CPU - " $11}' | sort -rn | head -10
echo ""

# 4. Istruzioni per azioni manuali
echo "4. Azioni Manuali Richieste:"
echo ""
echo "   🔴 CRITICO - Chiudere VM non necessarie:"
echo "      - Apri Activity Monitor"
echo "      - Cerca 'VirtualMachine'"
echo "      - Chiudi VM non necessarie"
echo "      - Spazio liberabile: ~10 GB RAM"
echo ""
echo "   ⚠️  Terminare processi npm non necessari:"
echo "      ps aux | grep npm | grep -v grep"
echo "      kill <PID>  # Per ogni processo non necessario"
echo ""
echo "   ⚠️  Purge memoria (richiede password):"
echo "      sudo purge"
echo ""
echo "=== FINE ==="
echo ""
echo "Dopo le azioni manuali, verifica con:"
echo "  vm_stat | grep 'Pages free'"
echo "  top -l 1 -o mem | head -10"
