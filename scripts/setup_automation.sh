#!/bin/bash

# Setup Automation Scripts
# Install automatic monitoring for optimal performance

echo "🔧 Setting up automatic system monitoring..."

# Install scripts
SCRIPTS_DIR="/Users/antonellosiano/Desktop/nuzantara/scripts"
PLIST_DIR="$HOME/Library/LaunchAgents"

# Create plist directory
mkdir -p "$PLIST_DIR"

# Copy plist file
cp "$SCRIPTS_DIR/launchd_com.nuzantara.memory.plist" "$PLIST_DIR/"

# Load the launch agent
launchctl load "$PLIST_DIR/launchd_com.nuzantara.memory.plist"

echo "✅ Automatic monitoring installed!"
echo ""
echo "📋 Available commands:"
echo "  • Start monitor: launchctl load ~/Library/LaunchAgents/com.nuzantara.memory.plist"
echo "  • Stop monitor: launchctl unload ~/Library/LaunchAgents/com.nuzantara.memory.plist"
echo "  • Run optimizer: $SCRIPTS_DIR/system_optimizer.sh"
echo "  • View logs: tail -f /tmp/memory_monitor.log"
echo ""
echo "🎯 Monitor runs every 30 seconds"
echo "🚀 System optimizer can be run daily"
