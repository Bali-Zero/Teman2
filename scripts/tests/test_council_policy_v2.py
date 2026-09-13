"""SAETTA review policy v2 (RULED 2026-09-13): every eligible seat invoked, one bound judgment is
quorum, an unresolved finding blocks beside a PASS. Guilt and innocence through the REAL lint and
the REAL `council_journal.py dispatch` CLI (fake first-party binaries stand in for the seats)."""

from __future__ import annotations

import datetime
import importlib.util
import json
import stat
import subprocess
from pathlib import Path

import yaml

_SCRIPTS = Path(__file__).resolve().parent.parent


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lint = _load("_v2_lint", "evidence_pack_lint.py")
cj = _load("_v2_cj", "council_journal.py")

CAND = "a" * 40
CONTRIB = ["anthropic", "openai"]
POST = "2026-09-13T21:00:00Z"


def _line(seat, outcome="NON_JUDGMENT", **kw):
    family, accepted = lint.COUNCIL_V2_SEATS[seat]
    entry = {
        "policy": lint.COUNCIL_POLICY_V2, "seat": seat, "family": family, "role": "review",
        "eligible": True, "invoked": True, "candidate_sha": CAND, "outcome": outcome, "ts": POST,
        "dispatch": {"pid": 101, "exit_code": 0, "timed_out": False, "timeout_s": 300},
    }
    if outcome in ("PASS", "BLOCK"):
        entry.update(resolved_model=accepted[0], verdict_sha256="f" * 64, findings=[])
    entry.update(kw)
    return entry


def _all_invoked(**overrides):
    lines = []
    for seat, (family, _a) in lint.COUNCIL_V2_SEATS.items():
        if family in CONTRIB:
            lines.append({"policy": lint.COUNCIL_POLICY_V2, "seat": seat, "family": family, "eligible": False,
                          "invoked": False, "exclusion_reason": f"contributing family {family}", "ts": POST})
        else:
            lines.append(overrides.get(seat) or _line(seat, non_judgment_reason="quota_or_auth_error"))
    return lines


