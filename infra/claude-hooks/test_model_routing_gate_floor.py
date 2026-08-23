#!/usr/bin/env python3
"""Guilt + innocence + mutation for model_routing_gate.py's routing floor
(Rule 2, added 2026-08-22 — docs/mandates/2026-08-22-arsenal-routing-mandate.md
D2), plus regression pins for the pre-existing explicit-model rule (Rule 1,
unchanged since 2026-07-14) so this file provably does not regress it.

Why the routing floor exists: measured 2026-08-22, 355 Agent(model:"sonnet")
build dispatches vs 7 cross-family workspace-write Codex builds. Rule 1
("no Agent without an explicit model") cannot fix this on its own — every
one of the 355 already carried an explicit `model:"sonnet"`. Rule 2 forces a
periodic detour through `scripts/seat_build.sh` (Codex/Kimi/Qwen) so
quota, resilience and parallelism spread across the arsenal instead of one
pool absorbing every build.

Tests use real `assert` (pytest-collectible AND directly runnable) — a
corpus that records failures without raising would pass under pytest no
matter what the hook does, which is its own instance of the disease this
family of tests exists to prevent.

Run directly:
    python3 infra/claude-hooks/test_model_routing_gate_floor.py
    PYTHONDONTWRITEBYTECODE=1 python3 infra/claude-hooks/test_model_routing_gate_floor.py --mutate
(--mutate self-checks the corpus against deliberate defects — see MUTANTS
below — and must report every mutant KILLED. PYTHONDONTWRITEBYTECODE=1 is
belt-and-suspenders here: each mutant already runs from its own fresh
tempdir so it cannot collide with a cached .pyc from a prior run, but W121
— mutation testing that ran against poisoned bytecode and reported a false
green — is cheap enough to guard against unconditionally.)

P0 FIX ROUND (2026-08-22, same day): the FIRST version of this file wrote
transcript fixtures as flat `{"name":..., "input":...}` lines — a shape
copied from test_orchestrate_gate_vocab.py's OWN fixture idiom, invented for
that file's convenience, that no real Claude Code transcript ever emits.
Verified against a live `~/.claude/projects/**/*.jsonl` (this very session's
transcript, 1218+ lines): a tool call lives inside `message.content[]`, one
block among possibly several, e.g.
    {"type":"assistant","message":{"content":[
        {"type":"tool_use","name":"Agent","input":{...}}
    ]}}
`_iter_transcript_events()` in the hook saw ZERO events against that real
file under the old fixture-shaped assumption — the floor could never fire
in production despite 18/18 green here. Every fixture below now emits that
real nested shape via `_transcript_line()`, and
`test_real_transcript_shape_is_parsed_end_to_end` uses a literal line
captured off disk (structure verbatim, content text redacted) rather than
one this file invents, per the non-negotiable fixture requirement from the
fix round that found this.
"""
import json
import pathlib
import subprocess
import sys
import tempfile

HOOK = pathlib.Path(__file__).resolve().parent / "model_routing_gate.py"
# Mutation mode points this at a mutant copy; every other test call goes
# through run_gate(), which always execs CURRENT_HOOK — never HOOK directly.
CURRENT_HOOK = HOOK

REPO_ROOT_FOR_HOTZONE = pathlib.Path(__file__).resolve().parents[2]

# A HOTZONE_PATTERNS fixture matching the real scripts/evidence_pack_lint.py
# tuple syntax closely enough for the hook's regex-extraction to round-trip
# it (verified separately against the real file below in
# test_real_repo_hotzone_patterns_load).
FIXTURE_EVIDENCE_LINT = '''\
HOTZONE_PATTERNS: tuple[str, ...] = (
    "apps/backend-rag/backend/services/pricing/*",
    ".github/workflows/*",
    "fly.toml",
)
'''


def _make_repo_fixture(root: pathlib.Path) -> str:
    """A throwaway 'repo root' with just scripts/evidence_pack_lint.py, so
    the hook's hot-zone loader (which walks up from `cwd`) finds a real,
    parseable HOTZONE_PATTERNS without touching the actual repo file."""
    repo = root / "repo"
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    (repo / "scripts" / "evidence_pack_lint.py").write_text(FIXTURE_EVIDENCE_LINT)
    return str(repo)


def _transcript_line(name, inp):
    """One REAL-shaped transcript line (P0 fix, 2026-08-22): a tool call
    lives inside message.content[], never at the line's top level — see the
    module docstring. Every fixture in this file goes through this
    function; none write the old flat {"name","input"} shape any more."""
    return json.dumps({
        "type": "assistant",
        "message": {"content": [{"type": "tool_use", "name": name, "input": inp}]},
    })


