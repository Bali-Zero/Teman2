# Automations Reference V2 — Unified Sources Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aggiornare `generate_automations_reference.py` per leggere anche `~/.agent/decisions/job_registry.json` e `~/.agent/decisions/sentinel_status.json` (e `circuit_breakers.json`), arricchire ogni job con campi sentinel (circuit state, DLQ phase, repair_scope, is_idempotent, critical, max_attempts), aggiungere una sezione "Sentinel Overview" al documento, e installare un LaunchAgent che rigenera il file ogni notte alle 23:00 UTC (06:00 WITA).

**Architecture:** Lo script esistente (`scripts/generate_automations_reference.py`) viene esteso in-place con due nuove funzioni: `_load_registry()` e `_load_sentinel_state()`. Il dataclass `Job` riceve 5 nuovi campi opzionali. La funzione `generate()` arricchisce ogni job dopo il parsing esistente tramite join su nome. Il LaunchAgent usa `StartCalendarInterval` (non `StartInterval`) per eseguire esattamente alle 23:00 UTC.

**Tech Stack:** Python 3.11 stdlib (json, dataclasses), macOS LaunchAgents (plist), file esistenti in `~/.agent/decisions/`.

---

## File Map

| File                                                               | Azione | Responsabilità                                                                                                                  |
| ------------------------------------------------------------------ | ------ | ------------------------------------------------------------------------------------------------------------------------------- |
| `scripts/generate_automations_reference.py`                        | Modify | Aggiungere 5 campi a `Job`, `_load_registry()`, `_load_sentinel_state()`, sezione Sentinel Overview, enrichment in `generate()` |
| `~/Library/LaunchAgents/com.nuzantara.automations-reference.plist` | Create | LaunchAgent daily 23:00 UTC                                                                                                     |
| `tests/scripts/test_generate_automations_reference.py`             | Create | Test unitari per le nuove funzioni                                                                                              |

---

## Task 1: Aggiungere test per le nuove funzioni (TDD — prima i test)

**Files:**

- Create: `tests/scripts/test_generate_automations_reference.py`

- [ ] **Step 1.1: Creare il file di test con fixture JSON**

