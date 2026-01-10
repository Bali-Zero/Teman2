#!/usr/bin/env python3
"""
PATCH 4/5 - Analizza Lampiran III con Gemini CLI
Worker 4: PP Nomor 28 Tahun 2025 - Lampiran III

IMPORTANTE: Processa pagina per pagina, NON carica tutto il PDF.
Ogni pagina viene estratta come immagine PNG e inviata separatamente a Gemini CLI.
"""

import asyncio
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple
import tempfile

import fitz  # PyMuPDF

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LAMPIRAN_DIR = os.path.join(PROJECT_ROOT, "lampiran")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "reports", "lampiran_analysis")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Configurazione
PDF_NAME = "PP Nomor 28 Tahun 2025 - Lampiran III"
PDF_FILENAME = "PP Nomor 28 Tahun 2025 - Lampiran III.pdf"
NUM_AGENTS = 3
MIN_PAGES_PER_AGENT = 50
DELAY_BETWEEN_PAGES = 2


def get_pdf_pages(pdf_path: str) -> int:
    """Ottiene numero totale di pagine."""
    try:
        doc = fitz.open(pdf_path)
        total = len(doc)
        doc.close()
        return total
    except Exception as e:
        print(f"❌ Errore apertura {pdf_path}: {e}")
        return 0


def extract_page_as_image(pdf_path: str, page_num: int, output_path: str) -> bool:
    """Estrae una pagina PDF come immagine PNG."""
    try:
        doc = fitz.open(pdf_path)
        page = doc[page_num - 1]  # 0-indexed
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom per qualità
        pix.save(output_path)
        doc.close()
        return True
    except Exception as e:
        print(f"❌ Errore estrazione pagina {page_num}: {e}")
        return False


def call_gemini_cli_with_image(image_path: str, prompt: str) -> str:
    """
    Chiama Gemini CLI con SOLO l'immagine della pagina (non il PDF).
    
    Prova diversi formati di comando:
    1. gemini analyze --image <path> --prompt "<prompt>"
    2. gemini vision --image <path> --prompt "<prompt>"
    3. python -m gemini analyze --image <path> --prompt "<prompt>"
    """
    commands_to_try = [
        ["gemini", "analyze", "--image", image_path, "--prompt", prompt],
        ["gemini", "vision", "--image", image_path, "--prompt", prompt],
        ["python", "-m", "gemini", "analyze", "--image", image_path, "--prompt", prompt],
        ["python3", "-m", "gemini", "analyze", "--image", image_path, "--prompt", prompt],
    ]
    
    for cmd in commands_to_try:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                check=True
            )
            return result.stdout
        except subprocess.TimeoutExpired:
            return "Error: Timeout"
        except subprocess.CalledProcessError as e:
            # Prova comando successivo
            continue
        except FileNotFoundError:
            # Prova comando successivo
            continue
    
    return "Error: Gemini CLI not found or command format incorrect"


