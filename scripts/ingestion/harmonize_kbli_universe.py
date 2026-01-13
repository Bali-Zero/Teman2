import json
import glob
import os
from difflib import SequenceMatcher

# Paths
BPS_REF = "/Users/antonellosiano/Desktop/nuzantara/reports/kbli_2025_reference.json"
REPORT_DIR = "/Users/antonellosiano/Desktop/nuzantara/reports/kbli_extraction/"
ID_V6_PATH = "/Users/antonellosiano/Desktop/nuzantara/scripts/ingestion/kbli_id_masterpiece_v6_integrated.json"
IF_V6_PATH = "/Users/antonellosiano/Desktop/nuzantara/reports/kbli_extraction/kbli_if_masterpiece_v6_clean.json"

OUTPUT_FILE = "/Users/antonellosiano/Desktop/nuzantara/reports/kbli_universal_atlas.json"

def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def load_all_extracted():
    all_data = []
    # 1. Standard Reports
    files = glob.glob(os.path.join(REPORT_DIR, "kbli_*_definitive.json"))
    
    # 2. Add ID V6 if exists
    if os.path.exists(ID_V6_PATH): files.append(ID_V6_PATH)
    else: print("⚠️ Warning: ID V6 not found, relying on glob.")
    
    # 3. Add IF V6 Clean (Override old I.F if present)
    if os.path.exists(IF_V6_PATH):
        # Remove old IF from files list to avoid dupes
        files = [f for f in files if "kbli_if_" not in f]
        files.append(IF_V6_PATH)
        
    print(f"📂 Loading {len(files)} Extracted Files...")
    for f in files:
        try:
            data = json.load(open(f))['data']
            for d in data:
                # Add source file metadata
                d['_source_file'] = os.path.basename(f)
                all_data.append(d)
        except Exception as e:
            print(f"❌ Error loading {f}: {e}")
            
    return all_data

def harmonize():
    print("🌍 STARTING KBLI HARMONIZATION (PP28 -> BPS 2025)...")
    
    # 1. Load Ground Truth (BPS 2025)
    bps_universe = json.load(open(BPS_REF))
    print(f"🎯 Target Universe: {len(bps_universe)} Codes (BPS 2025)")
    
    # 2. Load Source Data (PP 28)
    pp28_data = load_all_extracted()
    print(f"🧪 Source Data: {len(pp28_data)} Codes (PP 28)")
    
    # Index Source Data
    pp28_map = {d['kode']: d for d in pp28_data}
    
    final_universe = {}
    stats = {"Direct": 0, "Inherited": 0, "Unregulated": 0}
    
    # 3. Iterate BPS Universe
    for bps_code, bps_info in bps_universe.items():
        record = {
            "kbli_code": bps_code,
            "title": bps_info['title'],
            "source_std": "BPS 2025",
            "risk_data": None,
            "status": "UNREGULATED"
        }
        
        # Strategy A: Direct Match
        if bps_code in pp28_map:
            source = pp28_map[bps_code]
            record["risk_data"] = {k:v for k,v in source.items() if k not in ['kode', 'validation_status']}
            record["status"] = "REGULATED_DIRECT"
            record["inheritance_info"] = "Direct Match"
            stats["Direct"] += 1
            
        # Strategy B: Semantic Mapping (The "Future" Logic)
        else:
            # Look for Best Title Match in PP28 within same 2-digit Group
            # This drastically reduces search space and ensures relevance
            group_prefix = bps_code[:2]
            candidates = [d for d in pp28_data if d['kode'].startswith(group_prefix)]
            
            best_score = 0
            best_match = None
            
            for cand in candidates:
                # Compare Titles
                # Use source title (cand['judul']) vs target title (bps_info['title'])
                cand_title = cand.get('judul', '')
                score = similarity(bps_info['title'], cand_title)
                
                if score > best_score:
                    best_score = score
                    best_match = cand
            
            # Threshold for Inheritance: 60% (Adjustable)
            # "Furnitur dari Kayu" (PP28) vs "Industri Furnitur dari Kayu" (BPS) -> High Score
            if best_score > 0.60:
                record["risk_data"] = {k:v for k,v in best_match.items() if k not in ['kode', 'validation_status']}
                record["status"] = "REGULATED_INHERITED"
                record["inheritance_info"] = f"Inherited from {best_match['kode']} ({int(best_score*100)}% match)"
                stats["Inherited"] += 1
            else:
                # Truly Unregulated (Finance, Edu, or just unique)
                record["status"] = "UNREGULATED_OR_MISSING"
                stats["Unregulated"] += 1
                
        final_universe[bps_code] = record

    # 4. Save Universal Atlas
    with open(OUTPUT_FILE, 'w') as f:
        json.dump({"meta": stats, "data": final_universe}, f, indent=2)
        
    print(f"✅ HARMONIZATION COMPLETE.")
    print(f"📊 Stats:")
    print(f"   - Direct Match: {stats['Direct']}")
    print(f"   - Inherited (Mapped): {stats['Inherited']}")
    print(f"   - Unregulated (Gap): {stats['Unregulated']}")
    print(f"💾 Saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    harmonize()
