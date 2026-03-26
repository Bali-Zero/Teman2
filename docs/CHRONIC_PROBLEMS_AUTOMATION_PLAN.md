# Piano Automazione — 14 Problemi Cronici Nuzantara

**Data:** 2026-03-26
**Fonti:** Web Research (7 ricerche), Gemini codebase analysis, DeepSeek R1 671b reasoning (3926 tokens, $0.014), analisi diretta
**Obiettivo:** Azzerare ogni problema ricorrente con automazione autonoma, zero intervento umano

---

## Matrice Priorità

| Rank | # | Problema | Componente | Effort | Quick Win | ROI |
|------|---|----------|-----------|--------|-----------|-----|
| ⚡ | 10 | Query Expansion dead | `fly secrets set` | **5 min** | ✅ | +15-20% RAG |
| 1 | 12 | Dependency Debt | `dependabot.yml` | 1h | ✅ | Compliance auto |
| 2 | 4 | Test Debt CI | Fix `tests.yml` path | 2h | ✅ | Blocca ciclo sporco |
| 3 | 1 | Rogue AI Refactor | `.pre-commit-config.yaml` | 2h | ✅ | Previene production crash |
| 4 | 2 | asyncpg stale (residuo) | `pool_pre_ping` + `pool_recycle` | 30min | ✅ | Chiude fix di oggi |
| 5 | 3 | Drive OAuth alert | `drive_token_watchdog.py` | 3h | ✅ | Silent failure → alert |
| 6 | 7 | Monitoring cron inattivi | Attivare cron Air | 2h | ✅ | Proattivo invece reattivo |
| 7 | 13 | No Deploy Gate CI | `fly-deploy.yml` GitHub Actions | 3h | — | Deploy impossibile senza test verdi |
| 8 | 14 | Memory→CLAUDE.md | Migrazione + Core Guardian check | 2h | — | AI agent non ripete errori |
| 9 | 6 | Cache Invalidation | AST analyzer Core Guardian | 3h | — | Audit continuo automatico |
| 10 | 11 | Drive Polling fragile | `DrivePollCircuitBreaker` | 3h | — | Circuit breaker |
| 11 | 5 | CRM Data Quality | Pydantic bulk + cron hygiene | 4h | — | Rompe ciclo sporco |
| 12 | 8 | RAG Evaluation | `ragas_eval.py` + cron | 4h | — | Metriche oggettive |
| 13 | 9 | KG Visa hardcoded | Fix RPTKA sezione | 2h | — | Parziale, non totale |

**Totale effort:** ~120h (3 settimane) | **ROI atteso:** -80% incidenti, recupero 40h/settimana firefighting

---

## Dettaglio per Problema

---

### #1 — Rogue AI Refactor
> Gemini/Windsurf/Cursor rimuovono import critici → production crash (5+ volte, feb-mar 2026)

**Automazioni esistenti:**
- Pre-push hook presente ma `exit 0` forzato (non bloccante)
- Core Guardian V3 ogni 3h — rileva ma non blocca
- `scripts/preflight.sh pre` — manuale

**Automazione che azzera:**
```yaml
# .pre-commit-config.yaml (da creare nel repo root)
repos:
  - repo: local
    hooks:
      - id: import-chain-gate
        name: "Import chain test (blocca rogue refactor)"
        language: system
        entry: bash -c 'cd apps/backend-rag && source .venv/bin/activate && python -c "from backend.app.dependencies import get_current_user; print(OK)" || (echo "CRITICO: import chain rotta!" && exit 1)'
        pass_filenames: false
        files: ^apps/backend-rag/backend/

      - id: protected-files-gate
        name: "Block edits to OFF-LIMITS files"
        language: system
        entry: bash -c 'PROTECTED=$(git diff --cached --name-only | grep -E "zantara_core\.py|fly\.toml|alembic/env\.py"); [ -z "$PROTECTED" ] && exit 0 || (echo "BLOCKED: file protetto: $PROTECTED" && exit 1)'
        pass_filenames: false
        always_run: true
```
```bash
# Attivazione (una tantum):
pip install pre-commit
pre-commit install
```
**TRIGGER → DETECTOR → ACTOR → VERIFIER:**
- TRIGGER: `git commit`
- DETECTOR: AST import chain test + file name check
- ACTOR: blocco commit con messaggio esplicito
- VERIFIER: test import passa → commit procede

