"""Turīya View — read-only aggregator over all NLM state files.

Sacred root (not invoked in code, only here): in the Mandukya Upanishad
turīya is the fourth state — the witness of the other three (jagrat=waking,
svapna=dream, sushupti=deep sleep) that has no content of its own but is
the condition under which any content can appear. Our three operational
states are:

    jagrat    = nbX_pipeline ingests from the external world
    svapna    = gap_scanner recognizes internal absences
    sushupti  = synthesis_roller compacts without new input

This module is the fourth — it witnesses all three together. It does not
act. It does not decide. It does not call any LLM. It reads local state
files and composes a single JSON snapshot. Latency target <3s for all NBs.

Design rules:

    1. Read-only. No file mutation. No RPC. No network.
    2. No LLM. No Ollama. No prompt. Pure aggregation.
    3. On-demand only. NOT auto-injected into Claude SessionStart briefing
       (would induce diagnostic anxiety — see NLM_REDESIGN_PROPOSAL §7.3).
    4. Missing files are not errors — they're UNKNOWN in the output.

Usage:

    python -m apps.evaluator.nlm_deep_research.turiya --snapshot
    python -m apps.evaluator.nlm_deep_research.turiya --snapshot --nb nb4
    python -m apps.evaluator.nlm_deep_research.turiya --consistency

Output schema: see example at end of docstring (--snapshot JSON).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────────────

_DIR = Path(__file__).parent
_EVALUATOR = _DIR.parent
_HEARTBEAT_DIR = Path.home() / ".agent" / "decisions" / "state"

COVERAGE_MATRIX = _DIR / "coverage_matrix.json"
YAJNA_METRICS = _DIR / "yajna_metrics.jsonl"
YIN_YANG_STATE = _DIR / "yin_yang_state.jsonl"

# ── NB catalog (mirrors NLM_SYSTEM_MAP §2.1) ─────────────────────────────────

# Keys: nb → human-readable label + expected heartbeat pipeline name.
# Pipeline state files live at apps/evaluator/nlm_nbX_pipeline_state.json.
NB_CATALOG: dict[str, dict[str, str]] = {
    "nb2": {"label": "Immigration & Visa", "heartbeat": "nb2_pipeline", "domain": "immigration"},
    "nb3": {"label": "Company Setup & KBLI", "heartbeat": "nb3_pipeline", "domain": "company"},
    "nb4": {"label": "Tax & Fiscal", "heartbeat": "nb4_pipeline", "domain": "tax"},
    "nb5": {"label": "Property & Real Estate", "heartbeat": "nb5_pipeline", "domain": "property"},
    "nb6": {"label": "Operations & Compliance", "heartbeat": "nb6_pipeline", "domain": "operations"},
    "nb7": {"label": "Editorial & Content", "heartbeat": "nb7_pipeline", "domain": "editorial"},
    "nb8": {"label": "Expat Life Bali", "heartbeat": "nb8_pipeline", "domain": "lifestyle"},
    "nb10": {"label": "Team Guides / HR", "heartbeat": "nb10_pipeline", "domain": "team"},
}


# ── Safe readers (never raise) ───────────────────────────────────────────────


def _read_json(path: Path) -> Optional[dict[str, Any]]:
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.debug("turiya: failed to read %s — %s", path, exc)
        return None


def _read_jsonl_last(path: Path) -> Optional[dict[str, Any]]:
    if not path.exists():
        return None
    try:
        last: Optional[dict[str, Any]] = None
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    last = json.loads(line)
                except json.JSONDecodeError:
                    continue
        return last
    except OSError:
        return None


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with open(path, encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except OSError:
        return 0


# ── Per-state readers ────────────────────────────────────────────────────────


def _read_pipeline_state(nb: str, evaluator_root: Optional[Path] = None) -> dict[str, Any]:
    """Read nlm_nbX_pipeline_state.json — jagrat (waking/ingest) layer."""
    root = evaluator_root or _EVALUATOR
    path = root / f"nlm_{nb}_pipeline_state.json"
    data = _read_json(path)
    if not data:
        return {"available": False}
    return {
        "available": True,
        "current_state": data.get("current_state", "?"),
        "degradation_level": data.get("degradation_level", "?"),
        "last_updated": data.get("last_updated", "?"),
        "last_run_cluster": (data.get("last_run") or {}).get("cluster", "?"),
        "last_run_claims_total": (data.get("last_run") or {}).get("claims_total", 0),
    }


def _read_synthesis_state(nb: str, evaluator_root: Optional[Path] = None) -> dict[str, Any]:
    """Read nlm_nbX_synthesis_state.json — sushupti (deep sleep/compact) layer."""
    root = evaluator_root or _EVALUATOR
    path = root / f"nlm_{nb}_synthesis_state.json"
    data = _read_json(path)
    if not data:
        return {"available": False}
    return {
        "available": True,
        "last_updated": data.get("last_updated", "?"),
        "daily_sources_count": len(data.get("daily_sources", []) or []),
        "weekly_sources_count": len(data.get("weekly_sources", []) or []),
        "monthly_sources_count": len(data.get("monthly_sources", []) or []),
    }


def _read_heartbeat(pipeline_name: str, heartbeat_dir: Optional[Path] = None) -> dict[str, Any]:
    """Read heartbeat_<name>.json — ARCH-9 monitoring layer."""
    hdir = heartbeat_dir or _HEARTBEAT_DIR
    path = hdir / f"heartbeat_{pipeline_name}.json"
    data = _read_json(path)
    if not data:
        return {"available": False}
    last = data.get("last_success", "?")
    age_hours: Optional[float] = None
    if last and last != "?":
        try:
            dt = datetime.fromisoformat(last)
            now = datetime.now(timezone.utc) if dt.tzinfo is None else datetime.now(dt.tzinfo)
            age_hours = round((now - dt).total_seconds() / 3600, 2)
        except (ValueError, TypeError):
            pass
    return {
        "available": True,
        "last_success": last,
        "age_hours": age_hours,
        "duration_seconds": data.get("duration_seconds"),
    }


def _read_coverage_for_domain(domain: str) -> dict[str, Any]:
    """Read coverage_matrix.json → svapna (dream/gap) layer for this domain."""
    matrix = _read_json(COVERAGE_MATRIX)
    if not matrix:
        return {"available": False}
    entry = matrix.get(domain)
    if not entry:
        return {"available": False, "reason": f"no entry for domain={domain}"}
    coverage = entry.get("coverage") or {}
    total = len(coverage)
    fresh = sum(1 for v in coverage.values() if v == "FRESH")
    gap = sum(1 for v in coverage.values() if v == "GAP")
    return {
        "available": True,
        "gaps_count": len(entry.get("gaps", []) or []),
        "gaps_updated": entry.get("gaps_updated", "?"),
        "coverage_total": total,
        "coverage_fresh": fresh,
        "coverage_gap": gap,
        "fresh_pct": round(fresh / total * 100, 1) if total else 0.0,
        "gap_pct": round(gap / total * 100, 1) if total else 0.0,
        "coverage_updated": entry.get("coverage_updated", "?"),
    }


def _read_yajna_for_nb(nb: str) -> dict[str, Any]:
    """Read yajna_metrics.jsonl (last line) → return this NB's slice."""
    latest = _read_jsonl_last(YAJNA_METRICS)
    if not latest:
        return {"available": False}
    per_nb = (latest.get("per_nb") or {}).get(nb, {})
    totals = latest.get("totals") or {}
    rates = latest.get("rates") or {}
    return {
        "available": True,
        "window_days": latest.get("window_days"),
        "computed_at": latest.get("computed_at"),
        "offered": per_nb.get("offered", 0),
        "cited": per_nb.get("cited", 0),
        "promoted": per_nb.get("promoted", 0),
        "global_cite_rate": rates.get("cite_rate"),
        "global_orphans": latest.get("orphan_count", 0),
        "global_offered": totals.get("offered", 0),
    }


