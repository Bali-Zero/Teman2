"""The Gemini streaming call must AWAIT the SDK coroutine before iterating it.

WHY THIS FILE EXISTS

`GenAIClient.generate_content_stream` used to do:

    async for chunk in self._client.aio.models.generate_content_stream(...):

`google-genai`'s `AsyncModels.generate_content_stream` is a **coroutine
function** -- it must be awaited to obtain the `AsyncIterator`, despite a return
annotation that reads `AsyncIterator[...]`. Iterating the call directly raises
`TypeError: 'async for' requires an object with __aiter__ method, got coroutine`
on EVERY invocation. The caller catches it, logs "LLM stream failed", and
degrades in silence -- so the path was 100% broken with nothing red anywhere.

WHY CI DID NOT CATCH IT, WHICH IS THE MORE IMPORTANT HALF

`test_genai_client.py::test_generate_content_stream` mocked the SDK entrypoint
with an async GENERATOR function, and carried a comment asserting the mock
"must return async generator directly". The real SDK has never had that shape
in either version this repo touches. The test therefore answered where
production raised -- a mock that contradicts the contract is not a test, it is
a second implementation that only the test suite ever runs.

So a second mock, however carefully shaped, cannot be the whole guard here:
whatever shape we write is a shape WE chose. The first test below therefore
asserts against the INSTALLED SDK rather than against anything this repo wrote,
so a future SDK that flips the contract makes noise instead of silently
reverting us to the broken form.

MEASURED 2026-08-26, both versions in play:

  google-genai 1.75.0 (the apps/backend-rag/.venv on Pro)
  google-genai 2.18.1 (pinned by requirements.lock.txt AND
                       requirements-prod.lock.txt -- i.e. CI and production)

  iscoroutinefunction(AsyncModels.generate_content_stream) -> True   (both)
  isasyncgenfunction (AsyncModels.generate_content_stream) -> False  (both)

The import below is deliberately hard, not `importorskip`: google-genai is a
pinned dependency of this app, so "the SDK is absent" is a broken environment,
not a reason to pass. A skip here would restore exactly the silence this file
was written to end.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from google.genai import models as genai_models

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.llm.genai_client import GenAIClient  # noqa: E402


def test_the_sdk_streaming_entrypoint_is_still_a_coroutine_function():
    """Drift tripwire on the SDK itself, not on anything this repo wrote.

    If a future google-genai makes this an async generator function again, the
    awaited form in genai_client.py becomes the wrong one and this test says so
    with the reason, instead of the streaming path going quietly dead a second
    time.
    """
    fn = genai_models.AsyncModels.generate_content_stream
    assert inspect.iscoroutinefunction(fn), (
        "google-genai's AsyncModels.generate_content_stream is no longer a "
        "coroutine function. genai_client.py awaits it before iterating, which "
        "is correct ONLY while this holds. Re-check the SDK version pinned in "
        "requirements.lock.txt and adjust the call site — do NOT adjust this "
        "assertion to match a mock."
    )
    assert not inspect.isasyncgenfunction(fn), (
        "AsyncModels.generate_content_stream is now an async generator function. "
        "The call site must iterate it directly instead of awaiting it."
    )


def test_the_installed_sdk_matches_the_version_the_lockfile_pins():
    """The tripwire above measures the INSTALLED SDK. This one measures whether
    the installed SDK is the one CI and production actually run.

    Raised by a cross-family refuter against the first draft of this file: an
    SDK-shape assertion reads whatever is in the venv, so a drifted venv makes it
    green while saying nothing about the pinned version — the assertion silences
    itself exactly when it matters.

    That is not hypothetical. Measured 2026-08-26 on Pro: the
    apps/backend-rag/.venv carried google-genai 1.75.0 while
    requirements.lock.txt pinned 2.18.1. The contract happens to be identical in
    both, so the fix this file guards is right either way — but that was luck,
    established only by installing 2.18.1 into a throwaway venv to check. Local
    test results do not transfer to CI until this passes.

    Green in CI, which installs requirements.lock.txt. Red on a drifted
    workstation, which is the point: the cure is to reinstall the venv from the
    lockfile, NEVER to loosen this assertion.
    """
    import google.genai

    lock = Path(__file__).parents[4] / "requirements.lock.txt"
    assert lock.is_file(), f"requirements.lock.txt not found at {lock}"

    pinned = None
    for line in lock.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("google-genai=="):
            pinned = stripped.split("==", 1)[1].split()[0].rstrip(" \\")
            break
    assert pinned, "requirements.lock.txt does not pin google-genai with '=='"

    installed = google.genai.__version__
    assert installed == pinned, (
        f"google-genai drift: this environment has {installed}, "
        f"requirements.lock.txt pins {pinned}. Every result from this file — and "
        f"from any other test touching the Gemini SDK — is about a version CI and "
        f"production do not run. Reinstall the venv from the lockfile. Do not "
        f"relax this assertion: it exists because a shape tripwire reads whatever "
        f"is installed and therefore goes quiet on exactly the drifted machine "
        f"where it was needed."
    )


@pytest.mark.asyncio
async def test_the_sdk_call_returns_something_awaitable_that_then_iterates():
    """BEHAVIOURAL form of the shape tripwire, and the stronger of the two.

    Also raised by the refuter: asserting `iscoroutinefunction` on the CLASS
    ATTRIBUTE is an implementation detail Google may flip in a patch release, and
    it is not necessarily the object the production call site reaches —
    instrumentation (openinference-instrumentation-google-genai is installed and
    wraps this very method) or per-instance patching could diverge from the class.

    What the call site actually depends on is narrower and more stable: the call
    returns something awaitable, and awaiting it gives something iterable with
    `async for`. That is asserted here against a REAL client object rather than
    the class, with no network: the SDK builds the coroutine eagerly and only
    performs I/O once awaited, so constructing it and checking `isawaitable` is
    free. The coroutine is closed rather than awaited, so nothing is sent.
    """
    from google import genai

    sdk = genai.Client(api_key="not-a-real-key-nothing-is-sent")
    call = sdk.aio.models.generate_content_stream(
        model="gemini-2.0-flash-lite", contents="ping"
    )
    try:
        assert inspect.isawaitable(call), (
            "aio.models.generate_content_stream no longer returns an awaitable. "
            "genai_client.py awaits it before iterating; that call site must change "
            "with this contract, and the change must be made there, not here."
        )
    finally:
        call.close()


@pytest.fixture
def client():
    with (
        patch("backend.llm.genai_client.genai") as mock_genai,
        patch("backend.llm.genai_client.types"),
        patch("backend.llm.genai_client.GENAI_AVAILABLE", True),
    ):
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        c = GenAIClient(api_key="test-key")
        c._client = mock_client
        c._available = True
        return c


@pytest.mark.asyncio
async def test_the_wrapper_awaits_the_coroutine_and_yields_every_chunk(client):
    """GUILT: this is red on the pre-2026-08-26 call site.

    The mock's shape is copied from the SDK's real one -- a coroutine function
    resolving to an async iterator -- rather than chosen to make the code pass.
    Against the old `async for chunk in <coroutine>` form this raises TypeError
    and the wrapper re-raises it, so the test fails loudly rather than yielding
    nothing.
    """
    chunks_in = []
    for text in ("alpha", "beta", "gamma"):
        c = MagicMock()
        c.text = text
        chunks_in.append(c)

    awaited = {"count": 0}

    async def sdk_shaped_stream(*args, **kwargs):
        awaited["count"] += 1

        async def _iterator():
            for c in chunks_in:
                yield c

        return _iterator()

    client._client.aio.models.generate_content_stream = sdk_shaped_stream

    out = [chunk async for chunk in client.generate_content_stream("q")]

    assert out == ["alpha", "beta", "gamma"], (
        "the wrapper did not yield the SDK's chunks in order — if this is empty, "
        "the call site is iterating the coroutine instead of awaiting it"
    )
    assert awaited["count"] == 1, "the SDK entrypoint should be called exactly once"


@pytest.mark.asyncio
async def test_a_chunk_with_no_text_is_skipped_not_yielded_as_none(client):
    """INNOCENCE: the fix must not change which chunks reach the caller.

    google-genai emits chunks whose `.text` is None (tool-call and safety
    metadata frames). Those were skipped before and must still be skipped —
    yielding None here would push a None into every consumer's string
    concatenation.
    """
    good = MagicMock()
    good.text = "kept"
    empty = MagicMock()
    empty.text = None

    async def sdk_shaped_stream(*args, **kwargs):
        async def _iterator():
            yield empty
            yield good
            yield empty

        return _iterator()

    client._client.aio.models.generate_content_stream = sdk_shaped_stream

    out = [chunk async for chunk in client.generate_content_stream("q")]

    assert out == ["kept"], f"textless chunks leaked into the output: {out!r}"


@pytest.mark.asyncio
async def test_an_sdk_failure_still_propagates_rather_than_yielding_nothing(client):
    """INNOCENCE: the wrapper re-raises. A stream that dies must not look empty.

    This is what made the original defect invisible for so long — the caller
    logged "LLM stream failed" and carried on. The wrapper's own contract is to
    re-raise; that must survive the fix, or a dead Gemini becomes an empty
    answer instead of an error.
    """

    async def failing_stream(*args, **kwargs):
        raise RuntimeError("upstream refused")

    client._client.aio.models.generate_content_stream = failing_stream

    with pytest.raises(RuntimeError, match="upstream refused"):
        [chunk async for chunk in client.generate_content_stream("q")]
