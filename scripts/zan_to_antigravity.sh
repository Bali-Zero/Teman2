#!/bin/bash
# NUZANTARA BRIDGE: ZAN (OpenClaw) -> Antigravity IDE
# Utilizzo: ./zan_to_antigravity.sh "Il tuo prompt qui"

TASK="$1"
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")
CONTEXT_FILE="/Users/nuzantara/Desktop/nuzantara/.antigravity/context.md"

if [ -z "$TASK" ]; then
    echo "Errore: Nessun task fornito."
    exit 1
fi

# 1. Iniezione nel file di contesto di Antigravity
echo -e "

## 🚨 TASK PRIORITARIO DA WHATSAPP (via ZAN)
**Ricevuto:** $TIMESTAMP
**Comando:** $TASK

> *Nota per gli Agenti Antigravity: Interrompete il refactoring corrente e analizzate questa richiesta immediatamente.*" >> "$CONTEXT_FILE"

# 2. Notifica sonora sul Mac (per farti capire che il comando è arrivato al cuore del sistema)
say "ZAN has updated Antigravity context."

# 3. Output per ZAN
echo "✅ Context Injected! Ho aggiunto il comando al 'cervello' di Antigravity. Gli agenti nell'IDE vedranno il task non appena analizzeranno il contesto."
