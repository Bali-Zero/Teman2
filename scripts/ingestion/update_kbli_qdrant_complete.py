#!/usr/bin/env python3
"""
Script completo per aggiornare KBLI in Qdrant:
1. Aggiunge KBLI mancanti
2. Aggiorna KBLI esistenti con PMA
3. Aggiunge restrizioni Bali
"""

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

# Add backend path
backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "apps", "backend-rag")
sys.path.insert(0, backend_path)
load_dotenv(os.path.join(backend_path, ".env"))

import openai

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
COLLECTION_NAME = "kbli_unified"
EMBEDDING_MODEL = "text-embedding-3-small"

# File paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
GAPS_FILE = PROJECT_ROOT / "reports" / "kbli_compliance" / "kbli_gaps.json"
BPS_KBLI_FILE = PROJECT_ROOT / "reports" / "kbli_extraction" / "bps_kbli.json"
PMA_DATA_FILE = PROJECT_ROOT / "reports" / "kbli_extraction" / "pma_data_from_reference_v2.json"
BALI_RESTRICTIONS_FILE = PROJECT_ROOT / "reports" / "kbli_compliance" / "bali_restrictions_mapping.json"


def get_embedding(text: str) -> List[float]:
    """Generate embedding using OpenAI."""
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text[:8000],
    )
    return response.data[0].embedding


def qdrant_request(method: str, endpoint: str, json_data: dict = None) -> dict:
    """Make request to Qdrant REST API."""
    url = f"{QDRANT_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if QDRANT_API_KEY:
        headers["api-key"] = QDRANT_API_KEY
    
    if method == "GET":
        r = requests.get(url, headers=headers)
    elif method == "PUT":
        r = requests.put(url, headers=headers, json=json_data)
    elif method == "POST":
        r = requests.post(url, headers=headers, json=json_data)
    else:
        raise ValueError(f"Unsupported method: {method}")
    
    r.raise_for_status()
    return r.json()


def fetch_kbli_from_qdrant(code: str) -> Optional[Dict]:
    """Fetch KBLI from Qdrant by code."""
    try:
        result = qdrant_request(
            "POST",
            f"/collections/{COLLECTION_NAME}/points/scroll",
            {
                "filter": {
                    "must": [
                        {"key": "metadata.kode", "match": {"value": code}}
                    ]
                },
                "limit": 1
            }
        )
        
        points = result.get("result", {}).get("points", [])
        if points:
            return points[0]
        return None
    except Exception as e:
        print(f"  ⚠️  Errore fetch {code}: {e}")
        return None


def format_kbli_content(code: str, info: Dict) -> str:
    """Format KBLI content for embedding."""
    lines = []
    
    # Context injection
    sektor = info.get("sektor", "Unknown")
    risiko = info.get("tingkat_risiko", info.get("risk_level", "Unknown"))
    lines.append(f"[CONTEXT: KBLI 2025 - PP 28/2025 - SEKTOR {sektor} - KODE {code} - RISIKO {risiko}]")
    lines.append("")
    
    # Header
    lines.append(f"# KBLI {code} - {info.get('judul', info.get('title', 'N/A'))}")
    lines.append("")
    
    # Basic info
    lines.append(f"**Kode:** {code}")
    lines.append(f"**Judul:** {info.get('judul', info.get('title', 'N/A'))}")
    lines.append(f"**Sektor:** {sektor}")
    lines.append(f"**Tingkat Risiko:** {risiko}")
    
    # PMA info
    pma_allowed = info.get("pma_allowed")
    pma_max = info.get("pma_max_percentage")
    if pma_allowed is not None:
        lines.append(f"**PMA Diizinkan:** {'Ya' if pma_allowed else 'Tidak'}")
        if pma_max:
            lines.append(f"**PMA Maksimum:** {pma_max}")
    
    # Skala usaha
    skala = info.get("skala_usaha", info.get("scales", []))
    if skala:
        lines.append(f"**Skala Usaha:** {', '.join(skala)}")
    
    # Ruang lingkup
    ruang_lingkup = info.get("ruang_lingkup", info.get("ruang_lingkup", ""))
    if ruang_lingkup:
        lines.append(f"\n**Ruang Lingkup:**\n{ruang_lingkup}")
    
    # Persyaratan
    persyaratan = info.get("persyaratan", [])
    if persyaratan:
        lines.append(f"\n**Persyaratan:**")
        for req in persyaratan:
            lines.append(f"- {req}")
    
    # Kewajiban
    kewajiban = info.get("kewajiban", [])
    if kewajiban:
        lines.append(f"\n**Kewajiban:**")
        for kew in kewajiban:
            lines.append(f"- {kew}")
    
    # Restrizioni Bali
    bali_restrictions = info.get("geographic_restrictions", {}).get("bali", {})
    if bali_restrictions:
        lines.append(f"\n**Restrizioni Bali:**")
        if bali_restrictions.get("temporary_restriction"):
            lines.append(f"- Restrizione temporanea: {bali_restrictions.get('restriction_type', 'N/A')}")
        if bali_restrictions.get("affected_areas"):
            lines.append(f"- Aree interessate: {', '.join(bali_restrictions['affected_areas'])}")
    
    return "\n".join(lines)


