#!/usr/bin/env python3
"""Phase E of LOCALCI-SOVEREIGN, prepared and never applied by a session: the flip that leaves the merger's deploy key the
only writer of ``main`` (docs/specs/localci-sovereign-2026-10-07.md, §2 phase E, §4 item 2 and phase F's credential paragraph).

    (default)            read-only plan: the live classic protection of the branch, the ``merge-queue-main`` ruleset, the
                         ruleset that keeps deletion and force-push forbidden, the deploy keys and the report; prints the
                         current required set, the exact writes of the flip, what still blocks it, and the plan's digest
    --apply --confirm D  the flip, refused unless D is the digest the plan prints for this very state, the report is READY
                         (``phase_e_ready`` true, generated within 2 h, same repo) and exactly one write deploy key exists,
                         the merger's (``--key-pub``). The pre-flip state is saved (0600) before the first write; then (1) the
                         ruleset loses the merge queue and gains ``update`` with the DeployKey bypass as its only actor, (2) only
                         once GitHub's answer shows that, the classic protection is deleted; both are re-read and the run
                         fails unless they read flipped
    --rollback FILE      the same two-step shape in reverse from a saved state, again only with --apply --confirm D, re-read
                         after and failed unless both read as saved

Why the classic protection goes: it requires a pull request and the status checks on ``main``, and classic protection has no
deploy-key exemption, so while it stands the merger's push is refused whatever a ruleset says. Deletion and force-push stay
forbidden by the other ruleset (``deletion`` + ``non_fast_forward``, no bypass actor), which the flip requires to exist. The
order of the writes is the safe one: between them nobody moves ``main`` (the ruleset stops everyone but the key, the classic
protection still stops the key). A DeployKey bypass covers every write deploy key of the repository, hence exactly one.

The operator applies (operator[gui]) after creating the key (operator[secret]); a session runs the plan only. Every read is
a GET through ``gh api``; the writes exist only behind the checks above.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_REPO = "Bali-Zero/Teman2"
DEFAULT_BRANCH = "main"
RULESET = "merge-queue-main"
DEFAULT_REPORT = Path.home() / ".nuzantara-pilots" / "local-ci" / "merger" / "report.json"
DEFAULT_STATE_DIR = Path.home() / ".nuzantara-pilots" / "local-ci" / "phase-e"
DEFAULT_KEY_PUB = Path.home() / ".nuzantara-pilots" / "local-ci" / "merger" / "deploy_key.pub"
REPORT_MAX_AGE = timedelta(hours=2)
REPORT_MAX_SKEW = timedelta(minutes=5)
READY_MERGES, READY_DAYS = 50, 14   # phase D's READY as ruled 2026-10-07; read back from the report, never relaxed here
TARGET_RULES = [{"type": "update", "parameters": {"update_allows_fetch_and_merge": False}}]
TARGET_BYPASS = [{"actor_id": None, "actor_type": "DeployKey", "bypass_mode": "always"}]
CLASSIC_FLAGS = ("required_linear_history", "allow_force_pushes", "allow_deletions", "block_creations",
                 "required_conversation_resolution", "lock_branch", "allow_fork_syncing")
REVIEW_FIELDS = ("dismiss_stale_reviews", "require_code_owner_reviews", "require_last_push_approval", "required_approving_review_count")
RULESET_FIELDS = ("name", "target", "enforcement", "conditions", "rules", "bypass_actors")

EXIT_OK, EXIT_REFUSED, EXIT_BAD_INPUT, EXIT_WRITE_FAILED = 0, 1, 2, 3
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_BRANCH_RE = re.compile(r"^[A-Za-z0-9_./-]+$")
_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_GLOB = re.compile(r"[*?\[]")


class FlipError(Exception):
    pass


def now() -> datetime:
    return datetime.now(timezone.utc)


def gh(*args: str, body: dict | None = None, missing_ok: bool = False) -> Any:
    """One ``gh api`` call. Without ``--method`` it is a GET; a 404 reads as None only where the caller allows it."""
    res = subprocess.run(["gh", "api", *args], input=None if body is None else json.dumps(body), capture_output=True, text=True)
    if res.returncode != 0:
        if missing_ok and "(HTTP 404)" in res.stderr:
            return None
        raise FlipError(f"gh api {' '.join(args)} failed (rc={res.returncode}): {res.stderr.strip()[-200:]}")
    try:
        return json.loads(res.stdout) if res.stdout.strip() else {}
    except json.JSONDecodeError as exc:
        raise FlipError(f"gh api {' '.join(args)} returned no JSON: {exc}") from exc


def classic_body(doc: dict) -> dict:
    """The GET shape of a classic protection turned into the PUT body that recreates it; a setting this tool cannot restore
    exactly is refused, never dropped."""
    if doc.get("restrictions"):
        raise FlipError("classic protection restricts who can push: not restorable by this tool, refusing")
    if (doc.get("required_signatures") or {}).get("enabled"):
        raise FlipError("classic protection requires signed commits: not restorable by this tool, refusing")
    rsc = doc.get("required_status_checks")
    checks = None
    if rsc is not None:
        if rsc.get("checks") is None:
            raise FlipError("required_status_checks carries no `checks` list: refusing to guess the required set")
        # GET says null for "any source"; PUT reads an omitted app_id as "the app that last reported it", so null is -1
        checks = {"strict": bool(rsc.get("strict")),
                  "checks": [{"context": c["context"], "app_id": -1 if c.get("app_id") is None else c["app_id"]} for c in rsc["checks"]]}
    reviews = doc.get("required_pull_request_reviews")
    if reviews is not None:
        for key in ("dismissal_restrictions", "bypass_pull_request_allowances"):   # GET lists them only when configured
            if reviews.get(key) is not None:
                raise FlipError(f"required_pull_request_reviews.{key} is present: not restorable by this tool, refusing")
        reviews = {k: reviews[k] for k in REVIEW_FIELDS if k in reviews}
    body = {"required_status_checks": checks, "enforce_admins": bool((doc.get("enforce_admins") or {}).get("enabled")),
            "required_pull_request_reviews": reviews, "restrictions": None}
    body.update({k: bool((doc.get(k) or {}).get("enabled")) for k in CLASSIC_FLAGS})
    return body


def ruleset_body(doc: dict) -> dict:
    missing = [k for k in RULESET_FIELDS if k not in doc]
    if missing:
        raise FlipError(f"ruleset {doc.get('id')} lacks {missing}: refusing to rewrite what cannot be saved whole")
    return {k: doc[k] for k in RULESET_FIELDS}


def covers(rs: dict, branch: str, default_branch: str) -> bool:
    """Included by name and excluded by nothing; a pattern in the exclude list counts as excluding (never evaluated here)."""
    ref = (rs.get("conditions") or {}).get("ref_name") or {}
    names = {f"refs/heads/{branch}", "~ALL", *(["~DEFAULT_BRANCH"] if branch == default_branch else [])}
    exclude = ref.get("exclude") or []
    return bool(names & set(ref.get("include") or [])) and not names & set(exclude) and not any(_GLOB.search(x) for x in exclude)


def only_branch(rs: dict, branch: str, default_branch: str) -> bool:
    include = set(((rs.get("conditions") or {}).get("ref_name") or {}).get("include") or [])
    return bool(include) and include <= {f"refs/heads/{branch}", *(["~DEFAULT_BRANCH"] if branch == default_branch else [])}


def key_fingerprint(material: str | None) -> str | None:
    """sha256 of a public key's type and blob (no comment): names a key without printing it."""
    parts = (material or "").split()
    return hashlib.sha256(" ".join(parts[:2]).encode()).hexdigest()[:16] if len(parts) >= 2 else None


