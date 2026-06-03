"""Scale test: load N of one team member's loadable chats into ONE NB and prove
no cross-source contamination.

This closes two open risks from the design:
  - v6 blocker "one curated chat fools you": here we load N real chats at once.
  - spec §8 incognita #3 "cross-source contamination": with N files in one NB,
    NLM could cite verbatim from the WRONG chat. We query each source with an
    explicit --source-ids and assert every citation came from THAT source_id.

Per-source recap also re-uses the classifier so only CLIENT/PROSPECT chats are
loaded (team/group/multi-client excluded), exactly as v1 production would.

Usage:
  PYTHONPATH=. apps/backend-rag/.venv/bin/python -m scripts.wa_corpus.multi_chat_pilot \\
      --email surya@balizero.com --team-phone +628133946856 \\
      --nb <NB_ID> --limit 10
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import psycopg2

from scripts.wa_corpus import db
from scripts.wa_corpus.classifier import CounterpartClassifier
from scripts.wa_corpus.config import DB_DSN
from scripts.wa_corpus.prompt_master import recap_is_valid
from scripts.wa_corpus.query_runner import QueryRunner, parse_query_result, _nlm
from scripts.wa_corpus.renderer import ChatDocRenderer, render_markdown


def select_loadable_counterparts(conn, email: str, team_phone: str, limit: int):
    """Return up to `limit` loadable (CLIENT/PROSPECT) counterparts for a member."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT counterpart_phone, COUNT(*) n
        FROM whatsapp_message_context
        WHERE chat_type='direct' AND team_member_email=%s
          AND counterpart_phone IS NOT NULL
        GROUP BY counterpart_phone
        ORDER BY n DESC
        """,
        (email,),
    )
    rows = cur.fetchall()
    clf = CounterpartClassifier()
    selected = []
    for cp, n in rows:
        ct = db.get_contact_type(conn, cp)
        nn = db.count_distinct_names(conn, team_phone, cp)
        v = clf.classify(
            contact_type=ct,
            n_msgs=n,
            n_distinct_names=nn,
            chat_type="direct",
            is_team_member=db.is_team_member(conn, cp),
            in_crm=db.is_in_crm(conn, cp),
        )
        if v.loadable:
            selected.append((cp, n, v.verdict.value))
        if len(selected) >= limit:
            break
    return selected


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True, help="team_member_email, e.g. surya@balizero.com")
    ap.add_argument("--team-phone", required=True, help="member's outbound line for name counting")
    ap.add_argument("--nb", required=True, help="target NB id (profile zero)")
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()

    conn = psycopg2.connect(DB_DSN)
    chosen = select_loadable_counterparts(conn, args.email, args.team_phone, args.limit)
    print(f"[multi] selected {len(chosen)} loadable counterparts:")
    for cp, n, verdict in chosen:
        print(f"  {cp:18s} n={n:4d} {verdict}")
    if len(chosen) < 2:
        print("[multi] need >=2 loadable chats for a scale test")
        return 2

    renderer = ChatDocRenderer()
    qr = QueryRunner()
    stamp = f"{datetime.now(timezone.utc):%Y%m%d-%H%M%S}"

    # Stage 1: render + add all sources to the SAME NB.
    docs = []  # (counterpart, file_id, source_id, doc_name)
    for cp, n, _verdict in chosen:
        lines = db.fetch_chat(conn, args.team_phone, cp)
        md = render_markdown(args.team_phone, cp, lines)
        name = f"WA-MULTI-{cp}-{stamp}"
        file_id = renderer.create_doc(name, md)
        source_id = qr.ensure_source(args.nb, file_id, title=name)
        docs.append((cp, file_id, source_id, name))
        print(f"[multi] loaded {cp} -> source {source_id}")

    # Stage 2: sync all (explicit, F2) then per-source recap + contamination check.
    all_source_ids = ",".join(d[2] for d in docs)
    _nlm(["source", "sync", args.nb, "--source-ids", all_source_ids, "-y"])
    print(f"[multi] synced {len(docs)} sources")

    results = []
    contamination = 0
    for cp, file_id, source_id, name in docs:
        out = _nlm(
            ["notebook", "query", args.nb,
             "What is this client's current status? Quote exact text.",
             "--source-ids", source_id, "--json", "-t", "150"]
        )
        # Inspect raw references to verify every citation came from THIS source.
        data = json.loads(out)
        value = data.get("value", data)
        refs = value.get("references", []) or []
        foreign = [r for r in refs if r.get("source_id") and r["source_id"] != source_id]
        recap = parse_query_result(out)
        leaked = len(foreign)
        contamination += leaked
        status = "CLEAN" if leaked == 0 else f"LEAK x{leaked}"
        print(
            f"[multi] {cp}: citations={len(recap.cited_texts)} "
            f"valid_struct={recap_is_valid(recap.answer)} cross-source={status}"
        )
        results.append(
            {
                "counterpart": cp,
                "source_id": source_id,
                "citations": len(recap.cited_texts),
                "foreign_citations": leaked,
            }
        )

    print("=" * 60)
    print(f"[multi] {len(docs)} chats in one NB, total cross-source leaks: {contamination}")
    if contamination == 0:
        print("[multi] PASS ✅ — no cross-source contamination at scale")
        return 0
    print("[multi] FAIL ❌ — citations leaked across chats; need stricter source scoping")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
