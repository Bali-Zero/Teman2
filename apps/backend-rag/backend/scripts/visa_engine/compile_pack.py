"""Offline CLI: validate and statically compile a RulePack payload source.

Spec §1 module layout (``research/visa/2026-07-17-visa-oracle-v2-round2-
codex-engine-concretization.md``): ``scripts/visa_engine/compile_pack.py``.

Authoring workflow: a rule-pack author writes a plain JSON document that is
exactly a ``models.RulePackPayload`` (the unsigned legal content — products,
rules, source records; no ``protected``/``signature``/``payload_sha256``
envelope). This script:

1. Parses that JSON and validates it against the REAL ``RulePackPayload``
   Pydantic model (``load_rule_pack_payload``) — the same model
   ``bundle.verify_rule_pack`` builds after a signature verifies, so a
   payload that validates here is guaranteed to be structurally acceptable
   downstream too.
2. Wraps it in a throwaway placeholder envelope (``wrap_as_unsigned_pack``)
   purely so ``compiler.compile_rule_pack`` — which takes a full
   ``RulePack``, not a bare payload — has the shape it expects. This is NOT
   a trust claim of any kind: the placeholder ``kid``/``signature`` are
   fixed sentinel strings, never real key material, and this script never
   calls ``bundle.verify_rule_pack`` (which is the only place a signature is
   ever actually checked).
3. Runs every static validation pass (``compile_rule_pack``) and prints the
   resulting ``CompilationReport``.

Exit code is 0 only when the report is clean (``report.ok``); non-zero
otherwise (1 for a compilation defect, 1 for a file/JSON/schema read
failure). This script never signs anything and never touches a private key
— see ``sign_pack.py``, which imports and re-runs ``compile_pack_source``
from this module as its own mandatory pre-sign gate.

Usage::

    PYTHONPATH=. python -m backend.scripts.visa_engine.compile_pack \\
        backend/services/visa_engine/contracts/packs/rulepack-test-c1-tourism.source.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from backend.services.visa_engine.bundle import canonicalize_json
from backend.services.visa_engine.compiler import CompilationReport, compile_rule_pack
from backend.services.visa_engine.models import ProtectedHeader, RulePack, RulePackPayload

#: Placeholder kid/signature used ONLY to give ``compile_rule_pack`` a
#: well-typed ``RulePack`` envelope to run its checks against. Never a real
#: signature and never written anywhere as if it were one — ``sign_pack.py``
#: is the sole place a REAL signature is ever produced, offline, with an
#: operator-supplied Ed25519 key. ``compile_rule_pack`` itself never
#: inspects the signature at all (that is exclusively ``bundle.py``'s job),
#: so this placeholder can never be mistaken for a verified pack by any
#: downstream consumer that actually checks trust.
_PLACEHOLDER_KID = "compile-pack-unsigned-scaffold"
_PLACEHOLDER_SIGNATURE = "0" * 86


def load_rule_pack_payload(path: Path) -> RulePackPayload:
    """Parse ``path`` as JSON and validate it against the real
    ``RulePackPayload`` Pydantic model.

    Raises ``OSError`` (unreadable file), ``json.JSONDecodeError`` (not
    valid JSON), or ``pydantic.ValidationError`` (valid JSON, wrong shape)
    on failure — callers that want a clean CLI message catch these
    themselves (see ``main`` and ``sign_pack.sign_pack``).
    """

    raw = json.loads(path.read_text(encoding="utf-8"))
    return RulePackPayload.model_validate(raw)


def wrap_as_unsigned_pack(
    payload: RulePackPayload, *, observed_at: datetime | None = None
) -> RulePack:
    """Wrap ``payload`` in a throwaway envelope so ``compile_rule_pack``
    (which takes a full ``RulePack``, not a bare payload) has something to
    check.

    NOT a trust claim: ``protected.kid``/``signature`` are fixed placeholder
    values (see module constants above), never real key material. The
    ONLY consequential field is ``protected.environment``, set equal to
    ``payload.environment`` — matching ``RulePack``'s own
    ``_check_header_environment`` model validator, which every real signed
    envelope must also satisfy. ``payload_sha256`` is computed for real
    (``SHA256(JCS(payload))``, same formula as ``bundle.py``'s trust
    boundary) purely so the wrapped envelope is internally self-consistent
    — nothing here is ever checked against a public key.
    """

    observed = observed_at or datetime.now(timezone.utc)
    protected = ProtectedHeader(
        domain="balizero.visa-rulepack.v1",
        alg="Ed25519",
        kid=_PLACEHOLDER_KID,
        signed_at=observed,
        schema_version="1.0.0",
        environment=payload.environment,
    )
    payload_bytes = canonicalize_json(payload.model_dump(mode="json", by_alias=True))
    payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()
    return RulePack(
        canonicalization="RFC8785",
        protected=protected,
        payload=payload,
        payload_sha256=payload_sha256,
        signature=_PLACEHOLDER_SIGNATURE,
    )


def compile_pack_source(
    path: Path, *, observed_at: datetime | None = None
) -> tuple[RulePackPayload, CompilationReport]:
    """Load, validate, wrap, and compile ``path`` in one call.

    This is the exact gate ``sign_pack.py`` re-runs, every invocation,
    before it will ever touch a private key — "refuses to sign if
    compile_pack gate fails" per the PR-A1 task brief. Propagates
    ``load_rule_pack_payload``'s exceptions unwrapped; ``compile_rule_pack``
    itself never raises for an ordinary pack defect (it reports every defect
    in the returned ``CompilationReport`` instead).
    """

    payload = load_rule_pack_payload(path)
    pack = wrap_as_unsigned_pack(payload, observed_at=observed_at)
    report = compile_rule_pack(pack)
    return payload, report


def format_report(report: CompilationReport) -> str:
    """Human-readable rendering of a ``CompilationReport`` for CLI output."""

    lines = [f"rule_pack_id={report.rule_pack_id} sequence={report.sequence}"]
    if report.ok:
        lines.append("OK — zero compilation errors")
        return "\n".join(lines)
    lines.append(f"{len(report.errors)} compilation error(s):")
    for error in report.errors:
        locus = ""
        if error.rule_id is not None:
            locus = f" rule_id={error.rule_id}"
        elif error.product_code is not None:
            locus = f" product_code={error.product_code}"
        lines.append(f"  [{error.code}]{locus} {error.message}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="compile_pack",
        description=(
            "Validate and statically compile a RulePack payload source file "
            "(a bare, unsigned models.RulePackPayload JSON document). Exit "
            "0 only when compile_rule_pack reports zero errors. Never signs "
            "anything, never touches a private key."
        ),
    )
    parser.add_argument(
        "pack_source",
        type=Path,
        help="path to a JSON document containing a RulePackPayload (unsigned)",
    )
    args = parser.parse_args(argv)

    try:
        payload = load_rule_pack_payload(args.pack_source)
    except OSError as exc:
        print(f"FAIL: could not read {args.pack_source}: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"FAIL: {args.pack_source} is not valid JSON: {exc}", file=sys.stderr)
        return 1
    except ValidationError as exc:
        print(
            f"FAIL: {args.pack_source} does not validate as a RulePackPayload:\n{exc}",
            file=sys.stderr,
        )
        return 1

    pack = wrap_as_unsigned_pack(payload)
    report = compile_rule_pack(pack)
    print(format_report(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
