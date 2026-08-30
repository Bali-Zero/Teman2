"""Tests for scripts/lint_immune_contracts.py — the immune-contracts registry lint.

Module is imported via importlib.util.spec_from_file_location (not a package import)
because scripts/ is a flat bag of standalone tools, not a Python package.

The lint's own `--selftest` (see `_run_selftest` in the module) already exercises the
four checks (C1-C4) and four known_gaps scenarios end-to-end. This file does NOT
re-implement copies of those exact fixtures — it independently re-derives its own
guilt/innocence fixtures (different producer/consumer source, different registry
shapes) so a future regression can be caught by an ordinary `pytest` run even if
`_run_selftest` itself is ever weakened or deleted, and it covers the three
surfaces `--selftest` cannot reach on its own:

  * `main()`'s CLI exit codes (0/1/2/3), driven with a real argv list.
  * `_no_regrowth()` against a REAL throwaway git repository (not a mocked git).
  * A non-vacuity proof: at least three of the tests below are shown to actually
    go red against a deliberately-broken copy of the module (see the manual
    verification reported alongside this file, not embedded here — breaking the
    REAL module to prove a point would violate the instruction that only this
    test file may be touched).

REAL SIGNATURES USED BELOW (verified against the module on disk at test-authoring
time, not assumed from memory):

    main(argv: Optional[Sequence[str]] = None) -> int
    _lint_registry(registry_path, repo_root) -> (violations, unchecked, cannot_verify, gaps, anchored, total)
    _check_contract(contract, repo_root) -> (violations, gaps, unchecked, cannot_verify, anchored)   # NOT used directly here
    _no_regrowth(registry_path, registry_dict, base_ref) -> (violations, cannot_verify)

Two things worth flagging explicitly: `_check_contract`'s type hint (line ~235 of
the module) claims the order `(violations, unchecked, cannot_verify, gaps, bool)`,
but its actual `return (*_apply_gaps(...), unchecked, cannot_verify, anchored)`
unpacks (and is consumed by `_lint_registry`) as `(violations, gaps, unchecked,
cannot_verify, anchored)` — the hint is stale relative to behaviour. This file
never calls `_check_contract` directly (everything goes through `_lint_registry`,
per the brief), so the discrepancy does not affect any assertion here, but a
future reader relying on that type hint alone would be misled.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

MODULE_PATH = Path(__file__).resolve().parent.parent / "lint_immune_contracts.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("lint_immune_contracts", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


lic = _load_module()


# ---------------------------------------------------------------------------
# Synthetic contract/registry builders (independent of the module's own
# `_contract()` self-test helper, on purpose — see module docstring above).
# ---------------------------------------------------------------------------

def _producer(
    path: str = "producer.py",
    *,
    function: str | None = "build",
    kind: str = "python",
    emits: list[str] | None = None,
    nested: dict[str, list[str]] | None = None,
    enums: dict[str, list[str]] | None = None,
    unchecked_reason: str | None = None,
) -> dict:
    d: dict = {"path": path, "function": function, "kind": kind, "emits": list(emits or [])}
    if nested is not None:
        d["nested"] = nested
    if enums is not None:
        d["enums"] = enums
    if unchecked_reason is not None:
        d["unchecked_reason"] = unchecked_reason
    return d


def _consumer(
    path: str = "consumer.py",
    *,
    function: str | None = "consume",
    kind: str = "python",
    reads: list[str] | None = None,
    enum_literals: dict[str, list[str]] | None = None,
    unchecked_reason: str | None = None,
) -> dict:
    d: dict = {"path": path, "function": function, "kind": kind, "reads": list(reads or [])}
    if enum_literals is not None:
        d["enum_literals"] = enum_literals
    if unchecked_reason is not None:
        d["unchecked_reason"] = unchecked_reason
    return d


def _contract(cid: str, producer: dict, consumer: dict, *, known_gaps: list[dict] | None = None) -> dict:
    d: dict = {"id": cid, "producer": producer, "consumer": consumer}
    if known_gaps is not None:
        d["known_gaps"] = known_gaps
    return d


def _lint(root: Path, *contracts: dict):
    """Write a synthetic registry to disk and drive it through `_lint_registry`.

    Real unpack order (confirmed on the module currently on disk):
        violations, unchecked, cannot_verify, gaps, anchored, total
    """
    registry_path = root / "contracts.json"
    registry_path.write_text(json.dumps({"version": 1, "contracts": list(contracts)}), encoding="utf-8")
    return lic._lint_registry(registry_path, root)


def _cid(items, cid: str) -> list:
    return [x for x in items if x.cid == cid]


def _check(items, check: str) -> list:
    return [x for x in items if getattr(x, "check", None) == check]


def _gap(check: str, key: str, reason: str = "reason", ledger: str = "ledger-ref") -> dict:
    return {"check": check, "key": key, "reason": reason, "ledger": ledger}


# ---------------------------------------------------------------------------
# Section A — the four checks, guilt AND innocence each.
# ---------------------------------------------------------------------------

def test_c1_reports_the_w120_shape_drifted_read_key(tmp_path: Path) -> None:
    """C1 guilt: producer emits entries[].class, consumer reads entries[].classification (W120)."""
    (tmp_path / "producer.py").write_text(
        'def build():\n    return {"entries": [{"class": "TECH-DEBT", "overdue": True}]}\n'
    )
    (tmp_path / "consumer.py").write_text(
        'def consume(data):\n'
        '    for e in data.get("entries", []):\n'
        '        if e.get("classification") == "TECH-DEBT":\n'
        '            yield e\n'
    )
    contract = _contract(
        "c1_guilt",
        _producer(emits=["entries"], nested={"entries[]": ["class", "overdue"]}),
        _consumer(reads=["entries", "entries[].classification"]),
    )
    v, u, c, g, anchored, total = _lint(tmp_path, contract)
    c1 = _check(_cid(v, "c1_guilt"), "C1")
    assert len(c1) == 1
    assert any("classification" in x.key for x in c1)


def test_c1_matched_schema_is_clean(tmp_path: Path) -> None:
    """C1 innocence: consumer reads exactly what the producer declares -> zero violations."""
    (tmp_path / "producer.py").write_text(
        'def build():\n    return {"entries": [{"class": "TECH-DEBT"}]}\n'
    )
    (tmp_path / "consumer.py").write_text(
        'def consume(data):\n'
        '    for e in data.get("entries", []):\n'
        '        if e.get("class") == "TECH-DEBT":\n'
        '            yield e\n'
    )
    contract = _contract(
        "c1_innocent",
        _producer(emits=["entries"], nested={"entries[]": ["class"]}),
        _consumer(reads=["entries", "entries[].class"]),
    )
    v, u, c, g, anchored, total = _lint(tmp_path, contract)
    assert _cid(v, "c1_innocent") == []


def test_c2_reports_enum_literal_outside_producer_domain(tmp_path: Path) -> None:
    """C2 guilt: consumer compares against a literal the producer domain never declares."""
    (tmp_path / "producer.py").write_text(
        'def build():\n    return {"items": [{"status": "NORMAL"}]}\n'
    )
    (tmp_path / "consumer.py").write_text(
        'def consume(data):\n'
        '    for i in data.get("items", []):\n'
        '        if i.get("status") == "normal":\n'
        '            yield i\n'
    )
    contract = _contract(
        "c2_guilt",
        _producer(emits=["items"], nested={"items[]": ["status"]}, enums={"items[].status": ["NORMAL"]}),
        _consumer(reads=["items", "items[].status"], enum_literals={"items[].status": ["normal"]}),
    )
    v, u, c, g, anchored, total = _lint(tmp_path, contract)
    c2 = _check(_cid(v, "c2_guilt"), "C2")
    assert len(c2) == 1
    assert c2[0].key == "normal"


def test_c2_literal_inside_domain_is_clean(tmp_path: Path) -> None:
    """C2 innocence: the exact same shape, but the literal lives inside the domain."""
    (tmp_path / "producer.py").write_text(
        'def build():\n    return {"items": [{"status": "NORMAL"}]}\n'
    )
    (tmp_path / "consumer.py").write_text(
        'def consume(data):\n'
        '    for i in data.get("items", []):\n'
        '        if i.get("status") == "NORMAL":\n'
        '            yield i\n'
    )
    contract = _contract(
        "c2_innocent",
        _producer(emits=["items"], nested={"items[]": ["status"]}, enums={"items[].status": ["NORMAL"]}),
        _consumer(reads=["items", "items[].status"], enum_literals={"items[].status": ["NORMAL"]}),
    )
    v, u, c, g, anchored, total = _lint(tmp_path, contract)
    assert _cid(v, "c2_innocent") == []


def test_c2_missing_producer_domain_is_unchecked_not_a_silent_pass(tmp_path: Path) -> None:
    """C2 UNCHECKED: consumer declares enum_literals for a path the producer has NO
    domain for at all. Must read as zero violations PLUS a visible Unchecked entry
    — never as a silent pass indistinguishable from a real green check."""
    (tmp_path / "producer.py").write_text(
        'def build():\n    return {"items": [{"status": "NORMAL"}]}\n'
    )
    (tmp_path / "consumer.py").write_text(
        'def consume(data):\n'
        '    for i in data.get("items", []):\n'
        '        if i.get("status") == "NORMAL":\n'
        '            yield i\n'
    )
    contract = _contract(
        "c2_unchecked",
        _producer(emits=["items"], nested={"items[]": ["status"]}),  # no `enums` domain declared at all
        _consumer(reads=["items", "items[].status"], enum_literals={"items[].status": ["NORMAL"]}),
    )
    v, u, c, g, anchored, total = _lint(tmp_path, contract)
    assert _cid(v, "c2_unchecked") == []
    unchecked_for_cid = _cid(u, "c2_unchecked")
    assert len(unchecked_for_cid) == 1
    assert "items[].status" in unchecked_for_cid[0].reason
    assert "no matching producer enums domain" in unchecked_for_cid[0].reason


def test_c3_reports_omitted_registered_read_for_a_real_code_read(tmp_path: Path) -> None:
    """C3 guilt: the consumer's CODE reads a producer-declared key the registry
    `reads` never lists."""
    (tmp_path / "producer.py").write_text(
        'def build():\n    return {"items": [{"status": "NORMAL"}]}\n'
    )
    (tmp_path / "consumer.py").write_text(
        'def consume(data):\n'
        '    for i in data.get("items", []):\n'
        '        if i.get("status") == "OK":\n'
        '            yield i\n'
    )
    contract = _contract(
        "c3_guilt",
        _producer(emits=["items"], nested={"items[]": ["status"]}),
        _consumer(reads=["items"]),  # "status" is a real producer key, omitted here
    )
    v, u, c, g, anchored, total = _lint(tmp_path, contract)
    c3 = _check(_cid(v, "c3_guilt"), "C3")
    assert len(c3) == 1
    assert c3[0].key == "status"


def test_c3_ignores_an_ordinary_string_literal_that_is_not_a_producer_key(tmp_path: Path) -> None:
    """C3 innocence / over-match guard: a `.get("...")` call on something unrelated
    to the producer payload (here `os.environ.get`) must NOT be flagged — it is
    ordinary code, not a contract read, precisely because the string it reads is
    not a producer-declared key at all (superscar family #3 discipline)."""
    (tmp_path / "producer.py").write_text(
        'def build():\n    return {"items": [{"status": "NORMAL"}]}\n'
    )
    (tmp_path / "consumer.py").write_text(
        "import os\n\n\n"
        "def consume(data):\n"
        '    debug_flag = os.environ.get("SOME_ENV_VAR")\n'
        '    for i in data.get("items", []):\n'
        "        yield i\n"
    )
    contract = _contract(
        "c3_innocent",
        _producer(emits=["items"], nested={"items[]": ["status"]}),
        _consumer(reads=["items"]),
    )
    v, u, c, g, anchored, total = _lint(tmp_path, contract)
    assert _cid(v, "c3_innocent") == []


def test_c4_reports_declared_emit_producer_code_never_writes(tmp_path: Path) -> None:
    """C4 guilt: registry declares `emits` a key the producer function never
    actually constructs in a dict literal."""
    (tmp_path / "producer.py").write_text(
        'def build():\n    return {"counts": {}}\n'
    )
    (tmp_path / "consumer.py").write_text(
        'def consume(data):\n    return data.get("counts")\n'
    )
    contract = _contract(
        "c4_guilt",
        _producer(emits=["counts", "entries"]),  # "entries" is never written
        _consumer(reads=["counts"]),
    )
    v, u, c, g, anchored, total = _lint(tmp_path, contract)
    c4 = _check(_cid(v, "c4_guilt"), "C4")
    assert len(c4) == 1
    assert c4[0].key == "entries"


def test_c4_every_declared_emit_really_written_is_clean(tmp_path: Path) -> None:
    """C4 innocence: same schema, but the producer really writes both keys."""
    (tmp_path / "producer.py").write_text(
        'def build():\n    return {"counts": {}, "entries": []}\n'
    )
    (tmp_path / "consumer.py").write_text(
        'def consume(data):\n    return data.get("counts")\n'
    )
    contract = _contract(
        "c4_innocent",
        _producer(emits=["counts", "entries"]),
        _consumer(reads=["counts"]),
    )
    v, u, c, g, anchored, total = _lint(tmp_path, contract)
    assert _cid(v, "c4_innocent") == []


# ---------------------------------------------------------------------------
# Section B — UNCHECKED is never silence.
# ---------------------------------------------------------------------------

def test_unchecked_function_null_carries_the_custom_reason(tmp_path: Path) -> None:
    """`"function": null` + `unchecked_reason` -> one Unchecked entry carrying that
    EXACT reason text, and zero violations."""
    (tmp_path / "producer.py").write_text("# no named entry point; logic runs inline\n")
    (tmp_path / "consumer.py").write_text("def consume(data):\n    return None\n")
    reason = "producer logic runs at import time inside a class __init__, no named function to anchor"
    contract = _contract(
        "b_null_function",
        _producer(function=None, unchecked_reason=reason),
        _consumer(function="consume"),
    )
    v, u, c, g, anchored, total = _lint(tmp_path, contract)
    assert _cid(v, "b_null_function") == []
    unchecked_for_cid = _cid(u, "b_null_function")
    assert len(unchecked_for_cid) == 1
    assert unchecked_for_cid[0].reason == reason


def test_unchecked_shell_kind_carries_the_generated_reason(tmp_path: Path) -> None:
    """`kind: "shell"` -> one Unchecked entry naming the kind, and zero violations."""
    (tmp_path / "heartbeat.sh").write_text("#!/bin/bash\n# organism_heartbeat inline logic\n")
    (tmp_path / "consumer.py").write_text("def consume(data):\n    return None\n")
    contract = _contract(
        "b_shell_kind",
        _producer(path="heartbeat.sh", function="organism_heartbeat", kind="shell"),
        _consumer(function="consume"),
    )
    v, u, c, g, anchored, total = _lint(tmp_path, contract)
    assert _cid(v, "b_shell_kind") == []
    unchecked_for_cid = _cid(u, "b_shell_kind")
    assert len(unchecked_for_cid) == 1
    assert "kind='shell'" in unchecked_for_cid[0].reason
    assert "not AST-anchored" in unchecked_for_cid[0].reason


# ---------------------------------------------------------------------------
# Section C — known_gaps.
# ---------------------------------------------------------------------------

def test_known_gap_matching_a_real_violation_downgrades_it(tmp_path: Path) -> None:
    """A declared, well-formed gap matching a real violation: zero violations, one
    KnownGap, and the gap's reason+ledger are visible in its .line()."""
    (tmp_path / "producer.py").write_text(
        'def build():\n    return {"items": [{"status": "NORMAL"}]}\n'
    )
    (tmp_path / "consumer.py").write_text(
        'def consume(data):\n'
        '    for i in data.get("items", []):\n'
        '        if i.get("status") == "normal":\n'
        '            yield i\n'
    )
    contract = _contract(
        "c_gap_downgrade",
        _producer(emits=["items"], nested={"items[]": ["status"]}, enums={"items[].status": ["NORMAL"]}),
        _consumer(reads=["items", "items[].status"], enum_literals={"items[].status": ["normal"]}),
        known_gaps=[_gap("C2", "normal", reason="operator decided to defer, tracked externally", ledger="issue-123")],
    )
    v, u, c, g, anchored, total = _lint(tmp_path, contract)
    assert _cid(v, "c_gap_downgrade") == []
    gaps_for_cid = _cid(g, "c_gap_downgrade")
    assert len(gaps_for_cid) == 1
    line = gaps_for_cid[0].line()
    assert "operator decided to defer, tracked externally" in line
    assert "issue-123" in line


def test_known_gap_missing_reason_or_ledger_is_itself_a_c0_violation(tmp_path: Path) -> None:
    """A gap entry missing `reason` (or `ledger`) is itself a C0 violation — declaring
    it must not be a way to silence it."""
    (tmp_path / "producer.py").write_text('def build():\n    return {"items": []}\n')
    (tmp_path / "consumer.py").write_text('def consume(data):\n    return data.get("items")\n')
    contract = _contract(
        "c_gap_malformed",
        _producer(emits=["items"]),
        _consumer(reads=["items"]),
        known_gaps=[
            {"check": "C1", "key": "ghost_a", "ledger": "issue-1"},          # missing "reason"
            {"check": "C1", "key": "ghost_b", "reason": "some reason"},     # missing "ledger"
        ],
    )
    v, u, c, g, anchored, total = _lint(tmp_path, contract)
    violations_for_cid = _cid(v, "c_gap_malformed")
    assert len(violations_for_cid) == 2
    assert all(x.check == "C0" for x in violations_for_cid)
    assert all("incomplete" in x.msg for x in violations_for_cid)


def test_stale_known_gap_that_matches_nothing_is_a_c0_violation(tmp_path: Path) -> None:
    """A well-formed gap that no longer matches any real violation is itself a
    violation — a declared gap cannot outlive the thing it excused."""
    (tmp_path / "producer.py").write_text('def build():\n    return {"items": []}\n')
    (tmp_path / "consumer.py").write_text('def consume(data):\n    return data.get("items")\n')
    contract = _contract(
        "c_gap_stale",
        _producer(emits=["items"]),
        _consumer(reads=["items"]),
        known_gaps=[_gap("C1", "phantom_key")],  # well-formed, but nothing violates C1/phantom_key
    )
    v, u, c, g, anchored, total = _lint(tmp_path, contract)
    violations_for_cid = _cid(v, "c_gap_stale")
    assert len(violations_for_cid) == 1
    assert violations_for_cid[0].check == "C0"
    assert "nothing violates it any more" in violations_for_cid[0].msg


def test_known_gap_matches_on_check_and_key_together_not_key_alone(tmp_path: Path) -> None:
    """A gap declared for check C2 key "GHOST" must NOT swallow a C1 violation that
    happens to share the SAME key "GHOST" — the match is (check, key), never key
    alone."""
    (tmp_path / "producer.py").write_text(
        'def build():\n    return {"items": [{"status": "NORMAL"}]}\n'
    )
    (tmp_path / "consumer.py").write_text(
        'def consume(data):\n'
        '    for i in data.get("items", []):\n'
        '        if i.get("status") == "NORMAL":\n'
        '            yield i\n'
    )
    contract = _contract(
        "c_gap_check_and_key",
        _producer(emits=["items"], nested={"items[]": ["status"]}, enums={"items[].status": ["NORMAL"]}),
        _consumer(
            reads=["items", "items[].status", "GHOST"],  # "GHOST" resolves to nothing -> C1 violation
            enum_literals={"items[].status": ["GHOST"]},  # "GHOST" is outside the domain -> C2 violation
        ),
        known_gaps=[_gap("C2", "GHOST")],  # only excuses the C2 half
    )
    v, u, c, g, anchored, total = _lint(tmp_path, contract)
    violations_for_cid = _cid(v, "c_gap_check_and_key")
    assert len(violations_for_cid) == 1
    assert violations_for_cid[0].check == "C1"
    assert violations_for_cid[0].key == "GHOST"
    gaps_for_cid = _cid(g, "c_gap_check_and_key")
    assert len(gaps_for_cid) == 1
    assert gaps_for_cid[0].check == "C2"
    assert gaps_for_cid[0].key == "GHOST"


# ---------------------------------------------------------------------------
# Section D — the anchored counter.
# ---------------------------------------------------------------------------

def test_anchored_counts_clean_contracts_not_only_ones_that_produced_a_violation(tmp_path: Path) -> None:
    """A registry of two fully-matched, clean python contracts must report
    anchored == 2 and total == 2 — the counter previously counted contracts that
    had produced a VIOLATION, so a perfectly clean registry summarised as
    "0 checked", indistinguishable from "the lint did nothing", on the one
    surface whose job is proving it looked."""
    (tmp_path / "producer_a.py").write_text(
        'def build():\n    return {"items": [{"status": "NORMAL"}]}\n'
    )
    (tmp_path / "consumer_a.py").write_text(
        'def consume(data):\n'
        '    for i in data.get("items", []):\n'
        '        if i.get("status") == "NORMAL":\n'
        '            yield i\n'
    )
    (tmp_path / "producer_b.py").write_text(
        'def build():\n    return {"counts": {"total": 1}}\n'
    )
    (tmp_path / "consumer_b.py").write_text(
        'def consume(data):\n    return data.get("counts")\n'
    )
    contract_a = _contract(
        "clean_a",
        _producer(path="producer_a.py", emits=["items"], nested={"items[]": ["status"]}, enums={"items[].status": ["NORMAL"]}),
        _consumer(path="consumer_a.py", reads=["items", "items[].status"], enum_literals={"items[].status": ["NORMAL"]}),
    )
    contract_b = _contract(
        "clean_b",
        _producer(path="producer_b.py", emits=["counts"]),
        _consumer(path="consumer_b.py", reads=["counts"]),
    )
    v, u, c, g, anchored, total = _lint(tmp_path, contract_a, contract_b)
    assert anchored == 2
    assert total == 2
    assert v == []
    assert u == []
    assert c == []
    assert g == []


# ---------------------------------------------------------------------------
# Section E — `_no_regrowth` against a REAL throwaway git repository.
# ---------------------------------------------------------------------------

def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    """Run a git command in `repo`, isolated from this machine's real ~/.gitconfig
    (a signing key / gpgsign=true there could hang or fail an otherwise-correct
    commit) — never touching the developer's actual git identity/config."""
    git_home = repo.parent / "_git_home"
    git_home.mkdir(exist_ok=True)
    env = dict(os.environ)
    env.update({
        "HOME": str(git_home),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "lint-test",
        "GIT_AUTHOR_EMAIL": "lint-test@example.invalid",
        "GIT_COMMITTER_NAME": "lint-test",
        "GIT_COMMITTER_EMAIL": "lint-test@example.invalid",
    })
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "commit.gpgsign=false", *args],
        capture_output=True, text=True, env=env, timeout=20,
    )


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    r = _git(repo, "init", "-q")
    assert r.returncode == 0, r.stderr
    return repo


