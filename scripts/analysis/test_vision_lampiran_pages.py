#!/usr/bin/env python3
"""
Test Vision su pagine specifiche del Lampiran per verificare se riesce a estrarre tabelle KBLI
"""

import asyncio
import json
import os
import sys
import re

# Add backend path
backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "apps", "backend-rag")
sys.path.insert(0, backend_path)
sys.path.insert(0, os.path.join(backend_path, "backend"))

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_path, ".env"))

from services.multimodal.pdf_vision_service import PDFVisionService

PDF_PP28 = "/Users/antonellosiano/Desktop/PP_28_2025_JDIH_Kemenkeu.pdf"

# Pagine da testare (alcune pagine del Lampiran I e II)
TEST_PAGES = [10, 20, 30, 40, 50, 60, 70, 100, 150, 200, 250, 300]


async def test_vision_on_page(vision_service: PDFVisionService, page_num: int):
    """Test Vision su una pagina specifica"""
    prompt = """
    Analizza questa pagina del PP 28/2025.
    
    Cerca tabelle o liste che contengono:
    - Codici KBLI (5 cifre, es: 01111, 01138, 01271)
    - Informazioni su Tingkat Risiko (Rendah, Menengah, Tinggi)
    - Informazioni su PMA/Kepemilikan Asing
    - Informazioni su Skala Usaha
    
    Se trovi tabelle con codici KBLI, descrivi cosa vedi:
    - Quanti codici KBLI ci sono?
    - Come sono organizzati (tabella, lista, etc.)?
    - Ci sono informazioni su risk level, PMA, skala?
    
    Se NON vedi tabelle KBLI, descrivi cosa contiene questa pagina.
    """
    
    try:
        result = await vision_service.analyze_page(
            PDF_PP28, page_num, prompt=prompt, is_drive_file=False
        )
        return result
    except Exception as e:
        return f"Errore: {e}"


async def main():
    """Main test function"""
    print("=" * 60)
    print("TEST VISION SU PAGINE LAMPIRAN")
    print("=" * 60)
    
    vision_service = PDFVisionService()
    if not vision_service._available:
        print("❌ Vision service non disponibile")
        return
    
    print(f"\n📄 PDF: {PDF_PP28}")
    print(f"   Pagine da testare: {TEST_PAGES}\n")
    
    results = {}
    
    for page_num in TEST_PAGES:
        print(f"📄 Analizzando pagina {page_num}...")
        result = await test_vision_on_page(vision_service, page_num)
        results[page_num] = result
        
        # Mostra estratto
        if result:
            preview = result[:300].replace("\n", " ")
            print(f"   Preview: {preview}...")
            
            # Verifica se contiene riferimenti a KBLI
            if "kbli" in result.lower() or re.search(r'\d{5}', result):
                print(f"   ✅ Possibile contenuto KBLI trovato!")
        print()
    
    # Salva risultati
    output_file = "reports/vision_lampiran_test.json"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "test_pages": TEST_PAGES,
            "results": results
        }, f, indent=2, ensure_ascii=False)
    
    print(f"📁 Risultati salvati in: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