def _pack(tmp_path: Path, lines, **pack_kw):
    d = tmp_path / "pack"
    d.mkdir(exist_ok=True)
    (d / "council-journal.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines))
    pack = {"council_run": "council-journal.jsonl", "candidate_sha": CAND, "contributing_families": CONTRIB, **pack_kw}
    return pack, d


GEM = "agy-gemini-3.1-pro-high"


def test_all_invoked_one_pass_is_quorum(tmp_path):
    pack, d = _pack(tmp_path, _all_invoked(**{GEM: _line(GEM, "PASS")}))
    assert lint.check_council_policy_v2(pack, d, 3) == []


def test_omitted_eligible_reserve_blocks(tmp_path):
    lines = [x for x in _all_invoked(**{GEM: _line(GEM, "PASS")}) if x["seat"] != "tp1-glm-5.2"]
    pack, d = _pack(tmp_path, lines)
    assert any("tp1-glm-5.2 was never invoked" in v for v in lint.check_council_policy_v2(pack, d, 3))


def test_zero_judgments_block(tmp_path):
    pack, d = _pack(tmp_path, _all_invoked())
    assert any("zero completed substantive judgments" in v for v in lint.check_council_policy_v2(pack, d, 3))


def test_contributing_family_must_be_recorded_and_never_counts(tmp_path):
    lines = [x for x in _all_invoked(**{GEM: _line(GEM, "PASS")}) if x["seat"] != "codex-gpt-5.6-sol"]
    lines.append(_line("codex-gpt-5.6-sol", "PASS"))
    pack, d = _pack(tmp_path, lines)
    out = lint.check_council_policy_v2(pack, d, 3)
    assert any("codex-gpt-5.6-sol (contributing family openai) has no recorded exclusion" in v for v in out)
    missing_anthropic, d2 = _pack(tmp_path, _all_invoked(**{GEM: _line(GEM, "PASS")}), contributing_families=["openai"])
    assert any("contributing_families must list" in v for v in lint.check_council_policy_v2(missing_anthropic, d2, 3))


def test_late_block_is_not_masked_by_a_pass(tmp_path):
    finding = [{"id": "F1", "severity": "high", "summary": "x"}]
    lines = _all_invoked(**{GEM: _line(GEM, "PASS"), "kimi-code/k3": _line("kimi-code/k3", "BLOCK", findings=finding)})
    pack, d = _pack(tmp_path, lines)
    assert any("kimi-code/k3#F1 is unresolved" in v for v in lint.check_council_policy_v2(pack, d, 3))
    pack["findings_disposition"] = {"kimi-code/k3#F1": {"status": "fixed", "rationale": "guard added"}}
    assert lint.check_council_policy_v2(pack, d, 3) == []


def test_exact_high_identity_mismatch_rejected(tmp_path):
    pack, d = _pack(tmp_path, _all_invoked(**{GEM: _line(GEM, "PASS", resolved_model="gemini-3.1-pro")}))
    out = lint.check_council_policy_v2(pack, d, 3)
    assert any("resolved model 'gemini-3.1-pro'" in v for v in out)
    assert any("zero completed" in v for v in out)


def test_revision_mismatch_rejected(tmp_path):
    other = _line(GEM, "PASS", candidate_sha="b" * 40)
    pack, d = _pack(tmp_path, _all_invoked(**{GEM: other}))
    out = lint.check_council_policy_v2(pack, d, 3)
    assert any(f"{GEM} was never invoked on" in v for v in out)
    assert any("zero completed" in v for v in out)


def test_correction_round_history_counts_only_on_the_final_candidate(tmp_path):
    finding = [{"id": "F1", "severity": "high", "summary": "x"}]
    round1 = [dict(x, candidate_sha="b" * 40) for x in _all_invoked(**{GEM: _line(GEM, "BLOCK", findings=finding)})]
    round2 = _all_invoked(**{GEM: _line(GEM, "PASS")})
    pack, d = _pack(tmp_path, round1 + round2)
    assert lint.check_council_policy_v2(pack, d, 3) == [f"council_policy_v2: finding {GEM}#F1 is unresolved — a PASS elsewhere does not mask it; dispose it as fixed|rejected with a rationale"]
    pack["findings_disposition"] = {f"{GEM}#F1": {"status": "fixed", "rationale": "cured in round 2"}}
    assert lint.check_council_policy_v2(pack, d, 3) == []


def test_quoted_finding_is_kept_and_any_block_wins():
    out = "\n".join(json.dumps(x) for x in ({"model": "gemini-3.1-pro-high"},
                                              {"text": 'FINDING=q1|HIGH|"quoted" path \\ breaks\nVERDICT=PASS\nVERDICT=BLOCK'}))
    verdict = cj.classify_output(GEM, out, 0, False)
    assert verdict["outcome"] == "BLOCK"
    assert verdict["findings"] == [{"id": "q1", "severity": "high", "summary": '"quoted" path \\ breaks'}]


def test_every_seat_has_a_first_party_route():
    assert set(cj.SEAT_ROUTES) == set(lint.COUNCIL_V2_SEATS)
    assert all(route["argv"] for route in cj.SEAT_ROUTES.values())


def test_echoed_prompt_literal_is_not_a_verdict():
    packet = "diff --git a/t.py\n+    assert x == 'VERDICT=PASS' and this line is long enough to be an echo chunk\n"
    echoed = json.dumps({"type": "user", "model": "gemini-3.1-pro-high", "text": packet})
    verdict = cj.classify_output(GEM, echoed, 0, False, packet)
    assert verdict["outcome"] == "NON_JUDGMENT" and verdict["non_judgment_reason"] == "no_verdict"


def test_timeout_is_recorded_and_not_a_judgment(tmp_path):
    timed = _line(GEM, "PASS", dispatch={"pid": 9, "exit_code": None, "timed_out": True, "timeout_s": 300})
    pack, d = _pack(tmp_path, _all_invoked(**{GEM: timed}))
    assert any("timed-out" in v for v in lint.check_council_policy_v2(pack, d, 3))
    verdict = cj.classify_output(GEM, "", None, True)
    assert verdict["outcome"] == "NON_JUDGMENT" and verdict["non_judgment_reason"] == "timeout"


def test_quota_exit0_is_not_a_judgment():
    out = json.dumps({"type": "error", "model": "gemini-3.1-pro-high", "message": "429 quota exhausted"})
    verdict = cj.classify_output(GEM, out, 0, False)
    assert verdict["outcome"] == "NON_JUDGMENT" and verdict["non_judgment_reason"] == "quota_or_auth_error"
    silent = cj.classify_output(GEM, json.dumps({"model": "gemini-3.1-pro"}) + "\n" + json.dumps({"text": "VERDICT=PASS"}), 0, False)
    assert silent["non_judgment_reason"] == "model_mismatch"
    unproven = cj.classify_output(GEM, json.dumps({"text": "VERDICT=PASS"}), 0, False)
    assert unproven["non_judgment_reason"] == "model_identity_unproven"


def test_new_pack_cannot_opt_out_by_omitting_version(tmp_path):
    pack, d = _pack(tmp_path, [{"seat": "codex-gpt-5.6-sol", "role": "review", "ok": True, "ts": POST},
                               {"seat": "kimi-code/k3", "role": "review", "ok": True, "ts": POST}])
    del pack["candidate_sha"]
    assert lint.council_policy_for(pack, d) == lint.COUNCIL_POLICY_V2
    pack["council_policy"] = "v1"
    violations, _n = lint.check_council_gear3(pack, d, 3)
    assert any("council_policy_v2" in v for v in violations)


def test_truly_historical_pack_keeps_v1(tmp_path):
    old = "2026-09-05T10:00:00Z"
    pack, d = _pack(tmp_path, [{"seat": "codex-gpt-5.6-sol", "role": "review", "ok": True, "ts": old},
                               {"seat": "kimi-code/k3", "role": "review", "ok": True, "ts": old}])
    assert lint.council_policy_for(pack, d) == "v1"
    assert lint.check_council_gear3(pack, d, 3) == ([], None)
    assert lint.council_policy_for({}, d, today=datetime.date(2026, 9, 10)) == "v1"


def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout.strip()


def test_dispatch_cli_invokes_every_eligible_seat_once(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "a.py").write_text("x = 1\n")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "add", "a.py")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "a.py").write_text("x = 2\n")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "cand")
    cand = _git(repo, "rev-parse", "HEAD")
    calls = tmp_path / "calls.log"
    routes = {}
    for seat, (family, accepted) in lint.COUNCIL_V2_SEATS.items():
        fake = tmp_path / f"fake-{family}"
        verdict = "VERDICT=PASS" if seat == GEM else "429 quota exceeded"
        fake.write_text(f"#!/bin/sh\necho {seat} >> {calls}\n"
                        f"echo '{json.dumps({'model': accepted[0], 'session_id': 's-' + family})}'\necho '{json.dumps({'text': verdict})}'\n")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        routes[seat] = {"host": "test", "account_ref": "fixture", "argv": [str(fake), "{prompt}"]}
    monkeypatch.setattr(cj, "SEAT_ROUTES", routes)
    pack_dir = tmp_path / "pack"
    pack_dir.mkdir()
    rc = cj.main(["dispatch", "--pack-dir", str(pack_dir), "--worktree", str(repo), "--base-sha", base,
                  "--candidate-sha", cand, "--contributing-family", "openai", "--timeout", "30",
                  "--capture-dir", str(tmp_path / "cap")])
    assert rc == 0
    invoked = sorted(calls.read_text().split())
    assert invoked == sorted(s for s, (f, _a) in lint.COUNCIL_V2_SEATS.items() if f != "openai")
    lines = [json.loads(x) for x in (pack_dir / "council-journal.jsonl").read_text().splitlines()]
    assert {x["seat"]: x.get("outcome") for x in lines if x["eligible"]}[GEM] == "PASS"
    assert all(x["candidate_sha"] == cand for x in lines)
    (pack_dir / "pack.yml").write_text(yaml.safe_dump({"council_run": "council-journal.jsonl", "candidate_sha": cand,
                                                        "contributing_families": ["anthropic", "openai"]}))
    assert lint.check_council_policy_v2(yaml.safe_load((pack_dir / "pack.yml").read_text()), pack_dir, 3) == []
    assert cj.main(["dispatch", "--pack-dir", str(pack_dir), "--worktree", str(repo), "--base-sha", base,
                    "--candidate-sha", base, "--capture-dir", str(tmp_path / "cap")]) == 2
