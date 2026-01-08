#!/usr/bin/env python3
"""
Verifica tutti i file Lampiran per confermare presenza di tabelle KBLI complete
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

# Tutti i file Lampiran da verificare
ALL_LAMPIRAN_FILES = [
    ("Lampiran I.F (parte 1)", "2.6e. Lampiran I.F PP Nomor 28 Tahun 2025 (I.F.2923-3680).pdf"),
    ("Lampiran I.F (parte 2)", "2.6f Lampiran I.F PP Nomor 28 Tahun 2025 (I.F.3681-4500).pdf"),
    ("Lampiran I.F (parte 3)", "2.6h Lampiran I.F PP Nomor 28 Tahun 2025 (I.F.5249-11000).pdf"),
    ("Lampiran I.G", "2.7 Lampiran I.G PP Nomor 28 Tahun 2025 (I.G.1-341).pdf"),
    ("Lampiran I.H", "2.8 Lampiran I.H PP Nomor 28 Tahun 2025 (I.H.1-515).pdf"),
    ("Lampiran I.I", "2.9 Lampiran I.I PP Nomor 28 Tahun 2025 (I.I.1-411).pdf"),
    ("Lampiran I.J-I.P", "2.10 Lampiran I.J sd. I.P PP Nomor 28 Tahun 2025.pdf"),
    ("Lampiran I.Q-I.V", "2.11 Lampiran I.Q sd. I.V PP Nomor 28 Tahun 2025.pdf"),
    ("Lampiran II", "PP Nomor 28 Tahun 2025 - Lampiran II.pdf"),
    ("Lampiran III", "PP Nomor 28 Tahun 2025 - Lampiran III.pdf"),
    ("Lampiran IV", "PP Nomor 28 Tahun 2025 - Lampiran IV.pdf"),
]


async def verify_lampiran_file(vision_service: PDFVisionService, lampiran_name: str, filename: str):
    """Verifica un file Lampiran per presenza di tabelle KBLI complete"""
    pdf_path = os.path.join(LAMPIRAN_DIR, filename)
    
    if not os.path.exists(pdf_path):
        print(f"  ❌ File non trovato: {filename}")
        return None
    
    import pypdf
    reader = pypdf.PdfReader(pdf_path)
    total_pages = len(reader.pages)
    
    print(f"\n{'='*70}")
    print(f"📄 {lampiran_name}")
    print(f"   File: {filename}")
    print(f"   Pagine totali: {total_pages}")
    print(f"{'='*70}")
    
    # Testa prime 3 pagine per capire struttura
    for page_num in [1, 2, 3]:
        if page_num > total_pages:
            break
            
        prompt = f"""
        Analizza questa pagina del {lampiran_name} del PP 28/2025.
        
        Verifica se contiene tabelle con queste informazioni:
        1. Codici KBLI (5 cifre, es: 01111, 01138, 01271)
        2. Colonne con "Tingkat Risiko" o "Risiko" (Rendah, Menengah Rendah, Menengah, Menengah Tinggi, Tinggi)
        3. Colonne con "PMA" o "Kepemilikan Asing"
        4. Colonne con "Skala Usaha" (Mikro, Kecil, Menengah, Besar)
        5. Colonne con "Judul KBLI" o descrizioni
        6. Colonne con "Ruang Lingkup"
        
        Rispondi con:
        - "TABELLA_KBLI_COMPLETA" se trovi tabelle con TUTTE queste informazioni
        - "TABELLA_KBLI_PARZIALE" se trovi tabelle KBLI ma mancano alcune colonne (specifica quali)
        - "TABELLA_PB_UMKU" se trovi tabelle di permessi commerciali (PB UMKU) ma non direttamente KBLI
        - "ALTRO" se trovi altro tipo di contenuto
        - "VUOTO" se la pagina è vuota o non contiene tabelle
        
        Poi descrivi brevemente cosa vedi.
        """
        
        try:
            result = await vision_service.analyze_page(
                pdf_path, page_num, prompt=prompt, is_drive_file=False
            )
            
            # Estrai tipo di contenuto
            content_type = "ALTRO"
            if "TABELLA_KBLI_COMPLETA" in result:
                content_type = "✅ TABELLA_KBLI_COMPLETA"
            elif "TABELLA_KBLI_PARZIALE" in result:
                content_type = "⚠️ TABELLA_KBLI_PARZIALE"
            elif "TABELLA_PB_UMKU" in result:
                content_type = "📋 TABELLA_PB_UMKU"
            elif "VUOTO" in result:
                content_type = "⚪ VUOTO"
            
            print(f"\n   Pagina {page_num}: {content_type}")
            
            # Mostra preview della descrizione
            desc_start = result.find("Poi descrivi") + len("Poi descrivi brevemente cosa vedi.")
            if desc_start > len("Poi descrivi"):
                desc = result[desc_start:desc_start+200].strip()
                if desc:
                    print(f"      {desc[:150]}...")
            
            # Se troviamo una tabella completa, fermiamoci qui per questo file
            if "TABELLA_KBLI_COMPLETA" in result:
                print(f"\n   ✅ CONFERMATO: Questo file contiene tabelle KBLI complete!")
                return {
                    "file": filename,
                    "lampiran": lampiran_name,
                    "pages": total_pages,
                    "has_kbli_tables": True,
                    "status": "complete"
                }
                
        except Exception as e:
            print(f"   ⚠️  Errore pagina {page_num}: {e}")
    
    # Se arriviamo qui, non abbiamo trovato tabelle KBLI complete nelle prime 3 pagine
    print(f"\n   ⚠️  Non confermato nelle prime 3 pagine")
    return {
        "file": filename,
        "lampiran": lampiran_name,
        "pages": total_pages,
        "has_kbli_tables": False,
        "status": "unknown"
    }


async def main():
    """Verifica tutti i file Lampiran"""
    print("=" * 70)
    print("VERIFICA COMPLETA TUTTI I FILE LAMPIRAN")
    print("=" * 70)
    
    vision_service = PDFVisionService()
    if not vision_service._available:
        print("❌ Vision service non disponibile. Verifica GOOGLE_API_KEY")
        return
    
    print("✅ Vision service pronto\n")
    
    results = []
    
    for lampiran_name, filename in ALL_LAMPIRAN_FILES:
        result = await verify_lampiran_file(vision_service, lampiran_name, filename)
        if result:
            results.append(result)
    
    # Riepilogo finale
    print(f"\n\n{'='*70}")
    print("RIEPILOGO VERIFICA")
    print(f"{'='*70}\n")
    
    kbli_complete = [r for r in results if r.get("has_kbli_tables")]
    kbli_partial = [r for r in results if r.get("status") == "partial"]
    pb_umku_only = [r for r in results if "Lampiran II" in r.get("lampiran", "")]
    unknown = [r for r in results if r.get("status") == "unknown"]
    
    print(f"✅ File con tabelle KBLI complete: {len(kbli_complete)}")
    for r in kbli_complete:
        print(f"   - {r['lampiran']} ({r['pages']} pagine)")
    
    if kbli_partial:
        print(f"\n⚠️  File con tabelle KBLI parziali: {len(kbli_partial)}")
        for r in kbli_partial:
            print(f"   - {r['lampiran']} ({r['pages']} pagine)")
    
    if pb_umku_only:
        print(f"\n📋 File con tabelle PB UMKU (permessi commerciali): {len(pb_umku_only)}")
        for r in pb_umku_only:
            print(f"   - {r['lampiran']} ({r['pages']} pagine)")
    
    if unknown:
        print(f"\n❓ File da verificare meglio: {len(unknown)}")
        for r in unknown:
            print(f"   - {r['lampiran']} ({r['pages']} pagine)")
    
    print(f"\n📊 Totale file verificati: {len(results)}")


if __name__ == "__main__":
    asyncio.run(main())
