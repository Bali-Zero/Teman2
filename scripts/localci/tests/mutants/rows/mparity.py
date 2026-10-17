"""policy.matrix_parity (cure for matrix drift): one rule per row, against test_matrix_parity.py."""
PY = "scripts/localci/runner.py"
MP = ("scripts/localci/tests/test_matrix_parity.py",)

ROWS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "mparity-every-problem-is-new": (PY, "new = [p for p in now_ if p not in was]", "new = list(now_)", MP),
    "mparity-nothing-is-new": (PY, "new = [p for p in now_ if p not in was]", "new = []", MP),
    "mparity-base-and-candidate-swapped": (PY, "was, now_ = matrix_accounting(wt, base, scratch), matrix_accounting(wt, cand, scratch)",
                                           "now_, was = matrix_accounting(wt, base, scratch), matrix_accounting(wt, cand, scratch)", MP),
    "mparity-candidate-read-at-base": (PY, "was, now_ = matrix_accounting(wt, base, scratch), matrix_accounting(wt, cand, scratch)",
                                       "was, now_ = matrix_accounting(wt, base, scratch), matrix_accounting(wt, base, scratch)", MP),
    "mparity-inherited-passes": (PY, "    if now_:\n        return {\"kind\": \"record\", \"status\": \"NOT_APPLICABLE\",", "    if False:\n        return {\"kind\": \"record\", \"status\": \"NOT_APPLICABLE\",", MP),
    "mparity-inherited-fails": (PY, '"status": "NOT_APPLICABLE",\n                "reason": f"{len(now_)} problem(s) already present', '"status": "FAIL",\n                "reason": f"{len(now_)} problem(s) already present', MP),
    "mparity-crash-is-a-fail": (PY, 'return _blocked(f"matrix parity could not be computed: {type(e).__name__}: {e}")',
                                'return {"kind": "record", "status": "FAIL", "reason": f"matrix parity could not be computed: {e}"}', MP),
    "mparity-absent-matrix-is-fine": (PY, 'return [f"{MATRIX_REL} is absent"]', "return []", MP),
    "mparity-invalid-matrix-is-fine": (PY, 'return [f"{MATRIX_REL}: {ctxs[\'reason\']}"]', "return []", MP),
    "mparity-unreadable-workflow-skipped": (PY, 'problems.append(f"{cname}: workflow {wf} is unreadable")\n            continue',
                                            "continue", MP),
    "mparity-upstream-jobs-unread": (PY, 'legs = [*(local.get("jobs") or []), {**local, "job_id": ctx.get("job_id")}] if local.get("expressions") else',
                                     'legs = [{**local, "job_id": ctx.get("job_id")}] if local.get("expressions") else', MP),
    "mparity-absent-job-skipped": (PY, 'problems.append(f"{cname}: job {jl.get(\'job_id\')!r} is absent from {wf}")\n                continue',
                                   "continue", MP),
    "mparity-resolve-why-ignored": (PY, "            if why:\n                problems.append(f\"{cname}: job {jl.get('job_id')}: {why}\")", "            if False:\n                problems.append(f\"{cname}: job {jl.get('job_id')}: {why}\")", MP),
    "mparity-check-not-planned": (PY, 'checks["policy.matrix_parity"] = matrix_parity_check(wt, base, ident["candidate_sha"], run_dir / "state" / "parity")',
                                  'pass', MP),
    "mparity-plan-checks-base-twice": (PY, 'matrix_parity_check(wt, base, ident["candidate_sha"], run_dir / "state" / "parity")',
                                       'matrix_parity_check(wt, base, base, run_dir / "state" / "parity")', MP),
}
