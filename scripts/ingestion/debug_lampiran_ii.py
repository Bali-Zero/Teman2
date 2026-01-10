import pdfplumber
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PDF_FILE = PROJECT_ROOT / "lampiran" / "PP Nomor 28 Tahun 2025 - Lampiran II.pdf"

with pdfplumber.open(PDF_FILE) as pdf:
    for i in range(3):
        page = pdf.pages[i]
        print(f"--- PAGE {i+1} ---")
        
        # Try different table settings
        settings = {
            "vertical_strategy": "text", 
            "horizontal_strategy": "text",
            "intersection_y_tolerance": 10
        }
        tables = page.extract_tables(settings)
        
        if tables:
            print(f"Found {len(tables)} tables with settings.")
            for table in tables:
                for row in table[:3]:
                    clean_row = [str(c).replace('\n', ' ')[:50] + '...' if c else '' for c in row]
                    print(clean_row)
        else:
            print("No tables found with text strategy.")
        
        print("\n" + "="*50 + "\n")