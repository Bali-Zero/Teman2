#!/usr/bin/env python3
"""
Estrazione diretta dati Lampiran usando Vertex API Key.
"""

import asyncio
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

import fitz  # PyMuPDF
from PIL import Image
import io
import base64

# Configurazione
VERTEX_API_KEY = "AQ.Ab8RN6LeucltUGRQWjV60WEf5aa0iIG_o5urt6fN9yH4lbTS-w"
PROJECT_ROOT = Path(__file__).parent.parent.parent
LAMPIRAN_DIR = PROJECT_ROOT / "lampiran"
OUTPUT_DIR = PROJECT_ROOT / "reports" / "lampiran_analysis"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Configurazione agenti
NUM_AGENTS_PER_PDF = 3
MIN_PAGES_PER_AGENT = 50
DELAY_BETWEEN_PAGES = 2

# Inizializza Vertex AI una sola volta (globale)
_vertex_ai_initialized = False
_vertex_model = None

def init_vertex_ai():
    """Inizializza Vertex AI una sola volta."""
    global _vertex_ai_initialized, _vertex_model
    
    if _vertex_ai_initialized:
        return _vertex_model
    
    try:
        import vertexai
        from vertexai.preview.generative_models import GenerativeModel
        
        vertexai.init(project="gen-lang-client-0498009027", location="us-central1")
        _vertex_model = GenerativeModel("gemini-2.0-flash-exp")
        _vertex_ai_initialized = True
        print("✅ Vertex AI inizializzato")
        return _vertex_model
    except Exception as e:
        print(f"❌ Errore inizializzazione Vertex AI: {e}")
        return None


def get_all_pdfs() -> List[tuple]:
    """Trova tutti i PDF nella directory lampiran."""
    if not LAMPIRAN_DIR.exists():
        return []
    pdfs = []
    for pdf_file in sorted(LAMPIRAN_DIR.glob("*.pdf")):
        pdfs.append((pdf_file.stem, str(pdf_file)))
    return pdfs


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


def extract_page_as_image(pdf_path: str, page_num: int) -> bytes:
    """Estrae una pagina PDF come immagine PNG."""
    doc = fitz.open(pdf_path)
    page = doc[page_num - 1]  # 0-indexed
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom
    img_bytes = pix.tobytes("png")
    doc.close()
    return img_bytes


