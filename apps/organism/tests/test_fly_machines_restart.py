"""Tests for fly_machines_restart actuator (W31 2026-05-23).

Covers:
- _build_argv with and without machine_id
- _build_argv with skip_health_checks flag
- _dry_run returns expected argv
- ValueError when app param missing
- Registry registration (build_actuator_registry includes it)
- dispatch.py SAFE_ACTUATORS contains the name (security guard)
"""
import pytest

from organism.actuators.fly_machines_restart import FlyMachinesRestart


def test_build_argv_minimal():
    a = FlyMachinesRestart()
    argv = a._build_argv({"app": "nuzantara-rag"})
    assert argv == ["fly", "machines", "restart", "-a", "nuzantara-rag"]


def test_build_argv_with_machine_id():
    a = FlyMachinesRestart()
    argv = a._build_argv({"app": "nuzantara-rag", "machine": "7847d95ce257d8"})
    assert argv == [
        "fly", "machines", "restart", "-a", "nuzantara-rag", "7847d95ce257d8",
    ]


def test_build_argv_machine_id_alias():
    """machine_id alias also works."""
    a = FlyMachinesRestart()
    argv = a._build_argv({"app": "x", "machine_id": "abc"})
    assert argv == ["fly", "machines", "restart", "-a", "x", "abc"]


def test_build_argv_skip_health_checks():
    a = FlyMachinesRestart()
    argv = a._build_argv(
        {"app": "nuzantara-rag", "skip_health_checks": True}
    )
    assert argv == [
        "fly", "machines", "restart", "-a", "nuzantara-rag",
        "--skip-health-checks",
    ]


def test_build_argv_skip_health_checks_with_machine():
    a = FlyMachinesRestart()
    argv = a._build_argv({
        "app": "nuzantara-rag",
        "machine": "7847d95ce257d8",
        "skip_health_checks": True,
    })
    assert argv == [
        "fly", "machines", "restart", "-a", "nuzantara-rag",
        "7847d95ce257d8", "--skip-health-checks",
    ]


@pytest.mark.asyncio
async def test_dry_run_returns_argv():
    a = FlyMachinesRestart()
    result = await a._dry_run({"app": "nuzantara-rag"})
    assert result == {
        "would_run": ["fly", "machines", "restart", "-a", "nuzantara-rag"],
    }


@pytest.mark.asyncio
async def test_dry_run_missing_app():
    a = FlyMachinesRestart()
    result = await a._dry_run({})
    assert "would_restart" in result
    assert "missing" in result["would_restart"].lower()


@pytest.mark.asyncio
async def test_execute_raises_on_missing_app():
    a = FlyMachinesRestart()
    with pytest.raises(ValueError, match="requires 'app'"):
        await a._execute({})


def test_registry_includes_restart(fake_redis):
    """build_actuator_registry exposes fly_machines_restart."""
    from organism.actuators import build_actuator_registry
    reg = build_actuator_registry(redis=fake_redis)
    assert "fly_machines_restart" in reg
    assert isinstance(reg["fly_machines_restart"], FlyMachinesRestart)


def test_safe_actuators_includes_restart():
    """dispatch.py SAFE_ACTUATORS whitelist contains the actuator name.

    Without this, even a correctly-built rule referencing
    fly_machines_restart would be rejected at dispatch time.
    """
    from organism.supervisor.dispatch import SAFE_ACTUATORS
    assert "fly_machines_restart" in SAFE_ACTUATORS


def test_name_attribute():
    assert FlyMachinesRestart.name == "fly_machines_restart"
