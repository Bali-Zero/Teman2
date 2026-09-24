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
import subprocess
import sys
import threading
import urllib.request
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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


def _entry(endpoint: str, **extra) -> dict:
    """A well-formed authorization entry naming `endpoint`.

    Only the dict branch can ever authorize (a bare string entry is skipped
    outright — see `test_a_bare_string_entry_never_authorizes`), so a test
    exercising the ENTITY-match logic itself — near miss, prefix, superstring,
    suffix, case, whitespace — must use this shape or it never reaches the
    comparison it claims to test.
    """
    return {"endpoint": endpoint, "ruling": "unrelated", "paths": ["**"], **extra}


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
    never speak passes every guilt test ever written. `paths` is the
    perimeter the successor to PR #6989 added: a matching endpoint alone is
    no longer enough, so the innocence case must carry one."""
    _, write = listing
    write(
        {
            "endpoints": [
                {"endpoint": tc.ENDPOINT, "ruling": "RULED 2026-01-01", "paths": ["**"]}
            ]
        }
    )
    monkeypatch.setenv(tc.ENV_VAR, "a-configured-key")

    assert tc.authorized() is True
    assert tc.available() is True
    assert tc.unavailable_reason() is None


def test_the_dict_form_carries_its_ruling(listing, monkeypatch):
    """An entry is an object so the ruling that authorized it travels with it
    — the only form that can authorize at all, since a bare string has
    nowhere to carry `paths` (see test_a_bare_string_entry_never_authorizes)."""
    _, write = listing
    write(
        {
            "endpoints": [
                {"endpoint": tc.ENDPOINT, "ruling": "RULED 2026-01-01", "paths": ["**"]}
            ]
        }
    )
    monkeypatch.setenv(tc.ENV_VAR, "a-configured-key")

    assert tc.authorized() is True


def test_a_bare_string_entry_never_authorizes(listing, monkeypatch):
    """A bare string has nowhere to carry `paths`, and an entry with no
    perimeter authorizes everything — the same fail-open the file itself is
    built to refuse, one level down. Successor to PR #6989's Gear-3 gate,
    condition 5."""
    _, write = listing
    write({"endpoints": [tc.ENDPOINT]})
    monkeypatch.setenv(tc.ENV_VAR, "a-configured-key")

    assert tc.authorized() is False


def test_an_entry_without_paths_authorizes_nothing(listing, monkeypatch):
    """PROOF-OF-ARMED for condition 5: the exact endpoint, a real ruling, and
    no `paths` key — still refused. Delete the `paths` check and this test
    must turn red."""
    _, write = listing
    write({"endpoints": [{"endpoint": tc.ENDPOINT, "ruling": "RULED 2026-01-01"}]})
    monkeypatch.setenv(tc.ENV_VAR, "a-configured-key")

    assert tc.authorized() is False


def test_an_entry_with_empty_paths_authorizes_nothing(listing, monkeypatch):
    """An empty list is a perimeter of nothing, not a perimeter of
    everything — the same fail-closed reading as the field's absence."""
    _, write = listing
    write(
        {
            "endpoints": [
                {"endpoint": tc.ENDPOINT, "ruling": "RULED 2026-01-01", "paths": []}
            ]
        }
    )
    monkeypatch.setenv(tc.ENV_VAR, "a-configured-key")

    assert tc.authorized() is False


@pytest.mark.parametrize(
    "paths",
    ["**", [None], [""], [123], ["ok", None]],
    ids=["not-a-list", "none-element", "empty-string-element", "int-element", "mixed"],
)
def test_a_malshaped_paths_authorizes_nothing(listing, monkeypatch, paths):
    """`paths` as a bare string (not a list), or a list containing anything
    that is not a non-empty string, is malshaped and authorizes nothing —
    `isinstance(paths, list) and paths` alone does not inspect ELEMENTS, so
    `paths: [None]` would otherwise authorize. Found by a cross-family review
    seat on this PR."""
    _, write = listing
    write(
        {
            "endpoints": [
                {"endpoint": tc.ENDPOINT, "ruling": "RULED 2026-01-01", "paths": paths}
            ]
        }
    )
    monkeypatch.setenv(tc.ENV_VAR, "a-configured-key")

    assert tc.authorized() is False


