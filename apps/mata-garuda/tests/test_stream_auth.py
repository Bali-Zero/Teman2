"""Test stream_tools delegates to the authed base_worker.redis_cmd (harvest-stall fix).

The harvester (run_sentinel_py.harvest → stream_publish → _redis_cmd) was running
bare `redis-cli` with NO auth, so every XADD silently failed (NOAUTH) and
garuda:raw froze for days. _redis_cmd must now route through base_worker.redis_cmd,
which carries REDISCLI_AUTH + canonical host + abs-path.
"""
from __future__ import annotations

from unittest.mock import patch

from mata_garuda.tools import stream_tools
from mata_garuda.workers import base_worker


class TestStreamToolsUsesAuthedPath:
    def test_redis_cmd_delegates_to_base_worker(self):
        # _redis_cmd must call base_worker.redis_cmd, not raw subprocess.run
        with patch.object(base_worker, "redis_cmd", return_value="OK") as m_bw, \
             patch("subprocess.run") as m_raw:
            out = stream_tools._redis_cmd("PING")
        assert out == "OK"
        m_bw.assert_called_once()
        assert m_bw.call_args.args[0] == "PING"
        m_raw.assert_not_called()   # never bypasses the authed path

    def test_publish_routes_through_authed_path(self):
        # stream_publish must reach the authed path with a MAXLEN-capped XADD
        with patch.object(base_worker, "redis_cmd", return_value="1-0") as m_bw:
            res = stream_tools.stream_publish(
                "t", "http://u", "src", "body", stream="garuda:raw")
        assert "[SUCCESS]" in res
        argv = m_bw.call_args.args
        assert argv[0] == "XADD"
        assert "MAXLEN" in argv and "~" in argv          # cap preserved
        assert argv.index("MAXLEN") < argv.index("*")     # before the * id

    def test_redis_cmd_propagates_base_worker_error(self):
        # if the authed path errors (e.g. real NOAUTH), the error surfaces — not swallowed
        with patch.object(base_worker, "redis_cmd",
                          return_value="[ERROR] redis-cli: NOAUTH Authentication required"):
            out = stream_tools._redis_cmd("XADD", "garuda:raw", "*", "k", "v")
        assert out.startswith("[ERROR]")

    def test_no_circular_import(self):
        # base_worker must NOT import stream_tools (would deadlock the delegation)
        import inspect
        src = inspect.getsource(base_worker)
        assert "import stream_tools" not in src
        assert "from mata_garuda.tools.stream_tools" not in src
