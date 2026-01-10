#!/usr/bin/env python3
"""
Aggiorna Qdrant con i dati completi finali (KBLI + PMA + PB UMKU).
Usa il file completo finale creato dopo tutte le integrazioni.
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
DATA_DIR = PROJECT_ROOT / "reports" / "kbli_extraction"


def get_latest_final_file() -> Optional[Path]:
    """Trova il file completo finale più recente."""
    pattern = "kbli_complete_final_*.json"
    files = list(DATA_DIR.glob(pattern))
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


def format_kbli_content(code: str, info: Dict) -> str:
    """Format KBLI content for embedding."""
    lines = []
    
    # Context injection
    sektor = info.get("sektor", "Unknown")
    risiko = info.get("tingkat_risiko", "Unknown")
    lines.append(f"[CONTEXT: KBLI 2025 - PP 28/2025 - SEKTOR {sektor} - KODE {code} - RISIKO {risiko}]")
    lines.append("")
    
    # Header
    lines.append(f"# KBLI {code} - {info.get('judul', 'N/A')}")
    lines.append("")
    
    # Basic info
    lines.append(f"**Kode:** {code}")
    lines.append(f"**Judul:** {info.get('judul', 'N/A')}")
    if sektor:
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
    
    # PB UMKU
    pb_umku = info.get("pb_umku", [])
    if pb_umku:
        lines.append(f"\n**Permessi di Supporto (PB UMKU):**")
        for pb in pb_umku:
            pb_nama = pb.get("nama", pb.get("judul", "N/A"))
            pb_kode = pb.get("kode", "")
            lines.append(f"- {pb_kode}: {pb_nama}")
    
    return "\n".join(lines)


def update_qdrant_with_final_data(dry_run: bool = False, batch_size: int = 50):
    """Aggiorna Qdrant con dati completi finali."""
    print("=" * 70)
    print("AGGIORNAMENTO QDRANT CON DATI COMPLETI FINALI")
    print("=" * 70)
    
    # Load file completo finale
    final_file = get_latest_final_file()
    if not final_file:
        print("❌ Nessun file completo finale trovato!")
        print("   Cerca: kbli_complete_final_*.json")
        return
    
    print(f"📄 File completo finale: {final_file.name}")
    
    with open(final_file) as f:
        final_json = json.load(f)
    
    kbli_data = final_json.get("kbli_data", {})
    print(f"📊 KBLI totali: {len(kbli_data)}")
    
    # Processa ogni KBLI
    print(f"\n🔄 Processando {len(kbli_data)} KBLI...")
    if dry_run:
        print("   ⚠️  DRY RUN - Nessun aggiornamento verrà eseguito")
    
    points = []
    updated = 0
    created = 0
    errors = 0
    
    for i, (code, kbli_info) in enumerate(kbli_data.items(), 1):
        try:
            # Fetch esistente
            existing = fetch_kbli_from_qdrant(code)
            
            # Formatta contenuto
            content = format_kbli_content(code, kbli_info)
            
            # Genera embedding
            if not dry_run:
                embedding = get_embedding(content)
            else:
                embedding = [0.0] * 1536  # Placeholder
            
            # Prepara metadata
            metadata = {
                "kode": code,
                "judul": kbli_info.get("judul", ""),
                "sektor": kbli_info.get("sektor", ""),
                "risk_level": kbli_info.get("tingkat_risiko", ""),
                "ruang_lingkup": kbli_info.get("ruang_lingkup", ""),
                "skala_usaha": kbli_info.get("skala_usaha", []),
                "pma_allowed": kbli_info.get("pma_allowed"),
                "pma_max_percentage": kbli_info.get("pma_max_percentage", ""),
                "source": "PP_28_2025_Lampiran_I_Complete",
                "updated_at": datetime.now().isoformat(),
            }
            
            # PB UMKU
            pb_umku = kbli_info.get("pb_umku", [])
            if pb_umku:
                metadata["pb_umku"] = pb_umku
            
            # Usa ID esistente o crea nuovo
            if existing:
                point_id = existing["id"]
                updated += 1
            else:
                point_id = str(uuid.uuid4())
                created += 1
            
            point = {
                "id": point_id,
                "vector": embedding,
                "payload": {
                    "content": content,
                    "metadata": metadata
                }
            }
            
            points.append(point)
            
            # Batch upload
            if len(points) >= batch_size:
                if not dry_run:
                    qdrant_request(
                        "PUT",
                        f"/collections/{COLLECTION_NAME}/points",
                        {"points": points}
                    )
                print(f"   ✅ Batch {i//batch_size}: {len(points)} punti processati")
                points = []
            
            if i % 100 == 0:
                print(f"   Processati {i}/{len(kbli_data)} KBLI...")
                
        except Exception as e:
            print(f"   ❌ Errore processando {code}: {e}")
            errors += 1
    
    # Upload rimanenti
    if points:
        if not dry_run:
            qdrant_request(
                "PUT",
                f"/collections/{COLLECTION_NAME}/points",
                {"points": points}
            )
        print(f"   ✅ Batch finale: {len(points)} punti processati")
    
    print("\n" + "=" * 70)
    print("RIEPILOGO")
    print("=" * 70)
    print(f"   KBLI processati: {len(kbli_data)}")
    print(f"   Nuovi: {created}")
    print(f"   Aggiornati: {updated}")
    print(f"   Errori: {errors}")
    
    if dry_run:
        print("\n⚠️  DRY RUN - Nessun aggiornamento eseguito")
    else:
        print("\n✅ Qdrant aggiornato con successo!")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Aggiorna Qdrant con dati completi finali")
    parser.add_argument("--dry-run", action="store_true", help="Esegui senza aggiornare Qdrant")
    parser.add_argument("--batch-size", type=int, default=50, help="Dimensione batch per upload")
    
    args = parser.parse_args()
    
    update_qdrant_with_final_data(dry_run=args.dry_run, batch_size=args.batch_size)
