#!/bin/bash
# Script per pulire artefatti generati dal progetto
# Rimuove file temporanei, cache, coverage reports, etc.

set -e

echo "🧹 Pulizia artefatti generati..."

# Directory da rimuovere
DIRS_TO_REMOVE=(
    "htmlcov"
    ".pytest_cache"
    "coverage"
    "__pycache__"
    ".next"
    "out"
    "build"
    "dist"
    "node_modules/.cache"
    "test-results"
    "test_results"
    "playwright-report"
    ".playwright"
    "testsprite_tests/tmp"
)

# File da rimuovere
FILES_TO_REMOVE=(
    ".coverage"
    "coverage.xml"
    "*.pyc"
    "*.pyo"
    "*.pyd"
    ".Python"
    "*.so"
    "*.egg"
    "*.egg-info"
    "*.log"
)

# Rimuovi directory
for dir in "${DIRS_TO_REMOVE[@]}"; do
    if [ -d "$dir" ]; then
        echo "  🗑️  Rimuovendo $dir/"
        rm -rf "$dir"
    fi
done

# Rimuovi file (con pattern matching)
for pattern in "${FILES_TO_REMOVE[@]}"; do
    find . -name "$pattern" -not -path "*/node_modules/*" -not -path "*/.git/*" -not -path "*/.venv/*" -type f -delete 2>/dev/null || true
done

# Rimuovi __pycache__ ricorsivamente (ma non in .venv)
find . -type d -name "__pycache__" -not -path "*/.venv/*" -not -path "*/node_modules/*" -not -path "*/.git/*" -exec rm -rf {} + 2>/dev/null || true

# Rimuovi .pyc files
find . -name "*.pyc" -not -path "*/.venv/*" -not -path "*/node_modules/*" -not -path "*/.git/*" -delete 2>/dev/null || true

# Rimuovi .coverage.* files
find . -name ".coverage.*" -not -path "*/.venv/*" -not -path "*/node_modules/*" -not -path "*/.git/*" -delete 2>/dev/null || true

echo "✅ Pulizia completata!"

