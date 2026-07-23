from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable

import pytest

from scripts.check_worker_plane_review import (
    LAUNCHER_REPO_PATH,
    REVIEW_INPUT_MAGIC,
    REVIEW_INPUT_SCHEMA,
    VALIDATOR_REPO_PATH,
    ReviewValidationError,
    main,
    validate_review_panel,
)
from scripts.freeze_worker_plane_review import (
    DEFAULT_GENERATOR_PATH,
    EXPECTED_GLM_ROUTE_CONFIG,
    InputSpec,
    LEGACY_ROUTE_CONFIG_PATH,
    ReviewDocument,
    _entry,
    _render_packet,
    canonical_json_bytes,
    build_from_git,
    parse_packet,
    sha256_bytes,
)


CLAUDE_EXECUTABLE = "/Users/nuzantara/.local/share/claude/versions/2.1.214"
GEMINI_EXECUTABLE = "/Users/nuzantara/.local/bin/agy"
MCP_CONFIG = '{"mcpServers":{}}'
ROUTES = ("claude-fable-5", "Gemini 3.1 Pro (High)", "glm-5.2")
REVIEW_NAMES = (
    "01-fable-5-architecture.md",
    "02-gemini-3.1-pro-high.md",
    "03-glm-5.2-adversarial.md",
)
CLAUDE_SHA256 = "59796dd18e9d77f1256f367db6d28ce4bd9cd5968e402ad3a327aac36abc6dec"
CLAUDE_CDHASH = "57f37e5659c14725f4e11dc77a96b6e7ba3a80ca"
CLAUDE_REQUIREMENT = (
    'identifier "com.anthropic.claude-code" and anchor apple generic and '
    "certificate 1[field.1.2.840.113635.100.6.2.6] /* exists */ and "
    "certificate leaf[field.1.2.840.113635.100.6.1.13] /* exists */ and "
    "certificate leaf[subject.OU] = Q6L2SF6YDW"
)
GEMINI_SHA256 = "6509d6ca54a66e3eaf61dfe35308ba1dfa1e6b552ef5c4f5f861562c6811ecaf"
GEMINI_CDHASH = "d1ab6b43250ebdf79a8836804197495d39b9a5c1"
GEMINI_REQUIREMENT = (
    "identifier cli and anchor apple generic and certificate "
    "1[field.1.2.840.113635.100.6.2.6] /* exists */ and certificate "
    "leaf[field.1.2.840.113635.100.6.1.13] /* exists */ and "
    "certificate leaf[subject.OU] = EQHXZ8M8AV"
)


@dataclass
class Bundle:
    root: Path
    repo: Path
    h0: str
    h1: str
    covered_paths: tuple[str, ...]
    instructions_path: str
    validator_path: Path
    packet: Path
    manifest: Path
    receipt: Path
    disposition: Path
    reviews: tuple[Path, Path, Path]


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_file(path: Path, value: Any) -> None:
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _repo_file(repo: Path, relative: str, payload: bytes) -> Path:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def _blob_proof(repo: Path, commit: str, path: str) -> tuple[str, str]:
    oid = _git(repo, "rev-parse", f"{commit}:{path}")
    payload = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "blob", oid],
        check=True,
        capture_output=True,
    ).stdout
    return oid, sha256_bytes(payload)


def _packet() -> tuple[bytes, bytes]:
    contents = (b"covered bytes\n", b"review instructions\n")
    specs = (
        InputSpec("covered", "docs/covered.md"),
        InputSpec("instructions", "docs/00-review-brief.md"),
    )
    documents = tuple(
        ReviewDocument(
            ordinal=index,
            role=spec.role,
            path=spec.path,
            mode="100644",
            git_blob_oid=(
                hashlib.sha1(
                    f"blob {len(content)}\0".encode("ascii") + content,
                    usedforsecurity=False,
                ).hexdigest()
            ),
            content=content,
            sha256=_sha(content),
        )
        for index, (spec, content) in enumerate(
            zip(specs, contents, strict=True), start=1
        )
    )
    manifest_bytes = canonical_json_bytes(
        {"entries": [_entry(document) for document in documents]}
    )
    packet_bytes = _render_packet(manifest_bytes, documents)
    parse_packet(packet_bytes)
    return packet_bytes, manifest_bytes


def _argv(route: str) -> list[str]:
    if route == "Gemini 3.1 Pro (High)":
        return [
            "--mode",
            "plan",
            "--sandbox",
            "--print-timeout",
            "15m",
            "--model",
            "Gemini 3.1 Pro (High)",
        ]
    model = "claude-fable-5" if route == "claude-fable-5" else "glm-5.2"
    effort = "xhigh" if route == "claude-fable-5" else "high"
    permission_mode = "plan" if route == "claude-fable-5" else "dontAsk"
    return [
        "--print",
        "--model",
        model,
        "--effort",
        effort,
        "--output-format",
        "json",
        "--no-session-persistence",
        "--safe-mode",
        "--permission-mode",
        permission_mode,
        "--tools",
        "",
        "--disable-slash-commands",
        "--strict-mcp-config",
        "--mcp-config",
        MCP_CONFIG,
    ]


