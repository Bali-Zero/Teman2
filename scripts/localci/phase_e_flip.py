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
                         once GitHub's answer and a fresh read show that, with the guard and the one key unchanged, the classic
                         protection is deleted; both are re-read and the run fails unless they read flipped and safe
    --rollback FILE      the same two-step shape in reverse from a saved state, again only with --apply --confirm D, re-read
                         after and failed unless both read as saved

Why the classic protection goes: it requires a pull request and the status checks on ``main``, and classic protection has no
deploy-key exemption, so while it stands the merger's push is refused whatever a ruleset says. Deletion and force-push stay
forbidden by the other ruleset (``deletion`` + ``non_fast_forward``, no bypass actor), which the flip requires to exist. The
order of the writes is the safe one: between them nobody moves ``main`` (the ruleset stops everyone but the key, the classic
protection still stops the key). A DeployKey bypass covers every write deploy key of the repository, hence exactly one.

Every write obeys the write discipline RULED 2026-10-10 (scripts/localci/README.md, "Phase E flip"): Q the operator declares
the repository quiescent (--quiescent); W1 a fresh read immediately before EVERY write, equal to the state the plan confirmed
as advanced by the writes made ("changed since plan" otherwise, and nothing is written); W5 a fresh read after every write,
equal to the state it intended; W2 no rule beside the ruleset's own may stop the key; W3 READY is the branch's and the whole
journal's; W4 once a write was sent every failure is exit 3 with the rollback command. Residual, accepted: no compare-and-swap.

The operator applies (operator[gui]) after creating the key (operator[secret]); a session runs the plan only. Every read is
a GET through ``gh api``; the writes exist only behind the checks above.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
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
MAX_PAGES = 20
ALLOWED_BESIDE = frozenset({"deletion", "non_fast_forward", "copilot_code_review"})   # W2: what may apply beside the ruleset's rule
READ_RETRIES, READ_DELAY_S = 3, 2.0   # W5: a fresh read that lags the write (or fails) is read again before it counts
QUIESCENCE = ("--apply also needs --quiescent: the operator declares that no session, peer or cron writes rulesets or branch "
              "protection of this repository during the run (RULED 2026-10-10; GitHub offers no compare-and-swap, so this is "
              "a precondition, not a check)")
NOT_PROTECTED = "Branch not protected"   # GitHub's 404 for an unprotected branch; any other 404 is an error, never "absent"

EXIT_OK, EXIT_REFUSED, EXIT_BAD_INPUT, EXIT_WRITE_FAILED = 0, 1, 2, 3
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_BRANCH_RE = re.compile(r"^[A-Za-z0-9_./-]+$")
_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_GLOB = re.compile(r"[*?\[]")


class FlipError(Exception):
    pass


def now() -> datetime:
    return datetime.now(timezone.utc)


def pause(seconds: float) -> None:
    time.sleep(seconds)


def gh(*args: str, body: dict | None = None, missing: str | None = None) -> Any:
    """One ``gh api`` call. Without ``--method`` it is a GET; a 404 reads as None only when it carries the caller's message."""
    res = subprocess.run(["gh", "api", *args], input=None if body is None else json.dumps(body), capture_output=True, text=True)
    if res.returncode != 0:
        if missing and missing in res.stderr and "(HTTP 404)" in res.stderr:
            return None
        raise FlipError(f"gh api {' '.join(args)} failed (rc={res.returncode}): {res.stderr.strip()[-200:]}")
    try:
        return json.loads(res.stdout) if res.stdout.strip() else {}
    except json.JSONDecodeError as exc:
        raise FlipError(f"gh api {' '.join(args)} returned no JSON: {exc}") from exc


def gh_all(path: str) -> list:
    """Every page of a list endpoint: a count read from the first page of several is no count."""
    out: list = []
    for page in range(1, MAX_PAGES + 1):
        batch = gh(f"{path}?per_page=100&page={page}")
        if not isinstance(batch, list):
            raise FlipError(f"gh api {path}: page {page} is not a list")
        out += batch
        if len(batch) < 100:
            return out
    raise FlipError(f"gh api {path}: more than {MAX_PAGES} pages — refusing a truncated count")


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
    """The key's ``SHA256:`` fingerprint as ``ssh-keygen -lf`` and GitHub's key page print it: names it without printing it."""
    parts = (material or "").split()
    if len(parts) < 2:
        return None
    try:
        blob = base64.b64decode(parts[1], validate=True)
    except (binascii.Error, ValueError):
        return None
    return "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")


