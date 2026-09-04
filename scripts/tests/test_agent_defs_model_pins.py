#!/usr/bin/env python3
"""test_agent_defs_model_pins.py — E1/R1: seven grunt agent definitions pinned
to Haiku 4.5 in `.claude/agents/`, and proof that model_routing_gate.py's Rule
1 (frontmatter-pin honoring) actually recognizes each one as pinned.

Context (2026-08-27, spec §8 R1 in 2026-08-26-PIANO-SPEC-receptor-live.md):
measured the same day — 13 agent defs under `.claude/agents/` carried a
`model:` pin (4 opus, 9 sonnet, 0 haiku), and Haiku received 8 of 882
dispatches (0.9%) over the prior 48h. MODEL_ROSTER.md already names Haiku the
grunt tier (format/extract/classify/cheap VLM pre-pass); nothing routed there
because nothing was PINNED there. `model_routing_gate.py` Rule 1 ALLOWs an
Agent() call with no explicit `model` param IF the subagent_type's definition
file pins `model:` in its own frontmatter — so pinning these 7 defs is what
actually lets a conductor dispatch `Agent({subagent_type: "lint-fixer", ...})`
(no `model` kwarg needed) and land on Haiku instead of silently inheriting
the orchestrator's own model.

Round-2 fix (cross-family refuter, Kimi K3, same day): the first version of
this file's "guilt" tests re-asserted the same regex the innocence test used,
directly against a synthetic bad fixture — that proves the REGEX behaves,
not that the actual check would go red. Every property the 7 real defs must
satisfy is now a shared helper (`_assert_*`); the innocence tests call it
directly over the real files, and the guilt tests call the SAME helper via
`pytest.raises(AssertionError)` against synthetic bad fixtures — so a future
edit that quietly weakens the innocence check also breaks its guilt twin,
instead of the two silently diverging (cicatrix-superscar.md #3 antidote).

Same round: the two `model_routing_gate` integration tests used to `return`
silently when the hook module/function was missing — an
`agent_def_pins_model` signature drift would make the test vanish quietly,
exactly the esiste≠armato shape `log-triage` exists to catch. They now
`pytest.skip(reason=...)` instead, so the gap shows up in test output rather
than reading as an unqualified pass. The `if __name__ == "__main__":
sys.exit(0)` block was deleted outright — it was a self-inflicted instance
of the same defect (always exits 0, having run nothing); pytest collection
is this file's one real invocation path, same convention as its sibling
`test_prepush_classify.py`.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"
GATE_MODULE_PATH = REPO_ROOT / "infra" / "claude-hooks" / "model_routing_gate.py"

GRUNT_AGENTS = [
    "ledger-writer",
    "lint-fixer",
    "i18n-sync",
    "fixture-gen",
    "log-triage",
    "catalog-meta",
    "docs-sync",
]

MODEL_PIN_HAIKU_RE = re.compile(r"^model[ \t]*:[ \t]*haiku[ \t]*$", re.MULTILINE)
ANY_MODEL_PIN_RE = re.compile(r"^model[ \t]*:[ \t]*\S", re.MULTILINE)
DESCRIPTION_GRUNT_RE = re.compile(r"^description[ \t]*:[ \t]*GRUNT \(Haiku\):", re.MULTILINE)
TOOLS_LINE_RE = re.compile(r"^tools[ \t]*:[ \t]*(.+)$", re.MULTILINE)

MAX_GRUNT_TOOLS = 4
# A grunt lane must not spawn its own subagents — that would be an
# orchestrator capability smuggled into a def whose whole point is a narrow,
# mechanical, non-recursive toolset.
FORBIDDEN_GRUNT_TOOLS = {"Agent", "Task"}


def _frontmatter(text: str) -> str:
    stripped = text.lstrip()
    assert stripped.startswith("---"), "agent def must open with a --- frontmatter delimiter"
    parts = text.split("---", 2)
    assert len(parts) >= 3, "agent def must have a closing --- frontmatter delimiter"
    return parts[1]


def _assert_pinned_to_haiku_with_grunt_description(fm: str, label: str) -> None:
    assert MODEL_PIN_HAIKU_RE.search(fm), (
        f"{label} frontmatter does not pin `model: haiku` — got:\n{fm}"
    )
    assert DESCRIPTION_GRUNT_RE.search(fm), (
        f"{label} description must start with 'GRUNT (Haiku):' — got:\n{fm}"
    )


def _assert_minimal_non_overlapping_toolset(fm: str, label: str) -> None:
    """The actual safety property the spec asked for: MINIMAL tools. A def
    with no `tools:` line would inherit the harness default (every tool) —
    exactly what a cheap/fast grunt model must not have. A def that carries
    both Bash and Edit/Write can route around its own declared mutation
    surface via shell redirection, defeating the point of a narrow toolset.
    A def that carries Agent/Task can spawn its own subagents, defeating the
    point of a bounded grunt lane."""
    m = TOOLS_LINE_RE.search(fm)
    assert m, f"{label} has no `tools:` line"
    tool_names = [t.strip() for t in m.group(1).split(",") if t.strip()]
    assert tool_names, f"{label} `tools:` line is empty"
    assert len(tool_names) <= MAX_GRUNT_TOOLS, (
        f"{label} lists {len(tool_names)} tools ({tool_names}) — expected a MINIMAL "
        f"grunt toolset (<={MAX_GRUNT_TOOLS}), not a broad allowlist"
    )
    forbidden_present = FORBIDDEN_GRUNT_TOOLS & set(tool_names)
    assert not forbidden_present, (
        f"{label} lists {sorted(forbidden_present)} — a grunt lane must not spawn its own subagents"
    )
    if "Bash" in tool_names:
        assert "Edit" not in tool_names and "Write" not in tool_names, (
            f"{label} combines Bash with Edit/Write — a grunt def should mutate "
            "files through ONE route, not two"
        )


# ---------------------------------------------------------------------------
# Innocence: the 7 real defs exist and pass every check above.
# ---------------------------------------------------------------------------


def test_seven_grunt_agent_defs_exist_pinned_to_haiku_with_grunt_description():
    assert AGENTS_DIR.is_dir(), f"{AGENTS_DIR} missing"
    for name in GRUNT_AGENTS:
        path = AGENTS_DIR / f"{name}.md"
        assert path.is_file(), f"missing grunt agent def: {path}"
        fm = _frontmatter(path.read_text(encoding="utf-8"))
        _assert_pinned_to_haiku_with_grunt_description(fm, str(path))


def test_seven_grunt_agent_defs_declare_a_minimal_non_overlapping_toolset():
    for name in GRUNT_AGENTS:
        path = AGENTS_DIR / f"{name}.md"
        fm = _frontmatter(path.read_text(encoding="utf-8"))
        _assert_minimal_non_overlapping_toolset(fm, str(path))


# ---------------------------------------------------------------------------
# Guilt: the SAME helpers, run against synthetic bad fixtures, must raise —
# not a re-implementation of the same regex checked a second way.
# ---------------------------------------------------------------------------


def test_guilt_a_def_missing_model_pin_fails_the_same_check(tmp_path):
    bad = tmp_path / "no-pin.md"
    bad.write_text(
        "---\nname: no-pin\ndescription: GRUNT (Haiku): a def with no model pin\ntools: Read\n---\n\n# no-pin\n",
        encoding="utf-8",
    )
    fm = _frontmatter(bad.read_text(encoding="utf-8"))
    with pytest.raises(AssertionError):
        _assert_pinned_to_haiku_with_grunt_description(fm, str(bad))


def test_guilt_a_def_pinned_to_the_wrong_model_fails_the_same_check(tmp_path):
    bad = tmp_path / "wrong-pin.md"
    bad.write_text(
        "---\nname: wrong-pin\ndescription: GRUNT (Haiku): says grunt, pins sonnet\ntools: Read\nmodel: sonnet\n---\n\n# wrong-pin\n",
        encoding="utf-8",
    )
    fm = _frontmatter(bad.read_text(encoding="utf-8"))
    assert ANY_MODEL_PIN_RE.search(fm)  # it IS pinned to something...
    with pytest.raises(AssertionError):
        _assert_pinned_to_haiku_with_grunt_description(fm, str(bad))  # ...just not haiku


def test_guilt_a_def_with_seven_tools_fails_the_same_check(tmp_path):
    bad = tmp_path / "seven-tools.md"
    bad.write_text(
        "---\nname: seven-tools\ndescription: GRUNT (Haiku): too many tools\n"
        "tools: Read, Write, Edit, Bash, Grep, Glob, WebFetch\nmodel: haiku\n---\n\n# seven-tools\n",
        encoding="utf-8",
    )
    fm = _frontmatter(bad.read_text(encoding="utf-8"))
    with pytest.raises(AssertionError):
        _assert_minimal_non_overlapping_toolset(fm, str(bad))


def test_guilt_a_def_that_can_spawn_subagents_fails_the_same_check(tmp_path):
    bad = tmp_path / "spawns-agents.md"
    bad.write_text(
        "---\nname: spawns-agents\ndescription: GRUNT (Haiku): a grunt that spawns subagents\n"
        "tools: Read, Agent\nmodel: haiku\n---\n\n# spawns-agents\n",
        encoding="utf-8",
    )
    fm = _frontmatter(bad.read_text(encoding="utf-8"))
    with pytest.raises(AssertionError):
        _assert_minimal_non_overlapping_toolset(fm, str(bad))


def test_guilt_a_def_mixing_bash_and_write_fails_the_same_check(tmp_path):
    bad = tmp_path / "bash-and-write.md"
    bad.write_text(
        "---\nname: bash-and-write\ndescription: GRUNT (Haiku): mixes bash and write\n"
        "tools: Bash, Write\nmodel: haiku\n---\n\n# bash-and-write\n",
        encoding="utf-8",
    )
    fm = _frontmatter(bad.read_text(encoding="utf-8"))
    with pytest.raises(AssertionError):
        _assert_minimal_non_overlapping_toolset(fm, str(bad))


# ---------------------------------------------------------------------------
# model_routing_gate.py Rule 1 must actually recognize the pin (the real
# hook function, not a re-implementation of its regex in this test file).
# ---------------------------------------------------------------------------


def _load_gate_module():
    if not GATE_MODULE_PATH.is_file():
        return None
    spec = importlib.util.spec_from_file_location("model_routing_gate_e1r1", GATE_MODULE_PATH)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_model_routing_gate_honors_the_pin_for_all_seven_defs():
    gate = _load_gate_module()
    if gate is None:
        pytest.skip(f"{GATE_MODULE_PATH} not found in this checkout — cannot verify Rule 1 live")
    if not hasattr(gate, "agent_def_pins_model"):
        pytest.skip(
            "model_routing_gate.py no longer exposes agent_def_pins_model(subagent_type, cwd) — "
            "its Rule 1 API has drifted from what this test calls; re-sync before trusting this gap"
        )
    for name in GRUNT_AGENTS:
        allowed = gate.agent_def_pins_model(name, str(REPO_ROOT))
        assert allowed is True, (
            f"model_routing_gate does not recognize {name} as pinned (Rule 1 would DENY "
            "an Agent() dispatch with no explicit model param)"
        )


def test_guilt_gate_denies_a_subagent_type_with_no_def_on_disk():
    gate = _load_gate_module()
    if gate is None:
        pytest.skip(f"{GATE_MODULE_PATH} not found in this checkout — cannot verify Rule 1 live")
    if not hasattr(gate, "agent_def_pins_model"):
        pytest.skip("model_routing_gate.py no longer exposes agent_def_pins_model(subagent_type, cwd)")
    assert gate.agent_def_pins_model("definitely-not-a-real-grunt-agent-xyz", str(REPO_ROOT)) is False


# ---------------------------------------------------------------------------
# Fleet-wide floor (2026-09-04): the checks above cover the 7 grunt defs only.
# Everything else under `.claude/agents/` was unguarded — no workflow ran this
# file at all until the same PR wired it into immune-enforcement.yml, and no
# test looked at the other 13 defs' frontmatter.
#
# The floor asserts SHAPE, never a current value: `maxTurns`, `disallowedTools`
# and `memory` are deliberately NOT required here, because only 11/6/9 of the
# 20 defs carry them today and a guard pinned to the state it should be judging
# forbids the very normalization it exists to protect. What IS required is the
# set every def already satisfies, so this lands green and only a REGRESSION
# turns it red:
#
#   - `model:` — a def with no pin silently inherits the orchestrator's model,
#     which is precisely what model_routing_gate.py Rule 1 exists to prevent.
#   - `tools:` — a def with no tools line inherits the harness default (all of
#     them), the broadest possible surface arriving by omission.
#   - `description:` — the dispatcher matches a mandate against it, so a def
#     without one is invisible to routing rather than merely untidy.
#   - `name:` matching the filename — the dispatcher resolves a def by
#     filename, so a mismatched `name:` yields a def that loads under an
#     identifier nobody dispatches. This is the specific error a bulk promotion
#     of HOME agent files into this directory would introduce.
#
# "Carries a value" is the load-bearing phrase and it took three adversarial
# rounds to get right. A key satisfying `\S` is NOT a value: `model: ~`,
# `model: null` and `model: ""` are YAML's ways of writing nothing; `tools: #
# none` declares a key and supplies a comment; an empty `tools:` followed by
# `model: sonnet` used to BORROW the next line through a `\s*` that crossed the
# newline (W119). And a key declared TWICE is refused outright rather than
# resolved, because a line scanner takes the first while a YAML parser takes
# the last — so `name: on-disk-name` … `name: something-else` would pass a
# filename check and load as the other identifier.
# ---------------------------------------------------------------------------


def _agent_def_paths() -> list[Path]:
    # NON-RECURSIVE ON PURPOSE, and the sentinel in immune-enforcement.yml
    # deliberately is not: a shell `case` glob matches across `/`, so an edit
    # anywhere under `.claude/agents/` triggers the battery (broad is the safe
    # direction for a trigger). Recursing HERE would be the wrong half of the
    # symmetry — `.claude/agents/wr2-design-architect-resources/` holds 4 `.md`
    # RESOURCE files that are not agent definitions and would redden at once.
    return sorted(p for p in AGENTS_DIR.glob("*.md") if p.name != "README.md")


#: The floor below reads every key through ONE reader (`_scalar`) rather than a
#: per-key regex. Three per-key patterns lived here during the adversarial
#: rounds and were deleted once `_scalar` subsumed them: an unused module-level
#: regex reads to the next maintainer as a contract, which is the same defect
#: as an assert that cannot fail.
#:
#: All the frontmatter regexes in this file spell their inter-token gap `[ \t]*`
#: and
#: NOT `\s*`. Measured 2026-09-04 before narrowing them, on the pre-existing
#: `^tools\s*:\s*(.+)$`: given
#:
#:     tools:
#:     model: sonnet
#:
#: `\s*` consumed the NEWLINE and `(.+)` then matched the following line, so
#: `TOOLS_LINE_RE` reported a tools value of 'model: sonnet' for a def whose
#: `tools:` key is empty. Cicatrix W119 (`\s` attraversa il newline), family #3.
#:
#: NOTE ON THE PARSER THIS FILE DELIBERATELY DOES *NOT* USE. The obvious cure
#: for the same class is "stop regexing and parse the frontmatter as YAML".
#: Measured, and it is WRONG here: 7 of the 20 defs on disk — every one of the
#: grunt defs — are NOT valid YAML, because their description carries a second
#: unquoted colon (`description: GRUNT (Haiku): reads a bounded ...`), which
#: `yaml.safe_load` rejects with a ScannerError. Those 7 defs are nonetheless
#: LOADED AND DISPATCHABLE by the harness, with their descriptions rendered
#: intact — so the real consumer is line-based, not a strict YAML parser, and a
#: guard that demanded YAML-parseability would be STRICTER THAN THE CONSUMER
#: and would redden 7 working files. The corpus-level question (should those
#: descriptions be quoted anyway?) is real and belongs to the PR that edits agent
#: defs; it is not this guard's to force.
#: A value consisting only of a comment (`tools: # none`) is rejected below for
#: the same reason it is rejected by eye: it declares a key and supplies nothing.
COMMENT_ONLY_VALUE_RE = re.compile(r"^#")

#: Spellings that LOOK like a value and carry none. `~`, `null` and the empty
#: quoted scalars are YAML's own ways of writing nothing; a bare `""` pin is
#: the same surface as no pin at all. All of them satisfy `\S`, which is why
#: the presence regexes alone could not reject them.
NULLISH_VALUES = frozenset({"~", "null", "Null", "NULL", "~ ", '""', "''"})

#: A trailing ` # comment` is legal after a short YAML scalar. Stripping it is
#: the OVER-MATCH cure (a `name: my-agent # dispatcher name` must not be read as
#: the six-word string), and it is applied ONLY to the short routing scalars —
#: never to `description`, whose prose may legitimately contain a `#`.
TRAILING_COMMENT_RE = re.compile(r"[ \t]+#.*$")

#: Every key is read with `findall`, never `search`, because a regex reading the
#: FIRST occurrence and a loader reading the LAST is a silent disagreement about
#: what the def IS: `name: on-disk-name` … `name: something-else` would pass a
#: filename check and then load under the other identifier. A duplicated key is
#: therefore refused outright rather than resolved in either direction — this
#: guard has no standing to decide which one the harness meant.
def _value_re(key: str) -> re.Pattern[str]:
    return re.compile(rf"^{key}[ \t]*:[ \t]*(.*?)[ \t]*$", re.MULTILINE)


def _scalar(fm: str, key: str, label: str, *, strip_comment: bool) -> str | None:
    """The one declared value of `key`, normalized; None when the key is absent
    or carries nothing. Raises AssertionError when the key is declared twice."""
    found = _value_re(key).findall(fm)
    assert len(found) <= 1, (
        f"{label} declares `{key}:` {len(found)} times ({found!r}) — a line-scanning reader "
        "takes the FIRST and a YAML parser takes the LAST, so the two disagree about what this "
        "def is; a duplicated key is refused rather than resolved"
    )
    if not found:
        return None
    value = found[0].strip()
    if strip_comment:
        value = TRAILING_COMMENT_RE.sub("", value).strip()
    if COMMENT_ONLY_VALUE_RE.match(value):
        return None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1].strip()
    if value in NULLISH_VALUES or not value:
        return None
    return value


def _assert_agent_def_floor(fm: str, stem: str, label: str) -> None:
    # `description` keeps its own reader: its prose may contain a `#` and is
    # not a routing scalar, so only presence and comment-only are checked.
    assert _scalar(fm, "description", label, strip_comment=False), (
        f"{label} has no `description:` value — the dispatcher matches a mandate against the "
        "description, so a def without one is invisible to routing"
    )
    assert _scalar(fm, "tools", label, strip_comment=True), (
        f"{label} has no `tools:` value — it would inherit the harness default (every tool), "
        "the broadest possible surface arriving by omission"
    )
    assert _scalar(fm, "model", label, strip_comment=True), (
        f"{label} has no `model:` pin — it would silently inherit the dispatching "
        "orchestrator's model instead of its own tier"
    )
    declared = _scalar(fm, "name", label, strip_comment=True)
    # This single assert also covers "no `name:` line at all" (declared is
    # None). A separate presence assert used to sit above it and was measured
    # DEAD by mutation — deleting it reddened nothing, because this one fires
    # first on a nameless def. One assert that a guilt test can actually
    # discriminate beats two where one is decorative.
    assert declared == stem, (
        f"{label} declares name={declared!r} but its filename says {stem!r} — the dispatcher "
        "resolves by FILENAME, so this def would load under an identifier nothing dispatches "
        "(a missing or empty `name:` reads as None here)"
    )


def test_every_agent_def_meets_the_floor():
    paths = _agent_def_paths()
    assert paths, f"{AGENTS_DIR} contains no agent defs — the glob or the directory moved"
    for path in paths:
        fm = _frontmatter(path.read_text(encoding="utf-8"))
        _assert_agent_def_floor(fm, path.stem, str(path))


def test_guilt_a_def_with_no_model_pin_fails_the_floor(tmp_path):
    bad = tmp_path / "unpinned.md"
    bad.write_text(
        "---\nname: unpinned\ndescription: no model pin\ntools: Read\n---\n\n# unpinned\n",
        encoding="utf-8",
    )
    with pytest.raises(AssertionError):
        _assert_agent_def_floor(_frontmatter(bad.read_text(encoding="utf-8")), bad.stem, str(bad))


def test_guilt_a_def_with_no_tools_line_fails_the_floor(tmp_path):
    bad = tmp_path / "toolless.md"
    bad.write_text(
        "---\nname: toolless\ndescription: inherits every tool\nmodel: sonnet\n---\n\n# toolless\n",
        encoding="utf-8",
    )
    with pytest.raises(AssertionError):
        _assert_agent_def_floor(_frontmatter(bad.read_text(encoding="utf-8")), bad.stem, str(bad))


def test_guilt_a_def_whose_name_does_not_match_its_filename_fails_the_floor(tmp_path):
    bad = tmp_path / "on-disk-name.md"
    bad.write_text(
        "---\nname: some-other-name\ndescription: promoted with a stale name\ntools: Read\nmodel: sonnet\n---\n\n# x\n",
        encoding="utf-8",
    )
    with pytest.raises(AssertionError):
        _assert_agent_def_floor(_frontmatter(bad.read_text(encoding="utf-8")), bad.stem, str(bad))


def test_guilt_a_def_with_no_name_line_at_all_fails_the_floor(tmp_path):
    bad = tmp_path / "nameless.md"
    bad.write_text(
        "---\ndescription: no name line\ntools: Read\nmodel: sonnet\n---\n\n# nameless\n",
        encoding="utf-8",
    )
    with pytest.raises(AssertionError):
        _assert_agent_def_floor(_frontmatter(bad.read_text(encoding="utf-8")), bad.stem, str(bad))


def test_guilt_a_def_with_no_description_fails_the_floor(tmp_path):
    # Without this the `description:` assert is unreachable by any test: every
    # real def carries one, so mutating it away reddened nothing (measured
    # 2026-09-04). The description is what the dispatcher matches a mandate
    # against — a def with none is invisible to routing, not merely untidy.
    bad = tmp_path / "mute.md"
    bad.write_text(
        "---\nname: mute\ntools: Read\nmodel: sonnet\n---\n\n# mute\n",
        encoding="utf-8",
    )
    with pytest.raises(AssertionError):
        _assert_agent_def_floor(_frontmatter(bad.read_text(encoding="utf-8")), bad.stem, str(bad))


def test_guilt_an_empty_tools_key_does_not_borrow_the_next_line_as_its_value(tmp_path):
    # W119, measured on the pre-existing `^tools\s*:\s*(.+)$`: `\s*` crossed the
    # newline, so this def reported a tools value of 'model: sonnet' and passed.
    # Reverting the regex to `\s*` reddens exactly this test.
    bad = tmp_path / "borrowed.md"
    bad.write_text(
        "---\nname: borrowed\ndescription: empty tools key\ntools:\nmodel: sonnet\n---\n\n# x\n",
        encoding="utf-8",
    )
    with pytest.raises(AssertionError):
        _assert_agent_def_floor(_frontmatter(bad.read_text(encoding="utf-8")), bad.stem, str(bad))


def test_guilt_a_key_whose_value_is_only_a_comment_fails_the_floor(tmp_path):
    for key in ("tools", "model", "description"):
        lines = {"name": "commented", "description": "d", "tools": "Read", "model": "sonnet"}
        lines[key] = "# nothing here"
        body = "".join(f"{k}: {v}\n" for k, v in lines.items())
        bad = tmp_path / "commented.md"
        bad.write_text(f"---\n{body}---\n\n# x\n", encoding="utf-8")
        with pytest.raises(AssertionError):
            _assert_agent_def_floor(_frontmatter(bad.read_text(encoding="utf-8")), bad.stem, str(bad))


def test_guilt_a_nullish_routing_value_fails_the_floor(tmp_path):
    # `~`, `null` and empty quoted scalars all satisfy `\S`, so the presence
    # regexes alone accepted them while the def carries no pin and no toolset.
    for key in ("tools", "model", "name"):
        for spelling in ("~", "null", '""', "''"):
            lines = {"name": "nullish", "description": "d", "tools": "Read", "model": "sonnet"}
            lines[key] = spelling
            body = "".join(f"{k}: {v}\n" for k, v in lines.items())
            bad = tmp_path / "nullish.md"
            bad.write_text(f"---\n{body}---\n\n# x\n", encoding="utf-8")
            with pytest.raises(AssertionError):
                _assert_agent_def_floor(
                    _frontmatter(bad.read_text(encoding="utf-8")), bad.stem, str(bad)
                )


def test_guilt_a_duplicated_key_is_refused_rather_than_resolved(tmp_path):
    # A line scanner takes the first `name:`, a YAML parser takes the last. The
    # first matches the filename and the second does not, so whichever reader
    # the harness uses, one of them loads a def this floor said was fine.
    bad = tmp_path / "twofaced.md"
    bad.write_text(
        "---\nname: twofaced\ndescription: d\ntools: Read\nmodel: sonnet\nname: something-else\n"
        "---\n\n# x\n",
        encoding="utf-8",
    )
    with pytest.raises(AssertionError, match="declares `name:` 2 times"):
        _assert_agent_def_floor(_frontmatter(bad.read_text(encoding="utf-8")), bad.stem, str(bad))


def test_innocence_a_trailing_yaml_comment_on_a_routing_scalar_passes_the_floor(tmp_path):
    # The over-match twin of the quoted-name cure: ` # comment` after a short
    # scalar is legal YAML and must not become part of the value.
    ok = tmp_path / "annotated.md"
    ok.write_text(
        "---\nname: annotated # the dispatcher name\ndescription: prose may contain a # here\n"
        "tools: Read # read-only lane\nmodel: sonnet # implementer tier\n---\n\n# x\n",
        encoding="utf-8",
    )
    _assert_agent_def_floor(_frontmatter(ok.read_text(encoding="utf-8")), ok.stem, str(ok))


def test_innocence_a_quoted_name_matching_the_filename_passes_the_floor(tmp_path):
    # The over-match this cured: `name: "foo"` is legal YAML and names `foo`.
    # A bare `(\S+)` capture compared '"foo"' against 'foo' and rejected it.
    for spelling in ('name: "quoted"', "name: 'quoted'", "name: quoted   "):
        ok = tmp_path / "quoted.md"
        ok.write_text(
            f"---\n{spelling}\ndescription: legal yaml\ntools: Read\nmodel: sonnet\n---\n\n# quoted\n",
            encoding="utf-8",
        )
        _assert_agent_def_floor(_frontmatter(ok.read_text(encoding="utf-8")), ok.stem, str(ok))
