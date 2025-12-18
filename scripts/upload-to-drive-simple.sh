#!/bin/bash
# Script semplificato per caricare su Google Drive usando curl

ARCHIVE=$(ls -t zantara-essential-code-*.zip 2>/dev/null | head -1)
DRIVE_FOLDER_ID="1jAGhx7MjWtT0u3vfMRga2sTreV3815ZC"
BACKEND_URL="${BACKEND_URL:-https://nuzantara-backend.fly.dev}"

if [ -z "$ARCHIVE" ]; then
    echo "❌ Nessun archivio trovato!"
    echo "💡 Esegui prima: ./scripts/backup-essential-code.sh"
    exit 1
fi

echo "📦 Archivio: $ARCHIVE"
echo "📊 Dimensione: $(du -h "$ARCHIVE" | cut -f1)"
echo ""
echo "📤 Per caricare su Google Drive, usa uno di questi metodi:"
echo ""
echo "1️⃣  Metodo manuale (consigliato):"
echo "   - Apri: https://drive.google.com/drive/folders/$DRIVE_FOLDER_ID"
echo "   - Trascina il file: $ARCHIVE"
echo ""
echo "2️⃣  Usa l'API del backend (richiede autenticazione):"
echo "   BACKEND_URL=$BACKEND_URL node scripts/upload-to-drive.js"
echo ""
echo "3️⃣  Usa gdrive CLI (se installato):"
echo "   gdrive upload --parent $DRIVE_FOLDER_ID $ARCHIVE"
echo ""
