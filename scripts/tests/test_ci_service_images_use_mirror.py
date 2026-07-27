"""Pin for the `services:` container images across `.github/workflows/*.yml`.

WHY: `queue_rearm.sh` (PR #3342) exists because a required check went red at
CONTAINER INITIALISATION — `registry-1.docker.io ... context deadline
exceeded`, three back-offs, all timing out — before any test step ran, and
GitHub Actions pulls `services:` images during "Initialize containers",
BEFORE any step, so an in-step retry is structurally unreachable there. This
diff swaps the two official images this fleet's `services:` blocks actually
use (`postgres:15`, `redis:7`) from `docker.io` (rate-limited/flaky for
anonymous pulls, and the observed failure point) to `public.ecr.aws` (AWS's
mirror of Docker Official Images — no anonymous rate limit as of 2026-07-27,
verified reachable from this session).

GUILT: this test fails if any workflow reverts to an unmirrored official
image for postgres/redis — the exact shape that produced the outage.

INNOCENCE, verified once (not re-verified on every CI run — this is a
manifest-DIGEST equality check against two live registries at authoring
time, not something to hit on every pytest collection): as of 2026-07-27,
`public.ecr.aws/docker/library/postgres:15` and
`public.ecr.aws/docker/library/redis:7` are byte-identical (SHA-256 of the
raw OCI image-index manifest, and the amd64/linux child manifest digest
inside it) to `registry-1.docker.io/library/postgres:15` and
`.../redis:7` respectively — this is a REGISTRY MIRROR of the same image,
not a different image with the same tag.

SCOPE NOTE: `restore-drill.yml`'s `postgis/postgis:17-3.5` is deliberately
NOT touched — it is a third-party image with no verified ECR Public mirror
(checked: `bitnami/postgis` 404s), and that workflow is schedule +
workflow_dispatch only, never gating a PR or the merge queue, so it does not
share the failure mode this diff cures.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

# The two OFFICIAL images this fleet's services: blocks use, and the ONLY
# images this pin cares about — a third image would need its own verified
# mirror before being added here.
MIRRORED_IMAGES = ("postgres", "redis")
MIRROR_PREFIX = "public.ecr.aws/docker/library/"

# `image: <repo>:<tag>` anywhere under a `services:` block. Deliberately a
# repo-wide grep, not a fixed file list — a NEW workflow that adds
# `services: postgres:` must inherit the mirror or fail this test loudly,
# rather than silently reintroducing the docker.io single point of failure.
_IMAGE_LINE_RE = re.compile(r"^\s*image:\s*(\S+)\s*$", re.MULTILINE)


def _all_workflow_files() -> list[Path]:
    files = sorted(WORKFLOWS_DIR.glob("*.yml")) + sorted(WORKFLOWS_DIR.glob("*.yaml"))
    assert files, f"no workflow files found under {WORKFLOWS_DIR} — the glob is broken, not the repo"
    return files


def test_guilt_no_workflow_pulls_postgres_or_redis_straight_from_docker_hub() -> None:
    """The exact shape that caused the outage must not come back anywhere."""
    offenders: list[str] = []
    for path in _all_workflow_files():
        text = path.read_text(encoding="utf-8")
        for m in _IMAGE_LINE_RE.finditer(text):
            ref = m.group(1)
            repo = ref.split(":", 1)[0].split("/")[-1]
            if repo in MIRRORED_IMAGES and not ref.startswith(MIRROR_PREFIX):
                offenders.append(f"{path.relative_to(REPO_ROOT)}: image: {ref}")
    assert not offenders, (
        "unmirrored postgres/redis service image(s) found — this is the exact "
        "container-init failure mode queue_rearm.sh exists to recover from:\n"
        + "\n".join(offenders)
    )


def test_innocence_the_mirror_prefix_actually_appears_where_expected() -> None:
    """Non-vacuity: the guilt test above must have something real to find if
    the mirror were removed. Assert the mirror prefix is present in at least
    the 4 files known (2026-07-27) to declare a postgres/redis service."""
    known_files = (
        "tests.yml",
        "fly-deploy.yml",
        "intel-router-tests.yml",
        "scripts-tests-sweep.yml",
    )
    for name in known_files:
        path = WORKFLOWS_DIR / name
        assert path.is_file(), f"{path} not found — re-anchor this pin, do not delete it"
        text = path.read_text(encoding="utf-8")
        assert MIRROR_PREFIX in text, f"{name} lost its mirrored image reference entirely"


def test_guilt_mirror_prefix_targets_the_right_upstream_path() -> None:
    """A typo'd mirror path (e.g. `public.ecr.aws/postgres` without the
    `docker/library/` namespace) would 404 at container-init — exactly the
    class of failure this diff exists to avoid, just relocated. Assert the
    full, verified-live path is used everywhere it appears."""
    for path in _all_workflow_files():
        text = path.read_text(encoding="utf-8")
        for m in _IMAGE_LINE_RE.finditer(text):
            ref = m.group(1)
            if "public.ecr.aws" in ref:
                assert ref.startswith(MIRROR_PREFIX), (
                    f"{path.relative_to(REPO_ROOT)}: {ref!r} uses public.ecr.aws but not the "
                    f"verified path {MIRROR_PREFIX!r}"
                )


def test_innocence_postgis_third_party_image_deliberately_untouched() -> None:
    """SCOPE PIN: restore-drill.yml's postgis image is NOT expected to be
    mirrored — no verified ECR Public mirror exists for it, and it never
    gates a PR or the queue. If this ever flips (a mirror appears, or the
    workflow becomes PR-gating), this test should start failing and prompt a
    deliberate decision, not a silent divergence from the other four files.
    """
    path = WORKFLOWS_DIR / "restore-drill.yml"
    if not path.is_file():
        return  # file renamed/removed — nothing to pin against
    text = path.read_text(encoding="utf-8")
    assert "postgis/postgis:17-3.5" in text, (
        "restore-drill.yml's postgis image reference changed — re-check whether "
        "an ECR Public mirror now exists before deciding whether to touch it"
    )
    assert "public.ecr.aws" not in text, (
        "restore-drill.yml now references public.ecr.aws — update this test's "
        "docstring/scope note, this was deliberately left out of the original diff"
    )
