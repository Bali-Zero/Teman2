import csv
import json
import re
import sys
from pathlib import Path
from typing import List, Dict, Any

# Configure logging
import logging
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def clean_text(text: str) -> str:
    """
    Cleans OCR artifacts from text:
    1. Fixes hyphenation (e.g. 'Peng- usahaan' -> 'Pengusahaan')
    2. Removes noise characters
    3. Normalizes whitespace
    """
    if not text:
        return ""
    
    # 1. Fix aggressive hyphenation with spaces (e.g., 'Peng- usahaan' -> 'Pengusahaan')
    # Use 2 pass approach: 
    # Pass A: "Word- word" -> "Wordword"
    text = re.sub(r'(\w+)-\s+(\w+)', r'\1\2', text)
    # Pass B: "Word -word" -> "Wordword" (sometimes space is before hyphen)
    text = re.sub(r'(\w+)\s+-(\w+)', r'\1\2', text)
    
    # 2. Fix standard hyphens at end of lines without space (if any remain)
    text = text.replace('-\n', '')
    
    # 3. Remove column references like (1), (2) often found in header rows
    # Be careful not to remove valid lists like (1) Doing x...
    # We assume distinct floating numbers are bad, but numbered lists are usually "1." or "(1)" at start
    
    # 4. Remove :unselected: / :selected: artifacts (handled in extraction, but clean text should imply removal if meaningless)
    text = text.replace(":unselected:", "").replace(":selected:", "")
    
    # 5. Normalize whitespace
    text = " ".join(text.split())
    
    return text.strip()

def parse_business_scale(scale_text: str) -> Dict[str, bool]:
    """
    Parses 'Skala Usaha' column looking for :selected: markers or text indications.
    Input format often: "- Mikro :selected: - Kecil :unselected: ..."
    """
    scales = {
        "mikro": False,
        "kecil": False,
        "menengah": False,
        "besar": False
    }
    
    scale_text_lower = scale_text.lower()
    
    # Mapping of Indonesian terms to keys
    mapping = {
        "mikro": "mikro",
        "kecil": "kecil",
        "mene- ngah": "menengah", # OCR fail specific
        "mene-ngah": "menengah",
        "menengah": "menengah",
        "besar": "besar"
    }

    # If we have explicit markers
    if ":selected:" in scale_text_lower:
        # This is tricky because the text is a blob. 
        # Usually it's "- Mikro :selected:" or "- Mikro\n:selected:"
        # We need to associate the marker with the closest preceding label.
        
        # Simple heuristic: Split by '-' bullet points?
        # Let's try splitting by known keywords and looking ahead
        
        # Normalized text for scanning
        text_norm = scale_text_lower.replace("\n", " ")
        
        for label_raw, key in mapping.items():
            # Regex to find Label followed optionally by junk then :selected:
            # We look for "Mikro ... :selected:" vs "Mikro ... :unselected:"
            # The range of search is limited to avoid grabbing the status of the next item
            
            # Construct a regex that finds the label, then looks ahead specifically for the markers
            # We want the *nearest* marker after the label.
            
            pattern = re.escape(label_raw) + r".*?(:selected:|:unselected:)"
            match = re.search(pattern, text_norm)
            if match:
                marker = match.group(1)
                if marker == ":selected:":
                    scales[key] = True
    else:
        # Fallback: if no markers, assume all listed text is positive? 
        # Or maybe it's just text "Mikro, Kecil"
        for label_raw, key in mapping.items():
            if label_raw in scale_text_lower:
                scales[key] = True
                
    return scales

def parse_risk_level(risk_text: str) -> str:
    """Standardizes risk level."""
    normalized = clean_text(risk_text).upper()
    valid_risks = ["RENDAH", "MENENGAH RENDAH", "MENENGAH TINGGI", "TINGGI"]
    
    # OCR fixes
    if "MENENGAH" in normalized and "TINGGI" in normalized:
        return "MENENGAH TINGGI"
    if "MENENGAH" in normalized and "RENDAH" in normalized:
        return "MENENGAH RENDAH"
    
    for v in valid_risks:
        if v == normalized:
            return v
            
    return normalized # Return raw if no match

