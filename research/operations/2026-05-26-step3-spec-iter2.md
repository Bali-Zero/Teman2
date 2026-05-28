---
date: 2026-05-26
domain: operations
client_case: self-healing-wa-mirror-enrichment
sources:
  - /tmp/wave2-panel/gemini.md  (APPROVE_WITH_AMENDMENTS, 3 MUST-FIX)
  - /tmp/wave2-panel/codex2.md  (REJECT, 8 bugs + 5 security vulns)
  - /tmp/wave2-panel/deepseek-raw2.json  (panel synthesis)
  - apps/organism/organism/actuators/fly_machines_restart.py  (W31 reference)
  - apps/organism/organism/actuators/base.py  (W37 incident_ledger auto-wire)
  - apps/organism/organism/supervisor/dispatch.py  (target_key = actuator:target)
  - ~/scripts/wa-mirror-enrichment-wrapper.sh  (Layer A reference)
---

# Spec Step 3 iter-2 — `python_env_repair` Organism Actuator (PANEL-AMENDED)

## Status legend

- ✅ Implemented in iter-1
- 🔧 **Panel-amended** must-fix (10 items A1-A10)
- ❌ Out of scope iter-2

## Panel verdict synthesis

| LLM                 | Verdict                 | Severity caught                                                        |
| ------------------- | ----------------------- | ---------------------------------------------------------------------- |
| Gemini agy 3.1 Pro  | APPROVE_WITH_AMENDMENTS | 3 must-fix (orphan-started, root-module, index-pinning)                |
| Codex GPT-5.5 xhigh | REJECT                  | 8 bugs + 5 security vulns (regex, allowlist, env-pollution, race, DoS) |
| DeepSeek V4 Pro     | (synthesis)             | aggregated                                                             |

