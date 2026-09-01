#!/usr/bin/env python3
"""model_routing_gate.py — PreToolUse hook on Agent: no subagent without an
explicit model, plus a routing floor toward the cross-family arsenal.

RULE 1 — explicit model required (Zero, 2026-07-14, MANDATORY fleet-wide;
doctrine corrected 2026-08-20): the session's own model is the orchestrator
brain + final on-disk gate ONLY — it never does implementer/grunt work
itself, and it must never LEAK into subagents by inheritance. Fable 5 held
that seat until Zero's 2026-08-20 ruling took it out of the workflow
entirely (CLAUDE.md §5, "Togliere Fable 5 dal workflow, lo uso solo io
quando voglio"): the final on-disk gate is now **Opus 5 at effort xhigh** —
same invariant, different name. The Agent tool's default is "inherit the
parent model": an orchestrator session on Opus 5 that spawns readers/
implementers without an explicit `model` burns Opus 5 quota on Sonnet-grade
work (lived: 6 TAC readers on Fable, 2026-07-14 — the same defect, whichever
model sits in the orchestrator seat).

Contract (Rule 1, unchanged since 2026-07-14):
  ALLOW  — Agent call with explicit `model` param (any value: the choice is the point).
  ALLOW  — Agent call whose subagent_type definition file pins `model:` in frontmatter
           (the definition is the explicit choice; inheriting it is correct).
  ALLOW  — subagent_type "fork" (forks always inherit by design).
  DENY   — no `model` and no frontmatter pin → would inherit the session model.

RULE 2 — routing floor (added 2026-08-22, arsenal-routing mandate
docs/mandates/2026-08-22-arsenal-routing-mandate.md D2): Agent(model:"sonnet")
is one call, parallel, worktree-less, structured output — the path of least
resistance — while a cross-family build (`scripts/seat_build.sh`) is a
blocking Bash call needing a worktree, a watchdog, and flag-juggling.
Measured 2026-08-22: 355 Sonnet builds vs 7 cross-family workspace-write
Codex builds. Rule 1 alone cannot fix this — an explicit `model:"sonnet"` is
exactly what Rule 1 already demands, and every one of the 355 had it. Rule 2
does not forbid Anthropic builds; it forces a periodic detour so quota,
resilience and parallelism spread across the arsenal instead of one pool
absorbing everything.

On the 3rd CONSECUTIVE build-shaped Agent dispatch carrying an Anthropic
model (sonnet/haiku/opus) with NO EVIDENCE, BY ANY ROUTE, that a
non-Anthropic build seat was used since the last reset → DENY, with the
exact seat_build.sh line to use instead. "Build-shaped" = description
matches `implement|build|fix|write|add|cure|ship|refactor|create|patch`
(plus their gerunds) on WORD BOUNDARIES (never bare substring —
cicatrix-superscar.md #3, guard-over-match: "fix" must not match "prefix",
"add" must not match "address"). The counter resets to zero the instant
ANY of these is seen: a `scripts/seat_build.sh` Bash call, a raw
codex/kimi/qwen Bash call (SEAT_BINARY_NAMES, command position),
or a build-shaped Agent dispatch whose model is genuinely non-Anthropic
(addendum 2026-08-22 — watching only the wrapper's literal spelling was
itself a false-accusation bug, found by a cross-family refuter: see
_floor_state's docstring). It never applies to read/explore/review-shaped
dispatches regardless of model.

Exemptions are cabled in code, never judged by a model (superscar #3
antidote): a hot-zone description/worktree-path (sourced from
scripts/evidence_pack_lint.py::HOTZONE_PATTERNS — see the sourcing note
below), a `migration` description, or a `pii|ktp|passport|npwp` description
(standalone) or `client` CO-OCCURRING with a data-ish token — "client
data/record/file/pii" or "client_id" — all mean NO FLOOR, unconditionally.
Bare `client` alone does NOT exempt (2026-08-22 fix: this is an
immigration/company-services agency whose ordinary task descriptions say
"client" constantly — "fix client dashboard" is routine UI work, not PII
handling; see PII_RE/CLIENT_DATA_RE for the exact split).

Override: `ROUTING_FLOOR_OK=<reason>` in the Agent prompt text or in the
environment. It ALLOWS but prints an audible notice to stderr naming the
reason — the same audibility discipline `orchestrate_gate.py` uses for its
DISARM notice (2026-08-12): an override that leaves no trace is how a guard
quietly stops mattering.

P0 FIX (2026-08-22, same-day fix round): the first version of
`_iter_transcript_events` assumed a FLAT top-level `{"name":..., "input":...}`
shape per transcript line — the shape this file's own test fixtures invented
(mirroring test_orchestrate_gate_vocab.py's fixture idiom) — and it saw ZERO
events on any real transcript. Verified against a live
`~/.claude/projects/**/*.jsonl` (1218 lines, ground truth 4 Agent + 148 Bash
tool_use blocks by raw walk): a tool call is never at the line's top level —
it is one block inside `message.content[]`, e.g.
`{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Agent",
"input":{...}}]}}`, and a single line can carry multiple tool_use blocks.
`_iter_transcript_events` now walks that real shape directly; there is no
evidence the flat shape was ever emitted by a real transcript, so it is not
kept as a fallback.

HONESTY NOTE (2026-08-22, same fix round): `BUILD_VERB_RE` is approximate in
BOTH directions and is not going to be perfected — it misses `refactor`/
`create`/`patch`-adjacent phrasing it doesn't literally contain and gerunds
of verbs not in the list, and it fires on ordinary English that happens to
contain a build verb ("build consensus", "write up the findings", "ship a
summary email"). This is ACCEPTED, not a bug to chase: the guard is
fail-open with an audible override, so the cost of a false DENY is one
`ROUTING_FLOOR_OK=<reason>` line and the cost of a false ALLOW is nothing —
an asymmetry that makes precision-tuning this regex not worth the
maintenance burden. The same applies to the hot-zone/migration/PII
exemptions: they are lexical, string-matched, and trivially spoofable by
wording a description around them — documented here rather than engineered
against, because this is an economy guard, not a safety boundary, and an
economy guard that argues with its user about phrasing is worse than one
that occasionally misses.

Innocence (must NOT fire): custom agents with pinned models (wr2-critic →
opus); any Anthropic build call below the floor threshold; read/explore/
review-shaped dispatches (never counted, regardless of model); hot-zone/
migration/PII-shaped builds (exempt by construction); a floor whose
exemption evidence (HOTZONE_PATTERNS) could not be loaded (fails open,
never denies on evidence it does not have).
Guilt (must fire): bare Agent(general-purpose/Explore/claude/…) with no
model (Rule 1); the 3rd consecutive Anthropic build dispatch with no
seat_build.sh call in between (Rule 2).

Fail-open on every parse/IO error AND on inconclusive evidence (unreadable
transcript, HOTZONE_PATTERNS not loadable) — this hook is a routing/economy
guard, not a safety boundary. A broken hook, or a floor rule it cannot
safely evaluate, must never paralyze the harness or wrongfully deny real
work; the live copy of Rule 1 already followed this discipline and Rule 2
preserves it.

HOTZONE_PATTERNS sourcing (deliberate choice, not an oversight): this hook
runs from ~/.claude/hooks/ (HOME), detached from the repo's Python
environment — scripts/evidence_pack_lint.py imports `yaml`, which the
hook's bare system python3 is not guaranteed to have, so `import`ing that
module risks an ImportError unrelated to anything this hook actually needs.
Instead this file LOCATES scripts/evidence_pack_lint.py on disk (walking up
from the PreToolUse payload's `cwd` — covers a main checkout and any
`.worktrees/<lane>` subtree, since a worktree root already IS a repo root —
with HOME-relative fallbacks for a cwd-less subagent context) and
regex-extracts the `HOTZONE_PATTERNS` tuple literal as TEXT, never as code.
If the file cannot be found, read, or parsed, hot-zone exemption is
UNVERIFIABLE and the whole floor rule is skipped for that call (fail open)
rather than risk denying legitimate hot-zone work it failed to recognize.
"""

