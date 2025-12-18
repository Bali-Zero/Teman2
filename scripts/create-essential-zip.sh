#!/bin/bash

# Script per creare ZIP della codebase essenziale
# Esclude node_modules, cache, test, documentazione, etc.

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="$PROJECT_ROOT"
ZIP_NAME="nuzantara-essential-codebase-$(date +%Y%m%d-%H%M%S).zip"
TEMP_DIR=$(mktemp -d)

echo "📦 Creazione ZIP codebase essenziale..."
echo "📍 Root: $PROJECT_ROOT"
echo "📁 Temp: $TEMP_DIR"
echo ""

# Crea struttura directory
mkdir -p "$TEMP_DIR/apps/webapp"
mkdir -p "$TEMP_DIR/apps/backend-rag"
mkdir -p "$TEMP_DIR/apps/backend-ts"
mkdir -p "$TEMP_DIR/scripts"

# === WEBAPP ESSENZIALE ===
echo "📱 Copiando webapp essenziale..."
rsync -av --exclude='node_modules' \
  --exclude='*.md' \
  --exclude='*.log' \
  --exclude='.DS_Store' \
  --exclude='*.swp' \
  --exclude='*.swo' \
  --exclude='test' \
  --exclude='tests' \
  --exclude='__tests__' \
  --exclude='coverage' \
  --exclude='.git' \
  --exclude='.vscode' \
  --exclude='.idea' \
  "$PROJECT_ROOT/apps/webapp/" "$TEMP_DIR/apps/webapp/" \
  --include='*.html' \
  --include='*.js' \
  --include='*.css' \
  --include='*.json' \
  --include='*.svg' \
  --include='*.png' \
  --include='*.jpg' \
  --include='*.ico' \
  --include='*.mp3' \
  --include='*.mp4' \
  --include='service-worker*.js' \
  --include='manifest.json' \
  --include='CNAME' \
  --include='_redirects' \
  --include='deploy/' \
  --include='assets/' \
  --include='css/' \
  --include='js/' \
  --include='images/' \
  --exclude='*' 2>/dev/null || true

# === BACKEND RAG ESSENZIALE ===
echo "🐍 Copiando backend RAG essenziale..."
rsync -av --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='*.pyo' \
  --exclude='*.pyd' \
  --exclude='.Python' \
  --exclude='*.md' \
  --exclude='*.log' \
  --exclude='.DS_Store' \
  --exclude='test' \
  --exclude='tests' \
  --exclude='*.backup' \
  --exclude='.git' \
  --exclude='.venv' \
  --exclude='venv' \
  --exclude='env' \
  "$PROJECT_ROOT/apps/backend-rag/" "$TEMP_DIR/apps/backend-rag/" \
  --include='*.py' \
  --include='*.txt' \
  --include='*.toml' \
  --include='*.yaml' \
  --include='*.yml' \
  --include='Dockerfile' \
  --include='.dockerignore' \
  --include='deploy/fly.toml' \
  --include='requirements.txt' \
  --include='backend/' \
  --include='scripts/' \
  --exclude='*' 2>/dev/null || true

# === BACKEND TS ESSENZIALE ===
echo "📘 Copiando backend TypeScript essenziale..."
rsync -av --exclude='node_modules' \
  --exclude='*.md' \
  --exclude='*.log' \
  --exclude='.DS_Store' \
  --exclude='test' \
  --exclude='tests' \
  --exclude='__tests__' \
  --exclude='coverage' \
  --exclude='docs/api' \
  --exclude='.git' \
  --exclude='dist' \
  --exclude='build' \
  --exclude='*.tsbuildinfo' \
  "$PROJECT_ROOT/apps/backend-ts/" "$TEMP_DIR/apps/backend-ts/" \
  --include='*.ts' \
  --include='*.js' \
  --include='*.json' \
  --include='*.toml' \
  --include='Dockerfile' \
  --include='.dockerignore' \
  --include='deploy/fly.toml' \
  --include='tsconfig.json' \
  --include='src/' \
  --exclude='*' 2>/dev/null || true

# === SCRIPTS ESSENZIALI ===
echo "🔧 Copiando scripts essenziali..."
rsync -av --exclude='*.md' \
  --exclude='*.log' \
  "$PROJECT_ROOT/scripts/" "$TEMP_DIR/scripts/" \
  --include='*.sh' \
  --include='*.js' \
  --include='*.py' \
  --exclude='*' 2>/dev/null || true

# === FILE ROOT ESSENZIALI ===
echo "📄 Copiando file root essenziali..."
if [ -f "$PROJECT_ROOT/.gitignore" ]; then
  cp "$PROJECT_ROOT/.gitignore" "$TEMP_DIR/" 2>/dev/null || true
fi
if [ -f "$PROJECT_ROOT/README.md" ]; then
  cp "$PROJECT_ROOT/README.md" "$TEMP_DIR/" 2>/dev/null || true
fi
if [ -f "$PROJECT_ROOT/package.json" ]; then
  cp "$PROJECT_ROOT/package.json" "$TEMP_DIR/" 2>/dev/null || true
fi

# === CREA ZIP ===
echo ""
echo "🗜️  Creando ZIP..."
cd "$TEMP_DIR"
zip -r "$OUTPUT_DIR/$ZIP_NAME" . -q
cd "$PROJECT_ROOT"

# === PULIZIA ===
rm -rf "$TEMP_DIR"

# === STATISTICHE ===
ZIP_SIZE=$(du -h "$OUTPUT_DIR/$ZIP_NAME" | cut -f1)
echo ""
echo "✅ ZIP creato con successo!"
echo "📦 File: $ZIP_NAME"
echo "📊 Dimensione: $ZIP_SIZE"
echo "📍 Posizione: $OUTPUT_DIR"
echo ""
echo "📋 Contenuto essenziale:"
echo "  ✅ Frontend webapp (HTML, JS, CSS, assets)"
echo "  ✅ Backend RAG (Python, requirements, Dockerfile)"
echo "  ✅ Backend TypeScript (TS, config, Dockerfile)"
echo "  ✅ Scripts essenziali"
echo ""
echo "❌ Escluso:"
echo "  ❌ node_modules"
echo "  ❌ __pycache__"
echo "  ❌ File di test"
echo "  ❌ Documentazione .md"
echo "  ❌ File temporanei e cache"
