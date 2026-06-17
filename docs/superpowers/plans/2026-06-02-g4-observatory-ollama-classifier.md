# G4 — Cell Observatory Collector: Classifier → Ollama Local Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Far ripartire il `cell-observatory-collector` (morto dal ~2 mag) sostituendo il classifier MiniMax/OpenRouter (LLM a pagamento, NON sanzionato — viola HARD RULE costi) con Ollama `qwen3.5:9b` locale ($0), rendendo la key LLM opzionale e aggiungendo il `EVENTBUS_DATABASE_URL` mancante al plist del collector.

**Architecture:** Il `Collector` consuma il classifier solo via interfaccia `async classify(event: PulseEventV1) -> ClassificationResult` + `async aclose()`. Aggiungiamo un `OllamaClassifier` con la STESSA interfaccia (Liskov-substitutable per `MinimaxClassifier`), un selettore di backend in `Config`, e il wiring in `run_collector`. Il resto del collector (storage SQLite, replay outbox, listener PG, queue workers) resta INTATTO. Il plist riceve `EVENTBUS_DATABASE_URL` (proxy flyctl `:15432`, lo stesso DSN che usano gli emitter in `seo-cell-daily.sh:50`) + `OBSERVATORY_CLASSIFIER=ollama`.

**Tech Stack:** Python 3.11 (pyenv 3.11.11), httpx async, pydantic v2, asyncpg, structlog, Ollama HTTP `/api/chat` (`localhost:11434`), launchd plist.

---

## Contesto diagnostico (Phase 1 systematic-debugging — già eseguita, 2026-06-02)

Evidenza empirica raccolta PRIMA di questo piano (NON ri-assumere, è verificata su disco):

| Layer                             | Stato reale                                                                                                                  | Evidenza                        |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ------------------------------- |
| Emitter (`CELL_OBSERVATORY_EMIT`) | `true` su 3 plist (seo-cell.daily, seo-cell.28d-check, matagaruda.sentinel.hourly)                                           | `plutil -extract`               |
| Emitter DSN                       | `postgresql://…@localhost:15432/nuzantara_rag` (proxy flyctl → Fly)                                                          | `seo-cell-daily.sh:50`          |
| `com.cell.organism`               | VIVO (PID 9380)                                                                                                              | `launchctl list`                |
| flyctl proxy `:15432`             | APERTO                                                                                                                       | `nc -z localhost 15432`         |
| **Collector**                     | **MORTO** — crash all'avvio                                                                                                  | `collector.err.log`             |
| Collector crash #1                | `RuntimeError: OPENROUTER_API_KEY or MINIMAXM2_API_KEY or MINIMAX_API_KEY required`                                          | `config.py:33`                  |
| Collector crash #2 (latente)      | `EVENTBUS_DATABASE_URL` NON nel suo plist (solo PATH/HOME/MACHINE_ROLE) → `config.py:39` fallirebbe dopo aver risolto la key | `plutil -convert json`          |
| qwen3.5:9b                        | presente (6.6 GB) + `/api/chat format:json think:false` → JSON valido                                                        | `ollama list` + curl smoke PASS |

**CORREZIONE alla MEMORY**: `discovery_cell_pulse_observed_gate_off_2026_05_22` diceva "daemon dead + EMIT missing". È STALE/SBAGLIATA: gli emitter girano, l'organism è vivo, è il COLLECTOR che muore. Salvata correzione in memory (importance 8) il 2026-06-02.

**TRAP costi confermata sul codice**: `classifier.py:65` `MODEL = "minimax/minimax-m2.5"` (NON `:free`), prezzi `$0.15/$1.15` per M token. Il collector girava su LLM a pagamento, non sul "free tier" che il commento dichiara.

**Check di esecuzione (NON bloccante per il piano)**: se `events_outbox` su Fly contiene righe `cell_pulse_observed` con `consumed_at IS NULL` lo verificheremo DOPO aver acceso il collector (sarà il replay a dirlo nei log). Auth al DB Fly da fuori richiede la password reale di `backend_rag_v2` dai secrets — non serve per scrivere il fix.

---

## File Structure

