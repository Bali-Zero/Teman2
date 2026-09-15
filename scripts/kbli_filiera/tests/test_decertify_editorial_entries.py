"""Unit tests for scripts/kbli_filiera/decertify_editorial_entries.py — guilt
(drifted hash refused, wrong section refused), innocence (removal exact,
every other entry byte-identical) and idempotency, all on temp copies of the
real registry — never the tracked file itself."""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from kbli_filiera import decertify_editorial_entries as decert  # noqa: E402

REAL_REGISTRY = Path(__file__).resolve().parents[3] / decert.REGISTRY


def _registry_copy(tmp_path: Path) -> Path:
    dest = tmp_path / "registry.json"
    shutil.copy(REAL_REGISTRY, dest)
    return dest


def _spec(tmp_path: Path, entries: list[dict]) -> Path:
    path = tmp_path / "spec.json"
    path.write_text(json.dumps({"entries": entries}), encoding="utf-8")
    return path


def _entry(sha: str) -> dict:
    return {
        "section": "canonicalIntel",
        "code": "47221",
        "reason": "test",
        "expected_content_sha256": sha,
    }


def test_drifted_hash_is_refused(tmp_path: Path) -> None:
    registry = _registry_copy(tmp_path)
    before = registry.read_bytes()
    spec = _spec(tmp_path, [_entry("0" * 64)])
    assert decert.run(spec, apply=True, registry_path=registry) == 2
    assert registry.read_bytes() == before


def test_wrong_section_is_refused(tmp_path: Path) -> None:
    registry = _registry_copy(tmp_path)
    before = registry.read_bytes()
    spec = _spec(
        tmp_path,
        [{"section": "bogusSection", "code": "47221", "reason": "x", "expected_content_sha256": "x"}],
    )
    assert decert.run(spec, apply=True, registry_path=registry) == 2
    assert registry.read_bytes() == before


def _real_47221_sha() -> str:
    return json.loads(REAL_REGISTRY.read_text())["canonicalIntel"]["47221"]["contentSha256"]


def test_removal_is_exact_and_others_byte_identical(tmp_path: Path) -> None:
    registry = _registry_copy(tmp_path)
    before = json.loads(registry.read_text())
    spec = _spec(tmp_path, [_entry(_real_47221_sha())])
    assert decert.run(spec, apply=True, registry_path=registry) == 0
    after = json.loads(registry.read_text())
    assert "47221" not in after["canonicalIntel"]
    del before["canonicalIntel"]["47221"]
    assert after == before
    assert after["sourceDatasetSha256"] == before["sourceDatasetSha256"]
    assert after["reviewedAt"] == before["reviewedAt"]
    assert "47221" in after["mouthGold"], "canonicalIntel-only spec must not touch mouthGold"


def test_second_apply_is_a_byte_identical_noop(tmp_path: Path) -> None:
    registry = _registry_copy(tmp_path)
    spec = _spec(tmp_path, [_entry(_real_47221_sha())])
    assert decert.run(spec, apply=True, registry_path=registry) == 0
    once = registry.read_bytes()
    assert decert.run(spec, apply=True, registry_path=registry) == 0
    assert registry.read_bytes() == once


def test_check_mode_never_writes(tmp_path: Path) -> None:
    registry = _registry_copy(tmp_path)
    before = registry.read_bytes()
    spec = _spec(tmp_path, [_entry(_real_47221_sha())])
    assert decert.run(spec, apply=False, registry_path=registry) == 0
    assert registry.read_bytes() == before
