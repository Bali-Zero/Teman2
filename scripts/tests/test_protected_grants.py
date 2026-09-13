"""Protected authority cannot be replaced by caller JSON or writable files."""

import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from scripts.conductor.protected_grants import (
    MAX_REQUEST_BYTES,
    grant_name,
    parse_request,
    protected_document,
    strict_json,
)


def read(directory: Path, filename: str = "grant.json", **kwargs):
    return protected_document(
        directory, filename, file_uid=os.getuid(), directory_uid=os.getuid(), **kwargs
    )


def test_protected_document_reads_only_regular_bounded_owned_file(tmp_path):
    file = tmp_path / "grant.json"
    file.write_text('{"grant_id":"fixture"}')
    file.chmod(0o600)
    assert read(tmp_path, private=True) == {"grant_id": "fixture"}


@pytest.mark.parametrize(
    "kind",
    [
        "symlink",
        "hardlink",
        "group_write",
        "public_config",
        "directory",
        "oversize",
        "writable_parent",
    ],
)
def test_untrusted_document_is_rejected(tmp_path, kind):
    file = tmp_path / "grant.json"
    file.write_text("{}")
    file.chmod(0o600)
    kwargs = {}
    if kind == "symlink":
        file.rename(tmp_path / "other")
        file.symlink_to(tmp_path / "other")
    elif kind == "hardlink":
        os.link(file, tmp_path / "other")
    elif kind == "group_write":
        file.chmod(0o620)
    elif kind == "public_config":
        file.chmod(0o644)
        kwargs["private"] = True
    elif kind == "directory":
        file.unlink()
        file.mkdir()
    elif kind == "oversize":
        kwargs["max_bytes"] = 1
    else:
        tmp_path.chmod(0o777)
    with pytest.raises((PermissionError, OSError, ValueError)):
        read(tmp_path, **kwargs)


def test_protected_loader_rejects_untrusted_owner_and_directory_symlink(tmp_path):
    (tmp_path / "grant.json").write_text("{}")
    with pytest.raises(PermissionError):
        protected_document(
            tmp_path,
            "grant.json",
            file_uid=os.getuid() + 1000,
            directory_uid=os.getuid(),
        )
    link = tmp_path / "link"
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(PermissionError):
        read(link)


@pytest.mark.parametrize(
    "value", ["../x", "A" * 32, "", None, "{11111111-1111-1111-1111-111111111111}"]
)
def test_grant_id_cannot_choose_arbitrary_path(value):
    with pytest.raises(ValueError):
        grant_name(value)


@pytest.mark.parametrize(
    "raw", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b"[]", b"null"]
)
def test_ambiguous_json_refused(raw):
    with pytest.raises(ValueError):
        strict_json(raw)


@pytest.mark.parametrize(
    "extra",
    [
        {"approval": {}},
        {"database_dsn": "postgresql://caller"},
        {"command": "anything"},
        {"version": True},
        {"verb": "execute"},
    ],
)
def test_protocol_never_accepts_self_issued_authority_or_arbitrary_command(extra):
    request = {
        "version": 1,
        "verb": "admit",
        "grant_id": str(uuid4()),
        "binding": {},
        **extra,
    }
    with pytest.raises(ValueError):
        parse_request(json.dumps(request).encode())


def test_protocol_bounded_and_closed_but_cancel_allows_no_lease():
    request = {"version": 1, "verb": "cancel", "grant_id": str(uuid4())}
    assert parse_request(json.dumps(request).encode()) == request
    with pytest.raises(ValueError):
        parse_request(b" " * (MAX_REQUEST_BYTES + 1))
    with pytest.raises(ValueError):
        read(Path("/"), "../arbitrary")
