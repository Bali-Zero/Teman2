"""scripts/yield_optimizer_pitch_gate.py -- the deterministic PII fail-closed
cancello for yield-optimizer's Step 3 (draft pitch).

yield-optimizer (~/.claude/agents/yield-optimizer.md) is a Claude Sonnet-5
AGENT with unrestricted Bash access, not a Python daemon -- its "Ollama
unreachable: STOP, no fallback to cloud" rule used to live only as prose an
LLM has to remember every run. This module is the code-level gate; this test
file is the guilt+innocence+mutation proof the org's guard-conformance
doctrine (cicatrix-superscar.md #3) requires before a guard like this ships.

Four required proofs (team-lead mandate, 2026-08-20):
  1. Guilt: Ollama unreachable -> a PII-marked payload produces no cloud call
     and a named terminal outcome (SKIPPED_OLLAMA_FAIL), logged.
  2. Innocence: Ollama healthy -> the lane drafts exactly as before.
  3. Innocence-2 (adapted -- see class docstring on `TestNoNonSensitiveClass`):
     this lane has NO non-sensitive payload shape, so instead of "a
     non-sensitive payload keeps its normal cascade" the proof is that no
     dormant cloud branch exists AT ALL to leak through, structurally (static
     class-guard) and behaviourally (choose_tier(False) raises rather than
     degrading anywhere).
  4. Mutation: manually verified by commenting out the `ollama_up()` gate in
     a scratch copy of this file and re-running the guilt test against it --
     it goes red (documented in the shipping PR body, not re-run here, since
     a permanent mutant would defeat the real gate).
"""

from __future__ import annotations

import json
import sys
import urllib.error
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "scripts" / "yield_optimizer_pitch_gate.py"

from scripts import yield_optimizer_pitch_gate as gate  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_gate_log(tmp_path, monkeypatch):
    """Never touch the real ~/logs/yield-optimizer-pii-gate.jsonl (W96 class)."""
    monkeypatch.setattr(gate, "GATE_LOG", tmp_path / "gate.jsonl")
    yield


def _log_lines() -> list[dict]:
    if not gate.GATE_LOG.exists():
        return []
    return [
        json.loads(line)
        for line in gate.GATE_LOG.read_text().splitlines()
        if line.strip()
    ]


# ---------------------------------------------------------------------------
# 1. Guilt -- Ollama unreachable
# ---------------------------------------------------------------------------


def test_ollama_down_produces_no_cloud_call_and_a_named_terminal_outcome(monkeypatch):
    monkeypatch.setattr(gate, "ollama_up", lambda timeout=3.0: False)

    called = {"n": 0}

    def _poison(*a, **k):
        called["n"] += 1
        raise AssertionError(
            "draft_pitch must never call the model when ollama_up() is False"
        )

    monkeypatch.setattr(gate, "_call_ollama", _poison)

    outcome, text = gate.draft_pitch("C_TEST_1", "irrelevant prompt")

    assert outcome == gate.SKIPPED_OLLAMA_FAIL
    assert text is None
    assert called["n"] == 0

    lines = _log_lines()
    assert len(lines) == 1
    assert lines[0]["client_id"] == "C_TEST_1"
    assert lines[0]["outcome"] == gate.SKIPPED_OLLAMA_FAIL
    assert lines[0]["detail"] == "ollama_unreachable"


def test_ollama_reachable_but_generate_call_fails_is_also_terminal_not_a_retry(
    monkeypatch,
):
    """Guilt, second failure branch: ollama_up() says True (tags endpoint
    answers) but the actual generate call blows up (timeout / connection
    reset mid-request). Must still be terminal, never a cloud fallback."""
    monkeypatch.setattr(gate, "ollama_up", lambda timeout=3.0: True)

    def _boom(prompt, timeout=180.0):
        raise urllib.error.URLError("connection reset")

    monkeypatch.setattr(gate, "_call_ollama", _boom)

    outcome, text = gate.draft_pitch("C_TEST_2", "prompt")

    assert outcome == gate.SKIPPED_OLLAMA_FAIL
    assert text is None
    assert _log_lines()[0]["detail"] == "URLError"


def test_empty_ollama_response_is_terminal_not_a_blank_pitch(monkeypatch):
    monkeypatch.setattr(gate, "ollama_up", lambda timeout=3.0: True)
    monkeypatch.setattr(gate, "_call_ollama", lambda prompt, timeout=180.0: "")

    outcome, text = gate.draft_pitch("C_TEST_3", "prompt")

    assert outcome == gate.SKIPPED_OLLAMA_FAIL
    assert text is None


