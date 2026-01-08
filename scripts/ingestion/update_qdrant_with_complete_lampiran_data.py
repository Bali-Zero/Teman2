#!/usr/bin/env python3
"""
Aggiorna Qdrant con TUTTI i dati completi estratti dai Lampiran.
Mergia dati Lampiran con dati esistenti e PMA defaults.
"""

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

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

PROJECT_ROOT = Path(__file__).parent.parent.parent
LAMPIRAN_DATA_DIR = PROJECT_ROOT / "reports" / "kbli_extraction"
PMA_DEFAULTS_FILE = PROJECT_ROOT / "reports" / "kbli_extraction" / "pma_complete_with_defaults.json"
BPS_KBLI_FILE = PROJECT_ROOT / "reports" / "kbli_extraction" / "bps_kbli.json"


def get_latest_lampiran_file() -> Optional[Path]:
    """Trova il file più recente con dati Lampiran."""
    pattern = "kbli_complete_from_lampiran_*.json"
    files = list(LAMPIRAN_DATA_DIR.glob(pattern))
    if not files:
        return None
    return max(files, key=lambda f: f.stat().st_mtime)


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


def merge_kbli_data(
    lampiran_data: Dict,
    bps_data: Dict,
    pma_defaults: Dict,
    existing_qdrant: Optional[Dict]
) -> Dict:
    """
    Merge dati da tutte le fonti:
    1. Lampiran (priorità alta - dati più completi)
    2. BPS (fallback per titolo)
    3. PMA defaults (per PMA se non presente)
    4. Qdrant esistente (per preservare dati già presenti)
    """
    code = lampiran_data.get("kode", "")
    
    merged = {
        "kode": code,
        "judul": lampiran_data.get("judul") or bps_data.get("judul", ""),
        "sektor": lampiran_data.get("sektor") or existing_qdrant.get("metadata", {}).get("sektor", ""),
        "tingkat_risiko": lampiran_data.get("tingkat_risiko") or existing_qdrant.get("metadata", {}).get("risk_level", ""),
        "ruang_lingkup": lampiran_data.get("ruang_lingkup", ""),
        "skala_usaha": lampiran_data.get("skala_usaha", []),
        "persyaratan": existing_qdrant.get("metadata", {}).get("persyaratan", []),
        "kewajiban": existing_qdrant.get("metadata", {}).get("kewajiban", []),
        "source": "PP_28_2025_Lampiran_I",
        "updated_at": datetime.now().isoformat(),
    }
    
    # PMA: usa Lampiran se presente, altrimenti defaults
    if lampiran_data.get("pma_allowed") is not None:
        merged["pma_allowed"] = lampiran_data.get("pma_allowed")
        merged["pma_max_percentage"] = lampiran_data.get("pma_max_percentage", "")
    elif code in pma_defaults:
        pma_info = pma_defaults[code]
        merged["pma_allowed"] = pma_info.get("pma_allowed")
        merged["pma_max_percentage"] = pma_info.get("pma_max_percentage", "")
    else:
        # Default: PMA=100% (Positive Investment List)
        merged["pma_allowed"] = True
        merged["pma_max_percentage"] = "100%"
    
    return merged


def format_kbli_content(code: str, info: Dict) -> str:
    """Format KBLI content for embedding."""
    lines = []
    
    # Context injection
    sektor = info.get("sektor", "Unknown")
    risiko = info.get("tingkat_risiko", info.get("risk_level", "Unknown"))
    lines.append(f"[CONTEXT: KBLI 2025 - PP 28/2025 - SEKTOR {sektor} - KODE {code} - RISIKO {risiko}]")
    lines.append("")
    
    # Header
    lines.append(f"# KBLI {code} - {info.get('judul', 'N/A')}")
    lines.append("")
    
    # Basic info
    lines.append(f"**Kode:** {code}")
    lines.append(f"**Judul:** {info.get('judul', 'N/A')}")
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
    skala = info.get("skala_usaha", [])
    if skala:
        lines.append(f"**Skala Usaha:** {', '.join(skala)}")
    
    # Ruang lingkup
    ruang_lingkup = info.get("ruang_lingkup", "")
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
    
    return "\n".join(lines)


