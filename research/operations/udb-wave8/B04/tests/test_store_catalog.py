"""Unit tests for Block B04 physical store catalog & binding adapter.

Pure stdlib + pytest compatible. Zero imports from apps/backend-rag or third-party
packages, zero network calls, zero live DB/Qdrant/Redis connections.
Grounded in DUX-NOTE-CORRECTION.md and DUX-SCOPE-CORRECTION.md §3.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TEST_FILE = Path(__file__).resolve()
B04_DIR = TEST_FILE.parents[1]
REPO_ROOT = TEST_FILE.parents[5]

SPEC = importlib.util.spec_from_file_location(
    "b04_store_catalog", B04_DIR / "store_catalog.py"
)
assert SPEC is not None and SPEC.loader is not None
store_catalog = importlib.util.module_from_spec(SPEC)
sys.modules["b04_store_catalog"] = store_catalog
SPEC.loader.exec_module(store_catalog)


class TestB04StoreCatalog(unittest.TestCase):
    """Grounded verification suite for B04 store_catalog.py."""

    def test_a_input_manifest_string_mapping_and_pinned_hash_validation(self) -> None:
        """(a) Verify INPUT-MANIFEST.json filename->SHA256 string validation and fail-closed rejection on malformed, missing, or altered pins."""
        verified = store_catalog.verify_pinned_hashes(REPO_ROOT)
        self.assertGreaterEqual(len(verified), 26)

        with self.assertRaises(store_catalog.HashVerificationError):
            store_catalog.verify_pinned_hashes(
                REPO_ROOT,
                overrides={"REPORT.md": "0" * 64},
            )

        with self.assertRaises(store_catalog.HashVerificationError):
            store_catalog.verify_pinned_hashes(
                REPO_ROOT,
                overrides={
                    ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/QDRANT-METADATA.json": "deadbeef"
                },
            )

        malformed_string_manifest = {
            "files": {
                **store_catalog.PINNED_INPUT_MANIFEST_HASHES,
                "REPORT.md": "not-a-64-char-hex-digest",
            }
        }
        with self.assertRaises(store_catalog.HashVerificationError):
            store_catalog.verify_pinned_hashes(
                REPO_ROOT,
                manifest_data_override=malformed_string_manifest,
            )

        malformed_nested_dict_manifest = {
            "files": {
                **store_catalog.PINNED_INPUT_MANIFEST_HASHES,
                "REPORT.md": {
                    "sha256": store_catalog.PINNED_INPUT_MANIFEST_HASHES["REPORT.md"]
                },
            }
        }
        with self.assertRaises(store_catalog.HashVerificationError):
            store_catalog.verify_pinned_hashes(
                REPO_ROOT,
                manifest_data_override=malformed_nested_dict_manifest,
            )

        missing_entry_manifest = {
            "files": {
                k: v
                for k, v in store_catalog.PINNED_INPUT_MANIFEST_HASHES.items()
                if k != "REPORT.md"
            }
        }
        with self.assertRaises(store_catalog.HashVerificationError):
            store_catalog.verify_pinned_hashes(
                REPO_ROOT,
                manifest_data_override=missing_entry_manifest,
            )

    def test_b_qdrant_metadata_hashed_identity_list_and_collection_contract(self) -> None:
        """(b) Verify QDRANT-METADATA.json hashed identity list handling and verify_qdrant_collection_contract."""
        qdrant_meta_path = store_catalog.resolve_input_path(
            REPO_ROOT,
            ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/QDRANT-METADATA.json",
        )
        qdrant_meta = json.loads(qdrant_meta_path.read_text(encoding="utf-8"))
        self.assertIsInstance(qdrant_meta["collections"], list)

        parsed = store_catalog.parse_qdrant_metadata(qdrant_meta)
        self.assertEqual(parsed["collection_count"], 2)
        self.assertEqual(len(parsed["hashed_collections"]), 2)
        self.assertFalse(parsed["raw_collection_names_exported"])
        self.assertFalse(parsed["model_binding_proved"])
        self.assertFalse(parsed["live_dimension_mismatch_implied"])
        for obs in parsed["collection_observations"]:
            self.assertTrue(obs["identity_only"])
            self.assertFalse(obs["live_dimension_mismatch_implied"])
            self.assertEqual(obs["status"], "UNKNOWN")
            self.assertIsNone(obs["dimension_consistent"])
            self.assertFalse(obs["model_binding_proved"])

        with self.assertRaises(store_catalog.ContractValidationError):
            store_catalog.parse_qdrant_metadata({"collections": {"not": "a_list"}})
        with self.assertRaises(store_catalog.ContractValidationError):
            store_catalog.parse_qdrant_metadata({"collections": ["not-a-sha256-hash"]})

        unknown_contract = store_catalog.verify_qdrant_collection_contract(
            expected_dimension=1536,
            expected_distance="Cosine",
            observed_size=None,
        )
        self.assertEqual(unknown_contract["status"], "UNKNOWN")
        self.assertIsNone(unknown_contract["dimension_consistent"])
        self.assertFalse(unknown_contract["model_binding_proved"])

        conflict_contract = store_catalog.verify_qdrant_collection_contract(
            expected_dimension=1536,
            expected_distance="Cosine",
            observed_size=384,
            observed_distance="Cosine",
        )
        self.assertEqual(conflict_contract["status"], "CONFLICT")
        self.assertFalse(conflict_contract["dimension_consistent"])
        self.assertFalse(conflict_contract["model_binding_proved"])

        innocent_contract = store_catalog.verify_qdrant_collection_contract(
            expected_dimension=1536,
            expected_distance="Cosine",
            observed_size=1536,
            observed_distance="Cosine",
            observed_model=None,
        )
        self.assertEqual(innocent_contract["status"], "PARTIAL")
        self.assertTrue(innocent_contract["dimension_consistent"])
        self.assertFalse(innocent_contract["model_binding_proved"])

        static_discrepancies = store_catalog.detect_static_config_discrepancies(REPO_ROOT)
        self.assertEqual(len(static_discrepancies), 2)
        for item in static_discrepancies:
            self.assertEqual(
                item["proof_class"], "STATIC_SOURCE_DISCREPANCY_NOT_LIVE_PROOF"
            )
            self.assertTrue(item["verified_in_source"])

    def test_c_collection_registry_ast_exact_shape_and_synthetic_references(self) -> None:
        """(c) Verify real backend (11/18/11/21) and graph (16/9) AST registries, synthetic constant/shared-alias handling, and cross-registry conflict vs innocence."""
        backend_reg = store_catalog.parse_backend_collection_registry(REPO_ROOT)
        graph_reg = store_catalog.parse_graph_engine_collection_registry(REPO_ROOT)

        self.assertEqual(
            backend_reg.string_constants.get("SKILLS_MIRROR_COLLECTION"),
            "bali_zero_skills_hybrid",
        )
        self.assertEqual(backend_reg.canonical_logical_count, 11)
        self.assertIn("bali_zero_skills_hybrid", backend_reg.canonical_logical)
        self.assertEqual(backend_reg.logical_to_physical_count, 18)
        self.assertEqual(backend_reg.distinct_physical_count, 11)
        self.assertEqual(backend_reg.aliases_count, 21)
        self.assertEqual(len(backend_reg.distinct_alias_targets), 11)
        self.assertEqual(
            set(backend_reg.shared_physical_targets.keys()),
            {"legal_unified_hybrid_hybrid", "tax_genius_hybrid"},
        )
        self.assertEqual(
            len(backend_reg.shared_physical_targets["tax_genius_hybrid"]), 4
        )
        self.assertEqual(
            len(backend_reg.shared_physical_targets["legal_unified_hybrid_hybrid"]), 5
        )

        self.assertEqual(
            graph_reg.string_constants.get("DEFAULT_COLLECTION"), "legal_unified"
        )
        self.assertEqual(graph_reg.canonical_logical_count, 0)
        self.assertEqual(graph_reg.logical_to_physical_count, 16)
        self.assertEqual(graph_reg.distinct_physical_count, 9)
        self.assertEqual(graph_reg.aliases_count, 0)

        synthetic_src = """
