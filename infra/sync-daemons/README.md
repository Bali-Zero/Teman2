# sync-daemons (reference copies — audit trail)

⚠️ **Queste sono COPIE REFERENCE, non l'origine eseguibile.**

I daemon di sync memoria vivono in `~/scripts/mini-setup/` (HOME, non versionato) e sono
invocati dai LaunchAgent (`com.nuzantara.memory-sync-bidirectional` ogni 5min). Questa dir
nel repo esiste solo per **audit trail** — mitiga il rischio HOME-fork drift documentato
nelle cicatrici W50/W51/W52 (due sistemi credono di avere world-state diverso, drift silenzioso).

Se modifichi il daemon: la fonte di verità resta `~/scripts/mini-setup/`. Aggiorna QUI la
copia reference dopo ogni modifica, per tenere l'audit trail allineato.

## memory-sync-bidirectional.sh

Hub-and-spoke (Opzione A, hub=Pro). UN daemon sul Pro sincronizza la memoria L1
(`~/.claude/projects/<user>/memory/*.md`) verso 2 spoke:
- **Mini-Pro2** (user nuzantara, `/Users/nuzantara/...`)
- **Air-M5** (user balizero, `/Users/balizero/...`, ramo `sync_m5()` aggiunto 2026-06-01)

Ogni ramo è 2-way Pro↔spoke, conflict-aware (md5+mtime, delta<60s = conflict → backup+skip),
fail-soft (uno spoke giù non abortisce l'altro), lock unico Pro (`/tmp/memory-sync.lock`).

Kill switch ramo M5: `M5_SYNC_ENABLED=false` nell'env.
Dettaglio decisione: memory `decision_m5_air_fleet_join_2026_05_31.md`.
Studio topologia: `research/operations/2026-05-31-m5-memory-integrity-topology-STUDY.md`.
