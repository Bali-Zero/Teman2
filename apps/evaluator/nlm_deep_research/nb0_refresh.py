"""NB-0 Meta-NLM daily refresh — the fifth stratum.

NB-0 is the meta-NLM proposed in NLM_REDESIGN_PROPOSAL §1.2 (stratum "meta"):
a single notebook that watches the other 19 NBs watching the world. Its
contents are assembled daily from purely local state (no LLM, no RPC) and
pushed to NotebookLM as a handful of small Markdown sources. Claude at
SessionStart or Zero on-demand can then ask NB-0 "what is changing" and get
an answer anchored in data.

Bootstrap is Zero's responsibility (one-time manual step). This module
REFUSES TO RUN without ``NB0_NOTEBOOK_ID`` set — we never create NotebookLM
notebooks autonomously because:

    - NLM notebook creation is non-trivially irreversible (no native delete
      from CLI; the container is owned by the creator's Google account).
    - A mis-created NB-0 would need manual reconciliation.

The guard lives in ``main()``. In library mode (pure aggregator functions)
all components work without the env var.

Sacred root: no "meta" stratum is proposed anywhere in SYMBIOSIS.md or the
sacred traditions surveyed in NLM_SACRED_READING.md as a *substance*. It
exists only as *relation* — the position from which the others become
visible. This module makes that relation machine-readable.

Usage:

    # Dry-run (no NLM upload, prints the Markdown sources that would be pushed)
    python -m apps.evaluator.nlm_deep_research.nb0_refresh --dry-run

    # Production (requires NB0_NOTEBOOK_ID env set + nlm CLI in PATH)
    NB0_NOTEBOOK_ID=<uuid> python -m apps.evaluator.nlm_deep_research.nb0_refresh --push
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────────────

_DIR = Path(__file__).parent
STATE_FILE = _DIR / "nb0_refresh_state.json"

NLM_CLI = "nlm"
NLM_SOURCE_ADD_TIMEOUT = 120
NLM_SOURCE_DELETE_TIMEOUT = 60

# Five source titles we manage (stable titles → SHA256 diff to skip no-op pushes)
SOURCE_TITLES = {
    "yajna": "[NB-0] Yajña metrics — claim lifecycle weekly",
    "yin_yang": "[NB-0] Yin-Yang balance audit — weekly",
    "heartbeat": "[NB-0] Heartbeat digest — pipeline health",
    "turiya": "[NB-0] Turīya snapshot — cross-state consistency",
    "coverage": "[NB-0] Coverage matrix — freshness per domain",
}


# ── Bootstrap guard ──────────────────────────────────────────────────────────


def get_nb0_notebook_id() -> Optional[str]:
    """Read NB0_NOTEBOOK_ID env var. Returns None if unset or empty."""
    raw = os.environ.get("NB0_NOTEBOOK_ID", "").strip()
    return raw or None


class BootstrapRequired(RuntimeError):
    """Raised when --push mode is requested but NB0_NOTEBOOK_ID is unset."""


# ── Sources assemblers (pure, no side effects) ───────────────────────────────


def assemble_yajna_source(metrics_path: Optional[Path] = None) -> str:
    """Render yajna weekly metrics as Markdown. Returns "" if no metrics file."""
    metrics_path = metrics_path or (_DIR / "yajna_metrics.jsonl")
    if not metrics_path.exists():
        return ""
    last: Optional[dict[str, Any]] = None
    try:
        with open(metrics_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    last = json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return ""
    if not last:
        return ""

    totals = last.get("totals") or {}
    rates = last.get("rates") or {}
    per_nb = last.get("per_nb") or {}

    lines = ["# Yajña weekly metrics", ""]
    lines.append(f"- computed_at: {last.get('computed_at', '?')}")
    lines.append(f"- window_days: {last.get('window_days', '?')}")
    lines.append(f"- offered: {totals.get('offered', 0)}")
    lines.append(f"- cited: {totals.get('cited', 0)}")
    lines.append(f"- promoted: {totals.get('promoted', 0)}")
    lines.append(f"- cite_rate: {rates.get('cite_rate', 0.0)}")
    lines.append(f"- orphan_count: {last.get('orphan_count', 0)}")
    lines.append("")
    lines.append("## Per NB")
    lines.append("")
    if not per_nb:
        lines.append("(no NB-level data)")
    else:
        lines.append("| NB | offered | cited | promoted |")
        lines.append("| --- | --- | --- | --- |")
        for nb, counts in sorted(per_nb.items()):
            lines.append(
                f"| {nb} | {counts.get('offered', 0)} | {counts.get('cited', 0)} | {counts.get('promoted', 0)} |"
            )
    return "\n".join(lines) + "\n"


def assemble_yin_yang_source(state_path: Optional[Path] = None) -> str:
    """Render yin-yang latest audit as Markdown."""
    state_path = state_path or (_DIR / "yin_yang_state.jsonl")
    if not state_path.exists():
        return ""
    last: Optional[dict[str, Any]] = None
    try:
        with open(state_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    last = json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return ""
    if not last:
        return ""

    per_nb = last.get("per_nb") or {}
    recs = last.get("recommendations") or []

    lines = ["# Yin-Yang balance audit", ""]
    lines.append(f"- ts: {last.get('ts', '?')}")
    lines.append(f"- auto_adjust_enabled: {last.get('auto_adjust_enabled', 'n/a')}")
    lines.append("")
    lines.append("## Per-NB ratio + status")
    lines.append("")
    if not per_nb:
        lines.append("(no NB data)")
    else:
        lines.append("| NB | offered | cited | promoted | ratio | status |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for nb, v in sorted(per_nb.items()):
            lines.append(
                f"| {nb} | {v.get('offered', 0)} | {v.get('cited', 0)} | "
                f"{v.get('promoted', 0)} | {v.get('ratio', 0)} | {v.get('status', '?')} |"
            )
    lines.append("")
    lines.append("## Recommendations")
    lines.append("")
    if not recs:
        lines.append("_no recommendations this week_")
    else:
        for r in recs:
            lines.append(
                f"- **{r.get('nb', '?')}** — {r.get('action', '?')} "
                f"(auto_applied={r.get('auto_applied', 'n/a')}, reversible={r.get('reversible', 'n/a')}) "
                f"— {r.get('reason', '')}"
            )
    return "\n".join(lines) + "\n"


def assemble_heartbeat_source(
    state_dir: Optional[Path] = None,
    registry_path: Optional[Path] = None,
) -> str:
    """Render the current heartbeat digest as Markdown."""
    hdir = state_dir or (Path.home() / ".agent" / "decisions" / "state")
    reg_path = registry_path or (_DIR / "pipeline_heartbeat_registry.json")

    declared: list[str] = []
    if reg_path.exists():
        try:
            with open(reg_path, encoding="utf-8") as f:
                registry = json.load(f)
            declared = sorted(registry.keys())
        except (json.JSONDecodeError, OSError):
            pass

    rows: list[tuple[str, str]] = []  # (pipeline_name, last_success or "NEVER")
    if hdir.exists():
        for name in declared:
            hb_file = hdir / f"heartbeat_{name}.json"
            if not hb_file.exists():
                rows.append((name, "NEVER"))
                continue
            try:
                with open(hb_file, encoding="utf-8") as f:
                    hb = json.load(f)
                rows.append((name, hb.get("last_success", "?")))
            except (json.JSONDecodeError, OSError):
                rows.append((name, "CORRUPT"))

    lines = ["# Heartbeat digest", ""]
    lines.append(f"- declared_pipelines: {len(declared)}")
    lines.append(f"- recorded: {sum(1 for _, v in rows if v not in ('NEVER', 'CORRUPT'))}")
    lines.append(f"- missing: {sum(1 for _, v in rows if v == 'NEVER')}")
    lines.append("")
    lines.append("| pipeline | last_success |")
    lines.append("| --- | --- |")
    for name, v in rows:
        lines.append(f"| `{name}` | {v} |")
    return "\n".join(lines) + "\n"


def assemble_coverage_source(path: Optional[Path] = None) -> str:
    """Render coverage_matrix.json as Markdown."""
    path = path or (_DIR / "coverage_matrix.json")
    if not path.exists():
        return ""
    try:
        with open(path, encoding="utf-8") as f:
            matrix = json.load(f)
    except (json.JSONDecodeError, OSError):
        return ""
    if not isinstance(matrix, dict) or not matrix:
        return ""

    lines = ["# Coverage matrix — freshness per domain", ""]
    lines.append("| domain | gaps | fresh_pct | gap_pct | updated |")
    lines.append("| --- | --- | --- | --- | --- |")
    for domain, entry in sorted(matrix.items()):
        if not isinstance(entry, dict):
            continue
        gaps = entry.get("gaps", []) or []
        lines.append(
            f"| {domain} | {len(gaps)} | {entry.get('health_pct', 0)}% | "
            f"{entry.get('gap_pct', 0)}% | {entry.get('coverage_updated', '?')} |"
        )
    return "\n".join(lines) + "\n"


def assemble_turiya_source() -> str:
    """Render a turiya snapshot as Markdown."""
    try:
        from apps.evaluator.nlm_deep_research.turiya import snapshot_all  # noqa: PLC0415
    except ImportError:
        return ""
    try:
        snap = snapshot_all()
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("nb0: turiya snapshot failed — %s", exc)
        return ""

    per_nb = snap.get("per_nb", {})
    flags = snap.get("global_flags", [])

    lines = ["# Turīya snapshot — cross-state consistency", ""]
    lines.append(f"- ts: {snap.get('ts', '?')}")
    lines.append("")
    lines.append("## Global flags")
    lines.append("")
    if not flags:
        lines.append("_no global anomalies_")
    else:
        for f in flags:
            lines.append(f"- {f}")
    lines.append("")
    lines.append("## Per-NB consistency")
    lines.append("")
    for nb, entry in sorted(per_nb.items()):
        cons = entry.get("consistency", {})
        cons_flags = cons.get("flags", [])
        ok = "✅" if cons.get("ok") else "⚠️"
        lines.append(f"### {ok} {nb} — {entry.get('label', '')}")
        if cons_flags:
            for f in cons_flags:
                lines.append(f"- {f}")
        else:
            lines.append("- no anomalies")
    return "\n".join(lines) + "\n"


# ── Assemble + diff + push ───────────────────────────────────────────────────


def build_all_sources() -> dict[str, str]:
    """Return {key: markdown_body} for every NB-0 source. Empty strings are
    normal when the underlying data file does not yet exist."""
    return {
        "yajna": assemble_yajna_source(),
        "yin_yang": assemble_yin_yang_source(),
        "heartbeat": assemble_heartbeat_source(),
        "turiya": assemble_turiya_source(),
        "coverage": assemble_coverage_source(),
    }


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {"hashes": {}, "last_run": None}
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"hashes": {}, "last_run": None}


def _save_state(state: dict[str, Any]) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except OSError as exc:
        logger.warning("nb0: state save failed — %s", exc)


def _nlm_source_add(notebook_id: str, title: str, body: str) -> bool:
    """Invoke `nlm source add <notebook_id> --type text --title T --text BODY`."""
    try:
        result = subprocess.run(
            [
                NLM_CLI,
                "source",
                "add",
                notebook_id,
                "--type",
                "text",
                "--title",
                title,
                "--text",
                body,
            ],
            capture_output=True,
            text=True,
            timeout=NLM_SOURCE_ADD_TIMEOUT,
        )
        if result.returncode != 0:
            logger.error(
                "nb0: nlm source add failed (title=%s): %s",
                title,
                result.stderr.strip()[:200],
            )
            return False
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        logger.error("nb0: nlm CLI invocation failed — %s", exc)
        return False


def run_refresh(
    notebook_id: Optional[str] = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Execute a refresh cycle. Returns summary dict.

    When dry_run=True: renders Markdown, computes diff, does NOT call nlm CLI.
    When dry_run=False + notebook_id set: uploads changed sources.
    """
    sources = build_all_sources()
    state = _load_state()
    prior_hashes: dict[str, str] = state.get("hashes", {}) or {}
    new_hashes: dict[str, str] = {}
    pushed: list[str] = []
    skipped_unchanged: list[str] = []
    skipped_empty: list[str] = []
    failed: list[str] = []

    for key, body in sources.items():
        if not body:
            skipped_empty.append(key)
            new_hashes[key] = ""
            continue
        digest = _sha256(body)
        new_hashes[key] = digest
        if prior_hashes.get(key) == digest:
            skipped_unchanged.append(key)
            continue
        title = SOURCE_TITLES[key]
        if dry_run or not notebook_id:
            pushed.append(key)
            continue
        ok = _nlm_source_add(notebook_id, title, body)
        if ok:
            pushed.append(key)
        else:
            failed.append(key)

    # Only persist hashes for the ones we *actually* pushed (or dry-run accepted)
    if not dry_run:
        for key in pushed:
            state.setdefault("hashes", {})[key] = new_hashes[key]
        state["last_run"] = datetime.now(timezone.utc).isoformat()
        _save_state(state)

    return {
        "dry_run": dry_run,
        "notebook_id": notebook_id or "(unset)",
        "pushed": pushed,
        "skipped_unchanged": skipped_unchanged,
        "skipped_empty": skipped_empty,
        "failed": failed,
        "sources_total": len(sources),
    }


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="NB-0 Meta-NLM refresh")
    parser.add_argument("--dry-run", action="store_true", help="assemble + show diff, do NOT upload")
    parser.add_argument("--push", action="store_true", help="upload changed sources via nlm CLI")
    parser.add_argument("--print", dest="print_sources", action="store_true", help="print the assembled markdown")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if not (args.dry_run or args.push or args.print_sources):
        parser.print_help()
        return 1

    if args.print_sources:
        sources = build_all_sources()
        for key, body in sources.items():
            print(f"=== source: {key} ===")
            if not body:
                print("(empty — underlying data file not present yet)")
            else:
                print(body)
            print()
        return 0

    nb_id = get_nb0_notebook_id()

    if args.push and not nb_id:
        msg = (
            "NB-0 bootstrap required: NB0_NOTEBOOK_ID env var is not set.\n"
            "\n"
            "Zero must create the notebook ONCE manually:\n"
            "    nlm notebook create --title 'NB-0 Meta-NLM — System Reflection'\n"
            "then export the UUID:\n"
            "    export NB0_NOTEBOOK_ID=<uuid>\n"
            "and re-run this command.\n"
            "\n"
            "This script refuses to create the notebook itself because NLM notebook\n"
            "creation is non-trivially irreversible — a mis-created NB-0 would need\n"
            "manual reconciliation."
        )
        print(msg, file=sys.stderr)
        return 3

    summary = run_refresh(notebook_id=nb_id, dry_run=args.dry_run or not args.push)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if not summary.get("failed") else 2


if __name__ == "__main__":
    sys.exit(main())
