# Harness lifecycle tools — la cura di "Delega Invisibile del Lifecycle"

> Genesi: opus-mythos TAC del harness Claude Code (2026-06-15/16). Meta-pattern (Gemini→Opus→DeepSeek):
> gli artefatti append-by-default del harness crescono senza limite perché il tool non ha
> garbage-collector e l'utente non possiede il lifecycle → saturazione → troncamento silenzioso.
> Questi 3 tool **fanno possedere il lifecycle all'harness**. Versionati qui; la copia viva è in `~/.claude/`.

## I file (NB: operano su `~/.claude/` + `.claude/settings.local.json`, entrambi fuori da git → questi sono la SORGENTE riproducibile)

### `harness_lifecycle_guard.py` — il guardiano ATTIVO (SessionStart hook)
NON solo avvisa: **AGISCE**. A ogni avvio sessione:
1. **Auto-GC permessi**: rimuove la spazzatura Bash one-off (`echo`/`cd`/`source`/commenti/script>500char), con backup `.bak-guard`. Il vaso si svuota DA SOLO.
2. **Avvisa** (non auto-fixa, serve operatore): MEMORY.md vicino al tetto 25.6KB (#40614), secret PGPASSWORD residui.
- **Conservativo**: MAI tocca un pattern (`*`), mcp, Read, o secret. **Fail-open totale** (qualunque errore → sessione parte comunque).
- **Wiring**: `~/.claude/settings.json` → `hooks.SessionStart` → `python3 ~/.claude/hooks/harness_lifecycle_guard.py`. Copia il file da qui a `~/.claude/hooks/` (host-boundary: fallo tu o con `HOST_BOUNDARY_OFF=1`).

### `perm_gc.py` — garbage-collector dei permessi (one-shot, dry-run default)
Rimuove la spazzatura inequivocabile dai 909→ permessi auto-accumulati. `APPLY=1` per scrivere.
Stessa logica `_is_garbage` del guardiano. Usato una volta: 909→803.

### `perm_collapse.py` — dedup + dead-path removal (one-shot, dry-run default)
SOLO mosse a colpo sicuro: (1) rimuove path-morti `/Users/nuzantara` (utente M5=balizero), (2) dedup
literali già coperti da un pattern `*` esistente. **NON crea nuovi pattern** (il parsing dei comandi
multi-riga è troppo sporco per autogenerarli in sicurezza — quello resta revisione manuale).
Usato una volta: 803→693 (+ rimossi 2 secret embeddati: 1 JWT, 1 QDRANT_KEY).

## Risultato applicato (2026-06-16)
| | prima | dopo |
|---|---|---|
| MEMORY.md | 26175B (tail troncato) | 17117B (tutto caricato) |
| settings.local.json allow | 909 (0 deny/0 ask, discarica) | **693** + auto-GC continuo |
| secret embeddati (non-PGPASSWORD) | ≥2 (JWT, QDRANT_KEY) | **0** |

## Residuo operatore (§Solo-operatore, by design)
- **15 PGPASSWORD** + **QDRANT_KEY `d0e745ad…`** + **1 JWT** sono stati in chiaro storicamente → **considerarli compromessi, ruotare** (Fly secrets / Qdrant). Ordine: ruota PRIMA, poi il GC pulisce il file.
- I ~600 pattern residui sono regole sane; collassarli ulteriormente = revisione manuale (rischio buco se troppo larghi).
