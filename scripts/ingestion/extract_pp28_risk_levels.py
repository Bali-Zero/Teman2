"""
PP 28/2025 Risk Level Extractor
Extracts KBLI codes and Risk Levels (Rendah, Menengah Rendah, Menengah Tinggi, Tinggi)
from the official Lampiran PDFs.
"""

import re
import json
import logging
from pathlib import Path
from pdfminer.high_level import extract_text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_risk_levels(pdf_path):
    logger.info(f"📄 Processing {pdf_path}...")
    try:
        text = extract_text(pdf_path)
    except Exception as e:
        logger.error(f"Failed to read PDF: {e}")
        return {}

    # Pattern to find KBLI codes (5 digits) followed eventually by risk level
    # This is a heuristic because tables are hard to parse purely with regex
    # We look for lines starting with a KBLI code
    
    # Pattern: 5 digits at start of line
    # followed by text
    # Risk levels keywords: "Rendah", "Menengah Rendah", "Menengah Tinggi", "Tinggi"
    
    results = {}
    
    lines = text.split('\n')
    current_code = None
    
    kbli_pattern = re.compile(r"^\s*(\d{5})\s")
    
    # Simple risk detection
    risk_keywords = {
        "Tinggi": "Tinggi",
        "Menengah Tinggi": "Menengah Tinggi", 
        "Menengah Rendah": "Menengah Rendah",
        "Rendah": "Rendah"
    }
    
    count = 0
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        # Check for new code
        match = kbli_pattern.search(line)
        if match:
            current_code = match.group(1)
            # If line also contains risk, grab it immediately
            found_risk = False
            for key, val in risk_keywords.items():
                if key in line and not found_risk:
                    results[current_code] = val
                    found_risk = True
                    count += 1
            continue
            
        # If inside a code block, look for risk level on subsequent lines
        if current_code and current_code not in results:
            for key, val in risk_keywords.items():
                if key in line:
                    results[current_code] = val
                    count += 1
                    break
                    
    logger.info(f"✅ Extracted {count} risk levels from {pdf_path}")
    return results

def main():
    base_dir = Path("data/kbli_pdfs")
    output_file = "source_documents/pp28_2025_risk_mapping.json"
    
    all_data = {}
    
    for pdf in base_dir.glob("*.pdf"):
        data = extract_risk_levels(str(pdf))
        all_data.update(data)
        
    logger.info(f"🔥 Total Unique KBLI Risk Mappings: {len(all_data)}")
    
    with open(output_file, "w") as f:
        json.dump(all_data, f, indent=2)
        
if __name__ == "__main__":
    main()
