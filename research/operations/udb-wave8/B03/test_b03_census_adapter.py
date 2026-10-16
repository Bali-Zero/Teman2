"""Unit and negative tests for B03 deterministic consumer census adapter."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "fixtures"))

import b03_census_adapter as adapter  # noqa: E402
import build_fixtures as fixture_tool  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[4]


class TestB03CensusAdapter(unittest.TestCase):
    """Verify 6,030-row conservation, CONTRACT-CONVENTIONS.md compliance, and negative cases."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.rows, cls.summary = adapter.build_census_rows(REPO_ROOT)
        cls.rows_by_id = {row["consumer_id"]: row for row in cls.rows}

    def test_conservation_and_counts(self) -> None:
        """Total leads must equal 6,030 (6,029 matrix + 1 LEAD-DELTA)."""
        self.assertEqual(len(self.rows), 6030)
        self.assertEqual(self.summary["total_leads"], 6030)
        self.assertEqual(self.summary["matrix_leads"], 6029)
        self.assertEqual(self.summary["lead_delta_leads"], 1)

        disp = self.summary["disposition_counts"]
        self.assertEqual(sum(disp.values()), 6030)
        self.assertEqual(disp["excluded"], 1803)
        self.assertEqual(disp["duplicate"], 43)
        self.assertEqual(disp["retired"], 0)
        self.assertEqual(disp["active"], 0)
        self.assertEqual(disp["unresolved"], 4184)
        self.assertEqual(self.summary["active_consumer_denominator"], "UNKNOWN")

    def test_contract_conventions_all_rows(self) -> None:
        """Every row must obey CONTRACT-CONVENTIONS.md field order and value domains."""
        allowed_timestamps = {
            "2026-10-12T05:16:40.748258+00:00",
            "2026-10-12T05:16:41.077585+00:00",
            "2026-10-12T05:16:41.337970+00:00",
            "2026-10-13T22:12:52.915013+00:00",
            "2026-10-15T03:00:43Z",
            "2026-10-15T07:06:22Z",
        }
        for row in self.rows:
            adapter.validate_output_row(row)
            self.assertEqual(row["operation_id"], "UNASSIGNED_B05")
            self.assertEqual(row["store_id"], "unknown:unknown:unknown")
            self.assertIn("OPERATION_ID_PENDING_B05", row["unknowns"])
            self.assertIn(row["evidence_timestamp"], allowed_timestamps)
            if row["evidence_timestamp"] == "2026-10-15T07:06:22Z":
                self.assertIn("STATIC_SOURCE_ONLY", row["unknowns"])
            self.assertEqual(len(row["evidence_sha256"]), 64)

    def test_historical_restore_references_and_lead_delta_reconciled(self) -> None:
        """All 5 historical restore refs from LEAD-DELTA.json + the 6,030th lead are reconciled."""
        expected_refs = {
            "src_307bea3dfb94ec31": "unresolved",
            "src_d073f505ff1671ad": "unresolved",
            "src_def7a4c288a552af": "unresolved",
            "src_cdf3ae5e4ecf861c": "excluded",
            "src_2f350566b97aee80": "excluded",
            "runtime_mini_46522da0ef79d3aa7422ca41": "unresolved",
        }
        for cid, expected_disp in expected_refs.items():
            self.assertIn(cid, self.rows_by_id)
            row = self.rows_by_id[cid]
            self.assertEqual(row["x_disposition"], expected_disp)
            self.assertTrue(row["x_restore_ref_role"])

        workflow_row = self.rows_by_id["src_307bea3dfb94ec31"]
        self.assertIn(
            "GIT_DELETED_WORKFLOW_LEGACY_COPIES_UNPROVED_RETIRED",
            workflow_row["unknowns"],
        )

        mini_row = self.rows_by_id["runtime_mini_46522da0ef79d3aa7422ca41"]
        self.assertEqual(mini_row["store_id"], "unknown:unknown:unknown")
        self.assertIn("STORE_ID_PROPOSED:pg:mini:local", mini_row["unknowns"])
        self.assertIn("STORE_BINDING_PENDING_B04", mini_row["unknowns"])
        self.assertEqual(
            mini_row["source_version"],
            "prior:d0c67ee668f97c754e8bcec662d0df7dbf30a126",
        )
        self.assertEqual(mini_row["evidence_timestamp"], "2026-10-15T03:00:43Z")

    def test_ci_workflow_candidate_join_kept_unresolved(self) -> None:
        """CI-REGISTRATION-UNMATCHED-GH-* rows record candidate index_* join but stay unresolved."""
        gh_row = self.rows_by_id["CI-REGISTRATION-UNMATCHED-GH-dad0661358dde36a980e"]
        self.assertEqual(gh_row["x_disposition"], "unresolved")
        self.assertEqual(gh_row["x_candidate_join_id"], "index_7ead7509c09411da47590f81")
        self.assertEqual(gh_row["x_canonical_consumer_id"], "")
        self.assertIn(
            "CI_WORKFLOW_TO_INDEX_PATH_SHA24_MATCH_NEEDS_ACTOR_PROOF",
            gh_row["unknowns"],
        )

    def test_negative_hash_mismatch_refusal(self) -> None:
        """Adapter must fail closed (PinVerificationError) on any frozen or supplementary prior SHA-256 mismatch."""
        with self.assertRaises(adapter.PinVerificationError):
            adapter.verify_pinned_inputs(
                REPO_ROOT,
                extra_pins={
                    ".agent-receipts/udb-wave8-inputs/STATE.json": "0" * 64,
                },
            )
        with self.assertRaises(adapter.PinVerificationError):
            adapter.verify_pinned_inputs(
                REPO_ROOT,
                extra_pins={
                    adapter.SUPPLEMENTARY_PRIOR_PATHS["source_index"]: "0" * 64,
                },
            )

    def test_negative_duplicate_claim_without_preimage_or_bytes_rejected(self) -> None:
        """Claiming duplicate without verified pre-image or installed-bytes proof is rejected."""
        with self.assertRaises(adapter.ContractValidationError):
            adapter.validate_duplicate_claim(
                "index_7ead7509c09411da47590f81",
                "src_307bea3dfb94ec31",
                preimage_verified=False,
                same_installed_bytes_and_host=True,
            )

        with self.assertRaises(adapter.ContractValidationError):
            adapter.validate_duplicate_claim(
                "CI-REGISTRATION-UNMATCHED-GH-dad0661358dde36a980e",
                "index_7ead7509c09411da47590f81",
                preimage_verified=True,
                same_installed_bytes_and_host=False,
            )

    def test_negative_git_deleted_workflow_does_not_retire_without_host_proof(self) -> None:
        """A git-deleted workflow with live host registration or unproved legacy retirement stays unresolved."""
        self.assertEqual(
            adapter.evaluate_retirement_claim(
                "src_307bea3dfb94ec31",
                git_deleted=True,
                host_registrations_absent_verified=False,
                legacy_copies_retired_verified=True,
            ),
            "unresolved",
        )
        self.assertEqual(
            adapter.evaluate_retirement_claim(
                "src_307bea3dfb94ec31",
                git_deleted=True,
                host_registrations_absent_verified=True,
                legacy_copies_retired_verified=False,
            ),
            "unresolved",
        )
        self.assertEqual(
            adapter.evaluate_retirement_claim(
                "src_307bea3dfb94ec31",
                git_deleted=True,
                host_registrations_absent_verified=True,
                legacy_copies_retired_verified=True,
            ),
            "retired",
        )

    def test_negative_non_consumer_leakage_and_blocked_promotion_rejected(self) -> None:
        """Non-consumer leakage into active/unresolved and BLOCKED_DISCOVERY promotion to active are rejected."""
        source_row = next(row for row in self.rows if row["consumer_id"].startswith("NOTEBOOK-CONTAINER-REFERENCE-NLM-"))
        bad_row = dict(source_row)
        bad_row["x_disposition"] = "unresolved"
        with self.assertRaises(adapter.ContractValidationError):
            adapter.validate_output_row(bad_row)

        bad_status_row = dict(self.rows[0])
        bad_status_row["status"] = "blocked_evidence"
        with self.assertRaises(adapter.ContractValidationError):
            adapter.validate_output_row(bad_status_row)

        with self.assertRaises(adapter.ContractValidationError):
            adapter.validate_active_promotion(
                "src_c8f206461cd9bf69",
                "BLOCKED_DISCOVERY",
                has_deployed_execution_proof=False,
                has_resolved_target_contract=True,
            )

    def test_deterministic_serialization(self) -> None:
        """Writing outputs twice produces identical SHA-256 digests."""
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            hashes1 = adapter.write_census_outputs(
                self.rows, self.summary, Path(tmp1)
            )
            hashes2 = adapter.write_census_outputs(
                self.rows, self.summary, Path(tmp2)
            )
            self.assertEqual(
                list(hashes1.values()),
                list(hashes2.values()),
            )