import json
import os
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from gate_coverage import record as _gc_record
except Exception:
    def _gc_record(hook_name, decision, payload=None):
        pass

USER_AGENTS = Path.home() / ".claude" / "agents"
FRONTMATTER_MODEL_RE = re.compile(r"^model\s*:\s*\S", re.MULTILINE)

# ---------------------------------------------------------------------------
# Rule 2 — routing floor constants
# ---------------------------------------------------------------------------
FLOOR_THRESHOLD = 3
MAX_TRANSCRIPT_LINES = 4000

# Word-boundary, case-insensitive. `\b` on both sides is what keeps "prefix"
# from matching "fix" and "address" from matching "add" (superscar #3).
# Includes explicit gerund spellings (2026-08-22 fix round, cheap-and-stop
# per the mandate — see the module docstring's HONESTY NOTE for what this
# deliberately does NOT chase: refactor/create/patch was the ask, gerunds of
# the existing verbs were "if cheap", nothing more).
BUILD_VERB_RE = re.compile(
    r"\b(implement(?:ing)?|build(?:ing)?|fix(?:ing)?|writ(?:e|ing)|add(?:ing)?|"
    r"cur(?:e|ing)|ship(?:ping)?|refactor(?:ing)?|creat(?:e|ing)|patch(?:ing)?)\b",
    re.IGNORECASE,
)
# Exact-first-token match, not substring (2026-08-22 fix round — the prior
# `any(tok in m for tok in (...))` over-matched "haikuish-local-llm" and
# "my-custom-sonnetdb-worker"). Same rule the sibling D3 lane specified for
# scripts/evidence_pack_lint.py::_is_anthropic_seat: normalise, split on
# "-", the seat is Anthropic iff the FIRST token is exactly one of these —
# "opus-5"/"sonnet-5"/"haiku-4-5"/"claude-*" all match; "haikuish-…",
# "not-sonnet", "codex-sol" do not. NOTE: at the time of this fix,
# _is_anthropic_seat was not found on disk in this worktree or on
# origin/main (that lane had not merged yet) — this reimplements the exact
# algorithm as specified rather than importing it; reconcile if the two
# diverge once D3 lands.
ANTHROPIC_MODEL_TOKENS = ("claude", "sonnet", "opus", "haiku")

