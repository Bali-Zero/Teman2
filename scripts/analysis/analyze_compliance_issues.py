#!/usr/bin/env python3
"""
Analizza i problemi di compliance in dettaglio per capire se sono reali o solo differenze di formato.
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
COMPLIANCE_FILE = PROJECT_ROOT / "reports" / "kbli_compliance" / "kbli_compliance_report.json"


def analyze_compliance():
    """Analizza i problemi di compliance."""
    print("=" * 70)
    print("ANALISI DETTAGLIATA PROBLEMI COMPLIANCE")
    print("=" * 70)
    
    with open(COMPLIANCE_FILE) as f:
        report = json.load(f)
    
    comparisons = report.get("comparisons", [])
    
    # Categorizza problemi
    title_differences = []
    real_problems = []
    missing_fields_only = []
    
    for comp in comparisons:
        if not comp.get("found_in_qdrant"):
            continue
        
        differences = comp.get("differences", [])
        missing = comp.get("missing_fields", [])
        
        # Conta differenze titolo vs altri problemi
        title_diff = [d for d in differences if "Judul" in d or "judul" in d.lower()]
        other_diff = [d for d in differences if "Judul" not in d and "judul" not in d.lower()]
        
        if title_diff and not other_diff and not missing:
            title_differences.append(comp)
        elif missing and not differences:
            missing_fields_only.append(comp)
        elif other_diff or (differences and not title_diff):
            real_problems.append(comp)
    
    print(f"\n📊 Categorizzazione problemi:")
    print(f"   Solo differenze titolo (non critico): {len(title_differences)}")
    print(f"   Solo campi mancanti: {len(missing_fields_only)}")
    print(f"   Problemi reali: {len(real_problems)}")
    
    print(f"\n=== ESEMPI DIFFERENZE TITOLO (non critico) ===")
    for comp in title_differences[:5]:
        print(f"\n{comp['code']}:")
        for diff in comp.get("differences", [])[:2]:
            print(f"  {diff}")
    
    print(f"\n=== ESEMPI PROBLEMI REALI ===")
    for comp in real_problems[:5]:
        print(f"\n{comp['code']}:")
        for diff in comp.get("differences", [])[:3]:
            print(f"  ❌ {diff}")
        if comp.get("missing_fields"):
            print(f"  ⚠️  Campi mancanti: {', '.join(comp['missing_fields'])}")
    
    print(f"\n=== ESEMPI SOLO CAMPI MANCANTI ===")
    for comp in missing_fields_only[:5]:
        print(f"\n{comp['code']}:")
        print(f"  ⚠️  Campi mancanti: {', '.join(comp['missing_fields'])}")
    
    # Statistiche reali
    total_with_issues = len([c for c in comparisons if c.get("differences") or c.get("missing_fields")])
    real_issues_count = len(real_problems) + len(missing_fields_only)
    title_only_count = len(title_differences)
    
    print(f"\n📊 Statistiche corrette:")
    print(f"   Totale con problemi: {total_with_issues}")
    print(f"   Solo differenze titolo (non critico): {title_only_count} ({title_only_count*100/total_with_issues:.1f}%)")
    print(f"   Problemi reali: {real_issues_count} ({real_issues_count*100/total_with_issues:.1f}%)")
    print(f"   - Problemi critici: {len(real_problems)}")
    print(f"   - Solo campi mancanti: {len(missing_fields_only)}")


if __name__ == "__main__":
    analyze_compliance()
