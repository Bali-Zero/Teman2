"""Tests for scripts/ci/harness_gate_read.py — the READ-only harness/fable-gate verdict mirror.

Guilt + innocence per superscar #3 (Guard-over-match) discipline, with the innocence side
deliberately weighted heavier than usual (task brief: "a change that makes the gate publish on
merge_group must not make it publishable by a fork PR's untrusted workflow") — this script must be
provably incapable of writing anything, not merely observed to not write in the paths these tests
happen to exercise. See test_no_write_shaped_string_literal_appears_anywhere_in_the_code and
test_script_exposes_no_publish_or_verdict_cli_flag: those two are static proofs over the script's
OWN source, not behavioral samples, so they cannot be defeated by a code path a future edit adds
and no test happens to walk. Its own guilt pin
(test_write_shaped_literal_scan_actually_catches_the_reviewers_counterexample) exists because an
independent Gear-3 review (2026-08-21) demonstrated the FIRST version of that scan — a plain
substring regex — missed a real write built from split string constants; see that test and
test_no_write_shaped_string_literal_appears_anywhere_in_the_code's own docstring for the full story.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts" / "ci"
sys.path.insert(0, str(SCRIPTS))

import harness_gate_read as hgr  # noqa: E402

SCRIPT_SOURCE = (SCRIPTS / "harness_gate_read.py").read_text()


def _code_only(source: str) -> str:
    """Strip EVERY docstring (module, function, class) before a source-scan test — the
    docstrings illustratively quote the WRITE shape (`-f state=`, `POST/PATCH/PUT`) of the
    design this script deliberately does NOT implement, in the course of explaining why not.
    A naive substring scan over the raw file text would false-positive on that explanation.
    This walks the whole AST rather than special-casing the module docstring, so a future
    function docstring that also explains an invariant by naming the forbidden shape cannot
    reintroduce the same false positive."""
    tree = ast.parse(source)
    excluded_lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                excluded_lines.update(range(body[0].lineno, body[0].end_lineno + 1))
    lines = source.splitlines(keepends=True)
    return "".join(line for i, line in enumerate(lines, start=1) if i not in excluded_lines)


CODE_ONLY_SOURCE = _code_only(SCRIPT_SOURCE)


# ---------------------------------------------------------------------------
# extract_pr_number — merge_group ref parsing
# ---------------------------------------------------------------------------

def test_extract_pr_number_from_real_queue_ref():
    ref = "refs/heads/gh-readonly-queue/main/pr-3302-23dcbfe78addabc0123456789abcdef01234567"
    assert hgr.extract_pr_number(ref) == 3302


def test_extract_pr_number_none_when_ref_missing():
    assert hgr.extract_pr_number(None) is None


def test_extract_pr_number_none_when_ref_not_a_queue_ref():
    assert hgr.extract_pr_number("refs/heads/main") is None


# ---------------------------------------------------------------------------
# resolve_real_head_sha — one branch per event, guilt + innocence
# ---------------------------------------------------------------------------

VALID_SHA_A = "a" * 40
VALID_SHA_B = "b" * 40


def test_pull_request_event_uses_head_sha_directly():
    sha, reason = hgr.resolve_real_head_sha(
        event_name="pull_request", repo="acme/example",
        pr_head_sha=VALID_SHA_A, merge_group_head_ref=None, dispatch_sha=None, gh_bin="gh",
    )
    assert sha == VALID_SHA_A
    assert "pull_request" in reason


def test_pull_request_event_fails_closed_when_head_sha_missing():
    sha, reason = hgr.resolve_real_head_sha(
        event_name="pull_request", repo="acme/example",
        pr_head_sha=None, merge_group_head_ref=None, dispatch_sha=None, gh_bin="gh",
    )
    assert sha is None


def test_pull_request_event_fails_closed_on_malformed_sha():
    sha, _ = hgr.resolve_real_head_sha(
        event_name="pull_request", repo="acme/example",
        pr_head_sha="not-a-sha", merge_group_head_ref=None, dispatch_sha=None, gh_bin="gh",
    )
    assert sha is None


def test_workflow_dispatch_event_uses_github_sha_directly():
    sha, reason = hgr.resolve_real_head_sha(
        event_name="workflow_dispatch", repo="acme/example",
        pr_head_sha=None, merge_group_head_ref=None, dispatch_sha=VALID_SHA_B, gh_bin="gh",
    )
    assert sha == VALID_SHA_B
    assert "workflow_dispatch" in reason


def test_workflow_dispatch_event_fails_closed_when_sha_missing():
    sha, _ = hgr.resolve_real_head_sha(
        event_name="workflow_dispatch", repo="acme/example",
        pr_head_sha=None, merge_group_head_ref=None, dispatch_sha=None, gh_bin="gh",
    )
    assert sha is None


def test_unsupported_event_name_fails_closed():
    sha, reason = hgr.resolve_real_head_sha(
        event_name="push", repo="acme/example",
        pr_head_sha=VALID_SHA_A, merge_group_head_ref=None, dispatch_sha=None, gh_bin="gh",
    )
    assert sha is None
    assert "unsupported" in reason


def test_merge_group_event_resolves_via_live_pr_lookup(monkeypatch):
    """Innocence: the CORE happy path this whole design exists for — a merge_group run
    recovering the PR's real (non-synthetic) head sha via a READ-only `gh pr view`."""
    calls = []

    def fake_run_gh(gh_bin, args):
        calls.append(args)
        assert args[:2] == ["pr", "view"], "must be a read (pr view), never a write"
        return '{"headRefOid": "%s"}' % VALID_SHA_A

    monkeypatch.setattr(hgr, "_run_gh", fake_run_gh)
    ref = "refs/heads/gh-readonly-queue/main/pr-42-" + ("f" * 40)
    sha, reason = hgr.resolve_real_head_sha(
        event_name="merge_group", repo="acme/example",
        pr_head_sha=None, merge_group_head_ref=ref, dispatch_sha=None, gh_bin="gh",
    )
    assert sha == VALID_SHA_A
    assert "#42" in reason
    assert len(calls) == 1


