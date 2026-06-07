from cell.fast.red_summary import summarize_pulse


def test_red_summary_names_stale_backup_driver() -> None:
    summary = summarize_pulse(
        "red",
        {"http": "green", "backup": "red"},
        {"backup": {"age_hours": 113.3, "path": "fly_pg_backup.sql.gz"}},
    )

    assert summary.driver_sensors == ["backup"]
    assert "backup" in summary.headline
    assert "113h" in summary.headline
    assert "fly_pg_backup.sql.gz" in summary.headline


def test_red_summary_keeps_tied_red_drivers_in_input_order() -> None:
    summary = summarize_pulse(
        "red",
        {"http": "green", "backup": "red", "cron": "red"},
        {
            "backup": {"age_hours": 75.0},
            "cron": {"failed_jobs": ["a"], "stale_jobs": ["b", "c"], "total": 3},
        },
    )

    assert summary.driver_sensors == ["backup", "cron"]
    assert summary.headline.startswith("backup stale 75h; cron blocked")


def test_red_summary_default_driver_never_empty() -> None:
    summary = summarize_pulse("red", {"qdrant": "red"}, {"qdrant": {}})

    assert summary.driver_sensors == ["qdrant"]
    assert summary.headline == "qdrant=red"


def test_red_summary_green_is_empty() -> None:
    summary = summarize_pulse("green", {"http": "green"}, {"http": {"status_code": 200}})

    assert summary.driver_sensors == []
    assert summary.headline == ""
    assert summary.details == {}
