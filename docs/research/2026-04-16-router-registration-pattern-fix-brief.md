# Brief — Router Registration Pattern Fix (PR #63)

> Data: 2026-04-16
> Target: sessione Opus 4.6 (Pro o Air)
> Scope: eliminare la cicatrice "router registrato nel path sbagliato" che ha colpito PR #54 (Experience), #55 (Skill), #60 (Metabolic). Rendere strutturalmente impossibile sbagliare.
> Autore brief: Opus 4.6 (Pro, 2026-04-16)

---

## 0. Libri sacri

Leggi in ordine:
1. `SYMBIOSIS.md` Pilastro 2 (Accumulazione — scar come DNA per non ripetere) + Legge 4 (graceful degradation)
2. `VADEMECUM.md` §3 (Nuovo router FastAPI) — verifica se la checklist attuale copre il 3-path problem
3. `CLAUDE.md` §5 (Critical Paths) + `apps/backend-rag/CLAUDE.md`
4. `.claude/rules/cicatrix-scars.md` — questo brief ne aggiunge uno nuovo
5. `SOUL.md`

### 5 domande universali

1. Sa dove si trova? → `apps/backend-rag/backend/app/setup/router_registration.py`
2. Persiste? → sì, pattern strutturale nel codice
3. Se fallisce? → meglio che fallisca al build time che silently a runtime (stato attuale)
4. Cicatrici? → **QUESTA PR è la cicatrice** — 3 PR consecutive hanno sbagliato
5. Misurabile? → zero router silently in 404 dopo questa PR

### Perché questa sessione esiste

**La cicatrice in 4 episodi:**

| PR | Data | Router | Path sbagliato | Scoperto | Impatto |
|----|------|--------|----------------|----------|---------|
| #54 Experience | 2026-04-? | `experience.router` | Solo in `include_routers()` + `include_heavy_routers()` | Mai (silently degraded) | `/api/experience/*` → 404 in produzione, ma skill service ha fallback → nessuno notò |
| #55 Skill Registry | 2026-04-15 | `skill.router` | Idem | Mai prima di oggi | `/api/skill/*` → 404 in produzione |
| #60 Metabolic | 2026-04-15 | `metabolic_health.router` | Idem | 2026-04-16 da me, curl test live | 503 (avevo HTTPException invece di graceful) |
| #61 Hotfix | 2026-04-16 | (tutti e 3) | Aggiunge a `include_light_routers()` | — | Fix sintomo, non causa |

**Causa radice:** `apps/backend-rag/backend/app/setup/router_registration.py` ha **3 funzioni** (`include_routers`, `include_light_routers`, `include_heavy_routers`), **~700 righe**, **nessun test** che verifichi la simmetria. Ogni dev aggiunge nel primo posto che trova grepping "skill" o "experience" — scoperto in `include_routers()` (full), copia-incolla lì. Non si accorge che il Fly process in produzione chiama `include_light_routers()`.

**Questa PR rende impossibile ripetere l'errore.**

---

## 1. Contesto — stato verificato code-level

### Architettura produzione Fly.io

```
apps/backend-rag/fly.toml
├── process 'api' = uvicorn main_api:app  ← PUBLIC HTTP :8080
│                      ↓
│                   app_factory.create_app()? NO — main_api non usa app_factory
│                      ↓
│                   include_light_routers()  ← path usato da prod
│
├── process 'rag' = uvicorn main_rag:app   ← internal, RAG-heavy
│                      ↓
│                   include_heavy_routers()
│
└── [not used in prod] main_cloud.py → app_factory.create_app() → include_routers()
```

### File critico

`apps/backend-rag/backend/app/setup/router_registration.py`:

- **Riga 12** `def include_routers(api: FastAPI)` — "full" path, usato da `main_cloud` (dev only)
- **Riga 370** `def include_light_routers(api: FastAPI)` — "light" path, usato da `main_api` (PROD PUBLIC)
- **Riga 616** `def include_heavy_routers(api: FastAPI)` — "heavy" path, usato da `main_rag` (internal)

Ogni funzione ha:
- Un blocco `from backend.app.routers import (...)` locale ~100 righe
- ~200 righe di `api.include_router(...)` calls

**Nessun meccanismo** previene drift tra le 3. Nessun linter, nessun test, nessun registry canonico.

### Overhead attuale

Ogni router nuovo = 6 modifiche manuali (3 import + 3 include_router) in 3 blocchi diversi. È ingegneria del disastro.