async def analyze_page_with_gemini_cli(
    pdf_path: str,
    page_num: int,
    pdf_name: str,
    agent_id: int
) -> Dict[str, Any]:
    """
    Analizza UNA SINGOLA PAGINA usando Gemini CLI.
    IMPORTANTE: Estrae solo questa pagina come immagine, non carica tutto il PDF.
    """
    prompt = f"""
Analizza questa SINGOLA PAGINA (pagina {page_num}) del documento "{pdf_name}".

Fai un resoconto dettagliato di:

1. STRUTTURA DEL DOCUMENTO:
   - Tipo di contenuto (tabelle, testo, liste, etc.)
   - Colonne presenti nelle tabelle
   - Intestazioni e sezioni

2. CONTENUTO PRINCIPALE:
   - Cosa contiene questa pagina?
   - Quali informazioni sono presenti?
   - Ci sono codici KBLI? Se sì, quanti approssimativamente?
   - Ci sono permessi PB UMKU? Se sì, quanti?
   - Altri codici o classificazioni?

3. TABELLE TROVATE:
   - Quante tabelle ci sono in questa pagina?
   - Quante colonne ha ogni tabella?
   - Cosa contengono le colonne?
   - Esempi di righe (prime 3 righe)

4. DATI ESTRATTI:
   - Se ci sono codici KBLI, elenca TUTTI i codici trovati in questa pagina
   - Se ci sono permessi PB UMKU, elenca TUTTI quelli trovati in questa pagina
   - Altri codici o identificatori trovati

5. OSSERVAZIONI:
   - Qualche problema nella struttura?
   - Qualche dato mancante o incompleto?
   - Note importanti

Rispondi SOLO in formato JSON valido:
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
            "page": {page_num},
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
    
    # Estrai SOLO questa pagina come immagine PNG
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        image_path = tmp.name
    
    if not extract_page_as_image(pdf_path, page_num, image_path):
        return {"page": page_num, "error": "Failed to extract page"}
    
    try:
        # Chiama Gemini CLI con SOLO l'immagine della pagina (non il PDF)
        print(f"  [Agent {agent_id}] Invio pagina {page_num} come immagine PNG a Gemini CLI...")
        result = await asyncio.to_thread(call_gemini_cli_with_image, image_path, prompt)
        
        # Parse JSON
        try:
            result_clean = result
            if "```json" in result:
                result_clean = re.sub(r'```json\s*', '', result)
                result_clean = re.sub(r'```\s*$', '', result_clean, flags=re.MULTILINE)
            elif "```" in result:
                result_clean = re.sub(r'```[a-z]*\s*', '', result)
                result_clean = re.sub(r'```\s*$', '', result_clean, flags=re.MULTILINE)
            
            analysis = json.loads(result_clean)
            return {"page": page_num, "analysis": analysis}
        except json.JSONDecodeError as e:
            return {"page": page_num, "raw_response": result[:1000], "parse_error": str(e)}
    finally:
        # Cleanup: elimina immagine temporanea
        if os.path.exists(image_path):
            os.unlink(image_path)


async def analyze_pages_range(
    pdf_path: str,
    pdf_name: str,
    start_page: int,
    end_page: int,
    agent_id: int
) -> Dict[str, Any]:
    """Analizza un range di pagine - UNA PAGINA ALLA VOLTA."""
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
    print(f"  [Agent {agent_id}] ⚠️  IMPORTANTE: Processando pagina per pagina, NON caricando tutto il PDF")
    
    pages_analyzed = 0
    for page_num in range(start_page, end_page + 1):
        try:
            # Processa UNA pagina alla volta
            result = await analyze_page_with_gemini_cli(pdf_path, page_num, pdf_name, agent_id)
            resoconto["results"].append(result)
            pages_analyzed += 1
            
            if page_num % 10 == 0:
                print(f"  [Agent {agent_id}] Progress: {page_num - start_page + 1}/{end_page - start_page + 1} pagine")
            
            # Rate limiting tra pagine
            await asyncio.sleep(DELAY_BETWEEN_PAGES)
        except Exception as e:
            print(f"  [Agent {agent_id}] ⚠️  Errore pagina {page_num}: {e}")
            resoconto["results"].append({"page": page_num, "error": str(e)})
    
    resoconto["pages_analyzed"] = pages_analyzed
    print(f"  [Agent {agent_id}] ✅ Completato: {pages_analyzed}/{end_page - start_page + 1} pagine")
    return resoconto


def split_pages_for_agents(total_pages: int, num_agents: int) -> List[Tuple[int, int]]:
    """Divide pagine tra agenti."""
    pages_per_agent = max(MIN_PAGES_PER_AGENT, total_pages // num_agents)
    chunks = []
    for i in range(num_agents):
        start = i * pages_per_agent + 1
        end = min((i + 1) * pages_per_agent, total_pages)
        if start <= total_pages:
            chunks.append((start, end))
    return chunks


async def main():
    """Main function."""
    print("=" * 70)
    print(f"PATCH 4/5 - ANALISI: {PDF_NAME}")
    print("=" * 70)
    print("⚠️  IMPORTANTE: Processando pagina per pagina, NON caricando tutto il PDF")
    print("=" * 70)
    
    pdf_path = os.path.join(LAMPIRAN_DIR, PDF_FILENAME)
    if not os.path.exists(pdf_path):
        print(f"❌ PDF non trovato: {pdf_path}")
        return
    
    total_pages = get_pdf_pages(pdf_path)
    print(f"📄 Totale pagine: {total_pages}")
    
    num_agents = min(NUM_AGENTS, max(1, total_pages // MIN_PAGES_PER_AGENT))
    print(f"🤖 Agenti: {num_agents}")
    
    page_chunks = split_pages_for_agents(total_pages, num_agents)
    print(f"📦 Chunk: {len(page_chunks)}")
    for i, (start, end) in enumerate(page_chunks, 1):
        print(f"   Agent {i}: pagine {start}-{end} ({end - start + 1} pagine)")
    
    tasks = []
    for agent_id, (start, end) in enumerate(page_chunks, 1):
        task = analyze_pages_range(pdf_path, PDF_NAME, start, end, agent_id)
        tasks.append(task)
    
    print(f"\n🔄 Avvio {len(tasks)} agenti in parallelo...")
    print("⚠️  Ogni agente processa UNA PAGINA ALLA VOLTA come immagine PNG")
    start_time = time.time()
    resoconti = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.time() - start_time
    
    pdf_resoconto = {
        "pdf_name": PDF_NAME,
        "pdf_path": pdf_path,
        "total_pages": total_pages,
        "num_agents": num_agents,
        "analysis_date": datetime.now().isoformat(),
        "elapsed_time_seconds": elapsed,
        "agents": []
    }
    
    total_analyzed = 0
    for resoconto in resoconti:
        if isinstance(resoconto, Exception):
            pdf_resoconto["agents"].append({"error": str(resoconto)})
        else:
            pdf_resoconto["agents"].append(resoconto)
            total_analyzed += resoconto.get("pages_analyzed", 0)
    
    pdf_resoconto["total_pages_analyzed"] = total_analyzed
    
    safe_name = PDF_NAME.replace("/", "_").replace(" ", "_")
    output_file = os.path.join(OUTPUT_DIR, f"resoconto_{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(pdf_resoconto, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Resoconto salvato: {os.path.basename(output_file)}")
    print(f"📊 Pagine analizzate: {total_analyzed}/{total_pages} ({total_analyzed/total_pages*100:.1f}%)")
    print(f"⏱️  Tempo: {elapsed/60:.1f} minuti")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
