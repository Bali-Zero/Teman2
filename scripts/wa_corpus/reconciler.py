"""Reconciler (I/O) — executes the agentic flow for one team member.

For each direct counterpart of the member it computes the desired state, asks
reconcile.decide_action what to do, and performs it (CREATE/RENAME/UPDATE/SKIP/
ARCHIVE), persisting the result in wa_corpus_docs so the next pass is idempotent.

Recap is written to clients.strategic_recap (source=wa_auto) ONLY when the
counterpart is in the CRM AND the recap has verbatim citations (the query-runner
retries to get them; if still empty the recap is left unwritten and counted as
"unverified" in the digest — anti-hallucination gate).

Pure decision logic lives in reconcile.py; this module is the side-effecting
executor. It is driven per member so the cron can fan out one NB per member.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import psycopg2

from scripts.wa_corpus import db
from scripts.wa_corpus.classifier import CounterpartClassifier
from scripts.wa_corpus.config import DB_DSN
from scripts.wa_corpus.query_runner import QueryRunner
from scripts.wa_corpus.reconcile import (
    Action,
    DesiredState,
    RecordedState,
    decide_action,
)
from scripts.wa_corpus.renderer import ChatDocRenderer, doc_title, render_markdown


@dataclass
class Digest:
    member_email: str
    created: int = 0
    renamed: int = 0
    updated: int = 0
    skipped: int = 0
    archived: int = 0
    recap_written: int = 0
    unverified: int = 0
    errors: list[str] = field(default_factory=list)

    def line(self) -> str:
        return (
            f"{self.member_email}: create={self.created} rename={self.renamed} "
            f"update={self.updated} skip={self.skipped} archive={self.archived} "
            f"recap_written={self.recap_written} unverified={self.unverified} "
            f"errors={len(self.errors)}"
        )


class Reconciler:
    def __init__(self, conn, nb_id: str, *, dry_run: bool = False) -> None:
        self.conn = conn
        self.nb_id = nb_id
        self.dry_run = dry_run
        self.clf = CounterpartClassifier()
        self.renderer = None if dry_run else ChatDocRenderer()
        self.qr = None if dry_run else QueryRunner()
        db.ensure_state_table(conn)

    # --- desired-state computation (reads DB only) ------------------------
    def _desired(self, team_phone: str, counterpart_phone: str):
        ct = db.get_contact_type(self.conn, counterpart_phone)
        lines = db.fetch_chat(self.conn, team_phone, counterpart_phone)
        n_names = db.count_distinct_names(self.conn, team_phone, counterpart_phone)
        verdict = self.clf.classify(
            contact_type=ct,
            n_msgs=len(lines),
            n_distinct_names=n_names,
            chat_type="direct",
            is_team_member=db.is_team_member(self.conn, counterpart_phone),
            in_crm=db.is_in_crm(self.conn, counterpart_phone),
        )
        title = doc_title(counterpart_phone, db.crm_name(self.conn, counterpart_phone))
        latest = db.latest_message_at(self.conn, team_phone, counterpart_phone)
        return verdict, DesiredState(verdict.loadable, title, latest), lines

    def reconcile_member(self, team_email: str, team_phone: str, limit: int | None = None) -> Digest:
        dg = Digest(member_email=team_email)
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT counterpart_phone FROM whatsapp_message_context
            WHERE chat_type='direct' AND team_member_email=%s AND counterpart_phone IS NOT NULL
            GROUP BY counterpart_phone ORDER BY COUNT(*) DESC
            """,
            (team_email,),
        )
        counterparts = [r[0] for r in cur.fetchall()]
        if limit:
            counterparts = counterparts[:limit]

        for cp in counterparts:
            try:
                self._reconcile_one(team_email, team_phone, cp, dg)
            except Exception as exc:  # noqa: BLE001 — keep going, record the error
                dg.errors.append(f"{cp}: {exc}")
        return dg

    def _reconcile_one(self, team_email, team_phone, cp, dg: Digest) -> None:
        verdict, desired, lines = self._desired(team_phone, cp)
        rec_row = db.get_doc_state(self.conn, team_email, cp)
        recorded = (
            RecordedState(
                file_id=rec_row["file_id"],
                source_id=rec_row["source_id"],
                last_title=rec_row["last_title"],
                last_msg_at=rec_row["last_msg_at"],
            )
            if rec_row
            else None
        )
        decision = decide_action(desired, recorded)

        if decision.action is Action.SKIP:
            dg.skipped += 1
            return
        if self.dry_run:
            _count(dg, decision.action)
            return

        if decision.action is Action.CREATE:
            self._do_create(team_email, team_phone, cp, verdict, desired, lines, dg)
        elif decision.action is Action.RENAME:
            self.renderer.rename_doc(recorded.file_id, decision.new_title)
            self._persist(team_email, cp, rec_row, title=decision.new_title,
                          verdict=verdict.verdict.value, msg_at=desired.latest_msg_at)
            dg.renamed += 1
        elif decision.action is Action.UPDATE:
            md = render_markdown(team_phone, cp, lines)
            self.renderer.update_doc(recorded.file_id, md)
            self.qr.sync_source(self.nb_id, recorded.source_id)
            self._recap_and_persist(team_email, cp, rec_row, recorded.source_id,
                                    desired, verdict, dg)
            dg.updated += 1
        elif decision.action is Action.ARCHIVE:
            self.renderer.rename_doc(recorded.file_id, decision.new_title)
            self._persist(team_email, cp, rec_row, title=decision.new_title,
                          verdict=verdict.verdict.value, msg_at=desired.latest_msg_at)
            dg.archived += 1

    def _do_create(self, team_email, team_phone, cp, verdict, desired, lines, dg: Digest) -> None:
        md = render_markdown(team_phone, cp, lines)
        file_id = self.renderer.create_doc(desired.title, md)
        source_id = self.qr.ensure_source(self.nb_id, file_id, title=desired.title)
        self.qr.sync_source(self.nb_id, source_id)
        db.upsert_doc_state(
            self.conn, team_email=team_email, counterpart_phone=cp, nb_id=self.nb_id,
            file_id=file_id, source_id=source_id, last_title=desired.title,
            last_verdict=verdict.verdict.value, last_msg_at=desired.latest_msg_at,
            last_recap_at=None,
        )
        dg.created += 1
        # produce the first recap right away
        self._recap_and_persist(team_email, cp, db.get_doc_state(self.conn, team_email, cp),
                                source_id, desired, verdict, dg)

    def _recap_and_persist(self, team_email, cp, rec_row, source_id, desired, verdict, dg: Digest) -> None:
        recap = self.qr.run_prompt_master(self.nb_id, source_id)
        recap_at = None
        if recap.has_citations:
            client_id = db.client_id_for_phone(self.conn, cp)
            if client_id is not None:  # only write CRM for actual clients
                db.write_strategic_recap(self.conn, client_id, recap.answer)
                dg.recap_written += 1
                recap_at = datetime.now(timezone.utc)
        else:
            dg.unverified += 1
        self._persist(team_email, cp, rec_row, title=desired.title,
                      verdict=verdict.verdict.value, msg_at=desired.latest_msg_at,
                      recap_at=recap_at)

    def _persist(self, team_email, cp, rec_row, *, title, verdict, msg_at, recap_at=None) -> None:
        db.upsert_doc_state(
            self.conn, team_email=team_email, counterpart_phone=cp,
            nb_id=rec_row["nb_id"], file_id=rec_row["file_id"],
            source_id=rec_row["source_id"], last_title=title, last_verdict=verdict,
            last_msg_at=msg_at, last_recap_at=recap_at,
        )


def _count(dg: Digest, action: Action) -> None:
    setattr(dg, {
        Action.CREATE: "created", Action.RENAME: "renamed",
        Action.UPDATE: "updated", Action.ARCHIVE: "archived",
    }[action], getattr(dg, {
        Action.CREATE: "created", Action.RENAME: "renamed",
        Action.UPDATE: "updated", Action.ARCHIVE: "archived",
    }[action]) + 1)


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True)
    ap.add_argument("--team-phone", required=True)
    ap.add_argument("--nb", required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = psycopg2.connect(DB_DSN)
    rec = Reconciler(conn, args.nb, dry_run=args.dry_run)
    dg = rec.reconcile_member(args.email, args.team_phone, limit=args.limit)
    print(dg.line())
    for e in dg.errors:
        print("  ERROR", e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
