#!/usr/bin/env python3
"""
Quick environment variable checker for Fly.io debugging
"""
import os
import sys

print("=" * 60)
print("ENVIRONMENT VARIABLE CHECK")
print("=" * 60)

required_vars = ["R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT_URL", "QDRANT_URL"]

all_ok = True
for var in required_vars:
    value = os.getenv(var)
    if value:
        # Show first/last 4 chars only for security
        if len(value) > 8:
            masked = f"{value[:4]}...{value[-4:]}"
        else:
            masked = "***"
        print(f"✅ {var}: {masked}")
    else:
        print(f"❌ {var}: NOT FOUND")
        all_ok = False

print("=" * 60)

if all_ok:
    print("✅ All environment variables present!")
    sys.exit(0)
else:
    print("❌ Some environment variables missing!")
    sys.exit(1)
