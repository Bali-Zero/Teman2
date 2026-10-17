"""B43: the withdrawn clearance (cancel by an actor after an unmerged close) — one guard per row, against test_hosted_withdrawn.py."""
PY = "scripts/localci/merger.py"
WD = ("scripts/localci/tests/test_hosted_withdrawn.py",)

ROWS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "b43-merged-pr-withdrawn": (PY, 'p.get("state") == "closed" and p.get("merged") is False and is_ts', 'p.get("state") == "closed" and is_ts', WD),
    "b43-open-pr-withdrawn": (PY, 'p.get("state") == "closed" and p.get("merged") is False', 'p.get("merged") is False', WD),
    "b43-close-time-not-required": (PY, 'and p.get("merged") is False and is_ts(p.get("closed_at")))', 'and p.get("merged") is False)', WD),
    "b43-cancel-before-close-withdrawn": (PY, "not is_ts(completed_at) or completed_at < p[\"closed_at\"]", "not is_ts(completed_at)", WD),
    "b43-no-annotation-withdrawn": (PY, "if not fails or any(not (WITHDRAW_CANCEL", "if any(not (WITHDRAW_CANCEL", WD),
    "b43-other-failure-withdrawn": (PY, "any(not (WITHDRAW_CANCEL.fullmatch(m) or m == ABORT_CANCELED) for m in fails)", "not any(WITHDRAW_CANCEL.fullmatch(m) for m in fails)", WD),
    "b43-failed-step-withdrawn": (PY, 'x.get("conclusion") in ("failure", "timed_out") for x in self.job_steps(rid)', 'x.get("conclusion") == "timed_out" for x in self.job_steps(rid)', WD),
    "b43-timed-out-step-withdrawn": (PY, 'x.get("conclusion") in ("failure", "timed_out") for x in self.job_steps(rid)', 'x.get("conclusion") == "failure" for x in self.job_steps(rid)', WD),
    "b43-not-wired-in-clearance": (PY, "elif reads.withdrawn(rid, e.get(\"completed_at\"))[0]:", "elif False:", WD),
    "b43-pull-not-handed-to-the-judge": (PY, "            abort.pull = prs[n]   # B43", "            pass   # B43", WD),
    "b43-listed-among-the-setup-aborts": (PY, '.items(), key=lambda kv: tuple(str(x) for x in kv[0])) if v != WITHDRAWN]', '.items(), key=lambda kv: tuple(str(x) for x in kv[0]))]', WD),
    "b43-memo-pull-without-close-is-final": (PY, 'pr.get("state") == "closed" and "closed_at" in pr and isinstance(newest', 'pr.get("state") == "closed" and isinstance(newest', WD),
}
