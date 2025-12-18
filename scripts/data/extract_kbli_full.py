import json
import re

import pypdf


def main():
    pdf_path = "apps/scraper/data/correspondence-table-kbli-2020---kbli-2015.pdf"
    output_path = "kbli_2020_full_codes.json"

    codes = []
    seen_codes = set()

    try:
        reader = pypdf.PdfReader(pdf_path)
        total_pages = len(reader.pages)
        print(f"Processing {total_pages} pages...")

        # Regex to match lines starting with 5 digits
        # Pattern: 5 digits, spaces, (optional 2015 code part), spaces, Description
        # The 2015 part usually looks like "C 12345" or "C 12345 (1)" or just "-"
        # We'll try to capture the code and the rest of the line as description
        # We might need to clean the description later
        pattern = re.compile(r"^\s*(\d{5})\s+(?:[A-Z]\s+[\d\(\)\s]+|-)?\s*(.+)")

        for i in range(12, total_pages):  # Start from page 12 to skip intro
            text = reader.pages[i].extract_text()
            lines = text.split("\n")

            for line in lines:
                match = pattern.match(line)
                if match:
                    code = match.group(1)
                    desc = match.group(2).strip()

                    # Basic cleaning of description
                    # Remove trailing "https://www.bps.go.id" or page numbers if caught
                    if "https://www.bps.go.id" in desc:
                        desc = desc.replace("https://www.bps.go.id", "").strip()

                    if code not in seen_codes:
                        codes.append(
                            {
                                "code": code,
                                "description": desc,
                                "source": "KBLI 2020 PDF",
                            }
                        )
                        seen_codes.add(code)

        print(f"Extracted {len(codes)} unique KBLI codes.")

        with open(output_path, "w") as f:
            json.dump(codes, f, indent=2)

        print(f"Saved to {output_path}")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