def run_gate(tool_input, cwd=None, transcript_events=None, transcript_path=None,
             home=None, env_extra=None, omit_transcript_path=False):
    """Invoke the real hook (or, under --mutate, the current mutant) via
    subprocess. Returns (rc, stdout, stderr).

    `transcript_events` is a list of (name, input_dict) pairs, each written
    as one REAL-shaped transcript line via `_transcript_line()`.
    `transcript_path`, given verbatim, tests an absent/unreadable
    transcript.
    """
    tmp = pathlib.Path(home) if home else pathlib.Path(tempfile.mkdtemp())
    tmp.mkdir(parents=True, exist_ok=True)

    payload = {"tool_name": "Agent", "tool_input": dict(tool_input)}
    if cwd is not None:
        payload["cwd"] = cwd

    if transcript_path is not None:
        payload["transcript_path"] = transcript_path
    elif not omit_transcript_path:
        lines = [_transcript_line(n, i) for n, i in (transcript_events or [])]
        tp = tmp / "transcript.jsonl"
        tp.write_text("\n".join(lines) + ("\n" if lines else ""))
        payload["transcript_path"] = str(tp)

    env = {"HOME": str(tmp), "PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}
    env.update(env_extra or {})

    out = subprocess.run(
        [sys.executable, str(CURRENT_HOOK)], input=json.dumps(payload),
        capture_output=True, text=True, env=env,
    )
    return out.returncode, out.stdout, out.stderr


def _build(desc, model="sonnet"):
    return ("Agent", {"description": desc, "model": model})


def _seat_build():
    return ("Bash", {"command": "scripts/seat_build.sh --seat codex --worktree /tmp/w --task-file /tmp/t.md"})


# ── guilt: 3rd consecutive Anthropic build, 0 seat_build.sh -> deny ────────

def test_guilt_third_consecutive_sonnet_build_denies():
    tmp = tempfile.mkdtemp()
    repo = _make_repo_fixture(pathlib.Path(tmp))
    history = [_build("fix the retry logic"), _build("implement the new endpoint")]
    rc, out, err = run_gate(
        {"description": "add another feature", "model": "sonnet"},
        cwd=repo, transcript_events=history, home=tmp,
    )
    assert rc == 2, f"3rd consecutive Anthropic build must deny, got rc={rc} err={err!r}"
    assert "seat_build.sh" in err, f"deny message must hand over a usable line: {err!r}"
    assert "--seat codex" in err, err
    assert out == "", f"deny path prints to stderr only: {out!r}"


# ── innocence ────────────────────────────────────────────────────────────

def test_innocence_two_builds_below_threshold_allows():
    tmp = tempfile.mkdtemp()
    repo = _make_repo_fixture(pathlib.Path(tmp))
    history = [_build("fix the retry logic")]
    rc, _, err = run_gate(
        {"description": "implement the second thing", "model": "sonnet"},
        cwd=repo, transcript_events=history, home=tmp,
    )
    assert rc == 0, f"2 total builds is below the floor: rc={rc} err={err!r}"


def test_innocence_seat_build_between_resets_counter():
    tmp = tempfile.mkdtemp()
    repo = _make_repo_fixture(pathlib.Path(tmp))
    history = [_build("fix the retry logic"), _build("implement the new endpoint"), _seat_build()]
    rc, _, err = run_gate(
        {"description": "add another feature", "model": "sonnet"},
        cwd=repo, transcript_events=history, home=tmp,
    )
    assert rc == 0, f"a seat_build.sh call must reset the counter: rc={rc} err={err!r}"


def test_innocence_hotzone_description_allows_regardless_of_count():
    tmp = tempfile.mkdtemp()
    repo = _make_repo_fixture(pathlib.Path(tmp))
    history = [_build("fix the retry logic"), _build("implement the new endpoint")]
    rc, _, err = run_gate(
        {"description": "fix the pricing tiers in apps/backend-rag/backend/services/pricing/", "model": "sonnet"},
        cwd=repo, transcript_events=history, home=tmp,
    )
    assert rc == 0, f"hot-zone work is exempt: rc={rc} err={err!r}"


def test_innocence_migration_description_allows_regardless_of_count():
    tmp = tempfile.mkdtemp()
    repo = _make_repo_fixture(pathlib.Path(tmp))
    history = [_build("fix the retry logic"), _build("implement the new endpoint")]
    rc, _, err = run_gate(
        {"description": "write the migration for the new column", "model": "sonnet"},
        cwd=repo, transcript_events=history, home=tmp,
    )
    assert rc == 0, f"migration work is exempt: rc={rc} err={err!r}"


def test_innocence_pii_description_allows_regardless_of_count():
    tmp = tempfile.mkdtemp()
    repo = _make_repo_fixture(pathlib.Path(tmp))
    history = [_build("fix the retry logic"), _build("implement the new endpoint")]
    rc, _, err = run_gate(
        {"description": "fix the client passport OCR field mapping", "model": "sonnet"},
        cwd=repo, transcript_events=history, home=tmp,
    )
    assert rc == 0, f"PII-shaped work is exempt: rc={rc} err={err!r}"


def test_innocence_explicit_override_allows_and_notifies():
    tmp = tempfile.mkdtemp()
    repo = _make_repo_fixture(pathlib.Path(tmp))
    history = [_build("fix the retry logic"), _build("implement the new endpoint")]
    rc, _, err = run_gate(
        {"description": "add another feature", "model": "sonnet",
         "prompt": "ROUTING_FLOOR_OK=quota-emergency go ahead"},
        cwd=repo, transcript_events=history, home=tmp,
    )
    assert rc == 0, f"override must allow: rc={rc} err={err!r}"
    assert "ROUTING_FLOOR_OK" in err, f"override must never be silent: {err!r}"
    assert "quota-emergency" in err, f"override notice must name the reason: {err!r}"


def test_innocence_env_override_allows_and_notifies():
    tmp = tempfile.mkdtemp()
    repo = _make_repo_fixture(pathlib.Path(tmp))
    history = [_build("fix the retry logic"), _build("implement the new endpoint")]
    rc, _, err = run_gate(
        {"description": "add another feature", "model": "sonnet"},
        cwd=repo, transcript_events=history, home=tmp,
        env_extra={"ROUTING_FLOOR_OK": "env-reason"},
    )
    assert rc == 0, err
    assert "env-reason" in err, err


def test_innocence_three_read_shaped_dispatches_never_floored():
    tmp = tempfile.mkdtemp()
    repo = _make_repo_fixture(pathlib.Path(tmp))
    history = [
        ("Agent", {"description": "explore the pricing module", "model": "sonnet"}),
        ("Agent", {"description": "read the current config", "model": "sonnet"}),
        ("Agent", {"description": "audit the invoicing schema", "model": "sonnet"}),
    ]
    rc, _, err = run_gate(
        {"description": "review the PR diff", "model": "sonnet"},
        cwd=repo, transcript_events=history, home=tmp,
    )
    assert rc == 0, f"read/explore/audit/review are not build-shaped: rc={rc} err={err!r}"


def test_innocence_prefix_word_boundary_not_counted_as_fix():
    tmp = tempfile.mkdtemp()
    repo = _make_repo_fixture(pathlib.Path(tmp))
    history = [_build("fix the retry logic"), _build("implement the new endpoint")]
    rc, _, err = run_gate(
        {"description": "apply a prefix rule to the filenames", "model": "sonnet"},
        cwd=repo, transcript_events=history, home=tmp,
    )
    assert rc == 0, f"'prefix' must not match 'fix' on word boundaries: rc={rc} err={err!r}"


def test_innocence_address_word_boundary_not_counted_as_add():
    tmp = tempfile.mkdtemp()
    repo = _make_repo_fixture(pathlib.Path(tmp))
    history = [_build("fix the retry logic"), _build("implement the new endpoint")]
    rc, _, err = run_gate(
        # NOTE: avoid the word "shipping" here — it legitimately matches the
        # ship(?:ping)? gerund alternative added in the 2026-08-22 fix round
        # and would make this fixture accidentally build-shaped for a real
        # reason, defeating the point of this specific word-boundary test.
        {"description": "update the customer's home address on file", "model": "sonnet"},
        cwd=repo, transcript_events=history, home=tmp,
    )
    assert rc == 0, f"'address' must not match 'add' on word boundaries: rc={rc} err={err!r}"


def test_innocence_unreadable_transcript_fails_open():
    tmp = tempfile.mkdtemp()
    repo = _make_repo_fixture(pathlib.Path(tmp))
    rc, _, err = run_gate(
        {"description": "add another feature", "model": "sonnet"},
        cwd=repo, home=tmp,
        transcript_path=str(pathlib.Path(tmp) / "does-not-exist.jsonl"),
    )
    assert rc == 0, f"an unreadable transcript must fail open: rc={rc} err={err!r}"


def test_innocence_hotzone_source_unavailable_fails_open():
    """If scripts/evidence_pack_lint.py cannot be found at all (no repo
    fixture, HOME points nowhere useful), hot-zone exemption is
    UNVERIFIABLE — the whole floor must skip rather than risk a false deny
    (module docstring's sourcing note)."""
    tmp = tempfile.mkdtemp()
    history = [_build("fix the retry logic"), _build("implement the new endpoint")]
    rc, _, err = run_gate(
        {"description": "add another feature", "model": "sonnet"},
        cwd=str(pathlib.Path(tmp) / "no-such-repo"), transcript_events=history, home=tmp,
    )
    assert rc == 0, f"unverifiable hot-zone evidence must fail open: rc={rc} err={err!r}"


def test_real_repo_hotzone_patterns_load():
    """Sanity: the loader must round-trip the REAL repo file's syntax, not
    just the test fixture's — catches drift in evidence_pack_lint.py's
    HOTZONE_PATTERNS formatting before it silently defeats the exemption."""
    sys.path.insert(0, str(REPO_ROOT_FOR_HOTZONE))
    try:
        import importlib.util
        spec_path = REPO_ROOT_FOR_HOTZONE / "infra" / "claude-hooks" / "model_routing_gate.py"
        spec = importlib.util.spec_from_file_location("model_routing_gate", spec_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.path.pop(0)
    patterns = mod._load_hotzone_patterns(str(REPO_ROOT_FOR_HOTZONE))
    assert patterns is not None, "must load the real repo's HOTZONE_PATTERNS"
    assert ".github/workflows/*" in patterns, patterns


# ── real-shape fixture (2026-08-22 fix round, P0) ───────────────────────────
# Captured off disk from a live ~/.claude/projects/-Users-balizero-nuzantara/
# 59bef420-....jsonl — this very session's own transcript, 2026-08-22.
# Structure and key names are verbatim from a real Agent tool_use block in
# that file; free-text VALUES (description/prompt/command) are test-authored
# replacements, not the session's real content — this is a shape capture,
# not a content leak. This is exactly what the P0 bug never saw.

REAL_SHAPE_AGENT_LINE = json.dumps({
    "type": "assistant",
    "uuid": "REDACTED",
    "sessionId": "REDACTED",
    "isSidechain": False,
    "message": {
        "type": "message",
        "role": "assistant",
        "content": [
            {
                "type": "tool_use",
                "id": "REDACTED",
                "name": "Agent",
                "input": {
                    "description": "add another feature",
                    "subagent_type": "general-purpose",
                    "model": "sonnet",
                    "name": "REDACTED",
                    "prompt": "REDACTED",
                },
            }
        ],
    },
})


def test_real_transcript_shape_is_parsed_end_to_end():
    """Non-negotiable per the 2026-08-22 fix round: at least one test must
    exercise a transcript LINE shape captured off disk from a real
    ~/.claude/projects/**/*.jsonl, not a hand-invented one — that exact gap
    (every fixture here used to write a flat top-level {"name","input"}
    shape no real transcript ever emits) is what let P0 pass 18/18 green
    the first time. Builds a transcript from two REAL_SHAPE_AGENT_LINE
    copies and confirms the floor engages exactly as in
    test_guilt_third_consecutive_sonnet_build_denies — end-to-end proof
    the parser reads the real nested shape, not just that
    _iter_transcript_events does in isolation against a hand-built object."""
    tmp = tempfile.mkdtemp()
    repo = _make_repo_fixture(pathlib.Path(tmp))
    tp = pathlib.Path(tmp) / "real-shape-transcript.jsonl"
    tp.write_text(REAL_SHAPE_AGENT_LINE + "\n" + REAL_SHAPE_AGENT_LINE + "\n")
    rc, _, err = run_gate(
        {"description": "add a third feature", "model": "sonnet"},
        cwd=repo, transcript_path=str(tp), home=tmp,
    )
    assert rc == 2, f"a real-shaped transcript must be parsed and deny at count 3: rc={rc} err={err!r}"
    assert "seat_build.sh" in err, err


# ── anthropic-model classification (2026-08-22 fix round) ──────────────────
# The prior `any(tok in m for tok in ("sonnet","haiku","opus"))` was a bare
# substring test and over-matched lookalike names.

def test_innocence_anthropic_lookalike_models_not_counted():
    tmp = tempfile.mkdtemp()
    repo = _make_repo_fixture(pathlib.Path(tmp))
    history = [
        _build("fix the retry logic", model="haikuish-local-llm"),
        _build("implement the new endpoint", model="my-custom-sonnetdb-worker"),
    ]
    rc, _, err = run_gate(
        {"description": "add another feature", "model": "haikuish-local-llm"},
        cwd=repo, transcript_events=history, home=tmp,
    )
    assert rc == 0, f"model lookalikes must not be classified Anthropic: rc={rc} err={err!r}"


def test_guilt_dashed_anthropic_model_aliases_still_count():
    """opus-5 / claude-sonnet-5 / haiku-4-5 — real aliases used in this
    fleet (CLAUDE.md roster) — must still be recognised: first-token exact
    match, not literal string equality."""
    tmp = tempfile.mkdtemp()
    repo = _make_repo_fixture(pathlib.Path(tmp))
    history = [
        _build("fix the retry logic", model="opus-5"),
        _build("implement the new endpoint", model="claude-sonnet-5"),
    ]
    rc, _, err = run_gate(
        {"description": "add another feature", "model": "haiku-4-5"},
        cwd=repo, transcript_events=history, home=tmp,
    )
    assert rc == 2, f"real dashed model aliases must still count: rc={rc} err={err!r}"


# ── cwd/worktree-path hot-zone exemption (2026-08-22 fix round) ────────────

def test_innocence_hotzone_worktree_cwd_allows_regardless_of_count():
    """The mandate exempts 'task description OR worktree path' — cwd must
    reach the exemption check even with a fully generic description."""
    tmp = tempfile.mkdtemp()
    repo = pathlib.Path(_make_repo_fixture(pathlib.Path(tmp)))
    hotzone_cwd = repo / "apps" / "backend-rag" / "backend" / "services" / "pricing" / "tiers"
    hotzone_cwd.mkdir(parents=True, exist_ok=True)
    history = [_build("fix the retry logic"), _build("implement the new endpoint")]
    rc, _, err = run_gate(
        {"description": "add another feature", "model": "sonnet"},  # generic, not hot-zone by wording
        cwd=str(hotzone_cwd), transcript_events=history, home=tmp,
    )
    assert rc == 0, f"a hot-zone cwd must exempt even a generic description: rc={rc} err={err!r}"


# ── seat_build.sh reset requires command position (2026-08-22 fix round) ───

def test_guilt_echo_mention_of_seat_build_does_not_reset_counter():
    tmp = tempfile.mkdtemp()
    repo = _make_repo_fixture(pathlib.Path(tmp))
    history = [
        _build("fix the retry logic"),
        ("Bash", {"command": "echo 'use seat_build.sh next time'"}),
        _build("implement the new endpoint"),
    ]
    rc, _, err = run_gate(
        {"description": "add another feature", "model": "sonnet"},
        cwd=repo, transcript_events=history, home=tmp,
    )
    assert rc == 2, f"an echoed mention must not reset the counter: rc={rc} err={err!r}"


def test_innocence_chained_seat_build_invocation_resets_counter():
    """cd <worktree> && scripts/seat_build.sh ... — the realistic chained
    form used elsewhere in this repo — must still reset the counter."""
    tmp = tempfile.mkdtemp()
    repo = _make_repo_fixture(pathlib.Path(tmp))
    history = [
        _build("fix the retry logic"),
        _build("implement the new endpoint"),
        ("Bash", {"command": "cd /tmp/w && scripts/seat_build.sh --seat codex "
                              "--worktree /tmp/w --task-file /tmp/t.md"}),
    ]
    rc, _, err = run_gate(
        {"description": "add another feature", "model": "sonnet"},
        cwd=repo, transcript_events=history, home=tmp,
    )
    assert rc == 0, f"a chained real invocation must reset the counter: rc={rc} err={err!r}"


# ── addendum (2026-08-22, cross-family refuter finding, DeepSeek v4-pro) ───
# "The guard recognises exactly ONE spelling of compliance: its own
# wrapper" — a raw call to the seat CLI seat_build.sh wraps (codex/kimi/
# qwen), or a build-shaped Agent dispatch on a genuinely
# non-Anthropic model, left the streak running and denied a session that
# had already complied by a different, equally legitimate route. Now any
# of the three routes resets.

def test_guilt_raw_codex_call_resets_counter():
    tmp = tempfile.mkdtemp()
    repo = _make_repo_fixture(pathlib.Path(tmp))
    history = [
        _build("fix the retry logic"),
        _build("implement the new endpoint"),
        ("Bash", {"command": "codex exec --sandbox workspace-write -c "
                              "model_reasoning_effort=xhigh 'fix the thing'"}),
    ]
    rc, _, err = run_gate(
        {"description": "add another feature", "model": "sonnet"},
        cwd=repo, transcript_events=history, home=tmp,
    )
    assert rc == 0, f"a raw codex exec call must reset the counter: rc={rc} err={err!r}"


def test_guilt_raw_kimi_call_resets_counter():
    tmp = tempfile.mkdtemp()
    repo = _make_repo_fixture(pathlib.Path(tmp))
    history = [
        _build("fix the retry logic"),
        _build("implement the new endpoint"),
        ("Bash", {"command": "kimi -p 'implement the retry logic' "
                              "-m kimi-code/kimi-for-coding"}),
    ]
    rc, _, err = run_gate(
        {"description": "add another feature", "model": "sonnet"},
        cwd=repo, transcript_events=history, home=tmp,
    )
    assert rc == 0, f"a raw kimi call must reset the counter: rc={rc} err={err!r}"


def test_guilt_raw_qwen_call_resets_counter():
    tmp = tempfile.mkdtemp()
    repo = _make_repo_fixture(pathlib.Path(tmp))
    binary_cmd = "qwen -p 'implement the retry logic' < /dev/null"
    history = [
        _build("fix the retry logic"),
        _build("implement the new endpoint"),
        ("Bash", {"command": binary_cmd}),
    ]
    rc, _, err = run_gate(
        {"description": "add another feature", "model": "sonnet"},
        cwd=repo, transcript_events=history, home=tmp,
    )
    assert rc == 0, f"{binary_cmd!r} must reset the counter: rc={rc} err={err!r}"


def test_innocence_mere_mention_of_codex_or_kimi_does_not_reset():
    """Command-position discipline applies to the raw seat binaries too,
    not only seat_build.sh — 'ask codex about this' must not reset."""
    tmp = tempfile.mkdtemp()
    repo = _make_repo_fixture(pathlib.Path(tmp))
    history = [
        _build("fix the retry logic"),
        ("Bash", {"command": "echo 'maybe ask codex or kimi about this next time'"}),
        _build("implement the new endpoint"),
    ]
    rc, _, err = run_gate(
        {"description": "add another feature", "model": "sonnet"},
        cwd=repo, transcript_events=history, home=tmp,
    )
    assert rc == 2, f"a mere mention must not reset the counter: rc={rc} err={err!r}"


def test_guilt_non_anthropic_agent_dispatch_resets_counter():
    """A build-shaped Agent dispatch whose model is genuinely non-Anthropic
    (e.g. a future harness surface that lets Agent target gpt-5.6-sol) is
    itself evidence a non-Anthropic seat handled a build — must reset."""
    tmp = tempfile.mkdtemp()
    repo = _make_repo_fixture(pathlib.Path(tmp))
    history = [
        _build("fix the retry logic"),
        _build("implement the new endpoint"),
        _build("patch the config loader", model="gpt-5.6-sol"),
    ]
    rc, _, err = run_gate(
        {"description": "add another feature", "model": "sonnet"},
        cwd=repo, transcript_events=history, home=tmp,
    )
    assert rc == 0, f"a non-Anthropic Agent dispatch must reset the counter: rc={rc} err={err!r}"


def test_innocence_non_anthropic_agent_dispatch_not_itself_denied():
    """A non-Anthropic build-shaped Agent dispatch is never itself subject
    to the floor (the floor only classifies calls carrying an Anthropic
    model — see module docstring) — sanity-check it always allows."""
    tmp = tempfile.mkdtemp()
    repo = _make_repo_fixture(pathlib.Path(tmp))
    history = [_build("fix the retry logic"), _build("implement the new endpoint")]
    rc, _, err = run_gate(
        {"description": "add a third feature", "model": "gpt-5.6-sol"},
        cwd=repo, transcript_events=history, home=tmp,
    )
    assert rc == 0, f"a non-Anthropic dispatch is never floored: rc={rc} err={err!r}"


# ── genuine crashes (2026-08-22 fix round) — must fail OPEN, never raise ───

def _run_hook_raw(payload_text, env_extra=None):
    """Feed raw text to the hook's stdin directly (bypassing run_gate's
    dict-based payload construction) — needed to send a top-level JSON
    value that ISN'T an object (a list, a string, null, a number)."""
    tmp = tempfile.mkdtemp()
    env = {"HOME": tmp, "PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}
    env.update(env_extra or {})
    out = subprocess.run(
        [sys.executable, str(CURRENT_HOOK)], input=payload_text,
        capture_output=True, text=True, env=env,
    )
    return out.returncode, out.stdout, out.stderr


def test_innocence_non_dict_top_level_payload_fails_open():
    for payload_text in ("[]", '"text"', "null", "42"):
        rc, out, err = _run_hook_raw(payload_text)
        assert rc == 0, f"payload={payload_text!r} must fail open, got rc={rc} err={err!r}"
        assert "Traceback" not in err, f"payload={payload_text!r} must never raise: {err!r}"


def test_innocence_non_string_subagent_type_fails_open_not_raises():
    for bad in (1, {"x": 1}):
        rc, out, err = run_gate({"subagent_type": bad, "description": "x"})
        assert "Traceback" not in err, f"subagent_type={bad!r} must never raise: {err!r}"
        # A non-string/non-"fork"/non-pinning subagent_type legitimately has
        # no explicit model — Rule 1 correctly denies (rc=2) rather than
        # crashing (which is the bug being fixed: AttributeError on .split).
        assert rc in (0, 2), f"subagent_type={bad!r} must resolve to a real verdict, not crash: rc={rc}"


def test_innocence_non_string_cwd_fails_open_not_raises():
    """cwd non-string crashed Path(cwd) in agent_def_pins_model — the SAME
    cause as subagent_type, at a different call site, one round later.
    Fixed as a class (main()'s field-CLASS normalization), not per-site."""
    for bad_cwd in (123, {"a": 1}):
        rc, out, err = run_gate(
            {"subagent_type": "general-purpose", "description": "x"}, cwd=bad_cwd,
        )
        assert "Traceback" not in err, f"cwd={bad_cwd!r} must never raise: {err!r}"
        assert rc == 2, (
            f"cwd={bad_cwd!r}, no model, no valid pin -> Rule 1 correctly denies "
            f"(not a crash), got rc={rc}"
        )
    # None must still resolve exactly as before (explicit contract check).
    rc, _, err = run_gate(
        {"subagent_type": "general-purpose", "description": "x"}, cwd=None,
    )
    assert rc == 2, f"cwd=None: rc={rc} err={err!r}"


# ── addendum (2026-08-22, final round, cross-family panel) ─────────────────
# "client" alone over-exempted; the override fired inside an explicit
# negation. Both found reproducible, both fixed structurally.

def test_guilt_bare_client_mention_no_longer_exempts():
    tmp = tempfile.mkdtemp()
    repo = _make_repo_fixture(pathlib.Path(tmp))
    history = [_build("fix the retry logic"), _build("implement the new endpoint")]
    for desc in ("fix client dashboard", "build the client portal chart"):
        rc, _, err = run_gate(
            {"description": desc, "model": "sonnet"},
            cwd=repo, transcript_events=history, home=tmp,
        )
        assert rc == 2, f"bare 'client' must no longer exempt {desc!r}: rc={rc} err={err!r}"


def test_innocence_client_data_cooccurrence_still_exempts():
    tmp = tempfile.mkdtemp()
    repo = _make_repo_fixture(pathlib.Path(tmp))
    history = [_build("fix the retry logic"), _build("implement the new endpoint")]
    for desc in ("redact client data before egress", "handle client_id lookup"):
        rc, _, err = run_gate(
            {"description": desc, "model": "sonnet"},
            cwd=repo, transcript_events=history, home=tmp,
        )
        assert rc == 0, f"{desc!r} must still exempt: rc={rc} err={err!r}"


def test_guilt_override_inside_negation_does_not_fire():
    tmp = tempfile.mkdtemp()
    repo = _make_repo_fixture(pathlib.Path(tmp))
    history = [_build("fix the retry logic"), _build("implement the new endpoint")]
    for prompt in (
        "We should never set ROUTING_FLOOR_OK=yes here",
        "do NOT use ROUTING_FLOOR_OK=anything",
    ):
        rc, _, err = run_gate(
            {"description": "add another feature", "model": "sonnet", "prompt": prompt},
            cwd=repo, transcript_events=history, home=tmp,
        )
        assert rc == 2, f"override buried in negation must NOT fire: rc={rc} err={err!r}"
        assert "MODEL-ROUTING-FLOOR" not in err, f"no override notice expected: {err!r}"


def test_innocence_override_on_its_own_line_still_fires():
    tmp = tempfile.mkdtemp()
    repo = _make_repo_fixture(pathlib.Path(tmp))
    history = [_build("fix the retry logic"), _build("implement the new endpoint")]
    # Reason is a single \S+ token (OVERRIDE_RE's capture group stops at
    # whitespace, unchanged by the anchoring fix) — hyphenated the way a
    # session would actually write it.
    rc, _, err = run_gate(
        {"description": "add another feature", "model": "sonnet",
         "prompt": "please fix this\nROUTING_FLOOR_OK=codex-window-dead\nthanks"},
        cwd=repo, transcript_events=history, home=tmp,
    )
    assert rc == 0, f"an own-line override must still fire: rc={rc} err={err!r}"
    assert "codex-window-dead" in err, err


# ── innocence: the pre-existing explicit-model rule (Rule 1) unchanged ─────

def test_innocence_bare_agent_still_denied():
    rc, _, err = run_gate({"description": "do a thing"})
    assert rc == 2, f"bare Agent must still deny: rc={rc}"
    assert "BLOCKED by model_routing_gate" in err, err


def test_innocence_model_carrying_agent_still_allowed():
    rc, _, _ = run_gate({"description": "explore the codebase", "model": "sonnet"})
    assert rc == 0


def test_innocence_fork_still_allowed():
    rc, _, _ = run_gate({"subagent_type": "fork", "description": "x"})
    assert rc == 0


def test_innocence_frontmatter_pinned_agent_still_allowed():
    tmp = tempfile.mkdtemp()
    agents_dir = pathlib.Path(tmp) / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "wr2-critic.md").write_text("---\nname: wr2-critic\nmodel: opus\n---\nbody\n")
    rc, _, _ = run_gate({"subagent_type": "wr2-critic", "description": "critique"}, home=tmp)
    assert rc == 0, "a subagent_type whose definition pins model: in frontmatter must be allowed"


# ── mutation self-check ─────────────────────────────────────────────────────

MUTANTS = [
    (
        "threshold_3_to_4",
        "FLOOR_THRESHOLD = 3",
        "FLOOR_THRESHOLD = 4",
    ),
    (
        # Anchor updated (2026-08-22, final round) after PII_RE was
        # narrowed to drop bare "client" — see client_exemption_over_
        # broadened below for the mutant that pins THAT narrowing itself.
        "pii_exemption_neutered",
        'PII_RE = re.compile(r"\\b(pii|ktp|passport|npwp)\\b", re.IGNORECASE)',
        'PII_RE = re.compile(r"(?!x)x")',
    ),
    (
        # Reverts the P0 fix (2026-08-22): looks at a top-level key that
        # never exists on a real transcript line instead of message.content[]
        # — this is exactly the shape of the original bug, not an arbitrary
        # corruption. Must be killed by test_real_transcript_shape_is_parsed_
        # end_to_end and test_guilt_third_consecutive_sonnet_build_denies.
        "p0_content_walk_reverted",
        'message = obj.get("message")\n'
        '        content = message.get("content") if isinstance(message, dict) else None',
        'message = obj.get("__mutated_away__")\n'
        '        content = message.get("content") if isinstance(message, dict) else None',
    ),
    (
        # Reverts the anthropic-model over-match fix (2026-08-22): back to
        # a bare substring test. Must be killed by
        # test_innocence_anthropic_lookalike_models_not_counted.
        "anthropic_model_substring_reverted",
        'first = model.strip().lower().split("-", 1)[0]\n'
        '    return first in ANTHROPIC_MODEL_TOKENS',
        'm = model.strip().lower()\n'
        '    return any(tok in m for tok in ANTHROPIC_MODEL_TOKENS)',
    ),
    (
        # Reverts the command-position fix (2026-08-22): back to a bare
        # substring test on the whole command string, seat_build.sh only.
        # Must be killed by test_guilt_echo_mention_of_seat_build_does_not_
        # reset_counter (renamed function -> updated anchor after the
        # addendum widened its scope past seat_build.sh alone).
        "seat_command_position_reverted",
        'if _command_invokes_non_anthropic_seat(inp.get("command") or ""):',
        'if "seat_build.sh" in (inp.get("command") or ""):',
    ),
    (
        # Addendum (2026-08-22, cross-family refuter finding): reverts the
        # seat-binary set back to seat_build.sh only, so a raw codex/kimi/
        # qwen Bash call no longer resets. Must be killed by
        # test_guilt_raw_codex_call_resets_counter (and the sibling
        # kimi/qwen cases).
        "seat_binary_names_narrowed_to_wrapper_only",
        'SEAT_BINARY_NAMES = {"seat_build.sh", "codex", "kimi", "qwen"}',
        'SEAT_BINARY_NAMES = {"seat_build.sh"}',
    ),
    (
        # Final round (2026-08-22, cross-family panel): reverts the
        # field-CLASS normalization to a no-op identity — every externally
        # supplied field (cwd, transcript_path, description, prompt,
        # subagent_type) becomes unguarded again at once. Must be killed
        # by test_innocence_non_string_cwd_fails_open_not_raises (cwd has
        # no OTHER guard anywhere in the file — this is the only thing
        # standing between it and Path(cwd) raising TypeError).
        "field_class_normalization_neutered",
        'def _as_str(value):\n'
        '        return value if isinstance(value, str) else ""',
        'def _as_str(value):\n'
        '        return value',
    ),
    (
        # Final round (2026-08-22, cross-family panel): reverts the
        # client-exemption narrowing — bare "client" exempts again. Must
        # be killed by test_guilt_bare_client_mention_no_longer_exempts.
        "client_exemption_over_broadened",
        'PII_RE = re.compile(r"\\b(pii|ktp|passport|npwp)\\b", re.IGNORECASE)',
        'PII_RE = re.compile(r"\\b(pii|client|ktp|passport|npwp)\\b", re.IGNORECASE)',
    ),
    (
        # Final round (2026-08-22, cross-family panel): reverts the
        # override anchor — fires inside a negation again. Must be killed
        # by test_guilt_override_inside_negation_does_not_fire.
        "override_anchor_removed",
        'OVERRIDE_RE = re.compile(r"^[ \\t]*ROUTING_FLOOR_OK=(\\S+)", re.MULTILINE)',
        'OVERRIDE_RE = re.compile(r"ROUTING_FLOOR_OK=(\\S+)")',
    ),
    (
        # Addendum (2026-08-22, cross-family refuter finding): reverts the
        # non-Anthropic-Agent-dispatch reset back to a silent `continue`
        # (the false-accusation bug DeepSeek v4-pro found). Must be killed
        # by test_guilt_non_anthropic_agent_dispatch_resets_counter.
        "non_anthropic_agent_reset_removed",
        "            if model:\n"
        "                # Route (3): a build-shaped Agent dispatch with a truthy,\n"
        "                # genuinely non-Anthropic model IS evidence a non-Anthropic\n"
        "                # seat handled a build — the exact fact this floor cares\n"
        "                # about, regardless of which route produced it.\n"
        "                count = 0\n"
        "            continue",
        "            continue",
    ),
]


class _MutantAnchorMissing(Exception):
    """Raised when a mutant's `old` string is no longer found in the hook
    source — the anchor decayed under an edit elsewhere in the file that
    didn't update this mutant (2026-08-22, final round: a stale
    `pii_exemption_neutered` anchor killed `--mutate` entirely and the
    failure mode was a raw AssertionError traceback — reads as a crash to
    the next person who hits it, not as the finding it actually is). Caught
    by run_mutation_self_check() and printed as ONE labeled line naming the
    mutant, so `--mutate` still reports every OTHER mutant's real verdict
    instead of dying on the first stale anchor it meets."""


def _write_mutant(old: str, new: str, label: str) -> pathlib.Path:
    src = HOOK.read_text()
    if old not in src:
        raise _MutantAnchorMissing(
            f"anchor string not found in {HOOK.name} — the code under it "
            f"moved or was edited without updating this mutant. Update "
            f"MUTANTS' `old` string for {label!r} to match current source "
            f"(keep `new` a MEANINGFUL revert to the real prior bug, not "
            f"an arbitrary corruption)."
        )
    mutated = src.replace(old, new, 1)
    if mutated == src:
        raise _MutantAnchorMissing(
            f"replacement for {label!r} produced NO CHANGE — `old` and "
            f"`new` are identical text, so this mutant tests nothing."
        )
    mdir = pathlib.Path(tempfile.mkdtemp())
    mfile = mdir / "model_routing_gate.py"
    mfile.write_text(mutated)
    return mfile


def _run_all_tests() -> bool:
    """Run every guilt/innocence test_* function above (NOT this one).
    Returns True iff every one of them passes."""
    all_ok = True
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn) and fn is not _run_all_tests:
            try:
                fn()
            except AssertionError:
                all_ok = False
    return all_ok


def run_mutation_self_check() -> int:
    global CURRENT_HOOK
    import os
    if os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        print(
            "  WARN: PYTHONDONTWRITEBYTECODE=1 not set in this process's env "
            "(W121: mutation testing can run against poisoned bytecode). "
            "run_gate() sets it per-subprocess regardless, but set it on the "
            "outer invocation too.",
            file=sys.stderr,
        )
    original = CURRENT_HOOK
    all_killed = True
    try:
        for label, old, new in MUTANTS:
            try:
                CURRENT_HOOK = _write_mutant(old, new, label)
            except _MutantAnchorMissing as e:
                print(f"  mutant {label}: ANCHOR MISSING — {e}")
                all_killed = False
                continue
            passed = _run_all_tests()
            killed = not passed
            print(f"  mutant {label}: {'KILLED' if killed else 'SURVIVED — corpus is blind to this'}")
            if not killed:
                all_killed = False
    finally:
        CURRENT_HOOK = original
    print()
    print("PASS — every mutant killed" if all_killed else "FAIL — a mutant survived or an anchor is missing")
    return 0 if all_killed else 1


def main() -> int:
    if "--mutate" in sys.argv:
        return run_mutation_self_check()

    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn) and fn is not _run_all_tests:
            try:
                fn()
                print(f"  ok   — {name}")
            except AssertionError as e:
                print(f"  FAIL — {name}: {e}")
                failed += 1
    print()
    print("PASS — model_routing_gate routing floor" if not failed else f"FAIL ({failed})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