```python
# tests/scripts/test_generate_automations_reference.py
"""Unit tests for generate_automations_reference.py — registry + sentinel enrichment."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Aggiungi la root al path per importare lo script
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import generate_automations_reference as gen

REGISTRY_FIXTURE = {
    "jobs": {
        "fly_health_check": {
            "host": "Nuzantara",
            "type": "cron",
            "schedule_seconds": 1800,
            "staleness_threshold_s": 28800,
            "restart_cmd": "bash /Users/nuzantara/scripts/fly-health-check.sh",
            "is_idempotent": True,
            "repair_scope": "LOCAL",
            "critical": True,
            "max_attempts": 10,
        },
        "nlm_bridge": {
            "host": "Nuzantara",
            "type": "launchagent",
            "schedule_seconds": 60,
            "is_idempotent": True,
            "repair_scope": "LOCAL",
            "critical": False,
            "max_attempts": 5,
        },
    }
}

SENTINEL_STATUS_FIXTURE = {
    "ts": 1776001369.9,
    "generated_at": "2026-04-12T13:42:49Z",
    "jobs_total": 56,
    "jobs_checked": 56,
    "jobs_healthy": 15,
    "jobs_circuit_open": 12,
    "jobs_circuit_terminal": 16,
    "dlq_entries": 59,
    "dlq_terminal": 16,
    "dlq_phase_distribution": {"T0": 4, "T1": 0, "T2": 0, "T3": 20, "T4": 19, "TERMINAL": 16},
}

CIRCUIT_BREAKERS_FIXTURE = {
    "fly_health_check": {
        "state": "CLOSED",
        "failures": 0,
        "phase": "T0",
        "phase_updated_at": 1776001369.0,
    },
    "nlm_bridge": {
        "state": "OPEN",
        "failures": 3,
        "phase": "T3",
        "phase_updated_at": 1775000000.0,
    },
}


class TestLoadRegistry(unittest.TestCase):
    def test_returns_empty_dict_when_file_missing(self):
        result = gen._load_registry(Path("/nonexistent/job_registry.json"))
        self.assertEqual(result, {})

    def test_parses_jobs_correctly(self, tmp_path=None):
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(REGISTRY_FIXTURE, f)
            p = Path(f.name)
        try:
            result = gen._load_registry(p)
            self.assertIn("fly_health_check", result)
            self.assertTrue(result["fly_health_check"]["is_idempotent"])
            self.assertEqual(result["fly_health_check"]["repair_scope"], "LOCAL")
            self.assertEqual(result["fly_health_check"]["max_attempts"], 10)
        finally:
            p.unlink()

    def test_returns_empty_dict_on_invalid_json(self):
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ invalid json }")
            p = Path(f.name)
        try:
            result = gen._load_registry(p)
            self.assertEqual(result, {})
        finally:
            p.unlink()


class TestLoadSentinelState(unittest.TestCase):
    def test_returns_empty_tuple_when_files_missing(self):
        status, cb = gen._load_sentinel_state(
            Path("/nonexistent/sentinel_status.json"),
            Path("/nonexistent/circuit_breakers.json"),
        )
        self.assertEqual(status, {})
        self.assertEqual(cb, {})

    def test_parses_both_files(self):
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(SENTINEL_STATUS_FIXTURE, f)
            status_path = Path(f.name)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(CIRCUIT_BREAKERS_FIXTURE, f)
            cb_path = Path(f.name)
        try:
            status, cb = gen._load_sentinel_state(status_path, cb_path)
            self.assertEqual(status["jobs_healthy"], 15)
            self.assertEqual(cb["fly_health_check"]["state"], "CLOSED")
            self.assertEqual(cb["nlm_bridge"]["phase"], "T3")
        finally:
            status_path.unlink()
            cb_path.unlink()


class TestEnrichJobFromRegistry(unittest.TestCase):
    def _make_job(self, name: str) -> gen.Job:
        return gen.Job(
            name=name, machine="Pro", kind="cron",
            schedule="1800", command="bash test.sh",
        )

    def test_enriches_known_job(self):
        job = self._make_job("fly_health_check")
        registry = {
            "fly_health_check": {
                "is_idempotent": True,
                "repair_scope": "LOCAL",
                "critical": True,
                "max_attempts": 10,
            }
        }
        gen._enrich_job_from_registry(job, registry)
        self.assertTrue(job.is_idempotent)
        self.assertEqual(job.repair_scope, "LOCAL")
        self.assertTrue(job.critical)
        self.assertEqual(job.max_attempts, 10)

    def test_unknown_job_leaves_defaults(self):
        job = self._make_job("unknown_job")
        gen._enrich_job_from_registry(job, {})
        self.assertIsNone(job.is_idempotent)
        self.assertIsNone(job.repair_scope)
        self.assertFalse(job.critical)
        self.assertIsNone(job.max_attempts)


class TestEnrichJobFromCircuitBreaker(unittest.TestCase):
    def _make_job(self, name: str) -> gen.Job:
        return gen.Job(
            name=name, machine="Pro", kind="cron",
            schedule="1800", command="bash test.sh",
        )

    def test_enriches_open_circuit(self):
        job = self._make_job("nlm_bridge")
        cb = {"nlm_bridge": {"state": "OPEN", "failures": 3, "phase": "T3", "phase_updated_at": 0.0}}
        gen._enrich_job_from_circuit_breaker(job, cb)
        self.assertEqual(job.circuit_state, "OPEN")
        self.assertEqual(job.dlq_phase, "T3")

    def test_enriches_closed_circuit(self):
        job = self._make_job("fly_health_check")
        cb = {"fly_health_check": {"state": "CLOSED", "failures": 0, "phase": "T0", "phase_updated_at": 0.0}}
        gen._enrich_job_from_circuit_breaker(job, cb)
        self.assertEqual(job.circuit_state, "CLOSED")
        self.assertEqual(job.dlq_phase, "T0")

    def test_unknown_job_leaves_none(self):
        job = self._make_job("no_such_job")
        gen._enrich_job_from_circuit_breaker(job, {})
        self.assertIsNone(job.circuit_state)
        self.assertIsNone(job.dlq_phase)


class TestFormatCircuitBadge(unittest.TestCase):
    def test_closed_t0(self):
        result = gen._format_circuit_badge("CLOSED", "T0")
        self.assertEqual(result, "✅ CLOSED/T0")

    def test_open_t3(self):
        result = gen._format_circuit_badge("OPEN", "T3")
        self.assertEqual(result, "🔴 OPEN/T3")

    def test_terminal(self):
        result = gen._format_circuit_badge("OPEN", "TERMINAL")
        self.assertEqual(result, "💀 OPEN/TERMINAL")

    def test_none_values(self):
        result = gen._format_circuit_badge(None, None)
        self.assertEqual(result, "—")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 1.2: Verificare che i test FALLISCANO (le funzioni non esistono ancora)**

```bash
cd /Users/nuzantara/Desktop/nuzantara
python -m pytest tests/scripts/test_generate_automations_reference.py -v 2>&1 | head -40
```

Output atteso: `ImportError` o `AttributeError` — le funzioni `_load_registry`, `_load_sentinel_state`, ecc. non esistono.

- [ ] **Step 1.3: Commit dei test**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add tests/scripts/test_generate_automations_reference.py
git commit -m "test(scripts): unit tests per enrichment registry+sentinel in generate_automations_reference"
```

