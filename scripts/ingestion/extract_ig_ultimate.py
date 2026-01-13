import fitz
import json
import re
import glob

# Find Lampiran I.G
PDF_PATH = glob.glob('/Users/antonellosiano/Desktop/nuzantara/lampiran/*I.G*.pdf')[0]
OUTPUT_FILE = "/Users/antonellosiano/Desktop/nuzantara/reports/kbli_extraction/kbli_ig_masterpiece_v5_definitive.json"

# Column Centroids for Landscape I.G (Trade)
# Based on Page 5 Analysis
COLS = {
    "kode": 110,      
    "judul": 165,     
    "ruang": 228,     
    "skala": 291,     
    "risiko": 353,    
    "perizinan": 411, 
    "persyaratan": 485,
    "timeline": 567,  
    "kewajiban": 646, 
    "pb_umku": 731,
    "parameter": 788,
    "authority": 852
}

DEFAULT_AUTHORITY = "Menteri Perdagangan"

def extract_ig_ultimate():
    doc = fitz.open(PDF_PATH)
    all_data = []
    
    current_record = None
    # "Torch" variable to handle page breaks (Code only appears on first page of mult-page record)
    last_kbli = None 
    
    print(f"🚀 STARTING I.G EXTRACTION (TRADE) on {len(doc)} pages...")
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        words = page.get_text("words")
        
        # Filter headers/footers
        words = [w for w in words if 80 < w[1] < 550]
        
        lines = {}
        for w in words:
            y = round(w[1] / 5) * 5
            if y not in lines: lines[y] = []
            lines[y].append(w)
            
        sorted_y = sorted(lines.keys())
        
        for y in sorted_y:
            line_words = sorted(lines[y], key=lambda w: w[0])
            
            # Check for KBLI Code (Scan line for matches near X=110)
            potential_code = None
            for w in line_words:
                if abs(w[0] - COLS["kode"]) < 25:
                    txt = w[4].strip()
                    if re.match(r'^\d{5}$', txt):
                        potential_code = txt
                        break
            
            if potential_code:
                # Save previous row
                if current_record:
                    # Clean up
                    clean_record = {}
                    for k, v in current_record.items():
                        clean_record[k] = " ".join(v).strip()
                    
                    # Inherit KBLI if missing (shouldn't happen with new code trigger)
                    if not clean_record.get("kode") and last_kbli:
                        clean_record["kode"] = last_kbli
                    
                    if clean_record.get("kode"):
                        clean_record["sektor"] = "SEKTOR PERDAGANGAN"
                        clean_record["source_lampiran"] = "I.G"
                        clean_record["page"] = page_num + 1 
                        if not clean_record.get("authority"): clean_record["authority"] = DEFAULT_AUTHORITY
                        all_data.append(clean_record)
                        last_kbli = clean_record["kode"]
                
                # Start new record
                current_record = {k: [] for k in COLS.keys()}
                current_record["kode"] = [potential_code]
                last_kbli = potential_code
                
                # Add rest of words in this line
                for w in line_words:
                    if w[4] == potential_code: continue # Skip code itself
                    x_mid = (w[0] + w[2]) / 2
                    best_col = min(COLS.keys(), key=lambda k: abs(COLS[k] - x_mid))
                    if abs(COLS[best_col] - x_mid) < 50:
                        current_record[best_col].append(w[4])
            
            elif current_record:
                 # Append to current record
                 for w in line_words:
                    x_mid = (w[0] + w[2]) / 2
                    best_col = min(COLS.keys(), key=lambda k: abs(COLS[k] - x_mid))
                    if abs(COLS[best_col] - x_mid) < 60: 
                        current_record[best_col].append(w[4])

    # Save last
    if current_record:
        clean_record = {}
        for k, v in current_record.items():
            clean_record[k] = " ".join(v).strip()
        
        if not clean_record.get("kode") and last_kbli:
             clean_record["kode"] = last_kbli

        if clean_record.get("kode"):
            clean_record["sektor"] = "SEKTOR PERDAGANGAN"
            clean_record["source_lampiran"] = "I.G"
            clean_record["page"] = len(doc)
            if not clean_record.get("authority"): clean_record["authority"] = DEFAULT_AUTHORITY
            all_data.append(clean_record)

    with open(OUTPUT_FILE, 'w') as f:
        json.dump({"data": all_data}, f, indent=2)
    
    print(f"✅ I.G COMPLETE. {len(all_data)} records saved. Last Code: {last_kbli}")

if __name__ == "__main__":
    extract_ig_ultimate()
