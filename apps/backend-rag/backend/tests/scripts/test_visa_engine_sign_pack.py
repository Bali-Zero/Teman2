"""Tests for ``backend.scripts.visa_engine.sign_pack``.

TDD per the PR-A1 task brief:

(a) sign -> verify roundtrip with EPHEMERAL in-fixture keys through the
    REAL ``bundle.verify_rule_pack`` (ephemeral test keys are explicitly
    sanctioned by ``bundle.py``'s own module docstring: "Tests MAY generate
    ephemeral Ed25519 keys in-fixture to produce signed fixtures; that is a
    throwaway test key, not a ceremony").
(b) the COMMITTED signed fixture (produced once, for real, against the real
    TEST ceremony key) verifies via a ``StaticTrustStore`` pinned with the
    TEST PUBLIC key the task brief mandates as the cross-language test
    vector — this is the one place in this file a REAL (non-ephemeral,
    non-secret) value is asserted verbatim.
(c) guilt tests: a tampered payload fails verification; a wrong kid fails
    verification; ``sign_pack`` refuses a world-readable key file (an
    EPHEMERAL throwaway key created in ``tmp_path`` for this one test —
    the real ceremony key is NEVER touched by this suite); ``sign_pack``
    refuses ``--environment PRODUCTION`` without
    ``--i-know-this-is-production``.
(d) the offline signing ceremony never touches the private key's raw bytes
    in anything this suite can observe (stdout/the written envelope).

Post-review hardening (PR-A1 codex correctness review, gpt-5.6-sol xhigh —
6 real findings fixed, see ``sign_pack.py``'s inline comments for each):
``TestOutputCollisionGuard`` (finding #1), ``TestFutureSkewSelfVerify``
(finding #2), ``TestProductionGateStrictIdentity`` (finding #3),
``TestPermissionCheckIsToctouSafe`` (finding #4, also strengthens the
guilt-test-quality gap in finding #6), and the strengthened leak checks in
``TestNeverLeaksPrivateKeyMaterial`` (also finding #6). The compile_pack
nitpick (finding #7) is fixed in ``test_visa_engine_compile_pack.py``.

Round 2 (same review, confirming pass): ``TestOutputCollisionGuard`` gains
a hardlink/same-inode test (round-2 finding #1 — the original round-1 fix
compared resolved path STRINGS only, missing a same-inode alias e.g. on a
case-insensitive filesystem); ``TestKeyFileMustBeRegular`` (round-2 finding
#2 — FIFO/oversized-file rejection); ``TestUnsupportedAlgorithmIsWrapped``
and ``TestPathResolutionFailureIsWrapped`` (round-2 finding #3 — no raw
traceback from either the PEM parser or path resolution).
"""

from __future__ import annotations

import base64
import copy
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from backend.scripts.visa_engine.sign_pack import SignPackError, main, sign_pack
from backend.services.visa_engine.bundle import (
    StaticTrustStore,
    TrustedSigningKey,
    verify_rule_pack,
)
from backend.services.visa_engine.errors import RulePackVerificationError
from backend.tests.services.visa_engine._builders import (
    ed25519_public_key_b64url,
    ephemeral_ed25519_keypair,
    minimal_valid_envelope,
)

_FIXTURE_SIGNED = (
    Path(__file__).resolve().parents[2]
    / "services"
    / "visa_engine"
    / "contracts"
    / "packs"
    / "rulepack-test-c1-tourism.signed.json"
)

#: The cross-language test-vector public key the task brief mandates,
#: derived (and empirically re-verified, see PR body) from the real TEST
#: ceremony private key at
#: ``~/.config/nuzantara/visa-signing/2026-07-test-1.ed25519.pem`` — a
#: PUBLIC value, safe to commit verbatim. This suite never reads that PEM
#: file itself; it only checks the already-signed, already-committed
#: bundle against this pinned public key.
_TEST_CEREMONY_PUBLIC_KEY_B64URL = "hPwtyP1ekdj_n-BK4M97dyWnRxW1RJ-uGcnVsX5buHM"

