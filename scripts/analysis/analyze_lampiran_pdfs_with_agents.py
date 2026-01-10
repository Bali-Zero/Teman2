#!/usr/bin/env python3
"""
Analizza i PDF nella directory lampiran con agenti paralleli.
Un PDF alla volta, ogni PDF viene diviso tra agenti (es: 10 agenti).
Ogni agente analizza le sue pagine e produce un resoconto dettagliato.
"""

import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any
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
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "reports", "lampiran_analysis")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Configurazione agenti (ridotto per evitare quota limits)
NUM_AGENTS_PER_PDF = 3  # 3 agenti per PDF (ridotto da 10)
MIN_PAGES_PER_AGENT = 50  # Minimo 50 pagine per agente
DELAY_BETWEEN_PAGES = 2  # Secondi tra pagine (aumentato da 1)


def get_all_pdfs() -> List[Tuple[str, str]]:
    """Trova tutti i PDF nella directory lampiran."""
    pdfs = []
    
    if not os.path.exists(LAMPIRAN_DIR):
        print(f"❌ Directory lampiran non trovata: {LAMPIRAN_DIR}")
        return pdfs
    
    for pdf_file in sorted(Path(LAMPIRAN_DIR).glob("*.pdf")):
        pdfs.append((pdf_file.stem, str(pdf_file)))
        print(f"📄 Trovato: {pdf_file.name}")
    
    return pdfs


def get_pdf_pages(pdf_path: str) -> int:
    """Ottiene numero totale di pagine di un PDF."""
    try:
        doc = fitz.open(pdf_path)
        total = len(doc)
        doc.close()
        return total
    except Exception as e:
        print(f"❌ Errore apertura {pdf_path}: {e}")
        return 0


