# Cowork ↔ Nuzantara Integration

How to wire the Nuzantara stack into **Cowork** (the Claude desktop app) at full
potential **without violating PII / OSINT sovereignty**.

> **Load-bearing fact:** Cowork runs the conversation on Anthropic's **cloud**
> model, not on Pro/Mini. Anything a tool returns lands in a cloud endpoint.
> Therefore CRM client data and intel/OSINT tools must **never** be exposed here
> (UU PDP + project rule "PII assoluta"). They stay on Claude Code / Pro-Mini,
> where you are local-sovereign.

---

## 1. Baseline — what Cowork already has

Connected out of the box in this workspace (generic connectors + plugins):

- Google Drive, Gmail, Google Calendar, Canva, Chrome, computer-use
- **Legal** plugin: Atlassian, Box, DocuSign, Egnyte, MS365, Slack
- **Small-Business** plugin: HubSpot, PayPal, Square, Stripe

None of these are Nuzantara-specific. The blocks below add the Nuzantara
**knowledge layer**.

---

## 2. What we add — the cloud-safe (knowledge) tier

| Server | Tools | PII? | Note |
|---|---|---|---|
| **nuzantara-knowledge** *(new, fail-closed)* | search_kbli, inspect_kbli, chat_kbli, ask_legal, list_visa_types, get_visa_details, calculate_pricing, get_all_prices, search_service_pricing | ✅ none | The crown jewel for client-facing docs/decks. Enforced boundary — see §5. |
| **ga4-analytics** | GA4 traffic for property 505466833 | ✅ none | Website analytics, no client data. |
| **github** | repo read/write | ✅ none | Your code. Needs a PAT. |

**Dual-use (optional, add with caveat):**

| Server | Why caveat |
|---|---|
| notebooklm-mcp | Fine for *knowledge* notebooks (visa/property/tax). **Do not** point it at NB-INTEL notebooks — that's OSINT and must not reach cloud. |
| ocr-tesseract | The OCR engine is local, but the extracted **text** returns into the cloud chat. Never OCR client KTP/passport/akta here — that's the Pro's job. |
| nuzantara-fetch | Redundant with Cowork's built-in web fetch + Chrome. Skip unless you want the exact `mcp-server-fetch` behavior. |

**Deliberately excluded (stay on Pro/Mini only):** `nuzantara-mcp` (full),
`postgres-nuzantara`, `nuzantara-mcp-advanced`, all CRM / intel / drive / comms /
admin tools. See §6.

---

## 3. Paste-ready config

Add in Cowork via **Settings → Connectors → Add custom MCP** (or the desktop
`claude_desktop_config.json` under `~/Library/Application Support/Claude/`).
Merge into `mcpServers`:

```json
{
  "mcpServers": {
    "nuzantara-knowledge": {
      "command": "/Users/balizero/Desktop/nuzantara/apps/nuzantara-mcp/.venv/bin/python",
      "args": ["apps/nuzantara-mcp/nuzantara_mcp/server_knowledge.py"],
      "cwd": "/Users/balizero/Desktop/nuzantara",
      "env": {
        "PYTHONPATH": "apps/nuzantara-mcp",
        "NUZANTARA_API_KEY": "<PASTE_NUZANTARA_API_KEY>"
      }
    },
    "ga4-analytics": {
      "command": "/Users/balizero/Desktop/nuzantara/.mcp-servers/ga4-analytics/.venv/bin/ga4-mcp-server",
      "env": {
        "GOOGLE_APPLICATION_CREDENTIALS": "/Users/balizero/Desktop/nuzantara/.secrets/google-credentials.json",
        "GA4_PROPERTY_ID": "505466833"
      }
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "<PASTE_GITHUB_PAT>"
      }
    }
  }
}
```

> **Secrets:** the Cowork desktop config does **not** do `${VAR}` shell
> expansion like the Claude Code `.mcp.json`. Paste literal values for
> `NUZANTARA_API_KEY` and the GitHub PAT (or confirm Cowork's env handling
> first). Do **not** commit a config that contains live secrets.

Optional dual-use blocks (append to `mcpServers` only if you accept the §2
caveats):

```json
"notebooklm-mcp": { "command": "/Users/balizero/.local/bin/notebooklm-mcp" },
"ocr-tesseract": {
  "command": "/Users/balizero/Desktop/nuzantara/.mcp-servers/ocr/.venv/bin/mcp-ocr",
  "env": { "TESSDATA_PREFIX": "/opt/homebrew/share/tessdata" }
}
```

---

## 4. Prerequisites checklist (this machine)

- [ ] `apps/nuzantara-mcp/.venv/` exists and has `fastmcp` + `httpx` installed
- [ ] `NUZANTARA_API_KEY` available (and Fly backend `nuzantara-rag.fly.dev` reachable)
- [ ] `.mcp-servers/ga4-analytics/.venv/` built + `.secrets/google-credentials.json` present (for GA4)
- [ ] GitHub PAT with the scopes you want (for github)
- [ ] Restart Cowork after editing the config (MCP servers load at startup)

Verify the knowledge server boots before adding it to Cowork:

```bash
cd ~/Desktop/nuzantara
PYTHONPATH=apps/nuzantara-mcp NUZANTARA_API_KEY=dummy \
  timeout 3 apps/nuzantara-mcp/.venv/bin/python \
  apps/nuzantara-mcp/nuzantara_mcp/server_knowledge.py
echo "exit=$?   # 124 (timed out waiting for stdio) = boots clean. Any import traceback = fix it."
```

---

## 5. The enforced boundary

`server_knowledge.py` builds a **fresh** FastMCP instance and registers **only**
the `knowledge` + `pricing` modules. It is fail-closed by construction: a CRM or
intel module is reachable only if explicitly imported there. Add a new PII tool
to `server.py` and it will **not** leak into Cowork.

This is the "write the boundary in code, not in docs" rule applied — the
guarantee is the import list, not operator discipline.

---

## 6. What stays OUT of Cowork — and why

| Tool / server | Reason |
|---|---|
| `list_clients`, `get_client`, `create_client`, `get_practice`, `get_client_*` | Client PII → cloud = UU PDP violation |
| `postgres-nuzantara` (readonly CRM DB) | Same — returns client records |
| `intel`, `intel_alerts`, `intel_pipeline`, `intel_trends`, `kg_intel` | OSINT sovereignty — intel never leaves Pro |
| CRM-Guardian / drive / OCR of client docs | Passport/KTP/akta PII |
| comms / admin / federation / prime | Operational + write surface, run from Claude Code |

These continue to run on **Claude Code (Pro/Mini)** via the full `.mcp.json`,
where everything is local and sovereign.

---

## 7. Skills & plugins

- **Plugins:** Cowork already has the Legal + Small-Business plugins. There is no
  Nuzantara-specific Cowork plugin; the Nuzantara surface is the custom MCP above.
- **Skills:** your repo skills (`~/.claude/skills/`, `infra/claude-skills/`) are
  **Claude Code** skills — a different mechanism from Cowork's plugin/marketplace
  skills. They are not auto-portable. If you want one in Cowork (e.g. a KBLI or
  pricing skill), it has to be packaged as a Cowork skill separately.

---

_Last reviewed: 2026-06-07. Companion file: `apps/nuzantara-mcp/nuzantara_mcp/server_knowledge.py`._