async def analyze_page_with_vertex(
    pdf_path: str,
    page_num: int,
    pdf_name: str,
    agent_id: int
) -> Dict[str, Any]:
    """Analizza una pagina usando Vertex API."""
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
    
    try:
        # Estrai immagine
        image_bytes = extract_page_as_image(pdf_path, page_num)
        image_base64 = base64.b64encode(image_bytes).decode()
        
        # Usa Vertex AI SDK (inizializzato una volta all'inizio)
        from vertexai.preview.generative_models import Part
        
        # Ottieni modello (già inizializzato)
        model = init_vertex_ai()
        if model is None:
            return {
                "page": page_num,
                "error": "Vertex AI non inizializzato"
            }
        
        # Crea Part con i bytes dell'immagine
        image_part = Part.from_data(
            mime_type="image/png",
            data=image_bytes
        )
        
        # Aggiungi timeout e retry logic
        max_retries = 3
        retry_delay = 5  # secondi
        result_text = None
        
        for attempt in range(max_retries):
            try:
                # Timeout di 60 secondi per chiamata API
                response = model.generate_content(
                    [prompt, image_part],
                    generation_config={"max_output_tokens": 8192}
                )
                result_text = response.text
                break  # Successo, esci dal loop retry
            except Exception as api_error:
                error_msg = str(api_error)
                if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                    # Rate limiting - aspetta più a lungo
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    print(f"  [Agent {agent_id}] ⚠️  Rate limit (429) pagina {page_num}, attendo {wait_time}s...", flush=True)
                    await asyncio.sleep(wait_time)
                    if attempt == max_retries - 1:
                        raise  # Rilancia se ultimo tentativo
                elif "timeout" in error_msg.lower() or "deadline" in error_msg.lower():
                    # Timeout - riprova
                    print(f"  [Agent {agent_id}] ⚠️  Timeout pagina {page_num}, retry {attempt + 1}/{max_retries}...", flush=True)
                    await asyncio.sleep(retry_delay)
                    if attempt == max_retries - 1:
                        raise  # Rilancia se ultimo tentativo
                else:
                    # Altro errore - riprova o rilancia
                    print(f"  [Agent {agent_id}] ⚠️  Errore API pagina {page_num}: {error_msg[:100]}...", flush=True)
                    if attempt == max_retries - 1:
                        raise  # Rilancia se ultimo tentativo
                    await asyncio.sleep(retry_delay)
        
        # Se tutti i retry falliscono, result_text sarà None
        if result_text is None:
            return {
                "page": page_num,
                "error": "Failed after retries"
            }
        
        # Parse JSON
        try:
            result_clean = result_text
            if "```json" in result_text:
                result_clean = re.sub(r'```json\s*', '', result_text)
                result_clean = re.sub(r'```\s*$', '', result_clean, flags=re.MULTILINE)
            elif "```" in result_text:
                result_clean = re.sub(r'```[a-z]*\s*', '', result_text)
                result_clean = re.sub(r'```\s*$', '', result_clean, flags=re.MULTILINE)
            
            analysis = json.loads(result_clean)
            return {
                "page": page_num,
                "analysis": analysis
            }
        except json.JSONDecodeError as e:
            return {
                "page": page_num,
                "raw_response": result_text[:1000],
                "parse_error": str(e)
            }
                
    except Exception as e:
        return {
            "page": page_num,
            "error": str(e)
        }


async def analyze_pages_range(
    pdf_path: str,
    pdf_name: str,
    start_page: int,
    end_page: int,
    agent_id: int
) -> Dict[str, Any]:
    """Analizza un range di pagine."""
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
            result = await analyze_page_with_vertex(pdf_path, page_num, pdf_name, agent_id)
            resoconto["results"].append(result)
            
            if "error" not in result and "parse_error" not in result:
                pages_analyzed += 1
            
            if page_num % 10 == 0:
                print(f"  [Agent {agent_id}] Progress: {page_num - start_page + 1}/{end_page - start_page + 1} pagine")
            
            await asyncio.sleep(DELAY_BETWEEN_PAGES)
            
        except Exception as e:
            print(f"  [Agent {agent_id}] ⚠️  Errore pagina {page_num}: {e}")
            resoconto["results"].append({
                "page": page_num,
                "error": str(e)
            })
    
    resoconto["pages_analyzed"] = pages_analyzed
    print(f"  [Agent {agent_id}] ✅ Completato: {pages_analyzed}/{end_page - start_page + 1} pagine")
    
    return resoconto


