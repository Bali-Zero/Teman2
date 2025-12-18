import json
import os
import re

EXTRACTED_FILE = "apps/kb/data/PP_28_2025_LAMPIRAN/KBLI_PP28_2025_GEMINI_EXTRACTED.json"

CANARY_CODES = {
    "96111": "AKTIVITAS PANGKAS RAMBUT",
    "96112": "AKTIVITAS SALON KECANTIKAN",
    "96121": "RUMAH PIJAT",
    "96122": "AKTIVITAS SPA",
    "96129": "AKTIVITAS KEBUGARAN LAINNYA",
    "56101": "RESTORAN",
    "56102": "WARUNG MAKAN",
    "55111": "HOTEL BINTANG LIMA",
    "55112": "HOTEL BINTANG EMPAT",
    "62010": "AKTIVITAS PEMROGRAMAN KOMPUTER"
}

def verify():
    if not os.path.exists(EXTRACTED_FILE):
        print("FAIL: JSON file not found")
        return

    with open(EXTRACTED_FILE, 'r') as f:
        data = json.load(f)

    codes = data.get("kbli_codes", [])
    total = len(codes)
    print(f"Total Codes: {total}")

    # check count
    if total < 1034:
        print("FAIL: Total codes < 1034")
    else:
        print("PASS: Count check (>1034)")

    # check structure
    code_set = set()
    errors = 0
    for item in codes:
        c = item.get('kode')
        if not c:
            print("FAIL: Item missing code")
            errors += 1
            continue
        
        # Check format
        if not re.fullmatch(r'\d{5}', c):
            print(f"FAIL: Invalid code format: {c}")
            errors += 1
        
        # Check duplicates (though script deduplicated)
        if c in code_set:
            print(f"FAIL: Duplicate code {c}")
            errors += 1
        code_set.add(c)

    if errors == 0:
        print("PASS: Format check")

    # Check canaries
    missing_canaries = []
    for cc, name in CANARY_CODES.items():
        found = False
        for item in codes:
            if item['kode'] == cc:
                found = True
                print(f"Found Canary: {cc} - {item['judul']}")
                break
        if not found:
            missing_canaries.append(cc)

    if missing_canaries:
        print(f"FAIL: Missing canaries: {missing_canaries}")
    else:
        print("PASS: All canary codes found")

    # Sample check
    print("\n--- Sample Entry ---")
    import random
    if codes:
        print(json.dumps(random.choice(codes), indent=2))

if __name__ == "__main__":
    verify()