from typing import Final
SHARED_TARGET: Final[str] = "physical_shared_v1"
SOLO_KEY = "logical_solo"
SOLO_TARGET = "physical_solo_v1"

CANONICAL_LOGICAL_COLLECTIONS: Final[tuple[str, ...]] = (
    "logical_a",
    SOLO_KEY,
)

LOGICAL_TO_PHYSICAL_COLLECTIONS: Final[dict[str, str]] = {
    "logical_a": SHARED_TARGET,
    "logical_b": SHARED_TARGET,
    "logical_c": "physical_shared_v1",
    SOLO_KEY: SOLO_TARGET,
}

CANONICAL_COLLECTION_ALIASES: Final[dict[str, str]] = {
    "logical_a": "logical_a",
    "logical_b": "logical_a",
    "logical_c": "logical_a",
    SOLO_KEY: SOLO_KEY,
    SHARED_TARGET: "logical_a",
}
"""
        syn_report = store_catalog.parse_collection_registry_source(
            synthetic_src, module_path="<synthetic>"
        )
        self.assertEqual(syn_report.canonical_logical_count, 2)
        self.assertEqual(syn_report.logical_to_physical_count, 4)
        self.assertEqual(syn_report.distinct_physical_count, 2)
        self.assertEqual(syn_report.aliases_count, 5)
        self.assertEqual(
            syn_report.shared_physical_targets,
            {"physical_shared_v1": ("logical_a", "logical_b", "logical_c")},
        )

        bad_synthetic_src = """
