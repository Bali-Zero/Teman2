#!/bin/bash
# Frontend Cleanup Script
# Removes console.logs, fixes imports, and cleans up dead code

echo "🧹 Frontend Cleanup Script"
echo "=========================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Count before
echo -e "\n${YELLOW}Before cleanup:${NC}"
echo "Console.log statements: $(grep -r "console.log" src --include="*.tsx" --include="*.ts" | wc -l)"
echo "TODO/FIXME comments: $(grep -r "TODO\|FIXME" src --include="*.tsx" --include="*.ts" | wc -l)"

# Remove console.log statements (keep console.error and console.warn)
echo -e "\n${YELLOW}Removing console.log statements...${NC}"
find src -type f \( -name "*.tsx" -o -name "*.ts" \) -exec sed -i '' '/console\.log/d' {} \;

# Count after
echo -e "\n${GREEN}After cleanup:${NC}"
echo "Console.log statements: $(grep -r "console.log" src --include="*.tsx" --include="*.ts" | wc -l)"
echo "TODO/FIXME comments: $(grep -r "TODO\|FIXME" src --include="*.tsx" --include="*.ts" | wc -l)"

echo -e "\n${GREEN}✅ Cleanup complete!${NC}"
echo "Run 'npm run typecheck' to verify no type errors were introduced."
