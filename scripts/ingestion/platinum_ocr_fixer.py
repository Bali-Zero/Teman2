
import json
import re
import os

ATLAS_PATH = "/Users/antonellosiano/Desktop/nuzantara/reports/kbli_extraction/kbli_universal_atlas_polished.json"
OUTPUT_PATH = "/Users/antonellosiano/Desktop/nuzantara/reports/kbli_extraction/kbli_universal_atlas_polished.json"

# Common repetitive OCR headers and fuzzy corruptions to strip
GARBAGE_PATTERNS = [
    r"T[t|n]ng[l|t]at\s+R[l|s|i][s|l|h][i|l|o][k|h|l]o\s+\(?6[t|l|i|1]?\)?", 
    r"T[t|n]ng[l|t]at\s+R[l|s|i]sl?ko\s+\(?6?\)?",
    r"Ting[Ll]at\s+Rlsi[ho|lo]\s+\(?6?\)?",
    r"SLala Useha \(s\)", r"Skala Ueaha \(sl", r"Stala Usaha \(s\)", r"Strle Ueaha \(st", r"SLale Useha \(s\)", r"Skala Usehe \(ls\)", r"SLela Usahe \(sl",
    r"Kewen[a|c]ng[a|e]n\s+\(?13[t|l|i|1]?\)?", r"Keweaangan l13l", r"Kewenangaa t13t", r"Menteri/ Kepala Badan",
    r"Rueng Lingkup \(4\)", r"Ruang Lingkup \(4t\)?", r"Ruang Ltnglup \(41", r"Ruang Ltnglrup l4l", r"Ruaag Linglup \(4\)", r"Ruang Liagkup t4t", r"Seluruh Ruang Lingkup l4t",
    r"Periziaan Berusaha 17l", r"Perizinaa Berusaha 17l", r"Perizinan Berusehe 17l", r"Perizinan Beruerha t7l", r"Perizinan Berusrha 17l", r"Perizinan Berusahe t7l", r"NIB dan",
    r"Judul KBLI \(3t?", r"Judul I\(BLI \(3\)?", r"Judul KBLI l3t", r"Aktivitas r Kurir",
    r"Parameter lt2l", r"Paramcter t2", r"Parametcr t2", r"Peramcter t2", r"Peraneter t2",
    r"N\. PERIZINAN", r"BERUSAHA", r"SISTEM", r"TRANSAKSI", r"PB I'TIKTI", r"ELEKTRONIK"
]

def clean_string(s):
    if not s or not isinstance(s, str):
        return s
    
    # 1. Strip repetitive garbage headers
    for pattern in GARBAGE_PATTERNS:
        s = re.sub(pattern, "", s, flags=re.IGNORECASE)
    
    # 2. Deduplicate specific words that often repeat in OCR failures
    # If a word is repeated sequentially, keep only one.
    words = s.split()
    if not words: return ""
    
    new_words = []
    last_word = None
    for w in words:
        if w != last_word:
            new_words.append(w)
        last_word = w
    
    s = " ".join(new_words)
    
    # 3. Final cleanup of double spaces and trailing punctuation
    s = re.sub(r'\s+', ' ', s).strip()
    s = s.strip("-").strip()
    
    return s

def main():
    if not os.path.exists(ATLAS_PATH):
        print("Atlas not found.")
        return

    print(f"Reading Atlas: {ATLAS_PATH}")
    with open(ATLAS_PATH, 'r') as f:
        atlas = json.load(f)

    data = atlas.get('data', {})
    print(f"Sanitizing {len(data)} records...")

    count = 0
    for code, info in data.items():
        rd = info.get('risk_data', {})
        if rd:
            for key in ['risiko', 'skala', 'authority', 'ruang', 'judul']:
                if key in rd and rd[key]:
                    original = rd[key]
                    rd[key] = clean_string(rd[key])
                    if rd[key] != original:
                        count += 1
    
    print(f"Fixed {count} fields across the atlas.")
    
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(atlas, f, indent=2)
    
    print("Done. Atlas is now much cleaner.")

if __name__ == "__main__":
    main()
