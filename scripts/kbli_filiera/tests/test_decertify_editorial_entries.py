"""Unit tests for scripts/kbli_filiera/decertify_editorial_entries.py — guilt
(drifted hash refused, wrong section refused), innocence (removal exact,
every other entry byte-identical) and idempotency, all on a SYNTHETIC,
self-contained registry fixture written fresh per test — never the tracked
data/kbli-filiera/pma-editorial-certifications.json file, whose real
`canonicalIntel["47221"]` this same PR's other commit removes. A fixture
built from the live file would break the moment that removal lands (as
happened here first: the earlier version of this test read the real
registry for its "known-good" premise hash and KeyError'd once 47221 was
actually de-certified by the sibling commit)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from kbli_filiera import decertify_editorial_entries as decert  # noqa: E402

_GOOD_SHA = "b" * 64


def _registry_copy(tmp_path: Path) -> Path:
    dest = tmp_path / "registry.json"
    dest.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "hashAlgorithm": "sha256-stable-json-v1",
                "reviewedAt": "2026-09-15",
                "sourceDatasetSha256": "a" * 64,
                "canonicalIntel": {
                    "47221": {"pmaFingerprint": "c" * 64, "contentSha256": _GOOD_SHA},
                    "99999": {"pmaFingerprint": "d" * 64, "contentSha256": "e" * 64},
                },
                "mouthGold": {
                    "47221": {"pmaFingerprint": "c" * 64, "contentSha256": "f" * 64},
                },
                "standaloneGold": {},
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
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


def test_removal_is_exact_and_others_byte_identical(tmp_path: Path) -> None:
    registry = _registry_copy(tmp_path)
    before = json.loads(registry.read_text())
    spec = _spec(tmp_path, [_entry(_GOOD_SHA)])
    assert decert.run(spec, apply=True, registry_path=registry) == 0
    after = json.loads(registry.read_text())
    assert "47221" not in after["canonicalIntel"]
    assert after["canonicalIntel"]["99999"] == before["canonicalIntel"]["99999"]
    del before["canonicalIntel"]["47221"]
    assert after == before
    assert after["sourceDatasetSha256"] == before["sourceDatasetSha256"]
    assert after["reviewedAt"] == before["reviewedAt"]
    assert "47221" in after["mouthGold"], "canonicalIntel-only spec must not touch mouthGold"


def test_second_apply_is_a_byte_identical_noop(tmp_path: Path) -> None:
    registry = _registry_copy(tmp_path)
    spec = _spec(tmp_path, [_entry(_GOOD_SHA)])
    assert decert.run(spec, apply=True, registry_path=registry) == 0
    once = registry.read_bytes()
    assert decert.run(spec, apply=True, registry_path=registry) == 0
    assert registry.read_bytes() == once


def test_check_mode_never_writes(tmp_path: Path) -> None:
    registry = _registry_copy(tmp_path)
    before = registry.read_bytes()
    spec = _spec(tmp_path, [_entry(_GOOD_SHA)])
    assert decert.run(spec, apply=False, registry_path=registry) == 0
    assert registry.read_bytes() == before
