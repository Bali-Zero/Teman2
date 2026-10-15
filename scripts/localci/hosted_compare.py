#!/usr/bin/env python3
"""Read-only comparator: a local-CI ``status.json`` beside the HOSTED gate for the same commit.

For every context branch protection requires LIVE, it joins the hosted verdict (check runs and
commit statuses of the run's candidate sha) with the local per-context verdict and names the pair:

    AGREE           both green, or both red
    FALSE_GREEN     local green, hosted red — the one class that makes a local PASS a lie
    FALSE_RED       local red, hosted green
    LOCAL_BLIND     hosted has a verdict, local has none (BLOCKED / UNCOVERED / unmapped)
    HOSTED_PENDING  hosted has no complete verdict from the required source — nothing to compare
    HOSTED_STALE    (B10) the hosted verdict completed BEFORE the base the local run used, and main changed in between in a path
                    the BASE change_map selects for that context: the two sides judged different trees, so the pair is neither an
                    AGREE nor a FALSE_GREEN and is never counted as compared. Decided by a caller-supplied ``stale_judge`` (this
                    module has no git); without one, or when the judge cannot read its evidence, the row keeps its class and says so.
                    (B12b) Also when the hosted RED of a gate-reading context was its reader's PENDING read, given before the gate
                    verdict the local run read (``stale_why: gate_posted_after_hosted``), decided by a caller-supplied ``gate_judge``
    HOSTED_ABORTED  (B27) the hosted RED was a check run cancelled by the job timeout in a SETUP step with no logic step run: no hosted
                    verdict at all, so the pair is never compared. Decided by a caller-supplied ``abort_judge``; without one, or when it
                    cannot read its evidence, the row keeps its class.

The hosted verdict of a context is order-free and RED-DOMINANT: red if ANY entry GitHub lists
under that name for the commit is red (the latest attempt of each check; a red that a re-run
replaced is not listed) (GitHub requires a same-named check and status to both pass, and a
later green from another event does not erase a red); green only when at least one entry from
the REQUIRED source (the pinned ``app_id``, or any source when none is pinned) is complete and
none is pending. The class never reads a timestamp; only the optional ``stale_judge`` (B10) and ``gate_judge`` (B12b) do, from the
``completed_at`` of the entries that decided the verdict (and, for B12b, the statuses' ``updated_at`` and ``state``, the plan's frozen reader answers, and the red runs' annotations and jobs).

Each row carries the context's COVERAGE as the BASE runner recorded it from the BASE matrix (``full``, ``partial`` with its
note, or ``unrecorded`` for a status.json that predates it): the class is the same, but a partial AGREE is an agreement on a
subset and is counted apart (``agreement_full``, ``coverage.compared_partial``), never as a full one.

It also reports DRIFT between the live required names and the names the local run was planned
with, and which required contexts pin no source app. Every GitHub call is a GET through
``gh api <path>``: this module posts nothing and needs no arming. ``--fixtures`` replays a saved
``{"repo", "branch", "sha", "required_checks", "check_runs", "statuses"}`` document offline; a
document for another repo, branch or commit is refused.

Exit 0 = compared, complete · 1 = a FALSE_GREEN or name drift · 2 = unusable input ·
3 = incomplete (a required context is still HOSTED_PENDING: not known yet, never "no failure").
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_REPO = "Bali-Zero/Teman2"
DEFAULT_BRANCH = "main"
CLASSES = ("AGREE", "FALSE_GREEN", "FALSE_RED", "LOCAL_BLIND", "HOSTED_PENDING", "HOSTED_STALE", "HOSTED_ABORTED")
COMPARED = ("AGREE", "FALSE_GREEN", "FALSE_RED")   # a local verdict set beside a hosted one
COVERAGES = ("full", "partial")   # anything else a status.json says (or omits) is "unrecorded", which is never full
# skipped/neutral satisfy a required check on GitHub, so they are green FOR THE GATE; the raw conclusions stay in the row.
HOSTED_GREEN = frozenset({"success", "skipped", "neutral"})
HOSTED_RED = frozenset({"failure", "timed_out", "cancelled", "action_required", "startup_failure", "stale", "error"})
MAX_PAGES = 20

EXIT_OK = 0
EXIT_FOUND = 1
EXIT_BAD_INPUT = 2
EXIT_INCOMPLETE = 3

_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_BRANCH_RE = re.compile(r"^[A-Za-z0-9_./-]+$")


class CompareError(ValueError):
    """The inputs cannot be compared — refuse rather than print a table that looks like evidence."""


def _verdict(conclusion) -> str:
    return "GREEN" if conclusion in HOSTED_GREEN else "RED" if conclusion in HOSTED_RED else "PENDING"


def hosted_entries(check_runs: list, statuses: list) -> dict:
    """Every hosted entry on the commit, grouped by context name (nothing is dropped or ordered)."""
    by: dict = {}
    for run in check_runs:
        concl = run.get("conclusion") if run.get("status") == "completed" else None
        app = run.get("app") if isinstance(run.get("app"), dict) else {}
        by.setdefault(run.get("name"), []).append({"verdict": _verdict(concl), "conclusion": concl, "app_id": app.get("id"), "id": run.get("id"),
                                                   "source": app.get("slug") or "check-run", "completed_at": run.get("completed_at")})
    for st in statuses:
        state = st.get("state")
        by.setdefault(st.get("context"), []).append({"verdict": _verdict(None if state == "pending" else state), "conclusion": state,
                                                     "app_id": None, "id": None, "source": "commit-status", "completed_at": st.get("updated_at")})
    return by


def is_pinned(app_id) -> bool:
    return isinstance(app_id, int) and not isinstance(app_id, bool) and app_id > 0


def superseded_cancelled(entries: list, app_id) -> list:
    """B17: the entries (by identity: an id may be absent) of check runs cancelled by concurrency whose verdict another run decides. A
    cancellation judges nothing, so order does not matter: a cancelled check run is dropped when another check run of the same name on the
    commit (the pinned app's, when the context is pinned) completed with a non-cancelled conclusion, which then decides as usual. A lone
    cancelled run, or one beside pending runs only, is kept."""
    def run(e):
        return e["source"] != "commit-status" and e["conclusion"] is not None

    def same_app(e):
        return e["app_id"] == app_id if is_pinned(app_id) else True

    decided = any(run(o) and o["conclusion"] != "cancelled" and same_app(o) for o in entries)
    return [e for e in entries if decided and run(e) and e["conclusion"] == "cancelled" and same_app(e)]


def b17_answered(entries: list, app_id) -> set:
    """B27 R1: the ids of the cancelled CHECK-RUN entries (of the pinned app, as ``superseded_cancelled`` reads the pin) that ANY
    non-cancelled GREEN check run of the same app answers, in EITHER order (B17: the real #8231 has the green first). The job-timeout test is the caller's."""
    def run(e):
        return e["source"] != "commit-status" and e["conclusion"] is not None

    def same_app(e):
        return e["app_id"] == app_id if is_pinned(app_id) else True

    greens = [g for g in entries if run(g) and g["verdict"] == "GREEN" and same_app(g)]
    return {e["id"] for e in entries if run(e) and e["conclusion"] == "cancelled" and same_app(e) and type(e.get("id")) is int
            and bool(greens)}


def history_cleared(entries: list, app_id, qualified: set, red_ids) -> tuple[bool, str]:
    """B27 R1, the one predicate every path that clears a hosted red goes through. ``entries``: ``hosted_entries(every attempt of the name on the sha,
    plus the sha's commit statuses)[name]`` (all sources, all apps); ``qualified``: the ids of the cancelled check runs that qualify on their own
    (B17 ``b17_answered`` without a timeout, or a B27 setup abort); ``red_ids``: the reds being cleared. Cleared iff ``qualified`` is not empty, every
    red id is in it, no entry is PENDING or in progress, and the entries outside it hold no red of any source or app."""
    ids = set(red_ids)
    is_q = lambda e: e["source"] != "commit-status" and e.get("id") in qualified   # noqa: E731
    if not qualified or not ids or not ids <= qualified:
        return False, "a red is not among the cancelled attempts that qualify"
    if not ids <= {e["id"] for e in entries if e["source"] != "commit-status"}:
        return False, "a red the row stood on is not in the context's history"
    if any(e["verdict"] == "PENDING" for e in entries):
        return False, "an attempt or status of the context is pending or in progress"
    if any(e["verdict"] == "RED" for e in entries if not is_q(e)):
        return False, "the context holds a red outside the qualified cancels (a failed attempt, an unqualified cancel, or a red status)"
    return True, ""


def hosted_verdict(entries: list, app_id) -> dict:
    dropped = superseded_cancelled(entries, app_id)
    seen = [e for e in entries if not any(e is d for d in dropped)]
    counted = [e for e in seen if not is_pinned(app_id) or e["app_id"] == app_id]
    if any(e["verdict"] == "RED" for e in seen):
        verdict = "RED"
    elif not counted or any(e["verdict"] == "PENDING" for e in counted):
        verdict = "PENDING"
    else:
        verdict = "GREEN"
    decisive = [e for e in seen if e["verdict"] == "RED"] if verdict == "RED" else counted   # the entries that made the verdict
    stamps = [e.get("completed_at") for e in decisive]
    when = max(stamps) if verdict != "PENDING" and stamps and all(isinstance(t, str) and _TS_RE.match(t) for t in stamps) else None
    return {"verdict": verdict, "entries": len(entries), "counted": len(counted), "sources": sorted({e["source"] for e in entries}),
            "conclusions": sorted({str(e["conclusion"]) for e in entries}), "completed_at": when,
            "red": [{"id": e.get("id"), "conclusion": e.get("conclusion"), "completed_at": e.get("completed_at")}
                    for e in seen if e["verdict"] == "RED"],   # B12b: a status has no id
            "superseded_cancelled": [e.get("id") for e in dropped]}


def local_verdicts(status: dict) -> dict:
    """GREEN / RED only where the runner recorded a per-context verdict; everything else is BLIND."""
    ctx = status.get("contexts")
    ctx = ctx if isinstance(ctx, dict) else {}
    results = ctx.get("results")
    results = results if isinstance(results, dict) else {}
    usable = ctx.get("status") == "ok"
    out = {}
    for name, res in results.items():
        res = res if isinstance(res, dict) else {}
        verdict, cov = res.get("verdict"), res.get("coverage")
        out[name] = {"verdict": ("GREEN" if verdict == "OK" else "RED" if verdict == "FAIL" else "BLIND") if usable else "BLIND",
                     "detail": f"{verdict}" + (f" ({res.get('mapping')})" if res.get("mapping") else "")
                               + (f" {res['no_verdict']}" if isinstance(res.get("no_verdict"), str) else ""),   # host_disk_full: blind, never red
                     "coverage": cov if cov in COVERAGES else "unrecorded",
                     "coverage_note": res.get("coverage_note") if isinstance(res.get("coverage_note"), str) else None,
                     "skipped": res.get("skipped") if isinstance(res.get("skipped"), str) and verdict == "OK" else None}
    return out


def skip_reading(lo: dict, h: dict) -> dict:
    """What a skip on either side makes of a row (B5). Both skipped: the classifier's decision is compared, a full comparison,
    labelled as a skip. Skipped here, run hosted: the local verdict is a subset of hosted's, partial and named. Run here, skipped
    hosted: more was tested here, full. A skip is never labelled `OK (executed)`."""
    hosted_skipped = h["verdict"] == "GREEN" and h["conclusions"] == ["skipped"]
    if lo.get("skipped"):
        if hosted_skipped:
            return {"skip": "agreed", "local_detail": f"NOT_APPLICABLE (skip agreed: {lo['skipped']})", "coverage": "full", "coverage_note": None}
        if h["verdict"] != "PENDING":
            return {"skip": "hosted_ran", "local_detail": "NOT_APPLICABLE (skipped here; hosted ran)", "coverage": "partial",
                    "coverage_note": f"skipped here by the trusted {lo['skipped']} while hosted ran it: the local verdict is a subset of hosted's"}
        return {"skip": None, "local_detail": f"NOT_APPLICABLE (skipped here: {lo['skipped']})"}
    if hosted_skipped and lo["verdict"] in ("GREEN", "RED") and lo["detail"].endswith(")"):
        return {"skip": "hosted_skipped", "local_detail": lo["detail"][:-1] + "; hosted skipped)"}
    return {"skip": None}


def classify(local: str, hosted: str) -> str:
    if hosted == "PENDING":
        return "HOSTED_PENDING"
    if local == "BLIND":
        return "LOCAL_BLIND"
    if local == hosted:
        return "AGREE"
    return "FALSE_GREEN" if local == "GREEN" else "FALSE_RED"


def required_names(required_checks) -> list[str]:
    if not isinstance(required_checks, list) or not required_checks:
        raise CompareError("no required checks were read — an empty required set is a failed read, not a clean gate")
    names = [c.get("context") if isinstance(c, dict) else None for c in required_checks]
    if any(not isinstance(n, str) or not n.strip() for n in names):
        raise CompareError("a required check has no context name — refusing to skip it")
    if len(set(names)) != len(names):
        raise CompareError("the required set names a context twice")
    return names  # type: ignore[return-value]


def stale_reading(judge, name: str, completed_at) -> dict:
    """B10: what ``judge(name, completed_at)`` makes of one compared row. Total: a judge that cannot read its evidence, raises, or
    answers in any other shape gives ``stale_check: unknown (<why>)`` and the row keeps its class — an absence of proof never hides a red."""
    base = {"hosted_completed_at": completed_at, "hosted_main": None, "main_moved_paths": [], "main_moved_count": 0}
    if not isinstance(completed_at, str):
        return {**base, "stale": None, "stale_check": "unknown (the hosted verdict carries no readable completed_at)"}
    try:
        got = judge(name, completed_at)
        stale = got.get("stale")
        if stale not in (True, False, None):
            raise CompareError(f"the judge answered stale={stale!r}")
    except Exception as exc:  # noqa: BLE001 — see the docstring
        return {**base, "stale": None, "stale_check": f"unknown ({type(exc).__name__}: {str(exc)[-200:]})"}
    if stale is None:
        return {**base, "stale": None, "stale_check": f"unknown ({str(got.get('why'))[-300:]})"}
    return {**base, "stale": stale, "stale_check": "stale" if stale else "fresh", "hosted_main": got.get("hosted_main"),
            "main_moved_paths": list(got.get("main_moved_paths") or [])[:20], "main_moved_count": int(got.get("main_moved_count") or 0)}


def gate_reading(judge, name: str, h: dict, statuses: list) -> dict:
    """B12b: what ``judge(name, hosted, statuses)`` makes of one compared row: was its hosted RED the gate reader's PENDING read, given before
    the gate verdict the local run read? The judge answers None when the ground does not apply (no field is added). Total like
    ``stale_reading``: a judge that raises or answers in any other shape gives ``gate_check: unknown (<why>)`` and the row keeps its class."""
    try:
        got = judge(name, h, statuses)
        if got is None:
            return {}
        stale = got.get("stale")
        if stale not in (True, False, None):
            raise CompareError(f"the gate judge answered stale={stale!r}")
    except Exception as exc:  # noqa: BLE001 — see the docstring
        return {"gate_check": f"unknown ({type(exc).__name__}: {str(exc)[-200:]})"}
    if stale is not True:
        return {"gate_check": f"{'unknown' if stale is None else 'fresh'} ({str(got.get('why'))[-300:]})"}
    return {"stale": True, "gate_check": "stale", "stale_check": "stale", "stale_why": "gate_posted_after_hosted",
            "hosted_completed_at": h["completed_at"], "gate_posted_at": got.get("gate_posted_at"), "plan_at": got.get("plan_at")}


def abort_reading(judge, name: str, h: dict, statuses: list, app_id) -> dict:
    """B27: what ``judge(name, hosted, statuses, app_id)`` makes of one compared row whose hosted verdict is RED: did every red run die in a setup step with no
    logic step run? The judge answers None when the ground does not apply (nothing is added). Total like ``gate_reading``: a judge that raises
    or answers in any other shape gives ``abort_check: unknown (<why>)`` and the row keeps its class."""
    try:
        got = judge(name, h, statuses, app_id)
        if got is None:
            return {}
        aborted = got.get("aborted")
        if aborted not in (True, False):
            raise CompareError(f"the abort judge answered aborted={aborted!r}")
        if aborted and not (isinstance(got.get("runs"), list) and got["runs"]):
            raise CompareError("the abort judge named no run")
    except Exception as exc:  # noqa: BLE001 — see the docstring
        return {"abort_check": f"unknown ({type(exc).__name__}: {str(exc)[-200:]})"}
    if not aborted:
        return {"abort_check": f"fresh ({str(got.get('why'))[-300:]})"}
    return {"aborted": True, "abort_check": "aborted", "aborted_runs": got["runs"]}


def with_gate(reading: dict, gate: dict) -> dict:
    """B10's reading and B12b's on one row: stale when either ground is, else unknown when either is, else fresh; with no B10 reading
    (no ``stale_judge``), what the gate judge said and nothing it did not."""
    if not gate or gate.get("stale") is True:
        return {**reading, **gate}
    if "stale_check" not in reading:   # no B10 judge ran: the row's stale_check is the gate judge's word alone
        return {**reading, "gate_check": gate["gate_check"], "stale_check": gate["gate_check"]}
    prior = str(reading["stale_check"])
    return {**reading, "gate_check": gate["gate_check"],
            "stale_check": gate["gate_check"] if gate["gate_check"].startswith("unknown") and not prior.startswith("unknown") else prior}


def comparison_view(h: dict, entries: list, cancel_timeout) -> dict:
    """B27 R3: the hosted verdict as the COMPARISON reads it (the class and counts READY rests on), where a superseded cancel that carries the job-timeout
    annotation is red again, like a failure: ``hosted_verdict`` itself, which feeds mergeability, is left as GitHub's required-check semantics have it.
    ``cancel_timeout(id) -> bool`` reads the annotations; with none, or a read that raises, the cancel stays red (fail closed)."""
    dropped = [e for e in entries if e.get("id") in h["superseded_cancelled"] and e["source"] != "commit-status"]
    restored = []
    for e in dropped:
        try:
            timeout = True if cancel_timeout is None else bool(cancel_timeout(e["id"]))
        except Exception:  # noqa: BLE001 — an unreadable annotation list keeps the cancel red
            timeout = True
        if timeout:
            restored.append(e)
    if not restored:
        return h
    red = h["red"] + [{"id": e.get("id"), "conclusion": e.get("conclusion"), "completed_at": e.get("completed_at")} for e in restored]
    stamps = [r["completed_at"] for r in red]
    return {**h, "verdict": "RED", "red": red, "superseded_cancelled": [i for i in h["superseded_cancelled"] if i not in {e["id"] for e in restored}],
            "completed_at": max(stamps) if all(isinstance(t, str) and _TS_RE.match(t) for t in stamps) else None}


def compare(status: dict, required_checks, check_runs, statuses, stale_judge=None, gate_judge=None, abort_judge=None, cancel_timeout=None) -> dict:
    names = required_names(required_checks)
    if not isinstance(check_runs, list) or not isinstance(statuses, list) or any(not isinstance(x, dict) for x in check_runs + statuses):
        raise CompareError("check_runs / statuses are not lists of objects")
    hosted, local = hosted_entries(check_runs, statuses), local_verdicts(status)
    rows = []
    for chk in required_checks:
        name, app_id = chk["context"], chk.get("app_id")
        h = comparison_view(hosted_verdict(hosted.get(name, []), app_id), hosted.get(name, []), cancel_timeout)   # B27 R3
        lo = local.get(name, {"verdict": "BLIND", "detail": "unmapped", "coverage": "unrecorded", "coverage_note": None})
        klass = classify(lo["verdict"], h["verdict"])
        reading = stale_reading(stale_judge, name, h["completed_at"]) if stale_judge is not None and klass in COMPARED else {}
        if gate_judge is not None and klass in COMPARED and reading.get("stale") is not True:
            reading = with_gate(reading, gate_reading(gate_judge, name, h, statuses))
        if reading.get("stale") is True:
            reading["class_before"], klass = klass, "HOSTED_STALE"   # every compared class: a stale GREEN beside a local GREEN is no AGREE either
        if abort_judge is not None and klass in COMPARED and h["verdict"] == "RED" and reading.get("stale") is not True:
            reading = {**reading, **abort_reading(abort_judge, name, h, statuses, app_id)}
            if reading.get("aborted") is True:   # B27: no hosted verdict ran, so no compared class either
                reading["class_before"], klass = klass, "HOSTED_ABORTED"
        reading.pop("stale", None)
        reading.pop("aborted", None)
        rows.append({**reading, "context": name, "class": klass, "hosted": h["verdict"], "hosted_entries": h["entries"],
                     "hosted_counted": h["counted"], "hosted_sources": h["sources"], "hosted_conclusions": h["conclusions"],
                     "local": lo["verdict"], "local_detail": lo["detail"], "coverage": lo["coverage"], "coverage_note": lo["coverage_note"],
                     "app_id": app_id, "source_pinned": is_pinned(app_id), **skip_reading(lo, h),
                     **({"hosted_red": h["red"]} if h["verdict"] == "RED" else {}),   # B12b: the report finds these very runs again
                     **({"superseded_cancelled": h["superseded_cancelled"]} if h["superseded_cancelled"] else {})})   # B17: what the verdict dropped
    counts = {k: sum(1 for r in rows if r["class"] == k) for k in CLASSES}
    compared = [r for r in rows if r["class"] in COMPARED]
    coverage = {"compared_full": sum(1 for r in compared if r["coverage"] == "full"),
                "compared_partial": [r["context"] for r in compared if r["coverage"] == "partial"],
                "compared_unrecorded": [r["context"] for r in compared if r["coverage"] not in COVERAGES],
                "compared_skip_agreed": [r["context"] for r in compared if r["skip"] == "agreed"]}   # full, and counted apart
    return {"candidate_sha": status.get("candidate_sha"), "run_id": status.get("run_id"), "local_overall": status.get("overall"),
            "required": len(rows), "rows": rows, "counts": counts, "agreement": f"{counts['AGREE']}/{len(rows)}",
            "agreement_full": f"{sum(1 for r in compared if r['class'] == 'AGREE' and r['coverage'] == 'full')}/{len(rows)}", "coverage": coverage,
            "drift": {"missing_locally": sorted(n for n in names if n not in local), "stale_locally": sorted(n for n in local if n not in names)},
            "unpinned_source": [r["context"] for r in rows if not r["source_pinned"]]}


def exit_code(report: dict) -> int:
    if report["counts"]["FALSE_GREEN"] or report["drift"]["missing_locally"] or report["drift"]["stale_locally"]:
        return EXIT_FOUND
    return EXIT_INCOMPLETE if report["counts"]["HOSTED_PENDING"] else EXIT_OK


def gh_argv(path: str) -> list[str]:
    return ["gh", "api", path]


class GhError(CompareError):
    def __init__(self, msg: str, stderr: str = ""):
        super().__init__(msg)
        self.stderr = stderr


def gh_get(path: str):
    res = subprocess.run(gh_argv(path), capture_output=True, text=True)
    if res.returncode != 0:
        raise GhError(f"gh api {path} failed (rc={res.returncode}): {res.stderr.strip()[-200:]}", res.stderr)
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError as exc:
        raise CompareError(f"gh api {path} returned no JSON: {exc}") from exc


def _paged(path: str, key: str) -> list:
    out: list = []
    for page in range(1, MAX_PAGES + 1):
        doc = gh_get(f"{path}?per_page=100&page={page}")
        batch = doc.get(key) if isinstance(doc, dict) else None
        if not isinstance(batch, list):
            raise CompareError(f"gh api {path}: page {page} carries no `{key}` list")
        out += batch
        if len(batch) < 100:
            return out
    raise CompareError(f"gh api {path}: more than {MAX_PAGES} pages of `{key}` — refusing a truncated comparison")


# The flipped state phase_e_flip.py writes, restated here because the tick wrapper extracts only a handful of files into the
# code dir (localci_merger_tick.sh): importing phase_e_flip.py would raise FileNotFoundError exactly after the flip.
# tests/test_required_set.py pins every constant and both predicates to phase_e_flip.py's.
FLIP_RULESET = "merge-queue-main"
FLIP_RULES = [{"type": "update", "parameters": {"update_allows_fetch_and_merge": False}}]
FLIP_BYPASS = [{"actor_id": None, "actor_type": "DeployKey", "bypass_mode": "always"}]
NOT_PROTECTED = "Branch not protected"
_GLOB = re.compile(r"[*?\[]")
_CACHE: dict = {}   # per process; keyed by the gh reader too, so a replaced reader never sees another's answers


def is_flipped_ruleset(rs, branch: str, default_branch) -> bool:
    """The flipped ruleset by meaning: enforced, one ``update`` rule allowing no fetch-and-merge, the DeployKey the one bypass actor,
    always, and the branch included by name and excluded by nothing."""
    if not isinstance(rs, dict):
        return False
    rules, bypass = rs.get("rules") or [], rs.get("bypass_actors") or []
    ref = (rs.get("conditions") or {}).get("ref_name") or {}
    names = {f"refs/heads/{branch}", "~ALL", *(["~DEFAULT_BRANCH"] if branch == default_branch else [])}
    exclude = ref.get("exclude") or []
    return (rs.get("name") == FLIP_RULESET and rs.get("target") == "branch" and rs.get("enforcement") == "active"
            and len(rules) == 1 and rules[0].get("type") == "update"
            and (rules[0].get("parameters") or {}).get("update_allows_fetch_and_merge") is False
            and len(bypass) == 1 and bypass[0].get("actor_type") == "DeployKey" and bypass[0].get("bypass_mode") == "always"
            and bool(names & set(ref.get("include") or [])) and not names & set(exclude) and not any(_GLOB.search(x) for x in exclude))


def _flipped(repo: str, branch: str) -> bool:
    """True only when the repository has exactly one ``merge-queue-main`` ruleset and it is the flipped one. Any other state is False;
    an unreadable one raises."""
    named: list = []
    for page in range(1, MAX_PAGES + 1):
        batch = gh_get(f"repos/{repo}/rulesets?per_page=100&page={page}")
        if not isinstance(batch, list):
            raise CompareError("the rulesets list is not a list")
        named += [r for r in batch if isinstance(r, dict) and r.get("name") == FLIP_RULESET and r.get("source_type", "Repository") == "Repository"]
        if len(batch) < 100:
            break
    else:
        raise CompareError(f"more than {MAX_PAGES} pages of rulesets — refusing a truncated read")
    if len(named) != 1 or not isinstance(named[0].get("id"), int):
        return False
    rs = gh_get(f"repos/{repo}/rulesets/{named[0]['id']}")
    default = gh_get(f"repos/{repo}").get("default_branch")
    return is_flipped_ruleset(rs, branch, default)


def matrix_required(text) -> list[dict]:
    """The required set a BASE matrix declares: one ``{context, app_id}`` per context, ``app_id`` from the matrix's ``required_app_id``
    (None: any source), as protection lists them."""
    import yaml
    try:
        contexts = yaml.safe_load(text)["contexts"]
        checks = [{"context": c["name"], "app_id": c.get("required_app_id")} for c in contexts]
    except (ValueError, KeyError, TypeError, AttributeError, yaml.YAMLError) as exc:
        raise CompareError(f"the BASE matrix is unreadable: {exc}") from exc
    if any(c["app_id"] is not None and not is_pinned(c["app_id"]) for c in checks):
        raise CompareError("the BASE matrix carries a required_app_id that is not a positive integer")
    required_names(checks)
    return checks


def required_set(repo: str, branch: str, base=None) -> tuple[list | None, str]:
    """(required checks, source): protection when it is there; the BASE matrix only when GitHub says the branch has no protection
    AND the flipped ruleset is in force. ``base`` is ``(ref, reader)``: the decision's own BASE ref and a callable returning the matrix
    text at that ref from the merger's mirror; without it the matrix path fails closed. Every other failure raises. The protection
    and ruleset reads are made once per (repo, branch) per process, the matrix once per ref."""
    key = (gh_get, repo, branch)
    if key not in _CACHE:
        try:
            protection = gh_get(f"repos/{repo}/branches/{branch}/protection/required_status_checks")
            _CACHE[key] = ("protection", protection.get("checks") if isinstance(protection, dict) else None)
        except GhError as exc:
            if NOT_PROTECTED not in exc.stderr or "(HTTP 404)" not in exc.stderr or not _flipped(repo, branch):
                raise
            _CACHE[key] = ("matrix_after_flip", None)
    source, checks = _CACHE[key]
    if source == "protection":
        return checks, source
    if not (isinstance(base, tuple) and len(base) == 2 and isinstance(base[0], str) and base[0] and callable(base[1])):
        raise CompareError("the branch has no protection and this decision names no BASE ref to read the required set from")
    mkey = (*key, base[0])
    if mkey not in _CACHE:
        try:
            text = base[1]()
        except Exception as exc:  # noqa: BLE001 — a blob that cannot be read is no required set
            raise CompareError(f"the BASE matrix at {base[0][:12]} is unreadable: {type(exc).__name__}") from exc
        _CACHE[mkey] = matrix_required(text)
    return _CACHE[mkey], source


def fetch_live(repo: str, branch: str, sha: str, base=None) -> dict:
    required, source = required_set(repo, branch, base)
    pins = None if source == "protection" else ("present" if any(c["app_id"] for c in required) else "absent_at_base")   # R5, named
    return {"repo": repo, "branch": branch, "sha": sha, "required_checks": required, "required_source": source, "pins": pins,
            "check_runs": _paged(f"repos/{repo}/commits/{sha}/check-runs", "check_runs"),
            "statuses": _paged(f"repos/{repo}/commits/{sha}/status", "statuses")}


def bound_to(live, repo: str, branch: str, sha: str) -> dict:
    """A hosted document counts only for the repo, branch and commit it says it was read from."""
    if not isinstance(live, dict):
        raise CompareError("the hosted document is not a JSON object")
    for key, want in (("repo", repo), ("branch", branch), ("sha", sha)):
        if live.get(key) != want:
            raise CompareError(f"the hosted document is bound to {key}={live.get(key)!r}, this comparison needs {want!r}")
    runs = live.get("check_runs")
    if isinstance(runs, list) and any(isinstance(r, dict) and r.get("head_sha") not in (None, sha) for r in runs):
        raise CompareError("a check run in the hosted document belongs to another commit")
    return live


def render(report: dict) -> str:
    lines = [f"{'CLASS':15} {'HOSTED':10} {'LOCAL':6} {'PIN':4} {'COVERAGE':10} CONTEXT"]
    for r in report["rows"]:
        hosted = f"{r['hosted']}({r['hosted_entries']})"
        lines.append(f"{r['class']:15} {hosted:10} {r['local']:6} {'app' if r['source_pinned'] else 'any':4} {r['coverage']:10} {r['context']}  "
                     f"[{r['local_detail']}]")
    c, d, cov = report["counts"], report["drift"], report["coverage"]
    lines.append(f"source={report['source']} sha={str(report['candidate_sha'])[:12]} local_overall={report['local_overall']} "
                 f"required={report['required']} agreement={report['agreement']} " + " ".join(f"{k.lower()}={c[k]}" for k in CLASSES[1:]))
    lines.append(f"coverage: agreement_full={report['agreement_full']} compared_full={cov['compared_full']} "
                 f"compared_partial={len(cov['compared_partial'])} {cov['compared_partial']} compared_unrecorded={len(cov['compared_unrecorded'])} "
                 f"compared_skip_agreed={len(cov['compared_skip_agreed'])} {cov['compared_skip_agreed']} "
                 f"(a partial or unrecorded comparison is shown, never counted as a full one)")
    lines.append(f"drift: missing_locally={d['missing_locally']} stale_locally={d['stale_locally']} | "
                 f"unpinned_source={len(report['unpinned_source'])}/{report['required']}")
    return "\n".join(lines)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Read-only comparator: a local-CI status.json beside the hosted gate for the same commit.")
    ap.add_argument("status", type=Path, help="path to a local-CI status.json")
    ap.add_argument("--repo", default=DEFAULT_REPO, help=f"owner/name (default {DEFAULT_REPO})")
    ap.add_argument("--branch", default=DEFAULT_BRANCH, help=f"protected branch whose required set is read (default {DEFAULT_BRANCH})")
    ap.add_argument("--fixtures", type=Path, default=None, help="replay a saved hosted document (bound to repo, branch and sha) instead of calling gh")
    ap.add_argument("--out", type=Path, default=None, help="directory for hosted_compare.json (default: the status.json's directory)")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    out_dir = args.out if args.out is not None else args.status.parent
    if (out_dir / "state" / "plan.json").exists():   # B27 R4: this CLI has no annotation reader; a merger run dir's hosted_compare.json is the tick's evidence
        print(f"hosted_compare: refusing — {out_dir} is a merger run dir (state/plan.json); pass --out elsewhere", file=sys.stderr)
        return EXIT_BAD_INPUT
    try:
        status = json.loads(args.status.read_text())
        if not isinstance(status, dict):
            raise CompareError("status.json is not a JSON object")
        sha = status.get("candidate_sha")
        if not isinstance(sha, str) or not _SHA_RE.match(sha):
            raise CompareError("candidate_sha is missing or not a full 40-hex sha")
        if not _REPO_RE.match(args.repo) or not _BRANCH_RE.match(args.branch):
            raise CompareError(f"repo {args.repo!r} / branch {args.branch!r} is not a plain owner/name and branch")
        live = json.loads(args.fixtures.read_text()) if args.fixtures else fetch_live(args.repo, args.branch, sha)
        live = bound_to(live, args.repo, args.branch, sha)
        report = compare(status, live.get("required_checks"), live.get("check_runs"), live.get("statuses"))
    except (OSError, json.JSONDecodeError, CompareError) as exc:
        print(f"hosted_compare: refusing — {exc}", file=sys.stderr)
        return EXIT_BAD_INPUT
    report.update(source="fixtures" if args.fixtures else "live", repo=args.repo, branch=args.branch)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "hosted_compare.json").write_text(json.dumps(report, indent=2) + "\n")
    print(render(report))
    return exit_code(report)


if __name__ == "__main__":
    sys.exit(main())
