#!/usr/bin/env python3
"""
Estrae KBLI con risk level, PMA, skala dai Lampiran I usando Gemini Vision
Le tabelle hanno 13 colonne con Kode KBLI, Judul, Ruang Lingkup, Skala, Risk, PMA, ecc.
"""

import asyncio
import json
import os
import re
import sys
from datetime import datetime
from typing import Dict, List, Optional
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

# File Lampiran I da analizzare (in ordine)
LAMPIRAN_I_FILES = [
    ("I.F (parte 1)", "2.6e. Lampiran I.F PP Nomor 28 Tahun 2025 (I.F.2923-3680).pdf"),
    ("I.F (parte 2)", "2.6f Lampiran I.F PP Nomor 28 Tahun 2025 (I.F.3681-4500).pdf"),
    ("I.F (parte 3)", "2.6h Lampiran I.F PP Nomor 28 Tahun 2025 (I.F.5249-11000).pdf"),
    ("I.G", "2.7 Lampiran I.G PP Nomor 28 Tahun 2025 (I.G.1-341).pdf"),
    ("I.H", "2.8 Lampiran I.H PP Nomor 28 Tahun 2025 (I.H.1-515).pdf"),
    ("I.I", "2.9 Lampiran I.I PP Nomor 28 Tahun 2025 (I.I.1-411).pdf"),
    ("I.J-I.P", "2.10 Lampiran I.J sd. I.P PP Nomor 28 Tahun 2025.pdf"),
    ("I.Q-I.V", "2.11 Lampiran I.Q sd. I.V PP Nomor 28 Tahun 2025.pdf"),
]


