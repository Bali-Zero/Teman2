"""
Core Guardian V3 — WATCHDOG (Livello 1)

Runtime: launchd (macOS) o cron di sistema — NON OpenClaw
Frequenza: ogni 30 min (giorno) / ogni 2h (notte)
Modello: NESSUNO — Python puro deterministico
Costo: $0

Responsabilità:
- Esegue pytest con junitxml, conta passed/failed/errors
- Confronta con baseline.json
- Se regressione → alert Telegram + log circuit breaker
- Se miglioramento → aggiorna baseline
- Cleanup: worktree prune, branch vecchie

Principio: enforcement deterministico, nessun LLM.
"""

import fcntl
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[Watchdog %(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("watchdog")


# --- Path Resolution (robusto, non relativo) ---

def find_project_root() -> Path:
    """Trova la root del progetto cercando marker reali."""
    # Cerca partendo dalla directory di questo file, salendo
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / ".git").exists() and (current / "apps" / "backend-rag").exists():
            return current
        current = current.parent
    # Fallback: variabile d'ambiente
    env_root = os.environ.get("NUZANTARA_ROOT")
    if env_root and Path(env_root).exists():
        return Path(env_root)
    logger.error("Cannot find project root. Set NUZANTARA_ROOT env var.")
    sys.exit(1)


PROJECT_ROOT = find_project_root()
BACKEND_DIR = PROJECT_ROOT / "apps" / "backend-rag"
AGENT_DIR = PROJECT_ROOT / ".agent" / "decisions"
BASELINE_FILE = AGENT_DIR / "baseline.json"
STATE_FILE = AGENT_DIR / "state.json"
UNSENT_ALERTS_FILE = AGENT_DIR / "unsent_alerts.log"
LOCK_FILE = Path("/tmp/guardian.lock")
VENV_PYTHON = BACKEND_DIR / ".venv" / "bin" / "python"

# Telegram
TELEGRAM_CHAT_ID = "1125336968"

# Ruff rules (unified source of truth)
RUFF_RULES = ["BLE001", "DTZ003", "DTZ005", "C901", "TRY400", "ANN001", "ANN204"]


# --- Locking ---

def acquire_lock() -> int:
    """Acquisisce un lock esclusivo. Ritorna il fd o -1 se lock preso."""
    try:
        fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except (OSError, BlockingIOError):
        return -1


def release_lock(fd: int) -> None:
    """Rilascia il lock."""
    if fd >= 0:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        except OSError:
            pass
        try:
            LOCK_FILE.unlink(missing_ok=True)
        except OSError:
            pass


# --- Atomic File Operations ---

def atomic_write_json(filepath: Path, data: dict) -> None:
    """Scrittura atomica: temp file + os.replace."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(filepath.parent), suffix=".tmp", prefix=filepath.stem,
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(filepath))
    except Exception:
        # Cleanup temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def safe_load_json(filepath: Path) -> dict | None:
    """Carica JSON con gestione file corrotto."""
    if not filepath.exists():
        return None
    try:
        with open(filepath) as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError) as e:
        # Quarantine corrupted file
        quarantine = filepath.with_suffix(f".corrupted.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        logger.warning(f"Corrupted JSON {filepath}, moving to {quarantine}: {e}")
        try:
            filepath.rename(quarantine)
        except OSError:
            pass
        return None


# --- Test Execution ---

def build_test_env() -> dict:
    """Costruisce environment isolato per pytest. NON eredita os.environ cieco."""
    # Environment minimale e sicuro
    safe_env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin"),
        "HOME": os.environ.get("HOME", ""),
        "PYTHONPATH": ".",
        "ENVIRONMENT": "test",
        # Virtual env
        "VIRTUAL_ENV": str(BACKEND_DIR / ".venv"),
    }
    # Aggiungi LANG/LC per evitare encoding issues
    for key in ("LANG", "LC_ALL", "LC_CTYPE"):
        if key in os.environ:
            safe_env[key] = os.environ[key]
    return safe_env


def run_pytest_junitxml() -> dict:
    """Esegue pytest con junitxml output. Parser deterministico, nessuna regex."""
    report_path = Path(tempfile.mktemp(suffix=".xml", prefix="guardian-pytest-"))

    cmd = [
        str(VENV_PYTHON), "-m", "pytest",
        "backend/tests/",
        f"--junitxml={report_path}",
        "--tb=no", "-q", "--no-header",
        "--timeout=120",
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=str(BACKEND_DIR), timeout=660,
            env=build_test_env(),
        )

        if not report_path.exists():
            return {
                "passed": 0, "failed": 0, "errors": 0,
                "exit_code": result.returncode,
                "error": "junitxml report not generated",
            }

        # Parse junitxml — deterministico
        tree = ET.parse(str(report_path))
        root = tree.getroot()

        # Il root è <testsuites> o <testsuite>
        if root.tag == "testsuites":
            suite = root.find("testsuite")
        else:
            suite = root

        if suite is None:
            return {
                "passed": 0, "failed": 0, "errors": 0,
                "exit_code": result.returncode,
                "error": "No testsuite found in junitxml",
            }

        tests = int(suite.get("tests", 0))
        failures = int(suite.get("failures", 0))
        errors = int(suite.get("errors", 0))
        skipped = int(suite.get("skipped", 0))
        passed = tests - failures - errors - skipped

        return {
            "passed": max(passed, 0),
            "failed": failures,
            "errors": errors,
            "skipped": skipped,
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"passed": 0, "failed": 0, "errors": -1, "exit_code": -1,
                "error": "pytest timeout (660s)"}
    except ET.ParseError as e:
        return {"passed": 0, "failed": 0, "errors": -1, "exit_code": -1,
                "error": f"junitxml parse error: {e}"}
    except Exception as e:
        return {"passed": 0, "failed": 0, "errors": -1, "exit_code": -1,
                "error": str(e)}
    finally:
        # Cleanup report file
        try:
            report_path.unlink(missing_ok=True)
        except OSError:
            pass


def run_ruff_count() -> int:
    """Conta ruff violations per le regole monitorate. Ritorna -1 se errore."""
    rules_str = ",".join(RUFF_RULES)
    cmd = [
        str(VENV_PYTHON), "-m", "ruff", "check",
        "backend/services/", "backend/app/",
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
            return len(data) if isinstance(data, list) else -1
        # ruff con 0 violations = stdout vuoto o []
        return 0
    except Exception as e:
        logger.warning(f"Ruff check failed: {e}")
        return -1


# --- Telegram ---

def send_telegram_alert(message: str) -> bool:
    """Invia alert Telegram. Ritorna True se riuscito."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set, writing to unsent alerts")
        _log_unsent_alert(message)
        return False

    import urllib.request
    import urllib.error

    # Prova Markdown, fallback a plain text
    for parse_mode in ("Markdown", None):
        try:
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            data = json.dumps(payload).encode()
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10)
            return True
        except urllib.error.HTTPError:
            if parse_mode == "Markdown":
                continue  # Retry senza Markdown
            _log_unsent_alert(message)
            return False
        except Exception:
            _log_unsent_alert(message)
            return False
    return False


