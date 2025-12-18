import os

import google.generativeai as genai
from dotenv import load_dotenv

# Load env from apps/backend-rag/.env
load_dotenv("apps/backend-rag/.env")

api_key = os.getenv("GOOGLE_API_KEY")
print(f"Using API Key: {api_key[:10]}...")

genai.configure(api_key=api_key)

print("Listing available models...")
try:
    for m in genai.list_models():
        if "generateContent" in m.supported_generation_methods:
            print(f"- {m.name}")
except Exception as e:
    print(f"Error listing models: {e}")
