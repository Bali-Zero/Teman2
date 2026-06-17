#!/usr/bin/env python3
"""Health checks for the local Codex/Nuzantara operating profile.

The checker is intentionally read-only. It validates the quiet Codex profiles,
hook-noise policy, skill frontmatter shape, and AGENTS.md context budget without
printing secrets or large config bodies.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import Any, NamedTuple


REQUIRED_MODEL = "gpt-5.5"
REQUIRED_REASONING = "xhigh"
MIN_PROJECT_DOC_BYTES = 65_536
NOISY_HOOK_EVENTS = ("SessionStart", "UserPromptSubmit", "Stop")


class Check(NamedTuple):
    name: str
    status: str
    message: str
    path: str = ""


def make_check(name: str, status: str, message: str, path: Path | str | None = None) -> Check:
    return Check(name=name, status=status, message=message, path=str(path or ""))


def check_profile(
    path: Path,
    label: str,
    *,
    require_quiet_plugins: bool,
    min_project_doc_bytes: int = MIN_PROJECT_DOC_BYTES,
    missing_status: str = "FAIL",
) -> list[Check]:
    checks: list[Check] = []
    parse_name = f"profile:{label}:parse"
    if not path.exists():
        return [make_check(parse_name, missing_status, "profile file is missing", path)]

    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        return [make_check(parse_name, "FAIL", f"TOML parse error: {exc}", path)]

    checks.append(make_check(parse_name, "PASS", "TOML parses", path))

    model = data.get("model")
    checks.append(
        make_check(
            f"profile:{label}:model",
            "PASS" if model == REQUIRED_MODEL else "FAIL",
            "model is gpt-5.5" if model == REQUIRED_MODEL else "model is not gpt-5.5",
            path,
        )
    )

    reasoning = data.get("model_reasoning_effort")
    checks.append(
        make_check(
            f"profile:{label}:reasoning",
            "PASS" if reasoning == REQUIRED_REASONING else "FAIL",
            "reasoning effort is xhigh"
            if reasoning == REQUIRED_REASONING
            else "reasoning effort is not xhigh",
            path,
        )
    )

    project_doc_max_bytes = data.get("project_doc_max_bytes")
    budget_ok = isinstance(project_doc_max_bytes, int) and project_doc_max_bytes >= min_project_doc_bytes
    checks.append(
        make_check(
            f"profile:{label}:project_doc_budget",
            "PASS" if budget_ok else "WARN",
            f"project_doc_max_bytes >= {min_project_doc_bytes}"
            if budget_ok
            else f"project_doc_max_bytes below {min_project_doc_bytes}",
            path,
        )
    )

    features = data.get("features", {})
    if not isinstance(features, dict):
        features = {}
    plugin_hooks = features.get("plugin_hooks")
    plugins = features.get("plugins")

    expected_status = "PASS"
    noisy_status = "FAIL" if require_quiet_plugins else "WARN"
    checks.append(
        make_check(
            f"profile:{label}:plugin_hooks",
            expected_status if plugin_hooks is False else noisy_status,
            "plugin_hooks disabled"
            if plugin_hooks is False
            else "plugin_hooks not disabled; startup hook noise can return",
            path,
        )
    )
    checks.append(
        make_check(
            f"profile:{label}:plugins",
            expected_status if plugins is False else noisy_status,
            "plugins disabled"
            if plugins is False
            else "plugins not disabled; plugin-provided hooks can return",
            path,
        )
    )
    return checks


def _hook_count(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, list):
        return len(value)
    return 1


def check_hooks_file(path: Path, label: str) -> list[Check]:
    parse_name = f"hooks:{label}:parse"
    if not path.exists():
        return [make_check(parse_name, "WARN", "hook config file is missing", path)]

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [make_check(parse_name, "FAIL", f"JSON parse error: {exc}", path)]

    hooks = payload.get("hooks", {})
    if not isinstance(hooks, dict):
        return [make_check(parse_name, "FAIL", "hooks key is not an object", path)]

    checks = [make_check(parse_name, "PASS", "JSON parses", path)]
    for event in NOISY_HOOK_EVENTS:
        count = _hook_count(hooks.get(event))
        checks.append(
            make_check(
                f"hooks:{label}:{event}",
                "PASS" if count == 0 else "FAIL",
                "no active entries" if count == 0 else f"{count} active entries",
                path,
            )
        )
    return checks


def _frontmatter_lines(path: Path) -> tuple[list[str], str | None]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return [], "missing opening frontmatter marker"
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return lines[1:index], None
    return [], "missing closing frontmatter marker"


def check_skill_frontmatter(path: Path) -> list[Check]:
    name = f"skill:{path.name}:frontmatter"
    try:
        lines, error = _frontmatter_lines(path)
    except UnicodeDecodeError as exc:
        return [make_check(name, "FAIL", f"cannot decode UTF-8: {exc}", path)]

    if error is not None:
        return [make_check(name, "FAIL", error, path)]

    has_name = False
    has_description = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("name:"):
            has_name = True
        if stripped.startswith("description:"):
            has_description = True
            value = stripped.partition(":")[2].strip()
            is_block_scalar = value in {">", ">-", "|", "|-"}
            is_quoted = (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            )
            if ": " in value and not is_block_scalar and not is_quoted:
                return [
                    make_check(
                        name,
                        "FAIL",
                        "description contains an unquoted colon; use a block scalar",
                        path,
                    )
                ]

    if not has_name or not has_description:
        missing = ", ".join(
            field
            for field, present in (("name", has_name), ("description", has_description))
            if not present
        )
        return [make_check(name, "FAIL", f"missing required field(s): {missing}", path)]

    return [make_check(name, "PASS", "frontmatter has name and description", path)]


def check_skill_root(root: Path, label: str) -> list[Check]:
    if not root.exists():
        return [make_check(f"skills:{label}:root", "WARN", "skill root is missing", root)]

    skill_files = sorted(root.glob("*/SKILL.md"))
    if not skill_files:
        return [make_check(f"skills:{label}:root", "WARN", "no skill files found", root)]

    checks = [make_check(f"skills:{label}:root", "PASS", f"{len(skill_files)} skill files found", root)]
    for skill_file in skill_files:
        skill_checks = check_skill_frontmatter(skill_file)
        for check in skill_checks:
            checks.append(
                make_check(
                    f"skills:{label}:{skill_file.parent.name}:frontmatter",
                    check.status,
                    check.message,
                    skill_file,
                )
            )
    return checks


def check_agents_budget(path: Path, label: str, *, budget_bytes: int) -> list[Check]:
    name = f"agents:{label}:budget"
    if not path.exists():
        return [make_check(name, "WARN", "AGENTS.md is missing", path)]

    size = path.stat().st_size
    status = "PASS" if size <= budget_bytes else "WARN"
    return [
        make_check(
            name,
            status,
            f"{size} bytes within {budget_bytes} byte budget"
            if status == "PASS"
            else f"{size} bytes exceeds {budget_bytes} byte budget",
            path,
        )
    ]


def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for parent in (current, *current.parents):
        if (parent / ".git").exists() or (parent / "AGENTS.md").exists():
            return parent
    return current


def run_checks(repo_root: Path, home: Path) -> list[Check]:
    profile_specs = (
        ("nuzantara-core", home / ".codex" / "nuzantara-core.config.toml", True, "FAIL"),
        ("nuzantara-research", home / ".codex" / "nuzantara-research.config.toml", True, "FAIL"),
        ("nuzantara-toolful", home / ".codex" / "nuzantara-toolful.config.toml", False, "WARN"),
    )

    checks: list[Check] = []
    for label, path, require_quiet_plugins, missing_status in profile_specs:
        checks.extend(
            check_profile(
                path,
                label,
                require_quiet_plugins=require_quiet_plugins,
                missing_status=missing_status,
            )
        )

    checks.extend(check_hooks_file(home / ".codex" / "hooks.json", "codex"))
    checks.extend(check_hooks_file(home / ".claude" / "settings.json", "claude"))

    checks.extend(check_skill_root(home / ".agents" / "skills", "home-agents"))
    checks.extend(check_skill_root(home / ".codex" / "skills", "home-codex"))
    checks.extend(check_skill_root(repo_root / ".agents" / "skills", "repo"))

    checks.extend(check_agents_budget(home / ".codex" / "AGENTS.md", "home-codex", budget_bytes=MIN_PROJECT_DOC_BYTES))
    checks.extend(check_agents_budget(repo_root / "AGENTS.md", "repo", budget_bytes=MIN_PROJECT_DOC_BYTES))

    return checks


def checks_to_json(checks: list[Check]) -> str:
    return json.dumps([check._asdict() for check in checks], indent=2, sort_keys=True)


def print_text_report(checks: list[Check]) -> None:
    for check in checks:
        location = f" [{check.path}]" if check.path else ""
        print(f"{check.status} {check.name}: {check.message}{location}")

    fail_count = sum(1 for check in checks if check.status == "FAIL")
    warn_count = sum(1 for check in checks if check.status == "WARN")
    pass_count = sum(1 for check in checks if check.status == "PASS")
    summary_status = "FAIL" if fail_count else "WARN" if warn_count else "PASS"
    print(f"SUMMARY status={summary_status} pass={pass_count} warn={warn_count} fail={fail_count}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check local Codex/Nuzantara profile health.")
    parser.add_argument("--repo-root", type=Path, default=None, help="Repository root. Defaults to auto-detect.")
    parser.add_argument("--home", type=Path, default=Path.home(), help="Home directory to inspect.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument(
        "--allow-warnings",
        action="store_true",
        help="Exit 0 when only warnings are present. Failures still exit 1.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = args.repo_root or find_repo_root(Path.cwd())
    checks = run_checks(repo_root.resolve(), args.home.expanduser().resolve())

    if args.json:
        print(checks_to_json(checks))
    else:
        print_text_report(checks)

    has_failure = any(check.status == "FAIL" for check in checks)
    has_warning = any(check.status == "WARN" for check in checks)
    if has_failure:
        return 1
    if has_warning and not args.allow_warnings:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
