"""The token must not survive a log line — proven on both halves, and on the whole class.

Scar being pinned: on 2026-08-11 a live Telegram bot token was printed in cleartext in a
PUBLIC repository's Actions log, by httpx at INFO, because Telegram carries the token in
the URL path. See `backend/core/secret_log_redaction` for the full autopsy.

Three duties, and the third is the one that makes this a class cure:

* GUILT, twice — the redaction must hold at the NAMED-LOGGER level (the emitters we have
  measured) AND at the ROOT-HANDLER level (every logger we have not). One is not the other:
  a Logger's filters run only for records that ORIGINATE on it.
* INNOCENCE — an ordinary request line, and a line that merely contains the word "bot",
  must come through untouched. A redactor that eats real logs gets turned off.
* CENSUS — every non-test module that builds a Telegram URL must install the redaction.
  The file that bit us was one of sixteen; curing that one would only have moved which
  sender leaks next (W107).

No real secret appears here. The token below is synthetic and matches Telegram's SHAPE,
which is the whole point: the filter knows the shape, never our value.
"""

from __future__ import annotations

import ast
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest

from backend.core.secret_log_redaction import (
    TelegramTokenRedactionFilter,
    install_telegram_token_redaction,
)

# Synthetic, never issued by Telegram. Same shape as a real one — which is why
# the marker below is here: `scripts/lint_telegram_tokens.py` refuses a
# token-shaped literal anywhere in the tree, and this file needs the real shape
# to do its job. The marker is an assertion by the author, and it cannot excuse
# a token the linter already knows is burned.
# synthetic-telegram-token
FAKE_TOKEN = "bot7654321098:AAF9zZqLmN0pQrStUvWxYz1234567890abc"  # noqa: S105
FAKE_URL = f"https://api.telegram.org/{FAKE_TOKEN}/sendMessage"
SECRET_HALF = "AAF9zZqLmN0pQrStUvWxYz1234567890abc"

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _record(logger_name: str, msg: str, args: tuple = ()) -> logging.LogRecord:
    return logging.LogRecord(
        name=logger_name,
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args,
        exc_info=None,
    )


class _Capture(logging.Handler):
    """Records exactly what a handler would have written out."""

    def __init__(self) -> None:
        super().__init__()
        self.rendered: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.rendered.append(record.getMessage())


@pytest.fixture
def clean_logging():
    """Give each test a pristine root + httpx logger, and put it back afterwards.

    This resets more than looks necessary, and every extra line was earned: the first
    version restored only handlers/filters/root level, passed alone, and then failed in
    three places when run inside the wider suite — an earlier test had left the `httpx`
    logger muted, so nothing reached the capture handler and the assertions read as "the
    redactor ate the line". Logging is process-global state; a test that reasons about it
    must own every knob that can silence a record, not just the ones it sets itself.
    """
    root = logging.getLogger()
    httpx_logger = logging.getLogger("httpx")
    saved = {
        "root_handlers": list(root.handlers),
        "root_filters": list(root.filters),
        "root_level": root.level,
        "root_disabled": root.disabled,
        "global_disable": logging.root.manager.disable,
        "httpx_filters": list(httpx_logger.filters),
        "httpx_handlers": list(httpx_logger.handlers),
        "httpx_level": httpx_logger.level,
        "httpx_propagate": httpx_logger.propagate,
        "httpx_disabled": httpx_logger.disabled,
    }

    logging.disable(logging.NOTSET)  # a previous test may have muted everything globally
    root.handlers, root.filters = [], []
    root.setLevel(logging.INFO)
    root.disabled = False
    httpx_logger.filters, httpx_logger.handlers = [], []
    httpx_logger.setLevel(logging.INFO)
    httpx_logger.propagate = True
    httpx_logger.disabled = False

    yield root

    root.handlers = saved["root_handlers"]
    root.filters = saved["root_filters"]
    root.level = saved["root_level"]
    root.disabled = saved["root_disabled"]
    logging.root.manager.disable = saved["global_disable"]
    httpx_logger.filters = saved["httpx_filters"]
    httpx_logger.handlers = saved["httpx_handlers"]
    httpx_logger.level = saved["httpx_level"]
    httpx_logger.propagate = saved["httpx_propagate"]
    httpx_logger.disabled = saved["httpx_disabled"]


