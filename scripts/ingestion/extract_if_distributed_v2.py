import fitz
import json
import re
import glob
import os

# Configuration
# Sorted list of unique file parts to cover the whole range without duplication
# 2.6a (1-700), 2.6b (701-1400), 2.6c (1401-2125), 2.6d (2126-2922), 2.6e (2923-3680), 2.6f (3681-4500), 2.6g (4501-5248), 2.6h (5249-11000)
PDF_PARTS_PATTERN = [
    "/Users/antonellosiano/Desktop/nuzantara/lampiran/2.6a*I.F*1-700*.pdf",
    "/Users/antonellosiano/Desktop/nuzantara/lampiran/2.6b*I.F*701-1400*.pdf",
    "/Users/antonellosiano/Desktop/nuzantara/lampiran/2.6c*I.F*1401-2125*.pdf",
    "/Users/antonellosiano/Desktop/nuzantara/lampiran/2.6d*I.F*2126-2922*.pdf",
    "/Users/antonellosiano/Desktop/nuzantara/lampiran/2.6e*I.F*2923-3680*.pdf",
    "/Users/antonellosiano/Desktop/nuzantara/lampiran/2.6f*I.F*3681-4500*.pdf",
    "/Users/antonellosiano/Desktop/nuzantara/lampiran/2.6g*I.F*4501-5248*.pdf",
    "/Users/antonellosiano/Desktop/nuzantara/lampiran/2.6h*I.F*5249-11000*.pdf",
]

OUTPUT_FILE = "/Users/antonellosiano/Desktop/nuzantara/reports/kbli_extraction/kbli_if_masterpiece_v6_clean.json"
BPS_REF_FILE = (
    "/Users/antonellosiano/Desktop/nuzantara/reports/kbli_2025_reference.json"
)

# Centroids for I.F (Industry) - Landscape
COLS = {
    "kode": 98,
    "judul": 145,
    "ruang": 204,
    "skala": 266,
    "risiko": 320,
    "perizinan": 377,
    "persyaratan": 447,
    "timeline": 536,
    "kewajiban": 602,
    "pb_umku": 676,
    "parameter": 738,
    "authority": 805,
}

DEFAULT_AUTHORITY = "Menteri Perindustrian"


def clean_text(text):
    # Aggressive cleaning of header artifacts
    # Matches (3), (3t, (31, {31, l3l, (3!, (4), (S), (s) etc.
    # Generally short tokens with parens/braces
    text = re.sub(r"[\(\{l\[]\d+[tliI!1]?[\)\}\]I]", "", text)
    text = re.sub(r"t\d+t", "", text)  # t2t
    text = re.sub(r"\(\d+[t]?\)", "", text)  # Standard (3)
    text = re.sub(r"\([a-zA-Z]\)", "", text)  # (a), (b), (s) if header

    # Specific known bad tokens from output
    bad_tokens = ["(3t", "(31", "{31", "l3l", "(3!", "(s)", "t2t", "(u", "f,o"]
    for t in bad_tokens:
        text = text.replace(t, "")

    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_bps_ref():
    if os.path.exists(BPS_REF_FILE):
        return json.load(open(BPS_REF_FILE))
    return {}


