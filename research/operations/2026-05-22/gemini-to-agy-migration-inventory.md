---
date: 2026-05-22
domain: operations
client_case: internal — Antigravity CLI migration
sources: 8
---

# Inventario `gemini` CLI → `agy` migration

**Trigger**: Antonello 2026-05-22 02:30 WITA "gemini cli e' deprecato per agy cli, cerca in tutto il sistema dove usiamo gemini cli".

**Reality check**: i due CLI NON sono drop-in compatibili. `agy` ha surface drasticamente diversa.

## Surface diff `gemini` 0.42.0 vs `agy` 1.0.0

| Aspetto       | `gemini`                                  | `agy`                                                                   | Impatto migration                   |
| ------------- | ----------------------------------------- | ----------------------------------------------------------------------- | ----------------------------------- |
| Print mode    | `-p "prompt"` (arg)                       | `-p "prompt"` (arg) OR `-p` + stdin                                     | OK retro-compat                     |
| Stdin prompt  | `gemini -p "$(cat file)"`                 | `cat file \| agy -p`                                                    | preferire stdin per prompt grossi   |
| Model select  | `-m gemini-3.1-pro-preview`               | **assente** — letto da `~/.gemini/settings.json` `general.model`        | ⚠️ blocker per script multi-modello |
| Stream output | `-o stream-json -y`                       | **assente**                                                             | ⚠️ blocker per zantara-gateway SSE  |
| Approval      | `--approval-mode {default,yolo,plan}`     | `--dangerously-skip-permissions` (bool)                                 | parziale                            |
| Sandbox       | `--sandbox --approval-mode plan`          | `--sandbox` (bool, terminal restrict)                                   | semantica diversa                   |
| Timeout       | infinito (Go internal)                    | `--print-timeout 5m` configurabile                                      | DEVE specificare in script          |
| MCP allowlist | `--allowed-mcp-server-names X`            | **assente CLI** (config-level)                                          | impact zantara-gateway              |
| Config dir    | `~/.gemini/`                              | `~/.gemini/antigravity-cli/` overlay + `~/.gemini/settings.json` shared | settings condivisi                  |
| Auth          | OAuth personal token                      | stesso OAuth (eredita `~/.gemini/oauth_creds.json`)                     | OK riusa auth                       |
| Subscription  | Free tier Google AI Studio                | Google AI Ultra ($200/mo) — 10k Flow cr/mese + 2500 AI cr               | quota ⬆️                            |
| Binary        | `/opt/homebrew/bin/gemini` (node wrapper) | `/Users/nuzantara/.local/bin/agy` (Go binary 140MB)                     | path hardcode                       |

### Modello multipli — gap critico

`agy` legge il modello da `~/.gemini/settings.json`:

```json
{
  "general": { "model": "gemini-3.1-pro-preview" },
  "model": { "name": "gemini-3.1-pro-preview" }
}
```

Script che variano modello via CLI flag (es. `gemini -m gemini-2.5-flash` per task fast):

- `apps/bali-intel-scraper/scripts/translate_articles.py` — `gemini-3.1-pro`
- `apps/bali-intel-scraper/scripts/gemini_seo_optimizer.py` — `gemini-2.5-pro`
- `scripts/extract_worker.sh` — `gemini-2.5-flash`
- `scripts/batch_extract_company_capital.py` — `gemini-2.5-flash`
- `apps/backend-rag/scripts/naga_*.py` — `GEMINI_MODEL` env

3 strategie possibili:

**Strategia A — modello unico globale 3.1 Pro**. Tutti gli script usano lo stesso modello (quello in settings.json). Costo: perde fast-tier per task semplici. Benefit: zero config switch.

**Strategia B — wrapper per-modello con settings switch**. Pre-script: `cp ~/.gemini/settings.{fast,pro,preview}.json ~/.gemini/settings.json` poi `agy -p`. Race condition se 2 script paralleli vogliono modelli diversi.

**Strategia C — bipolar split**: `agy` per long-context (3.1 Pro), `gemini` legacy mantenuto SOLO per script che richiedono fast/flash. Surface duale documentata.

**Raccomandazione** (panel TBD): C nel breve termine (zero regression), A nel medio termine (consolidamento — Bali Zero usa 3.1 Pro al 90% comunque).

## Call-site inventory

### Tier 1 — Hot path PRODUZIONE (cron attivi, ship Wave 1)