MIGRATION_RE = re.compile(r"\bmigration\b", re.IGNORECASE)
# `pii`/`ktp`/`passport`/`npwp` stay standalone — unambiguous, rare outside
# a real PII context. `client` does NOT (2026-08-22, final round, found by
# a cross-family panel): this is an immigration/company-services agency —
# "fix client dashboard" / "build the client portal chart" are routine UI
# work that mentioned the word "client" the way any agency's task
# descriptions constantly do, not evidence of PII handling. Bare `client`
# exempted them from the floor for free. CLIENT_DATA_RE requires "client"
# to co-occur with a data-ish token — "client data/record/file/pii" or the
# underscore form "client_id" — the shape that actually signals PII work.
PII_RE = re.compile(r"\b(pii|ktp|passport|npwp)\b", re.IGNORECASE)
CLIENT_DATA_RE = re.compile(r"\bclient[_\s]+(?:id|data|record|file|pii)\b", re.IGNORECASE)

HOTZONE_TUPLE_RE = re.compile(r"HOTZONE_PATTERNS[^=]*=\s*\(([^)]*)\)", re.DOTALL)
HOTZONE_STRING_RE = re.compile(r'"([^"]+)"')

# Anchored to (optional leading horizontal whitespace +) start of line,
# MULTILINE (2026-08-22, final round, found by a cross-family panel): the
# prior bare search matched ROUTING_FLOOR_OK=... anywhere at all, including
# inside an explicit negation — "we should never set ROUTING_FLOOR_OK=yes
# here" overrode the floor. This is the shape a session writes DELIBERATELY
# (its own line), not one buried mid-sentence; negation-detection was
# explicitly rejected as the fix (rabbit hole, wrong instrument) in favor
# of this structural anchor.
OVERRIDE_RE = re.compile(r"^[ \t]*ROUTING_FLOOR_OK=(\S+)", re.MULTILINE)

