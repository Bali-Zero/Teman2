import csv
import json
import os
import sys
import re
import traceback

def convert_csv_to_masterpiece(csv_path: str, output_path: str):
    print(f"INFO: Processing {csv_path}...")
    
    if not os.path.exists(csv_path):
        print(f"ERROR: Input CSV file not found: {csv_path}")
        return

    masterpiece_data = []
    
    try:
        with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
            # Read header first to validation
            # sample = f.read(1024)
            # f.seek(0)
            # has_header = csv.Sniffer().has_header(sample)
            
            # Force standard CSV processing (comma delimited)
            reader = csv.DictReader(f, delimiter=',')
            headers = reader.fieldnames
            print(f"INFO: CSV Headers detected: {headers}")
            
            if "Kode KBLI" not in headers:
                print("CRITICAL ERROR: Column 'Kode KBLI' missing from CSV!")
                # Try to map if possible, or abort? 
                # For now abort as this is critical
                return

            # State for merging multi-line rows
            active_record = None
            row_count = 0
            
            for row in reader:
                try:
                    row_count += 1
                    # 0. Pre-process Merged Rows
                    rows_to_process = []
                    
                    kbli_code_raw_check = str(row.get("Kode KBLI") or "").strip()
                    
                    if "(2)" in kbli_code_raw_check:
                        code_parts = kbli_code_raw_check.split("(2)")
                        valid_parts = [p for p in code_parts if p.strip()]
                        
                        if len(valid_parts) > 1:
                            # TRUE MERGE DETECTED
                            # print(f"[DEBUG] Splitting Merged Row: {kbli_code_raw_check}")
                            delimiters = {
                                "Kode KBLI": "(2)",
                                "Judul KBLI": "(3)",
                                "Ruang Lingkup": "(4)",
                                "Skala Usaha": "(5)",
                                "Tingkat Risiko": "(6)",
                                "Perizinan Berusaha": "(7)",
                                "Persyaratan": "(8)",
                                "Jangka Waktu Penerbitan": "(9)", # Adjusted key from "Jangka Waktu"
                                "Jangka Waktu": "(9)",            # Legacy support
                                "Kewajiban": "(10)",
                                "PB UMKU": "(11)",
                                "Parameter": "(12)"
                            }
                            
                            num_records = len(code_parts)
                            
                            for i in range(num_records):
                                new_row_split = {}
                                for key, val in row.items():
                                    val_str = str(val or "")
                                    if key in delimiters:
                                        delim = delimiters[key]
                                        if val_str and delim in val_str:
                                            parts = val_str.split(delim)
                                            if i < len(parts):
                                                new_row_split[key] = parts[i].strip()
                                            elif len(parts) == 1:
                                                new_row_split[key] = parts[0].strip()
                                            else:
                                                new_row_split[key] = ""
                                        else:
                                            new_row_split[key] = val_str
                                    else:
                                        new_row_split[key] = val_str
                                rows_to_process.append(new_row_split)
                        else:
                            # NOISE DETECTED
                            row["Kode KBLI"] = valid_parts[0].strip() if valid_parts else kbli_code_raw_check
                            rows_to_process.append(row)
                    else:
                        rows_to_process.append(row)
                    
                    # Process Expanded Rows
                    for row_proc in rows_to_process:
                        kbli_code = str(row_proc.get("Kode KBLI") or "").strip()
                        
                        # Basic Regex for 5-digit code
                        kbli_match = re.search(r'(\d{5})', kbli_code)
                        
                        if kbli_match:
                            # Flush previous record if exists
                            if active_record:
                                masterpiece_data.append(active_record)
                                
                            # NEW RECORD
                            code = kbli_match.group(1)
                            title = str(row_proc.get("Judul KBLI") or "").strip()
                            scope = str(row_proc.get("Ruang Lingkup") or "").replace("\n", " ").strip()
                            
                            active_record = {
                                "kbli_code": code,
                                "title": title,
                                "description": scope,
                                "source_file": os.path.basename(csv_path),
                                "risk_level": str(row_proc.get("Tingkat Risiko") or "").strip(),
                                "business_scale": str(row_proc.get("Skala Usaha") or "").strip(),
                                "authority": str(row_proc.get("Kewenangan") or "").strip(),
                                "licensing_requirements": str(row_proc.get("Perizinan Berusaha") or "").strip(),
                                "requirements": str(row_proc.get("Persyaratan") or "").strip(),
                                "obligations": str(row_proc.get("Kewajiban") or "").strip(),
                                "issuance_period": str(row_proc.get("Jangka Waktu") or "").strip(),
                                "extraction_mode": "miner_u_csv_refined"
                            }
                        else:
                            # APPEND TO PREVIOUS (Content Overflow)
                            if active_record:
                                # Append to description/scope if it looks like text continuation
                                extra_scope = str(row_proc.get("Ruang Lingkup") or "").strip()
                                if extra_scope:
                                    active_record["description"] += f" {extra_scope}"
                                
                                # Append to Title if needed
                                extra_title = str(row_proc.get("Judul KBLI") or "").strip()
                                if extra_title and not active_record["title"].endswith(extra_title):
                                     active_record["title"] += f" {extra_title}"

                except Exception as row_e:
                    print(f"WARNING: Error processing row {row_count}: {row_e}")
                    continue

            # Flush last record
            if active_record:
                masterpiece_data.append(active_record)
                
    except Exception as e:
        print(f"CRITICAL ERROR in CSV Processing: {e}")
        # traceback.print_exc()
        return

    print(f"INFO: Extraction finished. Found {len(masterpiece_data)} records.")
    
    # Save output
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(masterpiece_data, f, indent=2, ensure_ascii=False)
        print(f"SUCCESS: Saved to {output_path}")
    except Exception as e:
         print(f"ERROR: Failed to save JSON output: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        # Fallback for testing
        print("Usage: python3 mineru_to_masterpiece.py <input.csv> <output.json>")
        # HARDCODED TEST PATHS FOR USER CONVENIENCE
        input_csv = "/Users/antonellosiano/Desktop/nuzantara/2.7 Lampiran I.G PP Nomor 28 Tahun 2025 (I.G.1-341)_consolidated.csv"
        output_json = "/Users/antonellosiano/Desktop/nuzantara/reports/kbli_extraction/kbli_lampiran_ig_final.json"
        
        # Check if user file exists, if not use dummy?
        # No, just print info
        if os.path.exists(input_csv):
             print(f"Running Default Test on {input_csv}")
             convert_csv_to_masterpiece(input_csv, output_json)
    else:
        convert_csv_to_masterpiece(sys.argv[1], sys.argv[2])
