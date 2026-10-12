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
import hashlib
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
LEDGER_KEEP = 8
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
        f"- Candidate: `{candidate_rel}` (inside the ledger dir), payload digest `{payload_sha or 'n/a'}`.",
        f"- Signing step: move it to `{PACKS_REL}/{candidate_name(next_seq)}` (`git mv`), then sign it there.",
        "- NOT signed, NOT armed. A session reviews the judge verdicts, signs on M5, activates per",
        "  `docs/runbooks/visa-engine-key-ceremony.md`, then merges. See `docs/runbooks/visa-reattestation-organ.md`.",
        "",
        "Bites: consumer is the signing session on M5 and, after activation, the Visa Oracle freshness gate; "
        f"observation is `python3 scripts/visa_freshness_sentinel.py --dry-run` reading seq-{next_seq} "
        "active with a later boundary.",
        "",
        "🤖 Generated by the Visa Oracle re-attestation organ",
    ])


def attestation_note(*, date: str, anchor_seq: int, next_seq: int, ledger_rel: str, reader: str, judge: str,
                     attested: dict[str, str] | None = None, disagreements: list[dict[str, str]] | None = None) -> str:
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
        "## Attested reads used as the fingerprint baseline",
        "",
        *([f"- `{rid}`: {label}" for rid, label in (attested or {}).items()] or ["- none provable"]),
        "",
        "## Baseline disagreements",
        "",
        *([f"- `{d['source_record_id'][:8]}` ({d['source_key']}): reader `{d['reader']}` said `changed` on a page whose "
           f"fingerprint `{d['fingerprint']}` equals the attested read {d['attested_read']}; downgraded to `none`."
           for d in (disagreements or [])] or ["- none"]),
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


def find_open_organ_pr(anchor_seq: int, repo: Path) -> dict[str, Any] | None:
    proc = _run(["gh", "pr", "list", "--state", "open", "--limit", "1000",
                 "--json", "number,headRefName,url"], cwd=repo)
    if proc.returncode != 0:
        raise OrganError("pr-lookup", f"gh pr list rc={proc.returncode}: {proc.stderr.strip()[-200:]}")
    prefix = f"{BRANCH_PREFIX}{anchor_seq}-"
    for pr in json.loads(proc.stdout or "[]"):
        if str(pr.get("headRefName", "")).startswith(prefix):
            return pr
    return None


def unsigned_candidate_on_main(repo: Path, next_seq: int) -> str | None:
    """A merged organ ledger whose candidate has not been moved into packs/ and signed."""
    name = candidate_name(next_seq)
    listing = _git(repo, "ls-tree", "-r", "--name-only", "origin/main", "research/visa/", check=False).stdout
    hits = sorted(x for x in listing.splitlines() if x.endswith(f"-organ-reattest-seq{next_seq}/{name}"))
    return hits[-1] if hits else None


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
    try:
        _board(Path(args.board), job, summary, detail)
    except Exception as exc:  # noqa: BLE001 — a dead board must not silence Telegram
        logger.warning("board write failed: %s", exc)
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
def _python(code_root: Path, repo: Path | None = None) -> str:
    """The backend venv is untracked, so a fresh worktree never has one: fall back to the
    shared checkout's, then to the interpreter running this script."""
    for root in (code_root, repo):
        venv = root / "apps" / "backend-rag" / ".venv" / "bin" / "python" if root else None
        if venv is not None and venv.is_file():
            return str(venv)
    return sys.executable