def _log_unsent_alert(message: str) -> None:
    """Salva alert non inviato su file locale."""
    try:
        UNSENT_ALERTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(UNSENT_ALERTS_FILE, "a") as f:
            f.write(f"[{datetime.now(timezone.utc).isoformat()}] {message}\n")
    except OSError:
        pass


# --- Auto-Dispatch Surgeon ---

SAFE_RUFF_CODES_FOR_DISPATCH: set[str] = {"ANN001", "ANN204", "DTZ003", "DTZ005"}


def _get_safe_ruff_candidates() -> list[str]:
    """Return up to 2 backend files that have SAFE_RUFF violations."""
    rules_str = ",".join(sorted(SAFE_RUFF_CODES_FOR_DISPATCH))
    try:
        result = subprocess.run(
            [str(VENV_PYTHON), "-m", "ruff", "check",
             "backend/services/", "backend/app/",
             "--select", rules_str,
             "--output-format", "json"],
            cwd=str(BACKEND_DIR),
            capture_output=True, text=True, timeout=60,
            env={**os.environ, "PYTHONPATH": str(BACKEND_DIR)},
        )
        if not result.stdout.strip():
            return []
        violations = json.loads(result.stdout)
        seen: list[str] = []
        for v in violations:
            fp = v.get("filename", "")
            if fp and fp not in seen:
                seen.append(fp)
            if len(seen) >= 2:
                break
        return seen
    except Exception as e:
        logger.warning(f"_get_safe_ruff_candidates failed: {e}")
        return []


