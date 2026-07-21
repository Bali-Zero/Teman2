"""OFFLINE-ONLY CLI: sign a validated RulePack payload with a real Ed25519 key.

Spec §1 module layout (``research/visa/2026-07-17-visa-oracle-v2-round2-
codex-engine-concretization.md``): ``scripts/visa_engine/sign_pack.py`` —
"offline only; private key never present in FastAPI".

**This script NEVER runs inside the FastAPI process.** It exists solely for
the offline signing ceremony an operator runs by hand, on their own machine,
against a key file that never leaves local disk. ``bundle.py``'s own module
docstring states the FIREBREAK this script is the signing half of: "key
generation/registration is the operator's ceremony, never autonomous code"
— nothing in this package imports ``sign_pack`` from any server code path,
and it must never be added to one.

Builds the exact spec §3 signing envelope (verbatim from ``bundle.py``'s
module docstring, which this script's signing-input construction
independently re-derives rather than importing — see ``_SIGNING_DOMAIN``
below for why that duplication is deliberate)::

    signed_bytes =
        UTF8("balizero.visa-rulepack.v1")
        || 0x00
        || JCS(protected)
        || 0x00
        || JCS(payload)

Refuses to sign unless the payload FIRST passes ``compile_pack.
compile_pack_source``'s gate, re-run internally on every invocation — a
signature over a broken pack is worse than no signature: it carries the full
weight of a "trusted" bundle while still failing every downstream evaluator
invariant.

SECURITY RAILS (absolute):

* Never prints/logs the private key's raw bytes or anything derived from it
  that could reconstruct it. The derived PUBLIC key IS printed on success —
  that is not a secret, it is the exact value an operator pins into a
  ``StaticTrustStore``.
* Loads the PEM in-process only, via ``cryptography``'s own PEM parser —
  never shells out to ``openssl`` or any external process that could leak
  key material via argv, a shell history file, or a subprocess log.
* Refuses to sign if the key file is not ``chmod 0600`` (or stricter) — the
  mode is checked via ``fstat`` on the SAME file descriptor the content is
  then read from (never a separate stat-by-path followed by a separate
  open-by-path), so there is no TOCTOU window for a symlink swap between
  the check and the read. No byte of the file's CONTENT is read before the
  mode check passes.
* Refuses ``--environment PRODUCTION`` unless ``--i-know-this-is-production``
  is EXACTLY ``True`` (strict identity check, not truthiness — a caller
  passing the string ``"false"`` must not silently bypass the gate).
* Refuses an ``--output`` that would overwrite ``--key-file`` or the
  payload source, and writes the signed bundle atomically (temp file +
  rename) so a crash mid-write can never leave a truncated ``--output``.

Usage::

    PYTHONPATH=. python -m backend.scripts.visa_engine.sign_pack \\
        backend/services/visa_engine/contracts/packs/rulepack-test-c1-tourism.source.json \\
        --kid key-2026-07-test-1 \\
        --key-file /path/to/2026-07-test-1.ed25519.pem \\
        --environment TEST \\
        --sequence 1 \\
        --output backend/services/visa_engine/contracts/packs/rulepack-test-c1-tourism.signed.json
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from backend.scripts.visa_engine.compile_pack import compile_pack_source, format_report
from backend.services.visa_engine.bundle import (
    StaticTrustStore,
    TrustedSigningKey,
    canonicalize_json,
)
from backend.services.visa_engine.bundle import verify_rule_pack as bundle_verify_rule_pack
from backend.services.visa_engine.enums import Environment
from backend.services.visa_engine.errors import RulePackVerificationError
from backend.services.visa_engine.models import IDENTIFIER_PATTERN, utc_isoformat

#: Independently re-derived (NOT imported from ``bundle.py``'s private
#: ``_SIGNING_DOMAIN``) as a deliberate cross-check on the production
#: signing-input formula — the same convention already established by
#: ``backend/tests/services/visa_engine/_builders.py``'s
#: ``sign_rule_pack_envelope`` (see that function's docstring for the
#: identical rationale: "doubles as a cross-check on the production
#: signing-input formula" rather than importing the private constant).
_SIGNING_DOMAIN = b"balizero.visa-rulepack.v1"

#: Group/other permission bits — a key file's mode must have NONE of these
#: set (0600 or stricter, e.g. 0400).
_KEY_FILE_FORBIDDEN_MODE_BITS = 0o077

#: A PKCS8 Ed25519 PEM private key is ~120 bytes. 1 MiB is wildly generous
#: headroom (encrypted/PKCS12-wrapped variants, comments, stray whitespace)
#: while still bounding the read loop against an attacker who replaces the
#: key path with a very large regular file (PR-A1 codex round-2 finding #2).
_MAX_KEY_FILE_BYTES = 1 << 20

_KID_PATTERN = re.compile(IDENTIFIER_PATTERN)


class SignPackError(RuntimeError):
    """Raised for any refusal to sign. Always caught in ``main`` and
    reported as a clean CLI failure — never a raw traceback."""


def _parse_cli_utc_datetime(value: str) -> datetime:
    if not value.endswith("Z"):
        raise SignPackError(f"--signed-at must end in 'Z' (UTC), got {value!r}")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise SignPackError(f"--signed-at is not a valid UTC date-time: {value!r}") from exc


def _check_permission_mode(mode: int, *, key_file: Path) -> None:
    """Pure check (no filesystem access): refuse a mode with any group/other
    bit set. A key file must be ``chmod 0600`` (owner read/write only) or
    stricter (e.g. ``0400``). Split out from ``_load_private_key`` so the
    bit arithmetic is independently unit-testable without touching a real
    file.
    """

    if mode & _KEY_FILE_FORBIDDEN_MODE_BITS:
        raise SignPackError(
            f"key file {key_file} has mode {oct(mode)} — refusing to sign with a "
            "world/group-accessible private key file. `chmod 0600` it first."
        )


def _load_private_key(key_file: Path) -> Ed25519PrivateKey:
    """Load ``key_file`` as a PKCS8 Ed25519 private key, in-process only.

    TOCTOU-safe (PR-A1 codex correctness review finding #4): the permission check and the
    read both operate on the SAME open file descriptor (``os.open`` once,
    ``os.fstat``/``os.read`` on that fd, ``os.close`` in ``finally``) —
    never re-opening the path by name between the check and the read. A
    ``key_file.stat()`` followed by a SEPARATE ``key_file.read_bytes()``
    (the previous implementation) resolves the path twice; an attacker who
    can swap a symlink at that path between the two calls could make the
    permission check see a world-readable decoy while the actual read
    pulls a different, real, restricted file (or vice versa) — binding
    both operations to one fd removes that window entirely.

    PR-A1 codex ROUND-2 review finding #2 hardening: ``O_NONBLOCK`` on the
    open call means a FIFO/named-pipe path never blocks the whole process
    waiting for a writer that will never come (the subsequent ``S_ISREG``
    check then refuses it cleanly instead of hanging); the same check
    refuses char/block devices and directories; the read loop is capped at
    :data:`_MAX_KEY_FILE_BYTES` so a regular file that has been swapped for
    something enormous cannot exhaust memory.

    Never shells out to an external process; never logs/prints the raw key
    bytes or the parsed key object.
    """

    try:
        fd = os.open(key_file, os.O_RDONLY | os.O_NONBLOCK)
    except OSError as exc:
        raise SignPackError(f"cannot open key file {key_file}: {exc}") from exc

    try:
        try:
            file_stat = os.fstat(fd)
            mode = stat.S_IMODE(file_stat.st_mode)
            _check_permission_mode(mode, key_file=key_file)

            if not stat.S_ISREG(file_stat.st_mode):
                raise SignPackError(
                    f"key file {key_file} is not a regular file "
                    f"(mode {oct(file_stat.st_mode)}) — refusing to read a "
                    "FIFO/device/directory/socket as a private key"
                )

            chunks: list[bytes] = []
            total_bytes = 0
            while True:
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > _MAX_KEY_FILE_BYTES:
                    raise SignPackError(
                        f"key file {key_file} exceeds {_MAX_KEY_FILE_BYTES} bytes "
                        "without terminating — refusing to read further "
                        "(not a plausible PEM private key)"
                    )
                chunks.append(chunk)
            key_bytes = b"".join(chunks)
            chunks.clear()
        except OSError as exc:
            raise SignPackError(f"cannot read key file {key_file}: {exc}") from exc
    finally:
        os.close(fd)

    try:
        private_key = serialization.load_pem_private_key(key_bytes, password=None)
    except (ValueError, TypeError, UnsupportedAlgorithm) as exc:
        raise SignPackError(f"key file {key_file} is not a valid PEM private key: {exc}") from exc
    finally:
        # Best-effort: drop the local reference to the raw PEM bytes as soon
        # as the key object exists. This does not guarantee memory zeroing
        # (Python offers no such guarantee for immutable bytes objects) —
        # it is a defense-in-depth gesture, not a claimed security property.
        del key_bytes

    if not isinstance(private_key, Ed25519PrivateKey):
        raise SignPackError(
            f"key file {key_file} is not an Ed25519 private key (got {type(private_key).__name__})"
        )
    return private_key


def _check_distinct_paths(*, payload_source: Path, key_file: Path, output: Path) -> None:
    """Refuse if ``--output`` would overwrite ``payload_source`` or
    ``--key-file`` (PR-A1 codex correctness review finding #1). Resolves all three paths
    (``strict=False`` — none need to exist yet, ``output`` in particular
    never does) and compares the resolved forms, so a relative path, a
    symlink, or a ``..``-laden path that happens to point at the same file
    as the key still gets caught, not just a literal string match.

    PR-A1 codex ROUND-2 review finding #1: a pure path-STRING comparison
    misses a collision on a case-insensitive filesystem (macOS APFS
    default) — ``/tmp/Key.pem`` and ``/tmp/key.pem`` are textually distinct
    but the SAME inode on disk. If ``output`` already exists as a
    filesystem entry (which it transparently would if it is really the
    same underlying file as ``key_file``/``payload_source`` under a
    different case spelling, or a hardlink), an additional
    ``(st_dev, st_ino)`` comparison catches that; a genuinely new
    ``output`` path, or one that is case-distinct AND inode-distinct, is
    unaffected — this does not fold case unconditionally (which would be
    WRONG on a case-sensitive filesystem, e.g. Linux CI), it only fires
    when the candidate paths provably share one inode.

    Any ``OSError``/``RuntimeError`` raised by path resolution or stat
    (e.g. a symlink loop) is converted to :class:`SignPackError` here so it
    can never surface as a raw traceback in ``main()``.
    """

    try:
        resolved_output = output.resolve()
        resolved_key = key_file.resolve()
        resolved_source = payload_source.resolve()
    except (OSError, RuntimeError) as exc:
        raise SignPackError(
            f"cannot resolve --output/--key-file/payload_source path: {exc}"
        ) from exc

    if resolved_output == resolved_key:
        raise SignPackError(
            f"--output {output} resolves to the same file as --key-file {key_file} — "
            "refusing to overwrite the private key with the signed JSON output"
        )
    if resolved_output == resolved_source:
        raise SignPackError(
            f"--output {output} resolves to the same file as the payload source "
            f"{payload_source} — refusing to overwrite the input with the signed output"
        )

    try:
        output_exists = resolved_output.exists()
    except OSError as exc:
        raise SignPackError(f"cannot stat --output {output}: {exc}") from exc

    if output_exists:
        try:
            output_stat = resolved_output.stat()
        except OSError as exc:
            raise SignPackError(f"cannot stat --output {output}: {exc}") from exc
        for label, path_arg, candidate in (
            ("--key-file", key_file, resolved_key),
            ("the payload source", payload_source, resolved_source),
        ):
            try:
                candidate_stat = candidate.stat()
            except OSError:
                continue  # candidate doesn't exist (yet) — cannot collide by inode
            if (output_stat.st_dev, output_stat.st_ino) == (
                candidate_stat.st_dev,
                candidate_stat.st_ino,
            ):
                raise SignPackError(
                    f"--output {output} is the SAME FILE ON DISK as {label} {path_arg} "
                    "(same device/inode — likely a case-insensitive-filesystem alias or "
                    "hardlink) — refusing to overwrite it"
                )


def _public_key_b64url(private_key: Ed25519PrivateKey) -> str:
    """43-char base64url (no padding) raw Ed25519 public key — the exact
    shape a ``StaticTrustStore`` entry pins. NOT a secret: printing this is
    the whole point of a signing ceremony's output."""

    raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def sign_pack(
    *,
    payload_source: Path,
    kid: str,
    key_file: Path,
    environment: str,
    sequence: int,
    output: Path,
    i_know_this_is_production: bool = False,
    signed_at: datetime | None = None,
) -> tuple[dict, str]:
    """Run the full offline signing ceremony and return
    ``(signed_envelope_dict, public_key_b64url)``.

    Raises ``SignPackError`` on any refusal. Never partially signs, never
    writes ``output`` itself (the caller — ``main`` — owns that write, only
    after this function returns successfully) so a refusal never leaves a
    half-written file behind.

    Order of checks (cheapest / least-sensitive-resource-touching first):
    (1) ``--environment PRODUCTION`` gate, (2) ``--output`` never collides
    with ``--key-file``/``payload_source``, (3) the compile_pack gate
    (re-validates + statically compiles the payload), (4) environment/
    sequence cross-checks against the payload's own fields, (5) ``--kid``
    shape, (6) the private key file (permission check, then load) — the
    sensitive resource is touched last, only once everything else already
    checks out. (7) sign. (8) self-verify via the REAL
    ``bundle.verify_rule_pack`` before ever returning.
    """

    # Strict identity check (PR-A1 codex correctness review finding #3), mirroring bundle.py's
    # own `allow_unsigned is not True` pattern (see that module's
    # `_verify_unsigned_dev` docstring): `i_know_this_is_production` is
    # typed as `bool`, but Python does not enforce that at runtime — a
    # caller passing the non-empty STRING `"false"` is truthy, and
    # `not "false"` is `False`, silently DISABLING this gate. Only the
    # exact value `True` satisfies it.
    if environment == "PRODUCTION" and i_know_this_is_production is not True:
        raise SignPackError(
            "refusing to sign for --environment PRODUCTION without --i-know-this-is-production"
        )

    # PR-A1 codex correctness review finding #1: catch an --output that would clobber the
    # key file or the payload source BEFORE any I/O that could act on it —
    # cheap path-string work, no reason to defer it past the PRODUCTION gate.
    _check_distinct_paths(payload_source=payload_source, key_file=key_file, output=output)

    try:
        payload, report = compile_pack_source(payload_source)
    except OSError as exc:
        raise SignPackError(f"cannot read {payload_source}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SignPackError(f"{payload_source} is not valid JSON: {exc}") from exc
    except ValidationError as exc:
        raise SignPackError(
            f"{payload_source} does not validate as a RulePackPayload:\n{exc}"
        ) from exc

    if not report.ok:
        raise SignPackError(
            "refusing to sign — compile_pack gate failed:\n" + format_report(report)
        )

    if payload.environment.value != environment:
        raise SignPackError(
            f"--environment {environment!r} does not match the payload's own "
            f"environment {payload.environment.value!r} — refusing to sign a pack "
            "for a different environment than the one asserted on the command line"
        )
    if payload.sequence != sequence:
        raise SignPackError(
            f"--sequence {sequence} does not match the payload's own sequence "
            f"{payload.sequence} — refusing to sign; sequence is the anti-rollback "
            "chain's own field, a mismatch here is almost always the wrong file"
        )

    if not _KID_PATTERN.fullmatch(kid):
        raise SignPackError(
            f"--kid {kid!r} does not match the Identifier pattern "
            f"{IDENTIFIER_PATTERN!r} (must start with a letter) — "
            "ProtectedHeader.kid would fail model validation downstream"
        )

    private_key = _load_private_key(key_file)

    signed_at_dt = signed_at or datetime.now(timezone.utc)
    protected: dict = {
        "domain": "balizero.visa-rulepack.v1",
        "alg": "Ed25519",
        "kid": kid,
        "signed_at": utc_isoformat(signed_at_dt),
        "schema_version": "1.0.0",
        "environment": environment,
    }
    payload_dict = payload.model_dump(mode="json", by_alias=True)

    protected_bytes = canonicalize_json(protected)
    payload_bytes = canonicalize_json(payload_dict)
    payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()

    signed_bytes = _SIGNING_DOMAIN + b"\x00" + protected_bytes + b"\x00" + payload_bytes
    signature = private_key.sign(signed_bytes)
    signature_b64url = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")

    envelope: dict = {
        "canonicalization": "RFC8785",
        "protected": protected,
        "payload": payload_dict,
        "payload_sha256": payload_sha256,
        "signature": signature_b64url,
    }

    public_key_b64url = _public_key_b64url(private_key)

    # Self-verify before ever returning: run the ACTUAL production verifier
    # (bundle.verify_rule_pack) against this exact envelope, pinned with the
    # public key just derived from `private_key` — never trust this
    # function's own re-derivation of the signing formula alone. A bug in
    # the re-derivation above (a byte out of place, a wrong separator) would
    # otherwise ship a self-inconsistent "signed" bundle that only fails
    # much later, in production, at verify time.
    #
    # `observed_at` (PR-A1 codex correctness review finding #2) is the REAL wall-clock time,
    # never `signed_at_dt` — passing `signed_at_dt` back as its own
    # `observed_at` makes the skew always exactly zero by construction,
    # which trivially defeats `verify_rule_pack`'s future-skew guard for
    # EVERY signature, including a badly wrong `--signed-at` (e.g. a
    # typo'd year far in the future). Reproduced: a `--signed-at` of
    # 2035-01-01 self-verified "successfully" under the old code, then was
    # rejected by any real downstream `verify_rule_pack(..., observed_at=
    # <actual now>)` call as future-dated — the self-verify step's entire
    # purpose (catch a problem HERE, not downstream) failed on exactly the
    # class of mistake it exists to catch. Using real "now" costs nothing
    # for the common case (a `--signed-at` at or before the real present
    # always has non-positive skew, which the guard always accepts).
    trust_store = StaticTrustStore(
        [
            TrustedSigningKey(
                key_id=kid,
                public_key=private_key.public_key(),
                valid_from=signed_at_dt,
                valid_to=None,
                revoked_at=None,
                environment=environment,
            )
        ]
    )
    try:
        bundle_verify_rule_pack(
            envelope, trust_store=trust_store, observed_at=datetime.now(timezone.utc)
        )
    except RulePackVerificationError as exc:
        raise SignPackError(
            "refusing to write a freshly-signed envelope that fails self-verification "
            f"via bundle.verify_rule_pack — check --signed-at is not implausibly far in "
            f"the future: {exc}"
        ) from exc

    return envelope, public_key_b64url


def _write_output_atomic(output: Path, content: str) -> None:
    """Write ``content`` to ``output`` atomically: write to a sibling temp
    file in the same directory, then ``os.replace`` it into place (PR-A1
    codex correctness review finding #1's second half — "the write is not
    atomic"). A crash
    or interruption mid-write can therefore never leave ``output`` holding
    a truncated/partial JSON document — the old file (if any) stays intact
    until the instant the fully-written replacement is renamed in.

    Raises ``OSError`` on any I/O failure (unwritable directory, disk full,
    ...); ``main`` wraps the call site so this never surfaces as a raw
    traceback.
    """

    fd, tmp_name = tempfile.mkstemp(
        dir=str(output.parent), prefix=f".{output.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp_name, output)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sign_pack",
        description=(
            "OFFLINE-ONLY: sign a validated RulePack payload with a real "
            "Ed25519 private key. Never runs inside the FastAPI process — "
            "operator ceremony only."
        ),
    )
    parser.add_argument(
        "payload_source", type=Path, help="path to a validated RulePackPayload JSON document"
    )
    parser.add_argument(
        "--kid", required=True, help="key id to embed in the protected header (Identifier pattern)"
    )
    parser.add_argument(
        "--key-file",
        required=True,
        type=Path,
        help="path to a PKCS8 Ed25519 PEM private key (must be chmod 0600 or stricter)",
    )
    parser.add_argument(
        "--environment",
        required=True,
        choices=[e.value for e in Environment],
        help="must match the payload's own `environment` field exactly",
    )
    parser.add_argument(
        "--sequence",
        required=True,
        type=int,
        help="must match the payload's own `sequence` field exactly",
    )
    parser.add_argument(
        "--output", required=True, type=Path, help="where to write the signed bundle JSON"
    )
    parser.add_argument(
        "--i-know-this-is-production",
        action="store_true",
        default=False,
        help="required to sign for --environment PRODUCTION",
    )
    parser.add_argument(
        "--signed-at",
        default=None,
        help="ISO-8601 UTC override for protected.signed_at (must end in 'Z'); default now",
    )
    args = parser.parse_args(argv)

    try:
        signed_at = _parse_cli_utc_datetime(args.signed_at) if args.signed_at else None
        envelope, public_key_b64url = sign_pack(
            payload_source=args.payload_source,
            kid=args.kid,
            key_file=args.key_file,
            environment=args.environment,
            sequence=args.sequence,
            output=args.output,
            i_know_this_is_production=args.i_know_this_is_production,
            signed_at=signed_at,
        )
    except SignPackError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    try:
        _write_output_atomic(args.output, json.dumps(envelope, indent=2, sort_keys=True) + "\n")
    except OSError as exc:
        # PR-A1 codex correctness review finding #5: this write must never surface as a raw
        # traceback either — same "never a raw traceback" contract as every
        # other I/O boundary in this script.
        print(f"FAIL: could not write {args.output}: {exc}", file=sys.stderr)
        return 1

    print(
        "OK — signed and self-verified.\n"
        f"  rule_pack_id={envelope['payload']['rule_pack_id']}\n"
        f"  sequence={envelope['payload']['sequence']}\n"
        f"  environment={envelope['payload']['environment']}\n"
        f"  kid={args.kid}\n"
        f"  payload_sha256={envelope['payload_sha256']}\n"
        f"  public_key (base64url, safe to pin in a trust store)={public_key_b64url}\n"
        f"  output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
