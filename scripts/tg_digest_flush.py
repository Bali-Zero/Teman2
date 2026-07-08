#!/usr/bin/env python3
"""tg_digest_flush.py — sends the ONE grouped digest for everything tg_notify spooled.

Runs 2×/day (08:00 + 20:00 WITA) via com.nuzantara.tg-digest-flush.plist on Pro
and Mini (M5 has no token by design — its spool relays P0s and keeps digest local).

Contracts:
  - Empty spool → exit 0, send nothing (organism_digest covers boot reporting).
    Healthy-silence is distinguishable from death via last_flush.json (self-probe,
    W84 rule: a receptor whose healthy output is silence must expose a probe).
  - Send failure → spool PRESERVED, exit 3 (fail-visible in launchd LastExitStatus).
  - Flushed lines archived to archive/YYYY-MM-DD.jsonl before truncation; the
    swap is rename-based so concurrent tg_notify appends are never lost.
  - Message ≤ 3500 chars; overflow collapses to "… e altri N eventi".

Usage:
  tg_digest_flush.py --now          # flush immediately
  tg_digest_flush.py --dry-run      # render to stdout, do not send/rotate
  tg_digest_flush.py --selftest
"""

from __future__ import annotations

import json
import os
import socket
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tg_notify import _spool_lock, resolve_credentials, send_telegram  # noqa: E402

MAX_CHARS = 3500


def _spool_dir() -> Path:
    return Path(os.environ.get("TG_SPOOL_DIR", str(Path.home() / ".organism" / "tg_spool")))


