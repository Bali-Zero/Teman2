#!/usr/bin/env python3
"""
Completa le pagine rimanenti di Agent 1 (1254-1625).
Agent 1 si è fermato a pagina 440/813 (globale 1253).
"""

import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add backend path
backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "apps", "backend-rag")
sys.path.insert(0, backend_path)
sys.path.insert(0, os.path.join(backend_path, "backend"))

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_path, ".env"))

import fitz  # PyMuPDF
from services.multimodal.pdf_vision_service import PDFVisionService

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LAMPIRAN_DIR = os.path.join(PROJECT_ROOT, "lampiran")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "reports", "kbli_extraction")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# File Lampiran I
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


def get_all_pages() -> List[Tuple[str, str, int]]:
    """Restituisce lista di (lampiran_name, pdf_path, page_num) per tutte le pagine."""
    pages = []
    
    for lampiran_name, pdf_filename in LAMPIRAN_I_FILES:
        pdf_path = os.path.join(LAMPIRAN_DIR, pdf_filename)
        
        if not os.path.exists(pdf_path):
            print(f"⚠️  File non trovato: {pdf_path}")
            continue
        
        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            doc.close()
            
            for page_num in range(1, total_pages + 1):
                pages.append((lampiran_name, pdf_path, page_num))
        except Exception as e:
            print(f"❌ Errore apertura {pdf_path}: {e}")
    
    return pages


