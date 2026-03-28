import pdfplumber
import re
from pathlib import Path

# Target specifically Lampiran I.C which we know has data but got low yield
PDF_PATH = Path("2.3 Lampiran I.C PP Nomor 28 Tahun 2025 (I.C.1-182) (1).pdf")

def debug_extraction():
    print(f"DEBUGGING extraction on: {PDF_PATH}")
    
    with pdfplumber.open(PDF_PATH) as pdf:
        # Check pages 2-5 (Page 1 is often cover/TOC)
        for i, page in enumerate(pdf.pages[1:5]): 
            print(f"\n--- Page {i+2} ---")
            
            tables = page.extract_tables(table_settings={
                "vertical_strategy": "text", 
                "horizontal_strategy": "text",
                "snap_tolerance": 3,
            })
            
            if not tables:
                print("NO TABLES FOUND")
                continue
                
            for t_idx, table in enumerate(tables):
                print(f"Table {t_idx} (First 5 rows):")
                for r_idx, row in enumerate(table):
                    # Clean slightly for display
                    row_display = [str(c).replace('\n', ' ')[:20] for c in row]
                    
                    # Run the logic found in universal_pdf_parser.py
                    cleaned_row = [str(cell).replace('\n', ' ').strip() for cell in row]
                    
                    # 1. Header Check
                    row_text = " ".join(cleaned_row).lower()
                    if "kode" in row_text and "judul" in row_text:
                        print(f"  [HEADER] {row_display}")
                        continue

                    # 2. KBLI Code Check
                    kbli_code = None
                    for idx, cell in enumerate(cleaned_row[:5]): # Expanded check scope
                        match = re.search(r'\b\d{5}\b', cell)
                        if match:
                            kbli_code = match.group(0)
                            break
                    
                    if kbli_code:
                         print(f"  [MATCH! {kbli_code}] {row_display}")
                    else:
                         # Check for spaced digits (e.g. "0 3 1 1 1")
                         spaced_match = re.search(r'\b(?:\d\s*){5}\b', " ".join(cleaned_row))
                         if spaced_match:
                             print(f"  [POTENTIAL SPACED MATCH: {spaced_match.group(0)}] {row_display}")
                         else:
                             print(f"  [REJECT] {row_display}")

if __name__ == "__main__":
    debug_extraction()
