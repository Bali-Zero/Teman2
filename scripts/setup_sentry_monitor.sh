#!/bin/bash
# Setup Sentry Monitor for Nuzantara
# ====================================
# Installa/disinstalla il monitor Sentry automatico su macOS

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PLIST_NAME="com.nuzantara.sentry-monitor.plist"
PLIST_SOURCE="$SCRIPT_DIR/$PLIST_NAME"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

install_monitor() {
    echo -e "${GREEN}Installing Sentry Monitor...${NC}"

    # Create directories
    mkdir -p "$HOME/Library/LaunchAgents"
    mkdir -p "$PROJECT_ROOT/logs"
    mkdir -p "$PROJECT_ROOT/data"

    # Copy plist
    cp "$PLIST_SOURCE" "$PLIST_DEST"

    # Load the agent
    launchctl load "$PLIST_DEST"

    echo -e "${GREEN}✓ Monitor installed and started${NC}"
    echo ""
    echo "The monitor will check Sentry every 5 minutes."
    echo "Logs: $PROJECT_ROOT/logs/sentry_monitor.log"
    echo ""
    echo "Commands:"
    echo "  Check status:  launchctl list | grep nuzantara"
    echo "  View logs:     tail -f $PROJECT_ROOT/logs/sentry_monitor.log"
    echo "  Stop:          launchctl unload $PLIST_DEST"
    echo "  Uninstall:     $0 uninstall"
}

uninstall_monitor() {
    echo -e "${YELLOW}Uninstalling Sentry Monitor...${NC}"

    if [ -f "$PLIST_DEST" ]; then
        launchctl unload "$PLIST_DEST" 2>/dev/null || true
        rm -f "$PLIST_DEST"
        echo -e "${GREEN}✓ Monitor uninstalled${NC}"
    else
        echo -e "${YELLOW}Monitor not installed${NC}"
    fi
}

status_monitor() {
    echo "Sentry Monitor Status"
    echo "====================="

    if launchctl list | grep -q "nuzantara.sentry"; then
        echo -e "${GREEN}✓ Running${NC}"
        launchctl list | grep nuzantara
    else
        echo -e "${YELLOW}○ Not running${NC}"
    fi

    echo ""
    if [ -f "$PROJECT_ROOT/data/sentry_report.md" ]; then
        echo "Last report: $(stat -f '%Sm' "$PROJECT_ROOT/data/sentry_report.md")"
        ISSUES=$(grep -c "^## \[" "$PROJECT_ROOT/data/sentry_report.md" 2>/dev/null || echo "0")
        echo "Issues found: $ISSUES"
    else
        echo "No reports generated yet"
    fi
}

test_monitor() {
    echo -e "${GREEN}Testing Sentry connection...${NC}"
    cd "$PROJECT_ROOT"
    python scripts/sentry_monitor.py
}

# Main
case "${1:-}" in
    install)
        install_monitor
        ;;
    uninstall)
        uninstall_monitor
        ;;
    status)
        status_monitor
        ;;
    test)
        test_monitor
        ;;
    *)
        echo "Sentry Monitor Setup"
        echo "===================="
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  install    Install and start the monitor"
        echo "  uninstall  Stop and remove the monitor"
        echo "  status     Check monitor status"
        echo "  test       Test Sentry connection"
        echo ""
        echo "Current status:"
        status_monitor
        ;;
esac
