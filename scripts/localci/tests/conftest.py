import pytest

from . import fixture_repo as fr


@pytest.fixture
def fake_env(monkeypatch):
    fe = fr.FakeEnv()
    monkeypatch.setattr(fr.runner, "env_fingerprint", fe)
    return fe


@pytest.fixture
def fx(tmp_path):
    return fr.make_repo(tmp_path)
