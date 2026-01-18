#!/usr/bin/env python3
"""
PREPARAZIONE CRM - INDIVIDUAL vs COMPANY
Separa clienti individuali da aziende PT/CV
"""

import shutil
from pathlib import Path
import re

# Paths
DROPBOX_PATH = Path("/sessions/upbeat-laughing-volta/mnt/antonellosiano/Dropbox")
OUTPUT_PATH = Path.home() / "Desktop" / "CRM_PULITA"
INDIVIDUAL_PATH = OUTPUT_PATH / "INDIVIDUAL"
COMPANY_PATH = OUTPUT_PATH / "COMPANY"

# Repository
REPOSITORIES = {
    "YANTI": DROPBOX_PATH / "YANTI",
    "NOVI": DROPBOX_PATH / "NOVI",
    "ADITYA": DROPBOX_PATH / "ADITYA",
    "MEGI": DROPBOX_PATH / "MEGI",
    "ANGEL": DROPBOX_PATH / "ANGEL",
}

# Esclusioni - cartelle lavoratori (non sono clienti)
EXCLUDE_WORKERS = {
    "MAS ADIT",
    "OM YOYOK",
    "Om Oman",
    "MAS ADI",
    "OM FIRDA",
    "FIRDA",
    "ARI",
    "MAS YOYOK",
}

# Esclusioni - utility (non sono né persone né PT)
EXCLUDE_UTILITY = {
    "Bali Zero",
    "Draft",
    "Foto",
    "BS",
    "Backup",
    "Archive",
    "Template",
    "Test",
    "Old",
    "Downloads",
    ".DS_Store",
    "Epson",
    "Keygen",
    "Resetter",
    "Jamu",
}

# Categorie (non sono clienti, sono organizzatori)
EXCLUDE_CATEGORIES = {
    "ALTUS",
    "ITAS",
    "KITAP",
    "KITAS",
    "E-VISA",
    "VOA",
    "Done",
    "On Proses",
    "Pending",
    "Rejected",
    "Cancelled",
}

# Cartelle documenti (da includere nei file della PT)
DOC_FOLDERS = {
    "AKTA",
    "DOKUMEN",
    "OSS",
    "DOCUMENT",
    "NIB",
    "NPWP",
    "IMTA",
    "PERMOHONAN",
    "WAJIB LAPOR",
    "BUSINESS LICENSE",
    "LKPM",
    "VKBP",
    "DATA DUKUNG",
    "DOCS",
}


def is_company(name: str) -> bool:
    """Determina se è una company (PT/CV/PMA)"""
    name_upper = name.upper()

    # Check explicit markers
    if name_upper.startswith("PT ") or name_upper.startswith("PT."):
        return True
    if name_upper.startswith("CV ") or name_upper.startswith("CV."):
        return True
    if "PT " in name_upper or "PT." in name_upper:
        return True
    if "PMA" in name_upper:
        return True

    return False


def is_person(name: str) -> bool:
    """Determina se è una persona"""
    # Escludi cartelle documenti
    if name.upper() in DOC_FOLDERS:
        return False

    # Escludi date patterns
    if re.match(r"^\d{4}[\s-]?\d{4}", name):  # "20202021", "2020-2021"
        return False
    if re.match(r"^\d{8}$", name):  # "20252026"
        return False

    # Escludi range date tipo "JAN 19 JUL 19"
    if re.match(r"^[A-Z]{3}\s+\d{2}\s+[A-Z]{3}\s+\d{2}", name.upper()):
        return False

    # Escludi "New folder"
    if "new folder" in name.lower():
        return False

    # Escludi utility
    if name in EXCLUDE_UTILITY:
        return False

    # Check se ha pattern nome+cognome
    parts = name.split()

    # Almeno 2 parole (nome + cognome)
    if len(parts) >= 2:
        # Prima parola inizia con maiuscola
        if parts[0][0].isupper():
            return True

    return False


