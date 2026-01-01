#!/bin/bash
# Rollback script for Nuzantara deployments
# Allows quick rollback to previous versions on Fly.io

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if flyctl is installed
if ! command -v flyctl &> /dev/null; then
    echo -e "${RED}❌ flyctl is not installed${NC}"
    echo "Install it from: https://fly.io/docs/hands-on/install-flyctl/"
    exit 1
fi

echo -e "${BLUE}🔄 Nuzantara Rollback Tool${NC}"
echo "=================================="

# Function to show releases
show_releases() {
    local app=$1
    echo ""
    echo -e "${YELLOW}Recent releases for $app:${NC}"
    flyctl releases list --app "$app" --json | jq -r '.[] | "\(.version) - \(.status) - \(.created_at)"' | head -10
}

# Function to rollback
rollback_app() {
    local app=$1
    local version=$2
    
    echo ""
    echo -e "${YELLOW}Rolling back $app...${NC}"
    
    if [ -n "$version" ]; then
        echo "Rolling back to version $version"
        flyctl releases rollback --app "$app" --version "$version" -y
    else
        echo "Rolling back to previous version"
        flyctl releases rollback --app "$app" -y
    fi
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Rollback successful${NC}"
        return 0
    else
        echo -e "${RED}✗ Rollback failed${NC}"
        return 1
    fi
}

# Main menu
echo ""
echo "Select service to rollback:"
echo "1) Backend RAG (nuzantara-rag)"
echo "2) Mouth Frontend (nuzantara-mouth)"
echo "3) Both services"
echo "4) View releases only"
echo "5) Exit"
echo ""
read -p "Enter choice [1-5]: " choice

case $choice in
    1)
        show_releases "nuzantara-rag"
        echo ""
        read -p "Enter version to rollback to (or press Enter for previous): " version
        read -p "Confirm rollback? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rollback_app "nuzantara-rag" "$version"
        fi
        ;;
    2)
        show_releases "nuzantara-mouth"
        echo ""
        read -p "Enter version to rollback to (or press Enter for previous): " version
        read -p "Confirm rollback? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rollback_app "nuzantara-mouth" "$version"
        fi
        ;;
    3)
        echo -e "${YELLOW}Rolling back both services...${NC}"
        show_releases "nuzantara-rag"
        show_releases "nuzantara-mouth"
        echo ""
        read -p "Confirm rollback of BOTH services? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rollback_app "nuzantara-rag"
            rollback_app "nuzantara-mouth"
        fi
        ;;
    4)
        show_releases "nuzantara-rag"
        show_releases "nuzantara-mouth"
        ;;
    5)
        echo "Exiting..."
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

# Run health check after rollback
echo ""
read -p "Run health check? (Y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    if [ -f "scripts/deployment/health-check.sh" ]; then
        ./scripts/deployment/health-check.sh
    else
        echo -e "${YELLOW}⚠ Health check script not found${NC}"
    fi
fi

echo ""
echo -e "${GREEN}✅ Rollback process complete${NC}"