# Counter-reset "command position" heuristic (2026-08-22 fix round — the
# prior bare `"seat_build.sh" in command` reset on `echo 'use seat_build.sh
# next time'`, which never invokes anything). Splits on shell separators,
# tokenizes each sub-command, skips VAR=value assignments and a small
# interpreter allowlist, and requires the basename of the PROGRAM token
# (not any token) to be one of SEAT_BINARY_NAMES. Deliberately does NOT
# attempt to detect success/failure — a Bash tool_use block's transcript
# entry carries no exit code, only the command text, so "was it actually
# invoked" is the only question this can answer at all.
SHELL_SEPARATOR_RE = re.compile(r"&&|\|\||[;|\n]")
KNOWN_INTERPRETERS = {"bash", "sh", "zsh", "env", "python3", "python"}
ENV_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# Addendum (2026-08-22, same fix round — found by a cross-family refuter,
# DeepSeek v4-pro): the floor used to reset ONLY on its own wrapper's exact
# spelling (seat_build.sh) and silently let a RAW direct call to the seat
# CLI it wraps — codex/kimi/qwen — leave the streak running,
# which is a FALSE ACCUSATION against a session that already complied with
# the mandate by a different, equally legitimate route (the session that
# built this very mandate routed D1 to Codex and D3 to Kimi via raw `codex
# exec`/`kimi -p` calls, before seat_build.sh existed). This is the same
# set scripts/seat_build.sh --seat accepts (codex|kimi|qwen) — kept in sync
# by NAME here so the wrapper and raw-call paths cannot silently diverge.
SEAT_BINARY_NAMES = {"seat_build.sh", "codex", "kimi", "qwen"}


def agent_def_pins_model(subagent_type: str, cwd: str) -> bool:
    # Fix (2026-08-22, round 1): a truthy non-string subagent_type used to
    # crash here on `.split(":")`. main()'s field-CLASS fix (2026-08-22,
    # final round) now coerces both `subagent_type` and `cwd` to strings
    # before this is ever called, so this guard is redundant for THAT
    # caller — kept anyway as defense-in-depth for any other caller this
    # function gains, and because it costs nothing.
    if not isinstance(subagent_type, str) or not subagent_type:
        return False
    name = subagent_type.split(":")[-1]
    candidates = [USER_AGENTS / f"{name}.md"]
    if cwd:
        candidates.append(Path(cwd) / ".claude" / "agents" / f"{name}.md")
    for path in candidates:
        try:
            if path.is_file():
                head = path.read_text(encoding="utf-8", errors="replace")[:2000]
                if head.lstrip().startswith("---") and head.count("---") >= 2:
                    fm = head.split("---", 2)[1]
                    if FRONTMATTER_MODEL_RE.search(fm):
                        return True
        except OSError:
            continue
    return False


# --------------------------------------------------------------------------
# Rule 2 helpers
# --------------------------------------------------------------------------


def _is_build_shaped(description: str) -> bool:
    return bool(BUILD_VERB_RE.search(description or ""))


def _is_anthropic_model(model: str) -> bool:
    """First-token-exact match on a "-"-split of the normalised model
    string — see ANTHROPIC_MODEL_TOKENS's comment for why this replaced a
    bare substring test."""
    if not isinstance(model, str) or not model:
        return False
    first = model.strip().lower().split("-", 1)[0]
    return first in ANTHROPIC_MODEL_TOKENS


