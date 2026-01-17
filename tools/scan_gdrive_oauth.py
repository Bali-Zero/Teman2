#!/usr/bin/env python3
"""
Scan Google Drive usando OAuth2 (user credentials)
Più semplice del service account - usa il TUO account Google
"""

import json
import pickle
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from collections import defaultdict

# Config
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
FOLDER_ID = '1je2YOEzBf2APKDbAdaXo2MGIu4N5nAEl'
TOKEN_FILE = Path(__file__).parent / 'token.pickle'
OUTPUT_FILE = Path(__file__).parent / 'gdrive_current_structure.json'


def get_credentials():
    """Get user credentials via OAuth2"""
    creds = None

    # Token salvato da sessione precedente
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)

    # Se non c'è token o è scaduto
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Crea credentials manualmente (senza file client_secret)
            # Usa public client ID di Google
            flow = InstalledAppFlow.from_client_config(
                {
                    "installed": {
                        "client_id": "407408718192.apps.googleusercontent.com",
                        "client_secret": "************",
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": ["http://localhost"]
                    }
                },
                SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Salva token per prossima volta
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)

    return creds


def scan_folder(service, folder_id, path="", depth=0, max_depth=3):
    """Scan folder recursively"""
    if depth > max_depth:
        return None

    try:
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            pageSize=1000,
            fields="files(id, name, mimeType, createdTime, modifiedTime, size)",
            orderBy="name"
        ).execute()

        items = results.get('files', [])

        folder_data = {
            'path': path,
            'items': [],
            'subfolders': {}
        }

        for item in items:
            is_folder = item['mimeType'] == 'application/vnd.google-apps.folder'

            item_data = {
                'id': item['id'],
                'name': item['name'],
                'type': 'folder' if is_folder else 'file',
                'size': int(item.get('size', 0)) if not is_folder else 0
            }

            folder_data['items'].append(item_data)

            if is_folder and depth < max_depth:
                print(f"{'  ' * depth}📁 {path}/{item['name']}" if path else f"📁 {item['name']}")
                subfolder = scan_folder(
                    service,
                    item['id'],
                    f"{path}/{item['name']}" if path else item['name'],
                    depth + 1,
                    max_depth
                )
                if subfolder:
                    folder_data['subfolders'][item['name']] = subfolder

        return folder_data

    except Exception as e:
        print(f"❌ Error scanning {path}: {e}")
        return None


def main():
    print("\n" + "="*80)
    print("📂 GOOGLE DRIVE SCANNER (OAuth2)")
    print("="*80 + "\n")

    print("🔑 Authenticating...")
    print("   (Browser window will open for authorization)\n")

    try:
        creds = get_credentials()
        service = build('drive', 'v3', credentials=creds)

        print("✅ Authentication successful!\n")

        # Get folder info
        folder = service.files().get(
            fileId=FOLDER_ID,
            fields='id, name, createdTime'
        ).execute()

        print(f"📂 Scanning folder: {folder['name']}")
        print(f"   ID: {FOLDER_ID}\n")

        # Scan
        structure = scan_folder(service, FOLDER_ID)

        # Count stats
        def count_items(data):
            folders = 0
            files = 0
            size = 0

            for item in data.get('items', []):
                if item['type'] == 'folder':
                    folders += 1
                else:
                    files += 1
                    size += item.get('size', 0)

            for subfolder in data.get('subfolders', {}).values():
                sf, ff, sz = count_items(subfolder)
                folders += sf
                files += ff
                size += sz

            return folders, files, size

        total_folders, total_files, total_size = count_items(structure)

        print(f"\n{'='*80}")
        print("📊 SUMMARY")
        print(f"{'='*80}\n")
        print(f"Folders: {total_folders:,}")
        print(f"Files:   {total_files:,}")
        print(f"Size:    {total_size / (1024**3):.2f} GB\n")

        # Save
        output = {
            'folder_id': FOLDER_ID,
            'folder_name': folder['name'],
            'total_folders': total_folders,
            'total_files': total_files,
            'total_size': total_size,
            'structure': structure
        }

        with open(OUTPUT_FILE, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"💾 Saved to: {OUTPUT_FILE}\n")

        print("="*80)
        print("✅ SCAN COMPLETE!")
        print("="*80 + "\n")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
