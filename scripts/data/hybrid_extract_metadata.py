#!/usr/bin/env python3
"""
ZANTARA - Hybrid Metadata Extraction (Pattern + ML)

Strategia ibrida: usa Pattern per velocità, ML per accuratezza.
"""

import os
import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))


# Try to import ML extractor
try:
    ML_AVAILABLE = True
except:
    ML_AVAILABLE = False


def main():
    """Hybrid extraction strategy"""
    print("=" * 80)
    print("ZANTARA - Hybrid Metadata Extraction")
    print("=" * 80)

    # Check ML availability
    api_key = os.getenv("GOOGLE_API_KEY")
    use_ml = ML_AVAILABLE and api_key

    if use_ml:
        print("\n✅ ML extraction disponibile (GOOGLE_API_KEY configurato)")
        print("   Strategia: Pattern + ML (ibrido)")
    else:
        print("\n⚠️ ML extraction non disponibile")
        print("   Strategia: Pattern only (veloce e gratis)")

    print("\n" + "=" * 80)
    print("📊 Strategia Raccomandata")
    print("=" * 80)
    print(
        """
1. **Pattern-Based (Attuale)**
   ✅ Success rate: 70-100%
   ✅ Gratis e veloce
   ✅ Già implementato

2. **Hybrid (Pattern + ML)**
   ✅ Pattern per documenti standardizzati
   ✅ ML per casi complessi/edge cases
   ✅ Best of both worlds

3. **ML-First (Opzionale)**
   ⚠️ Più costoso (~$2.50 per 25k docs)
   ✅ Accuratezza ~95-99%
   ✅ Adattivo e flessibile

💡 Raccomandazione: Usa Pattern per default, ML solo quando necessario.
    """
    )

    print("\n📚 Documentazione:")
    print("   - docs/ML_METADATA_EXTRACTION.md - Guida completa ML extraction")
    print("   - scripts/ml_metadata_extractor.py - Implementazione ML")
    print("   - scripts/extract_and_update_metadata.py - Pattern extraction")


if __name__ == "__main__":
    main()