def test_merge_group_event_fails_closed_when_ref_unparseable(monkeypatch):
    def fake_run_gh(gh_bin, args):  # pragma: no cover - must never be called
        raise AssertionError("gh must not be invoked when the PR number cannot be parsed")

    monkeypatch.setattr(hgr, "_run_gh", fake_run_gh)
    sha, reason = hgr.resolve_real_head_sha(
        event_name="merge_group", repo="acme/example",
        pr_head_sha=None, merge_group_head_ref="refs/heads/main", dispatch_sha=None, gh_bin="gh",
    )
    assert sha is None
    assert "could not parse" in reason


def test_merge_group_event_fails_closed_when_gh_pr_view_errors(monkeypatch):
    def fake_run_gh(gh_bin, args):
        raise hgr.GhCallError("network unreachable")

    monkeypatch.setattr(hgr, "_run_gh", fake_run_gh)
    ref = "refs/heads/gh-readonly-queue/main/pr-7-" + ("a" * 40)
    sha, reason = hgr.resolve_real_head_sha(
        event_name="merge_group", repo="acme/example",
        pr_head_sha=None, merge_group_head_ref=ref, dispatch_sha=None, gh_bin="gh",
    )
    assert sha is None
    assert "gh pr view #7 failed" in reason


def test_merge_group_event_fails_closed_on_malformed_json(monkeypatch):
    monkeypatch.setattr(hgr, "_run_gh", lambda gh_bin, args: "not json")
    ref = "refs/heads/gh-readonly-queue/main/pr-7-" + ("a" * 40)
    sha, reason = hgr.resolve_real_head_sha(
        event_name="merge_group", repo="acme/example",
        pr_head_sha=None, merge_group_head_ref=ref, dispatch_sha=None, gh_bin="gh",
    )
    assert sha is None
    assert "unparseable JSON" in reason


def test_merge_group_event_fails_closed_when_headrefoid_missing(monkeypatch):
    monkeypatch.setattr(hgr, "_run_gh", lambda gh_bin, args: "{}")
    ref = "refs/heads/gh-readonly-queue/main/pr-7-" + ("a" * 40)
    sha, reason = hgr.resolve_real_head_sha(
        event_name="merge_group", repo="acme/example",
        pr_head_sha=None, merge_group_head_ref=ref, dispatch_sha=None, gh_bin="gh",
    )
    assert sha is None
    assert "no usable headRefOid" in reason


