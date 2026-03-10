#!/bin/bash
# NUZANTARA VISION TOOL (macOS version)

TEMP_IMG="/tmp/nuzantara_vision.png"

if [ "$1" == "--webcam" ]; then
    echo "📸 Attivazione Webcam..."
    imagesnap "$TEMP_IMG"
    SHIFT_ARG=2
else
    echo "🖥️ Cattura Schermo (seleziona l'area con il mouse)..."
    screencapture -i "$TEMP_IMG"
    SHIFT_ARG=1
fi

# Invia a Gemini CLI
# Nota: Adattato per la sintassi standard di gemini-cli
gemini-cli ask "${@:$SHIFT_ARG}" --image "$TEMP_IMG"

# Pulizia opzionale
# rm "$TEMP_IMG"
