#!/usr/bin/env python3
"""
Monitora il progresso dell'estrazione Lampiran.
Controlla periodicamente i file creati e mostra lo stato.
"""

import time
import os
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "reports" / "lampiran_analysis"
LAMPIRAN_DIR = PROJECT_ROOT / "lampiran"

def get_all_pdfs():
    """Trova tutti i PDF nella directory lampiran."""
    if not LAMPIRAN_DIR.exists():
        return []
    return sorted(LAMPIRAN_DIR.glob("*.pdf"))

def get_resoconto_files():
    """Trova tutti i file resoconto JSON."""
    return sorted(OUTPUT_DIR.glob("resoconto_*.json"), key=lambda x: x.stat().st_mtime)

def analyze_resoconto(file_path):
    """Analizza un file resoconto per estrarre statistiche."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        pdf_name = data.get("pdf_name", "Unknown")
        total_pages = data.get("total_pages", 0)
        pages_analyzed = data.get("total_pages_analyzed", 0)
        num_agents = data.get("num_agents", 0)
        elapsed = data.get("elapsed_time_seconds", 0)
        
        # Conta errori
        agents = data.get("agents", [])
        total_errors = 0
        total_success = 0
        
        for agent in agents:
            if "error" in agent:
                total_errors += 1
            else:
                results = agent.get("results", [])
                errors = sum(1 for r in results if "error" in r or "parse_error" in r)
                success = len(results) - errors
                total_errors += errors
                total_success += success
        
        # Estrai dati estratti
        total_kbli = 0
        total_pb_umku = 0
        
        for agent in agents:
            if "error" in agent:
                continue
            results = agent.get("results", [])
            for result in results:
                if "error" in result or "parse_error" in result:
                    continue
                analysis = result.get("analysis", {})
                if not analysis:
                    continue
                extracted = analysis.get("extracted_data", {})
                kbli_codes = extracted.get("kbli_codes", [])
                pb_umku_codes = extracted.get("pb_umku_codes", [])
                if kbli_codes:
                    total_kbli += len(kbli_codes)
                if pb_umku_codes:
                    total_pb_umku += len(pb_umku_codes)
        
        return {
            "pdf_name": pdf_name,
            "total_pages": total_pages,
            "pages_analyzed": pages_analyzed,
            "completion": (pages_analyzed / total_pages * 100) if total_pages > 0 else 0,
            "num_agents": num_agents,
            "elapsed_minutes": elapsed / 60 if elapsed else 0,
            "total_success": total_success,
            "total_errors": total_errors,
            "total_kbli": total_kbli,
            "total_pb_umku": total_pb_umku,
            "status": "completed" if pages_analyzed >= total_pages else "in_progress"
        }
    except Exception as e:
        return {
            "pdf_name": file_path.name,
            "error": str(e),
            "status": "error"
        }

def check_process_running():
    """Verifica se il processo di estrazione è ancora in esecuzione."""
    import subprocess
    try:
        result = subprocess.run(
            ["pgrep", "-f", "analyze_lampiran_pdfs_with_agents.py"],
            capture_output=True,
            text=True
        )
        return len(result.stdout.strip()) > 0
    except:
        return False

def main():
    """Monitora il progresso."""
    print("=" * 70)
    print("MONITORAGGIO ESTRAZIONE LAMPIRAN")
    print("=" * 70)
    print()
    
    # Trova tutti i PDF
    all_pdfs = get_all_pdfs()
    print(f"📚 PDF totali da processare: {len(all_pdfs)}")
    
    # Trova file resoconto
    resoconto_files = get_resoconto_files()
    print(f"📄 File resoconto creati: {len(resoconto_files)}")
    print()
    
    # Verifica processo
    process_running = check_process_running()
    if process_running:
        print("🟢 Processo in esecuzione")
    else:
        print("🔴 Processo non trovato (potrebbe essere completato o terminato)")
    print()
    
    if resoconto_files:
        print("=" * 70)
        print("STATO ESTRAZIONE PER PDF")
        print("=" * 70)
        print()
        
        total_pages_all = 0
        total_pages_analyzed_all = 0
        total_kbli_all = 0
        total_pb_umku_all = 0
        
        for resoconto_file in resoconto_files:
            stats = analyze_resoconto(resoconto_file)
            
            if "error" in stats:
                print(f"❌ {stats['pdf_name']}: ERRORE - {stats['error']}")
                continue
            
            status_icon = "✅" if stats["status"] == "completed" else "🟡"
            print(f"{status_icon} {stats['pdf_name']}")
            print(f"   Pagine: {stats['pages_analyzed']}/{stats['total_pages']} ({stats['completion']:.1f}%)")
            print(f"   Agenti: {stats['num_agents']}")
            print(f"   Tempo: {stats['elapsed_minutes']:.1f} minuti")
            print(f"   Successi: {stats['total_success']}, Errori: {stats['total_errors']}")
            print(f"   KBLI estratti: {stats['total_kbli']}")
            print(f"   PB UMKU estratti: {stats['total_pb_umku']}")
            print()
            
            total_pages_all += stats['total_pages']
            total_pages_analyzed_all += stats['pages_analyzed']
            total_kbli_all += stats['total_kbli']
            total_pb_umku_all += stats['total_pb_umku']
        
        print("=" * 70)
        print("RIEPILOGO TOTALE")
        print("=" * 70)
        print(f"📄 PDF processati: {len(resoconto_files)}/{len(all_pdfs)}")
        print(f"📖 Pagine analizzate: {total_pages_analyzed_all}/{total_pages_all} ({total_pages_analyzed_all/total_pages_all*100:.1f}%)" if total_pages_all > 0 else "📖 Pagine analizzate: 0")
        print(f"🔢 KBLI estratti: {total_kbli_all}")
        print(f"📋 PB UMKU estratti: {total_pb_umku_all}")
        print()
    else:
        print("⏳ Nessun file resoconto ancora creato.")
        print("   Lo script potrebbe essere ancora in fase di inizializzazione...")
        print()
    
    print("=" * 70)
    print(f"Ultimo aggiornamento: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

if __name__ == "__main__":
    main()