if __name__ == "__main__":
    unittest.main()


class TestB03ActualSourceSchema(unittest.TestCase):
    @staticmethod
    def row(disposition="FIRST_PARTY_SOURCE", entry_point="scripts/synthetic_unmatched.py"):
        return {"consumer_id": "synthetic_schema_case", "entry_point": entry_point, "disposition": disposition, "blocker": "", "domain": "script", "activation_status": "active", "status": "EVIDENCED"}

    @staticmethod
    def transformed(row):
        pins = {".agent-receipts/udb-wave8-inputs/consumer-matrix.csv": "a" * 64}
        return adapter._transform_csv_row(row, pins, {})

    def test_real_header_disposition_is_not_a_status_alias(self):
        result = self.transformed(self.row(disposition="RETAINED_TEST_SOURCE"))
        self.assertEqual(result["x_disposition"], "excluded")
        self.assertEqual(result["status"], "PARTIAL")
        self.assertIn("CONSUMER_TYPE_NOT_PROVIDED_BY_SOURCE", result["unknowns"])

    def test_actual_schema_does_not_require_invented_consumer_type(self):
        adapter.validate_source_headers(["consumer_id", "entry_point", "disposition", "blocker"])
        with self.assertRaises(adapter.ContractValidationError):
            adapter.validate_source_headers(["consumer_id", "entry_point", "status", "blocker"])
        with self.assertRaises(adapter.ContractValidationError):
            adapter.validate_source_headers(["consumer_id", "entry_point", "disposition"])

    def test_missing_type_preserves_explicit_manual_pattern_and_unknown_fallback(self):
        result = self.transformed(self.row(entry_point="apps/backend-rag/backend/db/migrate.py"))
        self.assertEqual(result["x_manual_break_glass_class"], "manual_migration_cli")
        unmatched = self.transformed(self.row())
        self.assertEqual(unmatched["x_manual_break_glass_class"], "")
        self.assertIn("MANUAL_EXECUTION_UNRESOLVED", unmatched["unknowns"])

    def test_retained_test_never_becomes_manual_execution_candidate(self):
        result = self.transformed(self.row(disposition="RETAINED_TEST_SOURCE", entry_point="apps/backend-rag/backend/db/migrate.py"))
        self.assertEqual(result["x_disposition"], "excluded")
        self.assertEqual(result["x_manual_break_glass_class"], "")


