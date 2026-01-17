#!/usr/bin/env python3
"""
Extract REAL Clients from Dropbox

La struttura è più complessa:
ADITYA/
├── MAS ADIT/              ← Team member (non cliente)
│   ├── C1/                ← Tipo visa
│   │   ├── Done/          ← Status
│   │   │   ├── Cliente1/  ← VERO CLIENTE
│   │   │   └── Cliente2/
│   │   └── On Proses/
│   │       └── Cliente3/
│   └── D12/, E31A/, etc.

Questo script estrae SOLO i veri clienti.
"""

import os
from pathlib import Path
from collections import defaultdict

DROPBOX_PATH = Path("/sessions/upbeat-laughing-volta/mnt/antonellosiano/Dropbox")

# Team members / organizer folders (NOT clients)
TEAM_FOLDERS = {
    'MAS ADIT',
    'OM YOYOK',
    'Titip Punya ARI FIRDA',
    'Titip Punya Rina',
    'Titip Punya Vino',
    'Titip punya Suryadi',
    'TITIP KRISNA',
    'Bali Zero',
    'Draft',
    'Random',
    'Foto',
    'BJ',
    'BS',
    'LAPORAN KEUANGAN',
    'Perubahan',
    'Catatan Kerjaan'
}

# Visa type folders
VISA_TYPE_FOLDERS = {
    'C1', 'C18', 'C2', 'C22A&B', 'D1', 'D12', 'E31A', 'E33G',
    'C11', 'C211', 'D211', 'E31C', '211A', '211B'
}

# Status folders
STATUS_FOLDERS = {
    'Done', 'On Proses', 'On Process', 'Cancel', 'Pending'
}

# Utility folders
UTILITY_FOLDERS = {
    'ETC', 'Freelance', 'KBLI', 'KK', 'SET UP PT', 'Kitas to Kitap',
    'Bank Statement', 'STM-DOMISILI-SKCK', 'Contoh surat'
}


def is_client_folder(path: Path) -> bool:
    """Determine if folder is a real client"""
    name = path.name

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

    # Skip special markers
    if name.startswith('#'):
        return False

    # If inside a status folder (Done/On Proses), it's a client
    parent_name = path.parent.name
    if parent_name in STATUS_FOLDERS:
        return True

    # If looks like a person name (2+ words or specific patterns)
    if ' ' in name or any(prefix in name for prefix in ['Mr ', 'Ms ', 'Mrs ']):
        return True

    return False


def extract_all_clients():
    """Extract all real clients from Dropbox"""
    clients = []

    print("\n" + "="*80)
    print("🔍 EXTRACTING REAL CLIENTS FROM DROPBOX")
    print("="*80 + "\n")

    # Repository to scan
    repos_to_scan = [
        DROPBOX_PATH / "ADITYA",
        DROPBOX_PATH / "ANGEL",
        DROPBOX_PATH / "NOVI",
        DROPBOX_PATH / "MEGI",
        DROPBOX_PATH / "YANTI",
        DROPBOX_PATH / "DATA ADI",
        DROPBOX_PATH / "EXTEND VISA"
    ]

    for repo in repos_to_scan:
        if not repo.exists():
            continue

        print(f"📂 Scanning: {repo.name}/")

        # Scan up to 4 levels deep
        for root, dirs, files in os.walk(repo):
            root_path = Path(root)
            depth = len(root_path.relative_to(repo).parts)

            if depth > 4:  # Limit depth
                continue

            for dir_name in dirs:
                dir_path = root_path / dir_name

                if is_client_folder(dir_path):
                    # Count files
                    file_count = sum(1 for _ in dir_path.rglob('*') if _.is_file())

                    if file_count > 0:  # Only if has files
                        clients.append({
                            'name': dir_name,
                            'full_path': str(dir_path.relative_to(DROPBOX_PATH)),
                            'repository': repo.name,
                            'parent_context': root_path.name,
                            'file_count': file_count,
                            'depth': depth
                        })

                        print(f"   ✅ Found: {dir_name} ({file_count} files)")

    # Remove duplicates
    unique_clients = {}
    for client in clients:
        key = client['name']
        if key not in unique_clients or client['file_count'] > unique_clients[key]['file_count']:
            unique_clients[key] = client

    clients_list = list(unique_clients.values())
    clients_list.sort(key=lambda x: x['name'])

    print(f"\n{'='*80}")
    print(f"📊 SUMMARY")
    print(f"{'='*80}\n")
    print(f"Total unique clients found: {len(clients_list)}")
    print(f"\nTop 20 clients by file count:\n")

    for client in sorted(clients_list, key=lambda x: x['file_count'], reverse=True)[:20]:
        print(f"   {client['name']:40} - {client['file_count']:4} files - {client['repository']}")

    # Save to file
    output_file = Path(__file__).parent / "real_clients_extracted.txt"
    with open(output_file, 'w') as f:
        f.write("REAL CLIENTS EXTRACTED FROM DROPBOX\n")
        f.write("="*80 + "\n\n")

        for client in clients_list:
            f.write(f"{client['name']}\n")
            f.write(f"  Path: {client['full_path']}\n")
            f.write(f"  Files: {client['file_count']}\n")
            f.write(f"  Repository: {client['repository']}\n")
            f.write(f"\n")

    print(f"\n💾 Full list saved to: {output_file.name}\n")

    return clients_list


if __name__ == "__main__":
    try:
        clients = extract_all_clients()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