def split_pages_for_agents(total_pages: int, num_agents: int) -> List[tuple]:
    """Divide pagine tra agenti."""
    pages_per_agent = max(MIN_PAGES_PER_AGENT, total_pages // num_agents)
    chunks = []
    for i in range(num_agents):
        start = i * pages_per_agent + 1
        end = min((i + 1) * pages_per_agent, total_pages)
        if start <= total_pages:
            chunks.append((start, end))
    return chunks


async def analyze_pdf_with_agents(
    pdf_name: str,
    pdf_path: str
) -> Dict[str, Any]:
    """Analizza un PDF completo con agenti paralleli."""
    print(f"\n{'='*70}", flush=True)
    print(f"📄 ANALISI: {pdf_name}", flush=True)
    print(f"{'='*70}", flush=True)
    
    print(f"   📁 File: {pdf_path}", flush=True)
    total_pages = get_pdf_pages(pdf_path)
    print(f"   📖 Totale pagine: {total_pages}", flush=True)
    
    if total_pages == 0:
        print(f"   ⚠️  PDF vuoto o non leggibile", flush=True)
        return None
    
    num_agents = min(NUM_AGENTS_PER_PDF, max(1, total_pages // MIN_PAGES_PER_AGENT))
    if num_agents == 0:
        num_agents = 1
    
    print(f"   🤖 Agenti: {num_agents}", flush=True)
    
    print(f"   🔧 Divisione pagine tra agenti...", flush=True)
    page_chunks = split_pages_for_agents(total_pages, num_agents)
    print(f"   ✅ Chunk pagine: {len(page_chunks)}", flush=True)
    
    # Crea task
    print(f"   🔧 Creazione task agenti...", flush=True)
    tasks = []
    for agent_id, (start_page, end_page) in enumerate(page_chunks, 1):
        print(f"      Agent {agent_id}: pagine {start_page}-{end_page}", flush=True)
        task = analyze_pages_range(pdf_path, pdf_name, start_page, end_page, agent_id)
        tasks.append(task)
    
    print(f"\n🔄 Avvio {len(tasks)} agenti in parallelo...", flush=True)
    start_time = time.time()
    try:
        resoconti = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed_time = time.time() - start_time
        print(f"✅ Tutti gli agenti completati in {elapsed_time/60:.1f} minuti", flush=True)
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"❌ Errore durante elaborazione agenti: {e}", flush=True)
        import traceback
        traceback.print_exc()
        raise
    
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
    for resoconto in resoconti:
        if isinstance(resoconto, Exception):
            pdf_resoconto["agents"].append({"error": str(resoconto)})
        else:
            pdf_resoconto["agents"].append(resoconto)
            total_pages_analyzed += resoconto.get("pages_analyzed", 0)
    
    pdf_resoconto["total_pages_analyzed"] = total_pages_analyzed
    
    # Salva resoconto
    safe_name = pdf_name.replace("/", "_").replace(" ", "_")
    output_file = OUTPUT_DIR / f"resoconto_{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(pdf_resoconto, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Resoconto salvato: {output_file.name}")
    print(f"📊 Pagine analizzate: {total_pages_analyzed}/{total_pages} ({total_pages_analyzed/total_pages*100:.1f}%)")
    print(f"⏱️  Tempo: {elapsed_time/60:.1f} minuti")
    
    return pdf_resoconto


async def main():
    """Main function."""
    print("=" * 70, flush=True)
    print("ESTRAZIONE LAMPIRAN CON VERTEX API KEY", flush=True)
    print("=" * 70, flush=True)
    print(flush=True)
    
    # Inizializza Vertex AI all'inizio
    print("🔧 Inizializzazione Vertex AI...", flush=True)
    model = init_vertex_ai()
    if model is None:
        print("❌ Impossibile inizializzare Vertex AI!", flush=True)
        return
    print("✅ Vertex AI pronto\n", flush=True)
    
    pdfs = get_all_pdfs()
    if not pdfs:
        print("❌ Nessun PDF trovato!", flush=True)
        return
    
    print(f"📚 Trovati {len(pdfs)} PDF da analizzare\n", flush=True)
    
    # Analizza ogni PDF
    for idx, (pdf_name, pdf_path) in enumerate(pdfs, 1):
        print(f"\n{'#'*70}", flush=True)
        print(f"Inizio analisi PDF {idx}/{len(pdfs)}: {pdf_name}", flush=True)
        print(f"{'#'*70}\n", flush=True)
        try:
            await analyze_pdf_with_agents(pdf_name, pdf_path)
            print(f"\n✅ PDF {idx}/{len(pdfs)} completato: {pdf_name}\n", flush=True)
            
            if idx < len(pdfs):
                print(f"⏸️  Pausa 30 secondi prima del prossimo PDF...\n", flush=True)
                await asyncio.sleep(30)
        except Exception as e:
            print(f"❌ Errore analisi {pdf_name}: {e}", flush=True)
            import traceback
            traceback.print_exc()
            continue
    
    print("\n" + "=" * 70)
    print("✅ Estrazione completata!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