def auto_dispatch_surgeon(regressions: list[str]) -> None:
    """
    On regression detected, find SAFE_RUFF violations in failing files and
    launch Surgeon as a background process for each one.

    Only dispatches for codes in SAFE_RUFF_CODES_FOR_DISPATCH (deterministic,
    low-risk fixes). Max 2 files per regression event to avoid thrashing.

    If regressions is empty, scans the full backend for candidates instead.
    """
    targets = regressions[:2] if regressions else _get_safe_ruff_candidates()
    if not targets:
        return

    surgeon_script = Path(__file__).parent / "surgeon.py"
    if not surgeon_script.exists():
        logger.warning("surgeon.py not found — skipping auto-dispatch")
        return

    dispatched = 0
    for target_file in targets:
        try:
            result = subprocess.run(
                [str(VENV_PYTHON), "-m", "ruff", "check", target_file,
                 "--select", ",".join(sorted(SAFE_RUFF_CODES_FOR_DISPATCH)),
                 "--output-format", "json"],
                cwd=str(BACKEND_DIR),
                capture_output=True, text=True, timeout=30,
                env={**os.environ, "PYTHONPATH": str(BACKEND_DIR)},
            )
            if not result.stdout.strip():
                continue
            try:
                violations = json.loads(result.stdout)
            except Exception:
                continue
            if not violations:
                continue
            code = violations[0].get("code", "")
            if code not in SAFE_RUFF_CODES_FOR_DISPATCH:
                continue

            logger.info(f"Auto-dispatching Surgeon for {target_file} ({code})")
            subprocess.Popen(
                [str(VENV_PYTHON), str(surgeon_script),
                 f"Fix {code} in {target_file}", target_file, code],
                cwd=str(PROJECT_ROOT),
            )
            dispatched += 1
        except Exception as e:
            logger.warning(f"auto_dispatch_surgeon failed for {target_file}: {e}")

    if dispatched > 0:
        logger.info(f"Auto-dispatched Surgeon for {dispatched} file(s)")


# --- Main Logic ---

def watchdog_run() -> None:
    """Esecuzione principale del Watchdog."""
    logger.info("=== Watchdog Run ===")

    # 1. Lock
    lock_fd = acquire_lock()
    if lock_fd < 0:
        logger.info("Lock held by another process, skipping")
        return

    try:
        _watchdog_core()
    finally:
        release_lock(lock_fd)

    logger.info("=== Watchdog Complete ===")