| File                                                              | Responsabilità                                                                                                                      | Azione                                            |
| ----------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| `apps/cell-observatory-collector/cell_observatory/classifier.py`  | Aggiunge `OllamaClassifier` accanto a `MinimaxClassifier`; entrambi espongono `classify`/`aclose`                                   | Modify                                            |
| `apps/cell-observatory-collector/cell_observatory/config.py`      | `minimax_api_key` diventa `Optional`; nuovo campo `classifier_backend` (`ollama`\|`minimax`); key richiesta SOLO se backend=minimax | Modify                                            |
| `apps/cell-observatory-collector/cell_observatory/collector.py`   | `run_collector` sceglie il classifier in base a `cfg.classifier_backend`; type hint allargato                                       | Modify                                            |
| `apps/cell-observatory-collector/tests/test_ollama_classifier.py` | Test del nuovo classifier (parse JSON, label mapping, error path)                                                                   | Create                                            |
| `apps/cell-observatory-collector/tests/test_config_backend.py`    | Test del selettore backend + key opzionale                                                                                          | Create                                            |
| `~/Library/LaunchAgents/com.nuzantara.cell-observatory.plist`     | Aggiunge `EVENTBUS_DATABASE_URL` + `OBSERVATORY_CLASSIFIER=ollama` + `OLLAMA_HOST`                                                  | Modify (in esecuzione, fuori dal git — è in HOME) |

**Interfaccia condivisa (contratto, NON cambiarla):**

```python
class _ClassifierProtocol(Protocol):
    async def classify(self, event: PulseEventV1) -> ClassificationResult: ...
    async def aclose(self) -> None: ...
```

`ClassificationResult` è già definito in `models.py` (campi: `outbox_id, label, confidence, reasoning, label_diff, model, model_version, cost_usd, latency_ms, error`). NON modificare `models.py`.

---

## Task 1: Verifica baseline test esistenti (no regressioni di partenza)

**Files:**

- Test: `apps/cell-observatory-collector/tests/` (esistenti)

- [ ] **Step 1: Trovare i test esistenti del collector**

Run:

```bash
cd ~/Desktop/nuzantara/.worktrees/organism-g4-observatory-ollama/apps/cell-observatory-collector
ls tests/ 2>/dev/null
```

Expected: lista dei test file esistenti (potrebbe includere `test_classifier.py`, `test_collector.py`, `test_storage.py`).

- [ ] **Step 2: Attivare venv del collector e far girare i test esistenti**

Run:

```bash
cd ~/Desktop/nuzantara/.worktrees/organism-g4-observatory-ollama/apps/cell-observatory-collector
source .venv/bin/activate 2>/dev/null || python3.11 -m venv .venv && source .venv/bin/activate
pip install -q -e . 2>&1 | tail -1
python -m pytest tests/ -q 2>&1 | tail -15
```

Expected: baseline verde (o lista chiara dei fallimenti pre-esistenti). Annota il numero di test passati — sarà il floor da non abbassare.

- [ ] **Step 3: Commit (nessuna modifica codice — solo conferma baseline nel messaggio)**

Nessun file cambiato; salta il commit se git è pulito. Se il venv ha generato artefatti, NON committarli (sono in `.gitignore`).

---

## Task 2: OllamaClassifier (TDD)

**Files:**

- Test: `apps/cell-observatory-collector/tests/test_ollama_classifier.py` (create)
- Modify: `apps/cell-observatory-collector/cell_observatory/classifier.py`

- [ ] **Step 1: Scrivere il test che fallisce**

Create `apps/cell-observatory-collector/tests/test_ollama_classifier.py`:

