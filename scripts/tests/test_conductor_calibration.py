"""Fail-closed tests for MIR calibration and exact host observation overlays."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from scripts.conductor.model_registry import RegistryValidationError, load_registry


ROOT = Path(__file__).resolve().parents[2]
MIR = ROOT / "infra" / "conductor"
AS_OF = "2026-08-23T00:00:00Z"
MEASURED_AT = "2026-08-22T00:00:00Z"
EXPIRES_AT = "2026-08-29T00:00:00Z"
ENDPOINT_ID = "codex-gpt-5.6-luna"
PROFILE_ID = "mechanical"


def _hashes(count: int, prefix: str = "sample") -> list[str]:
    return [sha256(f"{prefix}-{index}".encode()).hexdigest() for index in range(count)]


class CalibrationOverlayTest(unittest.TestCase):
    def _clone(self, directory: str) -> Path:
        root = Path(directory)
        target = root / "infra" / "conductor"
        target.parent.mkdir(parents=True)
        shutil.copytree(MIR, target)
        return root

    def _endpoint_hash(self, root: Path, endpoint_id: str = ENDPOINT_ID) -> str:
        return load_registry(root).endpoint(endpoint_id).endpoint_profile_hash

    def _calibration(
        self,
        root: Path,
        *,
        endpoint_id: str = ENDPOINT_ID,
        profile_id: str = PROFILE_ID,
        count: int = 5,
    ) -> dict[str, object]:
        return {
            "benchmark_id": "conductor-priority-pilot",
            "benchmark_version": "1.0.0",
            "endpoint_id": endpoint_id,
            "endpoint_profile_hash": self._endpoint_hash(root, endpoint_id),
            "task_profile_id": profile_id,
            "score": 0.95,
            "conservative_score": 0.9,
            "sample_count": count,
            "sample_hashes": _hashes(count, endpoint_id),
            "scorer": {"id": "blinded-code-scorer", "version": "1.0.0"},
            "measured_at": MEASURED_AT,
            "expires_at": EXPIRES_AT,
            "dispersion": {"metric": "sample_variance", "value": 0.01},
        }

    def _observation(
        self, root: Path, *, endpoint_id: str = ENDPOINT_ID
    ) -> dict[str, object]:
        endpoint = load_registry(root).endpoint_profiles[endpoint_id]
        return {
            "endpoint_id": endpoint_id,
            "endpoint_profile_hash": self._endpoint_hash(root, endpoint_id),
            "host": "pro",
            "model_identifier": endpoint["invocation"]["model_identifier"],
            "available": True,
            "healthy": True,
            "latency_ms": 500,
            "context_tokens": 32768,
            "output_tokens": 8192,
            "enforcement_mode": "enforced",
            "identity_verified": True,
            "probe": {"id": "exact-cli-model-probe", "version": "1.0.0"},
            "observed_at": MEASURED_AT,
            "expires_at": EXPIRES_AT,
        }

    def _write_overlays(
        self,
        root: Path,
        calibrations: list[dict[str, object]],
        observations: list[dict[str, object]],
    ) -> None:
        mir = root / "infra" / "conductor"
        (mir / "calibrations.v1.json").write_text(
            json.dumps(
                {
                    "schema_version": "calibration-overlay.v1",
                    "generated_at": MEASURED_AT,
                    "records": calibrations,
                }
            ),
            encoding="utf-8",
        )
        (mir / "host_observations.v1.json").write_text(
            json.dumps(
                {
                    "schema_version": "host-observation-overlay.v1",
                    "generated_at": MEASURED_AT,
                    "observations": observations,
                }
            ),
            encoding="utf-8",
        )

    def test_fresh_calibrated_healthy_noneligible_endpoint_stays_unroutable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._clone(directory)
            self._write_overlays(
                root, [self._calibration(root)], [self._observation(root)]
            )

            registry = load_registry(root, as_of=AS_OF)
            candidates = registry.endpoints()

            self.assertFalse(registry.operational)
            self.assertEqual(candidates, ())

    def test_missing_and_rejected_artifacts_never_open_a_route(self) -> None:
        cases = {
            "missing_observation": (None, None, ""),
            "stale_calibration": ("expires_at", "2026-08-22T12:00:00Z", "stale"),
            "low_sample": ("sample", 4, "low_sample"),
            "high_variance": ("variance", 0.06, "high_variance"),
            "endpoint_mismatch": (
                "endpoint_profile_hash",
                "0" * 64,
                "endpoint_profile_mismatch",
            ),
            "benchmark_mismatch": (
                "benchmark_version",
                "2.0.0",
                "benchmark_version_mismatch",
            ),
        }
        for name, (field, value, reason) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = self._clone(directory)
                calibration = self._calibration(root)
                observations = (
                    [] if name == "missing_observation" else [self._observation(root)]
                )
                if field == "sample":
                    calibration["sample_count"] = value
                    calibration["sample_hashes"] = _hashes(int(value), ENDPOINT_ID)
                elif field == "variance":
                    calibration["dispersion"] = {
                        "metric": "sample_variance",
                        "value": value,
                    }
                elif field is not None:
                    calibration[field] = value
                self._write_overlays(root, [calibration], observations)

                registry = load_registry(root, as_of=AS_OF)

                self.assertFalse(registry.operational)
                self.assertEqual(registry.endpoints(), ())
                if reason:
                    self.assertTrue(
                        any(reason in item for item in registry.overlay_diagnostics),
                        registry.overlay_diagnostics,
                    )

    def test_stale_or_wrong_exact_model_observation_is_rejected(self) -> None:
        for name, mutation, reason in (
            ("stale", {"expires_at": "2026-08-22T12:00:00Z"}, "stale"),
            (
                "wrong_model",
                {"model_identifier": "gpt-5.6-not-luna"},
                "model_identifier_mismatch",
            ),
        ):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = self._clone(directory)
                observation = self._observation(root)
                observation.update(mutation)
                self._write_overlays(root, [self._calibration(root)], [observation])

                registry = load_registry(root, as_of=AS_OF)

                self.assertFalse(registry.operational)
                self.assertTrue(
                    any(reason in item for item in registry.overlay_diagnostics)
                )

    def test_overlay_schema_forbids_auth_secret_prompt_and_pii_fields(self) -> None:
        for forbidden in ("api_key", "prompt", "client_name"):
            with (
                self.subTest(field=forbidden),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = self._clone(directory)
                calibration = self._calibration(root)
                calibration[forbidden] = "must-not-survive"
                self._write_overlays(root, [calibration], [self._observation(root)])

                with self.assertRaisesRegex(
                    RegistryValidationError, f"unexpected property {forbidden}"
                ):
                    load_registry(root, as_of=AS_OF)

    def test_diagnostics_and_routing_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._clone(directory)
            low_sample = self._calibration(root, count=4)
            high_variance = self._calibration(
                root,
                endpoint_id="codex-gpt-5.6-terra",
                profile_id="standard_build",
            )
            high_variance["dispersion"] = {
                "metric": "sample_variance",
                "value": 0.06,
            }
            records = [high_variance, low_sample]
            self._write_overlays(root, records, [])
            first = load_registry(root, as_of=AS_OF)
            self._write_overlays(root, list(reversed(records)), [])
            second = load_registry(root, as_of=AS_OF)

            self.assertEqual(first.overlay_diagnostics, second.overlay_diagnostics)
            self.assertEqual(first.endpoints(), second.endpoints())

    def test_real_registry_is_non_operational_without_pilot_artifacts(self) -> None:
        registry = load_registry(ROOT)
        source_eligible = [
            endpoint_id
            for endpoint_id, endpoint in registry.endpoint_profiles.items()
            if endpoint["routing"]["status"] == "eligible"
            and endpoint["routing"]["automated_routing"] is True
        ]
        effective_eligible = registry.endpoints()

        self.assertTrue(
            source_eligible,
            "static eligibility must exist to exercise the effective evidence gate",
        )
        self.assertEqual(effective_eligible, ())
        self.assertFalse(registry.operational)
        self.assertTrue(
            all(
                registry.endpoint_profiles[endpoint_id]["routing"]["automated_routing"]
                is True
                for endpoint_id in source_eligible
            ),
            "the effective overlay must not mutate source routing truth",
        )

        candidate = registry.endpoint(ENDPOINT_ID)
        self.assertFalse(candidate.healthy)
        self.assertEqual(candidate.task_scores, ())

    def test_priority_cli_is_offline_and_aggregate_retains_only_hashes(self) -> None:
        plan = subprocess.run(
            [
                str(ROOT / "apps" / "backend-rag" / ".venv" / "bin" / "python"),
                str(ROOT / "scripts" / "conductor" / "calibration_cli.py"),
                "plan",
                "--root",
                str(ROOT),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(plan.returncode, 0, plan.stderr)
        manifest = json.loads(plan.stdout)
        self.assertEqual(manifest["execution"], "not_implemented_no_provider_calls")
        self.assertEqual(len({item["endpoint_id"] for item in manifest["entries"]}), 9)

        with tempfile.TemporaryDirectory() as directory:
            sample_path = Path(directory) / "samples.jsonl"
            output_path = Path(directory) / "overlay.json"
            samples = [
                {
                    "endpoint_id": ENDPOINT_ID,
                    "task_profile_id": PROFILE_ID,
                    "sample_hash": digest,
                    "score": 0.9,
                }
                for digest in _hashes(5)
            ]
            sample_path.write_text(
                "\n".join(json.dumps(item) for item in samples) + "\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    str(ROOT / "apps" / "backend-rag" / ".venv" / "bin" / "python"),
                    "-m",
                    "scripts.conductor.calibration_cli",
                    "aggregate",
                    "--root",
                    str(ROOT),
                    "--samples",
                    str(sample_path),
                    "--output",
                    str(output_path),
                    "--benchmark-id",
                    "conductor-priority-pilot",
                    "--benchmark-version",
                    "1.0.0",
                    "--scorer-id",
                    "blinded-code-scorer",
                    "--scorer-version",
                    "1.0.0",
                    "--measured-at",
                    MEASURED_AT,
                    "--expires-at",
                    EXPIRES_AT,
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            artifact = json.loads(output_path.read_text(encoding="utf-8"))
            serialized = json.dumps(artifact)
            self.assertNotIn("prompt", serialized)
            self.assertNotIn("response", serialized)
            self.assertEqual(artifact["records"][0]["sample_count"], 5)


if __name__ == "__main__":
    unittest.main()
