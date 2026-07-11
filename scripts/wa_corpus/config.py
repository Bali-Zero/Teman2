"""Central config. Values verified empirically during the 2026-06-04 gate."""
from __future__ import annotations

SA_KEY_PATH = "/Users/nuzantara/.config/nuzantara/service-accounts/nuzantara-google-drive-sa-20260530.json"
DELEGATED_USER = "zero@balizero.com"            # SA impersonates this (DWD configured)
NLM_ACCOUNT_EMAIL = "antonellosiano@gmail.com"  # F1: nlm profile 'zero' is THIS account
NLM_PROFILE = "zero"
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
DB_DSN = "postgresql://localhost:5432/nuzantara_dev"

# F3: exclusion-first. These contact_types are NEVER a 1-a-1 client profile.
EXCLUDED_CONTACT_TYPES = frozenset({"team", "partner", "group"})

# Heuristics for separating a 1-a-1 client from a multi-client operational channel.
MULTI_CLIENT_MIN_MSGS = 120          # high volume threshold
MULTI_CLIENT_MIN_DISTINCT_NAMES = 8  # many distinct client-like names mentioned
