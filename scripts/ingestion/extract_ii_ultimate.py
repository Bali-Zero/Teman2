import fitz
import json
import re
import glob
import os

# Configuration
PDF_PATTERN = '/Users/antonellosiano/Desktop/nuzantara/lampiran/*I.I*.pdf'
OUTPUT_FILE = "/Users/antonellosiano/Desktop/nuzantara/reports/kbli_extraction/kbli_ii_masterpiece_v5_definitive.json"
BPS_REF_FILE = "/Users/antonellosiano/Desktop/nuzantara/reports/kbli_2025_reference.json"

# Column Centroids for I.I (Transport)
COLS = {
    "kode": 99,      
    "judul": 149,     
    "ruang": 209,     
    "skala": 275,     
    "risiko": 331,    
    "perizinan": 387, 
    "persyaratan": 458,
    "timeline": 538,  
    "kewajiban": 617, 
    "pb_umku": 697,
    "parameter": 759,
    "authority": 821
}

DEFAULT_AUTHORITY = "Menteri Perhubungan"

def load_bps_ref():
    if os.path.exists(BPS_REF_FILE):
        return json.load(open(BPS_REF_FILE))
    return {}

def extract_ii_ultimate():
    # Load BPS Rerefence
    bps_map = load_bps_ref()
    print(f"📚 LOADED BPS 2025 REFERENCE ({len(bps_map)} codes).")
    
    pdf_path = glob.glob(PDF_PATTERN)[0]
    doc = fitz.open(pdf_path)
    all_data = []
    
    current_record = None
    last_kbli = None
    
    print(f"🚀 STARTING I.I EXTRACTION (TRANSPORT) on {len(doc)} pages...")
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        words = page.get_text("words")
        # Ignore Header Area (Keep Y > 200 for data)
        words = [w for w in words if 200 < w[1] < 550] 
        
        lines = {}
        for w in words:
            y = round(w[1] / 5) * 5
            if y not in lines: lines[y] = []
            lines[y].append(w)
            
        sorted_y = sorted(lines.keys())
        
        for y in sorted_y:
            line_words = sorted(lines[y], key=lambda w: w[0])
            
            potential_code = None
            # Scan for code near X=99
            for w in line_words:
                if abs(w[0] - COLS["kode"]) < 25:
                    txt = w[4].strip()
                    if re.match(r'^\d{5}$', txt):
                        potential_code = txt
                        break
            
            if potential_code:
                # Save previous
                if current_record:
                    clean_record = {}
                    # For non-code fields, join words
                    for k, v in current_record.items():
                        if k == "kode":
                            clean_record[k] = v[0] if v else "" 
                        else:
                            clean_record[k] = " ".join(v).strip()
                        
                    if not clean_record.get("kode") and last_kbli:
                        clean_record["kode"] = last_kbli
                    
                    if clean_record.get("kode"):
                        # ENRICHMENT
                        code = clean_record["kode"]
                        clean_record["sektor"] = "SEKTOR PERHUBUNGAN (TRANSPORTASI)"
                        clean_record["source_lampiran"] = "I.I"
                        clean_record["page"] = page_num + 1
                        if not clean_record.get("authority"): clean_record["authority"] = DEFAULT_AUTHORITY
                        
                        # BPS VALIDATION
                        if code in bps_map:
                            clean_record["judul_bps"] = bps_map[code]["title"]
                            clean_record["validation_status"] = "MATCH_BPS_2025"
                        else:
                            clean_record["validation_status"] = "NOT_IN_BPS_2025"
                            
                        all_data.append(clean_record)
                        last_kbli = clean_record["kode"]
                
                # New Record
                current_record = {k: [] for k in COLS.keys()}
                current_record["kode"] = [potential_code] # Strictly set code
                last_kbli = potential_code
                
                for w in line_words:
                    if w[4] == potential_code: continue
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

    # Save last
    if current_record:
        clean_record = {}
        for k, v in current_record.items():
            if k == "kode":
                 clean_record[k] = v[0] if v else ""
            else:
                 clean_record[k] = " ".join(v).strip()

        if not clean_record.get("kode") and last_kbli: clean_record["kode"] = last_kbli
        
        if clean_record.get("kode"):
             code = clean_record["kode"]
             clean_record["sektor"] = "SEKTOR PERHUBUNGAN (TRANSPORTASI)"
             clean_record["source_lampiran"] = "I.I"
             clean_record["page"] = len(doc)
             if not clean_record.get("authority"): clean_record["authority"] = DEFAULT_AUTHORITY
             
             if code in bps_map:
                 clean_record["judul_bps"] = bps_map[code]["title"]
                 clean_record["validation_status"] = "MATCH_BPS_2025"
             else:
                 clean_record["validation_status"] = "NOT_IN_BPS_2025"
             
             all_data.append(clean_record)

    with open(OUTPUT_FILE, 'w') as f:
        json.dump({"data": all_data}, f, indent=2)
        
    print(f"✅ I.I EXTRACTED: {len(all_data)} records.")
    valid_count = len([d for d in all_data if d["validation_status"] == "MATCH_BPS_2025"])
    print(f"📊 BPS 2025 VALIDATION: {valid_count}/{len(all_data)} ({int(valid_count/len(all_data)*100)}%) Match Rate.")

if __name__ == "__main__":
    extract_ii_ultimate()
