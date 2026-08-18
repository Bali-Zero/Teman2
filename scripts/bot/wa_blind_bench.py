#!/usr/bin/env python3
"""
Blind benchmark harness — ChatGPT-subscription Codex candidates vs quality ceiling.

Part of the WhatsApp OpenAI-provider shipping mandate (2026-08-15) —
`research/operations/2026-08-15-adr-wa-runtime-openai-provider.md`. Runs
the de-identified fixtures from `scripts/bot/build_deid_corpus.py` through
the three approved model candidates and prints per-fixture output for BLIND
scoring — this script does not score anything itself.

⚠️ NOT A CI GATE. Orchestrator corpus gate, 2026-08-15: this harness must
NEVER be wired into a CI required check or otherwise treated as a green/red
promotion signal. It uses the selected `CodexExecClient` path and the
operator's existing ChatGPT subscription; it never reads or requests a paid
OpenAI API key. It exists to be run BY A HUMAN, deliberately, after the
de-identified corpus has passed its independent human privacy/legal review.

Models — approved candidates, not an unbenchmarked placeholder. The
default `--candidates` list is all three of `gpt-5.6-terra`, `gpt-5.6-luna`
AND `gpt-5.6-sol`, and this harness genuinely calls all three (verify with
`--candidates` in the printed run stats, or by reading the label key
file) — an earlier draft's docstring claimed sol was "included as the
quality ceiling" while the code never called it, which was a promise the
code did not keep. `sol` is included here as a reference point for
whoever scores the blind transcript, not as a candidate for the runtime
default (`DEFAULT_MODEL` in `codex_exec_client.py` stays `gpt-5.6-terra`,
unaffected by anything in this file). SCORING never
happens inside this script (see SCORING below) — a human or a non-OpenAI
seat reads the blind transcript and decides, so "sol judging sol" never
arises regardless of which models this harness calls.

SKIP / NOT RUN semantics: if `CodexExecClient.available` is false (the Codex
binary or a non-empty `auth.json` under the selected `CODEX_HOME` is absent),
this script prints instructions and exits 0. Exit 0 here means "nothing ran",
NOT "checks passed" — do not let a CI wrapper collapse those two meanings.
The printed banner is machine-greppable (`WA_BLIND_BENCH_STATUS=`), values
`SKIPPED_UNAVAILABLE` / `SKIPPED_NO_FIXTURES` / `RAN` / `RAN_ALL_FAILED` (R6-6,
Kimi K3 round-6 review: a run that reached the provider and got NOTHING but
`[ERROR: ...]` back on every single response is not a completed benchmark
pass — `main()` exits non-zero for `RAN_ALL_FAILED`, exits 0 for `RAN`
even with SOME per-response failures, whose count is reported in the
returned stats and logged) / `FAILED_BAD_FIXTURES` (R8-11, Kimi K3
round-8 review: the fixtures corpus itself was malformed — invalid JSON
or the wrong shape — caught in `main()` and reported cleanly instead of
propagating a raw traceback with no status line at all) / `FAILED_NO_CANDIDATES`
(R9-4, Kimi K3 round-9 review: a key file with an empty `"candidates": []`
used to be silently ADOPTED — zero models called, zero responses, and
`RAN`/exit 0 reported for a run that benchmarked nothing; now rejected at
adoption time in `main()`, with `run_bench` itself refusing an empty
candidates list as defense in depth; widened round-10, R10-2/R10-3, to
also cover a malformed element or a duplicate candidate name) /
`FAILED_BAD_REUSE_FILE` (R10-1, Kimi K3 round-10 review: every early
`return 1` in `main()`'s `--reuse-nonce-from`/adoption block used to skip
`_print_status` entirely, breaking the "any outcome is machine-greppable"
contract on 9 distinct exit sites — an unreadable/malformed key file,
missing nonce, a seed/candidates conflict, or a legacy key file predating
R8-6's seed/candidates tracking (R12-3 count correction, 2026-08-15, Kimi
K3 round-12 review: the "8" figure above was stale — recounted on disk at
7 `FAILED_BAD_REUSE_FILE` sites + 2 `FAILED_NO_CANDIDATES` sites in the
`--reuse-nonce-from`/adoption block, 9 total, not 8)) / `FAILED_IO`
(R10-1(b): an `OSError`
raised inside `run_bench` — a permission failure, a pre-planted symlink
refused per R8-13/R9-8, disk full — used to propagate raw through
`asyncio.run`/`main()` with no status line at all) so a wrapper can tell
the difference if it ever needs to.

SCORING is explicitly OUT of this script's scope (mandate T4: "Nell'ADR
nota che lo scoring finale del bench va fatto da seat NON-OpenAI (sol che
giudica sol = self-approval)"). This script's job ends at producing a
blind transcript — `{fixture_id, language, history, prompt}` mapped to
`{variant_label: response_text}` with variant labels SHUFFLED per fixture
(see `_blind_labels`) so a human or a non-OpenAI scoring seat cannot infer
which model produced which answer from label order alone. The mapping from
shuffled label back to real model is written to a SEPARATE key file, never
shown alongside the transcript.

The per-fixture shuffle is seeded from a per-RUN SECRET nonce
(`secrets.token_hex(16)`, see `_fixture_seed`), not from `--seed`/
fixture-id alone (R6-2 binding correction, Kimi K3 round-6 review) — the
nonce is written ONLY to the key file's first line, never to the
transcript, never printed, never logged. An earlier draft derived the
seed from public inputs only (the default `--seed=42` and the fixture id,
which is printed in plain text in the transcript itself), which meant
anyone holding the blind transcript plus this file's source — i.e. every
legitimate scorer — could recompute the shuffle without the key file,
undermining the whole point of blinding. Reproducibility is therefore now
"reproducible GIVEN the same nonce" (a re-run that reuses the key file's
nonce via `--reuse-nonce-from <path-to-that-run's-label_key.local.jsonl>`),
not "reproducible from the transcript alone".

R6-2 REFINEMENT (orchestrator/Codex order, 2026-08-15, binding, supersedes
the CLI shape of the round-6 fix above): the nonce is a SECRET, and a
secret passed as a CLI argument is visible in plaintext to any other
process on the same machine via `ps`/`/proc` for the whole life of this
process — the exact class of exposure `build_deid_corpus.py`'s R6-4 fix
(Ollama prompt via stdin, never argv) already treats as unacceptable for
non-secret WhatsApp text, and a stricter standard applies to an actual
secret. There is therefore NO `--nonce` flag: the nonce is always either
generated fresh internally (`secrets.token_hex(16)`, the default) or,
for a legitimate re-run, read directly off disk from a PRIOR run's own
key file via `--reuse-nonce-from <path>` — a PATH in argv is fine (it
identifies a file, not a secret value), the secret itself never crosses
argv at any point. `run_bench(..., nonce=...)` still accepts an explicit
nonce as a plain function parameter — that path is for tests only (this
process's own test suite calling this process's own code in-process,
never a value that crosses an OS process boundary via argv).

R8-6 (Kimi K3 round-8 review): the nonce alone does not make a re-run's
shuffle reproducible — `_fixture_seed` also folds in `--seed`, and
`_blind_labels` shuffles the `--candidates` list itself, so a DIFFERENT
seed or candidate list under the SAME nonce silently produces a DIFFERENT
shuffle. `seed`/`candidates` now ride alongside the nonce on the key
file's first line and are adopted automatically by `--reuse-nonce-from`;
an explicit `--seed`/`--candidates` that conflicts with the key file's own
values fails loud rather than silently reshuffling.

Usage:
    PYTHONPATH=. python3 scripts/bot/wa_blind_bench.py \\
        --fixtures-dir research/personal/wa-bench-corpus/fixtures.local \\
        --output-dir research/personal/wa-bench-corpus/bench-runs.local

    # Codex CLI/auth unavailable: prints instructions, exits 0, runs nothing.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import random
import re
import secrets
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "apps" / "backend-rag"))

logger = logging.getLogger("wa_blind_bench")

_STATUS_PREFIX = "WA_BLIND_BENCH_STATUS="

# R8-6 binding correction, 2026-08-15 (Kimi K3 round-8 review): the actual
# default seed value, factored out so `main()` can distinguish "operator
# didn't pass --seed" (argparse default `None`) from "operator explicitly
# passed --seed 42" — both need different treatment when combined with
# `--reuse-nonce-from` (see `main()`).
_DEFAULT_SEED = 42


@dataclass(frozen=True)
class BenchCandidateResult:
    """Provider-neutral result shape used only by this offline harness."""

    text: str
    latency_ms: float
    attempts: int
    refusal: bool | None


class BenchClient(Protocol):
    """Narrow client contract needed by the blind harness."""

    @property
    def available(self) -> bool: ...

    async def generate(self, *, input_text: str, model: str | None = None) -> BenchCandidateResult: ...

    async def close(self) -> None: ...


class CodexSubscriptionBenchClient:
    """Compatibility facade from the harness contract to `CodexExecClient`.

    `CodexExecClient` performs one subprocess attempt and exposes no structured
    refusal field. The facade records `attempts=1` after a successful call and
    `refusal=None`; it never fabricates a refusal decision.
    """

    def __init__(self) -> None:
        from backend.llm.codex_exec_client import CodexExecClient

        self._client = CodexExecClient()

    @property
    def available(self) -> bool:
        return self._client.available

    async def generate(self, *, input_text: str, model: str | None = None) -> BenchCandidateResult:
        result = await self._client.generate(input_text, model=model)
        return BenchCandidateResult(
            text=result.text,
            latency_ms=result.latency_ms,
            attempts=1,
            refusal=None,
        )

    async def close(self) -> None:
        """No persistent HTTP client exists on the subprocess path."""


def _print_status(status: str) -> None:
    """Machine-greppable status line — see module docstring's SKIP note."""
    print(f"{_STATUS_PREFIX}{status}")