Convergence: 10 universal must-fix items A1-A10 (Codex must-fix subset is superset of Gemini's). Pre-ship: implement all 10 OR risk supply-chain attack vector + production env corruption.

## 10 panel must-fix items (NON-NEGOTIABLE)

| #       | Fix                                                                                                                                     | Source       | Implementation                                                                                                                  |
| ------- | --------------------------------------------------------------------------------------------------------------------------------------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------- |
| **A1**  | Force `--index-url=https://pypi.org/simple/` + `--no-input` on pip install (supply-chain)                                               | Gemini+Codex | `_build_argv`                                                                                                                   |
| **A2**  | Regex `fullmatch()` not `match()`, block newline/control chars                                                                          | Codex        | `_validate_pkg`                                                                                                                 |
| **A3**  | Explicit allowlist `_DEP_ALLOWLIST = {"asyncpg": {pkg, import_name}, "httpx": {pkg, import_name}}` — NO install di dep non in allowlist | Codex        | new constant + `_resolve_dep`                                                                                                   |
| **A4**  | TTL su outcome=`started` = 600s (orphan attempts cleanup)                                                                               | Gemini       | `_attempts_recent_count` filter                                                                                                 |
| **A5**  | Atomic lock `fcntl.flock` on attempts file                                                                                              | Codex        | `_record_attempt` + `_attempts_recent_count`                                                                                    |
| **A6**  | Python path lockdown: solo `~/.pyenv/versions/X.Y.Z/bin/python<v>` regex match                                                          | Codex+Gemini | `_validate_python_path` con regex `re.fullmatch(r"^.+/\.pyenv/versions/\d+\.\d+\.\d+/bin/python(?:\d+(?:\.\d+)?)?$", resolved)` |
| **A7**  | Fail-closed on corrupt attempts file (return -1 → quarantine, NOT 0)                                                                    | Codex        | `_attempts_recent_count`                                                                                                        |
| **A8**  | Sanitize env: `env -i` style, blocca tutti `PIP_*` attacker-controlled vars                                                             | Codex        | `_execute` builds clean env dict                                                                                                |
| **A9**  | `await verify_proc.wait()` post-kill on timeout                                                                                         | Codex bug #6 | `_execute` verify path                                                                                                          |
| **A10** | YAML rule `cooldown_minutes=10` (was 5, panel inconsistent con anti-loop 3/24h)                                                         | Codex bug #8 | `rules/base.yaml`                                                                                                               |

Bonus panel finding (Codex bug #2): **params key mismatch** spec dice `payload.missing_module` → YAML mapping `params: {dep: "{payload.missing_module}"}` → actuator reads `params["dep"]`. Spec iter-2 esplicita questo mapping in YAML rule + `_execute` accept solo `dep` key (NOT `missing_module`).

## Architettura empirica (re-verified 2026-05-26)

- Base class: `apps/organism/organism/actuators/base.py` lines 1-131 — `async run(*, params, correlation_id, dry_run)` automatically:
  - Writes WAL `~/logs/organism/wal/<name>-<exec_id>.json`
  - Emits `<name>_done` or `<name>_failed` event
  - Calls `incident_ledger.record_outcome(done/failed)` (W37)
- Pattern reference: `apps/organism/organism/actuators/fly_machines_restart.py` (W31 lines 1-93)
- W37 ledger: `apps/organism/organism/supervisor/incident_ledger.py` — `record_dispatch()` called by `Dispatcher.dispatch()` line 224, `record_outcome()` called by base.py lines 60-69 (done) and 83-95 (failed)
- Dispatcher `_target_key`: `f"{decision.actuator}:{target}"` line 110 — mutex/CB scoped by (actuator, target) tuple → **due deps diversi NON si bloccano** (target = dep_name). Open question #1 RESOLVED.
- SAFE_ACTUATORS frozenset: line 34-56 of dispatch.py
- W33 kill switch: `apps/cell/cell/core/pulse.py:56-82` — `CELL_AUTOREMEDIATION_ENABLED` default-on
- W36 stale-event TTL: 60min outbox replay guard (NO interferenza con 24h attempts TTL — diversi domini)
- W37 valid outcomes (migration 195 CHECK): dispatch ∈ {dispatched, deferred\_\*, rejected_unknown, awaiting_human, shadow_logged}; terminal ∈ {done, failed}

## CRITICAL empirical discovery (2026-05-26 19:18)

Live `~/logs/wa-mirror-attention-classifier.err.log` tail shows current breakage is **NOT** ModuleNotFoundError (Layer A wrapper resolved that). Current breakage is:

```
asyncpg.exceptions.InvalidPasswordError: password authentication failed for user "nuzantara"
```

Implication for Step 4 sensor:

- exit code 1 alone is INSUFFICIENT discriminator
- Sensor MUST parse stderr log to extract `error_class` (Python exception classname)
- Only ModuleNotFoundError → dispatch python_env_repair
- InvalidPasswordError, ConnectionRefusedError, etc → log + skip (awaiting_human / defer)

This shapes Step 4 sensor logic (separate spec — but documented here for completeness).

## Skeleton classe (iter-2, all amendments applied)

```python
"""python_env_repair actuator — auto-installs missing Python deps via pip.

PANEL-AMENDED iter-2 (2026-05-26): 10 must-fix items A1-A10 applied.

Triggered when Cell sustained_red emits cell_pulse_sustained_red with
payload.target_app="wa-mirror-enrichment", payload.metadata.error_class="ModuleNotFoundError",
payload.metadata.missing_module="<name>", payload.metadata.python_path="<abs path>".

Anti-loop: disk-based attempts counter per (dep, python_path), TTL 24h, max 3.
            Orphan "started" entries auto-cleaned at 600s (A4).
            Lock via fcntl.flock (A5). Fail-closed on corrupt file (A7).
Kill switch: CELL_AUTOREMEDIATION_ENABLED env var (default-on, W33).
Security:   - package name allowlist explicit dict NOT regex (A3)
            - regex validator uses fullmatch + control-char block (A2)
            - python path strict pyenv versions/X.Y.Z regex (A6)
            - subprocess env sanitized via env -i pattern (A8)
            - --index-url https://pypi.org/simple/ pinned (A1)
            - --no-input flag (A1)
Ledger:    W37 record_dispatch + record_outcome called by base.py automatically.
"""
import asyncio
import fcntl
import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Optional

from organism.actuators.base import ActuatorBase


# A3: Explicit allowlist — module → (pip pkg, import name). NO PyPI install
# di dep non in allowlist. Future ops: extend with explicit operator review.
_DEP_ALLOWLIST: dict[str, dict[str, str]] = {
    "asyncpg": {"pkg": "asyncpg>=0.29", "import_name": "asyncpg"},
    "httpx":   {"pkg": "httpx>=0.27",   "import_name": "httpx"},
}

# A2: fullmatch + block control chars + version spec. Used as last-line
# defense — allowlist (A3) is the primary gate.
_PKG_WHITELIST_RE = re.compile(
    r"\A[a-zA-Z][a-zA-Z0-9_\-]{0,79}"
    r"(\[[a-zA-Z0-9_,\-]{1,30}\])?"
    r"(?:(==|>=|<=|<|>|~=|!=)[0-9][a-zA-Z0-9.\-+]{0,30})?\Z"
)

# A6: Python path lockdown. Only pyenv versions/X.Y.Z/bin/pythonN(.N).
# Allows /opt/homebrew/bin/python ONLY if symlink to pyenv version.
_PY_PATH_RE = re.compile(
    r"\A.+/\.pyenv/versions/\d+\.\d+\.\d+/bin/python(?:\d+(?:\.\d+)?)?\Z"
)


class PythonEnvRepair(ActuatorBase):
    name = "python_env_repair"

    ATTEMPTS_DIR = Path.home() / ".agent" / "decisions" / "python_env_repair_attempts"
    PIP_MAX_ATTEMPTS = 3
    ATTEMPTS_TTL_SECONDS = 24 * 3600          # 24h
    ORPHAN_STARTED_TTL_SECONDS = 600          # A4 — 10min
    PIP_TIMEOUT_SECONDS = 120
    VERIFY_TIMEOUT_SECONDS = 15

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    def _validate_pkg(self, dep: str) -> str:
        """A2: fullmatch + block newline/control chars + length bound.

        Raises ValueError on injection attempt.
        """
        if not isinstance(dep, str) or not (1 <= len(dep) <= 80):
            raise ValueError("Invalid dep: type/length out of bounds")
        # A2: explicit control-char block (regex \A...\Z is fullmatch but
        # explicit defense-in-depth — no \n \r \t \0 anywhere)
        if any(c in dep for c in "\n\r\t\0\x0b\x0c"):
            raise ValueError(f"Invalid package name (control chars): {dep!r}")
        if not _PKG_WHITELIST_RE.fullmatch(dep):
            raise ValueError(f"Invalid package name rejected: {dep!r}")
        return dep

    def _resolve_dep(self, requested: str) -> tuple[str, str]:
        """A3: resolve module name → (pip pkg spec, import name) via allowlist.

        Codex bug #3 also covered here: import-name vs pkg-name distinction
        (e.g. PyYAML pkg → yaml import). Allowlist tracks both.

        Raises ValueError if not in allowlist.
        """
        # Strip dotted submodule path (Gemini must-fix #2: asyncpg.exceptions → asyncpg)
        root_module = requested.split(".", 1)[0]
        # Strip extras/version if present in incoming payload
        root_module = re.split(r"[\[<>=~!]", root_module, maxsplit=1)[0]

        if root_module not in _DEP_ALLOWLIST:
            raise ValueError(
                f"Dependency {root_module!r} not in allowlist "
                f"(allowed: {sorted(_DEP_ALLOWLIST)})"
            )
        entry = _DEP_ALLOWLIST[root_module]
        return entry["pkg"], entry["import_name"]

    def _validate_python_path(self, path: str) -> str:
        """A6: strict pyenv versions/X.Y.Z/bin/python(N.N)? path lockdown.

        Resolves symlinks (realpath) before regex match. Requires:
          - path matches /.pyenv/versions/X.Y.Z/bin/pythonN(.N)?
          - file exists, is regular file, is executable
        """
        resolved = os.path.realpath(path)
        if not _PY_PATH_RE.fullmatch(resolved):
            raise ValueError(
                f"Python path not in pyenv versions whitelist: {resolved}"
            )
        if not os.path.isfile(resolved) or not os.access(resolved, os.X_OK):
            raise ValueError(f"Python path not executable: {resolved}")
        return resolved

    # ------------------------------------------------------------------
    # Kill switch & attempts persistence (A5 lock, A7 fail-closed)
    # ------------------------------------------------------------------

    def _check_kill_switch(self) -> bool:
        """W33: returns False if CELL_AUTOREMEDIATION_ENABLED is disabled."""
        val = os.environ.get("CELL_AUTOREMEDIATION_ENABLED", "").strip().lower()
        return val not in {"false", "0", "no", "off", "disabled"}

    def _attempts_file(self, dep: str, python_path: str) -> Path:
        """Hash (dep, python_path) for stable disk key across envs."""
        key = hashlib.sha256(f"{dep}|{python_path}".encode()).hexdigest()[:16]
        return self.ATTEMPTS_DIR / f"{key}.jsonl"

    def _attempts_recent_count(self, dep: str, python_path: str) -> int:
        """A4 + A5 + A7: count recent failed attempts within TTL.

        - A4: outcome=`started` records older than ORPHAN_STARTED_TTL_SECONDS
          are skipped (orphans from killed processes don't permanently
          quarantine).
        - A5: fcntl.flock LOCK_SH shared lock during read.
        - A7: on corrupt file (JSON parse error), return -1 — caller treats
          as "fail-closed, quarantine".

        Returns:
            -1 if file is corrupt (fail-closed → caller quarantines)
             N count of attempts in TTL window
        """
        f = self._attempts_file(dep, python_path)
        if not f.exists():
            return 0
        cutoff_normal = time.time() - self.ATTEMPTS_TTL_SECONDS
        cutoff_started = time.time() - self.ORPHAN_STARTED_TTL_SECONDS

        count = 0
        try:
            with f.open("r") as fp:
                fcntl.flock(fp.fileno(), fcntl.LOCK_SH)
                try:
                    text = fp.read()
                finally:
                    fcntl.flock(fp.fileno(), fcntl.LOCK_UN)

            for line in text.splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)  # raises on corrupt
                ts = rec.get("ts", 0)
                outcome = rec.get("outcome", "")
                if outcome == "started":
                    # A4: orphan started TTL
                    if ts >= cutoff_started:
                        count += 1
                elif outcome in {"pip_failed", "verify_failed", "quarantine_blocked"}:
                    if ts >= cutoff_normal:
                        count += 1
                # success / other outcomes don't count toward quarantine
            return count
        except (json.JSONDecodeError, OSError):
            # A7: fail-closed on corruption — return -1 to caller
            return -1

    def _record_attempt(
        self,
        dep: str,
        python_path: str,
        outcome: str,
        error: str = "",
    ) -> None:
        """A5: atomic append with fcntl.flock LOCK_EX."""
        self.ATTEMPTS_DIR.mkdir(parents=True, exist_ok=True)
        f = self._attempts_file(dep, python_path)
        rec = {"ts": time.time(), "dep": dep, "outcome": outcome}
        if error:
            rec["error"] = error[:500]
        try:
            with f.open("a") as fp:
                fcntl.flock(fp.fileno(), fcntl.LOCK_EX)
                try:
                    fp.write(json.dumps(rec) + "\n")
                    fp.flush()
                    os.fsync(fp.fileno())
                finally:
                    fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
        except OSError:
            # Best-effort: failing to record is non-fatal (we'll just retry
            # at next pulse). Don't crash the actuator.
            pass

    # ------------------------------------------------------------------
    # Subprocess argv (A1 index-pin + A8 env-sanitize)
    # ------------------------------------------------------------------

    def _build_argv(self, python_path: str, pkg_spec: str) -> list[str]:
        """A1: --index-url + --no-input + --quiet + --disable-pip-version-check."""
        return [
            python_path, "-m", "pip", "install",
            "--quiet",
            "--no-input",
            "--disable-pip-version-check",
            "--index-url", "https://pypi.org/simple/",
            pkg_spec,
        ]

    def _build_sanitized_env(self) -> dict[str, str]:
        """A8: build a minimal env that excludes all PIP_* and proxy/config
        vars potentially controlled by an attacker.

        Allow only HOME, PATH (pinned), LANG, LC_ALL.
        """
        return {
            "HOME": os.environ.get("HOME", str(Path.home())),
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
            "LANG": os.environ.get("LANG", "en_US.UTF-8"),
            "LC_ALL": os.environ.get("LC_ALL", "en_US.UTF-8"),
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        }

    # ------------------------------------------------------------------
    # _execute (main path)
    # ------------------------------------------------------------------

    async def _execute(self, params: dict) -> dict:
        # 0. Kill switch (W33)
        if not self._check_kill_switch():
            return {"skipped": "kill_switch_active"}

        # 1. Validate inputs (raise ValueError → caught by base.run() → ledger=failed)
        raw_dep = params.get("dep", "")
        python_path_raw = params.get(
            "python_path",
            "/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3.11",
        )

        # A2 + A3 + A6 validation
        _ = self._validate_pkg(raw_dep)  # syntactic check on raw input
        pkg_spec, import_name = self._resolve_dep(raw_dep)
        # A2 again on resolved pkg_spec (defense-in-depth)
        self._validate_pkg(pkg_spec)
        python_path = self._validate_python_path(python_path_raw)

        # 2. Anti-loop check (A4 + A5 + A7)
        recent = self._attempts_recent_count(pkg_spec, python_path)
        if recent < 0:
            # A7: corrupt attempts file → fail-closed
            self._record_attempt(
                pkg_spec, python_path, "quarantine_blocked",
                "attempts file corrupt",
            )
            raise RuntimeError(
                f"python_env_repair: attempts file corrupt for {pkg_spec!r}, "
                f"quarantining for safety"
            )
        if recent >= self.PIP_MAX_ATTEMPTS:
            self._record_attempt(pkg_spec, python_path, "quarantine_blocked")
            raise RuntimeError(
                f"python_env_repair: quarantine for {pkg_spec!r} on "
                f"{python_path} — {recent} failed attempts in last 24h"
            )

        # 3. pip install (A1 argv + A8 sanitized env)
        self._record_attempt(pkg_spec, python_path, "started")
        argv = self._build_argv(python_path, pkg_spec)
        env = self._build_sanitized_env()

        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            out, err = await asyncio.wait_for(
                proc.communicate(), timeout=self.PIP_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()  # A9: wait for kill to settle
            except ProcessLookupError:
                pass
            self._record_attempt(pkg_spec, python_path, "pip_failed", "timeout")
            raise RuntimeError(
                f"pip install {pkg_spec!r} timed out after {self.PIP_TIMEOUT_SECONDS}s"
            )

        if proc.returncode != 0:
            err_text = err.decode("utf-8", errors="replace")
            self._record_attempt(pkg_spec, python_path, "pip_failed", err_text)
            raise RuntimeError(
                f"pip install {pkg_spec!r} exited {proc.returncode}: "
                f"{err_text[:200]}"
            )

        # 4. Verify import (using allowlist-resolved import_name, NOT derived)
        verify_proc = await asyncio.create_subprocess_exec(
            python_path, "-c", f"import {import_name}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            _, verr = await asyncio.wait_for(
                verify_proc.communicate(), timeout=self.VERIFY_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            try:
                verify_proc.kill()
                await verify_proc.wait()  # A9
            except ProcessLookupError:
                pass
            self._record_attempt(
                pkg_spec, python_path, "verify_failed", "timeout"
            )
            raise RuntimeError(f"import verify timed out for {import_name!r}")

        if verify_proc.returncode != 0:
            verr_text = verr.decode("utf-8", errors="replace")
            self._record_attempt(
                pkg_spec, python_path, "verify_failed", verr_text
            )
            raise RuntimeError(
                f"import {import_name} failed after install: "
                f"{verr_text[:200]}"
            )

        # 5. Success
        self._record_attempt(pkg_spec, python_path, "success")
        return {
            "dep": raw_dep,
            "pkg_spec": pkg_spec,
            "python_path": python_path,
            "import_name": import_name,
            "stdout_tail": out.decode("utf-8", errors="replace")[-500:],
        }

    async def _dry_run(self, params: dict) -> dict:
        """Dry-run with validation (per Codex bug #7 — don't show fooling argv)."""
        raw_dep = params.get("dep", "<missing>")
        python_path_raw = params.get(
            "python_path",
            "/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3.11",
        )
        # Best-effort validation in dry-run mode (don't crash on invalid;
        # just report it).
        try:
            self._validate_pkg(raw_dep)
            pkg_spec, import_name = self._resolve_dep(raw_dep)
        except ValueError as exc:
            return {
                "would_validate_pkg": raw_dep,
                "validation_error": str(exc),
                "kill_switch_active": not self._check_kill_switch(),
            }
        try:
            python_path = self._validate_python_path(python_path_raw)
        except ValueError as exc:
            return {
                "would_validate_pkg": raw_dep,
                "would_validate_python_path": python_path_raw,
                "validation_error": str(exc),
                "kill_switch_active": not self._check_kill_switch(),
            }
        return {
            "would_validate_pkg": raw_dep,
            "would_pkg_spec": pkg_spec,
            "would_import_name": import_name,
            "would_python_path": python_path,
            "would_argv": self._build_argv(python_path, pkg_spec),
            "anti_loop_recent": self._attempts_recent_count(pkg_spec, python_path),
            "kill_switch_active": not self._check_kill_switch(),
        }
```

## Integration patches (iter-2)

### 1. `apps/organism/organism/actuators/__init__.py`

Add import + export + registry:

```python
from organism.actuators.python_env_repair import PythonEnvRepair

__all__ = [..., "PythonEnvRepair"]

def build_actuator_registry(*, redis) -> dict[str, ActuatorBase]:
    return {
        ...,
        PythonEnvRepair.name: PythonEnvRepair(),
    }
```

### 2. `apps/organism/organism/supervisor/dispatch.py` SAFE_ACTUATORS

```python
SAFE_ACTUATORS = frozenset({
    ... existing 12 ...
    # W57 (2026-05-26): auto-install missing Python deps on
    # wa-mirror-enrichment failure. Allowlist explicit (only asyncpg+httpx
    # for now). Idempotent on already-installed deps (pip install is no-op).
    "python_env_repair",
})
```

### 3. `apps/organism/organism/rules/base.yaml` (append)

**A10**: cooldown_minutes=10 (consistent with pip timeout 120s + verify 15s + buffer for backoff).

```yaml
# W57 (2026-05-26): wa-mirror enrichment auto-install missing Python deps.
# Triggered when Cell sustained_red detects ModuleNotFoundError class on
# wa-mirror-enrichment organ. Cooldown 10min to prevent dispatch storm
# during a slow pip install (pip timeout=120s + buffer).
- id: enrichment_dep_missing_repair
  match:
    kind: cell_pulse_sustained_red
    payload.app: "wa-mirror-enrichment"
    payload.metadata.error_class: "ModuleNotFoundError"
  action:
    actuator: python_env_repair
    params:
      dep: "{payload.metadata.missing_module}"
      python_path: "{payload.metadata.python_path}"
  confidence: 0.92
  cooldown_minutes: 10
```

NOTE: payload structure exists (see `cell_core/observatory.py:emit_sustained_red`). `payload.app` and `payload.metadata.<...>` are both supported via the matcher.

## Test coverage (14 unit tests, panel-amended)

File: `apps/organism/tests/test_python_env_repair.py`

| #   | Test                                                      | Validates                                                   |
| --- | --------------------------------------------------------- | ----------------------------------------------------------- |
| 1   | `test_validate_pkg_bare_name`                             | A2: "asyncpg" accepted                                      |
| 2   | `test_validate_pkg_versioned`                             | A2: "asyncpg>=0.29" accepted                                |
| 3   | `test_validate_pkg_extras`                                | A2: "httpx[http2]>=0.27" accepted                           |
| 4   | `test_validate_pkg_blocks_semicolon`                      | A2: "asyncpg; rm -rf /" raises ValueError                   |
| 5   | `test_validate_pkg_blocks_newline`                        | A2: "asyncpg\nls" raises ValueError                         |
| 6   | `test_validate_pkg_blocks_shell_metachar`                 | A2: "asyncpg&" raises ValueError                            |
| 7   | `test_resolve_dep_allowlist_known`                        | A3: "asyncpg" → ("asyncpg>=0.29", "asyncpg")                |
| 8   | `test_resolve_dep_allowlist_dotted_path`                  | A3 + Gemini #2: "asyncpg.exceptions" → asyncpg root         |
| 9   | `test_resolve_dep_allowlist_unknown_blocks`               | A3: "malicious_pkg" raises ValueError                       |
| 10  | `test_validate_python_path_pyenv_ok`                      | A6: pyenv version path accepted                             |
| 11  | `test_validate_python_path_blocks_arbitrary`              | A6: /tmp/python blocks                                      |
| 12  | `test_attempts_recent_count_orphan_started_ttl`           | A4: started ts > 600s ago not counted                       |
| 13  | `test_attempts_recent_count_corrupt_file_returns_neg_one` | A7: fail-closed                                             |
| 14  | `test_dry_run_invalid_dep_no_crash`                       | Codex bug #7: dry_run on invalid input doesn't toggle state |
| 15  | `test_build_argv_has_index_url_and_no_input`              | A1: --index-url + --no-input present                        |
| 16  | `test_kill_switch_disabled_returns_skipped`               | W33: env=false → {"skipped": "kill_switch_active"}          |
| 17  | `test_registry_includes`                                  | Integration: `build_actuator_registry()` returns it         |
| 18  | `test_safe_actuators_includes`                            | Security: SAFE_ACTUATORS whitelist contains name            |
| 19  | `test_name_attribute`                                     | Class attribute correct                                     |

(Started at 14, ended at 19 — coverage of A1-A10 requires this many.)

## Coordination notes

- **Dispatcher target**: Cell yaml-rule passes `dep` as param value. Dispatcher computes `_target_key = "python_env_repair:<dep_name>"`. Mutex/CB scoped per-dep → asyncpg install doesn't block httpx install (Open Question #1 resolved).
- **W36 interaction**: stale-event TTL on outbox replay is 60min. Anti-loop TTL is 24h. They don't conflict — even if a stale event replays after 60min, the anti-loop sees recent attempts and quarantines.
- **W37 ledger**: base.py automatically writes `record_outcome(done/failed)`. Spec iter-1 was correct that we don't call manually.
- **Open question #6 (24h TTL)**: panel did not converge. Keep 24h for now (matches W31 `cooldown_minutes=10` × 144 ticks/day = single auto-retry per day max if cooldown alone fails). If field experience shows 24h too long, reduce to 6h in iter-3.

## Cosa NON è in scope iter-2

- pip uninstall (only install — anti-attacker)
- pip --upgrade (only fresh installs)
- uv variant (defer until pip proves slow in field)
- Cell sensor (separate Step 4 spec)

## Sign-off checklist

- [x] 10 panel must-fix A1-A10 applied
- [x] Codex bug #2 (params key mismatch) addressed via explicit YAML mapping
- [x] Codex bug #3 (import-name vs pkg-name) addressed via allowlist tuple
- [x] Codex bug #6 (await proc.wait() post-kill) applied in A9
- [x] Codex bug #7 (dry_run on invalid input) addressed in `_dry_run`
- [x] Codex bug #8 (YAML cooldown vs pip timeout) addressed in A10
- [x] Codex security #1 (supply-chain index pinning) A1
- [x] Codex security #2 (env mutation business allowlist) A3
- [x] Codex security #3 (PATH/config injection sanitize env) A8
- [x] Codex security #4 (race condition no atomic lock) A5
- [x] Codex security #5 (DoS via many installs) covered by per-dep CB + max_attempts
- [x] All paths empirical-verified 2026-05-26
- [x] No mocked tool output anywhere in this spec — every file path was Read'd or ls'd in this turn

Ready for implementation. Estimated LOC ~300 (actuator) + ~250 (test) + YAML + dispatch + **init**.