def _read_jsonl(path: Path) -> list[dict]:
    records = []
    for line in path.read_text(errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except ValueError:
            records.append({"ts": 0, "tier": "digest", "source": "corrupt-line", "text": line[:120]})
    return records


def _rotate_pending(spool: Path) -> list[dict]:
    """Atomically claim the current pending spool; new appends go to a fresh file.

    Crash recovery: a previous run that died between claim and archive leaves a
    stale .flushing-* file — ADOPT its records first, never delete them unread.
    """
    records: list[dict] = []
    for stale in sorted(spool.glob(".flushing-*.jsonl")):
        records.extend(_read_jsonl(stale))

    pending = spool / "pending.jsonl"
    if pending.exists():
        claim = spool / f".flushing-{os.getpid()}.jsonl"
        try:
            pending.rename(claim)
        except OSError:
            return records
        records.extend(_read_jsonl(claim))
    return records


def _restore(spool: Path, records: list[dict]) -> None:
    """Send failed: put the claimed records back into the pending spool.

    O_APPEND, never rewrite-and-replace: a concurrent tg_notify append between
    a read and a replace would be silently lost. Digest order is irrelevant.
    """
    pending = spool / "pending.jsonl"
    fd = os.open(str(pending), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        for r in records:
            os.write(fd, (json.dumps(r, ensure_ascii=False) + "\n").encode())
    finally:
        os.close(fd)


def _archive(spool: Path, records: list[dict]) -> None:
    day = time.strftime("%Y-%m-%d")
    adir = spool / "archive"
    adir.mkdir(parents=True, exist_ok=True)
    with (adir / f"{day}.jsonl").open("a") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def _archive_log_only(spool: Path) -> int:
    """Rotate log-only.jsonl into the archive. MUST be called under the spool
    lock (read+unlink would otherwise drop a concurrent tg_notify append).
    Returns the number of lines archived."""
    logf = spool / "log-only.jsonl"
    if not logf.exists():
        return 0
    day = time.strftime("%Y-%m-%d")
    adir = spool / "archive"
    adir.mkdir(parents=True, exist_ok=True)
    lines = [ln for ln in logf.read_text(errors="replace").splitlines() if ln.strip()]
    with (adir / f"{day}.log-only.jsonl").open("a") as fh:
        for ln in lines:
            fh.write(ln + "\n")
    logf.unlink()
    return len(lines)


def render(records: list[dict], log_count: int, machine: str) -> str:
    state_path = _spool_dir() / "state.json"
    suppressed = 0
    try:
        state = json.loads(state_path.read_text())
        suppressed = sum(v.get("count", 1) - 1 for v in state.get("dedup", {}).values())
    except (OSError, ValueError):
        pass

    by_source: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_source[r.get("source", "unknown")].append(r)

    unsent_p0 = [r for r in records if r.get("p0_unsent") or r.get("p0_overflow")]
    hhmm = time.strftime("%H:%M")
    head = f"📮 Digest {machine} {hhmm} — {len(records)} eventi"
    if suppressed:
        head += f" · {suppressed} duplicati soppressi"
    lines = [head]
    if unsent_p0:
        lines.append(f"⚠️ {len(unsent_p0)} P0 non consegnati in tempo reale (budget/token) — sono qui sotto.")

    for source in sorted(by_source, key=lambda s: -len(by_source[s])):
        rs = by_source[source]
        last = rs[-1].get("text", "").replace("\n", " ")[:140]
        mark = "🔴" if any(r.get("p0_unsent") or r.get("p0_overflow") for r in rs) else "•"
        lines.append(f"{mark} {source} ×{len(rs)} — {last}")

    if log_count:
        lines.append(f"（log-only: {log_count} eventi su disco, non inviati）")

    text = "\n".join(lines)
    if len(text) > MAX_CHARS:
        kept, total = [], 0
        for ln in lines:
            if total + len(ln) + 1 > MAX_CHARS - 40:
                kept.append(f"… e altre {len(lines) - len(kept)} righe")
                break
            kept.append(ln)
            total += len(ln) + 1
        text = "\n".join(kept)
    return text


def flush(dry_run: bool = False) -> int:
    spool = _spool_dir()
    spool.mkdir(parents=True, exist_ok=True)
    machine = socket.gethostname().split(".")[0]

    with _spool_lock(spool):
        records = _rotate_pending(spool)
        claim_files = list(spool.glob(".flushing-*.jsonl"))
        if dry_run:
            logf = spool / "log-only.jsonl"
            log_count = (
                sum(1 for ln in logf.read_text(errors="replace").splitlines() if ln.strip())
                if logf.exists() else 0
            )
        else:
            log_count = _archive_log_only(spool)

    if not records:
        # heartbeat for the self-probe even when silent-healthy;
        # claims are empty by construction here (anything with content was adopted)
        (spool / "last_flush.json").write_text(
            json.dumps({"ts": time.time(), "sent": False, "events": 0})
        )
        for c in claim_files:
            c.unlink(missing_ok=True)
        print("tg_digest_flush: spool empty — nothing to send")
        return 0

    text = render(records, log_count, machine)
    if dry_run:
        with _spool_lock(spool):
            _restore(spool, records)
        for c in claim_files:
            c.unlink(missing_ok=True)
        print(text)
        return 0

    # network send OUTSIDE the lock — a hung API must not block senders
    token, chat = resolve_credentials()
    ok = bool(token and chat) and send_telegram(token, chat, text)
    if not ok:
        with _spool_lock(spool):
            _restore(spool, records)
        for c in claim_files:
            c.unlink(missing_ok=True)
        (spool / "last_flush.json").write_text(
            json.dumps({"ts": time.time(), "sent": False, "events": len(records), "error": "send-failed"})
        )
        print("tg_digest_flush: SEND FAILED — spool preserved", file=sys.stderr)
        return 3

    with _spool_lock(spool):
        _archive(spool, records)
    for c in claim_files:
        c.unlink(missing_ok=True)
    (spool / "last_flush.json").write_text(
        json.dumps({"ts": time.time(), "sent": True, "events": len(records)})
    )
    print(f"tg_digest_flush: sent digest with {len(records)} events")
    return 0


def selftest() -> int:
    import tempfile

    failures = []
    with tempfile.TemporaryDirectory() as td:
        os.environ["TG_SPOOL_DIR"] = td
        os.environ["TG_DRY_RUN"] = "1"
        spool = Path(td)

        def check(name, cond):
            print(("  ok  " if cond else "  FAIL") + f" {name}")
            if not cond:
                failures.append(name)

        # empty spool → silent success + self-probe stamp
        check("empty spool exits 0", flush() == 0)
        check("self-probe stamp exists", (spool / "last_flush.json").exists())

        recs = [
            {"ts": 1, "tier": "digest", "source": "fly-watcher", "text": "green"},
            {"ts": 2, "tier": "digest", "source": "fly-watcher", "text": "still green"},
            {"ts": 3, "tier": "p0", "source": "dlq", "text": "late", "p0_overflow": True},
        ]
        with (spool / "pending.jsonl").open("w") as fh:
            for r in recs:
                fh.write(json.dumps(r) + "\n")
        (spool / "log-only.jsonl").write_text('{"ts":4,"tier":"log","source":"hb","text":"x"}\n')

        text = render(recs, 1, "testhost")
        check("digest header counts 3", "3 eventi" in text)
        check("groups by source", "fly-watcher ×2" in text)
        check("p0 overflow flagged", "P0 non consegnati" in text)
        check("log-only counted not sent", "log-only: 1" in text)

        # dry-run must not consume the spool
        rc = flush(dry_run=True)
        check("dry-run exit 0", rc == 0)
        check("dry-run preserves spool", (spool / "pending.jsonl").exists())

        # crash recovery: a stale .flushing-* from a dead run is ADOPTED, not deleted
        (spool / ".flushing-999.jsonl").write_text(
            '{"ts":9,"tier":"digest","source":"crashed-run","text":"orphan"}\n'
        )
        adopted = _rotate_pending(spool)
        check("stale claim adopted", any(r.get("source") == "crashed-run" for r in adopted))
        _restore(spool, adopted)
        (spool / ".flushing-999.jsonl").unlink(missing_ok=True)
        for c in spool.glob(".flushing-*.jsonl"):
            c.unlink()

        # send failure (no token in fixture env... force by pointing secrets at /dev/null)
        os.environ["TG_SECRETS_FILE"] = "/dev/null"
        saved_env = {k: os.environ.pop(k, None) for k in
                     ("TELEGRAM_BOT_TOKEN", "TELEGRAM_OWNER_CHAT_ID",
                      "TELEGRAM_ZERO_CHAT_ID", "TELEGRAM_ADMIN_CHAT_ID")}
        os.environ.pop("TG_DRY_RUN", None)
        import tg_notify as _n
        _n.DRY_RUN = False
        rc = flush()
        check("no-token send → exit 3", rc == 3)
        check("spool preserved on failure", (spool / "pending.jsonl").exists())
        for k, v in saved_env.items():
            if v is not None:
                os.environ[k] = v

    print("SELFTEST", "PASS" if not failures else f"FAIL ({failures})")
    return 0 if not failures else 1


def main() -> int:
    args = sys.argv[1:]
    if "--selftest" in args:
        return selftest()
    return flush(dry_run="--dry-run" in args)


if __name__ == "__main__":
    sys.exit(main())