| #   | File                                                                         | Cron/trigger            | Invocation pattern                                             | Modello                 | Migration        |
| --- | ---------------------------------------------------------------------------- | ----------------------- | -------------------------------------------------------------- | ----------------------- | ---------------- |
| 1   | `~/Library/LaunchAgents/com.balizero.crm-guardian-cli-worker.plist`          | cron LaunchAgent        | invoca `scripts/crm_guardian_gemini_cli_worker.py`             | 3.1-pro-preview default | A (no flag)      |
| 2   | `scripts/crm_guardian_gemini_cli_worker.py:96,762`                           | cron 1h                 | `GEMINI_CLI = "/opt/homebrew/bin/gemini"` + `gemini -p prompt` | settings default        | A                |
| 3   | `apps/bali-intel-scraper/scripts/translate_articles.py:162,174`              | cron Pro 03:00          | `gemini -m gemini-3.1-pro -p` + fallback `gemini -p`           | 3.1-pro                 | A (model uguale) |
| 4   | `apps/bali-intel-scraper/scripts/gemini_seo_optimizer.py:124`                | cron Pro                | `gemini -m gemini-2.5-pro -p`                                  | 2.5-pro                 | C (resta legacy) |
| 5   | `scripts/claude-cascade.sh:108-130`                                          | wrapper cascade         | tier-2 fallback `gemini -m gemini-3.1-pro-preview -p`          | 3.1-pro-preview         | A                |
| 6   | `scripts/_entailment_check.py:58-249`                                        | hook regulatory-watcher | `GEMINI_CLI` env + `gemini -m GEMINI_MODEL -p`                 | configurable            | A + env          |
| 7   | `apps/backend-rag/scripts/ocr_pipeline_gemini.py:122,135,352`                | OCR pipeline            | `gemini -p prompt` + version check                             | settings default        | A                |
| 8   | `apps/backend-rag/scripts/naga_bulk_enrich.py:324` + `naga_live_test.py:198` | cron naga               | `gemini -m GEMINI_MODEL -p`                                    | env-driven              | A                |

### Tier 2 — Cold path (script ad-hoc, ship Wave 2)

| #   | File                                                                | Pattern                                                     | Modello         | Migration                         |
| --- | ------------------------------------------------------------------- | ----------------------------------------------------------- | --------------- | --------------------------------- |
| 9   | `scripts/wr3_dispatch_agent.py:175`                                 | `shutil.which("gemini")` legacy lookup                      | —               | swap `agy`                        |
| 10  | `scripts/kbli_enrich_triage.py:13-19,64-79`                         | **GIÀ MIGRATO** (template canonico)                         | settings        | reference impl                    |
| 11  | `apps/backend-rag/scripts/kbli_silver_validate.py:47`               | `GEMINI_CLI = "gemini"`                                     | —               | A                                 |
| 12  | `apps/backend-rag/scripts/kbli_silver_parallel.py:49,452`           | `GEMINI_CLI = "gemini"` + provider tag                      | —               | A                                 |
| 13  | `apps/backend-rag/scripts/kbli_enrichment_pipeline.py:527`          | `GEMINI_CLI = "gemini"`                                     | —               | A                                 |
| 14  | `apps/kbli-navigator/scripts/generate_gold_content_gemini.py:37-40` | `gemini -p`                                                 | settings        | A                                 |
| 15  | `apps/mata-garuda/mata_garuda/runtime/cli_runtime.py:71-72,338,353` | `CLI_CONFIGS["gemini"]["cmd"] = "gemini"` dispatch table    | —               | A + key remap                     |
| 16  | `scripts/gemini_extract_company_data.sh:72`                         | bash `gemini -m gemini-3.1-pro-preview`                     | 3.1-pro-preview | A                                 |
| 17  | `scripts/extract_worker.sh:60`                                      | bash `gemini -m gemini-2.5-flash --approval-mode yolo -p`   | 2.5-flash       | C (resta legacy)                  |
| 18  | `scripts/batch_extract_company_capital.py:96`                       | python `gemini -m gemini-2.5-flash --approval-mode yolo -p` | 2.5-flash       | C (resta legacy)                  |
| 19  | `scripts/sota_consiglio_playbook.py:229`                            | panel registry `members.append("gemini")`                   | —               | A + key remap                     |
| 20  | `scripts/deepseek_vs_gemini_blite.py`                               | benchmark                                                   | —               | label only                        |
| 21  | `scripts/zantara-gateway/gateway.py:97-499`                         | SSE `stream_gemini_cli()` `gemini -p -o stream-json -y`     | —               | ⚠️ **BLOCKER** agy no stream-json |
| 22  | `scripts/zantara-gateway/acp_client.py:45`                          | `gemini_path: str = "gemini"` ACP client                    | —               | dipende #21                       |
| 23  | `apps/nuzantara-mcp/nuzantara_mcp/tools/google_bridge.py`           | MCP bridge                                                  | da ispezionare  | TBD                               |
| 24  | `apps/nuzantara-mcp/nuzantara_mcp/workflows/chains.py`              | MCP workflow                                                | da ispezionare  | TBD                               |
| 25  | `package.json:35`                                                   | `"ai:agent": "gemini -p"` npm script                        | —               | A                                 |

