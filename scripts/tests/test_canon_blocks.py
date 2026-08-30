"""Guilt + innocence for the canon-block comparator.

WHY IT EXISTS, measured rather than supposed. On 2026-08-31 the fleet's three
copies of the global `~/.claude/CLAUDE.md` were M5 27,377 B, Pro 22,795 B, Mini
22,795 B — and the difference was not cosmetic. Pro and Mini were missing the
entire SHIP-LIFECYCLE HARD RULE, carried the SUPERSEDED "no paid APIs ever"
wording of a rule Zero downgraded on 2026-06-04, and still named a seat retired
on 2026-07-19. Two of those govern how work ships and what it may cost, on the
machines where most of the fleet's work happens, and nothing was comparing them.

Every case here builds a synthetic HOME. The real `~/.claude/CLAUDE.md` is never
read: it is control-plane, it is the operator's, and a test that depends on one
machine's copy would pass or fail for reasons that have nothing to do with the
code (superscar family #1).
"""

from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "proprioception", Path(__file__).resolve().parents[1] / "proprioception.py"
)
assert _SPEC and _SPEC.loader
pp = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(pp)

ROOT = Path(__file__).resolve().parents[2]


def _doc(*blocks: tuple[str, str], preamble: str = "# Global doctrine\n\n") -> str:
    out = preamble
    for bid, body in blocks:
        out += f"<!-- CANON:{bid} -->\n{body}\n<!-- /CANON:{bid} -->\n\n"
    out += "## Machine-specific section\n\nPaths that differ per machine live here.\n"
    return out


def _home(tmp: Path, text: str | None, report: dict | None = None, age_min: float = 0.0) -> Path:
    h = tmp / "home"
    (h / ".claude").mkdir(parents=True)
    if text is not None:
        (h / ".claude" / "CLAUDE.md").write_text(text)
    if report is not None:
        rp = h / ".claude" / "canon-blocks.json"
        rp.write_text(json.dumps(report))
        if age_min:
            old = time.time() - age_min * 60
            import os

            os.utime(rp, (old, old))
    return h


def _probe(home: Path, **kw):
    args = {"home": str(home), "report": str(home / ".claude" / "canon-blocks.json")}
    args.update(kw)
    return pp.probe_canon_blocks(ROOT, args, 10)


# --- the state the fleet is actually in today -------------------------------


def test_no_markers_reads_UNPROBEABLE_not_agreement(tmp_path: Path) -> None:
    """The load-bearing case, because it is TODAY's state on all three machines:
    `grep -c 'CANON:'` returns 0 everywhere. A comparator answering RECONCILED
    across three files containing zero blocks would be the purest instance of the
    disease it exists to detect."""
    home = _home(tmp_path, "# Global doctrine\n\nNo markers here at all.\n")
    status, n, ev = _probe(home)
    assert status == pp.UNPROBEABLE, f"reported {status} for a file with nothing marked"
    assert n == 0
    assert "no <!-- CANON:" in ev[0]


def test_markers_but_no_fleet_report_reads_UNPROBEABLE(tmp_path: Path) -> None:
    home = _home(tmp_path, _doc(("ship", "The session merges, arms and deploys.")))
    status, _n, ev = _probe(home)
    assert status == pp.UNPROBEABLE
    assert "no fleet report" in ev[0]


def test_absent_claude_md_reads_UNPROBEABLE(tmp_path: Path) -> None:
    status, _n, ev = _probe(_home(tmp_path, None))
    assert status == pp.UNPROBEABLE
    assert "absent" in ev[0]


# --- innocence --------------------------------------------------------------


def test_identical_blocks_are_silent(tmp_path: Path) -> None:
    text = _doc(("ship", "The session merges, arms and deploys."), ("cost", "Paid keys need authorization."))
    digests = pp._canon_blocks(text)
    home = _home(tmp_path, text, report={"machines": {"Pro": digests, "Mini": digests}})
    status, n, ev = _probe(home)
    assert status == pp.RECONCILED, ev
    assert n == 0


def test_divergence_OUTSIDE_a_canon_block_is_not_a_finding(tmp_path: Path) -> None:
    """The file is SUPPOSED to differ per machine — it carries machine-specific
    paths and roles. Comparing whole files would alarm on every legitimate
    difference, and a guard that alarms on the normal case is one that gets
    switched off inside a week."""
    shared = ("ship", "The session merges, arms and deploys.")
    mine = _doc(shared, preamble="# Global doctrine\n\nI am M5 and my home is /Users/balizero.\n")
    theirs = _doc(shared, preamble="# Global doctrine\n\nI am Pro and my home is /Users/nuzantara.\n")
    assert mine != theirs, "premise: the two files must actually differ"
    home = _home(tmp_path, mine, report={"machines": {"Pro": pp._canon_blocks(theirs)}})
    status, n, _ev = _probe(home)
    assert status == pp.RECONCILED, "a difference outside the marked blocks was reported"
    assert n == 0