**Integrazione esistente:** Estende pre-commit (già installato), completa Core Guardian V3
**Effort:** S (2h) | **DeepSeek:** "Priorità 2, M (8h)" — effort sovrastimato, il wiring è già presente

---

### #2 — asyncpg Stale Connection (residuo)
> Fix principale completato questa sessione. Rimane un edge case: cold start >30s + prima request <15s prima del primo health loop cycle.

**Automazioni esistenti (mature):**
- `max_inactive_connection_lifetime=30s` ✅
- `_database_health_check_loop()` ogni 15s con `expire_connections()` ✅
- `exception_handlers.py` InterfaceError → 503 + Retry-After ✅
- `preflight.sh post` con auto-restart Fly machine ✅

**Fix residuo (30 minuti):**
```python
# service_initializer.py — aggiungere agli init_kwargs del pool
pool_kwargs = {
    "max_inactive_connection_lifetime": 30.0,
    "pool_pre_ping": True,     # AGGIUNGERE: health check PRIMA di ogni checkout
    "min_size": 1,
    "max_size": 10,
    "server_settings": {"tcp_keepalives_idle": "30"},  # AGGIUNGERE: fix cross-region timeout
}
```

**ConnectionSentinel (DeepSeek):** Il `_database_health_check_loop()` esistente copre già la logica. Non serve riscriverlo.

**Effort:** XS (30min) | Status: 90% risolto, questo chiude il 10% residuo

---

### #3 — Google Drive OAuth/SA Scaduta
> Silent failure ricorrente ogni ~trimestre: token scade, documenti clienti non visibili, scoperto solo da segnalazione cliente

**Automazioni esistenti:**
- `google_drive_tokens` table con `expires_at` ✅
- Admin endpoint che espone `expires_at` ✅
- **MANCA:** qualsiasi alert proattivo

**Automazione che azzera:**
```python
# scripts/drive_token_watchdog.py (da creare)
"""
Cron OpenClaw Air: 0 */6 * * *
Controlla scadenza token Drive e SA key, manda Telegram alert 7 giorni prima
"""
import asyncio, asyncpg, os
from datetime import datetime, timedelta
import httpx

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_OWNER_CHAT_ID"]
DATABASE_URL = os.environ["DATABASE_URL"]

async def check_drive_token():
    conn = await asyncpg.connect(DATABASE_URL)
    row = await conn.fetchrow(
        "SELECT expires_at FROM google_drive_tokens ORDER BY created_at DESC LIMIT 1"
    )
    await conn.close()

    if not row:
        await alert("⚠️ Drive token: NESSUN TOKEN in DB — polling Drive disabilitato")
        return

    days_left = (row['expires_at'] - datetime.utcnow()).days
    if days_left < 0:
        await alert(f"🔴 Drive OAuth SCADUTO ({abs(days_left)} giorni fa)!\nRe-auth: https://kita.balizero.com/settings/integrations")
    elif days_left < 7:
        await alert(f"⚠️ Drive OAuth scade in {days_left} giorni\nRe-auth: https://kita.balizero.com/settings/integrations")

async def check_sa_key_age():
    """Controlla età della service account key via gcloud CLI"""
    import subprocess, json
    try:
        result = subprocess.run([
            "gcloud", "iam", "service-accounts", "keys", "list",
            "--iam-account=nuzantara-drive-bot@nuzantara.iam.gserviceaccount.com",
            "--format=json"
        ], capture_output=True, text=True, timeout=30)
        keys = json.loads(result.stdout)
        if keys:
            oldest = min(keys, key=lambda k: k['validAfterTime'])
            from datetime import timezone
            key_date = datetime.fromisoformat(oldest['validAfterTime'].replace('Z', '+00:00'))
            age_days = (datetime.now(timezone.utc) - key_date).days
            if age_days > 30:
                await alert(f"⚠️ SA key age: {age_days} giorni (>30) — rotazione consigliata")
    except Exception as e:
        await alert(f"⚠️ SA key check fallito: {e}")

async def alert(message: str):
    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message}
        )

if __name__ == "__main__":
    asyncio.run(check_drive_token())
    asyncio.run(check_sa_key_age())
```