def should_exclude(name: str, parent_path: str) -> bool:
    """Determina se escludere completamente"""
    # Escludi lavoratori
    if name in EXCLUDE_WORKERS:
        return True

    # Escludi se contiene "titip"
    if "titip" in name.lower():
        return True

    # Escludi categorie
    if name in EXCLUDE_CATEGORIES:
        return True

    # Escludi se parent contiene lavoratori
    if any(worker in parent_path for worker in EXCLUDE_WORKERS):
        return True

    return False


def collect_all_files(folder: Path) -> list:
    """Raccoglie TUTTI i file dalla cartella e sottocartelle"""
    all_files = []

    for item in folder.rglob("*"):
        if item.is_file():
            all_files.append(item)

    return all_files


def find_all_clients():
    """Trova tutti i clienti (individual e company)"""
    print("\n" + "=" * 80)
    print("🔍 SCANSIONE DROPBOX")
    print("=" * 80 + "\n")

    individuals = {}
    companies = {}

    for repo_name, repo_path in REPOSITORIES.items():
        if not repo_path.exists():
            print(f"❌ {repo_name}: non trovato\n")
            continue

        print(f"📂 {repo_name}...")

        # Scan ricorsivo (profondità 3-6)
        for item in repo_path.rglob("*"):
            if not item.is_dir():
                continue

            try:
                rel_path = item.relative_to(repo_path)
                depth = len(rel_path.parts)
            except:
                continue

            # Solo profondità 3-6
            if depth < 3 or depth > 6:
                continue

            name = item.name
            parent_path = str(rel_path.parent)

            # Check esclusioni
            if should_exclude(name, parent_path):
                continue

            # Raccogli TUTTI i file (anche da sottocartelle)
            all_files = collect_all_files(item)

            if len(all_files) == 0:
                continue

            # Determina tipo
            if is_company(name):
                # È una company
                unique_name = name
                counter = 1
                while unique_name in companies:
                    counter += 1
                    unique_name = f"{name} ({counter})"

                companies[unique_name] = {
                    "path": item,
                    "repo": repo_name,
                    "files": all_files,
                }

            elif is_person(name):
                # È una persona
                unique_name = name
                counter = 1
                while unique_name in individuals:
                    counter += 1
                    unique_name = f"{name} ({counter})"

                individuals[unique_name] = {
                    "path": item,
                    "repo": repo_name,
                    "files": all_files,
                }

        print(
            f"   ✅ Individual: {len([i for i in individuals.values() if i['repo'] == repo_name])}"
        )
        print(
            f"   ✅ Company: {len([c for c in companies.values() if c['repo'] == repo_name])}\n"
        )

    print("🎯 TOTALE:")
    print(f"   👤 Individual: {len(individuals)}")
    print(f"   🏢 Company: {len(companies)}\n")

    return individuals, companies


