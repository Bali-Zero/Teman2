"""Offline preparation does not invent authority or leak rejected input."""

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import stat
from uuid import uuid4

import pytest

from backend.services.autonomous_lab.consul_native_broker import NativeGrant
from backend.tests.unit.services.autonomous_lab.consul_fixtures import reseal
from backend.tests.unit.services.autonomous_lab.native_consul_fixtures import (
    make_native_grant,
)
from scripts.conductor import consul_packet as packet
from scripts.conductor.codex_shadow_launch import QUALIFIED_BINARY_SHA256
from scripts.conductor.consul_native import CANARY_TEXT

NOW = datetime(2026, 9, 6, 12, tzinfo=timezone.utc)


def discovery():
    return {
        "mode": "discovery",
        "inference_performed": False,
        "binding": {
            "mission_id": str(uuid4()),
            "input_hash": sha256(CANARY_TEXT.encode()).hexdigest(),
            "discovery_key": {
                "runtime_version": "codex-cli 0.153.4@"
                + QUALIFIED_BINARY_SHA256["codex-cli 0.153.4"],
                "config_hash": "a" * 64,
                "host": "Air-M5",
                "auth_context_hash": "b" * 64,
            },
            "model": "gpt-6-astra",
            "effort": "medium",
            "thread_id": None,
        },
    }


def prepared(producer="astra", observed=None):
    return packet.prepare(
        observed or discovery(),
        producer=producer,
        action_item_ref={"action_item_id": str(uuid4()), "object_hash": "c" * 64},
        requested_action_spec_ref={
            "requested_action_spec_id": str(uuid4()),
            "object_hash": "d" * 64,
        },
        now=NOW - timedelta(seconds=20),
    )


def authority(draft):
    """Test-only receipts; production never imports this synthetic builder."""
    binding = draft["binding"]
    grant = make_native_grant(
        NOW,
        binding["mission_id"],
        binding=binding,
        builder=draft["intent"]["producer"]["name"].rsplit(".", 1)[-1],
    )
    intent = draft["intent"]
    approval = reseal(
        grant.approval,
        subject={
            "kind": "action_intent",
            "object_id": intent["action_intent_id"],
            "object_hash": intent["object_hash"],
        },
        context={"action_item_ref": intent["action_item_ref"]},
    )
    review = reseal(
        grant.review,
        target_objects=[
            {
                "object_kind": "action_intent",
                "object_id": intent["action_intent_id"],
                "object_hash": intent["object_hash"],
            }
        ],
    )
    return approval.model_dump(mode="json", exclude_unset=True), review.model_dump(
        mode="json", exclude_unset=True
    )


@pytest.mark.parametrize("producer", ["astra", "fable"])
def test_prepare_and_assemble_both_producer_directions(producer):
    draft = prepared(producer)
    assert set(draft) == {"version", "binding", "intent"}
    assert draft["intent"]["producer"]["name"] == "com.balizero.consul." + producer
    approval, review = authority(draft)
    result = packet.assemble(draft, approval, review, grant_id=str(uuid4()), now=NOW)
    NativeGrant.from_payload(result).validate(NOW)
    assert result["approval"] == approval
    assert result["review"] == review


@pytest.mark.parametrize(
    "change",
    [
        {"input_hash": "f" * 64},
        {"model": "gpt-5.6-terra"},
        {"effort": "ultra"},
        {"thread_id": "already-started"},
        {"mission_id": "client-name"},
    ],
)
def test_prepare_refuses_any_widening_of_fixed_canary(change):
    value = discovery()
    value["binding"].update(change)
    with pytest.raises((ValueError, PermissionError)):
        prepared(observed=value)


