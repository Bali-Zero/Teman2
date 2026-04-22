import pytest
from unittest.mock import AsyncMock, patch

from organism.schemas import Event, Severity, IncidentContext
from organism.supervisor.ollama_classifier import (
    OllamaClassifier,
    VALID_BUCKETS,
    DEFAULT_BUCKET,
)
from organism.supervisor.incident_context import IncidentStore


def _events(kinds):
    return [
        Event(
            severity=Severity.WARNING,
            source="guardian.system_doctor",
            kind=k,
            payload={"count": 1},
            correlation_id="c-test",
            host="Pro",
        )
        for k in kinds
    ]


class _MockProc:
    def __init__(self, stdout: bytes):
        self._stdout = stdout
        self.returncode = 0

    async def communicate(self):
        return self._stdout, b""

    def kill(self):
        pass

    async def wait(self):
        return


class _HangingProc:
    returncode = None

    async def communicate(self):
        import asyncio
        await asyncio.sleep(3600)

    def kill(self):
        pass

    async def wait(self):
        return


@pytest.mark.asyncio
async def test_classify_hardware_bucket(fake_redis):
    clf = OllamaClassifier(incident_store=IncidentStore(redis=fake_redis))
    with patch(
        "asyncio.create_subprocess_exec",
        AsyncMock(return_value=_MockProc(b"hardware\n")),
    ):
        bucket = await clf._classify(_events(["disk_fill"]))
    assert bucket == "hardware"


@pytest.mark.asyncio
async def test_classify_unknown_when_model_returns_gibberish(fake_redis):
    clf = OllamaClassifier(incident_store=IncidentStore(redis=fake_redis))
    with patch(
        "asyncio.create_subprocess_exec",
        AsyncMock(return_value=_MockProc(b"something_not_in_taxonomy")),
    ):
        bucket = await clf._classify(_events(["novel"]))
    assert bucket == DEFAULT_BUCKET


@pytest.mark.asyncio
async def test_classify_strips_punctuation(fake_redis):
    """Model may emit 'deploy.' or 'deploy:' with trailing punctuation."""
    clf = OllamaClassifier(incident_store=IncidentStore(redis=fake_redis))
    with patch(
        "asyncio.create_subprocess_exec",
        AsyncMock(return_value=_MockProc(b"deploy.\n")),
    ):
        bucket = await clf._classify(_events(["rollback"]))
    assert bucket == "deploy"


@pytest.mark.asyncio
async def test_classify_scans_full_output_as_fallback(fake_redis):
    """If first token isn't a bucket, fall back to scanning full response."""
    clf = OllamaClassifier(incident_store=IncidentStore(redis=fake_redis))
    with patch(
        "asyncio.create_subprocess_exec",
        AsyncMock(return_value=_MockProc(b"Analysis: this looks like a network issue.")),
    ):
        bucket = await clf._classify(_events(["conn_lost"]))
    assert bucket == "network"


@pytest.mark.asyncio
async def test_classify_empty_events_returns_unknown(fake_redis):
    clf = OllamaClassifier(incident_store=IncidentStore(redis=fake_redis))
    bucket = await clf._classify([])
    assert bucket == DEFAULT_BUCKET


@pytest.mark.asyncio
async def test_classify_timeout_returns_unknown(fake_redis):
    clf = OllamaClassifier(incident_store=IncidentStore(redis=fake_redis))
    with patch(
        "asyncio.create_subprocess_exec",
        AsyncMock(return_value=_HangingProc()),
    ):
        with patch("asyncio.wait_for", side_effect=__import__("asyncio").TimeoutError):
            bucket = await clf._classify(_events(["novel"]))
    assert bucket == DEFAULT_BUCKET


@pytest.mark.asyncio
async def test_classify_ollama_not_found_returns_unknown(fake_redis):
    clf = OllamaClassifier(
        incident_store=IncidentStore(redis=fake_redis),
        ollama_binary="/nonexistent/ollama",
    )
    with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
        bucket = await clf._classify(_events(["disk_fill"]))
    assert bucket == DEFAULT_BUCKET


@pytest.mark.asyncio
async def test_enqueue_returns_task_that_persists_bucket(fake_redis):
    store = IncidentStore(redis=fake_redis)
    # Seed context so hydrate returns existing one
    ctx = IncidentContext(correlation_id="c-e1", events=[])
    await store.persist(ctx)
    clf = OllamaClassifier(incident_store=store)
    with patch(
        "asyncio.create_subprocess_exec",
        AsyncMock(return_value=_MockProc(b"data\n")),
    ):
        task = clf.enqueue("c-e1", _events(["backup_failed"]))
        result = await task
    assert result == "data"
    hydrated = await store.hydrate("c-e1")
    assert hydrated.ollama_bucket == "data"


@pytest.mark.asyncio
async def test_enqueue_returns_asyncio_task(fake_redis):
    """enqueue() must return asyncio.Task so caller can fire-and-forget."""
    import asyncio
    store = IncidentStore(redis=fake_redis)
    clf = OllamaClassifier(incident_store=store)
    with patch(
        "asyncio.create_subprocess_exec",
        AsyncMock(return_value=_MockProc(b"network\n")),
    ):
        task = clf.enqueue("c-e2", _events(["dns_fail"]))
        assert isinstance(task, asyncio.Task)
        await task  # clean up


@pytest.mark.asyncio
async def test_summarize_includes_kind_source_severity(fake_redis):
    clf = OllamaClassifier(incident_store=IncidentStore(redis=fake_redis))
    summary = OllamaClassifier._summarize(_events(["disk_fill", "cpu_spike"]))
    assert "kind=disk_fill" in summary
    assert "source=guardian.system_doctor" in summary
    assert "severity=warning" in summary
    assert summary.count("\n") == 1  # two events → one newline


@pytest.mark.asyncio
async def test_classify_all_valid_buckets_round_trip(fake_redis):
    """Each bucket in VALID_BUCKETS must be recognizable in classifier output."""
    clf = OllamaClassifier(incident_store=IncidentStore(redis=fake_redis))
    for bucket in VALID_BUCKETS:
        with patch(
            "asyncio.create_subprocess_exec",
            AsyncMock(return_value=_MockProc(f"{bucket}\n".encode())),
        ):
            result = await clf._classify(_events(["probe"]))
        assert result == bucket