LOGICAL_TO_PHYSICAL_COLLECTIONS = {
    "logical_a": UNDEFINED_CONSTANT_NAME,
}
"""
        with self.assertRaises(store_catalog.ContractValidationError):
            store_catalog.parse_collection_registry_source(
                bad_synthetic_src, module_path="<bad_synthetic>"
            )

        cross_reg = store_catalog.detect_cross_registry_conflicts(REPO_ROOT)
        self.assertEqual(
            cross_reg["comparisons"]["balizero_news"]["status"], "CONFLICT"
        )
        self.assertEqual(
            cross_reg["comparisons"]["balizero_news"]["backend_physical"],
            "balizero_news",
        )
        self.assertEqual(
            cross_reg["comparisons"]["balizero_news"]["graph_engine_physical"],
            "intel_authoritative_sources",
        )
        self.assertEqual(
            cross_reg["comparisons"]["kbli_2025_final"]["status"], "PARTIAL"
        )
        self.assertEqual(
            cross_reg["comparisons"]["kbli_2025_final"]["backend_physical"],
            "kbli_2025_final_hybrid",
        )
        self.assertEqual(
            cross_reg["comparisons"]["kbli_2025_final"]["graph_engine_physical"],
            "kbli_2025_final_hybrid",
        )
        self.assertEqual(
            cross_reg["only_in_backend_rag"],
            ["bali_zero_skills_hybrid", "curated_qa", "nlm_shadow_hybrid"],
        )
        self.assertEqual(cross_reg["only_in_graph_engine"], ["v6_cache_vectors"])

    def test_d_writer_flat_payload_vs_reader_set_and_defects_d1_through_d6(self) -> None:
        """(d) Verify KBLI writer flat layout (kode/kode_kbli/kode_kbli_2025) vs reader _FLAT_PAYLOAD_COLLECTIONS omission (CONFLICT) and curated_qa innocence."""
        flat_report = store_catalog.detect_writer_reader_flat_payload_status(REPO_ROOT)
        self.assertEqual(
            flat_report["reader_flat_payload_collections"],
            ["curated_qa", "legal_unified", "tax_genius"],
        )

        kbli_entry = flat_report["collections"]["kbli_2025_final"]
        self.assertTrue(kbli_entry["writer_flat_payload"])
        self.assertEqual(
            kbli_entry["writer_code_keys"], ["kode", "kode_kbli", "kode_kbli_2025"]
        )
        self.assertFalse(kbli_entry["emits_legacy_code_key"])
        self.assertFalse(kbli_entry["in_qdrant_db_flat_payload_set"])
        self.assertEqual(kbli_entry["status"], "CONFLICT")

        curated_entry = flat_report["collections"]["curated_qa"]
        self.assertTrue(curated_entry["writer_flat_payload"])
        self.assertTrue(curated_entry["in_qdrant_db_flat_payload_set"])
        self.assertEqual(curated_entry["status"], "PARTIAL")

        defects = store_catalog.detect_defect_evidence(REPO_ROOT)
        self.assertEqual(set(defects.keys()), {"D1", "D2", "D3", "D4", "D5", "D6"})
        for defect_id, info in defects.items():
            self.assertTrue(
                info["verified"], f"Defect {defect_id} failed static verification"
            )

    def test_e_notebook_container_exclusion_and_consumer_id_membership(self) -> None:
        """(e) Verify 67 NOTEBOOK_CONTAINER_REFERENCE rows are excluded from DB consumer denominators while real postgresql rows are kept, and fabricated IDs are rejected."""
        csv_path = store_catalog.resolve_input_path(
            REPO_ROOT, ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv"
        )
        notebook_rows = []
        pg_src_rows = []
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if not store_catalog.is_database_consumer_candidate(row):
                    notebook_rows.append(row)
                elif (
                    row["consumer_id"].startswith("src_")
                    and row.get("store") == "postgresql"
                ):
                    pg_src_rows.append(row)

        self.assertEqual(len(notebook_rows), 67)
        self.assertGreater(len(pg_src_rows), 0)
        self.assertTrue(store_catalog.is_database_consumer_candidate(pg_src_rows[0]))

        valid_ids = store_catalog.load_valid_consumer_ids(REPO_ROOT)
        self.assertEqual(len(valid_ids), 6029)
        self.assertTrue(
            store_catalog.validate_consumer_id(pg_src_rows[0]["consumer_id"], valid_ids)
        )

        for fabricated in (
            "repo_0e2c9f158a76731f",
            "repo_5d54fa59301e6b3f",
            "repo_e4964f782237c1df",
            "nonexistent_consumer_12345",
        ):
            with self.assertRaises(store_catalog.ContractValidationError):
                store_catalog.validate_consumer_id(fabricated, valid_ids)

    def test_f_store_bindings_eight_column_contract_and_store_id_grammar(self) -> None:
        """(f) Verify store-bindings.csv 8-column header/schema and canonical store_id grammar."""
        for valid_sid in (
            "pg:fly:sha8-2bb691c3/public",
            "pg:pro:localhost-5432/public",
            "qdrant:pro:localhost-6333",
            "qdrant:pro:sha8-89ce6e19",
            "redis:pro:localhost-6379/db0",
            "redis:mini:localhost-6379/db0",
            "sqlite:pro:local-sqlite",
            "graph:fly:sha8-2bb691c3/kg_tables",
            "object:gdrive:google-drive-api",
            "sheet:gcloud:google-sheets-api",
            "file:unknown:local-filesystem",
            "browser:client:web-storage",
            "unknown:unknown:unknown",
        ):
            self.assertTrue(store_catalog.validate_store_id(valid_sid))

        for bad_sid in (
            "store:postgres:fly_prod",
            "pg:local:nuzantara_dev",
            "postgres:fly:nuzantara-postgres",
            "qdrant:pro:UPPERCASE",
            "",
        ):
            with self.assertRaises(store_catalog.ContractValidationError):
                store_catalog.validate_store_id(bad_sid)

        valid_ids = store_catalog.load_valid_consumer_ids(REPO_ROOT)
        rows = store_catalog.build_store_bindings(REPO_ROOT)
        self.assertEqual(len(rows), 6029)

        for row in rows:
            self.assertEqual(tuple(row.keys()), store_catalog.BINDING_COLUMNS)
            self.assertEqual(row["operation_id"], "UNASSIGNED_B05")
            self.assertIn("OPERATION_ID_PENDING_B05", row["unknowns"])
            self.assertIn(row["status"], store_catalog.ALLOWED_STATUSES)
            store_catalog.validate_binding_row(row, valid_ids)

        bad_extra_col = dict(rows[0])
        bad_extra_col["extra_column"] = "disallowed"
        with self.assertRaises(store_catalog.ContractValidationError):
            store_catalog.validate_binding_row(bad_extra_col, valid_ids)

        bad_status = dict(rows[0])
        bad_status["status"] = "NOT_DATABASE_CONSUMER"
        with self.assertRaises(store_catalog.ContractValidationError):
            store_catalog.validate_binding_row(bad_status, valid_ids)

    def test_g_pii_email_phone_dsn_boundary_and_artifact_generation(self) -> None:
        """(g) Verify zero raw DSNs, emails, phones, user paths, or secrets in generated artifacts and fail-closed boundary rejection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_paths = store_catalog.write_artifacts(REPO_ROOT, Path(tmpdir))
            catalog_text = out_paths["store_catalog_json"].read_text(encoding="utf-8")
            bindings_text = out_paths["store_bindings_csv"].read_text(encoding="utf-8")

            self.assertTrue(store_catalog.scan_no_secrets_or_pii(catalog_text))
            self.assertTrue(store_catalog.scan_no_secrets_or_pii(bindings_text))

            catalog_data = json.loads(catalog_text)
            self.assertFalse(catalog_data["qdrant_model_binding_proved"])
            self.assertEqual(
                catalog_data["consumer_denominators"][
                    "excluded_non_db_notebook_container_rows"
                ],
                67,
            )
            self.assertEqual(
                catalog_data["consumer_denominators"][
                    "database_consumer_candidate_rows"
                ],
                5962,
            )
            self.assertEqual(
                catalog_data["qdrant_registries"]["backend_rag"][
                    "canonical_logical_count"
                ],
                11,
            )
            self.assertEqual(
                catalog_data["qdrant_registries"]["backend_rag"][
                    "logical_to_physical_count"
                ],
                18,
            )
            self.assertEqual(
                catalog_data["qdrant_registries"]["backend_rag"][
                    "distinct_physical_count"
                ],
                11,
            )
            self.assertEqual(
                catalog_data["qdrant_registries"]["backend_rag"]["aliases_count"],
                21,
            )
            self.assertEqual(
                catalog_data["qdrant_registries"]["graph_engine"][
                    "logical_to_physical_count"
                ],
                16,
            )
            self.assertEqual(
                catalog_data["qdrant_registries"]["graph_engine"][
                    "distinct_physical_count"
                ],
                9,
            )

            with out_paths["store_bindings_csv"].open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                reader = csv.reader(handle)
                header = next(reader)
                self.assertEqual(tuple(header), store_catalog.BINDING_COLUMNS)

        for forbidden_sample in (
            "postgresql://backend_rag_user:secret@localhost:5432/nuzantara_dev",
            "redis://:password@localhost:6379/0",
            "/Users/nuzantara/Desktop/secret.json",
            "Contact info@balizero.com for details",
            "Call +62 821 3465 159 now",
            "openai_api_key = 'sk-proj1234567890abcdef'",
        ):
            with self.assertRaises(store_catalog.ContractValidationError):
                store_catalog.scan_no_secrets_or_pii(forbidden_sample)


