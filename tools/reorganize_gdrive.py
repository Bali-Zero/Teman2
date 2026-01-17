#!/usr/bin/env python3
"""
RIORGANIZZAZIONE GOOGLE DRIVE
Scansiona e riorganizza automaticamente tutti i clienti in CRM/

MODALITÀ:
- DRY RUN: Mostra cosa farebbe senza modificare nulla
- EXECUTE: Esegue le modifiche reali
"""

import json
import pickle
import sys
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from collections import defaultdict

# Config
SCOPES = ['https://www.googleapis.com/auth/drive']
FOLDER_ID = '1je2YOEzBf2APKDbAdaXo2MGIu4N5nAEl'  # CRM folder
TOKEN_FILE = Path(__file__).parent / 'token.pickle'
OUTPUT_FILE = Path(__file__).parent / 'reorganization_plan.json'

# Filtri
TEAM_FOLDERS = {
    'MAS ADIT', 'OM YOYOK', 'Om Oman', 'MAS ADI', 'OM FIRDA',
    'Titip Punya ARI FIRDA', 'FIRDA', 'ARI', 'MAS YOYOK',
    'Titip Punya Rina', 'Titip Punya Vino', 'Titip Punya'
}

UTILITY_FOLDERS = {
    'Bali Zero', 'Draft', 'Foto', 'BS', 'Backup', 'Archive',
    'Template', 'Samples', 'Test', 'Old', 'Downloads', '.DS_Store'
}

CATEGORY_FOLDERS = {
    'COMPANY', 'INDIVIDUAL', 'DATA BS', 'DATA ADI',
    'EXTEND VISA', 'ADITYA', 'ANGEL', 'MEGI', 'NOVI', 'YANTI'
}

VISA_TYPES = {'ALTUS', 'ITAS', 'KITAP', 'KITAS', 'E-VISA', 'VOA'}
STATUS_FOLDERS = {'Done', 'On Proses', 'Pending', 'Rejected', 'Cancelled'}

# Keywords categorizzazione file
PASSPORT_KEYWORDS = ['passport', 'paspor', 'pp', 'pasaporte']
COMPANY_KEYWORDS = ['pt', 'pma', 'cv', 'company', 'perusahaan', 'npwp', 'nib', 'akta', 'deed']


def get_credentials():
    """Get OAuth2 credentials"""
    creds = None

    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Usa client pubblico Google
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
    # Escludi categorie
    if name in CATEGORY_FOLDERS:
        return False

    # Escludi lavoratori
    if name in TEAM_FOLDERS:
        return False

    # Escludi se nome contiene "Titip"
    if 'titip' in name.lower():
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

    # Se parent contiene "titip", skip
    if 'titip' in parent_path.lower():
        return False

    # Se parent è status o visa type, probabile cliente
    parent_parts = parent_path.split('/')
    if any(part in STATUS_FOLDERS for part in parent_parts):
        return True
    if any(part in VISA_TYPES for part in parent_parts):
        return True

    # Default: considera cliente se non nelle esclusioni
    return True


def categorize_file(filename):
    """Categorizza file in 01/02/03"""
    filename_lower = filename.lower()

    # Passport
    if any(kw in filename_lower for kw in PASSPORT_KEYWORDS):
        return '01_Passport'

    # Company
    if any(kw in filename_lower for kw in COMPANY_KEYWORDS):
        return '02_Company'

    # Default
    return '03_Other_Documents'


