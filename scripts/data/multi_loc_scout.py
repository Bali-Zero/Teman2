from google import genai

locations = ["us-central1", "europe-west1", "asia-southeast1", "us-east4"]

for loc in locations:
    print(f"\n--- Scouting in {loc} ---")
    try:
        client = genai.Client(vertexai=True, project="nuzantara", location=loc)
        models = client.models.list()
        for m in models:
            if "gemini" in m.name.lower():
                print(f"✅ TROVATO: {m.name} in {loc}")
    except Exception as e:
        print(f"❌ Fallito in {loc}: {str(e)[:100]}")
