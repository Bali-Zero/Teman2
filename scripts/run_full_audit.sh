#!/bin/bash
# Full System Audit Script for Nuzantara
# Run this to perform a comprehensive data quality audit

echo "=============================================="
echo "NUZANTARA FULL SYSTEM AUDIT"
echo "=============================================="
echo "Started: $(date)"
echo ""

# Step 1: Qdrant Visa Code Check
echo "Step 1: Checking Qdrant for fake/obsolete visa codes..."
python scripts/purge_outdated_visa_codes.py --scan

# Step 2: Deep Audit (if script exists)
if [ -f "scripts/deep_audit_all_collections.py" ]; then
    echo ""
    echo "Step 2: Running deep audit of all collections..."
    python scripts/deep_audit_all_collections.py
fi

# Step 3: PostgreSQL Check (requires fly proxy)
echo ""
echo "Step 3: Checking PostgreSQL for old codes..."
echo "NOTE: This requires fly proxy to be running:"
echo "  fly proxy 15432:5432 -a nuzantara-db"
echo ""

# Check if port 15432 is accessible
if nc -z localhost 15432 2>/dev/null; then
    echo "Fly proxy detected, running PostgreSQL check..."
    python scripts/check_pg_old_codes.py --check
else
    echo "Fly proxy not running. Skipping PostgreSQL check."
    echo "To run manually: python scripts/check_pg_old_codes.py --check"
fi

echo ""
echo "=============================================="
echo "AUDIT COMPLETE"
echo "=============================================="
echo "Reports saved to: scripts/audit_reports/"
echo "Finished: $(date)"