def _mkdir_private(path: Path) -> None:
    """Create `path` (and any missing parents) with the leaf directory at
    0700, immune to the process umask, and ENFORCED even if the directory
    already existed with looser permissions — the directory-level
    counterpart to `_open_private`'s 0600-from-creation discipline (K5,
    orchestrator corpus gate, 2026-08-15). `Path.mkdir(mode=...)` alone is
    not enough on either count: the umask still narrows `mode` unless
    cleared first, and `exist_ok=True` on an already-existing directory
    does not retroactively fix its permissions — hence the explicit
    `os.chmod` after, unconditionally. Only the LEAF directory is
    guaranteed 0700; missing PARENT directories are created by
    `Path.mkdir(parents=True)` at their own default permissions,
    mirroring `mkdir -p`.

    R9-8 binding correction, 2026-08-15 (Kimi K3 round-9 review, MICRO):
    the directory-component twin of the leaf-file symlink hole R8-13
    closed for `_open_private` — `Path.mkdir(parents=True, exist_ok=True)`
    silently accepts a pre-planted symlink at `path` whose target is a
    directory (no `O_NOFOLLOW` equivalent exists for `mkdir`), and the
    unconditional `os.chmod` below FOLLOWS a symlink to its target by
    default, so a symlink leaf would get its chmod applied to whatever
    directory it points at, not `path` itself. Refused explicitly before
    the chmod — a directory that exists as a symlink is never something
    this function can make 0700 in the sense its docstring promises.

    R10-6 honesty note, 2026-08-15 (Kimi K3 round-10 review, MICRO): the
    check above is a check-then-chmod sequence, not an atomic one — there
    is a real TOCTOU window between `path.is_symlink()` and `os.chmod`
    where a symlink could be swapped in. This is protection against a
    symlink PRE-PLANTED before this function runs (the stated threat
    model, matching `_open_private`'s O_NOFOLLOW), not a TOCTOU-proof
    guarantee against a same-user attacker racing this exact call — that
    threat model is out of scope here (local same-user race, not the
    pre-planted-symlink class this fix targets)."""
    prior_umask = os.umask(0o077)
    try:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
    finally:
        os.umask(prior_umask)
    if path.is_symlink():
        raise OSError("refusing to chmod a symlink leaf directory")
    os.chmod(path, 0o700)


def _open_private(path: Path):
    """Open a file for text writing, mode 0600 FROM CREATION — not a
    trailing `os.chmod` after `open("w")`, which leaves a window where the
    file exists at the process umask's (typically 0o644) permissions
    before being narrowed. `os.open` with an explicit mode sets the bits
    at creation; the umask is cleared around the call so it cannot widen
    them, then restored.

    MEDIUM binding correction, 2026-08-15 (Kimi K3, live-gate round 5, two
    passes): the `mode=0o600` on `os.open` applies ONLY when the file is
    actually CREATED by this call (`O_CREAT` without `O_EXCL`) — if `path`
    already exists (e.g. a re-run over a prior 0o644 file, or one written
    by another tool), the OS silently keeps the file's PRE-EXISTING
    permissions and this function would then write into a file that
    stayed group/other-readable the whole time. Same class of bug as
    `build_deid_corpus.py::_write_jsonl_private`'s round-5 fix, and the
    same two-pass shape: pass 1 added `os.fchmod(fd, 0o600)` right after
    `os.open`; the orchestrator's pass-2 refinement caught that pass 1
    still opened with `O_TRUNC` up front, so a failed `fchmod` left the
    fail-closed path having already ZEROED the pre-existing file's
    content — "no new content written" was true, "old content destroyed"
    was a separate, real loss the framing missed. Fixed: open WITHOUT
    `O_TRUNC`, confirm `os.fchmod` succeeds FIRST, and only then
    explicitly truncate (`os.ftruncate`) and reset the write position
    (`os.lseek(..., os.SEEK_SET)`) before returning the file object for
    writing. Fail-closed, now genuinely so: if `os.fchmod` raises, the fd
    is closed, the file's pre-existing bytes are UNTOUCHED, and the
    exception propagates — this function never returns a writable handle
    whose permissions it could not confirm, and never destroys data on
    the failure path.

    R13-3 binding correction, 2026-08-15 (Kimi K3 round-13 review): the
    "never destroys data on the failure path" claim above is UNQUALIFIED
    in the docstring's own words, but it only actually holds for a
    failure inside the GUARDED syscalls — `os.fchmod`/`os.ftruncate`/
    `os.lseek`. It does NOT hold for the one path outside that guard
    since R12-4's revert: `os.fdopen`. By the time `os.fdopen` runs,
    `os.ftruncate(fd, 0)` has ALREADY executed successfully — the
    pre-existing file's content is already zeroed on disk. If `os.fdopen`
    then fails, the residual is not "no data destroyed, one fd leaked" —
    it is BOTH: one leaked `fd` AND the pre-existing file already
    truncated (the truncate preceded the fdopen failure; there is no
    "before truncation" state left to preserve at that point). The gate
    explicitly DECLARES this residual rather than reordering the syscalls
    to avoid it (e.g. `os.fdopen` before `os.ftruncate`) — a reorder would
    introduce a new ownership-transfer mechanic at almost exactly the
    hazard class R11-2's wrap already demonstrated (round-12's own
    mechanical "fix" generated its own new hazard; a prose correction
    must not risk generating a twin one). See `research/operations/
    2026-08-15-adr-wa-runtime-openai-provider.md` §20 for the full
    decision record.

    R10-4 binding correction, 2026-08-15 (Kimi K3 round-10 review): the
    guarantee above ("if os.fchmod raises, the fd is closed... exception
    propagates") only actually covered the `os.fchmod` call itself — the
    `os.ftruncate`/`os.lseek` calls immediately after were NAKED. An
    `OSError` from either of those (disk full on `ftruncate`, an
    unlikely-but-real `lseek` failure) would raise straight out of this
    function with the fd never closed — leaking it, and violating the
    exact "any post-open failure closes the fd" invariant this docstring
    already claims. Fixed: both calls now sit inside the same close-then-
    reraise guard as `os.fchmod`.

    R11-2 (Kimi K3 round-11 review) moved `os.fdopen(fd, "w",
    encoding="utf-8")` INSIDE this same guard, reasoning that an
    `os.fdopen` failure would otherwise leak `fd` past this function's
    last statement. R12-4 SUPERSEDES R11-2 and reverts it (Kimi K3
    round-12 review): wrapping `os.fdopen` in a close-on-exception guard
    is itself hazardous in CPython. `os.fdopen` constructs an
    `io.TextIOWrapper` around an `io.FileIO(fd, closefd=True)` (the
    default); if construction fails PARTWAY THROUGH — after `FileIO` has
    already taken ownership of `fd` but before `fdopen` returns — CPython
    may have already closed `fd` itself as part of unwinding the partial
    object. A blind `os.close(fd)` in the `except` clause then either (a)
    raises `OSError: [Errno 9] Bad file descriptor` on an
    already-closed fd, masking the ORIGINAL exception, or (b) — worse, in
    a multithreaded process — closes a DIFFERENT, unrelated fd that the
    OS has already recycled to the same integer, silently corrupting
    another part of the process. The round-11 reviewer offered both this
    "wrap" option and a "narrow" option (leave `os.fdopen` outside the
    guard); the round-11 gate mandate chose "wrap"; round-12 measured
    the CPython hazard above and mandates "narrow" instead. Reverted:
    `os.fdopen` sits OUTSIDE the guard again, covering only
    `os.fchmod`/`os.ftruncate`/`os.lseek` (R10-4's original scope). The
    accepted residual risk is narrower than it looks: `os.fdopen` does
    not allocate a new file descriptor (it wraps the one already open),
    so the realistic failure modes are a bad `mode` string (a
    programmer error, not a runtime condition) or the rare in-process
    memory-allocation failure while constructing the wrapper objects —
    neither is `EMFILE`/`ENFILE` (both are raised by calls that open a
    NEW fd, which `os.fdopen` never does; the R11-2 docstring's "errno 24
    EMFILE/ENFILE" was itself factually wrong on top of being the wrong
    fix — `ENFILE` is errno 23, not 24, and neither applies here). On the
    rare `os.fdopen` failure this function now leaks `fd` (a single fd,
    once, in an already-abnormal process) rather than risking a
    double-close or a stolen fd — the preferred trade."""
    prior_umask = os.umask(0o177)
    try:
        # R8-13 (MICRO, Kimi K3 round-8 review): O_NOFOLLOW — refuse to
        # follow a pre-planted symlink at `path`, so a symlink an attacker
        # placed here before this run cannot redirect the write.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    finally:
        os.umask(prior_umask)
    try:
        os.fchmod(fd, 0o600)
        os.ftruncate(fd, 0)
        os.lseek(fd, 0, os.SEEK_SET)
    except OSError:
        os.close(fd)
        raise
    return os.fdopen(fd, "w", encoding="utf-8")


