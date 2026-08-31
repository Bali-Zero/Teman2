"""An ingest that refused a document must not be reported as having stored it.

`LegalIngestionService.ingest_legal_document` catches everything internally and
signals failure by RETURNING ``{"success": False, "error": ...}``; it does not
raise. Two callers read "no exception reached me" as success:

* ``infra/eventbus/regulatory_ingest_runner.py`` printed ``{"ok": True}``
  unconditionally, so the nightly regulatory run wrote ``in_qdrant: YES`` into
  its tracking sheet and went on to run KG extraction over a document the
  corpus had never received;
* ``backend/cli/ingestion_cli.py`` returned a hardcoded ``"success": True``, so
  an operator re-running a law by hand saw "✅ Ingestion successful!" and an
  exit code of 0 for a document that had just been refused.

Both pre-date the completeness contract of #4896 and both became sharper with
it: before, a half-read document at least left *something* searchable behind,
so the claim was roughly true; now a refused document stores nothing at all and
the claim is simply false.

The runner lives outside any installed package, so it is loaded by path — and
deliberately from THIS repository tree rather than from a copy on some machine,
per the HOME-fork scar family.
"""

import importlib.util
import sys
from pathlib import Path

import pytest


def _find_runner() -> Path:
    """Walk up to the repository that CONTAINS this test, never a fixed depth.

    A hardcoded `parents[N]` breaks the moment the tree is re-nested, and an
    absolute path would let the test read a copy in some machine's home while
    the repository's own file rots (the HOME-fork scar family).
    """
    relative = Path("infra") / "eventbus" / "regulatory_ingest_runner.py"
    for parent in Path(__file__).resolve().parents:
        candidate = parent / relative
        if candidate.exists():
            return candidate
    raise AssertionError(f"{relative} not found above {__file__}")


RUNNER_PATH = _find_runner()


def _load_runner():
    spec = importlib.util.spec_from_file_location("regulatory_ingest_runner_undertest", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# GUILT
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        {"success": False, "error": "Legal identity collision"},
        {"success": None},
        {},  # the key never arrived
        {"result": "{'success': False}"},  # only the truncated repr, no verdict
    ],
)
def test_a_refused_ingest_is_never_reported_as_stored(payload):
    runner = _load_runner()
    verdict = runner._verdict_from_ingest_output(payload)
    assert verdict["ok"] is False
    assert verdict["error"], "a failure must say something, or step 8 prints nothing to act on"


def test_a_malformed_ingest_output_is_a_failure_not_a_success():
    """A runner that cannot tell must not claim."""
    runner = _load_runner()
    for junk in ("ok", 1, None, ["success"]):
        assert runner._verdict_from_ingest_output(junk)["ok"] is False


def test_the_subprocess_no_longer_hardcodes_its_own_verdict():
    """The decision used to live inside a GENERATED source string, where no test
    could reach it. This asserts on the artifact itself, because the artifact is
    the defect.

    Scoped to the doubled-brace form, which appears only inside the f-string
    that builds the subprocess: the other `{"ok": True}` returns in this module
    are ordinary in-process returns after work that either succeeded or raised,
    and they are not this bug.
    """
    source = RUNNER_PATH.read_text()
    assert '{{"ok": True' not in source, "the subprocess is claiming success again"
    assert '"success": result.get("success")' in source, "it must report the ingest's own verdict"


@pytest.mark.asyncio
async def test_the_cli_reports_the_ingest_verdict_not_its_own_optimism():
    from backend.cli.ingestion_cli import IngestionCLI

    cli = IngestionCLI()

    class _Refusing:
        async def ingest_legal_document(self, file_path, **kwargs):
            return {"success": False, "error": "Incomplete vision transcription of /x.pdf"}

    cli.legal_ingestion_service = _Refusing()
    out = await cli.ingest_laws(file_path="/x.pdf")
    assert out["success"] is False
    assert out["ingested"] == 0
    assert "Incomplete" in (out.get("error") or "")


# ---------------------------------------------------------------------------
# INNOCENCE
# ---------------------------------------------------------------------------


def test_a_real_success_is_still_a_success():
    runner = _load_runner()
    verdict = runner._verdict_from_ingest_output({"success": True, "result": "..."})
    assert verdict["ok"] is True
    assert verdict.get("error") is None


def test_a_subprocess_from_an_older_deploy_is_still_understood():
    """Mid-rollout the running script may still speak the old `ok` key. Reading
    that as a failure would turn a fixed reporter into a broken one."""
    runner = _load_runner()
    assert runner._verdict_from_ingest_output({"ok": True})["ok"] is True
    assert runner._verdict_from_ingest_output({"ok": False})["ok"] is False


@pytest.mark.asyncio
async def test_the_cli_still_reports_a_genuine_success():
    from backend.cli.ingestion_cli import IngestionCLI

    cli = IngestionCLI()

    class _Storing:
        async def ingest_legal_document(self, file_path, **kwargs):
            return {"success": True, "chunks_created": 413}

    cli.legal_ingestion_service = _Storing()
    out = await cli.ingest_laws(file_path="/x.pdf")
    assert out["success"] is True
    assert out["ingested"] == 1
    assert out["error"] is None