---

## Task 2: Estendere il dataclass `Job` e aggiungere le funzioni di loading

**Files:**

- Modify: `scripts/generate_automations_reference.py` (righe 37-50 per `Job`, poi dopo riga 50 per le nuove funzioni)

- [ ] **Step 2.1: Estendere il dataclass `Job` con 5 nuovi campi opzionali**

Sostituire il dataclass esistente (righe 37-50):

```python
@dataclass
class Job:
    name: str
    machine: str
    kind: str
    schedule: str
    command: str
    log_file: str = ""
    last_status: str = ""
    last_run: str = ""
    exit_code: str = ""
    plist_label: str = ""
    notes: str = ""
    # Campi sentinel/registry (opzionali — None se non in registry)
    is_idempotent: bool | None = None
    repair_scope: str | None = None
    critical: bool = False
    max_attempts: int | None = None
    circuit_state: str | None = None
    dlq_phase: str | None = None
```

- [ ] **Step 2.2: Aggiungere le costanti per i path dei file sentinel**

Dopo `WRITE_BLOCKLIST = ...` (riga 28), aggiungere:

```python
REGISTRY_PATH = Path.home() / ".agent" / "decisions" / "job_registry.json"
SENTINEL_STATUS_PATH = Path.home() / ".agent" / "decisions" / "sentinel_status.json"
CIRCUIT_BREAKERS_PATH = Path.home() / ".agent" / "decisions" / "circuit_breakers.json"
```

- [ ] **Step 2.3: Aggiungere `_load_registry()` dopo `_check_output_safety()`**

Inserire dopo la funzione `_check_output_safety` (dopo riga 34):

```python
def _load_registry(path: Path = REGISTRY_PATH) -> dict:
    """Carica job_registry.json. Restituisce {} se mancante o malformato (graceful degradation)."""
    try:
        data = json.loads(path.read_text())
        return data.get("jobs", {})
    except (FileNotFoundError, json.JSONDecodeError, Exception):
        return {}


def _load_sentinel_state(
    status_path: Path = SENTINEL_STATUS_PATH,
    cb_path: Path = CIRCUIT_BREAKERS_PATH,
) -> tuple[dict, dict]:
    """Carica sentinel_status.json e circuit_breakers.json. Restituisce ({}, {}) se mancanti."""
    status: dict = {}
    cb: dict = {}
    try:
        status = json.loads(status_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, Exception):
        pass
    try:
        cb = json.loads(cb_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, Exception):
        pass
    return status, cb
```

