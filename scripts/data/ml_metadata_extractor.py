#!/usr/bin/env python3
"""
ZANTARA - ML-Based Metadata Extractor

Usa Zantara AI (Gemini) per estrarre metadata strutturati dal testo
in modo più accurato rispetto ai pattern regex.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

# Add backend to path
backend_path = Path(__file__).parent.parent / "apps" / "backend-rag" / "backend"
sys.path.insert(0, str(backend_path))

# Set minimal env vars to avoid validation errors
os.environ.setdefault("JWT_SECRET_KEY", "dummy_jwt_secret_key_for_ml_extraction_12345")
os.environ.setdefault("API_KEYS", "{}")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "dummy")
os.environ.setdefault("INSTAGRAM_VERIFY_TOKEN", "dummy")

try:
    from llm.zantara_ai_client import ZantaraAIClient

    ML_AVAILABLE = True
except Exception as e:
    print(f"⚠️ ZantaraAIClient non disponibile: {e}")
    ML_AVAILABLE = False

# Load schema
SCHEMA_PATH = Path(__file__).parent.parent / "docs" / "qdrant_metadata_schema.json"
with open(SCHEMA_PATH, "r") as f:
    METADATA_SCHEMAS = json.load(f)


class MLMetadataExtractor:
    """Estrae metadata usando ML (Zantara AI)"""

    def __init__(self, model: str = "models/gemini-2.5-pro"):
        """
        Inizializza ML extractor con Zantara AI

        Args:
            model: Modello Gemini da usare
                - "models/gemini-2.5-pro": Migliore qualità, meno restrittivo (raccomandato con Ultra plan)
                - "models/gemini-2.5-flash": Più veloce, unlimited con Ultra plan
        """
        if not ML_AVAILABLE:
            raise RuntimeError("ZantaraAIClient non disponibile")

        # Con Ultra plan, usa Gemini 2.5 Pro per migliore qualità e meno restrizioni
        self.ai_client = ZantaraAIClient(model=model)
        self.model = model
        print(f"   🤖 ML Extractor inizializzato con modello: {model}")
        if not self.ai_client.is_available():
            raise RuntimeError("Zantara AI non disponibile - verifica GOOGLE_API_KEY")

    async def extract_with_ml_async(
        self, collection_name: str, text: str
    ) -> dict[str, Any]:
        """Estrae metadata usando ML (async)"""
        schema = METADATA_SCHEMAS.get(collection_name, {})
        fields = schema.get("fields", {})

        # Build extraction prompt
        prompt = self._build_extraction_prompt(collection_name, text, fields)

        try:
            # Call Zantara AI (async)
            messages = [{"role": "user", "content": prompt}]

            # Safety settings permissive per estrazione dati legali/fiscali
            # Formato corretto per Gemini API
            import google.generativeai as genai

            safety_settings = [
                {
                    "category": genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                    "threshold": genai.types.HarmBlockThreshold.BLOCK_NONE,
                },
                {
                    "category": genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    "threshold": genai.types.HarmBlockThreshold.BLOCK_NONE,
                },
                {
                    "category": genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    "threshold": genai.types.HarmBlockThreshold.BLOCK_NONE,
                },
                {
                    "category": genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    "threshold": genai.types.HarmBlockThreshold.BLOCK_NONE,
                },
            ]

            result = await self.ai_client.chat_async(
                messages=messages,
                max_tokens=500,
                temperature=0.1,  # Low temperature for consistent extraction
                safety_settings=safety_settings,
            )

            response_text = result.get("text", "")

            # Se response_text è vuoto, potrebbe essere bloccato da safety filters
            if not response_text:
                # Prova a estrarre direttamente dalla risposta raw
                if hasattr(result, "candidates") and result.candidates:
                    candidate = result.candidates[0]
                    if hasattr(candidate, "content") and candidate.content.parts:
                        response_text = candidate.content.parts[0].text

            # Parse JSON from response
            metadata = self._parse_json_response(response_text)

            return metadata

        except Exception as e:
            error_msg = str(e)
            # Se è un safety filter block, ritorna empty (pattern come fallback)
            if "safety" in error_msg.lower() or "blocked" in error_msg.lower():
                print(
                    "   ⚠️ Response bloccato da safety filters, usando pattern fallback"
                )
            else:
                print(f"   ⚠️ Errore ML extraction: {e}")
            return {}

    def extract_with_ml(self, collection_name: str, text: str) -> dict[str, Any]:
        """Estrae metadata usando ML (sync wrapper)"""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self.extract_with_ml_async(collection_name, text)
        )

    def _build_extraction_prompt(
        self, collection_name: str, text: str, fields: dict
    ) -> str:
        """Costruisce prompt per estrazione"""
        field_descriptions = []
        for field_name, field_def in fields.items():
            field_descriptions.append(
                f"- `{field_name}` ({field_def['type']}): {field_def['description']}"
            )

        prompt = f"""Estrai metadata strutturati dal seguente testo secondo lo schema specificato.

COLLEZIONE: {collection_name}

SCHEMA METADATA:
{chr(10).join(field_descriptions)}

TESTO DA ANALIZZARE:
{text[:2000]}  # Limita a 2000 caratteri per efficienza

ISTRUZIONI:
1. Estrai SOLO i campi presenti nel testo
2. Usa valori esatti quando possibile (es. numeri, date, codici)
3. Per campi obbligatori mancanti, usa null
4. Restituisci SOLO un JSON valido, senza spiegazioni
5. Formato: {{"field1": "value1", "field2": 123, "field3": null}}

