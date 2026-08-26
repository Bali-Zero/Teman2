#!/usr/bin/env python3
"""wa_codex_seat_probe.py — S3 seat-death probe for the wa-codex broker's
OpenAI/Codex seat (Piece A of the seat sentinel pair).

Runs AS zantara-codex, via a system LaunchDaemon (spec §4.1,
research/operations/2026-08-19-bot-chatgpt-provider-broker-spec.md — same
login-less-user shape as the broker daemon itself). zantara-codex's home is
`drwx------` — unreadable cross-user by the cron identity `nuzantara` — so
this probe is the ONLY thing that can look at codex's own auth state, and
the status file it writes is the sole channel that crosses the user
boundary. Piece B, scripts/wa_codex_seat_sentinel.py, runs as `nuzantara`
and reads that file (plus the server-side broker gauge) to decide whether to
alert.

WHY (2026-08-20): today auth death is detectable only by (a) an "AUTH DEATH"
line the broker daemon logs to a file the cron user cannot read, or (b) the
server-side broker gauge accumulating `consecutive_failures` — but only when
jobs actually flow, and the lane is flag-OFF with zero jobs right now.
Without this probe, a dead seat sits invisible until someone flips the flag.
This organ manufactures a signal independent of job traffic: `codex login
status` plus a 1-token synthetic `codex exec`, on the plist's own
StartInterval, regardless of whether the broker has anything to claim.

CLASSIFICATION (S1.5, 2026-08-26 — sharpens the bucket the paragraph above
used to describe): quota exhaustion is now its OWN verdict,
`VERDICT_QUOTA_EXHAUSTED` ("quota_exhausted"), distinct from `auth_death`
and from the generic `other_failure` bucket it used to fall into — the twin,
on the probe side, of `wa_codex_daemon.py`'s `CodexExecQuotaError` arm
(B2b). Detection REUSES the daemon's own quota word class
(`_QUOTA_STRUCTURED_RE`/`_QUOTA_PROSE_RE` in `backend/llm/codex_exec_client.py`)
via the same import-with-degraded-fallback pattern as `AUTH_STRUCTURED_RE`/
`AUTH_PROSE_RE` below — never a second, drifting definition. Priority is a
FIXED two-step order — auth checked first, quota second — deliberately
simpler than the daemon's full per-word-class confidence-tier SPEC
(`_classify_stderr` in that same
module): this probe's `guilty_texts` are the output of a single synthetic,
domain-free "ping" prompt (see `_PROBE_PROMPT` below), not a real client
payload, so the domain-overload ambiguity that SPEC exists to resolve (a
KITAS sponsor's own "quota", an immigration client's own "unauthorized")
cannot occur here — there is no real prompt for either word class to
collide with. This probe still answers only what it can: is the seat's
LOGIN dead, or its usage quota exhausted, or something else non-zero — never
a full replay of the daemon's SPEC.

LEAK SURFACE (Law 2 / scar family #4 — secret/PII in the clear): the status
file carries ONLY the verdict enum, the two raw exit codes, and a UTC
timestamp. No stdout/stderr from `codex` — which could echo prompt content,
an operator's local path, or other free text — ever reaches the file,
stdout, or a log line above WARNING.

EXIT: 0 = probed and the status file was written (even verdict=auth_death —
per scar family #2 "esiste ≠ armato", the FILE existing IS the alarm
mechanism, so a probe that saw the death and reported it is a SUCCESSFUL
run, not a failure). 2 = the whole probe attempt raised unexpectedly, or the
status file could not be written — CANNOT-VERIFY, never a silent "ok".
"""
from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, Mapping, Sequence

logger = logging.getLogger("wa_codex_seat_probe")