# --- guilt: the three shapes the real divergence took -----------------------


def test_a_reworded_rule_is_a_finding(tmp_path: Path) -> None:
    """The real case: Pro said "no paid APIs ever" where M5 said the rule Zero
    downgraded on 2026-06-04. Same block id, different text."""
    mine = _doc(("cost", "Paid API keys require Zero's authorization."))
    theirs = _doc(("cost", "Zero paid API keys. Period."))
    home = _home(tmp_path, mine, report={"machines": {"Pro": pp._canon_blocks(theirs)}})
    status, n, ev = _probe(home)
    assert status == pp.DIVERGED
    assert n == 1
    assert "CANON:cost differs from Pro" in ev[0]


def test_a_block_missing_on_a_peer_is_a_finding(tmp_path: Path) -> None:
    """The worst real case: Pro had NO ship-lifecycle section at all. A comparator
    that only checked blocks present on both sides would have said nothing."""
    mine = _doc(("ship", "The session merges, arms and deploys."), ("cost", "Authorized keys only."))
    theirs = _doc(("cost", "Authorized keys only."))
    home = _home(tmp_path, mine, report={"machines": {"Pro": pp._canon_blocks(theirs)}})
    status, n, ev = _probe(home)
    assert status == pp.DIVERGED
    assert any("CANON:ship is here but ABSENT on Pro" in line for line in ev), ev


def test_a_block_present_only_on_a_peer_is_a_finding(tmp_path: Path) -> None:
    """The same asymmetry from the other side — the machine reading might be the
    stale one, and a comparator that only looked outward would never say so."""
    mine = _doc(("cost", "Authorized keys only."))
    theirs = _doc(("cost", "Authorized keys only."), ("ship", "The session merges, arms and deploys."))
    home = _home(tmp_path, mine, report={"machines": {"Pro": pp._canon_blocks(theirs)}})
    status, _n, ev = _probe(home)
    assert status == pp.DIVERGED
    assert any("ABSENT here" in line for line in ev), ev


# --- the ways a comparator lies ---------------------------------------------


def test_a_stale_fleet_report_is_refused_not_believed(tmp_path: Path) -> None:
    """A published file rots into a confident lie. Comparing against a two-day-old
    snapshot and reporting RECONCILED is worse than reporting nothing."""
    text = _doc(("ship", "The session merges, arms and deploys."))
    home = _home(tmp_path, text, report={"machines": {"Pro": pp._canon_blocks(text)}}, age_min=3000)
    status, _n, ev = _probe(home, max_age_min=1440)
    assert status == pp.UNPROBEABLE
    assert "stale" in ev[0]


def test_an_unreadable_report_is_refused_not_treated_as_empty(tmp_path: Path) -> None:
    home = _home(tmp_path, _doc(("ship", "x")))
    (home / ".claude" / "canon-blocks.json").write_text("{not json")
    status, _n, ev = _probe(home)
    assert status == pp.UNPROBEABLE
    assert "unreadable" in ev[0]


def test_whitespace_only_change_is_not_drift(tmp_path: Path) -> None:
    """Trailing spaces and line endings differ between machines for reasons that
    are not doctrine. Treating them as drift makes the first real finding arrive
    inside a crowd of false ones."""
    a = pp._canon_blocks(_doc(("ship", "The session merges, arms and deploys.")))
    b = pp._canon_blocks(_doc(("ship", "The session merges, arms and deploys.   ")))
    assert a == b


def test_a_reworded_sentence_IS_drift(tmp_path: Path) -> None:
    """The other side of the same rule: anything meaning-bearing must change the
    digest, or the comparator is decorative."""
    a = pp._canon_blocks(_doc(("ship", "The session merges and deploys.")))
    b = pp._canon_blocks(_doc(("ship", "The codeowner merges and deploys.")))
    assert a != b


def test_an_unclosed_block_surfaces_rather_than_vanishing(tmp_path: Path) -> None:
    """A malformed marker must not silently mean one fewer thing to compare —
    that would let a bad edit REMOVE a block from comparison, which is the
    cheapest possible way to disarm this probe."""
    blocks = pp._canon_blocks("<!-- CANON:ship -->\nrule text\n\n## next section\n")
    assert any(k.endswith("!unclosed") for k in blocks), blocks