### Tier 3 — Installer/setup team Bali Zero (ship Wave 3)

| #   | File                                             | Pattern                                                                | Migration                                                       |
| --- | ------------------------------------------------ | ---------------------------------------------------------------------- | --------------------------------------------------------------- |
| 26  | `scripts/install-node.sh:42-43`                  | `npm install -g @google/gemini-cli`                                    | scarica agy binary (no npm/brew, no installer ufficiale ancora) |
| 27  | `scripts/damar-node/install.sh:41-42`            | idem                                                                   | idem                                                            |
| 28  | `scripts/ruslana-node/install.sh:63-64`          | idem                                                                   | idem                                                            |
| 29  | `scripts/krisna-node/install.sh:41-42`           | idem                                                                   | idem                                                            |
| 30  | `apps/team-agent/onboarding/mac-bootstrap.sh:56` | `npm install -g @google/gemini-cli`                                    | idem                                                            |
| 31  | `scripts/mini-setup/11-arsenal-llm.sh:27-31`     | `brew install gemini-cli`                                              | idem                                                            |
| 32  | `scripts/mini-setup/12-arsenal-auth-sync.sh:126` | `gemini --version` smoke                                               | swap a `agy --version`                                          |
| 33  | `scripts/mini-setup/STEP-B-arsenal.sh:18,54`     | `brew install gemini-cli codex`                                        | idem                                                            |
| 34  | `scripts/mini-setup/STEP-I-final-checks.sh:32`   | `gemini --version` health                                              | swap                                                            |
| 35  | `scripts/mini-setup/FIX-after-run.sh:91`         | `/opt/homebrew/bin/gemini --version`                                   | swap path + binary                                              |
| 36  | `scripts/mini-setup/mini-aliases.sh:14`          | `alias mini-gemini='ssh -t mini ... gemini -m gemini-3.1-pro-preview'` | swap a `mini-agy='ssh -t mini ... agy'`                         |

### Tier 4 — Documentazione/policy (ship Wave 4)

| #   | File                                             | Update                                                                   |
| --- | ------------------------------------------------ | ------------------------------------------------------------------------ |
| 37  | `SYMBIOSIS.md:178` (Legge 1 CLI-only)            | `gemini --print` → `agy --print`                                         |
| 38  | `VADEMECUM.md:389` (Legge 1)                     | idem                                                                     |
| 39  | `~/.claude/CLAUDE.md`                            | ✓ già aggiornato (cita agy tier-2 + gemini legacy deprecato)             |
| 40  | `~/.claude/agents/wr2-design-architect.md:120`   | cascade imagegen menziona `gemini-3.1-pro-preview`                       |
| 41  | `~/.claude/agents/deep-researcher.md`            | menziona gemini per long-context                                         |
| 42  | `~/.claude/agents/wr2-ig-metrics-analyst.md`     | Gemini 3.1 Pro free → agy                                                |
| 43  | `~/.claude/agents/wr2-external-bench.md`         | idem                                                                     |
| 44  | `~/.claude/agents/wr3-editorial-bench.md`        | idem                                                                     |
| 45  | `~/.claude/agents/wr3-reflexion-synth.md`        | gemini fallback → agy                                                    |
| 46  | `~/.claude/agents/wr3-yt-metrics-analyst.md`     | idem                                                                     |
| 47  | `~/.claude/skills/federation-dispatch.md`        | gemini explore/search/redteam → agy                                      |
| 48  | `scripts/prompts/gemini-debug.md`                | diagnostic obsoleto — riscrivere per agy o archiviare                    |
| 49  | `scripts/AGENTS.md`                              | menzioni gemini provider                                                 |
| 50  | `apps/nuzantara-mcp/skills/antigravity/SKILL.md` | verificare (probabilmente già OK)                                        |
| 51  | `apps/mouth/src/CLAUDE.md` (worktree)            | mata-garuda dummy_agent menziona "gemini" runtime — mantenere come alias |

### Da IGNORARE

- `.claude/worktrees/agent-a*` — worktree archiviati immutabili
- `docs/audits/**`, `research/**`, `ai-dispatch-output/**`, `tmp_notebooklm/**`, `data/**`, `reports/**`, `agent-library/**`, `vendor/evoskill/**` — storico/audit/log
- `venv/lib/**`, `**/__pycache__`, `apps/war-room/logs/**` — generato
- `apps/backend-rag/data/zantara_rag.log*`, `verification_output_*.txt` — log/output

