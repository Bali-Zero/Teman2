"""Unit and negative tests for B03 deterministic consumer census adapter."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import b03_census_adapter as adapter  # noqa: E402


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
        bad_row = dict(self.rows_by_id["NOTEBOOK-CONTAINER-REFERENCE-NLM-1ff5e127b174"])
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