class TestGuiltTheSecretHalfDoesNotSurvive:
    def test_the_measured_emitter_is_redacted_where_the_record_is_born(self, clean_logging):
        """httpx logs on its own name — the named-logger half must catch it there."""
        capture = _Capture()
        clean_logging.addHandler(capture)
        install_telegram_token_redaction()

        logging.getLogger("httpx").info('HTTP Request: POST %s "HTTP/1.1 200 OK"', FAKE_URL)

        assert capture.rendered, "the line must still be logged — we redact, we do not silence"
        (line,) = capture.rendered
        assert SECRET_HALF not in line
        assert "bot7654321098:<redacted>" in line

    def test_a_logger_this_module_has_never_heard_of_is_caught_by_the_handler(self, clean_logging):
        """The backstop: an unknown emitter propagates to root, whose handler filters run.

        This is what makes the cure general. If it only ever caught `httpx`, the next
        HTTP library the codebase adopts would leak on day one.
        """
        capture = _Capture()
        clean_logging.addHandler(capture)
        install_telegram_token_redaction()

        logging.getLogger("some.library.nobody.listed").info("calling %s", FAKE_URL)

        (line,) = capture.rendered
        assert SECRET_HALF not in line
        assert "<redacted>" in line

    def test_a_handler_bolted_straight_onto_httpx_is_still_covered(self, clean_logging):
        """The half the root backstop cannot reach — and the reason both halves exist.

        With a handler on the `httpx` logger itself and propagation off, no record ever
        arrives at root, so every root-handler filter is bypassed. Only the filter sitting
        on the NAMED logger runs. Without this case both halves look interchangeable and a
        mutation that deletes one of them survives.
        """
        httpx_logger = logging.getLogger("httpx")
        capture = _Capture()
        httpx_logger.addHandler(capture)
        httpx_logger.propagate = False
        try:
            install_telegram_token_redaction()
            httpx_logger.info('HTTP Request: POST %s "HTTP/1.1 200 OK"', FAKE_URL)
        finally:
            httpx_logger.removeHandler(capture)

        (line,) = capture.rendered
        assert SECRET_HALF not in line

    def test_the_token_hiding_in_args_is_redacted_too(self):
        """httpx uses %-formatting, so the secret arrives in `args`, not in `msg`.

        Rewriting only `msg` would leave the handler to re-render the secret from `args`.
        """
        record = _record("httpx", "HTTP Request: POST %s", (FAKE_URL,))
        TelegramTokenRedactionFilter().filter(record)
        assert SECRET_HALF not in record.getMessage()

    def test_a_token_anywhere_in_the_line_is_redacted_not_only_in_a_url(self):
        """Shape, not position — a token pasted into an error string leaks just as hard."""
        record = _record("anything", f"auth failed for {FAKE_TOKEN} after 3 tries")
        TelegramTokenRedactionFilter().filter(record)
        assert SECRET_HALF not in record.getMessage()


class TestInnocenceOrdinaryLogsAreLeftAlone:
    def test_an_ordinary_request_line_is_untouched(self, clean_logging):
        capture = _Capture()
        clean_logging.addHandler(capture)
        install_telegram_token_redaction()

        original = 'HTTP Request: POST https://graph.facebook.com/v21.0/messages "HTTP/1.1 200 OK"'
        logging.getLogger("httpx").info(original)

        assert capture.rendered == [original]

    def test_the_word_bot_alone_is_not_a_secret(self):
        """The cheap pre-filter keys on "bot"; that must not be enough to rewrite a line."""
        original = "wa_inbox bot auto-reply not enabled in v1"
        record = _record("backend.services", original)
        TelegramTokenRedactionFilter().filter(record)
        assert record.getMessage() == original

    def test_a_bot_id_without_its_secret_half_is_left_alone(self):
        """`bot` + digits identifies WHICH bot and authenticates nothing — keep it readable."""
        original = "resolved chat for bot7654321098 (owner)"
        record = _record("backend.services", original)
        TelegramTokenRedactionFilter().filter(record)
        assert record.getMessage() == original

    def test_the_filter_never_drops_a_record(self):
        """Returning False would be the silencing this module exists to avoid."""
        assert TelegramTokenRedactionFilter().filter(_record("httpx", "anything")) is True

    def test_it_fails_open_when_a_record_cannot_be_rendered(self):
        """A redactor that raises takes down the logging it was added to protect."""
        bad = _record("httpx", "%s %s", ("only-one-arg",))  # %-formatting will raise
        assert TelegramTokenRedactionFilter().filter(bad) is True


class TestInstallingTwiceIsNotInstallingTwice:
    def test_the_filter_is_not_stacked_on_repeat_calls(self, clean_logging):
        clean_logging.addHandler(_Capture())
        install_telegram_token_redaction()
        first = len(logging.getLogger("httpx").filters)

        install_telegram_token_redaction()
        install_telegram_token_redaction()

        assert len(logging.getLogger("httpx").filters) == first


