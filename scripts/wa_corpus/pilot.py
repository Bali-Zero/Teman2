"""One-shot pilot: pick a single CLIENT pair, build its Doc, query a recap.

Usage:
  PYTHONPATH=. apps/backend-rag/.venv/bin/python -m scripts.wa_corpus.pilot \\
      --team +628133946856 --counterpart +33614653019 --nb <NB_ID>
"""
from __future__ import annotations

import argparse

import psycopg2

from scripts.wa_corpus import db
from scripts.wa_corpus.classifier import CounterpartClassifier
from scripts.wa_corpus.config import DB_DSN
from scripts.wa_corpus.prompt_master import recap_is_valid
from scripts.wa_corpus.query_runner import QueryRunner
from scripts.wa_corpus.renderer import ChatDocRenderer, doc_title, render_markdown


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", required=True)
    ap.add_argument("--counterpart", required=True)
    ap.add_argument("--nb", required=True, help="target NB id (profile zero)")
    ap.add_argument(
        "--force",
        action="store_true",
        help="build even if not classified CLIENT (for diagnostics only)",
    )
    args = ap.parse_args()

    conn = psycopg2.connect(DB_DSN)
    ct = db.get_contact_type(conn, args.counterpart)
    lines = db.fetch_chat(conn, args.team, args.counterpart)
    n_names = db.count_distinct_names(conn, args.team, args.counterpart)

    verdict = CounterpartClassifier().classify(
        contact_type=ct,
        n_msgs=len(lines),
        n_distinct_names=n_names,
        chat_type="direct",
        is_team_member=db.is_team_member(conn, args.counterpart),
        in_crm=db.is_in_crm(conn, args.counterpart),
    )
    print(f"[pilot] classify -> {verdict.verdict.value}: {verdict.reason}")
    if not verdict.loadable and not args.force:
        print("[pilot] not a loadable client/prospect; refusing to build a recap.")
        return 2

    md = render_markdown(args.team, args.counterpart, lines)
    renderer = ChatDocRenderer()
    # OBLIGATORY naming: CRM name if a client, else the phone number.
    name = doc_title(args.counterpart, db.crm_name(conn, args.counterpart))
    file_id = renderer.create_doc(name, md)
    print(f"[pilot] doc '{name}' created + shared: {file_id}")

    qr = QueryRunner()
    source_id = qr.ensure_source(args.nb, file_id, title=name)
    qr.sync_source(args.nb, source_id)  # F2 explicit
    recap = qr.run_prompt_master(args.nb, source_id)

    print("=" * 60)
    print(recap.answer)
    print("=" * 60)
    print(
        f"[pilot] citations: {len(recap.cited_texts)} | "
        f"structure valid: {recap_is_valid(recap.answer)}"
    )
    if not recap.has_citations:
        print("[pilot] WARNING: recap has zero verbatim citations — do NOT trust.")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
