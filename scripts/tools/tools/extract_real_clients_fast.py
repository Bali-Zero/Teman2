#!/usr/bin/env python3
"""
Extract REAL Clients from Dropbox - FAST VERSION

Optimized version that:
1. Quickly identifies client folders
2. Uses fast file counting (limit depth)
3. Saves progress incrementally
"""

import os
import json
from pathlib import Path

DROPBOX_PATH = Path("/sessions/upbeat-laughing-volta/mnt/antonellosiano/Dropbox")
OUTPUT_DIR = Path(__file__).parent
OUTPUT_FILE = OUTPUT_DIR / "real_clients_extracted.json"

# Team members / organizer folders (NOT clients)
TEAM_FOLDERS = {
    "MAS ADIT",
    "OM YOYOK",
    "Titip Punya ARI FIRDA",
    "Titip Punya Rina",
    "Titip Punya Vino",
    "Titip punya Suryadi",
    "TITIP KRISNA",
    "Bali Zero",
    "Draft",
    "Random",
    "Foto",
    "BJ",
    "BS",
    "LAPORAN KEUANGAN",
    "Perubahan",
    "Catatan Kerjaan",
}

# Visa type folders
VISA_TYPE_FOLDERS = {
    "C1",
    "C18",
    "C2",
    "C22A&B",
    "D1",
    "D12",
    "E31A",
    "E33G",
    "C11",
    "C211",
    "D211",
    "E31C",
    "211A",
    "211B",
    "C7",
    "C22",
}

# Status folders
STATUS_FOLDERS = {
    "Done",
    "On Proses",
    "On Process",
    "Cancel",
    "Pending",
    "Sudah Submit",
}

# Utility folders
UTILITY_FOLDERS = {
    "ETC",
    "Freelance",
    "KBLI",
    "KK",
    "SET UP PT",
    "Kitas to Kitap",
    "Bank Statement",
    "STM-DOMISILI-SKCK",
    "Contoh surat",
    "Working kitas",
    "Spouse Kitas",
    "Retirement Kitas",
    "Bridging Visa",
    "Set UP PT",
    "Invoice Extend",
    "Invoice BS",
    "Minuta Sirkuler",
}


def is_client_folder(path: Path) -> bool:
    """Determine if folder is a real client"""
    name = path.name

    # Skip hidden/system folders
    if name.startswith(".") or name.startswith("#"):
        return False

    # Skip utility
    if name in UTILITY_FOLDERS:
        return False

    # Skip team/organizers
    if name in TEAM_FOLDERS:
        return False

    # Skip visa types
    if name in VISA_TYPE_FOLDERS:
        return False

    # Skip status
    if name in STATUS_FOLDERS:
        return False

    # If inside a status folder (Done/On Proses), it's a client
    parent_name = path.parent.name
    if parent_name in STATUS_FOLDERS:
        return True

    # If looks like a person name (2+ words or specific patterns)
    if " " in name or any(prefix in name for prefix in ["Mr ", "Ms ", "Mrs ", "Miss "]):
        # But not if it's a descriptive folder
        lower_name = name.lower()
        if any(
            word in lower_name
            for word in ["invoice", "laporan", "data", "catatan", "new folder"]
        ):
            return False
        return True

    return False


def fast_file_count(path: Path, max_files=100) -> int:
    """Quick file count - stop at max_files for speed"""
    count = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file():
                count += 1
                if count >= max_files:
                    return count  # Fast exit
    except (PermissionError, OSError):
        pass
    return count


def extract_from_repo(repo: Path, repo_name: str):
    """Extract clients from one repository"""
    clients = []

    if not repo.exists():
        print(f"   ⚠️ Repository not found: {repo_name}")
        return clients

    print(f"📂 Scanning: {repo_name}/")

    # Scan up to 4 levels deep
    for root, dirs, files in os.walk(repo):
        root_path = Path(root)

        try:
            depth = len(root_path.relative_to(repo).parts)
        except ValueError:
            continue

        if depth > 4:  # Limit depth
            dirs.clear()  # Don't descend further
            continue

        for dir_name in list(dirs):  # Copy list to allow modification
            dir_path = root_path / dir_name

            if is_client_folder(dir_path):
                # Fast file count
                file_count = fast_file_count(dir_path, max_files=100)

                if file_count > 0:  # Only if has files
                    client_data = {
                        "name": dir_name,
                        "full_path": str(dir_path.relative_to(DROPBOX_PATH)),
                        "repository": repo_name,
                        "parent_context": root_path.name,
                        "file_count": file_count,
                        "file_count_estimated": file_count >= 100,
                        "depth": depth,
                    }
                    clients.append(client_data)
                    print(
                        f"   ✅ {dir_name} ({file_count}{'+ ' if file_count >= 100 else ' '}files)"
                    )

    return clients


def main():
    print("\n" + "=" * 80)
    print("🔍 EXTRACTING REAL CLIENTS FROM DROPBOX (FAST MODE)")
    print("=" * 80 + "\n")

    # Repository to scan
    repos_to_scan = [
        ("ADITYA", DROPBOX_PATH / "ADITYA"),
        ("ANGEL", DROPBOX_PATH / "ANGEL"),
        ("NOVI", DROPBOX_PATH / "NOVI"),
        ("MEGI", DROPBOX_PATH / "MEGI"),
        ("YANTI", DROPBOX_PATH / "YANTI"),
        ("DATA ADI", DROPBOX_PATH / "DATA ADI"),
        ("EXTEND VISA", DROPBOX_PATH / "EXTEND VISA"),
    ]

    all_clients = []

    for repo_name, repo_path in repos_to_scan:
        clients = extract_from_repo(repo_path, repo_name)
        all_clients.extend(clients)
        print(f"   → Found {len(clients)} clients in {repo_name}\n")

    # Remove duplicates (keep entry with most files)
    unique_clients = {}
    for client in all_clients:
        key = client["name"]
        if (
            key not in unique_clients
            or client["file_count"] > unique_clients[key]["file_count"]
        ):
            unique_clients[key] = client

    clients_list = list(unique_clients.values())
    clients_list.sort(key=lambda x: x["name"])

    # Summary
    print(f"\n{'=' * 80}")
    print("📊 SUMMARY")
    print(f"{'=' * 80}\n")
    print(f"Total unique clients found: {len(clients_list)}")
    print(f"Total client entries (with duplicates): {len(all_clients)}")
    print("\nTop 30 clients by file count:\n")

    for client in sorted(clients_list, key=lambda x: x["file_count"], reverse=True)[
        :30
    ]:
        estimated = "+ (estimated)" if client.get("file_count_estimated") else ""
        print(f"   {client['name']:50} - {client['file_count']:4} files {estimated}")

    # Save to JSON
    output = {
        "timestamp": str(Path(__file__).stat().st_mtime),
        "total_unique_clients": len(clients_list),
        "total_entries": len(all_clients),
        "clients": clients_list,
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n💾 Full list saved to: {OUTPUT_FILE.name}\n")

    # Also save simple text list
    text_file = OUTPUT_DIR / "real_clients_list.txt"
    with open(text_file, "w") as f:
        f.write("REAL CLIENTS EXTRACTED FROM DROPBOX\n")
        f.write("=" * 80 + "\n\n")
        for client in clients_list:
            f.write(f"{client['name']}\n")
            f.write(f"  Repository: {client['repository']}\n")
            f.write(f"  Path: {client['full_path']}\n")
            f.write(f"  Files: {client['file_count']}\n\n")

    print(f"📄 Text list saved to: {text_file.name}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Extraction cancelled by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
