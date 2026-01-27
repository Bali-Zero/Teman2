#!/usr/bin/env python3
"""
adobe_extract.py - The "Vision Factory" Export Tool
---------------------------------------------------
This script uses AppleScript via osascript to control Adobe Acrobat Pro on macOS.
It iterates through PDF files in a source directory and converts them to Excel (.xlsx).

Usage:
    python3 scripts/vision_factory/adobe_extract.py [source_dir] [output_dir]

Requirements:
    - macOS
    - Adobe Acrobat Pro installed and running
    - Accessibility permissions granted to Terminal/MoltBot
"""

import sys
import subprocess
import time
from pathlib import Path


def log(msg, level="INFO"):
    print(f"[{level}] {msg}")


def run_applescript(script):
    """Run raw AppleScript using osascript."""
    proc = subprocess.Popen(
        ["osascript", "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stdout, stderr = proc.communicate(script)
    if proc.returncode != 0:
        log(f"AppleScript Error: {stderr}", "ERROR")
        return False
    return True


def convert_pdf_to_xlsx(pdf_path, output_path):
    """
    Tells Adobe Acrobat to open PDF and save as XLSX.
    Note: The conversion format string "com.adobe.acrobat.xlsx" is standard for modern Acrobat Pro.
    """
    abs_pdf = Path(pdf_path).resolve()
    abs_out = Path(output_path).resolve()

    # AppleScript to control Acrobat
    script = f'''
    tell application "Adobe Acrobat"
        activate
        open POSIX file "{abs_pdf}"
        
        -- Wait for file to open (simple delay, can be improved)
        delay 2
        
        set activeDoc to active doc
        
        -- Save as XLSX
        -- Note: path must be HFS style or POSIX file syntax might accept posix path depending on version.
        -- We use "save to file" with conversion.
        
        save activeDoc to file "{abs_out}" using conversion "com.adobe.acrobat.xlsx"
        
        close activeDoc
    end tell
    '''

    log(f"Converting: {abs_pdf.name} -> {abs_out.name}")
    start_time = time.time()

    success = run_applescript(script)

    duration = time.time() - start_time
    if success:
        log(f"Success! took {duration:.2f}s", "SUCCESS")
    else:
        log(f"Failed to convert {abs_pdf.name}", "ERROR")
    return success


def main():
    if len(sys.argv) < 3:
        # Default behavior for Nuzantara structure
        source_path = Path("lampiran")
        output_target = Path("lampiran/xlsx_source")
    else:
        source_path = Path(sys.argv[1])
        output_target = Path(sys.argv[2])

    if not source_path.exists():
        log(f"Source path not found: {source_path}", "ERROR")
        sys.exit(1)

    pdfs = []
    output_is_dir = True

    if source_path.is_file():
        if source_path.suffix.lower() == ".pdf":
            pdfs = [source_path]
            # If output has .xlsx extension, treat as file target
            if output_target.suffix.lower() == ".xlsx":
                output_is_dir = False
                # Ensure parent dir exists (NOT the file itself!)
                output_target.parent.mkdir(parents=True, exist_ok=True)
                # Remove if exists as directory (bug fix)
                if output_target.is_dir():
                    import shutil

                    shutil.rmtree(output_target)
            else:
                output_target.mkdir(parents=True, exist_ok=True)
        else:
            log("Source file is not a PDF.", "ERROR")
            sys.exit(1)
    elif source_path.is_dir():
        output_target.mkdir(parents=True, exist_ok=True)
        pdfs = list(source_path.glob("*.pdf"))

    if not pdfs:
        log("No PDF files found.", "WARNING")
        return

    log(f"Found {len(pdfs)} PDF(s). Starting Vision Factory...", "HEADER")

    success_count = 0

    for pdf in pdfs:
        if output_is_dir:
            xlsx_name = pdf.stem + ".xlsx"
            xlsx_path = output_target / xlsx_name
        else:
            # Single file mode uses explicit target
            xlsx_path = output_target

        if (
            xlsx_path.exists() and output_is_dir
        ):  # Overwrite logic for single file? default to standard behavior
            log(f"Skipping {pdf.name} (Output exists)", "INFO")
            success_count += 1
            continue

        if convert_pdf_to_xlsx(pdf, xlsx_path):
            success_count += 1

        # small buffer
        time.sleep(1)

    log(
        f"Vision Factory Run Complete. {success_count}/{len(pdfs)} processed.", "HEADER"
    )


if __name__ == "__main__":
    main()
