---
date: 2026-05-22
domain: operations
client_case: internal — Antigravity CLI migration spec
sources: 4
status: DRAFT v1 — awaiting 4-LLM panel review
---

# Spec: migrate `gemini` CLI → `agy` CLI across Nuzantara

## Context

Antonello 2026-05-22: "gemini cli e' deprecato per agy cli". Inventario completo: `2026-05-22/gemini-to-agy-migration-inventory.md` — 51 call-site identificati su Pro + Mini-Pro2, 1 LaunchAgent cron attivo.

`agy` (Antigravity CLI) v1.0.0 vs `gemini` v0.42.0: surface NON drop-in compatibile. Differenze critiche:

- nessun flag `-m model` (modello da `~/.gemini/settings.json`)
- nessun `-o stream-json -y` (no SSE)
- prompt via stdin preferito (`agy -p` + `input=`)
- `--print-timeout` esplicito necessario

Pattern di migrazione canonico già live: `scripts/kbli_enrich_triage.py`.

## Goal

1. Migrare hot-path produzione (8 file Tier 1) da `gemini` a `agy` in modo backward-compatible (env override `GEMINI_BIN`).
2. Migrare cold-path (17 file Tier 2) con stesso pattern.
3. Aggiornare installer team Bali Zero (11 file Tier 3) per scaricare `agy` invece di `npm i -g gemini-cli`.
4. Aggiornare policy docs SYMBIOSIS/VADEMECUM/agents/skills (15 file Tier 4) per riflettere nuovo canone.

## Non-goal

- NON rimuovere `gemini` legacy: resta come fallback per script `2.5-flash`/`2.5-pro` + zantara-gateway SSE (blocker noto).
- NON refactor zantara-gateway: rimane su `gemini` fino a decisione separata su SSE pattern.
- NON cambiare model selection logica: settings.json globale `general.model = gemini-3.1-pro-preview` resta unchanged.

## Strategy

**Strategia C bipolar** (raccomandata):

- `agy` per long-context default (3.1 Pro)
- `gemini` legacy SOLO per script che richiedono `-m gemini-2.5-flash`/`gemini-2.5-pro` explicit
- Zero breaking change: env override `GEMINI_BIN` permette A/B in CI

## Plan

### Wave 1 — Hot path produzione (8 file, ~3-4h)

Branch: `feat/migrate-gemini-to-agy-wave1-2026-05-22`

T1. `scripts/crm_guardian_gemini_cli_worker.py:96,762` — swap `GEMINI_CLI` constant + bracket invocation con pattern canonico
T2. `apps/bali-intel-scraper/scripts/translate_articles.py:162,174` — rimuovi `-m gemini-3.1-pro` flag (settings default già 3.1-pro-preview)
T3. `apps/bali-intel-scraper/scripts/gemini_seo_optimizer.py:124` — **decisione**: 2.5-pro→3.1-pro-preview (Strategia A) o resta gemini legacy (Strategia C)
T4. `scripts/claude-cascade.sh:108-130` — tier-2 fallback swap a `agy -p --print-timeout 5m`
T5. `scripts/_entailment_check.py:58-249` — env-driven, swap default GEMINI_CLI → agy + retain GEMINI_MODEL env
T6. `apps/backend-rag/scripts/ocr_pipeline_gemini.py:122,135,352` — swap subprocess invocation
T7. `apps/backend-rag/scripts/naga_bulk_enrich.py:324` + `naga_live_test.py:198` — swap + retain env model
T8. `~/Library/LaunchAgents/com.balizero.crm-guardian-cli-worker.plist` — NESSUN cambiamento (invoca script python, swap interno)

Acceptance criteria Wave 1:

- T1 cron LaunchAgent: 1 ciclo successful entro 1h post-deploy, no Telegram alert
- T2/T3 bali-intel scraper cron Pro 03:00: 1 ciclo successful entro 24h
- T4 claude-cascade tier-2 fallback: smoke test con prompt sintetico
- T5 entailment check: 5 verdict YES/NO parseable
- T6 OCR pipeline: 1 documento processato successful
- T7 naga: 10 entity enriched

### Wave 2 — Cold path (17 file, ~4-5h)

Branch: `feat/migrate-gemini-to-agy-wave2-2026-05-22`

T9-T25 secondo inventario. Pattern uniforme `_AGY_BIN`/`_LEGACY_GEMINI_BIN` + `_IS_AGY`.

Eccezione T17/T18 (extract_worker.sh, batch_extract_company_capital.py) e T21/T22 (zantara-gateway): **mantenere su gemini legacy** per Strategia C.

Acceptance:

- ogni script swap: 1 smoke test sintetico OK
- 0 regressioni in `pytest backend/tests/` per script importati da test

### Wave 3 — Installer team (11 file, ~1-2h)

Branch: `feat/migrate-gemini-to-agy-wave3-installers-2026-05-22`

`agy` non ha installer ufficiale brew/npm. Strategy:

