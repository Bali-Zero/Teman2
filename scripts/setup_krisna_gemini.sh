#!/usr/bin/env bash
# setup_krisna_gemini.sh — Setup Gemini CLI per Krisna Arimbawa
#
# Questo script configura Gemini CLI con:
# - Profilo Google separato (account Krisna)
# - MCP nuzantara già configurati
# - GEMINI.md con contesto CRM
# - Trusted folder per il repo
#
# Usage: bash scripts/setup_krisna_gemini.sh
# Da eseguire sul Mac di Krisna con il repo già clonato

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GEMINI_DIR="$HOME/.gemini"
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${BLUE}[setup]${NC} $1"; }
ok()   { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }

echo ""
echo "═══════════════════════════════════════════════════"
echo "  Gemini CLI Setup — Krisna Arimbawa / Nuzantara"
echo "═══════════════════════════════════════════════════"
echo ""

# ─── Step 1: Verifica Gemini CLI installato ───────────────────────────────────
log "Verifica Gemini CLI..."
if ! command -v gemini &>/dev/null; then
    warn "Gemini CLI non trovato. Installazione..."
    npm install -g @google/gemini-cli
fi
GEMINI_VERSION=$(gemini --version 2>/dev/null | head -1)
ok "Gemini CLI: $GEMINI_VERSION"

# ─── Step 2: Crea directory config ────────────────────────────────────────────
mkdir -p "$GEMINI_DIR"
log "Config dir: $GEMINI_DIR"

# ─── Step 3: Scrivi settings.json con MCP ─────────────────────────────────────
log "Scrittura settings.json con MCP servers..."

cat > "$GEMINI_DIR/settings.json" << 'SETTINGS_EOF'
{
  "security": {
    "auth": {
      "selectedType": "oauth-personal"
    },
    "enablePermanentToolApproval": true,
    "folderTrust": {
      "enabled": true
    },
    "environmentVariableRedaction": {
      "enabled": false
    }
  },
  "general": {
    "previewFeatures": true,
    "enableAutoUpdate": true,
    "defaultApprovalMode": "default"
  },
  "ui": {
    "showStatusInTitle": true,
    "showModelInfoInChat": true
  },
  "mcpServers": {
    "nuzantara": {
      "command": "python",
      "args": [
        "apps/nuzantara-mcp/nuzantara_mcp/server.py"
      ],
      "cwd": "REPLACE_WITH_PROJECT_ROOT",
      "env": {
        "NUZANTARA_BACKEND_URL": "https://nuzantara-rag.fly.dev",
        "NUZANTARA_TIMEOUT": "30",
        "NUZANTARA_API_KEY": "",
        "VIRTUAL_ENV": "REPLACE_WITH_PROJECT_ROOT/apps/nuzantara-mcp/.venv",
        "PYTHONPATH": "REPLACE_WITH_PROJECT_ROOT/apps/nuzantara-mcp",
        "PATH": "REPLACE_WITH_PROJECT_ROOT/apps/nuzantara-mcp/.venv/bin:/usr/local/bin:/usr/bin:/bin"
      }
    }
  }
}
SETTINGS_EOF

# Replace placeholder with actual project root
sed -i '' "s|REPLACE_WITH_PROJECT_ROOT|$PROJECT_ROOT|g" "$GEMINI_DIR/settings.json"
ok "settings.json scritto con MCP nuzantara"

# ─── Step 4: Trusted folder per il repo ───────────────────────────────────────
log "Aggiunta trusted folder..."
cat > "$GEMINI_DIR/trustedFolders.json" << TRUST_EOF
{
  "$PROJECT_ROOT": "TRUST_PARENT"
}
TRUST_EOF
ok "Trusted: $PROJECT_ROOT"

# ─── Step 5: GEMINI.md globale per Krisna ────────────────────────────────────
log "Scrittura GEMINI.md globale..."
cat > "$GEMINI_DIR/GEMINI.md" << 'GEMINI_EOF'
# Gemini CLI — Nuzantara CRM Assistant (Krisna)

