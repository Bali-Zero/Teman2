#!/usr/bin/env python3
"""
Analizza il gap tra KBLI estratti (832) e KBLI in Qdrant (~8,886).
Verifica quali KBLI sono già presenti e quali mancano.
"""

import json
import os
import sys
from pathlib import Path
from typing import Set
from collections import Counter

import requests
from dotenv import load_dotenv

# Add backend path
backend_path = os.path.join(
    os.path.dirname(__file__), "..", "..", "apps", "backend-rag"
)
sys.path.insert(0, backend_path)
load_dotenv(os.path.join(backend_path, ".env"))

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = "kbli_unified"

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "reports" / "kbli_extraction"


def qdrant_request(method: str, endpoint: str, json_data: dict = None) -> dict:
    """Make request to Qdrant REST API."""
    url = f"{QDRANT_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if QDRANT_API_KEY:
        headers["api-key"] = QDRANT_API_KEY

    if method == "GET":
        r = requests.get(url, headers=headers)
    elif method == "POST":
        r = requests.post(url, headers=headers, json=json_data)
    else:
        raise ValueError(f"Unsupported method: {method}")

    r.raise_for_status()
    return r.json()


def get_collection_info() -> dict:
    """Ottiene info sulla collection kbli_unified."""
    result = qdrant_request("GET", f"/collections/{COLLECTION_NAME}")
    return result.get("result", {})


def get_all_kbli_codes_from_qdrant() -> Set[str]:
    """Estrae tutti i codici KBLI dalla collection Qdrant."""
    print("📊 Estrazione codici KBLI da Qdrant...")

    kbli_codes = set()
    scroll_id = None
    batch_count = 0

    while True:
        payload = {"limit": 1000, "with_payload": True, "with_vectors": False}

        if scroll_id:
            payload["offset"] = scroll_id

        try:
            result = qdrant_request(
                "POST", f"/collections/{COLLECTION_NAME}/points/scroll", payload
            )
        except Exception as e:
            print(f"   ⚠️  Errore batch {batch_count + 1}: {e}")
            break

        points = result.get("result", {}).get("points", [])
        if not points:
            break

        for point in points:
            payload_data = point.get("payload", {})
            metadata = payload_data.get("metadata", {})
            kode = metadata.get("kode", "")

            if kode and isinstance(kode, str) and kode.isdigit() and len(kode) == 5:
                kbli_codes.add(kode)

        batch_count += 1
        print(
            f"   Batch {batch_count}: {len(points)} punti, {len(kbli_codes)} KBLI unici"
        )

        # Check if there are more points
        next_offset = result.get("result", {}).get("next_page_offset")
        if not next_offset:
            break
        scroll_id = next_offset

    return kbli_codes


def get_extracted_kbli_codes() -> Set[str]:
    """Ottiene codici KBLI dal file estratto."""
    final_file = sorted(
        DATA_DIR.glob("kbli_complete_final_*.json"),
        key=lambda x: x.stat().st_mtime,
        reverse=True,
    )

    if not final_file:
        print("❌ Nessun file completo finale trovato!")
        return set()

    print(f"📁 Caricamento file: {final_file[0].name}")
    with open(final_file[0]) as f:
        data = json.load(f)

    kbli_data = data.get("kbli_data", {})
    codes = set(kbli_data.keys())

    print(f"   KBLI estratti: {len(codes)}")
    return codes