# --- auth-death + quota-exhaustion detection: REUSE the daemon's own -------
# --- detectors ---------------------------------------------------------
# Primary path: scripts/provision_zantara_codex.sh already installs a
# root-owned copy of backend/llm/codex_exec_client.py under
# /usr/local/lib/wa-codex-broker/backend/llm/ for the daemon itself, and
# infra/launchagents/wrappers/wa-codex-seat-probe-wrapper.sh sets
# PYTHONPATH=/usr/local/lib/wa-codex-broker before exec'ing this script — so
# the import below resolves against that SAME runtime tree, not a repo
# checkout the zantara-codex user does not have.
#
# S1.5 (2026-08-26) FOUND AND FIXED, adjacent to the quota work: the
# single combined `_AUTH_DEATH_RE` this block used to import no longer
# exists in codex_exec_client.py — B2b's confidence-tier SPEC split it into
# `_AUTH_STRUCTURED_RE`/`_AUTH_PROSE_RE` (the same two-tier shape quota
# already had) without updating this probe's import, which meant the
# "primary path" below had been silently dead — ImportError on every run,
# unconditionally falling to the copy — since B2b landed, undetected because
# the fallback is functionally byte-identical. Verified live (not assumed):
# `PYTHONPATH=apps/backend-rag python3 -c "from backend.llm.codex_exec_client
# import _AUTH_DEATH_RE"` raises ImportError on this branch's HEAD. Now
# imports the same two symbols the daemon actually exports.
#
# If that import ever fails (runtime tree not provisioned, or provisioning
# drifted from the daemon's), fall back to a LOCAL COPY of the same pattern,
# marked below. The copies MUST be kept byte-identical to
# backend/llm/codex_exec_client.py::_AUTH_STRUCTURED_RE /
# ::_AUTH_PROSE_RE / ::_QUOTA_STRUCTURED_RE / ::_QUOTA_PROSE_RE or the two
# detectors will disagree about the same log line — superscar #1 (HOME-fork
# drift) applied to a regex instead of a whole script. The import is
# PRIMARY; this copy is a degraded fallback, never the source of truth.
# This fallback is also why promoting THIS file to the runtime tree does
# not require promoting codex_exec_client.py in lockstep — a stale runtime
# tree (one that predates the quota word class, or even the current
# auth-split) still gets correct detection from the local copy; see memory
# `dark-describes-the-branch-not-the-deployment` for why promoting
# codex_exec_client.py/wa_codex_daemon.py together is its own, separate,
# entangled decision this change does not need to make.
try:
    from backend.llm.codex_exec_client import _AUTH_PROSE_RE as AUTH_PROSE_RE
    from backend.llm.codex_exec_client import (
        _AUTH_STRUCTURED_RE as AUTH_STRUCTURED_RE,
    )
    from backend.llm.codex_exec_client import _QUOTA_PROSE_RE as QUOTA_PROSE_RE
    from backend.llm.codex_exec_client import (
        _QUOTA_STRUCTURED_RE as QUOTA_STRUCTURED_RE,
    )

    _AUTH_DEATH_SOURCE: Final[str] = "import"
except ImportError:  # pragma: no cover — exercised only when the runtime
    # tree is missing/stale; kept in sync by hand with the primary above.
    AUTH_STRUCTURED_RE = re.compile(
        r"\b401\s+unauthorized\b|\berror\s+401\b|\b401\s+error\b|\bhttp\s+401\b|"
        r"token_revoked|refresh_token(?:_reused|_revoked|_expired)?",
        re.IGNORECASE,
    )
    AUTH_PROSE_RE = re.compile(
        r"\b(?:"
        r"unauthorized|"
        r"token\s+has\s+expired|"
        r"not\s+logged\s+in|"
        r"login\s+required|"
        r"sign[- ]in\s+required|"
        r"need(?:s)?\s+to\s+sign[- ]in|"
        r"session\s+invalidated|"
        r"auth(?:entication)?\s+(?:failed|error|required|expired)|"
        r"run\s+`?codex\s+login`?"
        r")(?!\w)",
        re.IGNORECASE,
    )
    QUOTA_STRUCTURED_RE = re.compile(
        r"\b429\s+too\s+many\s+requests\b|insufficient_quota|rate_limit_exceeded",
        re.IGNORECASE,
    )
    QUOTA_PROSE_RE = re.compile(
        r"\b(?:"
        r"rate[- ]limit(?:ed)?\s+exceeded|"
        r"rate\s+limit\s+reached|"
        r"usage\s+limit(?:\s+reached)?|"
        r"exceeded\s+your\s+current\s+quota|"
        r"monthly\s+credits\s+exhausted|"
        r"credits\s+exhausted|"
        r"out\s+of\s+extra\s+usage"
        r")(?!\w)",
        re.IGNORECASE,
    )
    _AUTH_DEATH_SOURCE = "fallback-copy"

