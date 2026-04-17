# Pro-2 §7 P0 Findings — Review post-migrazione OAuth

**Branch:** `opus47-routing-audit`
**Status aggregato:** 3/4 P0 risolti in codice, 1 P0 parziale blocca il deploy

## Tabella stato

| P0   | Finding originale                          | Status                       | Commit                                          | Note                                                                                                                           |
| ---- | ------------------------------------------ | ---------------------------- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| P0.1 | Abilitare `cache_control` su 2 path Claude | **✅ fatto** (ma non attivo) | `23673a89a` → rollback implicito in `5d95abfa9` | Il `claude` CLI non espone cache_control; l'intento è nel codice ma inerte. Ritorna utile solo se passiamo a transport diverso |
| P0.2 | Bumpare `claude-3-opus-20240229` stale     | **✅ risolto**               | `c1e5aef80`                                     | Bump da opus-3 a sonnet-4-6 su tutti i pin (multi_ai_adapter, article_composer, coreference, pipeline)                         |
| P0.3 | Decidere KG LangGraph OpenAI vs Anthropic  | **✅ risolto**               | `5d95abfa9`                                     | KG ora preferisce Claude via OAuth subprocess (sonnet-4-6), OpenAI fallback esplicito via `KG_REASONING_PROVIDER=openai`       |
| —    | Migration 111 (notification_log)           | **⏳ in attesa**             | —                                               | Va applicata su dev/prod DB prima di attivare `portal_deadline_watchdog` cron                                                  |

## Decisioni di deploy — 3 punti da scegliere

### Decisione 1: quando mergere `opus47-routing-audit`

**Opzione A (consigliata):** prima il Dockerfile update, poi il merge

- Fare PR separato `infra/claude-cli-in-image` con solo la patch Dockerfile (~15 righe)
- Deploy staging, verifica `claude` CLI funziona nel container
- **Poi** mergere `opus47-routing-audit`
- **Rischio:** zero. Il container nuovo ha il CLI prima che il codice dipenda da esso.

**Opzione B (rischiosa):** merge simultaneo

- Dockerfile + codice nello stesso merge
- **Rischio:** un bug nella patch Docker fa crashare l'image e il rollback richiede rebuild.

**Opzione C (più conservativa):** merge senza rollout Fly.io

- Mergere `opus47-routing-audit` su main ma **non deployare** su Fly.io finché Dockerfile non è pronto
- Il codice sta su `origin/main` ma produzione continua con l'image vecchia (che ha ancora il vecchio claude_client.py? no, sarebbe fuori sync)
- **Problema:** next Fly.io deploy trigger (CI / manual) userebbe il nuovo codice senza CLI → crash
- **Mitigazione:** disattivare temporaneamente il workflow `.github/workflows/fly-deploy.yml` finché Dockerfile pronto

**Raccomandazione:** **Opzione A**.

### Decisione 2: scope del cache_control commit (23673a89a)

Il commit aggiunge `cache_control: {type: "ephemeral"}` alle 2 chiamate SDK `messages.create`. Dopo la migrazione a subprocess (commit `5d95abfa9`), quei file non chiamano più `messages.create` — il cache_control è **codice morto**.

**Opzioni:**

- **Lasciarlo:** history del ragionamento preservata, zero impatto runtime
- **Revertirlo:** pulire il diff. Ma un revert del 23673a89a complica il log lineare del branch
- **Squash:** combinare 23673a89a + 913d3f238 + 5d95abfa9 in un singolo commit "feat(claude): Max OAuth migration"

**Raccomandazione:** **lasciarlo**. La storia è pulita (ogni commit fa una cosa sola), e documenta il ragionamento "abbiamo provato cache_control, poi OAuth l'ha reso non più applicabile". Fa parte del record.

### Decisione 3: migrazione altri consumer Claude

Il commit `5d95abfa9` migra **4 call site**. Ma `grep -rn "anthropic.Anthropic" apps/backend-rag` potrebbe trovarne altri nati nel frattempo. Verifico:

```bash
grep -rn "anthropic\.\(Anthropic\|AsyncAnthropic\)" apps/backend-rag/backend --include="*.py"
```

Se emergono altri siti, aprire issue e migrarli nello stesso pattern. Non bloccare questo merge per cercarli tutti.

## Checklist pre-deploy produzione

Da completare **dopo** che `opus47-routing-audit` è mergiato su main:

- [ ] `fly secrets set CLAUDE_CODE_OAUTH_TOKEN=... -a nuzantara-rag`
- [ ] Build image nuova con `claude` CLI
- [ ] Canary deploy: 1 machine con nuovo image, rest old
- [ ] Monitor per 1h i log: cercare `🚨` (policy violations), `ClaudeOAuthError`, `ClaudeOAuthNotAvailable`
- [ ] Se clean → rolling deploy resto delle machine
- [ ] Se errori → `fly secrets set KG_REASONING_PROVIDER=openai` come escape hatch (copre KG), poi rollback image

## Follow-up backlog (non bloccante)

- **Real usage telemetry dal CLI**: `claude -p --output-format=json` include token counts. Sostituire le stime `len//4`.
- **Streaming support**: quando serve (non oggi), aggiungere un `stream_async()` a `claude_oauth_client` usando `--output-format=stream-json`.
- **Tool-use**: il CLI supporta tools via MCP config. Se un caller futuro serve, aggiungere un parametro `tools=` al wrapper.
- **Prompt caching attivo**: quando passiamo a un transport che espone il body builder (es. Claude Agent SDK una volta stabile), riattivare `cache_control` sui 2 path che ne beneficiano.
- **Test integrazione live su CI**: oggi i test sono mock-only. Aggiungere 1 job CI che esegue `complete_async("ping")` settimanalmente per validare che token + CLI + auth siano live.
