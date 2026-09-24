"""Guilt, refusal and idempotency for reissue_editorial_content_certs.py, on a
SYNTHETIC registry and canonical written fresh per test — never the tracked
registry, which this compiler's own PR rewrites. The hashers are injected, so
the suite never imports the backend package (the filiera CI job does not
install it); the real `stable_editorial_sha256` is exercised by the backend's
own certification tests against the shipped registry.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

_FILIERA = str(Path(__file__).resolve().parents[1])
if _FILIERA not in sys.path:
    sys.path.insert(0, _FILIERA)

import reissue_editorial_content_certs as R  # noqa: E402


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def content_sha(value) -> str:
    return sha(json.dumps(value, sort_keys=True, ensure_ascii=False))


def pma_fp(record) -> str:
    return sha(json.dumps([record.get("pma_status"), record.get("pma_max_asing")]))


OLD = "a PT PMA can hold up to 49% of the company"
NEW = "foreign shareholders can hold up to 49% of a PT PMA"


def record(code: str, what: str = OLD, body: str = "Scope.", cap: int = 49) -> dict:
    return {
        "kode_kbli_2025": code,
        "pma_status": "TERBATAS",
        "pma_max_asing": cap,
        "intel_2026": {"whatYouNeed": what, "editorial": {"body": body}},
    }


def spec(*codes: str) -> dict:
    return {
        "compiler": "cure_prose_national_openness",
        "codes": {
            c: {
                "expect": {"pma_max_asing": 49, "pma_status": "TERBATAS"},
                "fields": {"whatYouNeed": {"old_sha256": sha(OLD), "new": NEW}},
            }
            for c in codes
        },
    }


def setup(tmp_path: Path, base: list[dict], live: list[dict], certified: list[str], sp: dict):
    registry = {
        "schemaVersion": 1,
        "hashAlgorithm": "sha256-stable-json-v1",
        "reviewedAt": "2026-09-23",
        "sourceDatasetSha256": "a" * 64,
        "canonicalIntel": {
            r["kode_kbli_2025"]: {"pmaFingerprint": pma_fp(r), "contentSha256": content_sha(r["intel_2026"])}
            for r in base
            if r["kode_kbli_2025"] in certified
        },
        "mouthGold": {"50124": {"pmaFingerprint": "c" * 64, "contentSha256": "d" * 64}},
        "standaloneGold": {},
    }
    paths = {}
    for name, payload in (("spec", sp), ("canonical", {"data": live}), ("registry", registry)):
        paths[name] = tmp_path / f"{name}.json"
        paths[name].write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return paths


def go(paths: dict, base: list[dict], apply: bool = True) -> int:
    return R.run(paths["spec"], base, paths["canonical"], paths["registry"], apply, content_sha, pma_fp)


def cured(r: dict) -> dict:
    out = copy.deepcopy(r)
    out["intel_2026"]["whatYouNeed"] = NEW
    return out


def test_guilt_a_cured_certified_code_gets_the_hash_of_its_live_bytes(tmp_path: Path):
    base = [record("50124"), record("50125"), record("99999", what="untouched")]
    live = [cured(base[0]), cured(base[1]), base[2]]
    paths = setup(tmp_path, base, live, ["50124", "99999"], spec("50124", "50125"))
    before = json.loads(paths["registry"].read_text())

    assert go(paths, base) == 0

    after = json.loads(paths["registry"].read_text())
    assert after["canonicalIntel"]["50124"]["contentSha256"] == content_sha(live[0]["intel_2026"])
    assert after["canonicalIntel"]["50124"]["pmaFingerprint"] == before["canonicalIntel"]["50124"]["pmaFingerprint"]
    assert after["canonicalIntel"]["99999"] == before["canonicalIntel"]["99999"]
    assert "50125" not in after["canonicalIntel"], "an uncertified code must never be certified by a re-issue"
    for key in ("mouthGold", "standaloneGold", "sourceDatasetSha256", "reviewedAt"):
        assert after[key] == before[key]


def test_refusal_when_live_bytes_moved_beyond_the_spec(tmp_path: Path):
    base = [record("50124")]
    live = [cured(base[0])]
    live[0]["intel_2026"]["editorial"]["body"] = "Scope, plus an ungraded sentence."
    paths = setup(tmp_path, base, live, ["50124"], spec("50124"))
    before = paths["registry"].read_bytes()

    assert go(paths, base) == 2
    assert paths["registry"].read_bytes() == before


def test_refusal_when_the_registry_did_not_certify_the_base_bytes(tmp_path: Path):
    base = [record("50124")]
    stale = [record("50124", body="An older body the registry once saw.")]
    paths = setup(tmp_path, stale, [cured(base[0])], ["50124"], spec("50124"))
    before = paths["registry"].read_bytes()

    assert go(paths, base) == 2
    assert paths["registry"].read_bytes() == before


def test_refusal_when_the_pma_fingerprint_moved(tmp_path: Path):
    base = [record("50124")]
    live = [cured(base[0])]
    live[0]["pma_max_asing"] = 51
    paths = setup(tmp_path, base, live, ["50124"], spec("50124"))
    before = paths["registry"].read_bytes()

    assert go(paths, base) == 2
    assert paths["registry"].read_bytes() == before


def test_refusal_when_the_base_text_is_not_the_graded_text(tmp_path: Path):
    base = [record("50124", what="a different paragraph")]
    live = [cured(base[0])]
    paths = setup(tmp_path, base, live, ["50124"], spec("50124"))

    assert go(paths, base) == 2


def test_refusal_on_a_spec_from_another_compiler(tmp_path: Path):
    base = [record("50124")]
    sp = spec("50124")
    sp["compiler"] = "some_other_cure"
    paths = setup(tmp_path, base, [cured(base[0])], ["50124"], sp)

    assert go(paths, base) == 2


def test_dry_run_writes_nothing(tmp_path: Path):
    base = [record("50124")]
    paths = setup(tmp_path, base, [cured(base[0])], ["50124"], spec("50124"))
    before = paths["registry"].read_bytes()

    assert go(paths, base, apply=False) == 0
    assert paths["registry"].read_bytes() == before


def test_a_second_run_is_a_no_op(tmp_path: Path):
    base = [record("50124")]
    paths = setup(tmp_path, base, [cured(base[0])], ["50124"], spec("50124"))

    assert go(paths, base) == 0
    once = paths["registry"].read_bytes()
    assert go(paths, base) == 0
    assert paths["registry"].read_bytes() == once


def test_refusal_when_a_value_flips_type_that_python_equality_calls_equal(tmp_path: Path):
    base = [record("50124")]
    base[0]["intel_2026"]["editorial"]["rank"] = 1
    live = [cured(base[0])]
    live[0]["intel_2026"]["editorial"]["rank"] = True
    assert live[0]["intel_2026"]["editorial"] == cured(base[0])["intel_2026"]["editorial"]
    paths = setup(tmp_path, base, live, ["50124"], spec("50124"))
    before = paths["registry"].read_bytes()

    assert go(paths, base) == 2
    assert paths["registry"].read_bytes() == before


def test_an_already_reissued_entry_still_walks_the_chain(tmp_path: Path):
    base = [record("50124")]
    paths = setup(tmp_path, base, [cured(base[0])], ["50124"], spec("50124"))
    assert go(paths, base) == 0

    drifted = cured(base[0])
    drifted["intel_2026"]["editorial"]["body"] = "Scope, plus an ungraded sentence."
    registry = json.loads(paths["registry"].read_text())
    registry["canonicalIntel"]["50124"]["contentSha256"] = content_sha(drifted["intel_2026"])
    paths["registry"].write_text(json.dumps(registry), encoding="utf-8")
    paths["canonical"].write_text(json.dumps({"data": [drifted]}), encoding="utf-8")

    assert go(paths, base) == 2, "a live hash already in the registry must not excuse unreviewed bytes"


def test_refusal_on_a_spec_that_repeats_a_key(tmp_path: Path):
    base = [record("50124")]
    paths = setup(tmp_path, base, [cured(base[0])], ["50124"], spec("50124"))
    field = json.dumps({"old_sha256": sha(OLD), "new": NEW})
    paths["spec"].write_text(
        '{"compiler": "cure_prose_national_openness", "codes": {"50124": {"expect": {}, '
        f'"fields": {{"whatYouNeed": {field}, "whatYouNeed": {field}}}}}}}}}',
        encoding="utf-8",
    )
    before = paths["registry"].read_bytes()

    assert go(paths, base) == 2
    assert paths["registry"].read_bytes() == before


def test_guilt_an_indexed_path_is_reached_and_checked(tmp_path: Path):
    base = [record("50124")]
    base[0]["intel_2026"]["editorial"]["byTheNumbers"] = [{"value": OLD}, {"value": "untouched"}]
    live = [copy.deepcopy(base[0])]
    live[0]["intel_2026"]["editorial"]["byTheNumbers"][0]["value"] = NEW
    sp = spec("50124")
    sp["codes"]["50124"]["fields"] = {"editorial.byTheNumbers[0].value": {"old_sha256": sha(OLD), "new": NEW}}
    paths = setup(tmp_path, base, live, ["50124"], sp)
    assert go(paths, base) == 0
    assert json.loads(paths["registry"].read_text())["canonicalIntel"]["50124"]["contentSha256"] == content_sha(
        live[0]["intel_2026"]
    )

    collateral = copy.deepcopy(live)
    collateral[0]["intel_2026"]["editorial"]["byTheNumbers"][1]["value"] = "moved"
    (tmp_path / "c").mkdir()
    paths = setup(tmp_path / "c", base, collateral, ["50124"], sp)
    assert go(paths, base) == 2
