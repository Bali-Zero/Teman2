---
title: Jaksel AI Assistant
emoji: 🤖
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
license: mit
app_port: 7860
---

# Jaksel AI Assistant on Hugging Face Spaces

Jaksel is a multilingual AI assistant with Jakarta Selatan personality, powered by Gemma 9B fine-tuned model.

## Features

- 🤖 **Multilingual Support**: Responds in Italian, English, Bahasa Indonesia, and Chinese
- 🎭 **Jaksel Personality**: Casual, friendly Jakarta Selatan style
- ⚡ **Fast GPU Inference**: Powered by Hugging Face Spaces free GPU
- 🔄 **API Compatible**: Compatible with Ollama API format

## API Usage

### Generate Response
```bash
curl -X POST https://YOUR_USERNAME-jaksel.hf.space/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "zantara-jaksel:latest",
    "prompt": "Halo Kak Jaksel! Apa kabar?",
    "stream": false
  }'
```

### Health Check
```bash
curl https://YOUR_USERNAME-jaksel.hf.space/health
```

## Integration with Nuzantara

This endpoint is designed to work with the Nuzantara backend system. Update your `SimpleJakselCaller` to point to this URL.

## Model Details

- **Base Model**: Gemma 9B
- **Fine-tuned**: zantara-jaksel
- **Personality**: Jakarta Selatan casual style
- **Languages**: Indonesian primary, with multilingual capabilities

## Performance

- **GPU**: T4 (free tier)
- **RAM**: 16 GB
- **Response Time**: ~2-5 seconds

Made with ❤️ for Nuzantara project