```python
from __future__ import annotations
import json
import pytest

from cell_observatory.classifier import OllamaClassifier
from cell_observatory.models import ClassificationLabel, PulseEventV1


def _event(**over) -> PulseEventV1:
    base = dict(
        outbox_id=1,
        cell_id="seo_cell",
        cell_kind="seo",
        pulse_id="p1",
        pulse_timestamp=1717000000000,
        phase="observe",
        sensors=[{"name": "latency_ms", "value": 120}],
        pulse_result={"classifier_self": "green", "trend_label": "stable"},
        homeostatic_state={"energy_pct": 80, "load_factor": 0.3},
    )
    base.update(over)
    return PulseEventV1.model_validate(base)


class _FakeResponse:
    def __init__(self, payload: dict): self._payload = payload
    def raise_for_status(self): pass
    def json(self): return self._payload


class _FakeAsyncClient:
    def __init__(self, content: str): self._content = content; self.calls = []
    async def post(self, url, **kw):
        self.calls.append((url, kw))
        return _FakeResponse({"message": {"content": self._content},
                              "prompt_eval_count": 100, "eval_count": 20})
    async def aclose(self): pass


@pytest.mark.asyncio
async def test_classify_normal_label_maps_and_costs_zero():
    fake = _FakeAsyncClient(json.dumps({"label": "normal", "confidence": 0.92,
                                        "reasoning": "sensors within band"}))
    clf = OllamaClassifier(client=fake)
    res = await clf.classify(_event(pulse_result={"classifier_self": "green"}))
    assert res.label == ClassificationLabel.NORMAL
    assert res.confidence == pytest.approx(0.92)
    assert res.cost_usd == 0.0          # Ollama local = zero cost (HARD RULE)
    assert res.label_diff == "agree"    # self=green + normal => agree
    assert res.error is None
    assert "qwen" in res.model.lower()


@pytest.mark.asyncio
async def test_classify_uses_chat_endpoint_with_json_format_and_think_false():
    fake = _FakeAsyncClient(json.dumps({"label": "anomaly", "confidence": 0.5, "reasoning": "x"}))
    clf = OllamaClassifier(client=fake)
    await clf.classify(_event())
    url, kw = fake.calls[0]
    assert url.endswith("/api/chat")
    body = kw["json"]
    assert body["format"] == "json"
    assert body["think"] is False        # CLAUDE.md §9 invariant for Qwen 3.5
    assert body["stream"] is False


@pytest.mark.asyncio
async def test_classify_invalid_json_returns_uncertain_error_row():
    fake = _FakeAsyncClient("not json at all")
    clf = OllamaClassifier(client=fake)
    res = await clf.classify(_event())
    assert res.label == ClassificationLabel.UNCERTAIN
    assert res.confidence == 0.0
    assert res.error is not None
    assert res.cost_usd == 0.0
```

- [ ] **Step 2: Run test per verificare che fallisce**

Run:

```bash
cd ~/Desktop/nuzantara/.worktrees/organism-g4-observatory-ollama/apps/cell-observatory-collector
source .venv/bin/activate
python -m pytest tests/test_ollama_classifier.py -v 2>&1 | tail -20
```

Expected: FAIL — `ImportError: cannot import name 'OllamaClassifier'`.

- [ ] **Step 3: Implementare OllamaClassifier**

Append a `apps/cell-observatory-collector/cell_observatory/classifier.py` (DOPO la classe `MinimaxClassifier`, riusa `_SYSTEM_PROMPT`, `_render_user_prompt`, `_PROMPT_VERSION`, `CircuitOpenError` già definiti in cima al file):

