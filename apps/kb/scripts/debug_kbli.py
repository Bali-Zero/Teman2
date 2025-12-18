import os
import sys

# Add local libs to path
sys.path.append(os.path.join(os.getcwd(), '.libs'))

BASE_DIR = os.path.join(os.getcwd(), 'apps/kb/data/PP_28_2025_LAMPIRAN')
TEST_FILE = os.path.join(BASE_DIR, "Lampiran_I_J_to_P.pdf")

import pypdf

def debug_pdf(pdf_path):
    print(f"Debugging {os.path.basename(pdf_path)}...")
    try:
        reader = pypdf.PdfReader(pdf_path)
        # Check first 3 pages
        for p_idx in range(min(3, len(reader.pages))):
            page = reader.pages[p_idx]
            print(f"\n--- Page {p_idx+1} ---")
            text = page.extract_text()
            if text:
                print("First 500 chars:")
                print(text[:500])
                lines = text.split('\n')
                print(f"Total lines: {len(lines)}")
                # Check for potential codes
                import re
                print("Potential Codes found:")
                count = 0
                for line in lines:
                    matches = re.findall(r'\d{5}', line)
                    if matches:
                        print(f"Line: {line.strip()[:60]}... -> matches: {matches}")
                        count += 1
                        if count > 5: break
            else:
                print("No text extracted.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if os.path.exists(TEST_FILE):
        debug_pdf(TEST_FILE)
    else:
        print(f"Test file not found: {TEST_FILE}")