def test_a_different_endpoint_does_not_authorize_this_one(listing, monkeypatch):
    """Entity, not substring: authorizing one vendor must not authorize its
    neighbour, and a prefix of the real endpoint is not the real endpoint.

    Dict form, not bare strings: only the dict branch can authorize at all
    since the successor to PR #6989's Gear-3 gate, so a bare-string version of
    this test would pass regardless of whether the prefix check works —
    caught by a cross-family review seat on this very PR."""
    _, write = listing
    write(
        {
            "endpoints": [
                _entry("https://api.example.com/v1"),
                _entry(tc.ENDPOINT[:-4]),
            ]
        }
    )
    monkeypatch.setenv(tc.ENV_VAR, "a-configured-key")

    assert tc.authorized() is False


def test_an_entry_containing_the_endpoint_does_not_authorize_it(listing, monkeypatch):
    """A SUPERSTRING is not a match either, and the prefix case above does not
    cover it: a mutation from `==` to `in` survives a corpus that only tests
    prefixes, because a prefix does not contain what it is a prefix of. Found
    by a refuting seat's mutation run, confirmed independently — both halves of
    an entity match need a case, not just the cheaper one.

    Dict form for the same reason as the prefix test above."""
    _, write = listing
    write(
        {
            "endpoints": [
                _entry(tc.ENDPOINT + "/../evil"),
                _entry("prefix-" + tc.ENDPOINT),
            ]
        }
    )
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


def test_a_strict_suffix_does_not_authorize_on_the_dict_branch(listing, monkeypatch):
    """Same mutant, object branch — the shipped corpus only ever fed the dict
    branch the RIGHT endpoint or an unrelated one, never a suffix of it."""
    _, write = listing
    suffix = tc.ENDPOINT.removeprefix("https://")
    write(
        {
            "endpoints": [
                {"endpoint": suffix, "ruling": "unrelated", "paths": ["**"]}
            ]
        }
    )
    monkeypatch.setenv(tc.ENV_VAR, "a-configured-key")

    assert tc.authorized() is False


@pytest.mark.parametrize(
    "variant",
    ["HTTPS://API.TYPESAFE.AI/v1/systemone", " " + "https://api.typesafe.ai/v1/systemone" + " ",
     "https://api.typesafe.ai/v1/systemone/"],
    ids=["case", "whitespace", "trailing-slash"],
)
def test_a_near_miss_spelling_does_not_authorize(listing, monkeypatch, variant):
    """Today `==` rejects all three. Nothing TESTED that, so a mutant that
    normalised case or stripped whitespace would have passed the whole corpus
    — the rejection was true by accident of the operator rather than by a
    pinned decision. Raised by the kimi-code/k3 review seat.

    Dict form: a bare-string variant would be skipped outright regardless of
    its spelling, testing nothing about case/whitespace/slash normalisation."""
    _, write = listing
    write({"endpoints": [_entry(variant)]})
    monkeypatch.setenv(tc.ENV_VAR, "a-configured-key")

    assert tc.authorized() is False


@pytest.mark.parametrize(
    "payload",
    [
        "",
        "{",
        '{"endpoints": "all"}',
        '{"other": []}',
        '{"endpoints": null}',
        "[]",
        "true",
        "42",
        "null",
    ],
    ids=[
        "empty",
        "truncated",
        "not-a-list",
        "missing-key",
        "null",
        "top-level-array",
        "top-level-bool",
        "top-level-number",
        "top-level-null",
    ],
)
def test_an_unusable_list_authorizes_nothing(listing, monkeypatch, payload):
    """Fail-closed, like the ban-prose pardon list: failing open would make
    corrupting one file the way to arm every vendor. The four top-level cases
    (`[]`, `true`, `42`, `null`) are the ones that make `["endpoints"]` raise
    `TypeError` on the parsed document itself — dropping `TypeError` from
    `authorized()`'s except tuple survived the corpus measured on PR #6989
    because nothing fed it a top-level document of the wrong shape."""
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

    # The real guarantee here is the `json.dumps` patch: it sits BEFORE the
    # retry loop, so an explosion there propagates straight out of `ask()`.
    # `_OPENER.open` — the transport seam post-#6989's redirect fix, not
    # `urllib.request.urlopen`, which `ask()` no longer calls directly — sits
    # INSIDE the retry loop's `except Exception`, so an explosion there is
    # swallowed and retried into a quiet `None` regardless of which function
    # is patched. Kept pointed at the real seam for an honest read of what is
    # and is not covered, not because it adds enforcement here. Found by a
    # cross-family review seat on this PR.
    monkeypatch.setattr(tc._OPENER, "open", explode)
    monkeypatch.setattr(tc.json, "dumps", explode)

    assert tc.ask({"file": {"content": "secret source"}}, {}) is None