class FixtureFormatError(ValueError):
    """Raised by `_load_fixtures` when a fixture line is not valid JSON, or
    parses as valid JSON but is not shaped like a fixture (R7-3, extended
    R8-11 for the not-valid-JSON case; Kimi K3 rounds 7/8 review)."""


class CandidatesEmptyError(ValueError):
    """Raised by `run_bench` (R9-4(b), 2026-08-15, Kimi K3 round-9 review)
    when the candidates list it was given is unusable. Defense in depth
    behind the `main()`-level key-file validation (R9-4(a)): a caller
    that reaches `run_bench` directly (this process's own test suite, a
    future wrapper) with an unusable list must not silently run zero
    models (or fewer distinct models than labels) and report `RAN`/exit 0
    — see this module's docstring for why that must never be reported as
    a completed pass.

    Widened, 2026-08-15 (R10-2/R10-3, Kimi K3 round-10 review): originally
    covered only the empty-list case. Now also raised for a list
    containing a non-string or empty-string element (R10-2 — `[""]` is
    truthy and used to slip past the bare `if not candidates:` guard,
    only to fail later via the wrong mechanism deep inside
    `_run_one_fixture`) and for a list containing a duplicate candidate
    name (R10-3 — two blind labels bound to the same underlying model
    defeats the whole point of blind scoring)."""


_REQUIRED_FIXTURE_KEYS = ("id", "language", "text")
_MAX_HISTORY_TURNS = 12


def _is_valid_history(value: object) -> bool:
    """Validate the de-identified, role-aware history shape fail-closed."""
    if not isinstance(value, list) or len(value) > _MAX_HISTORY_TURNS:
        return False
    for turn in value:
        if not isinstance(turn, dict):
            return False
        if turn.get("role") not in {"user", "assistant"}:
            return False
        if not isinstance(turn.get("text"), str) or not turn["text"]:
            return False
    return True


# R8-4 binding correction, 2026-08-15 (Kimi K3 round-8 review): the EXACT
# basenames `_load_fixtures` itself ever generates would produce, if this
# script were also the writer — but the actual writer is
# `build_deid_corpus.py::build_corpus`, whose own `_write_jsonl_private`
# loop emits precisely `fixtures_{language}.local.jsonl` for
# `language in {"en", "it", "id", "other"}` (see that module's own bucket
# dict). This loader's glob (`fixtures_*.local.jsonl`, below) is looser
# than that — it accepts ANY middle segment, including one an operator
# renamed to something contact-identifying
# (`fixtures_<contact-name>.local.jsonl` would still match the glob).
# `_safe_fixture_ref` below refuses to log a basename that doesn't match
# this exact generated shape.
_SAFE_FIXTURE_BASENAME_RE = re.compile(r"^fixtures_(?:en|it|id|other)\.local\.jsonl$")


def _safe_fixture_ref(path: Path, *, file_index: int) -> str:
    """A safe-to-log reference to a fixtures file: its own basename ONLY
    if it matches the exact shape `build_deid_corpus.py` generates
    (`_SAFE_FIXTURE_BASENAME_RE`), else an opaque per-file ordinal
    (`fixtures file #N`) — mirrors the `file_index` convention already
    used by `build_deid_corpus.py::_iter_jsonl_records` for the same
    reason. R8-4, Kimi K3 round-8 review: a naive `path.name`
    interpolation (the R7-3 fix's own behavior) would log the full
    basename of ANY file the loader's glob accepts, contact-renamed ones
    included."""
    if _SAFE_FIXTURE_BASENAME_RE.match(path.name):
        return path.name
    return f"fixtures file #{file_index}"


