"""Tests for the immutable architecture-review packet builder.

The packet is a review input, not a convenience prompt.  These tests pin the
load-bearing properties: Git-object sourcing, deterministic framing, strict
round-trip validation, and projection stability across evidence-only commits.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

from scripts import freeze_worker_plane_review as packet


REVIEW_PATHS = tuple(f"docs/review-{index}.md" for index in range(1, 10))
BRIEF_PATH = "docs/review-brief.md"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def review_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Packet Test")
    _git(repo, "config", "user.email", "packet@example.invalid")

    for index, rel_path in enumerate(REVIEW_PATHS, start=1):
        path = repo / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"# Review document {index}\n\nbody-{index}\n".encode())
    brief = repo / BRIEF_PATH
    brief.write_bytes(b"# Review instructions\n\nReturn a verdict.\n")

    generator = repo / "scripts" / "freeze_worker_plane_review.py"
    generator.parent.mkdir(parents=True, exist_ok=True)
    generator.write_bytes(Path(packet.__file__).read_bytes())
    launcher = repo / "scripts" / "launch_worker_plane_review_panel.py"
    launcher.write_bytes(b"launcher-v1\n")
    validator = repo / "scripts" / "check_worker_plane_review.py"
    validator.write_bytes(b"validator-v1\n")
    route_config = repo / packet.DEFAULT_ROUTE_CONFIG_PATH
    route_config.parent.mkdir(parents=True, exist_ok=True)
    route_config.write_bytes(packet.EXPECTED_COUNCIL_ROUTE_CONFIG)
    _commit(repo, "initial review inputs")
    return repo


def _specs() -> tuple[packet.InputSpec, ...]:
    covered = tuple(
        packet.InputSpec(role="covered", path=path) for path in REVIEW_PATHS
    )
    return covered + (packet.InputSpec(role="instructions", path=BRIEF_PATH),)


def _build(repo: Path, source_ref: str = "HEAD") -> packet.BuiltPacket:
    return packet.build_from_git(
        repo_root=repo,
        source_ref=source_ref,
        base_ref=source_ref,
        upstream_ref=source_ref,
        inputs=_specs(),
        generator_path="scripts/freeze_worker_plane_review.py",
    )


def test_canonical_json_is_compact_sorted_utf8_and_newline_free() -> None:
    rendered = packet.canonical_json_bytes({"z": "Bali", "a": "Nusantara"})
    assert rendered == b'{"a":"Nusantara","z":"Bali"}'


def test_builder_reads_committed_git_objects_not_mutable_worktree(
    review_repo: Path,
) -> None:
    head = _git(review_repo, "rev-parse", "HEAD")
    original = _build(review_repo, head)

    changed_path = review_repo / REVIEW_PATHS[0]
    changed_path.write_bytes(b"MUTABLE WORKTREE CONTENT\n")

    rebuilt = packet.build_from_git(
        repo_root=review_repo,
        source_ref=head,
        base_ref=head,
        inputs=_specs(),
        generator_path="scripts/freeze_worker_plane_review.py",
        require_clean_tracked_status=False,
    )

    assert rebuilt.packet_bytes == original.packet_bytes
    assert b"MUTABLE WORKTREE CONTENT" not in rebuilt.packet_bytes


def test_builder_never_reads_dirty_review_input_from_worktree(
    review_repo: Path,
) -> None:
    (review_repo / REVIEW_PATHS[2]).write_bytes(b"uncommitted review mutation\n")

    with pytest.raises(packet.PacketError, match="tracked worktree is not clean"):
        _build(review_repo)


def test_general_engine_accepts_one_covered_and_one_instruction(
    review_repo: Path,
) -> None:
    inputs = (
        packet.InputSpec(role="covered", path=REVIEW_PATHS[0]),
        packet.InputSpec(role="instructions", path=BRIEF_PATH),
    )

    built = packet.build_from_git(
        repo_root=review_repo,
        source_ref="HEAD",
        base_ref="HEAD",
        inputs=inputs,
    )
    parsed = packet.parse_packet(built.packet_bytes)

    assert [entry["role"] for entry in built.manifest["entries"]] == [
        "covered",
        "instructions",
    ]
    assert len(parsed.documents) == 2


def test_initial_plan_preset_is_exactly_the_ten_normative_documents() -> None:
    assert packet.COVERED_SET_PRESETS["implementation-plan"] == (
        "docs/superpowers/specs/2026-07-17-backend-modular-kernel-worker-plane-design.md",
        "docs/superpowers/plans/2026-07-17-modular-kernel-worker-plane-implementation.md",
        "docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-0.md",
        "docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-1.md",
        "docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-2.md",
        "docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-3.md",
        "docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-4.md",
        "docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-5.md",
        "docs/superpowers/plans/2026-07-17-modular-worker-plane-production-rollout.md",
        (
            "docs/superpowers/reviews/"
            "2026-07-17-modular-worker-plane-implementation-plan/"
            "2026-07-23-current-system-refresh.md"
        ),
    )
    assert packet.PRESET_INSTRUCTION_PATHS["implementation-plan"] == (
        "docs/superpowers/reviews/"
        "2026-07-17-modular-worker-plane-implementation-plan/00-review-brief.md"
    )


def test_council_v3_route_is_canonical_and_makes_kimi_a_permanent_seat() -> None:
    route = json.loads(packet.EXPECTED_COUNCIL_ROUTE_CONFIG)

    assert packet.canonical_json_bytes(route) + b"\n" == (
        packet.EXPECTED_COUNCIL_ROUTE_CONFIG
    )
    assert [
        (seat["seat"], seat["role"], seat["model"])
        for seat in route["parallel_reviewers"]
    ] == [
        ("gemini", "constructive", "Gemini 3.1 Pro (High)"),
        ("codex", "red-team", "account-default"),
        ("kimi", "refuter", "kimi-code/k3"),
    ]
    assert route["parallel_reviewers"][0]["input_transport"] == "file"
    assert route["parallel_reviewers"][2]["input_transport"] == "file"
    assert route["retired_routes"] == ["deepseek", "glm"]
    assert route["final_gate"]["phase"] == "sequential-after-disposition"


def test_implementation_plan_preset_rejects_any_other_instruction(
    review_repo: Path,
) -> None:
    with pytest.raises(packet.PacketError, match="pins instruction brief"):
        packet._inputs_from_args(
            repo_root=review_repo,
            source_ref="HEAD",
            covered=None,
            covered_set="implementation-plan",
            instructions=BRIEF_PATH,
        )


def test_named_covered_set_must_be_canonically_sorted(review_repo: Path) -> None:
    set_path = review_repo / "scripts" / "review_sets" / "phase-test.json"
    set_path.parent.mkdir(parents=True, exist_ok=True)
    set_path.write_bytes(
        packet.canonical_json_bytes({"covered": [REVIEW_PATHS[1], REVIEW_PATHS[0]]})
        + b"\n"
    )
    source = _commit(review_repo, "add unsorted covered set")

    with pytest.raises(packet.PacketError, match="canonically sorted"):
        packet._covered_paths_for_name(review_repo, source, "phase-test")


def test_named_covered_set_loads_sorted_committed_paths(review_repo: Path) -> None:
    expected = tuple(sorted(REVIEW_PATHS[:2], key=lambda path: path.encode("utf-8")))
    set_path = review_repo / "scripts" / "review_sets" / "phase-test.json"
    set_path.parent.mkdir(parents=True, exist_ok=True)
    set_path.write_bytes(
        packet.canonical_json_bytes({"covered": list(expected)}) + b"\n"
    )
    source = _commit(review_repo, "add covered set")

    assert packet._covered_paths_for_name(review_repo, source, "phase-test") == expected


def test_manifest_has_nine_generic_covered_inputs_and_bound_instruction_brief(
    review_repo: Path,
) -> None:
    built = _build(review_repo)
    manifest = built.manifest

    assert set(manifest) == {"entries"}
    assert len(manifest["entries"]) == 10
    assert list(manifest["entries"]) == sorted(
        manifest["entries"], key=lambda entry: (entry["role"], entry["path"])
    )
    assert set(manifest["entries"][0]) == {
        "git_blob_oid",
        "path",
        "role",
        "sha256",
        "size",
    }
    assert manifest["entries"][-1]["role"] == "instructions"
    assert manifest["entries"][-1]["path"] == BRIEF_PATH
    assert built.manifest_sha256 == built.projection_sha256
    assert "manifest_sha256" not in manifest
    assert "packet_sha256" not in manifest


def test_packet_bytes_are_deterministic(review_repo: Path) -> None:
    first = _build(review_repo)
    second = _build(review_repo)

    assert first.manifest_bytes == second.manifest_bytes
    assert first.packet_bytes == second.packet_bytes
    assert first.packet_sha256 == second.packet_sha256


def test_builder_strictly_round_trips_its_completed_packet(
    review_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_render = packet._render_packet

    def render_with_trailing_byte(
        manifest_bytes: bytes,
        documents: tuple[packet.ReviewDocument, ...],
    ) -> bytes:
        return original_render(manifest_bytes, documents) + b"X"

    monkeypatch.setattr(packet, "_render_packet", render_with_trailing_byte)

    with pytest.raises(packet.PacketError, match="trailing bytes"):
        _build(review_repo)


def test_builder_binds_committed_launcher_and_validator_blobs(
    review_repo: Path,
) -> None:
    built = _build(review_repo)

    assert built.launcher.path == packet.DEFAULT_LAUNCHER_PATH
    assert built.launcher.content == b"launcher-v1\n"
    assert built.validator.path == packet.DEFAULT_VALIDATOR_PATH
    assert built.validator.content == b"validator-v1\n"


def test_builder_rejects_generator_blob_that_is_not_executing_freezer(
    review_repo: Path,
) -> None:
    generator = review_repo / packet.DEFAULT_GENERATOR_PATH
    generator.write_bytes(b"different-freezer\n")
    _commit(review_repo, "replace freezer")

    with pytest.raises(packet.PacketError, match="executing freezer bytes"):
        _build(review_repo)


def test_builder_requires_source_to_equal_current_head(review_repo: Path) -> None:
    old_head = _git(review_repo, "rev-parse", "HEAD")
    (review_repo / "README.md").write_text("new head\n", encoding="utf-8")
    _commit(review_repo, "advance head")

    with pytest.raises(
        packet.PacketError, match="source commit must equal current HEAD"
    ):
        packet.build_from_git(
            repo_root=review_repo,
            source_ref=old_head,
            base_ref=old_head,
            upstream_ref=old_head,
            inputs=_specs(),
        )


def test_builder_requires_base_to_equal_source_upstream_merge_base(
    review_repo: Path,
) -> None:
    upstream = _git(review_repo, "rev-parse", "HEAD")
    (review_repo / "README.md").write_text("feature\n", encoding="utf-8")
    source = _commit(review_repo, "feature commit")

    with pytest.raises(packet.PacketError, match="base commit must equal merge-base"):
        packet.build_from_git(
            repo_root=review_repo,
            source_ref=source,
            base_ref=source,
            upstream_ref=upstream,
            inputs=_specs(),
        )

    built = packet.build_from_git(
        repo_root=review_repo,
        source_ref=source,
        base_ref=upstream,
        upstream_ref=upstream,
        inputs=_specs(),
    )
    assert built.base_commit == upstream


def test_packet_round_trip_preserves_every_byte_and_requires_exact_eof(
    review_repo: Path,
) -> None:
    built = _build(review_repo)
    parsed = packet.parse_packet(built.packet_bytes)

    assert parsed.manifest == built.manifest
    assert parsed.manifest_sha256 == built.manifest_sha256
    assert parsed.packet_sha256 == hashlib.sha256(built.packet_bytes).hexdigest()
    assert [document.content for document in parsed.documents] == [
        (review_repo / spec.path).read_bytes() for spec in _specs()
    ]

    with pytest.raises(packet.PacketError, match="trailing bytes"):
        packet.parse_packet(built.packet_bytes + b"unexpected")


def test_length_framing_preserves_embedded_delimiters_newlines_and_nul(
    review_repo: Path,
) -> None:
    special = b"ENTRY 99 99 99\nEND\n\x00tail\n\n"
    (review_repo / REVIEW_PATHS[4]).write_bytes(special)
    _commit(review_repo, "add framing adversary")

    built = _build(review_repo)
    parsed = packet.parse_packet(built.packet_bytes)

    assert parsed.documents[4].content == special


def test_packet_parser_detects_content_tampering(review_repo: Path) -> None:
    built = _build(review_repo)
    tampered = built.packet_bytes.replace(b"body-4", b"body-X", 1)

    with pytest.raises(packet.PacketError, match="content SHA-256 mismatch"):
        packet.parse_packet(tampered)


def test_packet_parser_rejects_truncation_reordering_wrong_size_and_wrong_blob(
    review_repo: Path,
) -> None:
    built = _build(review_repo)
    with pytest.raises(packet.PacketError, match="ended before|expected packet marker"):
        packet.parse_packet(built.packet_bytes[:-2])

    reordered_manifest = {
        "entries": list(reversed(built.manifest["entries"])),
    }
    reordered_bytes = packet._render_packet(
        packet.canonical_json_bytes(reordered_manifest),
        tuple(reversed(built.documents)),
    )
    with pytest.raises(packet.PacketError, match="canonically ordered"):
        packet.parse_packet(reordered_bytes)

    wrong_size_manifest = json.loads(json.dumps(built.manifest))
    wrong_size_manifest["entries"][0]["size"] += 1
    wrong_size_bytes = packet._render_packet(
        packet.canonical_json_bytes(wrong_size_manifest),
        built.documents,
    )
    with pytest.raises(packet.PacketError, match="byte length does not match"):
        packet.parse_packet(wrong_size_bytes)

    wrong_blob_manifest = json.loads(json.dumps(built.manifest))
    oid = wrong_blob_manifest["entries"][0]["git_blob_oid"]
    wrong_blob_manifest["entries"][0]["git_blob_oid"] = (
        "0" if oid[0] != "0" else "1"
    ) + oid[1:]
    wrong_blob_bytes = packet._render_packet(
        packet.canonical_json_bytes(wrong_blob_manifest),
        built.documents,
    )
    with pytest.raises(packet.PacketError, match="Git blob OID mismatch"):
        packet.parse_packet(wrong_blob_bytes)


def test_packet_parser_fails_closed_on_non_object_manifest_entry(
    review_repo: Path,
) -> None:
    built = _build(review_repo)
    malformed = {"entries": [None, *built.manifest["entries"][1:]]}
    payload = packet._render_packet(
        packet.canonical_json_bytes(malformed), built.documents
    )

    with pytest.raises(packet.PacketError, match="entry shape is invalid"):
        packet.parse_packet(payload)


@pytest.mark.parametrize("value", [b"+1", b"-0", b"1_0"])
def test_decimal_parser_rejects_noncanonical_integer_spelling(value: bytes) -> None:
    with pytest.raises(packet.PacketError, match="invalid integer"):
        packet._parse_nonnegative_int(value, "test length")


def test_manifest_rejects_boolean_size(review_repo: Path) -> None:
    built = _build(review_repo)
    malformed = json.loads(json.dumps(built.manifest))
    malformed["entries"][0]["size"] = True
    payload = packet._render_packet(
        packet.canonical_json_bytes(malformed), built.documents
    )

    with pytest.raises(packet.PacketError, match="manifest entry size is invalid"):
        packet.parse_packet(payload)


def test_projection_stays_stable_across_evidence_only_commit(review_repo: Path) -> None:
    source_head = _git(review_repo, "rev-parse", "HEAD")
    first = packet.build_projection_from_git(
        repo_root=review_repo,
        source_ref=source_head,
        inputs=_specs(),
    )

    evidence = review_repo / "docs" / "reviews" / "raw" / "fable.json"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text('{"verdict":"GO"}\n', encoding="utf-8")
    evidence_head = _commit(review_repo, "record review evidence")
    second = packet.build_projection_from_git(
        repo_root=review_repo,
        source_ref=evidence_head,
        inputs=_specs(),
    )

    assert first.source_head != second.source_head
    assert first.projection_sha256 == second.projection_sha256
    assert first.manifest_sha256 == second.manifest_sha256
    assert first.packet_sha256 == second.packet_sha256


def test_projection_changes_when_any_review_input_changes(review_repo: Path) -> None:
    first = _build(review_repo)
    path = review_repo / REVIEW_PATHS[7]
    path.write_bytes(path.read_bytes() + b"accepted amendment\n")
    _commit(review_repo, "amend review input")
    second = _build(review_repo)

    assert first.projection_sha256 != second.projection_sha256


def test_write_artifacts_is_content_addressed_read_only_and_receipted(
    review_repo: Path,
    tmp_path: Path,
) -> None:
    built = _build(review_repo)
    artifact = packet.write_artifacts(built, tmp_path / "packets")

    assert artifact.review_dir == tmp_path / "packets" / "sha256" / built.packet_sha256
    assert artifact.packet_path == artifact.review_dir / "packet.bin"
    assert artifact.packet_path.read_bytes() == built.packet_bytes
    assert stat.S_IMODE(artifact.packet_path.stat().st_mode) == 0o444
    assert artifact.manifest_path.read_bytes() == built.manifest_bytes
    assert (
        artifact.route_config_path.read_bytes()
        == packet.EXPECTED_COUNCIL_ROUTE_CONFIG
    )

    receipt = json.loads(artifact.receipt_path.read_text(encoding="utf-8"))
    assert receipt["packet_sha256"] == built.packet_sha256
    assert receipt["input_manifest_sha256"] == built.manifest_sha256
    assert receipt["packet_bytes"] == len(built.packet_bytes)
    assert receipt["source_head"] == built.source_head
    assert receipt["packet_inode"] == artifact.packet_path.stat().st_ino
    assert receipt["packet_device"] == artifact.packet_path.stat().st_dev
    assert receipt["git_object_validation"] == "pass"
    assert receipt["launcher_git_blob_oid"] == built.launcher.git_blob_oid
    assert receipt["launcher_sha256"] == built.launcher.sha256
    assert receipt["validator_git_blob_oid"] == built.validator.git_blob_oid
    assert receipt["validator_sha256"] == built.validator.sha256
    assert stat.S_IMODE(artifact.receipt_path.stat().st_mode) == 0o444
    assert stat.S_IMODE(artifact.review_dir.stat().st_mode) == 0o555
    assert {path.name for path in artifact.review_dir.iterdir()} == {
        "packet.bin",
        "input-manifest.json",
        "freeze-receipt.json",
        "worker-plane-council-v3.json",
    }


def test_write_artifacts_rejects_store_inside_repository(review_repo: Path) -> None:
    built = _build(review_repo)

    with pytest.raises(packet.PacketError, match="outside repository"):
        packet.write_artifacts(built, review_repo / "review-store")


def test_write_artifacts_revalidates_after_move_and_fsyncs_parent(
    review_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    built = _build(review_repo)
    validations: list[Path] = []
    fsynced: list[Path] = []
    original_validate = packet._validate_existing_artifacts
    original_fsync = packet._fsync_directory

    def validate(paths: packet.ArtifactPaths, candidate: packet.BuiltPacket) -> None:
        validations.append(paths.review_dir)
        original_validate(paths, candidate)

    def fsync_directory(path: Path) -> None:
        fsynced.append(path)
        original_fsync(path)

    monkeypatch.setattr(packet, "_validate_existing_artifacts", validate)
    monkeypatch.setattr(packet, "_fsync_directory", fsync_directory)
    store = tmp_path / "packets"
    artifact = packet.write_artifacts(built, store)

    assert validations[-1] == artifact.review_dir
    assert (store / "sha256").resolve() in fsynced


def test_existing_store_rejects_extra_file_and_noncanonical_receipt(
    review_repo: Path,
    tmp_path: Path,
) -> None:
    built = _build(review_repo)
    store = tmp_path / "packets"
    artifact = packet.write_artifacts(built, store)
    os.chmod(artifact.review_dir, 0o755)
    extra = artifact.review_dir / "extra.txt"
    extra.write_bytes(b"not allowed\n")
    os.chmod(extra, 0o444)
    os.chmod(artifact.review_dir, 0o555)

    with pytest.raises(packet.PacketError, match="exactly four files"):
        packet.write_artifacts(built, store)

    os.chmod(artifact.review_dir, 0o755)
    os.chmod(extra, 0o644)
    extra.unlink()
    os.chmod(artifact.receipt_path, 0o644)
    receipt = json.loads(artifact.receipt_path.read_text(encoding="utf-8"))
    artifact.receipt_path.write_bytes(json.dumps(receipt, indent=2).encode("utf-8"))
    os.chmod(artifact.receipt_path, 0o444)
    os.chmod(artifact.review_dir, 0o555)

    with pytest.raises(packet.PacketError, match="canonical"):
        packet.write_artifacts(built, store)


def test_existing_store_rejects_symlink_or_writable_artifact(
    review_repo: Path,
    tmp_path: Path,
) -> None:
    built = _build(review_repo)
    store = tmp_path / "packets"
    artifact = packet.write_artifacts(built, store)
    packet_bytes = artifact.packet_path.read_bytes()
    outside = tmp_path / "outside-packet.bin"
    outside.write_bytes(packet_bytes)
    os.chmod(artifact.review_dir, 0o755)
    os.chmod(artifact.packet_path, 0o644)
    artifact.packet_path.unlink()
    artifact.packet_path.symlink_to(outside)
    os.chmod(artifact.review_dir, 0o555)

    with pytest.raises(packet.PacketError, match="regular non-symlink"):
        packet.write_artifacts(built, store)


def test_builder_rejects_any_dirty_tracked_file(review_repo: Path) -> None:
    unrelated = review_repo / "README.md"
    unrelated.write_text("clean\n", encoding="utf-8")
    _commit(review_repo, "add unrelated file")
    unrelated.write_text("dirty\n", encoding="utf-8")

    with pytest.raises(packet.PacketError, match="tracked worktree is not clean"):
        _build(review_repo)


def test_builder_rejects_noncanonical_council_route_config(
    review_repo: Path,
) -> None:
    route_config = review_repo / packet.DEFAULT_ROUTE_CONFIG_PATH
    route_config.write_bytes(b'{"base_url":"wrong"}\n')
    _commit(review_repo, "break route config")

    with pytest.raises(
        packet.PacketError, match="council route config bytes are not canonical"
    ):
        _build(review_repo)


def test_rejects_wrong_role_cardinality(review_repo: Path) -> None:
    bad_specs = (packet.InputSpec(role="covered", path=REVIEW_PATHS[0]),)

    with pytest.raises(
        packet.PacketError,
        match="one or more covered inputs and exactly one instructions input",
    ):
        packet.build_from_git(
            repo_root=review_repo,
            source_ref="HEAD",
            base_ref="HEAD",
            inputs=bad_specs,
            generator_path="scripts/freeze_worker_plane_review.py",
        )


def test_rejects_duplicate_paths_and_unknown_roles(review_repo: Path) -> None:
    with pytest.raises(packet.PacketError, match="paths must be unique"):
        packet.build_from_git(
            repo_root=review_repo,
            source_ref="HEAD",
            base_ref="HEAD",
            inputs=(
                packet.InputSpec(role="covered", path=REVIEW_PATHS[0]),
                packet.InputSpec(role="instructions", path=REVIEW_PATHS[0]),
            ),
        )

    with pytest.raises(packet.PacketError, match="one or more covered inputs"):
        packet.build_from_git(
            repo_root=review_repo,
            source_ref="HEAD",
            base_ref="HEAD",
            inputs=(
                packet.InputSpec(role="evidence", path=REVIEW_PATHS[0]),
                packet.InputSpec(role="instructions", path=BRIEF_PATH),
            ),
        )


@pytest.mark.parametrize(
    "bad_path", ["docs/./review.md", "docs//review.md", "./review.md"]
)
def test_rejects_non_normalized_paths(review_repo: Path, bad_path: str) -> None:
    with pytest.raises(packet.PacketError, match="invalid repository-relative path"):
        packet.build_from_git(
            repo_root=review_repo,
            source_ref="HEAD",
            base_ref="HEAD",
            inputs=(
                packet.InputSpec(role="covered", path=bad_path),
                packet.InputSpec(role="instructions", path=BRIEF_PATH),
            ),
        )


def test_packet_artifact_never_contains_secret_environment_values(
    review_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "forbidden-provider-secret-3db6c8"
    monkeypatch.setenv("ANTHROPIC_API_KEY", secret)
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", secret)
    monkeypatch.setenv("OPENAI_API_KEY", secret)

    built = _build(review_repo)

    assert secret.encode() not in built.packet_bytes
    assert secret not in json.dumps(built.manifest)
    assert os.environ["ANTHROPIC_API_KEY"] == secret


def test_compare_projection_cli_ignores_attestations_and_fails_on_covered_delta(
    review_repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    left = _git(review_repo, "rev-parse", "HEAD")
    evidence = review_repo / "docs" / "reviews" / "raw.txt"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text("attestation only\n", encoding="utf-8")
    attested = _commit(review_repo, "attestation")
    common = [
        "compare-projection",
        "--repo",
        str(review_repo),
        "--left",
        left,
        "--right",
        attested,
        "--covered",
        REVIEW_PATHS[0],
        "--instructions",
        BRIEF_PATH,
    ]

    assert packet.main(common) == 0
    assert json.loads(capsys.readouterr().out)["equal"] is True

    changed = review_repo / REVIEW_PATHS[0]
    changed.write_bytes(changed.read_bytes() + b"covered delta\n")
    changed_head = _commit(review_repo, "covered delta")
    common[common.index(attested)] = changed_head
    assert packet.main(common) == 1
    assert json.loads(capsys.readouterr().out)["equal"] is False


def test_freeze_cli_matches_runbook_option_names() -> None:
    parsed = packet.build_parser().parse_args(
        [
            "freeze",
            "--repo",
            ".",
            "--base",
            "origin/main",
            "--source",
            "HEAD",
            "--instructions",
            BRIEF_PATH,
            "--covered-set",
            "implementation-plan",
            "--output-store",
            "/tmp/review-store",
        ]
    )

    assert parsed.repo == Path(".")
    assert parsed.covered_set == "implementation-plan"
    assert parsed.upstream == "origin/main"
    assert not hasattr(parsed, "generator_path")
    assert not hasattr(parsed, "route_config_path")


def test_freeze_cli_rejects_generator_and_route_config_overrides() -> None:
    parser = packet.build_parser()
    common = [
        "freeze",
        "--repo",
        ".",
        "--base",
        "origin/main",
        "--source",
        "HEAD",
        "--instructions",
        packet.PRESET_INSTRUCTION_PATHS["implementation-plan"],
        "--covered-set",
        "implementation-plan",
        "--output-store",
        "/tmp/review-store",
    ]

    with pytest.raises(SystemExit):
        parser.parse_args([*common, "--generator-path", "attacker.py"])
    with pytest.raises(SystemExit):
        parser.parse_args([*common, "--route-config-path", "attacker.json"])
