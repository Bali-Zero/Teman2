"""kg-propose CLI — Zero's interface for managing KG proposals.

# Organo: graph-engine/curiosity/cli → consuma kg_proposals → produce kg_nodes/kg_edges (via apply)

Commands:
  kg-propose list [--domain X] [--status pending]
  kg-propose show <proposal_id>
  kg-propose apply <proposal_id>
  kg-propose reject <proposal_id> [--reason "..."]
  kg-propose stats

SYMBIOSIS Legge 5: Zero come ultima istanza. Apply requires explicit approval.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

from nuzantara_graph.curiosity.proposals import KGProposalStore

logger = logging.getLogger(__name__)

# Audit log path
AUDIT_LOG_PATH = os.path.expanduser("~/logs/kg_proposals_audit.jsonl")


def _get_database_url() -> str:
    """Resolve database URL from environment."""
    return os.environ.get(
        "DATABASE_URL",
        os.environ.get(
            "NUZANTARA_DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5432/nuzantara_rag",
        ),
    )


def _write_audit(action: str, proposal_id: str, details: dict[str, Any]) -> None:
    """Append audit entry to JSONL log."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "proposal_id": proposal_id,
        "user": os.environ.get("USER", "unknown"),
        **details,
    }
    try:
        os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)
        with open(AUDIT_LOG_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as e:
        logger.warning("audit write failed: %s", e)


def _format_proposal(p: dict[str, Any], verbose: bool = False) -> str:
    """Format a proposal for display."""
    pid = p.get("proposal_id", "?")[:12]
    domain = p.get("domain", "?")
    ptype = p.get("proposal_type", "?")
    score = p.get("self_rag_score", 0.0)
    status = p.get("status", "?")
    tier = p.get("tier", "?")
    created = str(p.get("created_at", ""))[:16]

    label = p.get("node_label", "") or p.get("relationship_type", "") or ""
    label_str = f" — {label[:50]}" if label else ""

    line = f"  {pid}  {domain:<12} {ptype:<8} {score:.2f}  {status:<12} {tier:<15} {created}{label_str}"

    if verbose:
        evidence = p.get("evidence_sources", [])
        if isinstance(evidence, str):
            evidence = json.loads(evidence)
        if evidence:
            line += f"\n    Evidence: {len(evidence)} sources"
            for e in evidence[:3]:
                src_type = e.get("source_type", "?")
                conf = e.get("confidence", 0.0)
                line += f"\n      [{src_type}] conf={conf:.2f}: {str(e.get('content', ''))[:80]}..."

        metadata = p.get("metadata", {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        if metadata.get("grade_reason"):
            line += f"\n    Grade: {metadata['grade_reason']}"

    return line


async def cmd_list(args: argparse.Namespace) -> None:
    """List proposals."""
    store = KGProposalStore(database_url=_get_database_url())
    try:
        proposals = await store.list_proposals(
            domain=args.domain,
            status=args.status,
            limit=args.limit,
        )

        if not proposals:
            print("No proposals found.")
            return

        print(f"  {'ID':<14} {'Domain':<12} {'Type':<8} {'Score':>5}  {'Status':<12} {'Tier':<15} Created")
        print("  " + "─" * 100)
        for p in proposals:
            print(_format_proposal(p))

        print(f"\n  Total: {len(proposals)} proposals")

    finally:
        await store.close()


async def cmd_show(args: argparse.Namespace) -> None:
    """Show a single proposal with details."""
    store = KGProposalStore(database_url=_get_database_url())
    try:
        p = await store.get_proposal(args.proposal_id)
        if not p:
            print(f"Proposal not found: {args.proposal_id}")
            return

        print(_format_proposal(p, verbose=True))

        # Show raw proposal data
        print("\n  Raw data:")
        for key, val in p.items():
            if key in ("id",):
                continue
            if isinstance(val, (dict, list)):
                val_str = json.dumps(val, indent=2, default=str)
            else:
                val_str = str(val)
            print(f"    {key}: {val_str[:200]}")

    finally:
        await store.close()


async def cmd_apply(args: argparse.Namespace) -> None:
    """Apply an approved proposal to kg_nodes/kg_edges."""
    store = KGProposalStore(database_url=_get_database_url())
    try:
        # First approve
        approved_by = os.environ.get("USER", "zero")
        approved = await store.approve(args.proposal_id, approved_by=approved_by)

        if not approved:
            # Maybe already approved?
            p = await store.get_proposal(args.proposal_id)
            if not p:
                print(f"Proposal not found: {args.proposal_id}")
                return
            if p.get("status") != "approved":
                print(f"Cannot apply: proposal status is '{p.get('status')}' (must be pending or approved)")
                return

        # Apply
        applied = await store.apply_approved(args.proposal_id)

        if applied:
            _write_audit("apply", args.proposal_id, {"approved_by": approved_by})
            print(f"Applied proposal {args.proposal_id[:12]}")
        else:
            print(f"Failed to apply proposal {args.proposal_id[:12]}")

    finally:
        await store.close()


async def cmd_reject(args: argparse.Namespace) -> None:
    """Reject a proposal."""
    store = KGProposalStore(database_url=_get_database_url())
    try:
        rejected = await store.reject(args.proposal_id, reason=args.reason or "")

        if rejected:
            _write_audit("reject", args.proposal_id, {"reason": args.reason or ""})
            print(f"Rejected proposal {args.proposal_id[:12]}")
        else:
            print(f"Cannot reject: proposal not found or not pending")

    finally:
        await store.close()


async def cmd_stats(args: argparse.Namespace) -> None:
    """Show proposal statistics."""
    store = KGProposalStore(database_url=_get_database_url())
    try:
        s = await store.stats()

        print("  KG Proposals Statistics")
        print("  " + "─" * 40)

        counts = s.get("status_counts", {})
        print(f"  Total proposals: {s.get('total', 0)}")
        for status in ["pending", "approved", "rejected", "applied", "auto_expired"]:
            cnt = counts.get(status, 0)
            if cnt > 0:
                print(f"    {status:<16} {cnt}")

        pending_domain = s.get("pending_by_domain", {})
        if pending_domain:
            print("\n  Pending by domain:")
            for domain, cnt in sorted(pending_domain.items(), key=lambda x: -x[1]):
                print(f"    {domain:<16} {cnt}")

        print(f"\n  KG density:")
        print(f"    Nodes: {s.get('node_count', 0):,}")
        print(f"    Edges: {s.get('edge_count', 0):,}")
        print(f"    Ontological density: {s.get('ontological_density', 0):.3f}")

    finally:
        await store.close()


def main() -> None:
    """CLI entrypoint for kg-propose."""
    parser = argparse.ArgumentParser(
        prog="kg-propose",
        description="Manage KG proposals from Curiosity Loop",
    )
    sub = parser.add_subparsers(dest="command")

    # list
    p_list = sub.add_parser("list", help="List proposals")
    p_list.add_argument("--domain", default=None, help="Filter by domain")
    p_list.add_argument("--status", default=None, help="Filter by status")
    p_list.add_argument("--limit", type=int, default=50, help="Max results")

    # show
    p_show = sub.add_parser("show", help="Show proposal details")
    p_show.add_argument("proposal_id", help="Proposal ID")

    # apply
    p_apply = sub.add_parser("apply", help="Approve and apply proposal to KG")
    p_apply.add_argument("proposal_id", help="Proposal ID")

    # reject
    p_reject = sub.add_parser("reject", help="Reject a proposal")
    p_reject.add_argument("proposal_id", help="Proposal ID")
    p_reject.add_argument("--reason", default="", help="Rejection reason")

    # stats
    sub.add_parser("stats", help="Show proposal statistics")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    cmd_map = {
        "list": cmd_list,
        "show": cmd_show,
        "apply": cmd_apply,
        "reject": cmd_reject,
        "stats": cmd_stats,
    }

    asyncio.run(cmd_map[args.command](args))


if __name__ == "__main__":
    main()