## Pattern di migrazione canonico

Reference impl: `scripts/kbli_enrich_triage.py:11-79`.

```python
# Antigravity CLI `agy` is the canonical Gemini frontend (Google AI Ultra sub).
# Legacy `/opt/homebrew/bin/gemini` remains as fallback during transition.
_AGY_BIN = "/Users/nuzantara/.local/bin/agy"
_LEGACY_GEMINI_BIN = "/opt/homebrew/bin/gemini"
GEMINI_BIN = os.environ.get(
    "GEMINI_BIN",
    _AGY_BIN if os.path.exists(_AGY_BIN) else _LEGACY_GEMINI_BIN,
)
_IS_AGY = os.path.basename(GEMINI_BIN) == "agy"

def call_llm(prompt: str, timeout: int = 310) -> str:
    if _IS_AGY:
        # agy: prompt via stdin + flag --print-timeout obbligatorio
        result = subprocess.run(
            [GEMINI_BIN, "-p", "--print-timeout", "5m"],
            input=prompt,
            capture_output=True, text=True, timeout=timeout,
        )
    else:
        # legacy gemini: prompt as -p arg
        result = subprocess.run(
            [GEMINI_BIN, "-p", prompt],
            capture_output=True, text=True, timeout=timeout - 10,
        )
    return result.stdout.strip()
```

Vantaggi:

- env override `GEMINI_BIN` per A/B testing in CI
- auto-detect: se `agy` esiste lo usa, altrimenti fallback
- isolamento differenze invocazione (stdin vs arg)
- timeout esplicito per agy (default Go 5m è OK ma serve flag)

Limitazioni:

- non gestisce model switching (script con `-m fast` perdono opzione)
- non gestisce streaming SSE
- non gestisce sandbox/approval-mode

## Blocker noti (richiedono decisione operativa)

1. **`zantara-gateway` SSE** — `gemini -p -o stream-json -y` non ha equivalente agy. Opzioni: (a) gateway resta su gemini legacy, (b) attendere agy SSE support, (c) re-implementare gateway con Gemini API SDK + Claude OAuth CLI (rischio: viola SYMBIOSIS Legge 1 se SDK). **Bipolar verifier richiesto** — NB-INTEL-Architecture per ground-truth pattern.

2. **Model multipli (2.5-flash + 2.5-pro)** — script che usano modelli fast/pro diversi. Opzioni: (a) consolidare tutto su 3.1-pro (settings.json), (b) mantenere gemini legacy per fast/flash, (c) wrapper per-modello con settings switch (race condition se parallelo).

3. **`--allowed-mcp-server-names`** — gateway usa allowlist MCP. agy non espone CLI flag. Probabilmente da `~/.gemini/config/mcp_config.json`.

## Stima effort

| Wave    | Scope                   | File count | Effort    | Risk               |
| ------- | ----------------------- | ---------- | --------- | ------------------ |
| 1       | Hot path (#1-8)         | 8          | 3-4h      | medio (cron prod)  |
| 2       | Cold path (#9-25)       | 17         | 4-5h      | basso              |
| 3       | Installer team (#26-36) | 11         | 1-2h      | basso (idempotent) |
| 4       | Docs/policy (#37-51)    | 15         | 1h        | nullo              |
| **Tot** |                         | **51**     | **9-12h** |                    |

## Note empiriche

- `agy --print-timeout 5m` deve essere esplicito — assenza = default Go 5m comunque, ma testato in `kbli_enrich_triage`.
- `agy` eredita auth OAuth da `~/.gemini/oauth_creds.json` (no re-auth necessario).
- Settings condivisi: cambiare `~/.gemini/settings.json` model field impatta SIA `gemini` SIA `agy`. Test cross-CLI before commit.
- Mini-Pro2: solo file in `scripts/mini-setup/*` (sync da Pro via git). Migration cascade automatica.
- `package.json` line 35 `"ai:agent": "gemini -p"` — verificare se invocato (`npm run ai:agent`). Se non usato da nessuno, rimuovere.

## Verification post-migration (per Wave)

1. `agy --version` returns 1.0.0+ su Pro e Mini
2. Per ogni script migrato: smoke test con prompt sintetico, output JSON-parseable
3. Cron LaunchAgent: 1 ciclo successful entro 1h post-deploy
4. Telegram alert se script fail: integrare in `_entailment_check.py` pattern
5. `git log --grep="agy\|gemini→"` mostra commit atomici per file