# ---------------------------------------------------------------------------
# 2. Innocence -- Ollama healthy, unchanged behaviour
# ---------------------------------------------------------------------------


def test_ollama_healthy_drafts_exactly_as_before(monkeypatch):
    monkeypatch.setattr(gate, "ollama_up", lambda timeout=3.0: True)
    seen_prompts = []

    def _fake_call(prompt, timeout=180.0):
        seen_prompts.append(prompt)
        return "Pak Budi, KITAS bapak akan expire 23 hari lagi. Boleh kita jadwalkan call minggu ini?"

    monkeypatch.setattr(gate, "_call_ollama", _fake_call)

    prompt = gate.build_prompt(
        name="Budi",
        language="Indonesian (Bahasa Indonesia)",
        fact="Their KITAS expires in 23 days (2026-09-12).",
        pitch_goal="renewal + KITAP eligibility check",
    )
    outcome, text = gate.draft_pitch("C_TEST_4", prompt)

    assert outcome == gate.OLLAMA_LOCAL
    assert text and "expire" in text
    assert seen_prompts == [prompt]

    lines = _log_lines()
    assert len(lines) == 1
    assert lines[0]["outcome"] == gate.OLLAMA_LOCAL
    assert lines[0]["client_id"] == "C_TEST_4"


def test_cli_end_to_end_ollama_healthy(monkeypatch, capsys):
    monkeypatch.setattr(gate, "ollama_up", lambda timeout=3.0: True)
    monkeypatch.setattr(
        gate,
        "_call_ollama",
        lambda prompt, timeout=180.0: "Hi there, quick call this week?",
    )

    payload = {
        "client_id": "C_TEST_5",
        "name": "Ari",
        "language": "English",
        "fact": "Their passport expires in 90 days.",
        "pitch_goal": "early passport renewal",
    }
    monkeypatch.setattr(sys, "stdin", _StdinStub(json.dumps(payload)))

    exit_code = gate.main()
    out = capsys.readouterr().out

    assert exit_code == 0
    assert out.strip() == "Hi there, quick call this week?"


def test_cli_end_to_end_ollama_down_exits_2_prints_nothing_on_stdout(
    monkeypatch, capsys
):
    monkeypatch.setattr(gate, "ollama_up", lambda timeout=3.0: False)

    payload = {"client_id": "C_TEST_6", "name": "Ari"}
    monkeypatch.setattr(sys, "stdin", _StdinStub(json.dumps(payload)))

    exit_code = gate.main()
    captured = capsys.readouterr()

    assert exit_code == 2
    assert (
        captured.out == ""
    )  # nothing on stdout -- caller cannot mistake this for a draft
    assert "SKIPPED_OLLAMA_FAIL" in captured.err


class _StdinStub:
    def __init__(self, text: str) -> None:
        self._text = text

    def read(self) -> str:
        return self._text


# ---------------------------------------------------------------------------
# 3. No non-sensitive payload class exists in this lane -- structural +
#    behavioural proof there is no dormant cloud branch to leak through.
# ---------------------------------------------------------------------------


class TestNoNonSensitiveClass:
    """This lane processes ONLY CRM client records; unlike
    mos-plus-compression-worker.py (which legitimately has a cloud tier for
    non-sensitive traffic), there is no non-sensitive payload shape here to
    exercise a 'normal cascade' against. The equivalent proof for a
    mono-purpose lane is: (a) the boolean is live code, not a tautology --
    both branches are reachable and behave differently -- and (b) there is no
    cloud call anywhere in the file for a future 'handle sensitive=False'
    edit to quietly wake up.
    """

    def test_choose_tier_sensitive_true_returns_ollama_local(self):
        assert gate.choose_tier(True) == gate.OLLAMA_LOCAL

    def test_choose_tier_sensitive_false_raises_rather_than_degrading(self):
        with pytest.raises(ValueError, match="no non-sensitive payload class"):
            gate.choose_tier(False)

    def test_draft_pitch_refuses_a_non_sensitive_call_before_touching_ollama(
        self, monkeypatch
    ):
        """Guilt for the caller-bug shape: a hypothetical future call site
        that passes sensitive=False must never reach ollama_up()/the network
        -- it must raise first."""
        monkeypatch.setattr(
            gate,
            "ollama_up",
            lambda timeout=3.0: (_ for _ in ()).throw(
                AssertionError("ollama_up must not be reached when sensitive=False")
            ),
        )

        with pytest.raises(ValueError):
            gate.draft_pitch("C_TEST_7", "prompt", sensitive=False)