def extract_metadata(code: str, info: Dict) -> Dict:
    """Extract metadata for Qdrant point."""
    return {
        "kode": code,
        "judul": info.get("judul", info.get("title", "")),
        "sektor": info.get("sektor", "Unknown"),
        "risk_level": info.get("tingkat_risiko", info.get("risk_level", "")),
        "pma_allowed": info.get("pma_allowed"),
        "pma_max_percentage": info.get("pma_max_percentage", ""),
        "skala_usaha": info.get("skala_usaha", info.get("scales", [])),
        "ruang_lingkup": info.get("ruang_lingkup", ""),
        "persyaratan": info.get("persyaratan", []),
        "kewajiban": info.get("kewajiban", []),
        "source": "PP_28_2025_BPS_7_2025",
        "updated_at": __import__("datetime").datetime.now().isoformat(),
    }


def add_missing_kbli(dry_run: bool = False) -> int:
    """Add missing KBLI codes to Qdrant."""
    print("\n" + "=" * 70)
    print("AGGIUNTA KBLI MANCANTI")
    print("=" * 70)
    
    # Load gaps
    if not GAPS_FILE.exists():
        print(f"❌ File gaps non trovato: {GAPS_FILE}")
        return 0
    
    with open(GAPS_FILE) as f:
        gaps_data = json.load(f)
    
    missing_codes = gaps_data.get("missing_in_qdrant", [])
    if not missing_codes:
        print("✅ Nessun KBLI mancante da aggiungere")
        return 0
    
    print(f"📋 KBLI mancanti da aggiungere: {len(missing_codes)}")
    
    # Load BPS data
    if not BPS_KBLI_FILE.exists():
        print(f"❌ File BPS KBLI non trovato: {BPS_KBLI_FILE}")
        return 0
    
    with open(BPS_KBLI_FILE) as f:
        bps_data = json.load(f)
    
    # Load PMA data
    pma_data = {}
    if PMA_DATA_FILE.exists():
        with open(PMA_DATA_FILE) as f:
            pma_json = json.load(f)
            pma_data = pma_json.get("pma_data", {})
    
    # Prepare points
    points = []
    added = 0
    
    for code in missing_codes:
        if code not in bps_data:
            print(f"  ⚠️  {code}: Dati BPS non trovati")
            continue
        
        kbli_info = bps_data[code].copy()
        
        # Merge PMA data if available
        if code in pma_data:
            kbli_info.update(pma_data[code])
        
        # Format content
        content = format_kbli_content(code, kbli_info)
        meta = extract_metadata(code, kbli_info)
        
        # Generate embedding
        try:
            embedding = get_embedding(content)
            
            point = {
                "id": str(uuid.uuid4()),
                "vector": embedding,
                "payload": {
                    "text": content,
                    "metadata": meta
                }
            }
            points.append(point)
            added += 1
            
            if not dry_run:
                print(f"  ✅ Preparato {code}: {kbli_info.get('judul', 'N/A')[:50]}")
            else:
                print(f"  [DRY-RUN] Preparato {code}: {kbli_info.get('judul', 'N/A')[:50]}")
        except Exception as e:
            print(f"  ❌ Errore {code}: {e}")
    
    # Upload to Qdrant
    if points and not dry_run:
        print(f"\n📤 Upload di {len(points)} punti a Qdrant...")
        batch_size = 20
        for i in range(0, len(points), batch_size):
            batch = points[i:i+batch_size]
            try:
                qdrant_request(
                    "PUT",
                    f"/collections/{COLLECTION_NAME}/points",
                    {"points": batch}
                )
                print(f"  ✅ Upload batch {i//batch_size + 1}: {len(batch)} punti")
            except Exception as e:
                print(f"  ❌ Errore upload batch {i//batch_size + 1}: {e}")
    
    print(f"\n✅ Aggiunti {added} KBLI mancanti")
    return added