def split_pages_for_agents(total_pages: int, num_agents: int) -> List[Tuple[int, int]]:
    """
    Divide le pagine tra agenti.
    Returns: Lista di (start_page, end_page) per ogni agente
    """
    pages_per_agent = max(MIN_PAGES_PER_AGENT, total_pages // num_agents)
    chunks = []
    
    for i in range(num_agents):
        start_page = i * pages_per_agent + 1
        end_page = min((i + 1) * pages_per_agent, total_pages)
        
        if start_page <= total_pages:
            chunks.append((start_page, end_page))
    
    return chunks


async def analyze_pages_range(
    vision_service: PDFVisionService,
    pdf_path: str,
    pdf_name: str,
    start_page: int,
    end_page: int,
    agent_id: int
) -> Dict[str, Any]:
    """
    Analizza un range di pagine e produce un resoconto dettagliato.
    """
    prompt = f"""
    Analizza queste pagine (da {start_page} a {end_page}) del documento "{pdf_name}".
    
    Fai un resoconto dettagliato di:
    
    1. STRUTTURA DEL DOCUMENTO:
       - Tipo di contenuto (tabelle, testo, liste, etc.)
       - Colonne presenti nelle tabelle
       - Intestazioni e sezioni
    
    2. CONTENUTO PRINCIPALE:
       - Cosa contiene questo documento?
       - Quali informazioni sono presenti?
       - Ci sono codici KBLI? Se sì, quanti approssimativamente?
       - Ci sono permessi PB UMKU? Se sì, quanti?
       - Altri codici o classificazioni?
    
    3. TABELLE TROVATE:
       - Quante tabelle ci sono?
       - Quante colonne ha ogni tabella?
       - Cosa contengono le colonne?
       - Esempi di righe (prime 3 righe)
    
    4. DATI ESTRATTI:
       - Se ci sono codici KBLI, elenca i primi 10 codici trovati
       - Se ci sono permessi PB UMKU, elenca i primi 10
       - Altri codici o identificatori trovati
    
    5. OSSERVAZIONI:
       - Qualche problema nella struttura?
       - Qualche dato mancante o incompleto?
       - Note importanti
    
    Rispondi in formato JSON:
    {{
        "structure": {{
            "content_type": "...",
            "has_tables": true/false,
            "table_columns": [...],
            "sections": [...]
        }},
        "content": {{
            "description": "...",
            "has_kbli": true/false,
            "kbli_count_approx": 0,
            "has_pb_umku": true/false,
            "pb_umku_count_approx": 0,
            "other_codes": [...]
        }},
        "tables": [
            {{
                "page": 1,
                "columns": [...],
                "row_count_approx": 0,
                "sample_rows": [...]
            }}
        ],
        "extracted_data": {{
            "kbli_codes": [...],
            "pb_umku_codes": [...],
            "other_codes": [...]
        }},
        "observations": "..."
    }}
    """
    
    resoconto = {
        "agent_id": agent_id,
        "pdf_name": pdf_name,
        "pages_range": f"{start_page}-{end_page}",
        "start_page": start_page,
        "end_page": end_page,
        "total_pages": end_page - start_page + 1,
        "analysis_date": datetime.now().isoformat(),
        "results": []
    }
    
    print(f"  [Agent {agent_id}] Analizzando pagine {start_page}-{end_page} ({end_page - start_page + 1} pagine)...")
    
    pages_analyzed = 0
    for page_num in range(start_page, end_page + 1):
        try:
            # Retry logic
            max_retries = 3
            result = None
            
            for attempt in range(max_retries):
                try:
                    result = await vision_service.analyze_page(
                        pdf_path, page_num, prompt=prompt, is_drive_file=False
                    )
                    break
                except Exception as e:
                    error_str = str(e)
                    # Gestisci errori 429 (quota esaurita) con retry molto più lunghi
                    if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower():
                        if attempt < max_retries - 1:
                            delay = 60 * (2 ** attempt)  # 60s, 120s, 240s per quota
                            print(f"  [Agent {agent_id}] ⚠️  Quota esaurita pagina {page_num}, retry {attempt + 1}/{max_retries} dopo {delay/60:.0f} minuti...")
                            await asyncio.sleep(delay)
                            continue
                        else:
                            print(f"  [Agent {agent_id}] ❌ Quota esaurita dopo {max_retries} tentativi per pagina {page_num}")
                            raise
                    elif "503" in error_str or "UNAVAILABLE" in error_str or "overloaded" in error_str.lower():
                        if attempt < max_retries - 1:
                            delay = 5 * (2 ** attempt)  # 5s, 10s, 20s per overload
                            print(f"  [Agent {agent_id}] ⚠️  API overloaded pagina {page_num}, retry {attempt + 1}/{max_retries} dopo {delay}s...")
                            await asyncio.sleep(delay)
                            continue
                    raise
            
            if result:
                # Prova a parsare JSON
                try:
                    result_clean = result
                    if "```json" in result:
                        result_clean = re.sub(r'```json\s*', '', result)
                        result_clean = re.sub(r'```\s*$', '', result_clean, flags=re.MULTILINE)
                    elif "```" in result:
                        result_clean = re.sub(r'```[a-z]*\s*', '', result)
                        result_clean = re.sub(r'```\s*$', '', result_clean, flags=re.MULTILINE)
                    
                    page_analysis = json.loads(result_clean)
                    resoconto["results"].append({
                        "page": page_num,
                        "analysis": page_analysis
                    })
                    pages_analyzed += 1
                except json.JSONDecodeError as e:
                    # Se non è JSON valido, salva come testo
                    resoconto["results"].append({
                        "page": page_num,
                        "raw_response": result[:1000],  # Primi 1000 caratteri
                        "parse_error": str(e)
                    })
                    pages_analyzed += 1
            
            # Rate limiting (aumentato per evitare quota limits)
            await asyncio.sleep(DELAY_BETWEEN_PAGES)  # Delay configurabile tra pagine
            
            if page_num % 10 == 0:
                print(f"  [Agent {agent_id}] Progress: {page_num - start_page + 1}/{end_page - start_page + 1} pagine")
            
        except Exception as e:
            print(f"  [Agent {agent_id}] ⚠️  Errore pagina {page_num}: {e}")
            resoconto["results"].append({
                "page": page_num,
                "error": str(e)
            })
    
    resoconto["pages_analyzed"] = pages_analyzed
    print(f"  [Agent {agent_id}] ✅ Completato: {pages_analyzed}/{end_page - start_page + 1} pagine analizzate")
    
    return resoconto


async def analyze_pdf_with_agents(
    vision_service: PDFVisionService,
    pdf_name: str,
    pdf_path: str
) -> Dict[str, Any]:
    """Analizza un PDF completo con agenti paralleli."""
    print(f"\n{'='*70}")
    print(f"📄 ANALISI: {pdf_name}")
    print(f"{'='*70}")
    
    total_pages = get_pdf_pages(pdf_path)
    if total_pages == 0:
        return None
    
    print(f"   Totale pagine: {total_pages}")
    
    # Calcola numero agenti ottimale
    num_agents = min(NUM_AGENTS_PER_PDF, max(1, total_pages // MIN_PAGES_PER_AGENT))
    if num_agents == 0:
        num_agents = 1
    
    print(f"   Agenti: {num_agents}")
    
    # Divide pagine tra agenti
    page_chunks = split_pages_for_agents(total_pages, num_agents)
    print(f"   Chunk pagine: {len(page_chunks)}")
    for i, (start, end) in enumerate(page_chunks, 1):
        print(f"      Agent {i}: pagine {start}-{end} ({end - start + 1} pagine)")
    
    # Crea task per ogni agente
    tasks = []
    for agent_id, (start_page, end_page) in enumerate(page_chunks, 1):
        task = analyze_pages_range(
            vision_service, pdf_path, pdf_name, start_page, end_page, agent_id
        )
        tasks.append(task)
    
    # Esegui in parallelo
    print(f"\n🔄 Avvio {len(tasks)} agenti in parallelo...")
    start_time = time.time()
    resoconti = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed_time = time.time() - start_time
    
    # Processa risultati
    pdf_resoconto = {
        "pdf_name": pdf_name,
        "pdf_path": pdf_path,
        "total_pages": total_pages,
        "num_agents": num_agents,
        "analysis_date": datetime.now().isoformat(),
        "elapsed_time_seconds": elapsed_time,
        "agents": []
    }
    
    total_pages_analyzed = 0
    for i, resoconto in enumerate(resoconti):
        if isinstance(resoconto, Exception):
            print(f"  ❌ Agent {i+1} errore: {resoconto}")
            pdf_resoconto["agents"].append({
                "agent_id": i+1,
                "error": str(resoconto)
            })
        else:
            pdf_resoconto["agents"].append(resoconto)
            total_pages_analyzed += resoconto.get("pages_analyzed", 0)
    
    pdf_resoconto["total_pages_analyzed"] = total_pages_analyzed
    
    # Salva resoconto per questo PDF
    safe_name = pdf_name.replace("/", "_").replace(" ", "_")
    output_file = os.path.join(OUTPUT_DIR, f"resoconto_{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(pdf_resoconto, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Resoconto salvato: {os.path.basename(output_file)}")
    
    # Statistiche
    print(f"\n📊 Statistiche:")
    print(f"   Pagine analizzate: {total_pages_analyzed}/{total_pages} ({total_pages_analyzed/total_pages*100:.1f}%)")
    print(f"   Tempo totale: {elapsed_time/60:.1f} minuti")
    print(f"   Tempo medio per pagina: {elapsed_time/total_pages_analyzed:.1f} secondi" if total_pages_analyzed > 0 else "")
    
    return pdf_resoconto


def get_already_processed_pdfs() -> set:
    """Ottiene lista PDF già processati."""
    processed = set()
    
    if not os.path.exists(OUTPUT_DIR):
        return processed
    
    for resoconto_file in Path(OUTPUT_DIR).glob("resoconto_*.json"):
        try:
            with open(resoconto_file) as f:
                data = json.load(f)
                pdf_name = data.get("pdf_name")
                if pdf_name:
                    # Verifica che sia completo
                    total_pages = data.get("total_pages", 0)
                    pages_analyzed = data.get("total_pages_analyzed", 0)
                    if pages_analyzed >= total_pages * 0.9:  # 90% completato
                        processed.add(pdf_name)
        except:
            pass
    
    return processed


async def main(skip_processed: bool = True):
    """Main function - analizza un PDF alla volta."""
    print("=" * 70)
    print("ANALISI PDF LAMPIRAN CON AGENTI PARALLELI")
    print("=" * 70)
    print()
    
    # Trova tutti i PDF
    pdfs = get_all_pdfs()
    if not pdfs:
        print("❌ Nessun PDF trovato!")
        return
    
    print(f"\n📊 Trovati {len(pdfs)} PDF da analizzare")
    
    # Verifica PDF già processati
    if skip_processed:
        processed = get_already_processed_pdfs()
        if processed:
            print(f"📋 PDF già processati: {len(processed)}")
            pdfs = [(name, path) for name, path in pdfs if name not in processed]
            print(f"📊 PDF rimanenti: {len(pdfs)}")
    
    print()
    
    # Inizializza Vision Service
    print("🔧 Inizializzazione Vision Service...")
    vision_service = PDFVisionService()
    
    if not vision_service._available:
        print("❌ Vision Service non disponibile!")
        return
    
    print("✅ Vision Service pronto\n")
    
    # Analizza ogni PDF uno alla volta
    all_resoconti = []
    
    for idx, (pdf_name, pdf_path) in enumerate(pdfs, 1):
        print(f"\n{'#'*70}")
        print(f"PDF {idx}/{len(pdfs)}: {pdf_name}")
        print(f"{'#'*70}")
        
        try:
            resoconto = await analyze_pdf_with_agents(vision_service, pdf_name, pdf_path)
            if resoconto:
                all_resoconti.append(resoconto)
            
            # Pausa tra PDF (tranne l'ultimo) - aumentata per evitare quota limits
            if idx < len(pdfs):
                print(f"\n⏸️  Pausa 30 secondi prima del prossimo PDF...\n")
                await asyncio.sleep(30)
            
        except Exception as e:
            print(f"❌ Errore analisi {pdf_name}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Resoconto finale
    print("\n" + "=" * 70)
    print("📊 RIEPILOGO FINALE")
    print("=" * 70)
    print(f"PDF analizzati: {len(all_resoconti)}/{len(pdfs)}")
    
    for resoconto in all_resoconti:
        print(f"\n📄 {resoconto['pdf_name']}:")
        print(f"   Pagine: {resoconto['total_pages']}")
        print(f"   Pagine analizzate: {resoconto.get('total_pages_analyzed', 0)}")
        print(f"   Agenti: {resoconto['num_agents']}")
        print(f"   Tempo: {resoconto.get('elapsed_time_seconds', 0)/60:.1f} minuti")
    
    print("\n" + "=" * 70)
    print("✅ Analisi completata!")
    print("=" * 70)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-processed", action="store_true", default=True,
                       help="Skip PDF già processati (default: True)")
    parser.add_argument("--process-all", action="store_true",
                       help="Processa tutti i PDF anche se già processati")
    args = parser.parse_args()
    
    skip_processed = not args.process_all
    asyncio.run(main(skip_processed=skip_processed))