def same_classic(a: dict | None, b: dict | None) -> bool:
    """Two classic bodies compared with their checks as a set: GitHub may list them in another order."""
    def norm(x):
        if not x or not x.get("required_status_checks"):
            return x
        rsc = x["required_status_checks"]
        return {**x, "required_status_checks": {**rsc, "checks": sorted(rsc["checks"], key=lambda c: (c["context"], str(c["app_id"])))}}
    return norm(a) == norm(b)


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
    classic = gh(f"repos/{repo}/branches/{branch}/protection", missing=NOT_PROTECTED)
    default_branch = gh(f"repos/{repo}")["default_branch"]
    # the list may omit `target` (GitHub's own example does): the details decide, never the summary
    details = [gh(f"repos/{repo}/rulesets/{r['id']}") for r in gh_all(f"repos/{repo}/rulesets") if r.get("source_type", "Repository") == "Repository"]
    full = [d for d in details if d.get("source_type", "Repository") == "Repository" and d.get("target") == "branch"]
    named = [r for r in full if r.get("name") == RULESET]
    if len(named) != 1:
        raise FlipError(f"{len(named)} repository rulesets named {RULESET!r}: expected exactly one")
    guards = [r for r in full if r is not named[0] and r.get("enforcement") == "active" and r.get("bypass_actors", None) == []
              and {"deletion", "non_fast_forward"} <= {x.get("type") for x in r.get("rules") or []} and covers(r, branch, default_branch)]
    keys = gh_all(f"repos/{repo}/keys")
    applied = gh_all(f"repos/{repo}/rules/branches/{branch}")   # every rule GitHub applies to the branch, inherited ones included
    return {"repo": repo, "branch": branch, "default_branch": default_branch,
            "classic": None if classic is None else classic_body(classic),
            # each applied rule whole — its ruleset, type, source and parameters: a changed parameter is a changed state
            "branch_rules": sorted(([r.get("ruleset_id"), r.get("type"), r.get("ruleset_source_type"), r.get("parameters")] for r in applied),
                                   key=lambda x: json.dumps(x, sort_keys=True)),
            "ruleset_id": named[0]["id"], "ruleset": ruleset_body(named[0]),
            "ruleset_covers_branch": covers(named[0], branch, default_branch), "ruleset_only_branch": only_branch(named[0], branch, default_branch),
            "guards": [{"id": g["id"], **ruleset_body(g)} for g in guards],
            "write_keys": [{"id": k["id"], "created_at": k.get("created_at"), "fingerprint": key_fingerprint(k.get("key"))}
                           for k in keys if k.get("read_only") is not True]}   # an unknown read_only is a write key


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


def with_ruleset(state: dict, rs: dict) -> dict:
    """The state as it must read once the ruleset is ``rs``: its scope and the rules GitHub applies to the branch follow it."""
    rid, default = state["ruleset_id"], state["default_branch"]
    own = [[rid, r.get("type"), "Repository", r.get("parameters")] for r in rs["rules"]] if rs.get("enforcement") == "active" else []
    return {**state, "ruleset": rs, "ruleset_covers_branch": covers(rs, state["branch"], default),
            "ruleset_only_branch": only_branch(rs, state["branch"], default),
            "branch_rules": sorted([*(x for x in state["branch_rules"] if x[0] != rid), *own], key=lambda x: json.dumps(x, sort_keys=True))}


def applied_rules(state: dict) -> list:
    """The rules GitHub applies to the branch, compared whole except the ruleset's own, whose parameters the ruleset itself is
    judged on (a read-back may spell them otherwise): its entries keep their ruleset and type only."""
    rid = state["ruleset_id"]
    return sorted((x[:2] if x[0] == rid else x for x in state["branch_rules"]), key=lambda x: json.dumps(x, sort_keys=True))


