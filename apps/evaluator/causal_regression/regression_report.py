"""Aggregate replay results and causal diffs into deterministic JSON + HTML reports.

The JSON report is the machine-readable surface: sorted keys, no timestamps,
byte-identical across runs on the same input. The HTML report is a self-contained
file (inline CSS, no scripts, no network) with a CSS-grid flamegraph: rows are
queries, columns are commits in order, and cells are colored by pass/fail with a
hover tooltip naming the root-cause category for any pass->fail transition. The
top three regressions are pulled out above the grid for quick scanning.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ._types import (
    ROOT_CAUSE_COLORS,
    CausalDiff,
    CommitSnapshot,
    QueryResult,
    RootCause,
)


@dataclass
class ReportInputs:
    range_expr: str
    snapshots: list[CommitSnapshot]
    results: list[QueryResult]  # flat list across all commits
    diffs: list[CausalDiff]  # list of pairwise diffs (prev -> curr)
    warnings: list[str]
    kb_root: str


def _top_regressions(diffs: list[CausalDiff], n: int = 3) -> list[dict]:
    """Return the top-N clear pass->fail transitions, sorted for determinism."""
    regressions = [
        d
        for d in diffs
        if d.prev_passed and not d.curr_passed
    ]
    # Sort by: biggest claim loss first, then by (query_id, curr_sha) for ties.
    def _score(d: CausalDiff) -> tuple:
        lost = len(d.claim_delta.get("missing_now", []))
        return (-lost, d.query_id, d.curr_sha)

    regressions.sort(key=_score)
    return [
        {
            "query_id": d.query_id,
            "prev_sha": d.prev_sha,
            "curr_sha": d.curr_sha,
            "root_cause": d.root_cause.value,
            "missing_keywords": sorted(d.claim_delta.get("missing_now", [])),
        }
        for d in regressions[:n]
    ]


def build_json(inputs: ReportInputs, trim: bool = False) -> dict:
    """Assemble the JSON-shape dict. Keys sorted by `json.dumps(sort_keys=True)`.

    When `trim=True`, per-query `results` are omitted and each diff's
    `retrieval_delta` is summarized by the count of moved docs. The report then
    keeps top regressions, snapshot metadata, and aggregate counts — enough to
    reproduce the flamegraph story, small enough to commit as an example.
    """
    snapshots = [s.to_dict() for s in sorted(inputs.snapshots, key=lambda s: s.order_index)]
    results_raw = sorted(
        [r.to_dict() for r in inputs.results],
        key=lambda r: (r["commit_sha"], r["query_id"]),
    )
    diffs_raw = sorted(
        [d.to_dict() for d in inputs.diffs],
        key=lambda d: (d["curr_sha"], d["query_id"]),
    )
    top_regs = _top_regressions(inputs.diffs, n=3)

    # Category counts for the legend / summary.
    cat_counts: dict[str, int] = {k: 0 for k in ROOT_CAUSE_COLORS}
    for d in inputs.diffs:
        if d.prev_passed and not d.curr_passed:
            cat_counts[d.root_cause.value] += 1

    if trim:
        results_payload: list[dict] = []
        # Keep only diffs that represent a state transition OR a non-trivial
        # retrieval/claim change — the rest is noise for a committed example.
        diffs_payload = []
        for d in diffs_raw:
            keep = (
                d["prev_passed"] != d["curr_passed"]
                or d["root_cause"] != RootCause.UNKNOWN.value
                or d["claim_delta"].get("missing_now")
                or d["claim_delta"].get("regained")
                or d["retrieval_delta"]
            )
            if not keep:
                continue
            diffs_payload.append(
                {
                    "curr_sha": d["curr_sha"],
                    "prev_sha": d["prev_sha"],
                    "query_id": d["query_id"],
                    "prev_passed": d["prev_passed"],
                    "curr_passed": d["curr_passed"],
                    "root_cause": d["root_cause"],
                    "retrieval_delta_count": len(d["retrieval_delta"]),
                    "claim_delta": d["claim_delta"],
                }
            )
    else:
        results_payload = results_raw
        diffs_payload = diffs_raw

    return {
        "metadata": {
            "range": inputs.range_expr,
            "kb_root": inputs.kb_root,
            "commit_count": len(snapshots),
            "query_count": (
                len({r["query_id"] for r in results_raw}) if results_raw else 0
            ),
            "warnings": sorted(set(inputs.warnings)),
            "trimmed": bool(trim),
        },
        "snapshots": snapshots,
        "results": results_payload,
        "diffs": diffs_payload,
        "top_regressions": top_regs,
        "regression_counts_by_cause": cat_counts,
    }


def write_json(report: dict, out_path: Path) -> None:
    """Write `report` to `out_path` with canonical formatting.

    We use `sort_keys=True`, no timestamps anywhere, UTF-8 (Python default),
    and a trailing newline so editors don't add one.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False)
    out_path.write_text(text + "\n", encoding="utf-8")


def write_trimmed_json(inputs: ReportInputs, out_path: Path) -> None:
    """Write a slimmed-down JSON for committed example artifacts."""
    write_json(build_json(inputs, trim=True), out_path)