HERMETIC_SOURCE_FILES = tuple(store_catalog.PINNED_SOURCE_FILE_HASHES) + (
    "apps/graph-engine/src/nuzantara_graph/services/collection_registry.py",
    "apps/bali-intel-scraper/scripts/load_intel_sources.py",
    "apps/backend-rag/backend/scripts/reindex_kbli_2025_final.py",
)
# Digests of the artifacts the frozen adapter wrote in the isolated regeneration
# (ISOLATED-REGENERATION-RECEIPT.json); the hermetic path must reproduce them byte for byte.
PINNED_ARTIFACT_SHA256 = {
    "store_catalog_json": "2b9c7d6492e8689dadc924e868f5f3548d48622db2561bae03cbacd4648c89e4",
    "store_bindings_csv": "712e98d987c4c1c38533e2bbbbd3f93366735d031219b107113a2971e6e29582",
}
CONSUMER_MATRIX = ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv"
LIVE_DB = ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LIVE-DB-METADATA.json"
QDRANT = ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/QDRANT-METADATA.json"
POOL_FACTORY = ".agent-receipts/udb-wave8-inputs-dux/prior/advance-20261013-1640/POOL-FACTORY-SOURCE.json"


class TestB04HermeticFixtures(unittest.TestCase):
    """B04 reproduces from committed files only: no `.agent-receipts/` in the scratch root."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.root = self.tmp / "root"
        for rel in HERMETIC_SOURCE_FILES:
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO_ROOT / rel, target)
        shutil.copytree(
            REPO_ROOT / store_catalog.FIXTURE_DIR_REL,
            self.root / store_catalog.FIXTURE_DIR_REL,
        )
        self.fixtures = self.root / store_catalog.FIXTURE_DIR_REL

    def test_h_checkout_without_receipts_uses_fixtures_and_reproduces_pinned_artifacts(self) -> None:
        """(h) A root with no receipts selects fixtures, keeps every pin and writes the pinned artifacts."""
        self.assertFalse((self.root / ".agent-receipts").exists())
        self.assertEqual(store_catalog.input_source_mode(self.root), "fixtures")

        verified = store_catalog.verify_pinned_hashes(self.root)
        self.assertGreaterEqual(len(verified), 26)
        self.assertEqual(
            verified[CONSUMER_MATRIX],
            store_catalog.PINNED_INPUT_MANIFEST_HASHES["consumer-matrix.csv"],
        )
        for rel, expected in store_catalog.PINNED_DUX_DOC_HASHES.items():
            self.assertEqual(verified[rel], expected)

        paths = store_catalog.write_artifacts(self.root, self.tmp / "hermetic-out")
        for key, expected in PINNED_ARTIFACT_SHA256.items():
            self.assertEqual(store_catalog.compute_sha256(paths[key]), expected)

        # Whatever mode REPO_ROOT is in (receipts here, fixtures in a clean checkout) the
        # artifacts it writes are byte-identical to the hermetic ones.
        reference = store_catalog.write_artifacts(REPO_ROOT, self.tmp / "reference-out")
        for key in PINNED_ARTIFACT_SHA256:
            self.assertEqual(paths[key].read_bytes(), reference[key].read_bytes())

    def test_i_projection_and_digest_only_inputs_never_claim_the_source_bytes(self) -> None:
        """(i) Projections carry a different digest than their source; digest-only inputs carry no content."""
        kinds = store_catalog.pinned_input_identity_kinds(self.root)
        self.assertEqual(len(kinds), 18)
        self.assertEqual(kinds[CONSUMER_MATRIX], store_catalog.IDENTITY_PROJECTION)
        self.assertEqual(kinds[LIVE_DB], store_catalog.IDENTITY_PROJECTION)
        self.assertEqual(kinds[POOL_FACTORY], store_catalog.IDENTITY_DIGEST_ONLY)
        self.assertEqual(kinds[QDRANT], store_catalog.IDENTITY_BYTE_IDENTICAL)
        for rel in store_catalog.PINNED_DUX_DOC_HASHES:
            self.assertEqual(kinds[rel], store_catalog.IDENTITY_DIGEST_ONLY)

        provenance = json.loads((self.fixtures / "PROVENANCE.json").read_text(encoding="utf-8"))
        self.assertEqual(provenance["kind"], store_catalog.FIXTURE_KIND)
        carried = set()
        for entry in provenance["entries"]:
            self.assertEqual(entry["kind"], store_catalog.FIXTURE_KIND)
            if entry["identity"] == store_catalog.IDENTITY_PROJECTION:
                self.assertNotEqual(entry["output_sha256"], entry["source_sha256"])
                self.assertIsNotNone(entry["projection"])
            elif entry["identity"] == store_catalog.IDENTITY_DIGEST_ONLY:
                self.assertIsNone(entry["fixture_rel"])
                self.assertIsNone(entry["output_sha256"])
            else:
                self.assertEqual(entry["output_sha256"], entry["source_sha256"])
            if entry["fixture_rel"]:
                carried.add(entry["fixture_rel"])
        on_disk = {
            p.relative_to(self.fixtures).as_posix() for p in self.fixtures.rglob("*") if p.is_file()
        }
        self.assertEqual(on_disk, carried | {"PROVENANCE.json"})

        with self.assertRaises(store_catalog.HashVerificationError):
            store_catalog.resolve_input_path(self.root, POOL_FACTORY)

        matrix = next(e for e in provenance["entries"] if e["source_rel"] == CONSUMER_MATRIX)
        self.assertEqual(
            matrix["projection"]["columns"], list(store_catalog.CONSUMER_MATRIX_PROJECTED_COLUMNS)
        )
        self.assertEqual(matrix["projection"]["rows"], 6029)
        for path in self.fixtures.rglob("*"):
            if path.is_file():
                self.assertTrue(store_catalog.scan_no_secrets_or_pii(path.read_text(encoding="utf-8")))

    def _assert_tamper_rejected(self, rel: str, mutate) -> None:
        path = self.fixtures / rel
        original = path.read_bytes()
        try:
            path.write_bytes(mutate(original))
            with self.assertRaises(store_catalog.HashVerificationError):
                store_catalog.verify_pinned_hashes(self.root)
        finally:
            path.write_bytes(original)
        self.assertGreaterEqual(len(store_catalog.verify_pinned_hashes(self.root)), 26)

    def test_j_fixture_tampering_and_pin_overrides_are_rejected(self) -> None:
        """(j) A tampered copy, projection or provenance file, a missing fixture and a wrong pin all fail closed."""
        self._assert_tamper_rejected(
            "udb-wave8-inputs-dux/prior/completion-20261015-0831/QDRANT-METADATA.json",
            lambda data: data + b" ",
        )
        self._assert_tamper_rejected("udb-wave8-inputs/INPUT-MANIFEST.json", lambda data: data + b"\n")
        self._assert_tamper_rejected("udb-wave8-inputs/STATE.json", lambda data: data + b"x")
        self._assert_tamper_rejected(
            "udb-wave8-inputs/consumer-matrix.projection.csv",
            lambda data: data.replace(b"postgresql", b"postgresqx", 1),
        )
        self._assert_tamper_rejected(
            "udb-wave8-inputs-dux/prior/completion-20261015-0831/LIVE-DB-METADATA.projection.json",
            lambda data: data.replace(b"557", b"558", 1),
        )
        self._assert_tamper_rejected(
            "PROVENANCE.json",
            lambda data: data.replace(b'"source_bytes": 278275', b'"source_bytes": 278276', 1),
        )

        missing = self.fixtures / "udb-wave8-inputs/consumer-matrix.projection.csv"
        original = missing.read_bytes()
        missing.unlink()
        try:
            with self.assertRaises(store_catalog.HashVerificationError):
                store_catalog.load_valid_consumer_ids(self.root)
        finally:
            missing.write_bytes(original)

        for rel, wrong_pin in (
            (CONSUMER_MATRIX, "0" * 64),
            (".agent-receipts/udb-wave8-dux/CONTRACT-CONVENTIONS.md", "0" * 64),
            (LIVE_DB, "deadbeef"),
            (POOL_FACTORY, "deadbeef"),
            (QDRANT, "deadbeef"),
        ):
            with self.assertRaises(store_catalog.HashVerificationError):
                store_catalog.verify_pinned_hashes(self.root, overrides={rel: wrong_pin})

    def test_k_projected_identity_check_rejects_a_reshaped_projection(self) -> None:
        """(k) The separate projected-identity check rejects a dropped row, an extra column and a changed leaf set."""
        entries = {
            e["source_rel"]: e
            for e in json.loads((self.fixtures / "PROVENANCE.json").read_text(encoding="utf-8"))[
                "entries"
            ]
        }
        matrix_entry = entries[CONSUMER_MATRIX]
        matrix_path = self.fixtures / matrix_entry["fixture_rel"]
        store_catalog.verify_fixture_projection(matrix_path, matrix_entry)

        lines = matrix_path.read_text(encoding="utf-8").splitlines(keepends=True)
        candidates = {
            "dropped_row": "".join(lines[:-1]),
            "extra_column": lines[0].rstrip("\n") + ",extra\n" + "".join(lines[1:]),
        }
        for name, text in candidates.items():
            broken = self.tmp / f"{name}.csv"
            broken.write_text(text, encoding="utf-8")
            with self.assertRaises(store_catalog.HashVerificationError, msg=name):
                store_catalog.verify_fixture_projection(broken, matrix_entry)

        live_entry = entries[LIVE_DB]
        live_path = self.fixtures / live_entry["fixture_rel"]
        store_catalog.verify_fixture_projection(live_path, live_entry)
        reshaped = self.tmp / "reshaped.json"
        reshaped.write_text(json.dumps({"native_metadata": {"summary": {"actors": 13}}}))
        with self.assertRaises(store_catalog.HashVerificationError):
            store_catalog.verify_fixture_projection(reshaped, live_entry)

    def test_l_partial_receipts_fail_closed_and_unrelated_receipts_are_ignored(self) -> None:
        """(l) A partial campaign receipts tree never falls back to fixtures; an unrelated one is ignored."""
        (self.root / ".agent-receipts" / "unrelated-campaign").mkdir(parents=True)
        self.assertEqual(store_catalog.input_source_mode(self.root), "fixtures")
        self.assertGreaterEqual(len(store_catalog.verify_pinned_hashes(self.root)), 26)

        (self.root / ".agent-receipts" / "udb-wave8-inputs").mkdir()
        self.assertEqual(store_catalog.input_source_mode(self.root), "receipts")
        with self.assertRaises(store_catalog.HashVerificationError):
            store_catalog.verify_pinned_hashes(self.root)
        with self.assertRaises(FileNotFoundError):
            store_catalog.load_valid_consumer_ids(self.root)

    def test_m_fixtures_are_the_exact_regeneration_of_the_receipts_when_present(self) -> None:
        """(m) With receipts, regenerating the fixtures reproduces the committed files byte for byte."""
        regenerated_dir = self.tmp / "regenerated"
        if store_catalog.input_source_mode(REPO_ROOT) == "receipts":
            store_catalog.regenerate_fixtures(REPO_ROOT, regenerated_dir)
            committed = REPO_ROOT / store_catalog.FIXTURE_DIR_REL
            regenerated_files = {
                p.relative_to(regenerated_dir).as_posix(): p.read_bytes()
                for p in regenerated_dir.rglob("*")
                if p.is_file()
            }
            committed_files = {
                p.relative_to(committed).as_posix(): p.read_bytes()
                for p in committed.rglob("*")
                if p.is_file()
            }
            self.assertEqual(regenerated_files, committed_files)
        else:
            self.assertEqual(store_catalog.input_source_mode(REPO_ROOT), "fixtures")
            with self.assertRaises(store_catalog.HashVerificationError):
                store_catalog.regenerate_fixtures(REPO_ROOT, regenerated_dir)
        provenance_sha = store_catalog.compute_sha256(self.fixtures / "PROVENANCE.json")
        self.assertEqual(provenance_sha, store_catalog.PINNED_FIXTURE_PROVENANCE_SHA256)


if __name__ == "__main__":
    unittest.main()


def test_r2_static_hint_keeps_frozen_platform_grammar_and_unknowns():
    row = {"consumer_id": "synthetic_r2_case", "entry_point": "synthetic/upload_r2_asset.py", "store": "object_storage", "disposition": "REQUIRES_REVIEW"}
    binding = store_catalog.classify_consumer_store_binding(row, consumer_csv_sha256="a"*64, live_db_sha256="b"*64, qdrant_meta_sha256="c"*64, pool_factory_sha256="d"*64)
    assert binding["store_id"] == "object:unknown:cloudflare-r2"
    assert binding["status"] == "PARTIAL"
    assert {"STATIC_SOURCE_ONLY", "R2_BUCKET_UNOBSERVED", "STORE_PLATFORM_UNRESOLVED"}.issubset(set(binding["unknowns"].split(";")))
    assert store_catalog.validate_store_id(binding["store_id"])
    catalog = store_catalog.build_store_catalog(REPO_ROOT)
    r2 = next(store for store in catalog["stores"] if store["instance"] == "cloudflare-r2")
    assert r2["store_id"] == binding["store_id"]
    assert r2["platform"] == "unknown"
    assert {"STATIC_SOURCE_ONLY", "R2_BUCKET_UNOBSERVED", "STORE_PLATFORM_UNRESOLVED"}.issubset(set(r2["unknowns"]))
    try:
        store_catalog.validate_store_id("object:external:cloudflare-r2")
    except store_catalog.ContractValidationError:
        pass
    else:
        raise AssertionError("invented external platform must remain invalid")



class TestB04OutputBoundary(unittest.TestCase):
    """Synthetic rejection paths must neither disclose nor publish rejected values."""

    @staticmethod
    def _samples():
        marker = "synthetic_boundary_probe"
        return (
            "redis" + "://" + marker,
            "/" + "Users/" + marker,
            marker + chr(64) + "example.invalid",
            "+" + "123 456 789 0123",
            "api" + "_key = '" + marker + "'",
        )

    @staticmethod
    def _binding():
        return dict(zip(store_catalog.BINDING_COLUMNS, (
            "synthetic_consumer", store_catalog.OPERATION_ID_SENTINEL,
            "postgres:unknown:synthetic", "PARTIAL",
            store_catalog.OPERATION_ID_PENDING_TOKEN, "synthetic:v1",
            "2026-10-16T00:00:00Z", "a" * 64,
        )))

    def test_n_rejection_exception_messages_contain_fixed_codes_only(self):
        import ast
        for index, sample in enumerate(self._samples()):
            with self.subTest(category=index):
                with self.assertRaises(store_catalog.ContractValidationError) as caught:
                    store_catalog.scan_no_secrets_or_pii(sample)
                self.assertEqual(str(caught.exception), "B04_OUTPUT_BOUNDARY_REJECTED")
                self.assertNotIn(sample, str(caught.exception))
        sample = self._samples()[2]
        cases = [
            lambda: store_catalog.validate_store_id(sample),
            lambda: store_catalog.validate_consumer_id(sample, set()),
            lambda: store_catalog.parse_qdrant_metadata({"collections": [sample]}),
            lambda: store_catalog._resolve_ast_string(ast.Name(id=sample), {}, sample),
            lambda: store_catalog._resolve_ast_string(ast.Constant(value=1), {}, sample),
            lambda: store_catalog.verify_pinned_hashes(
                REPO_ROOT, overrides={"REPORT.md": sample}),
            lambda: store_catalog.verify_pinned_hashes(
                REPO_ROOT, manifest_data_override={"files": {
                    **store_catalog.PINNED_INPUT_MANIFEST_HASHES, "REPORT.md": sample}}),
        ]
        for field in ("operation_id", "status", "evidence_sha256"):
            row = self._binding()
            row[field] = sample
            cases.append(lambda row=row: store_catalog.validate_binding_row(
                row, {"synthetic_consumer"}))
        malformed = self._binding()
        malformed[sample] = malformed.pop("status")
        cases.append(lambda: store_catalog.validate_binding_row(
            malformed, {"synthetic_consumer"}))
        for index, reject in enumerate(cases):
            with self.subTest(path=index):
                with self.assertRaises(
                    (store_catalog.ContractValidationError, store_catalog.HashVerificationError)
                ) as caught:
                    reject()
                self.assertRegex(str(caught.exception), r"^B04_[A-Z0-9_]+$")
                self.assertNotIn(sample, str(caught.exception))

    def test_o_boundary_rejection_never_creates_or_replaces_either_target(self):
        from unittest.mock import patch
        for index, sample in enumerate(self._samples()):
            for destination in ("catalog", "bindings"):
                for state in ("absent", "empty", "existing"):
                    with self.subTest(category=index, destination=destination, state=state):
                        with tempfile.TemporaryDirectory() as tmp:
                            output = Path(tmp) / "output"
                            if state != "absent":
                                output.mkdir()
                            if state == "existing":
                                (output / "store-catalog.json").write_bytes(b"old catalog\n")
                                (output / "store-bindings.csv").write_bytes(b"old bindings\n")
                                (output / "unrelated").write_bytes(b"keep\n")
                            before = {
                                str(p.relative_to(Path(tmp))): p.read_bytes()
                                for p in Path(tmp).rglob("*") if p.is_file()
                            }
                            catalog = {"synthetic": sample if destination == "catalog" else "safe"}
                            binding = self._binding()
                            if destination == "bindings":
                                binding["source_version"] = sample
                            with (
                                patch.object(store_catalog, "build_store_catalog", return_value=catalog),
                                patch.object(store_catalog, "build_store_bindings", return_value=[binding]),
                                patch.object(Path, "mkdir", side_effect=AssertionError("publication attempted")),
                                patch.object(Path, "write_text", side_effect=AssertionError("publication attempted")),
                            ):
                                with self.assertRaises(store_catalog.ContractValidationError) as caught:
                                    store_catalog.write_artifacts(REPO_ROOT, output)
                            self.assertEqual(str(caught.exception), "B04_OUTPUT_BOUNDARY_REJECTED")
                            self.assertEqual(output.exists(), state != "absent")
                            after = {
                                str(p.relative_to(Path(tmp))): p.read_bytes()
                                for p in Path(tmp).rglob("*") if p.is_file()
                            }
                            self.assertEqual(before, after)

    def test_p_serializer_errors_are_sanitized_before_any_publication(self):
        from unittest.mock import patch
        sample = self._samples()[2]
        extra_key = self._binding()
        extra_key[sample] = "unexpected column"
        unencodable = self._binding()
        unencodable["source_version"] = chr(0xD800)
        cases = (
            ({"safe": True}, [extra_key]),
            ({"safe": True}, [unencodable]),
            ({"invalid": object()}, [self._binding()]),
        )
        for index, (catalog, bindings) in enumerate(cases):
            for preexisting in (False, True):
                with self.subTest(serializer=index, preexisting=preexisting):
                    with tempfile.TemporaryDirectory() as tmp:
                        output = Path(tmp) / "output"
                        if preexisting:
                            output.mkdir()
                            (output / "store-catalog.json").write_bytes(b"old catalog\n")
                            (output / "store-bindings.csv").write_bytes(b"old bindings\n")
                        before = {p.name: p.read_bytes() for p in output.glob("*")}
                        with (
                            patch.object(store_catalog, "build_store_catalog", return_value=catalog),
                            patch.object(store_catalog, "build_store_bindings", return_value=bindings),
                            patch.object(Path, "mkdir") as mkdir,
                            patch.object(Path, "write_bytes") as write_bytes,
                            patch.object(Path, "write_text") as write_text,
                        ):
                            with self.assertRaises(store_catalog.ContractValidationError) as caught:
                                store_catalog.write_artifacts(REPO_ROOT, output)
                        self.assertEqual(str(caught.exception), "B04_ARTIFACT_PREPARATION_FAILED")
                        self.assertNotIn(sample, str(caught.exception))
                        mkdir.assert_not_called()
                        write_bytes.assert_not_called()
                        write_text.assert_not_called()
                        self.assertEqual(output.exists(), preexisting)
                        self.assertEqual(before, {p.name: p.read_bytes() for p in output.glob("*")})

    def test_q_cli_stderr_does_not_echo_rejected_values_or_tracebacks(self):
        import subprocess
        wrapper = """