RULINGS = Path(__file__).resolve().parents[2] / "docs" / "rules" / "RULINGS.md"
ENTRY_FIELDS = ("endpoint", "ruling", "use", "paths")


def _shipped_entries() -> list:
    """The registry as it ships, read from disk — never a fixture."""
    return json.loads(tc.AUTHORIZATION.read_text(encoding="utf-8"))["endpoints"]


def _ruling_blocks(text: str) -> list[str]:
    """The `>`-quoted blocks of RULINGS.md, each joined into one string.

    A ruling is one blockquote. A line that does not start with `>` ends the
    block, which is how the file itself separates one ruling from the next —
    so a ruling id and an endpoint that sit in DIFFERENT blocks never count
    as one ruling naming that endpoint.
    """
    blocks: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith(">"):
            current.append(line)
        elif current:
            blocks.append("\n".join(current))
            current = []
    if current:
        blocks.append("\n".join(current))
    return blocks


def _full_shape(entry) -> bool:
    """`_doc`'s contract for an entry: an object with all four fields present
    and non-empty, `paths` a non-empty list of non-empty strings."""
    if not isinstance(entry, dict):
        return False
    for field in ("endpoint", "ruling", "use"):
        if not (isinstance(entry.get(field), str) and entry[field].strip()):
            return False
    paths = entry.get("paths")
    return (
        isinstance(paths, list)
        and bool(paths)
        and all(isinstance(p, str) and p for p in paths)
    )


def _justified(entry: dict, rulings_text: str) -> bool:
    """True when `entry["ruling"]` is a quoted block of the rulings file that
    ALSO names `entry["endpoint"]` — a block that names only the vendor, or
    the ruling that closed the door, does not justify an entry."""
    blocks = [b for b in _ruling_blocks(rulings_text) if entry["ruling"] in b]
    return any(entry["endpoint"] in b for b in blocks)


def test_the_shipped_list_names_exactly_this_endpoint(monkeypatch):
    """The file as it ships, read as it ships. The empty-list tripwire that
    stood here was spent by the first entry, as the PENDING-ARMS row for PR
    #6999 foresaw; what replaces it has to be as loud about the SECOND entry
    as the tripwire was about the first. One endpoint is listed today and it
    is this client's — a second one comes through this suite too."""
    monkeypatch.setenv(tc.ENV_VAR, "a-configured-key")

    assert [e["endpoint"] for e in _shipped_entries()] == [tc.ENDPOINT]
    assert tc.authorized() is True
    assert tc.available() is True
    assert tc.unavailable_reason() is None


def test_the_shipped_entry_still_needs_the_key(monkeypatch):
    """Authorization on disk is one half; the fence has two. With the entry
    shipped and no key configured the client stays silent, and says which
    silence it is — otherwise the first entry would have turned a two-part
    fence into a one-part one without anyone noticing."""
    monkeypatch.delenv(tc.ENV_VAR, raising=False)

    assert tc.authorized() is True
    assert tc.available() is False
    assert tc.unavailable_reason() == tc.NO_KEY


def test_every_shipped_entry_carries_the_full_shape():
    """`_doc` requires `endpoint`, `ruling`, `use` and non-empty `paths`;
    `authorized()` reads only two of them (honestly, per its docstring), so
    nothing at runtime enforces the other two. This is the merge-time
    validator the PR #6999 ledger row asked for WITH the first entry."""
    entries = _shipped_entries()

    assert entries, "the registry is not empty any more; this suite owns its shape"
    for entry in entries:
        assert _full_shape(entry), entry


@pytest.mark.parametrize("missing", ENTRY_FIELDS)
def test_an_entry_missing_a_field_is_not_full_shape(missing):
    """GUILT for the shape validator: drop any one of the four fields and it
    must say no — a validator that passes a three-field entry is the
    `{endpoint, ruling}` fail-open one level up."""
    entry = _entry(tc.ENDPOINT, use="a use")
    del entry[missing]

    assert _full_shape(entry) is False


@pytest.mark.parametrize("blank", ["", "   "])
def test_an_entry_with_a_blank_field_is_not_full_shape(blank):
    assert _full_shape(_entry(tc.ENDPOINT, use=blank)) is False
    assert _full_shape(_entry(tc.ENDPOINT, use="a use", ruling=blank)) is False


