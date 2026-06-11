#!/usr/bin/env python3
import re
import time


def deduplicate_report(input_path, output_path):
    print(f"Reading raw report from {input_path}...")
    with open(input_path, encoding="utf-8") as f:
        content = f.read()

    blocks = content.split("----------------------------------\n")
    records = []

    # Regex to parse record details
    client_re = re.compile(r"Client:\s+(\d+)\s+-\s+(.+)")
    path_re = re.compile(r"\s+Percorso Fisico:\s+(.+)")
    file_re = re.compile(r"\s+File:\s+(.+)")
    size_re = re.compile(r"\s+Dimensione:\s+(\d+)\s+bytes")
    id_re = re.compile(r"\s+Google Drive ID:\s+(\S+)")

    for block in blocks:
        block = block.strip()
        if not block or "REPORT DI SCANSIONE" in block:
            continue

        client_match = client_re.search(block)
        path_match = path_re.search(block)
        file_match = file_re.search(block)
        size_match = size_re.search(block)
        id_match = id_re.search(block)

        if client_match and file_match and id_match:
            records.append(
                {
                    "client_id": int(client_match.group(1)),
                    "client_name": client_match.group(2).strip(),
                    "subfolder": path_match.group(1).strip() if path_match else "Root",
                    "file_name": file_match.group(1).strip(),
                    "file_size": int(size_match.group(1)) if size_match else 0,
                    "file_id": id_match.group(1).strip(),
                }
            )

    total_raw = len(records)

    # 1. Deduplicate by Google Drive ID
    seen_ids = set()
    dedup_id_records = []
    for r in records:
        if r["file_id"] not in seen_ids:
            seen_ids.add(r["file_id"])
            dedup_id_records.append(r)

    total_after_id = len(dedup_id_records)

    # 2. Deduplicate by Filename + Size per Client
    seen_client_files = set()
    final_records = []
    for r in dedup_id_records:
        key = (r["client_id"], r["file_name"], r["file_size"])
        if key not in seen_client_files:
            seen_client_files.add(key)
            final_records.append(r)

    total_final = len(final_records)

    print("Deduplication summary:")
    print(f"  Raw records: {total_raw}")
    print(
        f"  After unique Drive ID filter: {total_after_id} (removed {total_raw - total_after_id} ID duplicates)"
    )
    print(
        f"  After Client Filename+Size filter: {total_final} (removed {total_after_id - total_final} name+size duplicates for same client)"
    )
    print(f"  Total duplicates removed: {total_raw - total_final}")

    # Write deduped report
    with open(output_path, "w", encoding="utf-8") as rf:
        rf.write("=================================================================\n")
        rf.write(" REPORT DI SCANSIONE GOOGLE DRIVE PROFONDO - DE-DUPLICATO \n")
        rf.write("=================================================================\n\n")
        rf.write(f"Data Report: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        rf.write(f"File totali analizzati (grezzi): {total_raw}\n")
        rf.write(f"File totali dopo de-duplicazione: {total_final}\n")
        rf.write(
            f"Duplicati rimossi (ID identici o stesso Nome+Dimensione per client): {total_raw - total_final}\n\n"
        )

        if final_records:
            rf.write("Dettaglio dei file orfani trovati (De-duplicati):\n")
            rf.write("----------------------------------\n")
            for file in final_records:
                rf.write(f"Client: {file['client_id']} - {file['client_name']}\n")
                rf.write(f"  Percorso Fisico: {file['subfolder']}\n")
                rf.write(f"  File: {file['file_name']}\n")
                rf.write(f"  Dimensione: {file['file_size']} bytes\n")
                rf.write(f"  Google Drive ID: {file['file_id']}\n")
                rf.write("  Stato nel DB: MANCANTE\n")
                rf.write("----------------------------------\n")
        else:
            rf.write("Ottimo! Nessun file orfano trovato.\n")

    print(f"Deduped report written successfully to {output_path}!")


import os

if __name__ == "__main__":
    deduplicate_report(
        os.path.expanduser("~/Desktop/nuzantara_drive_scan_report.txt"),
        os.path.expanduser("~/Desktop/nuzantara_drive_scan_report_deduped.txt"),
    )
