# Fly.io — Imbarcare `claude` CLI per OAuth Migration

**Stato:** proposta. Blocca il merge di `opus47-routing-audit` finché non applicato.
**Obiettivo:** rendere eseguibile `backend.llm.claude_oauth_client.complete_async` in container Fly.io.

## Contesto

Post-commit `5d95abfa9`:

- 4 call site backend (article_composer, coreference, multi_ai_adapter, kg_langgraph) chiamano `claude -p` via subprocess
- In locale (Pro) funziona perché `~/.local/bin/claude` è installato e il token OAuth è in keychain
- **In container Fly.io il binario non esiste → crash al primo call Claude**

## Approccio consigliato: npm-install nello stage runtime

Il CLI `@anthropic-ai/claude-code` è distribuito come npm package. Richiede Node.js >= 18.

### Patch Dockerfile (applicare in `apps/backend-rag/Dockerfile`)

```diff
 # Stage 2: Runtime Stage
 # ========================================
 FROM python:3.11-slim

-# Install only runtime dependencies (curl for healthcheck)
-RUN apt-get update && apt-get install -y \
-    curl \
-    && rm -rf /var/lib/apt/lists/*
+# Install runtime dependencies:
+# - curl: healthcheck
+# - nodejs 20.x: required by the `claude` CLI (Claude Code),
+#   used by backend/llm/claude_oauth_client.py for Max OAuth calls.
+# The CLI is ~40MB on disk post-install; acceptable trade-off to avoid
+# ANTHROPIC_API_KEY billing (project policy, see feedback_claude_oauth_only.md).
+RUN apt-get update && apt-get install -y curl ca-certificates gnupg \
+    && mkdir -p /etc/apt/keyrings \
+    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
+        | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
+    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
+        > /etc/apt/sources.list.d/nodesource.list \
+    && apt-get update \
+    && apt-get install -y --no-install-recommends nodejs \
+    && npm install -g @anthropic-ai/claude-code \
+    && npm cache clean --force \
+    && apt-get remove -y gnupg \
+    && apt-get autoremove -y \
+    && rm -rf /var/lib/apt/lists/* /root/.npm
```

### Verify nella build

Aggiungere check end-of-stage:

```dockerfile
RUN which claude && claude --version
```

### Impact sull'image size

- Node.js 20.x slim: ~90MB
- `@anthropic-ai/claude-code` globale: ~40MB
- **Totale:** ~130MB sull'image finale (attualmente ~2GB ML → +6%)

## Secret Fly.io

I token OAuth vanno iniettati come **secrets** (non `[env]` in fly.toml — sono sensibili).

### Setup primario

```bash
# Recupera il token dal file locale (mai committare):
CLAUDE_TOKEN=$(grep "^CLAUDE_CODE_OAUTH_TOKEN=" \
  /Users/nuzantara/Desktop/codexyz/NUZANTARA_ENV_KEYS.env | cut -d= -f2-)

fly secrets set -a nuzantara-rag \
  CLAUDE_CODE_OAUTH_TOKEN="$CLAUDE_TOKEN"
```

### Setup 3-token fallback (opzionale, consigliato)

Se hai 3 account Max:

```bash
fly secrets set -a nuzantara-rag \
  CLAUDE_CODE_OAUTH_TOKEN_1="<primary>" \
  CLAUDE_CODE_OAUTH_TOKEN_2="<secondary>" \
  CLAUDE_CODE_OAUTH_TOKEN_3="<tertiary>"
```

Il wrapper prova 1 → 2 → 3 → legacy → keychain (quest'ultimo fallisce in container, solo best-effort).

### Verifica iniezione

```bash
fly ssh console -a nuzantara-rag -C \
  "python -c 'import os; print(bool(os.getenv(\"CLAUDE_CODE_OAUTH_TOKEN\")))'"
# expected: True
```

## Rollback plan

Se dopo il deploy i call Claude falliscono, escape hatch istantaneo:

```bash
# Forza il fallback OpenAI su KG reasoning senza rebuild
fly secrets set -a nuzantara-rag KG_REASONING_PROVIDER=openai
```

**Nota:** questo copre solo `kg_langgraph_orchestrator`. I 3 call site non-LangChain (`article_composer`, `coreference`, `multi_ai_adapter`) **non hanno fallback** — se il CLI crasha, crashano loro.

### Fallback più robusto (post-deploy, se necessario)

Aggiungere in `claude_oauth_client.py` un guard che, se `which claude` fallisce all'import, imposta un flag `CLAUDE_CLI_AVAILABLE = False` e fa raise di un `ClaudeOAuthNotAvailable` con messaggio chiaro. I 3 caller possono testarlo all'init e degradare (silent skip, Gemini fallback, o errore esplicito al chiamante).

## Checklist operativa

1. [ ] Applicare patch Dockerfile su branch `opus47-routing-audit` (o nuovo branch `infra/claude-cli-in-image`)
2. [ ] Build locale: `cd ~/Desktop/nuzantara && docker build -f apps/backend-rag/Dockerfile -t rag-claude-test .`
3. [ ] Test locale del binario: `docker run --rm rag-claude-test claude --version`
4. [ ] `fly secrets set CLAUDE_CODE_OAUTH_TOKEN=... -a nuzantara-rag`
5. [ ] Deploy staging prima di produzione: `fly deploy --app nuzantara-rag --strategy rolling`
6. [ ] Smoke test live: `curl https://nuzantara-rag.fly.dev/api/article-composer/compose/status` — deve ritornare `model=claude-sonnet-4-6`
7. [ ] End-to-end test: un call article-composer reale da staging/preview
8. [ ] Monitorare logs per 24h: cercare `🚨` (policy violation logs), `ClaudeOAuthError`, `ClaudeOAuthNotAvailable`

## Alternative considerate e scartate

- **Keychain-based auth in container**: impossibile, macOS-only
- **Curl-based HTTP a claude.ai/api**: l'endpoint OAuth non è documentato ufficialmente, rischio rottura
- **Anthropic SDK con OAuth token**: il SDK non supporta OAuth Max (accetta solo API key). Lasciato come issue upstream
