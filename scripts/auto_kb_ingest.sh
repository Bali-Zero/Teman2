#!/bin/bash

# Configuration
PROJECT_DIR="/Users/antonellosiano/Desktop/nuzantara"
PYTHON_EXEC="/Users/antonellosiano/.pyenv/shims/python3"
KB_DIR="$PROJECT_DIR/apps/kb"
LOG_FILE="$PROJECT_DIR/logs/kb_ingest.log"
DATE=$(date "+%Y-%m-%d %H:%M:%S")

# Ensure logs directory exists
mkdir -p "$PROJECT_DIR/logs"

# Execution
echo "[$DATE] Starting Knowledge Base Ingestion..." >> "$LOG_FILE"
cd "$PROJECT_DIR" # Run from root for imports

# 1. Intelligent Visa Agent (Vision + Map + Notifications)
echo "[$DATE] Running Intelligent Visa Agent..." >> "$LOG_FILE"
export PYTHONPATH="$PROJECT_DIR/apps/backend-rag/backend:$PYTHONPATH"
"$PYTHON_EXEC" apps/kb/intelligent_visa_agent.py >> "$LOG_FILE" 2>&1

# 2. Peraturan Spider (Laws) - Standard Update
echo "[$DATE] Running Peraturan Spider..." >> "$LOG_FILE"
"$PYTHON_EXEC" apps/kb/peraturan_spider.py --limit 10 >> "$LOG_FILE" 2>&1

# 3. Putusan Spider (Court) - Standard Update
echo "[$DATE] Running Putusan Spider..." >> "$LOG_FILE"
"$PYTHON_EXEC" apps/kb/putusan_spider.py >> "$LOG_FILE" 2>&1

echo "[$DATE] ✅ KB Ingestion Cycle Complete." >> "$LOG_FILE"
echo "----------------------------------------" >> "$LOG_FILE"
