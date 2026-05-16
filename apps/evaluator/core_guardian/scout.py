"""
Core Guardian V3 — SCOUT (Livello 2)

Runtime: launchd / cron di sistema — NON OpenClaw (Python puro, zero LLM)
Frequenza: ogni 6h
Costo: $0

Responsabilità:
- Esegue ruff con JSON output
- Raggruppa per codice + file
- Classifica SAFE/UNSAFE per tipo di operazione (deterministico)
- Produce report top 5 issue
- Invia report Telegram
- Scrive report in .agent/decisions/scout_reports/
"""

import json
import logging
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# Import shared utilities from watchdog
from watchdog import (
    AGENT_DIR,
    BACKEND_DIR,
    BASELINE_FILE,
    LOCK_FILE,
    RUFF_RULES,
    VENV_PYTHON,
    acquire_lock,
    atomic_write_json,
    build_test_env,
    release_lock,
    safe_load_json,
    send_telegram_alert,
)

logging.basicConfig(
    level=logging.INFO,
    format="[Scout %(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("scout")

SCOUT_REPORTS_DIR = AGENT_DIR / "scout_reports"

# Classificazione per TIPO DI OPERAZIONE (non per path file)
SAFE_RULES = {"ANN001", "ANN204", "DTZ003", "DTZ005"}  # type hints, timezone
UNSAFE_RULES = {"BLE001", "C901", "TRY400"}  # except handling, logic, error handling

# File intoccabili (indipendentemente dalla regola)
UNTOUCHABLE_PATTERNS = [
    "main.py", "main_cloud.py", "dependencies.py",
    "config.py", "zantara_core.py",
    "alembic/", "middleware/", "channels/",
]


def run_ruff_json() -> list[dict]:
    """Esegue ruff e ritorna la lista completa di violations come JSON."""
    rules_str = ",".join(RUFF_RULES)
    cmd = [
        str(VENV_PYTHON), "-m", "ruff", "check",
        "backend/services/", "backend/app/", "backend/agents/",
        "--select", rules_str,
        "--output-format=json",
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=str(BACKEND_DIR), timeout=120,
            env=build_test_env(),
        )
        if result.stdout:
            data = json.loads(result.stdout)
            return data if isinstance(data, list) else []
        return []
    except Exception as e:
        logger.error(f"Ruff check failed: {e}")
        return []


def is_untouchable(filepath: str) -> bool:
    """Verifica se un file è nella lista intoccabili."""
    for pattern in UNTOUCHABLE_PATTERNS:
        if pattern in filepath:
            return True
    return False


def classify_issue(code: str, filepath: str) -> str:
    """Classifica una issue come SAFE, UNSAFE, o BLOCKED."""
    if is_untouchable(filepath):
        return "BLOCKED"
    if code in SAFE_RULES:
        return "SAFE"
    if code in UNSAFE_RULES:
        return "UNSAFE"
    return "UNKNOWN"


def analyze_violations(violations: list[dict]) -> list[dict]:
    """Analizza le violations e produce un ranking per file+codice."""
    # Raggruppa per (code, filename)
    groups: dict[tuple[str, str], int] = Counter()
    for v in violations:
        code = v.get("code", "UNKNOWN")
        # Il path da ruff è relativo a cwd (BACKEND_DIR)
        filename = v.get("filename", "unknown")
        groups[(code, filename)] += 1

    # Ordina per conteggio decrescente
    ranked = []
    for (code, filename), count in groups.most_common(20):
        classification = classify_issue(code, filename)
        ranked.append({
            "code": code,
            "file": filename,
            "count": count,
            "classification": classification,
        })

    return ranked


def build_report(ranked: list[dict], total_violations: int) -> str:
    """Costruisce il report testuale."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    baseline = safe_load_json(BASELINE_FILE) or {}

    lines = [
        f"SCOUT REPORT {now}",
        f"Total violations: {total_violations}",
        f"Baseline: passed={baseline.get('test_passed', '?')}, ruff={baseline.get('ruff_violations', '?')}",
        "",
        "Top issues by file:",
    ]

    for i, item in enumerate(ranked[:10], 1):
        tag = item["classification"]
        lines.append(
            f"  {i}. [{tag}] {item['code']} in {item['file']} ({item['count']}x)"
        )

    # Candidati SAFE per il Surgeon (Fase 3 auto-approvati)
    safe_candidates = [r for r in ranked if r["classification"] == "SAFE"]
    if safe_candidates:
        lines.append("")
        lines.append("SAFE candidates (auto-approvable in Fase 3):")
        for c in safe_candidates[:5]:
            lines.append(f"  - {c['code']} in {c['file']} ({c['count']}x)")

    return "\n".join(lines)


# --- mypy + vulture ---

def run_mypy() -> dict:
    """
    Run mypy on backend/app/ and backend/services/.
    Returns {"errors": int, "output": str, "status": "ok"|"failed"|"unavailable"}.
    Informational only — does not block fixes.
    """
    cmd = [
        str(VENV_PYTHON), "-m", "mypy",
        "backend/app/", "backend/services/",
        "--ignore-missing-imports",
        "--no-error-summary",
        "--no-pretty",
        "--output", "json",
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=str(BACKEND_DIR), timeout=180,
            env=build_test_env(),
        )
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        errors = len(lines)
        return {"errors": errors, "output": result.stdout[:2000], "status": "ok" if errors == 0 else "failed"}
    except FileNotFoundError:
        return {"errors": -1, "output": "mypy not installed", "status": "unavailable"}
    except subprocess.TimeoutExpired:
        return {"errors": -1, "output": "mypy timeout (180s)", "status": "unavailable"}
    except Exception as e:
        return {"errors": -1, "output": str(e), "status": "unavailable"}


def run_vulture() -> dict:
    """
    Run vulture on backend/ to detect dead code.
    Returns {"dead_code": int, "output": str, "status": "ok"|"found"|"unavailable"}.
    Informational only — does not block fixes.
    """
    cmd = [
        str(VENV_PYTHON), "-m", "vulture",
        "backend/",
        "--min-confidence", "80",
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=str(BACKEND_DIR), timeout=120,
            env=build_test_env(),
        )
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        dead = len(lines)
        return {"dead_code": dead, "output": result.stdout[:2000], "status": "ok" if dead == 0 else "found"}
    except FileNotFoundError:
        return {"dead_code": -1, "output": "vulture not installed", "status": "unavailable"}
    except subprocess.TimeoutExpired:
        return {"dead_code": -1, "output": "vulture timeout (120s)", "status": "unavailable"}
    except Exception as e:
        return {"dead_code": -1, "output": str(e), "status": "unavailable"}


def scout_run() -> None:
    """Esecuzione principale dello Scout."""
    logger.info("=== Scout Run ===")

    lock_fd = acquire_lock()
    if lock_fd < 0:
        logger.info("Lock held by another process, skipping")
        return

    try:
        # 1. Esegui ruff
        violations = run_ruff_json()
        logger.info(f"Found {len(violations)} total violations")

        # 2. mypy (informational)
        mypy_result = run_mypy()
        logger.info(f"mypy: {mypy_result['errors']} errors ({mypy_result['status']})")

        # 3. vulture (informational)
        vulture_result = run_vulture()
        logger.info(f"vulture: {vulture_result['dead_code']} dead-code items ({vulture_result['status']})")

        if not violations:
            logger.info("No ruff violations found.")
            # Still send mypy/vulture summary if noteworthy
            extra = []
            if mypy_result["status"] == "failed":
                extra.append(f"mypy: {mypy_result['errors']} errors")
            if vulture_result["status"] == "found":
                extra.append(f"vulture: {vulture_result['dead_code']} dead-code items")
            if extra:
                send_telegram_alert("Scout: 0 ruff violations\n" + "\n".join(extra))
            release_lock(lock_fd)
            return

        # 4. Analizza
        ranked = analyze_violations(violations)

        # 5. Report
        report = build_report(ranked, len(violations))
        logger.info(f"\n{report}")

        # 6. Salva report
        SCOUT_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_file = SCOUT_REPORTS_DIR / f"scout_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        atomic_write_json(report_file, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_violations": len(violations),
            "ranked": ranked[:20],
            "safe_candidates": [r for r in ranked if r["classification"] == "SAFE"][:10],
            "mypy": mypy_result,
            "vulture": vulture_result,
        })

        # 7. Telegram — include mypy/vulture summary
        tg_lines = [f"Scout Report ({len(violations)} violations)"]
        for item in ranked[:5]:
            tg_lines.append(f"[{item['classification']}] {item['code']} {item['file']} ({item['count']}x)")
        if mypy_result["status"] == "failed":
            tg_lines.append(f"mypy: {mypy_result['errors']} type errors")
        if vulture_result["status"] == "found":
            tg_lines.append(f"vulture: {vulture_result['dead_code']} dead-code items")
        send_telegram_alert("\n".join(tg_lines))

    finally:
        release_lock(lock_fd)

    logger.info("=== Scout Complete ===")


if __name__ == "__main__":
    scout_run()
