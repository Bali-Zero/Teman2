#!/usr/bin/env python3
"""
Analisi specifica INGUB 6/2025 per restrizioni Bali

Identifica KBLI coinvolti, aree geografiche e crea mapping per Qdrant
"""

import os
import re
import json
import sys
from typing import Dict, List

try:
    import pypdf
except ImportError:
    from PyPDF2 import PdfReader as _PdfReader

    class _Wrapper:
        def __init__(self, path: str):
            self._reader = _PdfReader(path)

        @property
        def pages(self):
            return self._reader.pages

    class pypdf:  # type: ignore
        PdfReader = _Wrapper

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "reports", "kbli_compliance")

PDF_INGUB = "/Users/antonellosiano/Desktop/INGUB-6-TAHUN-2025-PENGHENTIAN-SEMENTARA-PEMBERIAN-IZIN-TOKO-MODERN-BERJEJARING.pdf"

# KBLI probabili per "toko modern berjejaring" (retail/franchising)
RETAIL_KBLI_PATTERNS = [
    r"4711",  # Perdagangan eceran dengan ruang penjualan tidak tetap
    r"4719",  # Perdagangan eceran lainnya dengan ruang penjualan tidak tetap
    r"4712",  # Perdagangan eceran makanan, minuman atau tembakau dengan ruang penjualan tidak tetap
    r"4713",  # Perdagangan eceran tekstil, pakaian dan alas kaki dengan ruang penjualan tidak tetap
    r"4714",  # Perdagangan eceran peralatan rumah tangga dengan ruang penjualan tidak tetap
    r"4715",  # Perdagangan eceran barang lainnya dengan ruang penjualan tidak tetap
    r"4719",  # Perdagangan eceran lainnya dengan ruang penjualan tidak tetap
    r"472",   # Perdagangan eceran dengan ruang penjualan tetap
    r"477",   # Perdagangan eceran bukan makanan, minuman atau tembakau dengan ruang penjualan tidak tetap
]


def analyze_ingub_pdf(pdf_path: str) -> Dict:
    """Analizza INGUB 6/2025 per estrarre informazioni."""
    if not os.path.exists(pdf_path):
        print(f"⚠️  PDF non trovato: {pdf_path}")
        return {}

    print(f"📄 Analisi INGUB 6/2025: {os.path.basename(pdf_path)}")
    reader = pypdf.PdfReader(pdf_path)

    result = {
        "source": "INGUB-6-TAHUN-2025",
        "title": "Penghantian Sementara Pemberian Izin Toko Modern Berjejaring",
        "kbli_codes": [],
        "kbli_patterns": [],
        "areas": [],
        "restrictions": {
            "type": "penghantian_sementara",
            "applies_to": "toko_modern_berjejaring",
            "scope": "regional_bali",
        },
        "valid_from": "",
        "valid_until": "",
        "full_text": "",
        "analysis_notes": [],
    }

    # Estrai tutto il testo
    full_text = ""
    for page_num, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
            full_text += text + "\n"
        except Exception as e:
            print(f"  ⚠️  Errore pagina {page_num}: {e}")
            continue

    result["full_text"] = full_text

    if not full_text.strip():
        result["analysis_notes"].append("PDF potrebbe essere scansionato (OCR necessario)")
        # Usa KBLI patterns noti per retail
        result["kbli_patterns"] = RETAIL_KBLI_PATTERNS
        result["analysis_notes"].append("Usati pattern KBLI noti per retail/franchising")
        return result

    # Cerca KBLI espliciti
    kbli_pattern = re.compile(r"\b(\d{5})\b")
    for match in kbli_pattern.finditer(full_text):
        code = match.group(1)
        if code not in result["kbli_codes"]:
            result["kbli_codes"].append(code)

    # Cerca pattern KBLI (es. "KBLI 4711", "kode 472")
    for pattern in RETAIL_KBLI_PATTERNS:
        if re.search(pattern, full_text):
            result["kbli_patterns"].append(pattern)

    # Cerca aree geografiche Bali
    area_keywords = [
        "Bali",
        "Denpasar",
        "Badung",
        "Gianyar",
        "Tabanan",
        "Klungkung",
        "Bangli",
        "Karangasem",
        "Buleleng",
        "Jembrana",
    ]
    for keyword in area_keywords:
        if re.search(rf"\b{keyword}\b", full_text, re.IGNORECASE):
            if keyword not in result["areas"]:
                result["areas"].append(keyword)

    # Cerca date
    date_patterns = [
        r"(\d{1,2}[-/]\d{1,2}[-/]\d{4})",
        r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})",
        r"tanggal\s+(\d{1,2})\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s+(\d{4})",
    ]
    for pattern in date_patterns:
        matches = re.findall(pattern, full_text, re.IGNORECASE)
        if matches:
            result["valid_from"] = str(matches[0]) if len(matches) > 0 else ""
            result["valid_until"] = str(matches[-1]) if len(matches) > 1 else ""

    # Analizza tipo restrizione
    text_lower = full_text.lower()
    if "penghantian" in text_lower or "sementara" in text_lower:
        result["restrictions"]["type"] = "penghantian_sementara"
    if "toko modern" in text_lower:
        result["restrictions"]["applies_to"] = "toko_modern_berjejaring"
    if "berjejaring" in text_lower or "franchise" in text_lower:
        result["restrictions"]["applies_to"] = "toko_modern_berjejaring"

    print(f"  ✅ Analisi completata:")
    print(f"     - KBLI espliciti: {len(result['kbli_codes'])}")
    print(f"     - Pattern KBLI: {len(result['kbli_patterns'])}")
    print(f"     - Aree identificate: {len(result['areas'])}")

    return result