def diverges(fresh: dict, expected: dict) -> list[str]:
    """W1: the components in which a fresh read differs from the expected state (none: it is the expected state)."""
    out = []
    if not same_classic(fresh["classic"], expected["classic"]):
        out.append("classic protection")
    rf, rx = fresh["ruleset"], expected["ruleset"]
    same_ruleset = (is_target(rf) and all(rf.get(k) == rx.get(k) for k in ("name", "target", "conditions"))) if is_target(rx) else rf == rx
    if fresh["ruleset_id"] != expected["ruleset_id"] or not same_ruleset:
        out.append(f"ruleset {RULESET!r}")
    out += [k for k in ("guards", "write_keys", "ruleset_covers_branch", "ruleset_only_branch") if fresh[k] != expected[k]]
    if applied_rules(fresh) != applied_rules(expected):
        out.append("branch_rules")
    return out


def settled(repo: str, branch: str, expected: dict, when: str) -> dict:
    """W5: a fresh read equal to the state a write intended, read again while GitHub may lag the write or a read fails; else
    FlipError."""
    differ: list[str] = []
    for attempt in range(READ_RETRIES):
        try:
            fresh = read_state(repo, branch)
            differ = diverges(fresh, expected)
        except FlipError as exc:   # a failed read is no read: it is retried like one that lags
            differ = [f"unreadable ({exc})"]
        if not differ:
            return fresh
        if attempt + 1 < READ_RETRIES:
            pause(READ_DELAY_S)
    raise FlipError(f"{when}: a fresh read differs from the intended state in {differ}")


def digest(state: dict, writes: list[dict]) -> str:
    return hashlib.sha256(json.dumps({"state": state, "writes": writes}, sort_keys=True).encode()).hexdigest()[:16]


def _no_constant(name: str):
    raise ValueError(f"non-standard JSON constant {name}")


