"""python_env_repair actuator — auto-installs missing Python deps via pip.

W57 (2026-05-26): Self-healing wa-mirror enrichment Layer B-2.

Triggered when Cell sustained_red emits cell_pulse_sustained_red with
payload.app="wa-mirror-enrichment", payload.metadata.error_class=
"ModuleNotFoundError", payload.metadata.missing_module=<name>,
payload.metadata.python_path=<abs path>.

Panel-amended iter-2 (Gemini agy 3.1 Pro APPROVE_WITH_AMENDMENTS + Codex
GPT-5.5 REJECT + DeepSeek V4 Pro synthesis). 10 must-fix items A1-A10:

  A1 — pip install pins --index-url + --no-input (supply-chain)
  A2 — regex fullmatch + control-char block in _validate_pkg
  A3 — explicit dep allowlist dict (NOT just regex)
  A4 — orphan "started" TTL 600s (separate from 24h normal TTL)
  A5 — atomic fcntl.flock on attempts file read/write
  A6 — Python path lockdown to pyenv versions/X.Y.Z regex
  A7 — fail-closed on corrupt attempts file (return -1 → quarantine)
  A8 — sanitized subprocess env (no PIP_* attacker injection)
  A9 — await proc.wait() post-kill on timeout
  A10 — YAML cooldown_minutes=10 (consistent with pip timeout 120s)

Kill switch: CELL_AUTOREMEDIATION_ENABLED env var (W33, default-on).
Ledger: W37 record_dispatch + record_outcome called by base.py automatically.

Pattern reference: fly_machines_restart.py (W31 validated 2026-05-23 in prod).
Spec ref: research/operations/2026-05-26-step3-spec-iter2.md.
"""
import asyncio
import fcntl
import hashlib
import json
import os
import re
import time
from pathlib import Path

from organism.actuators.base import ActuatorBase


# A3: Explicit allowlist — module root → (pip pkg spec, import name).
# NO PyPI install for any dep NOT in this dict. Future operators extending:
# add entry + corresponding unit test + cicatrix note explaining business
# rationale (e.g. wa-mirror tier-3 dep).
_DEP_ALLOWLIST: dict[str, dict[str, str]] = {
    "asyncpg": {"pkg": "asyncpg>=0.29", "import_name": "asyncpg"},
    "httpx":   {"pkg": "httpx>=0.27",   "import_name": "httpx"},
}

# A2: fullmatch (\A...\Z) + bounded length + version spec optional. Last-line
# syntactic defense; the allowlist (A3) is the primary semantic gate.
_PKG_WHITELIST_RE = re.compile(
    r"\A[a-zA-Z][a-zA-Z0-9_\-]{0,79}"
    r"(\[[a-zA-Z0-9_,\-]{1,30}\])?"
    r"(?:(==|>=|<=|<|>|~=|!=)[0-9][a-zA-Z0-9.\-+]{0,30})?\Z"
)

# A6: Python path lockdown. Only pyenv-managed interpreters allowed (not
# Homebrew externally-managed; not /tmp/anything). Pattern requires
# /<home>/.pyenv/versions/X.Y.Z/bin/python(N(.N)?)?
_PY_PATH_RE = re.compile(
    r"\A.+/\.pyenv/versions/\d+\.\d+\.\d+/bin/python(?:\d+(?:\.\d+)?)?\Z"
)