# The synthetic prompt MUST stay an inert, domain-free literal (Kimi r1 m8):
# this probe scans a FAILED exec's stderr raw, without the daemon's
# `_strip_known_lines` defusal — safe only while the prompt (and thus any
# echoed prompt/answer line) cannot contain auth-shaped vocabulary. A
# visa-domain prompt here ("check the client's login…") would reopen the
# family-#3 false positive the daemon spent rounds R25-R27 closing.
_PROBE_PROMPT: Final[str] = "ping"

_ENV_BIN: Final[str] = "WA_CODEX_BIN"
_ENV_STATUS_FILE: Final[str] = "WA_CODEX_SEAT_STATUS_FILE"
_DEFAULT_STATUS_FILE: Final[str] = "/usr/local/var/wa-codex-broker/seat-status.json"
_TIMEOUT_S: Final[int] = 60

# Sentinel exit code for a subprocess that never produced a real exit code
# (timeout or spawn failure). Never a real `codex` exit code — codex exits
# 0..255 like any CLI.
_UNRUN_RC: Final[int] = -1

VERDICT_OK: Final[str] = "ok"
VERDICT_AUTH_DEATH: Final[str] = "auth_death"
# S1.5 (2026-08-26): the token name is fixed by
# scripts/wa_codex_seat_sentinel.py's own forward-compat comment (it names
# this exact string as the example of a future verdict a reader must not
# swallow into silence) — do not rename without updating that reader too.
VERDICT_QUOTA_EXHAUSTED: Final[str] = "quota_exhausted"
VERDICT_OTHER_FAILURE: Final[str] = "other_failure"
VERDICT_PROBE_ERROR: Final[str] = "probe_error"

EXIT_OK: Final[int] = 0
EXIT_CANNOT_VERIFY: Final[int] = 2


@dataclass(frozen=True)
class ProbeStatus:
    """The ENTIRE contents of the status file. No field here may ever carry
    free text from a codex invocation — see module docstring, LEAK SURFACE.
    """

    checked_at: str
    verdict: str
    login_status_rc: int
    exec_rc: int

    def to_json(self) -> str:
        return json.dumps(
            {
                "checked_at": self.checked_at,
                "verdict": self.verdict,
                "login_status_rc": self.login_status_rc,
                "exec_rc": self.exec_rc,
            }
        )


def resolve_binary(env: Mapping[str, str]) -> str | None:
    """Same resolution order as CodexExecClient._resolve_binary (minus the
    constructor-arg step, which has no meaning for a standalone probe):
    env `WA_CODEX_BIN` first, else `codex` on PATH. None = unresolvable."""
    explicit = env.get(_ENV_BIN, "").strip()
    if explicit:
        return explicit
    return shutil.which("codex")


_CHILD_ENV_KEEP: Final[tuple[str, ...]] = (
    "PATH",
    "HOME",
    "TERM",
    "LANG",
    "LC_ALL",
    "TMPDIR",
    "CODEX_HOME",
)


