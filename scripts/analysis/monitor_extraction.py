#!/usr/bin/env python3
"""
Monitora il progresso dell'estrazione parallela KBLI.
"""

import os
import sys
import time
import json
import subprocess
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "reports", "kbli_extraction")


def check_process(pid):
    """Verifica se il processo è ancora in esecuzione."""
    try:
        result = subprocess.run(['ps', '-p', str(pid)], capture_output=True)
        return result.returncode == 0
    except:
        return False


def get_process_info(pid):
    """Ottiene info sul processo."""
    try:
        result = subprocess.run(['ps', '-p', str(pid), '-o', 'pid,pcpu,pmem,etime,command'], 
                              capture_output=True, text=True)
        lines = result.stdout.strip().split('\n')
        if len(lines) > 1:
            parts = lines[1].split()
            return {
                'pid': parts[0],
                'cpu': parts[1],
                'mem': parts[2],
                'etime': parts[3],
                'command': ' '.join(parts[4:])
            }
    except:
        pass
    return None


def find_latest_output():
    """Trova il file di output più recente."""
    files = list(Path(OUTPUT_DIR).glob('kbli_complete_from_lampiran_*.json'))
    # Escludi file agent1_remaining per ora
    main_files = [f for f in files if 'agent1_remaining' not in f.name]
    if main_files:
        return max(main_files, key=lambda x: x.stat().st_mtime)
    return None


def get_file_stats(file_path):
    """Ottiene statistiche dal file JSON."""
    try:
        with open(file_path) as f:
            data = json.load(f)
        return {
            'kbli_count': len(data.get('kbli_data', {})),
            'pages_processed': data.get('total_pages_processed', 0),
            'num_agents': data.get('num_agents', 0),
            'progress': data.get('progress', {}),
            'generated_at': data.get('generated_at', '')
        }
    except Exception as e:
        return {'error': str(e)}


def monitor(pid, interval=30):
    """Monitora il processo con aggiornamenti periodici."""
    print("=" * 70)
    print("MONITORAGGIO ESTRAZIONE PARALLELA KBLI")
    print("=" * 70)
    print(f"PID processo: {pid}")
    print(f"Intervallo controllo: {interval} secondi")
    print("Premi Ctrl+C per interrompere")
    print("=" * 70)
    print()
    
    start_time = time.time()
    last_kbli_count = 0
    last_pages = 0
    
    try:
        while True:
            # Verifica processo
            if not check_process(pid):
                print(f"\n❌ Processo {pid} non trovato - estrazione completata o terminata")
                break
            
            # Info processo
            proc_info = get_process_info(pid)
            if proc_info:
                elapsed = time.time() - start_time
                elapsed_str = time.strftime("%H:%M:%S", time.gmtime(elapsed))
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏱️  Tempo trascorso: {elapsed_str}")
                print(f"   CPU: {proc_info['cpu']}%, Mem: {proc_info['mem']}%, Etime: {proc_info['etime']}")
            
            # Verifica file output
            output_file = find_latest_output()
            if output_file:
                stats = get_file_stats(output_file)
                if 'error' not in stats:
                    kbli_count = stats['kbli_count']
                    pages = stats['pages_processed']
                    
                    print(f"   📁 File: {output_file.name}")
                    print(f"   📊 KBLI estratti: {kbli_count} (+{kbli_count - last_kbli_count if last_kbli_count > 0 else 0})")
                    print(f"   📄 Pagine processate: {pages} (+{pages - last_pages if last_pages > 0 else 0})")
                    
                    # Progress per agente
                    progress = stats.get('progress', {})
                    if progress:
                        print(f"   🤖 Progress agenti:")
                        for agent_id, agent_stats in sorted(progress.items()):
                            proc = agent_stats.get('processed', 0)
                            extr = agent_stats.get('extracted', 0)
                            print(f"      {agent_id}: {proc} pagine, {extr} KBLI")
                    
                    last_kbli_count = kbli_count
                    last_pages = pages
                else:
                    print(f"   ⚠️  Errore lettura file: {stats['error']}")
            else:
                print("   ⏳ Nessun file di output ancora creato...")
            
            print()
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Monitoraggio interrotto dall'utente")
    except Exception as e:
        print(f"\n\n❌ Errore durante monitoraggio: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Cerca il PID automaticamente
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        processes = [p for p in result.stdout.split('\n') 
                    if 'extract_all_kbli_from_lampiran_parallel.py' in p and 'grep' not in p]
        
        if processes:
            pid = int(processes[0].split()[1])
            print(f"🔍 Trovato processo: PID {pid}")
            monitor(pid)
        else:
            print("❌ Nessun processo di estrazione trovato")
            sys.exit(1)
    else:
        pid = int(sys.argv[1])
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        monitor(pid, interval)
