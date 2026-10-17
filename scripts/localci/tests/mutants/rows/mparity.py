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
    "mparity-unreadable-workflow-skipped": (PY, 'return [f"{cname}: workflow {wf} is unreadable (unparseable, oversized or over the expansion cap)"]', "return []", MP),
    "mparity-upstream-jobs-unread": (PY, 'legs = [*(local.get("jobs") or []), {**local, "job_id": ctx.get("job_id")}] if local.get("expressions") else',
                                     'legs = [{**local, "job_id": ctx.get("job_id")}] if local.get("expressions") else', MP),
    "mparity-absent-job-skipped": (PY, 'problems.append(f"{cname}: job {jl.get(\'job_id\')!r} is absent from {wf}")\n            continue',
                                   "continue", MP),
    "mparity-resolve-why-ignored": (PY, "        if why:\n            problems.append(f\"{cname}: job {jl.get('job_id')}: {why}\")", "        if False:\n            problems.append(f\"{cname}: job {jl.get('job_id')}: {why}\")", MP),
    "mparity-check-not-planned": (PY, 'checks["policy.matrix_parity"] = matrix_parity_check(wt, base, ident["candidate_sha"], run_dir / "state" / "parity")',
                                  'pass', MP),
    "mparity-plan-checks-base-twice": (PY, 'matrix_parity_check(wt, base, ident["candidate_sha"], run_dir / "state" / "parity")',
                                       'matrix_parity_check(wt, base, base, run_dir / "state" / "parity")', MP),
}

ROWS.update({
    "mparity-candidate-data-crash-raises": (PY, '            problems.append(f"{cname}: its matrix data cannot be read ({type(e).__name__})")', "            raise", MP),
    "mparity-expansion-uncapped": (PY, "    if not expanded_nodes_within(doc, PARITY_MAX_NODES):", "    if False:", MP),
    "mparity-size-uncapped": (PY, "    if len(blob) > PARITY_MAX_BYTES:", "    if False:", MP),
    "mparity-cap-ignores-values": (PY, "            stack.extend(cur.keys())\n            stack.extend(cur.values())", "            stack.extend(cur.keys())", MP),
    "mparity-cap-counts-nothing": (PY, "        n += 1\n        if n > cap:", "        n += 0\n        if n > cap:", MP),
    "mparity-workflow-bomb-reads-as-none": (PY, "        except Exception:  # noqa: BLE001 — an unparseable, oversized or bomb workflow is a finding, never a crash\n            docs[wf] = None",
                                            "        except Exception:  # noqa: BLE001 — an unparseable, oversized or bomb workflow is a finding, never a crash\n            docs[wf] = {'jobs': {}}", MP),
})