class TestTheEntryPointThatActuallyLeaked:
    def test_the_credit_sentinel_cli_redacts_on_the_path_that_leaked(self):
        """Replay the real sequence, in a real process, minus the network.

        This is the regression pin for the incident itself, and it exists because the
        ordering is not obvious: `llm_credit_sentinel_cli` raises the ROOT logger to INFO
        at import (which is what made httpx print request URLs at all), but it imports the
        Telegram sender LAZILY, inside the notifier — so the install happens later than
        the logging config and earlier than the first request. Reasoning about that order
        is how you get it wrong; running it is how you know.

        A subprocess, because both halves of the cure mutate global logging state.
        """
        probe = (
            "import logging, sys\n"
            "import backend.services.hardening.llm_credit_sentinel_cli\n"
            "assert logging.getLogger().handlers, 'the CLI no longer configures root'\n"
            "assert logging.getLogger().level == logging.INFO, 'root is no longer at INFO'\n"
            "from backend.services.integrations.telegram_bot_service import telegram_bot\n"
            f"logging.getLogger('httpx').info('HTTP Request: POST %s \"200 OK\"', '{FAKE_URL}')\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=BACKEND_ROOT.parent,
            capture_output=True,
            text=True,
            check=False,
            # Explicit, never inherited: a probe that runs only because the caller
            # happened to export PYTHONPATH is a probe that dies in CI.
            env={**os.environ, "PYTHONPATH": str(BACKEND_ROOT.parent)},
        )
        assert proc.returncode == 0, f"probe did not run: {proc.stderr[-2000:]}"
        combined = proc.stdout + proc.stderr
        assert "HTTP Request" in combined, "the request line was never logged — probe is vacuous"
        assert SECRET_HALF not in combined
        assert "bot7654321098:<redacted>" in combined


REPO_ROOT = BACKEND_ROOT.parents[2]
SENTINEL_WORKFLOW = REPO_ROOT / ".github/workflows/cron-llm-credit-sentinel.yml"


class TestTheWorkflowGuardIsArmedAndNotJustWritten:
    """The channel the Python filter structurally cannot reach.

    A `logging.Filter` only ever sees records that go through `logging`. An unhandled
    traceback does not, and httpx error strings quote the request URL — so a crash could
    still print the token into a PUBLIC Actions log. The workflow redacts `$OUT` once at
    capture. These two cases run the workflow's OWN expression, so the test fails if
    someone edits or deletes it, not merely if someone deletes the comment above it.
    """

    def _sed_expression(self) -> str:
        assert SENTINEL_WORKFLOW.exists(), f"workflow moved: {SENTINEL_WORKFLOW}"
        for line in SENTINEL_WORKFLOW.read_text().splitlines():
            if "sed -E" in line and "redacted" in line:
                return line.split("sed -E '", 1)[1].rsplit("'", 1)[0]
        pytest.fail("the sentinel workflow no longer redacts $OUT before echoing it")

    def test_it_redacts_a_token_the_python_filter_would_never_see(self):
        traceback_line = f"httpx.ConnectError: [Errno 61] connecting to {FAKE_URL}"
        proc = subprocess.run(
            ["sed", "-E", self._sed_expression()],
            input=traceback_line,
            capture_output=True,
            text=True,
            check=True,
        )
        assert SECRET_HALF not in proc.stdout
        assert "bot7654321098:<redacted>" in proc.stdout

    def test_it_leaves_the_lines_the_workflow_parses_alone(self):
        """STATE= and DETAIL= are parsed downstream — a redactor that mangles them breaks the alarm."""
        payload = "STATE=depleted\nDETAIL=prepay pool at zero\ncredito OK\n"
        proc = subprocess.run(
            ["sed", "-E", self._sed_expression()],
            input=payload,
            capture_output=True,
            text=True,
            check=True,
        )
        assert proc.stdout == payload


def _telegram_sender_files() -> list[Path]:
    """Every non-test module that builds a Telegram URL — measured, not listed by hand.

    A hardcoded list would go stale the moment someone adds the seventeenth sender, which
    is exactly the drift this census exists to catch.
    """
    proc = subprocess.run(
        ["grep", "-rl", "api.telegram.org", "--include=*.py", "backend/"],
        cwd=BACKEND_ROOT.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    # grep exits 1 on "no matches". Zero senders means the probe is broken (this file
    # itself mentions the host), not that the codebase stopped talking to Telegram.
    assert proc.returncode == 0, f"census probe failed: rc={proc.returncode} {proc.stderr}"

    found = []
    for line in proc.stdout.split():
        path = Path(line)
        if "test" in path.parts or path.name.startswith("test_"):
            continue
        if path.name == "secret_log_redaction.py":  # the cure itself
            continue
        found.append(BACKEND_ROOT.parent / path)
    assert found, "census found no sender files — the probe is measuring its own poverty"
    return found


def _installs_redaction(path: Path) -> bool:
    """Does this module CALL the installer at import time? Importing it is not enough."""
    tree = ast.parse(path.read_text())
    return any(
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "install_telegram_token_redaction"
        for node in tree.body
    )


class TestTheCensusEveryTelegramSenderIsCovered:
    def test_every_module_that_can_leak_the_token_redacts_it(self):
        """The class cure. Curing only the file that bit us moves the leak, it does not close it."""
        naked = [
            str(p.relative_to(BACKEND_ROOT.parent))
            for p in _telegram_sender_files()
            if not _installs_redaction(p)
        ]
        assert not naked, (
            "these modules build a Telegram URL and do not install the log redaction:\n  "
            + "\n  ".join(naked)
            + "\nAdd `install_telegram_token_redaction()` at module level."
        )

    def test_the_census_is_not_vacuous(self):
        """Guard the guard: a probe that finds nothing must not read as a clean bill of health."""
        assert len(_telegram_sender_files()) >= 10
