# Dockerfile ottimizzato per Hugging Face Spaces - Jaksel AI
# Usa immagine base con Python e CUDA per GPU
FROM python:3.11-slim

# Imposta environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV OLLAMA_HOST=0.0.0.0
ENV PORT=7860
ENV HF_HOME=/data
ENV TRANSFORMERS_CACHE=/data/transformers_cache

# Installa dipendenze di sistema
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Installa Ollama
RUN curl -fsSL https://ollama.ai/install.sh | sh

# Copia l'applicazione
WORKDIR /app
COPY . .

# Installa dipendenze Python
RUN pip install --no-cache-dir fastapi uvicorn python-multipart aiohttp

# Crea directory per il modello
RUN mkdir -p /root/.ollama

# Scarica Jaksel model ( questo avviene al runtime per evitare problemi con HF cache )
# Il modello verrà scaricato al primo avvio

# Script di startup che gestisce il download del modello e avvia Ollama
COPY <<EOF /app/start.sh
#!/bin/bash
echo "🚀 Starting Jaksel AI on Hugging Face Spaces..."

# Assicura che la directory esista
mkdir -p /root/.ollama

# Avvia Ollama in background
echo "📥 Starting Ollama server..."
ollama serve --host 0.0.0.0 --port 11434 &

# Attendi che Ollama sia avviato
echo "⏳ Waiting for Ollama to start..."
sleep 10

# Pull Jaksel model ( se non già presente )
echo "🤖 Pulling Jaksel model..."
ollama pull zantara-jaksel:latest || echo "Model already exists or download failed, continuing..."

# Tenta di nuovo se il primo download fallisce
if ! ollama list | grep -q "zantara-jaksel"; then
    echo "🔄 Retrying model download..."
    sleep 5
    ollama pull zantara-jaksel:latest
fi

# Crea proxy server per gli endpoint HF
python <<PYTHON
import subprocess
import time
import requests
from fastapi import FastAPI, Request
import uvicorn
import json

app = FastAPI(title="Jaksel AI Proxy")

@app.get("/")
async def root():
    return {"message": "Jaksel AI is running!", "status": "healthy"}

@app.get("/health")
async def health():
    try:
        response = requests.get("http://127.0.0.1:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            jaksel_found = any("zantara-jaksel" in m.get("name", "") for m in models)
            return {
                "status": "healthy",
                "ollama": "connected",
                "jaksel_loaded": jaksel_found,
                "models": [m.get("name") for m in models]
            }
        else:
            return {"status": "unhealthy", "ollama": "error"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.post("/api/generate")
@app.post("/api/chat")
async def proxy_ollama(request: Request):
    """Proxy per richieste a Ollama"""
    try:
        # Ottieni body della richiesta
        body = await request.json()

        # Forward a Ollama
        ollama_url = "http://127.0.0.1:11434" + request.scope.get("path", "")

        response = requests.post(
            ollama_url,
            json=body,
            headers={
                "Content-Type": "application/json",
            },
            timeout=120  # Timeout più lungo per HF Spaces
        )

        return Response(
            content=response.content,
            status_code=response.status_code,
            headers={
                "Content-Type": "application/json",
            }
        )
    except Exception as e:
        return {
            "error": f"Proxy error: {str(e)}",
            "response": "Maaf, Jaksel lagi nggak bisa merespon. Coba lagi ya!"
        }

from fastapi.responses import Response

print("🌐 Starting proxy server on port 7860...")
uvicorn.run(app, host="0.0.0.0", port=7860)
PYTHON

# Se il processo termina, aspetta un po' prima di uscire
sleep 30
EOF

# Rendi eseguibile lo script
RUN chmod +x /app/start.sh

# Esponi le porte
EXPOSE 7860 11434

# Comando di avvio
CMD ["/app/start.sh"]