def _read_yin_yang_for_nb(nb: str) -> dict[str, Any]:
    """Read yin_yang_state.jsonl (last line) → return this NB's slice."""
    latest = _read_jsonl_last(YIN_YANG_STATE)
    if not latest:
        return {"available": False}
    per_nb = (latest.get("per_nb") or {}).get(nb, {})
    streaks = (latest.get("streaks") or {}).get(nb, {})
    return {
        "available": True,
        "audit_ts": latest.get("ts"),
        "ratio": per_nb.get("ratio"),
        "status": per_nb.get("status", "?"),
        "consecutive_weeks": streaks.get("consecutive_weeks", 0),
    }


# ── Consistency checks ───────────────────────────────────────────────────────


def _build_consistency(
    nb: str,
    jagrat: dict[str, Any],
    svapna: dict[str, Any],
    sushupti: dict[str, Any],
    heartbeat: dict[str, Any],
    yajna: dict[str, Any],
    yin_yang: dict[str, Any],
) -> dict[str, Any]:
    """Cross-check the four states and surface structural inconsistencies."""
    flags: list[str] = []

    # Heartbeat stale despite recent pipeline run?
    hb_age = heartbeat.get("age_hours") if heartbeat.get("available") else None
    if (
        jagrat.get("available")
        and jagrat.get("current_state") == "COMPLETE"
        and hb_age is not None
        and hb_age > 48
    ):
        flags.append(f"jagrat COMPLETE but heartbeat stale {hb_age}h")

    # Pipeline HALTED but heartbeat fresh = paradox
    if (
        jagrat.get("available")
        and jagrat.get("current_state") == "HALTED"
        and hb_age is not None
        and hb_age < 12
    ):
        flags.append(f"jagrat HALTED but heartbeat fresh {hb_age}h — check halt reason")

    # Coverage matrix frozen (stale_updated >30d)
    cov_updated = svapna.get("coverage_updated", "?")
    if cov_updated and cov_updated != "?":
        try:
            dt = datetime.fromisoformat(cov_updated)
            age_days = (datetime.now(timezone.utc) - (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))).days
            if age_days > 30:
                flags.append(f"svapna coverage_matrix stale {age_days}d — gap_scanner layer-B not updating")
        except (ValueError, TypeError):
            pass

    # Yang flood surfaced
    yy_status = yin_yang.get("status") if yin_yang.get("available") else None
    if yy_status and yy_status not in {"HEALTHY", "UNKNOWN", "?"}:
        weeks = yin_yang.get("consecutive_weeks", 0)
        flags.append(f"yin-yang {yy_status} for {weeks} consecutive weeks")

    # Zero consumer (orphan NB = ingested but never cited)
    if yajna.get("available"):
        offered = int(yajna.get("offered", 0) or 0)
        cited = int(yajna.get("cited", 0) or 0)
        if offered >= 10 and cited == 0:
            flags.append(f"yajna: {offered} claims offered, 0 cited — possible orphan NB")

    return {"flags": flags, "ok": len(flags) == 0}


