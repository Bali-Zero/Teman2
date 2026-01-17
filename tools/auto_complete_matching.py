#!/usr/bin/env python3
"""
Auto-Complete Matching - Smart Pattern Recognition

Completa automaticamente il CSV usando pattern intelligenti e euristiche
basate sui nomi delle cartelle Dropbox.
"""

import csv
import re
from datetime import datetime
from pathlib import Path

# Lista clienti CRM conosciuti (da compilare con i dati reali)
# Questi sono esempi basati sulle cartelle Dropbox
KNOWN_CRM_CLIENTS = [
    {"id": 1, "name": "Adele Marthe", "aliases": ["adele", "marthe"]},
    {"id": 2, "name": "Aditya Pratama", "aliases": ["aditya"]},
    {"id": 3, "name": "Angel Christy", "aliases": ["angel"]},
    {"id": 4, "name": "David Wilson", "aliases": ["david"]},
    {"id": 5, "name": "Dinok Setiawan", "aliases": ["dinok"]},
    {"id": 6, "name": "Epo Kurniawan", "aliases": ["epo"]},
    {"id": 7, "name": "Ersa Mayanti", "aliases": ["ersa"]},
    {"id": 8, "name": "Gendu Hartono", "aliases": ["gendu"]},
    {"id": 9, "name": "Lia Amelia", "aliases": ["lia"]},
    {"id": 10, "name": "Megi Susanti", "aliases": ["megi"]},
    {"id": 11, "name": "Merp Trading Co", "aliases": ["merp"]},
    {"id": 12, "name": "Novi Kusuma", "aliases": ["novi"]},
    {"id": 13, "name": "Yanti Sari", "aliases": ["yanti"]},
    {"id": 14, "name": "Yoyok Widodo", "aliases": ["yoyok"]},
    {"id": 15, "name": "Yudi Setiawan", "aliases": ["yudi"]},
]


def normalize_name(name: str) -> str:
    """Normalize name for comparison"""
    # Remove special characters, convert to lowercase
    normalized = re.sub(r'[^a-z0-9\s]', '', name.lower())
    # Remove extra spaces
    normalized = ' '.join(normalized.split())
    return normalized


def find_best_match(folder_name: str, crm_clients: list) -> tuple:
    """
    Find best CRM client match for a Dropbox folder
    Returns (client_id, client_name, confidence_score)
    """
    folder_normalized = normalize_name(folder_name)

    best_match = None
    best_score = 0

    for client in crm_clients:
        # Check exact match with name
        if normalize_name(client['name']) == folder_normalized:
            return (client['id'], client['name'], 1.0)

        # Check aliases
        for alias in client['aliases']:
            if alias.lower() in folder_normalized:
                score = 0.9
                if len(alias) > 3:  # Longer aliases = higher confidence
                    score = 0.95
                if score > best_score:
                    best_score = score
                    best_match = client

        # Check if folder name contains client name words
        client_words = normalize_name(client['name']).split()
        folder_words = folder_normalized.split()

        matching_words = set(client_words) & set(folder_words)
        if matching_words:
            score = len(matching_words) / max(len(client_words), 1)
            if score > best_score:
                best_score = score
                best_match = client

    if best_match and best_score >= 0.7:
        return (best_match['id'], best_match['name'], best_score)

    return (None, None, 0.0)


def auto_complete_csv(template_file: str):
    """Auto-complete the CSV template with smart matching"""

    print("\n" + "="*80)
    print("🤖 AUTO-COMPLETE MATCHING CON PATTERN RECOGNITION")
    print("="*80 + "\n")

    # Read template
    if not Path(template_file).exists():
        print(f"❌ File non trovato: {template_file}")
        return

    rows = []
    with open(template_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"📊 Righe da processare: {len(rows)}\n")

    # Process each row
    completed = 0
    high_confidence = 0
    medium_confidence = 0
    needs_manual = 0

    for row in rows:
        folder = row['dropbox_folder']
        category = row['category']

        if category != 'CLIENT':
            # Skip non-client folders
            continue

        # Try to find match
        client_id, client_name, score = find_best_match(folder, KNOWN_CRM_CLIENTS)

        if client_id:
            row['crm_client_id'] = str(client_id)
            row['crm_client_name'] = client_name

            if score >= 0.9:
                row['action'] = 'MIGRATE'
                row['verified'] = 'YES'
                row['notes'] = f'Auto-matched (confidence: {score:.0%})'
                high_confidence += 1
                completed += 1
                print(f"✅ {folder:30} → {client_name:30} ({score:.0%})")
            else:
                row['action'] = 'MANUAL'
                row['verified'] = 'NO'
                row['notes'] = f'Medium confidence ({score:.0%}) - verify manually'
                medium_confidence += 1
                print(f"⚠️  {folder:30} → {client_name:30} ({score:.0%}) NEEDS REVIEW")
        else:
            needs_manual += 1
            print(f"❌ {folder:30} → NO MATCH - manual required")

    # Save completed CSV
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"dropbox_crm_matching_completed_{timestamp}.csv"

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = rows[0].keys() if rows else []
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("\n" + "="*80)
    print("📊 RIEPILOGO AUTO-COMPLETION")
    print("="*80)
    print(f"\n✅ Match automatici (alta confidenza ≥90%): {high_confidence}")
    print(f"⚠️  Match da verificare (media confidenza 70-89%): {medium_confidence}")
    print(f"❌ Richiedono matching manuale: {needs_manual}")
    print(f"\n📁 Totale righe processate: {len([r for r in rows if r['category'] == 'CLIENT'])}")
    print(f"\n💾 File salvato: {output_file}")

    print("\n" + "="*80)
    print("✅ PROSSIMI PASSI:")
    print("="*80)
    print(f"\n1. Apri il file: {output_file}")
    print(f"2. Verifica le {medium_confidence} righe con 'verified = NO'")
    print(f"3. Compila manualmente le {needs_manual} righe senza match")
    print(f"4. Salva il CSV finale")
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    import sys

    # Find most recent template
    import glob
    templates = glob.glob("dropbox_crm_matching_template_*.csv")

    if not templates:
        print("❌ Nessun template trovato!")
        print("Esegui prima: python3 generate_matching_template.py")
        sys.exit(1)

    # Use most recent template
    latest_template = sorted(templates)[-1]
    print(f"📂 Usando template: {latest_template}\n")

    auto_complete_csv(latest_template)
