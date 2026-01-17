#!/usr/bin/env python3
"""
Scan Current Google Drive Structure

Scansiona il folder Google Drive esistente per capire:
- Quanti file/cartelle ci sono
- Come sono organizzati
- Mapping per riorganizzazione
"""

import json
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build
from collections import defaultdict

# Config
SERVICE_ACCOUNT_FILE = Path(__file__).parent.parent / 'service-account-key.json'
SCOPES = ['https://www.googleapis.com/auth/drive']
FOLDER_ID = '1je2YOEzBf2APKDbAdaXo2MGIu4N5nAEl'
OUTPUT_FILE = Path(__file__).parent / 'gdrive_current_structure.json'


class GDriveScanner:
    def __init__(self, folder_id):
        self.folder_id = folder_id
        self.service = self.init_gdrive()
        self.stats = defaultdict(int)
        self.structure = {}

    def init_gdrive(self):
        """Initialize Google Drive API"""
        print("🔑 Authenticating with Google Drive...")
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        service = build('drive', 'v3', credentials=credentials)
        print("✅ Authentication successful!\n")
        return service

    def get_folder_info(self, folder_id):
        """Get folder metadata"""
        try:
            folder = self.service.files().get(
                fileId=folder_id,
                fields='id, name, mimeType, createdTime, modifiedTime, size'
            ).execute()
            return folder
        except Exception as e:
            print(f"❌ Error getting folder info: {e}")
            return None

    def list_folder_contents(self, folder_id, path=""):
        """Recursively list folder contents"""
        try:
            results = self.service.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                pageSize=1000,
                fields="files(id, name, mimeType, createdTime, modifiedTime, size)",
                orderBy="name"
            ).execute()

            items = results.get('files', [])
            self.stats['total_items'] += len(items)

            folder_data = {
                'path': path,
                'items': [],
                'subfolders': {}
            }

            for item in items:
                is_folder = item['mimeType'] == 'application/vnd.google-apps.folder'

                if is_folder:
                    self.stats['folders'] += 1
                else:
                    self.stats['files'] += 1
                    self.stats['total_size'] += int(item.get('size', 0))

                item_data = {
                    'id': item['id'],
                    'name': item['name'],
                    'type': 'folder' if is_folder else 'file',
                    'created': item.get('createdTime'),
                    'modified': item.get('modifiedTime'),
                    'size': int(item.get('size', 0)) if not is_folder else 0
                }

                folder_data['items'].append(item_data)

                # Recursively scan subfolders (up to 3 levels)
                if is_folder and path.count('/') < 3:
                    print(f"📁 Scanning: {path}/{item['name']}")
                    subfolder = self.list_folder_contents(
                        item['id'],
                        f"{path}/{item['name']}" if path else item['name']
                    )
                    folder_data['subfolders'][item['name']] = subfolder

            return folder_data

        except Exception as e:
            print(f"❌ Error listing folder: {e}")
            return None

    def find_clients(self, structure, clients=None):
        """Extract potential client folders from structure"""
        if clients is None:
            clients = []

        for item in structure.get('items', []):
            if item['type'] == 'folder':
                # Check if looks like a client folder
                name = item['name']

                # Skip known non-client folders
                skip_folders = {'MAS ADIT', 'OM YOYOK', 'Done', 'On Proses',
                               'Cancel', 'Pending', 'C1', 'C18', 'D12', 'E31A',
                               'PEMEGANG KITAS', 'ETC', 'Draft', 'Random'}

                if name not in skip_folders and ' ' in name:
                    # Looks like a person name (has space)
                    clients.append({
                        'name': name,
                        'id': item['id'],
                        'path': structure['path'],
                        'created': item['created'],
                        'modified': item['modified']
                    })

        # Recursively scan subfolders
        for subfolder_name, subfolder_data in structure.get('subfolders', {}).items():
            self.find_clients(subfolder_data, clients)

        return clients

    def scan(self):
        """Main scan function"""
        print("="*80)
        print("📂 SCANNING GOOGLE DRIVE FOLDER")
        print("="*80 + "\n")

        # Get root folder info
        root_info = self.get_folder_info(self.folder_id)
        if not root_info:
            print("❌ Could not access folder. Check permissions!")
            return None

        print(f"Root folder: {root_info.get('name', 'Unknown')}")
        print(f"Folder ID: {self.folder_id}\n")

        # Scan contents
        print("Scanning contents...\n")
        self.structure = self.list_folder_contents(self.folder_id)

        # Find potential clients
        print("\n" + "="*80)
        print("🔍 IDENTIFYING CLIENTS")
        print("="*80 + "\n")

        clients = self.find_clients(self.structure)
        print(f"Found {len(clients)} potential client folders\n")

        # Summary
        print("="*80)
        print("📊 SUMMARY")
        print("="*80 + "\n")

        print(f"Total items:    {self.stats['total_items']:,}")
        print(f"Folders:        {self.stats['folders']:,}")
        print(f"Files:          {self.stats['files']:,}")
        print(f"Total size:     {self.stats['total_size'] / (1024**3):.2f} GB")
        print(f"Potential clients: {len(clients):,}\n")

        # Save results
        output = {
            'folder_id': self.folder_id,
            'folder_name': root_info.get('name'),
            'stats': dict(self.stats),
            'structure': self.structure,
            'clients': clients
        }

        with open(OUTPUT_FILE, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"💾 Results saved to: {OUTPUT_FILE}\n")

        # Sample clients
        if clients:
            print("="*80)
            print("👥 SAMPLE CLIENTS (first 20)")
            print("="*80 + "\n")

            for i, client in enumerate(clients[:20], 1):
                print(f"{i:3}. {client['name']:50} ({client['path']})")

            if len(clients) > 20:
                print(f"\n... and {len(clients)-20} more")

        return output


def main():
    scanner = GDriveScanner(FOLDER_ID)
    result = scanner.scan()

    if result:
        print("\n" + "="*80)
        print("✅ SCAN COMPLETE!")
        print("="*80 + "\n")
        print("Next steps:")
        print("1. Review gdrive_current_structure.json")
        print("2. Export CRM client list")
        print("3. Match Dropbox clients → GDrive folders")
        print("4. Run pilot reorganization\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Scan cancelled")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