# ── Per-NB snapshot ──────────────────────────────────────────────────────────


def snapshot_nb(
    nb: str,
    evaluator_root: Optional[Path] = None,
    heartbeat_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """Compose the four-state snapshot for a single NB."""
    cat = NB_CATALOG.get(nb, {})
    label = cat.get("label", nb)
    hb_name = cat.get("heartbeat", f"{nb}_pipeline")
    domain = cat.get("domain", nb.replace("nb", ""))

    jagrat = _read_pipeline_state(nb, evaluator_root=evaluator_root)
    sushupti = _read_synthesis_state(nb, evaluator_root=evaluator_root)
    heartbeat = _read_heartbeat(hb_name, heartbeat_dir=heartbeat_dir)
    svapna = _read_coverage_for_domain(domain)
    yajna = _read_yajna_for_nb(nb)
    yin_yang = _read_yin_yang_for_nb(nb)

    consistency = _build_consistency(nb, jagrat, svapna, sushupti, heartbeat, yajna, yin_yang)

    return {
        "nb": nb,
        "label": label,
        "domain": domain,
        "jagrat": jagrat,
        "svapna": svapna,
        "sushupti": sushupti,
        "heartbeat": heartbeat,
        "yajna": yajna,
        "yin_yang": yin_yang,
        "consistency": consistency,
    }


# ── Global snapshot ──────────────────────────────────────────────────────────


def snapshot_all(
    nb_catalog: Optional[dict[str, dict[str, str]]] = None,
    evaluator_root: Optional[Path] = None,
    heartbeat_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """Compose snapshots for every NB in the catalog + global flags."""
    catalog = nb_catalog or NB_CATALOG
    per_nb: dict[str, Any] = {}
    global_flags: list[str] = []

    for nb in catalog:
        per_nb[nb] = snapshot_nb(
            nb, evaluator_root=evaluator_root, heartbeat_dir=heartbeat_dir
        )

    # Count heartbeat-registry coverage globally
    hdir = heartbeat_dir or _HEARTBEAT_DIR
    if hdir.exists():
        existing = sum(1 for _ in hdir.glob("heartbeat_*.json"))
        registry_path = _DIR / "pipeline_heartbeat_registry.json"
        registry = _read_json(registry_path)
        if registry:
            declared = len(registry)
            if existing < declared:
                global_flags.append(
                    f"heartbeat_registry: {existing}/{declared} pipelines have recorded heartbeat"
                )

    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "observer": "turiya-v1",
        "per_nb": per_nb,
        "global_flags": global_flags,
    }


# ── CLI ──────────────────────────────────────────────────────────────────────


def _print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def main() -> int:
    parser = argparse.ArgumentParser(description="Turīya View — read-only aggregator over NLM state")
    parser.add_argument("--snapshot", action="store_true", help="full snapshot of all NBs")
    parser.add_argument("--nb", metavar="NB", help="restrict snapshot to a single NB (e.g. nb4)")
    parser.add_argument(
        "--consistency",
        action="store_true",
        help="print only the consistency flags per NB, no raw state",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if not (args.snapshot or args.consistency):
        parser.print_help()
        return 1

    if args.nb:
        if args.nb not in NB_CATALOG:
            print(f"unknown nb={args.nb}. Valid: {sorted(NB_CATALOG)}", file=sys.stderr)
            return 2
        snap = snapshot_nb(args.nb)
        if args.consistency:
            _print_json({"nb": args.nb, "consistency": snap["consistency"]})
        else:
            _print_json(snap)
        return 0

    # All NBs
    full = snapshot_all()
    if args.consistency:
        out = {
            "ts": full["ts"],
            "global_flags": full["global_flags"],
            "per_nb": {
                nb: {"label": entry["label"], "consistency": entry["consistency"]}
                for nb, entry in full["per_nb"].items()
            },
        }
        _print_json(out)
    else:
        _print_json(full)
    return 0


if __name__ == "__main__":
    sys.exit(main())
