# Mata Garuda

> Intelligence Super Hub — OSINT blindato, CLI-only, Lamarckian meta-agent

**Owner:** Zero (esclusivo)
**Stato:** Sprint 1 — walking skeleton
**Vincoli:** LLM CLI-only, no API HTTP, no cloud, no shared

## Cos'è

Mata Garuda è un sistema di intelligence personale per Zero, progettato attorno a 5 layer (Harvester → Kognitif → Nexus → Analista → Distribuzione) più un **meta-agent layer** trasversale che governa il ciclo di vita degli agenti.

Il meta-agent usa il pattern **Lamarckian** (ispirato a `suryast/agent-taxonomy`) dove ogni fallimento diventa regola, ogni regola diventa mutazione di `GENOME.md`, ogni mutazione viene validata con fitness metrics e può essere auto-revertita.

## Principi inviolabili

1. **CLI-only** — Claude/Gemini/Codex via subprocess, MAI API HTTP. DeepSeek API OK per reasoning.
2. **OSINT blindato** — dati OSINT sono proprietà Zero, MAI frontend/clienti/team/cloud.
3. **Locale Pro** — tutto gira su MacBook Pro M4 48GB, one-way IN dal cloud.
4. **Lamarckian** — ogni agente ha `GENOME.md`, mutazioni richiedono review.
5. **Pydantic-only** — zero dipendenze HTTP nel runtime core.

## Stato attuale

- ✅ Sprint 1 walking skeleton (registry + types + dummy_agent)
- 🚧 Sprint 2 meta-agent (in design)
- ⏸️ Sprint 3 Lamarckian loop
- ⏸️ Sprint 4 POC Regulation Watcher

## Documentazione

La documentazione vive nel repo Nuzantara sotto `docs/mata-garuda/`:
- `01-VISION.md` — visione completa
- `02-ARCHITECTURE.md` — 5 layer + meta-agent
- `50-BUILD-ORDER.md` — sprint plan
- `40c-AUTOAGENT-EVAL.md`, `40d-AUTOAGENT-PATTERNS.md` — pattern estratti

## Install (Sprint 1)

```bash
cd ~/Desktop/mata-garuda
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m mata_garuda.cli list-agents
```

## License

MIT — vedi `LICENSE`
