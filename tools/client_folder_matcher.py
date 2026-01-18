#!/usr/bin/env python3
"""
Client Folder Matcher

Matches Dropbox folder names to CRM client records using fuzzy matching.
Uses the manually identified list of 37 Dropbox folders.
"""

import json
from datetime import datetime
from difflib import SequenceMatcher

# Lista di 37 cartelle Dropbox identificate manualmente
DROPBOX_FOLDERS = [
    "@selesei Cetak (2027)",
    "Adele Marthe",
    "ADITYA",
    "ANGEL",
    "DATA ADI",
    "DATA OM DIAN",
    "Data Scan",
    "DAVID",
    "DINOK",
    "DIRJEN",
    "Driver",
    "EPO",
    "ERSA",
    "EXTEND VISA",
    "FILE ARIF",
    "File dikirim",
    "gendu",
    "KANWIL - DIRJEN",
    "LIA",
    "MEGI",
    "MERP",
    "Mobile Uploads",
    "MUTASI",
    "My PC (adhi-PC)",
    "NOVI",
    "ONLINE EXTEND",
    "Other computers",
    "Pak Ari atau Mas Oman File PAJAK",
    "PC",
    "PC (2)",
    "PC (5)",
    "Pembubaran PT ROSI MEDIA CONSULTING",
    "PEMEGANG KITAS",
    "Screenshots",
    "YANTI",
    "YOYOK",
    "YUDI",
]

# Cartelle di processo (non clienti)
PROCESS_FOLDERS = [
    "###PERPANJANAN...A LANSIA###",
    "###DRAFT PROCESS###",
    "###ON PROCESS###",
]

# Cartelle utility (non clienti)
UTILITY_FOLDERS = [
    "Data Scan",
    "Driver",
    "File dikirim",
    "Mobile Uploads",
    "My PC (adhi-PC)",
    "Other computers",
    "PC",
    "PC (2)",
    "PC (5)",
    "Screenshots",
]


