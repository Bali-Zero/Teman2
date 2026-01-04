import builtins
import runpy
import sys
import types
from unittest.mock import patch


def test_verify_import_success(capsys):
    app_module = types.ModuleType("app")
    routers_module = types.ModuleType("app.routers")
    oracle_module = types.ModuleType("app.routers.oracle_universal")
    oracle_module.router = object()

    with patch.dict(
        sys.modules,
        {
            "app": app_module,
            "app.routers": routers_module,
            "app.routers.oracle_universal": oracle_module,
        },
        clear=False,
    ):
        runpy.run_module("verify_import", run_name="__main__")

    output = capsys.readouterr().out
    assert "Import successful" in output


def test_verify_import_import_error(capsys):
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "app.routers.oracle_universal":
            raise ImportError("boom")
        return original_import(name, globals, locals, fromlist, level)

    with patch("builtins.__import__", side_effect=fake_import):
        runpy.run_module("verify_import", run_name="__main__")

    output = capsys.readouterr().out
    assert "ImportError: boom" in output


def test_verify_import_exception(capsys):
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "app.routers.oracle_universal":
            raise RuntimeError("oops")
        return original_import(name, globals, locals, fromlist, level)

    with patch("builtins.__import__", side_effect=fake_import):
        runpy.run_module("verify_import", run_name="__main__")

    output = capsys.readouterr().out
    assert "Exception: oops" in output
