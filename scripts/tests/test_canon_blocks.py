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
import os
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


def _home(
    tmp: Path, text: str | None, report: dict | None = None, age_min: float = 0.0
) -> Path:
    """A synthetic HOME. `report` keeps the old {"machines":..., "seen_at":...}
    shape for readability and is exploded into the per-machine fragments the
    probe actually reads — one file per machine, because a shared document that
    every publisher rewrites whole lets two machines erase each other."""
    h = tmp / "home"
    (h / ".claude").mkdir(parents=True)
    if text is not None:
        (h / ".claude" / "CLAUDE.md").write_text(text)
    if report is not None:
        d = h / ".claude" / "canon-blocks.d"
        d.mkdir(parents=True, exist_ok=True)
        now = time.time()
        stamps = report.get("seen_at", {})
        for machine, blocks in report.get("machines", {}).items():
            frag = {"machine": machine, "blocks": blocks}
            if machine in stamps:
                frag["seen_at"] = stamps[machine]
            elif "seen_at" in report:
                pass  # deliberately unstamped: the test is about that
            else:
                frag["seen_at"] = now
            fp = d / f"{machine}.json"
            fp.write_text(json.dumps(frag))
            if age_min:
                old_t = now - age_min * 60
                import os

                os.utime(fp, (old_t, old_t))
    return h


def _probe(home: Path, **kw):
    # `hostname` is pinned so the corpus never depends on WHICH machine runs it:
    # the probe pulls its own entry out of the report, and a test whose verdict
    # changed with the runner's hostname would be measuring the runner.
    args = {
        "home": str(home),
        "report_dir": str(home / ".claude" / "canon-blocks.d"),
        "hostname": "TestRunner",
    }
    args.update(kw)
    return pp.probe_canon_blocks(ROOT, args, 10)


def _report(machines: dict, seen_at: dict | None = None) -> dict:
    """Every peer carries a fresh stamp unless a test deliberately says otherwise.

    `seen_at` is REQUIRED per peer: the report is merged and its mtime belongs to
    the last publisher only, so an unstamped entry would be trusted at whatever
    age it happened to be."""
    now = time.time()
    return {
        "machines": machines,
        "seen_at": seen_at if seen_at is not None else {m: now for m in machines},
    }


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
    assert "no fleet fragments" in ev[0]


def test_absent_claude_md_reads_UNPROBEABLE(tmp_path: Path) -> None:
    status, _n, ev = _probe(_home(tmp_path, None))
    assert status == pp.UNPROBEABLE
    assert "absent" in ev[0]


# --- innocence --------------------------------------------------------------


def test_identical_blocks_are_silent(tmp_path: Path) -> None:
    text = _doc(
        ("ship", "The session merges, arms and deploys."),
        ("cost", "Paid keys need authorization."),
    )
    digests = pp._canon_blocks(text)
    home = _home(tmp_path, text, report=_report({"Pro": digests, "Mini": digests}))
    status, n, ev = _probe(home)
    assert status == pp.RECONCILED, ev
    assert n == 0


def test_divergence_OUTSIDE_a_canon_block_is_not_a_finding(tmp_path: Path) -> None:
    """The file is SUPPOSED to differ per machine — it carries machine-specific
    paths and roles. Comparing whole files would alarm on every legitimate
    difference, and a guard that alarms on the normal case is one that gets
    switched off inside a week."""
    shared = ("ship", "The session merges, arms and deploys.")
    mine = _doc(
        shared,
        preamble="# Global doctrine\n\nI am M5 and my home is /Users/balizero.\n",
    )
    theirs = _doc(
        shared,
        preamble="# Global doctrine\n\nI am Pro and my home is /Users/nuzantara.\n",
    )
    assert mine != theirs, "premise: the two files must actually differ"
    home = _home(tmp_path, mine, report=_report({"Pro": pp._canon_blocks(theirs)}))
    status, n, _ev = _probe(home)
    assert status == pp.RECONCILED, (
        "a difference outside the marked blocks was reported"
    )
    assert n == 0


