# Canva Carousel Automation

Genera caroselli Canva automaticamente dal template Bali Zero.

## Setup (una volta sola)

```bash
cd ~/Desktop/nuzantara/scripts/canva

# 1. Autorizza il tuo account Canva
python3 canva_auth.py
# → si apre il browser, clicca "Autorizza"
# → token salvato in ~/.canva_tokens.json
```

## Uso

```bash
# Genera carosello KBLI 2025
python3 canva_carousel.py --template DAHBtCC2-9A --topic kbli_2025

# Ispeziona la struttura del template
python3 canva_carousel.py --template DAHBtCC2-9A --inspect

# Lista topic disponibili
python3 canva_carousel.py --list-topics

# Contenuto custom da JSON
python3 canva_carousel.py --template DAHBtCC2-9A --json my_content.json
```

## Struttura JSON custom

```json
{
  "topic": "Nome carosello",
  "output_name": "nome_file",
  "slides": [
    {
      "title": "TITOLO SLIDE",
      "body": "Testo principale...",
      "highlight": "Testo in evidenza",
      "cta": "Call to action"
    }
  ]
}
```

## Output

Le immagini vengono salvate in `output/<nome>/slide_01.png`, `slide_02.png`, ecc.

## Come funziona

1. `canva_auth.py` — OAuth flow una tantum, salva access + refresh token
2. `canva_client.py` — Client API con auto-refresh token
3. `canva_carousel.py` — Logica generazione: legge template, aggiorna testi, esporta PNG

## Note Canva API

- L'editing testuale richiede che gli elementi abbiano `type: text` accessibili via API
- Se il template usa elementi non modificabili via API, lo script esporta il template così com'è
- L'export PNG può richiedere 10-30 secondi
