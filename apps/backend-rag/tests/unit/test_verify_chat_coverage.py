import runpy
from unittest.mock import patch

import requests


class DummyResponse:
    def __init__(self, status_code):
        self.status_code = status_code
        self.closed = False

    def close(self):
        self.closed = True


def test_verify_chat_handles_404(capsys):
    response = DummyResponse(404)
    with patch("requests.post", return_value=response):
        runpy.run_module("verify_chat", run_name="__main__")
    output = capsys.readouterr().out
    assert "404 Not Found" in output
    assert response.closed is False


def test_verify_chat_handles_success(capsys):
    response = DummyResponse(200)
    with patch("requests.post", return_value=response):
        runpy.run_module("verify_chat", run_name="__main__")
    output = capsys.readouterr().out
    assert "Endpoint Exists" in output
    assert response.closed is True


def test_verify_chat_handles_read_timeout(capsys):
    with patch("requests.post", side_effect=requests.exceptions.ReadTimeout):
        runpy.run_module("verify_chat", run_name="__main__")
    output = capsys.readouterr().out
    assert "Read Timeout" in output


def test_verify_chat_handles_exception(capsys):
    with patch("requests.post", side_effect=RuntimeError("boom")):
        runpy.run_module("verify_chat", run_name="__main__")
    output = capsys.readouterr().out
    assert "Failed: boom" in output
