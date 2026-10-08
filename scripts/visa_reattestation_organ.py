#!/usr/bin/env python3
"""Visa Oracle weekly re-attestation organ (pro.visa_reattestation).

Reads the OFFICIAL_PORTAL pages, has a Claude judge compare them with the active
pack, folds an UNSIGNED candidate pack (seq N+1) and opens a PR for a session to
sign. Signing and activation stay session acts on M5. Runbook:
docs/runbooks/visa-reattestation-organ.md. Stdlib only (cron's bare python3).

Exit codes: 0 done (or nothing to do), 1 judge halted on an `unsure` page,
2 any other failure. Every non-zero exit has raised a board row and a Telegram p0.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

logger = logging.getLogger("visa_reattestation_organ")

PACKS_REL = "apps/backend-rag/backend/services/visa_engine/contracts/packs"
VISA_SCRIPTS_REL = "apps/backend-rag/backend/scripts/visa_engine"
PORTAL = "OFFICIAL_PORTAL"
BRANCH_PREFIX = "organ/visa-reattest/"
T_MINUS = timedelta(days=7)
DEFAULT_STATE_DIR = Path.home() / ".local" / "state" / "nuzantara" / "visa-reattestation"
DEFAULT_BOARD = REPO_ROOT / "shared" / "escalations_pro.jsonl"
TG_NOTIFY = REPO_ROOT / "scripts" / "tg_notify.py"
TG_SOURCE = "visa-reattestation"
CREATED_BY = "organ.pro.visa-reattestation"
GIT_IDENT = ["-c", "user.name=Zantara Organ", "-c", "user.email=zantara@balizero.com"]
# Public verification keys (docs/runbooks/visa-engine-key-ceremony.md, "Trust-store JSON").
TRUST_STORE_JSON = json.dumps(
    [
        {
            "kid": "prod-2026-07-1",
            "public_key": "gZoo1nzMsRpwWgw4HCzV_2YYxU0Vbt5FMfLWeOzAchA",  # pragma: allowlist secret
            "environment": "PRODUCTION",
            "valid_from": "2026-07-19T00:00:00Z",
            "valid_to": None,
            "revoked_at": None,
        }
    ]
)


class OrganError(Exception):
    def __init__(self, stage: str, detail: str, rc: int = 2):
        super().__init__(f"{stage}: {detail}")
        self.stage, self.detail, self.rc = stage, detail, rc


# ---------------------------------------------------------------- process chokepoint
def _run(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None,
         timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    """The ONLY place a child process starts. Tests patch this."""
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True,
                          timeout=timeout, check=False)


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = _run(["git", "-C", str(repo), *args])
    if check and proc.returncode != 0:
        raise OrganError("git", f"git {' '.join(args[:3])} rc={proc.returncode}: {proc.stderr.strip()[-300:]}")
    return proc


# ---------------------------------------------------------------- pure helpers
def parse_utc(value: str) -> datetime:
    text = value.strip()
    text = text[:-1] + "+00:00" if text.endswith("Z") else text
    dt = datetime.fromisoformat(text)
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def assert_not_shared_checkout(workdir: Path) -> None:
    """Scar #5: git work never happens in the shared checkout. A linked worktree has
    `.git` as a FILE; the primary checkout has it as a directory."""
    if not (workdir / ".git").is_file():
        raise OrganError("worktree", f"{workdir} is not a linked worktree (shared checkout refused)")


def boundary_of(payload: dict[str, Any]) -> datetime | None:
    """Earliest verified_at + max_age_seconds over the OFFICIAL_PORTAL records."""
    ends = []
    for rec in payload.get("source_records", []):
        if rec.get("authority_type") != PORTAL:
            continue
        policy = rec.get("freshness_policy") or {}
        if not rec.get("verified_at") or not isinstance(policy.get("max_age_seconds"), int):
            continue
        ends.append(parse_utc(rec["verified_at"]) + timedelta(seconds=policy["max_age_seconds"]))
    return min(ends) if ends else None


def t7_due(boundary: datetime, now: datetime) -> bool:
    return boundary - now <= T_MINUS


def candidate_name(seq: int) -> str:
    return f"rulepack-prod-{seq:03d}.source.json"


def reader_name(judge: str, model: str, now: datetime) -> str:
    stamp = now.strftime("%Y%m%d")
    return f"fake-organ-{stamp}" if judge == "fake" else f"organ-{re.sub(r'[^a-z0-9]+', '-', model.lower()).strip('-')}-{stamp}"


def pr_title(date: str, next_seq: int) -> str:
    return f"chore(visa-engine): organ re-attestation ledger {date} — candidate seq-{next_seq} (unsigned)"


def pr_body(*, anchor_seq: int, next_seq: int, ledger_rel: str, candidate_rel: str, reader: str,
            boundary: datetime, payload_sha: str) -> str:
    return "\n".join([
        f"Weekly organ run (`pro.visa_reattestation`): read ledger + UNSIGNED candidate seq-{next_seq}.",
        "",
        f"- Anchor: signed seq-{anchor_seq}; its earliest portal boundary is {boundary.strftime('%Y-%m-%dT%H:%M:%SZ')}.",
        f"- Ledger: `{ledger_rel}` (reader `{reader}`).",
        f"- Candidate: `{candidate_rel}`, payload digest `{payload_sha or 'n/a'}`.",
        "- NOT signed, NOT armed. A session reviews the judge verdicts, signs on M5, activates per",
        "  `docs/runbooks/visa-engine-key-ceremony.md`, then merges. See `docs/runbooks/visa-reattestation-organ.md`.",
        "",
        "Bites: consumer is the signing session on M5 and, after activation, the Visa Oracle freshness gate; "
        f"observation is `python3 scripts/visa_freshness_sentinel.py --dry-run` reading seq-{next_seq} "
        "active with a later boundary.",
        "",
        "🤖 Generated by the Visa Oracle re-attestation organ",
    ])


def attestation_note(*, date: str, anchor_seq: int, next_seq: int, ledger_rel: str, reader: str, judge: str) -> str:
    return "\n".join([
        "---",
        f"date: {date}",
        "domain: visa",
        "client_case: none — scheduled organ run, source-ledger attestation",
        "sources:",
        f"  - {ledger_rel}/ (read ledger: receipts, judgements, saved visible text)",
        "  - apps/backend-rag/backend/scripts/visa_engine/portal_read_receipt.py",
        "  - apps/backend-rag/backend/scripts/visa_engine/portal_judge.py",
        "  - apps/backend-rag/backend/scripts/visa_engine/fold_pack_generic.py",
        "adversarial_review: pending-session",
        "---",
        "",
        f"# Organ re-attestation {date} — candidate seq-{next_seq} (unsigned)",
        "",
        f"The organ read the OFFICIAL_PORTAL pages of the signed seq-{anchor_seq} pack as reader `{reader}`",
        f"(judge `{judge}`) and folded `{candidate_name(next_seq)}` from that ledger. Nothing here is",
        "signed or active. `verified_at` of the candidate is the earliest successful read in the ledger.",
        "",
        "## Adversarial review",
        "",
        "Pending. The session that signs this candidate reviews the judge verdicts and reads every",
        "`changed` page itself, then replaces `pending-session` in the frontmatter with the reviewer.",
        "",
    ])


# ---------------------------------------------------------------- repo reads (no writes)
def find_anchor(repo: Path, ref: str = "origin/main") -> dict[str, Any]:
    names = _git(repo, "ls-tree", "--name-only", ref, f"{PACKS_REL}/").stdout.split()
    best: tuple[int, str, dict] | None = None
    for name in sorted(n for n in names if n.endswith(".signed.json")):
        shown = _git(repo, "show", f"{ref}:{name}", check=False)
        if shown.returncode != 0:
            continue
        try:
            payload = json.loads(shown.stdout).get("payload", {})
        except json.JSONDecodeError:
            continue
        seq = payload.get("sequence")
        if payload.get("environment") != "PRODUCTION" or not isinstance(seq, int) or isinstance(seq, bool):
            continue
        if best is None or seq > best[0]:
            best = (seq, name, payload)
    if best is None:
        raise OrganError("anchor", f"no signed PRODUCTION pack under {PACKS_REL} at {ref}")
    seq, signed_rel, payload = best
    source_rel = signed_rel.replace(".signed.json", ".source.json")
    if source_rel not in names:
        raise OrganError("anchor", f"{source_rel} missing next to the signed seq-{seq}")
    boundary = boundary_of(payload)
    if boundary is None:
        raise OrganError("anchor", f"seq-{seq} has no ageable {PORTAL} record")
    return {"seq": seq, "signed_rel": signed_rel, "source_rel": source_rel, "boundary": boundary}


def find_open_organ_pr(anchor_seq: int) -> dict[str, Any] | None:
    proc = _run(["gh", "pr", "list", "--state", "open", "--limit", "100",
                 "--json", "number,headRefName,url"])
    if proc.returncode != 0:
        raise OrganError("pr-lookup", f"gh pr list rc={proc.returncode}: {proc.stderr.strip()[-200:]}")
    prefix = f"{BRANCH_PREFIX}{anchor_seq}-"
    for pr in json.loads(proc.stdout or "[]"):
        if str(pr.get("headRefName", "")).startswith(prefix):
            return pr
    return None


def unsigned_candidate_on_main(repo: Path, next_seq: int) -> str | None:
    rel = f"{PACKS_REL}/{candidate_name(next_seq)}"
    return rel if _git(repo, "cat-file", "-e", f"origin/main:{rel}", check=False).returncode == 0 else None


# ---------------------------------------------------------------- alerts / state
def _tg(text: str, key: str, tier: str = "p0") -> None:
    if not TG_NOTIFY.is_file():
        logger.warning("tg_notify.py missing — alert not sent: %s", key)
        return
    try:
        proc = _run([sys.executable, str(TG_NOTIFY), "--tier", tier, "--source", TG_SOURCE,
                     "--dedup-key", key, "--", text], timeout=60)
        logger.info("tg_notify rc=%s key=%s", proc.returncode, key)
    except Exception as exc:  # noqa: BLE001 — a gateway failure never crashes the organ
        logger.warning("tg_notify failed: %s", exc)


def _board(board: Path, job: str, summary: str, detail: str) -> None:
    open_now = False
    for line in board.read_text(encoding="utf-8").splitlines()[-400:] if board.is_file() else []:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("job") == job:
            open_now = row.get("status") == "pending"
    if open_now:
        return
    now = time.time()
    row = {"job": job, "type": "visa_reattestation", "priority": "HIGH", "status": "pending",
           "error_summary": summary, "detail": detail[-1500:], "machine": "pro", "_writer": "pro", "ts": now}
    board.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(board), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, (json.dumps(row, ensure_ascii=False) + "\n").encode())
    finally:
        os.close(fd)


def alert(args: argparse.Namespace, *, job: str, key: str, summary: str, detail: str = "") -> None:
    if args.dry_run or args.offline:
        logger.info("alert suppressed (%s): %s", "dry-run" if args.dry_run else "offline", summary)
        return
    _board(Path(args.board), job, summary, detail)
    _tg(summary, key)


def write_state(args: argparse.Namespace, state: dict[str, Any]) -> None:
    if args.dry_run:
        return
    d = Path(args.state_dir)
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "state.json.tmp"
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True, default=str), encoding="utf-8")
    tmp.replace(d / "state.json")


# ---------------------------------------------------------------- pipeline pieces
def _python(code_root: Path) -> str:
    venv = code_root / "apps" / "backend-rag" / ".venv" / "bin" / "python"
    return str(venv) if venv.is_file() else sys.executable


def _backend_env(code_root: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(code_root / "apps" / "backend-rag")
    env.setdefault("VISA_ENGINE_TRUST_STORE_KEYS_JSON", TRUST_STORE_JSON)
    return env


def _module(stage: str, code_root: Path, module: str, argv: list[str], ok: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess[str]:
    proc = _run([_python(code_root), "-m", f"backend.scripts.visa_engine.{module}", *argv],
                cwd=code_root / "apps" / "backend-rag", env=_backend_env(code_root))
    if proc.returncode not in ok:
        raise OrganError(stage, f"{module} rc={proc.returncode}: {(proc.stdout + proc.stderr).strip()[-600:]}",
                         rc=1 if stage == "judge" else 2)
    return proc


def ensure_worktree(args: argparse.Namespace, anchor_seq: int, branch: str, existing: bool, wt: Path) -> None:
    repo = Path(args.repo)
    _git(repo, "worktree", "prune")
    start = f"origin/{branch}" if existing else "origin/main"
    if existing:
        _git(repo, "fetch", "origin", branch)
    _git(repo, "worktree", "add", "-B", branch, str(wt), start)
    assert_not_shared_checkout(wt)


def read_and_judge(args: argparse.Namespace, wt: Path, code_root: Path, anchor: dict, ledger: Path, reader: str) -> None:
    signed = wt / anchor["signed_rel"]
    ledger.mkdir(parents=True, exist_ok=True)
    if args.ledger_dir:
        shutil.copytree(args.ledger_dir, ledger, dirs_exist_ok=True)
    receipts, judgements = ledger / f"{reader}-receipts.jsonl", ledger / f"{reader}-judgements.jsonl"
    if not args.offline and not args.ledger_dir and not receipts.is_file():
        proc = _run([_python(code_root), str(code_root / VISA_SCRIPTS_REL / "portal_read_receipt.py"),
                     "--pack", str(signed), "--out-dir", str(ledger), "--reader", reader, "--all"],
                    env=_backend_env(code_root))
        if proc.returncode != 0:
            raise OrganError("read", f"portal_read_receipt rc={proc.returncode}: {(proc.stdout + proc.stderr).strip()[-500:]}")
    if args.skip_judge:
        if not list(ledger.glob("*-judgements.jsonl")):
            raise OrganError("judge", "--skip-judge but the ledger has no *-judgements.jsonl")
    elif not judgements.is_file():
        if not (code_root / VISA_SCRIPTS_REL / "portal_judge.py").is_file():
            raise OrganError("judge", "portal_judge.py is absent in the code root (PR #8069 not merged yet)")
        _module("judge", code_root, "portal_judge", ["--pack", str(signed), "--ledger-dir", str(ledger),
                "--reader", reader, "--all", "--judge", args.judge, "--model", args.model], ok=(0,))


def fold(args: argparse.Namespace, wt: Path, code_root: Path, anchor: dict, ledger: Path, reader: str, now: datetime) -> tuple[Path, str]:
    out = wt / PACKS_REL / candidate_name(anchor["seq"] + 1)
    argv = ["--anchor-source", str(wt / anchor["source_rel"]), "--anchor-signed", str(wt / anchor["signed_rel"]),
            "--ledger-dir", str(ledger), "--output", str(out),
            "--version", f"{now.year}.{now.month}.{now.day}",
            "--created-by", args.fold_created_by or CREATED_BY, "--verified-by", args.fold_verified_by or reader]
    if args.fold_created_at:
        argv += ["--created-at", args.fold_created_at]
    if args.judge == "fake" or args.fold_allow_fake:
        argv.append("--allow-fake-reader")
    proc = _module("fold", code_root, "fold_pack_generic", argv)
    sha = next((ln.rsplit("= ", 1)[1].strip() for ln in proc.stdout.splitlines() if "payload_sha256 =" in ln), "")
    return out, sha


def commit_and_push(wt: Path, branch: str, title: str, rels: list[str]) -> None:
    _git(wt, "add", "--", *rels)
    if _git(wt, "diff", "--cached", "--quiet", check=False).returncode != 0:
        _git(wt, *GIT_IDENT, "commit", "-m", title)
    _git(wt, "push", "origin", f"HEAD:refs/heads/{branch}")


def publish(args: argparse.Namespace, wt: Path, branch: str, existing_pr: dict | None, date: str,
            anchor: dict, title: str, body: str, files: list[Path]) -> str:
    rels = [str(p.relative_to(wt)) for p in files]
    commit_and_push(wt, branch, title, rels)
    if existing_pr:
        return existing_pr["url"]
    proc = _run(["gh", "pr", "create", "--base", "main", "--head", branch, "--title", title, "--body", body])
    if proc.returncode != 0:
        raise OrganError("pr-create", f"gh pr create rc={proc.returncode}: {proc.stderr.strip()[-300:]}")
    return proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""


# ---------------------------------------------------------------- orchestration
def run(args: argparse.Namespace) -> int:
    now = parse_utc(args.now) if args.now else datetime.now(timezone.utc)
    date = now.strftime("%Y-%m-%d")
    repo = Path(args.repo)
    if not args.dry_run and not args.no_fetch:
        _git(repo, "fetch", "origin", "main")
    anchor = find_anchor(repo)
    next_seq = anchor["seq"] + 1
    existing_pr = None if args.offline else find_open_organ_pr(anchor["seq"])
    branch = existing_pr["headRefName"] if existing_pr else f"{BRANCH_PREFIX}{anchor['seq']}-{date}"
    remote_branch = existing_pr is not None or _git(
        repo, "ls-remote", "--exit-code", "--heads", "origin", branch, check=False).returncode == 0
    reader = reader_name(args.judge, args.model, now)
    ledger_rel = f"research/visa/{date}-organ-reattest-seq{next_seq}"
    plan = {"anchor_seq": anchor["seq"], "next_seq": next_seq, "boundary": anchor["boundary"].isoformat(),
            "days_to_boundary": round((anchor["boundary"] - now).total_seconds() / 86400, 2),
            "t7_due": t7_due(anchor["boundary"], now), "branch": branch, "reader": reader,
            "ledger": ledger_rel, "candidate": f"{PACKS_REL}/{candidate_name(next_seq)}",
            "existing_pr": existing_pr["url"] if existing_pr else None, "mode": "dry-run" if args.dry_run else
            "offline" if args.offline else "live", "judge": args.judge}
    if args.dry_run:
        print(json.dumps(plan, indent=2, default=str))
        return 0

    state: dict[str, Any] = {"ts": now.isoformat(), "anchor_seq": anchor["seq"], "boundary": plan["boundary"]}
    candidate_ref = None
    rc = 0
    wt = Path(args.state_dir) / "worktrees" / f"seq{next_seq}-{now.strftime('%Y%m%dT%H%M%S')}"
    code_root = Path(args.code_root) if args.code_root else repo
    try:
        ensure_worktree(args, anchor["seq"], branch, remote_branch, wt)
        if not args.code_root:
            code_root = wt
        ledger = wt / ledger_rel
        read_and_judge(args, wt, code_root, anchor, ledger, reader)
        candidate, sha = fold(args, wt, code_root, anchor, ledger, reader, now)
        note = wt / f"{ledger_rel}-attestation.md"
        note.write_text(attestation_note(date=date, anchor_seq=anchor["seq"], next_seq=next_seq,
                                         ledger_rel=ledger_rel, reader=reader, judge=args.judge), encoding="utf-8")
        title = pr_title(date, next_seq)
        body = pr_body(anchor_seq=anchor["seq"], next_seq=next_seq, ledger_rel=ledger_rel,
                       candidate_rel=plan["candidate"], reader=reader, boundary=anchor["boundary"], payload_sha=sha)
        state.update(candidate=plan["candidate"], payload_sha256=sha, pr_title=title, pr_body=body, branch=branch)
        if args.offline:
            commit_and_push(wt, branch, title, [str(ledger.relative_to(wt)), plan["candidate"], str(note.relative_to(wt))])
            print(json.dumps({"pr_title": title, "pr_body": body, "candidate": plan["candidate"]}, indent=2))
        else:
            state["pr_url"] = publish(args, wt, branch, existing_pr, date, anchor, title, body,
                                      [ledger, candidate, note])
        candidate_ref = state.get("pr_url") or f"{branch}:{plan['candidate']}"
        state["outcome"] = "candidate-ready"
    except OrganError as exc:
        rc = exc.rc
        state.update(outcome="failed", stage=exc.stage, detail=exc.detail)
        alert(args, job=f"visa-reattestation:{exc.stage}:seq{anchor['seq']}",
              key=f"visa-freshness:reattest-{exc.stage}:{anchor['seq']}",
              summary=f"Visa re-attestation FAILED at '{exc.stage}' (anchor seq-{anchor['seq']}, boundary "
                      f"{plan['boundary']}): {exc.detail[:300]}", detail=exc.detail)
    finally:
        if wt.exists():
            _git(repo, "worktree", "remove", "--force", str(wt), check=False)
        _git(repo, "branch", "-D", branch, check=False)

    if candidate_ref is None:
        candidate_ref = (existing_pr or {}).get("url") or unsigned_candidate_on_main(repo, next_seq)
    if candidate_ref and t7_due(anchor["boundary"], now):
        week = now.strftime("%G-W%V")
        alert(args, job=f"visa-reattestation:pack-ready:seq{next_seq}", key=f"visa-freshness:pack-ready:{next_seq}:{week}",
              summary=f"Visa pack ready to sign: {candidate_ref}, boundary {plan['boundary']} "
                      f"({plan['days_to_boundary']} days).")
        state["t7_alert"] = candidate_ref
    write_state(args, state)
    print(json.dumps({k: v for k, v in state.items() if k != "pr_body"}, indent=2, default=str))
    return rc


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Weekly Visa Oracle portal re-attestation organ.")
    p.add_argument("--dry-run", action="store_true", help="print the plan; no fetch, git write, PR, alert or state")
    p.add_argument("--offline", action="store_true", help="no portal read, no gh, no Telegram; needs --ledger-dir")
    p.add_argument("--judge", choices=("claude", "fake"), default="claude")
    p.add_argument("--model", default="sonnet")
    p.add_argument("--skip-judge", action="store_true", help="use judgements already in the ledger")
    p.add_argument("--ledger-dir", help="existing ledger copied into the worktree instead of reading portals")
    p.add_argument("--repo", default=str(REPO_ROOT), help="shared checkout (read + worktree add only)")
    p.add_argument("--code-root", help="where the visa_engine scripts run from (default: the worktree)")
    p.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    p.add_argument("--board", default=str(DEFAULT_BOARD))
    p.add_argument("--now", help="TEST-ONLY ISO-8601 clock override")
    p.add_argument("--no-fetch", action="store_true", help="rehearsal: do not fetch origin/main")
    p.add_argument("--fold-created-by")
    p.add_argument("--fold-verified-by")
    p.add_argument("--fold-created-at")
    p.add_argument("--fold-allow-fake", action="store_true", help="rehearsal only: pass --allow-fake-reader to the fold")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="[visa-reattestation] %(message)s")
    if args.offline and not args.ledger_dir:
        build_parser().error("--offline needs --ledger-dir")
    try:
        return run(args)
    except OrganError as exc:  # failure before the pipeline (anchor, fetch, pr lookup)
        alert(args, job=f"visa-reattestation:{exc.stage}", key=f"visa-freshness:reattest-{exc.stage}",
              summary=f"Visa re-attestation FAILED at '{exc.stage}': {exc.detail[:300]}", detail=exc.detail)
        write_state(args, {"ts": datetime.now(timezone.utc).isoformat(), "outcome": "failed",
                           "stage": exc.stage, "detail": exc.detail})
        print(f"visa_reattestation_organ: FAIL {exc}", file=sys.stderr)
        return exc.rc


if __name__ == "__main__":
    sys.exit(main())