def analyze_gap():
    """Analizza il gap tra KBLI estratti e KBLI in Qdrant."""
    print("=" * 70)
    print("🔍 ANALISI GAP KBLI")
    print("=" * 70)
    print()

    # 1. Info collection
    print("1️⃣  INFO COLLECTION:")
    try:
        info = get_collection_info()
        points_count = info.get("points_count", 0)
        print(f"   Collection: {COLLECTION_NAME}")
        print(f"   Totale punti: {points_count}")
        print(f"   URL: {QDRANT_URL}")
        print()
    except Exception as e:
        print(f"   ❌ Errore: {e}")
        return

    # 2. Estrai codici da Qdrant
    qdrant_codes = get_all_kbli_codes_from_qdrant()
    print(f"   ✅ Totale KBLI in Qdrant: {len(qdrant_codes)}")
    print()

    # 3. Estrai codici dal file
    extracted_codes = get_extracted_kbli_codes()
    print(f"   ✅ Totale KBLI estratti: {len(extracted_codes)}")
    print()

    # 4. Analisi gap
    print("2️⃣  ANALISI GAP:")
    print(f"   KBLI in Qdrant: {len(qdrant_codes)}")
    print(f"   KBLI estratti: {len(extracted_codes)}")
    print()

    # KBLI già presenti
    already_present = extracted_codes & qdrant_codes
    print(f"   ✅ KBLI già presenti in Qdrant: {len(already_present)}")

    # KBLI nuovi (da aggiungere)
    new_kbli = extracted_codes - qdrant_codes
    print(f"   ➕ KBLI nuovi da aggiungere: {len(new_kbli)}")

    # KBLI in Qdrant ma non estratti
    missing_from_extraction = qdrant_codes - extracted_codes
    print(f"   ⚠️  KBLI in Qdrant ma non estratti: {len(missing_from_extraction)}")
    print()

    # 5. Distribuzione per prefisso
    print("3️⃣  DISTRIBUZIONE PER PREFISSO (primi 2 cifre):")

    qdrant_prefixes = Counter(code[:2] for code in qdrant_codes)
    extracted_prefixes = Counter(code[:2] for code in extracted_codes)

    print("\n   Qdrant (top 10):")
    for prefix in sorted(qdrant_prefixes.keys())[:10]:
        print(f"      {prefix}xx: {qdrant_prefixes[prefix]} KBLI")

    print("\n   Estratti (top 10):")
    for prefix in sorted(extracted_prefixes.keys())[:10]:
        print(f"      {prefix}xx: {extracted_prefixes[prefix]} KBLI")
    print()

    # 6. Campione KBLI nuovi
    if new_kbli:
        print("4️⃣  CAMPIONE KBLI NUOVI (primi 20):")
        for code in sorted(list(new_kbli))[:20]:
            print(f"   {code}")
        print()

    # 7. Campione KBLI mancanti dall'estrazione
    if missing_from_extraction:
        print("5️⃣  CAMPIONE KBLI IN QDRANT MA NON ESTRATTI (primi 20):")
        for code in sorted(list(missing_from_extraction))[:20]:
            print(f"   {code}")
        print()

    # 8. Salva report
    report = {
        "qdrant_total": len(qdrant_codes),
        "extracted_total": len(extracted_codes),
        "already_present": len(already_present),
        "new_kbli": len(new_kbli),
        "missing_from_extraction": len(missing_from_extraction),
        "new_kbli_codes": sorted(list(new_kbli)),
        "missing_codes_sample": sorted(list(missing_from_extraction))[
            :100
        ],  # Primi 100
        "qdrant_prefixes": dict(qdrant_prefixes),
        "extracted_prefixes": dict(extracted_prefixes),
    }

    report_file = DATA_DIR / "kbli_gap_analysis.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"📁 Report salvato: {report_file.name}")
    print()

    # 9. Raccomandazioni
    print("6️⃣  RACCOMANDAZIONI:")
    if len(new_kbli) > 0:
        print(f"   ✅ Aggiungere {len(new_kbli)} KBLI nuovi a Qdrant")
        print(
            "      Questi sono KBLI estratti da Lampiran I che non sono ancora in Qdrant"
        )
    if len(missing_from_extraction) > 0:
        print(f"   ⚠️  Investigare {len(missing_from_extraction)} KBLI già in Qdrant")
        print("      Potrebbero essere da altre fonti (BPS, OSS, etc.)")
        print(
            "      Verificare se sono completi o necessitano aggiornamento con dati Lampiran"
        )

    print()
    print("=" * 70)


if __name__ == "__main__":
    analyze_gap()
