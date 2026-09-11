# Memory (MOS) — where project knowledge lives, for external agents

> Moved out of `AGENTS.md` on 2026-09-10 (boot diet). Substance unchanged.

La memoria di progetto (decisioni, scoperte, fatti, lessons) vive come file Markdown qui:

- **Pro**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/*.md` (388+ file)
- **Air-M5**: `~/.claude/projects/-Users-balizero-Desktop-nuzantara/memory/*.md` (sincronizzati dal Pro via hub-daemon)
- **Indice**: `MEMORY.md` nella stessa dir — leggi questo PRIMA per orientarti (1 riga per memory).

Per interrogarla:

- Comando `mem query "<termine>"` (FTS5 sul DB `memory.db`). Su **Pro** funziona diretto. Su **Air-M5** `mem` usa SSH-al-Pro per il DB ricco, con fallback grep sui `.md` locali se il Pro è irraggiungibile.
- In alternativa (sempre disponibile, zero dipendenze): leggi i `.md` direttamente col path sopra, o `grep -rl "<termine>" <memory-dir>/*.md`.

Codex NON carica la memory in automatico (a differenza di Claude che ha i SessionStart hook): leggi `MEMORY.md` + i `.md` rilevanti col path quando ti serve contesto storico del progetto.