- [ ] **Step 2.4: Aggiungere le funzioni di enrichment e formatting**

Inserire dopo `_load_sentinel_state` (prima di `_run`):

```python
def _enrich_job_from_registry(job: Job, registry: dict) -> None:
    """Arricchisce un Job con i campi del registry (in-place). No-op se il job non e' nel registry."""
    entry = registry.get(job.name, {})
    if not entry:
        return
    job.is_idempotent = entry.get("is_idempotent")
    job.repair_scope = entry.get("repair_scope")
    job.critical = bool(entry.get("critical", False))
    job.max_attempts = entry.get("max_attempts")


def _enrich_job_from_circuit_breaker(job: Job, cb: dict) -> None:
    """Arricchisce un Job con circuit state e DLQ phase (in-place). No-op se non in cb."""
    entry = cb.get(job.name, {})
    if not entry:
        return
    job.circuit_state = entry.get("state")
    job.dlq_phase = entry.get("phase")


def _format_circuit_badge(state: str | None, phase: str | None) -> str:
    """Restituisce un badge leggibile per lo stato del circuit breaker."""
    if state is None and phase is None:
        return "—"
    label = f"{state}/{phase}"
    if phase == "TERMINAL":
        return f"💀 {label}"
    if state == "OPEN":
        return f"🔴 {label}"
    return f"✅ {label}"
```

- [ ] **Step 2.5: Aggiungere `import json` in cima al file**

Il file attuale non importa `json`. Aggiungere dopo `import re`:

```python
import json
```

- [ ] **Step 2.6: Eseguire i test — devono passare parzialmente**

```bash
cd /Users/nuzantara/Desktop/nuzantara
python -m pytest tests/scripts/test_generate_automations_reference.py -v 2>&1
```

Output atteso: `TestLoadRegistry`, `TestLoadSentinelState`, `TestEnrichJobFromRegistry`, `TestEnrichJobFromCircuitBreaker`, `TestFormatCircuitBadge` — tutti PASS. Eventuali test di integrazione ancora FAIL sono ok.

- [ ] **Step 2.7: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add scripts/generate_automations_reference.py
git commit -m "feat(scripts): aggiungere _load_registry, _load_sentinel_state, enrichment e badge in generate_automations_reference"
```

---

## Task 3: Integrare l'enrichment nella funzione `generate()` e aggiungere sezione Sentinel Overview

**Files:**

- Modify: `scripts/generate_automations_reference.py` (funzione `generate()`, righe 362-446)

- [ ] **Step 3.1: Modificare `generate()` per caricare registry e sentinel all'inizio**

Sostituire le prime righe di `generate()` (attualmente righe 362-373) con:

```python
def generate(dry_run: bool = False) -> str:
    _check_output_safety(OUTPUT_FILE)
    generated_at = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())

    # Carica sorgenti aggiuntive (graceful: se mancano, i campi restano None)
    registry = _load_registry()
    sentinel_status, circuit_breakers = _load_sentinel_state()

    pro_cron = _consolidate_cron(_parse_crontab(_run("crontab -l 2>/dev/null"), "Pro"))
    air_cron = _consolidate_cron(_parse_crontab(_ssh_air("crontab -l 2>/dev/null"), "Air"))
    pro_la = _parse_launchagents("Pro")
    air_la = _parse_launchagents("Air")

    all_jobs = pro_cron + air_cron + pro_la + air_la
    _check_log_health_pro(all_jobs)
    _check_log_health_air(all_jobs)

    # Enrichment da registry e circuit breakers
    for job in all_jobs:
        _enrich_job_from_registry(job, registry)
        _enrich_job_from_circuit_breaker(job, circuit_breakers)