class TestB03LeadDeltaSourceSchema(unittest.TestCase):
    @staticmethod
    def payload():
        return {"baseline_rows_preserved": 6029, "union_lead_rows": 6030, "additions": [{"consumer_id": "synthetic_delta_case", "blocker": "SYNTHETIC_UNRESOLVED_REASON"}], "blocker": "IGNORE_TOP_LEVEL_BLOCKER"}

    @staticmethod
    def transformed(payload):
        return adapter._build_lead_delta_row(payload, {".agent-receipts/udb-wave8-inputs/REAL-RUN-RECEIPT.json": "b" * 64})

    def test_actual_nested_addition_identity_and_blocker_are_preserved(self):
        row = self.transformed(self.payload())
        self.assertEqual(row["consumer_id"], "synthetic_delta_case")
        self.assertIn("SYNTHETIC_UNRESOLVED_REASON", row["unknowns"])
        self.assertNotIn("IGNORE_TOP_LEVEL_BLOCKER", row["unknowns"])

    def test_invented_flat_lead_id_is_not_accepted(self):
        with self.assertRaises(adapter.ContractValidationError):
            self.transformed({"lead_id": "synthetic_delta_case"})

    def test_delta_requires_exactly_one_valid_addition(self):
        bad = self.payload()
        bad["additions"] *= 2
        with self.assertRaises(adapter.ContractValidationError):
            self.transformed(bad)
        bad = self.payload()
        bad["additions"][0].pop("consumer_id")
        with self.assertRaises(adapter.ContractValidationError):
            self.transformed(bad)


