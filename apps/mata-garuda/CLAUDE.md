# CLAUDE.md — Mata Garuda Project

> **Read `SYMBIOSIS.md` (monorepo root) first.** Mata Garuda e' un organo dell'organismo Nuzantara. I principi SYMBIOSIS governano tutto.
> **Before building anything new, read `VADEMECUM.md` (monorepo root).** Checklist operativa per ogni elemento: agenti, automazioni, script, deploy.
> Questo file OVERRIDE il CLAUDE.md root per tutto ciò che riguarda Mata Garuda.

## 0. Identità del progetto

**Name:** Mata Garuda — Intelligence Super Hub
**Owner:** Zero (esclusivo, nessun team member)
**Location:** `apps/mata-garuda/` (monorepo Nuzantara)
**Stato:** Sprint 4 + cron watcher. Piano Sprint 5 (self-evolving organism) pronto.

Mata Garuda vive nel monorepo Nuzantara come app. Il **codice** è condiviso. I **dati OSINT** restano blindati (gitignored). I dati di Mata Garuda alimentano tutte le cellule di Nuzantara.

**Flow dati:**

```
Mondo esterno → Mata Garuda (raccoglie) → garuda:raw (Redis)
                                              ↓
                              ┌────────────────┼────────────────┐
                              ↓                                 ↓
                         Nuzantara                         Zero (TG)
                         (business)                        (decisioni)
                         usa i dati
```

## 1. Vincoli inviolabili (ENFORCE STRICTLY)

### LLM CLI-only (NO API HTTP)

