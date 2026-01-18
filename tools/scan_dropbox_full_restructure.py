#!/usr/bin/env python3
"""
Dropbox Full Scan & CRM Restructure Plan Generator

Scansiona completamente il Dropbox e genera un piano di migrazione
per riorganizzare tutto in base ai clienti CRM (Opzione B).

Output:
1. Inventario completo Dropbox (JSON)
2. Piano di mapping Dropbox → CRM (CSV)
3. Struttura target Google Drive (YAML)
"""

import sys
import json
import csv
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from difflib import SequenceMatcher

# Path Dropbox
DROPBOX_PATH = Path("/sessions/upbeat-laughing-volta/mnt/antonellosiano/Dropbox")

# Output directory
OUTPUT_DIR = Path(__file__).parent / "dropbox_scan_results"
OUTPUT_DIR.mkdir(exist_ok=True)


def similarity(a: str, b: str) -> float:
    """Calculate string similarity"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def scan_directory(path: Path, max_depth=3, current_depth=0):
    """Recursively scan directory structure"""
    result = {
        "name": path.name,
        "path": str(path.relative_to(DROPBOX_PATH)),
        "type": "directory",
        "children": [],
        "file_count": 0,
        "total_size": 0,
        "depth": current_depth,
    }

    try:
        items = list(path.iterdir())

        for item in items:
            # Skip hidden and system files
            if item.name.startswith("."):
                continue

            if item.is_file():
                size = item.stat().st_size if item.exists() else 0
                result["file_count"] += 1
                result["total_size"] += size

                result["children"].append(
                    {
                        "name": item.name,
                        "type": "file",
                        "size": size,
                        "extension": item.suffix.lower(),
                    }
                )

            elif item.is_dir() and current_depth < max_depth:
                subdir = scan_directory(item, max_depth, current_depth + 1)
                result["children"].append(subdir)
                result["file_count"] += subdir["file_count"]
                result["total_size"] += subdir["total_size"]

    except PermissionError:
        result["error"] = "Permission denied"
    except Exception as e:
        result["error"] = str(e)

    return result


def extract_client_folders(scan_result):
    """Extract all potential client folders from scan"""
    clients = []

    def traverse(node, parent_path=""):
        current_path = f"{parent_path}/{node['name']}" if parent_path else node["name"]

        # Skip utility folders
        utility_keywords = [
            "draft",
            "random",
            "foto",
            "bali zero",
            "laporan",
            "titip krisna",
            "perubahan",
        ]
        if any(kw in node["name"].lower() for kw in utility_keywords):
            return

        # Check if this looks like a client folder
        is_client = False

        # Pattern 1: Folders in PEMEGANG KITAS (all clients)
        if "PEMEGANG KITAS" in current_path:
            if node.get("depth", 0) == 1:  # Direct children
                is_client = True

        # Pattern 2: Personal name folders (2+ words, capitalized)
        elif node.get("depth", 0) <= 2:
            name_parts = node["name"].split()
            if len(name_parts) >= 2:
                # Check if looks like a name (not all caps, not codes)
                if not node["name"].isupper() or " " in node["name"]:
                    is_client = True

        # Pattern 3: Known patterns like "MAS ADIT", "OM YOYOK"
        if node["name"].startswith(("MAS ", "OM ", "PAK ", "IBU ")):
            is_client = True

        # Pattern 4: "Titip Punya X" indicates X is a client
        if "titip punya" in node["name"].lower():
            client_name = (
                node["name"]
                .replace("Titip Punya", "")
                .replace("titip punya", "")
                .strip()
            )
            if client_name:
                clients.append(
                    {
                        "name": client_name,
                        "source_path": current_path,
                        "repository": parent_path.split("/")[0]
                        if "/" in parent_path
                        else "root",
                        "file_count": node.get("file_count", 0),
                        "total_size": node.get("total_size", 0),
                        "type": "deposited",
                    }
                )

        if is_client and not node["name"].startswith("###"):
            clients.append(
                {
                    "name": node["name"],
                    "source_path": current_path,
                    "repository": parent_path.split("/")[0]
                    if "/" in parent_path
                    else "root",
                    "file_count": node.get("file_count", 0),
                    "total_size": node.get("total_size", 0),
                    "type": "direct",
                }
            )

        # Recurse into children
        for child in node.get("children", []):
            if child.get("type") == "directory":
                traverse(child, current_path)

    traverse(scan_result)
    return clients


def match_with_crm(client_folders, crm_clients):
    """Match Dropbox folders with CRM clients"""
    matches = []

    for folder in client_folders:
        best_match = None
        best_score = 0.0

        for crm_client in crm_clients:
            score = similarity(folder["name"], crm_client["name"])

            if score > best_score:
                best_score = score
                best_match = crm_client

        if best_score >= 0.8:
            confidence = "high"
        elif best_score >= 0.6:
            confidence = "medium"
        else:
            confidence = "low"
            best_match = None

        matches.append(
            {
                "dropbox_name": folder["name"],
                "dropbox_path": folder["source_path"],
                "repository": folder["repository"],
                "file_count": folder["file_count"],
                "size_mb": round(folder["total_size"] / 1024 / 1024, 2),
                "crm_id": best_match["id"] if best_match else None,
                "crm_name": best_match["name"] if best_match else None,
                "similarity": round(best_score, 3),
                "confidence": confidence,
                "needs_review": confidence != "high",
            }
        )

    return matches


def generate_migration_plan(matches):
    """Generate migration plan with Google Drive target structure"""
    plan = {
        "timestamp": datetime.now().isoformat(),
        "strategy": "Restructure by CRM Client (Option B)",
        "target_structure": "Google Drive/Bali Zero Clients/{CRM_CLIENT}/",
        "clients": [],
    }

    # Group by CRM client
    by_crm = defaultdict(list)
    unmatched = []

    for match in matches:
        if match["crm_id"]:
            by_crm[match["crm_id"]].append(match)
        else:
            unmatched.append(match)

    # Generate plan for each CRM client
    for crm_id, sources in by_crm.items():
        crm_name = sources[0]["crm_name"]

        client_plan = {
            "crm_id": crm_id,
            "crm_name": crm_name,
            "target_folder": f"Bali Zero Clients/{crm_name}/",
            "source_folders": [s["dropbox_path"] for s in sources],
            "total_files": sum(s["file_count"] for s in sources),
            "total_size_mb": sum(s["size_mb"] for s in sources),
            "migration_steps": [
                {
                    "step": 1,
                    "action": "create_folder",
                    "path": f"Bali Zero Clients/{crm_name}/",
                },
                {
                    "step": 2,
                    "action": "create_subfolders",
                    "folders": [
                        "01_Immigration",
                        "02_Company",
                        "03_Tax",
                        "04_Family",
                        "05_Contracts",
                        "99_Uncategorized",
                    ],
                },
                {"step": 3, "action": "migrate_and_categorize", "sources": sources},
                {"step": 4, "action": "update_crm", "crm_id": crm_id},
            ],
        }

        plan["clients"].append(client_plan)

    # Add unmatched section
    plan["unmatched"] = {
        "count": len(unmatched),
        "folders": unmatched,
        "action": "manual_review_required",
    }

    return plan


def main():
    print("\n" + "=" * 80)
    print("🔍 DROPBOX FULL SCAN & CRM RESTRUCTURE PLAN")
    print("=" * 80 + "\n")

    # Check if Dropbox exists
    if not DROPBOX_PATH.exists():
        print(f"❌ Dropbox not found at: {DROPBOX_PATH}")
        print("   Make sure Dropbox.app is installed and syncing.")
        return 1

    print(f"📂 Scanning: {DROPBOX_PATH}")
    print("   This may take 5-10 minutes for 450GB...")
    print()

    # Step 1: Full scan
    print("[1/5] Scanning Dropbox structure...")
    scan_result = scan_directory(DROPBOX_PATH, max_depth=3)

    # Save full scan
    scan_file = (
        OUTPUT_DIR
        / f"dropbox_full_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(scan_file, "w") as f:
        json.dump(scan_result, f, indent=2)
    print(f"      ✅ Scan saved: {scan_file.name}")

    # Step 2: Extract client folders
    print("\n[2/5] Extracting client folders...")
    client_folders = extract_client_folders(scan_result)
    print(f"      ✅ Found {len(client_folders)} potential client folders")

    # Step 3: Load CRM clients (mock for now)
    print("\n[3/5] Loading CRM clients...")
    # TODO: Replace with real CRM query
    crm_clients = [
        {"id": 1, "name": "Adele Marthe"},
        {"id": 2, "name": "Aditya"},
        {"id": 3, "name": "Angel"},
        # Add more from CSV
    ]
    print(f"      ✅ Loaded {len(crm_clients)} CRM clients")

    # Step 4: Match
    print("\n[4/5] Matching Dropbox → CRM...")
    matches = match_with_crm(client_folders, crm_clients)

    high_conf = len([m for m in matches if m["confidence"] == "high"])
    med_conf = len([m for m in matches if m["confidence"] == "medium"])
    low_conf = len([m for m in matches if m["confidence"] == "low"])

    print(f"      ✅ High confidence: {high_conf}")
    print(f"      ⚠️  Medium confidence: {med_conf}")
    print(f"      ❌ Low/No match: {low_conf}")

    # Save matches CSV
    matches_file = (
        OUTPUT_DIR
        / f"dropbox_crm_matches_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )
    with open(matches_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=matches[0].keys())
        writer.writeheader()
        writer.writerows(matches)
    print(f"      💾 Matches saved: {matches_file.name}")

    # Step 5: Generate migration plan
    print("\n[5/5] Generating migration plan...")
    plan = generate_migration_plan(matches)

    plan_file = (
        OUTPUT_DIR / f"migration_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(plan_file, "w") as f:
        json.dump(plan, f, indent=2)
    print(f"      ✅ Plan saved: {plan_file.name}")

    # Summary
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    print(f"\n📁 Total folders scanned: {len(client_folders)}")
    print(f"✅ Clients to migrate: {len(plan['clients'])}")
    print(f"⚠️  Unmatched folders: {plan['unmatched']['count']}")
    print(f"📊 Total files: {scan_result['file_count']:,}")
    print(f"💾 Total size: {scan_result['total_size'] / 1024**3:.1f} GB")

    print("\n" + "=" * 80)
    print("✅ SCAN COMPLETE!")
    print("=" * 80)
    print(f"\nResults saved in: {OUTPUT_DIR}/")
    print("\nNext steps:")
    print("1. Review matches CSV")
    print("2. Verify migration plan JSON")
    print("3. Run pilot migration with 3-5 clients")
    print("4. Execute full migration")
    print()

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
