# M5 thin-client guards — reference mirror

Questi file VIVONO in `~/.claude/` su Air-M5 (HOME, non versionato). Qui ne teniamo
una **copia di riferimento per audit trail** (pattern HOME-fork drift, cf. cicatrici W50/W51/W52).

| File qui | File vero su M5 | Cosa fa |
|---|---|---|
| `m5_block_heavy_brew.py` | `~/.claude/hooks/m5_block_heavy_brew.py` | PreToolUse(Bash): blocca `brew install <tool-pesante>` su M5, redirect a `ssh pro`. Kill switch `M5_HEAVY_BREW_GUARD=off`. |
| `sync-check.sh` | `~/.claude/scripts/sync-check.sh` | Salute sync memoria M5↔Pro (6 check) + MOS. |
| `sync-now.sh` | `~/.claude/scripts/sync-now.sh` | Forza un tick di sync memoria. |

Regole thin-client R1-R6: memoria `reference_pro_ecosystem_map_for_m5_2026_06_01.md` (sincronizzata via daemon, non git).
Test di verifica: workflow `m5-map-test` (mappa) + `m5-skills-test` (skill/catalogo). Lezione: `--print` testa la mappa, NON le skill (servono sessioni interattive).
