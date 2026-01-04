import os
import google.generativeai as genai

# CLEAN ENV
if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
    del os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
if "GOOGLE_CREDENTIALS_JSON" in os.environ:
    del os.environ["GOOGLE_CREDENTIALS_JSON"]

API_KEY = "AQ.Ab8RN6LeucltUGRQWjV60WEf5aa0iIG_o5urt6fN9yH4lbTS-w"
print(f"Testing API Key: {API_KEY[:5]}...")

try:
    genai.configure(api_key=API_KEY)

    # List models to see what's available and if auth works
    print("Listing models...")
    for m in genai.list_models():
        if "generateContent" in m.supported_generation_methods:
            print(f"- {m.name}")

    print("\nGenerazione di prova con gemini-1.5-flash...")
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content("Sei vivo?")
    print(f"✅ RISPOSTA: {response.text}")

except Exception as e:
    print(f"❌ ERRORE: {e}")