def _load_fixtures(fixtures_dir: Path) -> list[dict]:
    """R7-3 binding correction, 2026-08-15 (Kimi K3 round-7 review): this
    used to append `json.loads(line)` with no shape check at all.
    `fixture["id"]` (seed of the label_map, in `_run_one_fixture`) and
    `fixture["language"]` (blind-transcript row) are read OUTSIDE any
    per-candidate try/except in the caller, so a fixture that is valid
    JSON but not a dict — or a dict missing `id`/`language` — used to
    crash `run_bench` PARTWAY THROUGH a run, AFTER `_open_private` had
    already created (and possibly partially written) the blind transcript
    and key files, with no status line recorded. Validating the shape here
    — before `run_bench` ever calls `_mkdir_private`/`_open_private` — means
    a malformed corpus fails loud with zero output files touched, never a
    half-written run.

    VINCOLO (R7-3): the raised message never contains the LINE's content
    (could itself carry redacted-but-not-yet-verified text) nor any
    operator-chosen path component (same R6-3 discipline as every other
    log/error site in this file) — only a safe reference to the file
    (`_safe_fixture_ref`, R8-4) and the line number.

    R8-1 binding correction, 2026-08-15 (Kimi K3 round-8 review):
    `path.open(encoding="utf-8")` had no `errors="replace"` — the exact
    gap R7-5 already fixed on `build_deid_corpus.py::_iter_jsonl_records`,
    unfixed here. A single non-UTF-8 byte in a fixtures file raised
    `UnicodeDecodeError` straight out of the file iterator (not
    `json.JSONDecodeError`), which no per-line handling here could catch.
    Fixed to match: `errors="replace"` turns a mangled byte into U+FFFD,
    which becomes invalid JSON and is now handled by the R8-11 fix below
    (raised as `FixtureFormatError`, same as any other malformed line —
    never a raw crash).

    R8-11 binding correction, 2026-08-15 (Kimi K3 round-8 review): a line
    that is simply not valid JSON at all (`json.loads` raising
    `json.JSONDecodeError`) was NOT caught here — it propagated raw
    through `run_bench`/`asyncio.run`/`main()`, printing no
    `WA_BLIND_BENCH_STATUS=` line at all (contrary to this module's own
    docstring, which presents that status line as the way ANY outcome is
    machine-greppable). Now converted to the same `FixtureFormatError`
    used for a wrong-shape-but-valid-JSON line, caught by `main()` (see
    the new `FAILED_BAD_FIXTURES` status there).

    R9-3 binding correction, 2026-08-15 (Kimi K3 round-9 review): the
    `raise FixtureFormatError(...) from exc` above chained the caught
    `json.JSONDecodeError` as `__cause__` — and `JSONDecodeError.doc`
    carries the RAW fixture line that failed to parse, i.e. exactly the
    unverified fixture content this module's own R7-3 discipline says
    the raised message must never contain (see this docstring's VINCOLO
    paragraph above). `from exc` put that content back one hop away, via
    the exception's cause chain rather than its message. Same class the
    client (`openai_responses_client.py`, K4 binding correction) already
    cures for its own JSON-decode site: `from None` alone is NOT enough
    — Python's implicit exception chaining still sets `__context__` to
    the original exception at raise time inside an active `except`
    block, `from None` only suppresses `__suppress_context__`'s effect
    on the STANDARD traceback formatter's printed output, not attribute
    access. Fixed with the same deferred-raise pattern: the exception is
    built HERE (only the safe file ref + line number captured — never
    `exc`/`str(exc)`/the raw line) but the `raise` itself happens AFTER
    this `except` block exits, when no exception is "currently being
    handled" — verified empirically (see
    `TestR9_3FixtureFormatErrorHasNoCauseOrContext` in
    `test_wa_blind_bench.py`) that this leaves BOTH `__cause__` and
    `__context__` `None`, not merely display-suppressed."""
    fixtures: list[dict] = []
    for file_index, path in enumerate(sorted(fixtures_dir.glob("fixtures_*.local.jsonl")), start=1):
        with path.open(encoding="utf-8", errors="replace") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                pending_json_error: FixtureFormatError | None = None
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    pending_json_error = FixtureFormatError(
                        f"{_safe_fixture_ref(path, file_index=file_index)}, line {line_no}: "
                        f"not valid JSON ({type(exc).__name__})",
                    )
                if pending_json_error is not None:
                    raise pending_json_error
                if not isinstance(record, dict) or not all(
                    isinstance(record.get(key), str) and record.get(key) for key in _REQUIRED_FIXTURE_KEYS
                ):
                    raise FixtureFormatError(
                        f"{_safe_fixture_ref(path, file_index=file_index)}, line {line_no}: not a "
                        f"valid fixture — expected a JSON object with non-empty string 'id', "
                        f"'language', 'text' fields",
                    )
                if record.get("role") != "user" or "history" not in record:
                    raise FixtureFormatError(
                        f"{_safe_fixture_ref(path, file_index=file_index)}, line {line_no}: not a "
                        f"valid fixture — the current benchmark requires role='user' and "
                        f"an explicit role-aware 'history' list",
                    )
                if not _is_valid_history(record["history"]):
                    raise FixtureFormatError(
                        f"{_safe_fixture_ref(path, file_index=file_index)}, line {line_no}: not a "
                        f"valid fixture — 'history' must be a list of at most "
                        f"{_MAX_HISTORY_TURNS} non-empty user/assistant turns",
                    )
                fixtures.append(record)
    return fixtures


def _stable_int_hash(text: str) -> int:
    """Deterministic, cross-process-stable integer hash of a string.

    Python's builtin `hash()` on `str` is salted per-process by
    `PYTHONHASHSEED` (randomized by default since Python 3.3) — the same
    input string can hash to a DIFFERENT value in every fresh interpreter.
    SHA-256 has no such salt: the same input byte string always maps to
    the same digest, in-process or across a hundred separate `python3`
    invocations. Binding correction, 2026-08-15 —
    `test_stable_hash_matches_across_a_fresh_subprocess` in
    `test_wa_blind_bench.py` proves this empirically rather than by citing
    the docs.

    R6-2 correction (Kimi K3 round-6 review): this function's OWN
    stability does not by itself make the per-fixture SHUFFLE reproducible
    across runs — see `_fixture_seed` below, which feeds this a string
    that includes the run's SECRET nonce. Reproducibility of the actual
    label shuffle is now "reproducible GIVEN the same nonce", not
    "reproducible from public inputs alone" (see the module docstring's
    R6-2 correction and `_fixture_seed`'s docstring for why the earlier,
    unconditional "reproducible" claim was a real blinding weakness, not
    just an imprecise word choice).
    """
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)


def _fixture_seed(*, nonce: str, fixture_id: str, seed_base: int) -> int:
    """Per-fixture shuffle seed, derived from the run's SECRET nonce +
    fixture id + base seed (R6-2 binding correction, Kimi K3 round-6
    review).

    Before this fix, the seed was `seed_base + _stable_int_hash(fixture_id)
    % 10_000` — a function of PUBLIC inputs only: `--seed` defaults to 42
    (printed in `--help` and in every run's own logs), and `fixture_id` is
    printed in PLAIN TEXT inside the blind transcript itself
    (`blind_row["fixture_id"]`) alongside the shuffled responses. Anyone
    holding the blind transcript plus this file's source (i.e. anyone with
    repo access, which is everyone who could ever be asked to score it)
    could recompute every fixture's shuffle WITHOUT the key file — the
    blinding was reconstructible from data the scorer is handed by design.
    Folding in a per-RUN secret nonce (`secrets.token_hex(16)`, written
    ONLY to the key file — never the transcript, never a log line, never
    printed) breaks that: recomputing the shuffle now requires the nonce,
    which lives in exactly the one file the scorer is told never to see
    (module docstring: "DO NOT hand this to the scorer"). Reproducibility
    is therefore now "reproducible GIVEN the nonce" (a legitimate re-run
    that has the key file, invoked with `--reuse-nonce-from <that key
    file's path>` — never the nonce value itself on the command line, see
    the module docstring's R6-2 refinement), not "reproducible from the
    transcript alone" — the earlier docstring's unconditional
    "reproducible" was correct about the MECHANISM but wrong about what it
    implied for secrecy, which is what made it a real blinding weakness
    rather than just an imprecise word choice.
    """
    return seed_base + _stable_int_hash(f"{nonce}:{fixture_id}") % 10_000