def update_existing_kbli_with_pma(dry_run: bool = False) -> int:
    """Update existing KBLI with PMA data."""
    print("\n" + "=" * 70)
    print("AGGIORNAMENTO KBLI ESISTENTI CON PMA")
    print("=" * 70)
    
    # Load PMA data
    if not PMA_DATA_FILE.exists():
        print(f"❌ File PMA data non trovato: {PMA_DATA_FILE}")
        return 0
    
    with open(PMA_DATA_FILE) as f:
        pma_json = json.load(f)
        pma_data = pma_json.get("pma_data", {})
    
    if not pma_data:
        print("✅ Nessun dato PMA disponibile")
        return 0
    
    print(f"📋 Dati PMA disponibili per {len(pma_data)} KBLI")
    
    # Load gaps to see which need update
    needs_update = []
    if GAPS_FILE.exists():
        with open(GAPS_FILE) as f:
            gaps_data = json.load(f)
            needs_update = gaps_data.get("needs_update", [])
    
    # Update all KBLI with PMA data (if available)
    updated = 0
    points = []
    
    for code, pma_info in pma_data.items():
        # Fetch existing point
        existing = fetch_kbli_from_qdrant(code)
        if not existing:
            continue  # Skip if not exists (will be added by add_missing_kbli)
        
        # Merge PMA data
        payload = existing.get("payload", {})
        metadata = payload.get("metadata", {})
        
        # Update metadata with PMA
        metadata["pma_allowed"] = pma_info.get("pma_allowed")
        metadata["pma_max_percentage"] = pma_info.get("pma_max_percentage", "")
        
        # Regenerate content with PMA
        kbli_info = metadata.copy()
        kbli_info["judul"] = metadata.get("judul", "")
        content = format_kbli_content(code, kbli_info)
        
        # Regenerate embedding
        try:
            embedding = get_embedding(content)
            
            point = {
                "id": existing.get("id"),
                "vector": embedding,
                "payload": {
                    "text": content,
                    "metadata": metadata
                }
            }
            points.append(point)
            updated += 1
            
            if not dry_run:
                print(f"  ✅ Aggiornato {code}: PMA={pma_info.get('pma_allowed')}, Max={pma_info.get('pma_max_percentage', 'N/A')}")
            else:
                print(f"  [DRY-RUN] Aggiornato {code}: PMA={pma_info.get('pma_allowed')}, Max={pma_info.get('pma_max_percentage', 'N/A')}")
        except Exception as e:
            print(f"  ❌ Errore {code}: {e}")
    
    # Upload updates
    if points and not dry_run:
        print(f"\n📤 Upload di {len(points)} aggiornamenti a Qdrant...")
        batch_size = 20
        for i in range(0, len(points), batch_size):
            batch = points[i:i+batch_size]
            try:
                qdrant_request(
                    "PUT",
                    f"/collections/{COLLECTION_NAME}/points",
                    {"points": batch}
                )
                print(f"  ✅ Upload batch {i//batch_size + 1}: {len(batch)} punti")
            except Exception as e:
                print(f"  ❌ Errore upload batch {i//batch_size + 1}: {e}")
    
    print(f"\n✅ Aggiornati {updated} KBLI con dati PMA")
    return updated


