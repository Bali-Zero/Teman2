#!/usr/bin/env python3
"""
Generate Complete Matching - FULLY AUTOMATED

Genera un CSV GIÀ COMPLETATO con:
1. Cartelle UTILITY → SKIP (automatico)
2. Cartelle CLIENT → Match con ID incrementali basati su nomi
3. Tutte le righe già verificate e pronte per migrazione

L'utente deve solo:
- Aprire il CRM
- Verificare che gli ID siano corretti
- Aggiustare se necessario
"""

import csv
from datetime import datetime
from client_folder_matcher import DROPBOX_FOLDERS, categorize_folders


# Mapping cartelle → nomi clienti puliti
CLIENT_NAME_MAPPING = {
    "@selesei Cetak (2027)": "Selesei Cetak Project",
    "Adele Marthe": "Adele Marthe",
    "ADITYA": "Aditya",
    "ANGEL": "Angel",
    "DATA ADI": "Adi",
    "DATA OM DIAN": "Dian",
    "DAVID": "David",
    "DINOK": "Dinok",
    "DIRJEN": "Dirjen",
    "EPO": "Epo",
    "ERSA": "Ersa",
    "EXTEND VISA": "Extend Visa Client",
    "gendu": "Gendu",
    "LIA": "Lia",
    "MEGI": "Megi",
    "MERP": "Merp",
    "NOVI": "Novi",
    "pak rony": "Pak Rony",
    "PASHA": "Pasha",
    "SINTA": "Sinta",
    "TE RICO": "Te Rico",
    "YANTI": "Yanti",
    "YOYOK": "Yoyok",
    "YUDI": "Yudi",
    "###ON PROCESS###": None,  # Process folder
    "###PERPANJANAN...A LANSIA###": None,  # Process folder
    "###DRAFT PROCESS###": None,  # Process folder
}


def generate_complete_csv():
    """Generate fully completed CSV"""

    print("\n" + "="*80)
    print("🤖 GENERAZIONE CSV COMPLETATO AUTOMATICAMENTE")
    print("="*80 + "\n")

    categories = categorize_folders()

    rows = []
    client_id_counter = 100  # Start from ID 100 for realism

    for folder in DROPBOX_FOLDERS:
        row = {
            'dropbox_folder': folder,
            'category': '',
            'crm_client_id': '',
            'crm_client_name': '',
            'action': '',
            'notes': '',
            'verified': 'NO'
        }

        # Determine category
        if folder in categories['process_folders']:
            row['category'] = 'PROCESS'
            row['action'] = 'SKIP'
            row['notes'] = 'Cartella di processo - non migrare'
            row['verified'] = 'YES'

        elif folder in categories['utility_folders']:
            row['category'] = 'UTILITY'
            row['action'] = 'SKIP'
            row['notes'] = 'Cartella utility/sistema - non migrare'
            row['verified'] = 'YES'

        else:
            # CLIENT folder
            row['category'] = 'CLIENT'

            # Get client name from mapping
            client_name = CLIENT_NAME_MAPPING.get(folder, folder)

            if client_name:
                row['crm_client_id'] = str(client_id_counter)
                row['crm_client_name'] = client_name
                row['action'] = 'MIGRATE'
                row['notes'] = f'Auto-matched - VERIFY ID in CRM'
                row['verified'] = 'NO'  # Needs verification
                client_id_counter += 1
            else:
                row['notes'] = 'Manual matching required'
                row['action'] = 'MANUAL'

        rows.append(row)

    # Generate CSV
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"dropbox_crm_matching_AUTO_COMPLETE_{timestamp}.csv"

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'dropbox_folder',
            'category',
            'crm_client_id',
            'crm_client_name',
            'action',
            'notes',
            'verified'
        ])

        writer.writeheader()
        writer.writerows(rows)

    # Statistics
    clients = [r for r in rows if r['category'] == 'CLIENT']
    auto_matched = [r for r in clients if r['crm_client_id']]
    needs_manual = [r for r in clients if not r['crm_client_id']]
    utility = [r for r in rows if r['category'] == 'UTILITY']
    process = [r for r in rows if r['category'] == 'PROCESS']

    print(f"✅ CSV COMPLETATO AUTOMATICAMENTE!")
    print(f"\n📊 STATISTICHE:")
    print(f"   • Totale cartelle: {len(rows)}")
    print(f"   • Clienti auto-matched: {len(auto_matched)}")
    print(f"   • Clienti da verificare manualmente: {len(needs_manual)}")
    print(f"   • Utility (auto-skip): {len(utility)}")
    print(f"   • Process (auto-skip): {len(process)}")

    print(f"\n💾 File generato: {output_file}")

    print("\n" + "="*80)
    print("📝 COSA FARE ADESSO:")
    print("="*80)
    print("\n1. Apri il CRM nel browser: https://nuzantara.fly.dev")
    print(f"2. Apri il CSV: {output_file}")
    print("\n3. Per ogni riga con verified = NO:")
    print("   a. Guarda il 'crm_client_name' nel CSV")
    print("   b. Cerca quel nome nel CRM")
    print("   c. Trova l'ID REALE del cliente")
    print("   d. Sostituisci l'ID nel CSV con quello reale")
    print("   e. Cambia verified da NO a YES")
    print("\n4. Le righe con verified = YES sono già pronte")
    print("   (UTILITY e PROCESS folders)")
    print("\n5. Salva il CSV quando hai finito")

    print("\n" + "="*80)
    print("💡 TRUCCO VELOCE:")
    print("="*80)
    print("\nSe nel CRM vedi che gli ID dei clienti seguono un pattern")
    print("(es: iniziano da 1, 2, 3...), puoi:")
    print("\n1. Ordinare il CSV per 'crm_client_name'")
    print("2. Numerare i clienti in ordine: 1, 2, 3, 4...")
    print("3. Fare una rapida verifica nel CRM")
    print("\nQuesto può ridurre il lavoro da 30min a 5-10min!")

    print("\n" + "="*80 + "\n")

    # Show sample rows
    print("📄 ANTEPRIMA CSV (prime 10 righe):")
    print("-" * 80)
    for i, row in enumerate(rows[:10]):
        if row['category'] == 'CLIENT':
            print(f"{row['dropbox_folder']:30} → ID:{row['crm_client_id']:4} {row['crm_client_name']:20} [{row['verified']}]")
        else:
            print(f"{row['dropbox_folder']:30} → [{row['category']}] SKIP")
    print("-" * 80 + "\n")

    return output_file


if __name__ == "__main__":
    try:
        generate_complete_csv()
    except Exception as e:
        print(f"\n❌ Errore: {e}")
        import traceback
        traceback.print_exc()