```

- [ ] **Step 3.2: Aggiungere il conteggio dei job critici nell'header e la sezione Sentinel Overview**

Dopo il calcolo di `ok`, `fail`, `warn`, `run` (riga ~378), aggiungere:

```python
    critical_count = sum(1 for j in all_jobs if j.critical)
    circuit_open = sentinel_status.get("jobs_circuit_open", "—")
    circuit_terminal = sentinel_status.get("jobs_circuit_terminal", "—")
    dlq_entries = sentinel_status.get("dlq_entries", "—")
    sentinel_generated_at = sentinel_status.get("generated_at", "—")
    dlq_phase_dist = sentinel_status.get("dlq_phase_distribution", {})
```

- [ ] **Step 3.3: Aggiungere "Sentinel Overview" al documento generato**

Aggiungere dopo il blocco `## System Health Summary` (dopo le righe del summary attuale), inserendo nella lista `lines`:

```python
    # Sezione Sentinel Overview (solo se sentinel_status disponibile)
    if sentinel_status:
        phase_str = " · ".join(
            f"{phase}={count}" for phase, count in dlq_phase_dist.items() if count > 0
        ) or "—"
        lines += [
            "## Sentinel Overview",
            "",
            f"> Ultimo aggiornamento sentinel: `{sentinel_generated_at}`",
            "",
            "| Metrica | Valore |",
            "|---------|--------|",
            f"| Circuit OPEN | **{circuit_open}** |",
            f"| Circuit TERMINAL | **{circuit_terminal}** |",
            f"| DLQ entries totali | **{dlq_entries}** |",
            f"| DLQ phase distribution | `{phase_str}` |",
            f"| Job critici (in registry) | **{critical_count}** |",
            "",
            "---",
            "",
        ]
```

- [ ] **Step 3.4: Aggiungere le colonne `Circuit` e `Scope` alle tabelle cron e launchagent**

Modificare il rendering delle tabelle cron (attualmente righe ~421-431) per aggiungere le nuove colonne:

```python
        if cron:
            lines += [
                "### Cron Jobs", "",
                "| Job | Schedule | Last Run | Status | Circuit | Scope | Critical | Notes |",
                "|-----|----------|----------|--------|---------|-------|----------|-------|",
            ]
            for j in cron:
                hs = _humanize_schedule(j.schedule)
                n = j.notes.replace("|", "\\|")[:50] if j.notes else ""
                circuit = _format_circuit_badge(j.circuit_state, j.dlq_phase)
                scope = j.repair_scope or "—"
                crit = "🔴" if j.critical else ""
                lines.append(
                    f"| `{j.name}` | {hs} | {j.last_run} | {j.last_status} | {circuit} | {scope} | {crit} | {n} |"
                )
            lines.append("")
```

Modificare il rendering dei launchagent:

```python
        if la:
            lines += [
                "### LaunchAgents", "",
                "| Label | Status | Exit | Circuit | Scope | Critical |",
                "|-------|--------|------|---------|-------|----------|",
            ]
            for j in la:
                circuit = _format_circuit_badge(j.circuit_state, j.dlq_phase)
                scope = j.repair_scope or "—"
                crit = "🔴" if j.critical else ""
                lines.append(
                    f"| `{j.plist_label}` | {j.last_status} | {j.exit_code} | {circuit} | {scope} | {crit} |"
                )
            lines.append("")
```

- [ ] **Step 3.5: Aggiornare l'header "Source" per includere le nuove sorgenti**

Sostituire la riga `"> Source: ..."` con:

```python
        "> Source: `crontab -l` (Pro+Air) + `launchctl list` (Pro+Air) + log health + `job_registry.json` + `sentinel_status.json` + `circuit_breakers.json`",
```

- [ ] **Step 3.6: Dry-run per verificare l'output**

