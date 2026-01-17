#!/usr/bin/env python3
"""
RIORGANIZZAZIONE GOOGLE DRIVE - Service Account
Usa service account invece di OAuth per evitare problema browser
"""

import json
import sys
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build
from collections import defaultdict

# Config
SERVICE_ACCOUNT_FILE = Path(__file__).parent.parent / 'service-account-key.json'
SCOPES = ['https://www.googleapis.com/auth/drive']
FOLDER_ID = '1je2YOEzBf2APKDbAdaXo2MGIu4N5nAEl'  # CRM folder
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

# Keywords
PASSPORT_KEYWORDS = ['passport', 'paspor', 'pp', 'pasaporte']
COMPANY_KEYWORDS = ['pt', 'pma', 'cv', 'company', 'perusahaan', 'npwp', 'nib', 'akta', 'deed']


def is_client_folder(name, parent_path):
    """Determina se è una cartella cliente"""
    if name in CATEGORY_FOLDERS or name in TEAM_FOLDERS or name in UTILITY_FOLDERS:
        return False
    if 'titip' in name.lower() or name in VISA_TYPES or name in STATUS_FOLDERS:
        return False
    if any(worker in parent_path for worker in TEAM_FOLDERS) or 'titip' in parent_path.lower():
        return False

    parent_parts = parent_path.split('/')
    if any(part in STATUS_FOLDERS or part in VISA_TYPES for part in parent_parts):
        return True

    return True


def categorize_file(filename):
    """Categorizza file"""
    filename_lower = filename.lower()
    if any(kw in filename_lower for kw in PASSPORT_KEYWORDS):
        return '01_Passport'
    if any(kw in filename_lower for kw in COMPANY_KEYWORDS):
        return '02_Company'
    return '03_Other_Documents'


class ReorganizationEngine:
    def __init__(self, dry_run=True):
        self.dry_run = dry_run
        self.service = None
        self.stats = {'clients_found': 0, 'files_total': 0, 'errors': []}
        self.clients = []

    def authenticate(self):
        """Autentica con Service Account"""
        print("🔑 Autenticazione con Service Account...")

        if not SERVICE_ACCOUNT_FILE.exists():
            raise Exception(f"File service account non trovato: {SERVICE_ACCOUNT_FILE}")

        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)

        self.service = build('drive', 'v3', credentials=credentials)
        print("✅ Autenticato!\n")

    def scan_recursive(self, folder_id, path="", depth=0, max_depth=10):
        """Scan ricorsivo"""
        if depth > max_depth:
            return

        try:
            # Lista folders
            results = self.service.files().list(
                q=f"'{folder_id}' in parents and trashed=false and mimeType='application/vnd.google-apps.folder'",
                pageSize=1000,
                fields="files(id, name)",
                orderBy="name"
            ).execute()

            folders = results.get('files', [])

            for folder in folders:
                folder_name = folder['name']
                current_path = f"{path}/{folder_name}" if path else folder_name

                # Check se è cliente
                if is_client_folder(folder_name, path):
                    # Conta file
                    file_results = self.service.files().list(
                        q=f"'{folder['id']}' in parents and trashed=false",
                        pageSize=1000,
                        fields="files(id, name, mimeType)"
                    ).execute()

                    files = [f for f in file_results.get('files', [])
                            if f['mimeType'] != 'application/vnd.google-apps.folder']

                    if len(files) > 0:
                        self.clients.append({
                            'name': folder_name,
                            'id': folder['id'],
                            'path': current_path,
                            'file_count': len(files),
                            'files': files
                        })
                        self.stats['clients_found'] += 1
                        self.stats['files_total'] += len(files)

                        if self.stats['clients_found'] % 50 == 0:
                            print(f"   Trovati {self.stats['clients_found']} clienti, {self.stats['files_total']} file...")

                # Scan subfolder
                self.scan_recursive(folder['id'], current_path, depth + 1, max_depth)

        except Exception as e:
            error_msg = f"Errore scanning {path}: {e}"
            print(f"❌ {error_msg}")
            self.stats['errors'].append({'path': path, 'error': str(e)})

    def run(self):
        """Esegui scan"""
        mode = "🔍 DRY RUN" if self.dry_run else "⚠️  ESECUZIONE"

        print("\n" + "="*80)
        print(f"{mode} - RIORGANIZZAZIONE GOOGLE DRIVE")
        print("="*80 + "\n")

        try:
            # Autentica
            self.authenticate()

            # Scan
            print("🔍 Scansione completa CRM folder...")
            print("   Questo può richiedere 5-15 minuti...\n")

            self.scan_recursive(FOLDER_ID)

            print(f"\n✅ Scan completato!")
            print(f"   Clienti trovati: {self.stats['clients_found']}")
            print(f"   File totali:     {self.stats['files_total']}\n")

            # Ordina alfabeticamente
            self.clients.sort(key=lambda x: x['name'].lower())

            # Salva piano
            plan = {
                'total_clients': len(self.clients),
                'total_files': self.stats['files_total'],
                'dry_run': self.dry_run,
                'clients': self.clients,
                'errors': self.stats['errors']
            }

            with open(OUTPUT_FILE, 'w') as f:
                json.dump(plan, f, indent=2)

            print(f"💾 Piano salvato: {OUTPUT_FILE}\n")

            # Mostra risultati
            print("="*80)
            print("📋 RISULTATI SCAN")
            print("="*80 + "\n")

            print(f"TOTALE CLIENTI: {len(self.clients)}")
            print(f"TOTALE FILE:    {self.stats['files_total']}\n")

            # Mostra primi 30 clienti
            print("Primi 30 clienti (ordinati alfabeticamente):\n")
            for i, client in enumerate(self.clients[:30], 1):
                print(f"{i:3}. {client['name']:<40} ({client['file_count']:3} file)")

            if len(self.clients) > 30:
                print(f"\n... e altri {len(self.clients) - 30} clienti")

            # Errori
            if self.stats['errors']:
                print(f"\n⚠️  ERRORI: {len(self.stats['errors'])}")
                for err in self.stats['errors'][:5]:
                    print(f"   - {err['path']}: {err['error']}")

            print("\n" + "="*80)
            print("💡 PROSSIMI STEP")
            print("="*80 + "\n")

            if self.dry_run:
                print("Questo era un SCAN - nessuna modifica effettuata.\n")
                print("📋 Ora puoi:")
                print("1. Verificare la lista clienti nel file JSON")
                print("2. Decidere se procedere con riorganizzazione\n")
                print("⚠️  NOTA: La riorganizzazione richiede sviluppo aggiuntivo")
                print("   perché Service Account ha limitazioni sui permessi.\n")
                print("   Alternativa: Usa script manuale o MCP browser.\n")

        except Exception as e:
            print(f"\n❌ Errore fatale: {e}")
            import traceback
            traceback.print_exc()


def main():
    engine = ReorganizationEngine(dry_run=True)
    engine.run()


if __name__ == "__main__":
    main()
