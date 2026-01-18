#!/usr/bin/env python3
"""
PREPARAZIONE LOCALE - 100 Clienti
Crea struttura locale pronta per upload manuale

Output: ~/Desktop/GDRIVE_READY/
  ├── Cliente 1/
  │   ├── 01_Passport/
  │   ├── 02_Company/
  │   └── 03_Other_Documents/
  └── Cliente 2/
      └── ...
"""

import json
import shutil
from pathlib import Path

# Config
DROPBOX_PATH = Path("/sessions/upbeat-laughing-volta/mnt/antonellosiano/Dropbox")
OUTPUT_DIR = Path.home() / "Desktop" / "GDRIVE_READY"
TEST_CLIENTS_FILE = Path(__file__).parent / "test_100_clients.json"

# Keywords
PASSPORT_KEYWORDS = ["passport", "paspor", "pp", "pasaporte"]
COMPANY_KEYWORDS = [
    "pt",
    "pma",
    "cv",
    "company",
    "perusahaan",
    "npwp",
    "nib",
    "akta",
    "deed",
]


def categorize_file(filename):
    """Categorize file"""
    filename_lower = filename.lower()

    if any(kw in filename_lower for kw in PASSPORT_KEYWORDS):
        return "01_Passport"
    if any(kw in filename_lower for kw in COMPANY_KEYWORDS):
        return "02_Company"
    return "03_Other_Documents"


def prepare_client(client, output_dir):
    """Prepare one client"""
    client_name = client["name"]
    print(f"📁 {client_name}", end=" ")

    try:
        # Create client folder
        client_dir = output_dir / client_name
        client_dir.mkdir(parents=True, exist_ok=True)

        # Create category folders
        (client_dir / "01_Passport").mkdir(exist_ok=True)
        (client_dir / "02_Company").mkdir(exist_ok=True)
        (client_dir / "03_Other_Documents").mkdir(exist_ok=True)

        # Get files from Dropbox
        client_path = DROPBOX_PATH / client["full_path"]
        if not client_path.exists():
            print("❌ Path not found")
            return 0

        files = list(client_path.rglob("*"))
        files = [f for f in files if f.is_file() and not f.name.startswith(".")]

        # Copy files
        for file_path in files:
            category = categorize_file(file_path.name)
            dest_dir = client_dir / category
            shutil.copy2(file_path, dest_dir / file_path.name)

        print(f"✅ {len(files)} files")
        return len(files)

    except Exception as e:
        print(f"❌ {e}")
        return 0


def main():
    print("\n" + "=" * 80)
    print("📦 PREPARAZIONE LOCALE - 100 CLIENTI")
    print("=" * 80 + "\n")

    # Clean output dir
    if OUTPUT_DIR.exists():
        print("🗑️  Cleaning old output...")
        shutil.rmtree(OUTPUT_DIR)

    OUTPUT_DIR.mkdir(parents=True)
    print(f"📂 Output: {OUTPUT_DIR}\n")

    # Load clients
    with open(TEST_CLIENTS_FILE, "r") as f:
        data = json.load(f)
        clients = data["clients"]

    print(f"Processing {len(clients)} clients...\n")

    total_files = 0
    success = 0

    for i, client in enumerate(clients, 1):
        print(f"[{i:3}/{len(clients)}] ", end="")
        files = prepare_client(client, OUTPUT_DIR)
        if files > 0:
            success += 1
            total_files += files

    print("\n" + "=" * 80)
    print("✅ COMPLETE!")
    print("=" * 80 + "\n")
    print(f"Clients prepared: {success}/{len(clients)}")
    print(f"Total files:      {total_files}")
    print(f"\nOutput folder: {OUTPUT_DIR}")
    print("\n📤 Ora puoi:")
    print("   1. Aprire il folder nel Finder")
    print("   2. Selezionare tutto")
    print("   3. Drag & drop su Google Drive")
    print()


if __name__ == "__main__":
    main()
