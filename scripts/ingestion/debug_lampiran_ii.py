import pdfplumber
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PDF_FILE = PROJECT_ROOT / "lampiran" / "PP Nomor 28 Tahun 2025 - Lampiran II.pdf"

with pdfplumber.open(PDF_FILE) as pdf:
    for i in range(3):
        page = pdf.pages[i]
        print(f"--- PAGE {i+1} ---")
        text = page.extract_text()
        print("TEXT PREVIEW:")
        print(text[:500] + "...")
        
        print("\nTABLE PREVIEW:")
        tables = page.extract_tables()
        for table in tables:
            for row in table[:3]: # Print first 3 rows
                print(row)
        print("\n" + "="*50 + "\n")

