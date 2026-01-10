"""Validatore per payload KBLI ultimate."""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.ingestion.schemas.kbli_ultimate_schema import validate_payload


def validate_all_payloads(payloads_file: Path) -> Tuple[int, int, List[str]]:
    """
    Valida tutti i payload.
    
    Returns:
        (valid_count, invalid_count, errors)
    """
    with open(payloads_file) as f:
        data = json.load(f)
    
    payloads = data.get("payloads", {})
    valid_count = 0
    invalid_count = 0
    errors = []
    
    print(f"🔍 Validating {len(payloads)} payloads...")
    
    for code, payload in payloads.items():
        is_valid, error_msg, validated = validate_payload(payload)
        
        if is_valid:
            valid_count += 1
        else:
            invalid_count += 1
            errors.append(f"{code}: {error_msg}")
            if len(errors) <= 10:  # Mostra solo primi 10 errori
                print(f"   ❌ {code}: {error_msg[:100]}")
    
    print(f"\n✅ Valid: {valid_count}")
    print(f"❌ Invalid: {invalid_count}")
    
    return valid_count, invalid_count, errors


if __name__ == "__main__":
    DATA_DIR = PROJECT_ROOT / "reports" / "kbli_extraction"
    payload_files = sorted(DATA_DIR.glob("kbli_ultimate_payloads_*.json"), 
                          key=lambda x: x.stat().st_mtime, reverse=True)
    
    if not payload_files:
        print("❌ Nessun file payload trovato")
        sys.exit(1)
    
    validate_all_payloads(payload_files[0])