def read_key_pub(path: Path) -> str | None:
    try:
        return key_fingerprint(path.read_text())
    except OSError:
        return None


def is_target(rs: dict) -> bool:
    """The flipped ruleset by meaning, not by spelling: enforced, one ``update`` rule allowing no fetch-and-merge, and the
    DeployKey the one bypass actor, always."""
    rules, bypass = rs.get("rules") or [], rs.get("bypass_actors") or []
    return (rs.get("enforcement") == "active" and len(rules) == 1 and rules[0].get("type") == "update"
            and (rules[0].get("parameters") or {}).get("update_allows_fetch_and_merge") is False
            and len(bypass) == 1 and bypass[0].get("actor_type") == "DeployKey" and bypass[0].get("bypass_mode") == "always")


def read_state(repo: str, branch: str) -> dict:
    classic = gh(f"repos/{repo}/branches/{branch}/protection", missing_ok=True)
    default_branch = gh(f"repos/{repo}")["default_branch"]
    full = [gh(f"repos/{repo}/rulesets/{r['id']}") for r in gh(f"repos/{repo}/rulesets?per_page=100")
            if r.get("source_type") == "Repository" and r.get("target") == "branch"]
    named = [r for r in full if r.get("name") == RULESET]
    if len(named) != 1:
        raise FlipError(f"{len(named)} repository rulesets named {RULESET!r}: expected exactly one")
    guards = [r for r in full if r is not named[0] and r.get("enforcement") == "active" and r.get("bypass_actors", None) == []
              and {"deletion", "non_fast_forward"} <= {x.get("type") for x in r.get("rules") or []} and covers(r, branch, default_branch)]
    keys = gh(f"repos/{repo}/keys?per_page=100")
    return {"repo": repo, "branch": branch, "classic": None if classic is None else classic_body(classic),
            "ruleset_id": named[0]["id"], "ruleset": ruleset_body(named[0]),
            "ruleset_covers_branch": covers(named[0], branch, default_branch), "ruleset_only_branch": only_branch(named[0], branch, default_branch),
            "guards": [{"id": g["id"], **ruleset_body(g)} for g in guards],
            "write_keys": [{"id": k["id"], "created_at": k.get("created_at"), "fingerprint": key_fingerprint(k.get("key"))}
                           for k in keys if k.get("read_only") is False]}


