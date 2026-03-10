#!/usr/bin/env python3
"""
PREPARAZIONE COMPLETA CLIENTI - STRUTTURA SEMPLICE
Estrae TUTTI i clienti da Dropbox e crea struttura pulita:
Cliente/
  ├── tutti_i_file.pdf
  └── ...
"""

import shutil
from pathlib import Path

# Paths
DROPBOX_PATH = Path("/sessions/upbeat-laughing-volta/mnt/antonellosiano/Dropbox")
OUTPUT_PATH = Path.home() / "Desktop" / "CRM_PULITA"

# Repository Dropbox
REPOSITORIES = {
    "YANTI": DROPBOX_PATH / "YANTI",
    "NOVI": DROPBOX_PATH / "NOVI",
    "ADITYA": DROPBOX_PATH / "ADITYA",
    "MEGI": DROPBOX_PATH / "MEGI",
    "ANGEL": DROPBOX_PATH / "ANGEL",
}

# Filtri - cartelle da ESCLUDERE (non sono clienti)
TEAM_FOLDERS = {
    "MAS ADIT",
    "OM YOYOK",
    "Om Oman",
    "MAS ADI",
    "OM FIRDA",
    "Titip Punya ARI FIRDA",
    "FIRDA",
    "ARI",
    "MAS YOYOK",
    "Titip Punya Rina",
    "Titip Punya Vino",
    "Titip Punya",
}

UTILITY_FOLDERS = {
    "Bali Zero",
    "Draft",
    "Foto",
    "BS",
    "Backup",
    "Archive",
    "Template",
    "Samples",
    "Test",
    "Old",
    "Downloads",
    ".DS_Store",
}

VISA_TYPES = {"ALTUS", "ITAS", "KITAP", "KITAS", "E-VISA", "VOA"}
STATUS_FOLDERS = {"Done", "On Proses", "Pending", "Rejected", "Cancelled"}


def is_client_folder(path: Path, parent_path: str) -> bool:
    """Determina se una cartella è un cliente"""
    name = path.name

    # Escludi lavoratori
    if name in TEAM_FOLDERS:
        return False

    # Escludi se contiene "titip"
    if "titip" in name.lower():
        return False

    # Escludi utility
    if name in UTILITY_FOLDERS:
        return False

    # Escludi visa types (sono categorie, non clienti)
    if name in VISA_TYPES:
        return False

    # Escludi status (sono categorie)
    if name in STATUS_FOLDERS:
        return False

    # Escludi se parent contiene lavoratori
    if any(worker in parent_path for worker in TEAM_FOLDERS):
        return False

    # Escludi se parent contiene "titip"
    if "titip" in parent_path.lower():
        return False

    # Se parent è status o visa type, PROBABILE cliente
    parent_parts = parent_path.split("/")
    if any(part in STATUS_FOLDERS for part in parent_parts):
        return True
    if any(part in VISA_TYPES for part in parent_parts):
        return True

    # Default: NO (per sicurezza, solo quelli in status/visa)
    return False


def find_all_clients():
    """Trova TUTTI i clienti in tutti i repository"""
    print("\n" + "=" * 80)
    print("🔍 RICERCA CLIENTI IN DROPBOX")
    print("=" * 80 + "\n")

    all_clients = {}
    total_found = 0

    for repo_name, repo_path in REPOSITORIES.items():
        if not repo_path.exists():
            print(f"❌ {repo_name}: non trovato")
            continue

        print(f"📂 Scansione {repo_name}...")

        # Scan ricorsivo
        for item in repo_path.rglob("*"):
            if item.is_dir():
                rel_path = str(item.relative_to(repo_path))

                if is_client_folder(item, rel_path):
                    # Verifica che contenga file
                    files = list(item.glob("*.*"))
                    if files:
                        client_name = item.name

                        # Gestisci duplicati (stesso nome in repo diversi)
                        if client_name in all_clients:
                            # Aggiungi suffisso repo
                            client_name = f"{client_name} ({repo_name})"

                        all_clients[client_name] = {
                            "path": item,
                            "repo": repo_name,
                            "files": files,
                        }
                        total_found += 1

                        if total_found % 100 == 0:
                            print(f"   Trovati {total_found} clienti...")

        print(
            f"   ✅ {repo_name}: {len([c for c in all_clients.values() if c['repo'] == repo_name])} clienti\n"
        )

    print(f"🎯 TOTALE: {len(all_clients)} clienti trovati\n")
    return all_clients


