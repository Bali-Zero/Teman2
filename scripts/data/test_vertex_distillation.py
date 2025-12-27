import os
import sys
import asyncio
import json
import requests
from typing import List, Dict, Any

# CONFIGURAZIONE: Carichiamo dal file creato via shell
CREDS_PATH = os.path.join(os.getcwd(), "scripts/data/sa_nuzantara.json")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDS_PATH

# Pulizia ambiente
for key in ["GOOGLE_CREDENTIALS_JSON", "GOOGLE_API_KEY", "GOOGLE_CLOUD_PROJECT"]:
    if key in os.environ: del os.environ[key]

sys.path.append(os.path.join(os.getcwd(), "apps/backend-rag/backend"))

QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

async def process():
    print("🚀 NUZANTARA BOT DISTILLATION (Service Account File)")
    
    if not os.path.exists(CREDS_PATH):
        print(f"❌ File credenziali non trovato in {CREDS_PATH}")
        return

    try:
        from google import genai
        # Carichiamo il project_id dal file
        with open(CREDS_PATH) as f:
            creds = json.load(f)
            project_id = creds["project_id"]
            
        client = genai.Client(vertexai=True, project=project_id, location="us-central1")
        print(f"✅ BOT AUTH SUCCESSFUL (Project: {project_id})")
        
        headers = {"api-key": QDRANT_API_KEY}
        resp = requests.post(f"{QDRANT_URL}/collections/training_conversations/points/scroll",
                            json={"limit": 10, "with_payload": True}, headers=headers)
        conversations = [p.get("payload", {}) for p in resp.json().get("result", {}).get("points", [])]
        
        results = []
        for i, conv in enumerate(conversations):
            text = conv.get("text", "")[:4000]
            topic = conv.get("topic", "Unknown")
            print(f"   ⚡ [{i+1}/10] Distilling: {topic}...")
            response = client.models.generate_content(
                model="gemini-3-flash-preview", 
                contents=f"Estrai conoscenza in JSON da questo testo:\n\n{text}",
                config={"response_mime_type": "application/json"}
            )
            results.append({"topic": topic, "distilled": json.loads(response.text)})
            print(f"      ✅ OK.")
            
        output_path = "data/datasets/gold/bot_distilled_10.json"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n✨ COMPLETATO! File: {output_path}")
        
    except Exception as e:
        print(f"❌ ERRORE: {e}")

if __name__ == "__main__":
    asyncio.run(process())
