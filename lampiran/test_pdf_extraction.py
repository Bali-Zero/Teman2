import pdfplumber
import json
from pathlib import Path

# Target file: Lampiran I.C (same as the Masterpiece source)
PDF_PATH = Path("2.3 Lampiran I.C PP Nomor 28 Tahun 2025 (I.C.1-182) (1).pdf")


def test_extraction():
    print(f"Testing extraction on: {PDF_PATH}")

    if not PDF_PATH.exists():
        print("File not found!")
        return

    results = []

    with pdfplumber.open(PDF_PATH) as pdf:
        # Test first 3 pages only to be fast
        for i, page in enumerate(pdf.pages[:3]):
            print(f"--- Page {i + 1} ---")

            # Extract tables
            tables = page.extract_tables()

            for table in tables:
                # Filter empty rows
                clean_table = [
                    [cell.replace("\n", " ") if cell else "" for cell in row]
                    for row in table
                ]
                results.append(clean_table)

                # Print first 2 rows of each table for inspection
                for row_idx, row in enumerate(clean_table[:2]):
                    print(f"Row {row_idx}: {row}")

    # Save a snippet to check structure
    with open("pdf_test_output.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nExtraction complete. Saved to pdf_test_output.json")


if __name__ == "__main__":
    test_extraction()
