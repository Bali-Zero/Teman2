"""B33 S2: per-container phases, trusted-side peak memory and layer size are data in the receipt, never a verdict — against test_capacity_probe.py."""
from merger_mutants import RUNNER, PY  # noqa: F401  (the table's own helpers)

CAP, B33S2 = "scripts/localci/capacity_report.py", ("scripts/localci/tests/test_capacity_probe.py",)   # B33 S2
NEW_FIN = ('        try:\n            if made:\n                _probe_layer(docker, ctr, denv, probe)\n        finally:   # a signal inside the layer read must still reach the removal\n'
           '            with _timed(probe, "t_remove"):\n                _remove_verified(docker, ctr, denv)\n')
OLD_FIN = '        if made:\n            _probe_layer(docker, ctr, denv, probe)\n        with _timed(probe, "t_remove"):\n            _remove_verified(docker, ctr, denv)\n'

ROWS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "b33s2-sampler-error-escapes-thread": (RUNNER, "        except Exception as e:   # noqa: BLE001 — a sampler failure is data in the receipt, never a verdict\n",
                                           "        except ZeroDivisionError as e:\n", B33S2),
    "b33s2-layer-error-escapes-run": (RUNNER, "    except Exception as e:   # noqa: BLE001 — as the memory sampler: data, never a verdict\n",
                                      "    except ZeroDivisionError as e:\n", B33S2),
    "b33s2-peak-is-last-sample": (RUNNER, '            elif used > 0 and (self.probe["mem_peak_bytes"] is None or used > self.probe["mem_peak_bytes"]):', "            elif True:", B33S2),
    "b33s2-zero-reading-is-a-peak": (RUNNER, "            elif used > 0 and (self.probe", "            elif (self.probe", B33S2),
    "b33s2-sampler-switch-ignored": (RUNNER, 'sampler = "off" if os.environ.get(SANDBOX_SAMPLER_ENV) == "0" else "on"', 'sampler = "on"', B33S2),
    "b33s2-layer-read-after-removal": (RUNNER, NEW_FIN, '        with _timed(probe, "t_remove"):\n            _remove_verified(docker, ctr, denv)\n        if made:\n            _probe_layer(docker, ctr, denv, probe)\n', B33S2),
    "b33s2-layer-signal-orphans-the-container": (RUNNER, NEW_FIN, OLD_FIN, B33S2),
    "b33s2-layer-asked-without-container": (RUNNER, "            if made:\n                _probe_layer(", "            if True:\n                _probe_layer(", B33S2),
    "b33s2-no-t-create": (RUNNER, '        with _timed(probe, "t_create"):\n', "        if True:\n", B33S2),
    "b33s2-no-t-copy-in": (RUNNER, '                    probe["t_copy_in"] = round(time.monotonic() - t_cp, 3)\n', "                    pass\n", B33S2),
    "b33s2-no-t-start-to-exit": (RUNNER, ', _timed(probe, "t_start_to_exit"):', ":", B33S2),
    "b33s2-join-inside-the-run-clock": (RUNNER, "with _MemSampler(docker, ctr, denv, probe), _timed(probe, \"t_start_to_exit\"):", "with _timed(probe, \"t_start_to_exit\"), _MemSampler(docker, ctr, denv, probe):", B33S2),
    "b33s2-no-t-junit": (RUNNER, '        with _timed(probe, "t_junit"):\n', "        if True:\n", B33S2),
    "b33s2-no-t-remove": (RUNNER, '            with _timed(probe, "t_remove"):\n                _remove_verified(docker, ctr, denv)\n\n\nclass', '            if True:\n                _remove_verified(docker, ctr, denv)\n\n\nclass', B33S2),
    "b33s2-sampler-not-joined": (RUNNER, "            self._t.join(30)\n", "            pass\n", B33S2),
    "b33s2-steps-verdict-reads-the-probe": (RUNNER, "def steps_verdict(steps: list, spec: dict) -> tuple[str, str]:\n",
                                            'def steps_verdict(steps: list, spec: dict) -> tuple[str, str]:\n    _ = spec.get("sandbox")\n', B33S2),
    "b33s2-merger-reads-the-probe": (PY, 'GATE_CONTEXT = "harness/fable-gate"\n', 'GATE_CONTEXT = "harness/fable-gate"\n_PEAK = "mem_peak_bytes"\n', B33S2),
    "b33s2-job-rows-drop-probes": (RUNNER, '"sandbox": x.get("sandbox") or []} for x in legs]', '"sandbox": []} for x in legs]', B33S2),
    "b33s2-stats-no-timeout": (RUNNER, "                               timeout=SANDBOX_STATS_TIMEOUT_S, env=self.denv)", "                               env=self.denv)", B33S2),
    "b33s2-ps-no-timeout": (RUNNER, "                           timeout=SANDBOX_PS_TIMEOUT_S, env=denv)", "                           env=denv)", B33S2),
    "b33s2-pytest-result-drops-probe": (RUNNER, '            "isolation": "container", "sandbox": [probe]}\n\n\ndef read_blobs', '            "isolation": "container"}\n\n\ndef read_blobs', B33S2),
    "b33s2-steps-result-drops-probe": (RUNNER, '"log": str(log), "isolation": "container", "sandbox": [probe]}\n    counts', '"log": str(log), "isolation": "container"}\n    counts', B33S2),
    "b33s2-no-verdict-return-drops-probe": (RUNNER, '"reason": err, "rc": None, "duration_s": dur, "counts": None, "log": str(log), "isolation": "container", "sandbox": [probe]}',
                                            '"reason": err, "rc": None, "duration_s": dur, "counts": None, "log": str(log), "isolation": "container"}', B33S2),
    "b33s2-leg-probe-not-appended": (RUNNER, 'out["sandbox"].append(probe := new_probe(f"{name}.{slug}"))', 'probe = new_probe(f"{name}.{slug}")', B33S2),
    "b33s2-egress-probe-not-appended": (RUNNER, "    if probes is not None:\n        probes.append(probe)\n", "    if probes is not None:\n        pass\n", B33S2),
    "b33s2-egress-list-not-passed": (RUNNER, 'run_dir, plan, out["sandbox"])', "run_dir, plan)", B33S2),
    "b33s2-candidate-status-reads-sampler-error": (RUNNER, '    if err:\n        return {"status": "ERROR", "reason": err,', '    if err or probe["sampler_error"]:\n        return {"status": "ERROR", "reason": err,', B33S2),
    "b33s2-run-status-reads-sampler-error": (RUNNER, 'c.update(status=res["status"], reason=res["reason"], at=now(), receipt=str(rp)',
                                             'c.update(status=("ERROR" if any(q.get("sampler_error") for q in res.get("sandbox") or []) else res["status"]), reason=res["reason"], at=now(), receipt=str(rp)', B33S2),
    "b33s2-report-p95-is-max": (CAP, "v[max(0, math.ceil(0.95 * len(v)) - 1)]", "v[-1]", B33S2),
    "b33s2-report-setup-drops-remove": (CAP, 'SETUP = ("t_create", "t_copy_in", "t_junit", "t_remove")', 'SETUP = ("t_create", "t_copy_in", "t_junit")', B33S2),
    "b33s2-report-ignores-jobs-shape": (CAP, ' + [j.get("sandbox") for j in res.get("jobs") or [] if isinstance(j, dict)]', "", B33S2),
}