```python
class OllamaClassifier:
    """Local Ollama classifier (qwen3.5:9b) — zero-cost replacement for MiniMax.

    Sanctioned arsenal Tier 4 (CLAUDE.md cost HARD RULE): runs on the local
    Ollama daemon, never a paid per-token endpoint. Same public interface as
    MinimaxClassifier (classify / aclose) so Collector is agnostic.
    """
    DEFAULT_HOST = "http://localhost:11434"
    MODEL = "qwen3.5:9b"

    def __init__(self, host: str | None = None, client: "httpx.AsyncClient | None" = None,
                 circuit_threshold: int = 5, circuit_recovery_s: float = 60.0):
        self._host = (host or self.DEFAULT_HOST).rstrip("/")
        # 60s timeout: local 9B JSON gen is slower than a cloud call (~5-20s).
        self._client = client or httpx.AsyncClient(timeout=60.0)
        self._consecutive_failures = 0
        self._circuit_threshold = circuit_threshold
        self._circuit_open_until: float = 0.0
        self._circuit_recovery_s = circuit_recovery_s

    async def aclose(self) -> None:
        await self._client.aclose()

    def _check_circuit(self) -> None:
        if time.monotonic() < self._circuit_open_until:
            raise CircuitOpenError("Ollama circuit open")

    def _record_success(self) -> None:
        self._consecutive_failures = 0

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._circuit_threshold:
            self._circuit_open_until = time.monotonic() + self._circuit_recovery_s

    async def classify(self, event: PulseEventV1) -> ClassificationResult:
        self._check_circuit()
        start = time.monotonic()
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _render_user_prompt(event)},
        ]
        cell_self = event.pulse_result.get("classifier_self", "unknown")

        try:
            resp = await self._client.post(
                f"{self._host}/api/chat",
                json={
                    "model": self.MODEL,
                    "messages": messages,
                    "format": "json",
                    "stream": False,
                    "think": False,  # CLAUDE.md §9: Qwen 3.5 strips reasoning
                    "options": {"temperature": 0.1},
                },
            )
            resp.raise_for_status()
            content = resp.json().get("message", {}).get("content", "") or ""
        except Exception as exc:
            self._record_failure()
            latency_ms = int((time.monotonic() - start) * 1000)
            return self._error_result(event.outbox_id, str(exc), latency_ms)
        self._record_success()
        latency_ms = int((time.monotonic() - start) * 1000)

        try:
            parsed = ClassificationOutput.model_validate_json(content)
        except (ValidationError, ValueError) as exc:
            return self._error_result(event.outbox_id, f"parse: {exc}", latency_ms)

        label_diff = "agree" if (
            (cell_self == "green" and parsed.label == ClassificationLabel.NORMAL)
            or (cell_self in ("yellow", "red") and parsed.label != ClassificationLabel.NORMAL)
        ) else "disagree"

        return ClassificationResult(
            outbox_id=event.outbox_id,
            label=parsed.label,
            confidence=parsed.confidence,
            reasoning=parsed.reasoning[:500],
            label_diff=label_diff,
            model=f"{self.MODEL}-{_PROMPT_VERSION}",
            model_version=self.MODEL,
            cost_usd=0.0,            # local = zero cost
            latency_ms=latency_ms,
            error=None,
        )

    @staticmethod
    def _error_result(outbox_id: int, err: str, latency_ms: int) -> ClassificationResult:
        return ClassificationResult(
            outbox_id=outbox_id,
            label=ClassificationLabel.UNCERTAIN,
            confidence=0.0,
            reasoning="",
            label_diff="agree",
            model=f"{OllamaClassifier.MODEL}-{_PROMPT_VERSION}",
            model_version=OllamaClassifier.MODEL,
            cost_usd=0.0,
            latency_ms=latency_ms,
            error=err[:500],
        )
```

Aggiungi in cima al file (se non già importato): `from cell_observatory.models import ClassificationLabel, ClassificationOutput, ClassificationResult, PulseEventV1` — verifica la riga import esistente (riga 7-9) e aggiungi solo i nomi mancanti (`ClassificationOutput`, `ClassificationLabel` sono già lì).

- [ ] **Step 4: Run test per verificare che passano**

Run:

```bash
cd ~/Desktop/nuzantara/.worktrees/organism-g4-observatory-ollama/apps/cell-observatory-collector
source .venv/bin/activate
python -m pytest tests/test_ollama_classifier.py -v 2>&1 | tail -15
```

Expected: PASS 3/3.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/nuzantara/.worktrees/organism-g4-observatory-ollama
git add apps/cell-observatory-collector/cell_observatory/classifier.py apps/cell-observatory-collector/tests/test_ollama_classifier.py
git commit -m "$(cat <<'EOF'
feat(observatory): add OllamaClassifier (local qwen3.5:9b, zero-cost)

Same classify/aclose interface as MinimaxClassifier so Collector stays
agnostic. Uses /api/chat with format:json + think:false (CLAUDE.md §9).
cost_usd hardcoded 0.0 — local arsenal Tier 4, no paid endpoint.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Config — backend selector + key opzionale (TDD)

**Files:**

- Test: `apps/cell-observatory-collector/tests/test_config_backend.py` (create)
- Modify: `apps/cell-observatory-collector/cell_observatory/config.py`

- [ ] **Step 1: Scrivere il test che fallisce**

Create `apps/cell-observatory-collector/tests/test_config_backend.py`:

```python
from __future__ import annotations
import pytest
from cell_observatory.config import Config


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("OPENROUTER_API_KEY", "MINIMAXM2_API_KEY", "MINIMAX_API_KEY",
              "OBSERVATORY_CLASSIFIER", "EVENTBUS_DATABASE_URL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("EVENTBUS_DATABASE_URL", "postgresql://x@localhost:15432/db")


def test_ollama_backend_needs_no_llm_key(monkeypatch):
    monkeypatch.setenv("OBSERVATORY_CLASSIFIER", "ollama")
    cfg = Config.from_env()
    assert cfg.classifier_backend == "ollama"
    assert cfg.minimax_api_key is None      # no key required


def test_default_backend_is_ollama(monkeypatch):
    # No OBSERVATORY_CLASSIFIER set, no key set -> must NOT raise, default ollama
    cfg = Config.from_env()
    assert cfg.classifier_backend == "ollama"


def test_minimax_backend_still_requires_key(monkeypatch):
    monkeypatch.setenv("OBSERVATORY_CLASSIFIER", "minimax")
    with pytest.raises(RuntimeError, match="API_KEY"):
        Config.from_env()


def test_minimax_backend_with_key_ok(monkeypatch):
    monkeypatch.setenv("OBSERVATORY_CLASSIFIER", "minimax")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    cfg = Config.from_env()
    assert cfg.classifier_backend == "minimax"
    assert cfg.minimax_api_key == "sk-test"
```

- [ ] **Step 2: Run test per verificare che fallisce**

Run:

```bash
cd ~/Desktop/nuzantara/.worktrees/organism-g4-observatory-ollama/apps/cell-observatory-collector
source .venv/bin/activate
python -m pytest tests/test_config_backend.py -v 2>&1 | tail -20
```

Expected: FAIL — `test_default_backend_is_ollama` raises `RuntimeError` (key required), `classifier_backend` AttributeError.

- [ ] **Step 3: Modificare config.py**

In `apps/cell-observatory-collector/cell_observatory/config.py`:

(a) Cambia il dataclass field type + aggiungi il nuovo campo (dopo `minimax_api_key: str`):

```python
    minimax_api_key: str | None
    classifier_backend: str  # "ollama" | "minimax"
```

(b) Sostituisci il blocco `from_env` (righe ~20-34, il try/except sulla key) con:

```python
        # Backend selector (default ollama — local, zero-cost, sanctioned).
        # Only the "minimax" backend needs a paid LLM key; "ollama" needs none.
        classifier_backend = os.environ.get("OBSERVATORY_CLASSIFIER", "ollama").lower()

        minimax_api_key: str | None = (
            os.environ.get("OPENROUTER_API_KEY")
            or os.environ.get("MINIMAXM2_API_KEY")
            or os.environ.get("MINIMAX_API_KEY")
        )
        if classifier_backend == "minimax" and not minimax_api_key:
            raise RuntimeError(
                "OBSERVATORY_CLASSIFIER=minimax requires OPENROUTER_API_KEY "
                "or MINIMAXM2_API_KEY or MINIMAX_API_KEY"
            )
```

(c) Aggiungi al `return cls(...)` il nuovo campo:

```python
            classifier_backend=classifier_backend,
```

(lascia `minimax_api_key=minimax_api_key,` invariato).

- [ ] **Step 4: Run test per verificare che passano**

Run:

```bash
cd ~/Desktop/nuzantara/.worktrees/organism-g4-observatory-ollama/apps/cell-observatory-collector
source .venv/bin/activate
python -m pytest tests/test_config_backend.py -v 2>&1 | tail -15
```

Expected: PASS 4/4.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/nuzantara/.worktrees/organism-g4-observatory-ollama
git add apps/cell-observatory-collector/cell_observatory/config.py apps/cell-observatory-collector/tests/test_config_backend.py
git commit -m "$(cat <<'EOF'
feat(observatory): config backend selector, LLM key now optional

OBSERVATORY_CLASSIFIER=ollama (default) needs no key; only =minimax
still requires a paid LLM key. Fixes the RuntimeError that killed the
collector at startup (config.py:33) without forcing a banned paid key.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Wiring run_collector (TDD-lite)

**Files:**

- Modify: `apps/cell-observatory-collector/cell_observatory/collector.py:144-159`

- [ ] **Step 1: Modificare run_collector + type hint del Collector**

In `collector.py`:

(a) Import (riga 9): allarga

