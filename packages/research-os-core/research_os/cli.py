"""Machine-readable validator CLI for the foundation contracts."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NoReturn

from pydantic import BaseModel, ValidationError

from research_os.hashing import HASH_OMISSION_FIELDS, object_hash
from research_os.models.conductor_handoff import ConductorHandoff
from research_os.models.outcome_event import OutcomeEvent
from research_os.models.revocation_receipt import RevocationReceipt
from research_os.models.successor_edge import ObjectSuccessorEdge
from research_os.models.verification_receipt import VerificationReceipt
from research_os.models.workflow_run import WorkflowRun
from research_os.version import check_compatibility

LOGGER = logging.getLogger(__name__)
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_ROOT = PACKAGE_ROOT / "fixtures"
CONTRACT_MODELS: dict[str, type[BaseModel]] = {
    "conductor_handoff": ConductorHandoff,
    "object_successor_edge": ObjectSuccessorEdge,
    "outcome_event": OutcomeEvent,
    "revocation_receipt": RevocationReceipt,
    "verification_receipt": VerificationReceipt,
    "workflow_run": WorkflowRun,
}


class JsonArgumentParser(argparse.ArgumentParser):
    """Argparse variant that preserves exit 2 while emitting JSON stdout."""

    def error(self, message: str) -> NoReturn:
        _emit({"valid": False, "error": "usage_error", "detail": message})
        raise SystemExit(2)


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _validation_errors(exc: ValidationError) -> list[dict[str, Any]]:
    return [
        {
            "location": [str(part) for part in error["loc"]],
            "message": error["msg"],
            "reason_code": str(error["type"]),
        }
        for error in exc.errors()
    ]


def _validate(contract_kind: str, path: Path) -> int:
    model = CONTRACT_MODELS[contract_kind]
    try:
        model.model_validate(_read_json(path))
    except ValidationError as exc:
        _emit(
            {
                "contract": contract_kind,
                "file": str(path),
                "valid": False,
                "errors": _validation_errors(exc),
            }
        )
        return 1
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.warning("cannot read validation input %s: %s", path, exc)
        _emit(
            {"contract": contract_kind, "file": str(path), "valid": False, "error": "invalid_json"}
        )
        return 1
    _emit({"contract": contract_kind, "file": str(path), "valid": True})
    return 0


def _hash(path: Path) -> int:
    try:
        payload = _read_json(path)
        if not isinstance(payload, dict):
            raise ValueError("hash input must be a JSON object")
        version = payload.get("contract_version")
        if not isinstance(version, str) or version not in HASH_OMISSION_FIELDS:
            raise ValueError("unsupported or missing contract_version")
        digest = object_hash(payload)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        LOGGER.warning("cannot hash %s: %s", path, exc)
        _emit({"file": str(path), "valid": False, "error": "hash_failed", "detail": str(exc)})
        return 1
    _emit({"file": str(path), "object_hash": digest, "valid": True})
    return 0


def _fixture_paths(contract_kind: str, prefix: str) -> tuple[Path, ...]:
    return tuple(
        sorted(
            path
            for path in (FIXTURES_ROOT / contract_kind).glob(f"{prefix}_*.json")
            if not path.name.endswith(".expect.json")
        )
    )


def _check_fixtures() -> int:
    failures: list[dict[str, Any]] = []
    checked = 0
    for contract_kind, model in CONTRACT_MODELS.items():
        for fixture_path in _fixture_paths(contract_kind, "valid"):
            checked += 1
            try:
                model.model_validate(_read_json(fixture_path))
            except (ValidationError, OSError, json.JSONDecodeError) as exc:
                failures.append({"file": str(fixture_path), "reason": str(exc)})
        for fixture_path in _fixture_paths(contract_kind, "invalid"):
            checked += 1
            try:
                expected = _read_json(fixture_path.with_suffix(".expect.json"))["reason_code"]
                model.model_validate(_read_json(fixture_path))
            except ValidationError as exc:
                actual_codes = {str(error["type"]) for error in exc.errors()}
                if expected not in actual_codes:
                    failures.append(
                        {
                            "file": str(fixture_path),
                            "reason": "unexpected_rejection_reason",
                            "expected": expected,
                            "actual": sorted(actual_codes),
                        }
                    )
            except (OSError, json.JSONDecodeError, KeyError) as exc:
                failures.append({"file": str(fixture_path), "reason": str(exc)})
            else:
                failures.append({"file": str(fixture_path), "reason": "invalid_fixture_accepted"})
    _emit({"valid": not failures, "checked": checked, "failures": failures})
    return 0 if not failures else 1


def _compat(old_path: Path, new_path: Path) -> int:
    try:
        old_schema = _read_json(old_path)
        new_schema = _read_json(new_path)
        if not isinstance(old_schema, dict) or not isinstance(new_schema, dict):
            raise ValueError("both schemas must be JSON objects")
        report = check_compatibility(old_schema, new_schema)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        LOGGER.warning("cannot compare schemas: %s", exc)
        _emit({"compatible": False, "error": "compat_failed", "detail": str(exc)})
        return 1
    _emit(
        {
            "compatible": report.compatible,
            "level": report.level.value,
            "breaking_reasons": list(report.breaking_reasons),
            "additive_optional_fields": list(report.additive_optional_fields),
        }
    )
    return 0 if report.compatible else 1


def _build_parser() -> JsonArgumentParser:
    parser = JsonArgumentParser(prog="python -m research_os.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--contract", choices=sorted(CONTRACT_MODELS), required=True)
    validate_parser.add_argument("--file", type=Path, required=True)

    hash_parser = subparsers.add_parser("hash")
    hash_parser.add_argument("--file", type=Path, required=True)

    fixtures_parser = subparsers.add_parser("fixtures")
    fixtures_parser.add_argument("--check", action="store_true", required=True)

    compat_parser = subparsers.add_parser("compat")
    compat_parser.add_argument("--old", type=Path, required=True)
    compat_parser.add_argument("--new", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "validate":
        return _validate(args.contract, args.file)
    if args.command == "hash":
        return _hash(args.file)
    if args.command == "fixtures":
        return _check_fixtures()
    if args.command == "compat":
        return _compat(args.old, args.new)
    _emit({"valid": False, "error": "usage_error", "detail": "unknown command"})
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
