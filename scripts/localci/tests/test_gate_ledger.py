"""B25-prime P1 (docs/specs/localci-sovereign-2026-10-07.md, 2b.2 and 2b.3 tier TB): the gate-verdict ledger, its one reader rule and its writer.

TB runs `gate_verdict` over every ledger of 0..3 lines drawn from 13 atoms (2 380 files) against an ORACLE written here from the spec
text, importing nothing from gate_ledger, and then the file states, the bad arguments, and the writer's guilt and innocence rows."""
from __future__ import annotations

import ast
import base64
import hashlib
import itertools
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from . import fixture_repo  # noqa: F401 - the package import path the other localci tests use
from .. import gate_ledger as gl

ROOT = Path(__file__).resolve().parents[3]
R = "Bali-Zero/Teman2"
H = hashlib.sha1(b"candidate head").hexdigest()
BASE = hashlib.sha1(b"base").hexdigest()
OTHER = hashlib.sha1(b"another pr head").hexdigest()
ONE_OFF = H[:-1] + ("0" if H[-1] != "0" else "1")   # shares 39 of 40 characters with H: kills every prefix match
TS = "2026-10-15T10:00:00Z"


def entry(**kw):
    e = dict(v=1, ts=TS, repo=R, pr=7, head_sha=H, verdict="success", gate_session="g", evidence_sha256=None, supersedes=None, via="local")
    e.update(kw)
    return e


def line(e) -> bytes:
    return json.dumps(e, separators=(",", ":")).encode()


