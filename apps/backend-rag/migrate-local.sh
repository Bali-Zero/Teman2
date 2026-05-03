#!/bin/bash
# Apply migrations to local DB

cd "$(dirname "$0")"

# Load local env
export $(grep -v '^#' .env.local | xargs)

# Activate venv
source .venv/bin/activate

# Run migrations
python3 -m backend.db.migrate apply-all
