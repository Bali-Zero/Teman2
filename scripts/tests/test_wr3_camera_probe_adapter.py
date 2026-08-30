"""E13 camera-probe adapter: immutable source, unique lineage, safe runtime."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
ADAPTER = SCRIPTS / "wr3_camera_probe_adapter.py"
EPISODE = REPO_ROOT / "docs/wr3/factory/episodes/s01e13-residency-permit"
PLAN = EPISODE / "probes/probe-plan.json"
TRANSPORT_UI_TRIGGERS = (
    "camera first",
    "vertical 9:16",
    "9:16",
    "720x1280",
    "aspect ratio",
    "aspect-ratio",
    "frame rate",
    "frame-rate",
    "fps label",
    "camera ui",
    "camera user interface",
    "technical overlay",
    "lens label",
    "framing guide",
    "contact sheet",
    "split screen",
    "reference-image display",
    "letterbox",
    "pillarbox",
    "visible text",
)
GLOBAL_NEGATIVE_PROTECTIONS = (
    "on-screen camera user interface",
    "technical overlays",
    "aspect-ratio labels",
    "frame-rate labels",
    "fps labels",
    "lens labels",
    "framing guides",
    "contact sheet",
    "split screen",
    "reference-image display",
    "letterbox bars",
    "pillarbox bars",
    "any visible text",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(
    output_root: Path,
    *,
    repo_root: Path = REPO_ROOT,
    plan: Path = PLAN,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(ADAPTER),
            "--repo-root",
            str(repo_root),
            "--plan",
            str(plan),
            "--output-root",
            str(output_root),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


@pytest.fixture
def source_hashes() -> dict[Path, str]:
    plan = json.loads(PLAN.read_text())
    paths = [REPO_ROOT / family["source_pack"] for family in plan["families"]]
    return {path: _sha(path) for path in paths}


def test_real_e13_plan_derives_24_unique_renderer_safe_probes(
    tmp_path: Path,
    source_hashes: dict[Path, str],
) -> None:
    output = tmp_path / "runtime"
    result = _run(output)
    assert result.returncode == 0, result.stderr or result.stdout

    verdict = json.loads((output / "probe-gate-verdict.json").read_text())
    assert verdict["verdict"] == "PASS"
    assert verdict["checks"]["authorization"]["generation_count"] == 24
    assert verdict["checks"]["global_uniqueness"]["passed"] is True
    assert verdict["checks"]["flow_or_publish_side_effects"]["count"] == 0

    packs = [
        json.loads(path.read_text())
        for path in sorted(output.glob("f*/shot-pack.json"))
    ]
    assert len(packs) == 6
    shots = [shot for pack in packs for shot in pack["shots"]]
    assert len(shots) == 24
    assert len({pack["episode_id"] for pack in packs}) == 6
    assert len({shot["shot_id"] for shot in shots}) == 24
    assert len({shot["global_probe_id"] for shot in shots}) == 24
    assert len({shot["variant_seed_id"] for shot in shots}) == 24

    for pack in packs:
        assert pack["schema_version"] == "wr3-camera-probe-runtime/1.0"
        assert pack["adapter_version"] == "1.2"
        assert pack["creative_seed_id"]
        assert pack["originality_gate"]["verdict"] == "PASS"
        assert pack["originality_gate"]["signature_sha256"] == (
            "b9a98c97a22e73240455e37b63bb4b6ca950164668910458220a722fa365d8ac"
        )
        originality_receipt = REPO_ROOT / pack["originality_gate"]["receipt_path"]
        assert pack["originality_gate"]["receipt_sha256"] == _sha(originality_receipt)
        assert pack["family_id"]
        assert pack["source_pack_sha256"] == _sha(REPO_ROOT / pack["source_pack"])
        assert len(pack["transition_map"]["entries"]) == 4
        assert pack["identity_token"] == "A007"
        for shot in pack["shots"]:
            # Both renderer dialects are present and bound to identical text.
            assert shot["prompt_positive"] == shot["positive_prompt"]
            assert shot["prompt_negative"] == shot["negative_prompt"]
            assert shot["shot_type"] == "zantara-camera-probe"
            assert shot["identity_tokens"] == ["A007"]
            assert shot["transition_to_next"] is None
            assert 60 <= len(shot["prompt_positive"].split()) <= 135

    for path, before in source_hashes.items():
        assert _sha(path) == before, f"source pack was modified: {path}"


def test_runtime_prompts_remove_transport_ui_triggers_but_keep_camera_direction(
    tmp_path: Path,
) -> None:
    output = tmp_path / "runtime"
    result = _run(output)
    assert result.returncode == 0, result.stderr or result.stdout

    shots = [
        shot
        for path in sorted(output.glob("f*/shot-pack.json"))
        for shot in json.loads(path.read_text())["shots"]
    ]
    assert len(shots) == 24
    for shot in shots:
        positive = shot["prompt_positive"].lower()
        negative = shot["prompt_negative"].lower()
        assert not any(trigger in positive for trigger in TRANSPORT_UI_TRIGGERS)
        assert all(protection in negative for protection in GLOBAL_NEGATIVE_PROTECTIONS)
        assert re.search(r"\b\d{2}mm\b", positive), positive
        assert any(
            term in positive
            for term in ("track", "camera", "lens", "static", "locked", "dolly", "move")
        )
        assert "  " not in shot["prompt_positive"]
        assert ", ," not in shot["prompt_positive"]
        assert " ;" not in shot["prompt_positive"]


def test_every_family_receipt_binds_exact_source_and_runtime_bytes(
    tmp_path: Path,
) -> None:
    output = tmp_path / "runtime"
    result = _run(output)
    assert result.returncode == 0, result.stderr or result.stdout

    for receipt_path in sorted(output.glob("f*/lineage-receipt.json")):
        receipt = json.loads(receipt_path.read_text())
        source = REPO_ROOT / receipt["source_pack"]
        runtime = output / receipt["runtime_pack"]
        assert receipt["source_pack_sha256"] == _sha(source)
        assert receipt["runtime_pack_sha256"] == _sha(runtime)
        assert len(receipt["variants"]) == 4
        assert all(item["variant_seed_id"] for item in receipt["variants"])


def test_f06_is_visual_only_and_contains_no_legal_claim_language(
    tmp_path: Path,
) -> None:
    output = tmp_path / "runtime"
    result = _run(output)
    assert result.returncode == 0, result.stderr or result.stdout
    pack = json.loads((output / "f06-static-verdict/shot-pack.json").read_text())

    forbidden = (
        "residence",
        "residency",
        "permit",
        "permission",
        "status",
        "rights",
        "says",
        "speaks",
        "voice",
        "dialogue",
        "\u201c",
        '"',
    )
    for shot in pack["shots"]:
        positive = shot["prompt_positive"].lower()
        assert shot["audio_mode"] == "native-ambient-only"
        assert "naturally closed lips" in positive
        assert not any(term in positive for term in forbidden)
        assert "speech" in shot["prompt_negative"].lower()
        assert "lip sync" in shot["prompt_negative"].lower()


def test_adapter_is_deterministic_for_same_approved_inputs(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    assert _run(first).returncode == 0
    assert _run(second).returncode == 0
    first_packs = {
        path.parent.name: _sha(path) for path in first.glob("f*/shot-pack.json")
    }
    second_packs = {
        path.parent.name: _sha(path) for path in second.glob("f*/shot-pack.json")
    }
    assert first_packs == second_packs


def test_tampered_family_fails_closed_before_any_runtime_pack_is_written(
    tmp_path: Path,
) -> None:
    repo_copy = tmp_path / "repo"
    docs_copy = repo_copy / "docs/wr3/factory/episodes/s01e13-residency-permit"
    shutil.copytree(EPISODE, docs_copy)
    plan_copy = docs_copy / "probes/probe-plan.json"
    plan = json.loads(plan_copy.read_text())
    source_ref = plan["families"][0]["source_pack"]
    source = repo_copy / source_ref
    source_data = json.loads(source.read_text())
    source_data["shots"][1]["index"] = 1
    source.write_text(json.dumps(source_data, indent=2))

    output = tmp_path / "failed-runtime"
    result = _run(output, repo_root=repo_copy, plan=plan_copy)
    assert result.returncode == 2
    verdict = json.loads((output / "probe-gate-verdict.json").read_text())
    assert verdict["verdict"] == "FAIL"
    assert "expected source index 2, got 1" in verdict["errors"][0]
    assert list(output.glob("f*/shot-pack.json")) == []


def test_tampered_originality_evidence_fails_before_runtime_write(
    tmp_path: Path,
) -> None:
    repo_copy = tmp_path / "repo"
    docs_copy = repo_copy / "docs/wr3/factory/episodes/s01e13-residency-permit"
    shutil.copytree(EPISODE, docs_copy)
    receipt = docs_copy / "originality-receipt.json"
    payload = json.loads(receipt.read_text())
    payload["signature_sha256"] = "0" * 64
    receipt.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    output = tmp_path / "failed-originality-runtime"
    result = _run(
        output,
        repo_root=repo_copy,
        plan=docs_copy / "probes/probe-plan.json",
    )

    assert result.returncode == 2
    verdict = json.loads((output / "probe-gate-verdict.json").read_text())
    assert verdict["verdict"] == "FAIL"
    assert "originality receipt SHA mismatch" in verdict["errors"][0]
    assert list(output.glob("f*/shot-pack.json")) == []


def test_failed_rederivation_invalidates_previous_runtime_authorization(
    tmp_path: Path,
) -> None:
    """Old family bytes may remain, but a current FAIL makes them unspendable."""
    repo_copy = tmp_path / "repo"
    docs_copy = repo_copy / "docs/wr3/factory/episodes/s01e13-residency-permit"
    shutil.copytree(EPISODE, docs_copy)
    plan_copy = docs_copy / "probes/probe-plan.json"
    output = tmp_path / "runtime"

    first = _run(output, repo_root=repo_copy, plan=plan_copy)
    assert first.returncode == 0, first.stderr or first.stdout
    old_packs = {
        path.relative_to(output): _sha(path)
        for path in sorted(output.glob("f*/shot-pack.json"))
    }
    assert len(old_packs) == 6
    assert (
        json.loads((output / "probe-gate-verdict.json").read_text())["verdict"]
        == "PASS"
    )

    receipt = docs_copy / "originality-receipt.json"
    payload = json.loads(receipt.read_text())
    payload["signature_sha256"] = "0" * 64
    receipt.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    second = _run(output, repo_root=repo_copy, plan=plan_copy)
    assert second.returncode == 2
    verdict = json.loads((output / "probe-gate-verdict.json").read_text())
    assert verdict["verdict"] == "FAIL"
    assert "originality receipt SHA mismatch" in verdict["errors"][0]
    assert {
        path.relative_to(output): _sha(path)
        for path in sorted(output.glob("f*/shot-pack.json"))
    } == old_packs