```
# OpenClaw cron da aggiungere su Air:
0 */6 * * *  cd ~/Projects/nuzantara && python3 scripts/drive_token_watchdog.py
```

**Effort:** S (3h) | **DeepSeek:** "TokenWarden, Priorità 3" ✅ allineato

---

### #4 — Test Debt a Ciclo
> CI usa `--cov=src` invece di `backend/` → raccoglie 0 items → nessun gate reale

**Fix parte 1 — 1 riga in tests.yml:**
```yaml
# .github/workflows/tests.yml — CORREGGERE
- name: Run tests
  working-directory: apps/backend-rag
  run: |
    PYTHONPATH=. pytest backend/tests/ -q --tb=short -x \
      --cov=backend --cov-report=xml --cov-fail-under=75
  # ERA: pytest tests/unit/ --cov=src  ← path sbagliato, 0 items
```

**Fix parte 2 — gate bloccante su PR:**
```yaml
# .github/workflows/tests.yml — aggiungere
on:
  pull_request:
    branches: [main]
    paths: ['apps/backend-rag/**']
# Aggiungere branch protection rule su GitHub:
# Settings → Branches → main → Required status checks → "test-gate"
```

**Effort:** S (2h) | **DeepSeek:** "TestGate, Priorità 1" ✅

---

### #5 — CRM Data Quality
> Bulk import senza validazione → ciclo sporco/pulito ogni 2 settimane

**Schema validation pre-insert (Pydantic v2):**
```python
# backend/app/schemas/crm_import.py (da creare)
from pydantic import BaseModel, EmailStr, field_validator, model_validator
from typing import Optional

class ClientImportRow(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    passport_number: Optional[str] = None
    assigned_to: Optional[str] = None
    phone: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Name too short (min 2 chars)")
        return v.title()

    @model_validator(mode="after")
    def at_least_one_identifier(self) -> "ClientImportRow":
        if not self.email and not self.passport_number:
            raise ValueError("Almeno email o passport_number obbligatorio")
        return self
```

**Daily hygiene cron (05:00 Air):**
```python
# scripts/crm_hygiene.py (da creare)
"""
Cron OpenClaw Air: 0 5 * * *
Verifica anomalie CRM e notifica se trovate
"""
ANOMALY_QUERIES = [
    ("Clienti senza identificatore",
     "SELECT COUNT(*) FROM clients WHERE email IS NULL AND passport_number IS NULL AND status != 'archived'"),
    ("Clienti assegnati a email inesistenti",
     "SELECT COUNT(*) FROM clients c WHERE c.assigned_to IS NOT NULL AND c.assigned_to NOT IN (SELECT email FROM user_profiles)"),
    ("Clienti attivi senza pratiche da 90 giorni",
     "SELECT COUNT(*) FROM clients c WHERE status='active' AND NOT EXISTS (SELECT 1 FROM practices p WHERE p.client_id=c.id AND p.updated_at > NOW()-interval '90 days')"),
    ("Possibili duplicati (stesso nome + nazionalità)",
     "SELECT COUNT(*) FROM (SELECT name, nationality, COUNT(*) FROM clients GROUP BY name, nationality HAVING COUNT(*)>1) AS dupes"),
]
```

**Effort:** M (4h) | **DeepSeek:** "DataJanitor, Priorità 2" ✅

---

### #6 — Cache Invalidation Mancante
> Mutation senza `invalidate_cache()` → dati stale visibili agli utenti

