#!/usr/bin/env bash
# install-handbook.sh — installa Employee Handbook sul Desktop del profilo balizero
#                       in modalità immutable (non spostabile, non eliminabile, non rinominabile)
#
# Esegui SOLO sul profilo macOS `balizero` (verificato all'avvio).
# Tipicamente chiamato da Antonello durante setup Mac di ogni dipendente.
#
# Uso:
#   bash install-handbook.sh
#
# Cosa fa:
#   1. Verifica di essere sul profilo balizero
#   2. Copia il PDF dell'Handbook dalla cartella mac-client/handbook-asset/
#      al Desktop del profilo balizero (~/Desktop/)
#   3. Imposta permessi read-only (0444) per gruppo/altri
#   4. Imposta il flag macOS `uchg` (user immutable) che blocca:
#      - rinominazione
#      - spostamento
#      - eliminazione
#      - modifica del contenuto
#   5. Verifica che il file sia visibile + immutable
#
# Per disinstallare (solo Antonello):
#   sudo chflags nouchg ~/Desktop/employee-handbook-v1-ID.pdf
#   rm ~/Desktop/employee-handbook-v1-ID.pdf

set -euo pipefail

# Verifica profilo
CURRENT_USER=$(whoami)
if [[ "$CURRENT_USER" != "balizero" ]]; then
    echo "❌ Devi eseguire questo installer dal profilo macOS 'balizero'"
    echo "   Profilo attuale: $CURRENT_USER"
    exit 1
fi

echo "═══ Bali Zero Employee Handbook Installer ═══"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_PDF="$SCRIPT_DIR/handbook-asset/employee-handbook-v1-ID.pdf"
DEST_PDF="$HOME/Desktop/employee-handbook-v1-ID.pdf"

# Verifica sorgente
if [[ ! -f "$SOURCE_PDF" ]]; then
    echo "❌ File sorgente non trovato: $SOURCE_PDF"
    echo "   Assicurati di eseguire dall'interno della cartella mac-client/"
    exit 1
fi

SOURCE_SIZE=$(stat -f%z "$SOURCE_PDF")
echo "  Sorgente: $SOURCE_PDF ($SOURCE_SIZE bytes)"

# Se file destinazione esiste già con flag uchg, rimuovi flag prima di sovrascrivere
if [[ -f "$DEST_PDF" ]]; then
    echo "  File già presente sul Desktop, rimuovo flag immutable per aggiornamento..."
    chflags nouchg "$DEST_PDF" 2>/dev/null || true
    rm -f "$DEST_PDF"
fi

# Copia
cp "$SOURCE_PDF" "$DEST_PDF"
echo "  Copiato → $DEST_PDF"

# Permessi read-only per tutti (owner balizero può leggere, non scrivere)
chmod 0444 "$DEST_PDF"
echo "  Permessi impostati a 0444 (read-only)"

# macOS user-immutable flag — blocca rename/move/delete/modify
chflags uchg "$DEST_PDF"
echo "  Flag immutable (uchg) applicato"

# Verifica
echo ""
echo "═══ Verifica ═══"
ls -laO "$DEST_PDF"
echo ""

# Test: prova a eliminare (deve fallire)
if rm "$DEST_PDF" 2>/dev/null; then
    echo "❌ ATTENZIONE: il file è ancora eliminabile — flag non applicato correttamente"
    exit 1
else
    echo "✅ File NON eliminabile (test rm fallito come atteso)"
fi

# Test: prova a rinominare (deve fallire)
if mv "$DEST_PDF" "${DEST_PDF}.test" 2>/dev/null; then
    echo "❌ ATTENZIONE: il file è ancora rinominabile"
    mv "${DEST_PDF}.test" "$DEST_PDF" 2>/dev/null || true
    exit 1
else
    echo "✅ File NON rinominabile (test mv fallito come atteso)"
fi

echo ""
echo "═══ Installazione completata ═══"
echo ""
echo "Il file Handbook è ora visibile sul Desktop del profilo balizero."
echo "Il dipendente può aprirlo con doppio click ma NON può:"
echo "  - spostarlo in un'altra cartella"
echo "  - rinominarlo"
echo "  - eliminarlo"
echo "  - modificarne il contenuto"
echo ""
echo "Per aggiornare a una nuova versione (solo Antonello):"
echo "  chflags nouchg $DEST_PDF"
echo "  rm $DEST_PDF"
echo "  bash install-handbook.sh"
