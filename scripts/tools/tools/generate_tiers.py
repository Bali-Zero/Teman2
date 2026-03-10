#!/usr/bin/env python3
"""
Generate Tier Lists - Stratify 17,400 clients

Input:
  - crm_active_clients.csv (from CRM export)
  - file_age_analysis.json (from analyze_dropbox_dates.py)

Output:
  - tier1_active_crm.json (~500 clients)
  - tier2_recent_2024_2025.json (~2,500 clients)
  - tier3_historical_2022_2023.json (~5,000 clients)
  - tier4_archive_pre2022.json (~9,000 clients)
"""

import json
import csv
from pathlib import Path
from difflib import SequenceMatcher

OUTPUT_DIR = Path(__file__).parent
CRM_FILE = OUTPUT_DIR / "crm_active_clients.csv"
AGE_ANALYSIS_FILE = OUTPUT_DIR / "file_age_analysis.json"


def similarity(a: str, b: str) -> float:
    """Calculate string similarity (0-1)"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def load_crm_clients():
    """Load CRM client list"""
    if not CRM_FILE.exists():
        print(f"⚠️  CRM file not found: {CRM_FILE}")
        print("   Using empty CRM list (Tier 1 will be empty)")
        return []

    crm_clients = []
    with open(CRM_FILE, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            crm_clients.append(
                {
                    "id": row.get("id"),
                    "name": row.get("full_name", ""),
                    "email": row.get("email", ""),
                    "status": row.get("status", "active"),
                }
            )

    return crm_clients


def load_age_analysis():
    """Load file age analysis"""
    if not AGE_ANALYSIS_FILE.exists():
        print(f"❌ Error: {AGE_ANALYSIS_FILE} not found!")
        print("   Run analyze_dropbox_dates.py first")
        return None

    with open(AGE_ANALYSIS_FILE, "r") as f:
        return json.load(f)


def match_crm_to_dropbox(crm_clients, dropbox_clients):
    """Match CRM clients to Dropbox clients (fuzzy)"""
    matches = []

    for crm in crm_clients:
        best_match = None
        best_score = 0

        for db_client in dropbox_clients:
            score = similarity(crm["name"], db_client["name"])

            if score > best_score:
                best_score = score
                best_match = db_client

        if best_match and best_score > 0.6:  # 60% similarity threshold
            matches.append(
                {
                    **best_match,
                    "crm_id": crm["id"],
                    "crm_name": crm["name"],
                    "crm_email": crm["email"],
                    "match_score": best_score,
                }
            )

    return matches


def generate_tiers(crm_clients, age_analysis):
    """Generate stratified tier lists"""

    all_clients = age_analysis["clients"]

    # Tier 1: Active CRM clients
    tier1 = match_crm_to_dropbox(crm_clients, all_clients)

    # Remove Tier 1 from pool
    tier1_names = {c["name"] for c in tier1}
    remaining = [c for c in all_clients if c["name"] not in tier1_names]

    # Tier 2: Recent (last 12 months)
    tier2 = [c for c in remaining if c["tier"] == "tier2_recent"]

    # Tier 3: Historical (1-3 years)
    tier3 = [c for c in remaining if c["tier"] == "tier3_historical"]

    # Tier 4: Archive (3+ years)
    tier4 = [c for c in remaining if c["tier"] == "tier4_archive"]

    return {
        "tier1": tier1,
        "tier2": tier2,
        "tier3": tier3,
        "tier4": tier4,
    }


def save_tier(tier_name, clients, description):
    """Save tier to JSON file"""
    filename = OUTPUT_DIR / f"{tier_name}.json"

    output = {
        "tier": tier_name,
        "description": description,
        "count": len(clients),
        "clients": clients,
    }

    with open(filename, "w") as f:
        json.dump(output, f, indent=2)

    print(f"✅ {tier_name:30} {len(clients):6,} clients → {filename.name}")


def main():
    print("\n" + "=" * 80)
    print("🎯 GENERATING TIER LISTS")
    print("=" * 80 + "\n")

    # Load data
    print("Loading data...")
    crm_clients = load_crm_clients()
    age_analysis = load_age_analysis()

    if age_analysis is None:
        return

    print(f"  CRM clients: {len(crm_clients):,}")
    print(f"  Dropbox clients: {age_analysis['total_analyzed']:,}\n")

    # Generate tiers
    print("Generating tiers...\n")
    tiers = generate_tiers(crm_clients, age_analysis)

    # Save each tier
    save_tier(
        "tier1_active_crm", tiers["tier1"], "Active CRM clients - HIGHEST PRIORITY"
    )

    save_tier(
        "tier2_recent_2024_2025",
        tiers["tier2"],
        "Recent clients (last 12 months) - HIGH PRIORITY",
    )

    save_tier(
        "tier3_historical_2022_2023",
        tiers["tier3"],
        "Historical clients (1-3 years) - MEDIUM PRIORITY",
    )

    save_tier(
        "tier4_archive_pre2022",
        tiers["tier4"],
        "Archive clients (3+ years) - LOW PRIORITY (consider skipping)",
    )

    # Summary
    print(f"\n{'=' * 80}")
    print("📊 TIER SUMMARY")
    print(f"{'=' * 80}\n")

    total = sum(len(t) for t in tiers.values())

    for tier_name, clients in tiers.items():
        count = len(clients)
        pct = (count / total * 100) if total > 0 else 0
        print(f"{tier_name:30} {count:6,} clients ({pct:5.1f}%)")

    print(f"\n{'Total:':30} {total:6,} clients\n")

    # Recommendations
    print(f"{'=' * 80}")
    print("💡 MIGRATION RECOMMENDATIONS")
    print(f"{'=' * 80}\n")

    tier1_count = len(tiers["tier1"])
    tier2_count = len(tiers["tier2"])
    tier3_count = len(tiers["tier3"])
    tier4_count = len(tiers["tier4"])

    print("SCENARIO A - Full Migration (NOT RECOMMENDED)")
    print(f"  Migrate: All {total:,} clients")
    print("  Time: 3-4 months")
    print("  Cost: €40,000-50,000")
    print()

    print("SCENARIO B - Smart Migration (RECOMMENDED) ✅")
    print(f"  Migrate: Tier 1 + Tier 2 = {tier1_count + tier2_count:,} clients")
    print(f"  Skip: Tier 4 = {tier4_count:,} clients")
    print(f"  Optional: Tier 3 = {tier3_count:,} clients (decide later)")
    print("  Time: 4-6 weeks")
    print("  Cost: €10,000-15,000")
    print()

    print("SCENARIO C - Minimum Viable (FASTEST)")
    print(f"  Migrate: Tier 1 only = {tier1_count:,} clients")
    print("  Time: 2-3 weeks")
    print("  Cost: €5,000-7,500")
    print()

    # Next steps
    print(f"{'=' * 80}")
    print("🚀 NEXT STEPS")
    print(f"{'=' * 80}\n")

    print("1. Review tier lists (JSON files generated)")
    print("2. Decide migration scope (Scenario A/B/C)")
    print("3. Run pilot test with 5 clients from Tier 1")
    print("4. Execute migration for approved tiers")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Generation cancelled")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