# --- guilt: the three shapes the real divergence took -----------------------


def test_a_reworded_rule_is_a_finding(tmp_path: Path) -> None:
    """The real case: Pro said "no paid APIs ever" where M5 said the rule Zero
    downgraded on 2026-06-04. Same block id, different text."""
    mine = _doc(("cost", "Paid API keys require Zero's authorization."))
    theirs = _doc(("cost", "Zero paid API keys. Period."))
    home = _home(tmp_path, mine, report=_report({"Pro": pp._canon_blocks(theirs)}))
    status, n, ev = _probe(home)
    assert status == pp.DIVERGED
    assert n == 1
    assert "CANON:cost differs from Pro" in ev[0]


def test_a_block_missing_on_a_peer_is_a_finding(tmp_path: Path) -> None:
    """The worst real case: Pro had NO ship-lifecycle section at all. A comparator
    that only checked blocks present on both sides would have said nothing."""
    mine = _doc(
        ("ship", "The session merges, arms and deploys."),
        ("cost", "Authorized keys only."),
    )
    theirs = _doc(("cost", "Authorized keys only."))
    home = _home(tmp_path, mine, report=_report({"Pro": pp._canon_blocks(theirs)}))
    status, n, ev = _probe(home)
    assert status == pp.DIVERGED
    assert any("CANON:ship is here but ABSENT on Pro" in line for line in ev), ev


def test_a_block_present_only_on_a_peer_is_a_finding(tmp_path: Path) -> None:
    """The same asymmetry from the other side — the machine reading might be the
    stale one, and a comparator that only looked outward would never say so."""
    mine = _doc(("cost", "Authorized keys only."))
    theirs = _doc(
        ("cost", "Authorized keys only."),
        ("ship", "The session merges, arms and deploys."),
    )
    home = _home(tmp_path, mine, report=_report({"Pro": pp._canon_blocks(theirs)}))
    status, _n, ev = _probe(home)
    assert status == pp.DIVERGED
    assert any("ABSENT here" in line for line in ev), ev


# --- the ways a comparator lies ---------------------------------------------


def test_a_stale_fragment_is_refused_not_believed(tmp_path: Path) -> None:
    """A published file rots into a confident lie. Comparing against a two-day-old
    snapshot and reporting RECONCILED is worse than reporting nothing."""
    text = _doc(("ship", "The session merges, arms and deploys."))
    report = {
        "machines": {"Pro": pp._canon_blocks(text)},
        "seen_at": {"Pro": time.time() - 3000 * 60},
    }
    status, _n, ev = _probe(_home(tmp_path, text, report=report), max_age_min=1440)
    assert status == pp.UNPROBEABLE
    assert "last published" in "\n".join(ev)


def test_TOUCHING_a_fragment_does_not_make_a_stale_peer_fresh(tmp_path: Path) -> None:
    """Freshness is the stamp INSIDE the fragment, never the file's mtime. An
    mtime is set by copying, syncing, backing up or `touch` — none of which mean
    a machine re-read its doctrine — so keying freshness on it would let any
    file-level operation revive an arbitrarily old peer."""
    text = _doc(("ship", "rule"))
    report = {
        "machines": {"Pro": pp._canon_blocks(text)},
        "seen_at": {"Pro": time.time() - 3000 * 60},
    }
    home = _home(tmp_path, text, report=report)
    frag = home / ".claude" / "canon-blocks.d" / "Pro.json"
    frag.touch()  # brand-new mtime, unchanged content
    assert frag.stat().st_mtime > time.time() - 5, "premise: the touch must have landed"
    status, _n, ev = _probe(home, max_age_min=1440)
    assert status == pp.UNPROBEABLE, f"a touch revived a 50-hour-old peer: {ev}"