def convert_csv_to_masterpiece(csv_path: str, output_path: str):
    logger.info(f"Processing {csv_path}...")
    
    masterpiece_data = []
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            # State for merging multi-line rows
            active_record = None
            
            for row in reader:
                # 1. Inspect KBLI Code
                kbli_code_raw = row.get("Kode KBLI", "").strip()
                
                # Check if this row initiates a new KBLI
                # Azure CSV sometimes drops leading zero (e.g. 2140 instead of 02140)
                kbli_match = re.search(r'\b\d{4,5}\b', kbli_code_raw)
                
                if kbli_match:
                    code_str = kbli_match.group(0)
                    if len(code_str) == 4:
                        code_str = "0" + code_str
                        
                    # --- NEW RECORD DETECTED ---
                    # If we have an active record pending, save it first
                    if active_record:
                        masterpiece_data.append(active_record)
                        
                    # Initialize new record
                    active_record = {
                        "kbli_code": code_str,
                        "title": row.get("Judul KBLI", ""),
                        "scope": row.get("Ruang Lingkup", ""),
                        "risk_level_raw": row.get("Tingkat Risiko", ""), # Temp storage for merging
                        "business_scale_raw": row.get("Skala Usaha", ""), # Temp storage
                        "licensing_requirements": {
                             "permit_type": row.get("Perizinan Berusaha", ""),
                             "requirements_list": row.get("Persyaratan", ""),
                             "durations": row.get("Jangka Waktu", ""),
                             "obligations": row.get("Kewajiban", ""),
                        },
                        "authority": row.get("Kewenangan", ""),
                        "parameters": row.get("Parameter", ""),
                        "umku_raw": row.get("PB UMKU", ""),
                        # Append raw lines for debugging/merging
                        "_raw_rows": 1
                    }
                    
                    # Handle multiple KBLIs in one row (Rare edge case in Azure output?)
                    # If there are multiple, we might need cloning, but usually Azure splits them.
                    # For now, assume 'primary' match is key.

                elif active_record:
                    # --- CONTINUATION ROW ---
                    # Merge content into active_record
                    
                    # Helper for appending with space if not empty
                    def append_field(key, value):
                        if value and value.strip():
                            # naive space join, we clean later
                            return (active_record[key] + " " + value).strip()
                        return active_record[key]
                    
                    active_record["title"] = append_field("title", row.get("Judul KBLI", ""))
                    active_record["scope"] = append_field("scope", row.get("Ruang Lingkup", ""))
                    active_record["authority"] = append_field("authority", row.get("Kewenangan", ""))
                    active_record["parameters"] = append_field("parameters", row.get("Parameter", ""))
                    active_record["umku_raw"] = append_field("umku_raw", row.get("PB UMKU", ""))
                    
                    # Merge structured fields
                    active_record["risk_level_raw"] += " " + row.get("Tingkat Risiko", "")
                    active_record["business_scale_raw"] += " " + row.get("Skala Usaha", "")
                    
                    # Merge nested dictionary
                    lic = active_record["licensing_requirements"]
                    lic["permit_type"] = (lic["permit_type"] + " " + row.get("Perizinan Berusaha", "")).strip()
                    lic["requirements_list"] = (lic["requirements_list"] + " " + row.get("Persyaratan", "")).strip()
                    lic["durations"] = (lic["durations"] + " " + row.get("Jangka Waktu", "")).strip()
                    lic["obligations"] = (lic["obligations"] + " " + row.get("Kewajiban", "")).strip()
                    
                    active_record["_raw_rows"] += 1
                
                else:
                    # No active record and no KBLI code -> Trash/Noise or Header continuation before first data
                    continue

            # Don't forget the last record
            if active_record:
                masterpiece_data.append(active_record)

            # --- POST-PROCESSING ---
            # Now we clean and parse the consolidated fields
            for item in masterpiece_data:
                item["title"] = clean_text(item["title"])
                item["scope"] = clean_text(item["scope"])
                item["authority"] = clean_text(item["authority"])
                item["parameters"] = clean_text(item["parameters"])
                item["umku_raw"] = clean_text(item["umku_raw"])
                
                # Parse Risk & Scale
                item["risk_level"] = parse_risk_level(item.pop("risk_level_raw"))
                item["business_scale"] = parse_business_scale(item.pop("business_scale_raw"))
                
                # Clean Nested
                lic = item["licensing_requirements"]
                lic["permit_type"] = clean_text(lic["permit_type"])
                lic["requirements_list"] = clean_text(lic["requirements_list"])
                lic["durations"] = clean_text(lic["durations"])
                lic["obligations"] = clean_text(lic["obligations"])

    except Exception as e:
        logger.error(f"Failed to parse CSV: {e}")
        # raise e # Debugging
        return

    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(masterpiece_data, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Successfully converted {len(masterpiece_data)} records to {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        # Default behavior for proactive verification (Hardcoded to Azure Extract)
        input_csv = "/Users/antonellosiano/Desktop/lampiran_IC_FINAL.csv"
        output_json = "/Users/antonellosiano/Desktop/nuzantara/reports/kbli_extraction/kbli_extraction_final_v2.json"
        
        print(f"Running in Zero-Conf Mode.")
        print(f"Input: {input_csv}")
        print(f"Output: {output_json}")

        if Path(input_csv).exists():
            convert_csv_to_masterpiece(input_csv, output_json)
        else:
            print(f"Error: Input file at {input_csv} not found.")
    else:
        convert_csv_to_masterpiece(sys.argv[1], sys.argv[2])
