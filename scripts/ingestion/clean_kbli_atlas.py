import json
import re
import os

INPUT_FILE = "/Users/antonellosiano/Desktop/nuzantara/reports/kbli_extraction/kbli_universal_atlas_final.json"
OUTPUT_FILE = "/Users/antonellosiano/Desktop/nuzantara/reports/kbli_extraction/kbli_universal_atlas_polished.json"

def clean_string(text):
    if not isinstance(text, str): return text
    
    # PASS 1: Strict OCR Artifact Removal (Garbage Only)
    # Remove: (3t, l3l, t2t, {31 but NOT (3) or (tiga)
    # The regex below matches (3t, (3l, (31, l3l, t2t
    text = re.sub(r'[\(\{l\[]\d+[tliI!][\)\}\]I]', '', text) 
    text = re.sub(r'\b[tli]2[tli]\b', '', text) # t2t, l2l
    text = re.sub(r'PRESlOEN|PRESINDONESIA|REPPUBLIK|PUBLIK|ELIK|Lingtup', '', text, flags=re.IGNORECASE)
    
    # PASS 2: OCR Typo Dictionary (The "Spellchecker")
    replacements = {
        'Perlzlnea': 'Perizinan',
        'Pcrsyereten': 'Persyaratan',
        'Pcrgyaratan': 'Persyaratan',
        'PersyarataE': 'Persyaratan',
        'Berusrhr': 'Berusaha',
        'Berusahr': 'Berusaha',
        'Kerajlban': 'Kewajiban',
        'Kewqilbea': 'Kewajiban',
        'Iftwdlban': 'Kewajiban',
        'Kerrjlbe': 'Kewajiban',
        'ruP': 'IUP',
        'rueng': 'Ruang',
        'Lingkup': 'Lingkup',
        'Perameter': 'Parameter',
        'Slrala': 'Skala',
        'JangLe': 'Jangka',
        'PelrerblteE': 'Penerbitan',
        'r.D.27': '', # Artifact
        'r.A.t2': '',
        'l.A.46': '',
        '1.A.76': '',
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
        
    # PASS 3: Hyphenation Repair
    # "Penga- wakan" -> "Pengawakan"
    text = re.sub(r'([a-zA-Z])-\s+([a-zA-Z])', r'\1\2', text)
    
    # PASS 4: Whitespace & Normalization
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def recursive_clean(obj):
    if isinstance(obj, dict):
        return {k: recursive_clean(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [recursive_clean(i) for i in obj]
    elif isinstance(obj, str):
        return clean_string(obj)
    else:
        return obj

def main():
    print("🧹 STARTING 3-PASS ORTHOGRAPHIC CLEANING (DICTIONARY ENHANCED)...")
    
    data = json.load(open(INPUT_FILE))
    
    # Process
    cleaned_data = recursive_clean(data)
    
    # Save
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(cleaned_data, f, indent=2)
        
    print(f"✨ Cleaning Complete.")
    print(f"💾 Saved Polished Atlas to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