def test_the_probe_is_registered_and_never_writes(tmp_path: Path) -> None:
    """Read-only by construction: the file it watches is control-plane and
    per-machine, and a watcher that can write is one flag away from becoming the
    thing that makes the copies diverge."""
    assert "canon_blocks" in pp.BUILTINS
    text = _doc(("ship", "x"))
    home = _home(tmp_path, text, report={"machines": {"Pro": pp._canon_blocks(text)}})
    before = {p: p.read_bytes() for p in (home / ".claude").rglob("*") if p.is_file()}
    _probe(home)
    after = {p: p.read_bytes() for p in (home / ".claude").rglob("*") if p.is_file()}
    assert before == after, "the probe modified the tree it was reading"


# --- per-machine freshness: the report is MERGED, so the file's mtime lies ----


def test_a_peer_that_stopped_publishing_is_dropped_not_believed(tmp_path: Path) -> None:
    """The report carries one entry per machine and its mtime is only the LAST
    publisher's. Without a per-machine stamp, a peer that went quiet a month ago
    is compared against as if it had answered this morning — the stale-report lie
    hidden one level down, where the file's own age looks fresh."""
    mine = _doc(("cost", "Authorized keys only."))
    theirs = _doc(("cost", "Zero paid API keys. Period."))
    now = time.time()
    report = {
        "machines": {"Pro": pp._canon_blocks(theirs), "Mini": pp._canon_blocks(mine)},
        "seen_at": {"Pro": now - 40 * 24 * 3600, "Mini": now},
    }
    status, n, ev = _probe(_home(tmp_path, mine, report=report), max_age_min=1440)
    assert status == pp.RECONCILED, ev
    assert n == 0
    assert "ignoring quiet: Pro" in ev[0]


def test_every_peer_quiet_reads_UNPROBEABLE_not_agreement(tmp_path: Path) -> None:
    mine = _doc(("cost", "Authorized keys only."))
    now = time.time()
    report = {"machines": {"Pro": pp._canon_blocks(mine)}, "seen_at": {"Pro": now - 40 * 24 * 3600}}
    status, _n, ev = _probe(_home(tmp_path, mine, report=report), max_age_min=1440)
    assert status == pp.UNPROBEABLE
    assert "nothing fresh to compare" in ev[0]


def test_a_fresh_peer_is_still_compared(tmp_path: Path) -> None:
    """Innocence for the same rule: the freshness filter must not become a way to
    drop the finding along with the peer."""
    mine = _doc(("cost", "Authorized keys only."))
    theirs = _doc(("cost", "Zero paid API keys. Period."))
    report = {"machines": {"Pro": pp._canon_blocks(theirs)}, "seen_at": {"Pro": time.time()}}
    status, n, _ev = _probe(_home(tmp_path, mine, report=report), max_age_min=1440)
    assert status == pp.DIVERGED and n == 1


def test_a_report_without_seen_at_still_compares(tmp_path: Path) -> None:
    """Back-compat: a report written before this field existed must not read as
    'every peer is quiet'. The whole-report age still governs it."""
    mine = _doc(("cost", "Authorized keys only."))
    theirs = _doc(("cost", "Zero paid API keys. Period."))
    status, n, _ev = _probe(_home(tmp_path, mine, report={"machines": {"Pro": pp._canon_blocks(theirs)}}))
    assert status == pp.DIVERGED and n == 1


def test_the_quiet_filter_matches_a_NAME_not_a_prefix_of_its_display_line(tmp_path: Path) -> None:
    """The machine key is DATA read out of a JSON file, not a validated hostname:
    whatever published it chose the string, and a hand-edited or peer-supplied
    report can carry any of them. Matching a name against a prefix of the human
    line ("Air (last published ...)") drops every machine whose name is a
    space-delimited prefix of a quiet one — superscar family #3, and it takes the
    FINDING down with the peer.

    The first version of this test used Pro/Pro2 and was vacuous: the trailing
    space in the prefix form already separates those, so the mutant survived.
    """
    mine = _doc(("cost", "Authorized keys only."))
    theirs = _doc(("cost", "Zero paid API keys. Period."))
    now = time.time()
    report = {
        "machines": {"Air M5": pp._canon_blocks(mine), "Air": pp._canon_blocks(theirs)},
        "seen_at": {"Air M5": now - 40 * 24 * 3600, "Air": now},
    }
    status, n, ev = _probe(_home(tmp_path, mine, report=report), max_age_min=1440)
    assert status == pp.DIVERGED, f"the fresh peer 'Air' was dropped along with 'Air M5': {ev}"
    assert n == 1 and "from Air " in ev[0], ev


def test_ordinary_sibling_names_are_unaffected(tmp_path: Path) -> None:
    """Innocence for the same rule, on the shape the fleet actually has."""
    mine = _doc(("cost", "Authorized keys only."))
    theirs = _doc(("cost", "Zero paid API keys. Period."))
    now = time.time()
    report = {
        "machines": {"Pro": pp._canon_blocks(mine), "Pro2": pp._canon_blocks(theirs)},
        "seen_at": {"Pro": now - 40 * 24 * 3600, "Pro2": now},
    }
    status, n, ev = _probe(_home(tmp_path, mine, report=report), max_age_min=1440)
    assert status == pp.DIVERGED and n == 1 and "Pro2" in ev[0], ev


