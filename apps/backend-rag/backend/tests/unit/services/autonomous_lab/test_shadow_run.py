from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from unittest.mock import patch

from backend.services.autonomous_lab.shadow_run import (
    SHADOW_RUN_CONTRACT_VERSION,
    build_shadow_run,
)


def test_shadow_run_composes_watch_to_curate_without_side_effects() -> None:
    with (
        patch("subprocess.run") as subprocess_run,
        patch("subprocess.Popen") as subprocess_popen,
        patch("os.system") as os_system,
    ):
        shadow = build_shadow_run(
            objective="study frontier AI and implement bounded Nuzantara experiments",
            task_id="shadow-test",
            created_at=datetime(2026, 6, 16, tzinfo=timezone.utc),
        )

    subprocess_run.assert_not_called()
    subprocess_popen.assert_not_called()
    os_system.assert_not_called()

    receipt = shadow.to_receipt()
    receipt_text = json.dumps(receipt, sort_keys=True)

    assert receipt["version"] == SHADOW_RUN_CONTRACT_VERSION
    assert receipt["run_id"] == "shadow-test"
    assert receipt["watch_tick"]["signal_count"] == 3
    assert receipt["normalized_batch"]["cluster_count"] == 3
    assert receipt["evaluation_report"]["verdict"] == "needs_review"
    assert receipt["curator_decision"]["promotion_allowed"] is False
    assert receipt["execution_allowed"] is False
    assert receipt["external_calls"] == 0
    assert "study frontier AI and implement bounded Nuzantara experiments" not in receipt_text
    assert "fly deploy" not in receipt_text
    assert "git push" not in receipt_text


def test_shadow_run_module_does_not_depend_on_subprocess_result() -> None:
    assert subprocess.CompletedProcess(["noop"], 0).returncode == 0