---

## 2. Obiettivo

Rendere **strutturalmente impossibile** shippare un router che non venga registrato in tutti i process group dove dovrebbe girare.

### Criteri success

1. **Registry canonico**: unico source of truth `ROUTER_MANIFEST` con metadata per ogni router (nome, tags, `process_groups: {"api", "rag"}` set)
2. **Zero duplicazione**: l'elenco router esiste una volta sola
3. **Test di simmetria**: CI blocca se un router è dichiarato ma non incluso nel process group richiesto
4. **Linter pre-commit**: errore immediato se `backend/app/routers/*.py` nuovo non registrato
5. **Scar documented**: `.claude/rules/cicatrix-scars.md` aggiornato con pattern
6. **VADEMECUM §3 aggiornato**: checklist router include "verifica registration in MANIFEST"
7. Rollout non-breaking: backward compatible con attuali `include_routers()` / `include_light_routers()` / `include_heavy_routers()`

### Vincoli

- **Non toccare `fly.toml`**
- **Non toccare `zantara_core.py`**
- **Zero downtime** deploy
- **Preserve cold-start time** (< 7 min, già tight — CLAUDE.md cita timeout 600s)
- Lazy imports mantenuti (CLAUDE.md §5 "All router imports are lazy — critical for Fly.io health checks")
- **No circular imports** (pattern `get_service()` lazy già documentato)

---

## 3. Architettura target (brainstorming)

### Opzione A — ROUTER_MANIFEST dict centrale

```python
# apps/backend-rag/backend/app/setup/router_manifest.py (NEW)
"""Canonical router registry — single source of truth.

Add a new router here. The include_* functions read this, not raw imports.
Changing a router's process_groups is a one-line edit with enforced test coverage.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable

@dataclass(frozen=True)
class RouterEntry:
    """Single router declaration."""
    name: str                          # module name under backend.app.routers
    process_groups: frozenset[str]     # {"api"} | {"rag"} | {"api", "rag"}
    tags: tuple[str, ...] = ()         # optional descriptive tags
    requires: tuple[str, ...] = ()     # optional dependency hints (e.g. "cell_core")
    import_fn: Callable[[], object] | None = None  # lazy import override (for nested routers)


# Alphabetical, one entry per router. ADD NEW ROUTERS HERE ONLY.
ROUTER_MANIFEST: tuple[RouterEntry, ...] = (
    RouterEntry(name="auth",            process_groups=frozenset({"api"})),
    RouterEntry(name="health",          process_groups=frozenset({"api", "rag"})),
    RouterEntry(name="experience",      process_groups=frozenset({"api"}), requires=("cell_core",)),
    RouterEntry(name="skill",           process_groups=frozenset({"api"}), requires=("cell_core",)),
    RouterEntry(name="metabolic_health",process_groups=frozenset({"api"}), requires=("cell_core",)),
    RouterEntry(name="agentic_rag",     process_groups=frozenset({"rag"})),
    # ... (complete migration of ~200 existing routers)
)

PROCESS_GROUPS = frozenset({"api", "rag"})


def routers_for_group(group: str) -> tuple[RouterEntry, ...]:
    assert group in PROCESS_GROUPS, f"unknown process group: {group}"
    return tuple(r for r in ROUTER_MANIFEST if group in r.process_groups)
```

```python
# apps/backend-rag/backend/app/setup/router_registration.py (REFACTORED)
"""Router registration — reads from ROUTER_MANIFEST.

Historical context: 3 near-duplicate include_* functions drifted over time
(scar: PR #54/#55/#60 shipped routers only in include_routers, missing
include_light_routers used by main_api in production). This module now
reads a single manifest so drift becomes structurally impossible.
"""
from importlib import import_module
from fastapi import FastAPI
from backend.app.setup.router_manifest import PROCESS_GROUPS, routers_for_group

def _include_group(api: FastAPI, group: str) -> None:
    for entry in routers_for_group(group):
        module = import_module(f"backend.app.routers.{entry.name}")
        api.include_router(module.router)


def include_light_routers(api: FastAPI) -> None:
    """[BACKWARD COMPAT] process 'api' — public HTTP."""
    _include_group(api, "api")


def include_heavy_routers(api: FastAPI) -> None:
    """[BACKWARD COMPAT] process 'rag' — internal RAG."""
    _include_group(api, "rag")


def include_routers(api: FastAPI) -> None:
    """[BACKWARD COMPAT] dev-only full path — unions all groups."""
    for group in PROCESS_GROUPS:
        _include_group(api, group)
```