```python
from cell_observatory.classifier import CircuitOpenError, MinimaxClassifier, OllamaClassifier
```

(b) Type hint del `Collector.__init__` (riga 23): da `classifier: MinimaxClassifier` a

```python
        classifier: "MinimaxClassifier | OllamaClassifier",
```

(c) `run_collector` (righe 144-159): sostituisci la riga di istanza del classifier

```python
    classifier = MinimaxClassifier(api_key=cfg.minimax_api_key)
```

con

```python
    if cfg.classifier_backend == "ollama":
        classifier = OllamaClassifier()
    else:
        classifier = MinimaxClassifier(api_key=cfg.minimax_api_key)
```

- [ ] **Step 2: Verificare che il modulo importa + i test esistenti non regrediscono**

Run:

```bash
cd ~/Desktop/nuzantara/.worktrees/organism-g4-observatory-ollama/apps/cell-observatory-collector
source .venv/bin/activate
python -c "from cell_observatory.collector import run_collector; print('import OK')"
python -m pytest tests/ -q 2>&1 | tail -15
```

Expected: `import OK` + tutti i test passano (≥ floor di Task 1 + 7 nuovi).

- [ ] **Step 3: Smoke end-to-end del Config.from_env con env ollama (no key)**

Run:

```bash
cd ~/Desktop/nuzantara/.worktrees/organism-g4-observatory-ollama/apps/cell-observatory-collector
source .venv/bin/activate
EVENTBUS_DATABASE_URL="postgresql://x@localhost:15432/db" OBSERVATORY_CLASSIFIER=ollama \
  python -c "from cell_observatory.config import Config; c=Config.from_env(); print('backend:', c.classifier_backend, '| key:', c.minimax_api_key)"
```

Expected: `backend: ollama | key: None` (NESSUN RuntimeError — il bug di startup è chiuso).

- [ ] **Step 4: Commit**

```bash
cd ~/Desktop/nuzantara/.worktrees/organism-g4-observatory-ollama
git add apps/cell-observatory-collector/cell_observatory/collector.py
git commit -m "$(cat <<'EOF'
feat(observatory): wire run_collector to pick classifier by backend

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Push branch + PR (L2 Autonomous Ops)

- [ ] **Step 1: Push**

```bash
cd ~/Desktop/nuzantara/.worktrees/organism-g4-observatory-ollama
git push -u origin "$(git branch --show-current)"
```

- [ ] **Step 2: PR**

```bash
gh pr create --title "feat(observatory): collector classifier -> Ollama local (resuscita G4)" \
  --body "$(cat <<'EOF'
## Cosa
Far ripartire il cell-observatory-collector morto dal ~2 mag. Root cause: crash a `config.py:33` perché esigeva una key OpenRouter/MiniMax (LLM a pagamento, NON sanzionata — viola HARD RULE costi CLAUDE.md §5).

## Fix
- `OllamaClassifier` locale (qwen3.5:9b, $0) con stessa interfaccia di `MinimaxClassifier`
- `OBSERVATORY_CLASSIFIER=ollama` (default) → nessuna key richiesta
- `=minimax` resta disponibile ma richiede key (path a pagamento esplicito)

## Test
- `test_ollama_classifier.py` 3/3 · `test_config_backend.py` 4/4 · suite esistente verde

## Plan
`docs/superpowers/plans/2026-06-02-g4-observatory-ollama-classifier.md`

## Pending (esecuzione operatore, fuori dal git)
- Plist `com.nuzantara.cell-observatory.plist`: aggiungere `EVENTBUS_DATABASE_URL` (proxy :15432) + `OBSERVATORY_CLASSIFIER=ollama` + `OLLAMA_HOST` — vedi Task 6
- Verificare che `events_outbox` su Fly abbia righe cell_pulse da consumare (replay log)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Task 6: Plist collector — wiring env (ESECUZIONE OPERATORE, fuori dal git)

> ⚠️ Il plist vive in `~/Library/LaunchAgents/`, NON nel repo. Modifica in esecuzione DOPO merge PR. Cicatrix 2026-04-29 (plist-secret-644): NON mettere secret in chiaro world-readable. Il DSN contiene una password → il plist va `chmod 0400` dopo l'edit.

**Files:**

- Modify: `~/Library/LaunchAgents/com.nuzantara.cell-observatory.plist`