def similarity(a: str, b: str) -> float:
    """Calculate similarity ratio between two strings"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def categorize_folders():
    """Categorize Dropbox folders into clients, process, and utility"""

    categories = {
        "potential_clients": [],
        "process_folders": PROCESS_FOLDERS.copy(),
        "utility_folders": UTILITY_FOLDERS.copy(),
        "unknown": [],
    }

    for folder in DROPBOX_FOLDERS:
        if folder in PROCESS_FOLDERS or folder in UTILITY_FOLDERS:
            continue

        # Check if it looks like a client folder
        # Heuristics: personal names, single words, company names
        if (
            folder.startswith("###")  # Process folder
            or folder.lower() in ["driver", "data scan", "screenshots"]  # Utility
            or "PC" in folder.upper()  # Computer sync
            or "uploads" in folder.lower()  # Auto uploads
        ):
            if folder not in categories["utility_folders"]:
                categories["utility_folders"].append(folder)
        else:
            categories["potential_clients"].append(folder)

    return categories


def fuzzy_match_clients(crm_clients: list, threshold: float = 0.6):
    """
    Fuzzy match Dropbox folders to CRM client names

    Args:
        crm_clients: List of dicts with 'id' and 'name' keys
        threshold: Minimum similarity score (0-1)

    Returns:
        List of matches with scores
    """
    categories = categorize_folders()
    matches = []

    for folder in categories["potential_clients"]:
        best_match = None
        best_score = 0

        for client in crm_clients:
            score = similarity(folder, client["name"])
            if score > best_score:
                best_score = score
                best_match = client

        match_info = {
            "dropbox_folder": folder,
            "crm_client_id": best_match["id"]
            if best_match and best_score >= threshold
            else None,
            "crm_client_name": best_match["name"]
            if best_match and best_score >= threshold
            else None,
            "similarity_score": round(best_score, 3),
            "confidence": "high"
            if best_score >= 0.8
            else "medium"
            if best_score >= threshold
            else "low",
            "needs_review": best_score < 0.8,
        }

        matches.append(match_info)

    # Sort by score descending
    matches.sort(key=lambda x: x["similarity_score"], reverse=True)

    return {
        "matches": matches,
        "categories": categories,
        "summary": {
            "total_dropbox_folders": len(DROPBOX_FOLDERS),
            "potential_clients": len(categories["potential_clients"]),
            "process_folders": len(categories["process_folders"]),
            "utility_folders": len(categories["utility_folders"]),
            "high_confidence_matches": sum(
                1 for m in matches if m["confidence"] == "high"
            ),
            "medium_confidence_matches": sum(
                1 for m in matches if m["confidence"] == "medium"
            ),
            "low_confidence_matches": sum(
                1 for m in matches if m["confidence"] == "low"
            ),
        },
    }


def generate_sample_report():
    """Generate a sample matching report with mock CRM data"""

    # Mock CRM clients for demonstration
    mock_crm_clients = [
        {"id": 1, "name": "Adele Marthe"},
        {"id": 2, "name": "Aditya Pratama"},
        {"id": 3, "name": "Angel"},
        {"id": 4, "name": "David Lee"},
        {"id": 5, "name": "Dinok"},
        {"id": 6, "name": "EPO International"},
        {"id": 7, "name": "Ersa"},
        {"id": 8, "name": "Gendu"},
        {"id": 9, "name": "Lia"},
        {"id": 10, "name": "Megi"},
        {"id": 11, "name": "Merp"},
        {"id": 12, "name": "Novi"},
        {"id": 13, "name": "Yanti"},
        {"id": 14, "name": "Yoyok"},
        {"id": 15, "name": "Yudi"},
    ]

    results = fuzzy_match_clients(mock_crm_clients, threshold=0.6)

    print("\n" + "=" * 80)
    print("📊 DROPBOX → CRM CLIENT MATCHING REPORT")
    print("=" * 80)

    print(f"\n📁 Total Dropbox Folders: {results['summary']['total_dropbox_folders']}")
    print(f"   • Potential Clients: {results['summary']['potential_clients']}")
    print(f"   • Process Folders: {results['summary']['process_folders']}")
    print(f"   • Utility Folders: {results['summary']['utility_folders']}")

    print("\n🎯 Matching Confidence:")
    print(f"   • High (≥80%): {results['summary']['high_confidence_matches']}")
    print(f"   • Medium (≥60%): {results['summary']['medium_confidence_matches']}")
    print(f"   • Low (<60%): {results['summary']['low_confidence_matches']}")

    print("\n✅ HIGH CONFIDENCE MATCHES:")
    for match in results["matches"]:
        if match["confidence"] == "high":
            print(f"   📁 {match['dropbox_folder']}")
            print(
                f"      → CRM: {match['crm_client_name']} (ID: {match['crm_client_id']})"
            )
            print(f"      Score: {match['similarity_score']:.1%}")

    print("\n⚠️  MEDIUM CONFIDENCE MATCHES (NEED REVIEW):")
    for match in results["matches"]:
        if match["confidence"] == "medium":
            print(f"   📁 {match['dropbox_folder']}")
            print(
                f"      → CRM: {match['crm_client_name']} (ID: {match['crm_client_id']})"
            )
            print(f"      Score: {match['similarity_score']:.1%}")

    print("\n❌ LOW CONFIDENCE / NO MATCH:")
    for match in results["matches"]:
        if match["confidence"] == "low":
            print(f"   📁 {match['dropbox_folder']}")
            if match["crm_client_name"]:
                print(
                    f"      Best guess: {match['crm_client_name']} (Score: {match['similarity_score']:.1%})"
                )
            else:
                print("      No match found in CRM")

    print("\n🗂️  PROCESS FOLDERS (excluded from matching):")
    for folder in results["categories"]["process_folders"]:
        print(f"   • {folder}")

    print("\n🛠️  UTILITY FOLDERS (excluded from matching):")
    for folder in results["categories"]["utility_folders"][:10]:
        print(f"   • {folder}")
    if len(results["categories"]["utility_folders"]) > 10:
        print(f"   ... and {len(results['categories']['utility_folders']) - 10} more")

    print("\n" + "=" * 80)

    # Save to JSON
    output_file = (
        f"client_matching_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n💾 Full report saved to: {output_file}")
    print("=" * 80 + "\n")

    return results


if __name__ == "__main__":
    generate_sample_report()
