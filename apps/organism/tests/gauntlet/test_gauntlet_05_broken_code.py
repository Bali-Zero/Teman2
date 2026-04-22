"""Scenario 5: broken code pushed to main. CI fails, emits ci_test_failure.
No dedicated rule for this kind, so Supervisor defers to human.
Gauntlet-valid behavior: don't auto-rollback random CI failures.
"""
import pytest
from organism.schemas import Severity


@pytest.mark.gauntlet
@pytest.mark.asyncio
async def test_gauntlet_05_broken_code(staging_organism):
    await staging_organism.emit(
        kind="ci_test_failure",
        source="github.actions",
        severity=Severity.ERROR,
        payload={"workflow": "tests.yml", "branch": "main", "run_url": "https://x"},
    )

    await staging_organism.drive_supervisor()

    # No rule matches ci_test_failure in BASE_YAML → defer_to_human
    decisions = staging_organism.decisions_for_actuator("defer_to_human")
    assert len(decisions) == 1, (
        "Supervisor should defer CI failures to human (no auto-handling in base rules)"
    )
