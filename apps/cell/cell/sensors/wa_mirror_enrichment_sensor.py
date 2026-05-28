"""WaMirrorEnrichmentSensor — monitors 3 wa-mirror attention LaunchAgents.

W57 (2026-05-26): Self-healing wa-mirror enrichment Layer B-3 sensor.

Probes 3 LaunchAgent labels via `launchctl print gui/<uid>/<label>`:
  - com.balizero.wa-mirror-attention-classifier  (5min cadence)
  - com.balizero.wa-mirror-attention-realtime    (10min cadence)
  - com.balizero.wa-mirror-attention-digest      (24h cadence, optional)

Health rules:
  - GREEN  — ALL three have last_exit_code == 0
  - YELLOW — at least one has last_exit_code != 0 AND != 75 (75=EX_TEMPFAIL,
             transient — Layer A wrapper emits this when pip install fails
             and launchd will retry on next StartInterval, no Organism action)
  - RED    — same condition as YELLOW (sensor doesn't escalate to RED on its
             own; the streak-counter in pulse.py owns the W27-style escalation
             to cell_pulse_sustained_red emit at threshold=3 consecutive).

When a non-zero+non-75 exit code is observed, sensor parses the stderr log
to extract the error class (Python exception classname). Only
`ModuleNotFoundError` triggers downstream enrichment_repair_request emit;
other classes (InvalidPasswordError, ConnectionRefusedError, etc.) are
yellow-but-unactionable and require operator intervention.

Pattern reference: cron_sensor.py + ollama_sensor.py.
Spec ref: research/operations/2026-05-26-step3-spec-iter2.md (CRITICAL section
on empirical InvalidPasswordError vs ModuleNotFoundError discrimination).
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("cell.sensors.wa_mirror_enrichment")


# Labels probed every pulse cycle. The sensor returns the worst signal
# across all three.
_DEFAULT_LABELS = (
    "com.balizero.wa-mirror-attention-classifier",
    "com.balizero.wa-mirror-attention-realtime",
    "com.balizero.wa-mirror-attention-digest",
)

# Mapping label → stderr log path (default macOS launchd output for these
# specific plists). Used to parse error_class on non-zero exit.
_DEFAULT_LOG_PATHS = {
    "com.balizero.wa-mirror-attention-classifier":
        "/Users/nuzantara/logs/wa-mirror-attention-classifier.err.log",
    "com.balizero.wa-mirror-attention-realtime":
        "/Users/nuzantara/logs/wa-mirror-attention-realtime.err.log",
    "com.balizero.wa-mirror-attention-digest":
        "/Users/nuzantara/logs/wa-mirror-attention-digest.err.log",
}

# Default Python interpreter expected by wa-mirror-enrichment wrapper.
# Note: Pro-only path. If wa-mirror-enrichment migrates to Mini-Pro2, this
# default must be updated. Override via constructor `python_path=`.
_DEFAULT_PYTHON_PATH = "/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3.11"

# Code-reviewer finding #2 (defense-in-depth): mirror the Organism actuator's
# _DEP_ALLOWLIST locally so the sensor pre-checks `missing_module` BEFORE
# marking the label repairable. Without this gate, an attacker writing to
# the stderr log file (world-readable on macOS) could inject any module name
# matching the regex \[\w.]+\ and the taint would propagate to all
# `cell_pulse_sustained_red` subscribers (pg-bridge, downstream Organism,
# any future consumer) before the actuator's A3 allowlist gate fires.
# Keep this list in sync with apps/organism/.../python_env_repair.py:_DEP_ALLOWLIST.
_SENSOR_REPAIR_ALLOWLIST: frozenset[str] = frozenset({
    "asyncpg",
    "httpx",
})

# Regex to extract ModuleNotFoundError(name='X') OR
# "ModuleNotFoundError: No module named 'X'" from stderr tail.
_MODULE_NOT_FOUND_RE = re.compile(
    r"ModuleNotFoundError:\s*No module named\s*['\"]([\w.]+)['\"]"
)

# Generic Python exception class extractor from final Traceback line.
# Examples we want to catch:
#   "asyncpg.exceptions.InvalidPasswordError: password authentication failed"
#   "ConnectionRefusedError: [Errno 61] Connection refused"
#   "ModuleNotFoundError: No module named 'asyncpg'"
# Final-line pattern: "<dotted.classname>: <message>"
_EXCEPTION_LINE_RE = re.compile(
    r"^([A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)*Error):"
)

# Tail bytes of stderr to scan for error class (avoids reading multi-MB log)
_STDERR_TAIL_BYTES = 8192


@dataclass
class LabelStatus:
    label: str
    state: str = "unknown"          # launchd state field (running/not running/...)
    runs: Optional[int] = None
    last_exit_code: Optional[int] = None
    error_class: Optional[str] = None        # Python exception class (if any)
    missing_module: Optional[str] = None     # populated if ModuleNotFoundError


@dataclass
class WaMirrorEnrichmentReading:
    status: str                        # "green" | "yellow" | "red"
    repairable: bool = False           # True if any label has ModuleNotFoundError
    labels: list[LabelStatus] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class WaMirrorEnrichmentSensor:
    """Probe wa-mirror enrichment LaunchAgents for failure signal.

    Returns a flat reading with:
      - status: green/yellow (this sensor never emits red — pulse.py W57
        streak counter owns red-escalation)
      - repairable: True iff any label has ModuleNotFoundError class
      - labels: per-label detail incl. parsed error_class + missing_module

    Anti-Telegram (Antonello rule 2026-05-26): sensor never sends alerts;
    only logs to cell logger. Downstream emit_enrichment_repair_request
    (called by pulse.py) is the only escalation path.
    """

    def __init__(
        self,
        labels: tuple[str, ...] = _DEFAULT_LABELS,
        log_paths: Optional[dict[str, str]] = None,
        python_path: str = _DEFAULT_PYTHON_PATH,
        launchctl_timeout: float = 5.0,
    ) -> None:
        self._labels = labels
        self._log_paths = log_paths or dict(_DEFAULT_LOG_PATHS)
        self._python_path = python_path
        self._timeout = launchctl_timeout

    # ------------------------------------------------------------------
    # launchctl introspection
    # ------------------------------------------------------------------

    def _launchctl_exit_code(self, label: str) -> tuple[Optional[int], Optional[int], str]:
        """Run `launchctl print gui/<uid>/<label>` and parse 3 fields.

        Returns: (last_exit_code, runs, state) — any may be None if not
        parseable from output (e.g. label not registered).
        """
        uid = os.getuid()
        target = f"gui/{uid}/{label}"
        try:
            proc = subprocess.run(
                ["launchctl", "print", target],
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=False,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            logger.warning(
                "WaMirrorEnrichmentSensor: launchctl probe failed (%s): %s",
                label, exc,
            )
            return None, None, "probe_failed"

        # launchctl returns non-zero if the label is not loaded — but we
        # still want to return what we got (the output is empty in that case)
        text = (proc.stdout or "") + (proc.stderr or "")
        exit_code: Optional[int] = None
        runs: Optional[int] = None
        state = "unknown"

        # Parse lines like "last exit code = 1", "runs = 3", "state = not running"
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("last exit code = "):
                try:
                    val = s[len("last exit code = "):].strip()
                    # Sometimes "(never exited)" or "killed: 9"
                    if val.isdigit() or (val.startswith("-") and val[1:].isdigit()):
                        exit_code = int(val)
                except ValueError:
                    pass
            elif s.startswith("runs = "):
                try:
                    runs = int(s[len("runs = "):].strip())
                except ValueError:
                    pass
            elif s.startswith("state = "):
                state = s[len("state = "):].strip()

        return exit_code, runs, state

    # ------------------------------------------------------------------
    # stderr log parsing — extract Python exception class
    # ------------------------------------------------------------------

    def _parse_error_class(
        self, label: str,
    ) -> tuple[Optional[str], Optional[str]]:
        """Read tail of stderr log, extract last Python exception class.

        Returns: (error_class, missing_module). missing_module is non-None
        only if error_class == "ModuleNotFoundError".
        """
        log_path = self._log_paths.get(label)
        if not log_path or not os.path.isfile(log_path):
            return None, None

        try:
            size = os.path.getsize(log_path)
            with open(log_path, "rb") as f:
                if size > _STDERR_TAIL_BYTES:
                    f.seek(-_STDERR_TAIL_BYTES, os.SEEK_END)
                tail_bytes = f.read()
            tail = tail_bytes.decode("utf-8", errors="replace")
        except OSError as exc:
            logger.warning(
                "WaMirrorEnrichmentSensor: log read failed (%s): %s",
                log_path, exc,
            )
            return None, None

        # ModuleNotFoundError specific extraction (gets the module name too)
        mod_match = _MODULE_NOT_FOUND_RE.search(tail)
        if mod_match:
            return "ModuleNotFoundError", mod_match.group(1).split(".", 1)[0]

        # Generic exception class — find the LAST exception line in tail.
        # Traceback puts the exception class on the final non-blank line.
        last_exception: Optional[str] = None
        for line in tail.splitlines():
            m = _EXCEPTION_LINE_RE.match(line.strip())
            if m:
                # Strip the module prefix if any: "asyncpg.exceptions.InvalidPasswordError"
                full = m.group(1)
                last_exception = full.rsplit(".", 1)[-1]
        return last_exception, None

    # ------------------------------------------------------------------
    # Main read entry point
    # ------------------------------------------------------------------

    def read(self) -> WaMirrorEnrichmentReading:
        """Probe all labels and aggregate health.

        Returns a flat WaMirrorEnrichmentReading. NEVER raises.
        """
        labels: list[LabelStatus] = []
        worst_status = "green"
        repairable = False
        repair_target: Optional[LabelStatus] = None

        for label in self._labels:
            ls = LabelStatus(label=label)
            try:
                exit_code, runs, state = self._launchctl_exit_code(label)
                ls.last_exit_code = exit_code
                ls.runs = runs
                ls.state = state

                # exit code 0 = healthy; 75 = EX_TEMPFAIL (Layer A wrapper
                # signals launchd to retry, no Organism action needed)
                if exit_code is not None and exit_code != 0 and exit_code != 75:
                    error_class, missing_module = self._parse_error_class(label)
                    ls.error_class = error_class
                    ls.missing_module = missing_module
                    worst_status = "yellow"
                    # Code-reviewer finding #2: gate `repairable` on the sensor
                    # allowlist (defense-in-depth before taint reaches PG outbox
                    # subscribers). Actuator A3 is the FINAL gate, this is the
                    # FIRST gate at the perception boundary.
                    if (error_class == "ModuleNotFoundError"
                            and missing_module
                            and missing_module in _SENSOR_REPAIR_ALLOWLIST):
                        repairable = True
                        if repair_target is None:
                            repair_target = ls
                    elif error_class == "ModuleNotFoundError" and missing_module:
                        logger.warning(
                            "W57 sensor: ModuleNotFoundError for %r NOT in "
                            "sensor allowlist; not marking repairable. "
                            "Allowed: %s",
                            missing_module, sorted(_SENSOR_REPAIR_ALLOWLIST),
                        )
            except Exception as exc:
                logger.warning(
                    "WaMirrorEnrichmentSensor: unexpected error on %s: %s",
                    label, exc,
                )
                # Sensor MUST NOT crash the pulse loop
                ls.state = "probe_error"
                worst_status = "yellow"

            labels.append(ls)

        return WaMirrorEnrichmentReading(
            status=worst_status,
            repairable=repairable,
            labels=labels,
            metadata={
                "label_count": len(labels),
                "repairable_target": repair_target.label if repair_target else None,
                "repair_missing_module": (
                    repair_target.missing_module if repair_target else None
                ),
                "repair_python_path": self._python_path if repairable else None,
            },
        )
