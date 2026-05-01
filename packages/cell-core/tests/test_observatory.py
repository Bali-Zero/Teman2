import os
import pytest
from cell_core import observatory


def test_is_enabled_default_false(monkeypatch):
    monkeypatch.delenv("CELL_OBSERVATORY_EMIT", raising=False)
    assert observatory.is_enabled() is False


def test_is_enabled_when_true(monkeypatch):
    monkeypatch.setenv("CELL_OBSERVATORY_EMIT", "true")
    assert observatory.is_enabled() is True


def test_is_enabled_case_insensitive(monkeypatch):
    monkeypatch.setenv("CELL_OBSERVATORY_EMIT", "TRUE")
    assert observatory.is_enabled() is True


def test_is_enabled_other_values_are_false(monkeypatch):
    monkeypatch.setenv("CELL_OBSERVATORY_EMIT", "yes")
    assert observatory.is_enabled() is False
    monkeypatch.setenv("CELL_OBSERVATORY_EMIT", "1")
    assert observatory.is_enabled() is False