# ---------------------------------------------------------------------------
# read_fable_gate_state
# ---------------------------------------------------------------------------

def test_read_fable_gate_state_success(monkeypatch):
    payload = '{"statuses": [{"context": "harness/fable-gate", "state": "success", "description": "PASS"}]}'
    monkeypatch.setattr(hgr, "_run_gh", lambda gh_bin, args: payload)
    state, desc = hgr.read_fable_gate_state(sha=VALID_SHA_A, repo="acme/example", gh_bin="gh")
    assert state == "success"
    assert desc == "PASS"


def test_read_fable_gate_state_none_when_statuses_empty(monkeypatch):
    """Innocence: an empty statuses array is a genuine 'never posted' — reported as
    (None, None), a distinct shape from a failed read (see the GhCallError tests below)."""
    monkeypatch.setattr(hgr, "_run_gh", lambda gh_bin, args: '{"statuses": []}')
    state, desc = hgr.read_fable_gate_state(sha=VALID_SHA_A, repo="acme/example", gh_bin="gh")
    assert state is None
    assert desc is None


def test_read_fable_gate_state_ignores_other_contexts(monkeypatch):
    """Guilt: a same-commit status from an unrelated context (e.g. hot-zone-enforcement) must
    never be mistaken for the harness/fable-gate verdict."""
    payload = '{"statuses": [{"context": "hot-zone-enforcement", "state": "success"}]}'
    monkeypatch.setattr(hgr, "_run_gh", lambda gh_bin, args: payload)
    state, desc = hgr.read_fable_gate_state(sha=VALID_SHA_A, repo="acme/example", gh_bin="gh")
    assert state is None


def test_read_fable_gate_state_picks_the_target_context_among_several(monkeypatch):
    payload = (
        '{"statuses": ['
        '{"context": "hot-zone-enforcement", "state": "success"},'
        '{"context": "harness/fable-gate", "state": "failure", "description": "REWORK-BUILD"}'
        "]}"
    )
    monkeypatch.setattr(hgr, "_run_gh", lambda gh_bin, args: payload)
    state, desc = hgr.read_fable_gate_state(sha=VALID_SHA_A, repo="acme/example", gh_bin="gh")
    assert state == "failure"
    assert desc == "REWORK-BUILD"


def test_read_fable_gate_state_raises_not_returns_none_on_gh_failure(monkeypatch):
    """Guilt/CANNOT-VERIFY: a broken read must never be silently reported as 'no verdict posted'
    — that would let a network blip read as a clean pending state instead of a defect (cicatrix
    W88/W106 — a proxy that can't check must never claim to have checked)."""
    def fake_run_gh(gh_bin, args):
        raise hgr.GhCallError("rate limited")

    monkeypatch.setattr(hgr, "_run_gh", fake_run_gh)
    try:
        hgr.read_fable_gate_state(sha=VALID_SHA_A, repo="acme/example", gh_bin="gh")
        assert False, "expected GhCallError to propagate"
    except hgr.GhCallError:
        pass


def test_read_fable_gate_state_raises_on_malformed_json(monkeypatch):
    monkeypatch.setattr(hgr, "_run_gh", lambda gh_bin, args: "not json")
    try:
        hgr.read_fable_gate_state(sha=VALID_SHA_A, repo="acme/example", gh_bin="gh")
        assert False, "expected GhCallError to propagate"
    except hgr.GhCallError:
        pass


def test_read_fable_gate_state_raises_when_statuses_key_missing_shape(monkeypatch):
    monkeypatch.setattr(hgr, "_run_gh", lambda gh_bin, args: '{"sha": "x"}')
    try:
        hgr.read_fable_gate_state(sha=VALID_SHA_A, repo="acme/example", gh_bin="gh")
        assert False, "expected GhCallError to propagate"
    except hgr.GhCallError:
        pass


# ---------------------------------------------------------------------------
# decide — the only state mapping to exit 0
# ---------------------------------------------------------------------------

def test_decide_success_state_passes():
    code, _ = hgr.decide("success")
    assert code == 0


def test_decide_none_state_fails_closed_and_says_pending():
    code, msg = hgr.decide(None)
    assert code == 1
    assert "PENDING" in msg


def test_decide_failure_state_fails():
    code, _ = hgr.decide("failure")
    assert code == 1


def test_decide_error_state_fails():
    code, _ = hgr.decide("error")
    assert code == 1


