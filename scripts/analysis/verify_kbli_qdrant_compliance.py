#!/usr/bin/env python3
"""
Verifica compliance collection KBLI in Qdrant rispetto ai PDF estratti

Confronta i dati estratti dai PDF con quelli in Qdrant e identifica:
- KBLI mancanti
- Dati obsoleti (risk level, PMA)
- Persyaratan/kewajiban mancanti
"""

import os
import json
import sys
from typing import Dict, List, Optional
from datetime import datetime
import requests
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXTRACTION_DIR = os.path.join(PROJECT_ROOT, "reports", "kbli_extraction")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "reports", "kbli_compliance")

# Load env
env_path = os.path.join(PROJECT_ROOT, "apps", "backend-rag", ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev").rstrip("/")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")


def fetch_kbli_from_qdrant(code: str) -> Optional[Dict]:
    """Recupera KBLI da Qdrant."""
    headers = {"Content-Type": "application/json"}
    if QDRANT_API_KEY:
        headers["api-key"] = QDRANT_API_KEY

    body = {
        "filter": {
            "must": [{"key": "metadata.kode", "match": {"value": code}}]
        },
        "limit": 1,
        "with_payload": True,
    }

    try:
        resp = requests.post(
            f"{QDRANT_URL}/collections/kbli_unified/points/scroll",
            headers=headers,
            json=body,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        points = data.get("result", {}).get("points", [])
        if points:
            return points[0].get("payload", {})
    except Exception as e:
        print(f"  ⚠️  Errore query Qdrant per {code}: {e}")
    return None


def extract_persyaratan_kewajiban(text: str) -> Dict:
    """Estrae Persyaratan e Kewajiban dal campo text."""
    result = {"persyaratan": [], "kewajiban": []}
    if not text:
        return result

    lines = text.split("\n")
    current_section = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if "## Persyaratan" in line or "Persyaratan (Requirements)" in line:
            current_section = "persyaratan"
            continue
        elif "## Kewajiban" in line or "Kewajiban (Obligations)" in line:
            current_section = "kewajiban"
            continue
        elif line.startswith("## "):
            current_section = None
            continue

        if current_section == "persyaratan":
            if line and (line[0].isdigit() or line.startswith("-")):
                clean = line.lstrip("0123456789.-) ").strip()
                if clean:
                    result["persyaratan"].append(clean)
        elif current_section == "kewajiban":
            if line and (line[0].isdigit() or line.startswith("-")):
                clean = line.lstrip("0123456789.-) ").strip()
                if clean:
                    result["kewajiban"].append(clean)

    return result


def compare_kbli(pdf_entry: Dict, qdrant_data: Optional[Dict]) -> Dict:
    """Confronta entry PDF con Qdrant."""
    code = pdf_entry.get("kode", "")
    comparison = {
        "code": code,
        "found_in_qdrant": qdrant_data is not None,
        "matches": {},
        "differences": [],
        "missing_fields": [],
    }

    if not qdrant_data:
        comparison["differences"].append("KBLI non trovato in Qdrant")
        return comparison

    meta = qdrant_data.get("metadata", {})
    text = qdrant_data.get("text", "")

    # Confronto titolo
    pdf_judul = pdf_entry.get("judul", "").lower().strip()
    q_judul = meta.get("judul", "").lower().strip()
    if pdf_judul and q_judul:
        if pdf_judul == q_judul:
            comparison["matches"]["judul"] = "identico"
        elif pdf_judul in q_judul or q_judul in pdf_judul:
            comparison["matches"]["judul"] = "simile"
        else:
            comparison["differences"].append(f"Judul diverso: PDF='{pdf_entry.get('judul')}', Qdrant='{meta.get('judul')}'")

    # Confronto risk level (se presente in PDF)
    pdf_risk = pdf_entry.get("tingkat_risiko", "")
    q_risk = meta.get("risk_level", "")
    if pdf_risk and q_risk:
        if pdf_risk == q_risk:
            comparison["matches"]["risk_level"] = "allineato"
        else:
            comparison["differences"].append(f"Risk level diverso: PDF={pdf_risk}, Qdrant={q_risk}")

    # Confronto PMA
    pdf_pma = pdf_entry.get("pma_allowed")
    q_pma = meta.get("pma_allowed")
    if pdf_pma is not None and q_pma is not None:
        if pdf_pma == q_pma:
            comparison["matches"]["pma_allowed"] = "allineato"
        else:
            comparison["differences"].append(f"PMA diverso: PDF={pdf_pma}, Qdrant={q_pma}")

    # Verifica persyaratan/kewajiban
    reqs = extract_persyaratan_kewajiban(text)
    if reqs["persyaratan"]:
        comparison["matches"]["has_persyaratan"] = len(reqs["persyaratan"])
    else:
        comparison["missing_fields"].append("persyaratan")

    if reqs["kewajiban"]:
        comparison["matches"]["has_kewajiban"] = len(reqs["kewajiban"])
    else:
        comparison["missing_fields"].append("kewajiban")

    # Verifica sources
    sources = meta.get("sources", [])
    if "PP_28_2025" in sources or "PP 28/2025" in str(sources):
        comparison["matches"]["has_pp28_source"] = True
    else:
        comparison["missing_fields"].append("source_PP_28_2025")

    return comparison


def main():
    """Main verification function."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("VERIFICA COMPLIANCE KBLI QDRANT")
    print("=" * 60)

    # Carica dati estratti
    bps_file = os.path.join(EXTRACTION_DIR, "bps_kbli.json")
    if not os.path.exists(bps_file):
        print(f"❌ File non trovato: {bps_file}")
        print("   Esegui prima: python scripts/analysis/extract_kbli_from_pdfs.py")
        sys.exit(1)

    with open(bps_file, "r", encoding="utf-8") as f:
        bps_kbli = json.load(f)

    print(f"\n📊 KBLI da confrontare: {len(bps_kbli)}")

    # Campione per test (primi 50)
    sample_size = min(50, len(bps_kbli))
    sample_codes = list(bps_kbli.keys())[:sample_size]
    print(f"🎯 Analizzando campione di {sample_size} codici...")

    comparisons = []
    stats = {
        "total_checked": 0,
        "found_in_qdrant": 0,
        "missing_in_qdrant": 0,
        "fully_aligned": 0,
        "has_differences": 0,
        "missing_persyaratan": 0,
        "missing_kewajiban": 0,
        "missing_pp28_source": 0,
    }

    for code in sample_codes:
        pdf_entry = bps_kbli[code]
        stats["total_checked"] += 1

        qdrant_data = fetch_kbli_from_qdrant(code)
        comparison = compare_kbli(pdf_entry, qdrant_data)
        comparisons.append(comparison)

        if comparison["found_in_qdrant"]:
            stats["found_in_qdrant"] += 1
            if not comparison["differences"] and not comparison["missing_fields"]:
                stats["fully_aligned"] += 1
            else:
                stats["has_differences"] += 1
                if "persyaratan" in comparison["missing_fields"]:
                    stats["missing_persyaratan"] += 1
                if "kewajiban" in comparison["missing_fields"]:
                    stats["missing_kewajiban"] += 1
                if "source_PP_28_2025" in comparison["missing_fields"]:
                    stats["missing_pp28_source"] += 1
        else:
            stats["missing_in_qdrant"] += 1

        if stats["total_checked"] % 10 == 0:
            print(f"  Processati: {stats['total_checked']}/{sample_size}")

    # Salva risultati
    compliance_report = {
        "generated_at": datetime.now().isoformat(),
        "stats": stats,
        "comparisons": comparisons,
    }

    report_file = os.path.join(OUTPUT_DIR, "kbli_compliance_report.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(compliance_report, f, indent=2, ensure_ascii=False)

    # Identifica gap
    missing_codes = [c["code"] for c in comparisons if not c["found_in_qdrant"]]
    needs_update = [c["code"] for c in comparisons if c["found_in_qdrant"] and (c["differences"] or c["missing_fields"])]

    gap_report = {
        "missing_in_qdrant": missing_codes,
        "needs_update": needs_update,
        "missing_details": {
            code: comparisons[i]["differences"] + comparisons[i]["missing_fields"]
            for i, code in enumerate(needs_update)
        },
    }

    gap_file = os.path.join(OUTPUT_DIR, "kbli_gaps.json")
    with open(gap_file, "w", encoding="utf-8") as f:
        json.dump(gap_report, f, indent=2, ensure_ascii=False)

    # Statistiche
    print("\n" + "=" * 60)
    print("RISULTATI VERIFICA COMPLIANCE")
    print("=" * 60)
    print(f"Totale verificati: {stats['total_checked']}")
    print(f"✅ Trovati in Qdrant: {stats['found_in_qdrant']} ({stats['found_in_qdrant']*100/stats['total_checked']:.1f}%)")
    print(f"❌ Mancanti in Qdrant: {stats['missing_in_qdrant']} ({stats['missing_in_qdrant']*100/stats['total_checked']:.1f}%)")
    print(f"✅ Completamente allineati: {stats['fully_aligned']} ({stats['fully_aligned']*100/stats['total_checked']:.1f}%)")
    print(f"⚠️  Con differenze: {stats['has_differences']}")
    print(f"   - Mancano persyaratan: {stats['missing_persyaratan']}")
    print(f"   - Mancano kewajiban: {stats['missing_kewajiban']}")
    print(f"   - Mancano source PP_28_2025: {stats['missing_pp28_source']}")
    print(f"\n📁 Report salvato in: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
