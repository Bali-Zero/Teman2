#!/usr/bin/env python3
"""
PREPARAZIONE CLIENTI - VERSIONE 2
Approccio opposto: Prendo TUTTE le cartelle che contengono file,
POI escludo solo quelle che sono sicuramente NON clienti
"""

import sys
import shutil
from pathlib import Path

# Paths
DROPBOX_PATH = Path("/sessions/upbeat-laughing-volta/mnt/antonellosiano/Dropbox")
OUTPUT_PATH = Path.home() / "Desktop" / "CRM_PULITA"

# Repository
REPOSITORIES = {
    'YANTI': DROPBOX_PATH / 'YANTI',
    'NOVI': DROPBOX_PATH / 'NOVI',
    'ADITYA': DROPBOX_PATH / 'ADITYA',
    'MEGI': DROPBOX_PATH / 'MEGI',
    'ANGEL': DROPBOX_PATH / 'ANGEL'
}

# ESCLUSIONI - solo queste NON sono clienti
EXCLUDE_NAMES = {
    # Lavoratori
    'MAS ADIT', 'OM YOYOK', 'Om Oman', 'MAS ADI', 'OM FIRDA',
    'FIRDA', 'ARI', 'MAS YOYOK',
    # Utility
    'Bali Zero', 'Draft', 'Foto', 'BS', 'Backup', 'Archive',
    'Template', 'Test', 'Old', 'Downloads', '.DS_Store',
    # Categorie top-level
    'ALTUS', 'ITAS', 'KITAP', 'KITAS', 'E-VISA', 'VOA',
    'Done', 'On Proses', 'Pending', 'Rejected', 'Cancelled'
}


def should_exclude(path: Path, parent_path: str) -> bool:
    """Determina se ESCLUDERE una cartella"""
    name = path.name

    # Escludi nomi specifici
    if name in EXCLUDE_NAMES:
        return True

    # Escludi se contiene "titip"
    if 'titip' in name.lower():
        return True

    # Escludi se parent contiene esclusioni
    if any(excl in parent_path for excl in EXCLUDE_NAMES):
        return True

    # Escludi se parent contiene "titip"
    if 'titip' in parent_path.lower():
        return True

    # Escludi cartelle con nomi generici
    if name in ['New folder', 'Untitled', 'Temp', 'tmp']:
        return True

    return False


def find_all_client_folders(repo_path: Path, repo_name: str, min_depth=3, max_depth=6):
    """
    Trova TUTTE le cartelle con file a una certa profondità
    Min depth 3 = salta le categorie top-level
    """
    clients = {}

    print(f"   Scansione profondità {min_depth}-{max_depth}...")

    for item in repo_path.rglob('*'):
        if not item.is_dir():
            continue

        # Calcola profondità
        try:
            rel_path = item.relative_to(repo_path)
            depth = len(rel_path.parts)
        except:
            continue

        # Solo cartelle alla giusta profondità
        if depth < min_depth or depth > max_depth:
            continue

        # Check esclusioni
        parent_path = str(rel_path.parent) if rel_path.parent != Path('.') else ''

        if should_exclude(item, parent_path):
            continue

        # Verifica che contenga file (non sotto-cartelle)
        files = [f for f in item.iterdir() if f.is_file()]

        if len(files) >= 1:  # Almeno 1 file
            client_name = item.name

            # Gestisci duplicati
            original_name = client_name
            counter = 1
            while client_name in clients:
                counter += 1
                client_name = f"{original_name} ({repo_name}_{counter})"

            clients[client_name] = {
                'path': item,
                'repo': repo_name,
                'files': files,
                'depth': depth
            }

    return clients


def main():
    """Main"""
    print("\n" + "="*80)
    print("🚀 PREPARAZIONE CRM - APPROCCIO INCLUSIVO")
    print("="*80)

    print("\n📋 Strategia:")
    print("   - Prendo TUTTE le cartelle con file")
    print("   - Escludo solo lavoratori/utility/categorie")
    print("   - Profondità 3-6 (salta top-level)\n")

    all_clients = {}

    print("="*80)
    print("🔍 SCAN REPOSITORY")
    print("="*80 + "\n")

    for repo_name, repo_path in REPOSITORIES.items():
        if not repo_path.exists():
            print(f"❌ {repo_name}: non trovato\n")
            continue

        print(f"📂 {repo_name}...")
        clients = find_all_client_folders(repo_path, repo_name)
        all_clients.update(clients)

        print(f"   ✅ Trovati: {len(clients)} cartelle")
        print(f"   📊 Totale parziale: {len(all_clients)}\n")

    if not all_clients:
        print("❌ Nessuna cartella trovata!")
        return

    print(f"🎯 TOTALE: {len(all_clients)} cartelle con file\n")

    # Mostra sample
    print("="*80)
    print("📋 PRIMI 20 ESEMPI")
    print("="*80 + "\n")

    sorted_sample = sorted(list(all_clients.items())[:20], key=lambda x: x[0].lower())

    for name, data in sorted_sample:
        print(f"   {name:<50} ({len(data['files'])} file, depth={data['depth']})")

    print("\n" + "="*80)
    print("❓ VERIFICA")
    print("="*80 + "\n")

    print("Questi sembrano CLIENTI REALI?")
    print()
    print("Se SÌ → Procedo a copiare tutto")
    print("Se NO → Devo aggiustare i filtri")
    print()

    response = input("Procedo? (y/n): ").strip().lower()

    if response != 'y':
        print("\n⚠️  Operazione annullata")
        return

    # Crea struttura
    print("\n" + "="*80)
    print("📦 COPIA FILE")
    print("="*80 + "\n")

    if OUTPUT_PATH.exists():
        shutil.rmtree(OUTPUT_PATH)

    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

    total_files = 0
    sorted_clients = sorted(all_clients.items(), key=lambda x: x[0].lower())

    for i, (name, data) in enumerate(sorted_clients, 1):
        client_folder = OUTPUT_PATH / name
        client_folder.mkdir(exist_ok=True)

        for file_path in data['files']:
            try:
                dest = client_folder / file_path.name
                shutil.copy2(file_path, dest)
                total_files += 1
            except:
                pass

        if i % 50 == 0:
            print(f"   [{i}/{len(sorted_clients)}] {name}")

    print(f"\n✅ COMPLETATO!")
    print(f"   📂 Output: {OUTPUT_PATH}")
    print(f"   👥 Clienti: {len(sorted_clients)}")
    print(f"   📄 File: {total_files}\n")


if __name__ == "__main__":
    main()
