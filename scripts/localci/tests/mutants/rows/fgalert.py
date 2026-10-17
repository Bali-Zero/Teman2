"""Owner ruling 2026-10-17: after the flip a FALSE_GREEN is an alarm, not a halt (tests/test_false_green_alarm.py)."""
PY, T = "scripts/localci/merger.py", ("scripts/localci/tests/test_false_green_alarm.py",)
CF = "scripts/localci/tests/conftest.py"
GATE = '        if not (os.environ.get(PHASE_F_ENV) == "1" and doc.get("phase_e_ready_ex_false_green") is True):'

ROWS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "fg-still-blocks-in-phase-f": (PY, GATE, '        if True:', T),
    "fg-unarmed-env-ignored": (PY, 'not (os.environ.get(PHASE_F_ENV) == "1" and doc.get("phase_e_ready_ex_false_green") is True):', 'not (doc.get("phase_e_ready_ex_false_green") is True):', T),
    "fg-any-truthy-ex-flag": (PY, 'doc.get("phase_e_ready_ex_false_green") is True):', 'doc.get("phase_e_ready_ex_false_green")):', T),
    "fg-ex-flag-ignores-the-other-terms": (PY, "    ready_ex_fg = compared_merges >= READY_MIN_MERGES and compared_days >= READY_MIN_DAYS", "    ready_ex_fg = compared_merges >= READY_MIN_MERGES or compared_days >= READY_MIN_DAYS", T),
    "fg-ready-drops-false-green-term": (PY, "    ready = fg == 0 and compared_merges >= READY_MIN_MERGES and compared_days >= READY_MIN_DAYS", "    ready = compared_merges >= READY_MIN_MERGES and compared_days >= READY_MIN_DAYS", T),
    "fg-cache-ex-flag-always-true": (PY, 'False if early else rep.get("phase_e_ready_ex_false_green") is True,', "True,", T),
    "fg-alarm-repeats-seen-keys": (PY, "for key in (k for k in keys if k not in seen):", "for key in keys:", T),
    "fg-alarm-no-journal-row": (PY, '        journal(state, {"kind": "false_green_alarm", "key": key, "escalated": ok, "result": "alarm"})\n', "", T),
    "fg-alarm-no-board-line": (PY, '            with board.open("a", encoding="utf-8") as fh:\n                fh.write(json.dumps(line, ensure_ascii=False) + "\\n")\n', "            pass\n", T),
    "fg-alarm-board-error-raises": (PY, "        except OSError:\n            ok = False\n", "        except ZeroDivisionError:\n            ok = False\n", T),
    "fg-alarm-fired-without-phase-f": (PY, '    if os.environ.get(PHASE_F_ENV) == "1":\n        alarm_false_green(', "    if True:\n        alarm_false_green(", T),
    "fg-alarm-never-fired-from-refresh": (PY, '        alarm_false_green(state, facts["false_green_keys"])', "        pass", T),
    "fg-alarm-not-high": (PY, '"priority": "HIGH", "status": "pending", "ts": ts, "machine": "pro"', '"priority": "LOW", "status": "pending", "ts": ts, "machine": "pro"', T),
    "fg-keys-skip-pr-level": (PY, 'if rows[-1]["class"] == "FALSE_GREEN" or ctx_fg or raw - len(got) > 0:', "if ctx_fg or raw - len(got) > 0:", T),
    "fg-board-fixture-not-autouse": (CF, "@pytest.fixture(autouse=True)\ndef board_off_the_checkout(", "@pytest.fixture\ndef board_off_the_checkout(", T),
    "fg-board-fixture-sets-no-env": (CF, '    monkeypatch.setenv("LOCALCI_ESCALATIONS_FILE", str(path))\n', "", T),
    "fg-keys-skip-every-level": (PY, 'if rows[-1]["class"] == "FALSE_GREEN" or ctx_fg or raw - len(got) > 0:', "if False:", T),
}
