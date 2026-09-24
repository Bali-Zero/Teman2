"""The reviewed Codex seat profile: install absent items, never overwrite drift."""

import json
import sys
import tomllib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import install_seat_profile as profile  # noqa: E402

TEXT, ROLES = profile.expected()


class FakeRPC:
    """config/batchWrite as Codex applies a top-level string key."""

    calls: list = []
    collateral = False

    def call(self, method, params):
        assert method == "config/batchWrite"
        FakeRPC.calls.append(params)
        config = profile.Path(profile.os.environ["CODEX_HOME"]) / "config.toml"
        (edit,) = params["edits"]
        line = f"{edit['keyPath']} = {json.dumps(edit['value'])}\n"
        extra = 'approval_policy = "never"\n' if self.collateral else ""
        config.write_text(line + extra + config.read_text())
        return {}

    def close(self):
        pass


@pytest.fixture
def seat(tmp_path, monkeypatch):
    seat = tmp_path / "seat"
    seat.mkdir()
    (seat / "config.toml").write_text('model = "example"\n\n[features]\nhooks = true\n')
    (seat / "config.toml").chmod(0o600)
    FakeRPC.calls = []
    monkeypatch.setattr(FakeRPC, "collateral", False)
    monkeypatch.setattr(profile, "RPC", FakeRPC)
    return seat


def test_fresh_seat_gets_exact_profile_with_backup(seat):
    original = (seat / "config.toml").read_bytes()
    result = profile.install(seat)
    assert (
        result["installed"] and result["before"]["developer_instructions"] == "absent"
    )
    config = tomllib.loads((seat / "config.toml").read_text())
    assert config["developer_instructions"] == TEXT and config["model"] == "example"
    assert (seat / "config.toml").stat().st_mode & 0o777 == 0o600
    for role, data in ROLES.items():
        path = seat / "agents" / f"{role}.toml"
        assert path.read_bytes() == data and path.stat().st_mode & 0o777 == 0o600
    assert (profile.Path(result["backup"]) / "config.toml").read_bytes() == original


def test_matching_seat_is_untouched(seat):
    profile.install(seat)
    FakeRPC.calls = []
    before = (seat / "config.toml").read_bytes()
    result = profile.install(seat)
    assert result["installed"] and result["backup"] is None and FakeRPC.calls == []
    assert (seat / "config.toml").read_bytes() == before


def test_drift_is_reported_and_never_overwritten(seat):
    (seat / "config.toml").write_text('developer_instructions = "operator text"\n')
    (seat / "agents").mkdir()
    (seat / "agents" / "mechanical.toml").write_text('model = "operator"\n')
    result = profile.install(seat)
    assert result["developer_instructions"] == "drift" and not result["installed"]
    assert result["roles"]["mechanical"] == "drift"
    assert (seat / "agents" / "mechanical.toml").read_text() == 'model = "operator"\n'
    assert (
        tomllib.loads((seat / "config.toml").read_text())["developer_instructions"]
        == "operator text"
    )
    assert FakeRPC.calls == []
    assert result["roles"]["routine-explorer"] == "match"


def test_collateral_config_change_is_refused(seat, monkeypatch):
    monkeypatch.setattr(FakeRPC, "collateral", True)
    with pytest.raises(RuntimeError, match="not exact"):
        profile.install(seat)


def test_symlinked_config_is_refused_before_any_write(seat):
    target = seat / "real.toml"
    (seat / "config.toml").rename(target)
    (seat / "config.toml").symlink_to(target)
    with pytest.raises(ValueError, match="symlink"):
        profile.install(seat)
    assert not (seat / "agents").exists() and not (seat / "state").exists()


# Routing contract: which seat does which routine work, and that none widens scope.
@pytest.mark.parametrize(
    "role,model,effort,read_only",
    [
        ("mechanical", "gpt-5.6-luna", "low", True),
        ("routine-explorer", "gpt-5.6-terra", "medium", True),
        ("routine-worker", "gpt-5.6-terra", "medium", False),
        ("code-reviewer", "gpt-5.6-sol", "high", True),
    ],
)
def test_role_pins_model_effort_and_sandbox(role, model, effort, read_only):
    spec = tomllib.loads(ROLES[role].decode())
    assert (spec["name"], spec["model"], spec["model_reasoning_effort"]) == (
        role,
        model,
        effort,
    )
    assert (spec.get("sandbox_mode") == "read-only") is read_only
    assert spec["agents"]["enabled"] is False
    assert role in TEXT


def test_instructions_keep_reviews_and_explicit_assignments_binding():
    assert (
        "never replace required cross-family reviews or mission-colour final gates"
        in TEXT
    )
    assert (
        "Honor required independent reviews and explicit model or effort assignments"
        in TEXT
    )
    for cap in (
        "mechanical 500",
        "routine-explorer and routine-worker 1000",
        "code-reviewer 1500",
    ):
        assert cap in TEXT


def test_role_created_concurrently_is_never_overwritten(seat, monkeypatch):
    real_backup = profile.backup_seat

    def racing_backup(seat_dir, config_file):
        backup = real_backup(seat_dir, config_file)
        (seat_dir / "agents").mkdir(exist_ok=True)
        (seat_dir / "agents" / "mechanical.toml").write_text('model = "operator"\n')
        return backup

    monkeypatch.setattr(profile, "backup_seat", racing_backup)
    result = profile.install(seat)
    assert (seat / "agents" / "mechanical.toml").read_text() == 'model = "operator"\n'
    assert result["roles"]["mechanical"] == "drift" and not result["installed"]
    assert not list((seat / "agents").glob("*.tmp"))


def test_mode_is_restored_when_the_write_is_refused(seat, monkeypatch):
    monkeypatch.setattr(FakeRPC, "collateral", True)
    real_call = FakeRPC.call

    def loosening_call(self, method, params):
        out = real_call(self, method, params)
        (profile.Path(profile.os.environ["CODEX_HOME"]) / "config.toml").chmod(0o644)
        return out

    monkeypatch.setattr(FakeRPC, "call", loosening_call)
    with pytest.raises(RuntimeError, match="not exact"):
        profile.install(seat)
    assert (seat / "config.toml").stat().st_mode & 0o777 == 0o600


def test_competitor_at_the_create_instant_keeps_its_bytes(seat, monkeypatch):
    real_link = profile.os.link

    def racing_link(src, dst):
        profile.Path(dst).write_text('model = "competitor"\n')
        return real_link(src, dst)

    monkeypatch.setattr(profile.os, "link", racing_link)
    result = profile.install(seat)
    for role in ROLES:
        assert (
            seat / "agents" / f"{role}.toml"
        ).read_text() == 'model = "competitor"\n'
        assert result["roles"][role] == "drift"
    assert not list((seat / "agents").glob("*.tmp"))


def test_there_is_no_automatic_removal(monkeypatch, seat):
    monkeypatch.setattr(profile.sys, "argv", ["x", "--seat", str(seat), "--remove"])
    with pytest.raises(SystemExit):
        profile.main()


def test_symlink_or_directory_at_a_role_path_is_drift(seat):
    (seat / "agents").mkdir()
    (seat / "agents" / "mechanical.toml").symlink_to(seat / "missing-target")
    (seat / "agents" / "routine-worker.toml").mkdir()
    result = profile.install(seat)
    assert result["roles"]["mechanical"] == "drift"
    assert result["roles"]["routine-worker"] == "drift"
    assert (seat / "agents" / "mechanical.toml").is_symlink()
    assert (seat / "agents" / "routine-worker.toml").is_dir()
    assert result["roles"]["routine-explorer"] == "match"
