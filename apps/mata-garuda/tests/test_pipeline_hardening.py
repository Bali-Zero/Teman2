"""Tests for the pipeline-hardening pass (2026-06-30): MAXLEN cap + health monitor."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from mata_garuda.workers import base_worker, pipeline_health
from mata_garuda.tools import stream_tools


class TestStreamMaxlen:
    """Council fix #1: every XADD must MAXLEN-cap so the in-memory stream is bounded."""

    def test_base_worker_publish_uses_maxlen(self):
        with patch.object(base_worker, "redis_cmd", return_value="1-0") as m:
            base_worker.stream_publish("garuda:raw", {"title": "x", "url": "u"})
        argv = m.call_args.args
        assert argv[0] == "XADD"
        assert "MAXLEN" in argv and "~" in argv
        # MAXLEN ~ N must come BEFORE the * id (Redis syntax)
        assert argv.index("MAXLEN") < argv.index("*")

    def test_stream_tools_publish_uses_maxlen(self):
        with patch.object(stream_tools, "_redis_cmd", return_value="1-0") as m:
            stream_tools.stream_publish("t", "http://u", "src", "body", stream="garuda:raw")
        argv = m.call_args.args
        assert argv[0] == "XADD"
        assert "MAXLEN" in argv and "~" in argv
        assert argv.index("MAXLEN") < argv.index("*")

    def test_maxlen_value_from_config(self):
        from mata_garuda.config import STREAM_MAXLEN
        assert isinstance(STREAM_MAXLEN, int) and STREAM_MAXLEN >= 1000


class TestPipelineHealthAssess:
    """The monitor must read OUTPUT (lag/freshness/RAM), not exit-0, and grade it."""

    def _mock_redis(self, xlens, lags, newest_age_ms_back, now_ms=2_000_000_000_000):
        """Build a fake _r() that answers XLEN/XINFO/XREVRANGE/TIME."""
        def fake_r(*args):
            cmd = args[0]
            if cmd == "TIME":
                return f"{now_ms // 1000}\n0"
            if cmd == "XLEN":
                return str(xlens.get(args[1], 0))
            if cmd == "XREVRANGE":
                stream = args[1]
                age = newest_age_ms_back.get(stream, 0)
                eid = now_ms - age
                return f"{eid}-0\ntitle\nx"
            if cmd == "XINFO" and args[1] == "GROUPS":
                # flat: name <g> ... lag <n> per group
                out = []
                for g, lag in lags.items():
                    out += ["name", g, "lag", str(lag)]
                return "\n".join(out)
            return ""
        return fake_r

    def test_green_when_all_nominal(self):
        fake = self._mock_redis(
            xlens={"garuda:raw": 100, "garuda:enriched": 200, "garuda:alerts": 10},
            lags={"classifier": 0, "nlm_feeder": 50},
            newest_age_ms_back={"garuda:raw": 3_600_000},  # 1h old
        )
        with patch.object(pipeline_health, "_r", side_effect=fake), \
             patch.object(pipeline_health, "_nlm_source_total", return_value=900), \
             patch.object(pipeline_health, "_load_state", return_value={}):
            r = pipeline_health.assess()
        assert r["verdict"] == "GREEN"

    def test_red_when_stream_over_maxlen(self):
        fake = self._mock_redis(
            xlens={"garuda:raw": 999_999, "garuda:enriched": 10, "garuda:alerts": 1},
            lags={"classifier": 0},
            newest_age_ms_back={"garuda:raw": 3_600_000},
        )
        with patch.object(pipeline_health, "_r", side_effect=fake), \
             patch.object(pipeline_health, "STREAM_MAXLEN", 100_000), \
             patch.object(pipeline_health, "_nlm_source_total", return_value=900), \
             patch.object(pipeline_health, "_load_state", return_value={}):
            r = pipeline_health.assess()
        assert r["verdict"] == "RED"
        assert any("MAXLEN" in f for f in r["findings"])

    def test_red_when_harvest_stale(self):
        fake = self._mock_redis(
            xlens={"garuda:raw": 100, "garuda:enriched": 100, "garuda:alerts": 1},
            lags={"classifier": 0},
            newest_age_ms_back={"garuda:raw": 100 * 3_600_000},  # 100h old
        )
        with patch.object(pipeline_health, "_r", side_effect=fake), \
             patch.object(pipeline_health, "_nlm_source_total", return_value=900), \
             patch.object(pipeline_health, "_load_state", return_value={}):
            r = pipeline_health.assess()
        assert r["verdict"] == "RED"
        assert any("harvest stalled" in f for f in r["findings"])

    def test_red_when_lag_high_and_growing(self):
        fake = self._mock_redis(
            xlens={"garuda:raw": 100, "garuda:enriched": 20000, "garuda:alerts": 1},
            lags={"nlm_feeder": 9000},
            newest_age_ms_back={"garuda:raw": 3_600_000},
        )
        # prev lag lower → growing
        with patch.object(pipeline_health, "_r", side_effect=fake), \
             patch.object(pipeline_health, "_nlm_source_total", return_value=900), \
             patch.object(pipeline_health, "_load_state",
                          return_value={"lags": {"nlm_feeder": 5000}, "nlm_total": 900}):
            r = pipeline_health.assess()
        assert r["verdict"] == "RED"
        assert any("growing" in f for f in r["findings"])

    def test_yellow_when_lag_high_but_draining(self):
        fake = self._mock_redis(
            xlens={"garuda:raw": 100, "garuda:enriched": 20000, "garuda:alerts": 1},
            lags={"nlm_feeder": 9000},
            newest_age_ms_back={"garuda:raw": 3_600_000},
        )
        # prev lag HIGHER → draining
        with patch.object(pipeline_health, "_r", side_effect=fake), \
             patch.object(pipeline_health, "_nlm_source_total", return_value=900), \
             patch.object(pipeline_health, "_load_state",
                          return_value={"lags": {"nlm_feeder": 11000}, "nlm_total": 900}):
            r = pipeline_health.assess()
        assert r["verdict"] == "YELLOW"
        assert any("draining" in f for f in r["findings"])