class TestB03HermeticFixtures(unittest.TestCase):
    """The census is reproducible from committed files only: no gitignored .agent-receipts."""

    B03_DIR = Path(__file__).resolve().parent
    OUTPUTS = ("b03-consumer-census.csv", "b03-consumer-census.jsonl", "b03-census-summary.json")
    MANIFEST_REL = ".agent-receipts/udb-wave8-inputs/INPUT-MANIFEST.json"
    MATRIX_REL = ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv"

    @classmethod
    def setUpClass(cls) -> None:
        cls.auto_rows, cls.auto_summary = adapter.build_census_rows(REPO_ROOT)
        cls.fixture_rows, cls.fixture_summary = adapter.build_census_rows(
            REPO_ROOT, input_mode="fixtures"
        )

    @staticmethod
    def clean_root(tmp: str) -> Path:
        """A repo root holding ONLY the committed fixtures: what a clean checkout has."""
        root = Path(tmp)
        shutil.copytree(
            REPO_ROOT / adapter.FIXTURES_DIR_REL,
            root / adapter.FIXTURES_DIR_REL,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        return root

    @staticmethod
    def tamper(path: Path) -> None:
        """Change the logical content while keeping the file well-formed."""
        if path.suffix == ".gz":
            path.write_bytes(gzip.compress(gzip.decompress(path.read_bytes()) + b"\n"))
        else:
            path.write_bytes(path.read_bytes() + b"\n")

    def test_clean_checkout_reproduces_committed_outputs_byte_for_byte(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as out:
            root = self.clean_root(tmp)
            self.assertFalse((root / ".agent-receipts").exists())
            self.assertEqual(adapter.resolve_input_mode(root), "fixtures")
            rows, summary = adapter.build_census_rows(root)
            hashes = adapter.write_census_outputs(rows, summary, Path(out))
            for name in self.OUTPUTS:
                self.assertEqual(
                    hashes[str(Path(out) / name)],
                    adapter.compute_sha256(self.B03_DIR / name),
                    name,
                )
        disp = summary["disposition_counts"]
        self.assertEqual(
            [disp["excluded"], disp["duplicate"], disp["retired"], disp["active"], disp["unresolved"]],
            [1803, 43, 0, 0, 4184],
        )
        self.assertEqual(summary["active_consumer_denominator"], "UNKNOWN")

    def test_fixture_mode_matches_default_mode_row_for_row(self) -> None:
        self.assertEqual(self.fixture_rows, self.auto_rows)
        self.assertEqual(self.fixture_summary, self.auto_summary)

    def test_fixture_mode_hash_mismatch_refusal_and_verified_set(self) -> None:
        refused = (
            ".agent-receipts/udb-wave8-inputs/STATE.json",  # manifest-attested, never copied
            adapter.SUPPLEMENTARY_PRIOR_PATHS["source_index"],  # projection
            adapter.SUPPLEMENTARY_PRIOR_PATHS["jobs_mini"],  # byte-identical copy
            self.MATRIX_REL,  # projection
        )
        for rel in refused:
            with self.assertRaises(adapter.PinVerificationError, msg=rel):
                adapter.verify_pinned_inputs(
                    REPO_ROOT, extra_pins={rel: "0" * 64}, input_mode="fixtures"
                )
        verified = adapter.verify_pinned_inputs(REPO_ROOT, input_mode="fixtures")
        pins = {**adapter.PINNED_FROZEN_INPUTS, **adapter.PINNED_PRIOR_INPUTS}
        self.assertEqual({k: v for k, v in verified.items() if k in pins}, pins)
        self.assertEqual(verified[self.MANIFEST_REL], adapter.INPUT_MANIFEST_SHA256)
        self.assertEqual(len(verified), len(pins) + 1)

    def test_tampered_byte_identical_fixture_fails_closed(self) -> None:
        for rel in adapter.BYTE_IDENTICAL_FIXTURES:
            with tempfile.TemporaryDirectory() as tmp:
                root = self.clean_root(tmp)
                self.tamper(adapter.resolve_input_path(root, rel, "fixtures"))
                with self.assertRaises(adapter.PinVerificationError, msg=rel):
                    adapter.verify_pinned_inputs(root)

    def test_tampered_projection_or_provenance_fails_closed(self) -> None:
        for rel in adapter.PROJECTED_FIXTURES:
            with tempfile.TemporaryDirectory() as tmp:
                root = self.clean_root(tmp)
                self.tamper(adapter.resolve_input_path(root, rel, "fixtures"))
                with self.assertRaises(adapter.PinVerificationError, msg=rel):
                    adapter.verify_pinned_inputs(root)

        with tempfile.TemporaryDirectory() as tmp:
            root = self.clean_root(tmp)
            path = adapter.resolve_input_path(root, self.MATRIX_REL, "fixtures")
            path.write_bytes(path.read_bytes()[:-8])  # truncated gzip store
            with self.assertRaises(adapter.PinVerificationError):
                adapter.verify_pinned_inputs(root)

        edits = (
            ("entry", "source_sha256", "0" * 64),
            ("entry", "output_sha256", "0" * 64),
            ("entry", "kind", "byte_identical"),
            ("entry", "fixture", "other.csv"),
            ("top", "kind", "SOMETHING_ELSE"),
            ("drop", None, None),
        )
        for scope, field, value in edits:
            with tempfile.TemporaryDirectory() as tmp:
                root = self.clean_root(tmp)
                path = root / adapter.FIXTURES_DIR_REL / adapter.FIXTURE_PROVENANCE_NAME
                provenance = json.loads(path.read_text(encoding="utf-8"))
                entry = next(
                    e for e in provenance["fixtures"] if e["source_rel_path"] == self.MATRIX_REL
                )
                if scope == "entry":
                    entry[field] = value
                elif scope == "top":
                    provenance[field] = value
                else:
                    provenance["fixtures"].remove(entry)
                path.write_text(json.dumps(provenance), encoding="utf-8")
                with self.assertRaises(adapter.PinVerificationError, msg=(scope, field)):
                    adapter.verify_pinned_inputs(root)

    def test_present_but_incomplete_receipts_never_fall_back_to_fixtures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.clean_root(tmp)
            (root / adapter.RECEIPTS_INPUT_ROOT_REL).mkdir(parents=True)
            self.assertEqual(adapter.resolve_input_mode(root), "receipts")
            with self.assertRaises(adapter.PinVerificationError):
                adapter.build_census_rows(root)
            self.assertEqual(adapter.resolve_input_mode(root, "fixtures"), "fixtures")
        with self.assertRaises(ValueError):
            adapter.resolve_input_mode(REPO_ROOT, "both")

    def test_sanitizer_patterns_have_guilt_as_well_as_innocence(self) -> None:
        for name, sample in (
            ("absolute_user_home", "/Users/someone/x.py"),
            ("email", "a.b@example.com"),
            ("phone", "+62 812 3456 7890"),
            ("credential_value", "sk-" + "A" * 20),
            ("credential_value", "token=abcdefgh123"),
        ):
            self.assertGreater(fixture_tool.forbidden_matches(sample)[name], 0, sample)
        self.assertEqual(
            {k: v for k, v in fixture_tool.forbidden_matches("scripts/api_key_auth.py").items() if v},
            {},
        )

    def test_fixture_set_is_exact_pinned_minimal_and_sanitized(self) -> None:
        fixtures_dir = REPO_ROOT / adapter.FIXTURES_DIR_REL
        projected_names = {name for name, _pin in adapter.PROJECTED_FIXTURES.values()}
        data_files = set(adapter.BYTE_IDENTICAL_FIXTURES.values()) | projected_names
        on_disk = {p.name for p in fixtures_dir.iterdir() if p.name != "__pycache__"}
        self.assertEqual(
            on_disk,
            data_files | {adapter.FIXTURE_PROVENANCE_NAME, "build_fixtures.py"},
        )

        provenance = json.loads(
            (fixtures_dir / adapter.FIXTURE_PROVENANCE_NAME).read_text(encoding="utf-8")
        )
        self.assertEqual(
            provenance["kind"], "FROZEN_METADATA_TEST_FIXTURES_NOT_NEW_NATIVE_OBSERVATIONS"
        )
        self.assertEqual(adapter.FIXTURE_KIND, provenance["kind"])
        pins = {**adapter.PINNED_FROZEN_INPUTS, **adapter.PINNED_PRIOR_INPUTS}
        by_rel = {e["source_rel_path"]: e for e in provenance["fixtures"]}
        self.assertEqual(len(by_rel), len(provenance["fixtures"]))
        self.assertEqual(
            set(by_rel), set(adapter.BYTE_IDENTICAL_FIXTURES) | set(adapter.PROJECTED_FIXTURES)
        )
        self.assertEqual(
            provenance["manifest_attested_not_copied"], sorted(adapter.MANIFEST_ATTESTED_INPUTS)
        )
        # every pinned input is exactly one of: byte-identical copy, projection, manifest-attested
        copied = set(adapter.BYTE_IDENTICAL_FIXTURES) - {self.MANIFEST_REL}
        self.assertEqual(copied | set(adapter.PROJECTED_FIXTURES) | adapter.MANIFEST_ATTESTED_INPUTS, set(pins))
        self.assertFalse(copied & set(adapter.PROJECTED_FIXTURES))
        self.assertFalse((copied | set(adapter.PROJECTED_FIXTURES)) & adapter.MANIFEST_ATTESTED_INPUTS)

        for rel, name in adapter.BYTE_IDENTICAL_FIXTURES.items():
            expected = adapter.INPUT_MANIFEST_SHA256 if rel == self.MANIFEST_REL else pins[rel]
            entry = by_rel[rel]
            self.assertEqual(
                (entry["kind"], entry["source_sha256"], entry["output_sha256"]),
                ("byte_identical", expected, expected),
            )
            self.assertEqual(adapter.compute_content_sha256(fixtures_dir / name), expected)

        for rel, (name, fixture_pin) in adapter.PROJECTED_FIXTURES.items():
            entry = by_rel[rel]
            self.assertEqual(entry["kind"], "projection")
            self.assertEqual(entry["source_sha256"], pins[rel])
            self.assertEqual(entry["output_sha256"], fixture_pin)
            self.assertNotEqual(fixture_pin, pins[rel])
            self.assertEqual(adapter.compute_content_sha256(fixtures_dir / name), fixture_pin)
            self.assertEqual(adapter._projected_identity_sha(REPO_ROOT, rel), pins[rel])

        for name in sorted(data_files | {adapter.FIXTURE_PROVENANCE_NAME}):
            raw = (fixtures_dir / name).read_bytes()
            text = (gzip.decompress(raw) if name.endswith(".gz") else raw).decode("utf-8")
            hits = {k: v for k, v in fixture_tool.forbidden_matches(text).items() if v}
            self.assertEqual(hits, {}, name)

        matrix_name = adapter.PROJECTED_FIXTURES[self.MATRIX_REL][0]
        matrix_text = gzip.decompress((fixtures_dir / matrix_name).read_bytes()).decode("utf-8")
        header, _, body = matrix_text.partition("\n")
        self.assertEqual(tuple(header.split(",")), fixture_tool.MATRIX_COLUMNS)
        self.assertNotIn("consumer_type", header)
        self.assertNotIn("status", header.split(","))
        self.assertEqual(by_rel[self.MATRIX_REL]["rows"], 6029)
        self.assertEqual(body.count("\n"), 6029)