# --- the write half ---------------------------------------------------------

_PUB = ROOT / "scripts" / "canon_blocks_publish.py"


def _publish(tmp: Path, claude_md: Path, report: Path, extra: list[str] | None = None):
    import subprocess
    import sys

    cmd = [sys.executable, str(_PUB), "--claude-md", str(claude_md),
           "--report-path", str(report), "--no-push", *(extra or [])]
    return subprocess.run(cmd, capture_output=True, text=True)


def test_publishing_an_unmarked_file_is_REFUSED(tmp_path: Path) -> None:
    """An empty map reads as agreement to every machine that receives it. This is
    the write-side twin of the UNPROBEABLE-not-RECONCILED rule, and it matters
    today because zero machines carry markers yet."""
    src = tmp_path / "CLAUDE.md"
    src.write_text("# doctrine\n\nnothing marked\n")
    report = tmp_path / "canon-blocks.json"
    r = _publish(tmp_path, src, report)
    assert r.returncode == 3, r.stdout + r.stderr
    assert not report.exists(), "refused, but wrote a report anyway"
    assert "reads as agreement" in r.stderr


def test_published_report_carries_digests_and_never_block_text(tmp_path: Path) -> None:
    """A report containing the text would be a FOURTH copy of the file, and the
    whole point of comparing is that there are three."""
    secretish = "The session merges, arms and deploys, and this exact sentence must not travel."
    src = tmp_path / "CLAUDE.md"
    src.write_text(_doc(("ship", secretish)))
    report = tmp_path / "canon-blocks.json"
    r = _publish(tmp_path, src, report)
    assert r.returncode == 0, r.stdout + r.stderr
    raw = report.read_text()
    assert "must not travel" not in raw
    assert list(json.loads(raw)["machines"].values())[0] == pp._canon_blocks(src.read_text())


def test_publishing_preserves_peer_entries_and_stamps_only_its_own(tmp_path: Path) -> None:
    """Merge, not overwrite — one machine publishing must not erase what the
    others said. And it stamps only ITSELF: forging a peer's freshness is how the
    quiet-peer guard would get silently disarmed."""
    src = tmp_path / "CLAUDE.md"
    src.write_text(_doc(("ship", "rule")))
    report = tmp_path / "canon-blocks.json"
    report.write_text(json.dumps({"machines": {"Peer": {"ship": "deadbeefdeadbeef"}},
                                  "seen_at": {"Peer": 1.0}}))
    assert _publish(tmp_path, src, report).returncode == 0
    got = json.loads(report.read_text())
    assert got["machines"]["Peer"] == {"ship": "deadbeefdeadbeef"}
    assert got["seen_at"]["Peer"] == 1.0, "publisher refreshed a peer's stamp it did not measure"
    assert len(got["seen_at"]) == 2


def test_publisher_and_probe_share_one_definition_of_a_block(tmp_path: Path) -> None:
    """Two implementations of 'what is a canon block' would drift, and the drift
    would be invisible: every machine would read DIVERGED for a reason that is
    not in the doctrine at all.

    Checked BEHAVIOURALLY, on the quirks a reimplementation would get wrong,
    rather than by asserting that some symbol name does or does not appear in the
    source. The first version of this test asserted `"_CANON_OPEN_RE" not in
    src`, which an independent parser passes trivially by choosing another name —
    a substring standing in for the entity, which is the family this repo keeps
    being bitten by (Codex sol, 2026-08-31).
    """
    src = tmp_path / "CLAUDE.md"
    src.write_text(
        "<!-- CANON:ws -->\nbody with trailing spaces   \n<!-- /CANON:ws -->\n"
        "<!-- CANON:mismatch -->\nbody\n<!-- /CANON:other -->\n"
        "<!-- CANON:dangling -->\nlast body\n"
    )
    report = tmp_path / "canon-blocks.json"
    assert _publish(tmp_path, src, report).returncode == 0
    published = list(json.loads(report.read_text())["machines"].values())[0]
    expected = pp._canon_blocks(src.read_text())

    # Non-vacuity: the fixture must actually exercise the quirks, or "equal"
    # would only mean "both parsers found nothing interesting".
    assert any(k.endswith("!unclosed") for k in expected), expected
    assert len(expected) >= 2, expected
    assert published == expected, (
        "the publisher's block map diverges from the probe's on a file that "
        f"exercises trailing whitespace, a mismatched close tag and an unclosed "
        f"block: published={published} probe={expected}"
    )