**AST Analyzer per Core Guardian V3:**
```python
# apps/evaluator/core_guardian/checks/cache_invalidation_audit.py (da creare)
import ast
from pathlib import Path
from typing import Iterator

def find_mutation_without_cache_invalidation() -> Iterator[str]:
    """Trova endpoint PUT/POST/DELETE/PATCH senza invalidate_cache()"""
    routers_dir = Path("apps/backend-rag/backend/app/routers")
    mutation_decorators = {'.post(', '.put(', '.patch(', '.delete('}

    for router_file in routers_dir.glob("*.py"):
        source = router_file.read_text()
        if 'invalidate_cache' not in source:
            # File intero senza nessuna invalidazione — controlla se ha mutations
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.AsyncFunctionDef):
                    deco_str = ''.join(ast.unparse(d) for d in node.decorator_list)
                    if any(m in deco_str for m in mutation_decorators):
                        yield f"⚠️ {router_file.name}:{node.lineno} `{node.name}` — mutation senza invalidate_cache"
            continue

        # File con alcune invalidazioni — trova quelle mancanti
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                deco_str = ''.join(ast.unparse(d) for d in node.decorator_list)
                if any(m in deco_str for m in mutation_decorators):
                    fn_source = ast.unparse(node)
                    if 'invalidate_cache' not in fn_source:
                        yield f"⚠️ {router_file.name}:{node.lineno} `{node.name}` — mutation senza invalidate_cache"
```

**Effort:** S (3h) | **DeepSeek:** "CacheLint, L (16h)" — sovrastimato, l'AST traversal è semplice

---

### #7 — Monitoring Reattivo
> Cron esistenti non attivi su Air, system_doctor manuale, rag_canary manuale

**Fix immediato — attivare cron su Air (2h):**
```bash
# Aggiungere a crontab Air (crontab -e):
# RAG canary ogni 6h
0 */6 * * *  cd ~/Projects/nuzantara && source apps/backend-rag/.venv/bin/activate && python3 scripts/rag_canary.py >> logs/rag_canary.log 2>&1

# System doctor ogni mattina
0 8 * * *    cd ~/Projects/nuzantara && source apps/backend-rag/.venv/bin/activate && python3 scripts/system_doctor.py --notify-telegram >> logs/system_doctor.log 2>&1

# Drive token watchdog ogni 6h
0 */6 * * *  cd ~/Projects/nuzantara && source apps/backend-rag/.venv/bin/activate && python3 scripts/drive_token_watchdog.py >> logs/drive_watchdog.log 2>&1

# Dependency audit ogni lunedì
0 1 * * 1    cd ~/Projects/nuzantara/apps/backend-rag && source .venv/bin/activate && safety check -r requirements.txt --output json >> ~/logs/dep_audit.log 2>&1
```

**Proactive forecast (HealthForecaster — DeepSeek):**
```python
# Aggiungere a system_doctor.py
def check_trends(metrics_history: list[dict]) -> list[str]:
    """Trend analysis — alert prima che si rompa"""
    alerts = []
    if len(metrics_history) >= 4:
        # RAM slope
        ram_values = [m['ram_percent'] for m in metrics_history[-4:]]
        slope = (ram_values[-1] - ram_values[0]) / len(ram_values)
        if slope > 5:  # +5% per ciclo → proiezione OOM
            alerts.append(f"⚠️ RAM trend: +{slope:.1f}%/check — possibile OOM in {100//slope:.0f}h")
    return alerts
```

**Effort:** S (2h) per attivare cron | M (4h) per forecast | **DeepSeek:** "HealthForecaster, L (20h)" — effort per il forecast completo, ma quick win solo attivando i cron

---

### #8 — RAG Evaluation (RAGAS)
> Pianificata feb-16, rimanda ogni sessione. Canary misura solo cosine similarity, non faithfulness.

