#!/usr/bin/env python3
"""
Pilot Migration Test - Dropbox → Google Drive

Migra 5 clienti selezionati per testare il processo completo:
1. Crea struttura cartelle Google Drive
2. Categorizza file automaticamente
3. Copia file da Dropbox
4. Genera report risultati

NOTA: Questo è un DRY-RUN - crea solo la struttura locale,
non fa upload reale a Google Drive.
"""

import os
import shutil
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Paths
DROPBOX_PATH = Path("/sessions/upbeat-laughing-volta/mnt/antonellosiano/Dropbox")
OUTPUT_DIR = Path(__file__).parent / "pilot_migration_results"
OUTPUT_DIR.mkdir(exist_ok=True)

# Simulate Google Drive structure locally
GDRIVE_SIMULATION = OUTPUT_DIR / "gdrive_structure"
GDRIVE_SIMULATION.mkdir(exist_ok=True)

# Category rules for automatic file classification
CATEGORY_RULES = {
    "01_Immigration": [
        "passport",
        "kitas",
        "kitap",
        "visa",
        "imta",
        "permit",
        "sponsor",
        "extension",
        "stay permit",
        "immigration",
        "merp",
        "limited stay",
        "c1",
        "c18",
        "d1",
        "d12",
        "e31",
        "e33",
    ],
    "02_Company": [
        "pt",
        "pma",
        "cv",
        "nib",
        "npwp",
        "deed",
        "akta",
        "company",
        "business",
        "license",
        "perusahaan",
        "izin",
        "usaha",
        "modal",
    ],
    "03_Tax": [
        "tax",
        "spt",
        "pajak",
        "pph",
        "ppn",
        "pbb",
        "tax report",
        "annual return",
        "fiscal",
        "laporan pajak",
    ],
    "04_Family": [
        "spouse",
        "wife",
        "husband",
        "child",
        "family",
        "dependent",
        "marriage",
        "birth certificate",
        "suami",
        "istri",
        "anak",
        "keluarga",
    ],
    "05_Contracts": [
        "contract",
        "agreement",
        "invoice",
        "quotation",
        "service agreement",
        "mou",
        "kontrak",
        "perjanjian",
    ],
    "99_Uncategorized": [],  # Default
}


def categorize_file(filename: str) -> str:
    """Automatically categorize file based on filename"""
    filename_lower = filename.lower()

    for category, keywords in CATEGORY_RULES.items():
        if category == "99_Uncategorized":
            continue

        for keyword in keywords:
            if keyword in filename_lower:
                return category

    return "99_Uncategorized"


def standardize_filename(filename: str, client_name: str) -> str:
    """Standardize filename with conventions"""
    # Keep original for now, add client name if not present
    name, ext = os.path.splitext(filename)

    # Remove special characters
    name_clean = name.replace("_", " ").replace("-", " ")

    # Capitalize words
    name_clean = " ".join(word.capitalize() for word in name_clean.split())

    return f"{name_clean}{ext}"


def create_client_structure(client_name: str):
    """Create folder structure for one client"""
    client_dir = GDRIVE_SIMULATION / "Bali Zero Clients" / client_name

    # Create main folder
    client_dir.mkdir(parents=True, exist_ok=True)

    # Create category subfolders
    categories = [
        "01_Immigration",
        "02_Company",
        "03_Tax",
        "04_Family",
        "05_Contracts",
        "99_Uncategorized",
    ]

    for category in categories:
        (client_dir / category).mkdir(exist_ok=True)

    return client_dir


def migrate_client(client_name: str, source_path: Path, dry_run=True):
    """Migrate one client with full categorization"""
    print(f"\n{'=' * 70}")
    print(f"📁 Migrating: {client_name}")
    print(f"   Source: {source_path.relative_to(DROPBOX_PATH)}")
    print(f"{'=' * 70}\n")

    # Create structure
    client_dir = create_client_structure(client_name)
    print(f"✅ Created structure: {client_dir.name}/")

    # Collect files
    files_found = []

    if source_path.exists() and source_path.is_dir():
        for file_path in source_path.rglob("*"):
            if file_path.is_file() and not file_path.name.startswith("."):
                files_found.append(file_path)

    print(f"📊 Found {len(files_found)} files\n")

    # Categorize and organize
    results = {
        "client_name": client_name,
        "source_path": str(source_path),
        "total_files": len(files_found),
        "categorized": defaultdict(int),
        "files_by_category": defaultdict(list),
        "errors": [],
    }

    for file_path in files_found:
        try:
            # Categorize
            category = categorize_file(file_path.name)
            results["categorized"][category] += 1

            # Standardize filename
            new_filename = standardize_filename(file_path.name, client_name)

            # Target path
            target_path = client_dir / category / new_filename

            # Record
            results["files_by_category"][category].append(
                {
                    "original": file_path.name,
                    "standardized": new_filename,
                    "category": category,
                    "size": file_path.stat().st_size if file_path.exists() else 0,
                }
            )

            # Copy file (in dry-run, just create placeholder)
            if dry_run:
                # Create empty placeholder
                target_path.touch()
            else:
                # Real copy
                shutil.copy2(file_path, target_path)

        except Exception as e:
            results["errors"].append({"file": file_path.name, "error": str(e)})

    # Print summary
    print("📊 Categorization Results:")
    for category in sorted(results["categorized"].keys()):
        count = results["categorized"][category]
        print(f"   {category}: {count} files")

    if results["errors"]:
        print(f"\n⚠️  Errors: {len(results['errors'])}")

    print()

    return results


