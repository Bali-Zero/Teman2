from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "audit/live_runtime_vs_genome.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("live_runtime_vs_genome", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_launchctl_list_filters_supported_prefixes() -> None:
    mod = _load_module()

    result = mod.parse_launchctl_list(
        "PID\tStatus\tLabel\n"
        "-\t0\tcom.nuzantara.sentinel\n"
        "123\t1\tcom.balizero.wr2.supervisor\n"
        "99\t0\tcom.apple.ignore\n"
    )

    assert result == {
        "com.nuzantara.sentinel": {"pid": None, "status": 0},
        "com.balizero.wr2.supervisor": {"pid": 123, "status": 1},
    }


def test_parse_crontab_skips_env_and_comments() -> None:
    mod = _load_module()

    result = mod.parse_crontab(
        "SHELL=/bin/zsh\n"
        "# disabled\n"
        "*/10 * * * * cd /repo && ./scripts/fly-watcher.sh\n"
        "@reboot /Users/me/bin/startup.sh\n"
    )

    assert [entry["schedule"] for entry in result] == ["*/10 * * * *", "@reboot"]
    assert result[0]["script_tokens"] == ["./scripts/fly-watcher.sh"]
    assert result[1]["script_tokens"] == ["/Users/me/bin/startup.sh"]


def test_parse_plist_label_listing_accepts_tab_labels_and_paths() -> None:
    mod = _load_module()

    result = mod.parse_plist_label_listing(
        "com.cell.organism\tcom.cell.organism.plist\n"
        "/Users/me/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist\n"
        "com.apple.ignore\tcom.apple.ignore.plist\n"
    )

    assert sorted(result) == [
        "com.cell.organism",
        "com.matagaruda.sentinel.hourly",
    ]


def test_load_registry_filters_runtime_scope(tmp_path: Path) -> None:
    mod = _load_module()
    registry = tmp_path / "organs.yaml"
    registry.write_text(
        "organs:\n"
        "  - id: pro.sentinel\n"
        "    runtime: pro_launchd\n"
        "    owner_module: scripts/pro.sh\n"
        "    recovery_params:\n"
        "      label: com.nuzantara.pro\n"
        "  - id: mata_garuda.sentinel_daily.mini\n"
        "    runtime: mini_launchd\n"
        "    owner_module: apps/mata-garuda/scripts/run_sentinel.sh\n"
        "    recovery_params:\n"
        "      label: com.matagaruda.sentinel.daily\n",
        encoding="utf-8",
    )

    result = mod.load_registry(registry, runtimes={"pro_launchd"})

    assert sorted(result["labels"]) == ["com.nuzantara.pro"]
    assert "com.matagaruda.sentinel.daily" not in result["labels"]
    assert "apps/mata-garuda/scripts/run_sentinel.sh" not in result["modules"]


def test_compare_runtime_flags_unmanaged_launchd_and_cron() -> None:
    mod = _load_module()
    registry = {
        "labels": {
            "com.nuzantara.sentinel": {
                "id": "pro.sentinel",
                "enabled": True,
                "runtime": "pro_launchd",
            }
        },
        "modules": {
            "scripts/known.sh": {"id": "pro.known"},
            "known.sh": {"id": "pro.known"},
        },
    }
    launchctl = {
        "com.nuzantara.sentinel": {"pid": None, "status": 0},
        "com.balizero.unmapped": {"pid": 123, "status": 1},
        "com.balizero.failed": {"pid": None, "status": 1},
    }
    plists = {
        "com.balizero.unmapped": {"source": "com.balizero.unmapped.plist"},
        "com.balizero.plist-only": {"source": "com.balizero.plist-only.plist"},
    }
    cron = mod.parse_crontab(
        "0 * * * * /repo/scripts/known.sh\n"
        "5 * * * * /repo/scripts/unknown.sh\n"
    )

    diff = mod.compare_runtime(registry, launchctl, plists, cron)

    assert diff["summary"]["unmanaged_launchctl"] == 2
    assert diff["summary"]["unmanaged_launchctl_running"] == 1
    assert diff["summary"]["unmanaged_launchctl_failed"] == 1
    assert diff["summary"]["unmanaged_plists"] == 2
    assert diff["summary"]["unmanaged_plist_only"] == 1
    assert diff["summary"]["unmanaged_cron"] == 1
    assert diff["unmanaged_cron"][0]["command"] == "/repo/scripts/unknown.sh"


def test_compare_runtime_covers_cron_by_explicit_match() -> None:
    mod = _load_module()
    registry = {
        "labels": {},
        "modules": {},
        "cron_matches": {
            "cron-state.sh heartbeat-pro": {
                "id": "pro.heartbeat_touch",
                "owner_module": "scripts/cron-state.sh",
                "enabled": True,
            }
        },
    }
    cron = mod.parse_crontab(
        "0 * * * * /Users/nuzantara/scripts/cron-state.sh heartbeat-pro "
        "bash -lc 'touch ~/.pro_heartbeat'\n"
        "5 * * * * /repo/scripts/unknown.sh\n"
    )

    diff = mod.compare_runtime(registry, {}, {}, cron)

    assert diff["summary"]["unmanaged_cron"] == 1
    assert diff["unmanaged_cron"][0]["command"] == "/repo/scripts/unknown.sh"