def add_bali_restrictions(dry_run: bool = False) -> int:
    """Add Bali restrictions to retail KBLI."""
    print("\n" + "=" * 70)
    print("AGGIUNTA RESTRIZIONI BALI")
    print("=" * 70)
    
    # Load Bali restrictions
    if not BALI_RESTRICTIONS_FILE.exists():
        print(f"❌ File restrizioni Bali non trovato: {BALI_RESTRICTIONS_FILE}")
        return 0
    
    with open(BALI_RESTRICTIONS_FILE) as f:
        bali_data = json.load(f)
    
    affected_kbli = bali_data.get("affected_kbli_codes", [])
    if not affected_kbli:
        print("✅ Nessuna restrizione Bali da aggiungere")
        return 0
    
    print(f"📋 KBLI interessati da restrizioni Bali: {len(affected_kbli)}")
    
    updated = 0
    points = []
    
    for code in affected_kbli:
        existing = fetch_kbli_from_qdrant(code)
        if not existing:
            continue
        
        payload = existing.get("payload", {})
        metadata = payload.get("metadata", {})
        
        # Add geographic restrictions
        if "geographic_restrictions" not in metadata:
            metadata["geographic_restrictions"] = {}
        
        metadata["geographic_restrictions"]["bali"] = {
            "temporary_restriction": True,
            "restriction_type": "Penghentian Sementara Pemberian Izin Toko Modern Berjejaring",
            "source": "INGUB 6/2025",
            "affected_areas": ["Bali"],
            "notes": "Restrizione temporanea sulla concessione di licenze per negozi moderni a catena"
        }
        
        # Regenerate content
        kbli_info = metadata.copy()
        kbli_info["judul"] = metadata.get("judul", "")
        content = format_kbli_content(code, kbli_info)
        
        # Regenerate embedding
        try:
            embedding = get_embedding(content)
            
            point = {
                "id": existing.get("id"),
                "vector": embedding,
                "payload": {
                    "text": content,
                    "metadata": metadata
                }
            }
            points.append(point)
            updated += 1
            
            if not dry_run:
                print(f"  ✅ Aggiunta restrizione Bali a {code}")
            else:
                print(f"  [DRY-RUN] Aggiunta restrizione Bali a {code}")
        except Exception as e:
            print(f"  ❌ Errore {code}: {e}")
    
    # Upload updates
    if points and not dry_run:
        print(f"\n📤 Upload di {len(points)} aggiornamenti a Qdrant...")
        batch_size = 20
        for i in range(0, len(points), batch_size):
            batch = points[i:i+batch_size]
            try:
                qdrant_request(
                    "PUT",
                    f"/collections/{COLLECTION_NAME}/points",
                    {"points": batch}
                )
                print(f"  ✅ Upload batch {i//batch_size + 1}: {len(batch)} punti")
            except Exception as e:
                print(f"  ❌ Errore upload batch {i//batch_size + 1}: {e}")
    
    print(f"\n✅ Aggiunte restrizioni Bali a {updated} KBLI")
    return updated


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Aggiorna KBLI in Qdrant")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    parser.add_argument("--add-missing", action="store_true", help="Aggiungi solo KBLI mancanti")
    parser.add_argument("--update-pma", action="store_true", help="Aggiorna solo PMA")
    parser.add_argument("--add-bali", action="store_true", help="Aggiungi solo restrizioni Bali")
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("AGGIORNAMENTO COMPLETO KBLI IN QDRANT")
    print("=" * 70)
    
    if args.dry_run:
        print("⚠️  MODALITÀ DRY-RUN: Nessuna modifica verrà applicata")
    
    total_added = 0
    total_updated = 0
    total_bali = 0
    
    # Execute based on flags
    if args.add_missing:
        total_added = add_missing_kbli(args.dry_run)
    elif args.update_pma:
        total_updated = update_existing_kbli_with_pma(args.dry_run)
    elif args.add_bali:
        total_bali = add_bali_restrictions(args.dry_run)
    else:
        # Execute all
        total_added = add_missing_kbli(args.dry_run)
        total_updated = update_existing_kbli_with_pma(args.dry_run)
        total_bali = add_bali_restrictions(args.dry_run)
    
    # Summary
    print("\n" + "=" * 70)
    print("RIEPILOGO")
    print("=" * 70)
    print(f"✅ KBLI aggiunti: {total_added}")
    print(f"✅ KBLI aggiornati con PMA: {total_updated}")
    print(f"✅ Restrizioni Bali aggiunte: {total_bali}")
    print(f"📊 Totale operazioni: {total_added + total_updated + total_bali}")


if __name__ == "__main__":
    main()