def dg(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


# atom -> (builder(previous lines) -> raw bytes, the oracle's view: (counts, verdict, names_index) )
ATOMS = ("S", "F", "S*", "Ss", "Sx", "Sb", "Sh", "Sp", "Sr", "Su", "Sc", "T", "J")
BAD_ATOMS = {"Sp", "Su", "Sc", "T", "J"}   # each fails the schema, so the ledger is unreadable for EVERY head
RANDOM_DIGEST = dg(b"a digest naming no line")


def build(atoms):
    """-> (ledger bytes, [(atom, success?, index of the failure it names or None)])"""
    raws, meta = [], []
    for pos, atom in enumerate(atoms):
        names = None
        if atom == "S*":   # supersedes the latest failure of this head written so far, else nothing
            prior = [i for i, (a, _, _) in enumerate(meta) if a == "F"]
            names = prior[-1] if prior else None
        e = lambda **kw: entry(gate_session=f"p{pos}", **kw)   # one distinct line per position, so a digest names one line
        raws.append({
            "S": lambda: line(e()), "F": lambda: line(e(verdict="failure")),
            "S*": lambda: line(e(supersedes=dg(raws[names]) if names is not None else None)),
            "Ss": lambda: line(e(supersedes=RANDOM_DIGEST)), "Sx": lambda: line(e(head_sha=ONE_OFF)),
            "Sb": lambda: line(e(head_sha=BASE)), "Sh": lambda: line(e(head_sha=OTHER, pr=8)),
            "Sp": lambda: line(e(head_sha=H[:12])), "Sr": lambda: line(e(repo="Bali-Zero/Other")),
            "Su": lambda: line(e(head_sha=H.upper())), "Sc": lambda: line(e(verdict="Success")),
            "T": lambda: line(e())[:60], "J": lambda: line({k: v for k, v in e().items() if k != "evidence_sha256"}),
        }[atom]())
        meta.append((atom, atom in ("S", "S*", "Ss"), names))
    return b"".join(r + b"\n" for r in raws), meta


def oracle(atoms, meta) -> bool:
    """2b.2 'Reader, one rule', from the spec text: a bad line anywhere is false for every head; the entries of this head only; the newest
    is a success; every earlier failure is named by a later entry of this head."""
    if any(a in BAD_ATOMS for a in atoms):
        return False
    mine = [i for i, a in enumerate(atoms) if a in ("S", "F", "S*", "Ss")]
    if not mine or not meta[mine[-1]][1]:
        return False
    return all(meta[i][1] or any(meta[j][2] == i for j in mine if j > i) for i in mine[:-1])


def write(path, data: bytes, mode=0o600):
    if os.path.lexists(path):
        os.unlink(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    os.write(fd, data)
    os.close(fd)
    os.chmod(path, mode)


@pytest.fixture
def ledger(tmp_path):
    d = tmp_path / "gate"
    d.mkdir(mode=0o700)
    return str(d / "verdicts.jsonl")


def test_tb_every_ledger_of_up_to_three_lines_reads_as_the_oracle_says(ledger):
    mismatches, n = [], 0
    for size in range(4):
        for atoms in itertools.product(ATOMS, repeat=size):
            data, meta = build(atoms)
            write(ledger, data)
            got, want = gl.gate_verdict(ledger, R, H)[0], oracle(atoms, meta)
            n += 1
            if got != want:
                mismatches.append(f"{','.join(atoms) or '(empty)'}: reader {got}, oracle {want}")
    assert n == 2380
    assert not mismatches, f"{len(mismatches)} mismatches, first 25:\n" + "\n".join(mismatches[:25])


@pytest.mark.parametrize("atoms,want", [
    (("S",), True), (("F", "S*"), True), (("F", "F", "S*"), False),   # one append per unsuperseded failure
    (("F", "S"), False), (("S", "F"), False), (("F", "Ss"), False), (("Sx", "Sb", "Sh"), False), (("S", "T"), False), (("S", "J"), False),
    (("S", "Sp"), False), (("S", "Su"), False), (("S", "Sc"), False), (("S", "Sr"), True), (("Sh",) * 3, False),
], ids=lambda v: ",".join(v) if isinstance(v, tuple) else str(v))
def test_tb_the_named_guilt_and_innocence_rows(ledger, atoms, want):
    data, meta = build(atoms)
    write(ledger, data)
    assert gl.gate_verdict(ledger, R, H)[0] is want is oracle(atoms, meta)


def test_tb_a_success_among_fifty_other_heads_entries_is_true(ledger):
    others = b"".join(line(entry(head_sha=hashlib.sha1(str(i).encode()).hexdigest(), pr=i + 1)) + b"\n" for i in range(50))
    write(ledger, others + line(entry()) + b"\n")
    assert gl.gate_verdict(ledger, R, H) == (True, "ok")


def test_tb_a_file_state_that_is_not_a_private_regular_file_is_false(ledger, tmp_path, monkeypatch):
    good = line(entry()) + b"\n"
    assert gl.gate_verdict(ledger, R, H)[0] is False and "missing" in gl.gate_verdict(ledger, R, H)[1]   # missing
    write(ledger, b"")
    assert gl.gate_verdict(ledger, R, H)[0] is False   # empty: no entry for the head
    real = tmp_path / "real.jsonl"
    write(str(real), good)
    os.unlink(ledger)
    os.symlink(real, ledger)
    assert gl.gate_verdict(ledger, R, H)[0] is False   # a symlink, though its target is a good private ledger
    os.unlink(ledger)
    write(ledger, good, mode=0o644)
    assert gl.gate_verdict(ledger, R, H)[0] is False   # group/other readable
    write(ledger, good, mode=0o640)
    assert gl.gate_verdict(ledger, R, H)[0] is False
    write(ledger, good)
    assert gl.gate_verdict(ledger, R, H)[0] is True
    monkeypatch.setattr(gl.os, "geteuid", lambda: os.getuid() + 1)
    assert gl.gate_verdict(ledger, R, H)[0] is False   # another owner
    monkeypatch.undo()
    real_lstat = os.lstat
    monkeypatch.setattr(gl.os, "lstat", lambda p: os.stat_result((stat.S_IFIFO | 0o600, *real_lstat(p)[1:])))
    assert gl.gate_verdict(ledger, R, H)[0] is False   # a readable 0600 FIFO: candidate False, S_ISREG-disabled mutant True
    monkeypatch.undo()
    os.unlink(ledger)
    os.mkdir(ledger, 0o700)   # 0700: no group/other bit and our owner, so only the regular-file check can refuse it
    assert gl.gate_verdict(ledger, R, H)[0] is False   # a directory
    os.rmdir(ledger)
    write(ledger, good[:-1])
    assert gl.gate_verdict(ledger, R, H)[0] is False   # a valid line with no newline is a torn tail


@pytest.mark.parametrize("repo,head", [(R, ""), (R, H[:12]), (R, H.upper()), (R, None), (R, 123), ("", H), (None, H), (R, H + "0")])
def test_tb_a_bad_argument_is_false_even_with_a_matching_success(ledger, repo, head):
    write(ledger, line(entry(head_sha=H.upper())) + b"\n" + line(entry()) + b"\n")   # the upper-case twin makes this ledger unreadable
    assert gl.gate_verdict(ledger, repo, head)[0] is False
    write(ledger, line(entry()) + b"\n")
    assert gl.gate_verdict(ledger, repo, head)[0] is False


def test_the_reader_never_raises_on_junk_bytes(ledger):
    for junk in (b"\xff\xfe\n", b"\n", b"[]\n", b"null\n", b"{}\n", b'{"v":NaN}\n', b'{"v":1,"v":1}\n', b"\x00" * 10, b"{" * 5000 + b"\n", b"[" * 2000 + b"]" * 2000 + b"\n"):
        write(ledger, junk)
        assert gl.gate_verdict(ledger, R, H)[0] is False


# --- the writer ---------------------------------------------------------------------------------------------------------------

def client(**kw):
    d = dict(repo=R, pr=7, head_sha=H, verdict="success", gate_session="gate-session", evidence_sha256=None, supersedes=None)
    d.update(kw)
    return d


def b64(d) -> str:
    return base64.b64encode(json.dumps(d).encode()).decode()


NOW = 1_792_000_000.0


def test_the_writer_stamps_v_ts_and_via_and_creates_a_private_ledger(ledger, monkeypatch):
    monkeypatch.delenv("SSH_CONNECTION", raising=False)
    shutil.rmtree(os.path.dirname(ledger))
    (d,) = gl.append(ledger, b64(client()), now=NOW)
    raw = Path(ledger).read_bytes()
    assert d == dg(raw[:-1]) and raw.endswith(b"\n")
    e = json.loads(raw)
    assert (e["v"], e["ts"], e["via"], e["repo"], e["head_sha"]) == (1, "2026-10-14T17:46:40Z", "local", R, H)
    assert list(e) == list(gl.KEYS) and gl.validate(e) is None
    assert oct(os.stat(ledger).st_mode & 0o777) == "0o600" and oct(os.stat(os.path.dirname(ledger)).st_mode & 0o777) == "0o700"
    assert gl.gate_verdict(ledger, R, H)[0] is True


def test_via_is_measured_from_ssh_connection_and_a_malformed_one_is_refused(ledger, monkeypatch):
    monkeypatch.setenv("SSH_CONNECTION", "100.64.1.2 51515 100.64.9.9 22")
    gl.append(ledger, b64(client()))
    assert json.loads(Path(ledger).read_text())["via"] == "100.64.1.2"
    for bad in ("", "only-one", "a b c", "bad;host 1 2 3", "x" * 70 + " 1 2 3"):
        monkeypatch.setenv("SSH_CONNECTION", bad)
        with pytest.raises(ValueError, match="SSH_CONNECTION"):
            gl.append(ledger, b64(client(head_sha=OTHER)))
    assert len(Path(ledger).read_text().splitlines()) == 1


MALFORMED = {
    "repo-not-owner/name": dict(repo="Teman2"), "repo-three-parts": dict(repo="a/b/c"), "repo-int": dict(repo=5), "repo-space": dict(repo="a b/c"),
    "pr-zero": dict(pr=0), "pr-negative": dict(pr=-3), "pr-string": dict(pr="7"), "pr-bool": dict(pr=True), "pr-float": dict(pr=7.0),
    "head-short": dict(head_sha=H[:39]), "head-upper": dict(head_sha=H.upper()), "head-non-hex": dict(head_sha="g" * 40), "head-null": dict(head_sha=None),
    "verdict-pass": dict(verdict="PASS"), "verdict-case": dict(verdict="Success"), "verdict-empty": dict(verdict=""), "verdict-list": dict(verdict=["success"]),
    "session-81": dict(gate_session="x" * 81), "session-int": dict(gate_session=7),
    "evidence-63": dict(evidence_sha256="a" * 63), "evidence-upper": dict(evidence_sha256="A" * 64), "evidence-int": dict(evidence_sha256=7),
    "supersedes-short": dict(supersedes="b" * 63), "supersedes-non-hex": dict(supersedes="z" * 64),
    "client-ts": dict(ts=TS), "client-via": dict(via="10.0.0.1"), "client-v": dict(v=1), "client-extra-key": dict(admin=True),
}


@pytest.mark.parametrize("name", sorted(MALFORMED))
def test_the_writer_rejects_each_malformed_field_and_a_client_supplied_ts_or_via(ledger, name):
    write(ledger, line(entry(verdict="failure")) + b"\n")
    before = Path(ledger).read_bytes()
    with pytest.raises(ValueError):
        gl.append(ledger, b64(client(**MALFORMED[name])))
    assert Path(ledger).read_bytes() == before


@pytest.mark.parametrize("raw", ["", "not base64!!", base64.b64encode(b"not json").decode(), base64.b64encode(b"[]").decode(),
                                 base64.b64encode(b'{"repo":"a/b","repo":"a/b"}').decode(), base64.b64encode(b'{"pr":NaN}').decode(),
                                 base64.b64encode(json.dumps({k: v for k, v in client().items() if k != "pr"}).encode()).decode(),
                                 "QQ" * 3000], ids=["empty", "not-b64", "not-json", "array", "duplicate-key", "nan", "missing-key", "too-long"])
def test_the_writer_rejects_an_entry_that_is_not_base64_json_of_exactly_the_seven_keys(ledger, raw):
    with pytest.raises(ValueError):
        gl.append(ledger, raw)
    assert not os.path.exists(ledger)


def test_the_writer_never_alters_existing_bytes_and_refuses_a_tail_without_newline(ledger):
    gl.append(ledger, b64(client(verdict="failure")), now=NOW)
    first = Path(ledger).read_bytes()
    gl.append(ledger, b64(client(head_sha=OTHER, pr=8)), now=NOW + 5)
    assert Path(ledger).read_bytes().startswith(first) and Path(ledger).read_bytes().count(b"\n") == 2
    torn = Path(ledger).read_bytes() + b'{"v":1,"ts"'
    write(ledger, torn)
    with pytest.raises(OSError, match="newline"):
        gl.append(ledger, b64(client(head_sha=BASE, pr=9)))
    assert Path(ledger).read_bytes() == torn


def test_the_writer_refuses_a_symlink_a_loose_mode_and_another_owner(ledger, tmp_path, monkeypatch):
    real = tmp_path / "real.jsonl"
    write(str(real), b"")
    os.symlink(real, ledger)
    with pytest.raises(OSError):
        gl.append(ledger, b64(client()))
    os.unlink(ledger)
    write(ledger, b"", mode=0o644)
    with pytest.raises(gl.LedgerFile):
        gl.append(ledger, b64(client()))
    write(ledger, b"")
    monkeypatch.setattr(gl.os, "geteuid", lambda: os.getuid() + 1)
    with pytest.raises(gl.LedgerFile):
        gl.append(ledger, b64(client()))
    assert Path(ledger).read_bytes() == real.read_bytes() == b""


def test_an_identical_reappend_adds_no_line_but_an_older_twin_behind_a_later_verdict_does_not_count(ledger):
    a = gl.append(ledger, b64(client(verdict="failure")), now=NOW)
    assert gl.append(ledger, b64(client(verdict="failure", gate_session="another")), now=NOW + 9) == a
    assert len(Path(ledger).read_text().splitlines()) == 1
    gl.append(ledger, b64(client()), supersede=True, now=NOW + 10)
    assert len(Path(ledger).read_text().splitlines()) == 2
    gl.append(ledger, b64(client(verdict="failure")), now=NOW + 11)   # the same key as line 1, but a success is newest: it must append
    assert len(Path(ledger).read_text().splitlines()) == 3 and gl.gate_verdict(ledger, R, H)[0] is False


def test_supersede_names_one_unsuperseded_failure_per_append_and_is_idempotent(ledger):
    f1, f2 = (gl.append(ledger, b64(client(verdict="failure", evidence_sha256=c * 64)), now=NOW + i)[0] for i, c in enumerate("ab"))
    assert gl.gate_verdict(ledger, R, H)[0] is False
    out = gl.append(ledger, b64(client()), supersede=True, now=NOW + 5)
    assert len(out) == 2 and gl.gate_verdict(ledger, R, H)[0] is True
    lines = [json.loads(x) for x in Path(ledger).read_text().splitlines()]
    assert [x["supersedes"] for x in lines[2:]] == [f2, f1]   # newest first
    assert gl.append(ledger, b64(client()), supersede=True, now=NOW + 9) == [out[-1]]   # nothing left to name: the newest success stands
    assert len(Path(ledger).read_text().splitlines()) == 4
    gl.append(ledger, b64(client(head_sha=OTHER, pr=8)), supersede=True, now=NOW + 9)   # nothing to supersede on this head: a plain append
    assert json.loads(Path(ledger).read_text().splitlines()[-1])["supersedes"] is None
    with pytest.raises(ValueError, match="exclusive"):
        gl.append(ledger, b64(client(supersedes="c" * 64)), supersede=True)
    gl.append(ledger, b64(client(verdict="failure", head_sha=BASE, pr=9, evidence_sha256="d" * 64)), now=NOW)
    gl.append(ledger, b64(client(verdict="failure", head_sha=BASE, pr=9, evidence_sha256="e" * 64)), supersede=True, now=NOW)   # a failure names nothing
    assert json.loads(Path(ledger).read_text().splitlines()[-1])["supersedes"] is None


def test_supersede_finishes_what_a_partly_superseded_head_still_owes(ledger):
    f1, f2 = (gl.append(ledger, b64(client(verdict="failure", evidence_sha256=c * 64)), now=NOW + i)[0] for i, c in enumerate("ab"))
    gl.append(ledger, b64(client(supersedes=f2)), now=NOW + 5)   # a success naming only the newest failure: the head still reads false
    assert gl.gate_verdict(ledger, R, H)[0] is False
    assert len(gl.append(ledger, b64(client()), supersede=True, now=NOW + 6)) == 1
    assert json.loads(Path(ledger).read_text().splitlines()[-1])["supersedes"] == f1 and gl.gate_verdict(ledger, R, H)[0] is True


def test_a_supersede_counts_only_from_a_later_entry_of_the_same_head(ledger):
    fail = line(entry(verdict="failure", gate_session="f"))
    fwd = line(entry(gate_session="s0", supersedes=dg(fail)))   # written BEFORE the failure it names
    write(ledger, fwd + b"\n" + fail + b"\n" + line(entry(gate_session="s2")) + b"\n")
    assert gl.gate_verdict(ledger, R, H)[0] is False
    other_head = line(entry(head_sha=OTHER, pr=8, supersedes=dg(fail)))   # a LATER entry, but of another head
    write(ledger, fail + b"\n" + other_head + b"\n" + line(entry(gate_session="s2")) + b"\n")
    assert gl.gate_verdict(ledger, R, H)[0] is False
    write(ledger, fail + b"\n" + line(entry(gate_session="s1", supersedes=dg(fail))) + b"\n" + line(entry(gate_session="s2")) + b"\n")
    assert gl.gate_verdict(ledger, R, H)[0] is True


def test_pr_is_a_positive_int_or_null_and_a_null_pr_reads_like_any_other(ledger):
    (d,) = gl.append(ledger, b64(client(pr=None)), now=NOW)
    assert json.loads(Path(ledger).read_text())["pr"] is None and gl.gate_verdict(ledger, R, H)[0] is True
    assert gl.append(ledger, b64(client(pr=9)), now=NOW + 1) == [d]   # pr is not part of the identity: the same verdict, no new line


def test_a_repo_is_matched_exactly_and_case_is_the_callers_to_get_right(ledger):
    write(ledger, line(entry()) + b"\n")
    assert gl.gate_verdict(ledger, R, H)[0] is True and gl.gate_verdict(ledger, R.lower(), H)[0] is False


def test_supersede_does_not_name_a_failure_of_another_head_or_repo(ledger):
    gl.append(ledger, b64(client(verdict="failure", head_sha=OTHER, pr=8)), now=NOW)
    gl.append(ledger, b64(client(verdict="failure", repo="Bali-Zero/Other")), now=NOW)
    gl.append(ledger, b64(client()), supersede=True, now=NOW)
    assert json.loads(Path(ledger).read_text().splitlines()[-1])["supersedes"] is None and gl.gate_verdict(ledger, R, H)[0] is True


def test_a_short_write_is_truncated_away_and_raises(ledger, monkeypatch):
    gl.append(ledger, b64(client(verdict="failure")), now=NOW)
    before = Path(ledger).read_bytes()
    real = os.write
    monkeypatch.setattr(gl.os, "write", lambda fd, b: real(fd, b[:7]))
    with pytest.raises(OSError, match="short write"):
        gl.append(ledger, b64(client(head_sha=OTHER, pr=8)))
    monkeypatch.undo()
    assert Path(ledger).read_bytes() == before


def test_a_ledger_replaced_while_the_writer_waited_for_the_lock_is_refused(ledger, monkeypatch):
    gl.append(ledger, b64(client(verdict="failure")), now=NOW)
    real_flock = gl.fcntl.flock

    def swap(fd, op):
        real_flock(fd, op)
        if op == gl.fcntl.LOCK_EX:
            write(ledger + ".new", Path(ledger).read_bytes())
            os.replace(ledger + ".new", ledger)

    monkeypatch.setattr(gl.fcntl, "flock", swap)
    with pytest.raises(OSError, match="replaced"):
        gl.append(ledger, b64(client(head_sha=OTHER, pr=8)))


def test_concurrent_appenders_each_leave_one_whole_line(ledger):
    cmd = [sys.executable, "-I", str(ROOT / "scripts/localci/gate_ledger.py"), "--ledger", ledger, "append"]
    procs = [subprocess.Popen(cmd + [b64(client(head_sha=hashlib.sha1(bytes([i])).hexdigest(), pr=i + 1))], stdout=subprocess.PIPE) for i in range(12)]
    assert [p.wait(timeout=60) for p in procs] == [0] * 12
    assert len(gl.read_entries(ledger)) == 12
    assert {l.split()[0] for l in (p.stdout.read().decode() for p in procs)} == {dg(x.encode()) for x in Path(ledger).read_text().splitlines()}


def test_the_cli_appends_verifies_and_exits_non_zero_on_a_bad_entry(ledger):
    run = lambda *a: subprocess.run([sys.executable, "-I", str(ROOT / "scripts/localci/gate_ledger.py"), "--ledger", ledger, *a], capture_output=True, text=True)
    ok = run("append", b64(client()))
    assert ok.returncode == 0 and ok.stdout.strip() == dg(Path(ledger).read_bytes()[:-1])
    assert run("verify").returncode == 0
    bad = run("append", b64(client(ts=TS)))
    assert bad.returncode == 1 and "keys" in bad.stderr and len(Path(ledger).read_text().splitlines()) == 1


@pytest.mark.skipif(not os.path.exists("/usr/bin/python3"), reason="no system python")
def test_the_writer_runs_on_the_system_python_and_the_source_parses_as_3_9(ledger):
    src = (ROOT / "scripts/localci/gate_ledger.py").read_text()
    ast.parse(src, feature_version=(3, 9))
    proc = subprocess.run(["/usr/bin/python3", "-I", str(ROOT / "scripts/localci/gate_ledger.py"), "--ledger", ledger, "append", b64(client())],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert gl.gate_verdict(ledger, R, H)[0] is True


def test_verify_names_the_first_bad_line_and_the_directory_mode(ledger):
    write(ledger, line(entry()) + b"\n" + b"{torn\n" + line(entry(head_sha=OTHER)) + b"\n" + b"{also torn\n")
    rc, msg = gl.verify(ledger)
    assert rc == 1 and "line 2" in msg
    write(ledger, line(entry()) + b"\n")
    rc, msg = gl.verify(ledger)
    assert rc == 0 and "1 entries" in msg and "0600" in msg
    os.chmod(os.path.dirname(ledger), 0o755)
    assert gl.verify(ledger)[0] == 1
    os.chmod(os.path.dirname(ledger), 0o700)
    os.chmod(ledger, 0o644)
    assert gl.verify(ledger)[0] == 1


def test_quarantine_moves_one_bad_line_journalled_and_refuses_a_line_that_validates(ledger):
    good1, good2 = line(entry()) + b"\n", line(entry(head_sha=OTHER, pr=8)) + b"\n"
    write(ledger, good1 + b"{torn\n" + good2)
    assert gl.quarantine(ledger, 1)[0] == 2 and gl.quarantine(ledger, 3)[0] == 2   # a valid verdict is never moved: that would be an override
    assert gl.quarantine(ledger, 0)[0] == 2 and gl.quarantine(ledger, 9)[0] == 2
    assert Path(ledger).read_bytes() == good1 + b"{torn\n" + good2
    rc, msg = gl.quarantine(ledger, 2, now=NOW)
    assert rc == 0 and Path(ledger).read_bytes() == good1 + good2 and gl.verify(ledger)[0] == 0
    (rec,) = [json.loads(x) for x in (Path(ledger).parent / "verdicts.quarantine.jsonl").read_text().splitlines()]
    assert rec["line"] == 2 and base64.b64decode(rec["raw_b64"]) == b"{torn" and rec["sha256"] == dg(b"{torn") and rec["ts"] == "2026-10-14T17:46:40Z"
    assert oct(os.stat(Path(ledger).parent / "verdicts.quarantine.jsonl").st_mode & 0o777) == "0o600" and oct(os.stat(ledger).st_mode & 0o777) == "0o600"
    torn = b'{"v":1,"ts"'   # removing ANOTHER line must leave a torn tail torn: completing it with a newline could turn it into a verdict
    valid_tail = line(entry(head_sha=OTHER, pr=8, gate_session="t"))
    write(ledger, line(entry(verdict="failure")) + b"\n" + b"{junk\n" + valid_tail)
    assert gl.verify(ledger)[0] == 1 and gl.gate_verdict(ledger, R, OTHER)[0] is False
    assert gl.quarantine(ledger, 2)[0] == 0
    assert Path(ledger).read_bytes().endswith(valid_tail) and not Path(ledger).read_bytes().endswith(b"\n")
    assert gl.gate_verdict(ledger, R, OTHER)[0] is False   # still torn, still unreadable
    write(ledger, good1 + good1[:-1])   # a complete line with no newline is the torn tail, and may go
    assert gl.quarantine(ledger, 2)[0] == 0 and Path(ledger).read_bytes() == good1


def test_quarantine_refuses_a_replaced_ledger_and_short_writes(ledger, monkeypatch):
    good1, good2 = line(entry(verdict="failure")) + b"\n", line(entry(head_sha=OTHER, pr=8)) + b"\n"
    write(ledger, good1 + b"{torn\n" + good2)
    qpath = Path(ledger).parent / "verdicts.quarantine.jsonl"
    real_flock = gl.fcntl.flock

    def swap(fd, op):
        real_flock(fd, op)
        if op == gl.fcntl.LOCK_EX:
            write(ledger + ".new", good1 + b"{torn\n" + good2)
            os.replace(ledger + ".new", ledger)

    monkeypatch.setattr(gl.fcntl, "flock", swap)
    with pytest.raises(OSError, match="replaced"):
        gl.quarantine(ledger, 2, now=NOW)
    monkeypatch.undo()
    assert not qpath.exists() and Path(ledger).read_bytes() == good1 + b"{torn\n" + good2
    real_write = os.write
    calls = []

    def short_first(fd, b):
        calls.append(1)
        return real_write(fd, b[:5]) if len(calls) == 1 else real_write(fd, b)

    monkeypatch.setattr(gl.os, "write", short_first)
    with pytest.raises(OSError, match="short write"):
        gl.quarantine(ledger, 2, now=NOW)
    monkeypatch.undo()
    assert (not qpath.exists() or qpath.read_bytes() == b"") and Path(ledger).read_bytes() == good1 + b"{torn\n" + good2
    calls.clear()

    def short_second(fd, b):
        calls.append(1)
        return real_write(fd, b[:5]) if len(calls) == 2 else real_write(fd, b)

    monkeypatch.setattr(gl.os, "write", short_second)
    with pytest.raises(OSError, match="short write"):
        gl.quarantine(ledger, 2, now=NOW)
    monkeypatch.undo()
    assert Path(ledger).read_bytes() == good1 + b"{torn\n" + good2 and not list(Path(ledger).parent.glob("*.tmp-*"))


# --- the wrapper's gate-append mode -----------------------------------------------------------------------------------------------

WRAPPER = ROOT / "scripts/localci/localci_merger_tick.sh"


def mirror(tmp_path, with_code=True):
    repo = tmp_path / "state" / "repo.git"
    repo.mkdir(parents=True)
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    work = tmp_path / "work"
    subprocess.run(["git", "init", "-q", str(work)], check=True, env=env)
    (work / "scripts/localci").mkdir(parents=True)
    if with_code:
        shutil.copy2(ROOT / "scripts/localci/gate_ledger.py", work / "scripts/localci/gate_ledger.py")
    else:
        (work / "scripts/localci/other").write_text("x")
    subprocess.run(["git", "-C", str(work), "add", "-A"], check=True, env=env)
    subprocess.run(["git", "-C", str(work), "commit", "-qm", "m"], check=True, env=env)
    subprocess.run(["git", "clone", "-q", "--bare", str(work), str(repo)], check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "update-ref", "refs/merger/wrapper", "HEAD"], check=True, env=env)
    empty = subprocess.run(["git", "-C", str(repo), "commit-tree", "4b825dc642cb6eb9a060e54bf8d69288fbee4904", "-m", "empty"], check=True, env=env,
                           capture_output=True, text=True).stdout.strip()
    subprocess.run(["git", "-C", str(repo), "update-ref", "refs/merger/base", empty], check=True, env=env)   # the wrapper ref has the code, base does not
    return tmp_path / "state"


def gate_append(state, ledger, *args, ssh="100.64.1.2 1 100.64.9.9 22"):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("MERGER_", "GATE_", "LOCALCI_"))}
    env.update(MERGER_STATE_DIR=str(state), MERGER_PYTHON=sys.executable, GATE_LEDGER=ledger, SSH_CONNECTION=ssh)
    return subprocess.run(["/bin/bash", str(WRAPPER), "gate-append", *args], capture_output=True, text=True, env=env, timeout=60)


