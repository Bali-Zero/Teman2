import runpy
from unittest.mock import patch


class DummyResponse:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


def test_verify_route_404(capsys):
    response = DummyResponse(404, "not found")
    with patch("requests.post", return_value=response):
        runpy.run_module("verify_route", run_name="__main__")
    output = capsys.readouterr().out
    assert "404 Not Found" in output


def test_verify_route_200(capsys):
    response = DummyResponse(200, "ok")
    with patch("requests.post", return_value=response):
        runpy.run_module("verify_route", run_name="__main__")
    output = capsys.readouterr().out
    assert "SUCCESS: Transcription worked" in output


def test_verify_route_other_status(capsys):
    response = DummyResponse(422, "error")
    with patch("requests.post", return_value=response):
        runpy.run_module("verify_route", run_name="__main__")
    output = capsys.readouterr().out
    assert "CONNECTIVITY SUCCESS" in output


def test_verify_route_exception(capsys):
    with patch("requests.post", side_effect=RuntimeError("boom")):
        runpy.run_module("verify_route", run_name="__main__")
    output = capsys.readouterr().out
    assert "CONNECTION FAILED: boom" in output
