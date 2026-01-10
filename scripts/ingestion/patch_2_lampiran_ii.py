#!/usr/bin/env python3
"""
PATCH 2: LAMPIRAN II PROCESSING
Extracts "Bidang Usaha Dengan Persyaratan Tertentu" from PP 28/2025 Lampiran II.
Updates the KBLI master list with these specific requirements.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional
import pdfplumber

# Project structure
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "reports" / "kbli_extraction"
LAMPIRAN_DIR = PROJECT_ROOT / "lampiran"
INPUT_JSON = DATA_DIR / "kbli_enriched_master_list.json"
OUTPUT_JSON = DATA_DIR / "kbli_enriched_master_list_v2.json"
PDF_FILE = LAMPIRAN_DIR / "PP Nomor 28 Tahun 2025 - Lampiran II.pdf"

def clean_text(text: Optional[str]) -> str:
    """Clean extracted text."""
    if not text:
        return ""
    return text.replace('\n', ' ').strip()

def extract_kbli_code(text: str) -> Optional[str]:
    """Extract 5-digit KBLI code from text."""
    match = re.search(r'\b\d{5}\b', text)
    return match.group(0) if match else None

def parse_lampiran_ii():
    """Parse Lampiran II PDF and return a dict of {kbli_code: requirements}."""
    print(f"📄 Reading PDF: {PDF_FILE}")
    
    if not PDF_FILE.exists():
        print(f"❌ PDF not found: {PDF_FILE}")
        sys.exit(1)

    extracted_data = {}
    
    try:
        with pdfplumber.open(PDF_FILE) as pdf:
            total_pages = len(pdf.pages)
            print(f"📊 Total pages: {total_pages}")
            
            for i, page in enumerate(pdf.pages):
                if i % 10 == 0:
                    print(f"   Processing page {i+1}/{total_pages}...")
                
                tables = page.extract_tables()
                
                for table in tables:
                    for row in table:
                        # Row structure usually: No | KBLI | Bidang Usaha | Persyaratan
                        # Sometimes header row
                        if not row or len(row) < 3:
                            continue
                            
                        # Clean row data
                        row_clean = [clean_text(cell) for cell in row]
                        
                        # Check if header
                        if "Kode KBLI" in row_clean[1] or "Bidang Usaha" in row_clean[2]:
                            continue
                            
                        # Extract KBLI
                        kbli_cell = row_clean[1]
                        requirements = row_clean[-1] # Last column is requirements
                        
                        # Handle multiple KBLIs in one cell (e.g. "01111, 01112")
                        # Or ranges "01111 - 01115"
                        # For now, let's look for all 5-digit codes
                        kbli_codes = re.findall(r'\d{5}', kbli_cell)
                        
                        if not kbli_codes:
                            continue
                            
                        for code in kbli_codes:
                            if code not in extracted_data:
                                extracted_data[code] = []
                            
                            # Add requirement if not duplicate
                            if requirements not in extracted_data[code]:
                                extracted_data[code].append(requirements)
                                
    except Exception as e:
        print(f"❌ Error parsing PDF: {e}")
        sys.exit(1)
        
    print(f"✅ Extracted requirements for {len(extracted_data)} KBLI codes.")
    return extracted_data

def update_kbli_json(extracted_data: Dict[str, List[str]]):
    """Update the JSON file with extracted data."""
    print(f"📂 Loading JSON: {INPUT_JSON}")
    
    if not INPUT_JSON.exists():
        print(f"❌ JSON not found: {INPUT_JSON}")
        # Try finding a fallback
        files = list(DATA_DIR.glob("kbli_complete_final_*.json"))
        if files:
            files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            fallback = files[0]
            print(f"⚠️  Falling back to: {fallback}")
            with open(fallback) as f:
                data = json.load(f)
        else:
            print("❌ No input JSON found.")
            sys.exit(1)
    else:
        with open(INPUT_JSON) as f:
            data = json.load(f)
            
    kbli_data = data.get("kbli_data", {})
    updated_count = 0
    
    for code, requirements_list in extracted_data.items():
        if code in kbli_data:
            entry = kbli_data[code]
            
            # Join requirements
            req_text = "; ".join(requirements_list)
            
            # Update fields
            entry["lampiran_ii_status"] = "Terbuka dengan Persyaratan"
            entry["lampiran_ii_requirements"] = req_text
            entry["investment_list_source"] = "PP 28/2025 Lampiran II"
            
            # Simple heuristic for PMA
            if "Penanaman Modal Dalam Negeri" in req_text or "PMDN" in req_text:
                 entry["pma_allowed"] = False
                 entry["pma_max_percentage"] = 0
            elif "Maksimal 49%" in req_text:
                 entry["pma_allowed"] = True
                 entry["pma_max_percentage"] = 49
            elif "Maksimal 51%" in req_text:
                 entry["pma_allowed"] = True
                 entry["pma_max_percentage"] = 51
            elif "Maksimal 67%" in req_text:
                 entry["pma_allowed"] = True
                 entry["pma_max_percentage"] = 67
            elif "Maksimal 70%" in req_text:
                 entry["pma_allowed"] = True
                 entry["pma_max_percentage"] = 70
                 
            updated_count += 1
            
    # Save output
    data["metadata"]["patch_2_date"] = "2026-01-10"
    data["metadata"]["lampiran_ii_processed"] = True
    data["metadata"]["updated_count"] = updated_count
    
    with open(OUTPUT_JSON, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    print(f"💾 Saved updated JSON to: {OUTPUT_JSON}")
    print(f"📈 Updated {updated_count} KBLI entries with Lampiran II data.")

def main():
    print("🚀 STARTING PATCH 2: LAMPIRAN II")
    extracted_data = parse_lampiran_ii()
    update_kbli_json(extracted_data)
    print("✅ PATCH COMPLETE")

if __name__ == "__main__":
    main()
