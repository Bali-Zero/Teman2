---
date: 2026-05-19
domain: operations
client_case: Claude Code Nuzantara regression diagnosis + fix plan
sources: 6
---

# Claude Code regression Nuzantara — diagnosi + fix plan

**Trigger**: Antonello segnala 2026-05-19 ~15:15 WITA: "da una settimana Claude Code in CLI ha avuto regressione, prima era completamente connesso a me e alla codebase e allo storico, ora fa errori banali e sembra non più il Claude di Nuzantara".

**Sintesi 1 frase**: Claude non ha perso Nuzantara — il sistema di memoria locale gli sta dando una mappa tagliata a metà dal 2026-05-12, con cicatrici giuste fuori dalla parte visibile e SessionStart saturo prima del primo turn.

---

## 1. Cause verificate empiricamente

### Causa primaria — MEMORY.md silent truncation

| Metrica                             | Valore                 | Path                                                                             |
| ----------------------------------- | ---------------------- | -------------------------------------------------------------------------------- |
| Limit hardcoded Claude Code         | 25.600 byte            | issue Anthropic [#40614](https://github.com/anthropics/claude-code/issues/40614) |
| MEMORY.md size attuale (2026-05-19) | 60.602 byte            | `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/MEMORY.md`         |
| Cutoff line                         | **riga 45**            | `head -c 25600 MEMORY.md \| wc -l = 45`                                          |
| Daily growth 2026-05-12→19          | 47.578 → 60.602 (+27%) | da `alzheimer-diagnose-*.md`                                                     |
| Giorni con alert flagged silenziati | **8 consecutivi**      | nessun Telegram emesso                                                           |

**Contenuto invisibile sotto riga 45** (verificato con `head -c 26000 MEMORY.md | tail`):

- Sezione "Research Captures" — 17 entry 2026-05-10→18 (architettura organism, property DD, video formats, OCR plan, etc.)
- Sezione "Workflow rules" — `feedback_always_review_spec_with_4_llm.md` (regola 2026-05-13 critica)
- Sezione "Facts (verified 2026-05-13)" — DeepSeek V4 Pro migration, Canva MCP, jsonb double-encoding discovery, crm-guardian Phase 1.5

### Causa secondaria — context saturation SessionStart

Ogni SessionStart auto-carica (verificato leggendo settings.json + system-reminder this turn):

| File                                            | Byte              | Trigger                                                        |
| ----------------------------------------------- | ----------------- | -------------------------------------------------------------- |
| `CLAUDE.md` project                             | 29.650            | Project instructions auto-include                              |
| `CLAUDE.md` global                              | 11.996            | User instructions                                              |
| `.claude/rules/cicatrix-scars.md`               | 25.839            | Project instructions glob `.claude/rules/*.md`                 |
| `.claude/rules/cicatrix-scars-archive.md`       | 27.343            | Stessa glob (anche se header dice "not auto-loaded" — VIOLATO) |
| `SYMBIOSIS.md`                                  | 24.453            | Hook `symbiosis-core.sh`                                       |
| `VADEMECUM.md`                                  | 21.114            | Referenced in CLAUDE.md, caricato on first reference           |
| `INDEX.md`                                      | 9.233             | Stesso pattern                                                 |
| `MEMORY.md` (truncato)                          | 25.600            | Auto memory                                                    |
| `lessons.md` last-2-entries                     | ~5.000            | Hook `awk L=count-2`                                           |
| 7 system-reminder + skill list + deferred tools | ~30.000           | Harness                                                        |
| **Totale stimato**                              | **~210.000 byte** |                                                                |

**Su context window 200K** = 75-100% consumato prima del primo turn user. Non c'è spazio per ragionare, ogni tool call comprime/dimentica.

### Causa terza — lessons.md hook misalignment

| Cosa                         | Stato                                                                                                                                                           |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Hook command                 | `awk '/^### /{c++} c>=L{print}' L=$(($(grep -c '^### ' "$LESSONS")-2))`                                                                                         |
| Comportamento                | Inietta **solo ultime 2 entry**                                                                                                                                 |
| Total entry in `lessons.md`  | 13                                                                                                                                                              |
| Ultima entry                 | 2026-05-02 (OpenClaw MCP child mortality)                                                                                                                       |
| Inietta ad ogni SessionStart | Wave 2 Pro + fs_usage trap (entrambe 2026-04-29, vecchie 20 giorni)                                                                                             |
| Lezioni 2026-05-13 critiche  | `lessons_hallucinating_tool_output_is_diabolical.md` + `feedback_always_review_spec_with_4_llm.md` — **NON sono in `lessons.md`**, solo in MEMORY.md (truncato) |

### Cause aggravanti minori

| #   | Cosa                                                                                                   | Effetto                                                                            |
| --- | ------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| 4   | Pro/Mini repo drift: Pro `4c1329ace`, Mini `cdd205cf4` (Mini avanti di PR #776 wr3 dispatch v2)        | Errori diversi tra sessioni Pro vs cron Mini                                       |
| 5   | Claude Code version drift: Pro 2.1.144, Mini 2.1.140                                                   | Comportamenti harness potenzialmente diversi                                       |
| 6   | SSH `mini-pro2.local` UNREACHABLE (mDNS), `ssh mini` (Tailscale) funziona — SessionStart hook usa mDNS | Falso allarme "Peer UNREACHABLE" ogni session                                      |
| 7   | `ssh mini "claude --version"` → `command not found` (non-interactive shell non sourcing .zshrc)        | Automazioni SSH cross-host falliscono silenziosamente                              |
| 8   | `.claude/settings.local.json` 107KB / 818 entry allowlist                                              | NON in context Claude (harness-side), ma accumulo cosmetico                        |
| 9   | 8 MCP server attivi → ~100+ tool schema in deferred ToolSearch                                         | Gemini panel: "attention dilution massiva", possibile causa "instruction override" |
| 10  | 7 system-reminder block iniettati ogni turn                                                            | Gemini panel: possibile "persona conflict"                                         |

---

## 2. Panel 3-LLM (deliberation 2026-05-19 ~16:00 WITA)

Domande inviate verbatim a Gemini 3.1 Pro CLI + DeepSeek V4 Pro API in parallelo dopo che Codex aveva già confermato indipendentemente.

### Convergenza 4/4 (Claude + Codex + Gemini + DeepSeek)

1. **MEMORY.md silent truncation è LA causa**, non concausa
2. **Context saturation ~210KB pre-turn** è amplificatore (rende il danno irrecuperabile mid-session)
3. **lessons.md hook è sub-ottimale** (inietta cose vecchie)
4. **Backup prima di compattare** è non-negoziabile

### Aggiunte indipendenti (cose Claude ha mancato)

| Da                | Aggiunta                                                                                                            | Verifica                                  |
| ----------------- | ------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| Gemini            | **Tool schema bloat** — 8 MCP server + deferred tools = JSON gigante system prompt, "attention dilution"            | Confermato (ToolSearch lista ~100+ tools) |
| Gemini            | **System prompt conflict** — 7 system-reminder block possono contraddire persona ("non sembra Claude di Nuzantara") | Plausibile                                |
| Gemini + DeepSeek | **Claude Code 2.1.140→2.1.144 changelog** — possibile cambio context-packing                                        | Da verificare (item 10 fix)               |
| DeepSeek          | **Hook fix da solo NON basta** — anche con `lessons.md` fresco, contenuto sotto riga 45 di MEMORY.md resta perso    | Logico, conferma necessità compaction     |
| DeepSeek          | **Monitoring "silently rotted"** è causa prossimale (alzheimer 8gg silent)                                          | Vero                                      |

### Divergenze (debolezza panel)

| Item                                   | Claude      | Codex       | Gemini     | DeepSeek       | Decisione                                                  |
| -------------------------------------- | ----------- | ----------- | ---------- | -------------- | ---------------------------------------------------------- |
| Target MEMORY.md size post-compaction  | 22-24KB     | 22-24KB     | <15KB      | ≤25.6KB margin | **18-20KB** (compromesso, ~2 settimane di growth headroom) |
| Tool schema bloat è davvero rilevante? | non flagged | non flagged | sì critico | non flagged    | **investigare empiricamente prima di toccare**             |

---

## 3. Fix plan ordinato (10 step)

### Critici (1-7, ~65 min totali)

| #     | Fix                                                                                                                                                                                | Convergenza               | Tempo  | Criterio verifica                                                      |
| ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- | ------ | ---------------------------------------------------------------------- |
| **1** | Backup completo `MEMORY.md` + tutto `.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/` in tar fuori repo                                                                | 4/4 LLM                   | 2 min  | `ls -la ~/backups/claude-memory-2026-05-19.tar.gz` esiste              |
| **2** | Dry-run compaction su copia: estrai 17 Research Captures → `MEMORY_RESEARCH_CAPTURES.md`, compatta entry restanti ≤150 char, target ≤20KB                                          | 4/4 LLM                   | 20 min | `wc -c MEMORY.md.new` ≤ 20.480                                         |
| **3** | Verifica cutoff post-compaction: `head -c 25600 MEMORY.md.new \| wc -l` deve far comparire sezioni "Workflow rules" + "Facts 2026-05-13" sopra cutoff                              | DeepSeek esplicito        | 1 min  | Output `wc -l` ≥ riga della sezione "Facts"                            |
| **4** | Sostituisci `MEMORY.md` con `.new`. Test session fresh: chiedere a Claude di citare regola 4-LLM panel o jsonb double-encoding                                                     | DeepSeek esplicito        | 5 min  | Claude cita verbatim senza Read tool call                              |
| **5** | Migra 2 lezioni 2026-05-13 in `lessons.md`: `lessons_hallucinating_tool_output_is_diabolical.md` + `feedback_always_review_spec_with_4_llm.md` come 2 entry `### 2026-05-13 — ...` | Gemini esplicito          | 10 min | `grep -c "^### 2026-05-13" lessons.md` = 2                             |
| **6** | Fix `lessons.md` hook in `settings.json`: passare da count-based (`L=count-2`) a date-based (entry con header `### 2026-MM-DD` negli ultimi 14gg)                                  | Gemini esplicito          | 10 min | Nuovo SessionStart inietta lezioni 2026-05-13                          |
| **7** | alzheimer-diagnose → emettere alert Telegram quando MEMORY.md > 25KB (oggi check c'è, alert no). Patch in script + LaunchAgent                                                     | Claude+DeepSeek esplicito | 15 min | Test: `truncate -s 26000 MEMORY.md.test` → script invoca curl Telegram |

### Importanti (8-10, ~45 min totali)

| #      | Fix                                                                                        | Convergenza     | Tempo | Criterio verifica                              |
| ------ | ------------------------------------------------------------------------------------------ | --------------- | ----- | ---------------------------------------------- |
| **8**  | Pro `git pull origin main` per allineare a `cdd205cf4` (Mini commit ahead)                 | Codex+Claude    | 2 min | `git log -1` mostra `cdd205cf4` o successivo   |
| **9**  | Fix SessionStart hook: sostituire `mini-pro2.local` mDNS con `ssh mini` Tailscale alias    | Codex esplicito | 5 min | Next SessionStart: "Peer: nuzantara@Mini-Pro2" |
| **10** | Fix Mini PATH non-interactive: `~/.zshenv` aggiungere export PATH con percorso Claude Code | Codex+Claude    | 5 min | `ssh mini "claude --version"` ritorna 2.1.140+ |

### Opzionali (R&D, ~60 min totali)

| #      | Fix                                                                                                                       | Convergenza      | Tempo  |
| ------ | ------------------------------------------------------------------------------------------------------------------------- | ---------------- | ------ |
| **R1** | Verificare changelog Claude Code 2.1.140→2.1.144 per cambi context-packing                                                | Gemini+DeepSeek  | 10 min |
| **R2** | Allineare Pro→Mini a stessa versione Claude Code (decidere se 2.1.144 o 2.1.140 master)                                   | Claude           | 10 min |
| **R3** | Audit 7 system-reminder block, consolidare a 1-2 ad alta densità                                                          | Gemini esplicito | 30 min |
| **R4** | (Strutturale) Cicatrix-scars-archive.md NON deve auto-load — verificare matcher glob in settings.json `additionalContext` | Claude           | 10 min |

---

## 4. Rischio + rollback

**Punto di rottura più critico**: step 2-4. Se compaction sbaglia ordine sezioni e cutoff finisce su una sezione interna a metà, perdo MEMORY visibility worse than prima.

**Rollback**:

```bash
tar -xzf ~/backups/claude-memory-2026-05-19.tar.gz -C ~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/
```

**Trigger rollback**: se in test session post-step-4 Claude NON cita lezioni 2026-05-13 anche con explicit prompt → ripristina backup e ri-progetta compaction.

---

## 5. Outcome atteso

| Metrica                         | Pre-fix (2026-05-19)    | Post-fix (target)                          |
| ------------------------------- | ----------------------- | ------------------------------------------ |
| MEMORY.md size                  | 60.6 KB                 | ≤ 20 KB                                    |
| Cutoff line                     | 45 (perde 60% del file) | cutoff irrilevante (file < limit)          |
| Lessons iniettate ogni session  | 2 vecchie (2026-04-29)  | 2-5 recenti (last 14d, include 2026-05-13) |
| Pre-turn context                | ~210 KB                 | ~175 KB (-17%)                             |
| Alert silenziati                | 8gg consecutivi         | 0 (Telegram on > 25KB)                     |
| Pro/Mini drift                  | 1 commit                | 0                                          |
| SessionStart "Peer UNREACHABLE" | sempre                  | mai (Tailscale alias)                      |

**Definizione di successo**: in una nuova sessione fresh post-fix, chiedere a Claude:

> "Quali sono le regole 2026-05-13 di review spec con 4-LLM panel?"

Risposta corretta: cita verbatim regola + path file `feedback_always_review_spec_with_4_llm.md` **senza** dover fare `Read` tool call (= sta in MEMORY caricato).

---

## 6. Decisione operativa

Antonello sign-off su:

- [ ] Procedere fix 1-7 critici nell'ordine indicato?
- [ ] Target MEMORY.md compaction: 18-20 KB (compromesso) vs 15 KB (Gemini) vs 24 KB (Claude/Codex)?
- [ ] Step 5 — migrare 2 lezioni 2026-05-13 OK?
- [ ] Step 7 — alert Telegram su quale chat_id? (1125336968 default Zero, conferma)
- [ ] Step 8 — Pro `git pull` su branch corrente (`feat/wr3-dispatch-refactor-no-task-tool-2026-05-19-v2`) o switch a `main` prima?
- [ ] Step R1 — leggere changelog Claude Code 2.1.140→2.1.144 prima o dopo i fix?

---

**Sources** (this diagnosis):

- Codex CLI output 2026-05-19 ~15:50 WITA (independent verification)
- Gemini 3.1 Pro CLI output `/tmp/gemini-diagnosis.txt` (22 lines)
- DeepSeek V4 Pro API `reasoning_effort=high` output `/tmp/deepseek-content.txt` (7 lines)
- Claude Opus 4.7 file:line investigation 2026-05-19 ~15:30 WITA
- `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/alzheimer-diagnose-20260519.md:9`
- `~/.claude/settings.json` SessionStart hook chain (verified verbatim)