@pytest.mark.parametrize(
    "change",
    [
        {"mode": "invoke"},
        {"inference_performed": 0},
        {"unexpected": "private"},
    ],
)
def test_prepare_refuses_non_discovery_and_extra_fields(change):
    value = discovery()
    value.update(change)
    with pytest.raises(ValueError):
        prepared(observed=value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("config_hash", "e" * 64),
        ("auth_context_hash", "f" * 64),
        ("host", "Nuzantara"),
        ("runtime_version", "codex-cli 0.153.4@" + "0" * 64),
    ],
)
def test_assemble_rejects_binding_drift(field, value):
    draft = prepared()
    approval, review = authority(draft)
    draft["binding"]["discovery_key"][field] = value
    with pytest.raises((ValueError, PermissionError)):
        packet.assemble(draft, approval, review, grant_id=str(uuid4()), now=NOW)


@pytest.mark.parametrize("producer", ["astra", "fable"])
def test_assemble_rejects_same_family_review_and_corrupt_intent(producer):
    draft = prepared(producer)
    approval, review = authority(draft)
    model = packet.NativeGrant.from_payload(
        {
            "grant_id": str(uuid4()),
            "binding": draft["binding"],
            "intent": draft["intent"],
            "approval": approval,
            "review": review,
        }
    ).review
    wrong = reseal(
        model,
        verifier={**review["verifier"], "name": "com.balizero.consul." + producer},
    )
    with pytest.raises(PermissionError, match="native_review"):
        packet.assemble(
            draft,
            approval,
            wrong.model_dump(mode="json", exclude_unset=True),
            grant_id=str(uuid4()),
            now=NOW,
        )
    draft["intent"]["arguments_hash"] = "0" * 64
    with pytest.raises(ValueError):
        packet.assemble(draft, approval, review, grant_id=str(uuid4()), now=NOW)


@pytest.mark.parametrize("reference", ["action_item_ref", "requested_action_spec_ref"])
@pytest.mark.parametrize("bad_hash", ["", "a" * 63, "g" * 64, "A" * 64])
def test_prepare_rejects_malformed_source_reference_hashes(reference, bad_hash):
    refs = {
        "action_item_ref": {"action_item_id": str(uuid4()), "object_hash": "a" * 64},
        "requested_action_spec_ref": {
            "requested_action_spec_id": str(uuid4()),
            "object_hash": "b" * 64,
        },
    }
    refs[reference]["object_hash"] = bad_hash
    with pytest.raises(ValueError):
        packet.prepare(discovery(), producer="astra", now=NOW, **refs)


@pytest.mark.parametrize("offset", [-60, 241, 301])
def test_assemble_checks_current_time_not_approval_issue_time(offset):
    draft = prepared()
    approval, review = authority(draft)
    with pytest.raises((ValueError, PermissionError)):
        packet.assemble(
            draft,
            approval,
            review,
            grant_id=str(uuid4()),
            now=NOW + timedelta(seconds=offset),
        )


@pytest.mark.parametrize("grant_id", ["slug", str(uuid4()).upper(), "../private", ""])
def test_assemble_requires_canonical_uuid_grant(grant_id):
    draft = prepared()
    approval, review = authority(draft)
    with pytest.raises((ValueError, PermissionError)):
        packet.assemble(draft, approval, review, grant_id=grant_id, now=NOW)


def test_file_io_exclusive_private_and_no_symlinks(tmp_path):
    root = tmp_path.resolve()
    output = root / "prepared.json"
    packet.write_json(output, prepared())
    original = output.read_bytes()
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert packet.read_json(output)["version"] == 1
    with pytest.raises(FileExistsError):
        packet.write_json(output, {})
    assert output.read_bytes() == original
    link = root / "linked.json"
    link.symlink_to(output)
    for operation in (
        lambda: packet.read_json(link),
        lambda: packet.write_json(link, {}),
    ):
        with pytest.raises(OSError):
            operation()
    alias = root / "alias"
    alias.symlink_to(root, target_is_directory=True)
    with pytest.raises(OSError):
        packet.write_json(alias / "new.json", {})
    assert not (root / "new.json").exists()
    with pytest.raises(ValueError):
        packet.write_json(Path("relative.json"), {})