```bash
cd /Users/nuzantara/Desktop/nuzantara
python scripts/generate_automations_reference.py --dry-run 2>&1 | head -80
```

Output atteso: sezione "Sentinel Overview" visibile, tabelle cron con colonne `Circuit | Scope | Critical`.

- [ ] **Step 3.7: Eseguire i test completi**

```bash
cd /Users/nuzantara/Desktop/nuzantara
python -m pytest tests/scripts/test_generate_automations_reference.py -v 2>&1
```

Output atteso: tutti i test PASS.

- [ ] **Step 3.8: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add scripts/generate_automations_reference.py
git commit -m "feat(scripts): integrare registry+sentinel in generate_automations_reference — Sentinel Overview + colonne Circuit/Scope/Critical"
```

---

## Task 4: Creare il LaunchAgent daily

**Files:**

- Create: `~/Library/LaunchAgents/com.nuzantara.automations-reference.plist`

> Note: il file va in `~/Library/LaunchAgents/`, NON nel monorepo. Non e' tracciato in git (e' infra locale).

- [ ] **Step 4.1: Creare il plist**

```bash
cat > ~/Library/LaunchAgents/com.nuzantara.automations-reference.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.nuzantara.automations-reference</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3</string>
        <string>/Users/nuzantara/Desktop/nuzantara/scripts/generate_automations_reference.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>23</integer>
        <key>Minute</key>
        <integer>15</integer>
    </dict>
    <key>RunAtLoad</key>
    <false/>
    <key>StandardOutPath</key>
    <string>/tmp/cron-automations-reference.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/cron-automations-reference.error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/Users/nuzantara/.openclaw/bin:/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:/Users/nuzantara/.pyenv/versions/3.11.11/bin</string>
        <key>HOME</key>
        <string>/Users/nuzantara</string>
    </dict>
    <key>ProcessType</key>
    <string>Background</string>
    <key>LowPriorityIO</key>
    <true/>
    <key>Nice</key>
    <integer>5</integer>
</dict>
</plist>
EOF
```

> `StartCalendarInterval Hour=23 Minute=15` = 23:15 UTC = 06:15 WITA. Offset di 15 minuti rispetto al sentinel (che gira alle 23:00 UTC) per leggere un `sentinel_status.json` fresco.

- [ ] **Step 4.2: Caricare il LaunchAgent**

```bash
launchctl load ~/Library/LaunchAgents/com.nuzantara.automations-reference.plist
launchctl list | grep automations-reference
```

Output atteso: una riga con `- 0 com.nuzantara.automations-reference` (PID `-` perche' non sta girando in questo momento — `StartCalendarInterval` non fa RunAtLoad).

- [ ] **Step 4.3: Test manuale — triggera il job ora**

```bash
launchctl kickstart -k gui/$(id -u)/com.nuzantara.automations-reference
sleep 30
cat /tmp/cron-automations-reference.log
```

Output atteso: `Written: /Users/nuzantara/Desktop/nuzantara/docs/AUTOMATIONS_REFERENCE.md (N jobs, M lines)`

- [ ] **Step 4.4: Verificare il file generato**

```bash
head -60 /Users/nuzantara/Desktop/nuzantara/docs/AUTOMATIONS_REFERENCE.md
```

Verificare: sezione "Sentinel Overview" presente, tabelle con colonne `Circuit | Scope | Critical`.

- [ ] **Step 4.5: Aggiungere il log map del job al PRO_LOG_MAP nello script**

Aggiungere `"automations_reference"` al `PRO_LOG_MAP` nello script (dopo la riga `"fly_backup": "~/logs/fly-backup.log"`):

```python
    "automations_reference": "/tmp/cron-automations-reference.log",
```

- [ ] **Step 4.6: Commit finale**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add scripts/generate_automations_reference.py
git commit -m "feat(infra): LaunchAgent daily automations-reference + aggiungi log map al PRO_LOG_MAP"
```

---