JSON METADATA:"""

        return prompt

    def _parse_json_response(self, response_text: str) -> dict[str, Any]:
        """Estrae JSON dalla risposta AI"""
        # Try to find JSON in response
        json_patterns = [
            r"\{[^{}]*\}",  # Simple JSON
            r"```json\s*(\{.*?\})\s*```",  # JSON in code block
            r"```\s*(\{.*?\})\s*```",  # JSON in code block without json tag
        ]

        import re

        for pattern in json_patterns:
            match = re.search(pattern, response_text, re.DOTALL)
            if match:
                json_str = match.group(1) if match.groups() else match.group(0)
                try:
                    return json.loads(json_str)
                except:
                    continue

        # Fallback: try to parse entire response as JSON
        try:
            return json.loads(response_text.strip())
        except:
            return {}


class HybridMetadataExtractor:
    """Estrae metadata usando sia pattern che ML"""

    def __init__(self):
        # Import pattern extractor
        import sys
        from pathlib import Path

        scripts_dir = Path(__file__).parent
        sys.path.insert(0, str(scripts_dir))

        try:
            from extract_and_update_metadata import MetadataExtractor
        except ImportError:
            # Fallback: create minimal pattern extractor
            class MetadataExtractor:
                def extract_metadata(self, collection_name: str, text: str) -> dict:
                    return {}

            print("⚠️ Pattern extractor non disponibile, solo ML extraction")
        self.pattern_extractor = MetadataExtractor()

        if ML_AVAILABLE:
            try:
                self.ml_extractor = MLMetadataExtractor()
                self.use_ml = True
            except:
                self.use_ml = False
        else:
            self.use_ml = False

    def extract(
        self, collection_name: str, text: str, use_ml: bool = False
    ) -> dict[str, Any]:
        """Estrae metadata con metodo ibrido"""
        # Pattern-based extraction (veloce)
        pattern_metadata = self.pattern_extractor.extract_metadata(
            collection_name, text
        )

        # ML-based extraction (più accurato ma più lento)
        ml_metadata = {}
        if use_ml and self.use_ml:
            try:
                # ML extraction è async, usa wrapper sync
                ml_metadata = self.ml_extractor.extract_with_ml(collection_name, text)
            except Exception as e:
                print(f"   ⚠️ ML extraction fallita: {e}")

        # Merge: ML ha priorità, pattern come fallback
        merged = pattern_metadata.copy()
        merged.update(ml_metadata)  # ML overwrites pattern

        return merged


def main():
    """Test ML extraction"""
    print("=" * 80)
    print("ZANTARA - ML-Based Metadata Extractor")
    print("=" * 80)

    if not ML_AVAILABLE:
        print("\n❌ ZantaraAIClient non disponibile")
        print("   Assicurati di avere GOOGLE_API_KEY configurato")
        print("\n💡 Per configurare:")
        print("   export GOOGLE_API_KEY='your-api-key'")
        print("   oppure aggiungi a .env: GOOGLE_API_KEY=your-api-key")
        return

    # Check API key
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("\n⚠️ GOOGLE_API_KEY non configurato")
        print("   ML extraction richiede API key Google")
        print("\n💡 Per configurare:")
        print("   export GOOGLE_API_KEY='your-api-key'")
        print("   oppure aggiungi a .env: GOOGLE_API_KEY=your-api-key")
        print("\n✅ Pattern-based extraction disponibile senza API key")
        api_key_available = False
    else:
        api_key_available = True
        print(f"\n✅ GOOGLE_API_KEY configurato ({api_key[:10]}...)")

    # Test samples
    test_samples = {
        "visa_oracle": """
        3. C7 VISA
        Description: Single entry visa designed for professionals like chefs, yoga
        instructors, bartenders, and photographers who are invited to take part in
        events throughout Indonesia.

        Fee: USD 100-200
        Duration: 2-3 weeks
        Application: At Indonesian embassy
        """,
        "kbli_unified": """
        KBLI Code: 12345
        Description: Construction of residential buildings

        Investment Minimum: IDR 10,000,000,000
        Risk Level: Medium-High (MT)
        Required Licenses: NIB, SBU
        """,
    }

    try:
        extractor = HybridMetadataExtractor()

        print("\n🔍 Test Pattern-Based Extraction:")
        for coll_name, text in test_samples.items():
            pattern_meta = extractor.pattern_extractor.extract_metadata(coll_name, text)
            print(f"\n{coll_name}:")
            print(f"   Pattern: {len(pattern_meta)} campi")
            for k, v in list(pattern_meta.items())[:3]:
                print(f"     - {k}: {v}")

        if extractor.use_ml and api_key_available:
            print("\n🤖 Test ML-Based Extraction:")
            for coll_name, text in test_samples.items():
                print(f"\n{coll_name}:")
                try:
                    ml_meta = extractor.ml_extractor.extract_with_ml(coll_name, text)
                    print(f"   ML: {len(ml_meta)} campi")
                    for k, v in list(ml_meta.items())[:3]:
                        print(f"     - {k}: {v}")
                except Exception as e:
                    print(f"   ⚠️ Errore: {str(e)[:100]}")

            print("\n🔄 Test Hybrid Extraction:")
            for coll_name, text in test_samples.items():
                try:
                    hybrid_meta = extractor.extract(coll_name, text, use_ml=True)
                    print(f"\n{coll_name}:")
                    print(f"   Hybrid: {len(hybrid_meta)} campi")
                    for k, v in list(hybrid_meta.items())[:3]:
                        print(f"     - {k}: {v}")
                except Exception as e:
                    print(f"   ⚠️ Errore: {str(e)[:100]}")
        elif extractor.use_ml:
            print("\n⚠️ ML extraction disponibile ma API key non configurata")
            print("   Pattern-based extraction funziona comunque")

        print("\n✅ Test completato!")

    except Exception as e:
        print(f"\n❌ Errore: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
