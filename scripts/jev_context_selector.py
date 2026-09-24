#!/usr/bin/env python3
"""Build a bounded, repository-only context packet for pilot arms B and C."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Callable

from redact_for_external import redact
from typesafe_client import MODEL, RequestBudget, ask_detailed, noul


POLICY_VERSION = "jev-context-selector-phase0-v2"
FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "research"
    / "operations"
    / "fixtures"
    / "jev-context-selector-eval-v1.json"
)
MIN_PACKET_TOKENS = 4000
MAX_PACKET_TOKENS = 8000
MAX_CANDIDATES = 50
MIN_CANDIDATES = 30
_TELEMETRY_FIELDS = {
    "attempted",
    "response_received",
    "schema_valid",
    "abstained",
    "failure",
    "requested_model",
    "resolved_model",
    "latency_ms",
    "http_attempts",
    "fallback",
}
_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_-]{2,}")
_SYMBOL = re.compile(
    r"^\s*(?:(?:export\s+)?(?:async\s+)?(?:def|class|function)\s+|"
    r"(?:export\s+)?(?:const|let|var)\s+)([A-Za-z_][A-Za-z0-9_]*)",
    re.M,
)
_DEFINITION = re.compile(
    r"^[ \t]*(?:(?:export\s+)?(?:default\s+)?(?:async\s+)?"
    r"(?:def|class|function|interface|enum)\s+|"
    r"(?:export\s+)?(?:const|let|var|type)\s+)"
    r"([A-Za-z_][A-Za-z0-9_]*)",
    re.M,
)
_HEADING = re.compile(r"^#{1,4}\s+(.+)$", re.M)
_IMPORT = re.compile(
    r"^\s*(?:from\s+([A-Za-z_][\w.]*)\s+import|import\s+([A-Za-z_][\w.]*))",
    re.M,
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout


def _tracked(repo: Path) -> list[str]:
    raw = subprocess.run(
        ["git", "ls-files", "-z"], cwd=repo, check=True, capture_output=True
    ).stdout
    return sorted(item.decode("utf-8") for item in raw.split(b"\0") if item)


def _inside(repo: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError("task path must stay inside the repository") from exc


def _words(text: str) -> set[str]:
    return {word.lower() for word in _WORD.findall(text)}


def _read_text(path: Path, limit: int | None = None) -> str:
    with path.open("rb") as handle:
        data = handle.read() if limit is None else handle.read(limit)
    if b"\0" in data[:4096]:
        return ""
    return data.decode("utf-8", errors="replace")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_repository_file(repo: Path, path: Path) -> bool:
    """True only for a regular, non-symlink file resolved below the repo root."""
    try:
        path.resolve(strict=True).relative_to(repo.resolve())
    except (OSError, ValueError):
        return False
    return path.is_file() and not path.is_symlink()


def _git_grep_paths(repo: Path, terms: list[str]) -> set[str]:
    if not terms:
        return set()
    command = ["git", "grep", "-I", "-i", "-l"]
    for term in terms:
        command.extend(("-e", term))
    result = subprocess.run(command, cwd=repo, capture_output=True, text=True)
    if result.returncode not in (0, 1):
        return set()
    return {line for line in result.stdout.splitlines() if line}


def _path_mentioned(task_text: str, path: str) -> bool:
    return re.search(
        rf"(?<![A-Za-z0-9_./-])(?:\./)?{re.escape(path)}"
        r"(?![A-Za-z0-9_/-]|\.[A-Za-z0-9_/-])",
        task_text,
    ) is not None


def _git_symbol_definitions(repo: Path, symbols: set[str]) -> dict[str, set[str]]:
    definitions: dict[str, set[str]] = {}
    for symbol in sorted(symbols):
        pattern = (
            r"^[[:space:]]*(export[[:space:]]+)?"
            r"(default[[:space:]]+)?(async[[:space:]]+)?"
            r"(def|class|function|interface|enum|const|let|var|type)"
            r"[[:space:]]+"
            + re.escape(symbol)
            + r"([^A-Za-z0-9_]|$)"
        )
        result = subprocess.run(
            ["git", "grep", "-I", "-l", "-E", "-e", pattern],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        if result.returncode in (0, 1):
            for path in result.stdout.splitlines():
                if path:
                    definitions.setdefault(path, set()).add(symbol)
    return definitions


def _working_tree_modified(repo: Path, path: str) -> bool:
    result = subprocess.run(
        ["git", "diff", "--quiet", "--", path], cwd=repo, capture_output=True
    )
    if result.returncode not in (0, 1):
        raise ValueError(f"cannot establish working-tree provenance for {path}")
    return result.returncode == 1


def _description(path: str, text: str) -> tuple[str, set[str], set[str]]:
    symbols = set(_SYMBOL.findall(text))
    headings = {heading.strip()[:100] for heading in _HEADING.findall(text)[:8]}
    imports = {
        left or right for left, right in _IMPORT.findall(text) if left or right
    }
    parts = [f"path={path}", f"suffix={Path(path).suffix or 'none'}"]
    if symbols:
        parts.append("symbols=" + ",".join(sorted(symbols)[:20]))
    if headings:
        parts.append("headings=" + " | ".join(sorted(headings)[:8]))
    if imports:
        parts.append("imports=" + ",".join(sorted(imports)[:20]))
    return "; ".join(parts), symbols, imports


def _index_blob(repo: Path, path: str) -> str:
    line = _git(repo, "ls-files", "-s", "--", path).strip()
    parts = line.split()
    return parts[1] if len(parts) >= 2 else ""


def _applicable_agents(path: str, tracked: set[str]) -> set[str]:
    parent = Path(path).parent
    result: set[str] = set()
    while True:
        candidate = (parent / "AGENTS.md").as_posix()
        if candidate in tracked:
            result.add(candidate)
        if parent == Path("."):
            break
        parent = parent.parent
    if "AGENTS.md" in tracked:
        result.add("AGENTS.md")
    return result


def _candidate_pool(
    repo: Path,
    task_rel: str,
    task_text: str,
    content_overrides: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    content_overrides = content_overrides or {}
    tracked = _tracked(repo)
    tracked_set = set(tracked)
    explicit = {
        path
        for path in tracked
        if path != task_rel and _path_mentioned(task_text, path)
    }
    protected = {task_rel, *explicit}
    for path in tuple(protected):
        protected.update(_applicable_agents(path, tracked_set))

    quoted = re.findall(r"`([^`\n]+)`", task_text)
    quoted_symbols = {
        value for value in quoted if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value)
    }
    symbol_definitions = _git_symbol_definitions(repo, quoted_symbols)
    symbol_definition_paths = set(symbol_definitions)
    protected.update(symbol_definition_paths)
    task_words = _words(task_text)
    search_terms = sorted(
        (
            word
            for word in task_words
            if len(word) >= 5
            and word
            not in {
                "about",
                "after",
                "before",
                "change",
                "existing",
                "without",
                "repository",
                "should",
                "their",
            }
        ),
        key=lambda word: (-len(word), word),
    )[:8]
    content_hits = _git_grep_paths(repo, search_terms)
    path_rank = sorted(
        tracked,
        key=lambda path: (
            -len(task_words & _words(path.replace("/", " "))),
            path,
        ),
    )
    preselected = (
        set(path_rank[:120])
        | set(sorted(content_hits)[:200])
        | symbol_definition_paths
        | protected
    )
    for path in tuple(preselected):
        preselected.update(_applicable_agents(path, tracked_set))
    rows: list[dict[str, Any]] = []
    imports_by_path: dict[str, set[str]] = {}
    for path in sorted(preselected):
        source = repo / path
        if not _safe_repository_file(repo, source):
            continue
        try:
            preview = (
                content_overrides[path]
                if path in content_overrides
                else _read_text(source, 24000)
            )
        except OSError:
            continue
        if not preview and source.stat().st_size:
            continue
        description, symbols, imports = _description(path, preview)
        imports_by_path[path] = imports
        path_words = _words(path.replace("/", " "))
        description_words = _words(description)
        overlap = task_words & (path_words | description_words)
        score = len(task_words & path_words) * 8 + len(overlap) * 2
        reasons = ["lexical"] if overlap else []
        if path in explicit:
            score += 1000
            reasons.append("explicit_path")
        if path == task_rel:
            score += 1200
            reasons.append("task_source")
        if path in symbol_definition_paths:
            score += 900
            reasons.append("quoted_symbol_definition")
            protected.add(path)
        symbol_hits = {symbol for symbol in symbols if symbol.lower() in task_words}
        if symbol_hits:
            score += 80 + (10 * len(symbol_hits))
            reasons.append("symbol_definition")
            protected.add(path)
        if any(fragment.startswith("assert ") and fragment in preview for fragment in quoted):
            score += 100
            reasons.append("failing_assertion")
            protected.add(path)
        rows.append(
            {
                "id": "c-" + hashlib.sha256(path.encode()).hexdigest()[:12],
                "path": path,
                "description": description,
                "score": score,
                "reasons": reasons,
                "protected": False,
                "source_sha256": "",
                "git_blob": "",
                "working_tree_modified": False,
                "source_kind": (
                    "fixture_task_record"
                    if path in content_overrides
                    else "repository_file"
                ),
                "protected_symbols": sorted(symbol_definitions.get(path, set())),
                "applicable_agents": sorted(
                    _applicable_agents(path, tracked_set) - {path}
                ),
            }
        )

    explicit_modules = {
        path.removesuffix(".py").replace("/", ".")
        for path in explicit
        if path.endswith(".py")
    }
    for row in rows:
        imports = imports_by_path.get(row["path"], set())
        if explicit_modules & imports:
            row["score"] += 40
            row["reasons"].append("dependency_proximity")
        row["protected"] = row["path"] in protected

    missing_protected = protected - {row["path"] for row in rows}
    if missing_protected:
        raise ValueError(
            "protected evidence is not a safe readable repository file: "
            + ", ".join(sorted(missing_protected))
        )

    rows.sort(key=lambda row: (-int(row["protected"]), -row["score"], row["path"]))
    required = [row for row in rows if row["protected"]]
    if len(required) > MAX_CANDIDATES:
        raise ValueError("protected evidence exceeds the 50-candidate ceiling")
    optional = [row for row in rows if not row["protected"]]
    target = min(MAX_CANDIDATES, max(MIN_CANDIDATES, len(required)))
    pool = required + optional[: max(0, target - len(required))]
    by_path = {row["path"]: row for row in rows}
    needed_agents = {
        agent for row in pool for agent in row["applicable_agents"]
    }
    for agent in sorted(needed_agents):
        if agent not in {row["path"] for row in pool}:
            candidate = by_path.get(agent)
            if candidate is None:
                raise ValueError(f"applicable AGENTS.md is unavailable: {agent}")
            pool.append(candidate)
    while len(pool) > MAX_CANDIDATES:
        removable = next(
            (
                row
                for row in reversed(pool)
                if not row["protected"] and row["path"] not in needed_agents
            ),
            None,
        )
        if removable is None:
            raise ValueError("applicable AGENTS.md chain exceeds the candidate ceiling")
        pool.remove(removable)
    for row in pool:
        override = content_overrides.get(row["path"])
        row["source_sha256"] = (
            hashlib.sha256(override.encode("utf-8")).hexdigest()
            if override is not None
            else _sha256_file(repo / row["path"])
        )
        row["git_blob"] = _index_blob(repo, row["path"])
        row["working_tree_modified"] = _working_tree_modified(repo, row["path"])
        if override is not None:
            row["carrier_source_sha256"] = _sha256_file(repo / row["path"])
    return pool


def _relevant_lines(
    text: str,
    task_words: set[str],
    protected: bool,
    required_symbols: set[str] | None = None,
) -> tuple[int, int, list[int], str]:
    lines = text.splitlines()
    if not lines:
        return 1, 1, [1], ""
    hits = [
        index
        for index, line in enumerate(lines)
        if task_words & _words(line) or line.lstrip().startswith(("def ", "class ", "#"))
    ]
    indexes: set[int] = set(range(min(len(lines), 12 if protected else 5)))
    for index in hits[:12]:
        indexes.update(range(max(0, index - 2), min(len(lines), index + 3)))
    required_indexes: set[int] = set()
    found_symbols: set[str] = set()
    for match in _DEFINITION.finditer(text):
        symbol = match.group(1)
        if symbol in (required_symbols or set()) and symbol not in found_symbols:
            index = text.count("\n", 0, match.start(1))
            required_indexes.update(
                range(max(0, index - 2), min(len(lines), index + 3))
            )
            found_symbols.add(symbol)
    missing = (required_symbols or set()) - found_symbols
    if missing:
        raise ValueError(
            "protected symbol definition is absent from packet source: "
            + ", ".join(sorted(missing))
        )
    if len(required_indexes) > 80:
        raise ValueError("protected symbol excerpts exceed the per-file excerpt limit")
    optional_indexes = [index for index in sorted(indexes) if index not in required_indexes]
    chosen = sorted(
        required_indexes
        | set(optional_indexes[: max(0, 80 - len(required_indexes))])
    )
    start, end = chosen[0], chosen[-1]
    excerpt = "\n".join(lines[index] for index in chosen)
    return start + 1, end + 1, [index + 1 for index in chosen], excerpt


def _estimate_tokens(text: str) -> int:
    return max(1, (len(text.encode("utf-8")) + 3) // 4)


def _assemble(
    repo: Path,
    ordered: list[dict[str, Any]],
    task_text: str,
    packet_budget_tokens: int,
    content_overrides: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str, int]:
    content_overrides = content_overrides or {}
    task_words = _words(task_text)
    selected: list[dict[str, Any]] = []
    omitted: list[dict[str, Any]] = []
    blocks: list[str] = []
    used = 0
    by_path = {candidate["path"]: candidate for candidate in ordered}
    for candidate in ordered:
        if candidate["path"] in {row["path"] for row in selected}:
            continue
        bundle: list[tuple[dict[str, Any], int, int, list[int], str, int]] = []
        for path in [*candidate.get("applicable_agents", []), candidate["path"]]:
            if path in {row["path"] for row in selected}:
                continue
            row = by_path.get(path)
            if row is None:
                raise ValueError(f"applicable AGENTS.md is unavailable: {path}")
            public_row = dict(row)
            if path != candidate["path"]:
                public_row["protected"] = True
                public_row["reasons"] = sorted(
                    {*public_row["reasons"], "applicable_agents"}
                )
            text = (
                content_overrides[path]
                if path in content_overrides
                else _read_text(repo / path, 512000)
            )
            start, end, line_numbers, excerpt = _relevant_lines(
                text,
                task_words,
                public_row["protected"],
                set(public_row.get("protected_symbols", [])),
            )
            block = f"## {path}:{start}-{end}\n{excerpt}\n"
            bundle.append(
                (
                    public_row,
                    start,
                    end,
                    line_numbers,
                    block,
                    _estimate_tokens(block),
                )
            )
        bundle_tokens = sum(item[-1] for item in bundle)
        if used + bundle_tokens > packet_budget_tokens:
            if candidate["protected"]:
                raise ValueError(
                    f"protected evidence exceeds packet budget at {candidate['path']}"
                )
            omitted.append(
                {
                    "id": candidate["id"],
                    "path": candidate["path"],
                    "reason": "packet_budget",
                }
            )
            continue
        for public, start, end, line_numbers, block, tokens in bundle:
            public.update(
                {
                    "excerpt_start": start,
                    "excerpt_end": end,
                    "excerpt_lines": line_numbers,
                    "estimated_tokens": tokens,
                }
            )
            selected.append(public)
            blocks.append(block)
            used += tokens
    selected_paths = {row["path"] for row in selected}
    for candidate in ordered:
        if candidate["path"] not in selected_paths and not any(
            item["path"] == candidate["path"] for item in omitted
        ):
            omitted.append(
                {
                    "id": candidate["id"],
                    "path": candidate["path"],
                    "reason": "not_selected",
                }
            )
    return selected, omitted, "\n".join(blocks), used


def _default_jev_ranker(
    candidates: list[dict[str, Any]], *, task_text: str, budget: RequestBudget
) -> dict[str, Any]:
    questions: dict[str, dict] = {}
    for candidate in candidates:
        questions[candidate["id"]] = {
            "type": "noul",
            "instructions": (
                "Is the candidate whose identifier and description are in "
                f"candidate.id={candidate['id']} relevant evidence for the repository task?"
            ),
            "criteria": {
                "true": "The candidate is likely needed to implement or verify the task.",
                "false": "The candidate is unrelated or merely shares generic words.",
            },
        }
    state = {
        "task": redact(task_text),
        "candidates": [
            {"id": row["id"], "description": redact(row["description"])}
            for row in candidates
        ],
    }
    result = ask_detailed(state, questions, timeout=1.5, budget=budget)
    selected = [
        candidate["id"]
        for candidate in candidates
        if (noul(result.answers, candidate["id"]) or 0.0) >= 0.5
    ]
    return {"selected_ids": selected, "telemetry": result.telemetry}


def _cache_key(task: bytes, candidates: list[dict[str, Any]]) -> str:
    material = {
        "policy": POLICY_VERSION,
        "model": MODEL,
        "task_sha256": hashlib.sha256(task).hexdigest(),
        "candidates": [
            {
                "id": row["id"],
                "description": row["description"],
                "source_sha256": row["source_sha256"],
            }
            for row in candidates
        ],
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()


def _safe_cache_record(ranked: object) -> dict[str, Any]:
    """Keep only selector identifiers and bounded structured telemetry on disk."""
    if not isinstance(ranked, dict):
        return {"selected_ids": None, "telemetry": None}
    selected = ranked.get("selected_ids")
    if not isinstance(selected, list) or not all(isinstance(item, str) for item in selected):
        selected = None
    raw = ranked.get("telemetry")
    telemetry: dict[str, Any] | None = None
    if isinstance(raw, dict):
        telemetry = {key: raw.get(key) for key in _TELEMETRY_FIELDS}
        failure = telemetry.get("failure")
        if failure is not None and (
            not isinstance(failure, str)
            or re.fullmatch(r"[a-z0-9_]{1,80}", failure) is None
        ):
            telemetry["failure"] = "invalid_failure"
        for key in ("requested_model", "resolved_model"):
            value = telemetry.get(key)
            if value is not None and (
                not isinstance(value, str)
                or re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", value) is None
            ):
                telemetry[key] = None
        usage = raw.get("usage")
        telemetry["usage"] = {
            key: value
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0
            else None
            for key in ("input_tokens", "output_tokens")
            for value in [usage.get(key) if isinstance(usage, dict) else None]
        }
    return {"selected_ids": selected, "telemetry": telemetry}


def _selection_input_size(task_text: str, candidates: list[dict[str, Any]]) -> tuple[int, str]:
    size = len(
        json.dumps(
            {
                "task": task_text,
                "candidates": [
                    {"id": row["id"], "description": row["description"]}
                    for row in candidates
                ],
            },
            sort_keys=True,
        ).encode("utf-8")
    )
    # Frozen Phase-0 diagnostic bands for the 30-candidate descriptor payload.
    # They are not vendor limits and must not be used as admission thresholds.
    band = "small" if size < 10000 else "medium" if size < 20000 else "large"
    return size, band


def select_context(
    repo_root: Path,
    task_path: Path,
    *,
    arm: str = "B",
    packet_budget_tokens: int = 6000,
    cache_dir: Path | None = None,
    jev_ranker: Callable[..., dict[str, Any]] | None = None,
    total_deadline_s: float = 1.5,
    max_http_attempts: int = 2,
    _task_text_override: str | None = None,
    _task_source_override: str | None = None,
) -> dict[str, Any]:
    repo = Path(repo_root).resolve()
    task = Path(task_path).resolve()
    if arm not in {"B", "C"}:
        raise ValueError("arm must be B or C")
    if not MIN_PACKET_TOKENS <= packet_budget_tokens <= MAX_PACKET_TOKENS:
        raise ValueError("packet budget must be between 4000 and 8000 tokens")
    task_rel = _inside(repo, task)
    tracked = set(_tracked(repo))
    if task_rel not in tracked:
        raise ValueError("task source must be a Git-tracked repository file")
    task_bytes = (
        _task_source_override.encode("utf-8")
        if _task_source_override is not None
        else task.read_bytes()
    )
    task_text = (
        _task_text_override
        if _task_text_override is not None
        else task_bytes.decode("utf-8", errors="replace")
    )
    content_overrides = (
        {task_rel: _task_source_override}
        if _task_source_override is not None
        else {}
    )
    candidates = _candidate_pool(repo, task_rel, task_text, content_overrides)
    selection_input_bytes, selection_input_band = _selection_input_size(
        task_text, candidates
    )
    baseline = list(candidates)
    ordered = baseline
    cache_hit = False
    fallback = False
    fallback_reason: str | None = None
    arm_used = arm
    telemetry: dict[str, Any] | None = None

    if arm == "C":
        key = _cache_key(task_bytes, candidates)
        cached: dict[str, Any] | None = None
        cache_file = Path(cache_dir) / f"{key}.json" if cache_dir else None
        if cache_file and cache_file.is_file():
            try:
                parsed = json.loads(cache_file.read_text())
                cached = parsed if isinstance(parsed, dict) else None
            except (OSError, ValueError, RecursionError):
                cached = None
        if cached is not None:
            ranked = cached
            cache_hit = True
        else:
            budget = RequestBudget(total_deadline_s, max_http_attempts)
            ranker = jev_ranker or _default_jev_ranker
            ranked = _safe_cache_record(
                ranker(candidates, task_text=task_text, budget=budget)
            )
        telemetry = ranked.get("telemetry") if isinstance(ranked, dict) else None
        selected_ids = ranked.get("selected_ids") if isinstance(ranked, dict) else None
        known = {row["id"]: row for row in candidates}
        if not isinstance(selected_ids, list):
            fallback_reason = "invalid_selection_schema"
        elif any(item not in known for item in selected_ids):
            fallback_reason = "invalid_candidate_id"
        elif not isinstance(telemetry, dict):
            fallback_reason = "missing_telemetry"
        elif telemetry.get("schema_valid") is not True:
            fallback_reason = telemetry.get("failure") or "invalid_telemetry"
        elif not selected_ids:
            fallback_reason = telemetry.get("failure") or "abstention"
        elif telemetry.get("fallback"):
            fallback_reason = telemetry.get("failure") or "semantic_fallback"
        if fallback_reason:
            fallback = True
            arm_used = "B"
            ordered = baseline
        else:
            if cache_file and not cache_hit:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(json.dumps(ranked, sort_keys=True))
            protected_ids = [row["id"] for row in candidates if row["protected"]]
            ids = list(dict.fromkeys(protected_ids + selected_ids))
            ordered = [known[item] for item in ids]

    known_by_path = {candidate["path"]: candidate for candidate in candidates}
    with_agents: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for candidate in ordered:
        for path in [*candidate.get("applicable_agents", []), candidate["path"]]:
            if path in seen_paths:
                continue
            linked = known_by_path.get(path)
            if linked is None:
                raise ValueError(f"applicable AGENTS.md is unavailable: {path}")
            if path != candidate["path"]:
                linked = dict(linked)
                linked["protected"] = True
                linked["reasons"] = sorted(
                    {*linked["reasons"], "applicable_agents"}
                )
            with_agents.append(linked)
            seen_paths.add(path)
    selected, omitted, packet, estimated_tokens = _assemble(
        repo,
        with_agents,
        task_text,
        packet_budget_tokens,
        content_overrides,
    )
    accounted_paths = {
        row["path"] for row in selected
    } | {row["path"] for row in omitted}
    for candidate in candidates:
        if candidate["path"] not in accounted_paths:
            omitted.append(
                {
                    "id": candidate["id"],
                    "path": candidate["path"],
                    "reason": "semantic_deselected",
                }
            )
    return {
        "policy_version": POLICY_VERSION,
        "arm_requested": arm,
        "arm_used": arm_used,
        "fallback": fallback,
        "fallback_reason": fallback_reason,
        "cache_hit": cache_hit,
        "task_path": task_rel,
        "candidate_count": len(candidates),
        "selection_input_bytes": selection_input_bytes,
        "selection_input_band": selection_input_band,
        "selected": selected,
        "omitted": omitted,
        "packet": packet,
        "packet_estimated_tokens": estimated_tokens,
        "packet_budget_tokens": packet_budget_tokens,
        "telemetry": telemetry,
        "expand_command": "python3 scripts/jev_context_selector.py --repo . --expand PATH",
    }


def load_evaluation_fixture(path: Path = FIXTURE) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text())
    if not isinstance(payload, dict) or not isinstance(payload.get("tasks"), list):
        raise ValueError("invalid evaluation fixture")
    return payload


def select_fixture_task(
    repo_root: Path,
    fixture_path: Path,
    task_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Select context from one frozen task while never passing its labels."""
    fixture = load_evaluation_fixture(fixture_path)
    matches = [task for task in fixture["tasks"] if task.get("id") == task_id]
    if len(matches) != 1 or not isinstance(matches[0].get("task"), str):
        raise ValueError(f"fixture task {task_id!r} is missing or duplicated")
    task_record = json.dumps(
        {"id": task_id, "task": matches[0]["task"]},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ) + "\n"
    result = select_context(
        repo_root,
        fixture_path,
        _task_text_override=matches[0]["task"],
        _task_source_override=task_record,
        **kwargs,
    )
    return {**result, "fixture_task_id": task_id}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", nargs="?", type=Path)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--arm", choices=("B", "C"), default="B")
    parser.add_argument("--packet-budget-tokens", type=int, default=6000)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--total-deadline-s", type=float, default=1.5)
    parser.add_argument("--max-http-attempts", type=int, default=2)
    parser.add_argument("--fixture-task-id")
    parser.add_argument("--expand")
    args = parser.parse_args(argv)
    if args.expand:
        tracked = set(_tracked(args.repo.resolve()))
        if args.expand not in tracked:
            raise SystemExit("refusing to expand a non-tracked path")
        expanded = args.repo.resolve() / args.expand
        if not _safe_repository_file(args.repo.resolve(), expanded):
            raise SystemExit("refusing to expand an unsafe repository path")
        print(_read_text(expanded))
        return 0
    if args.task is None:
        parser.error("task is required unless --expand is used")
    kwargs = {
        "arm": args.arm,
        "packet_budget_tokens": args.packet_budget_tokens,
        "cache_dir": args.cache_dir,
        "total_deadline_s": args.total_deadline_s,
        "max_http_attempts": args.max_http_attempts,
    }
    task = args.task if args.task.is_absolute() else args.repo / args.task
    result = (
        select_fixture_task(args.repo, task, args.fixture_task_id, **kwargs)
        if args.fixture_task_id
        else select_context(args.repo, task, **kwargs)
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