def test_a_peer_whose_clock_runs_AHEAD_does_not_become_immortal(tmp_path: Path) -> None:
    """A stamp in the future never ages out, so a peer whose clock runs ahead
    would be believed forever even if it died a year ago — the exact lie the
    stamp was added to prevent, reintroduced by clock skew."""
    text = _doc(("ship", "rule"))
    report = {
        "machines": {"Pro": pp._canon_blocks(text)},
        "seen_at": {"Pro": time.time() + 86400},
    }
    status, _n, ev = _probe(_home(tmp_path, text, report=report), max_age_min=1440)
    assert status == pp.UNPROBEABLE
    assert "FUTURE" in "\n".join(ev)


def test_ordinary_clock_drift_is_tolerated(tmp_path: Path) -> None:
    """Innocence for the same rule: machines are not synchronised to the second,
    and a comparator that alarmed on a few seconds of drift would be noise."""
    text = _doc(("ship", "rule"))
    report = {
        "machines": {"Pro": pp._canon_blocks(text)},
        "seen_at": {"Pro": time.time() + 60},
    }
    status, n, ev = _probe(_home(tmp_path, text, report=report), max_age_min=1440)
    assert status == pp.RECONCILED, ev
    assert n == 0


def test_ONE_unreadable_fragment_does_not_blind_the_others(tmp_path: Path) -> None:
    """One machine writing a bad file must not take the whole comparison with it.
    The fragment is named as unreadable and the remaining peers are still
    compared — the opposite of the single shared report, where one bad write made
    every machine unprobeable at once."""
    text = _doc(("ship", "rule"))
    other = _doc(("ship", "a DIFFERENT rule"))
    home = _home(tmp_path, text, report={"machines": {"Pro": pp._canon_blocks(other)}})
    (home / ".claude" / "canon-blocks.d" / "Mini.json").write_text("{not json")
    status, _n, ev = _probe(home)
    joined = "\n".join(ev)
    assert status == pp.DIVERGED
    assert "differs from Pro" in joined, joined
    assert "Mini.json" in joined, joined


def test_an_unreadable_report_is_refused_not_treated_as_empty(tmp_path: Path) -> None:
    home = _home(tmp_path, _doc(("ship", "x")))
    (home / ".claude" / "canon-blocks.json").write_text("{not json")
    status, _n, ev = _probe(home)
    assert status == pp.UNPROBEABLE
    assert "unreadable" in "\n".join(ev)


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
    home = _home(tmp_path, text, report=_report({"Pro": pp._canon_blocks(text)}))
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
    assert "ignoring: Pro" in ev[0]


def test_every_peer_quiet_reads_UNPROBEABLE_not_agreement(tmp_path: Path) -> None:
    mine = _doc(("cost", "Authorized keys only."))
    now = time.time()
    report = {
        "machines": {"Pro": pp._canon_blocks(mine)},
        "seen_at": {"Pro": now - 40 * 24 * 3600},
    }
    status, _n, ev = _probe(_home(tmp_path, mine, report=report), max_age_min=1440)
    assert status == pp.UNPROBEABLE
    assert "nothing to compare against" in ev[0]


def test_a_fresh_peer_is_still_compared(tmp_path: Path) -> None:
    """Innocence for the same rule: the freshness filter must not become a way to
    drop the finding along with the peer."""
    mine = _doc(("cost", "Authorized keys only."))
    theirs = _doc(("cost", "Zero paid API keys. Period."))
    report = {
        "machines": {"Pro": pp._canon_blocks(theirs)},
        "seen_at": {"Pro": time.time()},
    }
    status, n, _ev = _probe(_home(tmp_path, mine, report=report), max_age_min=1440)
    assert status == pp.DIVERGED and n == 1


def test_a_report_without_seen_at_still_compares(tmp_path: Path) -> None:
    """Back-compat: a report written before this field existed must not read as
    'every peer is quiet'. The whole-report age still governs it."""
    mine = _doc(("cost", "Authorized keys only."))
    theirs = _doc(("cost", "Zero paid API keys. Period."))
    status, n, _ev = _probe(
        _home(tmp_path, mine, report=_report({"Pro": pp._canon_blocks(theirs)}))
    )
    assert status == pp.DIVERGED and n == 1