class ReorganizationEngine:
    def __init__(self, dry_run=True):
        self.dry_run = dry_run
        self.service = None
        self.stats = {
            'clients_found': 0,
            'clients_created': 0,
            'files_moved': 0,
            'folders_deleted': 0,
            'errors': []
        }
        self.reorganization_plan = []

    def authenticate(self):
        """Autentica con Google Drive"""
        print("🔑 Autenticazione Google Drive...")
        creds = get_credentials()
        self.service = build('drive', 'v3', credentials=creds)
        print("✅ Autenticato!\n")

    def scan_recursive(self, folder_id, path="", depth=0, max_depth=10):
        """Scan ricorsivo per trovare clienti"""
        if depth > max_depth:
            return []

        clients = []

        try:
            # Lista items in folder
            results = self.service.files().list(
                q=f"'{folder_id}' in parents and trashed=false and mimeType='application/vnd.google-apps.folder'",
                pageSize=1000,
                fields="files(id, name)",
                orderBy="name"
            ).execute()

            items = results.get('files', [])

            for item in items:
                folder_name = item['name']
                current_path = f"{path}/{folder_name}" if path else folder_name

                # Determina se è cliente
                if is_client_folder(folder_name, path):
                    # Conta file in questo folder
                    file_results = self.service.files().list(
                        q=f"'{item['id']}' in parents and trashed=false",
                        pageSize=1000,
                        fields="files(id, name, mimeType)"
                    ).execute()

                    files = [f for f in file_results.get('files', [])
                            if f['mimeType'] != 'application/vnd.google-apps.folder']

                    if len(files) > 0:  # Solo clienti con file
                        clients.append({
                            'name': folder_name,
                            'id': item['id'],
                            'path': current_path,
                            'files': files
                        })
                        self.stats['clients_found'] += 1

                        if self.stats['clients_found'] % 10 == 0:
                            print(f"   Trovati {self.stats['clients_found']} clienti...")

                # Scan ricorsivo subfolder
                sub_clients = self.scan_recursive(item['id'], current_path, depth + 1, max_depth)
                clients.extend(sub_clients)

        except Exception as e:
            print(f"❌ Errore scanning {path}: {e}")
            self.stats['errors'].append({'path': path, 'error': str(e)})

        return clients

    def create_client_structure(self, client_name):
        """Crea struttura 01/02/03 per cliente"""
        if self.dry_run:
            return {'client': 'fake_id', 'folders': {
                '01_Passport': 'fake_id_1',
                '02_Company': 'fake_id_2',
                '03_Other_Documents': 'fake_id_3'
            }}

        # Crea folder cliente nella root CRM
        client_folder = self.service.files().create(
            body={
                'name': client_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [FOLDER_ID]
            },
            fields='id'
        ).execute()

        # Crea 3 subfolders
        folders = {}
        for folder_name in ['01_Passport', '02_Company', '03_Other_Documents']:
            subfolder = self.service.files().create(
                body={
                    'name': folder_name,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [client_folder['id']]
                },
                fields='id'
            ).execute()
            folders[folder_name] = subfolder['id']

        return {'client': client_folder['id'], 'folders': folders}

    def move_file(self, file_id, new_parent_id, old_parent_id):
        """Muovi file a nuova posizione"""
        if self.dry_run:
            return True

        try:
            self.service.files().update(
                fileId=file_id,
                addParents=new_parent_id,
                removeParents=old_parent_id,
                fields='id, parents'
            ).execute()
            return True
        except Exception as e:
            print(f"   ❌ Errore moving file: {e}")
            return False

    def process_client(self, client):
        """Processa un cliente: crea struttura e muove file"""
        client_name = client['name']

        # Crea struttura
        structure = self.create_client_structure(client_name)

        # Categorizza e muovi file
        files_moved = 0
        for file in client['files']:
            category = categorize_file(file['name'])
            target_folder_id = structure['folders'][category]

            if self.move_file(file['id'], target_folder_id, client['id']):
                files_moved += 1

        return files_moved

    def run(self):
        """Esegui riorganizzazione"""
        mode = "🔍 DRY RUN" if self.dry_run else "⚠️  ESECUZIONE REALE"

        print("\n" + "="*80)
        print(f"{mode} - RIORGANIZZAZIONE GOOGLE DRIVE")
        print("="*80 + "\n")

        # Autentica
        self.authenticate()

        # Scan completo
        print("🔍 Scansione completa CRM folder...")
        print(f"   Questo può richiedere 5-10 minuti...\n")

        clients = self.scan_recursive(FOLDER_ID)

        print(f"\n✅ Scan completato!")
        print(f"   Trovati {len(clients)} clienti con file\n")

        # Salva piano
        self.reorganization_plan = clients
        with open(OUTPUT_FILE, 'w') as f:
            json.dump({
                'total_clients': len(clients),
                'dry_run': self.dry_run,
                'clients': clients
            }, f, indent=2)

        print(f"💾 Piano salvato: {OUTPUT_FILE}\n")

        if self.dry_run:
            print("="*80)
            print("📋 PIANO DI RIORGANIZZAZIONE")
            print("="*80 + "\n")

            # Mostra primi 20 clienti
            print("Primi 20 clienti che verranno riorganizzati:\n")
            for i, client in enumerate(clients[:20], 1):
                print(f"{i:3}. {client['name']}")
                print(f"     Path originale: {client['path']}")
                print(f"     File: {len(client['files'])}")
                print()

            if len(clients) > 20:
                print(f"... e altri {len(clients) - 20} clienti\n")

            print("="*80)
            print("💡 PROSSIMI STEP")
            print("="*80 + "\n")
            print("Questo era un DRY RUN - nessuna modifica effettuata.\n")
            print("Per eseguire la riorganizzazione reale:")
            print("   python3 reorganize_gdrive.py --execute\n")
            print("⚠️  ATTENZIONE: L'esecuzione reale modificherà i file!")
            print("   Assicurati di avere un backup o di essere sicuro.\n")

        else:
            print("="*80)
            print("⚡ ESECUZIONE RIORGANIZZAZIONE")
            print("="*80 + "\n")

            for i, client in enumerate(clients, 1):
                print(f"[{i}/{len(clients)}] {client['name']} ({len(client['files'])} files)")
                files_moved = self.process_client(client)
                self.stats['files_moved'] += files_moved
                self.stats['clients_created'] += 1

            print("\n" + "="*80)
            print("✅ RIORGANIZZAZIONE COMPLETATA!")
            print("="*80 + "\n")
            print(f"Clienti processati: {self.stats['clients_created']}")
            print(f"File spostati:      {self.stats['files_moved']}")
            print(f"Errori:             {len(self.stats['errors'])}\n")


def main():
    # Check argument
    dry_run = '--execute' not in sys.argv

    if not dry_run:
        print("\n⚠️  ATTENZIONE: Stai per eseguire modifiche REALI!")
        print("Sei sicuro? (scrivi 'SI' per continuare): ")
        confirm = input().strip()
        if confirm != 'SI':
            print("Operazione annullata.")
            return

    engine = ReorganizationEngine(dry_run=dry_run)
    engine.run()


if __name__ == "__main__":
    main()