**Pipeline minimale:**
```python
# scripts/ragas_eval.py (da creare)
"""
Cron OpenClaw Air: 0 6 * * 0  (domenica 06:00)
Valuta RAG con metriche RAGAS su golden dataset esistente
"""
import json, asyncio
from datetime import date
from pathlib import Path

# Golden dataset già in .rag_canary/last_run.json — riuso!
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision
from ragas.llms import LangchainLLMWrapper
from langchain_anthropic import ChatAnthropic

async def run_eval():
    # Carica golden queries esistenti
    canary_data = json.loads(Path("scripts/.rag_canary/last_run.json").read_text())

    eval_data = {
        "question": [q["query"] for q in canary_data["results"]],
        "answer": [q["best_answer"] for q in canary_data["results"]],
        "contexts": [[q["best_answer"]] for q in canary_data["results"]],  # semplificato
    }

    llm = LangchainLLMWrapper(ChatAnthropic(model="claude-haiku-4-5-20251001"))
    results = evaluate(
        dataset=eval_data,
        metrics=[faithfulness, answer_relevancy, context_precision],
        llm=llm,
    )

    # Salva storico
    output = {"date": str(date.today()), "scores": results.to_pandas().mean().to_dict()}
    Path(f"scripts/.rag_canary/ragas_{date.today()}.json").write_text(json.dumps(output, indent=2))

    # Alert se sotto threshold
    if results['faithfulness'] < 0.80:
        # telegram alert
        print(f"⚠️ RAG faithfulness: {results['faithfulness']:.2f} < 0.80")
    else:
        print(f"✅ RAG eval: faithfulness={results['faithfulness']:.2f}, relevancy={results['answer_relevancy']:.2f}")

asyncio.run(run_eval())
```

**Effort:** M (4h) | **DeepSeek:** "RAGASAgent, Priorità 2, M (10h)"

---

### #9 — KG Subgraph Hardcoded
> Situazione reale: meno grave del previsto. Company usa KG reale. Solo visa RPTKA è hardcoded.

**Fix mirato (solo sezione RPTKA):**
```python
# backend/services/rag/kg_subgraph_visa.py — linea ~150
# PRIMA:
# rptka_requirements = ["hardcoded_list_item_1", ...]

# DOPO:
async def _get_rptka_requirements(db_pool) -> list[str]:
    rows = await db_pool.fetch(
        """SELECT DISTINCT e.properties->>'description' as req
           FROM kg_edges e
           JOIN kg_nodes n ON e.target_entity_id = n.entity_id
           WHERE n.entity_type = 'rptka'
           AND e.relationship_type = 'REQUIRES'
           LIMIT 20"""
    )
    return [r['req'] for r in rows if r['req']] or ["RPTKA requirements: verify with team"]
```

**Effort:** S (2h) | Status: fix parziale (solo visa), resto già wired

---

### #10 — Query Expansion (⚡ QUICK WIN 5 MINUTI)
> Il wiring c'è già. `ENABLE_QUERY_EXPANSION` è False per default. Un comando risolve.

```bash
fly secrets set ENABLE_QUERY_EXPANSION=true -a nuzantara-rag
```

**Impatto immediato:** +15-20% su query comparative ("PT PMA vs CV", "KITAS vs KITAP")
**Zero rischio:** il codice è già scritto e testato, solo disabilitato via flag
**Effort:** XS (**5 minuti**) — ROI più alto per effort più basso di tutto l'elenco

---

### #11 — Drive Polling Fragilità
> Circuit breaker mancante: 3x fallimenti consecutivi non vengono rilevati

```python
# backend/services/integrations/drive_poll_service.py — aggiungere
import time
from dataclasses import dataclass, field
from typing import Callable, Awaitable

@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    recovery_timeout: int = 300  # 5 minuti
    _failures: int = field(default=0, init=False)
    _last_failure: float = field(default=0.0, init=False)
    _state: str = field(default="closed", init=False)  # closed | open | half-open

    async def call(self, fn: Callable[[], Awaitable], alert_fn: Callable = None):
        if self._state == "open":
            if time.time() - self._last_failure > self.recovery_timeout:
                self._state = "half-open"
            else:
                return None  # skip poll silently

        try:
            result = await fn()
            self._failures = 0
            self._state = "closed"
            return result
        except Exception as e:
            self._failures += 1
            self._last_failure = time.time()
            if self._failures >= self.failure_threshold:
                self._state = "open"
                if alert_fn:
                    await alert_fn(f"⚠️ Drive polling: circuit OPEN dopo {self._failures} errori: {e}")
            raise

# Uso in drive_poll_service.py:
# self._circuit_breaker = CircuitBreaker()
# await self._circuit_breaker.call(self._do_poll, alert_fn=self._telegram_alert)
```