def _discover_repo_evidence_lint_path(cwd: str):
    """Locate scripts/evidence_pack_lint.py without importing it. Walks up
    from `cwd` (bounded to 8 ancestors — a worktree or main-checkout root is
    always within that), then falls back to the HOME-relative repo location
    for a cwd-less subagent context: `~/nuzantara`, which resolves on all
    three fleet machines (measured 2026-08-23, not the per-machine mapping
    this docstring used to state — that mapping was itself wrong and would
    only drift again). The old repo checkout under the TCC-protected
    `~/Desktop` folder (superscar #1, the W84 variant) is deliberately NOT
    a candidate: scripts/lint_tcc_desktop_paths.py bans that literal path
    segment in tracked *.py/.sh/.plist payloads, and a fallback here would
    reintroduce the exact dependency that lint exists to keep out."""
    candidates = []
    if cwd:
        start = Path(cwd)
        for anc in [start, *list(start.parents)[:8]]:
            candidates.append(anc / "scripts" / "evidence_pack_lint.py")
    candidates.append(Path.home() / "nuzantara" / "scripts" / "evidence_pack_lint.py")
    for c in candidates:
        try:
            if c.is_file():
                return c
        except OSError:
            continue
    return None


def _load_hotzone_patterns(cwd: str):
    """Returns a tuple of hot-zone glob-prefixes, or None if the source
    could not be found/read/parsed. None means UNVERIFIABLE, never "empty"
    — the caller must fail the whole floor rule open on it (see module
    docstring's sourcing note: a false deny on unrecognized hot-zone work is
    worse than a missed floor check)."""
    path = _discover_repo_evidence_lint_path(cwd)
    if path is None:
        return None
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = HOTZONE_TUPLE_RE.search(src)
    if not m:
        return None
    return tuple(HOTZONE_STRING_RE.findall(m.group(1)))


def _matches_hotzone(text: str, patterns) -> bool:
    """Literal, case-sensitive substring match on each pattern's
    non-wildcard prefix — ACCEPTED approximation (2026-08-22, final round),
    same bucket as BUILD_VERB_RE's lexical approximation (see module
    docstring's HONESTY NOTE): a differently-cased path
    (`Apps/Backend-RAG/...`) or a pattern with no useful literal prefix
    would not be recognised. Not engineered around — this is an economy
    guard with a fail-open default and an audible override; the cost of
    the rare miss is one `ROUTING_FLOOR_OK=` line, not a security gap."""
    if not text:
        return False
    for pat in patterns:
        prefix = pat.split("*", 1)[0]
        if prefix and prefix in text:
            return True
    return False


def _is_exempt(description: str, prompt: str, cwd: str, patterns) -> bool:
    # `cwd` (2026-08-22 fix round): the mandate exempts "task description OR
    # worktree path" for hot-zone — `cwd` is the worktree/repo path the
    # PreToolUse payload carries, and it was previously never reaching this
    # check at all, so a build dispatched from inside a hot-zone worktree
    # with a generic description was not exempt. Folded into the same
    # combined text used for all three checks — harmless for migration/pii
    # (a path is unlikely to spuriously contain those words, and if it does,
    # exempting is the fail-open-correct direction anyway).
    text = f"{description}\n{prompt}\n{cwd or ''}"
    return (
        _matches_hotzone(text, patterns)
        or bool(MIGRATION_RE.search(text))
        or bool(PII_RE.search(text))
        or bool(CLIENT_DATA_RE.search(text))
    )