def test_the_quiet_filter_matches_a_NAME_not_a_prefix_of_its_display_line(
    tmp_path: Path,
) -> None:
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
    assert status == pp.DIVERGED, (
        f"the fresh peer 'Air' was dropped along with 'Air M5': {ev}"
    )
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


def _publish(
    tmp: Path, claude_md: Path, report_dir: Path, extra: list[str] | None = None
):
    import subprocess
    import sys

    cmd = [
        sys.executable,
        str(_PUB),
        "--claude-md",
        str(claude_md),
        "--report-dir",
        str(report_dir),
        "--no-push",
        *(extra or []),
    ]
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
    assert not list(report.glob("*.json")), "refused, but wrote a fragment anyway"
    assert "reads as agreement" in r.stderr


def test_published_report_carries_digests_and_never_block_text(tmp_path: Path) -> None:
    """A report containing the text would be a FOURTH copy of the file, and the
    whole point of comparing is that there are three."""
    secretish = (
        "The session merges, arms and deploys, and this exact sentence must not travel."
    )
    src = tmp_path / "CLAUDE.md"
    src.write_text(_doc(("ship", secretish)))
    report = tmp_path / "canon-blocks.json"
    r = _publish(tmp_path, src, report)
    assert r.returncode == 0, r.stdout + r.stderr
    raw = "".join(f.read_text() for f in report.glob("*.json"))
    assert "must not travel" not in raw
    assert json.loads(raw)["blocks"] == pp._canon_blocks(src.read_text())


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
    published = json.loads(next(report.glob("*.json")).read_text())["blocks"]
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


# --- the adversarial round: eleven ways this said "agreed" and meant nothing ---
# All confirmed on disk before being fixed (Codex sol, blind on the diff,
# 2026-08-31). Each of these is a state the probe reached BEFORE the fix.


def test_a_report_holding_ONLY_this_machine_is_not_fleet_agreement(
    tmp_path: Path,
) -> None:
    """The report is merged, so it contains an entry for the machine reading it.
    Left in the peer set, a report holding only this machine read as '1 canon
    block identical across 1 machine' — zero peers masquerading as agreement,
    which is the exact disease this organ exists to detect."""
    text = _doc(("ship", "rule"))
    report = _report({"TestRunner": pp._canon_blocks(text)})
    status, _n, ev = _probe(_home(tmp_path, text, report=report))
    assert status == pp.UNPROBEABLE, ev
    assert "no peer" in ev[-1]


def test_a_stale_SELF_entry_is_named_as_local_not_as_fleet_drift(
    tmp_path: Path,
) -> None:
    """Saying 'differs from <this machine>' sends a reader to look at the other
    machines, where nothing is wrong. The cause is local — this machine edited
    its doctrine and did not republish — and so is the remedy."""
    local = _doc(("ship", "the NEW rule"))
    published = _doc(("ship", "the OLD rule"))
    peer = _doc(("ship", "the NEW rule"))
    report = _report(
        {"TestRunner": pp._canon_blocks(published), "Pro": pp._canon_blocks(peer)}
    )
    status, _n, ev = _probe(_home(tmp_path, local, report=report))
    assert status == pp.DIVERGED
    joined = "\n".join(ev)
    assert "own published snapshot is out of date" in joined
    assert "canon_blocks_publish.py" in joined
    assert "differs from TestRunner" not in joined


def test_an_unstamped_peer_is_unverifiable_not_fresh(tmp_path: Path) -> None:
    """Without a per-machine stamp, an entry is trusted at whatever age it
    happens to be — and touching or republishing the container file revives an
    arbitrarily stale peer while the file's own mtime looks new."""
    text = _doc(("ship", "rule"))
    report = {"machines": {"Pro": pp._canon_blocks(text)}, "seen_at": {}}
    status, _n, ev = _probe(_home(tmp_path, text, report=report))
    assert status == pp.UNPROBEABLE
    assert "no usable seen_at stamp" in "\n".join(ev)


