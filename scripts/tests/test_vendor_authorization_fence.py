"""The on-disk fence: a key is not permission.

Gate verdict on PR #6968, condition 3. Builder Contract §3 already forbade
installing a third-party per-token vendor without the owner's authorization,
and could not reach the act that arms one — adding a repository secret, which
is a settings page and not a PR. These tests pin that the client stays silent
until its endpoint is listed on disk, and that the silence says which silence
it is.

Guilt and innocence both, per cicatrix #3: a fence proven only by the case it
blocks is indistinguishable from a client that never worked.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import typesafe_client as tc  # noqa: E402


@pytest.fixture
def listing(tmp_path, monkeypatch):
    """Point the client at a scratch authorization file and return a writer."""
    path = tmp_path / "authorized_endpoints.json"
    monkeypatch.setattr(tc, "AUTHORIZATION", path)

    def write(payload):
        path.write_text(json.dumps(payload))

    return path, write


def test_a_key_alone_does_not_authorize(listing, monkeypatch):
    """GUILT. The exact shape of the scar: the secret gets configured, no
    ruling is merged, and the client must still refuse."""
    _, write = listing
    write({"endpoints": []})
    monkeypatch.setenv(tc.ENV_VAR, "a-configured-key")

    assert tc.authorized() is False
    assert tc.available() is False
    assert tc.unavailable_reason() == tc.NOT_AUTHORIZED


def test_a_listed_endpoint_with_a_key_is_available(listing, monkeypatch):
    """INNOCENCE. Without this the fence is unfalsifiable — a client that can
    never speak passes every guilt test ever written."""
    _, write = listing
    write({"endpoints": [tc.ENDPOINT]})
    monkeypatch.setenv(tc.ENV_VAR, "a-configured-key")

    assert tc.authorized() is True
    assert tc.available() is True
    assert tc.unavailable_reason() is None


def test_the_dict_form_carries_its_ruling(listing, monkeypatch):
    """An entry may be an object so the ruling that authorized it travels with
    it. The endpoint is read from the same key either way."""
    _, write = listing
    write({"endpoints": [{"endpoint": tc.ENDPOINT, "ruling": "RULED 2026-01-01"}]})
    monkeypatch.setenv(tc.ENV_VAR, "a-configured-key")

    assert tc.authorized() is True


def test_a_different_endpoint_does_not_authorize_this_one(listing, monkeypatch):
    """Entity, not substring: authorizing one vendor must not authorize its
    neighbour, and a prefix of the real endpoint is not the real endpoint."""
    _, write = listing
    write({"endpoints": ["https://api.example.com/v1", tc.ENDPOINT[:-4]]})
    monkeypatch.setenv(tc.ENV_VAR, "a-configured-key")

    assert tc.authorized() is False


def test_an_entry_containing_the_endpoint_does_not_authorize_it(listing, monkeypatch):
    """A SUPERSTRING is not a match either, and the prefix case above does not
    cover it: a mutation from `==` to `in` survives a corpus that only tests
    prefixes, because a prefix does not contain what it is a prefix of. Found
    by a refuting seat's mutation run, confirmed independently — both halves of
    an entity match need a case, not just the cheaper one."""
    _, write = listing
    write({"endpoints": [tc.ENDPOINT + "/../evil", "prefix-" + tc.ENDPOINT]})
    monkeypatch.setenv(tc.ENV_VAR, "a-configured-key")

    assert tc.authorized() is False


def test_a_dict_entry_naming_another_endpoint_does_not_authorize(listing, monkeypatch):
    """The dict branch must check the endpoint, not merely the shape. Dropping
    that comparison left every test green: the only dict in the corpus carried
    the right endpoint, so `isinstance(entry, dict)` alone passed. Same
    refuting seat, same run."""
    _, write = listing
    write({"endpoints": [{"endpoint": "https://api.example.com/v1", "ruling": "unrelated"}]})
    monkeypatch.setenv(tc.ENV_VAR, "a-configured-key")

    assert tc.authorized() is False


@pytest.mark.parametrize(
    "payload",
    ["", "{", '{"endpoints": "all"}', '{"other": []}', '{"endpoints": null}'],
    ids=["empty", "truncated", "not-a-list", "missing-key", "null"],
)
def test_an_unusable_list_authorizes_nothing(listing, monkeypatch, payload):
    """Fail-closed, like the ban-prose pardon list: failing open would make
    corrupting one file the way to arm every vendor."""
    path, _ = listing
    path.write_text(payload)
    monkeypatch.setenv(tc.ENV_VAR, "a-configured-key")

    assert tc.authorized() is False
    assert tc.unavailable_reason() == tc.NOT_AUTHORIZED


def test_deeply_nested_json_does_not_escape_as_an_exception(listing, monkeypatch):
    """A refusal is a return, never a raise. Deep nesting raises RecursionError
    out of the parser, which is neither a ValueError nor an OSError — the same
    class of miss as the UnicodeDecodeError that once escaped `ask`."""
    path, _ = listing
    path.write_text("[" * 20000 + "]" * 20000)
    monkeypatch.setenv(tc.ENV_VAR, "a-configured-key")

    assert tc.authorized() is False


def test_an_absent_file_authorizes_nothing(listing, monkeypatch):
    """Deleting the file must not be the way to go quiet."""
    monkeypatch.setenv(tc.ENV_VAR, "a-configured-key")
    assert tc.authorized() is False


def test_the_two_silences_are_distinguishable(listing, monkeypatch):
    """No key and no authorization look identical from outside. A caller that
    cannot tell them apart prints a message that is false half the time."""
    _, write = listing
    write({"endpoints": [tc.ENDPOINT]})
    monkeypatch.delenv(tc.ENV_VAR, raising=False)

    assert tc.unavailable_reason() == tc.NO_KEY
    assert tc.NO_KEY != tc.NOT_AUTHORIZED


def test_ask_never_serialises_for_an_unauthorized_endpoint(listing, monkeypatch):
    """The refusal happens BEFORE the payload exists. Source text must not be
    serialised for an unauthorized vendor even into a request that is then
    discarded, and no HTTP call may be attempted at all."""
    _, write = listing
    write({"endpoints": []})
    monkeypatch.setenv(tc.ENV_VAR, "a-configured-key")

    def explode(*_args, **_kwargs):  # pragma: no cover - must never run
        raise AssertionError("the client reached the network while unauthorized")

    monkeypatch.setattr(tc.urllib.request, "urlopen", explode)
    monkeypatch.setattr(tc.json, "dumps", explode)

    assert tc.ask({"file": {"content": "secret source"}}, {}) is None


def test_the_shipped_list_authorizes_nothing_today(monkeypatch):
    """The file this PR ships, read as it ships. If a later PR adds an entry
    without a ruling behind it, this is the test that turns red."""
    monkeypatch.setenv(tc.ENV_VAR, "a-configured-key")
    listed = json.loads(tc.AUTHORIZATION.read_text())["endpoints"]

    assert listed == []
    assert tc.authorized() is False