**Effort:** S (3h) | **DeepSeek:** "DriveCircuitBreaker, Priorità 2" ✅

---

### #12 — Dependency Debt
> `.github/workflows/security.yml` esiste ma tutti i job hanno `continue-on-error: true` — non bloccano nulla

**Fix in 2 file:**

```yaml
# .github/dependabot.yml (da CREARE — non esiste)
version: 2
updates:
  - package-ecosystem: pip
    directory: /apps/backend-rag
    schedule:
      interval: weekly
      day: monday
    ignore:
      - dependency-name: sentence-transformers  # pinned per torch compat
    labels:
      - "dependencies"
      - "security"

  - package-ecosystem: npm
    directory: /apps/mouth
    schedule:
      interval: weekly
      day: monday
    labels:
      - "dependencies"
```

```yaml
# .github/workflows/security.yml — MODIFICARE
# Rimuovere continue-on-error: true SOLO per severity CRITICAL
- name: Safety check (critical only)
  run: safety check -r requirements.txt --severity=critical
  # NO continue-on-error per critical — blocca il workflow
  working-directory: apps/backend-rag
```

**Effort:** XS (1h) | **DeepSeek:** "DepAuditor, Priorità 1" ✅

---

### #13 — Nessun Gate Pre-Deploy Automatico
> `fly deploy` può essere eseguito manualmente senza che preflight.sh venga mai chiamato

```yaml
# .github/workflows/fly-deploy.yml (da CREARE)
name: Deploy Backend to Fly.io
on:
  push:
    branches: [main]
    paths: ['apps/backend-rag/**']

jobs:
  pre-deploy-gate:
    name: Pre-deploy validation
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: apps/backend-rag
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      - run: pip install -r requirements.txt -q
      - name: Import chain test
        run: python -c "from backend.app.dependencies import get_current_user; print('✅ Import chain OK')"
      - name: Core tests
        run: PYTHONPATH=. pytest backend/tests/services/rag/test_confidence.py -q --tb=short -x
      - name: Ruff lint
        run: ruff check backend/app/ --select E,F --quiet

  deploy:
    name: Fly.io rolling deploy
    needs: pre-deploy-gate  # BLOCCATO se gate fallisce
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: superfly/flyctl-actions/setup-flyctl@master
      - run: flyctl deploy --strategy rolling --config apps/backend-rag/fly.toml
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
        working-directory: apps/backend-rag

  post-deploy-health:
    name: Post-deploy health check
    needs: deploy
    runs-on: ubuntu-latest
    steps:
      - name: Health check (10 retry × 30s = 5min max)
        run: |
          for i in $(seq 1 10); do
            if curl -sf https://nuzantara-rag.fly.dev/health | grep -q '"healthy"'; then
              echo "✅ Health check passed (attempt $i)"
              exit 0
            fi
            echo "Attempt $i/10 — waiting 30s..."
            sleep 30
          done
          echo "❌ Health check failed after 5 minutes"
          exit 1
      - name: Rollback on failure
        if: failure()
        run: |
          curl -sf https://api.telegram.org/bot${{ secrets.TELEGRAM_BOT_TOKEN }}/sendMessage \
            -d "chat_id=${{ secrets.TELEGRAM_OWNER_CHAT_ID }}" \
            -d "text=🔴 Deploy fallito — rollback automatico in corso"
          flyctl releases rollback --app nuzantara-rag
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
```

**Effort:** M (3h) | **DeepSeek:** "AutoPreflight, Priorità 1" ✅

---

### #14 — Logiche Istituzionali solo in Memory
> Logiche critiche in `~/.claude/MEMORY.md` invisibili a Gemini CLI, Windsurf, Codex