import importlib.util, pathlib, sys
p = pathlib.Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("b04_boundary_cli", p)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
sample = bytes.fromhex(sys.argv[2]).decode()
destination = sys.argv[3]
m.build_store_catalog = lambda _: {"synthetic": sample if destination == "catalog" else "safe"}
row = dict.fromkeys(m.BINDING_COLUMNS, "safe")
row["source_version"] = sample if destination == "bindings" else "safe"
m.build_store_bindings = lambda _: [row]
if destination == "unexpected":
    def reject(_):
        raise ValueError(sample)
    m.write_artifacts = reject
raise SystemExit(m.main())
"""
        with tempfile.TemporaryDirectory() as tmp:
            module = Path(tmp) / "research/operations/udb-wave8/B04/store_catalog.py"
            module.parent.mkdir(parents=True)
            shutil.copyfile(B04_DIR / "store_catalog.py", module)
            for index, sample in enumerate(self._samples()):
                for destination in ("catalog", "bindings", "unexpected"):
                    with self.subTest(category=index, destination=destination):
                        result = subprocess.run(
                            [sys.executable, "-I", "-B", "-c", wrapper, str(module),
                             sample.encode().hex(), destination],
                            capture_output=True, text=True, check=False, timeout=15,
                        )
                        self.assertEqual(result.returncode, 2)
                        self.assertEqual(result.stdout, "")
                        self.assertEqual(result.stderr, "B04_ARTIFACT_GENERATION_REJECTED\n")
                        self.assertNotIn(sample, result.stdout + result.stderr)
                        self.assertFalse((module.parent / "store-catalog.json").exists())
                        self.assertFalse((module.parent / "store-bindings.csv").exists())
