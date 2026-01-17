#!/usr/bin/env python3
"""
MIGRAZIONE TEST - 100 Clienti
Da Dropbox locale → Google Drive

Struttura per ogni cliente:
  Cliente Nome/
    ├── 01_Passport/
    ├── 02_Company/
    └── 03_Other_Documents/
"""

import json
import shutil
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Config
DROPBOX_PATH = Path("/sessions/upbeat-laughing-volta/mnt/antonellosiano/Dropbox")
SERVICE_ACCOUNT_FILE = Path(__file__).parent.parent / 'service-account-key.json'
SCOPES = ['https://www.googleapis.com/auth/drive']
GDRIVE_PARENT_FOLDER = '1je2YOEzBf2APKDbAdaXo2MGIu4N5nAEl'  # CRM folder
TEST_CLIENTS_FILE = Path(__file__).parent / 'test_100_clients.json'

# Categorization rules
PASSPORT_KEYWORDS = ['passport', 'paspor', 'pp', 'pasaporte']
COMPANY_KEYWORDS = ['pt', 'pma', 'cv', 'company', 'perusahaan', 'npwp', 'nib', 'akta', 'deed']


class MigrationEngine:
    def __init__(self):
        self.stats = {
            'clients_migrated': 0,
            'files_uploaded': 0,
            'errors': []
        }

        print("🔑 Initializing Google Drive...")
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        self.service = build('drive', 'v3', credentials=credentials)
        print("✅ Connected!\n")

    def create_folder(self, name, parent_id):
        """Create folder in Google Drive"""
        file_metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }

        folder = self.service.files().create(
            body=file_metadata,
            fields='id'
        ).execute()

        return folder.get('id')

    def upload_file(self, file_path, folder_id):
        """Upload file to Google Drive"""
        file_metadata = {
            'name': file_path.name,
            'parents': [folder_id]
        }

        media = MediaFileUpload(
            str(file_path),
            resumable=True
        )

        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()

        return file.get('id')

    def categorize_file(self, filename):
        """Categorize file by name"""
        filename_lower = filename.lower()

        # Passport
        if any(kw in filename_lower for kw in PASSPORT_KEYWORDS):
            return '01_Passport'

        # Company
        if any(kw in filename_lower for kw in COMPANY_KEYWORDS):
            return '02_Company'

        # Default
        return '03_Other_Documents'

    def migrate_client(self, client):
        """Migrate one client"""
        client_name = client['name']
        print(f"\n📁 {client_name}")

        try:
            # 1. Create client folder
            client_folder_id = self.create_folder(client_name, GDRIVE_PARENT_FOLDER)
            print(f"   ✅ Folder created")

            # 2. Create category subfolders
            categories = {
                '01_Passport': self.create_folder('01_Passport', client_folder_id),
                '02_Company': self.create_folder('02_Company', client_folder_id),
                '03_Other_Documents': self.create_folder('03_Other_Documents', client_folder_id)
            }
            print(f"   ✅ Categories created")

            # 3. Get all files from Dropbox
            client_path = DROPBOX_PATH / client['full_path']
            files = list(client_path.rglob('*'))
            files = [f for f in files if f.is_file() and not f.name.startswith('.')]

            print(f"   📄 Uploading {len(files)} files...")

            # 4. Upload files
            for file_path in files:
                category = self.categorize_file(file_path.name)
                folder_id = categories[category]

                self.upload_file(file_path, folder_id)
                self.stats['files_uploaded'] += 1

                # Progress
                if self.stats['files_uploaded'] % 10 == 0:
                    print(f"      {self.stats['files_uploaded']} files...")

            print(f"   ✅ {len(files)} files uploaded")
            self.stats['clients_migrated'] += 1

        except Exception as e:
            print(f"   ❌ Error: {e}")
            self.stats['errors'].append({
                'client': client_name,
                'error': str(e)
            })

    def run(self):
        """Run migration for 100 test clients"""
        print("="*80)
        print("🚀 MIGRAZIONE TEST - 100 CLIENTI")
        print("="*80 + "\n")

        # Load clients
        with open(TEST_CLIENTS_FILE, 'r') as f:
            data = json.load(f)
            clients = data['clients']

        print(f"Loaded {len(clients)} clients\n")

        # Migrate each client
        for i, client in enumerate(clients, 1):
            print(f"[{i}/{len(clients)}]", end=' ')
            self.migrate_client(client)

        # Summary
        print("\n" + "="*80)
        print("📊 SUMMARY")
        print("="*80 + "\n")
        print(f"Clients migrated: {self.stats['clients_migrated']}/{len(clients)}")
        print(f"Files uploaded:   {self.stats['files_uploaded']}")
        print(f"Errors:           {len(self.stats['errors'])}")

        if self.stats['errors']:
            print("\n❌ Errors:")
            for err in self.stats['errors'][:10]:
                print(f"   - {err['client']}: {err['error']}")


def main():
    try:
        engine = MigrationEngine()
        engine.run()
    except KeyboardInterrupt:
        print("\n\n⚠️ Migration cancelled")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
