#!/usr/bin/env python3
"""
Test veloce: estrae KBLI da 1 pagina per file Lampiran I
"""

import asyncio
import json
import os
import re
import sys

backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "apps", "backend-rag")
sys.path.insert(0, backend_path)
sys.path.insert(0, os.path.join(backend_path, "backend"))

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_path, ".env"))

from services.multimodal.pdf_vision_service import PDFVisionService

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LAMPIRAN_DIR = os.path.join(PROJECT_ROOT, "lampiran")

LAMPIRAN_I_FILES = [
    ("I.G", "2.7 Lampiran I.G PP Nomor 28 Tahun 2025 (I.G.1-341).pdf"),
]


async def extract_kbli_from_page(vision_service, pdf_path, page_num, lampiran_name):
    prompt = f"""
    Analizza questa pagina del {lampiran_name} del PP 28/2025.
    
    La tabella ha 13 colonne. Estrai TUTTI i KBLI dalla tabella con queste informazioni:
    
    Per ogni riga della tabella che contiene un codice KBLI (5 cifre), estrai:
    - kode: Il codice KBLI (5 cifre)
    - judul: Il titolo/descrizione del KBLI
    - ruang_lingkup: L'ambito di applicazione/attività
    - skala_usaha: Array con le scale (Mikro, Kecil, Menengah, Besar)
    - tingkat_risiko: Il livello di rischio (Rendah, Menengah Rendah, Menengah, Menengah Tinggi, Tinggi)
    - pma_allowed: true se PMA è permesso, false se non permesso, null se non specificato
    - pma_max_percentage: La percentuale massima di PMA se presente (es: "100%", "67%", null)
    
    Rispondi SOLO in formato JSON array:
    [
      {{
        "kode": "01111",
        "judul": "Pertanian Jagung",
        "ruang_lingkup": "...",
        "skala_usaha": ["Mikro", "Kecil", "Menengah", "Besar"],
        "tingkat_risiko": "Rendah",
        "pma_allowed": true,
        "pma_max_percentage": "100%"
      }}
    ]
    
    Se NON trovi tabelle con KBLI, rispondi: []
    """
    
    try:
        result = await vision_service.analyze_page(
            pdf_path, page_num, prompt=prompt, is_drive_file=False
        )
        
        if result:
            json_match = re.search(r'\[.*?\]', result, re.DOTALL)
            if json_match:
                try:
                    kbli_list = json.loads(json_match.group(0))
                    if isinstance(kbli_list, list):
                        return kbli_list
                except json.JSONDecodeError:
                    json_start = result.find("[")
                    json_end = result.rfind("]") + 1
                    if json_start >= 0 and json_end > json_start:
                        try:
                            return json.loads(result[json_start:json_end])
                        except:
                            pass
    except Exception as e:
        print(f"Errore: {e}")
    
    return []


async def main():
    print("=" * 60)
    print("TEST ESTRAZIONE KBLI DA 1 PAGINA LAMPIRAN I")
    print("=" * 60)
    
    vision_service = PDFVisionService()
    if not vision_service._available:
        print("❌ Vision service non disponibile")
        return
    
    print("✅ Vision service pronto\n")
    
    for lampiran_name, filename in LAMPIRAN_I_FILES:
        pdf_path = os.path.join(LAMPIRAN_DIR, filename)
        
        if not os.path.exists(pdf_path):
            print(f"❌ File non trovato: {filename}")
            continue
        
        print(f"📄 Analizzando: {lampiran_name} - Pagina 1")
        
        kbli_list = await extract_kbli_from_page(vision_service, pdf_path, 1, lampiran_name)
        
        print(f"\n✅ Trovati {len(kbli_list)} KBLI\n")
        
        if kbli_list:
            print("Primi 3 KBLI estratti:")
            for i, kbli in enumerate(kbli_list[:3], 1):
                print(f"\n{i}. {kbli.get('kode', 'N/A')}: {kbli.get('judul', 'N/A')[:60]}")
                print(f"   Risk: {kbli.get('tingkat_risiko', 'N/A')}")
                print(f"   PMA: {kbli.get('pma_allowed', 'N/A')} ({kbli.get('pma_max_percentage', 'N/A')})")
                print(f"   Skala: {kbli.get('skala_usaha', [])}")
            
            # Salva risultato
            output_file = os.path.join(PROJECT_ROOT, "reports", "kbli_extraction", "test_one_page_lampiran_i.json")
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(kbli_list, f, indent=2, ensure_ascii=False)
            print(f"\n📁 Salvato in: {output_file}")
        else:
            print("⚠️  Nessun KBLI estratto")


if __name__ == "__main__":
    asyncio.run(main())
