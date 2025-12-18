#!/bin/bash

# System Optimizer - Automatic Performance Tuning
# Esegui quotidianamente per mantenere il Mac veloce

echo "🚀 Starting System Optimizer..."

# 1. Memory Management
echo "🧠 Cleaning memory..."
sudo purge

# 2. Clear Caches
echo "🗂️  Clearing system caches..."
rm -rf ~/Library/Caches/*
sudo rm -rf /Library/Caches/*

# 3. Optimize Memory Compression
echo "⚡ Optimizing memory compression..."
sudo sysctl -w vm.compressor_mode=4

# 4. Disable Unused Services
echo "🔌 Disabling unused services..."
killall -STOP photoanalysisd 2>/dev/null
killall -STOP Siri 2>/dev/null
killall -STOP mdworker 2>/dev/null

# 5. Clean Docker (se installato)
if command -v docker &> /dev/null; then
    echo "🐳 Cleaning Docker..."
    docker system prune -f
fi

# 6. Optimize SSD (TRIM)
echo "💾 Optimizing SSD..."
sudo trimforce enable 2>/dev/null || echo "TRIM already enabled"

# 7. Reset DNS Cache
echo "🌐 Resetting DNS cache..."
sudo dscacheutil -flushcache

# 8. Display optimization
echo "🖥️  Optimizing display..."
defaults write com.apple.dock expose-animation-duration -float 0.0
killall Dock

# 9. Network optimization
echo "📶 Optimizing network..."
sudo sysctl -w net.inet.tcp.delayed_ack=0

echo "✅ System optimization completed!"

# Show results
echo ""
echo "📊 Current System Status:"
uptime
top -l 1 | grep "PhysMem"
