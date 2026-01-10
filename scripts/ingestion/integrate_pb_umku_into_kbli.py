#!/usr/bin/env python3
"""
Integra PB UMKU nei KBLI di riferimento in Qdrant.
Questo crea un sistema completo che mostra non solo l'attività principale,
ma anche tutti i permessi di supporto necessari.
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
PB_UMKU_DATA_DIR = PROJECT_ROOT / "reports" / "kbli_extraction"


def get_latest_pb_umku_file() -> Optional[Path]:
    """Trova il file più recente con dati PB UMKU."""
    pattern = "pb_umku_complete_from_lampiran_*.json"
    files = list(PB_UMKU_DATA_DIR.glob(pattern))
    if not files:
        return None
    return max(files, key=lambda f: f.stat().st_mtime)


def get_latest_kbli_mapping_file() -> Optional[Path]:
    """Trova il file più recente con mapping KBLI→PB UMKU."""
    pattern = "kbli_to_pb_umku_mapping_*.json"
    files = list(PB_UMKU_DATA_DIR.glob(pattern))
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


def format_kbli_content_with_pb_umku(code: str, kbli_info: Dict, pb_umku_list: List[Dict]) -> str:
    """Format KBLI content includendo PB UMKU."""
    lines = []
    
    # Context injection
    sektor = kbli_info.get("sektor", "Unknown")
    risiko = kbli_info.get("tingkat_risiko", kbli_info.get("risk_level", "Unknown"))
    lines.append(f"[CONTEXT: KBLI 2025 - PP 28/2025 - SEKTOR {sektor} - KODE {code} - RISIKO {risiko}]")
    lines.append("")
    
    # Header
    lines.append(f"# KBLI {code} - {kbli_info.get('judul', 'N/A')}")
    lines.append("")
    
    # Basic info
    lines.append(f"**Kode:** {code}")
    lines.append(f"**Judul:** {kbli_info.get('judul', 'N/A')}")
    lines.append(f"**Sektor:** {sektor}")
    lines.append(f"**Tingkat Risiko:** {risiko}")
    
    # PMA info
    pma_allowed = kbli_info.get("pma_allowed")
    pma_max = kbli_info.get("pma_max_percentage")
    if pma_allowed is not None:
        lines.append(f"**PMA Diizinkan:** {'Ya' if pma_allowed else 'Tidak'}")
        if pma_max:
            lines.append(f"**PMA Maksimum:** {pma_max}")
    
    # Skala usaha
    skala = kbli_info.get("skala_usaha", [])
    if skala:
        lines.append(f"**Skala Usaha:** {', '.join(skala)}")
    
    # Ruang lingkup
    ruang_lingkup = kbli_info.get("ruang_lingkup", "")
    if ruang_lingkup:
        lines.append(f"\n**Ruang Lingkup:**\n{ruang_lingkup}")
    
    # Persyaratan e Kewajiban esistenti
    persyaratan = kbli_info.get("persyaratan", [])
    kewajiban = kbli_info.get("kewajiban", [])
    
    # PB UMKU (NUOVO - valore aggiunto!)
    if pb_umku_list:
        lines.append(f"\n## Permessi di Supporto (PB UMKU)")
        lines.append("")
        lines.append("Per svolgere questa attività principale, potresti aver bisogno di questi permessi aggiuntivi:")
        lines.append("")
        
        for pb_umku in pb_umku_list:
            nama = pb_umku.get("nama_pb_umku", "")
            if nama:
                lines.append(f"### {nama}")
                
                # Persyaratan PB UMKU
                pb_persyaratan = pb_umku.get("persyaratan", [])
                if pb_persyaratan:
                    lines.append("**Requisiti:**")
                    for req in pb_persyaratan:
                        lines.append(f"- {req}")
                    lines.append("")
                
                # Kewajiban PB UMKU
                pb_kewajiban = pb_umku.get("kewajiban", [])
                if pb_kewajiban:
                    lines.append("**Obblighi:**")
                    for kew in pb_kewajiban:
                        lines.append(f"- {kew}")
                    lines.append("")
                
                # Altri dettagli
                jangka_waktu = pb_umku.get("jangka_waktu", "")
                penerbitan = pb_umku.get("penerbitan", "")
                if jangka_waktu:
                    lines.append(f"**Durata:** {jangka_waktu}")
                if penerbitan:
                    lines.append(f"**Emesso da:** {penerbitan}")
                lines.append("")
        
        # Aggiungi persyaratan/kewajiban PB UMKU a quelli esistenti
        for pb_umku in pb_umku_list:
            pb_persyaratan = pb_umku.get("persyaratan", [])
            pb_kewajiban = pb_umku.get("kewajiban", [])
            
            for req in pb_persyaratan:
                if req not in persyaratan:
                    persyaratan.append(f"[PB UMKU {pb_umku.get('nama_pb_umku', '')}] {req}")
            
            for kew in pb_kewajiban:
                if kew not in kewajiban:
                    kewajiban.append(f"[PB UMKU {pb_umku.get('nama_pb_umku', '')}] {kew}")
    
    # Persyaratan (completo)
    if persyaratan:
        lines.append(f"\n**Persyaratan:**")
        for req in persyaratan:
            lines.append(f"- {req}")
    
    # Kewajiban (completo)
    if kewajiban:
        lines.append(f"\n**Kewajiban:**")
        for kew in kewajiban:
            lines.append(f"- {kew}")
    
    return "\n".join(lines)


def integrate_pb_umku_into_kbli(dry_run: bool = False):
    """Integra PB UMKU nei KBLI in Qdrant."""
    print("=" * 70)
    print("INTEGRAZIONE PB UMKU NEI KBLI")
    print("=" * 70)
    
    # Load PB UMKU data
    pb_umku_file = get_latest_pb_umku_file()
    if not pb_umku_file:
        print("❌ Nessun file PB UMKU trovato!")
        print("   Esegui prima: python scripts/analysis/extract_pb_umku_from_lampiran_parallel.py")
        return
    
    print(f"📄 File PB UMKU: {pb_umku_file.name}")
    
    with open(pb_umku_file) as f:
        pb_umku_json = json.load(f)
    
    pb_umku_data = pb_umku_json.get("pb_umku_data", {})
    print(f"📊 PB UMKU estratti: {len(pb_umku_data)}")
    
    # Load mapping KBLI→PB UMKU
    mapping_file = get_latest_kbli_mapping_file()
    kbli_to_pb_umku = {}
    
    if mapping_file:
        print(f"📄 File mapping: {mapping_file.name}")
        with open(mapping_file) as f:
            mapping_json = json.load(f)
            kbli_to_pb_umku = mapping_json.get("kbli_to_pb_umku", {})
        print(f"📊 KBLI con PB UMKU mappati: {len(kbli_to_pb_umku)}")
    else:
        print("⚠️  File mapping non trovato, creerò mapping dai dati PB UMKU")
        # Crea mapping dai dati PB UMKU
        for nama, pb_umku_entry in pb_umku_data.items():
            kbli_refs = pb_umku_entry.get("kbli_referensi", [])
            for kbli_code in kbli_refs:
                if kbli_code and len(kbli_code) == 5:
                    if kbli_code not in kbli_to_pb_umku:
                        kbli_to_pb_umku[kbli_code] = []
                    if nama not in kbli_to_pb_umku[kbli_code]:
                        kbli_to_pb_umku[kbli_code].append(nama)
    
    # Processa ogni KBLI con PB UMKU
    print(f"\n🔄 Processando {len(kbli_to_pb_umku)} KBLI con PB UMKU...")
    
    points = []
    updated = 0
    
    for kbli_code, pb_umku_names in kbli_to_pb_umku.items():
        # Fetch KBLI esistente
        existing = fetch_kbli_from_qdrant(kbli_code)
        if not existing:
            print(f"  ⚠️  KBLI {kbli_code} non trovato in Qdrant, salto")
            continue
        
        # Prepara lista PB UMKU
        pb_umku_list = []
        for nama in pb_umku_names:
            if nama in pb_umku_data:
                pb_umku_list.append(pb_umku_data[nama])
        
        if not pb_umku_list:
            continue
        
        # Merge dati
        payload = existing.get("payload", {})
        metadata = payload.get("metadata", {})
        
        # Aggiungi PB UMKU ai metadata
        metadata["pb_umku"] = pb_umku_list
        metadata["pb_umku_names"] = pb_umku_names
        metadata["updated_at"] = datetime.now().isoformat()
        
        # Regenera content con PB UMKU
        kbli_info = metadata.copy()
        kbli_info["judul"] = metadata.get("judul", "")
        content = format_kbli_content_with_pb_umku(kbli_code, kbli_info, pb_umku_list)
        
        # Regenera embedding
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
                print(f"  ✅ Aggiornato {kbli_code}: {len(pb_umku_names)} PB UMKU aggiunti")
            else:
                print(f"  [DRY-RUN] Aggiornato {kbli_code}: {len(pb_umku_names)} PB UMKU")
            
        except Exception as e:
            print(f"  ❌ Errore {kbli_code}: {e}")
    
    # Upload to Qdrant
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
    
    print(f"\n✅ Completato:")
    print(f"   KBLI aggiornati con PB UMKU: {updated}")
    print(f"\n🎯 RISULTATO:")
    print(f"   Ora ogni KBLI mostra non solo l'attività principale,")
    print(f"   ma anche TUTTI i permessi di supporto necessari!")
    print(f"   Questo è un livello di dettaglio che OSS non ha mai raggiunto!")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Integra PB UMKU nei KBLI")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("⚠️  MODALITÀ DRY-RUN: Nessuna modifica verrà applicata\n")
    
    integrate_pb_umku_into_kbli(args.dry_run)