def test_a_close_marker_QUOTED_IN_PROSE_does_not_end_the_block(tmp_path: Path) -> None:
    """A doctrine file that documents its own markers is exactly the file where
    this happens. Recognising a marker mid-line let everything after that
    sentence leave the comparison silently — measured: two files that differ
    after such a line hashed IDENTICALLY."""
    a = "<!-- CANON:x -->\nsame\nprose <!-- /CANON:x --> LOCAL\nlocal drift\n"
    b = "<!-- CANON:x -->\nsame\nprose <!-- /CANON:x --> PEER\npeer drift\n"
    assert pp._canon_blocks(a) != pp._canon_blocks(b)


def test_a_duplicated_block_id_does_not_hide_the_earlier_one(tmp_path: Path) -> None:
    """Last-wins made drift in every occurrence but the last invisible."""
    a = _doc(("x", "local-drift"), ("x", "shared"))
    b = _doc(("x", "peer-drift"), ("x", "shared"))
    assert pp._canon_blocks(a) != pp._canon_blocks(b)
    assert any(k.endswith("!duplicate") for k in pp._canon_blocks(a))


def test_malformed_canon_is_a_finding_even_when_every_machine_agrees(
    tmp_path: Path,
) -> None:
    """Two machines carrying the SAME malformed marker is not fleet health. It is
    also the cheapest way to remove a block from comparison without deleting
    it — so agreement must not launder it."""
    text = "<!-- CANON:ship -->\nrule\n"  # never closed
    report = _report({"Pro": pp._canon_blocks(text)})
    status, n, ev = _probe(_home(tmp_path, text, report=report))
    assert status == pp.DIVERGED, ev
    assert n >= 1
    assert "malformed here (unclosed)" in "\n".join(ev)


def test_a_report_of_the_wrong_SHAPE_is_refused_not_traversed(tmp_path: Path) -> None:
    """Reading it optimistically raised AttributeError inside the enclosing
    proprioception run, which turns one malformed file into a dead report for
    every other boundary too."""
    text = _doc(("ship", "rule"))
    report = {"machines": {"Pro": "not-a-block-map"}, "seen_at": {"Pro": time.time()}}
    status, _n, ev = _probe(_home(tmp_path, text, report=report))
    assert status == pp.UNPROBEABLE
    assert "wrong shape" in "\n".join(ev)


def test_the_remote_destination_is_a_TILDE_not_this_machine_s_absolute_path() -> None:
    """M5's home is /Users/balizero and Pro's is /Users/nuzantara. Reusing the
    local absolute path publishes to a location the remote probe never reads:
    the file lands, scp reports success, and every machine keeps comparing
    against nothing."""
    src = _PUB.read_text()
    assert 'f"{host}:{remote}"' in src
    assert "{host}:{str(args.report" not in src
    assert 'remote = f"~/.claude/canon-blocks.d/{me}.json"' in src


