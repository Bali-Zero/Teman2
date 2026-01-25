#!/usr/bin/env python3
"""
Local PDF Extractor for KBLI Tables
Uses PyMuPDF (fitz) to extract text locally without API calls
"""

import fitz  # PyMuPDF
import json
import re
from pathlib import Path

# Configuration
PDF_PATH = "/Users/antonellosiano/Desktop/nuzantara/lampiran/2.3 Lampiran I.C PP Nomor 28 Tahun 2025 (I.C.1-182) (1).pdf"
OUTPUT_JSON = "/Users/antonellosiano/Desktop/nuzantara/lampiran/KBLI_Lampiran_I_C_Extracted_Local.json"


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract all text from PDF"""
    print(f"📖 Opening PDF: {Path(pdf_path).name}")
    doc = fitz.open(pdf_path)

    all_text = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        all_text.append(text)
        print(f"   Page {page_num + 1}/{len(doc)} extracted")

    doc.close()
    return "\n".join(all_text)


def parse_kbli_records(text: str) -> list:
    """Parse extracted text into structured KBLI records"""
    records = []

    # Split by numbered entries (e.g., "1.", "2.", etc.)
    # Look for pattern: number followed by 5-digit KBLI code
    pattern = r"(\d+)\.\s*(\d{5})\s+(.*?)(?=\n\d+\.\s*\d{5}|\Z)"
    matches = re.findall(pattern, text, re.DOTALL)

    for match in matches:
        no, kode_kbli, content = match

        # Try to extract structured fields from content
        record = {
            "no": no.strip(),
            "kode_kbli": kode_kbli.strip(),
            "raw_content": content.strip()[:500],  # First 500 chars
        }

        # Try to extract common fields
        if "Tingkat Risiko" in content or "tingkat risiko" in content.lower():
            risk_match = re.search(
                r"[Tt]ingkat [Rr]isiko[:\s]*(Rendah|Menengah Rendah|Menengah Tinggi|Tinggi)",
                content,
            )
            if risk_match:
                record["tingkat_risiko"] = risk_match.group(1)

        records.append(record)

    return records


def main():
    print("=" * 70)
    print("🚀 Local PDF Extractor for KBLI (PyMuPDF)")
    print("=" * 70)

    # Extract text
    try:
        full_text = extract_text_from_pdf(PDF_PATH)
        print(f"\n✅ Extracted {len(full_text)} characters")

        # Save raw text for debugging
        debug_file = OUTPUT_JSON.replace(".json", "_raw_text.txt")
        with open(debug_file, "w", encoding="utf-8") as f:
            f.write(full_text)
        print(f"💾 Saved raw text to: {debug_file}")

        # Parse records
        print("\n🔍 Parsing KBLI records...")
        records = parse_kbli_records(full_text)
        print(f"✅ Found {len(records)} potential records")

        # Save JSON
        output_data = {
            "meta": {
                "source_file": Path(PDF_PATH).name,
                "total_records": len(records),
                "extraction_method": "PyMuPDF_local",
            },
            "data": records,
        }

        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"✅ Saved JSON to: {OUTPUT_JSON}")
        print("\n" + "=" * 70)
        print("✨ Extraction Complete!")
        print("=" * 70)

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
