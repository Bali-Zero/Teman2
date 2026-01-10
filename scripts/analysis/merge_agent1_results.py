#!/usr/bin/env python3
"""
Unisce i risultati di Agent 1 (pagine rimanenti) con l'estrazione parallela principale.
Agent 1 ha completato pagine 1254-1625 separatamente.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "reports", "kbli_extraction")


def find_latest_file(pattern: str) -> Path:
    """Trova il file più recente che corrisponde al pattern."""
    files = list(Path(OUTPUT_DIR).glob(pattern))
    if not files:
        return None
    return max(files, key=lambda f: f.stat().st_mtime)


def merge_kbli_data(main_data: Dict, agent1_data: Dict) -> Dict:
    """
    Unisce i dati KBLI, dando priorità ai dati più completi.
    Agent 1 ha completato pagine 1254-1625.
    """
    merged = {}
    
    # Aggiungi tutti i KBLI dall'estrazione principale
    main_kbli = main_data.get("kbli_data", {})
    for code, entry in main_kbli.items():
        merged[code] = entry
    
    # Aggiungi/aggiorna con i dati di Agent 1 (pagine 1254-1625)
    agent1_kbli = agent1_data.get("kbli_data", {})
    for code, entry in agent1_kbli.items():
        if code in merged:
            # Confronta e prendi quello più completo
            main_entry = merged[code]
            agent1_entry = entry
            
            # Conta campi non vuoti
            main_completeness = sum(1 for v in main_entry.values() if v)
            agent1_completeness = sum(1 for v in agent1_entry.values() if v)
            
            # Prendi quello più completo
            if agent1_completeness > main_completeness:
                merged[code] = agent1_entry
                print(f"   ✅ Aggiornato {code} con dati Agent 1 (più completo)")
        else:
            # Nuovo KBLI da Agent 1
            merged[code] = entry
            print(f"   ➕ Aggiunto nuovo KBLI {code} da Agent 1")
    
    return merged


def main():
    print("=" * 70)
    print("MERGE RISULTATI AGENT 1 CON ESTRAZIONE PARALLELA PRINCIPALE")
    print("=" * 70)
    
    # Trova file più recenti
    print("\n📋 Ricerca file...")
    
    main_file = find_latest_file("kbli_complete_from_lampiran_*.json")
    if main_file and "agent1_remaining" not in main_file.name:
        print(f"   ✅ Estrazione principale: {main_file.name}")
    else:
        print("   ⚠️  Estrazione principale non trovata")
        main_file = None
    
    agent1_file = find_latest_file("kbli_complete_from_lampiran_agent1_remaining_*.json")
    if agent1_file:
        print(f"   ✅ Agent 1 rimanenti: {agent1_file.name}")
    else:
        print("   ❌ File Agent 1 non trovato!")
        return
    
    if not main_file:
        print("\n⚠️  Estrazione principale non completata ancora.")
        print("   Attendi il completamento dell'estrazione parallela principale.")
        return
    
    # Carica dati
    print("\n📂 Caricamento dati...")
    with open(main_file) as f:
        main_data = json.load(f)
    print(f"   Estrazione principale: {len(main_data.get('kbli_data', {}))} KBLI")
    
    with open(agent1_file) as f:
        agent1_data = json.load(f)
    print(f"   Agent 1 rimanenti: {len(agent1_data.get('kbli_data', {}))} KBLI")
    
    # Merge
    print("\n🔄 Unione dati...")
    merged_kbli = merge_kbli_data(main_data, agent1_data)
    print(f"   ✅ Totale KBLI dopo merge: {len(merged_kbli)}")
    
    # Crea file merged
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(OUTPUT_DIR, f"kbli_complete_from_lampiran_merged_{timestamp}.json")
    
    merged_data = {
        "generated_at": datetime.now().isoformat(),
        "source": "Lampiran I PP 28/2025 - Estrazione Parallela + Agent 1 Completamento",
        "main_extraction": main_file.name,
        "agent1_completion": agent1_file.name,
        "total_pages_processed": main_data.get("total_pages_processed", 0),
        "num_agents": main_data.get("num_agents", 0),
        "total_kbli_extracted": len(merged_kbli),
        "kbli_data": merged_kbli
    }
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(merged_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n📁 File merged salvato: {output_file}")
    print(f"   Totale KBLI: {len(merged_kbli)}")


if __name__ == "__main__":
    main()
