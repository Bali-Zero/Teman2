#!/bin/bash
# Script per creare un backup del codice essenziale di ZANTARA

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="$PROJECT_ROOT/essential-code-backup"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE_NAME="zantara-essential-code-${TIMESTAMP}.zip"

echo "📦 Creazione backup codice essenziale ZANTARA..."
echo "📍 Directory progetto: $PROJECT_ROOT"
echo "📁 Directory backup: $BACKUP_DIR"

# Crea directory backup
rm -rf "$BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

# 1. README e documentazione principale
echo "📄 Copiando README e documentazione..."
cp "$PROJECT_ROOT/README.md" "$BACKUP_DIR/" 2>/dev/null || true
cp "$PROJECT_ROOT/package.json" "$BACKUP_DIR/" 2>/dev/null || true
cp "$PROJECT_ROOT/tsconfig.json" "$BACKUP_DIR/" 2>/dev/null || true

# 2. Backend TypeScript (essenziale)
echo "🔷 Copiando Backend TypeScript..."
mkdir -p "$BACKUP_DIR/apps/backend-ts"
cp -r "$PROJECT_ROOT/apps/backend-ts/src" "$BACKUP_DIR/apps/backend-ts/" 2>/dev/null || true
cp "$PROJECT_ROOT/apps/backend-ts/package.json" "$BACKUP_DIR/apps/backend-ts/" 2>/dev/null || true
cp "$PROJECT_ROOT/apps/backend-ts/tsconfig.json" "$BACKUP_DIR/apps/backend-ts/" 2>/dev/null || true
cp "$PROJECT_ROOT/apps/backend-ts/Dockerfile" "$BACKUP_DIR/apps/backend-ts/" 2>/dev/null || true

# 3. Backend RAG Python (essenziale)
echo "🐍 Copiando Backend RAG Python..."
mkdir -p "$BACKUP_DIR/apps/backend-rag"
cp -r "$PROJECT_ROOT/apps/backend-rag/backend" "$BACKUP_DIR/apps/backend-rag/" 2>/dev/null || true
cp "$PROJECT_ROOT/apps/backend-rag/requirements.txt" "$BACKUP_DIR/apps/backend-rag/" 2>/dev/null || true
cp "$PROJECT_ROOT/apps/backend-rag/pyproject.toml" "$BACKUP_DIR/apps/backend-rag/" 2>/dev/null || true
cp "$PROJECT_ROOT/apps/backend-rag/Dockerfile" "$BACKUP_DIR/apps/backend-rag/" 2>/dev/null || true
cp "$PROJECT_ROOT/apps/backend-rag/README.md" "$BACKUP_DIR/apps/backend-rag/" 2>/dev/null || true

# 4. Frontend Webapp (essenziale)
echo "🌐 Copiando Frontend Webapp..."
mkdir -p "$BACKUP_DIR/apps/webapp"
cp -r "$PROJECT_ROOT/apps/webapp/js" "$BACKUP_DIR/apps/webapp/" 2>/dev/null || true
cp -r "$PROJECT_ROOT/apps/webapp/css" "$BACKUP_DIR/apps/webapp/" 2>/dev/null || true
cp "$PROJECT_ROOT/deploy/index.html" "$BACKUP_DIR/apps/webapp/" 2>/dev/null || true
cp "$PROJECT_ROOT/apps/webapp/chat.html" "$BACKUP_DIR/apps/webapp/" 2>/dev/null || true
cp "$PROJECT_ROOT/apps/webapp/login.html" "$BACKUP_DIR/apps/webapp/" 2>/dev/null || true

# 5. Configurazioni importanti
echo "⚙️ Copiando configurazioni..."
mkdir -p "$BACKUP_DIR/config"
cp "$PROJECT_ROOT/.gitignore" "$BACKUP_DIR/" 2>/dev/null || true
cp "$PROJECT_ROOT/deploy/fly.toml" "$BACKUP_DIR/" 2>/dev/null || true
cp "$PROJECT_ROOT/docker/docker-compose.yml" "$BACKUP_DIR/" 2>/dev/null || true

# 6. Documentazione essenziale
echo "📚 Copiando documentazione essenziale..."
mkdir -p "$BACKUP_DIR/docs"
find "$PROJECT_ROOT" -maxdepth 1 -name "*.md" -type f | head -10 | while read file; do
    cp "$file" "$BACKUP_DIR/docs/" 2>/dev/null || true
done

# 7. Crea archivio ZIP
echo "📦 Creando archivio ZIP..."
cd "$PROJECT_ROOT"
zip -r "$ARCHIVE_NAME" essential-code-backup/ -q

echo "✅ Backup completato!"
echo "📦 Archivio: $PROJECT_ROOT/$ARCHIVE_NAME"
echo "📊 Dimensione: $(du -h "$ARCHIVE_NAME" | cut -f1)"

# Mostra struttura
echo ""
echo "📁 Struttura backup:"
tree -L 3 "$BACKUP_DIR" 2>/dev/null || find "$BACKUP_DIR" -type f | head -20

echo ""
echo "🚀 Prossimo passo: caricare $ARCHIVE_NAME su Google Drive"
echo "   Folder ID: 1jAGhx7MjWtT0u3vfMRga2sTreV3815ZC"
