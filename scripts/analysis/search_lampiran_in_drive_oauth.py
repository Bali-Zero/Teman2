#!/usr/bin/env python3
"""
Cerca file Lampiran I, II, III, IV in Google Drive usando OAuth (TeamDriveService)
"""

import asyncio
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

from services.integrations.team_drive_service import TeamDriveService


async def search_lampiran_files_oauth() -> List[Dict]:
    """Cerca file Lampiran in Google Drive usando OAuth"""
    drive = TeamDriveService()
    
    print("🔍 Cercando file Lampiran in Google Drive (OAuth)...\n")

    # Lista di pattern da cercare
    search_queries = [
        "Lampiran I",
        "Lampiran II", 
        "Lampiran III",
        "Lampiran IV",
        "Lampiran_I",
        "PP 28 2025",
        "PP28",
    ]

    all_files = {}

    for query in search_queries:
        print(f"  Cercando: '{query}'...")
        try:
            files = await drive.search_files(query=query, file_type="pdf", page_size=50)
            
            if files:
                print(f"    ✅ Trovati {len(files)} file")
                for f in files:
                    if "lampiran" in f["name"].lower() or "pp" in f["name"].lower():
                        file_id = f["id"]
                        if file_id not in all_files:
                            all_files[file_id] = {
                                "id": f["id"],
                                "name": f["name"],
                                "size": f.get("size", 0),
                                "modifiedTime": f.get("modifiedTime"),
                                "webViewLink": f.get("webViewLink"),
                            }
                            print(f"      - {f['name']}")
            else:
                print(f"    ⏭️  Nessun file trovato")
        except Exception as e:
            print(f"    ❌ Errore: {e}")

    return list(all_files.values())


async def main():
    """Main search function"""
    print("=" * 60)
    print("RICERCA LAMPIRAN IN GOOGLE DRIVE (OAuth)")
    print("=" * 60)

    files = await search_lampiran_files_oauth()

    # Report finale
    print("\n" + "=" * 60)
    print("RISULTATI RICERCA")
    print("=" * 60)
    print(f"Totale file trovati: {len(files)}")

    if files:
        print("\n📋 File trovati:")
        for f in sorted(files, key=lambda x: x["name"]):
            size_mb = f["size"] / (1024 * 1024) if f["size"] else 0
            print(f"  - {f['name']}")
            print(f"    ID: {f['id']}")
            print(f"    Dimensione: {size_mb:.2f} MB")
            if f.get("webViewLink"):
                print(f"    Link: {f['webViewLink']}")
            print()

        # Salva risultati
        output_file = "reports/lampiran_drive_search_oauth.json"
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "total_found": len(files),
                "files": files
            }, f, indent=2, ensure_ascii=False)
        print(f"📁 Risultati salvati in: {output_file}")
    else:
        print("\n❌ Nessun file Lampiran trovato in Google Drive")
        print("\nPossibili cause:")
        print("  1. I file non sono stati caricati su Drive")
        print("  2. OAuth non configurato correttamente")
        print("  3. I file hanno nomi diversi")
        print("  4. I file non sono condivisi con l'account OAuth")


if __name__ == "__main__":
    asyncio.run(main())
