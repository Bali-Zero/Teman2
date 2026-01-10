#!/usr/bin/env python3
"""
PATCH 2: LAMPIRAN II PROCESSING (PB UMKU)
Extracts "Perizinan Berusaha Untuk Menunjang Kegiatan Usaha (PB UMKU)" from PP 28/2025 Lampiran II.
Saves extracted data to 'reports/kbli_extraction/pb_umku_lampiran_ii.json'.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Any
import pdfplumber

# Project structure
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "reports" / "kbli_extraction"
LAMPIRAN_DIR = PROJECT_ROOT / "lampiran"
OUTPUT_JSON = DATA_DIR / "pb_umku_lampiran_ii.json"
PDF_FILE = LAMPIRAN_DIR / "PP Nomor 28 Tahun 2025 - Lampiran II.pdf"

def clean_text(text: Any) -> str:
    """Clean extracted text."""
    if not text:
        return ""
    return str(text).replace('\n', ' ').strip()

def extract_kbli_codes(text: str) -> List[str]:
    """Extract 5-digit KBLI codes from text."""
    return re.findall(r'\b\d{5}\b', text)

def parse_lampiran_ii():
    """Parse Lampiran II PDF for PB UMKU data."""
    print(f"📄 Reading PDF: {PDF_FILE}")
    
    if not PDF_FILE.exists():
        print(f"❌ PDF not found: {PDF_FILE}")
        sys.exit(1)

    extracted_items = []
    
    try:
        with pdfplumber.open(PDF_FILE) as pdf:
            total_pages = len(pdf.pages)
            print(f"📊 Total pages: {total_pages}")
            
            # Table extraction settings
            settings = {
                "vertical_strategy": "text", 
                "horizontal_strategy": "text",
                "intersection_y_tolerance": 10
            }
            
            current_sector = "Unknown"
            
            for i, page in enumerate(pdf.pages):
                if i % 20 == 0:
                    print(f"   Processing page {i+1}/{total_pages}...")
                
                # Check for Sector headers in text (e.g. "A. SEKTOR ...")
                text = page.extract_text() or ""
                sector_match = re.search(r'([A-Z])\.\s+SEKTOR\s+([A-Z\s]+)', text)
                if sector_match:
                    current_sector = sector_match.group(2).strip()
                
                tables = page.extract_tables(settings)
                
                for table in tables:
                    for row in table:
                        # Skip empty rows
                        if not row or len(row) < 3:
                            continue
                        
                        # Clean row
                        row = [clean_text(c) for c in row]
                        
                        # Check if it's a valid data row (First col is number)
                        if re.match(r'^\d+$', row[0]):
                            # Attempt to map columns (Variable based on detection)
                            # Typically: No | Nomenklatur | Persyaratan | Jangka Waktu | Kewajiban | ...
                            
                            item = {
                                "no": row[0],
                                "sector": current_sector,
                                "nomenklatur_pb_umku": row[1] if len(row) > 1 else "",
                                "persyaratan": row[2] if len(row) > 2 else "",
                                "jangka_waktu": row[3] if len(row) > 3 else "",
                                "kewajiban": row[4] if len(row) > 4 else "",
                                "page": i + 1
                            }
                            
                            # Extract KBLI from any field
                            kblis = []
                            for field in item.values():
                                if isinstance(field, str):
                                    kblis.extend(extract_kbli_codes(field))
                            
                            item["related_kbli"] = sorted(list(set(kblis)))
                            extracted_items.append(item)
                                
    except Exception as e:
        print(f"❌ Error parsing PDF: {e}")
        # Continue to save what we have
        
    print(f"✅ Extracted {len(extracted_items)} PB UMKU items.")
    return extracted_items

def save_json(data: List[Dict]):
    """Save extracted data to JSON."""
    output_data = {
        "metadata": {
            "source": "PP 28/2025 Lampiran II",
            "extracted_date": "2026-01-10",
            "item_count": len(data)
        },
        "pb_umku_data": data
    }
    
    with open(OUTPUT_JSON, "w") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
        
    print(f"💾 Saved JSON to: {OUTPUT_JSON}")

def main():
    print("🚀 STARTING PATCH 2: LAMPIRAN II (PB UMKU)")
    data = parse_lampiran_ii()
    save_json(data)
    print("✅ PATCH COMPLETE")

if __name__ == "__main__":
    main()