def phase(state: dict) -> str:
    if state["classic"] is not None and "merge_queue" in {r.get("type") for r in state["ruleset"]["rules"]}:
        return "pre-flip"
    if state["classic"] is None and is_target(state["ruleset"]) and state["ruleset_covers_branch"]:
        return "flipped"
    return "drifted"


def flip_writes(state: dict) -> list[dict]:
    target = dict(state["ruleset"], rules=TARGET_RULES, bypass_actors=TARGET_BYPASS, enforcement="active")
    return [{"method": "PUT", "path": f"repos/{state['repo']}/rulesets/{state['ruleset_id']}", "body": target},
            {"method": "DELETE", "path": f"repos/{state['repo']}/branches/{state['branch']}/protection", "body": None}]


def rollback_writes(saved: dict) -> list[dict]:
    return [{"method": "PUT", "path": f"repos/{saved['repo']}/branches/{saved['branch']}/protection", "body": saved["classic"]},
            {"method": "PUT", "path": f"repos/{saved['repo']}/rulesets/{saved['ruleset_id']}", "body": saved["ruleset"]}]


def digest(state: dict, writes: list[dict]) -> str:
    return hashlib.sha256(json.dumps({"state": state, "writes": writes}, sort_keys=True).encode()).hexdigest()[:16]