def _commit_file(repo: Path, rel: str, content: str, message: str) -> None:
    (repo / rel).write_text(content, encoding="utf-8")
    r = _git(repo, "add", rel)
    assert r.returncode == 0, r.stderr
    r = _git(repo, "commit", "-q", "-m", message)
    assert r.returncode == 0, r.stderr


def test_no_regrowth_growth_against_base_is_a_c5_violation(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    registry_path = repo / "contracts.json"
    base_registry = {"version": 1, "contracts": [{"id": "x", "known_gaps": [_gap("C1", "a")]}]}
    _commit_file(repo, "contracts.json", json.dumps(base_registry), "base: 1 known gap")

    now_registry = {"version": 1, "contracts": [{"id": "x", "known_gaps": [_gap("C1", "a"), _gap("C1", "b")]}]}
    registry_path.write_text(json.dumps(now_registry), encoding="utf-8")  # uncommitted growth

    violations, cannot_verify = lic._no_regrowth(registry_path, now_registry, "HEAD")
    assert cannot_verify == []
    assert len(violations) == 1
    assert violations[0].check == "C5"
    assert "known_gaps grew 1 -> 2" in violations[0].msg


def test_no_regrowth_shrink_against_base_is_clean(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    registry_path = repo / "contracts.json"
    base_registry = {"version": 1, "contracts": [{"id": "x", "known_gaps": [_gap("C1", "a"), _gap("C1", "b")]}]}
    _commit_file(repo, "contracts.json", json.dumps(base_registry), "base: 2 known gaps")

    now_registry = {"version": 1, "contracts": [{"id": "x", "known_gaps": [_gap("C1", "a")]}]}
    registry_path.write_text(json.dumps(now_registry), encoding="utf-8")

    violations, cannot_verify = lic._no_regrowth(registry_path, now_registry, "HEAD")
    assert violations == []
    assert cannot_verify == []


def test_no_regrowth_equal_count_against_base_is_clean(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    registry_path = repo / "contracts.json"
    base_registry = {"version": 1, "contracts": [{"id": "x", "known_gaps": [_gap("C1", "a")]}]}
    _commit_file(repo, "contracts.json", json.dumps(base_registry), "base: 1 known gap")

    now_registry = {"version": 1, "contracts": [{"id": "x", "known_gaps": [_gap("C1", "a")]}]}
    registry_path.write_text(json.dumps(now_registry), encoding="utf-8")

    violations, cannot_verify = lic._no_regrowth(registry_path, now_registry, "HEAD")
    assert violations == []
    assert cannot_verify == []


def test_no_regrowth_bootstrap_window_file_absent_at_base_is_clean_not_cannot_verify(tmp_path: Path) -> None:
    """The registry FILE is absent at base_ref (the ref itself resolves fine) — this
    is the PR that introduces the registry, so baseline known_gaps is legitimately
    zero. Must be zero violations AND zero cannot-verify, never CANNOT-VERIFY."""
    repo = _init_repo(tmp_path)
    _commit_file(repo, "README.md", "placeholder\n", "base: no registry file yet")

    registry_path = repo / "contracts.json"
    now_registry = {"version": 1, "contracts": [{"id": "x", "known_gaps": [_gap("C1", "a"), _gap("C1", "b")]}]}
    registry_path.write_text(json.dumps(now_registry), encoding="utf-8")  # introduced only now, never committed

    violations, cannot_verify = lic._no_regrowth(registry_path, now_registry, "HEAD")
    assert violations == []
    assert cannot_verify == [], "the introducing PR must not be reported as CANNOT-VERIFY"


def test_no_regrowth_unresolvable_base_ref_is_cannot_verify_not_clean(tmp_path: Path) -> None:
    """A base ref that does NOT resolve at all (as opposed to resolving but lacking
    the file) is CANNOT-VERIFY, never a silent pass — these two failures must not
    collapse into each other."""
    repo = _init_repo(tmp_path)
    _commit_file(repo, "README.md", "placeholder\n", "only commit")

    registry_path = repo / "contracts.json"
    now_registry = {"version": 1, "contracts": [{"id": "x", "known_gaps": [_gap("C1", "a")]}]}
    registry_path.write_text(json.dumps(now_registry), encoding="utf-8")

    violations, cannot_verify = lic._no_regrowth(registry_path, now_registry, "refs/heads/does-not-exist-ever")
    assert violations == []
    assert len(cannot_verify) == 1
    assert "cannot resolve" in cannot_verify[0].reason


# ---------------------------------------------------------------------------
# Section F — main()'s CLI exit codes, driven with a real argv list.
# ---------------------------------------------------------------------------

def test_main_exit_0_on_clean_registry(tmp_path: Path) -> None:
    (tmp_path / "producer.py").write_text(
        'def build():\n    return {"items": [{"status": "NORMAL"}]}\n'
    )
    (tmp_path / "consumer.py").write_text(
        'def consume(data):\n'
        '    for i in data.get("items", []):\n'
        '        if i.get("status") == "NORMAL":\n'
        '            yield i\n'
    )
    contract = _contract(
        "main_clean",
        _producer(emits=["items"], nested={"items[]": ["status"]}, enums={"items[].status": ["NORMAL"]}),
        _consumer(reads=["items", "items[].status"], enum_literals={"items[].status": ["NORMAL"]}),
    )
    registry_path = tmp_path / "contracts.json"
    registry_path.write_text(json.dumps({"version": 1, "contracts": [contract]}), encoding="utf-8")

    ret = lic.main(["--registry", str(registry_path), "--repo-root", str(tmp_path)])
    assert ret == 0


def test_main_exit_1_on_violations(tmp_path: Path) -> None:
    (tmp_path / "producer.py").write_text('def build():\n    return {"counts": {}}\n')
    (tmp_path / "consumer.py").write_text('def consume(data):\n    return data.get("counts")\n')
    contract = _contract(
        "main_dirty",
        _producer(emits=["counts", "entries"]),  # "entries" never written -> C4 violation
        _consumer(reads=["counts"]),
    )
    registry_path = tmp_path / "contracts.json"
    registry_path.write_text(json.dumps({"version": 1, "contracts": [contract]}), encoding="utf-8")

    ret = lic.main(["--registry", str(registry_path), "--repo-root", str(tmp_path)])
    assert ret == 1


def test_main_exit_2_on_missing_registry_file(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.json"
    ret = lic.main(["--registry", str(missing), "--repo-root", str(tmp_path)])
    assert ret == 2


def test_main_exit_2_on_invalid_json_registry(tmp_path: Path) -> None:
    bad = tmp_path / "contracts.json"
    bad.write_text("{not valid json,,,", encoding="utf-8")
    ret = lic.main(["--registry", str(bad), "--repo-root", str(tmp_path)])
    assert ret == 2


def test_main_exit_3_on_cannot_verify_is_not_zero(tmp_path: Path) -> None:
    """A declared source file (here: the producer's) is missing on disk -> CANNOT-VERIFY.
    A scan that could not look is not a clean scan: exit 3, not exit 0."""
    # Deliberately do NOT create producer.py — only the consumer file exists.
    (tmp_path / "consumer.py").write_text('def consume(data):\n    return data.get("items")\n')
    contract = _contract(
        "main_cannot_verify",
        _producer(path="producer.py", emits=["items"]),  # file never written -> CannotVerify at C4
        _consumer(reads=["items"]),
    )
    registry_path = tmp_path / "contracts.json"
    registry_path.write_text(json.dumps({"version": 1, "contracts": [contract]}), encoding="utf-8")

    ret = lic.main(["--registry", str(registry_path), "--repo-root", str(tmp_path)])
    assert ret == 3
    assert ret != 0, "CANNOT-VERIFY must never read as a clean scan"


# ---------------------------------------------------------------------------
# Section G — `--selftest` returns 0, and is not a tautology.
# ---------------------------------------------------------------------------

def test_main_selftest_returns_zero() -> None:
    assert lic.main(["--selftest"]) == 0


def test_main_selftest_prints_named_individual_cases_not_just_a_bare_zero(capsys) -> None:
    """`assert main(["--selftest"]) == 0` alone would be satisfied by a stub that
    just `return`s 0. Prove the self-test actually ran and named its cases: it
    must print multiple distinct "PASS <name>" lines and end on a summary line,
    with zero "FAIL" lines."""
    ret = lic.main(["--selftest"])
    assert ret == 0
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line.strip()]
    assert lines, "selftest printed nothing at all"
    assert lines[-1] == "SELFTEST OK"
    pass_lines = [line for line in lines if line.startswith("PASS ")]
    assert len(pass_lines) >= 5, "selftest should name several individual passing cases, not just return 0"
    assert not any(line.startswith("FAIL ") for line in lines)