def _escape_html(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _cell_color(passed: bool, cause: str | None) -> str:
    if passed:
        return "#27ae60"  # green
    if cause and cause != RootCause.UNKNOWN.value:
        return ROOT_CAUSE_COLORS.get(cause, "#95a5a6")
    return "#95a5a6"  # grey for unclassified failure


def build_html(inputs: ReportInputs) -> str:
    """Render a self-contained HTML report with a CSS-grid flamegraph.

    No JS, no external CSS, no network calls. Safe to open offline.
    """
    snapshots = sorted(inputs.snapshots, key=lambda s: s.order_index)
    query_ids = sorted({r.query_id for r in inputs.results})

    # Index results by (sha, qid) for O(1) cell lookup.
    cells: dict[tuple[str, str], QueryResult] = {}
    for r in inputs.results:
        cells[(r.commit_sha, r.query_id)] = r

    # Index diffs similarly so we can attach root cause to the CURRENT commit cell.
    diff_by_cell: dict[tuple[str, str], str] = {}
    for d in inputs.diffs:
        diff_by_cell[(d.curr_sha, d.query_id)] = d.root_cause.value

    top_regs = _top_regressions(inputs.diffs, n=3)

    parts: list[str] = []
    parts.append("<!doctype html>")
    parts.append('<html lang="en"><head><meta charset="utf-8">')
    parts.append("<title>Causal Regression Report</title>")
    parts.append("<style>")
    parts.append(
        "body{font-family:-apple-system,Segoe UI,sans-serif;margin:24px;color:#222}"
        "h1{font-size:20px}h2{font-size:16px;margin-top:24px}"
        ".flamegraph{border-collapse:collapse;font-size:11px}"
        ".flamegraph td{border:1px solid #ccc;padding:2px 4px;text-align:center;"
        "min-width:22px;height:22px;color:#fff;font-weight:bold}"
        ".flamegraph th{border:1px solid #ccc;padding:2px 6px;"
        "background:#ecf0f1;font-family:ui-monospace,monospace;font-size:10px}"
        ".flamegraph th.qid{text-align:right;background:#f7f9fa;color:#222;font-weight:normal}"
        ".legend{margin:12px 0;font-size:12px}"
        ".legend .swatch{display:inline-block;width:12px;height:12px;margin-right:4px;"
        "vertical-align:middle;border:1px solid #888}"
        ".legend span.item{margin-right:14px;white-space:nowrap}"
        ".topreg li{margin:4px 0}"
        ".muted{color:#666;font-size:11px}"
        "details{margin-top:12px}"
    )
    parts.append("</style></head><body>")
    parts.append("<h1>Causal Regression Report</h1>")
    parts.append(
        f'<div class="muted">range: <code>{_escape_html(inputs.range_expr)}</code> '
        f'&middot; kb_root: <code>{_escape_html(inputs.kb_root)}</code> '
        f'&middot; {len(snapshots)} commits &middot; {len(query_ids)} queries</div>'
    )

    # Top regressions
    parts.append("<h2>Top regressions</h2>")
    if top_regs:
        parts.append('<ol class="topreg">')
        for r in top_regs:
            parts.append(
                "<li><code>{qid}</code> at <code>{csha}</code> — "
                "<strong>{cause}</strong> — "
                "missing: {kws}</li>".format(
                    qid=_escape_html(r["query_id"]),
                    csha=_escape_html(r["curr_sha"][:12]),
                    cause=_escape_html(r["root_cause"]),
                    kws=_escape_html(", ".join(r["missing_keywords"]) or "(retrieval drift)"),
                )
            )
        parts.append("</ol>")
    else:
        parts.append("<p>No pass-to-fail transitions detected.</p>")

    # Legend
    parts.append("<h2>Legend</h2><div class=\"legend\">")
    parts.append(
        '<span class="item"><span class="swatch" style="background:#27ae60"></span>pass</span>'
    )
    for cause, color in ROOT_CAUSE_COLORS.items():
        parts.append(
            f'<span class="item"><span class="swatch" style="background:{color}"></span>'
            f"{_escape_html(cause)}</span>"
        )
    parts.append("</div>")

    # Flamegraph table
    parts.append("<h2>Flamegraph (rows=queries, columns=commits, left=old)</h2>")
    parts.append('<table class="flamegraph"><thead><tr><th class="qid">query</th>')
    for s in snapshots:
        parts.append(
            f'<th title="{_escape_html(s.subject)}">{_escape_html(s.short_sha)}</th>'
        )
    parts.append("</tr></thead><tbody>")
    for qid in query_ids:
        parts.append(f'<tr><th class="qid">{_escape_html(qid)}</th>')
        for s in snapshots:
            cell = cells.get((s.sha, qid))
            if cell is None:
                parts.append('<td style="background:#ddd">-</td>')
                continue
            cause = diff_by_cell.get((s.sha, qid))
            color = _cell_color(cell.passed, cause)
            label = "P" if cell.passed else "F"
            tooltip = (
                f"{qid} @ {s.short_sha} | coverage={cell.coverage:.2f}"
                f" | {('PASS' if cell.passed else 'FAIL')}"
                f" | cause={cause or '-'}"
            )
            parts.append(
                f'<td style="background:{color}" title="{_escape_html(tooltip)}">{label}</td>'
            )
        parts.append("</tr>")
    parts.append("</tbody></table>")

    # Warnings section
    warns = sorted(set(inputs.warnings))
    if warns:
        parts.append(f"<details><summary>Warnings ({len(warns)})</summary><ul>")
        for w in warns[:100]:
            parts.append(f"<li><code>{_escape_html(w)}</code></li>")
        parts.append("</ul></details>")

    parts.append("</body></html>")
    return "\n".join(parts) + "\n"


def write_html(inputs: ReportInputs, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_html(inputs), encoding="utf-8")


def write_report(
    inputs: ReportInputs,
    out_dir: Path,
) -> dict[str, Path]:
    """Write both JSON and HTML. Returns the paths written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "causal_report.json"
    html_path = out_dir / "causal_report.html"
    write_json(build_json(inputs), json_path)
    write_html(inputs, html_path)
    return {"json": json_path, "html": html_path}
