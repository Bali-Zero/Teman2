"""Delivery/ACK contract for intel_dedup_gateway, with in-memory fakes only."""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("intel_dedup_gateway.py")


class _Env:
    event_id = "evt-synthetic"
    event_type = "intel.collected"
    emitted_by = "test"
    trace_id = "trace-synthetic"
    payload = {"citation_or_url": "https://example.invalid/item", "source": "test"}


class _Redis:
    def __init__(self):
        self.seen = set()

    def sismember(self, key, value):
        return value in self.seen

    def sadd(self, key, value):
        before = len(self.seen)
        self.seen.add(value)
        return int(len(self.seen) != before)

    def expire(self, key, ttl):
        return True


def _load_gateway(monkeypatch, tmp_path, publish, deliveries=1):
    redis = _Redis()
    subscribers = []

    class FakeSubscriber:
        MAX_DELIVERY_ATTEMPTS = 3

        def __init__(self, **kwargs):
            self.acks = []
            self.dlq = []
            subscribers.append(self)

        def listen(self, **kwargs):
            return [_Env()]

        def get_delivery_count(self, env):
            return deliveries

        def ack(self, env):
            self.acks.append(env.event_id)

        def park_to_dlq(self, env, reason):
            self.dlq.append((env.event_id, reason))

    eventbus = types.ModuleType("eventbus")
    eventbus.EventSubscriber = FakeSubscriber
    eventbus.publish = publish
    eventbus.beat = lambda *a, **kw: None
    eventbus.start_background_beater = lambda *a, **kw: None
    publisher = types.ModuleType("eventbus.publisher")
    publisher._client = lambda: redis
    monkeypatch.setitem(sys.modules, "eventbus", eventbus)
    monkeypatch.setitem(sys.modules, "eventbus.publisher", publisher)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    spec = importlib.util.spec_from_file_location("intel_dedup_gateway_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, redis, subscribers


def test_handler_failure_does_not_ack_or_mark_seen(monkeypatch, tmp_path):
    def publish(*args, **kwargs):
        raise TimeoutError("synthetic failure")

    gateway, redis, subscribers = _load_gateway(monkeypatch, tmp_path, publish)

    assert gateway.main() == 0
    assert subscribers[0].acks == []
    assert redis.seen == set()


def test_handler_success_acks_exactly_once_and_marks_seen(monkeypatch, tmp_path):
    gateway, redis, subscribers = _load_gateway(
        monkeypatch, tmp_path, lambda *a, **kw: "deduped-synthetic"
    )

    assert gateway.main() == 0
    assert subscribers[0].acks == ["evt-synthetic"]
    assert len(redis.seen) == 1


def test_failure_on_the_last_allowed_delivery_parks_with_the_error_class_only(monkeypatch, tmp_path):
    def publish(*args, **kwargs):
        raise TimeoutError("synthetic secret-looking text")

    gateway, redis, subscribers = _load_gateway(monkeypatch, tmp_path, publish, deliveries=5)

    assert gateway.main() == 0
    assert subscribers[0].dlq == [("evt-synthetic", "intel-dedup:TimeoutError")]
    assert subscribers[0].acks == []
    assert redis.seen == set()


def test_failure_below_the_bound_is_left_pending_not_parked(monkeypatch, tmp_path):
    def publish(*args, **kwargs):
        raise TimeoutError("synthetic")

    gateway, _, subscribers = _load_gateway(monkeypatch, tmp_path, publish, deliveries=4)

    assert gateway.main() == 0
    assert subscribers[0].dlq == [] and subscribers[0].acks == []


def test_duplicate_is_still_acked_once_without_publishing(monkeypatch, tmp_path):
    published = []
    gateway, redis, subscribers = _load_gateway(
        monkeypatch, tmp_path, lambda *a, **kw: published.append(a) or "x"
    )
    redis.seen.add("hash:" + gateway._content_hash(_Env.payload))

    assert gateway.main() == 0
    assert subscribers[0].acks == ["evt-synthetic"]
    assert published == []