def run_pilot_migration():
    """Run pilot migration with 5 selected clients"""
    print("\n" + "=" * 80)
    print("🚀 PILOT MIGRATION TEST - Dropbox → Google Drive")
    print("=" * 80)
    print("\nMode: DRY-RUN (structure only, no real upload)")
    print(f"Target: {GDRIVE_SIMULATION}\n")

    # Select pilot clients
    pilot_clients = [
        {
            "name": "Adele Marthe",
            "source": DROPBOX_PATH / "ADITYA" / "Adele Marthe",
            "reason": "Small client (3 files) - Good for quick test",
        },
        {
            "name": "MAS ADIT",
            "source": DROPBOX_PATH / "ADITYA" / "MAS ADIT",
            "reason": "Medium client (~20 files) - Test categorization",
        },
        {
            "name": "OM YOYOK",
            "source": DROPBOX_PATH / "ADITYA" / "OM YOYOK",
            "reason": "Small client - Verify naming patterns",
        },
        {
            "name": "GALACI (Om Oman)",
            "source": DROPBOX_PATH / "ADITYA" / "GALACI ( Om Oman )",
            "reason": "Test special characters in name",
        },
        {
            "name": "File PT Total Woman Bali",
            "source": DROPBOX_PATH
            / "ANGEL"
            / "File PT Total Woman Bali (Babette Esmay Monsma)",
            "reason": "Company client - Test company categorization",
        },
    ]

    print("📋 Pilot Clients Selected:\n")
    for i, client in enumerate(pilot_clients, 1):
        print(f"{i}. {client['name']}")
        print(f"   → {client['reason']}")
        print(
            f"   📂 {client['source'].relative_to(DROPBOX_PATH) if client['source'].exists() else 'NOT FOUND'}"
        )
        print()

    # Confirm
    print("=" * 80)
    input("Press ENTER to start migration (or Ctrl+C to cancel)...")
    print()

    # Migrate each client
    results_all = []

    for client in pilot_clients:
        try:
            result = migrate_client(
                client_name=client["name"], source_path=client["source"], dry_run=True
            )
            results_all.append(result)

        except Exception as e:
            print(f"❌ Error migrating {client['name']}: {e}\n")
            results_all.append({"client_name": client["name"], "error": str(e)})

    # Generate report
    print("=" * 80)
    print("📊 PILOT MIGRATION REPORT")
    print("=" * 80 + "\n")

    total_files = sum(r.get("total_files", 0) for r in results_all)
    total_errors = sum(len(r.get("errors", [])) for r in results_all)

    print(f"✅ Clients migrated: {len(pilot_clients)}")
    print(f"📁 Total files: {total_files}")
    print(f"❌ Errors: {total_errors}")
    print(
        f"📊 Success rate: {((total_files - total_errors) / max(total_files, 1) * 100):.1f}%"
    )

    print(f"\n📂 Structure created in: {GDRIVE_SIMULATION}")

    # Save report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = OUTPUT_DIR / f"pilot_report_{timestamp}.json"

    report = {
        "timestamp": datetime.now().isoformat(),
        "mode": "dry-run",
        "pilot_clients": pilot_clients,
        "results": results_all,
        "summary": {
            "clients": len(pilot_clients),
            "total_files": total_files,
            "total_errors": total_errors,
            "success_rate": f"{((total_files - total_errors) / max(total_files, 1) * 100):.1f}%",
        },
    }

    with open(report_file, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"💾 Report saved: {report_file.name}")

    print("\n" + "=" * 80)
    print("✅ PILOT MIGRATION COMPLETE!")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Review structure in: gdrive_structure/")
    print("2. Check categorization accuracy")
    print("3. Verify file naming")
    print("4. If OK → proceed with real migration")
    print()


if __name__ == "__main__":
    try:
        run_pilot_migration()
    except KeyboardInterrupt:
        print("\n\n⚠️  Migration cancelled by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
