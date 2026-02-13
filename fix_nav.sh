#!/bin/bash
# Fix Navigator: remove duplicate Browse Sectors section

FILE="/Users/nuzantara/Desktop/nuzantara/apps/mouth/public/kbli-navigator/index.html"
BACKUP="${FILE}.backup"

echo "Creating backup..."
cp "$FILE" "$BACKUP"

echo "Removing duplicate Browse Sectors (lines 2930-3023)..."
sed -i '' '2930,3023d' "$FILE"

echo "Done! Backup saved to: $BACKUP"
echo "Verify with: diff $BACKUP $FILE | head -20"
