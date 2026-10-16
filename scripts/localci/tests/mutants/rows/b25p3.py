"""B25-prime P3: the 30 merger, pending and retry mutant rows of docs/specs/localci-sovereign-2026-10-07.md §2b.4 (their exact --only names),
plus P3's provenance-mismatch, unreadable-ledger and wrapper rows."""
PY, SH = "scripts/localci/merger.py", "scripts/localci/localci_merger_tick.sh"
JG = ("scripts/localci/tests/test_merger_judge_gate.py",)

GATE_ONLY = '"judge_gate_only": bool(judge_base_ok) and why["executed_contexts_ok"] is None}'
RESCUE_IF = 'elif res.get("verdict") == "BLOCKED" and nv == JUDGE_BASE_OK:'
GATED_LINE = 'gated = dict.fromkeys(rescued, gate_ok and why.get("executed_contexts_ok") is None)'
WHY_GATE = '        if why.get("executed_contexts_ok") is None and not gate_ok:\n'
PEND_CRIT = 'crit = {**crit, "executed_contexts_ok": True} if isinstance(crit, dict) and isinstance(e, dict) and recorded_gate_only(e) else crit'
RETRY_RESCUED = '"judge_rewritten_base_ok": row.get("judge_rewritten_base_ok") or []}'

ROWS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    # --- §2b.4 merger, pending and retry rows (30 exact --only names)
    "m-gate-only-ignores-host": (PY, GATE_ONLY, '"judge_gate_only": bool(judge_base_ok) and not not_ok}', JG),
    "m-gate-replaces-hosted": (
        PY,
        '        why["hosted_required_green"] = hosted_side(live)\n        facts = pr_side(a, state, n, head, why)',
        '        why["hosted_required_green"] = None if rescued and gate_ok else hosted_side(live)\n        facts = pr_side(a, state, n, head, why)',
        JG,
    ),
    "g-gate-only-ignores-other-reds": (PY, GATE_ONLY, '"judge_gate_only": bool(judge_base_ok)}', JG),
    "g-gate-overrides-other-red": (
        PY,
        WHY_GATE,
        '        if gate_ok:\n            why["executed_contexts_ok"] = None\n' + WHY_GATE,
        JG,
    ),
    "g-gated-ignores-other-red": (PY, GATED_LINE, "gated = dict.fromkeys(rescued, gate_ok)", JG),
    "g-gated-record-lies": (PY, GATED_LINE, "gated = dict.fromkeys(rescued, True)", JG),
    "b25-gate-not-required": (PY, 'if why.get("executed_contexts_ok") is None and not gate_ok:', "if False:", JG),
    "b25-base-red-rescued": (PY, "nv == JUDGE_BASE_OK:", 'nv.startswith("judge_rewritten"):', JG),
    "b25-any-blocked-rescued": (PY, 'res.get("verdict") == "BLOCKED" and nv == JUDGE_BASE_OK:', 'res.get("verdict") == "BLOCKED":', JG),
    "g-base-ok-not-blocked-only": (PY, RESCUE_IF, 'elif nv == JUDGE_BASE_OK or res.get("verdict") == "ERROR":', JG),
    "g-local-verdict-unchecked": (PY, RESCUE_IF, "elif nv == JUDGE_BASE_OK:", JG),
    "m-rescue-any-red-verdict": (PY, RESCUE_IF, 'elif res.get("verdict") in ("BLOCKED", "ERROR", "FAIL") and nv == JUDGE_BASE_OK:', JG),
    "b25-retry-rescues-base-red": (PY, PEND_CRIT, 'crit = {**crit, "executed_contexts_ok": True} if isinstance(crit, dict) else crit', JG),
    "g-pending-gate-only-present": (
        PY,
        "and recorded_gate_only(e) else crit",
        'and (recorded_gate_only(e) or "judge_rewritten_gate_only" in e) else crit',
        JG,
    ),
    "m-pending-gate-only-any-term": (
        PY,
        PEND_CRIT,
        "crit = dict.fromkeys(LOCAL_TERMS, True) if isinstance(crit, dict) and isinstance(e, dict) and recorded_gate_only(e) else crit",
        JG,
    ),
    "pending-ignores-recorded-host": (
        PY,
        'and e.get("not_ok") == {} and e.get("host_no_verdict") == {}',
        'and e.get("not_ok") == {}',
        JG,
    ),
    "pending-ignores-recorded-not-ok": (
        PY,
        'and e.get("not_ok") == {} and e.get("host_no_verdict") == {}',
        'and e.get("host_no_verdict") == {}',
        JG,
    ),
    "pending-ignores-recorded-contexts-status": (
        PY,
        'e.get("contexts_status") == "ok" and ',
        "",
        JG,
    ),
    "pending-ignores-recorded-required-n": (
        PY,
        'type(e.get("required_n")) is int and e["required_n"] > 0',
        "True",
        JG,
    ),
    "pending-ignores-recorded-legacy-missing-field": (
        PY,
        'return (e.get("contexts_status") == "ok" and type(e.get("required_n")) is int and e["required_n"] > 0\n'
        '            and e.get("not_ok") == {} and e.get("host_no_verdict") == {}',
        'return (e.get("contexts_status", "ok") == "ok" and (e.get("required_n") or 1) > 0\n'
        '            and (e.get("not_ok") or {}) == {} and (e.get("host_no_verdict") or {}) == {}',
        JG,
    ),
    "b25-retry-copies-the-original-term": (PY, RETRY_RESCUED, '"judge_rewritten_base_ok": []}', JG),
    "g-retry-drops-rescued": (
        PY,
        'rescued, gated, gate_sources = list(loc.get("judge_rewritten_base_ok") or []), {}, None',
        'rescued, gated, gate_sources = (list(loc.get("judge_rewritten_base_ok") or []) if not rec.get("retry") else []), {}, None',
        JG,
    ),
    "m-retry-rescued-not-copied": (PY, 'row.get("judge_rewritten_base_ok") or []', "[]", JG),
    "m-gate-read-only-at-decision": (PY, "    if rescued:   # B25-prime J1'':", "    if rescued and not rec.get(\"retry\"):   # B25-prime J1'':", JG),
    "retry-copies-gated-record": (
        PY,
        RETRY_RESCUED,
        '"judge_rewritten_base_ok": [] if (row.get("judge_rewritten_gated") and all(row["judge_rewritten_gated"].values())) else (row.get("judge_rewritten_base_ok") or [])}',
        JG,
    ),
    "g-retry-reads-candidate-sha": (
        PY,
        "live = hc.fetch_live(a.repo, a.base, head, base_matrix(repo_dir, base_sha))",
        'live = hc.fetch_live(a.repo, a.base, d.get("candidate_sha") or head, base_matrix(repo_dir, base_sha))',
        JG,
    ),
    "retry-gate-keyed-on-candidate": (
        PY,
        "gate_ok, gate_why, ledger_path = gate_verdict(a, head)",
        'gate_ok, gate_why, ledger_path = gate_verdict(a, rec.get("candidate_sha") or head if rec.get("retry") else head)',
        JG,
    ),
    "gate-falls-back-to-github": (
        PY,
        "gh_ok = github_gate_success(live, head)",
        "gh_ok = github_gate_success(live, head)\n        gate_ok = gate_ok or gh_ok",
        JG,
    ),
    "hosted-read-failure-is-green": (
        PY,
        '    if isinstance(live, Exception):   # B19: a retry\'s failed read keeps its own message\n'
        '        return redact(f"the hosted read on the PR head failed: {type(live).__name__}: {live}")\n'
        '    if not isinstance(live, dict):\n'
        '        return "the hosted read on the PR head failed"',
        '    if not isinstance(live, dict):\n'
        '        return None',
        JG,
    ),
    "moved-key-retried": (PY, 'if base != base_sha or heads.get(n) != head or p["expired"]:', 'if p["expired"]:', JG),
    # --- P3 provenance mismatch, unreadable ledger, and wrapper wiring
    "b25p3-mismatch-not-journalled": (
        PY,
        'if gh_ok and not gate_ok and not any(',
        'if False and not any(',
        JG,
    ),
    "b25p3-mismatch-journalled-on-every-retry": (
        PY,
        'r.get("kind") == "gate_provenance_mismatch" and r.get("pr") == n and r.get("head_sha") == head for r in read_journal(state)',
        'False for r in read_journal(state)',
        JG,
    ),
    "b25p3-unreadable-not-journalled": (
        PY,
        'if gate_why.startswith("ledger ") and gate_why != "ledger missing" and not any(',
        'if False and not any(',
        JG,
    ),
    "b25p3-unreadable-journalled-on-every-retry": (
        PY,
        'r.get("kind") == "gate_ledger_unreadable" and r.get("why") == gate_why for r in read_journal(state)',
        'False for r in read_journal(state)',
        JG,
    ),
    "b25p3-wrapper-drops-ledger-flag": (
        SH,
        'if grep -q -- "--gate-ledger" "$CODE/merger.py"; then',
        'if false; then',
        JG,
    ),
    "b25p3-retry-gate-only-false": (
        PY,
        'loc["judge_gate_only"] is True if "judge_gate_only" in loc else recorded_gate_only(loc)',
        'loc.get("judge_gate_only") is True',
        JG,
    ),
}
