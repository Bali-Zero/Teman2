#!/usr/bin/env python3
"""
Test rapido: estrae KBLI da 10 pagine per verificare che tutto funzioni.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add backend path
backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "apps", "backend-rag")
sys.path.insert(0, backend_path)
sys.path.insert(0, os.path.join(backend_path, "backend"))

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_path, ".env"))

from services.multimodal.pdf_vision_service import PDFVisionService

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LAMPIRAN_DIR = os.path.join(PROJECT_ROOT, "lampiran")

# Test su un file piccolo
TEST_FILE = "2.7 Lampiran I.G PP Nomor 28 Tahun 2025 (I.G.1-341).pdf"
TEST_PAGES = [1, 2, 3]  # Solo prime 3 pagine per test


async def test_extraction():
    """Test estrazione su poche pagine."""
    print("=" * 70)
    print("TEST ESTRAZIONE KBLI - 3 PAGINE")
    print("=" * 70)
    
    pdf_path = os.path.join(LAMPIRAN_DIR, TEST_FILE)
    
    if not os.path.exists(pdf_path):
        print(f"❌ File non trovato: {pdf_path}")
        return
    
    print(f"📄 File: {TEST_FILE}")
    print(f"📄 Pagine test: {TEST_PAGES}\n")
    
    # Inizializza Vision Service
    vision_service = PDFVisionService()
    
    if not vision_service._available:
        print("❌ Vision Service non disponibile!")
        return
    
    print("✅ Vision Service pronto\n")
    
    # Estrai da ogni pagina
    all_kbli = []
    
    for page_num in TEST_PAGES:
        print(f"📄 Processando pagina {page_num}...")
        
        prompt = """
        Analizza questa pagina del Lampiran I.G del PP 28/2025.
        
        La tabella ha 13 colonne. Estrai TUTTI i KBLI dalla tabella con queste informazioni:
        
        Per ogni riga della tabella che contiene un codice KBLI (5 cifre), estrai:
        - kode: Il codice KBLI (5 cifre)
        - judul: Il titolo/descrizione del KBLI
        - ruang_lingkup: L'ambito di applicazione/attività
        - skala_usaha: Array con le scale (Mikro, Kecil, Menengah, Besar)
        - tingkat_risiko: Il livello di rischio (Rendah, Menengah Rendah, Menengah, Menengah Tinggi, Tinggi)
        - pma_allowed: true se PMA è permesso, false se non permesso, null se non specificato
        - pma_max_percentage: La percentuale massima di PMA se presente
        
        Rispondi SOLO in formato JSON array:
        [
          {
            "kode": "01111",
            "judul": "Pertanian Jagung",
            "ruang_lingkup": "...",
            "skala_usaha": ["Mikro", "Kecil", "Menengah", "Besar"],
            "tingkat_risiko": "Rendah",
            "pma_allowed": true,
            "pma_max_percentage": "100%"
          }
        ]
        
        Se NON trovi tabelle con KBLI, rispondi: []
        """
        
        try:
            result = await vision_service.analyze_page(
                pdf_path, page_num, prompt=prompt, is_drive_file=False
            )
            
            print(f"  📝 Risultato (primi 200 caratteri): {result[:200]}...")
            
            # Prova estrarre JSON
            import re
            json_match = re.search(r'\[.*?\]', result, re.DOTALL)
            if json_match:
                try:
                    kbli_list = json.loads(json_match.group(0))
                    if isinstance(kbli_list, list):
                        print(f"  ✅ Estratti {len(kbli_list)} KBLI")
                        all_kbli.extend(kbli_list)
                    else:
                        print(f"  ⚠️  Risultato non è una lista")
                except json.JSONDecodeError as e:
                    print(f"  ⚠️  Errore parsing JSON: {e}")
            else:
                print(f"  ⚠️  Nessun JSON trovato nella risposta")
            
        except Exception as e:
            print(f"  ❌ Errore: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n📊 Totale KBLI estratti: {len(all_kbli)}")
    
    if all_kbli:
        print("\n📋 Esempi estratti:")
        for i, kbli in enumerate(all_kbli[:3], 1):
            print(f"\n  {i}. {kbli.get('kode', 'N/A')}: {kbli.get('judul', 'N/A')[:50]}")
            print(f"     Risk: {kbli.get('tingkat_risiko', 'N/A')}")
            print(f"     PMA: {kbli.get('pma_allowed', 'N/A')}, Max: {kbli.get('pma_max_percentage', 'N/A')}")
            print(f"     Skala: {kbli.get('skala_usaha', 'N/A')}")


if __name__ == "__main__":
    asyncio.run(test_extraction())
