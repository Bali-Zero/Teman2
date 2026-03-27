#!/usr/bin/env bash
# setup_ruslana_gemini.sh — Setup Gemini CLI per Ruslana
#
# Configura Gemini CLI con:
# - Account ruslana@balizero.com
# - MCP nuzantara già configurati
# - GEMINI.md con contesto Board Member
# - Trusted folder per il repo
#
# Usage: bash scripts/setup_ruslana_gemini.sh
# Da eseguire sul Mac di Ruslana con il repo già clonato

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GEMINI_DIR="$HOME/.gemini"
RUSLANA_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIzNmRlMDI1ZC0xYjM4LTRhMmUtODI5Mi00ZTIwZGM2YmJjNGMiLCJlbWFpbCI6InJ1c2xhbmFAYmFsaXplcm8uY29tIiwicm9sZSI6IkJvYXJkIE1lbWJlciIsImV4cCI6MTgwNjEyNDkwMn0._dmDDDJqsVeCc1IYzBfpqoUfo67VU7tPX4fbtqsDARE"
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${BLUE}[setup]${NC} $1"; }
ok()   { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }

echo ""
echo "═══════════════════════════════════════════════════"
echo "  Gemini CLI Setup — Ruslana / Nuzantara Board"
echo "═══════════════════════════════════════════════════"
echo ""

# ─── Step 1: Verifica Gemini CLI ──────────────────────────────────────────────
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

# ─── Step 3: settings.json con MCP ────────────────────────────────────────────
log "Scrittura settings.json con MCP servers..."
cat > "$GEMINI_DIR/settings.json" << SETTINGS_EOF
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
      "command": "REPLACE_WITH_PROJECT_ROOT/apps/nuzantara-mcp/.venv/bin/python",
      "args": [
        "REPLACE_WITH_PROJECT_ROOT/apps/nuzantara-mcp/nuzantara_mcp/server.py"
      ],
      "env": {
        "NUZANTARA_BACKEND_URL": "https://nuzantara-rag.fly.dev",
        "NUZANTARA_TIMEOUT": "30",
        "NUZANTARA_API_KEY": "$RUSLANA_TOKEN",
        "PYTHONPATH": "REPLACE_WITH_PROJECT_ROOT/apps/nuzantara-mcp",
        "PATH": "REPLACE_WITH_PROJECT_ROOT/apps/nuzantara-mcp/.venv/bin:/usr/local/bin:/usr/bin:/bin"
      }
    }
  }
}
SETTINGS_EOF

sed -i '' "s|REPLACE_WITH_PROJECT_ROOT|$PROJECT_ROOT|g" "$GEMINI_DIR/settings.json"
ok "settings.json scritto con MCP nuzantara"

# ─── Step 4: Trusted folder ────────────────────────────────────────────────────
log "Aggiunta trusted folder..."
cat > "$GEMINI_DIR/trustedFolders.json" << TRUST_EOF
{
  "$PROJECT_ROOT": "TRUST_PARENT"
}
TRUST_EOF
ok "Trusted: $PROJECT_ROOT"

# ─── Step 5: GEMINI.md globale per Ruslana ────────────────────────────────────
log "Scrittura GEMINI.md globale..."
cat > "$GEMINI_DIR/GEMINI.md" << 'GEMINI_EOF'
# Gemini CLI — Nuzantara Board Assistant (Ruslana)

## Identità
Sei un AI assistant interno per il board di Nuzantara/Bali Zero.
- Parla **italiano** o **inglese** con Ruslana
- Sei diretto, concreto — fornisci dati reali, non stime
- Hai accesso completo al backend Nuzantara tramite MCP tools

## Il Tuo Ruolo (Ruslana — Board Member)
- **Board permanente** — visione completa sull'azienda
- Accesso a tutte le analytics: revenue, clienti, compliance, team
- Puoi richiedere report su qualsiasi metrica aziendale
- Per bug/deploy → segnala a Zero

## MCP Tools Disponibili (nuzantara-mcp)

### Analytics & Revenue
- `get_revenue_analytics` — analytics ricavi
- `get_client_stats` — statistiche CRM
- `get_completion_rates` — tassi completamento pratiche
- `get_team_productivity` — produttività team
- `get_intel_metrics` — metriche intelligence
- `get_sla_compliance` — compliance SLA

### Compliance & Alert
- `get_compliance_alerts` — alert compliance
- `get_compliance_summary` — sommario compliance
- `get_critical_alerts` — alert critici
- `get_expiry_alerts` — scadenze imminenti

### CRM & Clienti
- `list_clients` — lista clienti
- `get_client` — dettaglio cliente
- `get_client_timeline` — timeline eventi
- `get_client_compliance` — compliance singolo cliente
- `list_practices` — lista pratiche

### Sistema
- `check_health` — health check rapido
- `check_health_detailed` — health check dettagliato

## Come Usare i Tool

Revenue del mese:
```
/mcp nuzantara get_revenue_analytics {}
```

Clienti in scadenza nei prossimi 30 giorni:
```
/mcp nuzantara get_expiry_alerts {"days": 30}
```

## Stack (FYI)
- Backend: FastAPI su Fly.io (nuzantara-rag.fly.dev)
- Frontend: kita.balizero.com (Next.js, Vercel)
- Repo: ~/Desktop/nuzantara

## Regole
- Usa i tool MCP per dati reali — non inventare mai
- Se non sai, di' "verifico"
- Per azioni irreversibili → chiedi conferma
GEMINI_EOF
ok "GEMINI.md globale scritto"

# ─── Step 6: GEMINI.md nel progetto ──────────────────────────────────────────
if [ ! -f "$PROJECT_ROOT/GEMINI.md" ]; then
    log "Scrittura GEMINI.md nel progetto..."
    cat > "$PROJECT_ROOT/GEMINI.md" << 'PROJ_GEMINI_EOF'
# GEMINI.md — Nuzantara Project (Ruslana)

> Vedi ~/.gemini/GEMINI.md per il contesto completo.
> Per l'architettura dettagliata vedi CLAUDE.md.

## Quick Reference

**Backend:** `apps/backend-rag/` — FastAPI, Python 3.11
**Frontend:** `apps/mouth/` — Next.js, TypeScript
**MCP:** `apps/nuzantara-mcp/` — 109+ tools
**Swagger:** `https://nuzantara-rag.fly.dev/docs`
**Workspace:** `https://kita.balizero.com`
PROJ_GEMINI_EOF
    ok "GEMINI.md progetto scritto"
else
    ok "GEMINI.md progetto già esiste — non sovrascritto"
fi

# ─── Step 7: Login Google ──────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
echo "  STEP FINALE: Login con ruslana@balizero.com"
echo "═══════════════════════════════════════════════════"
echo ""
warn "Adesso fai login con l'account Google AZIENDALE: ruslana@balizero.com"
warn "Si aprirà il browser — seleziona quell'account."
echo ""
echo "Premi INVIO per avviare il login..."
read -r

gemini auth login

echo ""
ok "Setup Gemini completato!"
echo ""
echo "Per testare:"
echo "  cd $PROJECT_ROOT"
echo "  gemini"
echo "  > mostrami le analytics revenue"
echo ""
