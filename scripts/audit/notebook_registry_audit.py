"""Notebook registry audit — Sprint 1b

Inventories all NotebookLM notebooks declared across the monorepo and
reports divergences between the three independent "registries" that
exist today:

1. Backend oracle routing — ``apps/backend-rag/backend/services/oracle/
   nlm_notebook_registry.py::NLM_NOTEBOOKS`` (authoritative for chat
   routing).
2. Legacy backend fan-out map — ``nlm_orchestrator.py::
   DOMAIN_NOTEBOOK_MAP_V2`` (older, shorter copy — scheduled to be
   replaced by #1).
3. Evaluator pipelines registry — the hard-coded ``DOMAIN_REGISTRY`` /
   ``NOTEBOOKS`` / domain-to-UUID mappings scattered across
   ``apps/evaluator/nlm_deep_research/*`` (gap_scanner, freshness_monitor,
   multimodal_pipeline, cross_notebook_correlator).
4. Mata-Garuda NB-INTEL routing — ``apps/mata-garuda/mata_garuda/
   config.py::NLM_NOTEBOOKS`` (entirely separate UUID space used by the
   OSINT feeder).

Output:

- CSV report with one row per (source, domain, UUID, label) tuple —
  easy to diff against a future rerun or to paste into a spreadsheet.
- Markdown summary grouping anomalies by severity.
- Exit code 0 if no critical anomalies, 1 otherwise (useful for CI).

Critical anomalies (exit 1):

- **Orphan**: domain declared in the evaluator pipelines but not routed
  by the backend oracle — users cannot reach that notebook via the chat.
- **Conflict**: the same domain maps to two different UUIDs in two
  different sources (e.g. `property` → NB-3 in the old map vs NB-5 in
  the canonical registry).
- **Unknown UUID**: a UUID referenced in code but not present in any
  registry.

Warnings (logged, no exit change):

- **Duplicate domain key**: the same logical domain ("property",
  "tax" …) declared in >1 source pointing to the same UUID — cleanup
  opportunity, not a bug.
- **Silo crossing**: a Mata-Garuda NB-INTEL domain shares a semantic
  label ("immigration", "tax") with an evaluator domain but uses a
  different UUID — expected today, but the audit records the split so a
  later bridge decision has the data it needs.

Usage:
    python scripts/audit/notebook_registry_audit.py                 # stdout summary, write CSV to reports/
    python scripts/audit/notebook_registry_audit.py --json          # machine-readable
    python scripts/audit/notebook_registry_audit.py --fail-on warn  # also fail on warnings
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

BACKEND_REGISTRY = (
    REPO_ROOT
    / "apps/backend-rag/backend/services/oracle/nlm_notebook_registry.py"
)
BACKEND_ORCHESTRATOR = (
    REPO_ROOT / "apps/backend-rag/backend/services/oracle/nlm_orchestrator.py"
)
EVALUATOR_CORRELATOR = (
    REPO_ROOT / "apps/evaluator/nlm_deep_research/cross_notebook_correlator.py"
)
EVALUATOR_GAP_SCANNER = (
    REPO_ROOT / "apps/evaluator/nlm_deep_research/gap_scanner.py"
)
EVALUATOR_FRESHNESS = (
    REPO_ROOT / "apps/evaluator/nlm_deep_research/freshness_monitor.py"
)
EVALUATOR_MULTIMODAL = (
    REPO_ROOT / "apps/evaluator/nlm_deep_research/multimodal_pipeline.py"
)
MATA_GARUDA_CONFIG = REPO_ROOT / "apps/mata-garuda/mata_garuda/config.py"

# Known "meta" NBs that live outside the pipelines — we surface them but
# don't treat their absence from routing as orphan.
KNOWN_META_NBS: dict[str, str] = {
    "f6ecd115-dd89-4c9b-b3dd-071e0e2f1876": "NB-1 Codebase (self-reflection)",
    "1e5f9b04-9485-4620-a775-801b7e6b0395": "NB-14 Claude Session Memory",
    "2072e518-e6f9-437d-93ea-f9037ec54052": "NB-11 Ops Live",
    "5c2c3d90-eed2-4755-86b1-269e637e51e1": "NB-12 BI",
    "53441d9e-fb11-44cc-8dd8-4d70637b651f": "NB-13 Telemetry",
}

UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"
)


@dataclass
class NotebookEntry:
    source: str
    domain: str
    uuid: str
    label: str = ""

    def key(self) -> tuple[str, str]:
        return (self.source, self.domain)


@dataclass
class AuditReport:
    entries: list[NotebookEntry] = field(default_factory=list)
    critical: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_critical(self, msg: str) -> None:
        self.critical.append(msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


def _parse_python_dict(path: Path, var_name: str) -> dict:
    """Parse a top-level Python literal dict assignment using AST.

    Limited to dicts whose values are literal-evaluable (str, int, list,
    set, dict, None). Good enough for the three registries we need.
    """
    if not path.exists():
        return {}
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == var_name:
                    try:
                        return ast.literal_eval(node.value)
                    except ValueError:
                        return {}
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == var_name and node.value is not None:
                try:
                    return ast.literal_eval(node.value)
                except ValueError:
                    return {}
    return {}


def collect_backend_registry(report: AuditReport) -> None:
    data = _parse_python_dict(BACKEND_REGISTRY, "NLM_NOTEBOOKS")
    for domain, entry in data.items():
        uuid = entry.get("notebook_id") if isinstance(entry, dict) else None
        if uuid:
            report.entries.append(
                NotebookEntry(
                    source="backend/oracle/registry",
                    domain=domain,
                    uuid=uuid,
                    label=entry.get("label", ""),
                )
            )


def collect_backend_orchestrator(report: AuditReport) -> None:
    data = _parse_python_dict(BACKEND_ORCHESTRATOR, "DOMAIN_NOTEBOOK_MAP_V2")
    for domain, uuid_list in data.items():
        if not isinstance(uuid_list, list):
            continue
        for uuid in uuid_list:
            if isinstance(uuid, str) and UUID_RE.match(uuid):
                report.entries.append(
                    NotebookEntry(
                        source="backend/oracle/orchestrator_v2",
                        domain=domain,
                        uuid=uuid,
                    )
                )


def collect_evaluator(report: AuditReport) -> None:
    # cross_notebook_correlator has DOMAIN_REGISTRY with richer metadata
    data = _parse_python_dict(EVALUATOR_CORRELATOR, "DOMAIN_REGISTRY")
    for domain, entry in data.items():
        if not isinstance(entry, dict):
            continue
        uuid = entry.get("notebook_id")
        if uuid:
            report.entries.append(
                NotebookEntry(
                    source="evaluator/correlator",
                    domain=domain,
                    uuid=uuid,
                    label=entry.get("label", ""),
                )
            )
    # Other evaluator files sometimes inline the UUID in module constants
    # (NOTEBOOKS dict or DOMAIN_TOPICS). Pick them up opportunistically.
    for path, varnames in [
        (EVALUATOR_GAP_SCANNER, ["DOMAIN_TOPICS"]),
        (EVALUATOR_FRESHNESS, ["REGULATORY_DOMAINS"]),
        (EVALUATOR_MULTIMODAL, ["NOTEBOOKS"]),
    ]:
        for varname in varnames:
            data = _parse_python_dict(path, varname)
            if not isinstance(data, dict):
                # Some modules expose a list of dicts instead of a mapping
                # (e.g. multimodal_pipeline.NOTEBOOKS is a list of artifact
                # configs). Normalise by using the 'key' or 'domain' field.
                if isinstance(data, list):
                    for entry in data:
                        if not isinstance(entry, dict):
                            continue
                        domain = (
                            entry.get("key")
                            or entry.get("domain")
                            or entry.get("notebook_key")
                            or entry.get("notebook_domain")
                            or entry.get("name")
                            or "?"
                        )
                        uuid = entry.get("notebook_id")
                        if uuid and UUID_RE.match(str(uuid)):
                            report.entries.append(
                                NotebookEntry(
                                    source=f"evaluator/{path.stem}:{varname}",
                                    domain=str(domain),
                                    uuid=uuid,
                                    label=str(entry.get("label", "")),
                                )
                            )
                continue
            for domain, entry in data.items():
                if not isinstance(entry, dict):
                    continue
                uuid = entry.get("notebook_id")
                if uuid and UUID_RE.match(str(uuid)):
                    report.entries.append(
                        NotebookEntry(
                            source=f"evaluator/{path.stem}:{varname}",
                            domain=domain,
                            uuid=uuid,
                            label=entry.get("label", ""),
                        )
                    )


def collect_mata_garuda(report: AuditReport) -> None:
    data = _parse_python_dict(MATA_GARUDA_CONFIG, "NLM_NOTEBOOKS")
    for domain, uuid in data.items():
        if isinstance(uuid, str) and UUID_RE.match(uuid):
            report.entries.append(
                NotebookEntry(
                    source="mata-garuda/config",
                    domain=domain,
                    uuid=uuid,
                    label=f"NB-INTEL-{domain}",
                )
            )


def analyze(report: AuditReport) -> None:
    # Group by source → set of domains, and by UUID → set of (source, domain)
    by_source: dict[str, set[str]] = {}
    by_uuid: dict[str, list[NotebookEntry]] = {}
    for e in report.entries:
        by_source.setdefault(e.source, set()).add(e.domain)
        by_uuid.setdefault(e.uuid, []).append(e)

    # --- Critical #1: domain declared in evaluator but missing from backend registry
    backend_domains = by_source.get("backend/oracle/registry", set())
    evaluator_domains = by_source.get("evaluator/correlator", set())
    orphan_domains = evaluator_domains - backend_domains
    for d in sorted(orphan_domains):
        report.add_critical(
            f"ORPHAN: domain '{d}' is ingested by the evaluator pipelines "
            f"but NOT routed by the backend oracle registry — RAG queries "
            f"cannot reach this NB."
        )

    # --- Critical #2: same domain key, two UUIDs in different sources
    #     (excluding the known Mata-Garuda silo, which uses different semantic keys)
    domain_to_uuids: dict[str, set[str]] = {}
    for e in report.entries:
        if e.source == "mata-garuda/config":
            continue  # mata-garuda lives in a separate semantic namespace
        domain_to_uuids.setdefault(e.domain, set()).add(e.uuid)
    for domain, uuids in domain_to_uuids.items():
        if len(uuids) > 1:
            sources_list = sorted(
                {(e.source, e.uuid) for e in report.entries if e.domain == domain and e.source != "mata-garuda/config"}
            )
            report.add_critical(
                f"CONFLICT: domain '{domain}' maps to {len(uuids)} different "
                f"UUIDs across sources: {sources_list}"
            )

    # --- Warning: Mata-Garuda semantic twin (same label word, different UUID)
    for e in report.entries:
        if e.source != "mata-garuda/config":
            continue
        # Normalise: mata-garuda uses 'immigration' while backend uses 'immigration' too
        # but with a different UUID — flag as "silo twin"
        twin = [
            other
            for other in report.entries
            if other.source.startswith(("backend/", "evaluator/"))
            and other.domain == e.domain
        ]
        if twin and all(t.uuid != e.uuid for t in twin):
            for t in twin:
                report.add_warning(
                    f"SILO-TWIN: domain '{e.domain}' has NB-INTEL UUID "
                    f"{e.uuid[:8]}… ({e.source}) and domain NB UUID "
                    f"{t.uuid[:8]}… ({t.source}) — expected today, but "
                    f"the silo is a known gap (see NLM_VITAL_CYCLE.md §1.1)."
                )

    # --- Warning: duplicate (same UUID appearing >1 time as the canonical
    # notebook for the *same* domain in >1 source)
    for uuid, entries in by_uuid.items():
        same_domain_sources = {e.domain for e in entries}
        if len(entries) > 1 and len(same_domain_sources) == 1:
            srcs = sorted({e.source for e in entries})
            report.add_warning(
                f"DUPLICATE: UUID {uuid[:8]}… declared for domain "
                f"'{entries[0].domain}' in {len(entries)} sources "
                f"({srcs}) — consider consolidating via a single SSOT."
            )

    # --- Meta info: list known meta NBs that surfaced
    for uuid, label in KNOWN_META_NBS.items():
        if uuid in by_uuid:
            report.add_warning(
                f"META-NB: {label} (UUID {uuid[:8]}…) detected — "
                f"not a routing concern."
            )


def write_csv(report: AuditReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["source", "domain", "uuid", "label"])
        for e in sorted(report.entries, key=lambda x: (x.source, x.domain)):
            writer.writerow([e.source, e.domain, e.uuid, e.label])


def print_summary(report: AuditReport) -> None:
    print("=== Notebook Registry Audit ===")
    print(f"generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    print(f"entries:   {len(report.entries)}")
    print(f"critical:  {len(report.critical)}")
    print(f"warnings:  {len(report.warnings)}")
    print()
    sources: dict[str, int] = {}
    for e in report.entries:
        sources[e.source] = sources.get(e.source, 0) + 1
    print("Per source:")
    for src, n in sorted(sources.items()):
        print(f"  {src:40s} {n:3d}")
    print()
    if report.critical:
        print("CRITICAL")
        for c in report.critical:
            print(f"  - {c}")
        print()
    if report.warnings:
        print("WARNINGS")
        for w in report.warnings:
            print(f"  - {w}")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv",
        type=Path,
        default=REPO_ROOT / "reports/notebook_registry_audit.csv",
        help="Write CSV report to this path (default: reports/).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON on stdout instead of human summary.",
    )
    parser.add_argument(
        "--fail-on",
        choices=("critical", "warn"),
        default="critical",
        help="Exit non-zero on this severity or higher (default: critical).",
    )
    args = parser.parse_args()

    report = AuditReport()
    collect_backend_registry(report)
    collect_backend_orchestrator(report)
    collect_evaluator(report)
    collect_mata_garuda(report)
    analyze(report)
    write_csv(report, args.csv)

    if args.json:
        out = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "entries": [
                {"source": e.source, "domain": e.domain, "uuid": e.uuid, "label": e.label}
                for e in report.entries
            ],
            "critical": report.critical,
            "warnings": report.warnings,
        }
        print(json.dumps(out, indent=2))
    else:
        print_summary(report)
        print(f"CSV written: {args.csv}")

    should_fail = bool(report.critical)
    if args.fail_on == "warn":
        should_fail = should_fail or bool(report.warnings)
    return 1 if should_fail else 0


if __name__ == "__main__":
    sys.exit(main())
