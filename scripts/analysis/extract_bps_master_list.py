#!/usr/bin/env python3
"""
Estrae la master list completa di tutti i KBLI da BPS 7/2025.
Questo è il documento ufficiale che contiene TUTTI i KBLI esistenti in Indonesia.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict
from dataclasses import dataclass, asdict

try:
    import pypdf
except ImportError:
    try:
        from PyPDF2 import PdfReader as _PdfReader
        class _Wrapper:
            def __init__(self, path: str):
                self._reader = _PdfReader(path)
            @property
            def pages(self):
                return self._reader.pages
        class pypdf:
            PdfReader = _Wrapper
    except ImportError:
        print("❌ Errore: pypdf o PyPDF2 non installato")
        print("   Installa con: pip install pypdf")
        sys.exit(1)

PROJECT_ROOT = Path(__file__).parent.parent.parent
PDF_BPS_PATH = "/Users/antonellosiano/Desktop/peraturan-bps-no-7-tahun-2025.pdf"
OUTPUT_DIR = PROJECT_ROOT / "reports" / "kbli_extraction"
OUTPUT_FILE = OUTPUT_DIR / "bps_master_list_complete.json"

# Regex per codici KBLI (5 cifre)
KBLI_CODE_RE = re.compile(r"\b(\d{5})\b")


@dataclass
class KBLIEntry:
    kode: str
    judul: str
    source: str = "BPS_7_2025"
    page: int = 0


def extract_kbli_from_bps(pdf_path: str) -> Dict[str, KBLIEntry]:
    """Estrae TUTTI i KBLI da Peraturan BPS 7/2025 (master list completa)."""
    if not os.path.exists(pdf_path):
        print(f"❌ PDF non trovato: {pdf_path}")
        return {}
    
    print(f"📄 Estrazione master list da: {os.path.basename(pdf_path)}")
    reader = pypdf.PdfReader(pdf_path)
    results: Dict[str, KBLIEntry] = {}
    total_pages = len(reader.pages)
    
    print(f"   Totale pagine: {total_pages}")
    
    for page_num, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as e:
            print(f"  ⚠️  Errore pagina {page_num}: {e}")
            continue
        
        # Cerca codici KBLI nella pagina
        for line in text.split("\n"):
            clean = line.strip()
            if not clean:
                continue
            
            # Cerca pattern codice KBLI (5 cifre)
            for match in KBLI_CODE_RE.finditer(clean):
                code = match.group(1)
                
                # Verifica che sia un codice KBLI valido (5 cifre)
                if not code.isdigit() or len(code) != 5:
                    continue
                
                # Se già presente, salta (evita duplicati)
                if code in results:
                    continue
                
                # Estrai titolo (testo dopo il codice)
                start, end = match.span(1)
                rest = clean[end:].strip(" -:\t")
                title = rest if rest else ""
                
                # Se il titolo è vuoto o troppo corto, prova a cercare nella riga successiva
                if len(title) < 3:
                    lines = text.split("\n")
                    for i, line in enumerate(lines):
                        if code in line:
                            # Cerca nella riga successiva
                            if i + 1 < len(lines):
                                next_line = lines[i + 1].strip()
                                if next_line and not KBLI_CODE_RE.match(next_line):
                                    title = next_line
                                    break
                
                results[code] = KBLIEntry(
                    kode=code,
                    judul=title,
                    source="BPS_7_2025",
                    page=page_num
                )
        
        if page_num % 50 == 0:
            print(f"   Processate {page_num}/{total_pages} pagine, trovati {len(results)} KBLI")
    
    print(f"  ✅ Trovati {len(results)} codici KBLI unici in BPS 7/2025")
    return results


def main():
    """Main extraction function."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print("=" * 70)
    print("ESTRAZIONE MASTER LIST KBLI DA BPS 7/2025")
    print("=" * 70)
    print()
    
    # Estrai tutti i KBLI
    bps_kbli = extract_kbli_from_bps(PDF_BPS_PATH)
    
    if not bps_kbli:
        print("❌ Nessun KBLI estratto!")
        return
    
    # Converti in formato JSON
    output_data = {
        "metadata": {
            "source": "Peraturan BPS No. 7 Tahun 2025",
            "extraction_date": __import__("datetime").datetime.now().isoformat(),
            "total_kbli": len(bps_kbli),
            "pdf_path": PDF_BPS_PATH
        },
        "kbli_data": {code: asdict(entry) for code, entry in bps_kbli.items()}
    }
    
    # Salva output
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print()
    print("=" * 70)
    print("RISULTATI")
    print("=" * 70)
    print(f"✅ Totale KBLI estratti: {len(bps_kbli)}")
    print(f"📁 File salvato: {OUTPUT_FILE}")
    print()
    
    # Statistiche per prefisso
    prefix_counts = {}
    for code in bps_kbli.keys():
        prefix = code[:2]
        prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1
    
    print("Distribuzione per prefisso (prime 2 cifre):")
    for prefix in sorted(prefix_counts.keys())[:10]:
        print(f"   {prefix}xx: {prefix_counts[prefix]} KBLI")
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