def _blind_labels(variants: list[str], *, seed: int) -> dict[str, str]:
    """Shuffle model names to opaque labels (A/B/C…). Given the SAME seed
    (see `_fixture_seed` — now nonce-derived, R6-2), the SAME fixture
    always gets the SAME shuffle on a re-run; different fixtures get
    independently shuffled orders (a scorer cannot learn "label A is
    always terra" across the transcript)."""
    rng = random.Random(seed)
    shuffled = list(variants)
    rng.shuffle(shuffled)
    letters = [chr(ord("A") + i) for i in range(len(shuffled))]
    return dict(zip(letters, shuffled, strict=True))


def _render_fixture_prompt(fixture: dict[str, object]) -> str:
    """Serialize role-aware context into the text-only Codex provider.

    JSON keeps message boundaries explicit even when a message itself contains
    strings such as ``assistant:``. The fixture builder has already redacted and
    independently scanned every turn before this function can receive it.
    """
    history = fixture.get("history", [])
    payload = {
        "history": history,
        "current_user_message": fixture["text"],
    }
    return (
        "Offline de-identified WhatsApp response benchmark. Act as Zantara, "
        "Bali Zero's concise and careful assistant. Reply only to the current "
        "user message, using the prior role-labelled turns only as context. "
        "Do not invent prices, deadlines, legal certainty, or tool results; if "
        "grounding is unavailable, say what must be verified by the team. "
        "Return only the proposed WhatsApp reply.\n\n" + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )


async def _run_one_fixture(
    client: BenchClient,
    fixture: dict[str, object],
    *,
    candidates: list[str],
    seed_base: int,
    nonce: str,
) -> tuple[dict, dict]:
    """Returns (blind_transcript_row, key_row). `blind_transcript_row` has
    shuffled labels only; `key_row` maps label -> real model, written to a
    SEPARATE file (see module docstring). `nonce` is the run's secret —
    see `_fixture_seed` (R6-2) — threaded through here rather than read
    from a global, so this function stays independently testable.

    R8-3(a) binding correction, 2026-08-15 (Kimi K3 round-8 review):
    per-response `latency_ms`/`attempts` (from `LLMResult`) are now
    recorded in `key_row`, keyed by the same shuffled `label` as
    `label_map` — NEVER in `blind_row`/the blind transcript. Latency is a
    side-channel: different candidate models have measurably different
    latency profiles, so a scorer who could see per-response timing
    alongside the blind responses could use it to guess which label maps
    to which model without ever opening the key file — exactly the
    de-blinding risk `label_map` itself already lives in the key file to
    avoid (R6-2/R7-1). The key file is already sealed away from the
    scorer (module docstring: "DO NOT hand this to the scorer"), so
    recording latency there costs nothing and gives whoever DOES
    legitimately hold both files (an operator debugging the bench itself,
    not the blind scorer) real per-candidate timing data. A response that
    errored records `None` for both fields — there is no successful
    round-trip to time."""
    label_map = _blind_labels(
        candidates,
        seed=_fixture_seed(nonce=nonce, fixture_id=fixture["id"], seed_base=seed_base),
    )
    responses: dict[str, str] = {}
    latency_ms: dict[str, float | None] = {}
    attempts: dict[str, int | None] = {}
    for label, model in label_map.items():
        try:
            prompt = _render_fixture_prompt(fixture)
            result = await client.generate(input_text=prompt, model=model)
            responses[label] = "[REFUSED]" if result.refusal is True else result.text
            latency_ms[label] = result.latency_ms
            attempts[label] = result.attempts
        except Exception as exc:  # noqa: BLE001 — one candidate's failure must not sink the fixture
            # Exception TYPE only — never the exception's string content,
            # which for a provider failure could echo back output content
            # or, for other failure classes, local state we
            # don't want in a log line. Same discipline as
            # the selected provider boundary.
            #
            # R7-1 binding correction, 2026-08-15 (Kimi K3 round-7 review):
            # this used to log the REAL model name (`model`), not the
            # shuffled `label` — combined with the `[ERROR: ...]` marker
            # already visible in plain text inside the blind transcript
            # itself (`responses[label]` below), a scorer reading BOTH the
            # transcript and this process's log output could match a
            # failed response's label back to its real model for every
            # fixture that hit an error, de-blinding exactly the mapping
            # `label_key.local.jsonl` exists to keep separate. `label`
            # (A/B/C…) is already visible in the transcript alongside the
            # `[ERROR: ...]` text it corresponds to, so logging it here
            # adds no information a legitimate scorer doesn't already have
            # — never log the real model name in any PER-FIXTURE log line.
            logger.warning("Fixture %s, label %s failed (%s)", fixture["id"], label, type(exc).__name__)
            responses[label] = f"[ERROR: {type(exc).__name__}]"
            latency_ms[label] = None
            attempts[label] = None

    blind_row: dict[str, object] = {
        "fixture_id": fixture["id"],
        "language": fixture["language"],
        "history": fixture.get("history", []),
        "prompt": fixture["text"],
        "responses": responses,
    }
    key_row = {
        "fixture_id": fixture["id"],
        "label_map": label_map,
        "latency_ms": latency_ms,
        "attempts": attempts,
    }
    return blind_row, key_row