def create_structure(individuals, companies):
    """Crea struttura finale"""
    print("=" * 80)
    print("📦 CREAZIONE STRUTTURA")
    print("=" * 80 + "\n")

    # Rimuovi output esistente
    if OUTPUT_PATH.exists():
        print("🗑️  Rimuovo output precedente...")
        shutil.rmtree(OUTPUT_PATH)

    # Crea cartelle
    INDIVIDUAL_PATH.mkdir(parents=True, exist_ok=True)
    COMPANY_PATH.mkdir(parents=True, exist_ok=True)

    print(f"📁 {INDIVIDUAL_PATH}")
    print(f"📁 {COMPANY_PATH}\n")

    total_files = 0

    # Copia INDIVIDUAL
    print(f"👤 Copia {len(individuals)} individual...")
    sorted_ind = sorted(individuals.items(), key=lambda x: x[0].lower())

    for i, (name, data) in enumerate(sorted_ind, 1):
        client_folder = INDIVIDUAL_PATH / name
        client_folder.mkdir(exist_ok=True)

        for file_path in data["files"]:
            try:
                dest = client_folder / file_path.name
                # Evita duplicati
                if dest.exists():
                    stem = file_path.stem
                    suffix = file_path.suffix
                    counter = 1
                    while dest.exists():
                        dest = client_folder / f"{stem}_{counter}{suffix}"
                        counter += 1
                shutil.copy2(file_path, dest)
                total_files += 1
            except:
                pass

        if i % 100 == 0:
            print(f"   [{i}/{len(sorted_ind)}]")

    print("   ✅ Individual completati\n")

    # Copia COMPANY
    print(f"🏢 Copia {len(companies)} companies...")
    sorted_comp = sorted(companies.items(), key=lambda x: x[0].lower())

    for i, (name, data) in enumerate(sorted_comp, 1):
        company_folder = COMPANY_PATH / name
        company_folder.mkdir(exist_ok=True)

        for file_path in data["files"]:
            try:
                dest = company_folder / file_path.name
                # Evita duplicati
                if dest.exists():
                    stem = file_path.stem
                    suffix = file_path.suffix
                    counter = 1
                    while dest.exists():
                        dest = company_folder / f"{stem}_{counter}{suffix}"
                        counter += 1
                shutil.copy2(file_path, dest)
                total_files += 1
            except:
                pass

        if i % 50 == 0:
            print(f"   [{i}/{len(sorted_comp)}]")

    print("   ✅ Companies completate\n")

    return total_files


def generate_report(individuals, companies, total_files):
    """Report finale"""
    print("=" * 80)
    print("📊 REPORT FINALE")
    print("=" * 80 + "\n")

    # Sample INDIVIDUAL
    print("👤 INDIVIDUAL - Primi 20:\n")
    sorted_ind = sorted(individuals.items(), key=lambda x: x[0].lower())
    for i, (name, data) in enumerate(sorted_ind[:20], 1):
        print(f"   {i:2}. {name:<50} ({len(data['files'])} file)")

    if len(sorted_ind) > 20:
        print(f"\n   ... e altri {len(sorted_ind) - 20} individual\n")

    # Sample COMPANY
    print("\n🏢 COMPANY - Primi 20:\n")
    sorted_comp = sorted(companies.items(), key=lambda x: x[0].lower())
    for i, (name, data) in enumerate(sorted_comp[:20], 1):
        print(f"   {i:2}. {name:<50} ({len(data['files'])} file)")

    if len(sorted_comp) > 20:
        print(f"\n   ... e altri {len(sorted_comp) - 20} companies\n")

    print("\n" + "=" * 80)
    print("✅ COMPLETATO!")
    print("=" * 80 + "\n")

    print(f"📂 Output: {OUTPUT_PATH}")
    print(f"👤 Individual: {len(individuals)}")
    print(f"🏢 Company: {len(companies)}")
    print(f"📄 File totali: {total_files}\n")

    print("=" * 80)
    print("🚀 PROSSIMI STEP")
    print("=" * 80 + "\n")
    print("1. Apri Finder:")
    print(f"   open {OUTPUT_PATH}")
    print()
    print("2. Verifica:")
    print("   - INDIVIDUAL/ contiene solo persone")
    print("   - COMPANY/ contiene solo PT/CV")
    print()
    print("3. Upload su Google Drive")
    print("   - Drag & drop cartelle INDIVIDUAL e COMPANY")
    print()


def main():
    """Main"""
    try:
        print("\n" + "=" * 80)
        print("🚀 PREPARAZIONE CRM - INDIVIDUAL vs COMPANY")
        print("=" * 80)

        # Trova clienti
        individuals, companies = find_all_clients()

        if not individuals and not companies:
            print("❌ Nessun cliente trovato!")
            return

        # Crea struttura
        total_files = create_structure(individuals, companies)

        # Report
        generate_report(individuals, companies, total_files)

    except KeyboardInterrupt:
        print("\n\n⚠️  Operazione interrotta")
    except Exception as e:
        print(f"\n❌ Errore: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
