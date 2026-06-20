#!/usr/bin/env python3
"""kg-propose — operator CLI for the Curiosity Loop proposal queue.

The Curiosity Loop (gap_fill_autonomous.py) generates KG node/edge/property
proposals into the `kg_proposals` table in PROPOSE-ONLY mode — it never
auto-promotes to the live knowledge graph. Until this CLI existed there was no
operator path to consume that queue: proposals accumulated `pending` forever
(TAC 2026-06-19, superscar #11 "Anello di Chiusura Reciso" — the producer ran
green while the consumer was never wired). `curiosity_loop.sh` documents
`kg-propose apply <id>` as the approval path; this is that command.

It is a THIN wrapper around the existing, tested `KGProposalStore` methods
(`list_proposals` / `approve` / `apply_approved` / `reject`). No KG-mutation
logic lives here — `apply_approved` is the single sanctioned write path to
kg_nodes/kg_edges, and it already enforces the two-phase approve→apply gate
and an atomic, rolling-back transaction.

Usage:
    kg-propose list [--status pending] [--domain company] [--limit 50]
    kg-propose show <proposal_id>
    kg-propose approve <proposal_id> [--by <name>]
    kg-propose apply <proposal_id> --yes        # mutates the live KG
    kg-propose reject <proposal_id> [--reason "..."]
    kg-propose apply-all --status approved --yes  # batch-apply approved

`apply` / `apply-all` mutate production KG state and therefore REQUIRE an
explicit `--yes`. Without it they run as a dry-run that only reports what
would happen. This keeps the destructive boundary explicit per AUTONOMOUS_OPS.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

# graph-engine package lives outside backend; make it importable when run
# either from repo root or via an installed console-script.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_GRAPH_SRC = os.path.join(_REPO_ROOT, "apps", "graph-engine", "src")
if _GRAPH_SRC not in sys.path:
    sys.path.insert(0, _GRAPH_SRC)

from nuzantara_graph.curiosity.proposals import KGProposalStore  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("kg-propose")


def _get_database_url() -> str:
    """Resolve database URL — identical resolution to gap_fill_autonomous.py."""
    return os.environ.get(
        "DATABASE_URL",
        os.environ.get(
            "NUZANTARA_DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5432/nuzantara_rag",  # pragma: allowlist secret  # localhost dev default, not a production credential
        ),
    )


def _fmt_row(p: dict) -> str:
    """One-line summary of a proposal for the list view."""
    label = p.get("node_label") or p.get("relationship_type") or p.get("property_key") or "—"
    score = p.get("self_rag_score")
    score_s = f"{score:.2f}" if isinstance(score, (int, float)) else "  —"
    return (
        f"{str(p.get('proposal_id', ''))[:8]}  "
        f"{str(p.get('status', '')):9}  "
        f"{str(p.get('proposal_type', '')):9}  "
        f"{str(p.get('domain', '')):10}  "
        f"score={score_s}  {label}"
    )


async def cmd_list(store: KGProposalStore, args: argparse.Namespace) -> int:
    proposals = await store.list_proposals(
        status=args.status, domain=args.domain, limit=args.limit
    )
    if not proposals:
        logger.info("No proposals match (status=%s domain=%s).", args.status, args.domain)
        return 0
    logger.info("%d proposal(s):", len(proposals))
    for p in proposals:
        logger.info("  %s", _fmt_row(p))
    return 0


async def cmd_show(store: KGProposalStore, args: argparse.Namespace) -> int:
    p = await store.get_proposal(args.proposal_id)
    if not p:
        logger.error("Proposal %s not found.", args.proposal_id)
        return 1
    for k, v in p.items():
        logger.info("  %-22s %s", k, v)
    return 0


async def cmd_approve(store: KGProposalStore, args: argparse.Namespace) -> int:
    ok = await store.approve(args.proposal_id, approved_by=args.by)
    if ok:
        logger.info("Approved %s (by %s). Run `kg-propose apply %s --yes` to materialize.",
                    args.proposal_id[:8], args.by, args.proposal_id[:8])
        return 0
    logger.error("Approve failed for %s (not found or not in 'pending').", args.proposal_id)
    return 1


async def cmd_reject(store: KGProposalStore, args: argparse.Namespace) -> int:
    ok = await store.reject(args.proposal_id, reason=args.reason)
    logger.info("%s %s", "Rejected" if ok else "Reject failed for", args.proposal_id[:8])
    return 0 if ok else 1


async def cmd_apply(store: KGProposalStore, args: argparse.Namespace) -> int:
    p = await store.get_proposal(args.proposal_id)
    if not p:
        logger.error("Proposal %s not found.", args.proposal_id)
        return 1
    if p.get("status") != "approved":
        logger.error("Proposal %s is '%s', not 'approved'. Run `kg-propose approve` first.",
                     args.proposal_id[:8], p.get("status"))
        return 1
    if not args.yes:
        logger.info("DRY-RUN — would apply %s to the live KG:", args.proposal_id[:8])
        logger.info("  %s", _fmt_row(p))
        logger.info("Re-run with --yes to mutate production KG.")
        return 0
    ok = await store.apply_approved(args.proposal_id)
    logger.info("%s %s", "Applied" if ok else "Apply FAILED for", args.proposal_id[:8])
    return 0 if ok else 1


async def cmd_apply_all(store: KGProposalStore, args: argparse.Namespace) -> int:
    proposals = await store.list_proposals(status="approved", limit=args.limit)
    if not proposals:
        logger.info("No 'approved' proposals to apply.")
        return 0
    if not args.yes:
        logger.info("DRY-RUN — would apply %d approved proposal(s):", len(proposals))
        for p in proposals:
            logger.info("  %s", _fmt_row(p))
        logger.info("Re-run with --yes to mutate production KG.")
        return 0
    applied = 0
    for p in proposals:
        if await store.apply_approved(p["proposal_id"]):
            applied += 1
    logger.info("Applied %d/%d approved proposal(s).", applied, len(proposals))
    return 0 if applied == len(proposals) else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kg-propose", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="list proposals")
    p_list.add_argument("--status", default="pending")
    p_list.add_argument("--domain", default=None)
    p_list.add_argument("--limit", type=int, default=50)
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="show one proposal in full")
    p_show.add_argument("proposal_id")
    p_show.set_defaults(func=cmd_show)

    p_approve = sub.add_parser("approve", help="approve a pending proposal")
    p_approve.add_argument("proposal_id")
    p_approve.add_argument("--by", default="zero")
    p_approve.set_defaults(func=cmd_approve)

    p_reject = sub.add_parser("reject", help="reject a pending proposal")
    p_reject.add_argument("proposal_id")
    p_reject.add_argument("--reason", default="")
    p_reject.set_defaults(func=cmd_reject)

    p_apply = sub.add_parser("apply", help="apply an approved proposal to the live KG")
    p_apply.add_argument("proposal_id")
    p_apply.add_argument("--yes", action="store_true", help="confirm production KG mutation")
    p_apply.set_defaults(func=cmd_apply)

    p_apply_all = sub.add_parser("apply-all", help="apply all approved proposals")
    p_apply_all.add_argument("--limit", type=int, default=100)
    p_apply_all.add_argument("--yes", action="store_true", help="confirm production KG mutation")
    p_apply_all.set_defaults(func=cmd_apply_all)

    return parser


async def _amain(argv: list[str]) -> int:
    args = _build_parser().parse_args(argv)
    store = KGProposalStore(database_url=_get_database_url())
    try:
        return await args.func(store, args)
    finally:
        await store.close()


def main() -> None:
    sys.exit(asyncio.run(_amain(sys.argv[1:])))


if __name__ == "__main__":
    main()
