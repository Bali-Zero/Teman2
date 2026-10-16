"""B25-prime P3: merger half — one decision/retry predicate, gated by the Pro ledger, pinned by its oracle table (T1, T2, T2b, T2c, TI, MC/DC)."""
from __future__ import annotations

import argparse
import base64
import copy
import json
import os
import re
from pathlib import Path

import pytest

from . import b25_oracle as bo
from .test_merger import REPO, mg, pr, world  # noqa: F401 — `world` is a fixture
from .test_merger_phase_f import DOC, assert_nothing_merged, fw  # noqa: F401 — `fw` is a fixture
from .test_merger_pending import good, rows, watchdog_reset  # noqa: F401 — `watchdog_reset` is an autouse fixture

gl = mg.gl
H1, H2, B0, CAND = "a" * 40, "b" * 40, "c" * 40, "9" * 40
T0 = "2026-10-14T00:00:00Z"
EV = "e" * 64
_ABSENT = object()


def _b64(repo: str, head: str, verdict: str, pr_num: int | None = 1, supersedes: str | None = None) -> str:
    payload = {
        "repo": repo,
        "pr": pr_num,
        "head_sha": head,
        "verdict": verdict,
        "gate_session": "test-b25p3",
        "evidence_sha256": EV if verdict == "success" else None,
        "supersedes": supersedes,
    }
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def write_ledger_state(path: Path, state: str, head: str = H1, base: str = B0, cand: str = CAND, other_head: str = H2, repo: str = REPO) -> Path:
    """Materialize one of the 7 normative gate ledger states (S, N, F, U, O, Gh, SF) at ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        path.unlink()
    if state == "N":
        return path
    if state == "U":
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, b"{corrupt-json-line\n")
        finally:
            os.close(fd)
        return path
    if state == "Gh":
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.close(fd)
        return path
    if state == "S":
        gl.append(str(path), _b64(repo, head, "success"), now=1700000000)
    elif state == "F":
        gl.append(str(path), _b64(repo, head, "failure"), now=1700000000)
    elif state == "O":
        gl.append(str(path), _b64(repo, base, "success"), now=1700000000)
        gl.append(str(path), _b64(repo, cand, "success"), now=1700000001)
        gl.append(str(path), _b64(repo, other_head, "success"), now=1700000002)
        gl.append(str(path), _b64("other/repo", head, "success"), now=1700000003)
    elif state == "SF":
        gl.append(str(path), _b64(repo, head, "success"), now=1700000000)
        gl.append(str(path), _b64(repo, head, "failure"), now=1700000001)
    else:
        raise ValueError(f"unknown gate state {state!r}")
    return path


def doc(no_verdict="judge_rewritten_base_ok", verdict="BLOCKED"):
    d = copy.deepcopy(DOC)
    d["contexts"]["results"]["ctx-a"] = {
        "mapping": "executed",
        "verdict": verdict,
        "coverage": "full",
        **({"no_verdict": no_verdict} if no_verdict else {}),
    }
    return d


def two(other):
    d = doc()
    d["contexts"]["required"] = ["ctx-a", "ctx-b"]
    d["contexts"]["results"]["ctx-b"] = {"mapping": "executed", "coverage": "full", **other}
    return d


def three(c, **res):
    d = two({"verdict": "BLOCKED", "no_verdict": "judge_rewritten_base_ok"})
    d["contexts"]["required"] = ["ctx-a", "ctx-b", c]
    d["contexts"]["results"][c] = {"mapping": "executed", "coverage": "full", **res}
    return d


def enq(fw):
    return [r for r in fw.live() if r["kind"] == "would_enqueue" and not r.get("retry")][0]


# ------------------------------------------------------------------ §2b.3 AST check, HOST_KINDS pin, and MC/DC meta-test
def test_host_kinds_and_oracle_ast_and_mcdc_meta_test():
    assert bo.HOST_KINDS == set(mg.HOST_NO_VERDICT)
    bo.check_derived_ast()
    all_rows = bo.t2_rows() + bo.t2b_rows()
    pairs = bo.mcdc_pairs(all_rows)
    missing = sorted(set(bo.CONDS) - set(pairs))
    assert not missing, f"CONDS entries without an MC/DC independence pair in T2+T2b: {missing}"


# ------------------------------------------------------------------ §2b.3 T1: exhaustive local_side classification (~6.5k rows)
def test_t1_classification_product():
    verdicts = ("OK", "FAIL", "ERROR", "BLOCKED", "UNCOVERED", "STALE", "INTERRUPTED", _ABSENT, "not-a-dict")
    no_verdicts = (
        _ABSENT,
        "judge_rewritten_base_ok",
        "judge_rewritten",
        "gate_pending",
        "host_disk_full",
        "host_disk_full: x",
        "host_disk_below_floor",
        "host_disk_unmeasured (df)",
        "judge_rewritten_base_ok ",
        "JUDGE_REWRITTEN_BASE_OK",
        123,
    )
    mappings = ("executed", "blocked", "not_implemented")
    coverages = ("full", "partial")

    def build_res(v, nv, mp, cov):
        if v == "not-a-dict":
            return ["not-a-dict"]
        out = {"mapping": mp, "coverage": cov}
        if v is not _ABSENT:
            out["verdict"] = v
        if nv is not _ABSENT:
            out["no_verdict"] = nv
        return out

    singles = []
    for v in verdicts:
        for nv in no_verdicts:
            for mp in mappings:
                for cov in coverages:
                    tag = f"v={v!r},nv={nv!r},mp={mp},cov={cov}"
                    singles.append((tag, build_res(v, nv, mp, cov)))
    assert len(singles) == 594

    probes = {
        "NE": dict(bo.REPS["NE"]),
        "HOST": dict(bo.REPS["HB"]),
        "RESCUE": dict(bo.REPS["RS"]),
        "OK": dict(bo.REPS["OK"]),
        "RED": dict(bo.REPS["FA"]),
    }

    mismatches = []

    def check_doc(row_id: str, status_doc: dict) -> None:
        got = mg.local_side(status_doc)
        want = bo.local_oracle(status_doc)
        obs = {
            "executed_contexts_ok": got["why"]["executed_contexts_ok"] is None,
            "non_executed": got["non_executed"],
            "host_no_verdict": got["host_no_verdict"],
            "not_ok": got["not_ok"],
            "partial": got["partial"],
            "judge_rewritten_base_ok": got["judge_rewritten_base_ok"],
            "judge_gate_only": got["judge_gate_only"],
            "contexts_status": got["contexts_status"],
            "required_n": got["required_n"],
        }
        if obs != want:
            mismatches.append(f"{row_id}: got {obs} != want {want}")

    base_checks = {"c": {"status": "PASS"}, "review.independent": {"status": "QUEUED"}}
    for tag, res in singles:
        check_doc(f"T1:single:{tag}", {"checks": base_checks, "contexts": {"status": "ok", "required": ["ctx-a"], "results": {"ctx-a": res}}})
        for p_name, p_res in probes.items():
            check_doc(
                f"T1:pair:{tag}+{p_name}",
                {"checks": base_checks, "contexts": {"status": "ok", "required": ["ctx-a", "ctx-b"], "results": {"ctx-a": res, "ctx-b": p_res}}},
            )
            check_doc(
                f"T1:pair:{p_name}+{tag}",
                {"checks": base_checks, "contexts": {"status": "ok", "required": ["ctx-b", "ctx-a"], "results": {"ctx-b": p_res, "ctx-a": res}}},
            )

    for bad_status in ("error", "blocked", None, ""):
        check_doc(
            f"T1:ctx_status={bad_status!r}",
            {"checks": base_checks, "contexts": {"status": bad_status, "required": ["ctx-a"], "results": {"ctx-a": dict(bo.REPS["RS"])}}},
        )
    check_doc("T1:required_empty", {"checks": base_checks, "contexts": {"status": "ok", "required": [], "results": {}}})
    check_doc(
        "T1:non_str_required",
        {"checks": base_checks, "contexts": {"status": "ok", "required": [123, "ctx-a"], "results": {"ctx-a": dict(bo.REPS["RS"])}}},
    )
    assert not mismatches, f"{len(mismatches)} T1 mismatch(es):\n" + "\n".join(mismatches[:25])


# ------------------------------------------------------------------ §2b.3 T2 and T2b: fast harness over decision × retry
def _live_for(h_state: str, g_state: str, head: str = H1):
    if h_state == "x":
        return RuntimeError("hosted read failed")
    statuses = [{"context": mg.GATE_CONTEXT, "state": "success", "updated_at": T0}] if g_state == "Gh" else []
    verdict = "GREEN" if h_state == "g" else "PENDING"
    concl = "success" if verdict == "GREEN" else None
    st = "completed" if verdict == "GREEN" else "in_progress"
    return {
        "sha": head,
        "required_checks": [{"context": "c1", "app_id": None}],
        "check_runs": [{"id": 1, "name": "c1", "status": st, "conclusion": concl, "app": {"id": 1}, "completed_at": T0}],
        "statuses": statuses,
    }


def _run_fast_row(row: dict, state_dir: Path, ledgers: dict[str, Path], monkeypatch) -> tuple:
    now = mg.now()
    jpath = state_dir / "decisions.jsonl"
    if jpath.exists():
        jpath.unlink()
    a = argparse.Namespace(repo=REPO, base="main", gate_ledger=str(ledgers[row["G1"]]))

    def fake_pr_side(a_, st_, n_, head_, why_):
        why_["same_repo"] = None if row["same_repo1"] else "cross-repo"
        for t in bo.PR_TERMS:
            why_[t] = None if row["pr_terms1"][t] else f"{t} false"
        return {"pull_request_id": "PR_1", "live_head_oid": head_, "label_actor": "u", "bites": True}

    def fake_shadow(st_, repo_dir_, enq_, base_="main", a_=None, decision_=None):
        if enq_["ok"]:
            mg.journal(st_, {"kind": "merged", "ts": now, "pr": enq_["pr"], "head_sha": enq_["head_sha"], "base_sha": enq_["base_sha"]})
            return mg.journal(st_, {"kind": "pushed", "ts": now, "pr": enq_["pr"], "head_sha": enq_["head_sha"], "base_sha": enq_["base_sha"]})
        return mg.journal(
            st_,
            {
                "kind": "would_merge",
                "ts": now,
                "pr": enq_["pr"],
                "head_sha": enq_["head_sha"],
                "base_sha": enq_["base_sha"],
                "clean": True,
                "ok": False,
                "phase_f": {"armed": False, "why": ["disarmed"]},
                **({"retry": True, "decision_ts": enq_.get("decision_ts")} if enq_.get("retry") is True else {}),
            },
        )

    monkeypatch.setattr(mg, "pr_side", fake_pr_side)
    monkeypatch.setattr(mg, "merge_shadow_step", fake_shadow)
    monkeypatch.setattr(mg, "base_matrix", lambda *a_, **k_: None)
    monkeypatch.setattr(mg, "PENDING_RETRY_S", 0)

    checks = {
        "c": {"status": "PASS" if row["local_checks_clean"] else "FAIL"},
        "review.independent": {"status": "QUEUED" if row["review_independent"] else "FAIL"},
    }
    status_doc = {
        "overall": row["overall"],
        "checks": checks,
        "contexts": {"status": row["contexts_status"], "required": row["required"], "results": row["results"]},
    }
    mg.journal(
        state_dir,
        {
            "kind": "decision",
            "ts": now,
            "pr": 1,
            "head_sha": H1,
            "base_sha": B0,
            "candidate_sha": CAND,
            "overall": row["overall"],
            **({"gate_pending": True} if row["gate_pending"] else {}),
        },
    )
    loc = mg.local_side(status_doc)
    live1 = _live_for(row["H1"], row["G1"], H1)
    enq1 = mg.enqueue_step(a, state_dir, {"repo": REPO, "pr": 1, "head_sha": H1, "base_sha": B0, "candidate_sha": CAND, "lease_id": "L1"}, loc, live1)
    fake_shadow(state_dir, state_dir, enq1, "main", a)
    d_recs = mg.read_journal(state_dir)
    pending1 = (1, H1, B0) in mg.pending_merges(d_recs)

    # Retry step
    a.gate_ledger = str(ledgers[row["G2"]])

    def fake_pr_side2(a_, st_, n_, head_, why_):
        why_["same_repo"] = None if row["same_repo2"] else "cross-repo"
        for t in bo.PR_TERMS:
            why_[t] = None if row["pr_terms2"][t] else f"{t} false"
        return {"pull_request_id": "PR_1", "live_head_oid": head_, "label_actor": "u", "bites": True}

    def fake_fetch_live(repo_, base_, head_, matrix_=None):
        if head_ != H1:
            return _live_for(row["H2"], "S", head_)
        if row["H2"] == "x":
            raise mg.hc.CompareError("hosted read failed on retry")
        return _live_for(row["H2"], row["G2"], head_)

    monkeypatch.setattr(mg, "pr_side", fake_pr_side2)
    monkeypatch.setattr(mg.hc, "fetch_live", fake_fetch_live)
    r_base = "d" * 40 if row["moved"] == "base" else B0
    r_head = H2 if row["moved"] == "head" else H1
    mg.retry_pending_merges(a, state_dir, state_dir, "L2", d_recs, r_base, [pr(1, r_head, armed=False, labels=[mg.ARM_LABEL])])
    after = mg.read_journal(state_dir)[len(d_recs):]
    r_enqs = [r for r in after if r.get("kind") == "would_enqueue" and r.get("retry") is True]
    retried = bool(r_enqs)
    ok2 = bool(r_enqs and r_enqs[-1]["ok"] is True)
    if r_enqs and r_enqs[-1].get("judge_rewritten_base_ok"):
        assert bool(r_enqs[-1].get("judge_rewritten_gate_only")) is bool(enq1.get("judge_rewritten_gate_only"))
    merged2 = any(r.get("kind") == "merged" for r in after)
    return (
        enq1["ok"],
        enq1["criterion"]["executed_contexts_ok"],
        enq1["criterion"]["hosted_required_green"],
        bool(enq1.get("judge_rewritten_gate_only")),
        enq1.get("judge_rewritten_gated") or {},
        pending1,
        retried,
        ok2,
        merged2,
    )


def test_t2b_mcdc_and_terms(tmp_path, monkeypatch):
    monkeypatch.delenv(mg.ARM_ENV, raising=False)
    monkeypatch.setattr("builtins.print", lambda *a, **k: None)
    monkeypatch.setattr(mg.os, "fsync", lambda fd: None)
    ledgers = {st: write_ledger_state(tmp_path / "ledgers" / f"{st}.jsonl", st) for st in bo.G2_STATES}
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    mismatches = []
    for row in bo.t2b_rows():
        got = _run_fast_row(row, state_dir, ledgers, monkeypatch)
        want = bo.oracle_row(row)
        if got != want:
            mismatches.append(f"{row['id']}: got {got} != want {want}")
    assert not mismatches, f"{len(mismatches)} T2b mismatch(es):\n" + "\n".join(mismatches[:25])


def test_t2_decision_and_retry_product(tmp_path, monkeypatch):
    now = mg.now()
    monkeypatch.delenv(mg.ARM_ENV, raising=False)
    monkeypatch.setattr("builtins.print", lambda *a, **k: None)
    monkeypatch.setattr(mg.os, "fsync", lambda fd: None)
    ledgers = {st: write_ledger_state(tmp_path / "ledgers" / f"{st}.jsonl", st) for st in bo.G2_STATES}
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    jpath = state_dir / "decisions.jsonl"

    mismatches = []
    specs = bo.t2_decision_specs()
    assert len(specs) == 3744

    for cfg, g1, h1, retries in specs:
        first_row = bo.make_row(f"{'+'.join(cfg)} | {g1},{h1}", cfg, g1, h1, retries[0][0], retries[0][1], retries[0][2])
        if jpath.exists():
            jpath.unlink()
        a = argparse.Namespace(repo=REPO, base="main", gate_ledger=str(ledgers[g1]))

        def fake_pr_side1(a_, st_, n_, head_, why_):
            why_["same_repo"] = None
            for t in bo.PR_TERMS:
                why_[t] = None
            return {"pull_request_id": "PR_1", "live_head_oid": head_, "label_actor": "u", "bites": True}

        def fake_shadow(st_, repo_dir_, enq_, base_="main", a_=None, decision_=None):
            if enq_["ok"]:
                mg.journal(st_, {"kind": "merged", "ts": now, "pr": enq_["pr"], "head_sha": enq_["head_sha"], "base_sha": enq_["base_sha"]})
                return mg.journal(st_, {"kind": "pushed", "ts": now, "pr": enq_["pr"], "head_sha": enq_["head_sha"], "base_sha": enq_["base_sha"]})
            return mg.journal(
                st_,
                {
                    "kind": "would_merge",
                    "ts": now,
                    "pr": enq_["pr"],
                    "head_sha": enq_["head_sha"],
                    "base_sha": enq_["base_sha"],
                    "clean": True,
                    "ok": False,
                    "phase_f": {"armed": False, "why": ["disarmed"]},
                    **({"retry": True, "decision_ts": enq_.get("decision_ts")} if enq_.get("retry") is True else {}),
                },
            )

        monkeypatch.setattr(mg, "pr_side", fake_pr_side1)
        monkeypatch.setattr(mg, "merge_shadow_step", fake_shadow)
        monkeypatch.setattr(mg, "base_matrix", lambda *a_, **k_: None)
        monkeypatch.setattr(mg, "PENDING_RETRY_S", 0)

        status_doc = {
            "overall": "BLOCKED",
            "checks": {"c": {"status": "PASS"}, "review.independent": {"status": "QUEUED"}},
            "contexts": {"status": "ok", "required": first_row["required"], "results": first_row["results"]},
        }
        mg.journal(state_dir, {"kind": "decision", "ts": now, "pr": 1, "head_sha": H1, "base_sha": B0, "candidate_sha": CAND, "overall": "BLOCKED"})
        loc = mg.local_side(status_doc)
        enq1 = mg.enqueue_step(
            a, state_dir, {"repo": REPO, "pr": 1, "head_sha": H1, "base_sha": B0, "candidate_sha": CAND, "lease_id": "L1"}, loc, _live_for(h1, g1, H1)
        )
        fake_shadow(state_dir, state_dir, enq1, "main", a)
        d_bytes = jpath.read_bytes()
        d_recs = mg.read_journal(state_dir)
        pending1 = (1, H1, B0) in mg.pending_merges(d_recs)
        d_obs = (
            enq1["ok"],
            enq1["criterion"]["executed_contexts_ok"],
            enq1["criterion"]["hosted_required_green"],
            bool(enq1.get("judge_rewritten_gate_only")),
            enq1.get("judge_rewritten_gated") or {},
            pending1,
        )

        label = "+".join(cfg)
        for g2, h2, mv in retries:
            row_id = f"{label} | {g1},{h1} -> {g2},{h2},{mv}"
            row = bo.make_row(row_id, cfg, g1, h1, g2, h2, mv)
            want = bo.oracle_row(row)
            jpath.write_bytes(d_bytes)
            a.gate_ledger = str(ledgers[g2])

            def fake_fetch_live(repo_, base_, head_, matrix_=None, h2_=h2, g2_=g2):
                if head_ != H1:
                    return _live_for(h2_, "S", head_)
                if h2_ == "x":
                    raise mg.hc.CompareError("hosted read failed on retry")
                return _live_for(h2_, g2_, head_)

            monkeypatch.setattr(mg.hc, "fetch_live", fake_fetch_live)
            r_base = "d" * 40 if mv == "base" else B0
            r_head = H2 if mv == "head" else H1
            mg.retry_pending_merges(a, state_dir, state_dir, "L2", d_recs, r_base, [pr(1, r_head, armed=False, labels=[mg.ARM_LABEL])])
            after = mg.read_journal(state_dir)[len(d_recs):]
            r_enqs = [r for r in after if r.get("kind") == "would_enqueue" and r.get("retry") is True]
            if r_enqs and r_enqs[-1].get("judge_rewritten_base_ok") and bool(r_enqs[-1].get("judge_rewritten_gate_only")) is not want[3]:
                mismatches.append(f"{row_id}: retry judge_rewritten_gate_only={r_enqs[-1].get('judge_rewritten_gate_only')!r} != {want[3]!r}")
            got = (*d_obs, bool(r_enqs), bool(r_enqs and r_enqs[-1]["ok"] is True), any(r.get("kind") == "merged" for r in after))
            if got != want:
                mismatches.append(f"{row_id}: got {got} != want {want}")

    assert not mismatches, f"{len(mismatches)} T2 mismatch(es):\n" + "\n".join(mismatches[:25])


# ------------------------------------------------------------------ §2b.3 T2c: recorded-input pending_merges rows
def test_t2c_recorded_input_rows():
    clean_only = {
        1: {
            "criterion": {**dict.fromkeys(mg.CRITERION, True), "executed_contexts_ok": False},
            "contexts_status": "ok",
            "required_n": 1,
            "not_ok": {},
            "host_no_verdict": {},
            "judge_rewritten_base_ok": ["ctx-a"],
            "judge_rewritten_gate_only": True,
        }
    }
    assert list(mg.pending_merges(good(clean_only))) == [(1, H1, B0)]

    bad_variants = [
        {"host_no_verdict": {"ctx-b": "host_disk_full"}},
        {"not_ok": {"ctx-b": "FAIL (executed)"}},
        {"contexts_status": "error"},
        {"contexts_status": None},
        {"required_n": 0},
        {"required_n": True},
        {"judge_rewritten_base_ok": []},
        {"judge_rewritten_base_ok": "ctx-a"},
    ]
    for diff in bad_variants:
        over = {1: {**clean_only[1], **diff}}
        assert mg.pending_merges(good(over)) == {}, diff

    for missing_field in ("contexts_status", "required_n", "not_ok", "host_no_verdict", "judge_rewritten_base_ok"):
        rec1 = {k: v for k, v in clean_only[1].items() if k != missing_field}
        rows_in = good()
        rows_in[1] = {k: v for k, v in rows_in[1].items() if k != missing_field}
        rows_in[1].update(rec1)
        assert mg.pending_merges(rows_in) == {}, f"missing {missing_field}"

    for term in ("local_checks_clean", "review_independent", "same_repo"):
        over = {1: {**clean_only[1], "criterion": {**clean_only[1]["criterion"], term: False}}}
        assert mg.pending_merges(good(over)) == {}, f"false {term}"


# ------------------------------------------------------------------ §2b.3 TI: real fw integration rows (real git, real phase_f_arming, real ledger)
def _bind_fw_ledger(fw, monkeypatch, state: str = "N"):
    lpath = fw.state / "verdicts.jsonl"
    monkeypatch.setattr(mg, "DEFAULT_GATE_LEDGER", lpath)
    write_ledger_state(lpath, state, head=fw.head1, base=fw.base, cand=CAND, other_head=fw.head2)
    return lpath


def _set_gh_gate(fw, monkeypatch, states, hosted_green: bool = True):
    hub = fw.hub
    status_re = rf"repos/{REPO}/commits/{fw.head1}/status\?per_page=100&page=1"
    runs_re = rf"repos/{REPO}/commits/{fw.head1}/check-runs\?per_page=100&page=1"

    def get(path):
        if re.fullmatch(status_re, path):
            return {"statuses": [{"context": mg.GATE_CONTEXT, "state": s, "updated_at": T0} for s in states]}
        out = hub(path)
        if not hosted_green and re.fullmatch(runs_re, path):
            out = {"check_runs": [{**c, "status": "in_progress", "conclusion": None} for c in out["check_runs"]]}
        return out

    monkeypatch.setattr(mg.hc, "gh_get", get)


def test_ti_rewritten_judge_with_ledger_success_merges_and_records_j3_fields(fw, monkeypatch):
    fw.runner.doc = doc()
    _bind_fw_ledger(fw, monkeypatch, "S")
    _set_gh_gate(fw, monkeypatch, ["success"])
    assert fw.tick() == 0
    e = enq(fw)
    assert e["criterion"]["executed_contexts_ok"] is True and e["ok"] is True
    assert e["contexts_status"] == "ok" and e["required_n"] == 1 and e["not_ok"] == {}
    assert e["judge_rewritten_base_ok"] == ["ctx-a"] and e["judge_rewritten_gated"] == {"ctx-a": True}
    assert e["judge_rewritten_gate_only"] is True and e["gate_sources"] == {"ledger": True, "github": True}
    assert next(r for r in fw.live() if r["kind"] == "decision")["no_verdict"] == {"ctx-a": "judge_rewritten_base_ok"}
    assert fw.kinds()[-2:] == ["merged", "pushed"]


@pytest.mark.parametrize("g_state", ["N", "F", "U", "O", "Gh", "SF"])
def test_ti_without_ledger_success_refuses_and_journals_mismatch_or_unreadable_once(fw, monkeypatch, g_state):
    fw.runner.doc = doc()
    monkeypatch.setattr(mg, "PENDING_RETRY_S", 0)
    _bind_fw_ledger(fw, monkeypatch, g_state)
    _set_gh_gate(fw, monkeypatch, ["success"] if g_state == "Gh" else [])
    assert fw.tick() == 0 and fw.tick() == 0
    e = enq(fw)
    assert e["criterion"]["executed_contexts_ok"] is False and e["ok"] is False
    assert "judge rewritten: needs ledger gate success on the head" in e["why"]["executed_contexts_ok"]
    assert e["judge_rewritten_gated"] == {"ctx-a": False} and e["judge_rewritten_gate_only"] is True
    assert e["gate_sources"] == {"ledger": False, "github": g_state == "Gh"}
    mismatches = [r for r in fw.live() if r["kind"] == "gate_provenance_mismatch"]
    unreadables = [r for r in fw.live() if r["kind"] == "gate_ledger_unreadable"]
    assert len(mismatches) == (1 if g_state == "Gh" else 0)
    assert len(unreadables) == (1 if g_state == "U" else 0)
    assert "merged" not in fw.kinds()


@pytest.mark.parametrize("nv,verdict", [("judge_rewritten", "BLOCKED"), (None, "BLOCKED"), (None, "FAIL"), ("judge_rewritten_base_ok", "FAIL"), ("judge_rewritten_base_ok", "ERROR")])
def test_ti_non_rescuable_context_stays_refused_and_never_pending_even_with_ledger_success(fw, monkeypatch, nv, verdict):
    fw.runner.doc = doc(nv, verdict)
    monkeypatch.setattr(mg, "PENDING_RETRY_S", 0)
    _bind_fw_ledger(fw, monkeypatch, "S")
    assert fw.tick() == 0 and fw.tick() == 0
    e = enq(fw)
    assert e["criterion"]["executed_contexts_ok"] is False and e["ok"] is False and e["judge_rewritten_base_ok"] == [] and "judge_rewritten_gated" not in e
    assert mg.pending_merges(fw.journal()) == {} and rows(fw, "would_enqueue") == []
    assert_nothing_merged(fw)


def test_ti_gate_appended_after_decision_merges_on_retry(fw, monkeypatch):
    fw.runner.doc = doc()
    monkeypatch.setattr(mg, "PENDING_RETRY_S", 0)
    lpath = _bind_fw_ledger(fw, monkeypatch, "N")
    assert fw.tick() == 0
    assert enq(fw)["ok"] is False and len(mg.pending_merges(fw.journal())) == 1
    write_ledger_state(lpath, "S", head=fw.head1, base=fw.base)
    assert fw.tick() == 0
    (r,) = rows(fw, "would_enqueue")
    assert r["retry"] is True and r["criterion"]["executed_contexts_ok"] is True and r["ok"] is True and r["judge_rewritten_gated"] == {"ctx-a": True}
    assert fw.kinds()[-2:] == ["merged", "pushed"]


@pytest.mark.parametrize("r_state", ["F", "N", "O", "SF"])
def test_ti_success_at_decision_then_non_success_on_retry_is_refused(fw, monkeypatch, r_state):
    fw.runner.doc = doc()
    monkeypatch.setattr(mg, "PENDING_RETRY_S", 0)
    lpath = _bind_fw_ledger(fw, monkeypatch, "S")
    _set_gh_gate(fw, monkeypatch, ["success"], hosted_green=False)
    assert fw.tick() == 0
    e = enq(fw)
    assert e["criterion"]["executed_contexts_ok"] is True and e["criterion"]["hosted_required_green"] is False and e["ok"] is False
    assert len(mg.pending_merges(fw.journal())) == 1
    write_ledger_state(lpath, r_state, head=fw.head1, base=fw.base, cand=CAND, other_head=fw.head2)
    _set_gh_gate(fw, monkeypatch, ["success"], hosted_green=True)
    assert fw.tick() == 0
    (r,) = rows(fw, "would_enqueue")
    assert r["ok"] is False and r["criterion"]["executed_contexts_ok"] is False and r["judge_rewritten_gated"] == {"ctx-a": False}
    assert "merged" not in fw.kinds()


def test_ti_gate_never_stands_in_for_hosted_red_at_decision_or_retry(fw, monkeypatch):
    fw.runner.doc = doc()
    monkeypatch.setattr(mg, "PENDING_RETRY_S", 0)
    _bind_fw_ledger(fw, monkeypatch, "S")
    _set_gh_gate(fw, monkeypatch, ["success"], hosted_green=False)
    assert fw.tick() == 0 and fw.tick() == 0
    for r in [enq(fw), *rows(fw, "would_enqueue")]:
        assert r["criterion"]["executed_contexts_ok"] is True and r["criterion"]["hosted_required_green"] is False and r["ok"] is False
    assert "merged" not in fw.kinds()


@pytest.mark.parametrize("other", [
    {"verdict": "BLOCKED", "no_verdict": "host_disk_full"},
    {"verdict": "ERROR", "no_verdict": "host_disk_unmeasured x"},
    {"verdict": "FAIL"},
    {"verdict": "BLOCKED", "no_verdict": "judge_rewritten"},
])
def test_ti_two_rescued_and_host_or_other_red_never_gate_only_nor_merged(fw, monkeypatch, other):
    fw.runner.doc = three("ctx-c", **other)
    monkeypatch.setattr(mg, "PENDING_RETRY_S", 0)
    _bind_fw_ledger(fw, monkeypatch, "S")
    assert fw.tick() == 0 and fw.tick() == 0
    e = enq(fw)
    assert e["judge_rewritten_gate_only"] is False and e["judge_rewritten_gated"] == {"ctx-a": False, "ctx-b": False}
    assert e["criterion"]["executed_contexts_ok"] is False and mg.pending_merges(fw.journal()) == {}
    assert "merged" not in fw.kinds()


def test_tick_cli_and_wrapper_wire_gate_ledger_flag():
    sh = (Path(mg.__file__).resolve().parent / "localci_merger_tick.sh").read_text()
    assert 'grep -q -- "--gate-ledger" "$CODE/merger.py"' in sh
    assert "gate_ledger.py" in sh