def create_clean_structure(clients):
    """Crea struttura pulita locale"""
    print("=" * 80)
    print("📦 CREAZIONE STRUTTURA PULITA")
    print("=" * 80 + "\n")

    # Rimuovi output esistente
    if OUTPUT_PATH.exists():
        print("🗑️  Rimuovo output precedente...")
        shutil.rmtree(OUTPUT_PATH)

    # Crea cartella principale
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    print(f"📁 Creata: {OUTPUT_PATH}\n")

    # Ordina clienti alfabeticamente
    sorted_clients = sorted(clients.items(), key=lambda x: x[0].lower())

    print(f"📋 Copio file per {len(sorted_clients)} clienti...\n")

    total_files = 0
    errors = []

    for i, (client_name, client_data) in enumerate(sorted_clients, 1):
        client_folder = OUTPUT_PATH / client_name
        client_folder.mkdir(exist_ok=True)

        # Copia tutti i file
        files_copied = 0
        for file_path in client_data["files"]:
            try:
                dest = client_folder / file_path.name
                shutil.copy2(file_path, dest)
                files_copied += 1
                total_files += 1
            except Exception as e:
                errors.append(f"{client_name}/{file_path.name}: {e}")

        if i % 100 == 0:
            print(f"   [{i}/{len(sorted_clients)}] {client_name} - {files_copied} file")

    print("\n✅ Completato!")
    print(f"   Clienti: {len(sorted_clients)}")
    print(f"   File copiati: {total_files}")

    if errors:
        print(f"   ⚠️  Errori: {len(errors)}")
        print("\nPrimi 10 errori:")
        for err in errors[:10]:
            print(f"   - {err}")

    return total_files, errors


def generate_report(clients, total_files, errors):
    """Genera report finale"""
    print("\n" + "=" * 80)
    print("📊 REPORT FINALE")
    print("=" * 80 + "\n")

    # Primi 30 clienti
    sorted_clients = sorted(clients.items(), key=lambda x: x[0].lower())

    print("Primi 30 clienti (alfabetico):\n")
    for i, (name, data) in enumerate(sorted_clients[:30], 1):
        print(f"{i:3}. {name:<50} ({len(data['files'])} file)")

    if len(sorted_clients) > 30:
        print(f"\n... e altri {len(sorted_clients) - 30} clienti")

    print("\n" + "=" * 80)
    print("✅ PREPARAZIONE COMPLETATA")
    print("=" * 80 + "\n")

    print(f"📂 Cartella output: {OUTPUT_PATH}")
    print(f"👥 Totale clienti: {len(clients)}")
    print(f"📄 Totale file: {total_files}")
    print(f"⚠️  Errori: {len(errors)}\n")

    print("=" * 80)
    print("🚀 PROSSIMO STEP")
    print("=" * 80 + "\n")

    print("1. ✅ Apri Finder:")
    print(f"     {OUTPUT_PATH}")
    print()
    print("2. ✅ Verifica la struttura:")
    print("     - Ogni cliente ha 1 cartella")
    print("     - Tutti i file sono dentro")
    print()
    print("3. ✅ Upload su Google Drive:")
    print(
        "     - Apri https://drive.google.com/drive/folders/1je2YOEzBf2APKDbAdaXo2MGIu4N5nAEl"
    )
    print("     - Drag & drop TUTTE le cartelle clienti")
    print("     - Aspetta upload (2-4 ore)")
    print()
    print("4. 🎉 FINE!")
    print()


def main():
    """Main function"""
    try:
        print("\n" + "=" * 80)
        print("🚀 PREPARAZIONE COMPLETA CRM - STRUTTURA SEMPLICE")
        print("=" * 80)

        # Trova clienti
        clients = find_all_clients()

        if not clients:
            print("❌ Nessun cliente trovato!")
            return

        # Crea struttura
        total_files, errors = create_clean_structure(clients)

        # Report
        generate_report(clients, total_files, errors)

    except KeyboardInterrupt:
        print("\n\n⚠️  Operazione interrotta dall'utente")
    except Exception as e:
        print(f"\n❌ Errore: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
