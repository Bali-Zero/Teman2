"""Tests that bridge constants are exported by config."""
from mata_garuda import config


def test_bridge_stream_constants_exist():
    assert config.STREAM_BRIDGE_OUTBOUND == "bridge:outbound"
    assert config.STREAM_BRIDGE_INBOUND == "bridge:inbound"


def test_nexus_gaps_stream_exists():
    assert config.STREAM_NEXUS_GAPS == "nexus:gaps"


def test_bridge_api_key_env_name():
    assert config.BRIDGE_API_KEY_ENV == "BRIDGE_API_KEY"


def test_bridge_backend_url_default():
    assert config.BRIDGE_BACKEND_URL.startswith("https://")


def test_bridge_cursor_path_default():
    assert "bridge_cursor.json" in str(config.BRIDGE_CURSOR_PATH)


def test_bridge_polling_constants_exist():
    assert config.BRIDGE_POLL_INTERVAL_DAY_S == 30
    assert config.BRIDGE_POLL_INTERVAL_NIGHT_S == 300
    assert config.BRIDGE_PULL_LIMIT == 50
    assert config.BRIDGE_PUSH_BATCH == 10
    assert config.BRIDGE_HTTP_TIMEOUT_S == 15
