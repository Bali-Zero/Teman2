"""Lock files must satisfy every requirements.txt constraint (incident gate).

INCIDENT 2026-07-13: dependabot's group PR #2349 regenerated the lock files
and bumped ``fastapi`` to ``0.136.3`` — the exact version requirements.txt
excludes with ``!=0.136.3`` (MAL-2026-4750: attacker-published release
injecting the malicious ``fastar`` dependency via the "standard" extra).
Dependabot's pip lock updater does NOT honor requirements.txt specifiers,
CI installs the LOCK (never re-checking the manifest), Snyk/Socket both
stayed green, and the attacker-published wheel reached production (payload
confirmed absent — extra-gated — but the wheel bytes ran for ~2h).

This test is the structural antidote: any lock line whose pinned version
violates a requirements manifest specifier fails CI loudly, so a lock
regeneration can never again ride past a deliberate ``!=``/ceiling/floor.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

APP_ROOT = Path(__file__).resolve().parents[2]

PAIRS = [
    ("requirements.txt", "requirements.lock.txt"),
    ("requirements-prod.txt", "requirements-prod.lock.txt"),
]

_LOCK_PIN_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9.!+*rcpostdev]+)")


def _manifest_requirements(path: Path) -> list[Requirement]:
    reqs: list[Requirement] = []
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith(("-", "--")):
            continue
        try:
            req = Requirement(line)
        except InvalidRequirement:
            continue  # editable/url/odd lines are not version constraints
        if req.marker is not None and not req.marker.evaluate():
            continue
        if req.specifier:
            reqs.append(req)
    return reqs


def _lock_versions(path: Path) -> dict[str, Version]:
    pins: dict[str, Version] = {}
    for raw in path.read_text().splitlines():
        m = _LOCK_PIN_RE.match(raw.strip())
        if not m:
            continue
        try:
            pins[canonicalize_name(m.group(1))] = Version(m.group(2))
        except Exception:  # noqa: BLE001 - non-PEP440 pin, not our concern here
            continue
    return pins


@pytest.mark.parametrize(("manifest_name", "lock_name"), PAIRS)
def test_lock_satisfies_manifest_constraints(
    manifest_name: str, lock_name: str
) -> None:
    manifest = APP_ROOT / manifest_name
    lock = APP_ROOT / lock_name
    if not manifest.exists() or not lock.exists():
        pytest.skip(f"{manifest_name}/{lock_name} not present")

    pins = _lock_versions(lock)
    violations: list[str] = []
    for req in _manifest_requirements(manifest):
        name = canonicalize_name(req.name)
        pinned = pins.get(name)
        if pinned is None:
            continue  # not in this lock (extra/env-specific)
        if not req.specifier.contains(pinned, prereleases=True):
            violations.append(
                f"{name}=={pinned} violates {manifest_name} constraint "
                f"'{req.name}{req.specifier}'"
            )

    assert not violations, (
        f"{lock_name} pins versions the manifest forbids — a lock "
        "regeneration rode past a deliberate constraint (the #2349 "
        "fastapi==0.136.3 MAL-2026-4750 pattern):\n  "
        + "\n  ".join(violations)
    )


class TestCheckerItselfWorks:
    """Guilt+innocence for the gate (scar family #3 discipline)."""

    def test_guilt_excluded_version_is_flagged(self) -> None:
        req = Requirement("fastapi>=0.135.2,!=0.136.3")
        assert not req.specifier.contains(Version("0.136.3"), prereleases=True)

    def test_innocence_clean_version_passes(self) -> None:
        req = Requirement("fastapi>=0.135.2,!=0.136.3")
        assert req.specifier.contains(Version("0.139.0"), prereleases=True)

    def test_real_manifest_still_excludes_the_malware_release(self) -> None:
        manifest = APP_ROOT / "requirements.txt"
        fastapi_reqs = [
            r
            for r in _manifest_requirements(manifest)
            if canonicalize_name(r.name) == "fastapi"
        ]
        assert fastapi_reqs, "fastapi constraint disappeared from requirements.txt"
        assert not fastapi_reqs[0].specifier.contains(
            Version("0.136.3"), prereleases=True
        ), "the !=0.136.3 MAL-2026-4750 exclusion was dropped"