def update_qdrant_with_complete_data(dry_run: bool = False):
    """Aggiorna Qdrant con dati completi dai Lampiran."""
    print("=" * 70)
    print("AGGIORNAMENTO QDRANT CON DATI COMPLETI LAMPIRAN")
    print("=" * 70)
    
    # Load dati Lampiran
    lampiran_file = get_latest_lampiran_file()
    if not lampiran_file:
        print("❌ Nessun file Lampiran trovato!")
        print("   Esegui prima: python scripts/analysis/extract_all_kbli_from_lampiran_parallel.py")
        return
    
    print(f"📄 File Lampiran: {lampiran_file.name}")
    
    with open(lampiran_file) as f:
        lampiran_json = json.load(f)
    
    lampiran_data = lampiran_json.get("kbli_data", {})
    print(f"📊 KBLI estratti dai Lampiran: {len(lampiran_data)}")
    
    # Load BPS data
    bps_data = {}
    if BPS_KBLI_FILE.exists():
        with open(BPS_KBLI_FILE) as f:
            bps_data = json.load(f)
        print(f"📊 KBLI in BPS: {len(bps_data)}")
    
    # Load PMA defaults
    pma_defaults = {}
    if PMA_DEFAULTS_FILE.exists():
        with open(PMA_DEFAULTS_FILE) as f:
            pma_json = json.load(f)
            pma_defaults = pma_json.get("pma_data", {})
        print(f"📊 PMA defaults: {len(pma_defaults)}")
    
    # Processa ogni KBLI
    print(f"\n🔄 Processando {len(lampiran_data)} KBLI...")
    
    points = []
    updated = 0
    created = 0
    
    for code, lampiran_entry in lampiran_data.items():
        # Fetch esistente
        existing = fetch_kbli_from_qdrant(code)
        
        # Merge dati
        merged = merge_kbli_data(
            lampiran_entry,
            bps_data.get(code, {}),
            pma_defaults,
            existing or {}
        )
        
        # Format content
        content = format_kbli_content(code, merged)
        
        # Generate embedding
        try:
            embedding = get_embedding(content)
            
            # Metadata
            metadata = {
                "kode": code,
                "judul": merged.get("judul", ""),
                "sektor": merged.get("sektor", ""),
                "risk_level": merged.get("tingkat_risiko", ""),
                "pma_allowed": merged.get("pma_allowed"),
                "pma_max_percentage": merged.get("pma_max_percentage", ""),
                "skala_usaha": merged.get("skala_usaha", []),
                "ruang_lingkup": merged.get("ruang_lingkup", ""),
                "persyaratan": merged.get("persyaratan", []),
                "kewajiban": merged.get("kewajiban", []),
                "source": merged.get("source", ""),
                "updated_at": merged.get("updated_at", ""),
            }
            
            point = {
                "id": existing.get("id") if existing else str(uuid.uuid4()),
                "vector": embedding,
                "payload": {
                    "text": content,
                    "metadata": metadata
                }
            }
            points.append(point)
            
            if existing:
                updated += 1
                if not dry_run:
                    print(f"  ✅ Aggiornato {code}: {merged.get('judul', '')[:50]}")
            else:
                created += 1
                if not dry_run:
                    print(f"  ➕ Creato {code}: {merged.get('judul', '')[:50]}")
            
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
    
    print(f"\n✅ Completato:")
    print(f"   Aggiornati: {updated}")
    print(f"   Creati: {created}")
    print(f"   Totale: {len(points)}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Aggiorna Qdrant con dati completi Lampiran")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("⚠️  MODALITÀ DRY-RUN: Nessuna modifica verrà applicata\n")
    
    update_qdrant_with_complete_data(args.dry_run)