def test_every_shipped_entry_cites_a_ruling_that_names_its_endpoint():
    """A `ruling` field is a ledger pointer, and a pointer to nothing is the
    fail-open this file exists to prevent, one level up: the entry would
    authorize while the record that justifies it does not exist. Every
    shipped ruling must be a quoted block of docs/rules/RULINGS.md that also
    names the endpoint being authorized."""
    text = RULINGS.read_text(encoding="utf-8")

    for entry in _shipped_entries():
        assert _justified(entry, text), (
            f"{entry['ruling']!r} is not a ruling in {RULINGS.name} naming {entry['endpoint']}"
        )


def test_a_ruling_absent_from_the_file_does_not_justify():
    """GUILT. The pointer names a ruling nobody wrote."""
    text = "> ⚡ **RULED 2026-01-01 (Zero):** something else entirely.\n"

    assert _justified(_entry(tc.ENDPOINT, ruling="RULED 2026-02-02"), text) is False


def test_a_ruling_naming_only_the_vendor_does_not_justify():
    """GUILT. The shape of the closed-door ruling: it names the vendor and
    never the endpoint. `_doc` asks for a ruling naming the endpoint AND its
    use; a block without the endpoint is not that ruling."""
    text = "> ⚡ **RULED 2026-02-02 (Zero):** the TypeSafe / Jev endpoint is NOT authorized.\n"

    assert _justified(_entry(tc.ENDPOINT, ruling="RULED 2026-02-02"), text) is False


def test_a_ruling_id_and_endpoint_in_different_blocks_do_not_justify():
    """GUILT. Two rulings, one carrying the id and the next carrying the
    endpoint, must not be read as one — a blank line between them is the
    file's own separator."""
    text = (
        f"> ⚡ **RULED 2026-02-02 (Zero):** the vendor is NOT authorized.\n"
        f"\n"
        f"> ⚡ **RULED 2026-03-03 (Zero):** `{tc.ENDPOINT}` is authorized.\n"
    )

    assert _justified(_entry(tc.ENDPOINT, ruling="RULED 2026-02-02"), text) is False


def test_a_ruling_naming_the_endpoint_justifies():
    """INNOCENCE. Without this the validator is unfalsifiable."""
    text = (
        f"> ⚡ **RULED 2026-03-03 (Zero):** `{tc.ENDPOINT}` IS an authorized vendor.\n"
        f">\n"
        f"> **Permitted use:** typed judgments over repository content.\n"
    )

    assert _justified(_entry(tc.ENDPOINT, ruling="RULED 2026-03-03"), text) is True


def test_ask_returns_the_answers_for_an_authorized_endpoint(listing, monkeypatch):
    """`ask()` mutated to `return None` unconditionally survives every OTHER
    test in this file, because they all test the REFUSAL and none of them
    ever reaches the transport with a real response. This is the one that
    tests the SPEECH: an authorized endpoint, a stubbed valid reply, and the
    parsed `answers` map coming back untouched."""
    _, write = listing
    write(
        {
            "endpoints": [
                {"endpoint": tc.ENDPOINT, "ruling": "RULED 2026-01-01", "paths": ["**"]}
            ]
        }
    )
    monkeypatch.setenv(tc.ENV_VAR, "a-configured-key")

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def read(self):
            return json.dumps(
                {"answers": {"direct_paid_sdk": {"type": "noul", "noul": 0.91}}}
            ).encode("utf-8")

    class _Opener:
        def open(self, *_a, **_k):
            return _Resp()

    monkeypatch.setattr(tc, "_OPENER", _Opener())

    result = tc.ask({"file": {"content": "x"}}, {"direct_paid_sdk": {}})

    assert result == {"direct_paid_sdk": {"type": "noul", "noul": 0.91}}


