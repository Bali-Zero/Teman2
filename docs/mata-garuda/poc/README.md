# Mata Garuda POC — Sprint 1 reference code

> Data: 2026-04-09 | Sessione S04
> Status: REFERENCE CODE, non installabile
> Riferimento: [50-BUILD-ORDER.md](../50-BUILD-ORDER.md) Sprint 1

## Cos'è questo

Questi sono i **primi 3 file di riferimento** del Sprint 1 (registry, types, dummy_agent).
Sono codice leggibile, validato concettualmente, MA **non sono ancora un package installabile** perché manca la decisione architetturale:

> Q: dove vive il package `mata_garuda/`?
> - (a) `apps/mata-garuda/` dentro monorepo Nuzantara
> - (b) `~/Desktop/mata-garuda/` standalone
> - (c) Repo Git separato `Balizero1987/mata-garuda` privato (raccomandato)

Quando la decisione sarà presa, questi file vanno copiati nella destinazione finale e completati con `__init__.py`, `pyproject.toml`, `cli.py`, `runtime/`.

## File presenti

| File | LOC | Cosa fa |
|---|---|---|
| `registry.py` | ~80 | Singleton + decorator (Pattern 1 di 40d) |
| `types.py` | ~35 | Pydantic Agent/Response/Result |
| `dummy_agent.py` | ~50 | Agente template per `create_agent` del meta-agent |
| `dummy_agent_GENOME.md` | ~25 | GENOME esempio (Lamarckian-ready) |

## Validazione concettuale

Prima del POC reale, verificare che:
1. Sintassi Python valida (parsing)
2. Import strutture coerenti
3. Pydantic models compatibili tra loro
4. Pattern decorator funzioni in isolamento

Questi 4 punti sono coperti dai file qui sotto. Il vero `pip install -e .` arriva quando Zero decide la posizione del package.

## Prossimi step (post-decisione)

1. Decidere posizione (a/b/c)
2. `mkdir <posizione>/mata_garuda/`
3. Copiare i 3 file `.py` qui presenti
4. Creare `__init__.py`, `pyproject.toml`, `runtime/cli_runtime.py`
5. `pip install -e .` in venv pulito
6. `pytest tests/test_registry.py`
7. Validare DoD Sprint 1 di [50-BUILD-ORDER.md](../50-BUILD-ORDER.md)