def create_bali_restrictions_mapping(ingub_data: Dict) -> Dict:
    """Crea mapping KBLI → restrizioni Bali per Qdrant."""
    mapping = {
        "source": "INGUB-6-TAHUN-2025",
        "geographic_scope": "Bali",
        "restriction_type": "penghantian_sementara",
        "kbli_restrictions": {},
    }

    # Mappa KBLI espliciti
    for code in ingub_data.get("kbli_codes", []):
        mapping["kbli_restrictions"][code] = {
            "status": "restricted",
            "restriction": "penghantian_sementara",
            "areas": ingub_data.get("areas", []),
            "applies_to": "toko_modern_berjejaring",
        }

    # Mappa pattern (sarà necessario query Qdrant per trovare tutti i KBLI matching)
    for pattern in ingub_data.get("kbli_patterns", []):
        mapping["kbli_restrictions"][f"pattern_{pattern}"] = {
            "status": "pattern_match",
            "pattern": pattern,
            "restriction": "penghantian_sementara",
            "areas": ingub_data.get("areas", []),
            "note": "Richiede query Qdrant per trovare tutti i KBLI matching",
        }

    return mapping


def main():
    """Main analysis function."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("ANALISI INGUB 6/2025 - RESTRIZIONI BALI")
    print("=" * 60)

    # Analizza INGUB
    ingub_data = analyze_ingub_pdf(PDF_INGUB)

    # Salva analisi
    analysis_file = os.path.join(OUTPUT_DIR, "ingub_bali_analysis.json")
    with open(analysis_file, "w", encoding="utf-8") as f:
        json.dump(ingub_data, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Analisi salvata: {analysis_file}")

    # Crea mapping restrizioni
    restrictions_mapping = create_bali_restrictions_mapping(ingub_data)
    mapping_file = os.path.join(OUTPUT_DIR, "bali_restrictions_mapping.json")
    with open(mapping_file, "w", encoding="utf-8") as f:
        json.dump(restrictions_mapping, f, indent=2, ensure_ascii=False)
    print(f"💾 Mapping salvato: {mapping_file}")

    # Genera raccomandazioni
    recommendations = {
        "summary": "INGUB 6/2025 impatta KBLI per toko modern berjejaring in Bali",
        "action_required": [
            "Aggiungere campo metadata.geographic_restrictions in Qdrant per KBLI coinvolti",
            "Query Qdrant per trovare tutti i KBLI matching pattern retail (4711, 4719, 472, 477)",
            "Documentare restrizioni temporanee con valid_until date",
        ],
        "kbli_to_update": ingub_data.get("kbli_codes", []),
        "patterns_to_check": ingub_data.get("kbli_patterns", []),
    }

    rec_file = os.path.join(OUTPUT_DIR, "recommendations_bali.md")
    with open(rec_file, "w", encoding="utf-8") as f:
        f.write("# Raccomandazioni INGUB 6/2025 - Restrizioni Bali\n\n")
        f.write(f"**Data analisi**: {ingub_data.get('source', 'N/A')}\n\n")
        f.write(f"## Summary\n\n{recommendations['summary']}\n\n")
        f.write("## Azioni Richieste\n\n")
        for i, action in enumerate(recommendations["action_required"], 1):
            f.write(f"{i}. {action}\n")
        f.write("\n## KBLI da Aggiornare\n\n")
        if recommendations["kbli_to_update"]:
            for code in recommendations["kbli_to_update"]:
                f.write(f"- {code}\n")
        else:
            f.write("- Nessun KBLI esplicito trovato (usare pattern matching)\n")
        f.write("\n## Pattern da Verificare\n\n")
        for pattern in recommendations["patterns_to_check"]:
            f.write(f"- KBLI pattern: `{pattern}`\n")

    print(f"💾 Raccomandazioni salvate: {rec_file}")
    print(f"\n📁 Output salvato in: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