def test_published_fragment_reaches_final_path_by_atomic_replace(
    tmp_path: Path, monkeypatch
) -> None:
    """A reader must never see a fragment between truncate and completed write:
    that transient invalid JSON makes a healthy guard report itself unreadable.

    The publisher is imported so the filesystem boundary can be observed
    deterministically; a subprocess would require a timing race and eventually
    turn this protection into a flaky, slow test. The final file must be
    produced by replacing it with the fully written temporary file, not by
    writing the final path directly.
    """
    spec = importlib.util.spec_from_file_location("canon_blocks_publish_test", _PUB)
    assert spec and spec.loader
    publisher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(publisher)

    src = tmp_path / "CLAUDE.md"
    src.write_text(_doc(("ship", "The session merges, arms and deploys.")))
    report_dir = tmp_path / "canon-blocks.d"
    final_path = report_dir / "AtomicHost.json"
    tmp_fragment = report_dir / "AtomicHost.json.tmp"

    # BOTH rename primitives are recorded, not just `Path.replace`. Pinning one
    # method name checks the FORM: `os.replace(tmp, path)` is an equally correct
    # atomic commit and would have failed this test (measured — the conducting
    # session mutated the publisher to it and watched this test go red on
    # working code). What must hold is that the fragment arrives by a RENAME,
    # whichever call performs it.
    real_replace = Path.replace
    real_os_replace = os.replace
    replacements: list[tuple[Path, Path]] = []

    def record_replace(path: Path, target: Path) -> Path:
        replacements.append((Path(path), Path(target)))
        return real_replace(path, target)

    def record_os_replace(src, dst, **kw):
        replacements.append((Path(src), Path(dst)))
        return real_os_replace(src, dst, **kw)

    written_paths: list[Path] = []
    real_write_text = Path.write_text

    def record_write(path: Path, *a, **kw):
        written_paths.append(Path(path))
        return real_write_text(path, *a, **kw)

    monkeypatch.setattr(Path, "write_text", record_write)
    monkeypatch.setattr(Path, "replace", record_replace)
    monkeypatch.setattr(os, "replace", record_os_replace)
    rc = publisher.main(
        [
            "--claude-md",
            str(src),
            "--report-dir",
            str(report_dir),
            "--machine",
            "AtomicHost",
            "--no-push",
        ]
    )

    assert rc == 0
    # MEMBERSHIP, not exact-list equality: `Path.replace` is itself implemented
    # on `os.replace`, so recording both primitives sees ONE rename twice. An
    # equality assertion counts calls, which is an implementation detail; what
    # must hold is that the fragment arrived at its final path by a rename from
    # the temporary one.
    assert (tmp_fragment, final_path) in replacements, (
        "the final fragment was not committed by renaming the fully written "
        f"temporary file into place (renames seen: {replacements})"
    )
    assert json.loads(final_path.read_text())["machine"] == "AtomicHost"
    assert not tmp_fragment.exists(), "successful publish left temporary residue"
    # GRADER'S AMENDMENT (the build lane did not write this; the conducting
    # session did, reviewing work it had not authored). The assertion above pins
    # the MECHANISM — that `Path.replace` was the call used — so a correct
    # refactor to `os.replace(tmp, path)` would fail it while preserving every
    # property that matters. Below is the PROPERTY itself, stated
    # implementation-agnostically: whatever the scheme, the final path must
    # never be written into directly, because that write is the window in which
    # a reader sees invalid JSON. This is the difference between checking a form
    # and checking an entity, which is the family this repo is bitten by most.
    assert final_path not in written_paths, (
        f"the final fragment was written into DIRECTLY ({written_paths}); "
        "any atomic scheme writes elsewhere and renames, so a direct write to "
        "the path readers poll is the partial-read window itself"
    )
    assert tmp_fragment in written_paths, (
        "premise: the temporary file must be the thing written"
    )


# --- the second adversarial round: two ways this said nothing and meant it ---
# Both named by the conductor after an independent read, both reproduced on disk
# before being touched (2026-08-31): `<!-- canon:x -->` parsed to zero blocks
# without being flagged, and a marker shown inside a fenced code block became a
# live comparable block. The wave had already produced the fenced-example defect
# once (L10-PR1 finding #2), which makes it a pattern rather than a slip.


def test_a_MISCASED_marker_is_a_finding_not_silence(tmp_path: Path) -> None:
    """An operator who marks a block and gets the case wrong used to get nothing
    at all: zero blocks, no malformed key, and a machine indistinguishable from
    one where the doctrine is genuinely ABSENT. The wrong spelling is refused —
    accepting it would let `canon:ship` and `CANON:ship` name two different
    blocks under one id — but it is refused OUT LOUD."""
    text = "<!-- canon:ship -->\nthe rule\n<!-- /canon:ship -->\n"
    blocks = pp._canon_blocks(text)
    assert blocks, "a mis-cased marker parsed to nothing at all"
    assert any(k.endswith("!miscased") for k in blocks), blocks
    assert "ship" not in blocks, "the wrong spelling must not become a real block"

    # And it reaches the operator: malformed is a finding even when the whole
    # fleet carries the same typo.
    report = _report({"Pro": blocks})
    status, n, ev = _probe(_home(tmp_path, text, report=report))
    assert status == pp.DIVERGED, ev
    assert "malformed here (miscased)" in "\n".join(ev), ev


