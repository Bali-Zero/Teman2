#!/usr/bin/env python3
"""
ZANTARA - Test Metadata Extraction

Test rapido per verificare che l'estrazione metadata funzioni correttamente.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from extract_and_update_metadata import MetadataExtractor

# Test samples
TEST_SAMPLES = {
    "visa_oracle": """
    3. C7 VISA 
    Description: Single entry visa designed for professionals like chefs, yoga 
    instructors, bartenders, and photographers who are invited to take part in 
    events throughout Indonesia.
    
    Fee: USD 100-200
    Duration: 2-3 weeks
    """,
    "kbli_unified": """
    KBLI Code: 12345
    Description: Construction of residential buildings
    
    Investment Minimum: IDR 10,000,000,000
    Risk Level: Medium-High (MT)
    """,
    "tax_genius": """
    ### Income Tax (PPh)
    Rate: 5% - 30%
    Effective Date: 2024-01-01
    """,
    "legal_unified": """
    UU No. 13/2003
    Pasal 5
    Status: Berlaku
    Year: 2003
    """,
    "bali_zero_pricing": """
    8. D1 VISA
    Description: The ideal choice to attend as a participant at meetings.
    Fee: USD 150
    """,
}


def main():
    """Test extraction"""
    print("=" * 80)
    print("ZANTARA - Test Metadata Extraction")
    print("=" * 80)

    extractor = MetadataExtractor()
    all_passed = True

    for collection_name, sample_text in TEST_SAMPLES.items():
        print(f"\n📊 Testing: {collection_name}")
        metadata = extractor.extract_metadata(collection_name, sample_text)

        if metadata:
            print(f"   ✅ Metadata estratti: {len(metadata)} campi")
            for key, value in metadata.items():
                print(f"      - {key}: {value}")
        else:
            print(f"   ❌ Nessun metadata estratto")
            all_passed = False

    print(f"\n{'='*80}")
    if all_passed:
        print("✅ Tutti i test passati!")
    else:
        print("⚠️ Alcuni test falliti")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()