## Task 5: Aggiornare `job_registry.json` con i campi mancanti

Il `job_registry.json` attuale ha 31 job ma la maggior parte manca di `is_idempotent`, `repair_scope`, `critical`, `max_attempts`. Il documento sara' piu' utile se almeno i job piu' critici hanno questi campi.

**Files:**

- Modify: `~/.agent/decisions/job_registry.json`

- [ ] **Step 5.1: Verificare quanti job nel registry hanno gia' i campi sentinel**

```bash
python3 -c "
import json
data = json.load(open('/Users/nuzantara/.agent/decisions/job_registry.json'))
jobs = data['jobs']
has_fields = [(name, 'repair_scope' in j, 'is_idempotent' in j) for name, j in jobs.items()]
missing = [(n, rs, ii) for n, rs, ii in has_fields if not rs or not ii]
print(f'Jobs totali: {len(jobs)}')
print(f'Mancano campi sentinel: {len(missing)}')
for n, rs, ii in missing: print(f'  - {n} (repair_scope={rs}, is_idempotent={ii})')
"
```

- [ ] **Step 5.2: Aggiungere i campi ai job critici nel registry**

Editare `~/.agent/decisions/job_registry.json` aggiungendo i seguenti campi ai job che ne sono privi. Regola di classificazione:

- `is_idempotent: true` per tutti i job di tipo `launchagent` e `openclaw` (ripartibili senza side effects)
- `is_idempotent: false` per job che scrivono dati unici (es. `fly_backup`)
- `repair_scope: "LOCAL"` per job che non toccano infra esterna (restart locali)
- `repair_scope: "EXTERNAL"` per job che chiamano API esterne o Fly.io
- `repair_scope: "OBSERVE_ONLY"` per job di monitoring (non riparabili automaticamente)
- `critical: true` per: `fly_health_check`, `fly_backup`, `nlm_bridge`, `expiry_alerter`, `dlq_autopilot`, `cert_monitor`, `disk_monitor`
- `max_attempts: 10` default, `max_attempts: 5` per job instabili noti

