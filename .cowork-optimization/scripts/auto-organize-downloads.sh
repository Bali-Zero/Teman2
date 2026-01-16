#!/bin/bash
# Auto-organize Downloads - Cowork Automation
# Eseguito ogni ora per organizzare file in Downloads

DOWNLOADS_DIR="$HOME/Downloads"
ORGANIZED_DIR="$HOME/Documents/Downloads-Organized"
LOG_FILE="$HOME/Desktop/nuzantara/.cowork-optimization/logs/downloads-organize.log"

# Crea directory se non esistono
mkdir -p "$ORGANIZED_DIR"/{Documents,Images,Videos,Archives,Code,Other}
mkdir -p "$(dirname "$LOG_FILE")"

echo "[$(date)] Starting Downloads organization..." >> "$LOG_FILE"

# Organizza per tipo
find "$DOWNLOADS_DIR" -maxdepth 1 -type f -mtime -7 | while read file; do
    filename=$(basename "$file")
    extension="${filename##*.}"

    case "$extension" in
        pdf|doc|docx|txt|rtf|odt)
            dest="$ORGANIZED_DIR/Documents"
            ;;
        jpg|jpeg|png|gif|bmp|svg|webp)
            dest="$ORGANIZED_DIR/Images"
            ;;
        mp4|mov|avi|mkv|webm)
            dest="$ORGANIZED_DIR/Videos"
            ;;
        zip|tar|gz|rar|7z)
            dest="$ORGANIZED_DIR/Archives"
            ;;
        py|js|ts|jsx|tsx|json|yaml|yml|sh|md)
            dest="$ORGANIZED_DIR/Code"
            ;;
        *)
            dest="$ORGANIZED_DIR/Other"
            ;;
    esac

    # Sposta file se non esiste già
    if [ ! -f "$dest/$filename" ]; then
        mv "$file" "$dest/" && echo "[$(date)] Moved: $filename -> $(basename $dest)" >> "$LOG_FILE"
    fi
done

echo "[$(date)] Downloads organization completed" >> "$LOG_FILE"
