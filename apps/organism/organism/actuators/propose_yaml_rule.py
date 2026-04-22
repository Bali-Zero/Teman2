"""Actuator: open PR adding a learned YAML rule to organism/rules/learned/.

L3 actuator — IRREVERSIBLE (long-lived repo effect). Consiglio gate requires
3/4 agreement before dispatch (already wired in W2.C IRREVERSIBLE_ACTUATORS).

Input:
- params["rule_candidate"]: dict with at least {id, match, action, confidence}
  matching the YAML rule schema used by yaml_rules.py RuleMatcher

Flow:
1. Validate candidate has required fields
2. git rev-parse --show-toplevel to anchor paths
3. Render YAML rule file + pytest test case
4. git checkout -b organism/propose-rule-<id>
5. Write YAML to apps/organism/organism/rules/learned/<YYYY-MM-DD>-<id>.yaml
6. Write test to apps/organism/tests/rules/test_learned_<id>.py
7. Commit
8. Push
9. gh pr create --title + --body describing candidate origin + provenance
10. gh pr merge --auto --squash (rule becomes live once CI green)

Failure modes: each step short-circuits by raising RuntimeError so ActuatorBase
emits propose_yaml_rule_failed (not _done) and monitoring captures them.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from organism.actuators.base import ActuatorBase


log = logging.getLogger(__name__)

LEARNED_RULES_DIR_REL = "apps/organism/organism/rules/learned"
LEARNED_TESTS_DIR_REL = "apps/organism/tests/rules"

REQUIRED_CANDIDATE_KEYS = ("id", "match", "action")
RULE_ID_RE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")


class ProposeYamlRule(ActuatorBase):
    name = "propose_yaml_rule"

    async def _execute(self, params: dict) -> dict:
        candidate = params.get("rule_candidate")
        validation = self._validate_candidate(candidate)
        if validation is not None:
            raise RuntimeError(f"validation: {validation}")

        # Anchor to repo root — Supervisor daemon may run outside repo
        rc, repo_root_out, err = await self._run(["git", "rev-parse", "--show-toplevel"])
        if rc != 0 or not repo_root_out.strip():
            raise RuntimeError(f"git rev-parse failed: {err[:200]}")
        repo_root = Path(repo_root_out.strip())

        rule_id = candidate["id"]
        today = date.today().isoformat()
        branch = f"organism/propose-rule-{rule_id}"
        yaml_filename = f"{today}-{rule_id}.yaml"
        test_filename = f"test_learned_{rule_id}.py"

        yaml_rel = f"{LEARNED_RULES_DIR_REL}/{yaml_filename}"
        test_rel = f"{LEARNED_TESTS_DIR_REL}/{test_filename}"

        yaml_text = self._render_rule_yaml(candidate)
        test_text = self._render_test_py(candidate)

        # 1. branch
        rc, _, err = await self._run(["git", "checkout", "-b", branch])
        if rc != 0:
            raise RuntimeError(f"checkout -b {branch}: {err[:200]}")
        try:
            # 2. write YAML + test
            yaml_path = repo_root / yaml_rel
            test_path = repo_root / test_rel
            yaml_path.parent.mkdir(parents=True, exist_ok=True)
            test_path.parent.mkdir(parents=True, exist_ok=True)
            yaml_path.write_text(yaml_text, encoding="utf-8")
            test_path.write_text(test_text, encoding="utf-8")

            # 3. stage + commit
            rc, _, err = await self._run([
                "git", "add", str(yaml_path), str(test_path),
            ])
            if rc != 0:
                raise RuntimeError(f"git add: {err[:200]}")
            rc, _, err = await self._run([
                "git", "commit",
                "-m", f"feat(organism): propose learned rule {rule_id}",
            ])
            if rc != 0:
                raise RuntimeError(f"git commit: {err[:200]}")

            # 4. push
            rc, _, err = await self._run(["git", "push", "-u", "origin", branch])
            if rc != 0:
                raise RuntimeError(f"git push: {err[:200]}")

            # 5. gh pr create
            pr_body = self._render_pr_body(candidate, yaml_rel, test_rel)
            rc, out, err = await self._run([
                "gh", "pr", "create",
                "--title", f"feat(organism): propose learned rule {rule_id}",
                "--body", pr_body,
                "--head", branch,
            ])
            if rc != 0:
                raise RuntimeError(f"gh pr create: {err[:200]}")
            pr_url = out.strip().splitlines()[-1] if out.strip() else ""

            # 6. auto-merge
            rc, _, err = await self._run([
                "gh", "pr", "merge", pr_url, "--auto", "--squash",
            ])
            auto_merge_enabled = (rc == 0)

            return {
                "rule_id": rule_id,
                "branch": branch,
                "pr_url": pr_url,
                "yaml_path": yaml_rel,
                "test_path": test_rel,
                "auto_merge_enabled": auto_merge_enabled,
            }
        except OSError as exc:
            raise RuntimeError(f"file io: {exc}") from exc

    async def _dry_run(self, params: dict) -> dict:
        candidate = params.get("rule_candidate")
        validation = self._validate_candidate(candidate)
        if validation is not None:
            return {"would_propose": False, "error": validation}
        rule_id = candidate["id"]
        today = date.today().isoformat()
        return {
            "would_propose": True,
            "rule_id": rule_id,
            "branch": f"organism/propose-rule-{rule_id}",
            "yaml_path": f"{LEARNED_RULES_DIR_REL}/{today}-{rule_id}.yaml",
            "test_path": f"{LEARNED_TESTS_DIR_REL}/test_learned_{rule_id}.py",
            "candidate_summary": {
                "match": candidate.get("match"),
                "actuator": candidate.get("action", {}).get("actuator"),
                "confidence": candidate.get("confidence"),
            },
        }

    @staticmethod
    def _validate_candidate(candidate: Any) -> str | None:
        if not isinstance(candidate, dict):
            return "rule_candidate must be a dict"
        for key in REQUIRED_CANDIDATE_KEYS:
            if key not in candidate:
                return f"rule_candidate missing required key: {key}"
        rule_id = candidate.get("id")
        if not isinstance(rule_id, str) or not RULE_ID_RE.match(rule_id):
            return f"rule_candidate.id must match {RULE_ID_RE.pattern}; got {rule_id!r}"
        action = candidate.get("action")
        if not isinstance(action, dict) or "actuator" not in action:
            return "rule_candidate.action must be dict with 'actuator' key"
        match = candidate.get("match")
        if not isinstance(match, dict) or not match:
            return "rule_candidate.match must be non-empty dict"
        return None

    @staticmethod
    def _render_rule_yaml(candidate: dict) -> str:
        """Render a single-rule YAML file matching the organism rule schema."""
        # Use yaml.safe_dump for correct escaping + ordering by key
        data = {"rules": [dict(candidate)]}
        return yaml.safe_dump(data, sort_keys=False, default_flow_style=False)

    @staticmethod
    def _render_test_py(candidate: dict) -> str:
        """Render a pytest test case that loads the rule YAML and asserts match behavior."""
        rule_id = candidate["id"]
        match_spec = candidate["match"]
        example_kind = match_spec.get("kind", "example_kind")
        return f'''"""Auto-generated test for learned rule {rule_id}.