def test_decide_never_returns_zero_for_anything_but_literal_success():
    for garbage in ("Success", " success", "success ", "SUCCESS", "ok", "", "pending", "true", "1"):
        code, _ = hgr.decide(garbage)
        assert code != 0, f"decide({garbage!r}) must not pass"


# ---------------------------------------------------------------------------
# main() — the ONLY code path CI actually executes, and (until now) the
# only one this corpus never exercised. An independent Gear-3 review (F2,
# HIGH, 2026-08-21) mutated a sandbox copy and found THREE fail-open
# mutations survived all 30 prior tests: `main()` returning 0 on an
# unresolvable head sha, returning 0 on a GhCallError (CANNOT-VERIFY reading
# as pass), and discarding `decide()`'s code entirely and always returning 0.
# Every helper function was tested in isolation; the wiring between them —
# the only thing a shipped CI step actually runs — had zero coverage. These
# tests call `hgr.main([...])` directly, monkeypatching the two functions it
# orchestrates, so each of the three mutations above now turns one of these
# tests red.
# ---------------------------------------------------------------------------

def test_main_returns_1_when_head_sha_unresolvable(monkeypatch, capsys):
    monkeypatch.setattr(hgr, "resolve_real_head_sha", lambda **kw: (None, "unresolvable in test"))

    def fail_if_called(**kw):  # pragma: no cover - must never run
        raise AssertionError("read_fable_gate_state must not be called when sha resolution failed")

    monkeypatch.setattr(hgr, "read_fable_gate_state", fail_if_called)
    code = hgr.main(["--event-name", "pull_request", "--repo", "acme/example"])
    assert code == 1
    assert "could not resolve" in capsys.readouterr().err


def test_main_returns_1_on_cannot_verify_never_reads_as_pending_or_pass(monkeypatch, capsys):
    """The CANNOT-VERIFY case (the read itself failed) must fail exactly like every other
    non-success outcome — a network blip must never be silently treated as a clean pass."""
    monkeypatch.setattr(hgr, "resolve_real_head_sha", lambda **kw: (VALID_SHA_A, "test"))

    def raise_gh_error(**kw):
        raise hgr.GhCallError("simulated network failure")

    monkeypatch.setattr(hgr, "read_fable_gate_state", raise_gh_error)
    code = hgr.main(["--event-name", "pull_request", "--repo", "acme/example", "--pr-head-sha", VALID_SHA_A])
    assert code == 1
    assert "CANNOT-VERIFY" in capsys.readouterr().err


def test_main_returns_0_only_on_a_real_success_verdict(monkeypatch, capsys):
    monkeypatch.setattr(hgr, "resolve_real_head_sha", lambda **kw: (VALID_SHA_A, "test"))
    monkeypatch.setattr(hgr, "read_fable_gate_state", lambda **kw: ("success", "PASS"))
    code = hgr.main(["--event-name", "pull_request", "--repo", "acme/example", "--pr-head-sha", VALID_SHA_A])
    assert code == 0
    assert "::notice::" in capsys.readouterr().out


def test_main_returns_1_on_a_real_non_success_verdict_never_swallowed_as_0(monkeypatch, capsys):
    """Guards against `main()` discarding `decide()`'s return code and always exiting 0 — the
    third fail-open mutation the independent review demonstrated survives without this test."""
    monkeypatch.setattr(hgr, "resolve_real_head_sha", lambda **kw: (VALID_SHA_A, "test"))
    monkeypatch.setattr(hgr, "read_fable_gate_state", lambda **kw: ("failure", "REWORK-BUILD"))
    code = hgr.main(["--event-name", "pull_request", "--repo", "acme/example", "--pr-head-sha", VALID_SHA_A])
    assert code == 1
    stderr = capsys.readouterr().err
    assert "REWORK-BUILD" in stderr or "failure" in stderr


def test_main_returns_1_when_no_verdict_posted_yet(monkeypatch, capsys):
    monkeypatch.setattr(hgr, "resolve_real_head_sha", lambda **kw: (VALID_SHA_A, "test"))
    monkeypatch.setattr(hgr, "read_fable_gate_state", lambda **kw: (None, None))
    code = hgr.main(["--event-name", "pull_request", "--repo", "acme/example", "--pr-head-sha", VALID_SHA_A])
    assert code == 1
    assert "PENDING" in capsys.readouterr().err


