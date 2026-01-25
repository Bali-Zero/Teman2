import pdfplumber
import json
from pathlib import Path

PDF_PATH = Path("2.3 Lampiran I.C PP Nomor 28 Tahun 2025 (I.C.1-182) (1).pdf")


def test_extraction():
    print(f"Testing STREAM extraction on: {PDF_PATH}")

    if not PDF_PATH.exists():
        print("File not found!")
        return

    results = []

    with pdfplumber.open(PDF_PATH) as pdf:
        # Check first 2 pages
        for i, page in enumerate(pdf.pages[:2]):
            print(f"\n--- Page {i + 1} ---")

            # Try STREAM mode (for tables without distinct lines)
            # density=low might help if text is sparse
            tables = page.extract_tables(
                table_settings={
                    "vertical_strategy": "text",
                    "horizontal_strategy": "text",
                    "snap_tolerance": 3,
                }
            )

            if tables:
                print(f"Found {len(tables)} tables!")
                for t_idx, table in enumerate(tables):
                    print(f"Table {t_idx} Row 0: {table[0]}")
                    clean_table = [
                        [c.replace("\n", " ") if c else "" for c in row]
                        for row in table
                    ]
                    results.append(clean_table)
            else:
                print("No tables found with 'text' strategy.")

                # Fallback check: Extract raw text to see if it's readable at all
                text = page.extract_text()
                print(f"Raw Text Preview: {text[:200]}...")

    with open("pdf_stream_test.json", "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    test_extraction()