def test_no_cloud_references_in_file():
    """Static class-guard (cicatrix-superscar.md #2/#3 antidote pattern): the
    gate's EXECUTABLE source must never mention a cloud LLM CLI/SDK/host. If a
    future edit adds a fallback to claude/agy/kimi/codex/anthropic/openai/
    gemini or any non-localhost URL, this test goes red BEFORE the edit ships
    -- an unenforceable prose rule needs a code backstop (CLAUDE.md §7).

    Scanned on CODE only, not the module docstring: the docstring legitimately
    NAMES those providers to explain their absence (over-match on prose would
    be the exact guard-over-match bug this repo has scarred on repeatedly --
    cicatrix-superscar.md #3). Guilt for that framing is
    `test_over_matching_the_docstring_would_be_wrong` below.
    """
    hits = _forbidden_hits_outside_docstring(SRC.read_text())
    assert not hits, f"forbidden cloud references found in {SRC.name} CODE: {hits}"

    # Every literal http(s):// URL anywhere in the file (docstring examples
    # included -- a usage example pointed at a cloud host would still be a
    # real defect) must target localhost/127.0.0.1.
    import re

    urls = re.findall(r"https?://[^\s\"'{}]+", SRC.read_text())
    non_local = [u for u in urls if "localhost" not in u and "127.0.0.1" not in u]
    assert not non_local, f"non-localhost URL literal found: {non_local}"


def _strip_module_docstring(source: str) -> str:
    """Remove the leading module docstring using `ast` (never a hand-rolled
    quote scanner -- that class of bug is its own cicatrix, W99: "check != action",
    a strip that silently fails to strip is worse than no strip at all).
    Uses the exact literal `ast.get_docstring(..., clean=False)` text so the
    single `.replace()` below cannot partially match."""
    import ast

    tree = ast.parse(source)
    doc = ast.get_docstring(tree, clean=False)
    if doc is None:
        return source
    module_body = tree.body
    if not module_body or not isinstance(module_body[0], ast.Expr):
        return source
    doc_node = module_body[0]
    lines = source.splitlines(keepends=True)
    # doc_node.lineno/end_lineno are 1-indexed and inclusive.
    before = lines[: doc_node.lineno - 1]
    after = lines[doc_node.end_lineno :]
    blank = ["\n"] * (doc_node.end_lineno - doc_node.lineno + 1)
    return "".join(before) + "".join(blank) + "".join(after)


_FORBIDDEN_TOKENS = [
    "claude ",
    "claude-cascade",
    '"claude"',
    "'claude'",
    "anthropic",
    "openai",
    "chatgpt",
    "codex exec",
    '"codex"',
    " agy ",
    'agy"',
    "kimi-code",
    "kimi ",
    "gemini",
    "moonshot",
]


def _forbidden_hits_outside_docstring(source: str) -> list[str]:
    code_only = _strip_module_docstring(source).lower()
    return [token for token in _FORBIDDEN_TOKENS if token in code_only]


def test_over_matching_the_docstring_would_be_wrong():
    """Innocence for the class-guard above: the real module docstring (which
    legitimately names claude/anthropic/openai/agy/kimi/codex/gemini to
    explain their absence) must NOT trip the guard once the docstring is
    stripped -- proving the strip actually removes the prose, not just
    shifting where the false positive lands."""
    source = SRC.read_text()
    assert "anthropic" in source.lower(), (
        "fixture assumption broke: docstring no longer names it"
    )
    assert not _forbidden_hits_outside_docstring(source)


def test_docstring_stripper_still_catches_a_real_cloud_call():
    """Guilt for the stripper itself: a forbidden token placed AFTER the
    docstring (i.e. in real code) must still be caught."""
    mutated = (
        SRC.read_text() + '\nimport subprocess\nsubprocess.run(["claude", "-p", "x"])\n'
    )
    assert _forbidden_hits_outside_docstring(mutated)


# ---------------------------------------------------------------------------
# Privacy: only client_id ever reaches the log, never name/contact/facts.
# ---------------------------------------------------------------------------


def test_log_never_contains_name_or_facts(monkeypatch):
    monkeypatch.setattr(gate, "ollama_up", lambda timeout=3.0: True)
    monkeypatch.setattr(
        gate, "_call_ollama", lambda prompt, timeout=180.0: "some drafted pitch text"
    )

    prompt = gate.build_prompt(
        name="Siti Rahayu",
        language="Indonesian (Bahasa Indonesia)",
        fact="Their KITAS expires in 5 days -- URGENT, passport AB1234567.",
        pitch_goal="renewal",
    )
    gate.draft_pitch("C_TEST_8", prompt)

    raw_log_text = gate.GATE_LOG.read_text()
    assert "Siti Rahayu" not in raw_log_text
    assert "AB1234567" not in raw_log_text
    assert "C_TEST_8" in raw_log_text
