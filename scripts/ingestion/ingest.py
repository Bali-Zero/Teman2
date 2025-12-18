#!/usr/bin/env python3
"""
NUZANTARA PRIME - Unified Ingestion CLI Wrapper

Replaces fragmented ingestion scripts:
- scripts/ingest_team_data.py
- scripts/ingest_conversations.py
- scripts/ingest_synthetic_data.py
- apps/backend-rag/scripts/ingest_*.py

Usage:
    python apps/backend-rag/scripts/ingest.py list
    python apps/backend-rag/scripts/ingest.py team-members
    python apps/backend-rag/scripts/ingest.py conversations --source /path/to/data
    python apps/backend-rag/scripts/ingest.py laws --file /path/to/law.pdf
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

# Import and run CLI
from cli.ingestion_cli import main

if __name__ == "__main__":
    # Map old script names to new CLI commands
    if len(sys.argv) > 1:
        # Handle legacy script names
        if sys.argv[1] == "ingest_team_data.py" or sys.argv[1] == "team-members":
            sys.argv = ["ingest.py", "ingest", "team-members"] + sys.argv[2:]
        elif sys.argv[1] == "ingest_conversations.py" or sys.argv[1] == "conversations":
            sys.argv = ["ingest.py", "ingest", "conversations"] + sys.argv[2:]
        elif sys.argv[1] == "ingest_laws.py" or sys.argv[1] == "laws":
            sys.argv = ["ingest.py", "ingest", "laws"] + sys.argv[2:]

    sys.exit(main())