Loads the learned YAML rule and asserts it correctly matches the kind
it was proposed for. Regenerating this test is safe — the propose_yaml_rule
actuator will overwrite both files as a pair.
"""
import pytest
from pathlib import Path
from organism.supervisor.yaml_rules import RuleMatcher
from organism.schemas import Event, Severity


LEARNED_DIR = Path(__file__).resolve().parents[2] / "organism" / "rules" / "learned"


def _load_rule_text() -> str:
    for path in LEARNED_DIR.glob("*-{rule_id}.yaml"):
        return path.read_text(encoding="utf-8")
    raise FileNotFoundError("learned rule file for {rule_id} not found")


def test_learned_rule_{rule_id}_matches_expected_kind():
    matcher = RuleMatcher.from_yaml_text(_load_rule_text())
    event = Event(
        severity=Severity.ERROR,
        source="guardian.test",
        kind={example_kind!r},
        payload={{"probe": "value"}},
        correlation_id="c-test",
        host="Pro",
    )
    decision = matcher.match(event)
    assert decision is not None, "learned rule did not match its intended kind"
    assert decision.tier == "L0_yaml"
'''

    @staticmethod
    def _render_pr_body(candidate: dict, yaml_rel: str, test_rel: str) -> str:
        rule_id = candidate["id"]
        return f"""Auto-proposed YAML rule by the organism `propose_yaml_rule` actuator.

## Rule
- id: `{rule_id}`
- match: `{candidate.get('match')}`
- action: `{candidate.get('action')}`
- confidence: `{candidate.get('confidence', 0.8)}`

## Provenance
Proposed via Consiglio v1 3/4 deliberation (L3 irreversible actuator).
See `docs/superpowers/specs/2026-04-22-autonomic-organism-design.md` §Safety.

## Files
- YAML: `{yaml_rel}`
- Test: `{test_rel}`

When CI is green, this PR auto-merges via `--squash`. Supervisor
reloads rules on the next `run_once` iteration after merge.
"""

    @staticmethod
    async def _run(cmd: list[str]) -> tuple[int, str, str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, err = await asyncio.wait_for(proc.communicate(), timeout=30.0)
            return (
                proc.returncode or 0,
                out.decode("utf-8", errors="replace"),
                err.decode("utf-8", errors="replace"),
            )
        except (asyncio.TimeoutError, FileNotFoundError, OSError) as exc:
            return (-1, "", str(exc)[:200])
