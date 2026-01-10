#!/usr/bin/env python3
"""
Verifica contenuto resoconto Lampiran I.H
"""

import json
import os
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "reports" / "lampiran_analysis"

print(f"🔍 Cercando file in: {OUTPUT_DIR}")
print()

# Trova tutti i file resoconto
all_files = list(OUTPUT_DIR.glob("*.json"))
print(f"📁 File trovati: {len(all_files)}")

if not all_files:
    print("❌ Nessun file trovato!")
    print(f"   Directory esiste: {OUTPUT_DIR.exists()}")
    if OUTPUT_DIR.exists():
        print(f"   Contenuto directory: {list(OUTPUT_DIR.iterdir())}")
    exit(1)

# Mostra tutti i file
print("\n📄 File disponibili:")
for f in sorted(all_files, key=lambda x: x.stat().st_mtime, reverse=True):
    mtime = datetime.fromtimestamp(f.stat().st_mtime)
    print(f"   - {f.name} ({mtime.strftime('%Y-%m-%d %H:%M:%S')})")

# Prendi il più recente che contiene "I.H" nel nome
ih_files = [f for f in all_files if "I.H" in f.name or "I_H" in f.name]
if ih_files:
    latest_file = max(ih_files, key=lambda f: f.stat().st_mtime)
else:
    latest_file = max(all_files, key=lambda f: f.stat().st_mtime)

print(f"\n📄 Analizzando: {latest_file.name}")
print()

# Carica JSON
try:
    with open(latest_file, "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception as e:
    print(f"❌ Errore lettura file: {e}")
    exit(1)

print("=" * 70)
print("ANALISI RESOCONTO LAMPIRAN I.H")
print("=" * 70)
print()

# Info generali
print("📊 INFORMAZIONI GENERALI:")
print(f"   PDF: {data.get('pdf_name', 'N/A')}")
print(f"   Pagine totali: {data.get('total_pages', 'N/A')}")
print(f"   Pagine analizzate: {data.get('total_pages_analyzed', 'N/A')}")
print(f"   Agenti: {data.get('num_agents', 'N/A')}")
print(f"   Data analisi: {data.get('analysis_date', 'N/A')}")
elapsed = data.get('elapsed_time_seconds', 0)
if elapsed:
    print(f"   Tempo totale: {elapsed / 60:.1f} minuti")
print()

# Analisi agenti
print("🤖 ANALISI AGENTI:")
agents = data.get("agents", [])
total_errors = 0
total_success = 0

for i, agent in enumerate(agents, 1):
    if "error" in agent:
        print(f"   Agent {i}: ❌ ERRORE - {agent['error']}")
        total_errors += 1
    else:
        agent_id = agent.get("agent_id", i)
        pages_analyzed = agent.get("pages_analyzed", 0)
        total_pages = agent.get("total_pages", 0)
        results = agent.get("results", [])
        
        # Conta errori e successi
        errors = sum(1 for r in results if "error" in r or "parse_error" in r)
        success = len(results) - errors
        total_errors += errors
        total_success += success
        
        print(f"   Agent {agent_id}:")
        print(f"      Pagine analizzate: {pages_analyzed}/{total_pages}")
        print(f"      Risultati: {success} successi, {errors} errori")
        
        # Verifica pagine con errori
        if errors > 0:
            error_pages = [r.get("page", "?") for r in results if "error" in r or "parse_error" in r]
            print(f"      ⚠️  Pagine con errori: {error_pages[:10]}{'...' if len(error_pages) > 10 else ''}")

print(f"\n   📈 TOTALE: {total_success} successi, {total_errors} errori")
print()

# Estrazione dati
print("📋 ESTRAZIONE DATI:")
total_kbli = 0
total_pb_umku = 0
pages_with_kbli = 0
pages_with_pb_umku = 0
all_kbli_codes = set()
all_pb_umku_codes = set()

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
            
        content = analysis.get("content", {})
        extracted = analysis.get("extracted_data", {})
        
        # Conta KBLI
        kbli_codes = extracted.get("kbli_codes", [])
        if kbli_codes:
            total_kbli += len(kbli_codes)
            pages_with_kbli += 1
            all_kbli_codes.update(kbli_codes)
        
        # Conta PB UMKU
        pb_umku_codes = extracted.get("pb_umku_codes", [])
        if pb_umku_codes:
            total_pb_umku += len(pb_umku_codes)
            pages_with_pb_umku += 1
            all_pb_umku_codes.update(pb_umku_codes)

print(f"   KBLI estratti (totale): {total_kbli}")
print(f"   KBLI unici: {len(all_kbli_codes)}")
print(f"   Pagine con KBLI: {pages_with_kbli}")
print(f"   PB UMKU estratti (totale): {total_pb_umku}")
print(f"   PB UMKU unici: {len(all_pb_umku_codes)}")
print(f"   Pagine con PB UMKU: {pages_with_pb_umku}")
print()

# Qualità estrazione (campione)
print("🔍 CAMPIONE ESTRAZIONE (prime 5 pagine con dati):")
sample_count = 0
for agent in agents:
    if "error" in agent or sample_count >= 5:
        break
    
    results = agent.get("results", [])
    for result in results:
        if sample_count >= 5:
            break
        
        if "error" in result or "parse_error" in result:
            continue
        
        analysis = result.get("analysis", {})
        if not analysis:
            continue
            
        extracted = analysis.get("extracted_data", {})
        kbli_codes = extracted.get("kbli_codes", [])
        
        if kbli_codes:
            page_num = result.get("page", "?")
            print(f"   Pagina {page_num}:")
            print(f"      KBLI trovati: {len(kbli_codes)}")
            print(f"      Esempi: {kbli_codes[:5]}")
            
            # Mostra anche struttura analysis se disponibile
            content = analysis.get("content", {})
            if content.get("has_kbli"):
                print(f"      ✅ Contiene KBLI")
            sample_count += 1

print()
print("=" * 70)
print("✅ ANALISI COMPLETATA")
print("=" * 70)
