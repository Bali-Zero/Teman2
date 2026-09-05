"""Replay the 20 canonical Visa Oracle gold personas against a real RulePack.

This is the missing G-b evidence driver.  Unlike the older fixture replay in
``backend.tests.services.visa_engine.gold_replay``, both modes exercise policy
that can be compared with production:

* ``--live`` posts every canonical persona to the public evaluate endpoint as
  ``traffic_source=synthetic_gold``.  The driver token is read only from the
  operator-owned token file; it has no CLI option and is never logged.
* ``--offline`` verifies, compiles, and evaluates the highest-sequence signed
  PRODUCTION pack actually present in ``contracts/packs``.  It then calls the
  same deterministic, no-I/O policy adapter helper as the public evaluate path.
  This proves only what that repository artifact and those checked-out policy
  adapters do; it never claims that the artifact is the active production pack.
  Offline mode runs inside the repository's backend environment and therefore
  requires the serving stack's lock-pinned dependencies; it is not a standalone
  stdlib utility.

The JSON report keeps every divergence visible.  By default every divergent
persona has ``"explanation": null`` and therefore makes the command exit 1.
After an independent reviewer fills those fields in a saved report, pass that
report back with ``--accepted-explanations``.  Explained divergences remain
catalogued as divergences, but no longer count as *unexplained* for G-b's exit
criterion.

Usage::

    cd apps/backend-rag && source .venv/bin/activate
    PYTHONPATH=. python -m backend.scripts.visa_engine.gold_replay_driver \
      --offline --out /tmp/visa-gold-replay-offline.json

    PYTHONPATH=. python -m backend.scripts.visa_engine.gold_replay_driver \
      --live --out /tmp/visa-gold-replay-live.json
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import ValidationError

from backend.scripts.visa_engine.activate_pack import _load_strict_json
from backend.services.visa_engine import evaluate_path, evaluator
from backend.services.visa_engine.api_models import VisaOracleEvaluateRequest
from backend.services.visa_engine.bundle import (
    StaticTrustStore,
    TrustedSigningKey,
    verify_rule_pack,
)
from backend.services.visa_engine.compiler import build_compiled_pack
from backend.services.visa_engine.enums import Environment
from backend.services.visa_engine.evaluator import DecisionIdentity, build_decision_identity
from backend.services.visa_engine.models import (
    ApplicantFacts,
    Decision,
    RulePackRef,
)
from backend.tests.services.visa_engine import _gold_fixtures as gf
from backend.tests.services.visa_engine.gold_replay import (
    _decision_actual,
    _persona_assessment_id,
    _persona_divergences,
    _persona_expected,
)
from backend.tests.services.visa_engine.test_evaluator_gold import PERSONAS, Persona

logger = logging.getLogger("visa_engine.gold_replay_driver")

LIVE_ENDPOINT = "https://nuzantara-rag.fly.dev/api/visa-oracle/evaluate"
DRIVER_TOKEN_PATH = Path.home() / ".config/nuzantara/visa-signing/driver-token"
PACKS_DIR = Path(__file__).resolve().parents[2] / "services/visa_engine/contracts/packs"
REPORT_SCHEMA_VERSION = "1.0.0"

# Public verification key from the reviewed key-ceremony record.  This is a
# trust root, not a secret.  Keeping the public key here makes offline replay
# self-contained on a clean checkout and avoids the much worse requirement of
# access to the production private signing key.  A future signing-key rotation
# must add its reviewed public key before a pack bearing the new kid can replay.
_REPOSITORY_PRODUCTION_SIGNING_KEYS: tuple[dict[str, str | None], ...] = (
    {
        "kid": "prod-2026-07-1",
        "public_key": "gZoo1nzMsRpwWgw4HCzV_2YYxU0Vbt5FMfLWeOzAchA",  # pragma: allowlist secret - pinned Ed25519 public verification key, not a credential
        "environment": "PRODUCTION",
        "valid_from": "2026-07-19T00:00:00Z",
        "valid_to": None,
        "revoked_at": None,
    },
)


class GoldReplayDriverError(RuntimeError):
    """Operational failure that prevents a complete, trustworthy report."""


@dataclass(frozen=True)
class AcceptedExplanation:
    """A reviewed explanation bound to the exact divergence it accepted."""

    explanation: str
    expected: Mapping[str, Any]
    actual: Mapping[str, Any]
    pack: Mapping[str, Any]
    differences: Sequence[Mapping[str, Any]]


def _offline_identity_provider(
    facts: ApplicantFacts,
    rule_pack_ref: RulePackRef,
    effective_at: datetime,
    _environment: Environment,
) -> DecisionIdentity:
    """Build deterministic offline-only identities for a PRODUCTION pack.

    The evaluator correctly refuses its TEST placeholder for a PRODUCTION
    RulePack.  This explicitly injected provider uses a named non-secret key
    solely to let the pure local evaluator construct its required Decision
    identity.  Identity/fingerprint values are intentionally omitted from the
    report and must never be represented as production integrity evidence.
    """

    return build_decision_identity(
        facts,
        rule_pack_ref,
        effective_at,
        fingerprint_key=b"visa-gold-replay-offline-non-secret-v1",
        fingerprint_key_id="gold-replay-offline-non-secret-v1",
    )


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError(f"timestamp must be timezone-aware UTC: {value!r}")
    return parsed


def _decode_public_key(value: str) -> Ed25519PublicKey:
    raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    if len(raw) != 32:
        raise GoldReplayDriverError("repository trust key is not a 32-byte Ed25519 key")
    return Ed25519PublicKey.from_public_bytes(raw)


def _repository_trust_store() -> StaticTrustStore:
    keys = []
    for entry in _REPOSITORY_PRODUCTION_SIGNING_KEYS:
        valid_to = entry["valid_to"]
        revoked_at = entry["revoked_at"]
        keys.append(
            TrustedSigningKey(
                key_id=str(entry["kid"]),
                public_key=_decode_public_key(str(entry["public_key"])),
                valid_from=_parse_utc(str(entry["valid_from"])),
                valid_to=None if valid_to is None else _parse_utc(valid_to),
                revoked_at=None if revoked_at is None else _parse_utc(revoked_at),
                environment=str(entry["environment"]),
            )
        )
    return StaticTrustStore(keys)


def build_persona_request(persona: Persona) -> VisaOracleEvaluateRequest:
    """Map one canonical persona to the exact public request model.

    The baseline and overrides remain owned by ``_gold_fixtures``.  Dumping
    and re-validating through ``VisaOracleEvaluateRequest`` is deliberate: it
    proves that every dotted alias, enum, and required fact accepted by the
    pure evaluator is also valid on the real HTTP boundary.
    """

    applicant = gf.applicant_facts(
        assessment_id=_persona_assessment_id(persona.id),
        overrides=persona.overrides,
    )
    return VisaOracleEvaluateRequest.model_validate(
        applicant.model_dump(mode="json", by_alias=True)
    )


def build_persona_payload(persona: Persona) -> dict[str, Any]:
    """Return the JSON-safe, dotted-alias wire payload for one persona."""

    return build_persona_request(persona).model_dump(mode="json", by_alias=True)


def _read_driver_token(path: Path = DRIVER_TOKEN_PATH) -> str:
    try:
        token = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise GoldReplayDriverError(f"could not read driver token file {path}") from exc
    if not token:
        raise GoldReplayDriverError(f"driver token file is empty: {path}")
    return token


def _parse_live_decision(response: httpx.Response, *, persona_id: int) -> Decision:
    if response.status_code != 200:
        raise GoldReplayDriverError(
            f"live endpoint returned HTTP {response.status_code} for persona {persona_id:02d}"
        )
    try:
        body = response.json()
    except json.JSONDecodeError as exc:
        raise GoldReplayDriverError(
            f"live endpoint returned non-JSON for persona {persona_id:02d}"
        ) from exc
    if not isinstance(body, Mapping) or "decision" not in body:
        raise GoldReplayDriverError(f"live endpoint omitted decision for persona {persona_id:02d}")
    try:
        return Decision.model_validate(body["decision"])
    except ValidationError as exc:
        raise GoldReplayDriverError(
            f"live endpoint returned an invalid decision for persona {persona_id:02d}"
        ) from exc


async def replay_live_decisions(
    client: httpx.AsyncClient,
    *,
    token_path: Path = DRIVER_TOKEN_PATH,
) -> tuple[Decision, ...]:
    """POST all personas sequentially and return endpoint decisions.

    Sequential requests stay below the endpoint's dedicated 30/minute rate
    limit without introducing retries that could create misleading duplicate
    evidence rows after an ambiguous transport failure.
    """

    token = _read_driver_token(token_path)
    decisions: list[Decision] = []
    for persona in PERSONAS:
        response = await client.post(
            LIVE_ENDPOINT,
            params={"traffic_source": "synthetic_gold"},
            headers={"X-Visa-Driver-Token": token},
            json=build_persona_payload(persona),
        )
        decision = _parse_live_decision(response, persona_id=persona.id)
        decisions.append(decision)
        logger.info(
            "live replay persona=%02d state=%s candidates=%d",
            persona.id,
            decision.state.value,
            len(decision.candidates),
        )
    return tuple(decisions)


def _signed_production_sequence(path: Path) -> tuple[int, dict[str, Any]] | None:
    raw = _load_strict_json(path)
    payload = raw.get("payload")
    if not isinstance(payload, Mapping):
        raise GoldReplayDriverError(f"signed pack has no payload object: {path}")
    if payload.get("environment") != "PRODUCTION":
        return None
    sequence = payload.get("sequence")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
        raise GoldReplayDriverError(f"signed PRODUCTION pack has invalid sequence: {path}")
    return sequence, raw


def select_highest_repository_pack(
    packs_dir: Path = PACKS_DIR,
) -> tuple[Path, dict[str, Any]]:
    """Select the unique highest-sequence signed PRODUCTION pack on disk."""

    candidates: list[tuple[int, Path, dict[str, Any]]] = []
    for path in sorted(packs_dir.glob("*.signed.json")):
        selected = _signed_production_sequence(path)
        if selected is not None:
            sequence, raw = selected
            candidates.append((sequence, path, raw))
    if not candidates:
        raise GoldReplayDriverError(f"no signed PRODUCTION packs found in {packs_dir}")

    highest_sequence = max(sequence for sequence, _, _ in candidates)
    highest = [candidate for candidate in candidates if candidate[0] == highest_sequence]
    if len(highest) != 1:
        paths = ", ".join(str(path) for _, path, _ in highest)
        raise GoldReplayDriverError(
            f"multiple signed PRODUCTION packs carry highest sequence {highest_sequence}: {paths}"
        )
    _, path, raw = highest[0]
    return path, raw


def replay_offline_decisions(
    *,
    evaluated_at: datetime,
    packs_dir: Path = PACKS_DIR,
) -> tuple[tuple[Decision, ...], Path]:
    """Verify, compile, and replay the highest repository pack locally."""

    pack_path, raw_pack = select_highest_repository_pack(packs_dir)
    verified = verify_rule_pack(
        raw_pack,
        trust_store=_repository_trust_store(),
        observed_at=evaluated_at,
    )
    compiled = build_compiled_pack(verified.pack)

    decisions: list[Decision] = []
    for persona in PERSONAS:
        request = build_persona_request(persona)
        facts = request.applicant_facts()
        decision = evaluator.evaluate(
            facts,
            compiled,
            effective_at=evaluated_at,
            observed_at=evaluated_at,
            identity_provider=_offline_identity_provider,
        )
        decisions.append(
            evaluate_path.apply_public_policy_adapters(
                decision,
                facts,
                compiled,
                disclosed_review_flags=request.effective_review_flags(),
            )
        )
    logger.info(
        "offline replay used repository signed pack file=%s sequence=%d version=%s; "
        "active production status was not checked",
        pack_path.name,
        compiled.sequence,
        compiled.version,
    )
    return tuple(decisions), pack_path


def _normalized_expected(persona: Persona) -> dict[str, Any]:
    expected = _persona_expected(persona)
    return {
        "state": expected["state"],
        "candidate_products": expected["candidates"],
        "missing_facts": expected["missing_facts"],
        "review_reason_codes": expected["review_reason_codes"],
        "no_path_reason_codes": expected["no_path_reason_codes"],
        "notice_codes": expected["notice_codes"],
    }


def _normalized_actual(decision: Decision) -> dict[str, Any]:
    actual = _decision_actual(decision)
    return {
        "state": actual["state"],
        "candidate_products": actual["candidates"],
        "missing_facts": actual["missing_facts"],
        "review_reason_codes": actual["review_reason_codes"],
        "no_path_reason_codes": actual["no_path_reason_codes"],
        "notice_codes": actual["notice_codes"],
    }


def _decision_pack(decision: Decision) -> dict[str, Any]:
    if decision.rule_pack is None:
        return {
            "rule_pack_id": None,
            "sequence": None,
            "version": None,
            "payload_sha256": None,
        }
    return {
        "rule_pack_id": str(decision.rule_pack.rule_pack_id),
        "sequence": decision.rule_pack.sequence,
        "version": decision.rule_pack.version,
        "payload_sha256": decision.rule_pack.payload_sha256,
    }


def _unique_packs(decisions: Sequence[Decision]) -> list[dict[str, Any]]:
    observed: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for decision in decisions:
        pack = _decision_pack(decision)
        identity = tuple(pack.values())
        if identity not in seen:
            seen.add(identity)
            observed.append(pack)
    return observed


def _load_accepted_explanations(path: Path | None) -> dict[int, AcceptedExplanation]:
    """Read accepted explanations from a previously generated report.

    Supplying this file is the operator's assertion that its non-empty
    explanation strings were independently reviewed and accepted.  The
    function imports only those strings; it never trusts old outcomes or old
    divergence flags from the file.
    """

    if path is None:
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GoldReplayDriverError(f"could not read accepted explanations from {path}") from exc
    if not isinstance(raw, Mapping) or not isinstance(raw.get("personas"), list):
        raise GoldReplayDriverError("accepted explanations file must be a replay report")

    explanations: dict[int, AcceptedExplanation] = {}
    for entry in raw["personas"]:
        if not isinstance(entry, Mapping):
            raise GoldReplayDriverError("accepted explanations report has an invalid persona row")
        persona_id = entry.get("persona_id")
        explanation = entry.get("explanation")
        if explanation is None:
            continue
        expected = entry.get("expected")
        actual = entry.get("actual")
        pack = entry.get("pack")
        differences = entry.get("differences")
        if (
            isinstance(persona_id, bool)
            or not isinstance(persona_id, int)
            or not isinstance(explanation, str)
            or not explanation.strip()
            or not isinstance(expected, Mapping)
            or not isinstance(actual, Mapping)
            or not isinstance(pack, Mapping)
            or not isinstance(differences, list)
            or not all(isinstance(item, Mapping) for item in differences)
        ):
            raise GoldReplayDriverError(
                "accepted explanations must preserve the complete generated persona row"
            )
        explanations[persona_id] = AcceptedExplanation(
            explanation=explanation,
            expected=expected,
            actual=actual,
            pack=pack,
            differences=differences,
        )
    return explanations


def _matching_explanation(
    accepted: Mapping[int, AcceptedExplanation],
    *,
    persona_id: int,
    expected: Mapping[str, Any],
    actual: Mapping[str, Any],
    pack: Mapping[str, Any],
    differences: Sequence[Mapping[str, Any]],
) -> str | None:
    candidate = accepted.get(persona_id)
    if candidate is None:
        return None
    if (
        candidate.expected != expected
        or candidate.actual != actual
        or candidate.pack != pack
        or candidate.differences != differences
    ):
        return None
    return candidate.explanation


def build_report(
    *,
    mode: str,
    generated_at: datetime,
    decisions: Sequence[Decision],
    pack_source: Mapping[str, Any],
    explanations: Mapping[int, AcceptedExplanation] | None = None,
) -> dict[str, Any]:
    """Build the machine-readable G-b report from fresh decisions."""

    if mode not in {"live", "offline"}:
        raise ValueError("mode must be 'live' or 'offline'")
    if len(decisions) != len(PERSONAS):
        raise ValueError(f"expected {len(PERSONAS)} decisions, got {len(decisions)}")

    accepted = explanations or {}
    persona_reports: list[dict[str, Any]] = []
    for persona, decision in zip(PERSONAS, decisions, strict=True):
        expected = _normalized_expected(persona)
        actual = _normalized_actual(decision)
        differences = _persona_divergences(persona.id, expected, actual)
        pack = _decision_pack(decision)
        explanation = (
            _matching_explanation(
                accepted,
                persona_id=persona.id,
                expected=expected,
                actual=actual,
                pack=pack,
                differences=differences,
            )
            if differences
            else None
        )
        persona_reports.append(
            {
                "persona_id": persona.id,
                "label": persona.label,
                "expected": expected,
                "actual": actual,
                "pack": pack,
                "divergence": bool(differences),
                "differences": differences,
                "explanation": explanation,
            }
        )

    divergence_rows = [row for row in persona_reports if row["divergence"]]
    unexplained_rows = [
        row
        for row in divergence_rows
        if not isinstance(row["explanation"], str) or not row["explanation"].strip()
    ]
    packs_observed = _unique_packs(decisions)
    if len(packs_observed) == 1:
        common_pack = {**packs_observed[0], "consistent_across_personas": True}
    else:
        common_pack = {
            "rule_pack_id": None,
            "sequence": None,
            "version": None,
            "payload_sha256": None,
            "consistent_across_personas": False,
        }

    return {
        "gate": "G-b",
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": generated_at.isoformat(),
        "mode": mode,
        "pack_source": dict(pack_source),
        "pack": common_pack,
        "packs_observed": packs_observed,
        "persona_count": len(persona_reports),
        "personas": persona_reports,
        "summary": {
            "personas_total": len(persona_reports),
            "personas_match": len(persona_reports) - len(divergence_rows),
            "personas_with_divergence": len(divergence_rows),
            "explained_divergences": len(divergence_rows) - len(unexplained_rows),
            "unexplained_divergences": len(unexplained_rows),
        },
        "overall_pass": not unexplained_rows,
    }


def exit_code_for_report(report: Mapping[str, Any]) -> int:
    """Return 0 exactly when the report has zero unexplained divergences."""

    summary = report.get("summary")
    if not isinstance(summary, Mapping):
        raise ValueError("report has no summary object")
    unexplained = summary.get("unexplained_divergences")
    if isinstance(unexplained, bool) or not isinstance(unexplained, int) or unexplained < 0:
        raise ValueError("report has invalid unexplained_divergences")
    return 0 if unexplained == 0 else 1


def _relative_pack_path(path: Path) -> str:
    backend_root = Path(__file__).resolve().parents[2]
    try:
        return str(path.resolve().relative_to(backend_root))
    except ValueError:
        return str(path)


async def build_live_report(
    client: httpx.AsyncClient,
    *,
    generated_at: datetime,
    token_path: Path = DRIVER_TOKEN_PATH,
    explanations: Mapping[int, AcceptedExplanation] | None = None,
) -> dict[str, Any]:
    decisions = await replay_live_decisions(client, token_path=token_path)
    return build_report(
        mode="live",
        generated_at=generated_at,
        decisions=decisions,
        pack_source={
            "kind": "live_endpoint",
            "endpoint": LIVE_ENDPOINT,
            "pack_metadata_source": "each endpoint response decision.rule_pack",
        },
        explanations=explanations,
    )


def build_offline_report(
    *,
    generated_at: datetime,
    packs_dir: Path = PACKS_DIR,
    explanations: Mapping[int, AcceptedExplanation] | None = None,
) -> dict[str, Any]:
    decisions, pack_path = replay_offline_decisions(
        evaluated_at=generated_at,
        packs_dir=packs_dir,
    )
    return build_report(
        mode="offline",
        generated_at=generated_at,
        decisions=decisions,
        pack_source={
            "kind": "repository_signed_pack",
            "selection": "highest signed PRODUCTION sequence present in repository",
            "file": _relative_pack_path(pack_path),
            "production_activation_status": (
                "not checked; offline replay does not claim this pack is active in production"
            ),
            "pack_metadata_source": "local evaluator decision.rule_pack",
            "decision_identity": (
                "offline-only non-secret provider; not production integrity evidence"
            ),
            "policy_adapters": list(evaluate_path.PUBLIC_POLICY_ADAPTER_NAMES),
            "runtime_operations_excluded": [
                "active_database_binding",
                "retention_gate",
                "pricing",
                "sealing",
                "persistence",
            ],
        },
        explanations=explanations,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true", help="POST all personas to production")
    mode.add_argument(
        "--offline",
        action="store_true",
        help="replay the highest signed PRODUCTION pack present in contracts/packs",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="report JSON path (default: stdout)",
    )
    parser.add_argument(
        "--accepted-explanations",
        type=Path,
        default=None,
        metavar="REPORT_JSON",
        help=(
            "previous replay report whose non-null persona explanation fields "
            "were independently accepted"
        ),
    )
    return parser


def _write_report(report: Mapping[str, Any], path: Path | None) -> None:
    artifact = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if path is None:
        sys.stdout.write(artifact)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(artifact, encoding="utf-8")
    logger.info(
        "wrote replay report path=%s matches=%d/%d unexplained_divergences=%d",
        path,
        report["summary"]["personas_match"],
        report["summary"]["personas_total"],
        report["summary"]["unexplained_divergences"],
    )


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc)
    explanations = _load_accepted_explanations(args.accepted_explanations)
    if args.live:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
            return await build_live_report(
                client,
                generated_at=generated_at,
                explanations=explanations,
            )
    return build_offline_report(
        generated_at=generated_at,
        explanations=explanations,
    )


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = _parser().parse_args(argv)
    try:
        report = asyncio.run(_run(args))
        _write_report(report, args.out)
    except Exception as exc:
        # Exception text from the live HTTP stack is intentionally excluded:
        # future client/library versions must not be able to render headers
        # (and therefore the driver token) into this operational log line.
        logger.error("gold replay failed: %s", type(exc).__name__)
        return 2
    return exit_code_for_report(report)


if __name__ == "__main__":
    raise SystemExit(main())
