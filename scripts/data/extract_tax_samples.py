import os
import requests
import json

QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

def search_tax_docs(limit=5):
    headers = {"api-key": QDRANT_API_KEY}
    
    # Cerchiamo documenti che contengono "Pajak" o "PPh" nel testo
    search_payload = {
        "vector": [0.0] * 1536, # Dummy vector, usiamo filter/search
        "filter": {
            "should": [
                {"key": "text", "match": {"text": "Pajak"}},
                {"key": "text", "match": {"text": "PPh"}},
                {"key": "text", "match": {"text": "PPN"}}
            ]
        },
        "limit": limit,
        "with_payload": True
    }
    
    # Nota: Qdrant search richiede un vettore. 
    # Se vogliamo solo filtrare, meglio usare scroll con filtro.
    scroll_payload = {
        "filter": {
            "should": [
                {"key": "metadata.judul", "match": {"text": "Pajak"}}, # Cerca nel titolo
                {"key": "metadata.category", "match": {"text": "tax"}}  # Se categorizzato
            ]
        },
        "limit": limit,
        "with_payload": True
    }

    resp = requests.post(
        f"{QDRANT_URL}/collections/legal_unified_hybrid/points/scroll",
        json=scroll_payload,
        headers=headers,
    )
    
    if resp.status_code != 200:
        print(f"Error searching tax docs: {resp.text}")
        return []
        
    return resp.json().get("result", {}).get("points", [])

print("Extracting TAX samples from legal_unified_hybrid...")
points = search_tax_docs(5)
results = [p.get("payload", {}) for p in points]

print(json.dumps(results, indent=2))