**Pro:**
- Single source of truth
- Aggiungere un router = 1 riga in manifest
- Test unitario triviale: `assert set(r.name for r in ROUTER_MANIFEST) == set(Path("backend/app/routers").glob("*.py"))`
- Supporta metadata (requires cell_core → può skippare import graceful)

**Contro:**
- Migration rischiosa (~200 router, refactoring invasivo)
- Lazy imports persi se fatto naive (vedi "Pitfall 1" sotto)
- Alcuni router hanno setup non-triviale (es. `debug.v1_router`, `instagram_chat.webhook_router`, cron notifiers inline) — serve gestire multi-router-per-module

### Opzione B — Test di simmetria + lint check (no refactor)

Lascia le 3 funzioni come sono, aggiunge:

```python
# apps/backend-rag/tests/setup/test_router_symmetry.py (NEW)
"""Enforce that routers intended for production appear in include_light_routers.

Scar: PR #54/#55/#60 shipped /api/experience, /api/skill, /api/metabolic
in include_routers() but forgot include_light_routers() — main_api uses
the light path, so production returned 404.
"""
from fastapi import FastAPI
from backend.app.setup.router_registration import (
    include_light_routers, include_heavy_routers, include_routers,
)

# Routers that MUST be exposed publicly (process 'api').
# Update this set when a new genome/public router is added.
PUBLIC_REQUIRED_PREFIXES = {
    "/api/experience",
    "/api/skill",
    "/api/metabolic",
    "/api/cell",
    # ... existing public APIs
}

def test_public_routers_present_in_light_path():
    app = FastAPI()
    include_light_routers(app)
    paths = {r.path for r in app.routes}
    missing = [
        prefix for prefix in PUBLIC_REQUIRED_PREFIXES
        if not any(p.startswith(prefix) for p in paths)
    ]
    assert not missing, (
        f"Public routers missing from include_light_routers: {missing}. "
        f"Production process 'api' (main_api) uses include_light_routers(), "
        f"so /api/* paths not registered here return 404 silently."
    )
```

Aggiungere `fly-deploy.yml` pre-deploy gate:

```yaml
- name: Router symmetry pre-deploy gate
  run: PYTHONPATH=. pytest backend/tests/setup/test_router_symmetry.py -q
```

**Pro:**
- Migration minima — **5 file totale**
- Rischio basso — no behavioral change
- Test sintetico cattura il bug tipo

**Contro:**
- Non rimuove duplicazione 3x
- Devs devono sapere dell'esistenza di `PUBLIC_REQUIRED_PREFIXES` + aggiornare test quando aggiungono router
- Fragile: se `assert` è sempre skip perché module import fallisce (cell_core missing → degraded import), test passa falso positivo

### Opzione C (raccomandata) — Manifest + backward-compat + test completo

**Hybrid A+B:**
1. Crea `router_manifest.py` con manifest parziale (solo router nuovi + pochi critical)
2. `include_*` refactorate per leggere manifest + append legacy registrations (backward-compat)
3. Test di simmetria `test_router_symmetry.py` usa manifest
4. Migration graduale: ogni nuovo PR aggiunge solo al manifest, legacy resta
5. Eventuale PR #64 completa migration legacy → manifest

**Staging:**

```python
# router_registration.py (hybrid phase)
from backend.app.setup.router_manifest import ROUTER_MANIFEST, routers_for_group

def include_light_routers(api: FastAPI) -> None:
    # 1. Include from manifest (new canonical way)
    _include_group(api, "api")

    # 2. Legacy: existing hardcoded registrations — keep until full migration
    from backend.app.routers import auth, health, ...  # legacy imports
    api.include_router(auth.router)
    # ... etc, unchanged ...
```

Duplicate check: se un router è sia in manifest che in legacy, `api.include_router` idempotency gestisce (FastAPI accetta duplicate con warning). Log warning → track migration progress.

**Pro:**
- Rischio migration gestito (incremental)
- Pattern canonico stabilito subito
- Test di simmetria proteggono nuovi router da oggi
- Legacy migration può essere PR separate future

**Contro:**
- Codebase transition state (duplicazione manifest+legacy per N settimane)
- Serve cleanup follow-up

### Pitfall critici