## Identità
Sei un AI assistant tecnico per il team Nuzantara/Bali Zero.
- Parla **italiano** o **inglese** (segui la lingua di Krisna)
- Sei diretto, tecnico, concreto — non sei un chatbot cliente
- Hai accesso al backend Nuzantara tramite MCP tools

## Il Tuo Ruolo (Krisna)
- **Team CRM** — gestisci clienti, pratiche, compliance
- Puoi consultare dati CRM, timeline clienti, alert scadenze
- Puoi fare health check del sistema
- Per modifiche al codice → segnala a Zero

## MCP Tools Disponibili (nuzantara-mcp)

### CRM & Clienti
- `list_clients` — lista clienti con filtri
- `get_client` — dettaglio singolo cliente
- `get_client_timeline` — timeline eventi cliente
- `get_client_compliance` — stato compliance
- `get_expiry_alerts` — scadenze imminenti
- `get_compliance_alerts` — alert compliance
- `list_practices` — lista pratiche
- `get_practice` — dettaglio pratica

### Analytics
- `get_client_stats` — statistiche CRM
- `get_completion_rates` — tassi completamento
- `get_revenue_analytics` — analytics ricavi

### Sistema
- `check_health` — health check rapido backend
- `check_health_detailed` — health check dettagliato

## Come Usare i Tool

Quando cerchi info su un cliente:
```
/mcp nuzantara get_client {"name": "Mario Rossi"}
```

Quando vuoi la lista pratiche in scadenza:
```
/mcp nuzantara get_expiry_alerts {"days": 30}
```

## Stack (solo FYI)
- Backend: FastAPI su Fly.io (nuzantara-rag.fly.dev)
- Frontend: kita.balizero.com (Next.js, Vercel)
- DB: PostgreSQL + Qdrant (Fly.io)
- Repo: monorepo in questo folder

## Regole Anti-Allucinazione
- **Leggi il file** prima di commentarlo
- **Usa i tool MCP** per dati reali — non inventare
- Se non sai, dillo
GEMINI_EOF
ok "GEMINI.md globale scritto"

# ─── Step 6: GEMINI.md nel progetto (context locale) ─────────────────────────
# Il progetto ha già CLAUDE.md — aggiungiamo un GEMINI.md specifico solo se non esiste
if [ ! -f "$PROJECT_ROOT/GEMINI.md" ]; then
    log "Scrittura GEMINI.md nel progetto..."
    cat > "$PROJECT_ROOT/GEMINI.md" << 'PROJ_GEMINI_EOF'
# GEMINI.md — Nuzantara Project (Krisna)

> Vedi ~/.gemini/GEMINI.md per il contesto completo.
> Per l'architettura dettagliata vedi CLAUDE.md.

## Quick Reference

**Backend:** `apps/backend-rag/` — FastAPI, Python 3.11, `.venv`
**Frontend:** `apps/mouth/` — Next.js, TypeScript
**MCP:** `apps/nuzantara-mcp/` — 109 tools
**Deploy backend:** `fly deploy --strategy rolling` (da `apps/backend-rag/`)
**Deploy frontend:** `git push origin main` (auto Vercel)

## CRM API (Krisna)
- Endpoint: `https://nuzantara-rag.fly.dev/api/crm/`
- Auth: JWT Bearer (ottieni da kita.balizero.com login)
- Swagger: `https://nuzantara-rag.fly.dev/docs`
PROJ_GEMINI_EOF
    ok "GEMINI.md progetto scritto"
else
    ok "GEMINI.md progetto già esiste — non sovrascritto"
fi

# ─── Step 7: Login Google ─────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
echo "  STEP FINALE: Login con il tuo account Google"
echo "═══════════════════════════════════════════════════"
echo ""
warn "Adesso devi fare login con il TUO account Google (non quello aziendale)."
warn "Si aprirà il browser — seleziona il tuo account personale Google."
echo ""
echo "Premi INVIO per avviare il login..."
read -r

gemini auth login

echo ""
ok "Setup completato!"
echo ""
echo "Per testare:"
echo "  cd $PROJECT_ROOT"
echo "  gemini"
echo ""
echo "Poi prova: 'check health del sistema'"