async def extract_kbli_from_page(
    vision_service: PDFVisionService, pdf_path: str, page_num: int, lampiran_name: str, agent_id: int
) -> List[Dict]:
    """Estrae KBLI da una pagina specifica usando Vision con retry logic."""
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
    
    # Retry logic con exponential backoff
    max_retries = 5
    base_delay = 2  # secondi
    result = None
    
    for attempt in range(max_retries):
        try:
            result = await vision_service.analyze_page(
                pdf_path, page_num, prompt=prompt, is_drive_file=False
            )
            break  # Successo, esci dal loop retry
        except Exception as e:
            error_str = str(e)
            if "503" in error_str or "UNAVAILABLE" in error_str or "overloaded" in error_str.lower():
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff: 2s, 4s, 8s, 16s, 32s
                    print(f"  [Agent 1] ⚠️  API overloaded pagina {page_num}, retry {attempt + 1}/{max_retries} dopo {delay}s...")
                    await asyncio.sleep(delay)
                    continue
                else:
                    print(f"  [Agent 1] ❌ Max retries raggiunto per pagina {page_num}")
                    return []
            else:
                # Altro tipo di errore, non retry
                print(f"  [Agent 1] ❌ Errore pagina {page_num}: {e}")
                return []
    
    if not result:
        return []
    
    # Parsing JSON dalla risposta
    kbli_list = []
    try:
        # Cerca JSON array nella risposta
        json_match = re.search(r'\[.*\]', result, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            # Pulisci possibili caratteri problematici
            json_str_clean = json_str.replace('\n', ' ').replace('\r', ' ')
            # Prova a parsare
            parsed = json.loads(json_str_clean)
            if isinstance(parsed, list):
                for obj in parsed:
                    if isinstance(obj, dict) and obj.get("kode"):
                        obj["source_page"] = page_num
                        obj["source_lampiran"] = lampiran_name
                        obj["source_file"] = os.path.basename(pdf_path)
                        kbli_list.append(obj)
        else:
            # Prova a parsare direttamente
            try:
                parsed = json.loads(result)
                if isinstance(parsed, list):
                    for obj in parsed:
                        if isinstance(obj, dict) and obj.get("kode"):
                            obj["source_page"] = page_num
                            obj["source_lampiran"] = lampiran_name
                            obj["source_file"] = os.path.basename(pdf_path)
                            kbli_list.append(obj)
            except:
                # Prova a estrarre oggetti JSON singoli
                obj_matches = re.findall(r'\{[^{}]*"kode"[^{}]*\}', result)
                for obj_str in obj_matches:
                    try:
                        obj_str_clean = obj_str.replace('\n', ' ').replace('\r', ' ')
                        obj = json.loads(obj_str_clean)
                        if obj.get("kode"):
                            obj["source_page"] = page_num
                            obj["source_lampiran"] = lampiran_name
                            obj["source_file"] = os.path.basename(pdf_path)
                            kbli_list.append(obj)
                    except:
                        pass
    except Exception as e:
        print(f"  [Agent 1] ⚠️  Errore parsing JSON pagina {page_num}: {e}")
    
    return kbli_list


async def main():
    """Main function"""
    print("=" * 70)
    print("COMPLETAMENTO AGENT 1 - PAGINE RIMANENTI")
    print("=" * 70)
    
    # Ottieni tutte le pagine
    print("\n📋 Scansione file Lampiran I...")
    all_pages = get_all_pages()
    print(f"\n📊 Totale pagine disponibili: {len(all_pages)}")
    
    # Agent 1 aveva pagine 813-1625, si è fermato a 1253
    agent1_start = 813
    agent1_end = 1625
    agent1_last_processed = 1253
    
    # Pagine rimanenti
    remaining_pages = all_pages[agent1_last_processed + 1:agent1_end + 1]
    
    print(f"\n📊 Pagine rimanenti Agent 1:")
    print(f"   Range: {agent1_last_processed + 1}-{agent1_end} ({len(remaining_pages)} pagine)")
    
    # Raggruppa per file
    files_to_process = {}
    for lampiran_name, pdf_path, page_num in remaining_pages:
        if pdf_path not in files_to_process:
            files_to_process[pdf_path] = []
        files_to_process[pdf_path].append((lampiran_name, page_num))
    
    print(f"\n📄 File da processare:")
    for pdf_path, page_list in files_to_process.items():
        page_nums = sorted(set([p[1] for p in page_list]))
        print(f"   {os.path.basename(pdf_path)}: {len(page_nums)} pagine ({min(page_nums)}-{max(page_nums)})")
    
    # Inizializza Vision Service
    print("\n🔧 Inizializzazione Vision Service...")
    vision_service = PDFVisionService()
    
    if not vision_service._available:
        print("❌ Vision Service non disponibile!")
        return
    
    print("✅ Vision Service pronto")
    
    # Risultati
    results = {}  # {kode: [kbli_entries]}
    processed = 0
    extracted = 0
    
    print(f"\n🚀 Inizio elaborazione {len(remaining_pages)} pagine...")
    
    for lampiran_name, pdf_path, page_num in remaining_pages:
        try:
            kbli_list = await extract_kbli_from_page(
                vision_service, pdf_path, page_num, lampiran_name, 1
            )
            
            if kbli_list:
                # Aggiungi ai risultati
                for kbli in kbli_list:
                    code = kbli.get("kode", "")
                    if code:
                        if code not in results:
                            results[code] = []
                        results[code].append(kbli)
                        extracted += 1
            
            processed += 1
            
            if processed % 10 == 0:
                msg = f"  [Agent 1] Processate {processed}/{len(remaining_pages)} pagine, estratti {extracted} KBLI"
                print(msg, flush=True)
            
            # Rate limiting
            await asyncio.sleep(1.0)
            
        except Exception as e:
            print(f"  [Agent 1] ❌ Errore pagina {page_num}: {e}")
            processed += 1
    
    print(f"\n✅ Agent 1 completato: {processed} pagine, {extracted} KBLI estratti")
    
    # Consolida risultati
    print("\n" + "=" * 70)
    print("CONSOLIDAMENTO RISULTATI")
    print("=" * 70)
    
    consolidated = {}
    for code, entries in results.items():
        # Prendi l'entry più completa
        best_entry = max(entries, key=lambda e: sum(1 for v in e.values() if v))
        consolidated[code] = best_entry
    
    print(f"✅ KBLI unici estratti: {len(consolidated)}")
    
    # Salva risultati
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(OUTPUT_DIR, f"kbli_complete_from_lampiran_agent1_remaining_{timestamp}.json")
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "source": "Lampiran I PP 28/2025 - Agent 1 Remaining Pages",
            "pages_processed": f"{agent1_last_processed + 1}-{agent1_end}",
            "total_pages_processed": len(remaining_pages),
            "total_kbli_extracted": len(consolidated),
            "total_extractions": extracted,
            "kbli_data": consolidated
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n📁 Risultati salvati in: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
