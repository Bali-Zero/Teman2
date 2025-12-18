"""
Analyze PDFs with Unknown regulation type
Extract text from first pages to identify the correct regulation type
"""

import PyPDF2
import pandas as pd
from pathlib import Path

EXCEL_FILE = Path.home() / "Desktop" / "Indonesian_Laws_Inventory.xlsx"


def extract_text_from_pdf(pdf_path: Path, max_pages: int = 3) -> str:
    """Extract text from first pages of PDF"""
    try:
        with open(pdf_path, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)
            text = ""
            for i in range(min(max_pages, len(pdf_reader.pages))):
                text += pdf_reader.pages[i].extract_text() + "\n"
            return text[:2000]  # First 2000 chars
    except Exception as e:
        return f"Error: {e}"


def analyze_unknown_pdfs():
    """Analyze PDFs with Unknown regulation type"""
    df = pd.read_excel(EXCEL_FILE)
    unknown = df[df["Regulation Type"] == "Unknown"]
    
    print(f"Found {len(unknown)} PDFs with Unknown regulation type\n")
    print("=" * 80)
    
    for idx, row in unknown.iterrows():
        pdf_path = Path(row["Filepath"])
        print(f"\n{idx+1}. {row['Name']}")
        print(f"   File: {pdf_path.name}")
        print(f"   Category: {row['Category']}")
        print("-" * 80)
        
        if pdf_path.exists():
            text = extract_text_from_pdf(pdf_path)
            print(f"   First pages text (first 500 chars):")
            print(f"   {text[:500]}...")
            
            # Try to identify regulation type from text
            text_upper = text.upper()
            found_types = []
            
            if "UNDANG-UNDANG DASAR" in text_upper or "UUD" in text_upper:
                found_types.append("UUD")
            if "UNDANG-UNDANG" in text_upper and "PERATURAN" not in text_upper[:200]:
                found_types.append("UU")
            if "PERATURAN PRESIDEN" in text_upper or "PERPRES" in text_upper:
                found_types.append("Perpres")
            if "PERATURAN PEMERINTAH" in text_upper or re.search(r'\bPP\b', text_upper):
                found_types.append("PP")
            if "PERATURAN MENTERI" in text_upper or "PERMEN" in text_upper:
                found_types.append("Permen")
            if "PERATURAN DAERAH" in text_upper or "PERDA" in text_upper:
                found_types.append("Perda")
            if "KEPUTUSAN" in text_upper:
                found_types.append("Keputusan")
            
            if found_types:
                print(f"   ⚠️  Detected types: {', '.join(found_types)}")
            else:
                print(f"   ❓ No clear type detected")
        else:
            print(f"   ⚠️  File not found: {pdf_path}")
        
        print()


if __name__ == "__main__":
    import re
    analyze_unknown_pdfs()










