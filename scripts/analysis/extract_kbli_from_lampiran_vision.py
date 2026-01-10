#!/usr/bin/env python3
"""
Estrae KBLI con risk level, PMA, skala dai Lampiran del PP 28/2025 usando Gemini Vision
Analizza le pagine dei Lampiran I, II, III, IV per estrarre tabelle complete
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
PDF_PP28 = "/Users/antonellosiano/Desktop/PP_28_2025_JDIH_Kemenkeu.pdf"
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "reports", "kbli_extraction")

# Range pagine Lampiran (verificati dal PDF)
LAMPIRAN_RANGES = {
    "I": (9, 76),      # Lampiran I: pagine 9-76 (68 pagine)
    "II": (89, 383),   # Lampiran II: pagine 89-383 (295 pagine) - Probabilmente contiene tabelle KBLI principali
    "III": (77, 88),   # Lampiran III: pagine 77-88 (12 pagine)
}


async def extract_kbli_from_lampiran_page(
    vision_service: PDFVisionService, page_num: int, lampiran_num: str
) -> List[Dict]:
    """
    Estrae KBLI da una pagina specifica del Lampiran usando Vision.
    """
    prompt = f"""
    Analizza questa pagina del Lampiran {lampiran_num} del PP 28/2025.
    
    Cerca TUTTE le tabelle o liste che contengono:
    - Codici KBLI (5 cifre, es: 01111, 01138, 01271)
    - Tingkat Risiko (Rendah, Menengah Rendah, Menengah, Menengah Tinggi, Tinggi)
    - Kepemilikan Asing/PMA (Diizinkan/Tidak Diizinkan, percentuale massima)
    - Skala Usaha (Mikro, Kecil, Menengah, Besar)
    
    Estrai TUTTI i dati trovati in formato JSON array:
    [
      {{
        "kode": "01111",
        "judul": "...",
        "tingkat_risiko": "Rendah",
        "pma_allowed": true,
        "pma_max_percentage": "100%",
        "skala_usaha": ["Mikro", "Kecil", "Menengah", "Besar"]
      }},
      ...
    ]
    
    Se NON trovi tabelle con KBLI, rispondi: []
    """
    
    try:
        result = await vision_service.analyze_page(
            PDF_PP28, page_num, prompt=prompt, is_drive_file=False
        )
        
        # Estrai JSON dalla risposta
        if result:
            # Cerca array JSON
            json_match = re.search(r'\[.*?\]', result, re.DOTALL)
            if json_match:
                try:
                    kbli_list = json.loads(json_match.group(0))
                    if isinstance(kbli_list, list) and len(kbli_list) > 0:
                        return kbli_list
                except json.JSONDecodeError:
                    # Prova estrazione più ampia
                    json_start = result.find("[")
                    json_end = result.rfind("]") + 1
                    if json_start >= 0 and json_end > json_start:
                        try:
                            kbli_list = json.loads(result[json_start:json_end])
                            if isinstance(kbli_list, list):
                                return kbli_list
                        except json.JSONDecodeError:
                            pass
    except Exception as e:
        print(f"    ⚠️  Errore pagina {page_num}: {e}")
    
    return []


async def extract_kbli_from_lampiran(
    vision_service: PDFVisionService, lampiran_num: str, start_page: int, end_page: int
) -> List[Dict]:
    """
    Estrae tutti i KBLI da un Lampiran specifico.
    """
    print(f"\n📄 Lampiran {lampiran_num}: pagine {start_page}-{end_page}")
    
    all_kbli = []
    pages_with_data = 0
    
    # Analizza ogni pagina del Lampiran
    for page_num in range(start_page, min(end_page + 1, 400)):
        if page_num % 10 == 0:
            print(f"  📄 Pagina {page_num}/{end_page}...", end=" ", flush=True)
        
        kbli_list = await extract_kbli_from_lampiran_page(
            vision_service, page_num, lampiran_num
        )
        
        if kbli_list:
            all_kbli.extend(kbli_list)
            pages_with_data += 1
            print(f"✅ {len(kbli_list)} KBLI")
        else:
            if page_num % 10 == 0:
                print("⏭️")
    
    print(f"\n  ✅ Lampiran {lampiran_num}: {len(all_kbli)} KBLI totali da {pages_with_data} pagine")
    return all_kbli


async def main():
    """Main extraction function"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("=" * 60)
    print("ESTRAZIONE KBLI DA LAMPIRAN PP 28/2025 CON GEMINI VISION")
    print("=" * 60)
    
    # Inizializza Vision Service
    print("\n🔧 Inizializzazione Vision Service...")
    vision_service = PDFVisionService()
    if not vision_service._available:
        print("❌ Vision service non disponibile. Verifica GOOGLE_API_KEY")
        return
    print("✅ Vision service pronto")
    
    print(f"\n📄 PDF: {PDF_PP28}")
    print(f"   Esiste: {os.path.exists(PDF_PP28)}")
    
    # Estrai da ogni Lampiran
    # Inizia con Lampiran II che probabilmente contiene le tabelle KBLI principali
    # Limita a prime 50 pagine per test (89-139)
    all_kbli = {}
    
    print("\n🎯 Strategia: Inizia con Lampiran II (tabelle KBLI principali)")
    print("   Limita a prime 50 pagine per test veloce\n")
    
    # Test con Lampiran II prime 50 pagine
    test_start = 89
    test_end = min(139, 383)  # Prime 50 pagine di Lampiran II
    
    kbli_list = await extract_kbli_from_lampiran(
        vision_service, "II", test_start, test_end
    )
    
    # Rimuovi duplicati (mantieni il primo)
    for kbli in kbli_list:
        code = kbli.get("kode")
        if code and code not in all_kbli:
            all_kbli[code] = kbli
    
    # Salva risultati
    output_file = os.path.join(OUTPUT_DIR, "pp28_kbli_from_lampiran_vision.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "source": "PP 28/2025 Lampiran I-IV (Vision extraction)",
            "total_kbli": len(all_kbli),
            "kbli_codes": list(all_kbli.values())
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Estrazione completata!")
    print(f"   KBLI unici trovati: {len(all_kbli)}")
    print(f"📁 Salvato in: {output_file}")
    
    # Mostra alcuni esempi
    if all_kbli:
        print(f"\n📋 Primi 5 KBLI estratti:")
        for i, (code, kbli) in enumerate(list(all_kbli.items())[:5], 1):
            print(f"   {i}. {code}: {kbli.get('judul', 'N/A')}")
            print(f"      Risk: {kbli.get('tingkat_risiko', 'N/A')}")
            print(f"      PMA: {kbli.get('pma_allowed', 'N/A')}")
            print()


if __name__ == "__main__":
    asyncio.run(main())
