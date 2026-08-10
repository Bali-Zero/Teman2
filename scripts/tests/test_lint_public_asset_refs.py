"""Corpus for scripts/lint_public_asset_refs.py.

Superscar #3 contract: a guard is not merged without BOTH guilt (it fires on the
defect) AND innocence (it stays silent on the legitimate neighbour). The
innocence half is the load-bearing one here — this lint walks 1000+ files of a
live app, and a single false-positive class is how a gate gets switched off.

Deliberately NOT homogeneous (W116): the innocence fixtures are shapes that
already existed in the repo BEFORE this lint was written — a `.test.tsx` writing
`/broken.png` on purpose, `/favicon.ico` served by the app/ convention — not
shapes invented to match what the probe expects.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lint_public_asset_refs import (  # noqa: E402
    EXIT_CLEAN,
    EXIT_FINDINGS,
    EXIT_OPERATIONAL,
    main,
)

BASE_CONFIG: dict = {
    "roots": [{"src": "app/src", "public": "app/public"}],
    "code_suffixes": [".tsx", ".ts"],
    "exclude_path_globs": ["**/__tests__/**", "**/*.test.tsx", "**/*.d.ts"],
    "asset_extensions": ["mp4", "png", "jpg", "svg", "ico", "txt"],
    "ignore_prefixes": ["/_next/", "/api/"],
    "framework_served": ["/favicon.ico", "/robots.txt"],
    "known_missing": [],
}


def build_tree(
    tmp_path: Path,
    code: dict[str, str],
    public_files: list[str],
    config_overrides: dict | None = None,
) -> tuple[Path, Path]:
    """Return (repo_root, config_path)."""
    for rel, body in code.items():
        target = tmp_path / "app" / "src" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    for rel in public_files:
        target = tmp_path / "app" / "public" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"\x00binary-asset")
    (tmp_path / "app" / "public").mkdir(parents=True, exist_ok=True)

    cfg = json.loads(json.dumps(BASE_CONFIG))
    cfg.update(config_overrides or {})
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    return tmp_path, cfg_path


def run(repo: Path, cfg: Path) -> int:
    return main(["--repo-root", str(repo), "--config", str(cfg)])


# ---------------------------------------------------------------- guilt


def test_guilt_missing_asset_is_reported(tmp_path: Path) -> None:
    repo, cfg = build_tree(
        tmp_path,
        {"app/page.tsx": '<img src="/images/hero.png" />'},
        public_files=[],
    )
    assert run(repo, cfg) == EXIT_FINDINGS


def test_guilt_scar_pin_the_exact_kbli_shape(tmp_path: Path) -> None:
    """W-shape 2026-08-07: `public/video/` exists (SINGULAR) and the code asks
    for `/videos/...` (PLURAL). The near-miss directory is what made this
    survive review — a lint that only checked "is there a video dir?" passes."""
    repo, cfg = build_tree(
        tmp_path,
        {
            "app/kbli/page.tsx": (
                '<video src="/videos/kbli-demo.mp4" autoPlay loop '
                'playsInline controls />'
            )
        },
        public_files=["video/bali-ambient-loop.mp4"],
    )
    assert run(repo, cfg) == EXIT_FINDINGS


def test_guilt_stale_registry_entry_when_asset_reappears(tmp_path: Path) -> None:
    """The registry must shrink. An entry whose asset now EXISTS is stale."""
    repo, cfg = build_tree(
        tmp_path,
        {"app/page.tsx": '<img src="/images/hero.png" />'},
        public_files=["images/hero.png"],
        config_overrides={
            "known_missing": [{"path": "/images/hero.png", "reason": "historical"}]
        },
    )
    assert run(repo, cfg) == EXIT_FINDINGS


def test_guilt_stale_registry_entry_when_reference_is_deleted(tmp_path: Path) -> None:
    """An entry nothing references any more is also stale — otherwise the list
    outlives its defects and quietly becomes an exemption list."""
    repo, cfg = build_tree(
        tmp_path,
        {"app/page.tsx": "export default function Page() { return null }"},
        public_files=[],
        config_overrides={
            "known_missing": [{"path": "/images/gone.png", "reason": "historical"}]
        },
    )
    assert run(repo, cfg) == EXIT_FINDINGS


# ------------------------------------------------------------- innocence


def test_innocence_existing_asset_is_silent(tmp_path: Path) -> None:
    repo, cfg = build_tree(
        tmp_path,
        {"app/page.tsx": '<img src="/images/hero.png" />'},
        public_files=["images/hero.png"],
    )
    assert run(repo, cfg) == EXIT_CLEAN


def test_innocence_test_file_fixture_path_is_not_a_defect(tmp_path: Path) -> None:
    """A test that writes `/broken.png` on purpose, to prove a fallback renders,
    is doing its job. Flagging it teaches people to delete honest tests."""
    repo, cfg = build_tree(
        tmp_path,
        {"components/avatar.test.tsx": 'render(<Avatar src="/broken.png" />)'},
        public_files=[],
    )
    assert run(repo, cfg) == EXIT_CLEAN


def test_innocence_framework_served_paths(tmp_path: Path) -> None:
    """`/favicon.ico` and `/robots.txt` come from the Next app/ file convention
    and are absent from public/ BY DESIGN."""
    repo, cfg = build_tree(
        tmp_path,
        {"proxy.ts": 'const a = "/favicon.ico"; const b = "/robots.txt";'},
        public_files=[],
    )
    assert run(repo, cfg) == EXIT_CLEAN


def test_innocence_build_output_and_api_and_external(tmp_path: Path) -> None:
    repo, cfg = build_tree(
        tmp_path,
        {
            "app/page.tsx": (
                'const a = "/_next/static/chunk.png";'
                'const b = "/api/og/card.png";'
                'const c = "//cdn.example.com/x.png";'
            )
        },
        public_files=[],
    )
    assert run(repo, cfg) == EXIT_CLEAN


def test_innocence_registered_missing_reference_is_carried_not_failed(
    tmp_path: Path,
) -> None:
    repo, cfg = build_tree(
        tmp_path,
        {"app/page.tsx": '<img src="/static/blog/default.jpg" />'},
        public_files=[],
        config_overrides={
            "known_missing": [
                {"path": "/static/blog/default.jpg", "reason": "dead module, measured"}
            ]
        },
    )
    assert run(repo, cfg) == EXIT_CLEAN


def test_innocence_unquoted_path_in_prose_is_not_a_reference(tmp_path: Path) -> None:
    """The comment left behind when an asset is REMOVED names the dead path.
    Naming it must not resurrect the finding (W91: a token quoted in a comment
    is how an exception, or here a defect, leaks back in)."""
    repo, cfg = build_tree(
        tmp_path,
        {
            "app/kbli/page.tsx": (
                "// its src pointed at /videos/kbli-demo.mp4, a path that has\n"
                "// never existed in public/.\n"
                "export default function Page() { return null }"
            )
        },
        public_files=[],
    )
    assert run(repo, cfg) == EXIT_CLEAN


# ----------------------------------------------------------- operational


def test_blind_scan_is_not_clean(tmp_path: Path) -> None:
    """W84: a scan that matched ZERO code files must fail visibly, never
    silent-pass as green."""
    repo, cfg = build_tree(tmp_path, {}, public_files=[])
    (repo / "app" / "src").mkdir(parents=True, exist_ok=True)
    assert run(repo, cfg) == EXIT_OPERATIONAL


def test_absent_src_root_is_operational_not_clean(tmp_path: Path) -> None:
    repo, cfg = build_tree(tmp_path, {"app/page.tsx": "x"}, public_files=[])
    cfg_data = json.loads(cfg.read_text(encoding="utf-8"))
    cfg_data["roots"] = [{"src": "does/not/exist", "public": "app/public"}]
    cfg.write_text(json.dumps(cfg_data), encoding="utf-8")
    assert run(repo, cfg) == EXIT_OPERATIONAL


# ------------------------------------------------- the real config, live


def test_real_config_registry_entries_carry_a_reason() -> None:
    """A registry entry without a stated reason is an exemption wearing a
    disguise. Every entry must say what was MEASURED.

    The registry is ALLOWED to be empty — that is the goal state, and it became
    empty on 2026-08-07 when all nine founding entries were cured. An earlier
    version of this test asserted the list was non-empty, which would have made
    curing the last defect turn the suite red: a test that punishes you for
    fixing the thing it exists to track. The invariant is the SHAPE of whatever
    entries exist, never that any exist.
    """
    repo_root = Path(__file__).resolve().parents[2]
    cfg_path = repo_root / "infra" / "asset-lint" / "public-asset-refs-config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert "known_missing" in cfg, "registry key absent — did the config get truncated?"
    for entry in cfg["known_missing"]:
        assert entry.get("path", "").startswith("/")
        assert len(entry.get("reason", "")) > 40, f"thin reason on {entry.get('path')}"


def test_empty_registry_still_catches_a_new_defect(tmp_path: Path) -> None:
    """Guilt with an EMPTY registry — the state the repo is now in. Without
    this, "0 entries" and "the gate stopped looking" are indistinguishable."""
    repo, cfg = build_tree(
        tmp_path,
        {"app/page.tsx": '<img src="/images/brand-new-typo.png" />'},
        public_files=["images/real.png"],
        config_overrides={"known_missing": []},
    )
    assert run(repo, cfg) == EXIT_FINDINGS


def test_real_repo_is_clean_under_the_lint() -> None:
    """The gate must be green on main the day it lands, or it gets disarmed."""
    repo_root = Path(__file__).resolve().parents[2]
    cfg = repo_root / "infra" / "asset-lint" / "public-asset-refs-config.json"
    if not (repo_root / "apps" / "mouth" / "src").is_dir():
        pytest.skip("mouth app not present in this checkout")
    assert main(["--repo-root", str(repo_root), "--config", str(cfg)]) == EXIT_CLEAN
