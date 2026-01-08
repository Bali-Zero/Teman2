#!/usr/bin/env python3
"""
Confronta dati KBLI estratti da PP 28/2025 con Gemini Vision vs dati in Qdrant
Analizza un campione sparso di 50 KBLI per verificare allineamento
"""

import asyncio
import json
import os
import random
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

# Add backend path
backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "apps", "backend-rag")
sys.path.insert(0, backend_path)
sys.path.insert(0, os.path.join(backend_path, "backend"))

load_dotenv(os.path.join(backend_path, ".env"))

# Import after path setup
from services.multimodal.pdf_vision_service import PDFVisionService

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PDF_PP28 = "/Users/antonellosiano/Desktop/PP Nomor 28 Tahun 2025 (1).pdf"
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "reports", "kbli_vision_comparison")

# Qdrant config
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev").rstrip("/")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")


def get_random_kbli_sample_from_qdrant(sample_size: int = 50) -> List[str]:
    """Recupera un campione casuale di codici KBLI da Qdrant"""
    headers = {"Content-Type": "application/json"}
    if QDRANT_API_KEY:
        headers["api-key"] = QDRANT_API_KEY

    # Scroll per ottenere tutti i punti (limit alto)
    body = {
        "limit": 1000,  # Prendiamo i primi 1000 per avere un pool più grande
        "with_payload": True,
        "offset": None,
    }

    try:
        resp = requests.post(
            f"{QDRANT_URL}/collections/kbli_unified/points/scroll",
            headers=headers,
            json=body,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        points = data.get("result", {}).get("points", [])

        # Estrai codici KBLI
        codes = []
        for point in points:
            payload = point.get("payload", {})
            meta = payload.get("metadata", {})
            code = meta.get("kode") or meta.get("code") or payload.get("kbli_code")
            if code and re.match(r"^\d{5}$", str(code)):
                codes.append(str(code))

        # Campione casuale
        if len(codes) > sample_size:
            return random.sample(codes, sample_size)
        return codes

    except Exception as e:
        print(f"❌ Errore recupero KBLI da Qdrant: {e}")
        return []


def fetch_kbli_from_qdrant(code: str) -> Optional[Dict]:
    """Recupera dati completi di un KBLI da Qdrant"""
    headers = {"Content-Type": "application/json"}
    if QDRANT_API_KEY:
        headers["api-key"] = QDRANT_API_KEY

    body = {
        "filter": {
            "must": [{"key": "metadata.kode", "match": {"value": code}}]
        },
        "limit": 1,
        "with_payload": True,
    }

    try:
        resp = requests.post(
            f"{QDRANT_URL}/collections/kbli_unified/points/scroll",
            headers=headers,
            json=body,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        points = data.get("result", {}).get("points", [])
        if points:
            return points[0].get("payload", {})
    except Exception as e:
        print(f"  ⚠️  Errore query Qdrant per {code}: {e}")
    return None


async def search_kbli_in_pp28_vision(
    vision_service: PDFVisionService, code: str, max_pages: int = 50
) -> Optional[Dict]:
    """
    Cerca un KBLI specifico nel PDF PP 28/2025 usando Vision.
    Analizza le pagine fino a trovare il codice o esaurire le pagine.
    """
    prompt = f"""
    Cerca il codice KBLI {code} in questa pagina del PP 28/2025.
    
    Se trovi questo codice, estrai:
    - Tingkat Risiko (Rendah, Menengah Rendah, Menengah, Menengah Tinggi, Tinggi)
    - Kepemilikan Asing (PMA) - Diizinkan/Tidak Diizinkan e percentuale massima se presente
    - Skala Usaha (Mikro, Kecil, Menengah, Besar)
    
    Rispondi SOLO in formato JSON:
    {{
      "found": true/false,
      "kode": "{code}",
      "tingkat_risiko": "...",
      "pma_allowed": true/false/null,
      "pma_max_percentage": "...",
      "skala_usaha": ["Mikro", "Kecil", ...]
    }}
    
    Se NON trovi il codice, rispondi: {{"found": false}}
    """

    # Analizza pagine in batch per efficienza
    # Inizia dalle prime pagine (dove di solito ci sono le tabelle)
    for page_num in range(1, min(max_pages + 1, 200)):
        try:
            result = await vision_service.analyze_page(
                PDF_PP28, page_num, prompt=prompt, is_drive_file=False
            )

            # Prova a parsare JSON dalla risposta
            if result and "found" in result:
                # Cerca JSON nella risposta
                json_match = re.search(r'\{[^{}]*"found"[^{}]*\}', result)
                if json_match:
                    try:
                        data = json.loads(json_match.group(0))
                        if data.get("found"):
                            print(f"    ✅ Trovato {code} a pagina {page_num}")
                            return data
                    except json.JSONDecodeError:
                        # Prova a estrarre JSON più complesso
                        json_start = result.find("{")
                        json_end = result.rfind("}") + 1
                        if json_start >= 0 and json_end > json_start:
                            try:
                                data = json.loads(result[json_start:json_end])
                                if data.get("found"):
                                    print(f"    ✅ Trovato {code} a pagina {page_num}")
                                    return data
                            except json.JSONDecodeError:
                                continue

        except Exception as e:
            print(f"    ⚠️  Errore pagina {page_num} per {code}: {e}")
            continue

    return None


def compare_kbli_data(qdrant_data: Dict, vision_data: Optional[Dict]) -> Dict:
    """Confronta dati Qdrant vs Vision"""
    comparison = {
        "code": qdrant_data.get("metadata", {}).get("kode", "UNKNOWN"),
        "found_in_pp28": vision_data is not None,
        "matches": {},
        "differences": [],
    }

    if not vision_data:
        comparison["differences"].append("KBLI non trovato in PP 28/2025 (Vision)")
        return comparison

    meta = qdrant_data.get("metadata", {})

    # Confronto Risk Level
    q_risk = meta.get("risk_level", "").strip()
    v_risk = vision_data.get("tingkat_risiko", "").strip()
    if q_risk and v_risk:
        if q_risk.lower() == v_risk.lower():
            comparison["matches"]["risk_level"] = True
        else:
            comparison["differences"].append(
                f"Risk level: Qdrant='{q_risk}' vs PP28='{v_risk}'"
            )
    elif v_risk and not q_risk:
        comparison["differences"].append(f"Risk level mancante in Qdrant: PP28 ha '{v_risk}'")
    elif q_risk and not v_risk:
        comparison["differences"].append(f"Risk level mancante in PP28: Qdrant ha '{q_risk}'")

    # Confronto PMA
    q_pma = meta.get("pma_allowed")
    v_pma = vision_data.get("pma_allowed")
    if q_pma is not None and v_pma is not None:
        if q_pma == v_pma:
            comparison["matches"]["pma_allowed"] = True
        else:
            comparison["differences"].append(
                f"PMA allowed: Qdrant={q_pma} vs PP28={v_pma}"
            )
    elif v_pma is not None and q_pma is None:
        comparison["differences"].append(f"PMA mancante in Qdrant: PP28 ha {v_pma}")
    elif q_pma is not None and v_pma is None:
        comparison["differences"].append(f"PMA mancante in PP28: Qdrant ha {q_pma}")

    # Confronto PMA Max Percentage
    q_pma_max = str(meta.get("pma_max_percentage", "")).strip()
    v_pma_max = str(vision_data.get("pma_max_percentage", "")).strip()
    if q_pma_max and v_pma_max:
        if q_pma_max == v_pma_max:
            comparison["matches"]["pma_max"] = True
        else:
            comparison["differences"].append(
                f"PMA max: Qdrant='{q_pma_max}' vs PP28='{v_pma_max}'"
            )

    # Confronto Skala Usaha
    q_scales = set(meta.get("scales", []))
    v_scales = set(vision_data.get("skala_usaha", []))
    if q_scales and v_scales:
        if q_scales == v_scales:
            comparison["matches"]["scales"] = True
        else:
            comparison["differences"].append(
                f"Skala: Qdrant={sorted(q_scales)} vs PP28={sorted(v_scales)}"
            )
    elif v_scales and not q_scales:
        comparison["differences"].append(f"Skala mancante in Qdrant: PP28 ha {sorted(v_scales)}")

    return comparison


async def main():
    """Main comparison function"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("CONFRONTO KBLI: PP 28/2025 (Vision) vs Qdrant")
    print("=" * 60)

    # 1. Inizializza Vision Service
    print("\n🔧 Inizializzazione Vision Service...")
    print("   Caricamento PDFVisionService...")
    vision_service = PDFVisionService()
    print(f"   Vision service disponibile: {vision_service._available}")
    if not vision_service._available:
        print("❌ Vision service non disponibile. Verifica GOOGLE_API_KEY")
        return
    print("✅ Vision service pronto")

    # 2. Recupera campione KBLI da Qdrant
    print("\n📊 Recupero campione KBLI da Qdrant...")
    # Usa KBLI noti per test (agricoltura, che sappiamo essere nel PDF)
    known_codes = ["01111", "01138", "01271", "01272", "01273", "01279", "01133", "01112", "01116", "01117"]
    sample_codes = known_codes[:10]  # Usa KBLI noti invece di casuali
    print(f"   Usando KBLI noti: {sample_codes}")
    if not sample_codes:
        print("❌ Nessun KBLI trovato in Qdrant")
        return
    print(f"✅ Campione di {len(sample_codes)} KBLI selezionato")
    print(f"   Codici: {', '.join(sample_codes[:10])}...")

    # 3. Per ogni KBLI: recupera da Qdrant e cerca in PP 28/2025
    comparisons = []
    stats = {
        "total": len(sample_codes),
        "found_in_pp28": 0,
        "not_found_in_pp28": 0,
        "fully_matching": 0,
        "has_differences": 0,
        "risk_level_mismatch": 0,
        "pma_mismatch": 0,
        "scales_mismatch": 0,
    }

    print(f"\n🔍 Analisi {len(sample_codes)} KBLI con Vision...")
    print(f"   PDF da analizzare: {PDF_PP28}")
    print(f"   Esiste: {os.path.exists(PDF_PP28)}")
    
    for i, code in enumerate(sample_codes, 1):
        print(f"\n[{i}/{len(sample_codes)}] KBLI {code}")
        sys.stdout.flush()  # Force flush per vedere output in tempo reale

        # Recupera da Qdrant
        qdrant_data = fetch_kbli_from_qdrant(code)
        if not qdrant_data:
            print(f"  ⚠️  Non trovato in Qdrant")
            continue

        # Cerca in PP 28/2025 con Vision
        print(f"  👁️  Cercando in PP 28/2025...")
        vision_data = await search_kbli_in_pp28_vision(vision_service, code, max_pages=20)  # Ridotto per test veloce

        # Confronta
        comparison = compare_kbli_data(qdrant_data, vision_data)
        comparisons.append(comparison)

        # Aggiorna stats
        if comparison["found_in_pp28"]:
            stats["found_in_pp28"] += 1
            if not comparison["differences"]:
                stats["fully_matching"] += 1
            else:
                stats["has_differences"] += 1
                if any("Risk level" in d for d in comparison["differences"]):
                    stats["risk_level_mismatch"] += 1
                if any("PMA" in d for d in comparison["differences"]):
                    stats["pma_mismatch"] += 1
                if any("Skala" in d for d in comparison["differences"]):
                    stats["scales_mismatch"] += 1
        else:
            stats["not_found_in_pp28"] += 1

        # Stampa risultato
        if comparison["found_in_pp28"]:
            if comparison["differences"]:
                print(f"  ⚠️  Differenze: {len(comparison['differences'])}")
                for diff in comparison["differences"][:2]:
                    print(f"     - {diff}")
            else:
                print(f"  ✅ Completamente allineato")

    # 4. Salva risultati
    report = {
        "generated_at": datetime.now().isoformat(),
        "stats": stats,
        "comparisons": comparisons,
    }

    output_file = os.path.join(OUTPUT_DIR, f"vision_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # 5. Report finale
    print("\n" + "=" * 60)
    print("RISULTATI CONFRONTO")
    print("=" * 60)
    print(f"Totale analizzati: {stats['total']}")
    if stats['total'] > 0:
        print(f"✅ Trovati in PP 28/2025: {stats['found_in_pp28']} ({stats['found_in_pp28']*100/stats['total']:.1f}%)")
        print(f"❌ Non trovati in PP 28/2025: {stats['not_found_in_pp28']}")
        print(f"✅ Completamente allineati: {stats['fully_matching']} ({stats['fully_matching']*100/stats['total']:.1f}%)")
        print(f"⚠️  Con differenze: {stats['has_differences']}")
        if stats['has_differences'] > 0:
            print(f"   - Risk level mismatch: {stats['risk_level_mismatch']}")
            print(f"   - PMA mismatch: {stats['pma_mismatch']}")
            print(f"   - Skala mismatch: {stats['scales_mismatch']}")
    print(f"\n📁 Report salvato in: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
