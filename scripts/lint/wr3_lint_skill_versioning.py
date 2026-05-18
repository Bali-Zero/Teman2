#!/usr/bin/env python3
"""WR3 Lint — Law 8 (Passato/Presente/Futuro).

Symbiosis Law 8: Past episodes feed future via Voyager skill library. Each
agent's skill cortex declares contract_version, and the contract YAML must
match. Manifest sha256 anchors enable cross-episode comparison.

Checks:
  1. Every `~/.claude/agents/wr3-<slug>.md` has frontmatter `contract_version: <semver>`.
  2. The same `contract_version` is declared in `docs/wr3/contracts/<slug>.yaml`.
  3. Every `~/.claude/skills/bali-zero-brand/wr3/<slug>/SKILL.md` has the same.
  4. `_voyager-curriculum.md` exists at the skill cortex root.
  5. Manifest validator includes `wr3_room_version` field (sha256 chain anchor).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

try:
    from . import LintFinding
except ImportError:
    import sys
    HERE = Path(__file__).resolve().parent
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    from __init__ import LintFinding  # type: ignore

LAW_NUMBER = 8
LAW_NAME = "Passato/Presente/Futuro"

SEMVER_RE = re.compile(r"contract_version:\s*([\"\']?)([\d]+\.[\d]+\.[\d]+)\1")

AGENT_DIR = Path(os.environ.get(
    "WR3_AGENT_DIR",
    str(Path.home() / ".claude" / "agents"),
))
SKILL_DIR = Path(os.environ.get(
    "WR3_SKILL_DIR",
    str(Path.home() / ".claude" / "skills" / "bali-zero-brand" / "wr3"),
))


def _extract_version(text: str) -> str | None:
    m = SEMVER_RE.search(text)
    return m.group(2) if m else None


def check(repo_root: Path) -> list[LintFinding]:
    findings: list[LintFinding] = []
    contracts_dir = repo_root / "docs" / "wr3" / "contracts"

    if not contracts_dir.exists():
        return findings

    # Walk per-agent contracts and cross-check version triple
    for yaml_path in sorted(contracts_dir.glob("*.yaml")):
        if yaml_path.name.startswith("_"):
            continue
        slug = yaml_path.stem
        try:
            yaml_text = yaml_path.read_text()
        except Exception:
            continue

        yaml_ver = _extract_version(yaml_text)
        if not yaml_ver:
            findings.append(LintFinding(
                severity="ERROR",
                law=LAW_NUMBER,
                file=str(yaml_path.relative_to(repo_root)),
                line=None,
                message="contract_version missing or non-semver in YAML",
            ))
            continue

        # Cross-check agent .md
        agent_md = AGENT_DIR / f"wr3-{slug}.md"
        if agent_md.exists():
            agent_ver = _extract_version(agent_md.read_text())
            if not agent_ver:
                findings.append(LintFinding(
                    severity="WARN",
                    law=LAW_NUMBER,
                    file=f"~/.claude/agents/wr3-{slug}.md",
                    line=None,
                    message="agent .md missing contract_version frontmatter (will skip cross-check)",
                ))
            elif agent_ver != yaml_ver:
                findings.append(LintFinding(
                    severity="ERROR",
                    law=LAW_NUMBER,
                    file=f"~/.claude/agents/wr3-{slug}.md",
                    line=None,
                    message=f"contract_version mismatch: agent.md={agent_ver} vs yaml={yaml_ver}",
                ))

        # Cross-check skill cortex SKILL.md
        skill_md = SKILL_DIR / slug / "SKILL.md"
        if skill_md.exists():
            skill_ver = _extract_version(skill_md.read_text())
            if not skill_ver:
                findings.append(LintFinding(
                    severity="WARN",
                    law=LAW_NUMBER,
                    file=f"~/.claude/skills/bali-zero-brand/wr3/{slug}/SKILL.md",
                    line=None,
                    message="SKILL.md missing contract_version frontmatter",
                ))
            elif skill_ver != yaml_ver:
                findings.append(LintFinding(
                    severity="ERROR",
                    law=LAW_NUMBER,
                    file=f"~/.claude/skills/bali-zero-brand/wr3/{slug}/SKILL.md",
                    line=None,
                    message=f"contract_version mismatch: skill={skill_ver} vs yaml={yaml_ver}",
                ))

    # Voyager curriculum exists
    voyager = SKILL_DIR / "_voyager-curriculum.md"
    if not voyager.exists():
        findings.append(LintFinding(
            severity="ERROR",
            law=LAW_NUMBER,
            file=str(voyager),
            line=None,
            message="_voyager-curriculum.md missing — Law 8 skill library lifecycle undeclared",
        ))

    # Manifest validator declares wr3_room_version
    manifest_py = repo_root / "scripts" / "wr3_episode_manifest.py"
    if manifest_py.exists():
        text = manifest_py.read_text()
        if "wr3_room_version" not in text:
            findings.append(LintFinding(
                severity="ERROR",
                law=LAW_NUMBER,
                file=str(manifest_py.relative_to(repo_root)),
                line=None,
                message="Manifest missing wr3_room_version field — Law 8 cross-episode anchor",
            ))

    return findings


if __name__ == "__main__":
    import sys
    repo_root = Path(__file__).resolve().parents[2]
    findings = check(repo_root)
    for f in findings:
        print(f.fmt())
    sys.exit(1 if any(f.severity == "ERROR" for f in findings) else 0)