def _command_invokes_non_anthropic_seat(command: str) -> bool:
    """True only when a SEAT_BINARY_NAMES entry is the PROGRAM being
    executed in some sub-command — never merely quoted/mentioned as an
    argument (2026-08-22 fix round: `echo 'use seat_build.sh next time'`
    used to reset the counter under the prior bare substring check, and a
    raw `codex`/`kimi`/`qwen` call wasn't recognised at all —
    see SEAT_BINARY_NAMES's own comment for why that second gap was a
    false-accusation bug, not a cosmetic one). See the module-level
    SHELL_SEPARATOR_RE/KNOWN_INTERPRETERS comment for the exact heuristic
    and its stated limit (no exit-code awareness — the transcript doesn't
    carry one). Renamed from `_command_invokes_seat_build` in the same fix
    round, once its scope widened past that one wrapper."""
    if not command:
        return False
    for sub in SHELL_SEPARATOR_RE.split(command):
        sub = sub.strip()
        if not sub:
            continue
        try:
            tokens = shlex.split(sub)
        except ValueError:
            tokens = sub.split()
        idx = 0
        while idx < len(tokens) and ENV_ASSIGNMENT_RE.match(tokens[idx]):
            idx += 1
        if idx < len(tokens) and tokens[idx] in KNOWN_INTERPRETERS:
            idx += 1
        if idx < len(tokens):
            prog = tokens[idx].rsplit("/", 1)[-1]
            if prog in SEAT_BINARY_NAMES:
                return True
    return False


def _read_transcript(transcript_path: str):
    """Return the transcript text, or None if it cannot be read
    (cannot-verify — never a claim about what it would have said).

    ACCEPTED, measured (2026-08-22, final round): this reads the WHOLE
    file before the MAX_TRANSCRIPT_LINES cap is applied in
    _iter_transcript_events — a real shape (a panel flagged it), not a
    live problem on this fleet. Measured against this machine's largest
    transcript (22 MB) → 0.89s, and against a live growing session
    transcript (2.8 MB) → 0.34s, both far inside the hook's 10s PreToolUse
    budget; a smaller independent spot-check here (2.4 MB) → 0.12s
    end-to-end (read + full _floor_state scan) corroborates the same order
    of magnitude. The panel's 1 GB / OOM scenario does not exist on this
    fleet's real transcripts. Left as-is deliberately — do not add
    chunked/streaming reads for a cost that has been measured, not
    assumed."""
    if not transcript_path:
        return None
    p = Path(transcript_path)
    if not p.exists():
        return None
    try:
        return p.read_text(errors="ignore")
    except OSError:
        return None


def _iter_transcript_events(text: str, max_lines: int = MAX_TRANSCRIPT_LINES):
    """Yield (name, input_dict) for each tool_use block in the transcript,
    most recent `max_lines` lines only (a live transcript can be huge;
    recency is what "consecutive" needs). A malformed or non-dict line is
    skipped, never raised.

    REAL SHAPE (P0 fix, 2026-08-22 — see module docstring): each line is
    one JSON object for a transcript entry; a tool call is NOT at the
    line's top level. It is a block inside `message.content[]` with
    `type == "tool_use"`, e.g.
        {"type":"assistant","message":{"content":[
            {"type":"tool_use","name":"Agent","input":{...}}
        ]}}
    A single line's content[] can carry multiple tool_use blocks (e.g. a
    Bash call alongside a text block) — every one is yielded, not just the
    first."""
    lines = text.splitlines()
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
        if not isinstance(obj, dict):
            continue
        message = obj.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_use":
                continue
            name = block.get("name")
            inp = block.get("input")
            if not isinstance(inp, dict):
                inp = {}
            yield name, inp


