#!/usr/bin/env python3
"""
Test per capire la struttura delle tabelle KBLI nei Lampiran I
"""

import asyncio
import os
import sys
from pathlib import Path

backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "apps", "backend-rag")
sys.path.insert(0, backend_path)
sys.path.insert(0, os.path.join(backend_path, "backend"))

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_path, ".env"))

from services.multimodal.pdf_vision_service import PDFVisionService

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LAMPIRAN_DIR = os.path.join(PROJECT_ROOT, "lampiran")

# File Lampiran I da testare
LAMPIRAN_I_FILES = {
    "I.F (parte 1)": "2.6e. Lampiran I.F PP Nomor 28 Tahun 2025 (I.F.2923-3680).pdf",
    "I.G": "2.7 Lampiran I.G PP Nomor 28 Tahun 2025 (I.G.1-341).pdf",
    "I.H": "2.8 Lampiran I.H PP Nomor 28 Tahun 2025 (I.H.1-515).pdf",
}


async def test_lampiran_i():
    vision_service = PDFVisionService()
    
    if not vision_service._available:
        print("❌ Vision service non disponibile")
        return
    
    print("🔍 Test struttura Lampiran I per trovare tabelle KBLI\n")
    
    for lampiran_name, filename in LAMPIRAN_I_FILES.items():
        pdf_path = os.path.join(LAMPIRAN_DIR, filename)
        
        if not os.path.exists(pdf_path):
            print(f"❌ File non trovato: {filename}")
            continue
        
        print(f"\n{'='*60}")
        print(f"LAMPIRAN {lampiran_name}: {filename}")
        print(f"{'='*60}\n")
        
        # Test prime 3 pagine
        for page_num in [1, 2, 3]:
            print(f"\n--- Pagina {page_num} ---")
            
            prompt = """
            Analizza questa pagina del Lampiran I del PP 28/2025.
            
            Cerca:
            1. Codici KBLI (5 cifre, es: 01111, 01138, 01271)
            2. Colonne con "Tingkat Risiko" o "Risiko" (Rendah, Menengah Rendah, Menengah, Menengah Tinggi, Tinggi)
            3. Colonne con "PMA" o "Kepemilikan Asing"
            4. Colonne con "Skala Usaha" (Mikro, Kecil, Menengah, Besar)
            
            Se trovi una tabella con questi elementi, descrivi:
            - Quante colonne ha?
            - Quali sono le intestazioni delle colonne?
            - Mostra un esempio di riga con un codice KBLI e i suoi valori
            
            Rispondi in modo dettagliato.
            """
            
            try:
                result = await vision_service.analyze_page(
                    pdf_path, page_num, prompt=prompt, is_drive_file=False
                )
                # Mostra primi 800 caratteri
                preview = result[:800] if len(result) > 800 else result
                print(preview)
                if len(result) > 800:
                    print("...")
                
                # Se trova KBLI, fermati qui per questo file
                if "01111" in result or "KBLI" in result.upper() or "risiko" in result.lower():
                    print(f"\n✅ Trovato contenuto KBLI nella pagina {page_num}!")
                    break
                    
            except Exception as e:
                print(f"❌ Errore pagina {page_num}: {e}")


if __name__ == "__main__":
    asyncio.run(test_lampiran_i())