async def run_bench(
    *,
    fixtures_dir: Path,
    output_dir: Path,
    candidates: list[str],
    seed: int,
    nonce: str | None = None,
) -> dict[str, object]:
    """`nonce` (R6-2, refined): the per-run SECRET that makes the label
    shuffle reproducible only to a holder of the key file. Normally
    omitted — a fresh `secrets.token_hex(16)` is generated per call — and
    passed explicitly ONLY to reproduce a prior run's exact shuffle (a
    re-run that reads the nonce back out of that run's own key file).
    Never pass a guessed or low-entropy value here; it defeats the whole
    point of R6-2. This parameter exists for CALLERS OF THIS FUNCTION IN
    PYTHON — this process's own test suite, or `main()` after it has
    already read the nonce off disk via `--reuse-nonce-from`. It is NOT
    exposed as a CLI flag (see module docstring's R6-2 refinement): a
    secret belongs in a function argument passed in-process, never in
    argv, where any other process on the machine can read it via
    `ps`/`/proc` for this process's whole lifetime.

    R8-6 binding correction, 2026-08-15 (Kimi K3 round-8 review): the
    key file's first line used to carry ONLY the nonce — but the actual
    per-fixture shuffle is a function of nonce + `seed` + `candidates`
    (`_fixture_seed` folds in `seed_base`; `_blind_labels` shuffles
    exactly the `candidates` list it's given, and a Fisher-Yates shuffle
    over a DIFFERENT list — different length, order, or membership —
    produces a different result even from the identical seed). A re-run
    via `--reuse-nonce-from` that supplied the SAME nonce but a different
    `--seed` or `--candidates` therefore silently reproduced a DIFFERENT
    shuffle — exactly the outcome R6-2 says must fail loud, not happen
    quietly. `seed` and `candidates` are now written alongside the nonce
    on the key file's first line; `main()` adopts them from the key file
    on `--reuse-nonce-from` (conflict with an explicit CLI value fails
    loud, never silently prefers one) and fails loud (never falls back to
    the default) if an OLDER key file lacks them."""
    client: BenchClient = CodexSubscriptionBenchClient()
    if not client.available:
        _print_status("SKIPPED_UNAVAILABLE")
        print(
            "\nCodex subscription client unavailable (binary or local ChatGPT auth "
            "material missing). Nothing was run.\n"
            "Authenticate the existing subscription with `codex login`; do not add a "
            "paid OpenAI API key for this lane.\n",
        )
        return {"fixtures": 0, "skipped": 1}

    fixtures = _load_fixtures(fixtures_dir)
    if not fixtures:
        _print_status("SKIPPED_NO_FIXTURES")
        # R7-4 binding correction, 2026-08-15 (Kimi K3 round-7 review):
        # never interpolate `fixtures_dir` — the operator-chosen
        # `--fixtures-dir` path can be named after the export it holds
        # (same R6-3 class as `build_deid_corpus.py`'s `--input-dir`
        # discipline). Refer to it generically.
        print("No fixtures found under the --fixtures-dir you passed. Run build_deid_corpus.py first.")
        return {"fixtures": 0, "skipped": 1}

    # R9-4(b) binding correction, 2026-08-15 (Kimi K3 round-9 review):
    # defense in depth behind `main()`'s own key-file validation
    # (R9-4(a)) — a `candidates=[]` call reaching this function (whether
    # from a stale key file's now-tightened check, or a future caller
    # that skips `main()` entirely) must fail loud BEFORE any output file
    # is opened, not run zero models and let `_blind_labels([])` quietly
    # produce zero responses (which would leave `all_failed` False,
    # `total_responses == 0`, `main()` reporting `RAN`, exit 0, and no
    # model ever called).
    if not candidates:
        raise CandidatesEmptyError("candidates list is empty — nothing to benchmark")
    # R10-2 binding correction, 2026-08-15 (Kimi K3 round-10 review):
    # `if not candidates:` alone does not mirror the element-level
    # predicate the main()-level adoption check (R9-4(a)) already
    # enforces — `[""]` is truthy, so it passed this guard and only
    # failed later via the WRONG mechanism (`OpenAIModelNotAllowedError`
    # raised per-candidate deep inside `_run_one_fixture`, surfacing as
    # `RAN_ALL_FAILED` rather than the `FAILED_NO_CANDIDATES` this whole
    # fix exists to produce). The element check is a SEPARATE raise, not
    # folded into the emptiness check above, so the two failure modes get
    # distinct messages — the element's own content is never echoed
    # (same R6-3-class discipline as every other operator-input message
    # in this file; a candidate "name" could in principle be operator-
    # typed and shouldn't appear verbatim in a log line).
    if not all(isinstance(c, str) and c for c in candidates):
        raise CandidatesEmptyError("candidates list contains a non-string or empty-string element")
    # R10-3 binding correction, 2026-08-15 (Kimi K3 round-10 review): a
    # duplicate candidate name (`["gpt-5.6-terra", "gpt-5.6-terra"]`)
    # passes both checks above — it IS a non-empty list of non-empty
    # strings — but `_blind_labels` then binds two DIFFERENT blind labels
    # to the SAME underlying model, and a scorer reading the transcript
    # would judge them as independent candidates when they are not.
    # Rejected unconditionally here (this is the layer every caller
    # reaches, CLI included, even when `main()`'s own adoption-layer
    # duplicate check — added the same round for the `--reuse-nonce-from`
    # key-file path — does not apply).
    if len(set(candidates)) != len(candidates):
        raise CandidatesEmptyError("candidates list contains duplicate candidate names")

    run_nonce = nonce if nonce is not None else secrets.token_hex(16)

    _mkdir_private(output_dir)
    blind_path = output_dir / "blind_transcript.local.jsonl"
    key_path = output_dir / "label_key.local.jsonl"

    total_responses = 0
    error_responses = 0

    try:
        with _open_private(blind_path) as blind_f, _open_private(key_path) as key_f:
            # The nonce is the FIRST line of the key file, and ONLY there
            # — never in the blind transcript, never printed, never
            # logged (R6-2). A dedicated `{"nonce": ...}` row rather than
            # a bare string so the file stays uniformly one-JSON-object-
            # per-line, matching every other row this script writes.
            #
            # R8-6 binding correction, 2026-08-15 (Kimi K3 round-8
            # review): `seed`/`candidates` now ride alongside the nonce on
            # this same first line — the shuffle is a function of all
            # three (see `run_bench`'s own docstring above), so a
            # `--reuse-nonce-from` re-run needs all three to actually
            # reproduce this run's shuffle, not just the nonce.
            key_f.write(
                json.dumps({"nonce": run_nonce, "seed": seed, "candidates": candidates}, ensure_ascii=False) + "\n",
            )
            for fixture in fixtures:
                blind_row, key_row = await _run_one_fixture(
                    client,
                    fixture,
                    candidates=candidates,
                    seed_base=seed,
                    nonce=run_nonce,
                )
                blind_f.write(json.dumps(blind_row, ensure_ascii=False) + "\n")
                key_f.write(json.dumps(key_row, ensure_ascii=False) + "\n")
                # R6-6: count per-response failures across the whole run —
                # a run that "RAN" (exit 0) with EVERY response an
                # `[ERROR: ...]` placeholder is not a completed benchmark,
                # it's a run that never produced a provider response.
                #
                # R14-3 binding correction, 2026-08-15 (Kimi K3 round-14
                # review): this used to count failures by testing
                # `response_text.startswith("[ERROR:")` against
                # `blind_row["responses"]` — an IN-BAND sentinel on text
                # the underlying model actually controls. A genuine model
                # response that happens to start with the literal
                # `"[ERROR:"` (the model quoting an error message back, an
                # adversarial/red-team fixture, ...) would be miscounted
                # as a failure, and in the limit case where every fixture
                # response happened to start that way, this would flip
                # `all_failed`/`RAN_ALL_FAILED` on a run that actually
                # succeeded end-to-end. `_run_one_fixture` already
                # distinguishes success from failure STRUCTURALLY —
                # `key_row["attempts"][label]` (and `latency_ms`) is `None`
                # if and only if that label's `except` branch ran (see
                # `_run_one_fixture`'s own docstring) — so counting reads
                # that structural signal instead of pattern-matching
                # model-controlled text.
                for attempts_value in key_row["attempts"].values():
                    total_responses += 1
                    if attempts_value is None:
                        error_responses += 1
    finally:
        await client.close()

    all_failed = total_responses > 0 and error_responses == total_responses

    if all_failed:
        _print_status("RAN_ALL_FAILED")
        logger.error(
            "All %d responses across %d fixture(s) failed — this is NOT a completed "
            "benchmark pass, treat it as a run that never produced a provider response "
            "(check Codex subscription availability and the per-fixture warnings above).",
            total_responses,
            len(fixtures),
        )
    else:
        _print_status("RAN")
        if error_responses:
            # R8-10 binding correction, 2026-08-15 (Kimi K3 round-8
            # review): this was stale text post-R7-1 — it still said
            # "model/fixture pairs" when the per-fixture warning above
            # (`_run_one_fixture`) has named the LABEL, never the model,
            # since R7-1. Corrected to say what the warnings actually
            # name, plus where the label->model mapping actually lives.
            logger.warning(
                "%d of %d responses failed (partial failure, run still counts) — see "
                "per-fixture warnings above for which label/fixture pairs failed "
                "(cross-reference the key file's label_map for the real model).",
                error_responses,
                total_responses,
            )
    # R7-4 binding correction, 2026-08-15 (Kimi K3 round-7 review):
    # `blind_path`/`key_path` both embed the operator-chosen `--output-dir`
    # component — the same class of leak R6-3 already fixed for
    # `build_deid_corpus.py`'s output paths (a directory can be named after
    # the export/contact it holds), just not yet applied here. Log only the
    # file's own generated basename (always `blind_transcript.local.jsonl`
    # / `label_key.local.jsonl` — builder-fixed, never operator-chosen,
    # safe per the same reasoning as `_load_fixtures`'s R7-3 fix), and
    # refer to the directory generically.
    logger.info("Wrote blind transcript -> %s (chmod 0600) in the --output-dir you passed", blind_path.name)
    logger.info(
        "Wrote label key -> %s (chmod 0600) in the --output-dir you passed — DO NOT hand this to the scorer",
        key_path.name,
    )
    logger.info(
        "SCORING: hand only %s (from the --output-dir you passed) to a NON-OpenAI seat (sol "
        "judging sol/terra/luna is self-approval, mandate T4). This script does not score.",
        blind_path.name,
    )
    return {
        "fixtures": len(fixtures),
        "skipped": 0,
        "responses": total_responses,
        "errors": error_responses,
        "all_failed": all_failed,
    }


