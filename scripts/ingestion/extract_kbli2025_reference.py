import fitz
import re
import json

PDF_PATH = "/Users/antonellosiano/Desktop/peraturan-bps-no-7-tahun-2025.pdf"
OUTPUT_FILE = "/Users/antonellosiano/Desktop/nuzantara/reports/kbli_2025_reference.json"

def extract_kbli_2025():
    doc = fitz.open(PDF_PATH)
    all_codes = {}
    
    print(f"📖 READING KBLI 2025 BPS REFERENCE ({len(doc)} pages)...")
    
    # regex for "12345 TITLE STRING"
    # Typically: "32111 INDUSTRI PERHIASAN DAN LOGAM MULIA"
    # Or "12345. Judul..." ? No, usually space or tab.
    # Let's try matching start of lines.
    
    # 5-digit pattern: Start of line, 5 digits, space, Title
    pattern_5 = r'^\s*(\d{5})\s+(.+)$'
    
    # 3-digit pattern (Group)
    pattern_3 = r'^\s*(\d{3})\s+([A-Z\s,]+)$' # Groups usually ALL CAPS
    
    count_5 = 0
    
    for page in doc:
        text = page.get_text()
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Match 5 digits
            m5 = re.match(pattern_5, line)
            if m5:
                code, title = m5.groups()
                # Exclude years or page numbers disguised as codes
                if int(code) > 0 and len(title) > 3: 
                    all_codes[code] = {
                        "code": code,
                        "title": title.strip(),
                        "source": "BPS 2025"
                    }
                    count_5 += 1
                    
            # Match 3 digits (Context) (Optional, for now focusing on leaf nodes)
            
    # Verify count
    print(f"✅ EXTRACTED {count_5} KBLI 2025 CODES.")
    
    # Sort
    sorted_codes = dict(sorted(all_codes.items()))
    
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(sorted_codes, f, indent=2, ensure_ascii=False)
        
    print(f"💾 SAVED TO {OUTPUT_FILE}")

if __name__ == "__main__":
    extract_kbli_2025()
