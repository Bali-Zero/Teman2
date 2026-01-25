import os

from google import genai

# Force the credentials file path (as it is in Docker)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/app/google_credentials.json"
PROJECT_ID = "nuzantara"
LOCATION = "us-central1"
MODEL_ID = "gemini-1.5-flash"  # Use stable model for connectivity test

print("--- Vertex AI Debug ---")
print(f"Google GenAI Version: {genai.__version__}")
print(f"Creds File: {os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')}")
print(f"Exists: {os.path.exists(os.environ['GOOGLE_APPLICATION_CREDENTIALS'])}")

try:
    print(f"Initializing Client(vertexai=True, project={PROJECT_ID}, location={LOCATION})...")
    client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

    print(f"Listing models in location: {LOCATION}...")
    print(f"Listing models in location: {LOCATION}...")

    target_model = "gemini-2.0-flash-001"
    print(f"Testing generation with: {target_model}...")

    response = client.models.generate_content(
        model=target_model, contents="Hello from Vertex AI Gemini 3"
    )
    print("\n✅ SUCCESS!")
    print(f"Response: {response.text}")

except Exception as e:
    print("\n❌ FAILED!")
    print(f"Error: {e}")
