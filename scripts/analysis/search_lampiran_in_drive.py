#!/usr/bin/env python3
"""
Cerca file Lampiran I, II, III, IV in Google Drive
"""

import os
import sys
import json
from typing import List, Dict

# Add backend path
backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "apps", "backend-rag")
sys.path.insert(0, backend_path)
sys.path.insert(0, os.path.join(backend_path, "backend"))

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_path, ".env"))

from services.oracle.smart_oracle import get_drive_service


def search_lampiran_files() -> List[Dict]:
    """Cerca file Lampiran in Google Drive"""
    service = get_drive_service()
    if not service:
        print("❌ Google Drive service non disponibile")
        print("   Verifica GOOGLE_CREDENTIALS_JSON")
        return []

    print("🔍 Cercando file Lampiran in Google Drive...\n")

    # Lista di pattern da cercare
    search_patterns = [
        "Lampiran I",
        "Lampiran II",
        "Lampiran III",
        "Lampiran IV",
        "Lampiran_I",
        "Lampiran_II",
        "Lampiran_III",
        "Lampiran_IV",
    ]

    all_files = []

    for pattern in search_patterns:
        print(f"  Cercando: {pattern}...")
        try:
            query = f"name contains '{pattern}' and mimeType = 'application/pdf' and trashed = false"
            
            results = (
                service.files()
                .list(
                    q=query,
                    fields="files(id, name, mimeType, size, modifiedTime, webViewLink)",
                    pageSize=50,
                )
                .execute()
            )

            files = results.get("files", [])
            if files:
                print(f"    ✅ Trovati {len(files)} file")
                for f in files:
                    print(f"      - {f['name']} (ID: {f['id']})")
                    all_files.append({
                        "id": f["id"],
                        "name": f["name"],
                        "size": f.get("size", 0),
                        "modifiedTime": f.get("modifiedTime"),
                        "webViewLink": f.get("webViewLink"),
                    })
            else:
                print(f"    ⏭️  Nessun file trovato")
        except Exception as e:
            print(f"    ❌ Errore: {e}")

    return all_files


def search_specific_lampiran_files() -> List[Dict]:
    """Cerca i file specifici Lampiran_I_A.pdf, etc."""
    service = get_drive_service()
    if not service:
        return []

    print("\n🔍 Cercando file specifici Lampiran_I_*.pdf...\n")

    # File specifici che lo script extract_kbli.py cerca
    specific_files = [
        "Lampiran_I_A.pdf",
        "Lampiran_I_B.pdf",
        "Lampiran_I_C.pdf",
        "Lampiran_I_D.pdf",
        "Lampiran_I_E.pdf",
        "Lampiran_I_F_1.pdf",
        "Lampiran_I_F_2.pdf",
        "Lampiran_I_F_3.pdf",
        "Lampiran_I_F_4.pdf",
        "Lampiran_I_F_5.pdf",
        "Lampiran_I_F_6.pdf",
        "Lampiran_I_F_7.pdf",
        "Lampiran_I_F_8.pdf",
        "Lampiran_I_G.pdf",
        "Lampiran_I_H.pdf",
        "Lampiran_I_I.pdf",
        "Lampiran_I_J_to_P.pdf",
        "Lampiran_I_Q_to_V.pdf",
        "Lampiran_II",
        "Lampiran_III",
        "Lampiran_IV",
    ]

    found_files = []

    for filename in specific_files:
        try:
            # Cerca esatto o contiene
            query = f"name contains '{filename.replace('.pdf', '')}' and mimeType = 'application/pdf' and trashed = false"
            
            results = (
                service.files()
                .list(
                    q=query,
                    fields="files(id, name, mimeType, size, modifiedTime, webViewLink)",
                    pageSize=5,
                )
                .execute()
            )

            files = results.get("files", [])
            if files:
                for f in files:
                    if filename.replace('.pdf', '') in f['name']:
                        print(f"  ✅ {f['name']} (ID: {f['id']})")
                        found_files.append({
                            "id": f["id"],
                            "name": f["name"],
                            "size": f.get("size", 0),
                            "modifiedTime": f.get("modifiedTime"),
                            "webViewLink": f.get("webViewLink"),
                        })
        except Exception as e:
            print(f"  ⚠️  Errore cercando {filename}: {e}")

    return found_files


def main():
    """Main search function"""
    print("=" * 60)
    print("RICERCA LAMPIRAN IN GOOGLE DRIVE")
    print("=" * 60)

    # Cerca pattern generali
    general_files = search_lampiran_files()

    # Cerca file specifici
    specific_files = search_specific_lampiran_files()

    # Combina risultati (rimuovi duplicati per ID)
    all_files = {}
    for f in general_files + specific_files:
        all_files[f["id"]] = f

    # Report finale
    print("\n" + "=" * 60)
    print("RISULTATI RICERCA")
    print("=" * 60)
    print(f"Totale file trovati: {len(all_files)}")

    if all_files:
        print("\n📋 File trovati:")
        for f in sorted(all_files.values(), key=lambda x: x["name"]):
            size_mb = f["size"] / (1024 * 1024) if f["size"] else 0
            print(f"  - {f['name']}")
            print(f"    ID: {f['id']}")
            print(f"    Dimensione: {size_mb:.2f} MB")
            if f.get("webViewLink"):
                print(f"    Link: {f['webViewLink']}")
            print()

        # Salva risultati
        output_file = "reports/lampiran_drive_search.json"
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "total_found": len(all_files),
                "files": list(all_files.values())
            }, f, indent=2, ensure_ascii=False)
        print(f"📁 Risultati salvati in: {output_file}")
    else:
        print("\n❌ Nessun file Lampiran trovato in Google Drive")
        print("\nPossibili cause:")
        print("  1. I file non sono stati caricati su Drive")
        print("  2. Il Service Account non ha accesso ai file")
        print("  3. I file hanno nomi diversi")


if __name__ == "__main__":
    main()
