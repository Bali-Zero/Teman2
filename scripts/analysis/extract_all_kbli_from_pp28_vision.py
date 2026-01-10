#!/usr/bin/env python3
"""
Estrae TUTTI i KBLI dal PDF PP 28/2025 usando Gemini Vision
Analizza tutte le pagine per trovare tabelle con KBLI e i loro dati (risk, PMA, skala)
"""

import asyncio
import json
import os
import re
import sys
from datetime import datetime
from typing import Dict, List

# Add backend path
backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "apps", "backend-rag")
sys.path.insert(0, backend_path)
sys.path.insert(0, os.path.join(backend_path, "backend"))

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_path, ".env"))

from services.multimodal.pdf_vision_service import PDFVisionService

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PDF_PP28 = "/Users/antonellosiano/Desktop/PP Nomor 28 Tahun 2025 (1).pdf"
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "reports", "kbli_extraction")


async def extract_all_kbli_from_pdf(vision_service: PDFVisionService, max_pages: int = 100) -> List[Dict]:
    """
    Analizza tutte le pagine del PDF per estrarre KBLI con i loro dati.
    """
    prompt = """
    Analizza questa pagina del PP 28/2025.
    
    Cerca TUTTE le tabelle o liste che contengono codici KBLI (5 cifre) con:
    - Tingkat Risiko (Rendah, Menengah Rendah, Menengah, Menengah Tinggi, Tinggi)
    - Kepemilikan Asing (PMA) - Diizinkan/Tidak Diizinkan e percentuale massima
    - Skala Usaha (Mikro, Kecil, Menengah, Besar)
    
    Estrai TUTTI i KBLI trovati in formato JSON array:
    [
      {
        "kode": "01111",
        "judul": "...",
        "tingkat_risiko": "Rendah",
        "pma_allowed": true,
        "pma_max_percentage": "100%",
        "skala_usaha": ["Mikro", "Kecil", "Menengah", "Besar"]
      },
      ...
    ]
    
    Se NON trovi nessun KBLI, rispondi: []
    """
    
    all_kbli = []
    
    print(f"📄 Analizzando fino a {max_pages} pagine del PDF...")
    
    for page_num in range(1, max_pages + 1):
        try:
            print(f"  📄 Pagina {page_num}/{max_pages}...", end=" ", flush=True)
            result = await vision_service.analyze_page(
                PDF_PP28, page_num, prompt=prompt, is_drive_file=False
            )
            
            # Prova a estrarre JSON dalla risposta
            if result:
                # Cerca array JSON
                json_match = re.search(r'\[.*?\]', result, re.DOTALL)
                if json_match:
                    try:
                        page_kbli = json.loads(json_match.group(0))
                        if isinstance(page_kbli, list) and len(page_kbli) > 0:
                            all_kbli.extend(page_kbli)
                            print(f"✅ Trovati {len(page_kbli)} KBLI")
                        else:
                            print("⏭️  Nessun KBLI")
                    except json.JSONDecodeError:
                        print("⚠️  Errore parsing JSON")
                else:
                    print("⏭️  Nessun JSON trovato")
        except Exception as e:
            print(f"❌ Errore pagina {page_num}: {e}")
            continue
    
    return all_kbli


async def main():
    """Main extraction function"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("=" * 60)
    print("ESTRAZIONE KBLI DA PP 28/2025 CON GEMINI VISION")
    print("=" * 60)
    
    # Inizializza Vision Service
    print("\n🔧 Inizializzazione Vision Service...")
    vision_service = PDFVisionService()
    if not vision_service._available:
        print("❌ Vision service non disponibile. Verifica GOOGLE_API_KEY")
        return
    print("✅ Vision service pronto")
    
    # Estrai tutti i KBLI
    print(f"\n📄 PDF: {PDF_PP28}")
    print(f"   Esiste: {os.path.exists(PDF_PP28)}")
    
    kbli_list = await extract_all_kbli_from_pdf(vision_service, max_pages=50)  # Limita a 50 per test
    
    # Rimuovi duplicati (mantieni il primo)
    seen_codes = set()
    unique_kbli = []
    for kbli in kbli_list:
        code = kbli.get("kode")
        if code and code not in seen_codes:
            seen_codes.add(code)
            unique_kbli.append(kbli)
    
    # Salva risultati
    output_file = os.path.join(OUTPUT_DIR, "pp28_kbli_vision_extracted.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "total_kbli": len(unique_kbli),
            "kbli_codes": unique_kbli
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Estrazione completata!")
    print(f"   KBLI trovati: {len(unique_kbli)}")
    print(f"   Duplicati rimossi: {len(kbli_list) - len(unique_kbli)}")
    print(f"📁 Salvato in: {output_file}")
    
    # Mostra alcuni esempi
    if unique_kbli:
        print(f"\n📋 Primi 5 KBLI estratti:")
        for kbli in unique_kbli[:5]:
            print(f"   {kbli.get('kode')}: {kbli.get('judul', 'N/A')} - Risk: {kbli.get('tingkat_risiko', 'N/A')}")


if __name__ == "__main__":
    asyncio.run(main())