def main() -> int:
    from backend.llm.codex_exec_client import MODEL_LUNA, MODEL_SOL, MODEL_TERRA

    default_candidates = [MODEL_TERRA, MODEL_LUNA, MODEL_SOL]

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fixtures-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--candidates",
        nargs="+",
        # R8-6 binding correction, 2026-08-15 (Kimi K3 round-8 review):
        # default is now the sentinel `None`, not the real default list —
        # `main()` needs to tell "operator didn't pass --candidates" apart
        # from "operator explicitly passed the same three models", because
        # the two get different treatment under --reuse-nonce-from (see
        # below). The real default is applied further down.
        default=None,
        help=(
            f"Models to run per fixture, blind-labeled (default: "
            f"{MODEL_TERRA} {MODEL_LUNA} {MODEL_SOL} — sol is the quality-ceiling "
            f"reference, genuinely called, never scored by itself; see module docstring). "
            f"With --reuse-nonce-from, defaults to that run's OWN candidate list instead "
            f"(R8-6) — pass this explicitly only to deliberately reproduce with a DIFFERENT "
            f"list, which is itself a contradiction the tool refuses (a re-run needs the "
            f"same candidates to reproduce the same shuffle) unless it matches the key file."
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,  # R8-6: sentinel, see --candidates above for why.
        help=(
            f"Base seed for per-fixture label shuffling (default: {_DEFAULT_SEED}; with "
            f"--reuse-nonce-from, defaults to that run's OWN seed instead, R8-6)"
        ),
    )
    parser.add_argument(
        "--reuse-nonce-from",
        type=Path,
        default=None,
        help=(
            "Reproduce a prior run's exact label shuffle by pointing at that run's OWN "
            "label_key.local.jsonl file — the nonce is read from its first line, never "
            "typed on the command line (R6-2 refinement, orchestrator/Codex order, "
            "2026-08-15: a secret in argv is visible to any other process on the machine "
            "via ps/proc for this process's whole lifetime; a PATH in argv is fine, it "
            "identifies a file, not a secret value). Normally omitted — a fresh nonce is "
            "generated per run and written ONLY to the key file (R6-2). Since R8-6, the "
            "same file's 'seed'/'candidates' fields are also adopted (they are load-bearing "
            "for reproducing the exact shuffle, not just the nonce) unless you pass a "
            "conflicting --seed/--candidates explicitly, which fails loud rather than "
            "silently reshuffling."
        ),
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    reused_nonce: str | None = None
    final_seed: int
    final_candidates: list[str]

    if args.reuse_nonce_from is not None:
        # Read ONLY the first line — the nonce/seed/candidates row — never
        # the rest of the key file (which also names real per-fixture
        # models, out of scope for this read). A malformed/missing nonce
        # fails LOUD, not silently falling back to "generate a fresh one"
        # — an operator who asked to reproduce a specific shuffle and
        # silently got a different one would have no way to notice.
        #
        # R9-7 binding correction, 2026-08-15 (Kimi K3 round-9 review):
        # this comment said "Read ONLY the first line" while the code did
        # `read_text().splitlines()[0]` — which reads the ENTIRE file
        # (real per-fixture models and label assignments, the "rest of
        # the key file" this very comment says is out of scope) into
        # memory before discarding everything past the first newline.
        # Made true: `f.readline()` reads exactly one line off the file
        # object, the rest of the file is never pulled into memory. An
        # EMPTY file now yields `""` from `readline()` rather than
        # raising `IndexError` from `splitlines()[0]` — `json.loads("")`
        # already raises `json.JSONDecodeError`, already in the except
        # tuple below, so the fail-loud outcome for an empty file is
        # unchanged; `IndexError` is dropped from the tuple as dead
        # (unreachable via this read path any more).
        #
        # R7-2 binding correction, 2026-08-15 (Kimi K3 round-7 review): a
        # first line that is syntactically valid JSON but NOT a JSON object
        # — `[1,2]`, `42`, `"str"`, `null` — used to reach `["nonce"]`
        # directly and raise a raw `TypeError` (list/int/str/NoneType is
        # not subscriptable by a string key), which was NOT in the except
        # tuple below and therefore propagated as an unhandled traceback
        # instead of this function's promised clean `return 1`. Fixed by
        # parsing first, THEN checking `isinstance(parsed, dict)` before
        # any indexing — the isinstance check folds naturally into the
        # existing "is 'nonce' a non-empty string" validation below rather
        # than needing its own separate except clause.
        try:
            with args.reuse_nonce_from.open(encoding="utf-8") as f:
                first_line = f.readline().strip()
            parsed = json.loads(first_line)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            # R7-4 binding correction, 2026-08-15 (Kimi K3 round-7 review):
            # never interpolate `args.reuse_nonce_from` verbatim — same
            # R6-3 class as every other operator-chosen path in this file
            # (a path can be named after what it contains, e.g. a
            # contact-named directory). Refer to it generically.
            #
            # R8-9 binding correction, 2026-08-15 (Kimi K3 round-8 review):
            # `UnicodeDecodeError` added — R9-6 text correction, 2026-08-15
            # (Kimi K3 round-9 review): the fix itself was already right,
            # this comment's reasoning was not — `UnicodeDecodeError` IS a
            # subclass of `ValueError` (via `UnicodeError`), so it is a
            # SIBLING of `json.JSONDecodeError` (also a `ValueError`
            # subclass), not of `ValueError` itself. It is raised on a
            # binary/non-UTF-8 file — R10-5 text correction, 2026-08-15
            # (Kimi K3 round-10 review): this comment still said "raised
            # by `read_text(encoding="utf-8")`", stale since R9-7 replaced
            # that call with `open(encoding="utf-8")` + `f.readline()` —
            # by the file object's own text-mode decoding on `readline()`,
            # not by a `read_text()` call that no longer exists here — and
            # was NOT covered by the existing tuple, so it propagated raw.
            # Added explicitly rather than widening to bare `ValueError`,
            # which would also silently swallow unrelated `ValueError`s a
            # future change to this block might raise. The tuple entry
            # itself is unaffected by this correction — it was, and
            # remains, correct.
            # R10-1(a) binding correction, 2026-08-15 (Kimi K3 round-10
            # review): every `return 1` in this block used to skip
            # `_print_status` entirely — the `WA_BLIND_BENCH_STATUS=`
            # contract this module's own docstring presents as how ANY
            # outcome is machine-greppable was broken on all 9 early-exit
            # sites in the --reuse-nonce-from/adoption block. Fixed: a new
            # `FAILED_BAD_REUSE_FILE` status is printed before every exit
            # in this block EXCEPT the candidates-empty-or-malformed sites
            # below, which print `FAILED_NO_CANDIDATES` instead (symmetry
            # with the `run_bench`-level `CandidatesEmptyError` catch in
            # `main()`, R9-4(b)). R12-3 count correction, 2026-08-15 (Kimi
            # K3 round-12 review): "8" here was stale — recounted on disk
            # at 7 `FAILED_BAD_REUSE_FILE` sites + 2 `FAILED_NO_CANDIDATES`
            # sites, 9 total, not 8.
            _print_status("FAILED_BAD_REUSE_FILE")
            logger.error(
                "--reuse-nonce-from: could not read a nonce from the file you passed (%s)",
                type(exc).__name__,
            )
            return 1
        if not isinstance(parsed, dict) or not isinstance(parsed.get("nonce"), str) or not parsed.get("nonce"):
            _print_status("FAILED_BAD_REUSE_FILE")
            logger.error(
                "--reuse-nonce-from: the file you passed has no 'nonce' field, or it is not a "
                "non-empty string, on its first line",
            )
            return 1
        reused_nonce = parsed["nonce"]

        # R8-6 binding correction, 2026-08-15 (Kimi K3 round-8 review):
        # the shuffle also depends on `seed` and `candidates` — adopt them
        # from the key file, an explicit conflicting CLI value fails loud
        # (never silently prefers one over the other), and a key file that
        # PREDATES this fix (only "nonce", no "seed"/"candidates") fails
        # loud asking for the missing value explicitly rather than
        # silently falling back to today's default.
        file_seed = parsed.get("seed")
        if file_seed is not None:
            if not isinstance(file_seed, int) or isinstance(file_seed, bool):
                _print_status("FAILED_BAD_REUSE_FILE")
                logger.error("--reuse-nonce-from: the file you passed has a 'seed' field that is not an integer")
                return 1
            if args.seed is not None and args.seed != file_seed:
                _print_status("FAILED_BAD_REUSE_FILE")
                logger.error(
                    "--reuse-nonce-from: --seed %d conflicts with the key file's own seed %d — "
                    "reproducing a prior shuffle requires the SAME seed; drop --seed to inherit "
                    "it from the key file, or pass the matching value",
                    args.seed,
                    file_seed,
                )
                return 1
            final_seed = file_seed
        elif args.seed is not None:
            final_seed = args.seed
        else:
            _print_status("FAILED_BAD_REUSE_FILE")
            logger.error(
                "--reuse-nonce-from: the file you passed predates seed/candidates tracking "
                "(R8-6, only 'nonce' on its first line) — pass --seed explicitly to reproduce "
                "its shuffle; this never silently falls back to today's default",
            )
            return 1

        file_candidates = parsed.get("candidates")
        if file_candidates is not None:
            # R9-4(a) binding correction, 2026-08-15 (Kimi K3 round-9
            # review): `all(isinstance(c, str) for c in file_candidates)`
            # is vacuously True on `[]` — a key file with
            # `"candidates": []` used to be silently ADOPTED as a valid,
            # empty candidate list. Now requires at least one candidate,
            # and each string non-empty (an empty-string candidate name
            # is exactly as unusable as an absent list, and would slip
            # past the same vacuous-True trap one level down).
            if not (
                isinstance(file_candidates, list)
                and file_candidates
                and all(isinstance(c, str) and c for c in file_candidates)
            ):
                # R10-1(a): this site prints `FAILED_NO_CANDIDATES`, NOT
                # `FAILED_BAD_REUSE_FILE` — symmetry with the
                # `run_bench`-level `CandidatesEmptyError` catch in
                # `main()` (R9-4(b)): both report the same status for the
                # same underlying defect (an unusable candidates list),
                # regardless of which layer catches it first.
                _print_status("FAILED_NO_CANDIDATES")
                logger.error(
                    "--reuse-nonce-from: the file you passed has a 'candidates' field that is "
                    "not a non-empty list of non-empty strings",
                )
                return 1
            # R10-3 binding correction, 2026-08-15 (Kimi K3 round-10
            # review): a duplicate candidate name (`["terra", "terra"]`)
            # passed the check above (it IS a non-empty list of non-empty
            # strings) but produces two blind labels bound to the SAME
            # underlying model — a scorer reading the blind transcript
            # would judge them as independent candidates when they are
            # not. Rejected here too (adoption layer), mirroring the same
            # check `run_bench` now applies unconditionally (R10-3, this
            # function's own guard below) — this key-file path fails loud
            # BEFORE adoption rather than only when `run_bench` is reached.
            if len(set(file_candidates)) != len(file_candidates):
                _print_status("FAILED_NO_CANDIDATES")
                logger.error(
                    "--reuse-nonce-from: the file you passed has a 'candidates' field with duplicate candidate names",
                )
                return 1
            if args.candidates is not None and list(args.candidates) != list(file_candidates):
                _print_status("FAILED_BAD_REUSE_FILE")
                logger.error(
                    "--reuse-nonce-from: --candidates conflicts with the key file's own "
                    "candidate list — reproducing a prior shuffle requires the SAME candidates "
                    "in the SAME order; drop --candidates to inherit it from the key file, or "
                    "pass the matching value",
                )
                return 1
            final_candidates = file_candidates
        elif args.candidates is not None:
            final_candidates = args.candidates
        else:
            _print_status("FAILED_BAD_REUSE_FILE")
            logger.error(
                "--reuse-nonce-from: the file you passed predates seed/candidates tracking "
                "(R8-6, only 'nonce' on its first line) — pass --candidates explicitly to "
                "reproduce its shuffle; this never silently falls back to today's default",
            )
            return 1
    else:
        final_seed = args.seed if args.seed is not None else _DEFAULT_SEED
        final_candidates = args.candidates if args.candidates is not None else default_candidates

    # R8-11 binding correction, 2026-08-15 (Kimi K3 round-8 review): a
    # malformed corpus (`FixtureFormatError`, raised by `_load_fixtures`
    # inside `run_bench` — R7-3/R8-1) used to propagate raw through
    # `asyncio.run`/`main()` with NO `WA_BLIND_BENCH_STATUS=` line printed
    # at all, contrary to this module's own docstring, which presents that
    # status line as how ANY outcome is machine-greppable. Caught here and
    # reported as the new `FAILED_BAD_FIXTURES` status, non-zero exit,
    # same clean-failure posture as every other malformed-input path in
    # this file.
    try:
        stats = asyncio.run(
            run_bench(
                fixtures_dir=args.fixtures_dir,
                output_dir=args.output_dir,
                candidates=final_candidates,
                seed=final_seed,
                nonce=reused_nonce,
            ),
        )
    except FixtureFormatError as exc:
        _print_status("FAILED_BAD_FIXTURES")
        logger.error("Fixtures corpus is malformed, nothing was run: %s", exc)
        return 1
    except CandidatesEmptyError as exc:
        # R9-4(b): defense-in-depth path — `main()`'s own key-file
        # validation (R9-4(a)) should already have caught an empty
        # `candidates` list before `run_bench` was ever called; this
        # catches the case where it didn't. R10-2/R10-3 (Kimi K3 round-10
        # review) widened what this can mean — empty, a non-string/
        # empty-string element, or a duplicate name — the log text below
        # is now generic ("invalid", not "empty") to match.
        _print_status("FAILED_NO_CANDIDATES")
        logger.error("Candidates list is invalid, nothing was run: %s", exc)
        return 1
    except OSError as exc:
        # R10-1(b) binding correction, 2026-08-15 (Kimi K3 round-10
        # review): an `OSError` raised inside `run_bench` — from
        # `_mkdir_private`/`_open_private` (permission failure, a
        # pre-planted symlink refused per R8-13/R9-8, disk full, ...) —
        # propagated raw through `asyncio.run`/`main()` with no
        # `WA_BLIND_BENCH_STATUS=` line printed, the same broken-contract
        # shape R8-11 already fixed for `FixtureFormatError`. Caught here
        # and reported as the new `FAILED_IO` status. The log line
        # deliberately logs ONLY the exception TYPE name, never
        # `str(exc)` — an `OSError`'s message commonly embeds the
        # filesystem path that triggered it (the operator's own
        # `--output-dir`/`--fixtures-dir`/`--reuse-nonce-from` value, or a
        # symlink target), and this file's R6-3/R7-4 discipline never logs
        # an operator-chosen path verbatim.
        _print_status("FAILED_IO")
        logger.error("I/O error while running the benchmark: %s", type(exc).__name__)
        return 1
    logger.info("Done: %s", stats)
    # R6-6: a run where every response failed is not a completed benchmark
    # pass — non-zero so a wrapper/operator sees it as distinct from a
    # genuine (possibly partial-failure) RAN.
    if stats.get("all_failed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