def read_report(path: Path, repo: str, branch: str) -> tuple[list[str], str]:
    """(blockers, one summary line). READY is the report's own field; the numbers beside it are read back so a report that
    says READY without them is refused, not believed."""
    try:
        rep = json.loads(path.read_text(), parse_constant=_no_constant)   # W3: Infinity and NaN are no numbers
    except (OSError, ValueError) as exc:
        return [f"report {path} unreadable: {type(exc).__name__}: {exc}"], f"report: unreadable ({path})"
    if not isinstance(rep, dict):
        return [f"report {path} is not a JSON object"], f"report: not an object ({path})"
    win, counts, ctx = (rep.get(k) if isinstance(rep.get(k), dict) else {} for k in ("window", "counts", "context_counts"))
    gen = rep.get("generated_at")
    line = (f"report: phase_e_ready {json.dumps(rep.get('phase_e_ready'))} (generated {gen}): compared_merges "
            f"{win.get('compared_merges')}/{READY_MERGES}, compared_days {win.get('compared_days')}/{READY_DAYS}, "
            f"FALSE_GREEN {counts.get('FALSE_GREEN')}")
    blockers = []
    if rep.get("phase_e_ready") is not True:
        blockers.append("report is not READY (phase_e_ready is not true)")
    if rep.get("repo") != repo:
        blockers.append(f"report is for {rep.get('repo')!r}, not {repo!r}")
    if rep.get("base") != branch:
        blockers.append(f"report judged base {rep.get('base')!r}, not {branch!r}")
    if "since" not in rep:
        blockers.append("report carries no `since`: it must say its window is the whole journal (since null)")
    elif rep["since"] is not None:
        blockers.append(f"report window is cut at since={rep['since']!r}: READY is read over the whole journal")
    if not (isinstance(gen, str) and _TS_RE.match(gen)):
        blockers.append("report carries no readable generated_at")
    else:
        try:
            age = now() - datetime.strptime(gen, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            age = None
        if age is None:
            blockers.append(f"report generated_at {gen} is no date")
        elif age > REPORT_MAX_AGE or age < -REPORT_MAX_SKEW:
            blockers.append(f"report generated {gen} is outside the last {REPORT_MAX_AGE} — recompute it first")
    if rep.get("phase_e_ready") is True:
        cm, cd = win.get("compared_merges"), win.get("compared_days")
        # READY's FALSE_GREEN 0 is "at every level" (merger.py report): the decisions, the contexts and the recorded ones
        fgs = (counts.get("FALSE_GREEN"), ctx.get("FALSE_GREEN"), rep.get("recorded_context_false_green"))
        if not (type(cm) is int and cm >= READY_MERGES and (type(cd) is int or (type(cd) is float and math.isfinite(cd))) and cd >= READY_DAYS
                and all(type(x) is int and x == 0 for x in fgs)):
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
    # a guard counts only when GitHub's own rules/branches shows its deletion and non_fast_forward on the branch
    proven = [g for g in state["guards"] if {(g["id"], "deletion"), (g["id"], "non_fast_forward")} <= {tuple(x[:2]) for x in state["branch_rules"]}]
    if not proven:
        out.append("no active ruleset without bypass actors forbids deletion AND force-push on the branch, as GitHub applies it "
                   "(rules/branches): the flip would open both")
    if beside := [f"{t} (ruleset {rid})" for rid, t, *_ in state["branch_rules"] if rid != state["ruleset_id"] and t not in ALLOWED_BESIDE]:
        out.append("rules beside the ruleset's own would also stop the merger's push (rules layer, a bypass exempts only its own "
                   "ruleset): " + ", ".join(beside))
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


def execute(repo: str, branch: str, writes: list[dict], expected: list[dict], took: dict, sent: list) -> None:
    """The writes in order under the RULED write discipline. ``expected[0]`` is the confirmed state and ``expected[i]`` the
    state write i intends. W1: immediately before write i a fresh read must equal ``expected[i-1]`` — else "changed since
    plan" and nothing is written; ``took[i]`` judges write i's answer (None when it took, else why not); W5: after it a
    fresh read must equal ``expected[i]``. ``sent`` records each write index as it goes out (W4 reads it)."""
    n = len(writes)
    for i, w in enumerate(writes, 1):
        try:
            fresh = read_state(repo, branch)
        except FlipError as exc:
            raise FlipError(f"before write {i}/{n}: the object could not be read again ({exc}); nothing written by this step") from exc
        if differ := diverges(fresh, expected[i - 1]):
            raise FlipError(f"before write {i}/{n}: changed since plan: {differ}; nothing written by this step")
        args = ["--method", w["method"], w["path"]] + (["--input", "-"] if w["body"] is not None else [])
        sent.append(i)   # from here the write may have landed, whatever the answer says
        try:
            answer = gh(*args, body=w["body"])
        except FlipError as exc:
            raise FlipError(f"write {i}/{n} failed: {exc}") from exc
        if i in took and (why := took[i](answer)):
            raise FlipError(f"write {i}/{n} did not take ({why}): {w['method']} {w['path']}; nothing after it was sent")
        print(f"  write {i}/{n} done: {w['method']} {w['path']}")
        settled(repo, branch, expected[i], f"after write {i}/{n}")


def run_flip(a: argparse.Namespace) -> int:
    state = read_state(a.repo, a.branch)
    writes = flip_writes(state)
    dig = digest(state, writes)
    merger_key = read_key_pub(a.key_pub)
    blockers = plan_blockers(state, flip=True, merger_key=merger_key)
    rep_blockers, rep_line = read_report(a.report, a.repo, a.branch)
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
    print(QUIESCENCE)
    if not a.apply:
        return EXIT_OK
    if a.confirm != dig:
        print("REFUSED: --confirm does not match this plan's digest (re-read the plan; the state may have changed)", file=sys.stderr)
        return EXIT_REFUSED
    if not a.quiescent:
        print("REFUSED: " + QUIESCENCE, file=sys.stderr)
        return EXIT_REFUSED
    if all_blockers:
        print("REFUSED: " + "; ".join(all_blockers), file=sys.stderr)
        return EXIT_REFUSED
    saved = save_state(a.state_dir, state, dig)
    print(f"pre-flip state saved: {saved}")
    # the intended states: the confirmed one, the ruleset as the target, then no classic protection
    expect_mid = with_ruleset(state, writes[0]["body"])
    expected = [state, expect_mid, {**expect_mid, "classic": None}]
    def ruleset_took(answer) -> str | None:
        ok = isinstance(answer, dict) and is_target(answer) and answer.get("conditions") == state["ruleset"]["conditions"]
        return None if ok else "the ruleset's answer is not the target"

    sent: list = []
    try:
        execute(a.repo, a.branch, writes, expected, {1: ruleset_took}, sent)
    except BaseException as exc:   # W4: Ctrl-C included — a write sent is a write owned, never a traceback that reads as "refused"
        if not sent:
            print(f"REFUSED: {type(exc).__name__}: {exc}\n  nothing was written; the state file {saved} is unused", file=sys.stderr)
            return EXIT_REFUSED
        print(f"FAILED: {type(exc).__name__}: {exc}\n  restore with: {Path(sys.argv[0]).name} --repo {a.repo} --branch {a.branch} "
              f"--rollback {saved} (plan first, then --apply --confirm <digest> --quiescent)", file=sys.stderr)
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
    # both bodies whole before anything is planned: a hand-edited file must fail here, never between the two writes
    classic_fields = {"required_status_checks", "enforce_admins", "required_pull_request_reviews", "restrictions"}
    if not classic_fields <= set(saved["classic"]):
        raise FlipError(f"{a.rollback}: the saved classic protection lacks {sorted(classic_fields - set(saved['classic']))}")
    if not isinstance(saved["ruleset"], dict) or ruleset_body(saved["ruleset"]) != saved["ruleset"] or not (
            isinstance(saved["ruleset"]["rules"], list) and all(isinstance(r, dict) for r in saved["ruleset"]["rules"])):
        raise FlipError(f"{a.rollback}: the saved ruleset is not a whole ruleset body")
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
    print(QUIESCENCE)
    if not a.apply:
        return EXIT_OK
    if a.confirm != dig:
        print("REFUSED: --confirm does not match this plan's digest", file=sys.stderr)
        return EXIT_REFUSED
    if not a.quiescent:
        print("REFUSED: " + QUIESCENCE, file=sys.stderr)
        return EXIT_REFUSED
    # the intended states: the confirmed live one, the classic protection as saved (never the merge queue back without the
    # checks), then the ruleset as saved
    expect_mid = {**live, "classic": saved["classic"]}
    expected = [live, expect_mid, with_ruleset(expect_mid, saved["ruleset"])]
    def classic_took(answer) -> str | None:
        try:
            back = classic_body(answer) if isinstance(answer, dict) else None
        except FlipError as exc:
            return str(exc)
        return None if same_classic(back, saved["classic"]) else "the classic protection's answer is not as saved"
    def ruleset_back(answer) -> str | None:
        try:
            ok = isinstance(answer, dict) and ruleset_body(answer) == saved["ruleset"]
        except FlipError:
            ok = False
        return None if ok else "the ruleset's answer is not as saved"

    sent: list = []
    try:
        execute(a.repo, a.branch, writes, expected, {1: classic_took, 2: ruleset_back}, sent)
    except BaseException as exc:   # W4
        if not sent:
            print(f"REFUSED: {type(exc).__name__}: {exc}\n  nothing was written", file=sys.stderr)
            return EXIT_REFUSED
        print(f"FAILED: {type(exc).__name__}: {exc}\n  the branch is as the last write left it — still flipped if write 1 did "
              "not take, frozen (classic protection and the key-only ruleset) if it did. The state file is unchanged: "
              f"{a.rollback}\n  re-run: python scripts/localci/phase_e_flip.py --repo {a.repo} --branch {a.branch} --rollback "
              f"{a.rollback} (plan first, then --apply --confirm <digest> --quiescent), or restore its `ruleset` by hand",
              file=sys.stderr)
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
    ap.add_argument("--quiescent", action="store_true", help="the operator declares no session, peer or cron writes rulesets or protection during the run")
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