def _backend_env(code_root: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(code_root / "apps" / "backend-rag")
    env.setdefault("VISA_ENGINE_TRUST_STORE_KEYS_JSON", TRUST_STORE_JSON)
    return env


def _module(stage: str, code_root: Path, repo: Path, module: str, argv: list[str],
            ok: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess[str]:
    proc = _run([_python(code_root, repo), "-m", f"backend.scripts.visa_engine.{module}", *argv],
                cwd=code_root / "apps" / "backend-rag", env=_backend_env(code_root))
    if proc.returncode not in ok:
        raise OrganError(stage, f"{module} rc={proc.returncode}: {(proc.stdout + proc.stderr).strip()[-600:]}",
                         rc=1 if stage == "judge" and proc.returncode == 1 else 2)
    return proc


def reap_own_worktrees(repo: Path, state_dir: Path, spare: list[Path] | None = None) -> None:
    """A hard-killed run leaves its worktree registered and its branch checked out, which
    blocks every later `worktree add -B`. The wrapper's pidfile makes this organ a singleton,
    so anything under its own state dir is an orphan."""
    root = str((state_dir / "worktrees").resolve())
    listing = _git(repo, "worktree", "list", "--porcelain", check=False).stdout
    for line in listing.splitlines():
        if line.startswith("worktree ") and line[9:].startswith(root) and (
                Path(line[9:]).resolve() not in {p.resolve() for p in spare or []}):
            _git(repo, "worktree", "remove", "--force", line[9:], check=False)


def ensure_worktree(args: argparse.Namespace, anchor_seq: int, branch: str, existing: bool, wt: Path,
                    spare: list[Path] | None = None) -> None:
    repo = Path(args.repo)
    wt.parent.mkdir(parents=True, exist_ok=True)
    reap_own_worktrees(repo, Path(args.state_dir), spare)
    _git(repo, "worktree", "prune")
    start = f"origin/{branch}" if existing else "origin/main"
    if existing:
        _git(repo, "fetch", "origin", f"+refs/heads/{branch}:refs/remotes/origin/{branch}")
    _git(repo, "worktree", "add", "-B", branch, str(wt), start)
    assert_not_shared_checkout(wt)


def _baseline_module() -> Any:
    """The shared fingerprint/baseline logic lives next to the fold that also uses it."""
    backend = str(REPO_ROOT / "apps" / "backend-rag")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    from backend.scripts.visa_engine import baseline_ledger  # noqa: PLC0415 — needs the path above

    return baseline_ledger


def portal_records_of(signed: Path) -> list[dict[str, Any]]:
    data = json.loads(signed.read_text(encoding="utf-8"))
    payload = data.get("payload", data)
    return [r for r in payload.get("source_records", []) if r.get("authority_type") == PORTAL]


def judged_ids(ledger: Path) -> set[str]:
    ids: set[str] = set()
    for path in ledger.glob("*-judgements.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and row.get("source_record_id"):
                ids.add(row["source_record_id"])
    return ids


def baseline_root_of(args: argparse.Namespace, code_root: Path) -> Path:
    """`--baseline-root`, else `research/visa` of the code root. Which ledger inside it attests a
    record is PROVEN per record (baseline_ledger.attested_reads), never named."""
    if args.baseline_root:
        root = Path(args.baseline_root)
        if not root.is_dir():
            raise OrganError("baseline", f"--baseline-root {root} is not a directory")
        return root
    return code_root / "research" / "visa"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_and_judge(args: argparse.Namespace, wt: Path, code_root: Path, anchor: dict, ledger: Path,
                   reader: str) -> tuple[Path, dict[str, Any]]:
    """Read the portals, judge them; returns the baseline root for the fold and the attested reads."""
    signed = wt / anchor["signed_rel"]
    ledger.mkdir(parents=True, exist_ok=True)
    if args.ledger_dir:
        shutil.copytree(args.ledger_dir, ledger, dirs_exist_ok=True)
    receipts, judgements = ledger / f"{reader}-receipts.jsonl", ledger / f"{reader}-judgements.jsonl"
    if not args.offline and not args.ledger_dir and not receipts.is_file():
        proc = _run([_python(code_root, Path(args.repo)), str(code_root / VISA_SCRIPTS_REL / "portal_read_receipt.py"),
                     "--pack", str(signed), "--out-dir", str(ledger), "--reader", reader, "--all"],
                    cwd=code_root / "apps" / "backend-rag", env=_backend_env(code_root))
        if proc.returncode != 0:
            raise OrganError("read", f"portal_read_receipt rc={proc.returncode}: {(proc.stdout + proc.stderr).strip()[-500:]}")
    portals = portal_records_of(signed)
    root = baseline_root_of(args, code_root)
    bl = _baseline_module()
    attested = bl.attested_reads(root, portals, exclude=[ledger], log=logger.warning)
    for rid, held in sorted(attested.items()):
        logger.info("attested read %s: %s", rid[:8], held.label())
    if args.skip_judge:
        if not list(ledger.glob("*-judgements.jsonl")):
            raise OrganError("judge", "--skip-judge but the ledger has no *-judgements.jsonl")
        return root, attested
    portal_ids = [r["source_record_id"] for r in portals]
    pending = [i for i in portal_ids if i not in judged_ids(ledger)]
    asked_all = len(pending) == len(portal_ids)
    if attested and pending:
        rows = bl.fingerprint_judgements(ledger, pending, attested, reader=reader, judged_at=_utc_stamp())
        if rows:
            with judgements.open("a", encoding="utf-8") as out:
                out.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
        proven = {r["source_record_id"] for r in rows}
        logger.info("fingerprint: %d of %d pages identical to their attested read — judged without a model",
                    len(proven), len(pending))
        asked_all = asked_all and not proven
        pending = [i for i in pending if i not in proven]
    if not pending:
        logger.info("judge skipped: every portal record already has a judgement")
        return root, attested
    if not (code_root / VISA_SCRIPTS_REL / "portal_judge.py").is_file():
        raise OrganError("judge", "portal_judge.py is absent in the code root (PR #8069 not merged yet)")
    which = ["--all"] if asked_all else ["--ids", ",".join(pending)]
    _module("judge", code_root, Path(args.repo), "portal_judge", ["--pack", str(signed), "--ledger-dir", str(ledger),
            "--reader", reader, *which, "--judge", args.judge, "--model", args.model], ok=(0,))
    return root, attested


def fold(args: argparse.Namespace, wt: Path, code_root: Path, anchor: dict, ledger: Path, reader: str, now: datetime,
         baseline_root: Path | None = None) -> tuple[Path, str, list[dict[str, str]]]:
    out = ledger / candidate_name(anchor["seq"] + 1)
    argv = ["--anchor-source", str(wt / anchor["source_rel"]), "--anchor-signed", str(wt / anchor["signed_rel"]),
            "--ledger-dir", str(ledger), "--output", str(out),
            "--version", f"{now.year}.{now.month}.{now.day}",
            "--created-by", args.fold_created_by or CREATED_BY, "--verified-by", args.fold_verified_by or reader]
    if args.fold_created_at:
        argv += ["--created-at", args.fold_created_at]
    if baseline_root is not None:
        argv += ["--baseline-root", str(baseline_root)]
    if args.judge == "fake" or args.fold_allow_fake:
        argv.append("--allow-fake-reader")
    proc = _module("fold", code_root, Path(args.repo), "fold_pack_generic", argv)
    sha = next((ln.rsplit("= ", 1)[1].strip() for ln in proc.stdout.splitlines() if "payload_sha256 =" in ln), "")
    line = next((ln for ln in proc.stdout.splitlines() if "baseline_disagreements =" in ln), "")
    try:
        disagreements = json.loads(line.rsplit("= ", 1)[1]) if line else []
    except json.JSONDecodeError:
        disagreements = []
    return out, sha, disagreements


def _manifest(directory: Path) -> dict[str, tuple[str, str]]:
    """Every entry with its content: size and sha256 for files, the target for links."""
    out: dict[str, tuple[str, str]] = {}
    for p in sorted(directory.rglob("*")):
        rel = str(p.relative_to(directory))
        if p.is_symlink():
            out[rel] = ("link", os.readlink(p))
        elif p.is_dir():
            out[rel] = ("dir", "")
        else:
            out[rel] = (str(p.stat().st_size), hashlib.sha256(p.read_bytes()).hexdigest())
    return out


def _refuse_unsafe_symlinks(ledger: Path) -> None:
    """A link is copied as a link, so it must still point inside the copy: relative and in-ledger only."""
    inside = ledger.resolve()
    for entry in ledger.rglob("*"):
        if not entry.is_symlink():
            continue
        if os.path.isabs(os.readlink(entry)):
            raise OSError(f"{entry} is an absolute symlink (it would dangle once the worktree is gone)")
        if not entry.resolve().is_relative_to(inside):
            raise OSError(f"{entry} is a symlink leaving the ledger")


def _ledger_age(path: Path) -> tuple[str, int]:
    """`<UTC ts>-seq<N>[-<k>]` -> (ts, k): copying preserves mtimes, so the name is the clock."""
    m = re.match(r"(\d{8}T\d{6}Z)-seq\d+(?:-(\d+))?$", path.name)
    return (m.group(1), int(m.group(2) or 1)) if m else ("", 0)


def retry_kept_worktree(args: argparse.Namespace, repo: Path) -> list[Path]:
    """Worktrees earlier runs kept because their ledger copy failed: retry the copy first and reap each
    only after a VERIFIED copy. Returns those still unresolved (spare them, keep alerting)."""
    try:
        prior = json.loads((Path(args.state_dir) / "state.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(prior, dict):
        return []
    paths = prior.get("worktrees_kept") or ([prior["worktree_kept"]] if prior.get("worktree_kept") else [])
    unresolved: list[Path] = []
    for raw in paths:
        kept = Path(raw)
        if not kept.is_dir():
            continue
        ledgers = sorted(kept.glob("research/visa/*-organ-reattest-seq*"))
        why: list[str] = []
        if ledgers and keep_ledger(args, ledgers[-1], int(prior.get("anchor_seq") or 0), why) is None:
            logger.warning("kept worktree %s: copy still failing (%s)", kept, "; ".join(why))
            unresolved.append(kept)
            continue
        _git(repo, "worktree", "remove", "--force", str(kept), check=False)
        logger.info("kept worktree %s: ledger copied and verified, reaped", kept)
    return unresolved


KEPT_NAME = re.compile(r"\d{8}T\d{6}Z-seq\d+(-\d+)?")


def keep_ledger(args: argparse.Namespace, ledger: Path, anchor_seq: int, why: list[str] | None = None) -> Path | None:
    """Copy the run's ledger (receipts, judgements, texts) out of the worktree that is about to be
    removed, VERIFY the copy (same entries, sizes and sha256), and keep the newest LEDGER_KEEP copies.
    Symlinks are copied as links and one that leaves the ledger refuses the copy. Returns None when
    there is nothing to keep or the copy failed or did not verify: the caller then keeps the worktree.
    Never raises."""
    if not ledger.is_dir():
        return None
    dest: Path | None = None
    try:
        root = Path(args.state_dir) / "ledgers"
        root.mkdir(parents=True, exist_ok=True)
        _refuse_unsafe_symlinks(ledger)
        base = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-seq{anchor_seq}"
        taken = [_ledger_age(p)[1] for p in root.iterdir() if p.name == base or p.name.startswith(f"{base}-")]
        dest = root / (base if not taken else f"{base}-{max(taken) + 1}")
        shutil.copytree(ledger, dest, symlinks=True)
        if _manifest(dest) != _manifest(ledger):
            raise OSError("the copy does not match the ledger (entries or sizes differ)")
        kept = sorted((p for p in root.iterdir() if p.is_dir() and KEPT_NAME.fullmatch(p.name)), key=_ledger_age)
        for old in kept[:-LEDGER_KEEP]:
            shutil.rmtree(old, ignore_errors=True)
        return dest
    except Exception as exc:  # noqa: BLE001 — keeping evidence must never fail the run it documents
        logger.warning("could not keep the ledger: %s", exc)
        if why is not None:
            why.append(f"{type(exc).__name__}: {exc}"[:300])
        if dest is not None:
            shutil.rmtree(dest, ignore_errors=True)
        return None


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
    proc = _run(["gh", "pr", "create", "--base", "main", "--head", branch, "--title", title, "--body", body], cwd=wt)
    if proc.returncode != 0:
        raise OrganError("pr-create", f"gh pr create rc={proc.returncode}: {proc.stderr.strip()[-300:]}")
    return proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""


# ---------------------------------------------------------------- orchestration
def run(args: argparse.Namespace) -> int:
    now = parse_utc(args.now) if args.now else datetime.now(timezone.utc)
    date = now.strftime("%Y-%m-%d")
    repo = Path(args.repo)
    if not args.dry_run and not args.no_fetch:
        _git(repo, "fetch", "origin", "+refs/heads/main:refs/remotes/origin/main")
    anchor = find_anchor(repo)
    next_seq = anchor["seq"] + 1
    existing_pr = None if args.offline else find_open_organ_pr(anchor["seq"], repo)
    branch = existing_pr["headRefName"] if existing_pr else f"{BRANCH_PREFIX}{anchor['seq']}-{date}"
    remote_branch = existing_pr is not None or _git(
        repo, "ls-remote", "--exit-code", "--heads", "origin", branch, check=False).returncode == 0
    reader = reader_name(args.judge, args.model, now)
    ledger_rel = f"research/visa/{date}-organ-reattest-seq{next_seq}"
    plan = {"anchor_seq": anchor["seq"], "next_seq": next_seq, "boundary": anchor["boundary"].isoformat(),
            "days_to_boundary": round((anchor["boundary"] - now).total_seconds() / 86400, 2),
            "t7_due": t7_due(anchor["boundary"], now), "branch": branch, "reader": reader,
            "ledger": ledger_rel, "candidate": f"{ledger_rel}/{candidate_name(next_seq)}",
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
    ledger = wt / ledger_rel
    worktree_kept: Path | None = None
    prior_kept = retry_kept_worktree(args, repo)
    if prior_kept:
        state.update(worktree_kept=str(prior_kept[0]), worktrees_kept=[str(p) for p in prior_kept])
        alert(args, job=f"visa-reattestation:worktree-kept:seq{anchor['seq']}",
              key=f"visa-freshness:reattest-worktree-kept:{anchor['seq']}",
              summary=f"Visa re-attestation: a failed run's ledger is still only in the worktree "
                      f"{prior_kept[0]} (the copy keeps failing). Read it before it is lost.",
              detail="\n".join(str(p) for p in prior_kept))
    try:
        ensure_worktree(args, anchor["seq"], branch, remote_branch, wt, prior_kept)
        if not args.code_root:
            code_root = wt
        baseline_root, attested = read_and_judge(args, wt, code_root, anchor, ledger, reader)
        candidate, sha, disagreements = fold(args, wt, code_root, anchor, ledger, reader, now, baseline_root)
        choices = {rid[:8]: held.label() for rid, held in sorted(attested.items())}
        note = wt / f"{ledger_rel}-attestation.md"
        note.write_text(attestation_note(date=date, anchor_seq=anchor["seq"], next_seq=next_seq,
                                         ledger_rel=ledger_rel, reader=reader, judge=args.judge,
                                         attested=choices, disagreements=disagreements), encoding="utf-8")
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
        state.update(attested_reads=choices, baseline_disagreements=disagreements)
        why: list[str] = []
        kept = keep_ledger(args, ledger, anchor["seq"], why)
        state["ledger_copy"] = str(kept) if kept else None
        if kept is None and ledger.is_dir():
            worktree_kept = wt
    except Exception as exc:  # noqa: BLE001 — anything unexpected is still a failed run, never a silent one
        if not isinstance(exc, OrganError):
            exc = OrganError("unexpected", f"{type(exc).__name__}: {exc}")
        rc = exc.rc
        why = []
        kept = keep_ledger(args, ledger, anchor["seq"], why)
        if kept is None and ledger.is_dir():
            worktree_kept = wt
        where = (f" Ledger kept at {kept}" if kept else
                 f" Ledger copy FAILED ({'; '.join(why)}): worktree kept at {wt} "
                 "(the next run retries the copy before reaping it)" if worktree_kept else "")
        state.update(outcome="failed", stage=exc.stage, detail=exc.detail,
                     ledger_copy=str(kept) if kept else None)
        alert(args, job=f"visa-reattestation:{exc.stage}:seq{anchor['seq']}",
              key=f"visa-freshness:reattest-{exc.stage}:{anchor['seq']}",
              summary=f"Visa re-attestation FAILED at '{exc.stage}' (anchor seq-{anchor['seq']}, boundary "
                      f"{plan['boundary']}): {exc.detail[:300]}{where}", detail=exc.detail[-1200:] + where)
    finally:
        if worktree_kept is None:
            if wt.exists():
                _git(repo, "worktree", "remove", "--force", str(wt), check=False)
            _git(repo, "branch", "-D", branch, check=False)
        else:
            state.update(worktree_kept=str(worktree_kept),
                         worktrees_kept=[str(worktree_kept), *[str(p) for p in prior_kept]])

    if candidate_ref is None:
        candidate_ref = (existing_pr or {}).get("url") or unsigned_candidate_on_main(repo, next_seq)
    if candidate_ref and t7_due(anchor["boundary"], now):
        week = now.strftime("%G-W%V")
        alert(args, job=f"visa-reattestation:pack-ready:seq{next_seq}", key=f"visa-freshness:pack-ready:{next_seq}:{week}",
              summary=f"Visa pack ready to sign: {candidate_ref}, boundary {plan['boundary']} "
                      f"({plan['days_to_boundary']} days)."
                      + (f" Candidate is from an earlier run; this run failed at '{state['stage']}'."
                         if state.get("outcome") == "failed" else ""))
        state["t7_alert"] = candidate_ref
    write_state(args, state)
    print(json.dumps({k: v for k, v in state.items() if k != "pr_body"}, indent=2, default=str))
    return rc


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Weekly Visa Oracle portal re-attestation organ.")
    p.add_argument("--dry-run", action="store_true", help="print the plan; no fetch, git write, PR, alert or state")
    p.add_argument("--offline", action="store_true", help="no portal read, no gh, no Telegram, no board; git still talks to --repo's origin; needs --ledger-dir")
    p.add_argument("--judge", choices=("claude", "fake"), default="claude")
    p.add_argument("--model", default="sonnet")
    p.add_argument("--skip-judge", action="store_true", help="use judgements already in the ledger")
    p.add_argument("--ledger-dir", help="existing ledger copied into the worktree instead of reading portals")
    p.add_argument("--baseline-root", help="directory of ledgers (default: research/visa of the code root) "
                   "from which each record's attested read is proven; see the runbook")
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
        try:
            return run(args)
        except OrganError:
            raise
        except Exception as exc:  # noqa: BLE001 — timeouts, OS and JSON errors must still alert
            raise OrganError("unexpected", f"{type(exc).__name__}: {exc}") from exc
    except OrganError as exc:  # failure before the pipeline (anchor, fetch, pr lookup) or unexpected
        alert(args, job=f"visa-reattestation:{exc.stage}", key=f"visa-freshness:reattest-{exc.stage}",
              summary=f"Visa re-attestation FAILED at '{exc.stage}': {exc.detail[:300]}", detail=exc.detail)
        write_state(args, {"ts": datetime.now(timezone.utc).isoformat(), "outcome": "failed",
                           "stage": exc.stage, "detail": exc.detail})
        print(f"visa_reattestation_organ: FAIL {exc}", file=sys.stderr)
        return exc.rc


if __name__ == "__main__":
    sys.exit(main())
