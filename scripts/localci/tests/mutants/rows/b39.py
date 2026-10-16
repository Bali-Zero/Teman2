"""B39: the start floor follows the plan. Every row is killed by test_start_floor_by_plan.py (and the wrapper rows by its wrapper tests)."""
from merger_mutants import MERGER_T  # noqa: F401

PY = "scripts/localci/merger.py"
SH = "scripts/localci/localci_merger_tick.sh"
T = ("scripts/localci/tests/test_start_floor_by_plan.py",)

ROWS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "b39-heavy-margin-10": (PY, "START_MARGIN_HEAVY_GB = 18.0", "START_MARGIN_HEAVY_GB = 10.0", T),
    "b39-light-margin-12": (PY, "START_MARGIN_LIGHT_GB = 6.0", "START_MARGIN_LIGHT_GB = 12.0", T),
    "b39-light-margin-0": (PY, "START_MARGIN_LIGHT_GB = 6.0", "START_MARGIN_LIGHT_GB = 0.0", T),
    "b39-unclassifiable-is-light": (PY, 'return "heavy", f"unclassifiable: {type(exc).__name__}"', 'return "light", f"unclassifiable: {type(exc).__name__}"', T),
    "b39-classifier-failure-is-light": (PY, 'return "heavy", f"change_map rc={res.returncode}"', 'return "light", f"change_map rc={res.returncode}"', T),
    "b39-heavy-never-collected": (PY, "                heavy.append(c[\"name\"])", "                pass", T),
    "b39-deps-by-name": (PY, '                if not local.get("deps"):', '                if c["name"] != "Backend Tests (Python)":', T),
    "b39-runs-when-ignored": (PY, "                if flag and mapped and flag not in", "                if False and flag and mapped and flag not in", T),
    "b39-codeql-classifier-ignored": (PY, '                    if got is not None and got["result"] == "success" and all(', '                    if False and got is not None and got["result"] == "success" and all(', T),
    "b39-codeql-override-ignored": (PY, "                        if not override_active(c, local):", "                        if True:", T),
    "b39-explicit-ignored": (PY, '    if floor_explicit(a) is not None:\n        return floor_explicit(a), "explicit"', '    if False:\n        return floor_explicit(a), "explicit"', T),
    "b39-probe-blind": (PY, "    return probe.parse_known_args(argv)[0].min_host_free_gb", "    return None", T),
    "b39-floor-never-met": (PY, "    if a.host_free_gb >= floor:\n        return True", "    if True:\n        return True", T),
    "b39-decision-loses-floor": (PY, '**(getattr(a, "last_floor", None) or {})}', "}", T),
    "b39-journal-without-why": (PY, '"floor_kind": kind, "floor_why": why, "pr": n,', '"pr": n,', T),
    "b39-head-of-line-blocks": (PY, "for i, item in enumerate(todo[:PLAN_PROBE_MAX]):", "for i, item in enumerate(todo[:1]):", T),
    "b39-replay-unchecked": (PY, "        if not floor_met(a, state, repo_dir, lease_id, pick[\"pr\"]", "        if False and not floor_met(a, state, repo_dir, lease_id, pick[\"pr\"]", T),
    "b39-kill-switch-ignored": (PY, 'if getattr(a, "floor_by_plan", True) else a.min_host_free_gb', 'if True else a.min_host_free_gb', T),
    "b39-wrapper-forces-floor": (SH, "${MERGER_MIN_HOST_FREE_GB:+--min-host-free-gb=$MERGER_MIN_HOST_FREE_GB}", "--min-host-free-gb=$FLOOR_GB", T),
    "b39-base-runner-cql-deps-unchecked": (PY, 'if local.get("classifier") and cql_skip_ok:', 'if local.get("classifier"):', T),
    "b39-override-env-diverges": ("scripts/localci/runner.py", '    if getattr(get, "__name__", None) == "gh_get":\n        get = None', '    if False:\n        get = None', T),
    "b39-preflight-unfiltered-env": (PY, "rn.trusted_env = lambda base=None: _te(runner_base_env() if base is None else base)", "rn.trusted_env = _te", T),
    "b39-stopped-swallowed": (PY, "    except (Stopped, TickTimeout):\n        raise\n    except Exception as exc:  # noqa: BLE001 — an unreadable diff", "    except Exception as exc:  # noqa: BLE001 — an unreadable diff", T),
}