```bash
# Replacement per `npm install -g @google/gemini-cli`:
AGY_VERSION="1.0.0"
AGY_URL="https://storage.googleapis.com/antigravity-public/agy-${AGY_VERSION}-darwin-arm64"
curl -fsSL "$AGY_URL" -o ~/.local/bin/agy
chmod +x ~/.local/bin/agy
~/.local/bin/agy --version  # verify
```

⚠️ **TBD**: verificare URL distribuzione ufficiale `agy` (potrebbe richiedere auth Antigravity).

Files: `scripts/install-node.sh`, `scripts/{damar,ruslana,krisna}-node/install.sh`, `apps/team-agent/onboarding/mac-bootstrap.sh`, `scripts/mini-setup/{11-arsenal-llm,12-arsenal-auth-sync,STEP-B-arsenal,STEP-I-final-checks,FIX-after-run}.sh`, `scripts/mini-setup/mini-aliases.sh`.

Acceptance:

- 1 fresh install onboarding-node (test su VM o Subhi onboarding stage) successful
- `agy --version` returns 1.0.0+ post-install

### Wave 4 — Policy docs (15 file, ~1h)

Branch: `chore/agy-canonical-cli-docs-2026-05-22`

- `SYMBIOSIS.md:178` (Legge 1): `claude --print`, `gemini --print` → `claude --print`, `agy --print` (gemini menzionato come legacy fallback)
- `VADEMECUM.md:389`: idem
- `~/.claude/CLAUDE.md`: già aggiornato ✓
- `~/.claude/agents/*.md` (6 file): update model references
- `~/.claude/skills/federation-dispatch.md`: gemini → agy per explore/search/redteam
- `scripts/prompts/gemini-debug.md`: rinomina a `agy-debug.md` o archivia
- `scripts/AGENTS.md`: update provider table
- `apps/nuzantara-mcp/skills/antigravity/SKILL.md`: verificare allineamento

Acceptance:

- grep `gemini --print` zero match in policy docs (eccezione: storical "legacy fallback" mentions in cicatrix-scars)
- 1 cross-LLM panel re-read SYMBIOSIS post-update conferma coerenza Legge 1

## Risks

| Risk                                                                     | Severity | Mitigation                                                                                 |
| ------------------------------------------------------------------------ | -------- | ------------------------------------------------------------------------------------------ |
| `agy` cron silently failing su Pro (no Telegram)                         | P0       | T1.5 alzheimer-hook pattern: ogni script swap deve avere Sentry capture o Telegram on fail |
| Model mismatch settings.json globale vs script che si aspetta fast model | P1       | Strategia C: lasciare gemini legacy per 2.5-flash/2.5-pro                                  |
| zantara-gateway SSE break                                                | P0       | OUT of scope — gateway resta su gemini                                                     |
| Antigravity CLI binary distribution non documentata                      | P1       | Wave 3 TBD: chiedere Antonello URL ufficiale                                               |
| Quota Google AI Ultra esaurita (10k Flow cr/mese)                        | P2       | Cascade tier-3 codex GPT-5.5 già documentato CLAUDE.md                                     |
| `~/.gemini/settings.json` race condition tra agy e gemini paralleli      | P2       | Documentare: nessun script paralelo deve cambiare settings.json                            |

## 4-LLM panel review (BEFORE Wave 1 implementation)

Per `feedback_always_review_spec_with_4_llm.md`, fan-out parallel:

1. **agy CLI** (`agy -p`) self-review — meta-test del CLI stesso
2. **Codex GPT-5.5** (`codex exec --sandbox workspace-write`) — adversarial: cerca race condition + secret leak + circular dependency
3. **DeepSeek V4 Pro** (`reasoning_effort=high`) — devils-advocate: validi blocker zantara-gateway? Strategia C è davvero zero-regression?
4. **NotebookLM NB-INTEL-Architecture** (se UUID known) — ground-truth: pattern subprocess migration in altri progetti monorepo

Convergent verdict required prima di Wave 1 ship. Divergenze documentate in sintesi.

## Verification post-Wave (cross-wave)

1. `grep -rn "gemini -[mp]" scripts apps --include='*.py' --include='*.sh'` — zero match in file migrati
2. `pytest apps/backend-rag/backend/tests/ -k "gemini or agy"` — 0 fail
3. LaunchAgent `com.balizero.crm-guardian-cli-worker.plist` health post 4h
4. `~/scripts/fly-health-check.sh` mostra 0 nuovi error post-deploy
5. SessionStart hook conferma `agy --version 1.0.0+` su Pro e Mini

## References

- Pattern canonico: `scripts/kbli_enrich_triage.py:11-79`
- Inventario: `2026-05-22/gemini-to-agy-migration-inventory.md`
- CLAUDE.md global: §"External LLM arsenal" — `agy` già canonico tier-2
- agy CLI help: `agy --help` (no `-m`, `--print-timeout`, `--sandbox`, `--dangerously-skip-permissions`)
- gemini CLI: `/opt/homebrew/bin/gemini` v0.42.0
- agy binary: `/Users/nuzantara/.local/bin/agy` v1.0.0, 140MB Go binary
- Settings: `~/.gemini/settings.json` (shared) + `~/.gemini/antigravity-cli/settings.json` (overlay)
