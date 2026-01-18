#!/usr/bin/env python3
"""
CONTA CLIENTI SU GOOGLE DRIVE
Conta quanti clienti REALI hai già in DATA BS (escludendo cartelle lavoratori)
"""

from pathlib import Path

# Aggiungi path per Dropbox locale (per usare stesso filtro)
DROPBOX_PATH = Path("/sessions/upbeat-laughing-volta/mnt/antonellosiano/Dropbox")

# Cartelle lavoratori da escludere
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
    "Team Member",
    "Staff",
    "Employee",
}

# Cartelle utility da escludere
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
}

# Visa types e status (non sono clienti)
VISA_TYPES = {"ALTUS", "ITAS", "KITAP", "KITAS", "E-VISA", "VOA"}
STATUS_FOLDERS = {"Done", "On Proses", "Pending", "Rejected", "Cancelled"}


def is_client_folder(folder_name, parent_path_str):
    """
    Determina se una cartella è un cliente REALE
    """
    # Escludi lavoratori
    if folder_name in TEAM_FOLDERS:
        return False

    # Escludi utility
    if folder_name in UTILITY_FOLDERS:
        return False

    # Escludi visa types
    if folder_name in VISA_TYPES:
        return False

    # Escludi status
    if folder_name in STATUS_FOLDERS:
        return False

    # Se il parent è un lavoratore, skip
    parent_parts = parent_path_str.split("/")
    if any(part in TEAM_FOLDERS for part in parent_parts):
        return False

    # Se il parent è visa type o status, probabile cliente
    if any(part in VISA_TYPES for part in parent_parts):
        return True
    if any(part in STATUS_FOLDERS for part in parent_parts):
        return True

    # Default: considera cliente se non è nelle liste di esclusione
    return True


def count_dropbox_clients():
    """
    Conta clienti nei repository Dropbox locali
    """
    print("\n" + "=" * 80)
    print("📊 CONTA CLIENTI - DROPBOX vs GOOGLE DRIVE")
    print("=" * 80 + "\n")

    repositories = {
        "YANTI": DROPBOX_PATH / "BaliZero Repository" / "YANTI",
        "NOVI": DROPBOX_PATH / "BaliZero Repository" / "NOVI",
        "ADITYA": DROPBOX_PATH / "BaliZero Repository" / "ADITYA",
        "MEGI": DROPBOX_PATH / "BaliZero Repository" / "MEGI",
        "ANGEL": DROPBOX_PATH / "BaliZero Repository" / "ANGEL",
    }

    total_clients = 0
    repo_counts = {}

    print("🔍 Analisi Dropbox...")
    for repo_name, repo_path in repositories.items():
        if not repo_path.exists():
            print(f"   ❌ {repo_name}: Not found")
            continue

        # Conta cartelle che sembrano clienti
        client_count = 0

        # Esplora ricorsivamente
        for item in repo_path.rglob("*"):
            if item.is_dir():
                # Ottieni path relativo
                rel_path = str(item.relative_to(repo_path))

                if is_client_folder(item.name, rel_path):
                    # Verifica che contenga file (non sia cartella vuota)
                    has_files = (
                        any(f.is_file() for f in item.iterdir())
                        if item.exists()
                        else False
                    )
                    if has_files:
                        client_count += 1

        repo_counts[repo_name] = client_count
        total_clients += client_count
        print(f"   ✅ {repo_name}: {client_count:,} clienti")

    print(f"\n   📦 TOTALE DROPBOX: {total_clients:,} clienti\n")

    return total_clients, repo_counts


def estimate_gdrive_clients():
    """
    Stima quanti clienti potrebbero essere già su Google Drive
    Basato su quello che hai copiato in DATA BS
    """
    print("🔍 Stima Google Drive...")
    print("   (Questa è una STIMA - serve scan effettivo per numero preciso)\n")

    # Sappiamo che hai copiato alcune repository in DATA BS
    # Ma non sappiamo esattamente quanti clienti contengono
    print("   📂 DATA BS contiene:")
    print("      - ADITYA (copiato da Dropbox)")
    print("      - ANGEL (copiato da Dropbox)")
    print("      - DATA ADI")
    print("      - EXTEND VISA")
    print("      - MEGI (copiato da Dropbox)")
    print()
    print("   ❓ Per sapere il numero ESATTO, serve:")
    print("      1. OAuth2 authentication (browser login)")
    print("      2. Scan ricorsivo di DATA BS via API")
    print("      3. Filtrare cartelle lavoratori")
    print()


def main():
    """Main function"""
    try:
        # Conta Dropbox
        total_dropbox, repo_counts = count_dropbox_clients()

        # Stima Drive
        estimate_gdrive_clients()

        print("=" * 80)
        print("💡 RACCOMANDAZIONI")
        print("=" * 80 + "\n")

        print("📋 Opzione A: Riorganizza Google Drive")
        print("   - Se hai GIA' >50% dei clienti su Drive (>8,700)")
        print("   - Veloce: 1-2 ore per riorganizzare")
        print("   - Usa Google Drive API per MUOVERE file")
        print()

        print("📋 Opzione B: Upload da Dropbox")
        print(f"   - Upload tutti i {total_dropbox:,} clienti da Dropbox")
        print("   - Lento: 3-4 mesi per completare")
        print("   - Ma hai certezza di avere TUTTO")
        print()

        print("📋 Opzione C: Ibrido (CONSIGLIATO)")
        print("   - Prima: Conta ESATTAMENTE quanti clienti hai su Drive")
        print("   - Se >50%: Riorganizza Drive + integra mancanti")
        print("   - Se <50%: Upload completo da Dropbox")
        print()

        print("=" * 80)
        print("🎯 PROSSIMO STEP")
        print("=" * 80 + "\n")

        print("Per decidere la strategia migliore, devo:")
        print("1. ✅ Autenticarti con OAuth2 (browser)")
        print("2. ✅ Scannerizzare DATA BS su Google Drive")
        print("3. ✅ Contare clienti REALI (escludendo lavoratori)")
        print("4. ✅ Confrontare con Dropbox (17,400 clienti)")
        print()
        print("Vuoi procedere con lo scan di Google Drive? (y/n)")
        print()

    except Exception as e:
        print(f"\n❌ Errore: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
