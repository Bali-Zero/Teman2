#!/usr/bin/env python3
"""
Estrae KBLI con risk level, PMA, skala dai file Lampiran separati usando Gemini Vision
Inizia con Lampiran II che probabilmente contiene le tabelle KBLI principali
"""

import asyncio
import json
import os
import re
import sys
from datetime import datetime
from typing import Dict, List
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
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "reports", "kbli_extraction")

# File Lampiran da analizzare (in ordine di priorità)
LAMPIRAN_FILES = {
    "Lampiran II": "PP Nomor 28 Tahun 2025 - Lampiran II.pdf",  # Probabilmente tabelle KBLI principali
    "Lampiran I.F (parte 1)": "2.6e. Lampiran I.F PP Nomor 28 Tahun 2025 (I.F.2923-3680).pdf",
    "Lampiran I.F (parte 2)": "2.6f Lampiran I.F PP Nomor 28 Tahun 2025 (I.F.3681-4500).pdf",
    "Lampiran I.F (parte 3)": "2.6h Lampiran I.F PP Nomor 28 Tahun 2025 (I.F.5249-11000).pdf",
}


async def extract_kbli_from_pdf_page(
    vision_service: PDFVisionService, pdf_path: str, page_num: int, lampiran_name: str
) -> List[Dict]:
    """
    Estrae KBLI da una pagina specifica usando Vision.
    """
    prompt = f"""
    Analizza questa pagina del {lampiran_name} del PP 28/2025.
    
    Cerca TUTTE le tabelle o liste che contengono:
    - Codici KBLI (5 cifre, es: 01111, 01138, 01271, 01272, 01273, 01279)
    - Tingkat Risiko (Rendah, Menengah Rendah, Menengah, Menengah Tinggi, Tinggi)
    - Kepemilikan Asing/PMA (Diizinkan/Tidak Diizinkan, percentuale massima se presente)
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
            pdf_path, page_num, prompt=prompt, is_drive_file=False
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


async def extract_kbli_from_lampiran_file(
    vision_service: PDFVisionService, filename: str, max_pages: int = 50
) -> List[Dict]:
    """
    Estrae KBLI da un file Lampiran specifico.
    Limita a max_pages per test iniziale.
    """
    pdf_path = os.path.join(LAMPIRAN_DIR, filename)
    
    if not os.path.exists(pdf_path):
        print(f"  ❌ File non trovato: {filename}")
        return []
    
    print(f"\n📄 Analizzando: {filename}")
    
    import pypdf
    reader = pypdf.PdfReader(pdf_path)
    total_pages = len(reader.pages)
    pages_to_analyze = min(max_pages, total_pages)
    
    print(f"   Totale pagine: {total_pages}")
    print(f"   Analizzerò: prime {pages_to_analyze} pagine\n")
    
    all_kbli = []
    pages_with_data = 0
    
    for page_num in range(1, pages_to_analyze + 1):
        if page_num % 10 == 0:
            print(f"  📄 Pagina {page_num}/{pages_to_analyze}...", end=" ", flush=True)
        
        kbli_list = await extract_kbli_from_pdf_page(
            vision_service, pdf_path, page_num, filename
        )
        
        if kbli_list:
            all_kbli.extend(kbli_list)
            pages_with_data += 1
            print(f"✅ {len(kbli_list)} KBLI")
        else:
            if page_num % 10 == 0:
                print("⏭️")
    
    print(f"\n  ✅ {filename}: {len(all_kbli)} KBLI totali da {pages_with_data} pagine")
    return all_kbli


async def main():
    """Main extraction function"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("=" * 60)
    print("ESTRAZIONE KBLI DA FILE LAMPIRAN CON GEMINI VISION")
    print("=" * 60)
    
    # Inizializza Vision Service
    print("\n🔧 Inizializzazione Vision Service...")
    vision_service = PDFVisionService()
    if not vision_service._available:
        print("❌ Vision service non disponibile. Verifica GOOGLE_API_KEY")
        return
    print("✅ Vision service pronto")
    
    print(f"\n📁 Directory Lampiran: {LAMPIRAN_DIR}")
    print(f"   Esiste: {os.path.exists(LAMPIRAN_DIR)}")
    
    # Estrai da Lampiran II (priorità)
    all_kbli = {}
    
    # Inizia con Lampiran II (prime 50 pagine per test)
    print("\n🎯 Strategia: Inizia con Lampiran II (tabelle KBLI principali)")
    print("   Limita a prime 50 pagine per test veloce\n")
    
    kbli_list = await extract_kbli_from_lampiran_file(
        vision_service, 
        LAMPIRAN_FILES["Lampiran II"],
        max_pages=50  # Limita per test
    )
    
    # Rimuovi duplicati
    for kbli in kbli_list:
        code = kbli.get("kode")
        if code and code not in all_kbli:
            all_kbli[code] = kbli
    
    # Salva risultati
    output_file = os.path.join(OUTPUT_DIR, "pp28_kbli_from_lampiran_ii_vision.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "source": "PP 28/2025 Lampiran II (Vision extraction - prime 50 pagine)",
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
            print(f"      Skala: {kbli.get('skala_usaha', [])}")
            print()
    else:
        print("\n⚠️  Nessun KBLI estratto. Le tabelle potrebbero essere:")
        print("   - In formato immagine/scansione non leggibile")
        print("   - In pagine successive (oltre le prime 50)")
        print("   - In altri file Lampiran")


if __name__ == "__main__":
    asyncio.run(main())
