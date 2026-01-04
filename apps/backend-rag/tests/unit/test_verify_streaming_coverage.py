import runpy
from unittest.mock import patch


class DummyResponse:
    def __init__(self, status_code=200, text="ok", lines=None):
        self.status_code = status_code
        self.text = text
        self._lines = lines or []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def iter_lines(self):
        for line in self._lines:
            yield line


def test_verify_streaming_error_status(capsys):
    response = DummyResponse(status_code=500, text="error")
    with patch("requests.post", return_value=response):
        with patch("builtins.exit", side_effect=SystemExit(1)) as exit_call:
            try:
                runpy.run_module("verify_streaming", run_name="__main__")
            except SystemExit:
                pass
    output = capsys.readouterr().out
    assert "Error Content: error" in output
    exit_call.assert_called_once()


def test_verify_streaming_success(capsys):
    lines = [b"event1", b"event2", b"event3", b"event4"]
    response = DummyResponse(status_code=200, lines=lines)
    with patch("requests.post", return_value=response):
        runpy.run_module("verify_streaming", run_name="__main__")
    output = capsys.readouterr().out
    assert "Received enough events" in output
    assert "Finished in" in output


def test_verify_streaming_exception(capsys):
    with patch("requests.post", side_effect=RuntimeError("boom")):
        runpy.run_module("verify_streaming", run_name="__main__")
    output = capsys.readouterr().out
    assert "Failed: boom" in output
