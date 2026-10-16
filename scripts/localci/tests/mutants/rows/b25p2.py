"""B25-prime P2: the runner mutant rows of docs/specs/localci-sovereign-2026-10-07.md 2b.4 (their exact --only names), plus the decision-row no_verdict."""
PY, RUN = "scripts/localci/merger.py", "scripts/localci/runner.py"
JRW = ("scripts/localci/tests/test_judge_rewritten.py",)
FLAG_LINE = ('elif s == "BLOCKED" and view[chk].get("judge_no_verdict") in ("judge_rewritten_base_ok", "judge_rewritten"):   # B25: the structured flag, never the text\n'
             '            out["results"][name]["no_verdict"] = view[chk]["judge_no_verdict"]')
WIRING = '**({"judge_no_verdict": jv} if (jv := judge_rc0_of(res["status"], res.get("steps"), spec)) else {})'

ROWS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    # --- 2b.4 runner labels and rc0
    "b25-runner-labels-swapped": (RUN, '        return None\n    return "judge_rewritten_base_ok"', '        return None\n    return "judge_rewritten"', JRW),
    "b25-runner-red-labelled-base-ok": (RUN, 'out["results"][name]["no_verdict"] = "judge_rewritten"\n', 'out["results"][name]["no_verdict"] = "judge_rewritten_base_ok"\n', JRW),
    "b25-runner-no-base-ok-record": (RUN, 'elif s == "BLOCKED" and view[chk].get("judge_no_verdict") in (', 'elif False and view[chk].get("judge_no_verdict") in (', JRW),
    "b25-runner-any-step-status-counts": (RUN, ' or any(x not in ("PASS", "NOT_APPLICABLE") for x in sts):', ":", JRW),
    "b25-runner-no-judge-modified-rescued": (RUN, 'if status != "BLOCKED" or not mod or not sts', 'if status != "BLOCKED" or not sts', JRW),
    "g-rc0-no-pass-needed": (RUN, ' or "PASS" not in sts', "", JRW),
    "g-rc0-status-unchecked": (RUN, 'if status != "BLOCKED" or not mod', 'if not mod', JRW),
    "g-rc0-reads-step-reason": (RUN, 'sts = [s.get("status") for s in steps or [] if isinstance(s, dict)]',
                                'sts = [("PASS" if "rc=0" in str(s.get("reason")) else s.get("status")) for s in steps or [] if isinstance(s, dict)]', JRW),
    "m-rc0-allows-error-step": (RUN, 'any(x not in ("PASS", "NOT_APPLICABLE") for x in sts)', 'any(x not in ("PASS", "NOT_APPLICABLE", "ERROR") for x in sts)', JRW),
    "m-rc0-allows-blocked-step": (RUN, 'any(x not in ("PASS", "NOT_APPLICABLE") for x in sts)', 'any(x not in ("PASS", "NOT_APPLICABLE", "BLOCKED") for x in sts)', JRW),
    "m-rc0-allows-unknown-status": (RUN, 'any(x not in ("PASS", "NOT_APPLICABLE") for x in sts)', 'any(x in ("FAIL", "ERROR", "BLOCKED") for x in sts)', JRW),
    # --- 2b.4 runner text/flag rescue
    "g-runner-text-rescue": (RUN, FLAG_LINE, 'elif s == "BLOCKED" and "rc=0 with the BASE judge" in reason:\n'
                             '            out["results"][name]["no_verdict"] = "judge_rewritten_base_ok"', JRW),
    "g-runner-text-or-flag": (RUN, FLAG_LINE, 'elif s == "BLOCKED" and (view[chk].get("judge_no_verdict") in ("judge_rewritten_base_ok", "judge_rewritten") '
                              'or "rc=0 with the BASE judge" in reason):\n'
                              '            out["results"][name]["no_verdict"] = view[chk].get("judge_no_verdict") or "judge_rewritten_base_ok"', JRW),
    "g-runner-search-not-match": (RUN, 'elif s == "BLOCKED" and reason.startswith("judge_rewritten: "):',
                                  'elif s == "BLOCKED" and "judge_rewritten: " in reason:', JRW),
    "g-eval-flag-any-status": (RUN, 'elif s == "BLOCKED" and view[chk].get("judge_no_verdict") in (', 'elif view[chk].get("judge_no_verdict") in (', JRW),
    "m-eval-flag-value-forced": (RUN, '            out["results"][name]["no_verdict"] = view[chk]["judge_no_verdict"]',
                                 '            out["results"][name]["no_verdict"] = "judge_rewritten_base_ok"', JRW),
    # --- 2b.4 runner wiring
    "g-cmdrun-flag-any-blocked": (RUN, WIRING, '**({"judge_no_verdict": jv} if (jv := ("judge_rewritten_base_ok" if res["status"] == "BLOCKED" and '
                                  'spec.get("judge_modified") else None)) else {})', JRW),
    "g-cmdrun-flag-from-text": (RUN, WIRING, '**({"judge_no_verdict": jv} if (jv := ("judge_rewritten_base_ok" if res["status"] == "BLOCKED" and '
                                '"rc=0 with the BASE judge" in str(res.get("reason")) else None)) else {})', JRW),
    "b25-cmdrun-flag-any-blocked": (RUN, WIRING, '**({"judge_no_verdict": "judge_rewritten_base_ok"} if res["status"] == "BLOCKED" and spec.get("judge_modified") else {})', JRW),
    "b25-cmdrun-flag-from-text": (RUN, WIRING, '**({"judge_no_verdict": "judge_rewritten_base_ok"} if "rc=0 with the BASE judge" in str(res.get("reason")) or '
                                  '"rc=0 with the BASE judge" in str(res.get("steps")) else {})', JRW),
    # --- decision-row no_verdict
    "b25p2-decision-drops-no-verdict": (PY, '                               **({"no_verdict": nvs} if (nvs := {k: v["no_verdict"] for k, v in results.items() '
                                        'if isinstance(v, dict) and v.get("no_verdict")}) else {}),\n', "", JRW),
    "b25p2-decision-empty-no-verdict": (PY, 'if (nvs := {k: v["no_verdict"] for k, v in results.items() if isinstance(v, dict) and v.get("no_verdict")}) else {}',
                                        'if (nvs := {k: v.get("no_verdict") for k, v in results.items() if isinstance(v, dict)}) else {}', JRW),
}