def test_main_end_to_end_via_real_subprocess_smoke():
    """One real subprocess invocation (no monkeypatching, no network — an unresolvable-sha path
    that never reaches `gh`) proving the CLI wiring itself (argparse, exit code propagation via
    `raise SystemExit(main())`) works end to end, not just the in-process `hgr.main()` calls
    above. Mirrors harness_fable_gate.py's own `test_cli_dry_run_prints_gh_command_without_network`
    pattern (scripts/tests/test_harness_fable_gate.py)."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "harness_gate_read.py"),
         "--event-name", "pull_request", "--repo", "acme/example"],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 1
    assert "could not resolve" in proc.stderr


# ---------------------------------------------------------------------------
# Fork-PR safety by CONSTRUCTION — static proofs over the script's own source.
# These cannot be defeated by a future code path a behavioral test forgets to
# exercise, because they scan every line of the shipped script, not a sample.
# ---------------------------------------------------------------------------

def test_no_write_shaped_string_literal_appears_anywhere_in_the_code():
    """AST-based proof, allow-list-adjacent in spirit: scans every string CONSTANT node in the
    script (docstrings included — see below for why that is safe here) for exact-match
    write-verb flags and write-shaped value PREFIXES.

    CLOSES a gap an independent Gear-3 review demonstrated LIVE (2026-08-21, finding F3): the
    superseded regex `r"-f\\s+state="` looked for `-f` and `state=` as ONE adjacent token, so a
    call built as `_run_gh(gh_bin, ["api", url, "-f", field_state, "-f", field_ctx])` with
    `field_state = "state=" + verdict` sailed through 30/30 tests — `-f` and `state=` are each
    individually present as SEPARATE string constants (the literal `"-f"` twice, `"state="` via
    the `+` concatenation), invisible to a whole-file regex over adjacent characters. Scanning
    `ast.Constant` string VALUES one node at a time catches both independently: `-f` matches
    the exact-flag set on its own, `state=`/`context=` match the value-prefix set on their own
    — an attacker doesn't get to split the tell into two "innocent-looking" pieces and have
    neither one alone read as guilty.

    Deliberately scans the FULL source (docstrings included), unlike the two source-scan tests
    below — and that is safe, not an oversight: prose describing "-f state=" in a docstring
    renders as ONE joined phrase inside a single large multi-paragraph ast.Constant string, which
    is neither EQUAL to a banned exact flag nor STARTS WITH a banned prefix. Only a genuine,
    standalone string literal in actual code can trip this — verified: this test passes
    unmodified against this file's own docstrings."""
    banned_exact = {"-f", "-F", "-X", "--method", "--field", "--raw-field", "-d", "--input", "-i"}
    banned_prefixes = ("state=", "context=", "POST", "PATCH", "PUT")
    tree = ast.parse(SCRIPT_SOURCE)
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value
            if value in banned_exact:
                offenders.append((node.lineno, repr(value), "exact-flag"))
            elif value.startswith(banned_prefixes):
                offenders.append((node.lineno, repr(value), "value-prefix"))
    assert not offenders, f"write-shaped string literal(s) found: {offenders}"


def test_write_shaped_literal_scan_actually_catches_the_reviewers_counterexample():
    """Guilt pin for the test above: run the SAME scan logic against the literal counterexample
    an independent review supplied (a `-f state=...` write built from split string constants),
    on a throwaway AST — never against this repo's own script — to prove the scan is not
    vacuously green. If this test starts failing, the scan above has stopped being able to catch
    the exact shape it was written to catch."""
    poisoned_source = (
        "def publish_backdoor(gh_bin, repo, sha, verdict):\n"
        '    field_state = "state=" + verdict\n'
        '    field_ctx = "context=" + "harness/fable-gate"\n'
        '    _run_gh(gh_bin, ["api", f"repos/{repo}/statuses/{sha}", "-f", field_state, "-f", field_ctx])\n'
    )
    banned_exact = {"-f", "-F", "-X", "--method", "--field", "--raw-field", "-d", "--input", "-i"}
    banned_prefixes = ("state=", "context=", "POST", "PATCH", "PUT")
    tree = ast.parse(poisoned_source)
    offenders = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and (node.value in banned_exact or node.value.startswith(banned_prefixes))
    ]
    assert offenders, "the scan failed to catch its own reference counterexample — it is not testing anything"
    assert "-f" in offenders
    assert "state=" in offenders


