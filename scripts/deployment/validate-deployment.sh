#!/bin/bash
# Pre-deployment validation script for Nuzantara platform
# Validates configuration, dependencies, and environment before deployment

set -e

echo "🔍 Starting pre-deployment validation..."

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Error counter
ERRORS=0

# Function to check command existence
check_command() {
    if command -v "$1" &> /dev/null; then
        echo -e "${GREEN}✓${NC} $1 is installed"
        return 0
    else
        echo -e "${RED}✗${NC} $1 is not installed"
        ERRORS=$((ERRORS + 1))
        return 1
    fi
}

# Function to check file existence
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} Found $1"
        return 0
    else
        echo -e "${RED}✗${NC} Missing $1"
        ERRORS=$((ERRORS + 1))
        return 1
    fi
}

# Function to validate JSON/YAML syntax
validate_syntax() {
    local file=$1
    local type=$2
    
    if [ "$type" == "json" ]; then
        if jq empty "$file" 2>/dev/null; then
            echo -e "${GREEN}✓${NC} Valid JSON: $file"
            return 0
        else
            echo -e "${RED}✗${NC} Invalid JSON: $file"
            ERRORS=$((ERRORS + 1))
            return 1
        fi
    fi
}

echo ""
echo "==================================="
echo "1. Checking Required Tools"
echo "==================================="
check_command "docker"
check_command "node"
check_command "npm"
check_command "git"
check_command "curl"
check_command "jq"

echo ""
echo "==================================="
echo "2. Checking Project Structure"
echo "==================================="
check_file "package.json"
check_file "docker-compose.yml"
check_file ".env.example"
check_file "apps/backend-rag/Dockerfile"
check_file "apps/backend-rag/fly.toml"
check_file "apps/mouth/Dockerfile"
# check_file "apps/mouth/fly.toml" # Migrated to Vercel

echo ""
echo "==================================="
echo "3. Validating Configuration Files"
echo "==================================="

# Validate package.json
if [ -f "package.json" ]; then
    validate_syntax "package.json" "json"
fi

# Check fly.toml files for required fields
if [ -f "apps/backend-rag/fly.toml" ]; then
    if grep -q "app = " "apps/backend-rag/fly.toml"; then
        echo -e "${GREEN}✓${NC} Backend RAG fly.toml has app name"
    else
        echo -e "${RED}✗${NC} Backend RAG fly.toml missing app name"
        ERRORS=$((ERRORS + 1))
    fi
fi

if [ -f "apps/mouth/fly.toml" ]; then
    if grep -q "app = " "apps/mouth/fly.toml"; then
        echo -e "${GREEN}✓${NC} Mouth fly.toml has app name"
    else
        echo -e "${RED}✗${NC} Mouth fly.toml missing app name"
        ERRORS=$((ERRORS + 1))
    fi
fi

echo ""
echo "==================================="
echo "4. Checking Git Status"
echo "==================================="
if git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Git repository detected"
    
    # Check for uncommitted changes
    if [ -z "$(git status --porcelain)" ]; then
        echo -e "${GREEN}✓${NC} No uncommitted changes"
    else
        echo -e "${YELLOW}⚠${NC}  Uncommitted changes detected"
    fi
    
    # Show current branch
    BRANCH=$(git branch --show-current)
    echo -e "${GREEN}ℹ${NC}  Current branch: $BRANCH"
else
    echo -e "${RED}✗${NC} Not a git repository"
    ERRORS=$((ERRORS + 1))
fi

echo ""
echo "==================================="
echo "5. Checking Dependencies"
echo "==================================="
if [ -f "package-lock.json" ]; then
    echo -e "${GREEN}✓${NC} package-lock.json exists"
else
    echo -e "${YELLOW}⚠${NC}  package-lock.json not found"
fi

if [ -d "node_modules" ]; then
    echo -e "${GREEN}✓${NC} node_modules directory exists"
else
    echo -e "${YELLOW}⚠${NC}  node_modules not found, run: npm install"
fi

echo ""
echo "==================================="
echo "6. Docker Build Test (Optional)"
echo "==================================="
if check_command "docker" >/dev/null 2>&1; then
    read -p "Run Docker build test? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Building backend-rag..."
        if docker build -t nuzantara-backend-test apps/backend-rag; then
            echo -e "${GREEN}✓${NC} Backend RAG Docker build successful"
        else
            echo -e "${RED}✗${NC} Backend RAG Docker build failed"
            ERRORS=$((ERRORS + 1))
        fi
    fi
fi

echo ""
echo "==================================="
echo "Validation Summary"
echo "==================================="

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ All validation checks passed!${NC}"
    echo "✅ Ready for deployment"
    exit 0
else
    echo -e "${RED}✗ Validation failed with $ERRORS error(s)${NC}"
    echo "❌ Please fix the errors before deploying"
    exit 1
fi