class PythonEnvRepair(ActuatorBase):
    name = "python_env_repair"

    ATTEMPTS_DIR = Path.home() / ".agent" / "decisions" / "python_env_repair_attempts"
    PIP_MAX_ATTEMPTS = 3
    ATTEMPTS_TTL_SECONDS = 24 * 3600          # 24h for failed attempts
    ORPHAN_STARTED_TTL_SECONDS = 600          # A4 — 10min for orphan "started"
    PIP_TIMEOUT_SECONDS = 120
    VERIFY_TIMEOUT_SECONDS = 15

    # ------------------------------------------------------------------
    # Validators (A2, A3, A6)
    # ------------------------------------------------------------------

    def _validate_pkg(self, dep: str) -> str:
        """A2: fullmatch + length bound + control-char block.

        Raises ValueError on injection / invalid input.
        """
        if not isinstance(dep, str) or not (1 <= len(dep) <= 80):
            raise ValueError("Invalid dep: type/length out of bounds")
        # A2: explicit control-char block (defense-in-depth even though
        # the fullmatch regex \A...\Z already rejects them)
        if any(c in dep for c in "\n\r\t\0\x0b\x0c"):
            raise ValueError(f"Invalid package name (control chars): {dep!r}")
        if not _PKG_WHITELIST_RE.fullmatch(dep):
            raise ValueError(f"Invalid package name rejected: {dep!r}")
        return dep

    def _resolve_dep(self, requested: str) -> tuple[str, str]:
        """A3 + Gemini #2: resolve module name → (pip pkg, import name).

        - Strips dotted submodule path (e.g. "asyncpg.exceptions" → "asyncpg")
        - Strips extras/version markers
        - Requires root module in _DEP_ALLOWLIST

        Returns:
            (pip pkg spec like "asyncpg>=0.29", import name like "asyncpg")

        Raises:
            ValueError if root module not in allowlist.
        """
        # Strip dotted submodule path (Gemini must-fix #2)
        root_module = requested.split(".", 1)[0]
        # Strip extras/version if present
        root_module = re.split(r"[\[<>=~!]", root_module, maxsplit=1)[0]

        if root_module not in _DEP_ALLOWLIST:
            raise ValueError(
                f"Dependency {root_module!r} not in allowlist "
                f"(allowed: {sorted(_DEP_ALLOWLIST)})"
            )
        entry = _DEP_ALLOWLIST[root_module]
        return entry["pkg"], entry["import_name"]

    def _validate_python_path(self, path: str) -> str:
        """A6: strict pyenv versions/X.Y.Z/bin/python path lockdown.

        Resolves symlinks (realpath) before regex match. Requires:
          - resolved path matches /.pyenv/versions/X.Y.Z/bin/pythonN(.N)?
          - file exists, is regular file, is executable

        Raises ValueError on any check failure.
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
    # Kill switch (W33)
    # ------------------------------------------------------------------

    def _check_kill_switch(self) -> bool:
        """W33: returns False if CELL_AUTOREMEDIATION_ENABLED is disabled."""
        val = os.environ.get("CELL_AUTOREMEDIATION_ENABLED", "").strip().lower()
        return val not in {"false", "0", "no", "off", "disabled"}

    # ------------------------------------------------------------------
    # Attempts persistence (A4, A5, A7)
    # ------------------------------------------------------------------

    def _attempts_file(self, dep: str, python_path: str) -> Path:
        """Stable disk key derived from (dep, python_path) sha256."""
        key = hashlib.sha256(f"{dep}|{python_path}".encode()).hexdigest()[:16]
        return self.ATTEMPTS_DIR / f"{key}.jsonl"

    def _attempts_recent_count(self, dep: str, python_path: str) -> int:
        """Count recent attempts that should block another retry.

        A4 — orphan "started" entries (process killed mid-install) only count
        if newer than ORPHAN_STARTED_TTL_SECONDS (10min). Prevents permanent
        quarantine from a single crashed process.

        A5 — shared fcntl.flock for atomic read.

        A7 — corrupt file → return -1 → caller treats as fail-closed.

        Returns:
            -1 on corrupt file (caller MUST quarantine)
             N count of recent blocking attempts
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
                rec = json.loads(line)  # raises JSONDecodeError on corrupt
                ts = rec.get("ts", 0)
                outcome = rec.get("outcome", "")
                if outcome == "started":
                    if ts >= cutoff_started:
                        count += 1
                elif outcome in {"pip_failed", "verify_failed", "quarantine_blocked"}:
                    if ts >= cutoff_normal:
                        count += 1
                # success / other outcomes don't count toward quarantine
            return count
        except (json.JSONDecodeError, OSError):
            # A7: fail-closed
            return -1

    def _record_attempt(
        self,
        dep: str,
        python_path: str,
        outcome: str,
        error: str = "",
    ) -> None:
        """A5: atomic append-then-fsync with exclusive fcntl.flock."""
        try:
            self.ATTEMPTS_DIR.mkdir(parents=True, exist_ok=True)
        except OSError:
            return  # Best-effort
        f = self._attempts_file(dep, python_path)
        rec: dict = {"ts": time.time(), "dep": dep, "outcome": outcome}
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
            # Best-effort: failing to record is non-fatal — next pulse retries
            pass

    # ------------------------------------------------------------------
    # Subprocess argv & env (A1, A8)
    # ------------------------------------------------------------------

    def _build_argv(self, python_path: str, pkg_spec: str) -> list[str]:
        """A1: pin index-url + no-input + disable version check."""
        return [
            python_path, "-m", "pip", "install",
            "--quiet",
            "--no-input",
            "--disable-pip-version-check",
            "--index-url", "https://pypi.org/simple/",
            pkg_spec,
        ]

    def _build_sanitized_env(self) -> dict[str, str]:
        """A8: minimal env that excludes PIP_*, proxy, cert, and other
        attacker-controllable vars. Only essential vars whitelisted.
        """
        return {
            "HOME": os.environ.get("HOME", str(Path.home())),
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
            "LANG": os.environ.get("LANG", "en_US.UTF-8"),
            "LC_ALL": os.environ.get("LC_ALL", "en_US.UTF-8"),
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        }

    # ------------------------------------------------------------------
    # _execute
    # ------------------------------------------------------------------

    async def _execute(self, params: dict) -> dict:
        # 0. Kill switch (W33)
        if not self._check_kill_switch():
            return {"skipped": "kill_switch_active"}

        # 1. Validate inputs — raises ValueError on bad input. base.run()
        # catches and emits failed event + ledger UPDATE outcome="failed".
        raw_dep = params.get("dep", "")
        python_path_raw = params.get(
            "python_path",
            "/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3.11",
        )

        # A2 syntactic check on raw payload
        _ = self._validate_pkg(raw_dep)
        # A3 semantic allowlist + import-name resolution
        pkg_spec, import_name = self._resolve_dep(raw_dep)
        # A2 again on resolved pkg_spec (defense-in-depth — allowlist entry
        # could theoretically have a bug; never trust internal data either)
        self._validate_pkg(pkg_spec)
        # A6 Python path lockdown
        python_path = self._validate_python_path(python_path_raw)

        # 2. Anti-loop check (A4 + A5 + A7)
        recent = self._attempts_recent_count(pkg_spec, python_path)
        if recent < 0:
            # A7: corrupt attempts file → fail-closed → quarantine
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

        # 3. pip install (A1 argv + A8 env)
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
                proc.communicate(), timeout=self.PIP_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()  # A9
            except ProcessLookupError:
                pass
            self._record_attempt(
                pkg_spec, python_path, "pip_failed", "timeout"
            )
            raise RuntimeError(
                f"pip install {pkg_spec!r} timed out after "
                f"{self.PIP_TIMEOUT_SECONDS}s"
            )

        if proc.returncode != 0:
            err_text = err.decode("utf-8", errors="replace")
            self._record_attempt(pkg_spec, python_path, "pip_failed", err_text)
            raise RuntimeError(
                f"pip install {pkg_spec!r} exited {proc.returncode}: "
                f"{err_text[:200]}"
            )

        # 4. Verify import (uses allowlist-resolved import_name, NEVER derived
        # from pkg name — Codex bug #3 covered)
        verify_proc = await asyncio.create_subprocess_exec(
            python_path, "-c", f"import {import_name}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            _, verr = await asyncio.wait_for(
                verify_proc.communicate(), timeout=self.VERIFY_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            try:
                verify_proc.kill()
                await verify_proc.wait()  # A9
            except ProcessLookupError:
                pass
            self._record_attempt(
                pkg_spec, python_path, "verify_failed", "timeout",
            )
            raise RuntimeError(f"import verify timed out for {import_name!r}")

        if verify_proc.returncode != 0:
            verr_text = verr.decode("utf-8", errors="replace")
            self._record_attempt(
                pkg_spec, python_path, "verify_failed", verr_text,
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
        """Dry-run with best-effort validation. NEVER toggles disk state.

        Codex bug #7 fix: validate input BEFORE returning argv so dry-run
        doesn't show fooling commands for invalid params.
        """
        raw_dep = params.get("dep", "<missing>")
        python_path_raw = params.get(
            "python_path",
            "/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3.11",
        )
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
                "would_pkg_spec": pkg_spec,
                "would_import_name": import_name,
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