def test_the_wrapper_gate_append_runs_the_mirrors_code_and_appends_over_one_base64_argv(tmp_path, ledger):
    r = gate_append(mirror(tmp_path), ledger, b64(client()))
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == dg(Path(ledger).read_bytes()[:-1]) and json.loads(Path(ledger).read_text())["via"] == "100.64.1.2"
    assert gate_append(mirror(tmp_path / "again"), ledger, b64(client(verdict="failure")), "--supersede").returncode == 0   # success-only flag: ignored on a failure
    assert gl.gate_verdict(ledger, R, H)[0] is False


def test_the_wrapper_gate_append_fails_closed_without_a_mirror_a_ledger_module_or_a_good_entry(tmp_path, ledger):
    assert gate_append(tmp_path / "nowhere", ledger, b64(client())).returncode == 3
    assert gate_append(mirror(tmp_path / "x", with_code=False), ledger, b64(client())).returncode == 3
    good = mirror(tmp_path / "y")
    for bad in (b64(client(ts=TS)), "not base64!!", ""):
        assert gate_append(good, ledger, bad).returncode != 0
    assert gate_append(good, ledger).returncode != 0
    assert not os.path.exists(ledger)
    assert gate_append(good, ledger, b64(client()), ssh="garbage").returncode != 0


def test_no_file_under_dot_github_names_the_ledger_or_its_module():
    hits = [str(p.relative_to(ROOT)) for p in (ROOT / ".github").rglob("*") if p.is_file()
            and any(t in p.read_text(errors="replace") for t in ("gate_ledger", "verdicts.jsonl", "local-ci-gate"))]
    assert hits == []
