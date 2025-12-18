#!/usr/bin/env python3
"""
Test diretto Gemini 2.5 Pro per estrazione metadata
"""

import os
import json
import google.generativeai as genai

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("⚠️ GOOGLE_API_KEY non configurato")
    exit(1)

genai.configure(api_key=api_key)

test_text = """
KBLI Code: 20296
Description: Production of medium‑chain essential oils
Investment Minimum: IDR 10,000,000,000
Risk Level: Medium‑Low (MR) to Medium‑High (MT)
"""

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

print("="*80)
print("🧪 TEST DIRETTO GEMINI 2.5 PRO")
print("="*80)

# Safety settings - formato corretto
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

try:
    model = genai.GenerativeModel("models/gemini-2.5-pro")
    
    response = model.generate_content(
        prompt,
        safety_settings=safety_settings,
        generation_config=genai.types.GenerationConfig(
            temperature=0.1,
            max_output_tokens=500,
        )
    )
    
    # Check safety e estrai contenuto
    if hasattr(response, 'candidates') and response.candidates:
        candidate = response.candidates[0]
        
        # Check finish_reason
        if hasattr(candidate, 'finish_reason'):
            finish_reason = candidate.finish_reason.name if hasattr(candidate.finish_reason, 'name') else str(candidate.finish_reason)
            print(f"\n📊 Finish Reason: {finish_reason}")
            if finish_reason == 'SAFETY':
                print("   ⚠️ Bloccato da safety filters!")
            elif finish_reason == 'OTHER':
                print("   ⚠️ Terminato per altro motivo")
            elif finish_reason == 'STOP':
                print("   ✅ Terminato normalmente")
            else:
                print(f"   ⚠️ Motivo sconosciuto: {finish_reason}")
        
        # Check safety ratings
        if hasattr(candidate, 'safety_ratings'):
            print("\n📊 Safety Ratings:")
            blocked_any = False
            for rating in candidate.safety_ratings:
                prob = rating.probability.name if hasattr(rating.probability, 'name') else str(rating.probability)
                cat = rating.category.name if hasattr(rating.category, 'name') else str(rating.category)
                print(f"   - {cat}: {prob}")
                if prob in ['HIGH', 'MEDIUM']:
                    blocked_any = True
            
            if blocked_any:
                print("\n⚠️ Alcuni safety ratings sono HIGH/MEDIUM")
            else:
                print("\n✅ Safety ratings OK")
        
        # Debug: mostra struttura completa
        print(f"\n🔍 Debug struttura response:")
        print(f"   response type: {type(response)}")
        print(f"   response attrs: {dir(response)}")
        print(f"   candidate type: {type(candidate)}")
        print(f"   candidate attrs: {dir(candidate)}")
        
        if hasattr(candidate, 'content'):
            print(f"   candidate.content type: {type(candidate.content)}")
            print(f"   candidate.content attrs: {dir(candidate.content)}")
            if hasattr(candidate.content, 'parts'):
                print(f"   candidate.content.parts: {candidate.content.parts}")
        
        # Prova a estrarre contenuto
        answer = None
        try:
            # Metodo 1: response.text
            answer = response.text
            print(f"\n✅ Risposta ricevuta via response.text ({len(answer)} chars)")
        except ValueError as e:
            print(f"\n⚠️ response.text non disponibile: {e}")
            
            # Metodo 2: Estrai da candidate.content.parts
            if hasattr(candidate, 'content'):
                print(f"   candidate.content presente")
                if hasattr(candidate.content, 'parts'):
                    print(f"   candidate.content.parts presente: {len(candidate.content.parts) if candidate.content.parts else 0} parts")
                    if candidate.content.parts:
                        for i, part in enumerate(candidate.content.parts):
                            print(f"   Part {i} type: {type(part)}, attrs: {dir(part)}")
                            if hasattr(part, 'text'):
                                answer = part.text
                                print(f"   ✅ Contenuto estratto da part {i} ({len(answer)} chars)")
                                break
                    else:
                        print("   ⚠️ parts è vuoto")
                else:
                    print("   ⚠️ candidate.content.parts non presente")
            else:
                print("   ⚠️ candidate.content non presente")
        
        # Parse JSON se disponibile
        if answer:
            import re
            json_match = re.search(r'\{[^{}]*\}', answer, re.DOTALL)
            if json_match:
                try:
                    metadata = json.loads(json_match.group(0))
                    print(f"\n✅ JSON parsato: {len(metadata)} campi")
                    for k, v in metadata.items():
                        print(f"   - {k}: {v}")
                except Exception as e:
                    print(f"\n⚠️ Errore parsing JSON: {e}")
    else:
        print("⚠️ Nessuna risposta/candidate disponibile")
        
except Exception as e:
    print(f"❌ Errore: {e}")
    import traceback
    traceback.print_exc()

