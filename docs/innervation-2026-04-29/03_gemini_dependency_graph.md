# 03 — Gemini 3.1 Pro: dependency graph (SKIPPED — capacity exhausted)

**Data**: 2026-04-29 21:35 WITA
**Esito**: ❌ HTTP 429 — `MODEL_CAPACITY_EXHAUSTED` server-side Google ("No capacity available for model gemini-3.1-pro-preview on the server")
**Decisione orchestratore**: NON ritento. Memory check `lessons.md` 2026-04-29 conferma pattern (Codex usage limit + Gemini 3.1 Pro 429 + NotebookLM API errors simultanei in finestra ravvicinata = capacity exhaustion wave-level). Ho 3/4 LLM con output sostanziale (Codex 76 lines + DeepSeek 14k char + NLM NB-1+NB-14 ~11k char) che coprono i pilastri minimi: signals + contract + storia.

---

## 1. Cosa Gemini avrebbe coperto

Cross-organ dependency graph DOT/Mermaid. La 1M context Gemini è ottima per "leggi tutto il monorepo e mappa chi chiama chi". Per il Track C3, sarebbe stato utile per:
- Identificare SPOFs (single point of failure) tra i 149 organi
- Catalogare implicit dependencies (Pro→Air SSH, Telegram chat ID 1125336968 hardcoded, ecc.)
- Suggerire ordine innervazione che minimizza cascade failures

## 2. Sostituzione

L'orchestratore (Claude Opus 4.7) costruisce manualmente il dependency graph essenziale a partire da:
- `02_dispatch_resilience_log.md` § "Output NLM è solido" (3 heartbeat silos già esistenti + Federation launcher + Olympus heartbeat + NLM ARCH-9)
- `04_codex_existing_signals.md` § "28 patterns enumerated" (con file:line per ogni emit/consume)
- `06_notebooklm_history.md` § "5 ground truth + 4 cicatrici" (NB-1 architecture decisions + NB-14 past failures)

Il resultatone è il Mermaid graph in `07_innervation_protocol.md` § "Dependency model" (ridotto al minimo viable per FASE 2 design).

## 3. Lesson per future agent sessions

- Quando Gemini 3.1 Pro restituisce 429, **non sprecare 3+ retry**. È server-side, non rate-limit dell'utente. Aspetta 30+ minuti o fallback a `gemini-2.5-flash` o costruisci manualmente.
- Memory `lessons.md` 2026-04-19→29 ha già documentato il pattern. SessionStart hook lo carica automaticamente.

## 4. Possibile retry posteriore

Se Gemini torna disponibile durante FASE 2 o FASE 3, l'orchestratore può lanciare il dispatch in background per completare il quadro. Il brief originale è in `/tmp/innervation-gemini-brief.md` e resta valido.
