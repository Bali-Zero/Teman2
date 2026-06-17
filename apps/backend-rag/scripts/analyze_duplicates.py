#!/usr/bin/env python3
import re
from collections import Counter


def analyze_report(report_path):
    print(f"Reading report from {report_path}...")
    with open(report_path, encoding="utf-8") as f:
        content = f.read()

    blocks = content.split("----------------------------------\n")
    # The first block contains the header, skip it.
    # The last block might be empty, skip it.
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

    total_records = len(records)
    print(f"Parsed {total_records} records.")

    # 1. Check duplicate Google Drive IDs
    drive_ids = [r["file_id"] for r in records]
    drive_id_counts = Counter(drive_ids)
    duplicate_drive_ids = {id_: count for id_, count in drive_id_counts.items() if count > 1}

    # 2. Check duplicate filenames per client (exact same name + size for the same client)
    client_file_keys = [(r["client_id"], r["file_name"], r["file_size"]) for r in records]
    client_file_counts = Counter(client_file_keys)
    duplicate_client_files = {k: count for k, count in client_file_counts.items() if count > 1}

    # 3. Check duplicate filenames + sizes globally (same filename + same size across different clients)
    global_file_keys = [(r["file_name"], r["file_size"]) for r in records]
    global_file_counts = Counter(global_file_keys)
    duplicate_global_files = {k: count for k, count in global_file_counts.items() if count > 1}

    # 4. Check duplicate filenames globally regardless of size
    global_name_counts = Counter([r["file_name"] for r in records])
    most_common_names = global_name_counts.most_common(15)

    print("\n=== RESULTS ===")
    print(f"Total Discovered Files: {total_records}")
    print(f"Unique Google Drive IDs: {len(drive_id_counts)}")
    print(
        f"Duplicate Google Drive IDs (same file ID listed multiple times): {len(duplicate_drive_ids)}"
    )
    print(
        f"Duplicate Filename+Size for the SAME client: {len(duplicate_client_files)} cases (totaling {sum(duplicate_client_files.values())} files)"
    )
    print(
        f"Duplicate Filename+Size GLOBALLY (across different clients): {len(duplicate_global_files)} patterns"
    )

    print("\n--- Most Common Filenames (Top 15) ---")
    for name, count in most_common_names:
        print(f"  - '{name}': {count} occurrences")

    # Print details of a few duplicate cases per client
    if duplicate_client_files:
        print("\n--- Examples of Duplicates for the Same Client (Top 5) ---")
        sorted_dup_clients = sorted(
            duplicate_client_files.items(), key=lambda x: x[1], reverse=True
        )
        for (client_id, name, size), count in sorted_dup_clients[:5]:
            client_name = next(r["client_name"] for r in records if r["client_id"] == client_id)
            print(
                f"  Client {client_id} ({client_name}): '{name}' ({size} bytes) appears {count} times"
            )


import os

if __name__ == "__main__":
    report_path = os.path.expanduser("~/Desktop/nuzantara_drive_scan_report.txt")
    analyze_report(report_path)