def extract_part(pdf_path, bps_map, context):
    print(f"   Processing {os.path.basename(pdf_path)}...")
    doc = fitz.open(pdf_path)
    part_data = []

    current_record = None
    last_kbli = context.get("last_kbli")

    for page_num in range(len(doc)):
        page = doc[page_num]
        words = page.get_text("words")
        # STRICT FILTER: Y > 250 to avoid headers
        words = [w for w in words if 250 < w[1] < 550]

        lines = {}
        for w in words:
            y = round(w[1] / 5) * 5
            if y not in lines:
                lines[y] = []
            lines[y].append(w)

        sorted_y = sorted(lines.keys())

        for y in sorted_y:
            line_words = sorted(lines[y], key=lambda w: w[0])

            potential_code = None
            # Scan for code near X=98
            for w in line_words:
                if abs(w[0] - COLS["kode"]) < 25:
                    txt = w[4].strip()
                    # Valid KBLI is 5 digits. Filter out garbage.
                    if re.match(r"^\d{5}$", txt):
                        potential_code = txt
                        break

            if potential_code:
                # Save previous
                if current_record:
                    clean_record = {}
                    for k, v in current_record.items():
                        if k == "kode":
                            clean_record[k] = v[0] if v else ""
                        else:
                            clean_record[k] = clean_text(" ".join(v))

                    if not clean_record.get("kode") and last_kbli:
                        clean_record["kode"] = last_kbli

                    if clean_record.get("kode"):
                        code = clean_record["kode"]
                        clean_record["sektor"] = "SEKTOR PERINDUSTRIAN"
                        clean_record["source_lampiran"] = "I.F"
                        clean_record["authority"] = DEFAULT_AUTHORITY

                        if code in bps_map:
                            clean_record["judul_bps"] = bps_map[code]["title"]
                            clean_record["validation_status"] = "MATCH_BPS_2025"
                        else:
                            clean_record["validation_status"] = "NOT_IN_BPS_2025"

                        part_data.append(clean_record)
                        last_kbli = clean_record["kode"]

                current_record = {k: [] for k in COLS.keys()}
                current_record["kode"] = [potential_code]
                last_kbli = potential_code

                for w in line_words:
                    if w[4] == potential_code:
                        continue
                    x_mid = (w[0] + w[2]) / 2
                    best_col = min(COLS.keys(), key=lambda k: abs(COLS[k] - x_mid))
                    if abs(COLS[best_col] - x_mid) < 50:
                        current_record[best_col].append(w[4])
            elif current_record:
                for w in line_words:
                    x_mid = (w[0] + w[2]) / 2
                    best_col = min(COLS.keys(), key=lambda k: abs(COLS[k] - x_mid))
                    if abs(COLS[best_col] - x_mid) < 60:
                        current_record[best_col].append(w[4])

    # Save last of this part
    if current_record:
        clean_record = {}
        for k, v in current_record.items():
            if k == "kode":
                clean_record[k] = v[0] if v else ""
            else:
                clean_record[k] = clean_text(" ".join(v))

        if not clean_record.get("kode") and last_kbli:
            clean_record["kode"] = last_kbli

        if clean_record.get("kode"):
            code = clean_record["kode"]
            clean_record["sektor"] = "SEKTOR PERINDUSTRIAN"
            clean_record["source_lampiran"] = "I.F"
            clean_record["authority"] = DEFAULT_AUTHORITY
            if code in bps_map:
                clean_record["judul_bps"] = bps_map[code]["title"]
                clean_record["validation_status"] = "MATCH_BPS_2025"
            else:
                clean_record["validation_status"] = "NOT_IN_BPS_2025"
            part_data.append(clean_record)

    context["last_kbli"] = last_kbli
    return part_data


def extract_if_v2():
    print("🚀 STARTING I.F (INDUSTRY) RE-EXTRACTION V2 (CLEAN)...")
    bps_map = load_bps_ref()
    context = {"last_kbli": None}
    all_rows = []

    # Resolve file paths
    resolved_files = []
    for pattern in PDF_PARTS_PATTERN:
        matched = glob.glob(pattern)
        if matched:
            resolved_files.append(sorted(matched)[0])  # Take first match
        else:
            print(f"⚠️ Warning: No file found for pattern {pattern}")

    # Sequential Processing
    for fpath in resolved_files:
        rows = extract_part(fpath, bps_map, context)
        all_rows.extend(rows)

    print(f"✅ Total Extracted Rows: {len(all_rows)}")

    # Post-Process: Remove any row where description is junk or empty?
    # Or strict check on KBLI.

    clean_rows = []
    seen = set()
    for row in all_rows:
        code = row["kode"]
        if code not in seen:
            clean_rows.append(row)
            seen.add(code)

    print(f"✅ Unique Codes: {len(seen)}")

    bspan_match = len(
        [r for r in clean_rows if r["validation_status"] == "MATCH_BPS_2025"]
    )
    print(f"📊 BPS 2025 Match Rate: {int(bspan_match / len(clean_rows) * 100)}%")

    with open(OUTPUT_FILE, "w") as f:
        json.dump({"data": clean_rows}, f, indent=2)


if __name__ == "__main__":
    extract_if_v2()
