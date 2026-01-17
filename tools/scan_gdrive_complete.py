#!/usr/bin/env python3
"""
SCAN COMPLETO GOOGLE DRIVE
Analizza tutto quello che hai in CRM folder
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
FOLDER_ID = '1je2YOEzBf2APKDbAdaXo2MGIu4N5nAEl'  # CRM folder
TOKEN_FILE = Path(__file__).parent / 'token.pickle'
OUTPUT_FILE = Path(__file__).parent / 'gdrive_scan_results.json'

# Filtri
TEAM_FOLDERS = {
    'MAS ADIT', 'OM YOYOK', 'Om Oman', 'MAS ADI', 'OM FIRDA',
    'Titip Punya ARI FIRDA', 'FIRDA', 'ARI', 'MAS YOYOK'
}

UTILITY_FOLDERS = {
    'Bali Zero', 'Draft', 'Foto', 'BS', 'Backup', 'Archive',
    'Template', 'Samples', 'Test', 'Old', 'Downloads'
}

CATEGORY_FOLDERS = {
    'COMPANY', 'INDIVIDUAL', 'DATA BS', 'DATA ADI',
    'EXTEND VISA', 'ADITYA', 'ANGEL', 'MEGI', 'NOVI', 'YANTI'
}

VISA_TYPES = {'ALTUS', 'ITAS', 'KITAP', 'KITAS', 'E-VISA', 'VOA'}
STATUS_FOLDERS = {'Done', 'On Proses', 'Pending', 'Rejected', 'Cancelled'}


def get_credentials():
    """Get user credentials via OAuth2"""
    creds = None

    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
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

        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)

    return creds


def is_client_folder(name, parent_path):
    """Determina se è una cartella cliente"""
    # Escludi categorie top-level
    if name in CATEGORY_FOLDERS:
        return False

    # Escludi lavoratori
    if name in TEAM_FOLDERS:
        return False

    # Escludi utility
    if name in UTILITY_FOLDERS:
        return False

    # Escludi visa types
    if name in VISA_TYPES:
        return False

    # Escludi status
    if name in STATUS_FOLDERS:
        return False

    # Se parent contiene lavoratore, skip
    if any(worker in parent_path for worker in TEAM_FOLDERS):
        return False

    # Se parent è status o visa type, probabile cliente
    parent_parts = parent_path.split('/')
    if any(part in STATUS_FOLDERS for part in parent_parts):
        return True
    if any(part in VISA_TYPES for part in parent_parts):
        return True

    # Default: considera cliente
    return True


def scan_folder_recursive(service, folder_id, path="", depth=0, max_depth=5):
    """Scan folder ricorsivamente"""
    if depth > max_depth:
        return None

    try:
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            pageSize=1000,
            fields="files(id, name, mimeType, size, createdTime, modifiedTime)",
            orderBy="name"
        ).execute()

        items = results.get('files', [])

        folder_data = {
            'path': path,
            'folders': [],
            'files': [],
            'stats': {
                'total_folders': 0,
                'total_files': 0,
                'total_size': 0,
                'client_folders': 0
            }
        }

        for item in items:
            is_folder = item['mimeType'] == 'application/vnd.google-apps.folder'

            if is_folder:
                folder_info = {
                    'id': item['id'],
                    'name': item['name'],
                    'is_client': is_client_folder(item['name'], path)
                }

                folder_data['folders'].append(folder_info)
                folder_data['stats']['total_folders'] += 1

                if folder_info['is_client']:
                    folder_data['stats']['client_folders'] += 1

                # Scan subfolder
                print(f"{'  ' * depth}📁 {path}/{item['name']}" if path else f"📁 {item['name']}")

                subfolder = scan_folder_recursive(
                    service,
                    item['id'],
                    f"{path}/{item['name']}" if path else item['name'],
                    depth + 1,
                    max_depth
                )

                if subfolder:
                    folder_info['content'] = subfolder
                    # Aggrega stats
                    folder_data['stats']['total_folders'] += subfolder['stats']['total_folders']
                    folder_data['stats']['total_files'] += subfolder['stats']['total_files']
                    folder_data['stats']['total_size'] += subfolder['stats']['total_size']
                    folder_data['stats']['client_folders'] += subfolder['stats']['client_folders']

            else:
                file_info = {
                    'name': item['name'],
                    'size': int(item.get('size', 0))
                }
                folder_data['files'].append(file_info)
                folder_data['stats']['total_files'] += 1
                folder_data['stats']['total_size'] += file_info['size']

        return folder_data

    except Exception as e:
        print(f"❌ Error scanning {path}: {e}")
        return None


def analyze_structure(data):
    """Analizza la struttura e genera report"""
    print("\n" + "="*80)
    print("📊 ANALISI STRUTTURA")
    print("="*80 + "\n")

    stats = data['stats']

    print(f"Cartelle totali:    {stats['total_folders']:,}")
    print(f"File totali:        {stats['total_files']:,}")
    print(f"Dimensione totale:  {stats['total_size'] / (1024**3):.2f} GB")
    print(f"")
    print(f"🎯 Cartelle CLIENTI: {stats['client_folders']:,}")
    print()

    # Lista top-level folders
    print("📂 Cartelle TOP-LEVEL:")
    for folder in data['folders']:
        client_mark = "✅" if folder['is_client'] else "📁"
        subfolder_count = folder.get('content', {}).get('stats', {}).get('client_folders', 0)
        print(f"   {client_mark} {folder['name']}")
        if subfolder_count > 0:
            print(f"      → {subfolder_count} clienti dentro")

    print()


def extract_all_clients(data, clients_list=None, parent_path=""):
    """Estrai lista di TUTTI i clienti"""
    if clients_list is None:
        clients_list = []

    for folder in data.get('folders', []):
        folder_name = folder['name']
        current_path = f"{parent_path}/{folder_name}" if parent_path else folder_name

        # Se è cliente, aggiungi
        if folder['is_client']:
            # Conta file
            file_count = 0
            if 'content' in folder:
                file_count = folder['content']['stats']['total_files']

            clients_list.append({
                'name': folder_name,
                'path': current_path,
                'file_count': file_count,
                'drive_id': folder['id']
            })

        # Scansiona subfolders
        if 'content' in folder:
            extract_all_clients(folder['content'], clients_list, current_path)

    return clients_list


def main():
    print("\n" + "="*80)
    print("🔍 SCAN COMPLETO GOOGLE DRIVE")
    print("="*80 + "\n")

    print("🔑 Autenticazione...")
    print("   (Si aprirà il browser per login Google)\n")

    try:
        creds = get_credentials()
        service = build('drive', 'v3', credentials=creds)

        print("✅ Autenticato!\n")

        # Get folder info
        folder = service.files().get(
            fileId=FOLDER_ID,
            fields='id, name'
        ).execute()

        print(f"📂 Scanning: {folder['name']}")
        print(f"   ID: {FOLDER_ID}\n")

        # Scan completo
        print("🔍 Scansione in corso...\n")
        structure = scan_folder_recursive(service, FOLDER_ID)

        # Analizza
        analyze_structure(structure)

        # Estrai clienti
        print("="*80)
        print("🎯 ESTRAZIONE CLIENTI")
        print("="*80 + "\n")

        clients = extract_all_clients(structure)
        clients.sort(key=lambda x: x['name'].lower())

        print(f"Trovati {len(clients)} clienti totali\n")

        # Mostra primi 20
        print("📋 Primi 20 clienti:")
        for i, client in enumerate(clients[:20], 1):
            print(f"   {i:2}. {client['name']} ({client['file_count']} files)")

        if len(clients) > 20:
            print(f"   ... e altri {len(clients) - 20} clienti\n")

        # Salva risultati
        output = {
            'folder_id': FOLDER_ID,
            'folder_name': folder['name'],
            'scan_date': '2026-01-16',
            'summary': structure['stats'],
            'structure': structure,
            'clients': clients
        }

        with open(OUTPUT_FILE, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"💾 Risultati salvati: {OUTPUT_FILE}\n")

        print("="*80)
        print("✅ SCAN COMPLETATO!")
        print("="*80 + "\n")

        print("🎯 PROSSIMI STEP:")
        print("   1. Verifica la lista clienti nel file JSON")
        print("   2. Decidi se la struttura attuale è OK")
        print("   3. Posso creare script per riorganizzare tutto\n")

    except Exception as e:
        print(f"\n❌ Errore: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