def _child_env(env: Mapping[str, str]) -> dict[str, str]:
    """Minimal codex child env — the same allowlist discipline as the
    daemon's `CodexExecClient._build_env`: a probe launched from a fat
    interactive shell must never hand unrelated secrets to an agentic child
    process (scar 2026-08-18: dispatching an external CLI delivers the
    ENVIRONMENT, not just the prompt). The wrapper already strips the env
    file down to WA_CODEX_BIN/CODEX_HOME; this is the second, in-process
    layer."""
    return {key: env[key] for key in _CHILD_ENV_KEEP if key in env}


def _run(binary: str, args: Sequence[str], env: Mapping[str, str]) -> tuple[int, str, str]:
    """Runs one codex subcommand. Returns (rc, stdout, stderr); rc=_UNRUN_RC
    on timeout or spawn failure — the caller reads the SENTINEL value, never
    an exception, and neither failure mode leaks free text (both return
    empty strings for stdout/stderr, since the file this feeds never
    carries codex's raw text anyway)."""
    try:
        proc = subprocess.run(
            [binary, *args],
            env=_child_env(env),
            capture_output=True,
            text=True,
            # Same decode discipline as the daemon (its R25-8 note): codex
            # emitting invalid UTF-8 must degrade to replacement chars, not
            # raise UnicodeDecodeError past the except clauses below and
            # skip the status write entirely (Kimi r1 m6).
            errors="replace",
            timeout=_TIMEOUT_S,
            check=False,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired:
        logger.warning("wa_codex_seat_probe: %s timed out after %ss", list(args), _TIMEOUT_S)
        return _UNRUN_RC, "", ""
    except OSError as exc:
        logger.warning(
            "wa_codex_seat_probe: %s failed to spawn: %s", list(args), type(exc).__name__
        )
        return _UNRUN_RC, "", ""


def _auth_detected(text: str) -> bool:
    """True if `text` matches either tier of the daemon's auth-death word
    class (structured token OR prose phrase)."""
    return bool(AUTH_STRUCTURED_RE.search(text) or AUTH_PROSE_RE.search(text))


def _quota_detected(text: str) -> bool:
    """True if `text` matches either tier of the daemon's quota-exhaustion
    word class (structured token OR domain-safe prose phrase — see the
    import block above for why both tiers are safe to OR together here,
    unlike in the daemon's real-prompt classifier)."""
    return bool(QUOTA_STRUCTURED_RE.search(text) or QUOTA_PROSE_RE.search(text))


def classify(
    login_rc: int,
    login_out: str,
    login_err: str,
    exec_rc: int,
    exec_out: str,
    exec_err: str,
) -> str:
    """Pure — no I/O, so this is where a future unit test would live.

    Priority (S1.5, 2026-08-26): auth-death outranks quota-exhaustion
    outranks a generic nonzero. Fixed two-step order, not the daemon's full
    per-word-class confidence-tier SPEC — see the module docstring's
    CLASSIFICATION section for why that's a safe simplification here (this
    probe's guilty_texts come from one synthetic, domain-free "ping", never
    a real client prompt the two word classes could collide inside). Each
    regex is searched on EACH text independently — never concatenated —
    matching the discipline of the upstream `_auth_death_detected`: joining
    texts with any separator risks a `\\s+` alternative bridging two
    innocent fragments across the seam into a false match.

    Scanning discipline imitates the daemon's R26 rule: only a FAILED
    command's text is scanned — a succeeding command's output is a status
    line or a model answer whose vocabulary is innocent by construction
    (family #3: "unauthorized"/"login"/"quota"/"expired" are ordinary
    visa-domain words in a legitimate answer). Per-command surface: for
    `login status` BOTH streams (measured 2026-08-20 on the live CLI: the
    logged-out marker "Not logged in" arrives on STDOUT, rc=1; healthy
    prints "Logged in using ChatGPT", rc=0, no match); for `exec` STDERR
    ONLY (the daemon's measured evidence places codex's own diagnostics on
    stderr, and exec stdout may carry a partial model answer discussing a
    CLIENT's login/credential/quota).

    Only if NEITHER command produced a real exit code at all is this a
    probe_error (we could not observe anything, auth-dead or otherwise).
    Any other nonzero combination that matches neither word class is
    other_failure."""
    guilty_texts: list[str] = []
    if login_rc not in (0, _UNRUN_RC):
        guilty_texts.extend((login_out, login_err))
    if exec_rc not in (0, _UNRUN_RC):
        guilty_texts.append(exec_err)
    if any(_auth_detected(t) for t in guilty_texts if t):
        return VERDICT_AUTH_DEATH
    if any(_quota_detected(t) for t in guilty_texts if t):
        return VERDICT_QUOTA_EXHAUSTED
    if login_rc == _UNRUN_RC and exec_rc == _UNRUN_RC:
        return VERDICT_PROBE_ERROR
    if login_rc != 0 or exec_rc != 0:
        return VERDICT_OTHER_FAILURE
    return VERDICT_OK


def probe(env: Mapping[str, str] | None = None) -> ProbeStatus:
    """Runs both checks and classifies the outcome. Always returns a
    ProbeStatus — a fully-unresolvable binary is itself a verdict
    (probe_error), not an exception; the caller still gets to write it."""
    resolved_env = dict(env if env is not None else os.environ)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    binary = resolve_binary(resolved_env)
    if binary is None:
        logger.error(
            "wa_codex_seat_probe: codex binary unresolvable (WA_CODEX_BIN unset, not on PATH)"
        )
        return ProbeStatus(now_iso, VERDICT_PROBE_ERROR, _UNRUN_RC, _UNRUN_RC)

    login_rc, login_out, login_err = _run(binary, ["login", "status"], resolved_env)
    exec_rc, exec_out, exec_err = _run(
        binary,
        ["exec", "--sandbox", "read-only", "--skip-git-repo-check", _PROBE_PROMPT],
        resolved_env,
    )
    verdict = classify(login_rc, login_out, login_err, exec_rc, exec_out, exec_err)
    return ProbeStatus(now_iso, verdict, login_rc, exec_rc)


def write_status_atomic(status: ProbeStatus, path: Path) -> None:
    """tmp+rename in the SAME directory (atomic on one filesystem) — Piece B
    never observes a half-written file. Mode 0640, group staff: Piece B runs
    as a DIFFERENT user (nuzantara, a staff member — measured on Pro:
    gid=20(staff)) and reads via the group bit; "others" get nothing. The
    payload is enum-only by design, but family-#4 hygiene says grant the one
    reader, not the world (this probe's process group is staff, so the tmp
    file inherits it). CodeQL's py/overly-permissive-file flags ANY group
    bit — dismissed as won't-fix (alert #8634): the group bit IS the channel
    this organ exists to provide; 0600 would sever probe→sentinel."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=".seat-status-", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(status.to_json())
        os.chmod(tmp_name, 0o640)
        os.replace(tmp_name, str(path))
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise


def default_status_path() -> Path:
    return Path(os.environ.get(_ENV_STATUS_FILE, _DEFAULT_STATUS_FILE))


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="wa_codex_seat_probe: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args(argv)  # no flags today; keeps the CLI extensible

    logger.info("auth-death detector source: %s", _AUTH_DEATH_SOURCE)

    try:
        status = probe()
    except Exception as exc:  # noqa: BLE001 — any unexpected failure here is
        # CANNOT-VERIFY, not a stack trace on stdout: nothing valid to write.
        logger.error("probe failed unexpectedly: %s", type(exc).__name__)
        return EXIT_CANNOT_VERIFY

    status_path = default_status_path()
    try:
        write_status_atomic(status, status_path)
    except OSError as exc:
        logger.error(
            "could not write status file %s: %s", status_path, type(exc).__name__
        )
        return EXIT_CANNOT_VERIFY

    logger.info("verdict=%s written to %s", status.verdict, status_path)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
