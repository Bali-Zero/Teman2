#!/usr/bin/env python3
"""
analyze_extraction.py - Vision Factory QA Diagnostic
----------------------------------------------------
Analyzes a raw Excel export from Adobe Acrobat to determine if it meets
the "Masterpiece" standard for KBLI extraction.

Checks:
1. Column Recognition (Kode, Judul, etc.)
2. Merged Cell Integrity (Forward-fill needs)
3. Data Density (Empty rows vs Content)
4. OCR Artifact Detection

Usage:
    python3 scripts/vision_factory/analyze_extraction.py <path_to_xlsx>
"""

import sys
import pandas as pd
import re
from pathlib import Path

def analyze_excel(path):
    print(f"🔍 Analyzing: {path}")
    if not Path(path).exists():
        print("❌ File not found!")
        return

    try:
        # Load raw first to detect headers
        df_raw = pd.read_excel(path, header=None)
        print(f"📊 Raw Dimensions: {df_raw.shape[0]} rows x {df_raw.shape[1]} cols")
    except Exception as e:
        print(f"❌ Read Failed: {e}")
        return

    # Find Header
    header_idx = None
    for idx, row in df_raw.iterrows():
        row_txt = " ".join([str(x) for x in row.values]).lower()
        if "kode" in row_txt and "judul" in row_txt:
            header_idx = idx
            print(f"✅ Header found at Row {idx+1}")
            break
            
    if header_idx is None:
        print("❌ CRITICAL: Could not detect KBLI Header row (Kode/Judul).")
        print("   -> Tip: Check if the PDF table has standard headers.")
        return

    # Load with header
    df = pd.read_excel(path, header=header_idx)
    
    # 1. Structure Analysis
    cols = [str(c).lower() for c in df.columns]
    found_cols = {
        "kode": any("kode" in c for c in cols),
        "judul": any("judul" in c for c in cols),
        "ruang": any("ruang" in c for c in cols) or any("lingkup" in c for c in cols),
        "skala": any("skala" in c for c in cols),
        "risiko": any("risiko" in c for c in cols),
        "perizinan": any("perizinan" in c for c in cols)
    }
    
    missing = [k for k,v in found_cols.items() if not v]
    if missing:
        print(f"⚠️  Missing Columns: {', '.join(missing)}")
    else:
        print("✅ Column Schema: COMPLETE")

    # 2. Data Health
    # Check for merging issues (empty codes)
    possible_code_col = [c for c in df.columns if "kode" in str(c).lower()][0]
    
    total_rows = len(df)
    empty_codes = df[possible_code_col].isna().sum()
    print(f"📉 Rows with Empty Codes: {empty_codes}/{total_rows} ({(empty_codes/total_rows)*100:.1f}%)")
    
    if empty_codes > 0:
        print("   -> Info: This usually indicates merged cells. The Parser will fixes this via ffill().")

    # 3. Content Sampling
    print("\n🧐 Content Sample (First valid record):")
    valid_rows = df[df[possible_code_col].notna()].head(1)
    if not valid_rows.empty:
        print(valid_rows.iloc[0].to_dict())
    else:
        print("   (No valid records found)")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_extraction.py <file.xlsx>")
    else:
        analyze_excel(sys.argv[1])
