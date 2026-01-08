#!/usr/bin/env python3
"""
Estrae TUTTI i KBLI da TUTTI i Lampiran I usando 20 agenti paralleli.
Processa tutte le 4837 pagine per totale copertura.
"""

import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

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

# Numero di agenti paralleli (ridotto per evitare rate limits)
NUM_AGENTS = 5  # Ridotto da 20 a 5 per evitare sovraccarico API

# File Lampiran I da analizzare (solo quelli con tabelle KBLI)
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
    """
    Restituisce lista di (lampiran_name, pdf_path, page_num) per tutte le pagine.
    """
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
            
            print(f"✅ {lampiran_name}: {total_pages} pagine")
        except Exception as e:
            print(f"❌ Errore apertura {pdf_path}: {e}")
    
    return pages


def split_pages_among_agents(pages: List[Tuple], num_agents: int) -> List[List[Tuple]]:
    """
    Divide le pagine tra gli agenti.
    """
    chunks = [[] for _ in range(num_agents)]
    
    for i, page in enumerate(pages):
        agent_idx = i % num_agents
        chunks[agent_idx].append(page)
    
    return chunks


async def extract_kbli_from_page(
    vision_service: PDFVisionService, pdf_path: str, page_num: int, lampiran_name: str, agent_id: int
) -> List[Dict]:
    """
    Estrae KBLI da una pagina specifica usando Vision con retry logic.
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
                    print(f"  [Agent {agent_id}] ⚠️  API overloaded pagina {page_num}, retry {attempt + 1}/{max_retries} dopo {delay}s...")
                    await asyncio.sleep(delay)
                    continue
                else:
                    print(f"  [Agent {agent_id}] ❌ Max retries raggiunto per pagina {page_num}")
                    return []
            else:
                # Altro tipo di errore, non retry
                print(f"  [Agent {agent_id}] ❌ Errore pagina {page_num}: {e}")
                return []
    
    if not result:
        return []
    
    # Estrai JSON dalla risposta
    try:
        # Rimuovi markdown code blocks se presenti
        result_clean = result
        if "```json" in result:
            result_clean = re.sub(r'```json\s*', '', result)
            result_clean = re.sub(r'```\s*$', '', result_clean, flags=re.MULTILINE)
        elif "```" in result:
            result_clean = re.sub(r'```[a-z]*\s*', '', result)
            result_clean = re.sub(r'```\s*$', '', result_clean, flags=re.MULTILINE)
        
        # Cerca array JSON (con matching più robusto)
        json_match = re.search(r'\[[\s\S]*?\]', result_clean, re.DOTALL)
        if json_match:
            try:
                json_str = json_match.group(0)
                # Prova a fixare JSON comune
                json_str = json_str.replace("'", '"')  # Single to double quotes
                json_str = re.sub(r',\s*}', '}', json_str)  # Remove trailing commas
                json_str = re.sub(r',\s*]', ']', json_str)  # Remove trailing commas
                
                kbli_list = json.loads(json_str)
                if isinstance(kbli_list, list) and len(kbli_list) > 0:
                    # Aggiungi metadati
                    for kbli in kbli_list:
                        kbli["source_page"] = page_num
                        kbli["source_lampiran"] = lampiran_name
                        kbli["source_file"] = os.path.basename(pdf_path)
                    return kbli_list
            except json.JSONDecodeError as e:
                # Prova estrazione più ampia: cerca singoli oggetti JSON
                try:
                    json_objects = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', result_clean, re.DOTALL)
                    if json_objects:
                        kbli_list = []
                        for obj_str in json_objects:
                            if '"kode"' in obj_str or "'kode'" in obj_str:
                                try:
                                    obj_str_clean = obj_str.replace("'", '"')
                                    obj = json.loads(obj_str_clean)
                                    if obj.get("kode"):
                                        obj["source_page"] = page_num
                                        obj["source_lampiran"] = lampiran_name
                                        obj["source_file"] = os.path.basename(pdf_path)
                                        kbli_list.append(obj)
                                except:
                                    pass
                        if kbli_list:
                            return kbli_list
                except:
                    pass
    except Exception as e:
        print(f"  [Agent {agent_id}] ⚠️  Errore parsing JSON pagina {page_num}: {e}")
    
    return []


async def agent_worker(
    agent_id: int,
    pages: List[Tuple[str, str, int]],
    vision_service: PDFVisionService,
    results: Dict[str, List],
    progress: Dict[str, int]
):
    """
    Worker per un agente: processa le sue pagine assegnate.
    """
    msg = f"🤖 Agent {agent_id} iniziato: {len(pages)} pagine"
    print(msg, flush=True)
    
    processed = 0
    extracted = 0
    
    for lampiran_name, pdf_path, page_num in pages:
        try:
            kbli_list = await extract_kbli_from_page(
                vision_service, pdf_path, page_num, lampiran_name, agent_id
            )
            
            if kbli_list:
                # Aggiungi ai risultati (per codice KBLI)
                for kbli in kbli_list:
                    code = kbli.get("kode", "")
                    if code:
                        if code not in results:
                            results[code] = []
                        results[code].append(kbli)
                        extracted += 1
            
            processed += 1
            
            if processed % 10 == 0:
                msg = f"  [Agent {agent_id}] Processate {processed}/{len(pages)} pagine, estratti {extracted} KBLI"
                print(msg, flush=True)
            
            # Rate limiting: pausa più lunga per evitare sovraccarico API
            await asyncio.sleep(1.0)  # Aumentato da 0.1s a 1s
            
        except Exception as e:
            print(f"  [Agent {agent_id}] ❌ Errore pagina {page_num}: {e}")
            processed += 1
    
    progress[f"agent_{agent_id}"] = {
        "processed": processed,
        "extracted": extracted
    }
    msg = f"✅ Agent {agent_id} completato: {processed} pagine, {extracted} KBLI estratti"
    print(msg, flush=True)


async def main():
    """Main function"""
    print("=" * 70)
    print("ESTRAZIONE COMPLETA KBLI DA TUTTI I LAMPIRAN")
    print(f"Usando {NUM_AGENTS} agenti paralleli")
    print("=" * 70)
    
    # Ottieni tutte le pagine
    print("\n📋 Scansione file Lampiran I...")
    all_pages = get_all_pages()
    print(f"\n📊 Totale pagine da processare: {len(all_pages)}")
    
    # Dividi tra agenti
    page_chunks = split_pages_among_agents(all_pages, NUM_AGENTS)
    print(f"📊 Pagine per agente: ~{len(all_pages) // NUM_AGENTS}")
    
    # Inizializza Vision Service
    print("\n🔧 Inizializzazione Vision Service...")
    vision_service = PDFVisionService()
    
    if not vision_service._available:
        print("❌ Vision Service non disponibile!")
        return
    
    print("✅ Vision Service pronto")
    
    # Risultati condivisi
    results = {}  # {kode: [kbli_entries]}
    progress = {}  # {agent_id: {processed, extracted}}
    
    # Avvia agenti
    print(f"\n🚀 Avvio {NUM_AGENTS} agenti paralleli...")
    tasks = []
    
    for agent_id in range(NUM_AGENTS):
        if page_chunks[agent_id]:  # Solo se ha pagine da processare
            task = agent_worker(
                agent_id,
                page_chunks[agent_id],
                vision_service,
                results,
                progress
            )
            tasks.append(task)
    
    # Esegui tutti gli agenti in parallelo
    await asyncio.gather(*tasks)
    
    # Consolida risultati
    print("\n" + "=" * 70)
    print("CONSOLIDAMENTO RISULTATI")
    print("=" * 70)
    
    consolidated = {}
    for code, entries in results.items():
        # Prendi l'entry più completa (quella con più campi)
        best_entry = max(entries, key=lambda e: sum(1 for v in e.values() if v))
        consolidated[code] = best_entry
    
    print(f"✅ KBLI unici estratti: {len(consolidated)}")
    
    # Statistiche
    total_extracted = sum(len(entries) for entries in results.values())
    print(f"📊 Totale estrazioni: {total_extracted}")
    print(f"📊 Media estrazioni per KBLI: {total_extracted/len(consolidated):.2f}")
    
    # Salva risultati
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(OUTPUT_DIR, f"kbli_complete_from_lampiran_{timestamp}.json")
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "source": "Lampiran I PP 28/2025",
            "total_pages_processed": len(all_pages),
            "num_agents": NUM_AGENTS,
            "total_kbli_extracted": len(consolidated),
            "total_extractions": total_extracted,
            "progress": progress,
            "kbli_data": consolidated
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n📁 Risultati salvati in: {output_file}")
    
    # Statistiche per agente
    print("\n📊 Statistiche per agente:")
    for agent_id, stats in sorted(progress.items()):
        print(f"   {agent_id}: {stats['processed']} pagine, {stats['extracted']} KBLI")


if __name__ == "__main__":
    asyncio.run(main())