@contextmanager
def _redirect_pair():
    """A local origin that answers 302 to a local target: the target's record
    of whether it was ever hit and with what `Authorization` header, and the
    origin's own hit count.

    Reproduces the shape reported against PR #6989 with the real
    `HTTPRedirectHandler`, not a simulation: a POST to `origin` gets a `302`
    naming `target`, and a client with the default opener would issue a
    second, unauthenticated-looking GET to `target` carrying the bearer.
    """
    hits: list[str | None] = []
    origin_hits: list[int] = []

    class TargetHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            hits.append(self.headers.get("Authorization"))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *_a):
            pass

    target_srv = ThreadingHTTPServer(("127.0.0.1", 0), TargetHandler)
    target_thread = threading.Thread(target=target_srv.serve_forever, daemon=True)
    target_thread.start()
    target_url = f"http://127.0.0.1:{target_srv.server_address[1]}/charge"

    class OriginHandler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            origin_hits.append(1)
            self.send_response(302)
            self.send_header("Location", target_url)
            self.end_headers()

        def log_message(self, *_a):
            pass

    origin_srv = ThreadingHTTPServer(("127.0.0.1", 0), OriginHandler)
    origin_thread = threading.Thread(target=origin_srv.serve_forever, daemon=True)
    origin_thread.start()
    origin_url = f"http://127.0.0.1:{origin_srv.server_address[1]}/v1/systemone"

    try:
        yield origin_url, hits, origin_hits
    finally:
        origin_srv.shutdown()
        origin_srv.server_close()
        origin_thread.join(timeout=5)
        target_srv.shutdown()
        target_srv.server_close()
        target_thread.join(timeout=5)


def test_a_redirect_never_reaches_the_second_host(listing, monkeypatch):
    """GATING — condition 1 of the successor to PR #6989's Gear-3 gate.

    The base client (predating this diff) called `urlopen` with the default
    opener, which follows a `302` and carries `Authorization` to the new
    host — reproduced against the real handler on py 3.11.15: `AUTH FORWARDED
    True`. Authorizing an endpoint bound the FIRST HOP ONLY.

    Mechanism, verified against the real handler rather than assumed: refusing
    the redirect makes `OpenerDirector` raise `HTTPError(302)` — it does NOT
    hand back the 302 response for `ask()` to fail to parse. 302 is outside
    `RETRY_STATUS`, so `ask()` returns `None` on the FIRST attempt with no
    retry and no backoff delay; `origin_hits == 1` pins that down, since a
    retry loop silently re-POSTing to the origin would not be caught by
    `target_hits` alone. Either way the target never sees the bearer because
    it never sees a request.
    """
    _, write = listing

    with _redirect_pair() as (origin_url, target_hits, origin_hits):
        monkeypatch.setattr(tc, "ENDPOINT", origin_url)
        write(
            {
                "endpoints": [
                    {"endpoint": origin_url, "ruling": "test", "use": "test", "paths": ["**"]}
                ]
            }
        )
        monkeypatch.setenv(tc.ENV_VAR, "a-configured-key")

        result = tc.ask({"file": {"content": "x"}}, {})

    assert result is None, "a refused redirect raises HTTPError(302), which ask() degrades to None"
    assert origin_hits == [1], "no retry: 302 is outside RETRY_STATUS"
    assert target_hits == [], "the second hop must never be reached"


# ───────────────────────────── the opener is MODULE-LOCAL (PWC-6999, condition 1)

_SCRIPTS = Path(__file__).resolve().parents[1]


def _global_opener_after_import(extra: str = "") -> str:
    """Probe `urllib.request._opener` in a FRESH interpreter.

    That attribute is process-global state: an in-process assertion would report
    whatever an earlier test in the same session left there, in either direction.
    `extra` runs after the import so the probe can be made to say yes on purpose.
    """
    code = (
        "import sys, urllib.request\n"
        f"sys.path.insert(0, {str(_SCRIPTS)!r})\n"
        "import typesafe_client\n"
        f"{extra}\n"
        "print('installed' if urllib.request._opener is not None else 'none')\n"
    )
    done = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


def test_importing_the_client_installs_no_process_wide_opener():
    """The no-redirect opener is held module-local, and this is what keeps it so.

    `urllib.request.install_opener(_OPENER)` would make `_NoRedirects` bind every
    OTHER `urlopen` caller in the interpreter — a regression elsewhere that this
    client's own refusal would never reveal. Until this test the property lived
    in three sentences of prose and no assertion: the gate of PR #6999 measured
    that mutant GREEN at 120 passed.
    """
    assert _global_opener_after_import() == "none"
    assert isinstance(tc._OPENER, urllib.request.OpenerDirector)
    assert any(isinstance(h, tc._NoRedirects) for h in tc._OPENER.handlers)


def test_the_opener_probe_can_say_yes():
    """Guilt control for the test above: the same probe with the mutant applied
    AFTER import reports the installed opener — so a green above is a finding
    about the module, not about a probe that cannot see."""
    mutant = "urllib.request.install_opener(typesafe_client._OPENER)"
    assert _global_opener_after_import(mutant) == "installed"
