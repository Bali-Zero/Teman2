#!/usr/bin/env python3
"""
Match Dropbox folders to CRM clients using Fly.io machine exec.
Outputs a verified CSV with real CRM IDs.
"""

import json
import subprocess
import csv
from difflib import SequenceMatcher
from pathlib import Path

# Dropbox folders from the CSV
DROPBOX_FOLDERS = [
    # CLIENT folders (need matching)
    ("@selesei Cetak (2027)", "CLIENT"),
    ("Adele Marthe", "CLIENT"),
    ("ADITYA", "CLIENT"),
    ("ANGEL", "CLIENT"),
    ("DATA ADI", "CLIENT"),
    ("DATA OM DIAN", "CLIENT"),
    ("DAVID", "CLIENT"),
    ("DINOK", "CLIENT"),
    ("DIRJEN", "CLIENT"),
    ("EPO", "CLIENT"),
    ("ERSA", "CLIENT"),
    ("EXTEND VISA", "CLIENT"),
    ("FILE ARIF", "CLIENT"),
    ("gendu", "CLIENT"),
    ("KANWIL - DIRJEN", "CLIENT"),
    ("LIA", "CLIENT"),
    ("MEGI", "CLIENT"),
    ("MERP", "CLIENT"),
    ("MUTASI", "CLIENT"),
    ("NOVI", "CLIENT"),
    ("ONLINE EXTEND", "CLIENT"),
    ("Pak Ari atau Mas Oman File PAJAK", "CLIENT"),
    ("Pembubaran PT ROSI MEDIA CONSULTING", "CLIENT"),
    ("PEMEGANG KITAS", "CLIENT"),
    ("YANTI", "CLIENT"),
    ("YOYOK", "CLIENT"),
    ("YUDI", "CLIENT"),
    # UTILITY folders (skip)
    ("Data Scan", "UTILITY"),
    ("Driver", "UTILITY"),
    ("File dikirim", "UTILITY"),
    ("Mobile Uploads", "UTILITY"),
    ("My PC (adhi-PC)", "UTILITY"),
    ("Other computers", "UTILITY"),
    ("PC", "UTILITY"),
    ("PC (2)", "UTILITY"),
    ("PC (5)", "UTILITY"),
    ("Screenshots", "UTILITY"),
]

# Folders that are likely CATEGORIES, not individual clients
CATEGORY_FOLDERS = {
    "DIRJEN",           # Government office
    "KANWIL - DIRJEN",  # Government office
    "EXTEND VISA",      # Service type
    "ONLINE EXTEND",    # Service type
    "MUTASI",           # Document type (transfer)
    "PEMEGANG KITAS",   # Category (KITAS holders)
    "Pembubaran PT ROSI MEDIA CONSULTING",  # Company dissolution docs
    "Pak Ari atau Mas Oman File PAJAK",     # Tax files for specific people
    "DATA ADI",         # Data folder for Adi
    "DATA OM DIAN",     # Data folder for Dian
    "FILE ARIF",        # Files for Arif
    "@selesei Cetak (2027)",  # Print project
}


def get_crm_clients():
    """Query CRM database via fly machine exec"""
    cmd = [
        "fly", "machine", "exec",
        "-a", "nuzantara-rag",
        "7843e55cdd3ed8",  # Running machine ID
        "python3", "-c", '''
import asyncio, asyncpg, os, json

async def get_clients():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    rows = await conn.fetch("""
        SELECT id, full_name, email
        FROM clients
        WHERE full_name IS NOT NULL
        AND length(full_name) > 2
        AND full_name !~ '^[0-9+]'
        AND full_name !~ '^[\\W\\d]+$'
        ORDER BY full_name
    """)
    await conn.close()
    return [{"id": r["id"], "name": r["full_name"], "email": r["email"]} for r in rows]

clients = asyncio.run(get_clients())
print(json.dumps(clients))
'''
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return []

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"Failed to parse: {result.stdout[:500]}")
        return []


def fuzzy_match(folder_name: str, crm_clients: list, threshold: float = 0.6) -> tuple:
    """Find best match using fuzzy string matching"""
    folder_clean = folder_name.upper().strip()

    # Quick exact match first
    for client in crm_clients:
        if client["name"].upper().strip() == folder_clean:
            return client["id"], client["name"], 1.0

    # Fuzzy match
    best_match = None
    best_score = 0

    for client in crm_clients:
        client_name = client["name"].upper().strip()

        # Try different matching strategies
        scores = [
            SequenceMatcher(None, folder_clean, client_name).ratio(),
            # Match first word
            SequenceMatcher(None, folder_clean.split()[0], client_name.split()[0]).ratio() if folder_clean.split() and client_name.split() else 0,
        ]

        score = max(scores)
        if score > best_score and score >= threshold:
            best_score = score
            best_match = client

    if best_match:
        return best_match["id"], best_match["name"], best_score
    return None, None, 0


def main():
    print("🔍 Querying CRM database...")
    crm_clients = get_crm_clients()
    print(f"   Found {len(crm_clients)} valid clients in CRM")

    if not crm_clients:
        print("❌ Failed to get CRM clients")
        return

    results = []

    for folder_name, category in DROPBOX_FOLDERS:
        if category == "UTILITY":
            results.append({
                "dropbox_folder": folder_name,
                "category": "UTILITY",
                "crm_client_id": "",
                "crm_client_name": "",
                "action": "SKIP",
                "notes": "Utility folder - do not migrate",
                "verified": "YES",
                "match_score": ""
            })
            continue

        # Check if it's a category folder
        if folder_name in CATEGORY_FOLDERS:
            results.append({
                "dropbox_folder": folder_name,
                "category": "CATEGORY",
                "crm_client_id": "",
                "crm_client_name": "",
                "action": "REVIEW",
                "notes": "Category folder - review contents manually",
                "verified": "NO",
                "match_score": ""
            })
            continue

        # Try to match to CRM
        crm_id, crm_name, score = fuzzy_match(folder_name, crm_clients)

        if crm_id:
            results.append({
                "dropbox_folder": folder_name,
                "category": "CLIENT",
                "crm_client_id": crm_id,
                "crm_client_name": crm_name,
                "action": "MIGRATE",
                "notes": f"Matched (score: {score:.2f})",
                "verified": "YES" if score >= 0.9 else "VERIFY",
                "match_score": f"{score:.2f}"
            })
        else:
            results.append({
                "dropbox_folder": folder_name,
                "category": "CLIENT",
                "crm_client_id": "",
                "crm_client_name": "",
                "action": "MANUAL",
                "notes": "No CRM match found - search manually",
                "verified": "NO",
                "match_score": ""
            })

    # Write CSV
    output_path = Path(__file__).parent / "dropbox_crm_VERIFIED.csv"
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "dropbox_folder", "category", "crm_client_id", "crm_client_name",
            "action", "notes", "verified", "match_score"
        ])
        writer.writeheader()
        writer.writerows(results)

    print(f"\n✅ Output written to: {output_path}")

    # Summary
    matched = sum(1 for r in results if r["action"] == "MIGRATE")
    review = sum(1 for r in results if r["action"] == "REVIEW")
    manual = sum(1 for r in results if r["action"] == "MANUAL")
    skip = sum(1 for r in results if r["action"] == "SKIP")

    print(f"\n📊 Summary:")
    print(f"   MIGRATE (matched): {matched}")
    print(f"   REVIEW (category): {review}")
    print(f"   MANUAL (no match): {manual}")
    print(f"   SKIP (utility):    {skip}")


if __name__ == "__main__":
    main()