Esempio per `fly_health_check` (gia' in registry, aggiungere i campi mancanti):

```json
"fly_health_check": {
  "host": "Nuzantara",
  "type": "cron",
  "schedule_seconds": 1800,
  "staleness_threshold_s": 28800,
  "restart_cmd": "bash /Users/nuzantara/scripts/fly-health-check.sh",
  "test_cmd": "bash /Users/nuzantara/scripts/fly-health-check.sh",
  "is_idempotent": true,
  "repair_scope": "EXTERNAL",
  "critical": true,
  "max_attempts": 10
}
```

- [ ] **Step 5.3: Rigenerare il documento per verificare i nuovi dati**

```bash
cd /Users/nuzantara/Desktop/nuzantara
python scripts/generate_automations_reference.py --dry-run 2>&1 | grep -A2 "fly_health_check"
```

Output atteso: la riga di `fly_health_check` mostra `✅ CLOSED/T0` nella colonna Circuit e `EXTERNAL` nella colonna Scope.

---

## Task 6: Verifica finale e commit del documento rigenerato

- [ ] **Step 6.1: Rigenerare il documento completo**

```bash
cd /Users/nuzantara/Desktop/nuzantara
python scripts/generate_automations_reference.py
```

Output atteso: `Written: .../docs/AUTOMATIONS_REFERENCE.md (N jobs, M lines)`

- [ ] **Step 6.2: Verificare struttura del documento**

```bash
grep -E "^## |^### " /Users/nuzantara/Desktop/nuzantara/docs/AUTOMATIONS_REFERENCE.md
```

Output atteso:

```
## System Health Summary
## Sentinel Overview
## Pro (nuzantara@Nuzantara — M4 Pro 48GB)
### LaunchAgents
### Cron Jobs
---
## Air (antonellosiano@Nuzantara-9 — M4 16GB, H24)
### LaunchAgents
### Cron Jobs
```

- [ ] **Step 6.3: Commit del documento rigenerato**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add docs/AUTOMATIONS_REFERENCE.md
git commit -m "docs: rigenera AUTOMATIONS_REFERENCE.md con Sentinel Overview + colonne Circuit/Scope/Critical"
```

- [ ] **Step 6.4: Verificare che il LaunchAgent sia nel registry del sentinel**

Il sentinel legge `job_registry.json` ogni run. Aggiungere `automations_reference` al registry:

```json
"automations_reference": {
  "host": "Nuzantara",
  "type": "launchagent",
  "plist": "com.nuzantara.automations-reference",
  "schedule_seconds": 86400,
  "staleness_threshold_s": 93600,
  "restart_cmd": "launchctl kickstart -k gui/$(id -u)/com.nuzantara.automations-reference",
  "test_cmd": null,
  "is_idempotent": true,
  "repair_scope": "LOCAL",
  "critical": false,
  "max_attempts": 3,
  "_note": "Rigenera docs/AUTOMATIONS_REFERENCE.md ogni notte alle 23:15 UTC."
}
```

---

## Checklist VADEMECUM (Sezione 1 — Nuova automazione)

| #   | Punto                                   | Risposta                                                                                                                                          |
| --- | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Dove vive nell'organismo?               | Organo infra-docs. Produce `AUTOMATIONS_REFERENCE.md`. Consumato da agenti Claude Code a sessione start e da Zero per overview.                   |
| 2   | Cosa produce?                           | File markdown in `docs/`, aggiornato ogni notte.                                                                                                  |
| 3   | Chi legge quello che produce?           | Claude Code (sessione start), Zero (manuale).                                                                                                     |
| 4   | Ha una reflection post-run?             | No — il job e' deterministico e non ha errori domain-specific. Log in `/tmp/cron-automations-reference.log`.                                      |
| 5   | Logga in modo strutturato?              | `print()` con formato `Written: path (N jobs, M lines)` — sufficiente per un doc generator.                                                       |
| 6   | Ha un meccanismo di failure silenzioso? | Si — `_load_registry()` e `_load_sentinel_state()` restituiscono `{}` su qualsiasi errore. Il documento viene generato anche senza dati sentinel. |
| 7   | E' misurabile?                          | Si — `N jobs, M lines` nel log.                                                                                                                   |
| 8   | Produce un evento Redis?                | No — non necessario per un doc generator.                                                                                                         |

---

## Self-Review del Piano

**Spec coverage:**

- ✅ `job_registry.json` integrato (Task 2 + 3)
- ✅ `sentinel_status.json` integrato (Task 2 + 3)
- ✅ `circuit_breakers.json` integrato (Task 2 + 3)
- ✅ Campi V3.3 (repair_scope, is_idempotent, critical, circuit state, DLQ phase) — Task 3
- ✅ LaunchAgent daily — Task 4
- ✅ Graceful degradation se file mancanti — Task 2 (`_load_registry` e `_load_sentinel_state`)
- ✅ D3.1 write-blocklist rispettata — `_check_output_safety` invariata
- ✅ Job aggiunto al registry sentinel — Task 6

**Placeholder scan:** Nessun TBD, nessun "implementare dopo". Ogni step ha codice completo.

**Type consistency:**

- `_load_registry()` restituisce `dict` — usato come `registry: dict` in `generate()`
- `_load_sentinel_state()` restituisce `tuple[dict, dict]` — destructured in `sentinel_status, circuit_breakers`
- `_enrich_job_from_registry(job, registry)` — `job: Job`, `registry: dict`
- `_enrich_job_from_circuit_breaker(job, cb)` — `job: Job`, `cb: dict`
- `_format_circuit_badge(state, phase)` — `str | None, str | None` → `str`
- `Job.circuit_state: str | None` e `Job.dlq_phase: str | None` — coerenti con i valori di `circuit_breakers.json`