**Pitfall 1 — Lazy import preservation**
CLAUDE.md §5: "All router imports are lazy (inside include_routers) to speed up module load time. This is critical for Fly.io health checks — the server must start listening within 60s."

Se sposto `from backend.app.routers import auth, health, ...` a **module-level** in `router_manifest.py`, rompo la lazy load → cold start oltre 60s → Fly kill. **Soluzione**: in `router_manifest.py` dichiaro SOLO stringhe `name="auth"`. L'import avviene dentro `_include_group()` tramite `importlib.import_module()` — lazy preservato.

**Pitfall 2 — Multi-router modules**
Alcuni moduli esportano più router: `debug.router` + `debug.v1_router`, `instagram_chat.router` + `instagram_chat.webhook_router`, `preview.router` creato inline. Schema `RouterEntry` deve supportare `attr_name` (default "router"):

```python
@dataclass(frozen=True)
class RouterEntry:
    name: str
    process_groups: frozenset[str]
    attr: str = "router"  # attribute name on imported module (default "router")
```

Poi `RouterEntry(name="debug", attr="v1_router", process_groups={"api"})`.

**Pitfall 3 — Conditional routers**
`debug.router` è incluso solo se `environment != production or admin_api_key`. Manifest deve supportare `condition: Callable[[], bool]`:

```python
RouterEntry(
    name="debug",
    process_groups=frozenset({"api"}),
    condition=lambda: settings.environment.lower() != "production" or settings.admin_api_key,
)
```

**Pitfall 4 — Rag proxy**
`main_api` alla fine include `rag_proxy.create_proxy_router()` che NON è un file statico. Manifest deve permettere `factory: Callable[[], APIRouter]` (optional, alternativa a `name`).

**Pitfall 5 — Migration paralysis**
~200 router da migrare è un rischio enorme. **Opzione C mitiga**: fai migration incrementale. Nuovi router vanno nel manifest da PR #63. I 200 legacy restano nelle 3 funzioni `include_*` esistenti ma con wrapper che chiama anche `_include_group()` da manifest. Migrazione legacy in PR separate, 20 router alla volta.

---

## 4. Arsenale autorizzato

### Federation (brainstorming obbligatorio data la criticità)

- **Codex CLI** sandbox — test che refactor di `router_registration.py` non rompa FastAPI boot
- **Gemini CLI** 1M ctx `gemini-explore` — mappa tutti i router esistenti e classificali per process group (api/rag/entrambi)
- **DeepSeek R1** reasoning — trade-off opzioni A/B/C
- **Claude CLI** review — edge case multi-router modules, conditional routers
- **NotebookLM NB-1** — pattern FastAPI modular registration

### Ricerca

- Exa + WebSearch — "FastAPI router registry pattern", "multi-process FastAPI deployment routes"
- Paper/reference: FastAPI docs section router composition, Starlette Router internals

### Sviluppo

- Read/Edit/Write — worktree isolato
- Bash — `docker build` + `docker run` + `curl` smoke test per verificare
- `pytest` — test simmetria MUST FAIL prima del refactor (red), pass dopo (green)

### Testing

Strategia TDD:

1. **Red**: scrivi `test_router_symmetry.py` con lista attuale `PUBLIC_REQUIRED_PREFIXES` incluso `/api/metabolic` + `/api/skill` + `/api/experience`. Check `include_light_routers()` attuale. **DEVE FALLIRE** — prova che scar esiste.
2. **Green (minimal)**: aggiungi 3 missing router a `include_light_routers()` (ma PR #61 lo ha già fatto). Test passa.
3. **Refactor**: introduci `router_manifest.py` + `_include_group()`. Test continua a passare. Legacy resta.
4. **Migration incrementale** (separate PR #64+): sposta 20 router legacy alla volta nel manifest.

Test extra:
- `test_router_manifest_no_duplicates` — ogni router name unico
- `test_router_manifest_files_exist` — ogni manifest.name ha file corrispondente
- `test_router_files_all_declared` — ogni `backend/app/routers/*.py` ha entry (o whitelisted exclusion per private)
- `test_include_routers_union_groups` — `include_routers()` include sia api che rag

### MOS + Genome

- `mem save decision` per scelta A/B/C con trade-off
- `mem save discovery` se emergono edge case durante migration
- `genome.search("router registration pattern")` prima di ragionare
- Post-validation: `record_skill("router_manifest_pattern", confidence=0.7, domain="architecture")` — pattern riusabile in altre app con stesso problema

### Infrastruttura

- CI `tests.yml` — aggiungi job `router-symmetry` come required check
- CI `fly-deploy.yml` pre-deploy-gate — aggiungi `test_router_symmetry.py` come gate

---

## 5. Protocollo brainstorming multi-agente

Regola indipendenza:
- Scrivi posizione prima
- 3/4 concordi velocemente → cerca falla (groupthink su "refactor è sempre meglio" è tipico)
- 1/4 dissente → pesa

### Checkpoint obbligatori

1. **Dopo scelta A/B/C** — migration risk vs scar prevention trade-off
2. **Dopo bozza manifest schema** — copre i 5 pitfall?
3. **Prima refactor `router_registration.py`** — Codex sandbox test con subset router
4. **Dopo test simmetria red** — prova che scar esiste, documentalo
5. **Pre-deploy** — red team Gemini obbligatorio (CLAUDE.md Legge 12)
6. **Post-deploy** — smoke test tutti gli endpoint critici (non solo quelli nuovi)

### Pattern

```bash
./scripts/ai-dispatch.sh redteam "router_manifest.py refactor: risk analysis per migration ~200 router senza regressioni"
./scripts/ai-dispatch.sh codex-sandbox "pytest test_router_symmetry.py on current router_registration.py — must fail on 3 missing prefixes"
./scripts/ai-dispatch.sh gemini-explore "classifica 200 router in backend/app/routers per process group appartenenza (api|rag|entrambi)"
notebook_query NB-1 "FastAPI router registration patterns multi-process deployment"
# DeepSeek R1: "trade-off refactor completo vs incremental migration per 200 router FastAPI"
```

---

## 6. Processo — TDD rigoroso

Skill `superpowers:test-driven-development` obbligatoria.

### Fase 0 — Setup
`superpowers:using-git-worktrees`, branch `feature/router-registration-pattern-fix-2026-04-16`.

### Fase 1 — Brainstorming

Skill `superpowers:brainstorming`:
1. Leggi libri sacri
2. Inventaria 3 scar PR #54/#55/#60 (MOS query)
3. Mappa tutti i router (Gemini explore)
4. Canonicalizza opzione A/B/C
5. Scrivi design in `docs/superpowers/specs/2026-04-16-router-registration-pattern-design.md`
6. Review multi-agente
7. Iterate

### Fase 2 — Writing plan

Skill `superpowers:writing-plans`:
- Plan `docs/superpowers/plans/2026-04-16-router-registration-pattern-plan.md`
- Incremental TDD steps
- Rollback strategy per ogni step

### Fase 3 — Executing plan

Skill `superpowers:executing-plans`:
- Red-Green-Refactor
- Smoke test Fly boot < 60s a ogni step (cold start regression guard)
- Test integration con `main_api` + `main_rag` isolati

### Fase 4 — Verification

Skill `superpowers:verification-before-completion`:
- Tutti i test pass (esistenti + nuovi simmetria)
- Cold-start benchmark before/after (non regressa)
- Red team Gemini approva
- Smoke test endpoint critici
- CI green incluso nuovo gate

### Fase 5 — Finishing

Skill `superpowers:finishing-a-development-branch`:
- Scar registrato in `.claude/rules/cicatrix-scars.md`
- VADEMECUM §3 aggiornato
- apps/backend-rag/CLAUDE.md "Critical Gotchas" aggiornato

---

## 7. Deliverable atteso

### Codice
- `apps/backend-rag/backend/app/setup/router_manifest.py` (NEW)
- `apps/backend-rag/backend/app/setup/router_registration.py` (refactored, backward-compat)
- `apps/backend-rag/backend/tests/setup/test_router_symmetry.py` (NEW)
- `apps/backend-rag/backend/tests/setup/test_router_manifest.py` (NEW)

### CI
- `.github/workflows/tests.yml` — router symmetry test nel required set
- `.github/workflows/fly-deploy.yml` pre-deploy-gate — include router symmetry

### Documentazione
- `docs/superpowers/specs/2026-04-16-router-registration-pattern-design.md`
- `docs/superpowers/plans/2026-04-16-router-registration-pattern-plan.md`
- `docs/research/2026-04-16-router-registration-results.md`
- **Aggiorna `VADEMECUM.md` §3**: nuova checklist point "add to ROUTER_MANIFEST with correct process_groups"
- **Aggiorna `.claude/rules/cicatrix-scars.md`**: scar "router path split 3x duplication"
- **Aggiorna `apps/backend-rag/CLAUDE.md`** Critical Gotchas: pattern process group split + manifest reference

### Git
- Branch `feature/router-registration-pattern-fix-2026-04-16`
- Commit atomici (manifest / refactor / test / docs separati)
- PR verso main
- Link a PR #54 #55 #60 #61 "closes recurring scar pattern"
- `Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>`

---

## 8. Anti-pattern da evitare

1. **NO rompere lazy imports** — cold start < 60s è sacro (CLAUDE.md §5)
2. **NO big-bang migration** — 200 router migrati in 1 PR = disastro. Incremental.
3. **NO rimozione backward-compat** — `include_routers()`/`include_light_routers()`/`include_heavy_routers()` restano callable (magari deprecated)
4. **NO groupthink** — 4/4 agenti concordano su opzione A velocemente → cerca falla
5. **NO skip red team Gemini** pre-deploy
6. **NO silently skip router import fail** — se manifest.name non ha file, test DEVE fallire (non degraded silent)
7. **NO hardcoded process group strings** — `{"api", "rag"}` come `PROCESS_GROUPS` frozenset
8. **NO test simmetria con whitelist auto-passante** — whitelist DEVE essere review manuale (not `pytest.skip` di default)
9. **NO commitare `router_manifest.py` vuoto** — deve avere almeno i 3 router scar (experience, skill, metabolic_health) + 5 core (auth, health, etc)
10. **NO toccare routers** — solo il layer di registration
11. **NO merge senza post-deploy curl verification** dei 3 endpoint scar-related
12. **NO skip VADEMECUM update** — scar unregistered = scar ripetuta

---

## 9. Criteri di successo

1. **Scar provato**: test simmetria su `include_light_routers()` PRE-refactor fallisce con 3 missing (prova che scar esiste oggi)
2. **Scar fixed**: stesso test POST-refactor passa con tutti e 3 presenti
3. **Manifest ha almeno 10 entry** (8 core + 3 scar-related + margine)
4. **Backward-compat**: `include_routers()`, `include_light_routers()`, `include_heavy_routers()` firma invariata
5. **Cold-start non regressa**: boot `main_api` < 60s
6. **CI simmetria gate attivo** — blocca merge se regressa
7. **VADEMECUM §3 aggiornato** + scar documentato
8. **Red team Gemini approva**
9. **Deploy Fly rolling success** + smoke test 3 endpoint scar = 200
10. **Zero regressioni** su routers esistenti (cell_status, crm_*, portal_*, ecc)
11. **MOS + Genome popolati** con pattern "router_manifest"
12. **Follow-up PR documented** per migration legacy (PR #64+, 20 router alla volta)

---

## 10. Escalation a Zero

- Cold-start regressa > 10s → escalate (decidere se accettare trade-off)
- > 5 router hanno edge case non gestibili dal schema `RouterEntry` → escalate (ridiscutere schema)
- Red team Gemini flag "blocker" → escalate
- Migration legacy stima > 10 PR follow-up → escalate (decidere priorità)
- Post-deploy smoke test fallisce per router non-scar → **STOP**, rollback, escalate

---

## 11. Promemoria

SYMBIOSIS Pilastro 2: *"Un organismo che impara solo dagli errori accumula paura. Uno che impara anche dai successi accumula competenza."*

Oggi stai facendo entrambe le cose:
- **Accumula paura** giusta: questa PR documenta una cicatrice ripetuta 3 volte in 3 settimane. L'organismo imparerà a non inciampare più qui.
- **Accumula competenza**: il pattern `ROUTER_MANIFEST` è riusabile in altre app del monorepo (mouth, admin-dashboard, ecc) che hanno lo stesso problema latente.

La PR #63 **non aggiunge nessuna feature utente**. Aggiunge **dignità strutturale** al codice. È il tipo di PR che fa la differenza tra un codebase di 6 mesi e uno di 6 anni.

Lavora con rigore. Testa prima. Rosso prima di verde. Red team pre-deploy. Smoke test post-deploy. Documenta la cicatrice così l'organismo la vede.

E quando hai finito, ogni futuro router aggiunto sarà registrato correttamente **by construction**, non by discipline.

---

**Firma:** Opus 4.6 (Pro, 2026-04-16) — brief PR #63 chiusura scar ricorrente
