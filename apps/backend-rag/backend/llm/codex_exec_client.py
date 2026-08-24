"""Codex-exec subscription provider — OFFLINE, standalone provider adapter.

Owner credential-path ruling recorded by this client (2026-08-15, Zero,
direct, Legge 5 — see
`research/operations/2026-08-15-adr-wa-runtime-openai-provider.md` §30): if a
separately reviewed future WA OpenAI runtime is authorized, its intended path
is the **ChatGPT Pro SUBSCRIPTION** (headless `codex exec`), not a per-token
OpenAI API key. The current authorization is narrower: this module may be used
only by the human-run offline evidence harness. The ruling does not authorize
a service credential, runtime wiring, real client text, traffic, deployment,
or cutover. The council's runtime-risk analysis stays recorded as history.
`OPENAI_WA_PROVIDER_API_KEY` (the sibling `openai_responses_client.py`'s
credential) is not provisioned under this ruling; that client stays in-tree
as a DORMANT, reviewed alternative — this module does not import it, replace
it, or delete it.

⚠️ THIS FILE HAS ZERO WIRING. Nothing in `backend/services/rag/agentic/` or
any other live module imports it. No config flag, no gateway branch, no
hot-path reference exists anywhere in this repo — grep it yourself before
trusting this comment. Any live use still requires a separate runtime design,
security/privacy review, context-parity evidence, and explicit activation
authorization; none is supplied by this file or ruling.

Design mirrors `openai_responses_client.py`'s discipline (read that module's
docstring first): a property-based `available` that never raises on
construction, a typed exception hierarchy so a caller can distinguish
failure classes without ever seeing raw remote/subprocess content, and
"fail-closed on shape, not just on transport/exit-code" applied to a
subprocess boundary instead of an HTTP one.

Binding invariants (R24-1, mandate 2026-08-15):

1.  **Async subprocess only.** `asyncio.create_subprocess_exec` — never
    `shell=True`, never a shell string, never `subprocess.run`. Argv is a
    fixed shape: `codex exec --sandbox read-only --skip-git-repo-check
    --ephemeral --ignore-user-config --ignore-rules -m <model> -`. `cwd` is a
    FRESH, EMPTY, per-call temp
    directory created via `tempfile.mkdtemp()` and removed in a `finally`
    block — never the repo, never the caller's inherited cwd, never a shared
    `/tmp` used by other processes. **Two independent things are needed here,
    not one** (R25-1 correction, 2026-08-15 THAW round — an earlier draft of
    this module relied on cwd neutrality alone and that was not sufficient):
    cwd neutrality stops REPO-LOCAL context (this repo's own
    `.claude/`-relative project config) from leaking in; `--ignore-user-config`
    separately stops USER-level config — including `~/.codex/config.toml`'s
    hooks — from running at all, regardless of cwd. This was not a
    theoretical concern: during this module's original grounding probe (see
    point 7 below), one invocation was accidentally run from the repo
    worktree's cwd instead of a neutral dir, and `codex exec` picked up this
    repo's own Claude-hook machinery (`SessionStart`, `UserPromptSubmit`, a
    cross-machine "Peer Pro" ping) and answered in a machine-specific persona
    ("[Air-M5] Pong. Peer Pro non raggiungibile") — empirical proof that an
    unset/inherited cwd leaks ambient repo/host context into the model's
    turn. A follow-up adversarial round (R25-1) then flagged a SEPARATE risk
    the neutral-cwd fix alone did not close: `codex exec --help` documents
    `--ignore-user-config` as "Do not load `$CODEX_HOME/config.toml`; auth
    still uses `CODEX_HOME`" — meaning HOST-level hooks configured in the
    user's own `~/.codex/config.toml` (not this repo's config) run
    regardless of cwd, and a `UserPromptSubmit` hook is a host command that
    receives the prompt text OUTSIDE the model's own sandbox — the exact
    class of leak the "[Air-M5]" persona above is one instance of. Re-measured
    (point 7): with `--ignore-user-config` added, the same PONG probe from
    the same neutral cwd produced stderr with NO `hook:` lines at all — the
    fix is confirmed on the wire, not just reasoned about. A per-call empty
    tempdir is also a stronger guarantee than "a directory outside the repo":
    it cannot leak even another local process's temp files back through the
    sandboxed read-only filesystem access `codex exec` grants the model.

    `--ephemeral` prevents Codex from persisting session files, while
    `--ignore-rules` prevents user/project exec-policy rule files from being
    loaded. These are separate controls from the neutral cwd and
    `--ignore-user-config`; none substitutes for another.

    **The tempdir cleanup and the child process lifecycle must agree, even
    under cancellation** (R26-1 fix, 2026-08-15 THAW round): `generate()`
    now has a dedicated `except asyncio.CancelledError:` arm around
    `communicate()` that reaps the child before re-raising. Before this fix,
    `asyncio.CancelledError` (a `BaseException` subclass since Python 3.8,
    NOT caught by `except Exception:`) would bypass reaping entirely on task
    cancellation (a client disconnect, an upstream abort) — the `finally`
    block's `shutil.rmtree(neutral_dir, ...)` would then delete the
    per-call tempdir out from under a still-alive, now-orphaned `codex`
    child process. The sibling `except Exception:` arm in the same
    `communicate()` block (R25-5, same round — widened from
    `TimeoutError`-only reaping to every non-`CancelledError` exception) now
    converts the arbitrary underlying failure to
    `CodexExecCommunicationError` after reaping. Raw OS/provider exception
    text does not cross the adapter boundary.

2.  **Prompt text NEVER on argv, NEVER in the child env** (W115 scar: argv is
    `ps`-readable by every user on the box; the same lesson this repo
    learned the hard way in `apps/mouth-cell/mail_loop` passing a client's
    message as a `claude -p <prompt>` argv value). Verified offline against
    `codex exec --help`: "[PROMPT] ... If not provided as an argument (or if
    `-` is used), instructions are read from stdin." This client always
    passes the literal argv token `-` and writes the prompt to the child's
    **stdin** via `proc.communicate(input=prompt.encode())`. If the binary
    cannot be resolved at all, `generate()` fails closed with
    `CodexExecUnavailableError` before ever touching argv/stdin — there is
    no fallback path that would put the prompt on argv.

3.  **`available` is a property, fail-closed, computed fresh on every read**
    (never cached, never raises) from binary presence — resolution order:
    constructor `binary=` arg, else env `WA_CODEX_BIN`, else `codex` resolved
    on `PATH` via `shutil.which` — AND auth-material presence: an `auth.json`
    file under `CODEX_HOME` (constructor `codex_home=` arg, else env
    `CODEX_HOME`, else `~/.codex`) that exists and is non-empty.
    `generate()` raises `CodexExecUnavailableError` when `available` is
    `False`; it never raises on construction.

    ⚠️ MEASURED CAVEAT, corrected 2026-08-18 (see point 7): file presence is
    a NECESSARY but NOT SUFFICIENT proxy for "a real call will succeed".
    A 2026-08-15 probe appeared to authenticate with an empty isolated
    `CODEX_HOME`, which led to an explicitly labelled inference that a
    macOS Keychain credential might exist outside that directory. A fresh
    reproduction attempt on 2026-08-18 did **not** reproduce that result:
    `codex login status` reported "Not logged in" and `codex exec` failed
    with HTTP 401, while the default authenticated `CODEX_HOME` succeeded.
    This adapter therefore does not rely on an inferred Keychain fallback.
    `available=True` means only "the configured auth file exists and is
    non-empty", not "the credential is live"; point 5's real-call
    auth-death handling remains necessary.

    **The gate and the child MUST agree by construction** (R25-2 fix,
    2026-08-15 THAW round): `_build_env` now always injects
    `CODEX_HOME=str(self._resolve_codex_home())` — the SAME value `available`
    just checked — regardless of whether that value came from the explicit
    constructor arg, the `CODEX_HOME` env var, or the `~/.codex` default. An
    earlier draft injected `CODEX_HOME` into the child env ONLY when the
    constructor received an explicit `codex_home=` argument, which meant a
    caller relying on the `CODEX_HOME` env var alone could pass the
    `available` gate (which DOES honor the env var) while the spawned child
    silently fell back to `codex`'s own unrelated default resolution — a
    gate validating one directory while the subprocess sees another. This is
    now structurally impossible: both `available` and `_build_env` call
    `_resolve_codex_home()`, there is no second code path.

4.  **Judge the OUTPUT, not just the RC** (W104 scar). Both stdout and
    stderr are ALWAYS read via `communicate()` and decoded before either is
    even looked at — but they are NOT both consulted as a verdict SIGNAL on
    every path (R25-6 doc-accuracy fix, 2026-08-15 THAW round: an earlier
    draft of this sentence claimed they are judged "together" unconditionally,
    which was false against this module's own point-5 scoping — the honest
    statement is: on `exit_code == 0`, stderr is decoded but never scanned,
    per the stderr-echoes-the-prompt finding below; only stdout decides the
    result. stderr becomes a signal source ONLY on `exit_code != 0`, per
    point 5). The deterministic output contract, MEASURED against a real
    `codex exec` invocation (point 7):
      - On `exit_code == 0`, **stdout is the answer, and nothing else** —
        no banner, no metadata, no session id. `text = stdout.strip()`.
        Empty/whitespace-only stdout on a zero exit is a shape violation,
        never a best-effort empty answer: raises `CodexExecOutputShapeError`.
      - stderr on a *successful* run is NOT clean metadata-only noise — it
        is a full human-readable transcript: a banner (`workdir`/`model`/
        `sandbox`/`session id`), then a literal `user\n<the prompt text>`
        echo, then hook/warning lines, then a literal `codex\n<the answer
        text>` echo, then a token-count footer. Because stderr echoes
        CLIENT-SUPPLIED prompt text verbatim, this client never treats
        `exit_code == 0` stderr as a signal source (see point 5 — the
        auth-death scan is `exit_code != 0` only) and never logs it.
      - Un-parseable output (a shape this contract does not recognise) never
        falls back to a best-effort partial answer.

5.  **Auth-death detection, distinguished from generic failure** (house scar
    2026-05-24, same class `claude_oauth_client.py::_classify_cli_diagnostic`
    exists for). On `exit_code != 0`, STDERR ONLY is scanned — stdout is
    NEVER part of the scanned text (CORRECTED, R27-3, 2026-08-15: this lead
    sentence previously said "stdout+stderr are scanned", which was true
    only through the R25-3/R26-2 intermediate design and false against the
    FINAL one — see the "scan SURFACE itself was wrong" paragraph below for
    the full evolution) — after stripping, WHOLE-LINE-ONLY, any stderr line
    that verbatim-equals the exact prompt text the caller supplied OR the
    run's own stdout content (R25-3 fix, 2026-08-15 THAW round: the
    transcript echoes the ANSWER too when one was produced before a late
    failure, not only the prompt, so stripping the prompt alone left that
    second echo scannable) for a bounded set of auth-failure word classes —
    see `_AUTH_STRUCTURED_RE`/`_AUTH_PROSE_RE` (B2b split, superseding the
    single `_AUTH_DEATH_RE` this paragraph originally named) for the exact,
    context-anchored
    patterns (bare `401` was REMOVED after R25-3 found it false-positived on
    ordinary text like "completed after 401 ms"; only `401` in explicit
    auth-shaped context — `401 unauthorized`, `error 401`, `http 401` —
    counts now) — defusing the stderr-echoes-the-prompt risk from point 4: a
    WA immigration bot's real traffic routinely contains words like
    "login"/"expired"/"unauthorized" as normal Indonesian-visa vocabulary,
    not diagnostics — and raise the distinct `CodexExecAuthError` — never
    folded into the generic `CodexExecProcessError` a caller would otherwise
    get for any other non-zero exit. Deliberately scoped to `exit_code != 0`
    only: this client's own success-path stderr echoes the model's answer
    verbatim (see point 4), and scanning THAT for the same word classes
    would be a textbook cicatrix family #3 guard-over-match — a legitimate
    answer about an expired KITAS or a portal login flow would spuriously
    classify as an auth-death of the CLIENT's OWN credential.

    ⚠️ UNMEASURED (declared, not silently assumed): the exact stderr shape
    `codex exec` prints for its OWN auth failure was not empirically
    triggered — doing so would have required logging out of the operator's
    real, working ChatGPT Pro session, which this offline/no-wiring phase
    does not authorize. The word-class list above is built from `codex
    login status`'s measured "Not logged in" string (point 3) plus the
    house pattern already proven in production by
    `claude_oauth_client.py::_AUTH_DIAGNOSTIC_PATTERN`. Test fixtures for
    this path are CONSTRUCTED, not measured, and are labelled as such.

    **The stripping mechanism itself was fail-OPEN, not just imprecise**
    (R26-2 fix, 2026-08-15 THAW round): the R25-3 fix above stripped known
    text via whole-text `str.replace()` — a global substring removal. When
    the run's own stdout is short/common (a one-word answer like `"in"`),
    that removal corrupted UNRELATED, genuinely diagnostic stderr text: `"in"`
    would strip the `"in"` inside `"not logged in"` too, silently turning a
    real auth failure into a non-match at the worst possible moment. The
    fix (`_strip_known_lines`, replacing `_strip_known_texts`) operates at
    LINE granularity — a stderr line is dropped only if it wholly EQUALS a
    line of the known text (EQUALITY ONLY, R27-1 fix, 2026-08-15 THAW round
    — the first version of this function ALSO dropped a stderr line that was
    merely a substring of a known line, which is its own fail-open: a
    genuine diagnostic line that happens to be textually contained in the
    prompt, e.g. a client asking "why am I not logged in after midnight" with
    stderr independently reporting the exact diagnostic line "not logged
    in", would have been dropped and never reached the regex, at the exact
    moment it must page); a surviving line is NEVER internally mutated, so a
    short candidate can no longer carve a hole out of an unrelated
    diagnostic line. See `_strip_known_lines`'s own docstring for the full
    mechanism and why line-granularity still defeats the R25-3
    boundary-adjacency case it was built for.

    **The regex's own trailing boundary had a latent gap** (R26-3 fix, same
    round): the group's closing `\b` failed to account for the LAST
    alternative's optional trailing backtick (`` `?``) — a backtick followed
    by a space or end-of-string is non-word on both sides, so a plain `\b`
    is unsatisfied for the branch that consumed the backtick (Python's `re`
    engine backtracks the optional group in every case this module tested
    and still finds a match without it — see the ADR §30.7 for the honest
    record of what did and did not reproduce empirically — but the fix is
    correct and strictly safer regardless of that nuance). `(?!\\w)` replaces
    the trailing `\b`: satisfied at end-of-string and after any non-word
    character without requiring a same-position transition, correct after
    both a word ending and a non-word (backtick) ending.

    **The scan SURFACE itself was wrong, not just the stripping mechanism**
    (R26 GLM addendum, F26-1 HIGH + F26-4, 2026-08-15 THAW round — supersedes
    the two-stream-concatenation shape the R26-2 fix above still used):
    concatenating `_strip_known_lines(stdout, prompt) + "\\n" +
    _strip_known_lines(stderr, prompt, stdout)` still put the model's OWN
    ANSWER into the scanned text whenever a partial answer preceded a late
    failure — constructed example: stdout = "Your KITAS login has expired;
    you are unauthorized until renewal (401 on the portal)." with a clean,
    unrelated stderr would still false-page, because that sentence was never
    stripped from ITSELF. Worse, the `"\\n"` join between the two
    independently-stripped streams was itself a seam the (then single)
    `_AUTH_DEATH_RE`'s `\\s+` alternatives could bridge across (every
    alternative uses `\\s+`, which matches a newline too). Fix, UNIFIED —
    one design closing both this finding and the R26-2 mangle finding
    above, not two overlapping patches: (a) the scan reads STDERR ONLY now
    — stdout is no longer part of the scanned text at all. Declared, not
    silently assumed: no measured evidence (point 7) places `codex exec`'s
    own diagnostics on stdout — every measured and constructed auth-shaped
    fixture is stderr-only — and dropping stdout from the scan surface is
    also the only way to stop a legitimate partial answer that happens to
    discuss the CLIENT's own "expired"/"unauthorized" situation from paging
    on itself, the exact guard-over-match this point's success-path stderr
    scoping already avoids elsewhere. (b) stderr is still stripped of known
    prompt/stdout LINES via `_strip_known_lines` (R26-2, unchanged
    mechanism) before scanning — still necessary because stderr's own
    transcript echoes both. (c) the scan itself, as of B2b (2026-08-25),
    goes through `_classify_stderr` (superseding this paragraph's original
    `_auth_death_detected(*texts)`, which the B2b redesign folded into the
    same per-line, multi-class engine that now also covers quota/policy —
    see the block comment above `MatchConfidence`), which still classifies
    each STDERR LINE independently and never joins lines with a separator
    first — the concatenation seam this paragraph describes stays closed
    structurally, not only for the auth word class or today's
    single-argument call site. See `_classify_stderr`'s own docstring
    and `TestAuthDeathDetection`'s R26-addendum tests (late-failure-partial-
    answer innocence, and a direct boundary-formation guilt test on the
    helper itself).

6.  **Sanitized errors/logs.** No prompt text, no raw stdout/stderr content,
    no auth material (not even a file path's existence bit beyond the
    boolean `available` result) ever reaches an exception message or a log
    line. `CodexExecProcessError` carries only the numeric exit code;
    `CodexExecAuthError`/`CodexExecOutputShapeError`/`CodexExecTimeoutError`/
    `CodexExecCommunicationError` carry only fixed local literals. Full type
    hints throughout; `logger` never `print`.

7.  **GROUNDING PROBE.** One designated live call was run from this session
    in the original R24 round (`printf 'Reply with exactly PONG' | codex
    exec --sandbox read-only --skip-git-repo-check -m gpt-5.6-terra -`, cwd
    `/tmp/codex-probe-neutral`, 2026-08-15): `exit_code=0`,
    `stdout=b'PONG\\n'`, and a stderr transcript that (that round did not yet
    know to test for) included `hook:` lines — see point 1. R25-1 authorized
    ONE additional re-measure with the fixed argv
    (`... --skip-git-repo-check --ignore-user-config -m gpt-5.6-terra -`,
    cwd `/tmp/codex-probe-neutral-r25`, same THAW round): `exit_code=0`,
    `stdout=b'PONG\\n'` (unchanged), and stderr with the SAME banner/echo
    shape but ZERO `hook:` lines — confirming `--ignore-user-config` closes
    the point-1 finding on the wire. The re-measured fixtures are what
    `test_codex_exec_client.py`'s `_MEASURED_SUCCESS_STDOUT` /
    `_MEASURED_SUCCESS_STDERR` now hold (replacing the R24 originals) — the
    RE-MEASURED transcript IS captured verbatim there. CORRECTED (R26 GLM
    addendum, F26-5, 2026-08-15): this sentence previously claimed "both
    probe transcripts are quoted in the ADR §30 for provenance" — false.
    Only the re-measured (R25) transcript survives, in the test fixture
    above, not inline in the ADR. The ORIGINAL R24 transcript — the one that
    actually contained the `hook:` lines cited two sentences up as the
    point-1 finding's evidence — was overwritten in place by the re-measure
    and is not preserved verbatim anywhere in this tree or in git history
    (`git log -p` on the test file shows a single commit already containing
    only the re-measured content). What remains of it is this narrative
    description (`hook:` lines present, no verbatim quote) — declared as a
    gap, not silently smoothed over. See ADR §30.8 for the full disposition.
    Beyond these two designated probes, two additional non-PII diagnostic calls
    were made in the original R24 round — one that (by operator error, cwd
    left at the repo default) demonstrated the point-1 cwd-leak finding
    before `--ignore-user-config` existed, and one `CODEX_HOME` variant that
    produced the historical point-3 auth-proxy finding. Three additional
    synthetic, non-PII calls were made on 2026-08-18: two attempts with a
    fresh isolated `CODEX_HOME` failed at authentication ("Not logged in" /
    HTTP 401), created no session file, and left no sentinel residue; one
    call through this adapter's final argv, using the default authenticated
    ChatGPT-subscription home, returned a runtime-generated sentinel exactly,
    left the observed session-file count unchanged (`3273 -> 3273`), and left
    zero files containing that sentinel under `~/.codex`. These observations
    are deliberately narrow: they demonstrate the measured call and the
    searched surfaces, not universal absence of every possible persistence
    surface. All seven calls are declared rather than hidden; no further live
    calls are planned. Everything else in this module (timeout,
    model-not-allowed, malformed output shapes) is OFFLINE, faking at the
    SUBPROCESS boundary per W114 discipline: the fake speaks the measured
    wire shape for the success path, and an honestly labelled constructed
    shape for the paths that were not (and, per this phase's scope, should
    not be) empirically triggered.

Scope boundary (explicit, identical to the sibling client): this module is a
pure provider — it turns (prompt in) into (text out). It does not touch
retrieval, abstention, provenance, PricingTool/auth, PII handling, cache,
routing, rate-limiting, audit, or human handoff. It has no caller in this PR.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import os
import re
import shutil
import signal
import tempfile
import time
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model governance — same GPT-5.6 family as the sibling Responses client
# (CLAUDE.md §5), duplicated here rather than imported: this module and
# `openai_responses_client.py` are two independent, offline, no-wiring
# adapters — coupling them via a shared import would make an edit to one
# silently affect the other's model allowlist, which neither module's own
# docstring would then accurately describe. `MODEL_TERRA` (balanced) is the
# default per the mandate; `MODEL_SOL`/`MODEL_LUNA` remain reachable via an
# explicit `generate(model=...)` call.
# ---------------------------------------------------------------------------
MODEL_SOL = "gpt-5.6-sol"
MODEL_TERRA = "gpt-5.6-terra"
MODEL_LUNA = "gpt-5.6-luna"
DEFAULT_MODEL = MODEL_TERRA
_ALLOWED_MODELS: frozenset[str] = frozenset({MODEL_SOL, MODEL_TERRA, MODEL_LUNA})

# Env var overriding binary resolution — see `available`/point 3 above.
_ENV_BIN = "WA_CODEX_BIN"
_DEFAULT_BINARY_NAME = "codex"
_ENV_CODEX_HOME = "CODEX_HOME"
_DEFAULT_CODEX_HOME_SUBDIR = ".codex"
_AUTH_FILE_NAME = "auth.json"

_DEFAULT_TIMEOUT_S = 60.0

_FIXED_ARGV_PREFIX: tuple[str, ...] = (
    "exec",
    "--sandbox",
    "read-only",
    "--skip-git-repo-check",
    # CLI 0.147.0: "Run without persisting session files to disk." This is
    # mandatory for every de-identified replay and cannot be disabled by a
    # caller.
    "--ephemeral",
    # R25-1 (2026-08-15 THAW round): neutral cwd alone stops REPO-local
    # context from leaking in but does NOT stop USER-level config
    # (`~/.codex/config.toml`) hooks from running regardless of cwd — see
    # point 1's docstring. `codex exec --help`: "Do not load
    # `$CODEX_HOME/config.toml`; auth still uses `CODEX_HOME`" — auth
    # resolution is unaffected, only host-config-driven hooks are disabled.
    "--ignore-user-config",
    # Separate from user config: suppress user/project exec-policy `.rules`
    # files so host policy cannot silently alter this provider contract.
    "--ignore-rules",
)
# The literal argv token that tells `codex exec` to read the prompt from
# stdin regardless of whether stdin happens to be piped (`codex exec --help`:
# "If not provided as an argument (or if `-` is used), instructions are read
# from stdin.") — never the prompt text itself (point 2 above).
_STDIN_SENTINEL = "-"

# ---------------------------------------------------------------------------
# B2b (2026-08-25) — REDESIGNED per
# docs/plans/2026-08-25-due-bot-live/SPEC-codex-error-classification.md.
# SUPERSEDES B2a's fixed-order, first-match-wins design (commit 0590b1ce3).
#
# B2a's own in-file comment (now deleted) claimed the three word classes
# "are independent vocabularies by construction — a stderr line cannot
# legitimately match more than one" and used that to license a fixed
# auth -> quota -> policy-blocked check order. A fenced cross-family
# refuter (gpt-5.6-sol, xhigh) reproduced 12 findings proving that claim
# FALSE — see
# `docs/plans/2026-08-25-due-bot-live/evidence/b2a-refuter-gpt56sol.txt`.
# The flagship one: `Error: token has expired; refresh failed with 429 too
# many requests` matches AUTH (prose "token has expired") AND QUOTA
# (structured "429 too many requests") on the SAME line — a realistic
# causal chain (expired token -> refresh attempt -> refresh rate-limited),
# not a constructed edge case. Fixed check order silently picked AUTH and
# sent an operator to `codex login` for something login cannot fix.
#
# This design closes the defect with four properties (SPEC P1-P4), not by
# tuning alternatives (SPEC: "[t]uning the alternatives closes those and
# widens the over-match surface at the same time. That trade has no good
# side."):
#
#   P1 — every class is evaluated, never just the first hit. Two classes
#        matching one payload is a DEFINED outcome (AMBIGUOUS,
#        `CodexExecAmbiguousError`), not a silent precedence — UNLESS a
#        stated reason justifies resolving it (P3 below), in which case the
#        code says so and the suppressed candidate(s) survive on the raised
#        exception (`.suppressed`), never silently dropped.
#   P2 — classification happens PER LINE, never across the whole blob. A
#        stderr is split on `\n` before any pattern ever runs (see
#        `_classify_stderr`); no pattern can bridge two records. This kills
#        the newline-bridging class of finding (`quota\nexceeded`,
#        `content\npolicy`) by construction, not by pattern care.
#   P3 — every word class is split into a STRUCTURED tier (an error code,
#        an HTTP-status-shaped token, another machine-readable marker) and
#        a PROSE tier (natural-language phrasing). When multiple classes
#        match and exactly one of them matched at the STRUCTURED tier, that
#        one wins — machine-readable evidence outranks a guess about
#        ordinary prose. This is the ONLY precedence rule in this module,
#        fully stated here, applied in exactly one place
#        (`_classify_stderr`).
#   P4 — confidence (`MatchConfidence.HIGH` for a structured-tier hit,
#        `.LOW` for a prose-tier-only hit) travels with the result, all the
#        way onto the raised exception (`confidence=` kwarg) and into
#        `codex_broker_wire.py`'s detail field. An unmeasured prose guess
#        and a matched error code are never presented as the same fact.
#
# P5 ("unknown stays unknown") and P6 (guilt AND innocence per class) are
# enforced by the pattern content itself and by
# `backend/tests/llm/test_codex_exec_client.py` respectively — not by this
# module's structure. P7 (disjointness, if claimed, is TESTED on realistic
# COMPOSITE payloads) is what this comment block's predecessor got wrong:
# the pre-B2b `TestWordClassDisjointness` tested each vocabulary's own
# alternatives in isolation and reported the payload-level claim settled —
# that was the weaker test the B2a landing commit's own narrative names.
# The corrected tests construct the SAME composite strings the refuter
# used.
#
# The SPEC's "Arming condition" (nothing here is trusted until a REAL codex
# exec quota event and a REAL policy block are observed) is expressed
# structurally, not just by comment: POLICY_BLOCKED has NO structured tier
# at all (nobody has ever seen what `codex exec` prints on a policy block —
# there is no machine-readable anchor to give it one), so every
# `CodexExecPolicyBlockedError` this module can ever raise carries
# `confidence=MatchConfidence.LOW` by construction. A caller that treats
# LOW confidence as advisory-only (never an irreversible action) honors the
# arming condition without needing to re-read this comment to know it.
# ---------------------------------------------------------------------------


class MatchConfidence(StrEnum):
    """How a matched word class was recognised. `HIGH` — a STRUCTURED,
    machine-readable token (an HTTP-status-shaped phrase, a `snake_case`
    error-code identifier) fired. `LOW` — only a PROSE, natural-language
    phrase fired. SPEC P3/P4: never presented as the same fact; see the
    B2b block comment above for the one place this drives a decision."""

    HIGH = "HIGH"
    LOW = "LOW"


class _WireWordClass(StrEnum):
    """The stderr word classes this module recognises — a strict SUBSET of
    F3's closed wire vocabulary (`codex_broker_wire.py`): F3's
    `TIMEOUT`/`HOST_OFFLINE` never come from stderr-pattern matching at all
    (a wall-clock deadline, a missing binary — both determined
    structurally), so neither has a member here. `OUTPUT_OVERSIZED` maps
    onto the PRE-EXISTING F3 member `OUTPUT_INVALID` alongside the
    empty-stdout-on-exit-0 path (Ruling A — see `OutputShapeReason`); it is
    not itself a new F3 member."""

    AUTH_DEATH = "AUTH_DEATH"
    QUOTA = "QUOTA"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    OUTPUT_OVERSIZED = "OUTPUT_OVERSIZED"


# Auth-death word class — mirrors (does not import, per point 6's "no
# cross-file assumptions") `claude_oauth_client.py::_AUTH_DIAGNOSTIC_PATTERN`.
# Only "not logged in" is measured (`codex login status`); the rest is
# constructed, plausible wording — see point 5's docstring (module header)
# for the full R24-R28 provenance history, which is otherwise unchanged by
# this round: the auth vocabulary's CONTENT is not what the refuter found
# defective, only its participation in the old fixed-order dispatch was.
#
# STRUCTURED (HIGH): HTTP-status-shaped phrases and `snake_case`
# error-code identifiers. The digit-anchored alternatives keep `\b`/
# `(?!\w)` word boundaries (a stray "3401" must not match); the underscored
# identifiers do NOT require a boundary at either edge — a namespaced/
# suffixed compound identifier like `token_revoked` carries essentially
# zero over-match risk in ordinary prose regardless of what precedes or
# follows it (see `_QUOTA_STRUCTURED_RE`'s comment below for the reproduced
# finding that makes this concrete for the sibling quota token).
_AUTH_STRUCTURED_RE: re.Pattern[str] = re.compile(
    r"\b401\s+unauthorized\b|\berror\s+401\b|\b401\s+error\b|\bhttp\s+401\b|"
    r"token_revoked|refresh_token(?:_reused|_revoked|_expired)?",
    re.IGNORECASE,
)

# PROSE (LOW): natural-language phrasing. Every phrase is deliberately
# SPECIFIC (word-boundary AND multi-word where the single word alone is
# common in ordinary text) — e.g. "token has expired" not bare "expired"
# (which appears in perfectly normal WA traffic: "my passport expired last
# month"), "sign in"/"sign-in" not bare "sign" (which appears in "please
# sign the form"). This guard pages a human on a match, so both an
# under-match (a real auth failure nobody hears about) and an over-match (a
# false page on ordinary visa-vocabulary text) cost real operator time.
_AUTH_PROSE_RE: re.Pattern[str] = re.compile(
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

# Quota-exhaustion word class — F3 (docs/plans/2026-08-25-due-bot-live/MANDATE.md):
# "Closed wire error vocabulary: AUTH_DEAD | QUOTA | TIMEOUT | ... — auth and
# quota MUST be distinct (today they collapse; split before arming)."
#
# UNVERIFIED HYPOTHESIS (see the B2b block comment's Arming Condition
# paragraph above): this pattern has never been validated against a real
# `codex exec` quota-exhaustion event. The vocabulary is CROSS-REFERENCED
# from a DIFFERENT CLI's cascade-detection grep (`~/.claude/CLAUDE.md`
# §Multi-LLM cascade) plus standard OpenAI/Codex-CLI quota/rate-limit
# diagnostic tokens, never measured against this specific CLI's actual
# stderr. A green test proves the code path reachable, not that the
# pattern fires on real `codex exec` output.
#
# R28-1 correction (2026-08-25, this round — NARROWS B2a's vocabulary,
# never widens it, per the reproduced over-match findings §2 of the
# evidence file above):
#   - The underscored `insufficient_quota` STRUCTURED token no longer
#     requires a `\b`/`(?!\w)` boundary at either edge — B2a's version
#     required both, and both fail next to a `_` (`_` is a word character,
#     so `openai_insufficient_quota` defeats the leading `\b` and
#     `insufficient_quota_error` defeats the trailing `(?!\w)`) —
#     reproduced findings §4.
#   - Bare "too many requests" (no leading "429") DROPPED: over-matches
#     ordinary consultancy prose ("the officer made too many requests for
#     the same document" — reproduced finding §2). The `429`-anchored
#     structured phrase remains, and stays exactly as specific as the
#     R25-3 lesson that bare `401` false-positived on "completed after 401
#     ms" warns against for bare `429`.
#   - `resource_exhausted` DROPPED entirely: the reproduced finding showed
#     it firing on `RESOURCE_EXHAUSTED: received message larger than max
#     (...)` — a payload-SIZE failure, not account quota (reproduced
#     finding §2). That shape is now its own class,
#     `_WireWordClass.OUTPUT_OVERSIZED` below (Ruling A — this maps onto
#     F3's `OUTPUT_INVALID`, not `QUOTA`). Bare `RESOURCE_EXHAUSTED` with
#     no size-qualifying context is genuinely ambiguous between the two
#     meanings (gRPC/Google API convention uses this status for BOTH) with
#     no anchor either way for this CLI — SPEC P5, "unknown stays unknown",
#     applies: deliberately left unmatched rather than guessed.
#   - Bare "quota exceeded"/"quota is exceeded" DROPPED: the reproduced
#     finding ("Your sponsor's quota exceeded this year's KITAS
#     allocation" — reproduced finding §2) shows this phrase is
#     domain-overloaded in an immigration-consultancy corpus specifically —
#     "quota" is ordinary KITAS/RPTKA-sponsor vocabulary here, not just
#     generic English. A narrower anchor ("your current quota",
#     billing/plan-shaped) is kept below instead of excepting every
#     possessive that could precede the bare phrase — whack-a-mole the
#     SPEC explicitly warns against ("[t]uning the alternatives ... widens
#     the over-match surface at the same time").
#   - Added per the reproduced UNDER-match findings §3: `rate_limit_exceeded`
#     (structured), "rate limit reached", "exceeded your current quota",
#     "monthly credits exhausted"/"credits exhausted" (prose — "credits"
#     and "current quota"/billing framing are not plausible immigration
#     vocabulary, unlike bare "quota").
# Bare "exhausted"/"limit" remain deliberately excluded as standalone
# alternatives — both are plausible ordinary WA-immigration vocabulary (a
# KITAS sponsor "quota limit", "I am exhausted from the process").
_QUOTA_STRUCTURED_RE: re.Pattern[str] = re.compile(
    r"\b429\s+too\s+many\s+requests\b|insufficient_quota|rate_limit_exceeded",
    re.IGNORECASE,
)
_QUOTA_PROSE_RE: re.Pattern[str] = re.compile(
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

# Payload/output-too-large word class (Ruling A, orchestrator mandate
# 2026-08-25): NOT an F3 vocabulary member on its own — it maps onto the
# PRE-EXISTING `OUTPUT_INVALID` member alongside the empty-stdout-on-exit-0
# path, via `OutputShapeReason` (see `CodexExecOutputShapeError` below). F3
# collapses "the model produced too much" and "the model produced nothing"
# into one bucket, but their retry semantics are OPPOSITE: an oversized
# response reproduces on the same prompt (retrying wastes a call; the fix
# is truncation or a reprompt), while an empty response on exit 0 is the
# classic transient (retry is exactly right). No new F3 member is added —
# the distinction lives in the required `reason` detail, per the
# orchestrator's ruling that F3's vocabulary stays closed. This specific
# pattern is STRUCTURED-only (no prose tier): it is a reproduced over-match
# FIX (this exact string was previously misread as `QUOTA` via bare
# `resource_exhausted` above), grounded in the reproduced finding itself,
# not a guess.
_OUTPUT_OVERSIZED_STRUCTURED_RE: re.Pattern[str] = re.compile(
    r"received\s+message\s+larger\s+than\s+max",
    re.IGNORECASE,
)

# Content-policy-refusal word class — F3's `POLICY_BLOCKED` member. EVEN
# WEAKER precedent than quota (see the B2b block comment's Arming Condition
# paragraph above): nobody has ever seen what `codex exec` prints on a
# policy block, and this class has no structured tier at all — every
# alternative below is prose, so every match is `MatchConfidence.LOW` by
# construction.
#
# R28-2 correction (2026-08-25, this round — NARROWS, never widens, per the
# reproduced over-match findings §2):
#   - "cannot assist with" DROPPED bare, replaced with
#     `can(?:not|'t)\s+assist\s+with\s+(?:this|that)\s+request`: the
#     reproduced over-match ("We cannot assist with the visa extension
#     until your sponsor sends the missing passport scan") has no "this/
#     that request" object — it is conditional business prose about a
#     named service, not a model refusing a request. The narrower anchor
#     ALSO closes the reproduced under-match ("I can't assist with that
#     request").
#   - "refused to answer"/"refused to respond" DROPPED bare, replaced with
#     `refused\s+to\s+respond\s+to\s+(?:this|that|the)\s+request`: the
#     reproduced over-match ("The applicant refused to answer the
#     immigration officer's question") is about a THIRD PARTY (the
#     applicant), not the model.
#   - the "violates ... policy" alternative now REQUIRES "usage": the
#     reproduced over-match ("Submitting duplicate visa applications
#     violates the policy and may delay approval") never says "usage". The
#     narrower anchor also closes the reproduced under-match ("this
#     request may violate our usage policy").
#   - "safety system" DROPPED, replaced with "safety filter": the
#     reproduced over-match ("The office fire safety system is under
#     maintenance") is ordinary facilities prose; "safety filter" is not
#     plausible outside a content-moderation context and closes the
#     reproduced under-match ("blocked by the safety filter") at the same
#     time.
_POLICY_PROSE_RE: re.Pattern[str] = re.compile(
    r"\b(?:"
    r"content\s+policy|"
    r"safety\s+filter|"
    r"can(?:not|'t)\s+assist\s+with\s+(?:this|that)\s+request|"
    r"refused\s+to\s+respond\s+to\s+(?:this|that|the)\s+request|"
    r"violat(?:es?|ing)\s+(?:(?:the|our)\s+)?usage\s+polic(?:y|ies)|"
    r"moderation\s+block(?:ed)?"
    r")(?!\w)",
    re.IGNORECASE,
)

# One table, one place: every `_WireWordClass` maps to its (HIGH, LOW)
# pattern pair — `None` where a tier does not exist (POLICY_BLOCKED has no
# structured tier; OUTPUT_OVERSIZED has no prose tier). `_classify_stderr`
# is the sole reader.
_PATTERNS: dict[_WireWordClass, dict[MatchConfidence, re.Pattern[str] | None]] = {
    _WireWordClass.AUTH_DEATH: {
        MatchConfidence.HIGH: _AUTH_STRUCTURED_RE,
        MatchConfidence.LOW: _AUTH_PROSE_RE,
    },
    _WireWordClass.QUOTA: {
        MatchConfidence.HIGH: _QUOTA_STRUCTURED_RE,
        MatchConfidence.LOW: _QUOTA_PROSE_RE,
    },
    _WireWordClass.POLICY_BLOCKED: {
        MatchConfidence.HIGH: None,
        MatchConfidence.LOW: _POLICY_PROSE_RE,
    },
    _WireWordClass.OUTPUT_OVERSIZED: {
        MatchConfidence.HIGH: _OUTPUT_OVERSIZED_STRUCTURED_RE,
        MatchConfidence.LOW: None,
    },
}


class CodexExecUnavailableError(RuntimeError):
    """Raised by `generate()` when `available` is `False` (binary missing,
    or no auth-material file present) — checked BEFORE any subprocess is
    spawned. Also raised if the resolved binary cannot actually be launched
    between the `available` check and the real launch — any `OSError`
    (`FileNotFoundError`, `PermissionError`, or another subclass; widened
    R25-5, 2026-08-15 THAW round — the original code only caught
    `FileNotFoundError`) from `asyncio.create_subprocess_exec`, mirroring
    `claude_oauth_client.py::ClaudeOAuthNotAvailable`.
    """


class CodexExecAuthError(RuntimeError):
    """The subprocess exited non-zero and its STDERR — with known
    prompt/stdout LINES stripped (CORRECTED, R27-3, 2026-08-15: this
    docstring previously said "(prompt-stripped) output", stale against the
    stderr-only, line-based design point 5 now describes — stdout is never
    scanned at all, and stderr is line-stripped, not the whole "output")
    — matched the auth-failure word class (see point 5 / the B2b block
    comment near `_AUTH_STRUCTURED_RE`). Operator re-login (`codex login`)
    is needed. Distinct from `CodexExecProcessError` so a caller can page a
    human for THIS class and silently retry-later for a generic failure.

    `confidence` (SPEC P4) is `MatchConfidence.HIGH` when a STRUCTURED
    token fired (`_AUTH_STRUCTURED_RE`) or `.LOW` when only PROSE fired
    (`_AUTH_PROSE_RE`). `suppressed` (SPEC P1) names any OTHER
    `_WireWordClass` that also matched this stderr but lost to this one
    under P3's machine-readable-evidence precedence — empty when AUTH_DEATH
    was the only class that matched at all.
    """

    def __init__(
        self,
        message: str,
        *,
        confidence: MatchConfidence,
        suppressed: frozenset[str] = frozenset(),
    ) -> None:
        self.confidence = confidence
        self.suppressed = suppressed
        super().__init__(message)


class CodexExecQuotaError(RuntimeError):
    """The subprocess exited non-zero and its stderr (line-stripped of
    echoed prompt/stdout, per `CodexExecAuthError`'s discipline) matched
    the quota-exhaustion word class (`_QUOTA_STRUCTURED_RE`/
    `_QUOTA_PROSE_RE`). Distinct from `CodexExecAuthError` — F3 (MANDATE.md)
    explicitly requires auth and quota to be distinguishable outcomes,
    never collapsed into one bucket. Distinct from `CodexExecProcessError`
    so a caller can apply quota-specific backoff/fallback (e.g. route to a
    different seat) instead of a generic retry-later.

    `confidence`/`suppressed` — see `CodexExecAuthError`'s docstring; same
    contract.
    """

    def __init__(
        self,
        message: str,
        *,
        confidence: MatchConfidence,
        suppressed: frozenset[str] = frozenset(),
    ) -> None:
        self.confidence = confidence
        self.suppressed = suppressed
        super().__init__(message)


class CodexExecPolicyBlockedError(RuntimeError):
    """The subprocess exited non-zero and its stderr (line-stripped)
    matched the content-policy-refusal word class (`_POLICY_PROSE_RE`).
    Distinct from `CodexExecProcessError` so a caller can classify this as
    a policy outcome (F3's `POLICY_BLOCKED`) rather than a transient
    failure worth retrying.

    `confidence` is ALWAYS `MatchConfidence.LOW` — this class has no
    structured tier (see the B2b block comment near `_POLICY_PROSE_RE`),
    which is itself how the SPEC's Arming Condition is enforced
    structurally rather than by convention. `suppressed` — see
    `CodexExecAuthError`'s docstring; same contract.
    """

    def __init__(
        self,
        message: str,
        *,
        confidence: MatchConfidence,
        suppressed: frozenset[str] = frozenset(),
    ) -> None:
        self.confidence = confidence
        self.suppressed = suppressed
        super().__init__(message)


class CodexExecAmbiguousError(RuntimeError):
    """The subprocess exited non-zero and its stderr (line-stripped, then
    classified PER LINE per SPEC P2) matched more than one F3-adjacent word
    class with no principled winner — SPEC P1: "If two classes match one
    payload, that is a defined outcome ... not a silent precedence."

    Raised ONLY when P3's machine-readable-evidence precedence rule cannot
    resolve the collision by itself: zero, or more than one, class matched
    at `MatchConfidence.HIGH`. A HIGH-vs-LOW collision (e.g. the flagship
    reproduced finding, `token has expired` (AUTH, LOW) + `429 too many
    requests` (QUOTA, HIGH) in one stderr) resolves to the HIGH class
    instead (`CodexExecQuotaError` in that example, with `AUTH_DEATH` on
    its `.suppressed`) and never reaches this exception.

    `candidates` carries `_WireWordClass` string values only — never raw
    stderr content (point 6). Maps onto F3's `INTERNAL` in
    `codex_broker_wire.py` (F3's frozen 7-member vocabulary has no
    AMBIGUOUS slot) with a detail field naming the candidates, rather than
    guessing one.
    """

    def __init__(self, message: str, *, candidates: frozenset[str]) -> None:
        self.candidates = candidates
        super().__init__(message)


class CodexExecTimeoutError(RuntimeError):
    """The subprocess did not complete within the wall-clock timeout. The
    process is killed and reaped (`kill()` + `wait()`) before this is
    raised — no zombie process is left behind.
    """


class CodexExecCommunicationError(RuntimeError):
    """The child was launched but stdin/stdout/stderr communication failed
    outside the timeout/cancellation paths. The child is killed and reaped
    before this sanitized error is raised. The underlying exception object
    and message are deliberately not exposed across the provider boundary.
    """


class OutputShapeReason(StrEnum):
    """Ruling A (orchestrator mandate 2026-08-25): F3's `OUTPUT_INVALID`
    member collapses two conditions with OPPOSITE retry semantics —
    `EMPTY` (`exit_code == 0` but stdout was empty/whitespace-only, the
    classic transient; retrying is likely to help) and `OVERSIZED` (a
    payload/output-too-large failure; the SAME prompt reproduces it, so
    retrying wastes a call — the fix is truncation or a reprompt). F3's
    vocabulary stays closed and unchanged; the distinction lives here,
    required on every `CodexExecOutputShapeError`."""

    EMPTY = "empty"
    OVERSIZED = "oversized"


class CodexExecOutputShapeError(RuntimeError):
    """`exit_code == 0` but stdout was empty/whitespace-only
    (`reason=OutputShapeReason.EMPTY`, point 4), OR `exit_code != 0` with
    stderr matching the payload/output-too-large structured pattern
    (`reason=OutputShapeReason.OVERSIZED`, Ruling A — see
    `OutputShapeReason`'s docstring and `_OUTPUT_OVERSIZED_STRUCTURED_RE`).
    Never a best-effort empty answer. `reason` is a required keyword-only
    argument, not a default — every raise site must declare which
    condition this is, by design (F3 exists because an earlier
    undistinguished bucket is exactly how AUTH_DEAD and QUOTA collapsed
    into one).
    """

    def __init__(self, message: str, *, reason: OutputShapeReason) -> None:
        self.reason = reason
        super().__init__(message)


class CodexExecProcessError(RuntimeError):
    """The subprocess exited non-zero for a reason that did NOT match the
    auth-death word classes (see `CodexExecAuthError`). Carries only the
    numeric exit code — never raw stdout/stderr content (point 6).
    """

    def __init__(self, exit_code: int) -> None:
        self.exit_code = exit_code
        super().__init__(f"codex exec failed (exit_code={exit_code})")


class CodexExecModelNotAllowedError(RuntimeError):
    """`generate()` (or the constructor) was given a model slug not in
    `_ALLOWED_MODELS`. Mirrors `OpenAIModelNotAllowedError`'s
    positive-allowlist shape — a spend/scope control on CALLER input, so the
    rejected model name is safe to include (it never originates from the
    subprocess's own output).
    """


@dataclass(frozen=True)
class CodexExecResult:
    """Provider-neutral envelope for a successful `codex exec` completion."""

    text: str
    model: str
    latency_ms: float


# Upper bound on how long `_kill_and_reap` waits for `proc.wait()` to
# resolve after the kill signals have been delivered. This is NOT the time
# a SIGKILLed child needs to die (milliseconds): it bounds a measured
# CPython 3.11 transport behavior — `BaseSubprocessTransport._wait()`
# resolves its waiters only in `_call_connection_lost`, which fires only
# when ALL pipe transports have disconnected, and a surviving DESCENDANT of
# the child holds the inherited stdout/stderr write ends open indefinitely.
# Measured live (PR-6 mutation run, 2026-08-20): with the group-kill
# disabled, `_kill_and_reap` hung >90s on a dead, already-OS-reaped child
# whose grandchild held the pipes. The group-kill makes that shape rare;
# this deadline makes it impossible to hang the caller when it happens
# anyway (guard skip-branch, cross-uid kill failure).
_REAP_ABANDON_S = 5.0


async def _kill_and_reap(proc: Any) -> None:
    """Kill and reap a child, deferring repeated caller cancellation.

    The first caller cancellation is caught by ``generate()`` before this
    helper runs. A second ``Task.cancel()`` can still arrive while
    ``proc.wait()`` is in flight. Shield one stable wait task, finish the
    reap, then propagate that later cancellation; suppressing
    ``CancelledError`` around a bare wait would return before the child was
    actually reaped.

    The wait is BOUNDED by ``_REAP_ABANDON_S``: `proc.wait()`'s resolution
    is tied to pipe disconnection, not to process death (see the constant's
    comment), so an unbounded wait here could hang the calling coroutine
    forever on a child that is already dead and OS-reaped. When the
    deadline expires the wait task is cancelled and the reap is abandoned
    with a warning — at that point every kill signal has long been
    delivered and `proc.returncode` (set by the child watcher independent
    of pipes) tells the truth about the child.
    """
    # Group-kill FIRST (chaos row 5 / spec "kill process group on expiry"):
    # `codex exec` spawns descendants of its own, and killing only the direct
    # child leaves those grandchildren alive holding stdout/stderr pipes —
    # `communicate()`'s reader would then hang past the kill. The spawn site
    # sets `start_new_session=True`, making the child a session leader whose
    # pgid == its pid, so the guard below can never target OUR OWN group:
    # killing our own pgid would take down the daemon itself. The guard is a
    # backstop, not dead code — it also protects any future caller that
    # passes a process spawned WITHOUT `start_new_session`.
    # `OSError` covers the whole failure class here: `ProcessLookupError`
    # (child already reaped) and `PermissionError` (cross-uid signal) are
    # both `OSError` subclasses.
    with contextlib.suppress(OSError):
        pgid = os.getpgid(proc.pid)
        if pgid != os.getpgid(0):
            os.killpg(pgid, signal.SIGKILL)
    # Direct-child kill stays as the belt under the group-kill braces: if the
    # group-kill was skipped (pgid lookup failed, or the guard matched), the
    # child itself must still die before we wait on it.
    with contextlib.suppress(ProcessLookupError):
        proc.kill()

    wait_task = asyncio.ensure_future(proc.wait())
    deferred_cancellation: asyncio.CancelledError | None = None
    deadline = time.monotonic() + _REAP_ABANDON_S
    while True:
        try:
            await asyncio.wait_for(
                asyncio.shield(wait_task),
                timeout=max(0.0, deadline - time.monotonic()),
            )
            break
        except asyncio.TimeoutError:
            # ABANDON path (see `_REAP_ABANDON_S`): the child is killed and
            # OS-reaped; only the transport's pipe bookkeeping is stuck on
            # FDs held by orphaned descendants. `wait_for` cancelled the
            # shield wrapper, never `wait_task` itself — cancel it
            # explicitly so it does not linger pending forever.
            wait_task.cancel()
            logger.warning(
                "codex_exec: reap abandoned after %.1fs — child killed "
                "(returncode=%r) but pipe bookkeeping never resolved "
                "(descendants holding inherited pipe FDs)",
                _REAP_ABANDON_S,
                proc.returncode,
            )
            break
        except asyncio.CancelledError as exc:
            if wait_task.cancelled():
                break
            deferred_cancellation = exc
        except Exception:
            break

    if deferred_cancellation is not None:
        raise deferred_cancellation


def _strip_known_lines(text: str, *known: str) -> str:
    """Drop, WHOLE-LINE-ONLY, every line of `text` that verbatim-EQUALS a
    line of `known`, before auth-death classification (point 5). Every
    `known` argument is CALLER-KNOWN local data (the prompt this process
    sent, or the stdout this process just received back) — never a value
    the classifier invented or a value that arrived from anywhere
    remote-and-untrusted — so this is a safe, targeted defusal of the
    "stderr echoes the client's own prompt AND, on a late failure, the
    answer produced before it" finding from point 4/7.

    EQUALITY ONLY (R27-1 fix, 2026-08-15 THAW round, second generation of
    this line-based rewrite): the first version of this function ALSO
    dropped a `text` line whenever it was merely a SUBSTRING of some known
    line (`stripped in kl`, not just `stripped == kl`) — reasoned at the
    time as tolerance for a wrapped/truncated echo, but this is its own
    fail-open bug, symmetric to the mangle case R26-2 fixed: a GENUINE,
    UNRELATED diagnostic stderr line that happens to be textually contained
    in the prompt or stdout gets silently dropped before it ever reaches
    the auth word-class patterns (`_AUTH_STRUCTURED_RE`/`_AUTH_PROSE_RE`,
    B2b split — originally named `_AUTH_DEATH_RE` when this paragraph was
    written). Measured example: prompt = "why am I not logged in
    after midnight, is this urgent?" and stderr independently contains the
    exact diagnostic line "not logged in" (unrelated to the prompt's own
    wording, a real auth failure) — the old containment check saw
    `"not logged in" in "why am I not logged in after midnight..."` as
    `True` and dropped the diagnostic line, silencing a page that should
    have fired. The module's own MEASURED wire shape (point 4/7) never
    needed containment in the first place: the prompt and the answer are
    each echoed as their OWN complete line(s), never wrapped or truncated
    mid-line — so equality-only is not a narrower defusal for the shape this
    client actually sees, only a categorically safer one against the
    substring-collision case above.

    R26-2 fix (2026-08-15 THAW round, SECOND generation of this function —
    R25-3 named this file `_strip_known_texts` and did WHOLE-TEXT
    `str.replace(candidate, "")`, i.e. removed every occurrence of the
    candidate substring ANYWHERE in `text`, including mid-line. That is
    unsafe when a candidate is short or a common substring: a one-word
    stdout answer like `"in"` would strip every `"in"` occurrence from
    stderr — including the one INSIDE the genuine diagnostic phrase
    `"not logged in"`, mangling it to `"not logged "` and making the auth
    word-class patterns go silent exactly when it must page (a fail-OPEN
    regression the R25-3 round introduced while fixing a different
    problem). This rewrite operates on WHOLE LINES only: split `text` and
    every `known` string on `\\n`, and for each line of `text`, KEEP it
    verbatim unless the line (after stripping surrounding whitespace)
    EQUALS some line of `known` (R27-1 narrowed this from "equals, or is a
    substring of" — see the paragraph above) — a kept line is NEVER
    internally mutated, so a short candidate can never carve a hole out of
    the middle of an unrelated, longer, genuinely diagnostic line.
    This matches the module's own MEASURED wire shape (point 4/7): the
    prompt and the answer are each echoed as their own complete line(s) in
    stderr, never spliced mid-line into unrelated framing text — so
    line-granularity is not a weaker defusal than the old character-level
    one for the shape this client actually sees, and it is categorically
    safer against the short-candidate mangle case above. No minimum-length
    floor was added on top of this (R26-2 offered one as an
    alternative/additional mitigation) — the line-based rewrite removes the
    root cause (intra-line substring surgery) directly, so a length floor
    would be redundant defense-in-depth, not a required companion fix; this
    is a declared design choice, not an oversight.

    Not a general PII scrubber, and not a substitute for never logging
    `text` itself (point 6, unchanged: the scrubbed text is used only for an
    in-memory regex match, never surfaced).

    Declared residual (R25-8, still applies, no code change): both `text`
    and the strings in `known` are decoded upstream with `errors="replace"`
    — a multibyte UTF-8 character split across the stdout/stderr pipe
    boundary decodes to the U+FFFD replacement character on ONE side and may
    decode cleanly on the other, so a line-equality/containment check can
    miss at that exact margin. Not treated as a load-bearing defense here —
    the classification that follows is a best-effort auth-death PAGE, not a
    security boundary, and a missed strip only means a marginal extra
    false-positive risk on an already-narrow, context-anchored pattern set
    (see `_AUTH_DEATH_RE`), not a missed real detection."""
    known_lines: set[str] = set()
    for candidate in known:
        if not candidate:
            continue
        for line in candidate.split("\n"):
            stripped = line.strip()
            if stripped:
                known_lines.add(stripped)

    if not known_lines:
        return text

    kept: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped and stripped in known_lines:
            # R27-1 fix: EQUALITY only (set membership) — the prior
            # `stripped == kl or stripped in kl` also matched a `text` line
            # that was merely a SUBSTRING of a known line, dropping genuine,
            # unrelated diagnostic content that happened to be textually
            # contained in the prompt (see the function docstring's R27-1
            # paragraph). Whole-line drop only either way — never mutate a
            # surviving line.
            continue
        kept.append(line)
    return "\n".join(kept)


@dataclass(frozen=True)
class StderrVerdict:
    """The outcome of classifying one already-line-stripped stderr blob
    against F3's word-class vocabulary (SPEC P1/P2/P3/P4). Exactly one of
    three shapes:

    - No class matched: `winner is None` and `ambiguous_classes` is empty
      (SPEC P5, "unknown stays unknown" — the caller falls through to the
      generic residual bucket).
    - Exactly one class matched, OR more than one matched but P3's
      machine-readable-evidence precedence resolved it: `winner` is set,
      `confidence` is set, `suppressed` names any OTHER class that also
      matched but lost (empty when only one class matched at all).
    - More than one class matched with NO principled winner (zero, or more
      than one, class at `MatchConfidence.HIGH`): `winner is None` again,
      but `ambiguous_classes` is non-empty this time (SPEC P1, "an
      AMBIGUOUS result carrying both — not a silent precedence") — the
      caller must raise `CodexExecAmbiguousError`, never guess.

    `matched_tags` is always populated when anything matched at all (safe,
    fixed-vocabulary `"<CLASS>:<CONFIDENCE>"` literals — never raw stderr
    text, point 6) — useful for logging/detail regardless of which of the
    three shapes above resulted.
    """

    winner: _WireWordClass | None
    confidence: MatchConfidence | None
    matched_tags: frozenset[str]
    suppressed: frozenset[_WireWordClass]
    ambiguous_classes: frozenset[_WireWordClass]


def _classify_stderr(stderr: str) -> StderrVerdict:
    """Classify an already-line-stripped stderr blob against every
    `_WireWordClass` in `_PATTERNS`, per SPEC P1-P4 (see the B2b block
    comment above `MatchConfidence` for the full statement of each
    property). Supersedes the pre-B2b `_auth_death_detected`/
    `_quota_detected`/`_policy_blocked_detected` trio and the fixed
    auth -> quota -> policy check order in `generate()` that consumed them.

    P2 (per-record, never cross-blob): `stderr` is split on `\\n` FIRST;
    every pattern is then searched within ONE line only, so no pattern can
    bridge two records — this is what makes the newline-bridging class of
    finding (`quota\\nexceeded`, `content\\npolicy`) structurally
    impossible rather than merely patched.

    Aggregation: for each line, every class's BEST confidence on that line
    is recorded (`HIGH` beats `LOW` if both tiers fire on the same line);
    those per-line best-confidences are then unioned across the WHOLE
    stderr — a class that matched on any line at all is "matched" for
    precedence purposes, at its best confidence anywhere.

    P1/P3 (precedence): with 0 classes matched, the result is UNKNOWN. With
    exactly 1, that class wins outright. With >1, a lone class at
    `MatchConfidence.HIGH` (with every other matched class only at `.LOW`)
    wins — P3, machine-readable evidence outranks a prose guess — and the
    others land on `.suppressed`. Any other multi-match shape (a genuine
    tie: 0 or >=2 classes at HIGH) has no principled winner and is reported
    via `ambiguous_classes` instead of guessed — P1.
    """
    per_class_confidence: dict[_WireWordClass, MatchConfidence] = {}
    per_class_tags: dict[_WireWordClass, set[str]] = {}

    for line in stderr.split("\n"):
        stripped_line = line.strip()
        if not stripped_line:
            continue
        for word_class, tiers in _PATTERNS.items():
            best_on_this_line: MatchConfidence | None = None
            # `tiers` is built as `{HIGH: ..., LOW: ...}` (see `_PATTERNS`
            # above) — dict order is insertion order (Python 3.7+), so HIGH
            # is always checked before LOW here; once found, nothing can
            # beat it, so the loop breaks rather than continuing to search.
            for confidence, pattern in tiers.items():
                if best_on_this_line is MatchConfidence.HIGH:
                    break
                if pattern is not None and pattern.search(stripped_line):
                    best_on_this_line = confidence
            if best_on_this_line is None:
                continue
            per_class_tags.setdefault(word_class, set()).add(
                f"{word_class.value}:{best_on_this_line.value}"
            )
            existing = per_class_confidence.get(word_class)
            if existing is None or (
                existing is MatchConfidence.LOW and best_on_this_line is MatchConfidence.HIGH
            ):
                per_class_confidence[word_class] = best_on_this_line

    if not per_class_confidence:
        return StderrVerdict(None, None, frozenset(), frozenset(), frozenset())

    all_tags = frozenset(tag for tags in per_class_tags.values() for tag in tags)

    if len(per_class_confidence) == 1:
        ((winner, confidence),) = per_class_confidence.items()
        return StderrVerdict(winner, confidence, all_tags, frozenset(), frozenset())

    high_classes = {wc for wc, conf in per_class_confidence.items() if conf is MatchConfidence.HIGH}
    if len(high_classes) == 1:
        (winner,) = high_classes
        suppressed = frozenset(per_class_confidence) - {winner}
        return StderrVerdict(winner, MatchConfidence.HIGH, all_tags, suppressed, frozenset())

    return StderrVerdict(None, None, all_tags, frozenset(), frozenset(per_class_confidence))


class CodexExecClient:
    """Thin async wrapper spawning `codex exec` as a subprocess.

    OFFLINE, NO-WIRING (see module docstring). There is no live caller of
    this class in this repo today. Never instantiate this expecting a
    persistent resource to manage — unlike `OpenAIResponsesClient`, there is
    no persistent connection object; every `generate()` call spawns and
    reaps its own subprocess and its own temp `cwd`.
    """

    def __init__(
        self,
        binary: str | None = None,
        *,
        model: str = DEFAULT_MODEL,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
        codex_home: str | None = None,
    ) -> None:
        """
        Args:
            binary: Explicit path to the `codex` executable. Highest
                priority in `available`'s resolution order (point 3).
            model: Default model slug for `generate()` when no per-call
                `model=` override is given. Must be in `_ALLOWED_MODELS`.
            timeout_s: Default wall-clock timeout in seconds for
                `generate()` when no per-call `timeout_s=` override is
                given.
            codex_home: Explicit `CODEX_HOME` override, used both to
                resolve the auth-material file (point 3) and passed through
                to the child process's env so the two agree (a test fixture
                pointing `codex_home=` at a fake directory must see the
                SAME directory the subprocess would use — not the real
                `~/.codex` regardless of what was configured).

        Raises:
            CodexExecModelNotAllowedError: `model` is not one of
                `_ALLOWED_MODELS`.
            ValueError: `timeout_s` is not a finite positive number (`bool`
                excluded — same subtype trap `openai_responses_client.py`
                guards against, since `isinstance(True, int)` is `True` in
                Python).
        """
        if model not in _ALLOWED_MODELS:
            raise CodexExecModelNotAllowedError(
                f"model not allowed: {model!r} — must be one of {sorted(_ALLOWED_MODELS)}",
            )
        if (
            not isinstance(timeout_s, (int, float))
            or isinstance(timeout_s, bool)
            or not math.isfinite(timeout_s)
            or timeout_s <= 0
        ):
            raise ValueError(f"timeout_s must be a finite positive number, got {timeout_s!r}")

        self._explicit_binary = binary
        self._model = model
        self._timeout_s = float(timeout_s)
        self._explicit_codex_home = codex_home

        if not self.available:
            logger.info(
                "CodexExecClient: not available (binary or auth-material missing) — "
                "this is expected in the offline/no-wiring phase (see module docstring).",
            )

    def _resolve_binary(self) -> str | None:
        """Single place deciding the `codex` binary path. Re-checked on
        every `available`/`generate()` call — genuinely live, never cached
        past construction (point 3)."""
        if self._explicit_binary:
            return self._explicit_binary
        env_bin = os.getenv(_ENV_BIN, "").strip()
        if env_bin:
            return env_bin
        return shutil.which(_DEFAULT_BINARY_NAME)

    def _resolve_codex_home(self) -> Path:
        """Single place deciding `CODEX_HOME`. Resolution order: explicit
        constructor arg, else env `CODEX_HOME`, else `~/.codex` — matches
        `codex`'s own documented resolution (`codex exec --help`:
        "`--ignore-user-config` ... auth still uses `CODEX_HOME`").

        ALWAYS resolved to an absolute path (R27-2 fix, 2026-08-15 THAW
        round): a RELATIVE `codex_home=`/`CODEX_HOME` value used to be
        returned as-is, which re-opened the exact gate/child divergence
        R25-2 declared structurally impossible — `available` (the gate)
        resolves a relative `Path` against the CALLING process's cwd at
        property-access time, while the spawned child (point 1) always runs
        from a fresh NEUTRAL TEMPDIR cwd, created and torn down per call. The
        same relative string therefore meant two DIFFERENT directories
        depending on WHEN it was resolved — gate and child could silently
        diverge again despite both calling this single method. `.resolve()`
        on all three tiers (explicit arg, env var, and — harmlessly, since
        it is already absolute — the `~/.codex` default) closes this: gate
        and child always agree on the same absolute path regardless of the
        caller's cwd."""
        if self._explicit_codex_home:
            return Path(self._explicit_codex_home).resolve()
        env_home = os.getenv(_ENV_CODEX_HOME, "").strip()
        if env_home:
            return Path(env_home).resolve()
        return (Path.home() / _DEFAULT_CODEX_HOME_SUBDIR).resolve()

    @property
    def available(self) -> bool:
        """True only when BOTH a resolvable, executable binary AND a
        non-empty auth-material file are present — re-checked on every
        access (point 3). See the point-3 MEASURED CAVEAT: this is a
        necessary-but-not-sufficient proxy for "a real call will succeed",
        by design mirroring the mandate's specified check — the auth-death
        detection in `generate()` (point 5) is the actual backstop for a
        credential that is genuinely dead despite the file existing."""
        binary = self._resolve_binary()
        if not binary:
            return False
        try:
            if not (os.path.isfile(binary) and os.access(binary, os.X_OK)):
                return False
            auth_file = self._resolve_codex_home() / _AUTH_FILE_NAME
            return auth_file.is_file() and auth_file.stat().st_size > 0
        except (OSError, ValueError):
            return False

    def _build_env(self) -> dict[str, str]:
        """Minimal child env — PATH/HOME/TERM/LANG/LC_ALL/TMPDIR plus
        `CODEX_HOME` — rather than the full inherited `os.environ`.
        Defense-in-depth (not a complete guarantee — that is the pending
        security review's job, see module docstring): reduces how much of
        this process's own environment (other providers' keys, unrelated
        secrets) is exposed to a sandboxed-but-agentic child process.

        `CODEX_HOME` is ALWAYS injected now (R25-2 fix, 2026-08-15 THAW
        round), set to `str(self._resolve_codex_home())` — the exact same
        value the `available` property just checked, whether that value came
        from an explicit constructor arg, the `CODEX_HOME` env var, or the
        `~/.codex` default. An earlier draft injected it ONLY when the
        constructor received an explicit `codex_home=` argument, which let
        the `available` gate (env-var-aware) and the actual child process
        (env-var-BLIND under that old code) validate two different
        directories when `CODEX_HOME` was set via the environment rather
        than the constructor — see `_resolve_codex_home`'s point-3 docstring
        note for the full failure mode this closes.
        """
        env: dict[str, str] = {}
        for key in ("PATH", "HOME", "TERM", "LANG", "LC_ALL", "TMPDIR"):
            value = os.environ.get(key)
            if value is not None:
                env[key] = value
        env[_ENV_CODEX_HOME] = str(self._resolve_codex_home())
        return env

    async def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        timeout_s: float | None = None,
    ) -> CodexExecResult:
        """Run `codex exec` once and return its answer.

        Args:
            prompt: Non-empty prompt text. Sent via stdin ONLY — never argv,
                never env (point 2).
            model: Per-call model override. Must be in `_ALLOWED_MODELS`.
            timeout_s: Per-call wall-clock timeout override, in seconds.

        Raises:
            ValueError: `prompt` is empty/whitespace-only, or `timeout_s`
                (when given) is not a finite positive number.
            CodexExecModelNotAllowedError: resolved model not in
                `_ALLOWED_MODELS`.
            CodexExecUnavailableError: `available` is `False`, the resolved
                binary vanished before launch, or the neutral per-call temp
                directory could not be created (R27-5, 2026-08-15 THAW
                round — `tempfile.mkdtemp()` was previously unwrapped and
                could leak a raw `OSError` past this method's typed
                exception contract).
            CodexExecTimeoutError: the subprocess exceeded the wall-clock
                budget; it is killed and reaped before this is raised.
            CodexExecCommunicationError: subprocess stdin/stdout/stderr
                communication failed outside timeout/cancellation; the child
                was killed and reaped and the raw exception was suppressed.
            CodexExecAuthError: the subprocess exited non-zero and stderr
                matched the auth-failure word class (point 5 / B2b).
            CodexExecQuotaError: the subprocess exited non-zero and stderr
                matched the quota-exhaustion word class (B2b).
            CodexExecPolicyBlockedError: the subprocess exited non-zero and
                stderr matched the content-policy-refusal word class (B2b).
            CodexExecAmbiguousError: the subprocess exited non-zero and
                stderr matched more than one word class with no principled
                machine-readable-evidence winner (SPEC P1, B2b).
            CodexExecProcessError: the subprocess exited non-zero and
                stderr matched no known word class.
            CodexExecOutputShapeError: `exit_code == 0` but stdout was
                empty/whitespace-only (`reason=OutputShapeReason.EMPTY`),
                or `exit_code != 0` with stderr matching the
                payload/output-too-large pattern
                (`reason=OutputShapeReason.OVERSIZED`, Ruling A).
        """
        if not prompt or not prompt.strip():
            raise ValueError("prompt must be non-empty")

        resolved_model = model if model is not None else self._model
        if resolved_model not in _ALLOWED_MODELS:
            raise CodexExecModelNotAllowedError(
                f"model not allowed: {resolved_model!r} — must be one of {sorted(_ALLOWED_MODELS)}",
            )

        if timeout_s is None:
            effective_timeout = self._timeout_s
        else:
            if (
                not isinstance(timeout_s, (int, float))
                or isinstance(timeout_s, bool)
                or not math.isfinite(timeout_s)
                or timeout_s <= 0
            ):
                raise ValueError(f"timeout_s must be a finite positive number, got {timeout_s!r}")
            effective_timeout = float(timeout_s)

        if not self.available:
            raise CodexExecUnavailableError(
                "CodexExecClient.available is False (binary and/or auth-material missing) — "
                "check .available before calling generate()",
            )

        binary = self._resolve_binary()
        if not binary:
            # TOCTOU: available was True a moment ago, binary resolution
            # changed underneath us. Fail the same way as a missing binary.
            raise CodexExecUnavailableError("codex binary could not be resolved")

        argv = [binary, *_FIXED_ARGV_PREFIX, "-m", resolved_model, _STDIN_SENTINEL]
        env = self._build_env()
        try:
            # R27-5 fix (2026-08-15 THAW round): `tempfile.mkdtemp()` was
            # previously called unwrapped, outside every typed-exception
            # boundary — a raw `OSError` (e.g. `/tmp` unwritable, disk full,
            # a TOCTOU permission change) would propagate straight out of
            # `generate()`, breaking this module's own "fail-closed with
            # typed exceptions" contract (module docstring). Mirrors the
            # R25-5 treatment of `create_subprocess_exec`'s own `OSError`
            # just below.
            neutral_dir = tempfile.mkdtemp(prefix="codex-exec-wa-")
        except OSError as exc:
            raise CodexExecUnavailableError(
                "could not create a neutral temp directory for the subprocess cwd",
            ) from exc
        start = time.monotonic()
        try:
            try:
                proc = await asyncio.create_subprocess_exec(
                    *argv,
                    cwd=neutral_dir,
                    env=env,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    # The child becomes its own session (and process-group)
                    # leader so that `_kill_and_reap` can SIGKILL the WHOLE
                    # group: `codex exec` spawns its own descendants, and a
                    # `proc.kill()` on the direct child alone leaves those
                    # grandchildren alive past a wall-clock timeout — the
                    # broker spec ("kill process group on expiry", chaos
                    # row 5) requires the whole tree dead. Also the
                    # precondition for the `pgid != our own pgid` guard in
                    # `_kill_and_reap`: a session leader's pgid is its own
                    # pid, never ours.
                    start_new_session=True,
                )
            except OSError as exc:
                # R25-5 fix (2026-08-15 THAW round): `FileNotFoundError`
                # alone was too narrow — `PermissionError` (binary present
                # but not executable by the launching user, e.g. a TOCTOU
                # permission change) and other `OSError` subclasses can also
                # come out of `create_subprocess_exec` before a process ever
                # exists. `FileNotFoundError`/`PermissionError` are both
                # `OSError` subclasses in Python, so this single broad catch
                # covers the whole class without narrowing coverage.
                raise CodexExecUnavailableError(
                    "codex binary could not be launched (missing or unusable)",
                ) from exc

            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(input=prompt.encode("utf-8")),
                    timeout=effective_timeout,
                )
            except asyncio.TimeoutError:
                await _kill_and_reap(proc)
                logger.warning(
                    "codex_exec: wall-clock timeout after %.1fs (model=%s)",
                    effective_timeout,
                    resolved_model,
                )
                raise CodexExecTimeoutError(
                    f"codex exec exceeded {effective_timeout}s wall-clock — process killed",
                ) from None
            except asyncio.CancelledError:
                # R26-1 fix (2026-08-15 THAW round): `asyncio.CancelledError`
                # inherits from `BaseException`, NOT `Exception`, since
                # Python 3.8 — the `except Exception:` arm below NEVER catches
                # it, so task cancellation (a client disconnect, an upstream
                # abort) used to bypass reaping entirely: `_kill_and_reap`
                # never ran, and the `finally` block's `shutil.rmtree` on the
                # temp `cwd` could then yank the working directory out from
                # under a still-live orphaned `codex` child process. This arm
                # reaps the child THEN re-raises `CancelledError` unchanged —
                # required so the caller's own cancellation still propagates
                # correctly (swallowing it here would break asyncio's
                # cancellation contract for whoever awaited this call).
                await _kill_and_reap(proc)
                raise
            except Exception:
                # R25-5 fix (2026-08-15 THAW round): the ORIGINAL code only
                # reaped the child on `asyncio.TimeoutError` — any OTHER
                # exception out of `communicate()` (a broken pipe, an
                # unexpected OS error writing stdin) would propagate straight
                # out of `generate()` with the child still alive, unreaped.
                # NOTE (R26-1 correction, same round): an earlier version of
                # this comment claimed this arm also covers "a cancelled
                # task" — FALSE, `CancelledError` is a `BaseException`
                # subclass and never reaches an `except Exception:` arm; see
                # the dedicated `except asyncio.CancelledError:` arm above,
                # which is what actually covers cancellation. This arm
                # guarantees `_kill_and_reap` runs before every OTHER
                # exception class from `communicate()` leaves this method.
                # The raw exception cannot cross a provider boundary: callers
                # receive a stable typed error with no underlying message or
                # exception object attached.
                await _kill_and_reap(proc)
                communication_failed = True
            else:
                communication_failed = False

            if communication_failed:
                logger.warning(
                    "codex_exec: subprocess communication failed (model=%s)",
                    resolved_model,
                )
                raise CodexExecCommunicationError(
                    "codex exec subprocess communication failed after launch — process killed",
                ) from None

            latency_ms = (time.monotonic() - start) * 1000.0
            exit_code = proc.returncode if proc.returncode is not None else -1
            stdout = stdout_b.decode("utf-8", errors="replace")
            stderr = stderr_b.decode("utf-8", errors="replace")

            if exit_code != 0:
                # R26 addendum, UNIFIED design (2026-08-15 THAW round, GLM
                # F26-1/F26-4 — see point 5's docstring for the full
                # disposition): scan STDERR ONLY. stdout is NEVER part of
                # the scanned text — concatenating it back in (the R25-3/
                # R26-2 shape) still let a partial ANSWER that happened to
                # discuss the client's own "expired"/"unauthorized"
                # situation false-page on itself, and the "\n" join between
                # two independently-stripped streams was its own seam a
                # `\s+` alternative could bridge across. stderr is still
                # stripped of known prompt/stdout LINES, WHOLE-LINE-ONLY
                # (R25-3 finding, R26-2 mechanism — stderr's own transcript
                # echoes both).
                stripped_stderr = _strip_known_lines(stderr, prompt, stdout)
                # B2b (2026-08-25) — see the block comment above
                # `MatchConfidence` for the full design this replaces
                # (B2a's fixed auth -> quota -> policy check order, which a
                # fenced refuter proved unsound in 12 reproduced ways).
                # `_classify_stderr` evaluates EVERY word class (SPEC P1),
                # per line (P2), tiered by machine-readable-evidence
                # confidence (P3/P4), and returns one of three shapes.
                verdict = _classify_stderr(stripped_stderr)

                if verdict.ambiguous_classes:
                    candidate_names = frozenset(wc.value for wc in verdict.ambiguous_classes)
                    logger.warning(
                        "codex_exec: ambiguous failure (exit_code=%d, model=%s, "
                        "candidates=%s) — no machine-readable-evidence winner, refusing "
                        "to guess (SPEC P1)",
                        exit_code,
                        resolved_model,
                        sorted(candidate_names),
                    )
                    raise CodexExecAmbiguousError(
                        "codex exec failed with a stderr matching more than one word class "
                        f"with no clear machine-readable-evidence winner: {sorted(candidate_names)}",
                        candidates=candidate_names,
                    )

                if verdict.winner is _WireWordClass.AUTH_DEATH:
                    logger.warning(
                        "codex_exec: auth-death detected (exit_code=%d, model=%s, "
                        "confidence=%s) — operator re-login needed",
                        exit_code,
                        resolved_model,
                        verdict.confidence.value if verdict.confidence else None,
                    )
                    raise CodexExecAuthError(
                        "codex exec reported an authentication failure — operator re-login "
                        "(`codex login`) needed",
                        confidence=verdict.confidence,
                        suppressed=frozenset(wc.value for wc in verdict.suppressed),
                    )
                if verdict.winner is _WireWordClass.QUOTA:
                    logger.warning(
                        "codex_exec: quota exhaustion detected (exit_code=%d, model=%s, "
                        "confidence=%s)",
                        exit_code,
                        resolved_model,
                        verdict.confidence.value if verdict.confidence else None,
                    )
                    raise CodexExecQuotaError(
                        "codex exec reported quota/rate-limit exhaustion — distinct from an "
                        "auth failure, needs quota-specific backoff or fallback",
                        confidence=verdict.confidence,
                        suppressed=frozenset(wc.value for wc in verdict.suppressed),
                    )
                if verdict.winner is _WireWordClass.POLICY_BLOCKED:
                    logger.warning(
                        "codex_exec: policy-blocked detected (exit_code=%d, model=%s, "
                        "confidence=%s)",
                        exit_code,
                        resolved_model,
                        verdict.confidence.value if verdict.confidence else None,
                    )
                    raise CodexExecPolicyBlockedError(
                        "codex exec reported a content-policy refusal — no usable text",
                        confidence=verdict.confidence,
                        suppressed=frozenset(wc.value for wc in verdict.suppressed),
                    )
                if verdict.winner is _WireWordClass.OUTPUT_OVERSIZED:
                    logger.warning(
                        "codex_exec: oversized output detected (exit_code=%d, model=%s) — "
                        "Ruling A: same prompt would reproduce this, retrying is wasted",
                        exit_code,
                        resolved_model,
                    )
                    raise CodexExecOutputShapeError(
                        "codex exec reported a payload/output-too-large failure — the same "
                        "prompt would reproduce it; truncate or reprompt, do not blind-retry",
                        reason=OutputShapeReason.OVERSIZED,
                    )
                logger.warning(
                    "codex_exec: process failed (exit_code=%d, model=%s)",
                    exit_code,
                    resolved_model,
                )
                raise CodexExecProcessError(exit_code)

            text = stdout.strip()
            if not text:
                raise CodexExecOutputShapeError(
                    "codex exec exited 0 but stdout was empty/whitespace-only",
                    reason=OutputShapeReason.EMPTY,
                )

            logger.info(
                "codex_exec: success (model=%s, latency_ms=%.0f)",
                resolved_model,
                latency_ms,
            )
            return CodexExecResult(text=text, model=resolved_model, latency_ms=latency_ms)
        finally:
            shutil.rmtree(neutral_dir, ignore_errors=True)