def test_compare_runtime_flags_disabled_registry_entries_still_live() -> None:
    mod = _load_module()
    registry = {
        "labels": {
            "com.nuzantara.enabled": {
                "id": "pro.enabled",
                "enabled": True,
                "runtime": "pro_launchd",
            },
            "com.nuzantara.disabled": {
                "id": "pro.disabled",
                "enabled": False,
                "runtime": "pro_launchd",
            },
        },
        "modules": {
            "scripts/enabled.sh": {
                "id": "pro.enabled",
                "owner_module": "scripts/enabled.sh",
                "enabled": True,
            },
            "enabled.sh": {
                "id": "pro.enabled",
                "owner_module": "scripts/enabled.sh",
                "enabled": True,
            },
            "scripts/disabled.sh": {
                "id": "pro.disabled",
                "owner_module": "scripts/disabled.sh",
                "enabled": False,
            },
            "disabled.sh": {
                "id": "pro.disabled",
                "owner_module": "scripts/disabled.sh",
                "enabled": False,
            },
        },
    }
    launchctl = {
        "com.nuzantara.enabled": {"pid": 123, "status": 0},
        "com.nuzantara.disabled": {"pid": 456, "status": 0},
    }
    plists = {
        "com.nuzantara.disabled": {"source": "com.nuzantara.disabled.plist"},
    }
    cron = mod.parse_crontab(
        "0 * * * * /repo/scripts/enabled.sh\n"
        "5 * * * * /repo/scripts/disabled.sh\n"
    )

    diff = mod.compare_runtime(registry, launchctl, plists, cron)

    assert diff["summary"]["unmanaged_launchctl"] == 0
    assert diff["summary"]["unmanaged_plists"] == 0
    assert diff["summary"]["unmanaged_cron"] == 0
    assert diff["summary"]["disabled_registry_launchctl"] == 1
    assert diff["summary"]["disabled_registry_plists"] == 1
    assert diff["summary"]["disabled_registry_cron"] == 1
    assert "com.nuzantara.disabled" in diff["disabled_registry_launchctl"]
    assert diff["disabled_registry_cron"][0]["command"] == "/repo/scripts/disabled.sh"


def test_main_fail_on_drift_returns_nonzero(tmp_path: Path, capsys) -> None:
    mod = _load_module()
    registry = tmp_path / "organs.yaml"
    registry.write_text(
        "organs:\n"
        "  - id: pro.sentinel\n"
        "    owner_module: scripts/sentinel.sh\n"
        "    recovery_params:\n"
        "      label: com.nuzantara.sentinel\n",
        encoding="utf-8",
    )
    launchctl = tmp_path / "launchctl.txt"
    launchctl.write_text(
        "PID\tStatus\tLabel\n"
        "123\t1\tcom.balizero.unmapped\n",
        encoding="utf-8",
    )
    crontab = tmp_path / "cron.txt"
    crontab.write_text("", encoding="utf-8")
    plists = tmp_path / "plists.txt"
    plists.write_text("", encoding="utf-8")

    rc = mod.main(
        [
            "--registry",
            str(registry),
            "--launchctl-file",
            str(launchctl),
            "--crontab-file",
            str(crontab),
            "--plist-label-file",
            str(plists),
            "--no-local-probe",
            "--fail-on-drift",
        ]
    )
    captured = capsys.readouterr()

    assert rc == 1
    assert "com.balizero.unmapped" in captured.out


def test_main_fail_on_drift_returns_nonzero_for_disabled_live(
    tmp_path: Path,
) -> None:
    mod = _load_module()
    registry = tmp_path / "organs.yaml"
    registry.write_text(
        "organs:\n"
        "  - id: pro.disabled\n"
        "    enabled: false\n"
        "    owner_module: scripts/disabled.sh\n"
        "    recovery_params:\n"
        "      label: com.nuzantara.disabled\n",
        encoding="utf-8",
    )
    launchctl = tmp_path / "launchctl.txt"
    launchctl.write_text(
        "PID\tStatus\tLabel\n"
        "123\t0\tcom.nuzantara.disabled\n",
        encoding="utf-8",
    )
    crontab = tmp_path / "cron.txt"
    crontab.write_text("", encoding="utf-8")
    plists = tmp_path / "plists.txt"
    plists.write_text("", encoding="utf-8")

    rc = mod.main(
        [
            "--registry",
            str(registry),
            "--launchctl-file",
            str(launchctl),
            "--crontab-file",
            str(crontab),
            "--plist-label-file",
            str(plists),
            "--no-local-probe",
            "--fail-on-drift",
        ]
    )

    assert rc == 1
