"""Integrity checks for the static Model Intelligence Registry (MIR).

These tests intentionally use only the standard library: runtime schema validation may
choose a JSON Schema library later, but the checked-in data must remain inspectable in
minimal CI environments.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from scripts.conductor.calibration import CalibrationRecord, EndpointHostObservation
from scripts.conductor.contracts import AuthSurface
from scripts.conductor.model_registry import (
    RegistryValidationError,
    _candidate_from_records,
    _content_hash,
    load_registry,
)


ROOT = Path(__file__).resolve().parents[2]
MIR = ROOT / "infra" / "conductor"
CARD_DIR = MIR / "model_cards"
ENDPOINT_DIR = MIR / "endpoint_profiles"
STATUSES = {
    "eligible",
    "manual_only",
    "probation",
    "phantom",
    "denied",
    "investigation_required",
    "listed_unexploited",
    "deprecated",
    "known_unmeasured",
}
EVIDENCE_LEVELS = {"declared", "probed", "benchmarked", "production", "unmeasured"}
PUBLIC_URL_PATTERN = re.compile(r"https?://[^\s|]+")
AUTH_SURFACES = {surface.value for surface in AuthSurface}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def assert_evidence(test: unittest.TestCase, evidence: Any, location: str) -> None:
    test.assertIsInstance(evidence, list, location)
    test.assertGreater(len(evidence), 0, location)
    for item in evidence:
        test.assertIsInstance(item, dict, location)
        test.assertIn(item.get("level"), EVIDENCE_LEVELS, location)
        test.assertTrue(item.get("ref"), location)
        test.assertRegex(str(item.get("observed_at")), r"^\d{4}-\d{2}-\d{2}", location)


def iter_evidence(value: Any) -> list[dict[str, Any]]:
    """Return evidence records nested anywhere in a static registry record."""
    if isinstance(value, dict):
        if set(value) == {"level", "ref", "observed_at"}:
            return [value]
        return [item for child in value.values() for item in iter_evidence(child)]
    if isinstance(value, list):
        return [item for child in value for item in iter_evidence(child)]
    return []


def has_declared_limit_evidence(limit: dict[str, Any]) -> bool:
    """Require an explicit declaration before a token limit may be non-null."""
    return any(item["level"] == "declared" for item in limit["evidence"])


def limit_value_is_evidenced(limit: dict[str, Any]) -> bool:
    """Keep unknown limits null and admit numeric limits only with a declaration."""
    if limit["value"] is None:
        return any(item["level"] == "unmeasured" for item in limit["evidence"])
    return has_declared_limit_evidence(limit)


def json_type_matches(value: Any, expected_type: str) -> bool:
    """Implement the JSON types used by the checked-in MIR schemas."""
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    raise AssertionError(f"unsupported JSON Schema type in MIR schema: {expected_type}")


def assert_matches_mir_schema(
    test: unittest.TestCase,
    value: Any,
    schema: dict[str, Any],
    root_schema: dict[str, Any],
    location: str,
) -> None:
    """Validate all JSON Schema keywords used by the two MIR schemas.

    This deliberately implements only the fixed, local schema subset in this repository,
    avoiding a new dependency merely to validate static registry data in minimal CI.
    """
    if "$ref" in schema:
        reference = schema["$ref"]
        test.assertTrue(
            reference.startswith("#/$defs/"),
            f"{location}: local $defs reference expected",
        )
        definition_name = reference.removeprefix("#/$defs/")
        assert_matches_mir_schema(
            test, value, root_schema["$defs"][definition_name], root_schema, location
        )
        return

    if "type" in schema:
        expected_types = schema["type"]
        if isinstance(expected_types, str):
            expected_types = [expected_types]
        test.assertTrue(
            any(
                json_type_matches(value, expected_type)
                for expected_type in expected_types
            ),
            f"{location}: expected JSON type {expected_types}, got {type(value).__name__}",
        )

    if "const" in schema:
        test.assertEqual(value, schema["const"], f"{location}: const mismatch")
    if "enum" in schema:
        test.assertTrue(
            any(value == allowed for allowed in schema["enum"]),
            f"{location}: enum mismatch",
        )
    if "pattern" in schema and isinstance(value, str):
        test.assertRegex(value, schema["pattern"], f"{location}: pattern mismatch")
    if "minLength" in schema and isinstance(value, str):
        test.assertGreaterEqual(
            len(value), schema["minLength"], f"{location}: string is too short"
        )
    if (
        "minimum" in schema
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
    ):
        test.assertGreaterEqual(
            value, schema["minimum"], f"{location}: number is too small"
        )
    if (
        "maximum" in schema
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
    ):
        test.assertLessEqual(
            value, schema["maximum"], f"{location}: number is too large"
        )

    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for required_name in schema.get("required", []):
            test.assertIn(
                required_name, value, f"{location}: missing required property"
            )
        if schema.get("additionalProperties") is False:
            unexpected = set(value) - set(properties)
            test.assertFalse(
                unexpected, f"{location}: unexpected properties {sorted(unexpected)}"
            )
        for property_name, property_schema in properties.items():
            if property_name in value:
                assert_matches_mir_schema(
                    test,
                    value[property_name],
                    property_schema,
                    root_schema,
                    f"{location}.{property_name}",
                )

    if isinstance(value, list):
        if "minItems" in schema:
            test.assertGreaterEqual(
                len(value), schema["minItems"], f"{location}: array is too short"
            )
        if "items" in schema:
            for index, item in enumerate(value):
                assert_matches_mir_schema(
                    test, item, schema["items"], root_schema, f"{location}[{index}]"
                )


class ModelIntelligenceRegistryTest(unittest.TestCase):
    def _clone_registry(self, directory: str) -> Path:
        """Return a disposable repository root containing only MIR inputs."""
        root = Path(directory)
        target = root / "infra" / "conductor"
        target.parent.mkdir(parents=True)
        shutil.copytree(MIR, target)
        return root

    def _endpoint_document(self, root: Path) -> tuple[Path, dict[str, Any]]:
        path = sorted(
            (root / "infra" / "conductor" / "endpoint_profiles").glob("*.json")
        )[0]
        return path, load_json(path)

    def test_loader_rejects_endpoint_without_explicit_auth_surface(self) -> None:
        """A missing concrete auth authority must never be treated as routable."""
        with tempfile.TemporaryDirectory() as directory:
            root = self._clone_registry(directory)
            path, endpoint = self._endpoint_document(root)
            endpoint.pop("auth_surface", None)
            path.write_text(json.dumps(endpoint), encoding="utf-8")

            with self.assertRaisesRegex(RegistryValidationError, "auth_surface"):
                load_registry(root)

    def test_loader_rejects_paid_anthropic_endpoint_as_eligible(self) -> None:
        """The paid Anthropic surface is inventory-only even if schema-valid."""
        with tempfile.TemporaryDirectory() as directory:
            root = self._clone_registry(directory)
            path, endpoint = self._endpoint_document(root)
            endpoint["auth_surface"] = "anthropic_paid_api"
            endpoint["routing"]["status"] = "eligible"
            endpoint["routing"]["automated_routing"] = False
            path.write_text(json.dumps(endpoint), encoding="utf-8")

            with self.assertRaisesRegex(RegistryValidationError, "paid Anthropic"):
                load_registry(root)

    def test_loader_rejects_unknown_task_profile_in_static_score(self) -> None:
        """Static score evidence must join to a real task profile before routing."""
        with tempfile.TemporaryDirectory() as directory:
            root = self._clone_registry(directory)
            path = sorted(
                (root / "infra" / "conductor" / "model_cards").glob("*.json")
            )[0]
            card = load_json(path)
            card["task_scores"] = [
                {
                    "task_profile_id": "unknown-profile",
                    "score": 0.9,
                    "benchmark_id": "test-benchmark",
                    "benchmark_version": "1.0.0",
                    "sample_count": 1,
                    "evidence": [
                        {
                            "level": "benchmarked",
                            "ref": "test:score",
                            "observed_at": "2026-08-21",
                        }
                    ],
                }
            ]
            path.write_text(json.dumps(card), encoding="utf-8")

            with self.assertRaisesRegex(
                RegistryValidationError, "unknown task profile"
            ):
                load_registry(root)

    def test_loader_rejects_numeric_static_score_without_samples(self) -> None:
        """A zero-sample score is unavailable rather than a routable quality claim."""
        with tempfile.TemporaryDirectory() as directory:
            root = self._clone_registry(directory)
            path = sorted(
                (root / "infra" / "conductor" / "model_cards").glob("*.json")
            )[0]
            card = load_json(path)
            card["task_scores"] = [
                {
                    "task_profile_id": "mechanical",
                    "score": 0.9,
                    "benchmark_id": None,
                    "benchmark_version": None,
                    "sample_count": 0,
                    "evidence": [
                        {
                            "level": "unmeasured",
                            "ref": "test:unavailable-score",
                            "observed_at": "2026-08-21",
                        }
                    ],
                }
            ]
            path.write_text(json.dumps(card), encoding="utf-8")

            with self.assertRaisesRegex(RegistryValidationError, "zero samples"):
                load_registry(root)

    def test_loader_rejects_nonlocal_endpoint_claiming_local_pii_capability(
        self,
    ) -> None:
        """A cloud auth surface cannot self-attest the local PII execution boundary."""
        with tempfile.TemporaryDirectory() as directory:
            root = self._clone_registry(directory)
            path, endpoint = self._endpoint_document(root)
            endpoint["auth_surface"] = "openai_chatgpt_subscription"
            endpoint["exposed_capabilities"].append(
                {
                    "id": "local_only",
                    "value": True,
                    "evidence": [
                        {
                            "level": "declared",
                            "ref": "test:nonlocal-local-only",
                            "observed_at": "2026-08-21",
                        }
                    ],
                }
            )
            path.write_text(json.dumps(endpoint), encoding="utf-8")

            with self.assertRaisesRegex(RegistryValidationError, "local_runtime"):
                load_registry(root)

    def test_cloud_endpoint_cannot_inherit_local_pii_capability_from_model_card(
        self,
    ) -> None:
        """The concrete auth surface, not a shared card, binds PII-local claims."""
        with tempfile.TemporaryDirectory() as directory:
            root = self._clone_registry(directory)
            path, endpoint = self._endpoint_document(root)
            endpoint["auth_surface"] = "openai_chatgpt_subscription"
            endpoint["model_card_id"] = "deepseek-r1-32b"
            path.write_text(json.dumps(endpoint), encoding="utf-8")

            card = load_json(
                root / "infra" / "conductor" / "model_cards" / "deepseek-r1-32b.json"
            )
            candidate = _candidate_from_records(
                endpoint,
                card,
                (),
                (),
                load_registry(ROOT).task_profiles,
            )

            capabilities = {item.capability for item in candidate.features}
            self.assertNotIn("local_only", capabilities)
            self.assertNotIn("pii_safe_local", capabilities)

    def test_loader_rejects_local_pii_profile_without_local_capabilities(self) -> None:
        """A local-only task must request both capability guards at the schema join."""
        with tempfile.TemporaryDirectory() as directory:
            root = self._clone_registry(directory)
            path = root / "infra" / "conductor" / "task_profiles.v1.json"
            profiles = load_json(path)
            profile = profiles["profiles"][0]
            profile["pii_policy"] = "local_only"
            profile["required_capabilities"] = ["coding"]
            path.write_text(json.dumps(profiles), encoding="utf-8")

            with self.assertRaisesRegex(RegistryValidationError, "local_only policy"):
                load_registry(root)

    def test_noneligible_endpoint_is_not_promoted_after_valid_overlay_evidence(
        self,
    ) -> None:
        """Calibration health cannot override a static non-eligibility status."""
        registry = load_registry(ROOT)
        endpoint = registry.endpoint_profiles["claude-claude-opus-5"]
        profile = registry.task_profiles["mechanical"]
        endpoint_hash = _content_hash(endpoint)
        calibration = CalibrationRecord(
            benchmark_id="conductor-priority-pilot",
            benchmark_version="1.0.0",
            endpoint_id="claude-claude-opus-5",
            endpoint_profile_hash=endpoint_hash,
            task_profile_id=profile.id,
            score=0.95,
            conservative_score=0.9,
            sample_count=5,
            sample_hashes=("a", "b", "c", "d", "e"),
            scorer_id="test-scorer",
            scorer_version="1.0.0",
            measured_at="2026-08-21T00:00:00Z",
            expires_at="2026-08-22T00:00:00Z",
            dispersion=0.01,
        )
        observation = EndpointHostObservation(
            endpoint_id="claude-claude-opus-5",
            endpoint_profile_hash=endpoint_hash,
            host="pro",
            model_identifier="claude-opus-5",
            available=True,
            healthy=True,
            latency_ms=10,
            context_tokens=100_000,
            output_tokens=10_000,
            enforcement_mode="enforced",
            identity_verified=True,
            probe_id="test-probe",
            probe_version="1.0.0",
            observed_at="2026-08-21T00:00:00Z",
            expires_at="2026-08-22T00:00:00Z",
        )

        candidate = _candidate_from_records(
            endpoint,
            registry.model_cards[endpoint["model_card_id"]],
            (calibration,),
            (observation,),
            registry.task_profiles,
        )

        self.assertTrue(candidate.healthy)
        self.assertFalse(candidate.automated_routing)
        self.assertEqual(candidate.routing_status, "known_unmeasured")

    def test_all_noneligible_statuses_stay_nonautomated(self) -> None:
        """Every non-eligible static status is a hard routing boundary."""
        registry = load_registry(ROOT)
        source = registry.endpoint_profiles["claude-claude-opus-5"]
        card = registry.model_cards[source["model_card_id"]]
        for status in (
            "known_unmeasured",
            "denied",
            "phantom",
            "investigation_required",
        ):
            with self.subTest(status=status):
                endpoint = {
                    **source,
                    "routing": {
                        **source["routing"],
                        "status": status,
                        "automated_routing": False,
                    },
                }
                candidate = _candidate_from_records(
                    endpoint,
                    card,
                    (),
                    (),
                    registry.task_profiles,
                )
                self.assertFalse(candidate.automated_routing)
                self.assertEqual(candidate.routing_status, status)

    def test_loader_rejects_unknown_model_card_and_endpoint_profile_fields(
        self,
    ) -> None:
        """Schema drift cannot silently create an unreviewed authority field."""
        with tempfile.TemporaryDirectory() as directory:
            root = self._clone_registry(directory)
            endpoint_path, endpoint = self._endpoint_document(root)
            endpoint["unreviewed_authority"] = "allow"
            endpoint_path.write_text(json.dumps(endpoint), encoding="utf-8")
            card_path = sorted(
                (root / "infra" / "conductor" / "model_cards").glob("*.json")
            )[0]
            card = load_json(card_path)
            card["unreviewed_authority"] = "allow"
            card_path.write_text(json.dumps(card), encoding="utf-8")

            with self.assertRaisesRegex(RegistryValidationError, "unexpected property"):
                load_registry(root)

    def test_loader_rejects_malformed_checked_in_schema(self) -> None:
        """A malformed schema must not downgrade validation into an allow path."""
        with tempfile.TemporaryDirectory() as directory:
            root = self._clone_registry(directory)
            schema_path = root / "infra" / "conductor" / "endpoint_profile.schema.json"
            schema = load_json(schema_path)
            schema["properties"]["auth_surface"] = {"type": "not-a-json-type"}
            schema_path.write_text(json.dumps(schema), encoding="utf-8")

            with self.assertRaisesRegex(
                RegistryValidationError, "unsupported JSON Schema type"
            ):
                load_registry(root)

    def test_loader_rejects_index_that_is_not_the_exact_generated_projection(
        self,
    ) -> None:
        """Counts and identifiers alone cannot prove the generated index is current."""
        with tempfile.TemporaryDirectory() as directory:
            root = self._clone_registry(directory)
            index_path = root / "infra" / "conductor" / "model_capability_index.v1.json"
            index = load_json(index_path)
            index["endpoints"][0]["machine_allowlist"] = ["mini-pro2"]
            index_path.write_text(json.dumps(index), encoding="utf-8")

            with self.assertRaisesRegex(
                RegistryValidationError, "deterministic projection"
            ):
                load_registry(root)

    def test_static_json_is_parseable(self) -> None:
        json_paths = (
            sorted(MIR.glob("*.json"))
            + sorted(CARD_DIR.glob("*.json"))
            + sorted(ENDPOINT_DIR.glob("*.json"))
        )
        self.assertGreater(len(json_paths), 0)
        for path in json_paths:
            with self.subTest(path=path.relative_to(ROOT)):
                load_json(path)

    def test_cards_have_evidenced_claims_and_unique_ids(self) -> None:
        cards = [load_json(path) for path in sorted(CARD_DIR.glob("*.json"))]
        self.assertTrue(cards, "MIR must contain at least one evidenced ModelCard")
        ids = [card["id"] for card in cards]
        self.assertEqual(len(ids), len(set(ids)))
        aliases = [alias for card in cards for alias in card["identity"]["aliases"]]
        self.assertEqual(
            len(aliases),
            len(set(aliases)),
            "a concrete model alias must identify exactly one ModelCard",
        )
        for card in cards:
            with self.subTest(card=card["id"]):
                self.assertEqual(card["schema_version"], "model-card.v1")
                self.assertIn(card["routing"]["status"], STATUSES)
                self.assertFalse(
                    card["routing"]["automated_routing"],
                    "ModelCard is abstract; only EndpointProfile can authorize invocation",
                )
                assert_evidence(self, card["evidence"], card["id"])
                assert_evidence(
                    self, card["identity"]["evidence"], card["id"] + ".identity"
                )
                assert_evidence(
                    self, card["routing"]["evidence"], card["id"] + ".routing"
                )
                for modality in card["modalities"]:
                    assert_evidence(
                        self, modality["evidence"], card["id"] + ".modalities"
                    )
                modality_ids = [modality["id"] for modality in card["modalities"]]
                self.assertEqual(
                    len(modality_ids),
                    len(set(modality_ids)),
                    card["id"] + ".modalities",
                )
                for limit_name, limit in card["limits"].items():
                    assert_evidence(
                        self, limit["evidence"], f"{card['id']}.limits.{limit_name}"
                    )
                    self.assertTrue(
                        limit_value_is_evidenced(limit),
                        f"{card['id']}.limits.{limit_name}: numeric limits require declared evidence; "
                        "unmeasured limits must remain null",
                    )
                for constraint in card.get("constraints", []):
                    assert_evidence(
                        self, constraint["evidence"], card["id"] + ".constraints"
                    )
                self.assertEqual(card["task_scores"], [])

    def test_cards_and_endpoints_conform_to_checked_in_schemas(self) -> None:
        model_schema = load_json(MIR / "model_card.schema.json")
        endpoint_schema = load_json(MIR / "endpoint_profile.schema.json")
        for path in sorted(CARD_DIR.glob("*.json")):
            with self.subTest(path=path.relative_to(ROOT)):
                assert_matches_mir_schema(
                    self, load_json(path), model_schema, model_schema, path.stem
                )
        for path in sorted(ENDPOINT_DIR.glob("*.json")):
            with self.subTest(path=path.relative_to(ROOT)):
                assert_matches_mir_schema(
                    self, load_json(path), endpoint_schema, endpoint_schema, path.stem
                )

    def test_evidence_and_routing_vocabularies_are_contract_consistent(self) -> None:
        """Schemas, ontology, and typed registry vocabulary cannot silently drift."""
        ontology = load_json(MIR / "capability_ontology.v1.json")
        ontology_evidence = {item["id"] for item in ontology["evidence_levels"]}
        ontology_routing = {item["id"] for item in ontology["routing_statuses"]}
        self.assertEqual(ontology_evidence, EVIDENCE_LEVELS)
        self.assertEqual(ontology_routing, STATUSES)
        for schema_name in (
            "model_card.schema.json",
            "endpoint_profile.schema.json",
            "task_profile.schema.json",
        ):
            schema = load_json(MIR / schema_name)
            with self.subTest(schema=schema_name):
                self.assertEqual(
                    set(schema["$defs"]["evidence"]["properties"]["level"]["enum"]),
                    EVIDENCE_LEVELS,
                )
        for schema_name in ("model_card.schema.json", "endpoint_profile.schema.json"):
            schema = load_json(MIR / schema_name)
            with self.subTest(schema=schema_name):
                self.assertEqual(
                    set(
                        schema["properties"]["routing"]["properties"]["status"]["enum"]
                    ),
                    STATUSES,
                )

    def test_limit_rule_rejects_unsupported_numbers(self) -> None:
        unsupported_numeric_limit = {
            "value": 1,
            "evidence": [
                {
                    "level": "unmeasured",
                    "ref": "inventory",
                    "observed_at": "2026-08-21",
                }
            ],
        }
        supported_numeric_limit = {
            "value": 1,
            "evidence": [
                {
                    "level": "declared",
                    "ref": "https://example.com/model",
                    "observed_at": "2026-08-21",
                }
            ],
        }
        unknown_limit = {
            "value": None,
            "evidence": [
                {
                    "level": "unmeasured",
                    "ref": "inventory",
                    "observed_at": "2026-08-21",
                }
            ],
        }

        self.assertFalse(limit_value_is_evidenced(unsupported_numeric_limit))
        self.assertTrue(limit_value_is_evidenced(supported_numeric_limit))
        self.assertTrue(limit_value_is_evidenced(unknown_limit))

    def test_public_evidence_is_declared_and_urls_are_valid(self) -> None:
        registry_paths = sorted(CARD_DIR.glob("*.json")) + sorted(
            ENDPOINT_DIR.glob("*.json")
        )
        for path in registry_paths:
            for item in iter_evidence(load_json(path)):
                for raw_url in PUBLIC_URL_PATTERN.findall(item["ref"]):
                    with self.subTest(path=path.relative_to(ROOT), url=raw_url):
                        parsed = urlparse(raw_url)
                        self.assertIn(parsed.scheme, {"http", "https"})
                        self.assertTrue(parsed.netloc)
                        self.assertEqual(
                            item["level"],
                            "declared",
                            "public documentation is a declaration, not an availability, auth, or quality probe",
                        )

    def test_endpoint_profiles_are_unique_and_conservatively_routable(self) -> None:
        cards = {
            card["id"]: card
            for card in (load_json(path) for path in sorted(CARD_DIR.glob("*.json")))
        }
        endpoints = [load_json(path) for path in sorted(ENDPOINT_DIR.glob("*.json"))]
        endpoint_ids = [endpoint["id"] for endpoint in endpoints]
        self.assertEqual(len(endpoint_ids), len(set(endpoint_ids)))
        invocation_keys = [
            (
                endpoint["invocation"]["engine"],
                endpoint["invocation"]["model_identifier"],
            )
            for endpoint in endpoints
        ]
        self.assertEqual(
            len(invocation_keys),
            len(set(invocation_keys)),
            "a concrete provider invocation must identify exactly one EndpointProfile",
        )
        self.assertEqual(
            {endpoint["model_card_id"] for endpoint in endpoints},
            set(cards),
            "every ModelCard must have a concrete endpoint profile",
        )
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint["id"]):
                self.assertEqual(endpoint["schema_version"], "endpoint-profile.v1")
                self.assertIn(endpoint["model_card_id"], cards)
                self.assertIn(endpoint["auth_surface"], AUTH_SURFACES)
                self.assertIn(endpoint["routing"]["status"], STATUSES)
                if endpoint["routing"]["automated_routing"]:
                    self.assertEqual(endpoint["routing"]["status"], "eligible")
                assert_evidence(self, endpoint["evidence"], endpoint["id"])
                assert_evidence(
                    self,
                    endpoint["invocation"]["evidence"],
                    endpoint["id"] + ".invocation",
                )
                assert_evidence(
                    self,
                    endpoint["account_class"]["evidence"],
                    endpoint["id"] + ".account_class",
                )
                assert_evidence(
                    self,
                    endpoint["machine_constraints"]["evidence"],
                    endpoint["id"] + ".machines",
                )
                self.assertTrue(endpoint["machine_constraints"]["allowlist"])
                capability_ids = [
                    capability["id"] for capability in endpoint["exposed_capabilities"]
                ]
                self.assertEqual(
                    len(capability_ids),
                    len(set(capability_ids)),
                    endpoint["id"] + ".exposed_capabilities",
                )

    def test_auth_surfaces_are_complete_and_conservatively_routable(self) -> None:
        """Every concrete endpoint states an authority; unverified providers stay denied."""
        schema = load_json(MIR / "endpoint_profile.schema.json")
        self.assertEqual(
            set(schema["properties"]["auth_surface"]["enum"]), AUTH_SURFACES
        )
        registry = load_registry(ROOT)
        for endpoint in registry.endpoint_profiles.values():
            with self.subTest(endpoint=endpoint["id"]):
                self.assertIn(endpoint["auth_surface"], AUTH_SURFACES)
                self.assertNotEqual(endpoint["auth_surface"], "anthropic_paid_api")
                candidate = registry.endpoint(endpoint["id"])
                self.assertEqual(candidate.auth_surface.value, endpoint["auth_surface"])
                if candidate.auth_surface is AuthSurface.UNKNOWN:
                    self.assertFalse(candidate.automated_routing)

    def test_index_is_a_complete_normalized_projection(self) -> None:
        cards = [load_json(path) for path in sorted(CARD_DIR.glob("*.json"))]
        endpoints = [load_json(path) for path in sorted(ENDPOINT_DIR.glob("*.json"))]
        index = load_json(MIR / "model_capability_index.v1.json")
        self.assertEqual(index["schema_version"], "model-capability-index.v1")
        self.assertEqual(index["model_count"], len(cards))
        self.assertEqual(index["endpoint_count"], len(endpoints))
        self.assertEqual(
            {item["model_card_id"] for item in index["models"]},
            {card["id"] for card in cards},
        )
        self.assertEqual(
            {item["endpoint_id"] for item in index["endpoints"]},
            {endpoint["id"] for endpoint in endpoints},
        )
        self.assertEqual(
            len(index["endpoints"]),
            len({item["endpoint_id"] for item in index["endpoints"]}),
        )
        assert_evidence(self, index["generation"]["evidence"], "index.generation")
        for item in index["models"] + index["endpoints"]:
            assert_evidence(self, item["evidence"], "index item")

    def test_projection_is_current_for_the_deterministic_generator(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/conductor/build_model_capability_index.py",
                "--check",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        prettier = subprocess.run(
            [
                "npx",
                "--no-install",
                "prettier",
                "--check",
                str(MIR / "model_capability_index.v1.json"),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(prettier.returncode, 0, prettier.stdout + prettier.stderr)


if __name__ == "__main__":
    unittest.main()