- [ ] **Step 1: Backup + sblocco scrittura**

```bash
P=~/Library/LaunchAgents/com.nuzantara.cell-observatory.plist
cp "$P" "$P.bak-pre-g4-$(date +%Y%m%d)" && chmod 0600 "$P.bak-pre-g4-$(date +%Y%m%d)"  # backup NON world-readable (W65 lesson)
chmod u+w "$P"
```

- [ ] **Step 2: Aggiungere le 3 env var**

Risolvi il DSN reale (stesso degli emitter) e inseriscilo:

```bash
P=~/Library/LaunchAgents/com.nuzantara.cell-observatory.plist
DSN=$(grep -E '^export EVENTBUS_DATABASE_URL=' ~/scripts/openclaw-cron/seo-cell-daily.sh | head -1 | sed -E 's/^export EVENTBUS_DATABASE_URL=//; s/^"//; s/"$//')
# se DSN ha password placeholder, prendila da ~/.nuzantara-secrets.env
case "$DSN" in *'***'*|*REDACTED*) DSN=$(grep -hE 'EVENTBUS_DATABASE_URL|^DATABASE_URL' ~/.nuzantara-secrets.env | head -1 | sed -E 's/^(export )?[A-Z_]+=//; s/^"//; s/"$//');; esac
plutil -replace EnvironmentVariables.EVENTBUS_DATABASE_URL -string "$DSN" "$P"
plutil -replace EnvironmentVariables.OBSERVATORY_CLASSIFIER -string "ollama" "$P"
plutil -replace EnvironmentVariables.OLLAMA_HOST -string "http://localhost:11434" "$P"
plutil -lint "$P"
```

Expected: `OK`.

- [ ] **Step 3: Re-hardening permessi (DSN ha password)**

```bash
P=~/Library/LaunchAgents/com.nuzantara.cell-observatory.plist
chmod 0400 "$P"
ls -la "$P"   # deve essere -r--------
```

- [ ] **Step 4: Reload daemon + verifica boot pulito**

```bash
launchctl bootout gui/501/com.nuzantara.cell-observatory 2>/dev/null
launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.nuzantara.cell-observatory.plist
sleep 8
launchctl list | grep cell-observatory       # PID > 0 e exit code 0
tail -20 ~/logs/cell-observatory/collector.err.log
```

Expected: PID assegnato, exit 0, nei log `listener attached, replaying outbox` → `replay complete`. NESSUN `RuntimeError`. Se il replay trova righe → classificazione parte su Ollama (latency 5-20s/pulse).

- [ ] **Step 5: Verifica end-to-end — la classificazione finisce nello storage SQLite**

```bash
sleep 30
sqlite3 ~/.cell-observatory/observatory.db "SELECT model, label, count(*) FROM classifications GROUP BY model, label ORDER BY 3 DESC LIMIT 10;" 2>&1
```

Expected: righe con `model` tipo `qwen3.5:9b-v1` → il collector consuma e classifica in locale, zero costo.

---

## Self-Review

**1. Spec coverage:** Obiettivo = collector riparte senza key a pagamento. Task 2 (classifier), Task 3 (config opzionale), Task 4 (wiring), Task 6 (env DSN mancante) coprono i due crash diagnosticati (LLM key + EVENTBUS_DATABASE_URL). ✓

**2. Placeholder scan:** nessun TBD/TODO; tutto il codice è completo e i comandi hanno expected output. ✓

**3. Type consistency:** `OllamaClassifier.classify -> ClassificationResult` identica a `MinimaxClassifier`. `classifier_backend` usato uguale in config.py (write) e collector.py (read). `ClassificationLabel.NORMAL/UNCERTAIN` esistono già in `models.py` (usati da MinimaxClassifier riga 175). `model_validate_json` su `ClassificationOutput` riusato dal pattern MiniMax (riga 158). ✓

**Nota su events_outbox**: NON è coperto da una task di fix perché l'evidenza dice che gli emitter SONO configurati per scrivere (EMIT=true + DSN→Fly + proxy vivo). Se Task 6 Step 4 mostra replay che trova 0 righe, allora il problema si sposta a monte (emitter non scrivono davvero) → NUOVO ciclo systematic-debugging, fuori da questo piano.
