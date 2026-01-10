#!/usr/bin/env python3
"""
Verifica se Lampiran II, III, IV contengono informazioni PMA o altre info mancanti
"""

import asyncio
import os
import sys

backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "apps", "backend-rag")
sys.path.insert(0, backend_path)
sys.path.insert(0, os.path.join(backend_path, "backend"))

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_path, ".env"))

from services.multimodal.pdf_vision_service import PDFVisionService

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LAMPIRAN_DIR = os.path.join(PROJECT_ROOT, "lampiran")

LAMPIRAN_OTHER = [
    ("Lampiran II", "PP Nomor 28 Tahun 2025 - Lampiran II.pdf"),
    ("Lampiran III", "PP Nomor 28 Tahun 2025 - Lampiran III.pdf"),
    ("Lampiran IV", "PP Nomor 28 Tahun 2025 - Lampiran IV.pdf"),
]


async def check_lampiran_for_pma(vision_service, lampiran_name, filename):
    pdf_path = os.path.join(LAMPIRAN_DIR, filename)
    
    if not os.path.exists(pdf_path):
        print(f"❌ File non trovato: {filename}")
        return
    
    import pypdf
    reader = pypdf.PdfReader(pdf_path)
    total_pages = len(reader.pages)
    
    print(f"\n{'='*70}")
    print(f"📄 {lampiran_name}")
    print(f"   Pagine: {total_pages}")
    print(f"{'='*70}")
    
    # Verifica prime 5 pagine
    for page_num in range(1, min(6, total_pages + 1)):
        prompt = f"""
        Analizza questa pagina del {lampiran_name} del PP 28/2025.
        
        Cerca:
        1. Informazioni su PMA (Penanaman Modal Asing) o Kepemilikan Asing
        2. Tabelle con codici KBLI e percentuali PMA
        3. Regole o restrizioni su investimenti stranieri
        4. Qualsiasi riferimento a "PMA", "Asing", "Foreign", percentuali come "100%", "67%", "49%"
        
        Descrivi cosa vedi in dettaglio. Se trovi informazioni PMA, evidenziale chiaramente.
        """
        
        try:
            result = await vision_service.analyze_page(
                pdf_path, page_num, prompt=prompt, is_drive_file=False
            )
            
            # Cerca riferimenti a PMA
            has_pma = any(keyword in result.upper() for keyword in ["PMA", "ASING", "FOREIGN", "100%", "67%", "49%"])
            
            status = "✅ TROVATO PMA" if has_pma else "⏭️ Nessun PMA"
            print(f"\n   Pagina {page_num}: {status}")
            
            if has_pma:
                # Estrai snippet rilevante
                result_lower = result.lower()
                pma_pos = result_lower.find("pma")
                if pma_pos >= 0:
                    snippet = result[max(0, pma_pos-100):pma_pos+300]
                    print(f"      {snippet[:200]}...")
                    print(f"\n   ✅ QUESTO FILE CONTIENE INFORMAZIONI PMA!")
                return True
                
        except Exception as e:
            print(f"   ⚠️  Errore pagina {page_num}: {e}")
    
    return False


async def main():
    print("=" * 70)
    print("VERIFICA INFORMAZIONI PMA IN LAMPIRAN II, III, IV")
    print("=" * 70)
    
    vision_service = PDFVisionService()
    if not vision_service._available:
        print("❌ Vision service non disponibile")
        return
    
    print("✅ Vision service pronto\n")
    
    for lampiran_name, filename in LAMPIRAN_OTHER:
        found = await check_lampiran_for_pma(vision_service, lampiran_name, filename)
        if found:
            print(f"\n🎯 {lampiran_name} contiene informazioni PMA!")


if __name__ == "__main__":
    asyncio.run(main())