def _floor_state(text: str, cwd: str, patterns) -> int:
    """Walk the transcript chronologically; return the count of consecutive
    Anthropic build-shaped Agent dispatches SINCE THE LAST TIME A
    NON-ANTHROPIC BUILD SEAT WAS USED, BY ANY ROUTE — not "since the last
    seat_build.sh invocation" (that was the pre-addendum rule; see below).
    Exempted Anthropic dispatches neither increment nor reset the counter —
    invisible to the floor, exactly like the current call is treated.
    `cwd` is the CURRENT call's worktree path, reused for exemption checks
    on historical dispatches too (a single session runs from one worktree
    throughout, so this is the correct proxy for "were prior dispatches
    also hot-zone work").

    ADDENDUM (2026-08-22, same fix round, found by a cross-family refuter):
    the counter used to reset ONLY on scripts/seat_build.sh by its exact
    spelling — a non-Anthropic seat used any other way (a raw `codex exec`/
    `kimi -p`/`qwen` Bash call, or a build-shaped Agent
    dispatch whose model is genuinely non-Anthropic) left the streak
    running, which is a FALSE ACCUSATION against a session that already
    complied with the mandate's intent by a different, equally legitimate
    route (watching the literal spelling instead of the fact — this
    repo's guard-over-match scar family). It now resets on evidence of a
    non-Anthropic build seat by any of three routes: (1) seat_build.sh,
    (2) a raw seat-binary Bash call (SEAT_BINARY_NAMES, command position —
    see _command_invokes_non_anthropic_seat), (3) a build-shaped Agent
    dispatch whose model is truthy and NOT Anthropic."""
    count = 0
    for name, inp in _iter_transcript_events(text):
        if name == "Bash":
            if _command_invokes_non_anthropic_seat(inp.get("command") or ""):
                count = 0
            continue
        if name != "Agent":
            continue
        desc = inp.get("description") or ""
        model = inp.get("model") or ""
        prompt = inp.get("prompt") or ""
        if not _is_build_shaped(desc):
            continue
        if not _is_anthropic_model(model):
            if model:
                # Route (3): a build-shaped Agent dispatch with a truthy,
                # genuinely non-Anthropic model IS evidence a non-Anthropic
                # seat handled a build — the exact fact this floor cares
                # about, regardless of which route produced it.
                count = 0
            continue
        if _is_exempt(desc, prompt, cwd, patterns):
            continue
        count += 1
    return count


def _find_override(prompt: str, env: dict):
    m = OVERRIDE_RE.search(prompt or "")
    if m:
        return m.group(1)
    val = env.get("ROUTING_FLOOR_OK")
    if val:
        return val
    return None