def _watchdog_core() -> None:
    """Core logic, eseguita sotto lock."""

    # 1. Worktree prune (cleanup)
    try:
        subprocess.run(
            ["git", "worktree", "prune"],
            cwd=str(PROJECT_ROOT), capture_output=True, timeout=10,
        )
    except Exception:
        pass

    # 2. Esegui pytest
    test_result = run_pytest_junitxml()
    logger.info(
        f"Tests: passed={test_result['passed']}, "
        f"failed={test_result['failed']}, errors={test_result['errors']}"
    )

    if test_result.get("error"):
        send_telegram_alert(f"Watchdog Error: {test_result['error']}")
        return

    # 3. Ruff count
    ruff_count = run_ruff_count()
    logger.info(f"Ruff violations ({','.join(RUFF_RULES)}): {ruff_count}")

    # 4. Load baseline
    baseline = safe_load_json(BASELINE_FILE)
    now = datetime.now(timezone.utc).isoformat()

    if baseline is None:
        # Prima esecuzione — crea baseline SOLO se stato sano
        if test_result["exit_code"] != 0 or test_result["failed"] > 0 or test_result["errors"] > 0:
            msg = (
                f"Watchdog: cannot create baseline, suite unhealthy. "
                f"passed={test_result['passed']}, failed={test_result['failed']}, "
                f"errors={test_result['errors']}, exit_code={test_result['exit_code']}"
            )
            logger.warning(msg)
            send_telegram_alert(msg)
            return

        if ruff_count < 0:
            logger.warning("Watchdog: cannot create baseline, ruff check failed")
            return

        baseline = {
            "test_passed": test_result["passed"],
            "test_failed": test_result["failed"],
            "test_errors": test_result["errors"],
            "ruff_violations": ruff_count,
            "created_at": now,
            "updated_at": now,
        }
        atomic_write_json(BASELINE_FILE, baseline)
        logger.info(f"Baseline created: {test_result['passed']} passed, {ruff_count} ruff violations")
        send_telegram_alert(
            f"Watchdog Baseline Created\n"
            f"Tests passed: {test_result['passed']}\n"
            f"Ruff violations: {ruff_count}"
        )
        return

    # 5. Confronto
    baseline_passed = baseline.get("test_passed", 0)
    current_passed = test_result["passed"]
    current_failed = test_result["failed"]
    current_errors = test_result["errors"]

    # Check exit code first
    if test_result["exit_code"] != 0 and current_failed == 0 and current_errors == 0:
        # pytest errore non catturato da junitxml (collection error, etc.)
        send_telegram_alert(
            f"Watchdog: pytest exit_code={test_result['exit_code']} "
            f"but 0 failed/errors — possible collection error"
        )

    if current_passed < baseline_passed:
        if current_failed == 0 and current_errors == 0:
            # Test rimossi legittimamente (refactoring)
            delta = baseline_passed - current_passed
            logger.info(f"Tests decreased by {delta} but suite is green — accepting as legitimate removal")
            baseline["test_passed"] = current_passed
            baseline["test_failed"] = current_failed
            baseline["test_errors"] = current_errors
            baseline["updated_at"] = now
            atomic_write_json(BASELINE_FILE, baseline)
        else:
            # REGRESSIONE
            delta = baseline_passed - current_passed
            msg = (
                f"REGRESSION DETECTED\n"
                f"Tests passed: {current_passed} (was {baseline_passed}, -{delta})\n"
                f"Failed: {current_failed}, Errors: {current_errors}\n"
                f"Baseline set at: {baseline.get('updated_at', '?')}"
            )
            logger.warning(msg)
            send_telegram_alert(msg)

            # Log per circuit breaker
            _log_circuit_breaker_event("regression_detected", {
                "baseline_passed": baseline_passed,
                "current_passed": current_passed,
                "delta": -delta,
            })

            # Auto-dispatch Surgeon to fix safe ruff violations while humans investigate
            auto_dispatch_surgeon([])

    elif current_passed > baseline_passed:
        # Miglioramento
        delta = current_passed - baseline_passed
        baseline["test_passed"] = current_passed
        baseline["test_failed"] = current_failed
        baseline["test_errors"] = current_errors
        baseline["updated_at"] = now
        atomic_write_json(BASELINE_FILE, baseline)
        logger.info(f"Baseline updated: {current_passed} passed (+{delta})")

    else:
        # Passed uguale — aggiorna comunque se failed/errors cambiano
        if (current_failed != baseline.get("test_failed") or
                current_errors != baseline.get("test_errors")):
            baseline["test_failed"] = current_failed
            baseline["test_errors"] = current_errors
            baseline["updated_at"] = now
            atomic_write_json(BASELINE_FILE, baseline)
            logger.info("Baseline updated (failed/errors changed)")
        else:
            logger.info(f"Stable: {current_passed} passed = baseline")

    # 6. Ruff check
    baseline_ruff = baseline.get("ruff_violations", 0)
    if ruff_count >= 0:  # Guard: skip se ruff fallito
        if baseline_ruff >= 0 and ruff_count > baseline_ruff:
            delta = ruff_count - baseline_ruff
            send_telegram_alert(
                f"Ruff Violations Increased\n"
                f"Current: {ruff_count} (was {baseline_ruff}, +{delta})"
            )
        elif ruff_count < baseline_ruff:
            baseline["ruff_violations"] = ruff_count
            baseline["updated_at"] = now
            atomic_write_json(BASELINE_FILE, baseline)
            logger.info(f"Ruff improved: {ruff_count} (was {baseline_ruff})")

    # 7. Cache invalidation audit (AST — informativo, non bloccante)
    try:
        import sys as _sys
        _checks_dir = Path(__file__).parent / "checks"
        if str(_checks_dir) not in _sys.path:
            _sys.path.insert(0, str(_checks_dir.parent.parent.parent))
        from apps.evaluator.core_guardian.checks.cache_invalidation_audit import (
            run_audit as _cache_audit,
            format_report as _cache_format,
        )
        _cache_findings = _cache_audit(PROJECT_ROOT)
        _baseline_cache = baseline.get("cache_audit_count", None)
        logger.info(f"Cache audit: {len(_cache_findings)} endpoint senza invalidate_cache")
        if _baseline_cache is None:
            # Prima run — salva baseline silenziosamente
            baseline["cache_audit_count"] = len(_cache_findings)
            baseline["updated_at"] = now
            atomic_write_json(BASELINE_FILE, baseline)
        elif len(_cache_findings) > _baseline_cache + 5:
            # Aumento significativo (>5 nuovi) — alert
            delta_cache = len(_cache_findings) - _baseline_cache
            send_telegram_alert(
                f"Cache Invalidation Gap Aumentato\n"
                f"Endpoint senza invalidate_cache: {len(_cache_findings)} (era {_baseline_cache}, +{delta_cache})\n"
                f"Possibile nuova mutation senza cache invalidation."
            )
        elif len(_cache_findings) < _baseline_cache:
            # Miglioramento
            baseline["cache_audit_count"] = len(_cache_findings)
            baseline["updated_at"] = now
            atomic_write_json(BASELINE_FILE, baseline)
            logger.info(f"Cache audit migliorato: {len(_cache_findings)} (era {_baseline_cache})")
    except Exception as _e:
        logger.debug(f"Cache audit skip: {_e}")


def _log_circuit_breaker_event(event_type: str, data: dict) -> None:
    """Appende un evento al circuit breaker log."""
    log_file = AGENT_DIR / "circuit_breaker.jsonl"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "event": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **data,
    }
    try:
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def reset_baseline() -> None:
    """Reset manuale della baseline. Usa dopo refactoring legittimi."""
    logger.info("Resetting baseline...")
    if BASELINE_FILE.exists():
        BASELINE_FILE.unlink()
    logger.info("Baseline removed. Next watchdog run will create a new one.")


# --- Entry Point ---

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--reset-baseline":
        reset_baseline()
    else:
        watchdog_run()
