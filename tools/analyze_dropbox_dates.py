#!/usr/bin/env python3
"""
Analyze File Dates in Dropbox - Per Tier Stratification

Scansiona tutti i 17,400 clienti e trova:
- File più recente per ogni cliente
- Età del cliente (days since last file)
- Distribuzione per tier (active, recent, historical, archive)
"""

import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

DROPBOX_PATH = Path("/sessions/upbeat-laughing-volta/mnt/antonellosiano/Dropbox")
OUTPUT_DIR = Path(__file__).parent
OUTPUT_FILE = OUTPUT_DIR / "file_age_analysis.json"

# Thresholds (in days)
TIER_THRESHOLDS = {
    "tier2_recent": 365,  # Last 12 months
    "tier3_historical": 1095,  # 1-3 years ago
    "tier4_archive": 99999,  # 3+ years ago
}


def get_latest_file_date(client_path: Path) -> datetime:
    """Find the most recent file in client folder"""
    latest = None

    try:
        for file_path in client_path.rglob("*"):
            if file_path.is_file() and not file_path.name.startswith("."):
                try:
                    mtime = file_path.stat().st_mtime
                    file_date = datetime.fromtimestamp(mtime)

                    if latest is None or file_date > latest:
                        latest = file_date
                except (OSError, PermissionError):
                    continue
    except (OSError, PermissionError):
        pass

    return latest


def analyze_client_age(client_name: str, client_path: Path, repository: str):
    """Analyze one client's file age"""
    latest_date = get_latest_file_date(client_path)

    if latest_date is None:
        return None  # No files or inaccessible

    today = datetime.now()
    age_days = (today - latest_date).days

    # Determine tier
    if age_days <= TIER_THRESHOLDS["tier2_recent"]:
        tier = "tier2_recent"
    elif age_days <= TIER_THRESHOLDS["tier3_historical"]:
        tier = "tier3_historical"
    else:
        tier = "tier4_archive"

    return {
        "name": client_name,
        "repository": repository,
        "latest_file_date": latest_date.isoformat(),
        "age_days": age_days,
        "tier": tier,
        "path": str(client_path.relative_to(DROPBOX_PATH)),
    }


def main():
    print("\n" + "=" * 80)
    print("📅 ANALYZING FILE DATES - 17,400 Clients")
    print("=" * 80 + "\n")

    # Load previously extracted clients
    clients_file = OUTPUT_DIR / "real_clients_extracted.json"

    if not clients_file.exists():
        print("❌ Error: real_clients_extracted.json not found!")
        print("   Run extract_real_clients_fast.py first")
        return

    with open(clients_file, "r") as f:
        data = json.load(f)
        all_clients = data.get("clients", [])

    print(f"Loaded {len(all_clients)} clients from extraction\n")

    # Analyze each client
    results = []
    tier_counts = defaultdict(int)
    processed = 0

    for client in all_clients:
        client_path = DROPBOX_PATH / client["full_path"]

        analysis = analyze_client_age(client["name"], client_path, client["repository"])

        if analysis:
            results.append(analysis)
            tier_counts[analysis["tier"]] += 1

        processed += 1
        if processed % 100 == 0:
            print(f"Processed {processed}/{len(all_clients)} clients...")

    # Summary
    print(f"\n{'=' * 80}")
    print("📊 TIER DISTRIBUTION")
    print(f"{'=' * 80}\n")

    for tier, count in sorted(tier_counts.items()):
        pct = (count / len(results)) * 100
        print(f"{tier:20} {count:6,} clients ({pct:5.1f}%)")

    print(f"\n{'Total analyzed:':20} {len(results):6,} clients")

    # Age distribution
    age_ranges = {
        "0-6 months": 0,
        "6-12 months": 0,
        "1-2 years": 0,
        "2-3 years": 0,
        "3+ years": 0,
    }

    for result in results:
        days = result["age_days"]
        if days <= 180:
            age_ranges["0-6 months"] += 1
        elif days <= 365:
            age_ranges["6-12 months"] += 1
        elif days <= 730:
            age_ranges["1-2 years"] += 1
        elif days <= 1095:
            age_ranges["2-3 years"] += 1
        else:
            age_ranges["3+ years"] += 1

    print(f"\n{'=' * 80}")
    print("📅 AGE DISTRIBUTION")
    print(f"{'=' * 80}\n")

    for age_range, count in age_ranges.items():
        pct = (count / len(results)) * 100
        print(f"{age_range:20} {count:6,} clients ({pct:5.1f}%)")

    # Save results
    output = {
        "timestamp": datetime.now().isoformat(),
        "total_analyzed": len(results),
        "tier_counts": dict(tier_counts),
        "age_distribution": age_ranges,
        "clients": results,
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n💾 Results saved to: {OUTPUT_FILE.name}\n")

    # Recommendations
    print(f"{'=' * 80}")
    print("💡 RECOMMENDATIONS")
    print(f"{'=' * 80}\n")

    recent_count = tier_counts.get("tier2_recent", 0)
    historical_count = tier_counts.get("tier3_historical", 0)
    archive_count = tier_counts.get("tier4_archive", 0)

    print(f"Tier 2 (Recent):     {recent_count:6,} - MIGRATE (high priority)")
    print(f"Tier 3 (Historical): {historical_count:6,} - CONSIDER (medium priority)")
    print(f"Tier 4 (Archive):    {archive_count:6,} - SKIP (low priority)")

    savings = archive_count
    print(
        f"\nSkipping Tier 4 saves: {savings:,} clients (~{savings / len(results) * 100:.0f}% reduction)"
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Analysis cancelled")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
