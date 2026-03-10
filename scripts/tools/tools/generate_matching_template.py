#!/usr/bin/env python3
"""
Generate Dropbox → CRM Matching Template

Crea un CSV template con le 37 cartelle Dropbox e suggerimenti basati su pattern.
L'utente può poi compilare manualmente i match o usarlo come base.
"""

import csv
from datetime import datetime
from client_folder_matcher import DROPBOX_FOLDERS, categorize_folders


def generate_template():
    """Generate CSV template for manual matching"""

    print("\n" + "=" * 80)
    print("📋 GENERAZIONE TEMPLATE MATCHING DROPBOX → CRM")
    print("=" * 80 + "\n")

    # Categorize folders
    categories = categorize_folders()

    print(f"📁 Cartelle Dropbox trovate: {len(DROPBOX_FOLDERS)}")
    print(f"   • Potenziali clienti: {len(categories['potential_clients'])}")
    print(f"   • Cartelle di processo: {len(categories['process_folders'])}")
    print(f"   • Cartelle utility: {len(categories['utility_folders'])}")
    print()

    # Generate timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file = f"dropbox_crm_matching_template_{timestamp}.csv"

    # Prepare data for CSV
    rows = []

    for folder in DROPBOX_FOLDERS:
        # Determine category
        if folder in categories["process_folders"]:
            category = "PROCESS"
            action = "SKIP"
            notes = "Cartella di processo - non migrare"
        elif folder in categories["utility_folders"]:
            category = "UTILITY"
            action = "SKIP"
            notes = "Cartella utility/sistema - non migrare"
        else:
            category = "CLIENT"
            action = "MANUAL"
            notes = "Cerca il cliente nel CRM e inserisci l'ID"

        rows.append(
            {
                "dropbox_folder": folder,
                "category": category,
                "crm_client_id": "",  # To be filled manually
                "crm_client_name": "",  # To be filled manually
                "action": action,
                "notes": notes,
                "verified": "NO",
            }
        )

    # Write CSV
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "dropbox_folder",
                "category",
                "crm_client_id",
                "crm_client_name",
                "action",
                "notes",
                "verified",
            ],
        )

        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ Template CSV generato: {csv_file}")
    print()
    print("=" * 80)
    print("📝 ISTRUZIONI PER LA COMPILAZIONE:")
    print("=" * 80)
    print()
    print("1. Apri il CSV con Excel/Numbers/Google Sheets")
    print()
    print("2. Per ogni riga con category = CLIENT:")
    print("   a. Cerca il cliente nel CRM (https://nuzantara.fly.dev)")
    print("   b. Copia l'ID del cliente")
    print("   c. Incolla nella colonna 'crm_client_id'")
    print("   d. Copia il nome completo del cliente")
    print("   e. Incolla nella colonna 'crm_client_name'")
    print("   f. Cambia 'action' da MANUAL a MIGRATE")
    print("   g. Cambia 'verified' da NO a YES")
    print()
    print("3. Per le righe con category = PROCESS o UTILITY:")
    print("   • Lascia action = SKIP")
    print("   • Queste cartelle NON saranno migrate")
    print()
    print("4. Colonna 'action' può essere:")
    print("   • MIGRATE = Cartella sarà migrata")
    print("   • SKIP = Cartella NON sarà migrata")
    print("   • MANUAL = Richiede intervento manuale")
    print()
    print("5. Usa la colonna 'notes' per annotazioni")
    print()
    print("6. Salva il CSV quando hai finito")
    print()
    print("=" * 80)
    print()
    print("💡 SUGGERIMENTI:")
    print()
    print("• Ordina per 'category' per lavorare per gruppi")
    print("• Usa il filtro per mostrare solo CLIENT")
    print("• Tieni aperta la pagina CRM in un'altra finestra")
    print("• Usa Ctrl+F nel CRM per cercare i nomi")
    print()
    print("=" * 80)
    print()

    # Print summary by category
    client_count = len([r for r in rows if r["category"] == "CLIENT"])
    process_count = len([r for r in rows if r["category"] == "PROCESS"])
    utility_count = len([r for r in rows if r["category"] == "UTILITY"])

    print("📊 RIEPILOGO:")
    print(f"   • Clienti da matchare manualmente: {client_count}")
    print(f"   • Cartelle processo (auto-skip): {process_count}")
    print(f"   • Cartelle utility (auto-skip): {utility_count}")
    print(f"   • TOTALE cartelle: {len(rows)}")
    print()
    print("=" * 80)
    print()


if __name__ == "__main__":
    try:
        generate_template()
    except Exception as e:
        print(f"\n❌ Errore: {e}")
        import traceback

        traceback.print_exc()