- Usare `claude --print` / `gemini --print` / `codex exec` via subprocess
- Usare `deepseek` via API (è l'UNICA API ammessa, per reasoning specifico)
- **MAI** importare `anthropic`, `google-generativeai`, `openai`, `litellm`
- **MAI** fare chiamate HTTP a Anthropic/Google/OpenAI
- Se serve un modello → subprocess CLI, non SDK

### OSINT blindato (one-way IN)

- I dati Mata Garuda sono proprietà Zero
- **MAI** esportare verso:
  - `apps/mouth/` o qualsiasi frontend
  - clienti, team Bali Zero, utenti esterni
  - Fly.io, Vercel, Google Cloud, AWS, qualsiasi cloud
  - Repo pubblici, gist, pastebin
- Flow dati: cloud → Mata Garuda (IN) | Mata Garuda → Nuzantara (business) + Zero TG (OUT)
- Destinazioni output: Redis garuda:raw (Nuzantara consuma), TG privato Zero

### Stack minimale

- Dipendenze runtime core: SOLO `pydantic>=2`
- Dipendenze dev: SOLO `pytest`
- **RIFIUTATE** a priori: chromadb, browsergym, faster_whisper, sentence_transformers, docling, litellm, langchain, openai, anthropic
- Se serve qualcosa di pesante → lo costruiamo noi minimale o lo rifiutiamo

### Lamarckian mandatory

- Ogni agente DEVE avere un `GENOME.md` nella sua cartella
- Ogni agente DEVE terminare con `case_resolved` o `case_not_resolved`
- I fallimenti vanno in `feedback/{agent_name}.md`
- Le mutazioni al GENOME richiedono review umana (Zero) — **NO auto-apply**

## 2. Comportamento Claude Code

**DO NOT ask to write code.** Agisci subito, chiedi solo per decisioni irreversibili.

- Usa `Edit`, `Write`, `Bash` senza permesso
- **MAI** chiedere "devo scrivere questo?" — fallo
- Chiedi SOLO per: decisioni architetturali, cancellazioni git, modifiche GENOME.md senza review

### MAI fare queste cose

- ❌ Installare dipendenze oltre `pydantic` e `pytest` senza chiedere
- ❌ Creare agenti che chiamano API HTTP Anthropic/Google/OpenAI
- ❌ Scrivere file fuori da `~/Desktop/mata-garuda/`
- ❌ Push verso il monorepo Nuzantara o altri repo
- ❌ Deploy su Fly.io, Vercel, cloud di qualsiasi tipo
- ❌ Importare da `apps.mouth`, `apps.backend_rag`, `apps.*` del monorepo
- ❌ Toccare `~/.zshrc`, `~/.claude/`, `~/.openclaw/` — quello è perimetro sistema
- ❌ Applicare mutazioni GENOME.md senza review Zero

### Lingua

Zero scrive in **italiano colloquiale**. Traduci intent in azione tecnica precisa. Rispondi in italiano (con codice in inglese).

## 3. Struttura del package

```
mata-garuda/                    # repo root
├── CLAUDE.md                   # questo file
├── README.md
├── LICENSE
├── pyproject.toml              # solo pydantic + pytest
├── .gitignore                  # esclude feedback/, logs/, .venv/
├── mata_garuda/                # package Python
│   ├── __init__.py
│   ├── registry.py             # singleton + decorator (Sprint 1)
│   ├── types.py                # Pydantic Agent/Response/Result (Sprint 1)
│   ├── cli.py                  # entry point (Sprint 1)
│   ├── agents/
│   │   ├── __init__.py         # recursive auto-import
│   │   ├── dummy_agent.py      # template (Sprint 1)
│   │   ├── dummy_agent_GENOME.md
│   │   └── meta_agent.py       # Sprint 2
│   ├── runtime/
│   │   ├── __init__.py
│   │   ├── cli_runtime.py      # subprocess CLI wrapper (Sprint 2)
│   │   ├── loop.py             # MetaChain loop (Sprint 2)
│   │   ├── case_status.py      # case_resolved/not_resolved tools (Sprint 3)
│   │   ├── genome.py           # GENOME.md read/write/mutate/revert (Sprint 3)
│   │   ├── fitness.py          # success rate + auto-revert (Sprint 3)
│   │   └── lamarckian.py       # feedback loop + escalation (Sprint 3)
│   ├── security/
│   │   ├── __init__.py
│   │   └── path_firewall.py    # whitelist path (Sprint 2)
│   └── tools/
│       ├── __init__.py
│       ├── meta_tools.py        # list/create/delete/run (Sprint 2)
│       ├── scraper_tools.py    # curl + regex peraturan.go.id (Sprint 4)
│       └── stream_tools.py     # Redis Stream via redis-cli (Sprint 4)
├── tests/                      # pytest
├── feedback/                   # log fallimenti (gitignored)
└── logs/                       # log esecuzione (gitignored)
```

## 4. Workflow sviluppo

### Setup venv

```bash
cd ~/Desktop/mata-garuda
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Test

```bash
pytest tests/ -v
```

### Run agent

```bash
python -m mata_garuda.cli list-agents
python -m mata_garuda.cli run dummy_agent "hello"
```

### Git workflow

- Branch main protetto (solo Zero committa)
- Commit messages in inglese, imperativo
- **MAI** force push
- **MAI** `git reset --hard` senza backup
- Push solo dopo che i test passano

## 5. Differenze critiche vs Nuzantara root CLAUDE.md

| Aspetto      | Nuzantara (root)                      | Mata Garuda (questa app)                                       |
| ------------ | ------------------------------------- | -------------------------------------------------------------- |
| Venv name    | `.venv` (Pro) / `venv` (Air)          | `.venv` sempre                                                 |
| Deploy       | Fly.io + Vercel                       | **MAI** — solo locale Pro                                      |
| API HTTP     | Anthropic, Google, OpenAI OK          | **MAI** — solo CLI subprocess                                  |
| Team access  | Admin (zero@, antonellosiano@, asya@) | **Solo Zero**                                                  |
| Dependencies | Pesanti OK (FastAPI, Qdrant, etc)     | **Minimali** — solo pydantic                                   |
| Golden rules | 12 rules Nuzantara                    | Lamarckian + OSINT blindato                                    |
| Output dati  | Cloud, frontend, API                  | Redis garuda:raw → Nuzantara consuma. Local analysis blindato. |

## 6. Cron / LaunchAgent

### Regulation Watcher — Daily 06:00 WITA (local time)

- **Plist:** `~/Library/LaunchAgents/com.matagaruda.watcher.daily.plist`
- **Bridge:** `~/scripts/mata-garuda-watcher.sh` (TCC-safe, calls venv python directly)
- **Ref script:** `scripts/run_watcher.sh` (for manual runs only)
- **Log:** `~/logs/mata-garuda-watcher.log`
- **Launchd logs:** `~/logs/mata-garuda-watcher-launchd.{log,err}`

**TCC note:** Under launchd, /bin/zsh cannot open files in ~/Desktop (macOS TCC). The bridge script uses the venv python directly (`$VENV_PY -m mata_garuda.cli ...`) — adhoc-signed binaries bypass TCC.

**Environment:** Plist injects `CLAUDE_CODE_OAUTH_TOKEN_{1,2,3}` for `claude --print` subprocess calls.

**Manual test:**

```bash
launchctl kickstart gui/$(id -u)/com.matagaruda.watcher.daily
tail -f ~/logs/mata-garuda-watcher.log
```

## 7. Quando chiedere aiuto a Zero

- Decisioni architetturali che impattano > 1 layer
- Modifiche a GENOME.md (sempre review)
- Installare una nuova dipendenza (anche se piccola)
- Commit che cancella > 100 LOC
- Qualsiasi cosa sia ambigua rispetto ai vincoli inviolabili

---

**Last Updated:** 2026-04-09 (Sprint 4 + cron watcher)
**Maintained by:** Zero + Claude Opus