def _apply_routing_floor(payload: dict, tool_input: dict, model: str, cwd: str) -> int:
    desc = tool_input.get("description") or ""
    prompt = tool_input.get("prompt") or ""

    if not _is_build_shaped(desc):
        return 0
    if not _is_anthropic_model(model):
        return 0

    patterns = _load_hotzone_patterns(cwd)
    if patterns is None:
        return 0  # cannot verify hot-zone exemption -> fail open, floor skipped

    if _is_exempt(desc, prompt, cwd, patterns):
        return 0

    text = _read_transcript(payload.get("transcript_path") or "")
    if text is None:
        return 0  # cannot-verify transcript -> fail open

    historical = _floor_state(text, cwd, patterns)
    total = historical + 1  # +1: the current call, about to happen, is itself a build dispatch
    if total < FLOOR_THRESHOLD:
        return 0

    override = _find_override(prompt, os.environ)
    if override:
        sys.stderr.write(
            "[MODEL-ROUTING-FLOOR] override ROUTING_FLOOR_OK=%r — allowing Anthropic "
            "build dispatch #%d with no non-Anthropic-seat evidence in between. Never "
            "silent: this line is the audit trail.\n" % (override, total)
        )
        return 0

    print(
        "BLOCKED by model_routing_gate — routing floor "
        "(docs/mandates/2026-08-22-arsenal-routing-mandate.md D2): "
        f"{total} consecutive Anthropic build dispatch(es) "
        f"({desc!r}, model={model!r}) with NO EVIDENCE a non-Anthropic build seat was "
        "used (scripts/seat_build.sh, a raw codex/kimi/qwen call, or a "
        "non-Anthropic Agent dispatch) in this transcript since the last reset. Route "
        "this build through a non-Anthropic seat instead:\n"
        "  scripts/seat_build.sh --seat codex --worktree <path> --task-file <path>\n"
        "(swap --seat codex for kimi|qwen — or call codex/kimi/qwen "
        "directly). Any of those resets the "
        "counter. Override if this really must stay Anthropic: set "
        "ROUTING_FLOOR_OK=<reason> in the Agent prompt or in the environment — "
        "never silent, always printed here.",
        file=sys.stderr,
    )
    return 2


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        _gc_record("model_routing_gate", "exempt", None)
        return 0

    # Fix (2026-08-22): valid JSON that isn't a dict (`[]`, `"text"`, `null`,
    # `42`) used to crash on the next line's `.get` — genuine unhandled
    # AttributeError, before any try/except in this function. Fail open.
    if not isinstance(payload, dict):
        _gc_record("model_routing_gate", "exempt", payload)
        return 0

    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        _gc_record("model_routing_gate", "exempt", payload)
        return 0

    # Field-CLASS fix (2026-08-22, final round). Every externally-supplied
    # field this hook reads as a string is coerced to one HERE, ONCE — not
    # per call-site. Two separate rounds were spent on the exact same
    # underlying cause at two different call sites: `subagent_type` non-
    # string crashed `.split(":")` inside agent_def_pins_model (round 1,
    # patched there); `cwd` non-string then crashed `Path(cwd)` in the SAME
    # function one round later (round 2 — the class was never actually
    # fixed, only the one site that had already been caught). Coercing here
    # and writing back into `tool_input`/`payload` means every downstream
    # `.get(...)` — in this function and in _apply_routing_floor, which
    # re-reads these same keys from these same dicts — sees the coerced
    # value transparently, with no signature changes needed anywhere else.
    # `model` is DELIBERATELY excluded: Rule 1 treats "any truthy value" as
    # an explicit choice by design (see the module docstring: "any value:
    # the choice is the point"), no code path calls a string method on it
    # without an isinstance guard (_is_anthropic_model already has one),
    # and coercing a non-string truthy model to "" would silently turn an
    # ALLOW into a DENY for a case that was never actually broken.
    def _as_str(value):
        return value if isinstance(value, str) else ""

    tool_input["description"] = _as_str(tool_input.get("description"))
    tool_input["prompt"] = _as_str(tool_input.get("prompt"))
    tool_input["subagent_type"] = _as_str(tool_input.get("subagent_type"))
    payload["cwd"] = _as_str(payload.get("cwd"))
    payload["transcript_path"] = _as_str(payload.get("transcript_path"))

    model = tool_input.get("model")
    subagent_type = tool_input["subagent_type"]
    cwd = payload["cwd"]

    explicit_ok = bool(model)
    if not explicit_ok and subagent_type == "fork":
        explicit_ok = True
    if not explicit_ok and agent_def_pins_model(subagent_type, cwd):
        explicit_ok = True

    if not explicit_ok:
        desc = tool_input["description"]
        print(
            "BLOCKED by model_routing_gate (regola OBBLIGATORIA, Zero 2026-07-14, "
            "corretta 2026-08-20): "
            f"Agent spawn {desc!r} senza `model` esplicito erediterebbe il modello di "
            "sessione (Opus 5) e brucerebbe quota da orchestratore su lavoro da "
            "implementer. Ripeti la chiamata dichiarando il modello: model:\"sonnet\" "
            "per reader/implementer/analisi, model:\"haiku\" per grunt meccanico, "
            "model:\"opus\" solo se il task richiede davvero quel tier. Opus 5 (effort "
            "xhigh) resta SOLO orchestrazione + final on-disk gate — Fable 5 è fuori "
            "dal workflow (RULED 2026-08-20).",
            file=sys.stderr,
        )
        _gc_record("model_routing_gate", "deny", payload)
        return 2

    if not model:
        # Allowed via "fork" or a frontmatter pin, not via an explicit model
        # string on this call — Rule 2 classifies strictly on tool_input.model
        # (see module docstring), so there is nothing for it to count here.
        _gc_record("model_routing_gate", "allow", payload)
        return 0

    try:
        verdict = _apply_routing_floor(payload, tool_input, model, cwd)
        _gc_record("model_routing_gate", "deny" if verdict == 2 else "allow", payload)
        return verdict
    except Exception:
        # Rule 2 is a routing/economy guard, not a safety boundary — a bug in
        # it must never paralyze the harness. Rule 1's verdict above already
        # stands regardless of what happens here.
        _gc_record("model_routing_gate", "exempt", payload)
        return 0


if __name__ == "__main__":
    sys.exit(main())