@pytest.mark.parametrize(
    "raw",
    [
        b'{"secret":1,"secret":2}',
        b'{"secret":NaN}',
        b"private fixture not json",
        b'"private fixture"',
        b" " * (packet.MAX_GRANT_BYTES + 1),
    ],
)
def test_input_read_errors_are_redacted(raw, tmp_path, capsys):
    root = tmp_path.resolve()
    path, output = root / "private-fixture.json", root / "out.json"
    path.write_bytes(raw)
    code = packet.main(
        [
            "assemble",
            "--prepared",
            str(path),
            "--approval",
            str(path),
            "--review",
            str(path),
            "--grant-id",
            str(uuid4()),
            "--output",
            str(output),
        ]
    )
    assert code == 1 and not output.exists()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "consul_packet_refused\n"


def test_cli_argument_errors_do_not_echo_values(capsys):
    assert packet.main(["prepare", "--producer", "private-invalid-value"]) == 1
    assert capsys.readouterr().err == "consul_packet_refused\n"


def test_cli_prepare_writes_only_new_artifact(tmp_path, capsys):
    root = tmp_path.resolve()
    source, output = root / "discovery.json", root / "prepared.json"
    source.write_text(json.dumps(discovery()))
    argv = [
        "prepare",
        "--discovery",
        str(source),
        "--producer",
        "astra",
        "--action-item-id",
        str(uuid4()),
        "--action-item-hash",
        "a" * 64,
        "--requested-action-spec-id",
        str(uuid4()),
        "--requested-action-spec-hash",
        "b" * 64,
        "--output",
        str(output),
    ]
    assert packet.main(argv) == 0
    assert capsys.readouterr().out == ""
    assert packet.read_json(output)["intent"]["action_type"] == packet.EFFECT
    assert packet.main(argv) == 1
    assert capsys.readouterr().err == "consul_packet_refused\n"


def test_cli_assemble_uses_actual_clock_and_preserves_supplied_receipts(
    tmp_path, monkeypatch, capsys
):
    root = tmp_path.resolve()
    draft = prepared()
    approval, review = authority(draft)
    paths = {
        name: root / (name + ".json") for name in ("prepared", "approval", "review")
    }
    for name, payload in (
        ("prepared", draft),
        ("approval", approval),
        ("review", review),
    ):
        paths[name].write_text(json.dumps(payload))

    class Clock:
        current = NOW

        @classmethod
        def now(cls, tz):
            assert tz is timezone.utc
            return cls.current

    monkeypatch.setattr(packet, "datetime", Clock)
    output = root / "grant.json"
    argv = ["assemble", "--grant-id", str(uuid4()), "--output", str(output)]
    for name, path in paths.items():
        argv.extend(["--" + name, str(path)])
    assert packet.main(argv) == 0
    assert capsys.readouterr().out == ""
    result = packet.read_json(output)
    assert result["approval"] == approval and result["review"] == review
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    Clock.current += timedelta(minutes=10)
    argv[4] = str(root / "expired.json")
    assert packet.main(argv) == 1
    assert not (root / "expired.json").exists()
    assert capsys.readouterr().err == "consul_packet_refused\n"


def test_missing_file_path_is_not_echoed(tmp_path, capsys):
    missing = str(tmp_path.resolve() / "private-fixture-missing.json")
    assert (
        packet.main(
            [
                "assemble",
                "--prepared",
                missing,
                "--approval",
                missing,
                "--review",
                missing,
                "--grant-id",
                str(uuid4()),
                "--output",
                missing,
            ]
        )
        == 1
    )
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == "consul_packet_refused\n"


def test_preparation_is_separate_from_issuer_authenticity():
    assert "NOT issuer authenticity" in packet.__doc__
    assert "offline tool does not establish their existence" in packet.__doc__