def test_script_only_calls_gh_with_read_subcommands():
    """Every literal argv this script builds for `gh` starts with a read-shaped subcommand
    ('pr view' or 'api ... commits/.../status', a GET by REST convention with no -f/-X). Kept as
    defense-in-depth alongside the stronger AST scan above — `re.DOTALL` so a call site
    reformatted across multiple lines is not silently invisible to this regex (an independent
    review noted the non-DOTALL version would miss exactly that)."""
    invocations = re.findall(r'_run_gh\(gh_bin,\s*\[(.*?)\]\)', CODE_ONLY_SOURCE, re.DOTALL)
    assert invocations, "expected to find at least one _run_gh(...) call site to audit"
    for call in invocations:
        assert '"pr", "view"' in call or '"api"' in call, f"unexpected gh invocation shape: {call}"


def test_script_exposes_no_publish_or_verdict_cli_flag():
    """This script's argparse surface must never grow a --verdict/--publish/--state flag — that
    would reintroduce the exact write capability the design deliberately removed from the
    merge_group/fork-PR path."""
    banned_flags = ["--verdict", "--publish", "--state", "--sha-to-publish", "--write"]
    for flag in banned_flags:
        assert flag not in CODE_ONLY_SOURCE, f"banned CLI flag present: {flag}"


def test_script_context_constant_matches_the_publisher():
    """Sanity: this script's CONTEXT must be byte-identical to harness_fable_gate.py's, or it
    would silently read the wrong status forever."""
    sys.path.insert(0, str(REPO / "scripts"))
    import harness_fable_gate  # noqa: E402
    assert hgr.CONTEXT == harness_fable_gate.CONTEXT


def _mentions_are_all_prohibitions(text: str, phrase: str) -> bool:
    """True if every occurrence of `phrase` is negated by a marker within the 60 characters
    before it. Used instead of a bare `phrase not in text`, because the CORRECT text has to name
    the wrong command in order to forbid it — a guard that bans the mention bans the cure along
    with the disease (cicatrix #3, guard-over-match). The first draft of these two tests did
    exactly that and failed against the very text it was written to protect."""
    markers = ("do not", "don't", "never", "used to say", "instead of", "not ")
    idx = text.lower().find(phrase.lower())
    while idx != -1:
        window = text.lower()[max(0, idx - 60) : idx]
        if not any(m in window for m in markers):
            return False
        idx = text.lower().find(phrase.lower(), idx + 1)
    return True


def test_pending_message_prescribes_rerun_and_only_forbids_workflow_dispatch():
    """The PENDING annotation is the one place a blocked session is GUARANTEED to read, so a wrong
    recovery command there costs more than a wrong one in any doc.

    It used to prescribe `gh workflow run harness-floor.yml --ref <branch>` and forbid
    `gh run rerun` outright. That is backwards for this job and deadlocked #4543: a
    workflow_dispatch run puts its check-run in a DIFFERENT check suite, and that check-run never
    enters the PR's statusCheckRollup at all, so the dispatch goes green while the PR stays
    BLOCKED. Nothing pinned the sentence, so it could regrow silently. This pins it."""
    _, msg = hgr.decide(None)
    assert "gh run rerun" in msg, "PENDING message must name the command that actually works"
    assert _mentions_are_all_prohibitions(msg, "gh workflow run"), (
        "PENDING message may mention `gh workflow run` only to forbid it: an un-negated mention "
        "sends a blocked PR to a run that cannot clear its rollup"
    )


def test_module_docstring_does_not_prescribe_workflow_dispatch_as_the_cure():
    """Same regression, one level up: the docstring is what a session reads when it goes looking
    for WHY the check is red. It carried the same repealed instruction as the annotation. A
    historical mention ("used to say ...") is fine; a prescription is not."""
    doc = hgr.__doc__ or ""
    assert "gh run rerun" in doc, "module docstring should name the working recovery command"
    assert _mentions_are_all_prohibitions(doc, "gh workflow run harness-floor.yml --ref"), (
        "module docstring must not prescribe workflow_dispatch as the recovery path"
    )