def test_correct_case_is_untouched_by_the_miscase_rule(tmp_path: Path) -> None:
    """Innocence: the fix must not make an ordinary, correctly-spelled file
    malformed. Without this, 'miscased is a finding' could be satisfied by a
    parser that flags everything."""
    blocks = pp._canon_blocks(_doc(("ship", "the rule")))
    assert blocks == {"ship": blocks["ship"]}, blocks
    assert not any(pp._is_malformed(k) for k in blocks), blocks


def test_a_marker_SHOWN_IN_A_FENCE_is_an_example_not_a_block(tmp_path: Path) -> None:
    """A doctrine file that documents its own markers shows them in a code
    fence. Parsing those granted a live, comparable ceiling to a piece of
    documentation — and the id would then read as ABSENT on any machine whose
    docs word the example differently."""
    fenced = (
        "# Doctrine\n\nMark a canon region like this:\n\n"
        "```markdown\n<!-- CANON:example -->\n...doctrine...\n<!-- /CANON:example -->\n```\n"
    )
    assert pp._canon_blocks(fenced) == {}, "a fenced example became a real block"

    # Non-vacuity: the same text outside a fence DOES produce a block, so the
    # empty result above is the fence's doing and not the fixture being inert.
    assert pp._canon_blocks(fenced.replace("```markdown\n", "").replace("```\n", ""))


def test_a_REAL_block_beside_a_fenced_example_survives(tmp_path: Path) -> None:
    """The dangerous shape is not the degenerate one. A file with one real block
    AND one fenced example must yield exactly the real block — suppressing both
    would be an over-match cure for an under-match defect."""
    text = (
        "<!-- CANON:real -->\nreal doctrine\n<!-- /CANON:real -->\n\n"
        "```\n<!-- CANON:fake -->\nan example\n<!-- /CANON:fake -->\n```\n"
    )
    blocks = pp._canon_blocks(text)
    assert set(blocks) == {"real"}, blocks


def test_a_fence_INSIDE_a_block_is_body_not_a_wall(tmp_path: Path) -> None:
    """A canon block whose doctrine contains a code sample must still close, and
    the sample must still be part of what is hashed — a fenced region's CONTENT
    is content, it is only the MARKUP recognition that is suppressed."""

    def doc(sample: str) -> str:
        return (
            f"<!-- CANON:r -->\nintro\n```sh\n{sample}\n```\noutro\n<!-- /CANON:r -->\n"
        )

    a, b = pp._canon_blocks(doc("run --safe")), pp._canon_blocks(doc("run --unsafe"))
    assert set(a) == {"r"}, a  # it closed: not '!unclosed'
    assert a != b, "drift inside the fenced sample was not hashed"


def test_a_file_whose_markers_are_ALL_FENCED_says_so(tmp_path: Path) -> None:
    """'Nothing is marked' and 'you marked it inside a code block' need
    different remedies, and used to produce the same sentence."""
    text = "# Doctrine\n\n```\n<!-- CANON:x -->\nbody\n<!-- /CANON:x -->\n```\n"
    status, n, ev = _probe(_home(tmp_path, text))
    assert status == pp.UNPROBEABLE
    joined = "\n".join(ev)
    assert "inside fenced" in joined, joined
    assert "2 canon-shaped line" in joined, joined  # the open and the close


def test_an_ordinary_unmarked_file_is_NOT_told_about_fences(tmp_path: Path) -> None:
    """Innocence for the message: a file with no canon-shaped lines at all must
    get the plain 'nothing is declared canon yet', with no fence advice bolted
    on to confuse an operator who has no fences."""
    status, n, ev = _probe(_home(tmp_path, "# Doctrine\n\nordinary prose\n"))
    assert status == pp.UNPROBEABLE
    assert "fenced" not in "\n".join(ev), ev