async def extract_kbli_from_page(
    vision_service: PDFVisionService, pdf_path: str, page_num: int, lampiran_name: str
) -> List[Dict]:
    """
    Estrae KBLI da una pagina specifica usando Vision.
    Le tabelle hanno 13 colonne con: No, Kode KBLI, Judul KBLI, Ruang Lingkup, Skala, Risk, PMA, ecc.
    """
    prompt = f"""
    Analizza questa pagina del {lampiran_name} del PP 28/2025.
    
    La tabella ha 13 colonne. Estrai TUTTI i KBLI dalla tabella con queste informazioni:
    
    Per ogni riga della tabella che contiene un codice KBLI (5 cifre), estrai:
    - kode: Il codice KBLI (5 cifre, es: 01111, 01138, 01271)
    - judul: Il titolo/descrizione del KBLI
    - ruang_lingkup: L'ambito di applicazione/attività
    - skala_usaha: Array con le scale (Mikro, Kecil, Menengah, Besar) - può essere una colonna o più colonne
    - tingkat_risiko: Il livello di rischio (Rendah, Menengah Rendah, Menengah, Menengah Tinggi, Tinggi)
    - pma_allowed: true se PMA è permesso, false se non permesso, null se non specificato
    - pma_max_percentage: La percentuale massima di PMA se presente (es: "100%", "67%", null)
    - sektor: Il settore se presente nell'intestazione o nella pagina
    
    Rispondi SOLO in formato JSON array:
    [
      {{
        "kode": "01111",
        "judul": "Pertanian Jagung",
        "ruang_lingkup": "...",
        "skala_usaha": ["Mikro", "Kecil", "Menengah", "Besar"],
        "tingkat_risiko": "Rendah",
        "pma_allowed": true,
        "pma_max_percentage": "100%",
        "sektor": "..."
      }},
      ...
    ]
    
    Se NON trovi tabelle con KBLI, rispondi: []
    
    IMPORTANTE: Estrai TUTTE le righe della tabella, non solo alcune.
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
                            # Prova a pulire e riprovare
                            cleaned = result[json_start:json_end].replace('\n', ' ').replace('\r', '')
                            try:
                                kbli_list = json.loads(cleaned)
                                if isinstance(kbli_list, list):
                                    return kbli_list
                            except:
                                pass
    except Exception as e:
        print(f"    ⚠️  Errore pagina {page_num}: {e}")
    
    return []


async def extract_kbli_from_lampiran_file(
    vision_service: PDFVisionService, lampiran_name: str, filename: str, 
    start_page: int = 1, max_pages: Optional[int] = None
) -> List[Dict]:
    """
    Estrae KBLI da un file Lampiran I specifico.
    """
    pdf_path = os.path.join(LAMPIRAN_DIR, filename)
    
    if not os.path.exists(pdf_path):
        print(f"  ❌ File non trovato: {filename}")
        return []
    
    print(f"\n📄 Analizzando: {lampiran_name}")
    print(f"   File: {filename}")
    
    import pypdf
    reader = pypdf.PdfReader(pdf_path)
    total_pages = len(reader.pages)
    end_page = min(start_page + max_pages - 1, total_pages) if max_pages else total_pages
    pages_to_analyze = end_page - start_page + 1
    
    print(f"   Totale pagine: {total_pages}")
    print(f"   Analizzerò: pagine {start_page}-{end_page} ({pages_to_analyze} pagine)\n")
    
    all_kbli = []
    pages_with_data = 0
    
    for page_num in range(start_page, end_page + 1):
        if page_num % 5 == 0 or page_num == start_page:
            print(f"  📄 Pagina {page_num}/{end_page}...", end=" ", flush=True)
        
        kbli_list = await extract_kbli_from_page(
            vision_service, pdf_path, page_num, lampiran_name
        )
        
        if kbli_list:
            all_kbli.extend(kbli_list)
            pages_with_data += 1
            if page_num % 5 == 0 or page_num == start_page:
                print(f"✅ {len(kbli_list)} KBLI")
        else:
            if page_num % 5 == 0 or page_num == start_page:
                print("⏭️")
    
    print(f"\n  ✅ {lampiran_name}: {len(all_kbli)} KBLI totali da {pages_with_data} pagine")
    return all_kbli


async def main():
    """Main extraction function"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("=" * 60)
    print("ESTRAZIONE KBLI DA LAMPIRAN I CON GEMINI VISION")
    print("=" * 60)
    
    # Inizializza Vision Service
    print("\n🔧 Inizializzazione Vision Service...")
    vision_service = PDFVisionService()
    if not vision_service._available:
        print("❌ Vision service non disponibile. Verifica GOOGLE_API_KEY")
        return
    print("✅ Vision service pronto")
    
    print(f"\n📁 Directory Lampiran: {LAMPIRAN_DIR}")
    
    # Estrai da tutti i file Lampiran I
    all_kbli = {}
    all_kbli_list = []
    
    # Per test iniziale, inizia con prime 10 pagine di ogni file
    # Poi si può espandere a tutte le pagine
    print("\n🎯 Strategia: Estrazione da Lampiran I (prime 10 pagine per test)")
    print("   Poi si può espandere a tutte le pagine\n")
    
    for lampiran_name, filename in LAMPIRAN_I_FILES:
        kbli_list = await extract_kbli_from_lampiran_file(
            vision_service, lampiran_name, filename, start_page=1, max_pages=10
        )
        
        # Rimuovi duplicati e aggiungi
        for kbli in kbli_list:
            code = kbli.get("kode")
            if code and code not in all_kbli:
                all_kbli[code] = kbli
                all_kbli_list.append(kbli)
    
    # Salva risultati
    output_file = os.path.join(OUTPUT_DIR, "pp28_kbli_from_lampiran_i_vision.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "source": "PP 28/2025 Lampiran I (Vision extraction - prime 10 pagine per file)",
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
            print(f"   {i}. {code}: {kbli.get('judul', 'N/A')[:50]}")
            print(f"      Risk: {kbli.get('tingkat_risiko', 'N/A')}")
            print(f"      PMA: {kbli.get('pma_allowed', 'N/A')} ({kbli.get('pma_max_percentage', 'N/A')})")
            print(f"      Skala: {kbli.get('skala_usaha', [])}")
            print()
    else:
        print("\n⚠️  Nessun KBLI estratto. Verifica:")
        print("   - Il formato delle tabelle")
        print("   - Il prompt di estrazione")
        print("   - Le pagine analizzate")


if __name__ == "__main__":
    asyncio.run(main())
