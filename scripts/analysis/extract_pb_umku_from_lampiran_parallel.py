#!/usr/bin/env python3
"""
Estrae TUTTI i PB UMKU da Lampiran II, III, IV e li mappa ai KBLI di riferimento.
Questo è fondamentale per avere un quadro completo di cosa serve per ogni attività.
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

# Numero di agenti paralleli
NUM_AGENTS = 5

# File Lampiran con PB UMKU
LAMPIRAN_PB_UMKU_FILES = [
    ("Lampiran II", "PP Nomor 28 Tahun 2025 - Lampiran II.pdf"),
    ("Lampiran III", "PP Nomor 28 Tahun 2025 - Lampiran III.pdf"),
    ("Lampiran IV", "PP Nomor 28 Tahun 2025 - Lampiran IV.pdf"),
]


def get_all_pages() -> List[Tuple[str, str, int]]:
    """
    Restituisce lista di (lampiran_name, pdf_path, page_num) per tutte le pagine PB UMKU.
    """
    pages = []
    
    for lampiran_name, pdf_filename in LAMPIRAN_PB_UMKU_FILES:
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
    """Divide le pagine tra gli agenti."""
    chunks = [[] for _ in range(num_agents)]
    
    for i, page in enumerate(pages):
        agent_idx = i % num_agents
        chunks[agent_idx].append(page)
    
    return chunks


async def extract_pb_umku_from_page(
    vision_service: PDFVisionService, pdf_path: str, page_num: int, lampiran_name: str, agent_id: int
) -> List[Dict]:
    """
    Estrae PB UMKU da una pagina specifica usando Vision.
    """
    prompt = f"""
    Analizza questa pagina del {lampiran_name} del PP 28/2025.
    
    Questa pagina contiene tabelle di PB UMKU (Perizinan Berusaha Untuk Menunjang Kegiatan Usaha).
    
    Per ogni riga della tabella che contiene un PB UMKU, estrai:
    - nama_pb_umku: Il nome del permesso (es: "API-P", "Retail Permit", "Catering Permit")
    - persyaratan: Array con i requisiti per ottenere questo permesso (ogni requisito in un elemento separato)
    - kewajiban: Array con gli obblighi dopo aver ottenuto il permesso (ogni obbligo in un elemento separato)
    - jangka_waktu: Durata validità del permesso se presente
    - penerbitan: Chi emette il permesso se presente
    - kbli_referensi: Array con codici KBLI (5 cifre) a cui questo PB UMKU si applica, se presenti nella pagina
    
    Rispondi SOLO in formato JSON array:
    [
      {{
        "nama_pb_umku": "API-P (Producer Import)",
        "persyaratan": [
          "Memiliki IUI atau IUM",
          "Memiliki NPWP",
          "Memiliki kontrak dengan supplier"
        ],
        "kewajiban": [
          "Melaporkan impor setiap bulan",
          "Menyimpan dokumen impor minimal 5 tahun"
        ],
        "jangka_waktu": "1 tahun",
        "penerbitan": "Bea Cukai",
        "kbli_referensi": ["10612", "10720"]
      }},
      ...
    ]
    
    Se NON trovi tabelle PB UMKU, rispondi: []
    
    IMPORTANTE: 
    - Estrai TUTTE le righe della tabella
    - Se vedi codici KBLI nella pagina (5 cifre), includili in kbli_referensi
    - Se i persyaratan/kewajiban sono in formato lista, estrai ogni punto come elemento separato
    """
    
    # Retry logic con exponential backoff
    max_retries = 5
    base_delay = 2
    result = None
    
    for attempt in range(max_retries):
        try:
            result = await vision_service.analyze_page(
                pdf_path, page_num, prompt=prompt, is_drive_file=False
            )
            break
        except Exception as e:
            error_str = str(e)
            if "503" in error_str or "UNAVAILABLE" in error_str or "overloaded" in error_str.lower():
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    print(f"  [Agent {agent_id}] ⚠️  API overloaded pagina {page_num}, retry {attempt + 1}/{max_retries} dopo {delay}s...", flush=True)
                    await asyncio.sleep(delay)
                    continue
                else:
                    print(f"  [Agent {agent_id}] ❌ Max retries raggiunto per pagina {page_num}", flush=True)
                    return []
            else:
                print(f"  [Agent {agent_id}] ❌ Errore pagina {page_num}: {e}", flush=True)
                return []
    
    if not result:
        return []
    
    # Estrai JSON dalla risposta
    try:
        # Rimuovi markdown code blocks
        result_clean = result
        if "```json" in result:
            result_clean = re.sub(r'```json\s*', '', result)
            result_clean = re.sub(r'```\s*$', '', result_clean, flags=re.MULTILINE)
        elif "```" in result:
            result_clean = re.sub(r'```[a-z]*\s*', '', result)
            result_clean = re.sub(r'```\s*$', '', result_clean, flags=re.MULTILINE)
        
        # Cerca array JSON
        json_match = re.search(r'\[[\s\S]*?\]', result_clean, re.DOTALL)
        if json_match:
            try:
                json_str = json_match.group(0)
                json_str = json_str.replace("'", '"')
                json_str = re.sub(r',\s*}', '}', json_str)
                json_str = re.sub(r',\s*]', ']', json_str)
                
                pb_umku_list = json.loads(json_str)
                if isinstance(pb_umku_list, list) and len(pb_umku_list) > 0:
                    # Aggiungi metadati
                    for pb_umku in pb_umku_list:
                        pb_umku["source_page"] = page_num
                        pb_umku["source_lampiran"] = lampiran_name
                        pb_umku["source_file"] = os.path.basename(pdf_path)
                    return pb_umku_list
            except json.JSONDecodeError as e:
                # Prova estrazione più ampia
                try:
                    json_objects = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', result_clean, re.DOTALL)
                    if json_objects:
                        pb_umku_list = []
                        for obj_str in json_objects:
                            if '"nama_pb_umku"' in obj_str or "'nama_pb_umku'" in obj_str:
                                try:
                                    obj_str_clean = obj_str.replace("'", '"')
                                    obj = json.loads(obj_str_clean)
                                    if obj.get("nama_pb_umku"):
                                        obj["source_page"] = page_num
                                        obj["source_lampiran"] = lampiran_name
                                        obj["source_file"] = os.path.basename(pdf_path)
                                        pb_umku_list.append(obj)
                                except:
                                    pass
                        if pb_umku_list:
                            return pb_umku_list
                except:
                    pass
    except Exception as e:
        print(f"  [Agent {agent_id}] ⚠️  Errore parsing JSON pagina {page_num}: {e}", flush=True)
    
    return []


async def agent_worker(
    agent_id: int,
    pages: List[Tuple[str, str, int]],
    vision_service: PDFVisionService,
    results: Dict[str, List],
    progress: Dict[str, int]
):
    """Worker per un agente: processa le sue pagine assegnate."""
    msg = f"🤖 Agent {agent_id} iniziato: {len(pages)} pagine"
    print(msg, flush=True)
    
    processed = 0
    extracted = 0
    
    for lampiran_name, pdf_path, page_num in pages:
        try:
            pb_umku_list = await extract_pb_umku_from_page(
                vision_service, pdf_path, page_num, lampiran_name, agent_id
            )
            
            if pb_umku_list:
                # Aggiungi ai risultati (per nome PB UMKU)
                for pb_umku in pb_umku_list:
                    nama = pb_umku.get("nama_pb_umku", "")
                    if nama:
                        if nama not in results:
                            results[nama] = []
                        results[nama].append(pb_umku)
                        extracted += 1
            
            processed += 1
            
            if processed % 10 == 0:
                msg = f"  [Agent {agent_id}] Processate {processed}/{len(pages)} pagine, estratti {extracted} PB UMKU"
                print(msg, flush=True)
            
            await asyncio.sleep(1.0)
            
        except Exception as e:
            print(f"  [Agent {agent_id}] ❌ Errore pagina {page_num}: {e}", flush=True)
            processed += 1
    
    progress[f"agent_{agent_id}"] = {
        "processed": processed,
        "extracted": extracted
    }
    msg = f"✅ Agent {agent_id} completato: {processed} pagine, {extracted} PB UMKU estratti"
    print(msg, flush=True)


async def main():
    """Main function"""
    print("=" * 70)
    print("ESTRAZIONE COMPLETA PB UMKU DA LAMPIRAN II, III, IV")
    print(f"Usando {NUM_AGENTS} agenti paralleli")
    print("=" * 70)
    
    # Ottieni tutte le pagine
    print("\n📋 Scansione file Lampiran PB UMKU...")
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
    results = {}  # {nama_pb_umku: [pb_umku_entries]}
    progress = {}  # {agent_id: {processed, extracted}}
    
    # Avvia agenti
    print(f"\n🚀 Avvio {NUM_AGENTS} agenti paralleli...")
    tasks = []
    
    for agent_id in range(NUM_AGENTS):
        if page_chunks[agent_id]:
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
    kbli_to_pb_umku = defaultdict(list)  # {kbli_code: [pb_umku_names]}
    
    for nama, entries in results.items():
        # Prendi l'entry più completa
        best_entry = max(entries, key=lambda e: sum(1 for v in e.values() if v))
        consolidated[nama] = best_entry
        
        # Mappa ai KBLI di riferimento
        kbli_refs = best_entry.get("kbli_referensi", [])
        for kbli_code in kbli_refs:
            if kbli_code and len(kbli_code) == 5:
                kbli_to_pb_umku[kbli_code].append(nama)
    
    print(f"✅ PB UMKU unici estratti: {len(consolidated)}")
    print(f"✅ KBLI con PB UMKU mappati: {len(kbli_to_pb_umku)}")
    
    # Salva risultati
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(OUTPUT_DIR, f"pb_umku_complete_from_lampiran_{timestamp}.json")
    mapping_file = os.path.join(OUTPUT_DIR, f"kbli_to_pb_umku_mapping_{timestamp}.json")
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "source": "Lampiran II, III, IV PP 28/2025",
            "total_pages_processed": len(all_pages),
            "num_agents": NUM_AGENTS,
            "total_pb_umku_extracted": len(consolidated),
            "progress": progress,
            "pb_umku_data": consolidated
        }, f, indent=2, ensure_ascii=False)
    
    with open(mapping_file, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "source": "Lampiran II, III, IV PP 28/2025",
            "kbli_to_pb_umku": dict(kbli_to_pb_umku),
            "total_kbli_with_pb_umku": len(kbli_to_pb_umku)
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n📁 Risultati salvati:")
    print(f"   - PB UMKU: {output_file}")
    print(f"   - Mapping KBLI→PB UMKU: {mapping_file}")
    
    # Statistiche
    print("\n📊 Statistiche per agente:")
    for agent_id, stats in sorted(progress.items()):
        print(f"   {agent_id}: {stats['processed']} pagine, {stats['extracted']} PB UMKU")


if __name__ == "__main__":
    asyncio.run(main())
