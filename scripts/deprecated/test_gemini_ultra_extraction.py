#!/usr/bin/env python3
"""
ZANTARA - Test Gemini Ultra per Estrazione Metadata

Con Google AI Ultra plan, possiamo provare Gemini Ultra
che potrebbe avere meno restrizioni rispetto a Flash.
"""

import json
import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "apps" / "backend-rag" / "backend"
sys.path.insert(0, str(backend_path))

# Set minimal env vars
os.environ.setdefault("JWT_SECRET_KEY", "dummy_jwt_secret_key_for_ml_extraction_12345")
os.environ.setdefault("API_KEYS", "{}")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "dummy")
os.environ.setdefault("INSTAGRAM_VERIFY_TOKEN", "dummy")

try:
    import google.generativeai as genai
    from app.core.config import settings
    
    # Configure Gemini
    api_key = os.getenv("GOOGLE_API_KEY") or settings.google_api_key
    if api_key:
        genai.configure(api_key=api_key)
        print(f"✅ Gemini configurato con API key")
    else:
        print("⚠️ GOOGLE_API_KEY non configurato")
        sys.exit(1)
        
except Exception as e:
    print(f"❌ Errore configurazione: {e}")
    sys.exit(1)


def test_model(model_name: str, test_text: str):
    """Testa un modello Gemini specifico"""
    print(f"\n{'='*80}")
    print(f"🧪 TEST MODELLO: {model_name}")
    print(f"{'='*80}")
    
    try:
        # Crea modello
        model = genai.GenerativeModel(model_name)
        
        # Prompt per estrazione metadata
        prompt = f"""Estrai metadata strutturati dal seguente testo.

TESTO:
{test_text}

Estrai i seguenti campi se presenti:
- kbli_code: Codice KBLI
- kbli_description: Descrizione attività
- risk_level: Livello di rischio
- investment_minimum: Investimento minimo

Restituisci SOLO un JSON valido, senza spiegazioni.
Formato: {{"kbli_code": "...", "kbli_description": "...", "risk_level": "...", "investment_minimum": ...}}

JSON:"""

        # Safety settings permissive
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        
        # Genera risposta
        response = model.generate_content(
            prompt,
            safety_settings=safety_settings,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=500,
            )
        )
        
        # Controlla safety ratings
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'safety_ratings'):
                blocked = any(
                    rating.probability.name in ['HIGH', 'MEDIUM'] 
                    for rating in candidate.safety_ratings
                )
                if blocked:
                    print("   ⚠️ Response bloccato da safety filters")
                    print("   Safety ratings:")
                    for rating in candidate.safety_ratings:
                        print(f"     - {rating.category.name}: {rating.probability.name}")
                    return None
        
        # Estrai testo
        if hasattr(response, 'text'):
            response_text = response.text
        elif hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                response_text = candidate.content.parts[0].text
            else:
                print("   ⚠️ Nessun contenuto disponibile")
                return None
        else:
            print("   ⚠️ Nessuna risposta disponibile")
            return None
        
        print(f"   ✅ Risposta ricevuta ({len(response_text)} chars)")
        print(f"\n   📄 Risposta:")
        print(f"   {response_text[:200]}...")
        
        # Prova a parsare JSON
        try:
            # Cerca JSON nella risposta
            import re
            json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                metadata = json.loads(json_str)
                print(f"\n   ✅ JSON parsato: {len(metadata)} campi")
                for k, v in metadata.items():
                    print(f"     - {k}: {v}")
                return metadata
            else:
                print(f"\n   ⚠️ Nessun JSON trovato nella risposta")
                return None
        except Exception as e:
            print(f"\n   ⚠️ Errore parsing JSON: {e}")
            return None
            
    except Exception as e:
        print(f"   ❌ Errore: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Test vari modelli Gemini"""
    print("="*80)
    print("ZANTARA - Test Gemini Ultra per Estrazione Metadata")
    print("="*80)
    
    # Test sample con contenuto legale/fiscale
    test_text = """
    KBLI Code: 20296
    Description: Production of medium‑chain essential oils
    
    Investment Minimum: IDR 10,000,000,000
    Risk Level: Medium‑Low (MR) to Medium‑High (MT)
    Required Licenses: NIB, SBU
    Timeline: 2-4 months
    """
    
    # Modelli da testare
    models_to_test = [
        "gemini-2.5-flash",  # Attuale (bloccato)
        "gemini-2.0-flash-exp",  # Experimental
        "gemini-1.5-pro",  # Pro (potrebbe essere meno restrittivo)
        "gemini-1.5-pro-latest",  # Latest Pro
        "gemini-pro",  # Pro originale
        "gemini-ultra",  # Ultra (se disponibile)
        "models/gemini-2.5-flash",  # Con prefisso models/
        "models/gemini-1.5-pro",  # Pro con prefisso
    ]
    
    print(f"\n📝 Test text (contenuto legale/fiscale):")
    print(f"{test_text[:100]}...")
    
    results = {}
    
    for model_name in models_to_test:
        result = test_model(model_name, test_text)
        results[model_name] = result is not None
    
    # Report finale
    print(f"\n{'='*80}")
    print("📊 REPORT FINALE")
    print(f"{'='*80}")
    
    working_models = [m for m, r in results.items() if r]
    blocked_models = [m for m, r in results.items() if not r]
    
    if working_models:
        print(f"\n✅ MODELLI FUNZIONANTI ({len(working_models)}):")
        for model in working_models:
            print(f"   - {model}")
    else:
        print(f"\n❌ NESSUN MODELLO FUNZIONANTE")
    
    if blocked_models:
        print(f"\n⚠️ MODELLI BLOCCATI ({len(blocked_models)}):")
        for model in blocked_models:
            print(f"   - {model}")
    
    print(f"\n💡 RACCOMANDAZIONE:")
    if working_models:
        print(f"   ✅ Usa: {working_models[0]}")
        print(f"   Questo modello funziona con contenuti legali/fiscali")
    else:
        print(f"   ⚠️ Nessun modello Gemini funziona con contenuti legali")
        print(f"   ✅ Usa Pattern Extraction (gratis, 100% success)")
        print(f"   ✅ Oppure OpenAI GPT-4o-mini ($2.63 per 25k docs)")


if __name__ == "__main__":
    main()

