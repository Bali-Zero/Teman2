"""B35: the run budget (RUN_TIMEOUT_S), the bounds derived from it, and the heartbeat window of pro.localci_merger."""
from merger_mutants import MERGER_T, PY

REG = "apps/organism/organism/organs_registry.yaml"
B35 = (f"{MERGER_T}::test_the_timeouts_hold_a_cold_build_inside_one_tick", f"{MERGER_T}::test_the_plan_step_outlasts_a_cold_deps_build",
       f"{MERGER_T}::test_a_guarded_runner_is_given_the_whole_budget_it_was_handed")
HB = "  type: cron\n  expected_hb_seconds: {}\n  owner_module: scripts/localci/localci_merger_tick.sh"

ROWS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "b35-run-budget-back-to-5400": (PY, "RUN_TIMEOUT_S = 7200\n", "RUN_TIMEOUT_S = 5400\n", B35),
    "b35-run-budget-under-measured-need": (PY, "RUN_TIMEOUT_S = 7200\n", "RUN_TIMEOUT_S = 6500\n", B35),
    "b35-run-default-not-the-constant": (PY, "type=int, default=RUN_TIMEOUT_S,", "type=int, default=5400,", B35),
    "b35-tick-watchdog-not-raised": (PY, "TICK_TIMEOUT_S = 16200 ", "TICK_TIMEOUT_S = 14400 ", B35),
    "b35-tick-watchdog-no-margin": (PY, "TICK_TIMEOUT_S = 16200 ", "TICK_TIMEOUT_S = 15600 ", B35),
    "b35-run-step-hardcodes-5400": (PY, 'step("run", [*runner, "run", "--run-dir", str(run_dir)], a.run_timeout)',
                                    'step("run", [*runner, "run", "--run-dir", str(run_dir)], 5400)', B35),
    "b35-guard-deadline-capped": (PY, "deadline = time.monotonic() + timeout\n", "deadline = time.monotonic() + min(timeout, 5400)\n", B35),
    "b35-guard-deadline-capped-7000": (PY, "deadline = time.monotonic() + timeout\n", "deadline = time.monotonic() + min(timeout, 7000)\n", B35),
    "b35-heartbeat-window-not-raised": (REG, HB.format(6000), HB.format(5400), B35),
}
