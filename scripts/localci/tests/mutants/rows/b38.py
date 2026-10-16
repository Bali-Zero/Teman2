"""B38: dead keys are decided last, never skipped — one rule per row, against test_dead_last.py."""
PY = "scripts/localci/merger.py"
DL = ("scripts/localci/tests/test_dead_last.py",)
SORT = '(not has_arm_label(p), (p["number"], head_of(p)) in dead_keys, *order(p)[1:])'

ROWS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    # the order
    "b38-dead-class-ignored": (PY, '(p["number"], head_of(p)) in dead_keys, *order(p)[1:]))', 'False, *order(p)[1:]))', DL),
    "b38-dead-before-labelled": (PY, SORT, '((p["number"], head_of(p)) in dead_keys, not has_arm_label(p), *order(p)[1:])', DL),
    "b38-dead-key-skipped": (PY, "        dead_keys = classify_dead(todo, recs, dead_probes)\n",
                             "        dead_keys = classify_dead(todo, recs, dead_probes)\n        todo[:] = [p for p in todo if (p[\"number\"], head_of(p)) not in dead_keys]\n", DL),
    "b38-inner-order-lost": (PY, "in dead_keys, *order(p)[1:]))", "in dead_keys, p[\"number\"]))", DL),
    "b38-probes-not-wired": (PY, "dead_probes=dead_probes(a, repo_dir, base_sha), dead=dead,", "dead=dead,", DL),
    "b38-reviews-not-writers-only": (PY, "latestOpinionatedReviews(writersOnly: true, first: 100)", "latestOpinionatedReviews(first: 100)", DL),
    "b38-dead-journalled-every-tick": (PY, 'r.get("why") == "dead_last" and all(r.get(k) == v for k, v in key.items()) for r in recs):', "False for r in recs):", DL),
    # (a) the review
    "b38-unreadable-review-is-dead": (PY, "return reason is not None and reason.startswith(REVIEW_CR)", "return reason is not None", DL),
    "b38-review-batch-per-key": (PY, 'if "r" not in cache:', "if True:", DL),
    # (b) the hosted document
    "b38-cancelled-is-dead": (PY, '"startup_failure", "error"})   # B38', '"startup_failure", "error", "cancelled"})   # B38', DL),
    "b38-error-not-dead": (PY, '"startup_failure", "error"})   # B38', '"startup_failure"})   # B38', DL),
    "b38-timed-out-not-dead": (PY, 'frozenset({"failure", "timed_out", ', 'frozenset({"failure", ', DL),
    "b38-pending-attempt-is-dead": (PY, ' and not any(e["verdict"] == "PENDING" for e in entries):', ":", DL),
    "b38-unrequired-context-is-dead": (PY, 'for c in live["required_checks"]:\n        entries = by.get(c["context"], [])',
                                       'for c in [{"context": k} for k in by]:\n        entries = by.get(c["context"], [])', DL),
    "b38-hosted-required-names-unchecked": (PY, '        raise hc.CompareError("hosted document is not an object")\n    hc.required_names(live.get("required_checks"))\n',
                                            '        raise hc.CompareError("hosted document is not an object")\n', DL),
    # (c) the journal
    "b38-fail-any-overall": (PY, '(r.get("overall") == "FAIL" and "error" not in hc_', '("error" not in hc_', DL),
    "b38-fail-comparison-error-ignored": (PY, '(r.get("overall") == "FAIL" and "error" not in hc_', '(r.get("overall") == "FAIL"', DL),
    "b38-fail-counts-ignored": (PY, 'and all(v == 0 for k, v in counts.items() if k != "AGREE")', "and True", DL),
    "b38-fail-without-failing-context": (PY, 'and any(v == "FAIL" for v in compared.values()))', "and True)", DL),
    "b38-fail-stale-context-counted": (PY, "if k not in stale}", "}", DL),
    "b38-fail-compared-len-unchecked": (PY, 'and len(compared) == counts["AGREE"]', "and True", DL),
    # (d) the gate
    "b38-gate-need-sticky": (PY, 'needs_gate[r.get("pr")] = r.get("gate_pending") is True', 'needs_gate[r.get("pr")] = needs_gate.get(r.get("pr")) or r.get("gate_pending") is True', DL),
    "b38-gate-asked-of-every-key": (PY, 'if needs_gate.get(n) and ask("gate_missing", n, head):', 'if ask("gate_missing", n, head):', DL),
    "b38-gate-posted-reads-inverted": (PY, "gate_posted_at(a.repo, head) is None}", "gate_posted_at(a.repo, head) is not None}", DL),
    # the failure mode and the cost
    "b38-failed-read-is-dead": (PY, "            return False\n\n    for p in todo:", "            return True\n\n    for p in todo:", DL),
    "b38-absent-probe-is-dead": (PY, "        if probe is None:\n            return False", "        if probe is None:\n            return True", DL),
    "b38-stop-swallowed": (PY, "        except (Stopped, TickTimeout):\n            raise\n        except Exception as exc:  # noqa: BLE001 — an unreadable fact",
                           "        except Exception as exc:  # noqa: BLE001 — an unreadable fact", DL),
    "b38-rest-cap-off": (PY, "stop = not why or reads >= DEAD_READ_CAP", "stop = not why", DL),
    "b38-rest-never-stops-at-alive": (PY, "stop = not why or reads >= DEAD_READ_CAP", "stop = reads >= DEAD_READ_CAP", DL),
    "b38-free-tiers-stop-with-the-rest": (PY, '        elif ask("review", n, head):', '        elif not stop and ask("review", n, head):', DL),
}