def read_report(path: Path, repo: str) -> tuple[list[str], str]:
    """(blockers, one summary line). READY is the report's own field; the numbers beside it are read back so a report that
    says READY without them is refused, not believed."""
    try:
        rep = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return [f"report {path} unreadable: {type(exc).__name__}"], f"report: unreadable ({path})"
    win, counts = rep.get("window") or {}, rep.get("counts") or {}
    gen = rep.get("generated_at")
    line = (f"report: phase_e_ready {json.dumps(rep.get('phase_e_ready'))} (generated {gen}): compared_merges "
            f"{win.get('compared_merges')}/{READY_MERGES}, compared_days {win.get('compared_days')}/{READY_DAYS}, "
            f"FALSE_GREEN {counts.get('FALSE_GREEN')}")
    blockers = []
    if rep.get("phase_e_ready") is not True:
        blockers.append("report is not READY (phase_e_ready is not true)")
    if rep.get("repo") != repo:
        blockers.append(f"report is for {rep.get('repo')!r}, not {repo!r}")
    if not (isinstance(gen, str) and _TS_RE.match(gen)):
        blockers.append("report carries no readable generated_at")
    else:
        age = now() - datetime.strptime(gen, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if age > REPORT_MAX_AGE or age < -REPORT_MAX_SKEW:
            blockers.append(f"report generated {gen} is outside the last {REPORT_MAX_AGE} — recompute it first")
    if rep.get("phase_e_ready") is True:
        cm, cd, fg = win.get("compared_merges"), win.get("compared_days"), counts.get("FALSE_GREEN")
        if not (isinstance(cm, int) and cm >= READY_MERGES and isinstance(cd, (int, float)) and cd >= READY_DAYS and fg == 0):
            blockers.append("report says READY but its window does not show it: refusing the contradiction")
    return blockers, line


def plan_blockers(state: dict, flip: bool, merger_key: str | None) -> list[str]:
    out = []
    if flip:
        if (p := phase(state)) != "pre-flip":
            out.append(f"live state is {p}, not pre-flip")
        if not state["ruleset_covers_branch"]:
            out.append(f"ruleset {RULESET!r} does not cover {state['branch']}: restricting it would not restrict the branch")
        if not state["ruleset_only_branch"]:
            out.append(f"ruleset {RULESET!r} includes more than {state['branch']}: its update rule would freeze those branches too")
    if not state["guards"]:
        out.append("no active ruleset without bypass actors forbids deletion AND force-push on the branch: the flip would open both")
    if len(state["write_keys"]) != 1:
        out.append(f"{len(state['write_keys'])} write deploy keys: the DeployKey bypass covers each one, exactly one must exist (operator[secret])")
    elif merger_key is None:
        out.append("the merger's public key (--key-pub) is unreadable: the one write deploy key cannot be identified as the merger's")
    elif state["write_keys"][0]["fingerprint"] != merger_key:
        out.append("the one write deploy key is not the merger's (its fingerprint differs from --key-pub)")
    return out


def describe(state: dict) -> list[str]:
    out = []
    c = state["classic"]
    if c is None:
        out.append(f"classic protection on {state['branch']}: absent")
    else:
        rsc = c["required_status_checks"]
        reviews = c["required_pull_request_reviews"]
        out.append(f"classic protection on {state['branch']}: present — enforce_admins {c['enforce_admins']}, pull request "
                   f"{'required (' + str(reviews.get('required_approving_review_count')) + ' approvals)' if reviews is not None else 'not required'}, "
                   f"force pushes {'allowed' if c['allow_force_pushes'] else 'blocked'}, deletions {'allowed' if c['allow_deletions'] else 'blocked'}")
        if rsc is None:
            out.append("  required status checks: none")
        else:
            out.append(f"  required status checks ({len(rsc['checks'])}, strict {rsc['strict']}):")
            out += [f"    - {ch['context']}  [source: {'any' if ch['app_id'] == -1 else 'app ' + str(ch['app_id'])}]" for ch in rsc["checks"]]
    rs = state["ruleset"]
    out.append(f"ruleset {rs['name']!r} (id {state['ruleset_id']}, {rs['enforcement']}): rules {[r.get('type') for r in rs['rules']]}, "
               f"bypass {[b.get('actor_type') for b in rs['bypass_actors']] or 'none'}, "
               f"includes {((rs.get('conditions') or {}).get('ref_name') or {}).get('include')}")
    out.append("deletion/force-push guard: " + (", ".join(f"{g['name']!r} (id {g['id']})" for g in state["guards"]) or "NONE"))
    out.append(f"write deploy keys: {len(state['write_keys'])}" + "".join(
        f"\n  - id {k['id']} created {k['created_at']} fingerprint {k['fingerprint']}" for k in state["write_keys"]))
    return out


def show_writes(writes: list[dict]) -> list[str]:
    out = []
    for i, w in enumerate(writes, 1):
        out.append(f"  {i}. {w['method']} {w['path']}")
        if w["body"] is not None:
            out.append("     " + json.dumps(w["body"], sort_keys=True))
    return out


def save_state(state_dir: Path, state: dict, dig: str) -> Path:
    path = state_dir / f"pre-flip-{now().strftime('%Y%m%dT%H%M%SZ')}.json"
    try:   # no write to GitHub before this file exists: a flip that cannot be undone from disk is refused
        state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(state_dir, 0o700)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump({**state, "saved_at": now().strftime("%Y-%m-%dT%H:%M:%SZ"), "plan_digest": dig}, fh, indent=2, sort_keys=True)
            fh.write("\n")
    except OSError as exc:
        raise FlipError(f"pre-flip state not saved to {path} ({type(exc).__name__}): nothing written") from exc
    return path


def execute(writes: list[dict], took: dict | None = None) -> None:
    """The writes in order; ``took[i]`` judges write i's answer, and a write that answered without taking stops the rest."""
    for i, w in enumerate(writes, 1):
        args = ["--method", w["method"], w["path"]] + (["--input", "-"] if w["body"] is not None else [])
        try:
            answer = gh(*args, body=w["body"])
        except FlipError as exc:
            raise FlipError(f"write {i}/{len(writes)} failed: {exc}") from exc
        if took and i in took and not took[i](answer):
            raise FlipError(f"write {i}/{len(writes)} answered without taking: {w['method']} {w['path']}; nothing after it was sent")
        print(f"  write {i}/{len(writes)} done: {w['method']} {w['path']}")


def run_flip(a: argparse.Namespace) -> int:
    state = read_state(a.repo, a.branch)
    writes = flip_writes(state)
    dig = digest(state, writes)
    merger_key = read_key_pub(a.key_pub)
    blockers = plan_blockers(state, flip=True, merger_key=merger_key)
    rep_blockers, rep_line = read_report(a.report, a.repo)
    print(f"phase E flip — {a.repo} {a.branch} — {'APPLY' if a.apply else 'DRY RUN (nothing is written)'}")
    print(f"state: {phase(state)}")
    print("\n".join(describe(state)))
    print(f"merger key (--key-pub): {merger_key or 'unreadable'}")
    print(rep_line)
    if phase(state) == "flipped":
        if unsafe := plan_blockers(state, flip=False, merger_key=merger_key):
            print("already flipped, but: " + "; ".join(unsafe), file=sys.stderr)
            return EXIT_REFUSED
        print("already flipped: nothing to write")
        return EXIT_OK
    print("writes the flip makes, in order:")
    print("\n".join(show_writes(writes)))
    all_blockers = blockers + rep_blockers
    print("blockers for --apply: " + ("; ".join(all_blockers) if all_blockers else "none"))
    print(f"plan digest: {dig}  (--apply needs --confirm {dig}, read from a plan of this very state)")
    if not a.apply:
        return EXIT_OK
    if a.confirm != dig:
        print("REFUSED: --confirm does not match this plan's digest (re-read the plan; the state may have changed)", file=sys.stderr)
        return EXIT_REFUSED
    if all_blockers:
        print("REFUSED: " + "; ".join(all_blockers), file=sys.stderr)
        return EXIT_REFUSED
    saved = save_state(a.state_dir, state, dig)
    print(f"pre-flip state saved: {saved}")
    took = {1: lambda answer: isinstance(answer, dict) and is_target(answer) and answer.get("conditions") == state["ruleset"]["conditions"]}
    try:   # the classic protection goes only once the ruleset's answer shows it restricted: never a branch with neither
        execute(writes, took)
        after = read_state(a.repo, a.branch)
    except FlipError as exc:
        print(f"FAILED: {exc}\n  restore with: {Path(sys.argv[0]).name} --rollback {saved} (plan first, then --apply --confirm)", file=sys.stderr)
        return EXIT_WRITE_FAILED
    if phase(after) != "flipped":
        print(f"FAILED: re-read after the writes says {phase(after)}, not flipped\n  restore with: --rollback {saved}", file=sys.stderr)
        return EXIT_WRITE_FAILED
    print("flipped: the classic protection is gone and only the deploy key can update the branch")
    return EXIT_OK


def run_rollback(a: argparse.Namespace) -> int:
    try:
        saved = json.loads(a.rollback.read_text())
        state_keys = {"repo", "branch", "classic", "ruleset_id", "ruleset"}
        if not isinstance(saved, dict) or not state_keys <= set(saved) or not isinstance(saved["classic"], dict):
            raise FlipError(f"{a.rollback} is not a pre-flip state (needs {sorted(state_keys)} with a classic protection)")
    except (OSError, json.JSONDecodeError) as exc:
        raise FlipError(f"{a.rollback} unreadable: {type(exc).__name__}") from exc
    if (saved["repo"], saved["branch"]) != (a.repo, a.branch):
        raise FlipError(f"{a.rollback} is for {saved['repo']} {saved['branch']}, not {a.repo} {a.branch}")
    live = read_state(a.repo, a.branch)
    if live["ruleset_id"] != saved["ruleset_id"]:
        raise FlipError(f"ruleset {RULESET!r} is now id {live['ruleset_id']}, the saved state names {saved['ruleset_id']}")
    writes = rollback_writes(saved)
    dig = digest(live, writes)
    print(f"phase E rollback — {a.repo} {a.branch} — {'APPLY' if a.apply else 'DRY RUN (nothing is written)'}")
    print(f"live state: {phase(live)}")
    print("\n".join(describe(live)))
    print("writes the rollback makes, in order:")
    print("\n".join(show_writes(writes)))
    print(f"plan digest: {dig}  (--apply needs --confirm {dig})")
    if not a.apply:
        return EXIT_OK
    if a.confirm != dig:
        print("REFUSED: --confirm does not match this plan's digest", file=sys.stderr)
        return EXIT_REFUSED
    try:
        execute(writes)
        after = read_state(a.repo, a.branch)
    except FlipError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return EXIT_WRITE_FAILED
    if differ := [k for k in ("classic", "ruleset") if after[k] != saved[k]]:
        print(f"FAILED: re-read after the rollback differs from the saved state in {differ}", file=sys.stderr)
        return EXIT_WRITE_FAILED
    print("rolled back: classic protection and the ruleset re-read as saved")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="LOCALCI phase E flip: read-only plan by default; the operator applies.")
    ap.add_argument("--repo", default=DEFAULT_REPO, help=f"owner/name (default {DEFAULT_REPO})")
    ap.add_argument("--branch", default=DEFAULT_BRANCH, help=f"the branch the merger alone will update (default {DEFAULT_BRANCH})")
    ap.add_argument("--report", type=Path, default=DEFAULT_REPORT, help="the merger's report.json (READY is read from it)")
    ap.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR, help="where the pre-flip state is saved (0700/0600)")
    ap.add_argument("--key-pub", type=Path, default=DEFAULT_KEY_PUB, help="the merger's deploy key, public half (identifies the one write key)")
    ap.add_argument("--rollback", type=Path, default=None, metavar="STATE", help="plan (or with --apply, make) the restore of a saved state")
    ap.add_argument("--apply", action="store_true", help="write; refused without --confirm and the preconditions")
    ap.add_argument("--confirm", default=None, metavar="DIGEST", help="the plan digest of the very state being changed")
    a = ap.parse_args(argv)
    if not _REPO_RE.match(a.repo) or not _BRANCH_RE.match(a.branch):
        print("bad --repo or --branch", file=sys.stderr)
        return EXIT_BAD_INPUT
    try:
        return run_rollback(a) if a.rollback else run_flip(a)
    except FlipError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
