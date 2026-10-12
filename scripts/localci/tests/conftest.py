import pytest

from . import fixture_repo as fr

# pytest exports the running test's nodeid as PYTEST_CURRENT_TEST, and Linux refuses to exec a child whose env holds one
# string of 128 KiB or more (MAX_ARG_STRLEN, E2BIG). macOS has no such limit, so a parametrize id built from a big value
# passes on Pro and fails only on the hosted runner, which then loses the failure body to the giant header line.
NODEID_MAX = 4096


def pytest_collection_modifyitems(items):
    long_ids = [item.nodeid[:120] + "..." for item in items if len(item.nodeid) > NODEID_MAX]
    if long_ids:
        raise pytest.UsageError(f"{len(long_ids)} test id(s) over {NODEID_MAX} chars; give the parametrize short ids=: {long_ids}")


@pytest.fixture
def fake_env(monkeypatch):
    fe = fr.FakeEnv()
    monkeypatch.setattr(fr.runner, "env_fingerprint", fe)
    return fe


@pytest.fixture
def fx(tmp_path):
    return fr.make_repo(tmp_path)