def _body(manifest_sha256: str, index: int) -> str:
    blocking = "None" if index != 0 else "[FABLE-B1] Fence the legacy claim path."
    important = "None" if index != 1 else "[GEMINI-I1] Pin the readiness ceiling."
    return (
        "# Verdict\n\n"
        f"GO-WITH-CHANGES — confidence {91 - index}\n\n"
        f"input_manifest_sha256: {manifest_sha256}\n\n"
        "# Blocking findings\n\n"
        f"{blocking}\n\n"
        "# Important findings\n\n"
        f"{important}\n\n"
        "# What survives review\n\n"
        "The generation fence and reverse-cutover invariant remain coherent.\n\n"
        "# Required amendments\n\n"
        "Retain the measured gate and bind every accepted finding to evidence.\n\n"
        "# Falsification test\n\n"
        "Run cutover and reverse cutover while an old owner attempts one claim.\n"
    )


def _frontmatter(values: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in values.items():
        if value is None:
            rendered = "null"
        else:
            rendered = str(value)
        lines.append(f"{key}: {rendered}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def make_bundle(tmp_path: Path) -> Bundle:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "review-tests@example.com")
    _git(repo, "config", "user.name", "Review Tests")
    covered_paths = ("docs/covered.md",)
    instructions_path = "docs/00-review-brief.md"
    _repo_file(repo, covered_paths[0], b"covered bytes\n")
    _repo_file(repo, instructions_path, b"review instructions\n")
    source_root = Path(__file__).resolve().parents[2]
    for relative in (
        DEFAULT_GENERATOR_PATH,
        LAUNCHER_REPO_PATH,
        VALIDATOR_REPO_PATH,
    ):
        _repo_file(repo, relative, (source_root / relative).read_bytes())
    _repo_file(repo, LEGACY_ROUTE_CONFIG_PATH, EXPECTED_GLM_ROUTE_CONFIG)
    evidence_payload = b"readiness probe passed\n"
    _repo_file(
        repo,
        "tests/test_fence.py",
        b"def test_legacy_fence():\n    pass\n\ndef test_readiness_ceiling():\n    pass\n",
    )
    _repo_file(repo, "docs/evidence.md", evidence_payload)
    h0 = _commit(repo, "freeze review inputs")
    inputs = (
        InputSpec("covered", covered_paths[0]),
        InputSpec("instructions", instructions_path),
    )
    built = build_from_git(
        repo_root=repo,
        source_ref=h0,
        base_ref=h0,
        inputs=inputs,
        route_config_path=LEGACY_ROUTE_CONFIG_PATH,
    )
    packet_bytes = built.packet_bytes
    manifest_bytes = built.manifest_bytes
    packet_sha256 = built.packet_sha256
    manifest_sha256 = built.manifest_sha256
    review_input_bytes = b"".join(
        (
            REVIEW_INPUT_MAGIC,
            f"schema: {REVIEW_INPUT_SCHEMA}\n".encode("ascii"),
            f"input_manifest_sha256: {manifest_sha256}\n".encode("ascii"),
            f"packet_bytes: {len(packet_bytes)}\n".encode("ascii"),
            b"\n",
            packet_bytes,
        )
    )

    artifact_root = repo / "review-artifacts"
    artifact_root.mkdir()
    packet_path = artifact_root / "00-review-packet.bin"
    manifest_path = artifact_root / "input-manifest.json"
    receipt_path = artifact_root / "freeze-receipt.json"
    disposition_path = artifact_root / "99-disposition.md"
    packet_path.write_bytes(packet_bytes)
    manifest_path.write_bytes(manifest_bytes)
    packet_stat = packet_path.stat()
    generator_oid, generator_sha = _blob_proof(repo, h0, DEFAULT_GENERATOR_PATH)
    route_oid, route_sha = _blob_proof(repo, h0, LEGACY_ROUTE_CONFIG_PATH)
    launcher_oid, launcher_sha = _blob_proof(repo, h0, LAUNCHER_REPO_PATH)
    validator_oid, validator_sha = _blob_proof(repo, h0, VALIDATOR_REPO_PATH)
    freeze_receipt = {
        "base_commit": h0,
        "built_at_utc": "2026-07-18T01:00:00+00:00",
        "generator_git_blob_oid": generator_oid,
        "generator_path": DEFAULT_GENERATOR_PATH,
        "generator_sha256": generator_sha,
        "generator_version": "1.0.0",
        "git_object_validation": "pass",
        "input_manifest_sha256": manifest_sha256,
        "launcher_git_blob_oid": launcher_oid,
        "launcher_path": LAUNCHER_REPO_PATH,
        "launcher_sha256": launcher_sha,
        "packet_bytes": len(packet_bytes),
        "packet_device": packet_stat.st_dev,
        "packet_inode": packet_stat.st_ino,
        "packet_sha256": packet_sha256,
        "route_config_git_blob_oid": route_oid,
        "route_config_path": LEGACY_ROUTE_CONFIG_PATH,
        "route_config_sha256": route_sha,
        "schema": "nuzantara.worker-plane-review-freeze-receipt/v1",
        "source_head": h0,
        "source_tree": _git(repo, "rev-parse", f"{h0}^{{tree}}"),
        "tracked_status_sha256": sha256_bytes(b""),
        "upstream_commit": h0,
        "validator_git_blob_oid": validator_oid,
        "validator_path": VALIDATOR_REPO_PATH,
        "validator_sha256": validator_sha,
    }
    _canonical_file(receipt_path, freeze_receipt)

    review_paths: list[Path] = []
    for index, (name, route) in enumerate(zip(REVIEW_NAMES, ROUTES, strict=True)):
        review_path = artifact_root / name
        raw_path = review_path.with_suffix(".raw.txt" if index == 1 else ".raw.json")
        stderr_path = review_path.with_suffix(".stderr.bin")
        invocation_path = review_path.with_suffix(".invocation.json")
        body = _body(manifest_sha256, index)
        provider_session_id = None if index == 1 else f"session-{index + 1}"
        reported_model = None if index == 1 else route
        raw_envelope = {
            "modelUsage": ({route: {}} if index == 0 else {"glm-4.7": {}, route: {}}),
            "result": body,
            "session_id": provider_session_id,
        }
        raw_bytes = (
            body.encode("utf-8")
            if index == 1
            else (canonical_json_bytes(raw_envelope) + b"\n")
        )
        raw_path.write_bytes(raw_bytes)
        stderr_path.write_bytes(b"")
        launcher_uuid = str(uuid.uuid4())
        executable = GEMINI_EXECUTABLE if index == 1 else CLAUDE_EXECUTABLE
        executable_sha256 = GEMINI_SHA256 if index == 1 else CLAUDE_SHA256
        executable_cdhash = GEMINI_CDHASH if index == 1 else CLAUDE_CDHASH
        executable_team_identifier = "EQHXZ8M8AV" if index == 1 else "Q6L2SF6YDW"
        executable_requirement = (
            GEMINI_REQUIREMENT if index == 1 else CLAUDE_REQUIREMENT
        )
        argv = [executable, *_argv(route)]
        cwd_path = f"/private/tmp/worker-plane-review-{index}"
        cwd_proof = {
            "device": 8,
            "initial_entries": [],
            "inode": 1000 + index,
            "mode": "0700",
            "path": cwd_path,
        }
        invocation = {
            "argv": argv,
            "argv_sha256": sha256_bytes(canonical_json_bytes(argv)),
            "client_version": "1.1.3" if index == 1 else "2.1.0",
            "cwd_device": 8,
            "cwd_initial_entries": [],
            "cwd_inode": 1000 + index,
            "cwd_mode": "0700",
            "cwd_path": cwd_path,
            "cwd_proof_sha256": sha256_bytes(canonical_json_bytes(cwd_proof)),
            "cwd_removed_after_run": True,
            "descendants_absent_after_run": True,
            "ended_at_utc": "2026-07-18T01:01:00+00:00",
            "executable_cdhash": executable_cdhash,
            "executable_designated_requirement": executable_requirement,
            "executable_identity_policy_revision": "pro-clients-2026-07-23-v3",
            "executable_path": executable,
            "executable_sha256": executable_sha256,
            "executable_team_identifier": executable_team_identifier,
            "exit_status": 0,
            "home_path": cwd_path,
            "input_manifest_sha256": manifest_sha256,
            "launcher_invocation_uuid": launcher_uuid,
            "launcher_path": str((repo / LAUNCHER_REPO_PATH).resolve()),
            "launcher_sha256": launcher_sha,
            "max_output_bytes": 16 * 1024 * 1024,
            "output_spooled": True,
            "packet_sha256": packet_sha256,
            "process_group_isolated": True,
            "provider_session_id": provider_session_id,
            "raw_output_path": raw_path.name,
            "reported_model": reported_model,
            "requested_route": route,
            "route_config_path": "glm-5.2-v1.json" if index == 2 else None,
            "route_config_sha256": route_sha if index == 2 else None,
            "review_input_bytes": len(review_input_bytes),
            "review_input_schema": REVIEW_INPUT_SCHEMA,
            "review_input_sha256": sha256_bytes(review_input_bytes),
            "schema": "nuzantara.worker-plane-review-launcher-receipt/v2",
            "seat": ("fable", "gemini", "glm")[index],
            "shell": False,
            "started_at_utc": "2026-07-18T01:00:00+00:00",
            "stderr_bytes": 0,
            "stderr_output_path": stderr_path.name,
            "stderr_sha256": sha256_bytes(b""),
            "stdout_bytes": len(raw_bytes),
            "stdout_sha256": sha256_bytes(raw_bytes),
            "tools_denied": True,
            "wall_timeout_seconds": 900.0,
            "xdg_cache_home": cwd_path,
            "xdg_config_home": cwd_path,
            "xdg_data_home": cwd_path,
            "xdg_state_home": cwd_path,
        }
        _canonical_file(invocation_path, invocation)
        frontmatter = {
            "requested_route": route,
            "launcher_invocation_uuid": launcher_uuid,
            "provider_session_id": provider_session_id,
            "reported_model": reported_model,
            "input_manifest_sha256": manifest_sha256,
            "packet_sha256": packet_sha256,
            "launcher_proof_sha256": sha256_bytes(invocation_path.read_bytes()),
            "raw_response_sha256": sha256_bytes(raw_bytes),
        }
        review_path.write_text(_frontmatter(frontmatter) + body, encoding="utf-8")
        review_paths.append(review_path)

    evidence_sha = sha256_bytes(evidence_payload)
    disposition_path.write_text(
        "# Review finding disposition\n\n"
        "| Finding ID | Severity | Decision | Evidence | Owning commit | Rereview status |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| FABLE-B1 | Blocking | accepted | evidence=test:tests/test_fence.py::test_legacy_fence; resolution=legacy claim fence implemented | "
        f"{h0} | resolved |\n"
        "| GEMINI-I1 | Important | accepted | evidence=artifact:docs/evidence.md@"
        f"{evidence_sha}; resolution=readiness ceiling pinned | {h0} | resolved |\n",
        encoding="utf-8",
    )
    h1 = _commit(repo, "record immutable review artifacts")
    return Bundle(
        root=tmp_path,
        repo=repo,
        h0=h0,
        h1=h1,
        covered_paths=covered_paths,
        instructions_path=instructions_path,
        validator_path=repo / VALIDATOR_REPO_PATH,
        packet=packet_path,
        manifest=manifest_path,
        receipt=receipt_path,
        disposition=disposition_path,
        reviews=tuple(review_paths),  # type: ignore[arg-type]
    )


def _externalized_bundle(bundle: Bundle) -> Bundle:
    external_root = bundle.root / "external-review-artifacts"
    shutil.copytree(bundle.packet.parent, external_root)
    reviews = tuple(external_root / path.name for path in bundle.reviews)
    return replace(
        bundle,
        packet=external_root / bundle.packet.name,
        manifest=external_root / bundle.manifest.name,
        receipt=external_root / bundle.receipt.name,
        disposition=external_root / bundle.disposition.name,
        reviews=reviews,  # type: ignore[arg-type]
    )


def _validate(bundle: Bundle) -> dict[str, Any]:
    return validate_review_panel(
        repo_root=bundle.repo,
        h0_ref=bundle.h0,
        h1_ref=bundle.h1,
        covered_paths=bundle.covered_paths,
        covered_set=None,
        instructions_path=bundle.instructions_path,
        packet_path=bundle.packet,
        input_manifest_path=bundle.manifest,
        freeze_receipt_path=bundle.receipt,
        disposition_path=bundle.disposition,
        review_paths=bundle.reviews,
        executing_validator_path=bundle.validator_path,
    )


def _commit_artifact_mutation(bundle: Bundle) -> None:
    bundle.h1 = _commit(bundle.repo, "commit mutated review artifact")


def _review_text(bundle: Bundle, index: int) -> str:
    return bundle.reviews[index].read_text(encoding="utf-8")


def _write_review(bundle: Bundle, index: int, transform: Callable[[str], str]) -> None:
    path = bundle.reviews[index]
    path.write_text(transform(_review_text(bundle, index)), encoding="utf-8")


def _invocation_path(review_path: Path) -> Path:
    return review_path.with_suffix(".invocation.json")


def _raw_path(review_path: Path) -> Path:
    txt = review_path.with_suffix(".raw.txt")
    return txt if txt.exists() else review_path.with_suffix(".raw.json")


def _rewrite_body_and_raw(
    bundle: Bundle, index: int, transform: Callable[[str], str]
) -> None:
    review_path = bundle.reviews[index]
    review_text = review_path.read_text(encoding="utf-8")
    marker = review_text.find("---\n", 4)
    frontmatter = review_text[: marker + 4]
    body = review_text[marker + 4 :]
    updated_body = transform(body)
    raw_path = _raw_path(review_path)
    if raw_path.suffix == ".txt":
        raw_bytes = updated_body.encode("utf-8")
    else:
        envelope = json.loads(raw_path.read_text(encoding="utf-8"))
        envelope["result"] = updated_body
        raw_bytes = canonical_json_bytes(envelope) + b"\n"
    raw_path.write_bytes(raw_bytes)
    invocation_path = _invocation_path(review_path)
    invocation = json.loads(invocation_path.read_text(encoding="utf-8"))
    invocation["stdout_bytes"] = len(raw_bytes)
    invocation["stdout_sha256"] = sha256_bytes(raw_bytes)
    _canonical_file(invocation_path, invocation)
    lines = frontmatter.splitlines(keepends=True)
    replacements = {
        "launcher_proof_sha256:": sha256_bytes(invocation_path.read_bytes()),
        "raw_response_sha256:": sha256_bytes(raw_bytes),
    }
    for line_index, line in enumerate(lines):
        for key, value in replacements.items():
            if line.startswith(key):
                lines[line_index] = f"{key} {value}\n"
    review_path.write_text("".join(lines) + updated_body, encoding="utf-8")


def _rewrite_invocation(
    bundle: Bundle, index: int, mutate: Callable[[dict[str, Any]], None]
) -> None:
    review_path = bundle.reviews[index]
    invocation_path = _invocation_path(review_path)
    invocation = json.loads(invocation_path.read_text(encoding="utf-8"))
    mutate(invocation)
    _canonical_file(invocation_path, invocation)
    old_text = review_path.read_text(encoding="utf-8")
    lines = old_text.splitlines(keepends=True)
    for line_index, line in enumerate(lines):
        if line.startswith("launcher_proof_sha256:"):
            lines[line_index] = (
                f"launcher_proof_sha256: {sha256_bytes(invocation_path.read_bytes())}\n"
            )
            break
    review_path.write_text("".join(lines), encoding="utf-8")


def test_valid_review_panel_passes_and_cli_emits_canonical_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = make_bundle(tmp_path)

    result = _validate(bundle)

    assert result == {
        "finding_count": 2,
        "input_manifest_sha256": sha256_bytes(bundle.manifest.read_bytes()),
        "packet_sha256": sha256_bytes(bundle.packet.read_bytes()),
        "review_count": 3,
        "valid": True,
    }
    exit_code = main(
        [
            "--repo",
            str(bundle.repo),
            "--h0",
            bundle.h0,
            "--h1",
            bundle.h1,
            "--covered",
            bundle.covered_paths[0],
            "--instructions",
            bundle.instructions_path,
            "--packet",
            str(bundle.packet),
            "--input-manifest",
            str(bundle.manifest),
            "--freeze-receipt",
            str(bundle.receipt),
            "--disposition",
            str(bundle.disposition),
            "--files",
            *(str(path) for path in bundle.reviews),
        ]
    )
    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == result


def test_v3_reviewer_evidence_cannot_authorize_without_fable_final_gate(
    tmp_path: Path,
) -> None:
    bundle = make_bundle(tmp_path)
    receipt = json.loads(bundle.receipt.read_text(encoding="utf-8"))
    receipt["route_config_path"] = (
        "scripts/review_routes/worker-plane-council-v3.json"
    )
    _canonical_file(bundle.receipt, receipt)
    h1 = _commit(bundle.repo, "mark evidence as council v3")
    v3_bundle = replace(bundle, h1=h1)

    with pytest.raises(
        ReviewValidationError,
        match="final Fable gate is not implemented",
    ):
        _validate(v3_bundle)


@pytest.mark.parametrize("generator_version", ("1.0.0", "3.0.0", "forged"))
def test_v3_final_gate_blocker_does_not_trust_declared_generator_version(
    tmp_path: Path,
    generator_version: str,
) -> None:
    bundle = make_bundle(tmp_path)
    receipt = json.loads(bundle.receipt.read_text(encoding="utf-8"))
    receipt["route_config_path"] = (
        "scripts/review_routes/worker-plane-council-v3.json"
    )
    receipt["generator_version"] = generator_version
    _canonical_file(bundle.receipt, receipt)
    h1 = _commit(bundle.repo, "forge the declared generator version")

    with pytest.raises(
        ReviewValidationError,
        match="final Fable gate is not implemented",
    ):
        _validate(replace(bundle, h1=h1))


def test_rejects_external_only_review_artifacts(tmp_path: Path) -> None:
    bundle = _externalized_bundle(make_bundle(tmp_path))

    with pytest.raises(ReviewValidationError, match="inside --repo"):
        _validate(bundle)


@pytest.mark.parametrize(
    "artifact",
    (
        "packet",
        "manifest",
        "receipt",
        "disposition",
        "review",
        "raw",
        "stderr",
        "invocation",
    ),
)
def test_rejects_mutable_only_artifact_that_differs_from_h1(
    tmp_path: Path, artifact: str
) -> None:
    bundle = make_bundle(tmp_path)
    artifact_paths = {
        "packet": bundle.packet,
        "manifest": bundle.manifest,
        "receipt": bundle.receipt,
        "disposition": bundle.disposition,
        "review": bundle.reviews[0],
        "raw": _raw_path(bundle.reviews[1]),
        "stderr": bundle.reviews[2].with_suffix(".stderr.bin"),
        "invocation": _invocation_path(bundle.reviews[0]),
    }
    path = artifact_paths[artifact]
    path.write_bytes(path.read_bytes() + b"\n")

    with pytest.raises(ReviewValidationError, match="exact committed H1 Git blob"):
        _validate(bundle)


@pytest.mark.parametrize(
    ("transform", "error"),
    [
        (
            lambda text: text.replace("# Required amendments\n\n", "", 1),
            "exactly six",
        ),
        (
            lambda text: text.replace(
                "# What survives review", "# Preserved design", 1
            ),
            "heading order",
        ),
        (
            lambda text: text.replace(
                "# Important findings\n\nNone",
                "# Important findings\n\nNone\n\n# Extra heading\n\nSurprise",
                1,
            ),
            "exactly six",
        ),
        (
            lambda text: text.replace(
                "# What survives review\n\nThe generation fence",
                "# Required amendments\n\nRetain the measured gate.\n\n"
                "# What survives review\n\nThe generation fence",
                1,
            ).replace(
                "# Required amendments\n\nRetain the measured gate and bind every accepted finding to evidence.\n\n",
                "",
                1,
            ),
            "heading order",
        ),
        (
            lambda text: text.replace(
                "GO-WITH-CHANGES — confidence 91", "MAYBE — confidence 91", 1
            ),
            "verdict",
        ),
        (
            lambda text: text.replace(
                "The generation fence and reverse-cutover invariant remain coherent.",
                "TBD",
                1,
            ),
            "placeholder",
        ),
    ],
    ids=(
        "missing-heading",
        "renamed-heading",
        "extra-h1",
        "wrong-order",
        "invalid-verdict",
        "placeholder-body",
    ),
)
def test_rejects_malformed_review_contract(
    tmp_path: Path,
    transform: Callable[[str], str],
    error: str,
) -> None:
    bundle = make_bundle(tmp_path)
    _write_review(bundle, 0, transform)
    _commit_artifact_mutation(bundle)

    with pytest.raises(ReviewValidationError, match=error):
        _validate(bundle)


def test_rejects_finding_without_stable_id(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    _write_review(bundle, 0, lambda text: text.replace("[FABLE-B1] ", "", 1))
    _commit_artifact_mutation(bundle)

    with pytest.raises(ReviewValidationError, match="stable unique"):
        _validate(bundle)


def test_rejects_duplicate_finding_id_across_reviews(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    _rewrite_body_and_raw(
        bundle, 1, lambda text: text.replace("GEMINI-I1", "FABLE-B1", 1)
    )
    _commit_artifact_mutation(bundle)

    with pytest.raises(ReviewValidationError, match="duplicate finding"):
        _validate(bundle)


def test_rejects_absent_launcher_proof(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    _invocation_path(bundle.reviews[0]).unlink()
    _commit_artifact_mutation(bundle)

    with pytest.raises(ReviewValidationError, match="invocation companion"):
        _validate(bundle)


@pytest.mark.parametrize("field", ["input_manifest_sha256", "packet_sha256"])
def test_rejects_receipt_manifest_or_packet_sha_mismatch(
    tmp_path: Path, field: str
) -> None:
    bundle = make_bundle(tmp_path)
    receipt = json.loads(bundle.receipt.read_text(encoding="utf-8"))
    receipt[field] = "f" * 64
    _canonical_file(bundle.receipt, receipt)
    _commit_artifact_mutation(bundle)

    with pytest.raises(ReviewValidationError, match=field):
        _validate(bundle)


@pytest.mark.parametrize(
    ("case", "error"),
    [
        ("missing", "missing disposition"),
        ("duplicate", "duplicate disposition"),
        ("extra", "extra disposition"),
    ],
    ids=("missing", "duplicate", "extra"),
)
def test_rejects_non_exact_disposition_finding_ids(
    tmp_path: Path,
    case: str,
    error: str,
) -> None:
    bundle = make_bundle(tmp_path)
    text = bundle.disposition.read_text(encoding="utf-8")
    first_row = next(
        line for line in text.splitlines() if line.startswith("| FABLE-B1 |")
    )
    if case == "missing":
        text = text.replace(first_row + "\n", "", 1)
    elif case == "duplicate":
        text += first_row + "\n"
    else:
        text += first_row.replace("FABLE-B1", "EXTRA-B1", 1) + "\n"
    bundle.disposition.write_text(text, encoding="utf-8")
    _commit_artifact_mutation(bundle)

    with pytest.raises(ReviewValidationError, match=error):
        _validate(bundle)


@pytest.mark.parametrize(
    ("field", "error"),
    [
        ("rereview", "not resolved"),
        ("decision", "not resolved"),
        ("evidence", "deterministic evidence"),
        ("owning_commit", "resolved owning commit"),
    ],
    ids=(
        "rereview-unresolved",
        "decision-pending",
        "missing-evidence",
        "missing-owning-commit",
    ),
)
def test_rejects_unresolved_blocking_or_important_disposition(
    tmp_path: Path,
    field: str,
    error: str,
) -> None:
    bundle = make_bundle(tmp_path)
    text = bundle.disposition.read_text(encoding="utf-8")
    replacements = {
        "rereview": ("| resolved |", "| unresolved |"),
        "decision": ("| accepted |", "| pending |"),
        "evidence": (
            "evidence=test:tests/test_fence.py::test_legacy_fence; resolution=legacy claim fence implemented",
            "TBD",
        ),
        "owning_commit": (f"| {bundle.h0} | resolved |", "| none | resolved |"),
    }
    old, new = replacements[field]
    bundle.disposition.write_text(text.replace(old, new, 1), encoding="utf-8")
    _commit_artifact_mutation(bundle)

    with pytest.raises(ReviewValidationError, match=error):
        _validate(bundle)


def test_rejects_raw_response_sha_mismatch(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    raw_path = _raw_path(bundle.reviews[0])
    envelope = json.loads(raw_path.read_text(encoding="utf-8"))
    envelope["unexpected"] = True
    raw_path.write_bytes(canonical_json_bytes(envelope) + b"\n")
    _commit_artifact_mutation(bundle)

    with pytest.raises(ReviewValidationError, match="raw response SHA-256"):
        _validate(bundle)


def test_rejects_raw_stderr_sha_mismatch(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    changed = b"changed stderr"
    bundle.reviews[0].with_suffix(".stderr.bin").write_bytes(changed)
    _rewrite_invocation(
        bundle, 0, lambda receipt: receipt.__setitem__("stderr_bytes", len(changed))
    )
    _commit_artifact_mutation(bundle)

    with pytest.raises(ReviewValidationError, match="stderr SHA-256"):
        _validate(bundle)


def test_rejects_reviewer_repeating_packet_sha_instead_of_manifest_sha(
    tmp_path: Path,
) -> None:
    bundle = make_bundle(tmp_path)
    packet_sha = sha256_bytes(bundle.packet.read_bytes())
    manifest_sha = sha256_bytes(bundle.manifest.read_bytes())
    _rewrite_body_and_raw(
        bundle, 0, lambda text: text.replace(manifest_sha, packet_sha, 1)
    )
    _commit_artifact_mutation(bundle)

    with pytest.raises(
        ReviewValidationError, match="reviewer must repeat only input_manifest_sha256"
    ):
        _validate(bundle)


def test_rejects_attestation_only_h1_whose_projection_differs_from_h0(
    tmp_path: Path,
) -> None:
    bundle = make_bundle(tmp_path)
    _repo_file(bundle.repo, bundle.covered_paths[0], b"changed committed bytes\n")
    changed_h1 = _commit(bundle.repo, "change covered projection")

    with pytest.raises(
        ReviewValidationError, match=r"projection\(H1\) != projection\(H0\)"
    ):
        validate_review_panel(
            repo_root=bundle.repo,
            h0_ref=bundle.h0,
            h1_ref=changed_h1,
            covered_paths=bundle.covered_paths,
            covered_set=None,
            instructions_path=bundle.instructions_path,
            packet_path=bundle.packet,
            input_manifest_path=bundle.manifest,
            freeze_receipt_path=bundle.receipt,
            disposition_path=bundle.disposition,
            review_paths=bundle.reviews,
            executing_validator_path=bundle.validator_path,
        )


def test_requires_exactly_three_review_files(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)

    with pytest.raises(ReviewValidationError, match="exactly three"):
        validate_review_panel(
            repo_root=bundle.repo,
            h0_ref=bundle.h0,
            h1_ref=bundle.h1,
            covered_paths=bundle.covered_paths,
            covered_set=None,
            instructions_path=bundle.instructions_path,
            packet_path=bundle.packet,
            input_manifest_path=bundle.manifest,
            freeze_receipt_path=bundle.receipt,
            disposition_path=bundle.disposition,
            review_paths=bundle.reviews[:2],
            executing_validator_path=bundle.validator_path,
        )


def test_rejects_non_distinct_requested_routes(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)

    def duplicate_fable_route(value: dict[str, Any]) -> None:
        argv = [CLAUDE_EXECUTABLE, *_argv(ROUTES[0])]
        value["requested_route"] = ROUTES[0]
        value["seat"] = "fable"
        value["executable_path"] = CLAUDE_EXECUTABLE
        value["executable_sha256"] = CLAUDE_SHA256
        value["executable_cdhash"] = CLAUDE_CDHASH
        value["executable_team_identifier"] = "Q6L2SF6YDW"
        value["executable_designated_requirement"] = CLAUDE_REQUIREMENT
        value["argv"] = argv
        value["argv_sha256"] = sha256_bytes(canonical_json_bytes(argv))

    _rewrite_invocation(bundle, 1, duplicate_fable_route)
    _write_review(
        bundle,
        1,
        lambda text: text.replace(
            f"requested_route: {ROUTES[1]}", f"requested_route: {ROUTES[0]}", 1
        ),
    )
    _commit_artifact_mutation(bundle)

    with pytest.raises(ReviewValidationError, match="distinct requested routes"):
        _validate(bundle)


def test_rejects_duplicate_launcher_uuid(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    first = json.loads(_invocation_path(bundle.reviews[0]).read_text(encoding="utf-8"))
    duplicate = first["launcher_invocation_uuid"]
    _rewrite_invocation(
        bundle,
        1,
        lambda value: value.__setitem__("launcher_invocation_uuid", duplicate),
    )
    _write_review(
        bundle,
        1,
        lambda text: text.replace(
            next(
                line
                for line in text.splitlines()
                if line.startswith("launcher_invocation_uuid:")
            ),
            f"launcher_invocation_uuid: {duplicate}",
            1,
        ),
    )
    _commit_artifact_mutation(bundle)

    with pytest.raises(ReviewValidationError, match="unique launcher"):
        _validate(bundle)


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("executable_path", "/usr/bin/env", "executable_path"),
        ("executable_sha256", "bad", "executable_sha256"),
        ("argv_sha256", "0" * 64, "argv_sha256"),
        ("cwd_initial_entries", ["checkout"], "empty cwd"),
        ("cwd_mode", "0755", "0700"),
        ("descendants_absent_after_run", False, "descendants_absent_after_run"),
        ("home_path", "/tmp/wrong-home", "home_path"),
        ("max_output_bytes", 0, "max_output_bytes"),
        ("output_spooled", False, "output_spooled"),
        ("process_group_isolated", False, "process_group_isolated"),
        ("review_input_bytes", 0, "review-input attestation"),
        ("review_input_schema", "wrong", "review-input attestation"),
        ("review_input_sha256", "0" * 64, "review-input attestation"),
        ("tools_denied", False, "tools denied"),
        ("wall_timeout_seconds", 0, "wall_timeout_seconds"),
        ("xdg_config_home", "/tmp/wrong-xdg", "xdg_config_home"),
        ("shell", True, "shell=false"),
        ("exit_status", 1, "exit status"),
    ],
)
def test_rejects_invalid_invocation_proof(
    tmp_path: Path,
    field: str,
    value: Any,
    error: str,
) -> None:
    bundle = make_bundle(tmp_path)
    _rewrite_invocation(bundle, 0, lambda receipt: receipt.__setitem__(field, value))
    _commit_artifact_mutation(bundle)

    with pytest.raises(ReviewValidationError, match=error):
        _validate(bundle)


def test_rejects_glm_route_config_hash_mismatch(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    _rewrite_invocation(
        bundle, 2, lambda receipt: receipt.__setitem__("route_config_sha256", "b" * 64)
    )
    _commit_artifact_mutation(bundle)

    with pytest.raises(ReviewValidationError, match="route_config_sha256"):
        _validate(bundle)


def test_rejects_gemini_client_older_than_pinned_minimum(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    _rewrite_invocation(
        bundle, 1, lambda receipt: receipt.__setitem__("client_version", "agy 1.1.1")
    )
    _commit_artifact_mutation(bundle)

    with pytest.raises(ReviewValidationError, match="Gemini client version"):
        _validate(bundle)


def test_rejects_raw_body_that_was_edited_during_normalization(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    _write_review(
        bundle,
        2,
        lambda text: text.replace("reverse-cutover invariant", "edited invariant", 1),
    )
    _commit_artifact_mutation(bundle)

    with pytest.raises(ReviewValidationError, match="unedited raw model body"):
        _validate(bundle)


def test_projection_validation_requires_committed_h0_and_h1_git_objects(
    tmp_path: Path,
) -> None:
    """A copied H0 manifest is not evidence that the committed H1 projection matches."""
    bundle = make_bundle(tmp_path)

    _repo_file(bundle.repo, bundle.covered_paths[0], b"H1 bytes differ\n")
    changed_h1 = _commit(bundle.repo, "change H1 covered bytes")

    with pytest.raises(
        ReviewValidationError, match=r"projection\(H1\) != projection\(H0\)"
    ):
        validate_review_panel(
            repo_root=bundle.repo,
            h0_ref=bundle.h0,
            h1_ref=changed_h1,
            covered_paths=bundle.covered_paths,
            covered_set=None,
            instructions_path="docs/00-review-brief.md",
            packet_path=bundle.packet,
            input_manifest_path=bundle.manifest,
            freeze_receipt_path=bundle.receipt,
            disposition_path=bundle.disposition,
            review_paths=bundle.reviews,
            executing_validator_path=bundle.validator_path,
        )


def test_validator_cli_runs_directly_outside_repository_cwd(tmp_path: Path) -> None:
    """The documented script entrypoint must not rely on PYTHONPATH or repo cwd."""
    repository_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            str(repository_root / "scripts/check_worker_plane_review.py"),
            "--help",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