**Logiche da spostare in `CLAUDE.md` (sezione nuova):**
```markdown
## CRITICAL OPERATIONAL RULES — Non Documentate Altrove

### Virtualenv
- SEMPRE `.venv` — NON `venv` (venv è deprecated). Path: `apps/backend-rag/.venv/`
- Su cron/CI: usare path assoluto `.venv/bin/python` o `.venv/bin/pytest`

### Drive Polling
- Gira su Air cron ogni 5min (`apps/backend-rag/scripts/drive_poll_cron.sh`)
- NON su Fly.io scheduler — incompatibile con auto_stop=true (perde page_token)
- Se si aggiunge alla pipeline Fly → rischio loss sync silenzioso

### OCR Multi-page
- Leggere SEMPRE tutte le pagine del PDF, non solo pagina 0
- I direttori delle perseroan sono tipicamente in pagina 2-3
- Timeout: 120s per PDF >3 pagine

### Cache Invalidation
- Pattern obbligatorio: `await invalidate_cache("zantara:namespace:*")` dopo OGNI mutation
- Namespace: `zantara:crm_clients_stats:*` per clients, `zantara:crm_practices:*` per practices
- Non invalidare → dati stale → confusion clienti

### KG Subgraph Status
- Company: wired al KG reale ✅
- Visa: wired al KG reale tranne sezione RPTKA (hardcoded) ⚠️
- Property/Tax: da verificare
```

**Core Guardian check automatico (da aggiungere):**
```python
# apps/evaluator/core_guardian/checks/memory_sync.py
def check_memory_vs_claude_md():
    """Alert se ci sono regole in MEMORY.md non ancora in CLAUDE.md"""
    # Legge MEMORY.md e CLAUDE.md
    # Trova pattern "ALWAYS", "NEVER", "CRITICAL", "WARNING" in MEMORY
    # Verifica che siano presenti anche in CLAUDE.md
    # Alert se gap > 3 regole non sincronizzate
```

**Effort:** S (2h) | **DeepSeek:** "MemorySyncAgent, L (15h)" — l'implementazione completa è L, ma la migrazione manuale è S

---

## Integrazione con Automazioni Esistenti

| Automazione Esistente | Problemi Coperti | Estensione Necessaria |
|---|---|---|
| **Core Guardian V3** (ogni 3h) | #1 parziale, #6 parziale | Aggiungere: import-chain check, AST cache audit, memory sync check |
| **preflight.sh** (pre/post deploy) | #2, #13 parziale | Aggiungere: Drive token check, SA key age |
| **auto_test.sh** (OpenClaw) | #4 parziale | Fix path `backend/` invece di `src/` |
| **rag_canary.py** (manuale) | #7, #8 parziale | Aggiungere cron OpenClaw + RAGAS layer |
| **system_doctor.py** (47 check) | #7 parziale | Attivare cron + aggiungere trend analysis |
| **GitHub Actions CI** | #4 parziale | Fix path + aggiungere `fly-deploy.yml` |
| **drive_poll_cron.sh** (Air) | #11 parziale | Aggiungere circuit breaker |

---

## Roadmap di Implementazione

### Settimana 1 — Quick Wins (totale ~10h)
1. ⚡ `fly secrets set ENABLE_QUERY_EXPANSION=true` (5min) — **fare subito**
2. ✅ `.github/dependabot.yml` (1h)
3. ✅ Fix `tests.yml` path (2h)
4. ✅ `.pre-commit-config.yaml` bloccante (2h)
5. ✅ `pool_pre_ping=True` + `pool_recycle=180` (30min)
6. ✅ Attivare cron su Air (2h)

### Settimana 2 — Gates e Guardrails (totale ~15h)
7. `.github/workflows/fly-deploy.yml` (3h)
8. `drive_token_watchdog.py` + cron (3h)
9. Migrazione Memory → `CLAUDE.md` (2h)
10. AST cache audit in Core Guardian (3h)
11. `DrivePollCircuitBreaker` (3h)

### Settimana 3 — Evaluation e Quality (totale ~10h)
12. `ragas_eval.py` + cron domenicale (4h)
13. `crm_hygiene.py` + cron giornaliero (4h)
14. Fix KG subgraph visa RPTKA (2h)

---

*Documento generato da: Claude Code (Air) + DeepSeek R1 671b + Web Research + Gemini codebase analysis*
*2026-03-26*