_UTC_NOW = datetime(2026, 7, 19, 0, 10, 0, tzinfo=timezone.utc)


def _write_pem(path: Path, private_key, *, mode: int = 0o600) -> None:
    pem_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    path.write_bytes(pem_bytes)
    path.chmod(mode)


def _decode_b64url(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


class TestSignVerifyRoundtripEphemeralKey:
    def test_sign_then_verify_via_real_bundle_verify_rule_pack(self, tmp_path: Path) -> None:
        private_key, public_key = ephemeral_ed25519_keypair()
        key_path = tmp_path / "ephemeral.ed25519.pem"
        _write_pem(key_path, private_key)

        payload_path = tmp_path / "pack.json"
        payload = minimal_valid_envelope()["payload"]
        payload_path.write_text(json.dumps(payload), encoding="utf-8")
        output_path = tmp_path / "signed.json"

        envelope, public_key_b64url = sign_pack(
            payload_source=payload_path,
            kid="key-ephemeral-roundtrip",
            key_file=key_path,
            environment="TEST",
            sequence=1,
            output=output_path,
            signed_at=_UTC_NOW,
        )

        assert public_key_b64url == ed25519_public_key_b64url(public_key)

        trust_store = StaticTrustStore(
            [
                TrustedSigningKey(
                    key_id="key-ephemeral-roundtrip",
                    public_key=public_key,
                    valid_from=_UTC_NOW,
                    valid_to=None,
                    revoked_at=None,
                    environment="TEST",
                )
            ]
        )
        verified = verify_rule_pack(envelope, trust_store=trust_store, observed_at=_UTC_NOW)
        assert verified.unsigned_dev is False
        assert str(verified.pack.payload.rule_pack_id) == payload["rule_pack_id"]

    def test_main_writes_output_file_and_exits_zero(self, tmp_path: Path) -> None:
        private_key, _public_key = ephemeral_ed25519_keypair()
        key_path = tmp_path / "ephemeral.ed25519.pem"
        _write_pem(key_path, private_key)
        payload_path = tmp_path / "pack.json"
        payload = minimal_valid_envelope()["payload"]
        payload_path.write_text(json.dumps(payload), encoding="utf-8")
        output_path = tmp_path / "signed.json"

        rc = main(
            [
                str(payload_path),
                "--kid",
                "key-ephemeral-cli",
                "--key-file",
                str(key_path),
                "--environment",
                "TEST",
                "--sequence",
                "1",
                "--signed-at",
                "2026-07-19T00:10:00Z",
                "--output",
                str(output_path),
            ]
        )

        assert rc == 0
        assert output_path.exists()
        written = output_path.read_text(encoding="utf-8")
        assert "key-ephemeral-cli" in written


class TestCommittedFixtureVerifiesAgainstPinnedTestKey:
    def test_committed_signed_fixture_verifies(self) -> None:
        assert _FIXTURE_SIGNED.exists(), f"fixture missing: {_FIXTURE_SIGNED}"
        envelope = json.loads(_FIXTURE_SIGNED.read_text(encoding="utf-8"))

        public_key = Ed25519PublicKey.from_public_bytes(
            _decode_b64url(_TEST_CEREMONY_PUBLIC_KEY_B64URL)
        )
        trust_store = StaticTrustStore(
            [
                TrustedSigningKey(
                    key_id=envelope["protected"]["kid"],
                    public_key=public_key,
                    valid_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
                    valid_to=None,
                    revoked_at=None,
                    environment="TEST",
                )
            ]
        )
        verified = verify_rule_pack(
            envelope,
            trust_store=trust_store,
            observed_at=datetime(2026, 7, 19, 0, 30, 0, tzinfo=timezone.utc),
        )
        assert verified.unsigned_dev is False
        assert verified.pack.payload.environment.value == "TEST"


class TestGuilt:
    def test_tampered_payload_fails_verification(self, tmp_path: Path) -> None:
        private_key, public_key = ephemeral_ed25519_keypair()
        key_path = tmp_path / "ephemeral.ed25519.pem"
        _write_pem(key_path, private_key)
        payload_path = tmp_path / "pack.json"
        payload = minimal_valid_envelope()["payload"]
        payload_path.write_text(json.dumps(payload), encoding="utf-8")
        output_path = tmp_path / "signed.json"

        envelope, _pk = sign_pack(
            payload_source=payload_path,
            kid="key-tamper-test",
            key_file=key_path,
            environment="TEST",
            sequence=1,
            output=output_path,
            signed_at=_UTC_NOW,
        )

        tampered = copy.deepcopy(envelope)
        # Flip a rule's priority to another SCHEMA-VALID value (still within
        # [0, 100000], so the JSON Schema pass does not itself catch it) —
        # payload_sha256 stays declared as the ORIGINAL value, so the tamper
        # must be caught by the payload_sha256 self-consistency check
        # specifically, not merely by schema validation.
        original_priority = tampered["payload"]["rules"][0]["priority"]
        tampered["payload"]["rules"][0]["priority"] = original_priority + 1

        trust_store = StaticTrustStore(
            [
                TrustedSigningKey(
                    key_id="key-tamper-test",
                    public_key=public_key,
                    valid_from=_UTC_NOW,
                    valid_to=None,
                    revoked_at=None,
                    environment="TEST",
                )
            ]
        )
        with pytest.raises(RulePackVerificationError, match="payload_sha256"):
            verify_rule_pack(tampered, trust_store=trust_store, observed_at=_UTC_NOW)

    def test_wrong_kid_fails_verification(self, tmp_path: Path) -> None:
        private_key, public_key = ephemeral_ed25519_keypair()
        key_path = tmp_path / "ephemeral.ed25519.pem"
        _write_pem(key_path, private_key)
        payload_path = tmp_path / "pack.json"
        payload = minimal_valid_envelope()["payload"]
        payload_path.write_text(json.dumps(payload), encoding="utf-8")
        output_path = tmp_path / "signed.json"

        envelope, _pk = sign_pack(
            payload_source=payload_path,
            kid="key-real-kid",
            key_file=key_path,
            environment="TEST",
            sequence=1,
            output=output_path,
            signed_at=_UTC_NOW,
        )

        # Trust store only knows a DIFFERENT key_id than the one the
        # envelope claims to be signed with.
        trust_store = StaticTrustStore(
            [
                TrustedSigningKey(
                    key_id="key-a-different-kid",
                    public_key=public_key,
                    valid_from=_UTC_NOW,
                    valid_to=None,
                    revoked_at=None,
                    environment="TEST",
                )
            ]
        )
        with pytest.raises(RulePackVerificationError, match="unknown signing key_id"):
            verify_rule_pack(envelope, trust_store=trust_store, observed_at=_UTC_NOW)

    def test_refuses_world_readable_key_file(self, tmp_path: Path) -> None:
        private_key, _public_key = ephemeral_ed25519_keypair()
        # Deliberately throwaway, ephemeral key — chmod 0644 (world-readable)
        # to exercise the permission guard. NEVER the real ceremony key.
        key_path = tmp_path / "world-readable.ed25519.pem"
        _write_pem(key_path, private_key, mode=0o644)
        assert stat.S_IMODE(key_path.stat().st_mode) == 0o644
        payload_path = tmp_path / "pack.json"
        payload = minimal_valid_envelope()["payload"]
        payload_path.write_text(json.dumps(payload), encoding="utf-8")
        output_path = tmp_path / "signed.json"

        with pytest.raises(SignPackError, match="0644|world"):
            sign_pack(
                payload_source=payload_path,
                kid="key-world-readable",
                key_file=key_path,
                environment="TEST",
                sequence=1,
                output=output_path,
                signed_at=_UTC_NOW,
            )
        assert not output_path.exists()

    def test_refuses_production_without_explicit_flag(self, tmp_path: Path) -> None:
        # The PRODUCTION gate must fire BEFORE any other resource (payload
        # file, key file) is even touched — pass paths that do not exist to
        # prove the check-ordering.
        with pytest.raises(SignPackError, match="PRODUCTION"):
            sign_pack(
                payload_source=tmp_path / "does-not-exist.json",
                kid="key-prod-attempt",
                key_file=tmp_path / "does-not-exist.pem",
                environment="PRODUCTION",
                sequence=1,
                output=tmp_path / "signed.json",
                i_know_this_is_production=False,
            )

    def test_production_with_explicit_flag_reaches_compile_gate(self, tmp_path: Path) -> None:
        # With the flag set, the PRODUCTION-specific refusal must NOT fire
        # — the next thing that fails should be the payload read (a real,
        # different error), proving the gate only blocks the unacknowledged
        # case.
        with pytest.raises(SignPackError) as exc_info:
            sign_pack(
                payload_source=tmp_path / "does-not-exist.json",
                kid="key-prod-attempt",
                key_file=tmp_path / "does-not-exist.pem",
                environment="PRODUCTION",
                sequence=1,
                output=tmp_path / "signed.json",
                i_know_this_is_production=True,
            )
        assert "PRODUCTION" not in str(exc_info.value)
        assert "does-not-exist.json" in str(exc_info.value)

    def test_refuses_environment_mismatch(self, tmp_path: Path) -> None:
        private_key, _public_key = ephemeral_ed25519_keypair()
        key_path = tmp_path / "ephemeral.ed25519.pem"
        _write_pem(key_path, private_key)
        payload_path = tmp_path / "pack.json"
        payload = minimal_valid_envelope()["payload"]  # environment=TEST
        payload_path.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(SignPackError, match="environment"):
            sign_pack(
                payload_source=payload_path,
                kid="key-env-mismatch",
                key_file=key_path,
                environment="STAGING",
                sequence=1,
                output=tmp_path / "signed.json",
                signed_at=_UTC_NOW,
            )

    def test_refuses_sequence_mismatch(self, tmp_path: Path) -> None:
        private_key, _public_key = ephemeral_ed25519_keypair()
        key_path = tmp_path / "ephemeral.ed25519.pem"
        _write_pem(key_path, private_key)
        payload_path = tmp_path / "pack.json"
        payload = minimal_valid_envelope()["payload"]  # sequence=1
        payload_path.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(SignPackError, match="sequence"):
            sign_pack(
                payload_source=payload_path,
                kid="key-seq-mismatch",
                key_file=key_path,
                environment="TEST",
                sequence=2,
                output=tmp_path / "signed.json",
                signed_at=_UTC_NOW,
            )

    def test_refuses_to_sign_when_compile_gate_fails(self, tmp_path: Path) -> None:
        private_key, _public_key = ephemeral_ed25519_keypair()
        key_path = tmp_path / "ephemeral.ed25519.pem"
        _write_pem(key_path, private_key)
        payload = minimal_valid_envelope()["payload"]
        for rule in payload["rules"]:
            if rule["rule_id"] == "el-tourism":
                rule["required_facts"] = []  # REQUIRED_FACTS_MISMATCH
        payload_path = tmp_path / "pack.json"
        payload_path.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(SignPackError, match="compile_pack gate failed"):
            sign_pack(
                payload_source=payload_path,
                kid="key-broken-pack",
                key_file=key_path,
                environment="TEST",
                sequence=1,
                output=tmp_path / "signed.json",
                signed_at=_UTC_NOW,
            )

    def test_rejects_kid_not_matching_identifier_pattern(self, tmp_path: Path) -> None:
        private_key, _public_key = ephemeral_ed25519_keypair()
        key_path = tmp_path / "ephemeral.ed25519.pem"
        _write_pem(key_path, private_key)
        payload_path = tmp_path / "pack.json"
        payload = minimal_valid_envelope()["payload"]
        payload_path.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(SignPackError, match="Identifier pattern"):
            sign_pack(
                payload_source=payload_path,
                kid="2026-07-test-1",  # digit-first: fails Identifier pattern
                key_file=key_path,
                environment="TEST",
                sequence=1,
                output=tmp_path / "signed.json",
                signed_at=_UTC_NOW,
            )


class TestOutputCollisionGuard:
    """PR-A1 codex correctness review finding #1: ``--output`` must never be
    allowed to clobber ``--key-file`` or the payload source.
    """

    def test_refuses_output_same_as_key_file(self, tmp_path: Path) -> None:
        private_key, _public_key = ephemeral_ed25519_keypair()
        key_path = tmp_path / "ephemeral.ed25519.pem"
        _write_pem(key_path, private_key)
        original_key_bytes = key_path.read_bytes()
        payload_path = tmp_path / "pack.json"
        payload = minimal_valid_envelope()["payload"]
        payload_path.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(SignPackError, match="same file as --key-file"):
            sign_pack(
                payload_source=payload_path,
                kid="key-output-collides-with-key",
                key_file=key_path,
                environment="TEST",
                sequence=1,
                output=key_path,  # <-- collision
                signed_at=_UTC_NOW,
            )

        # The private key file itself must be untouched — never clobbered
        # with signed JSON output.
        assert key_path.read_bytes() == original_key_bytes

    def test_refuses_output_same_as_payload_source(self, tmp_path: Path) -> None:
        private_key, _public_key = ephemeral_ed25519_keypair()
        key_path = tmp_path / "ephemeral.ed25519.pem"
        _write_pem(key_path, private_key)
        payload_path = tmp_path / "pack.json"
        payload = minimal_valid_envelope()["payload"]
        original_payload_text = json.dumps(payload)
        payload_path.write_text(original_payload_text, encoding="utf-8")

        with pytest.raises(SignPackError, match="same file as the payload source"):
            sign_pack(
                payload_source=payload_path,
                kid="key-output-collides-with-source",
                key_file=key_path,
                environment="TEST",
                sequence=1,
                output=payload_path,  # <-- collision
                signed_at=_UTC_NOW,
            )

        assert payload_path.read_text(encoding="utf-8") == original_payload_text

    def test_refuses_output_hardlinked_to_key_file(self, tmp_path: Path) -> None:
        """PR-A1 codex ROUND-2 review finding #1: a pure resolved-path-STRING
        comparison misses a collision where ``--output`` is a DIFFERENT
        path spelling that is nonetheless the SAME file on disk (the
        motivating real-world case is a case-insensitive filesystem, e.g.
        macOS APFS default — ``Key.PEM`` vs ``key.pem`` — which a hardlink
        deterministically reproduces on ANY filesystem, portable across
        CI). ``output`` here is a hardlink to ``key_path``: textually a
        distinct path, but ``(st_dev, st_ino)`` identical.
        """
        private_key, _public_key = ephemeral_ed25519_keypair()
        key_path = tmp_path / "ephemeral.ed25519.pem"
        _write_pem(key_path, private_key)
        original_key_bytes = key_path.read_bytes()
        payload_path = tmp_path / "pack.json"
        payload = minimal_valid_envelope()["payload"]
        payload_path.write_text(json.dumps(payload), encoding="utf-8")

        hardlinked_output = tmp_path / "Key-Alias.ed25519.pem"
        os.link(key_path, hardlinked_output)
        assert hardlinked_output.stat().st_ino == key_path.stat().st_ino

        with pytest.raises(SignPackError, match="SAME FILE ON DISK"):
            sign_pack(
                payload_source=payload_path,
                kid="key-output-hardlinked-to-key",
                key_file=key_path,
                environment="TEST",
                sequence=1,
                output=hardlinked_output,  # <-- inode collision, different path text
                signed_at=_UTC_NOW,
            )

        assert key_path.read_bytes() == original_key_bytes


class TestFutureSkewSelfVerify:
    """PR-A1 codex correctness review finding #2: the self-verify step must
    check against the REAL wall-clock ``observed_at``, never
    ``signed_at_dt`` itself (which would make the skew always exactly zero
    by construction and defeat the guard for every signature, including an
    implausible/typo'd future ``--signed-at``).
    """

    def test_self_verify_rejects_implausibly_future_signed_at(self, tmp_path: Path) -> None:
        private_key, _public_key = ephemeral_ed25519_keypair()
        key_path = tmp_path / "ephemeral.ed25519.pem"
        _write_pem(key_path, private_key)
        payload_path = tmp_path / "pack.json"
        payload = minimal_valid_envelope()["payload"]
        payload_path.write_text(json.dumps(payload), encoding="utf-8")
        output_path = tmp_path / "signed.json"

        implausible_future = datetime(2035, 1, 1, tzinfo=timezone.utc)
        # PR-A1 codex round-2 review nitpick: `match="self-verification"`
        # alone could pass on an UNRELATED self-verification failure — also
        # require "in the future" so this test specifically proves the
        # future-skew path fired, not merely that self-verification failed
        # for some reason.
        with pytest.raises(SignPackError, match=r"self-verification.*in the future"):
            sign_pack(
                payload_source=payload_path,
                kid="key-future-skew",
                key_file=key_path,
                environment="TEST",
                sequence=1,
                output=output_path,
                signed_at=implausible_future,
            )
        assert not output_path.exists()


class TestProductionGateStrictIdentity:
    """PR-A1 codex correctness review finding #3: ``i_know_this_is_production``
    must be checked by strict identity (``is not True``), never truthiness —
    mirroring ``bundle.py``'s own ``allow_unsigned is not True`` pattern. A
    non-empty, truthy STRING like ``"false"`` must not silently disable the
    gate via ``not "false"`` == ``False``.
    """

    def test_production_gate_rejects_truthy_non_true_value(self, tmp_path: Path) -> None:
        with pytest.raises(SignPackError, match="PRODUCTION"):
            sign_pack(
                payload_source=tmp_path / "does-not-exist.json",
                kid="key-prod-string-bypass-attempt",
                key_file=tmp_path / "does-not-exist.pem",
                environment="PRODUCTION",
                sequence=1,
                output=tmp_path / "signed.json",
                i_know_this_is_production="false",  # type: ignore[arg-type]
            )


class TestPermissionCheckIsToctouSafe:
    """PR-A1 codex correctness review finding #4: the permission check and
    the content read must share one file descriptor. This test proves the
    check-before-read ORDERING directly — not just the final error message
    — by asserting ``os.read`` is never invoked once the mode check has
    already failed.
    """

    def test_key_file_content_never_read_when_permission_check_fails(self, tmp_path: Path) -> None:
        private_key, _public_key = ephemeral_ed25519_keypair()
        key_path = tmp_path / "world-readable.ed25519.pem"
        _write_pem(key_path, private_key, mode=0o644)
        payload_path = tmp_path / "pack.json"
        payload = minimal_valid_envelope()["payload"]
        payload_path.write_text(json.dumps(payload), encoding="utf-8")

        with patch("backend.scripts.visa_engine.sign_pack.os.read") as mock_read:
            with pytest.raises(SignPackError, match="0644|world"):
                sign_pack(
                    payload_source=payload_path,
                    kid="key-toctou-check",
                    key_file=key_path,
                    environment="TEST",
                    sequence=1,
                    output=tmp_path / "signed.json",
                    signed_at=_UTC_NOW,
                )
        mock_read.assert_not_called()


class TestKeyFileMustBeRegular:
    """PR-A1 codex ROUND-2 review finding #2: ``--key-file`` must be a
    REGULAR file, never a FIFO/device/directory, and the read is bounded so
    a swapped-in giant regular file cannot exhaust memory.
    """

    def test_refuses_fifo_key_file_without_hanging(self, tmp_path: Path) -> None:
        # Before the fix, `os.open(key_file, os.O_RDONLY)` on a FIFO with
        # no writer BLOCKS THE WHOLE PROCESS at open() time. `O_NONBLOCK`
        # plus the S_ISREG check must make this fail fast and cleanly
        # instead — this test itself is the proof-of-liveness: if the fix
        # regresses, this test hangs (and the suite's own timeout catches
        # it) rather than merely asserting a wrong value.
        fifo_path = tmp_path / "not-a-key.fifo"
        os.mkfifo(fifo_path, mode=0o600)
        payload_path = tmp_path / "pack.json"
        payload = minimal_valid_envelope()["payload"]
        payload_path.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(SignPackError, match="not a regular file"):
            sign_pack(
                payload_source=payload_path,
                kid="key-fifo-attempt",
                key_file=fifo_path,
                environment="TEST",
                sequence=1,
                output=tmp_path / "signed.json",
                signed_at=_UTC_NOW,
            )

    def test_refuses_key_file_exceeding_size_cap(self, tmp_path: Path) -> None:
        oversized_path = tmp_path / "oversized.ed25519.pem"
        # 1 MiB + 1 byte of junk — well past `_MAX_KEY_FILE_BYTES`, and NOT
        # a real PEM at all (the size cap must fire before the PEM parser
        # ever runs, so the content being garbage is deliberate).
        oversized_path.write_bytes(b"x" * ((1 << 20) + 1))
        oversized_path.chmod(0o600)
        payload_path = tmp_path / "pack.json"
        payload = minimal_valid_envelope()["payload"]
        payload_path.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(SignPackError, match="exceeds"):
            sign_pack(
                payload_source=payload_path,
                kid="key-oversized-attempt",
                key_file=oversized_path,
                environment="TEST",
                sequence=1,
                output=tmp_path / "signed.json",
                signed_at=_UTC_NOW,
            )


class TestUnsupportedAlgorithmIsWrapped:
    """PR-A1 codex ROUND-2 review finding #3 (first half): the PEM parser
    can raise ``cryptography.exceptions.UnsupportedAlgorithm`` (e.g. a
    PKCS8 key wrapping an OID ``cryptography`` doesn't support) in addition
    to ``ValueError``/``TypeError`` — that must be wrapped as
    ``SignPackError`` too, never surface as a raw traceback through
    ``main()``.
    """

    def test_unsupported_algorithm_from_pem_parser_is_wrapped(self, tmp_path: Path) -> None:
        private_key, _public_key = ephemeral_ed25519_keypair()
        key_path = tmp_path / "ephemeral.ed25519.pem"
        _write_pem(key_path, private_key)
        payload_path = tmp_path / "pack.json"
        payload = minimal_valid_envelope()["payload"]
        payload_path.write_text(json.dumps(payload), encoding="utf-8")

        with patch(
            "backend.scripts.visa_engine.sign_pack.serialization.load_pem_private_key",
            side_effect=UnsupportedAlgorithm("unsupported OID (simulated)"),
        ):
            with pytest.raises(SignPackError, match="not a valid PEM private key"):
                sign_pack(
                    payload_source=payload_path,
                    kid="key-unsupported-algo",
                    key_file=key_path,
                    environment="TEST",
                    sequence=1,
                    output=tmp_path / "signed.json",
                    signed_at=_UTC_NOW,
                )


class TestPathResolutionFailureIsWrapped:
    """PR-A1 codex ROUND-2 review finding #3 (second half): an
    ``OSError``/``RuntimeError`` raised while resolving ``--output``/
    ``--key-file``/``payload_source`` (e.g. a symlink loop) must be
    converted to ``SignPackError``, never surface as a raw traceback
    through ``main()``.
    """

    def test_symlink_loop_in_output_path_is_wrapped(self, tmp_path: Path) -> None:
        private_key, _public_key = ephemeral_ed25519_keypair()
        key_path = tmp_path / "ephemeral.ed25519.pem"
        _write_pem(key_path, private_key)
        payload_path = tmp_path / "pack.json"
        payload = minimal_valid_envelope()["payload"]
        payload_path.write_text(json.dumps(payload), encoding="utf-8")

        # A -> B -> A: `Path.resolve()` raises RuntimeError("Symlink loop")
        # on this (empirically verified against this Python's pathlib).
        loop_a = tmp_path / "loop-a"
        loop_b = tmp_path / "loop-b"
        os.symlink(loop_b, loop_a)
        os.symlink(loop_a, loop_b)

        with pytest.raises(SignPackError, match="cannot resolve"):
            sign_pack(
                payload_source=payload_path,
                kid="key-symlink-loop-output",
                key_file=key_path,
                environment="TEST",
                sequence=1,
                output=loop_a,
                signed_at=_UTC_NOW,
            )


class TestNeverLeaksPrivateKeyMaterial:
    """PR-A1 codex correctness review finding #6 (test-quality gap): the
    original version of this class only grepped for the literal string
    ``"PRIVATE KEY"``. That proves the PEM ARMOR never leaks, but says
    nothing about the RAW key bytes themselves leaking in hex/base64 form
    (e.g. via an accidental ``str(private_key)`` or a debug repr) — and the
    stdout test never checked the actual file ``main()`` wrote. Both gaps
    are closed here: every forbidden substring is checked against the
    envelope, stdout, stderr, AND the file on disk.
    """

    @staticmethod
    def _forbidden_substrings(private_key: Ed25519PrivateKey) -> list[str]:
        raw_private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return [
            "PRIVATE KEY",
            raw_private_bytes.hex(),
            base64.b64encode(raw_private_bytes).decode("ascii"),
            base64.urlsafe_b64encode(raw_private_bytes).decode("ascii").rstrip("="),
        ]

    def test_signed_output_never_contains_pem_markers_or_raw_key_bytes(
        self, tmp_path: Path
    ) -> None:
        private_key, _public_key = ephemeral_ed25519_keypair()
        key_path = tmp_path / "ephemeral.ed25519.pem"
        _write_pem(key_path, private_key)
        payload_path = tmp_path / "pack.json"
        payload = minimal_valid_envelope()["payload"]
        payload_path.write_text(json.dumps(payload), encoding="utf-8")
        output_path = tmp_path / "signed.json"

        envelope, _pk = sign_pack(
            payload_source=payload_path,
            kid="key-leak-check",
            key_file=key_path,
            environment="TEST",
            sequence=1,
            output=output_path,
            signed_at=_UTC_NOW,
        )

        serialized = str(envelope)
        for forbidden in self._forbidden_substrings(private_key):
            assert forbidden not in serialized

    def test_main_writes_no_key_material_to_stdout_stderr_or_output_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        private_key, _public_key = ephemeral_ed25519_keypair()
        key_path = tmp_path / "ephemeral.ed25519.pem"
        _write_pem(key_path, private_key)
        payload_path = tmp_path / "pack.json"
        payload = minimal_valid_envelope()["payload"]
        payload_path.write_text(json.dumps(payload), encoding="utf-8")
        output_path = tmp_path / "signed.json"

        rc = main(
            [
                str(payload_path),
                "--kid",
                "key-leak-check-cli",
                "--key-file",
                str(key_path),
                "--environment",
                "TEST",
                "--sequence",
                "1",
                "--signed-at",
                "2026-07-19T00:10:00Z",
                "--output",
                str(output_path),
            ]
        )
        assert rc == 0

        captured = capsys.readouterr()
        written_output = output_path.read_text(encoding="utf-8")
        for forbidden in self._forbidden_substrings(private_key):
            assert forbidden not in captured.out
            assert forbidden not in captured.err
            assert forbidden not in written_output
