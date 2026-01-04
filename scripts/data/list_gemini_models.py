import os
from google import genai

# PULIZIA ENV
if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
    del os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
if "GOOGLE_CREDENTIALS_JSON" in os.environ:
    del os.environ["GOOGLE_CREDENTIALS_JSON"]


def list_vertex_models():
    print("🔍 Scouting Modelli su Vertex AI (Project: nuzantara)...")
    try:
        # Usiamo ADC
        client = genai.Client(
            vertexai=True, project="nuzantara", location="us-central1"
        )

        models = client.models.list()
        print("\nModelli trovati:")
        found = False
        for m in models:
            # Stampiamo solo quelli che sembrano Gemini
            if "gemini" in m.name.lower():
                print(f"- Nome: {m.name} | Modello: {m.base_model_id}")
                found = True

        if not found:
            print(
                "❌ Nessun modello Gemini trovato. Probabilmente l'API 'aiplatform.googleapis.com' non è abilitata o non hai i permessi."
            )

    except Exception as e:
        print(f"❌ Errore durante la list: {e}")


if __name__ == "__main__":
    list_vertex_models()
