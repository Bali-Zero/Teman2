#!/usr/bin/env python3
"""Turn one probe run into HISTORY, and answer the one question MANDATE §8 asks.

MANDATE §8: "A topic is current when ... the probe suite for that topic is green
against production **and has stayed green for 48h under the scheduled job**. Point
four is the only one that proves the other three." Until this file existed there
was no scheduled job and nothing recorded a run's outcome anywhere — so "stayed
green for 48h" was unmeasurable by construction, no matter how many times a lane
ran `probe_retrieval.py` by hand. This file is the ledger and the question-answerer.

TWO SUBCOMMANDS

  record   Runs `probe_retrieval.py --json` for every `kb/journeys/*.yaml` found on
           disk right now, and appends ONE line per topic to the history file
           (default `kb/ops/probe_history.jsonl`, gitignored — this is per-machine
           runtime state, the same class as the DLQ/heartbeat files this repo
           already keeps out of git).

  status   Reads the history file and answers, per topic, exactly the question
           §8 asks: has this topic been continuously at target for 48 hours? Never
           invents an answer from a single record — the answer is a computed
           streak with the evidence printed alongside it, never asserted alone.

SEVEN WAYS THIS COULD LIE, AND HOW EACH IS CLOSED (read this before touching the
streak logic — the guilt/innocence matrix in the test file exists to keep these
seven true, not merely once, forever):

(a) THE STREAK MUST NOT SURVIVE AN EDIT TO ANY OF THE THREE ARTIFACTS MANDATE §8
    ACTUALLY NAMES. §8 defines "current" over `kb/journeys/<topic>.yaml` (the
    probe), `kb/topics/<topic>.yaml` (the per-document legal_status mark and
    instrument roster), AND `kb/inventory/<topic>.yaml` (point counts and
    supersession dates) — "every in-force instrument present under its correct
    identity and whole, every superseded one marked, the inventory listing both
    sets with dates, AND the suite green 48h." A streak that only watches the
    journeys file certifies a claim the other two artifacts can quietly withdraw:
    mark a superseded law back to in-force in `kb/topics/`, or edit a point count
    in `kb/inventory/`, on day 2 of a streak, and a journeys-only hash would never
    move. So every record carries the sha256 of ALL THREE files' bytes AT THE TIME
    OF THAT RUN (`artifact_shas`; a missing topics/inventory file hashes to the
    fixed sentinel `MISSING_SHA`, which cannot collide with a real sha256 by
    construction — so a file's first appearance is itself counted as a change).
    `status` computes the CURRENT triple and only counts records whose triple
    matches it, in full, towards the live streak. Change ANY of the three — or
    merely reorder two lines in one of them — and that artifact's sha changes,
    every prior record stops counting, and the 48h clock restarts at zero.
    Without this, "make the suite pass" and "make the suite (or its supporting
    facts) easier" are indistinguishable to this file, and the second is a
    straight reward-hacking path to a green ledger with no work behind it. This
    is the single most important rule here.

(b) AN EMPTY RUN MUST NOT READ AS SUCCESS. Zero `kb/journeys/*.yaml` files, or a
    file that declares zero journeys inside it (which `probe_retrieval.py` itself
    reports as its own `broken`/`no_journeys` case), is recorded as the verdict
    `nothing_measured` — a member of this file's OWN closed vocabulary, never
    `at_target`, and `record` does not exit 0 when EVERY topic it looked at ended
    up `nothing_measured`. As of 2026-08-25 `kb/journeys/` holds only `.gitkeep`,
    so this is not a hypothetical: it is the exact state this file ships in, and
    `record`/`status` are exercised against it below (see module-level smoke
    invocation note in the test file).

(c) BROKEN MUST NOT COUNT AS ANYTHING TOWARD THE STREAK ITSELF. A run where
    `probe_retrieval.py`'s own control query failed graded nothing about the
    topic — it is an absence of evidence about the corpus, not evidence of
    anything. `broken` records are therefore dropped OUT of the streak timeline
    entirely before the streak is walked: they neither extend a run of
    `at_target` records (they prove nothing good happened) nor break one (they
    prove nothing bad happened either) DECIDED HERE, not left implicit — see
    `_streak` and the deliberate `verdict != "broken"` filter at its top. What
    they DO affect is visibility: `status` reports how many broken runs sit
    inside the window, because a topic whose "streak" is propped up by three
    broken runs in a row is not the same claim as one with 20 clean at_target
    runs, even if both currently answer "yes, 48h". See (e) for what a broken
    verdict means to `record`'s OWN exit code, which is a different question
    answered by a different function.

(d) A GAP IN THE RECORD MUST BREAK THE STREAK. If the scheduled job did not run for
    longer than `MAX_GAP_HOURS`, the evidence has a hole, whatever the two records
    on either side say. The threshold is `24` — not invented for this file, but
    reused from MANDATE §7's own dead-man-switch declaration for this exact probe
    ("Dead-man switch: probe silent 24h → alert"). A gap check also applies between
    the most recent gradable record and NOW: a topic whose last real measurement
    is 30 hours old is not "currently" anything, it is stale, and `status` says so
    explicitly rather than reporting a stopped clock as if it were still ticking.

(e) `record`'S EXIT CODE MUST NOT GO GREEN ON A PARTIAL RUN. This is a distinct
    question from (c): (c) is about what a `broken` record contributes to a
    topic's own 48h streak (nothing, in either direction, once its sha still
    matches). This point is about what `cmd_record` itself reports to whatever
    is watching its exit code — a scheduler, a dead-man-switch, an operator's
    shell. The evasion this closes: set one journey's `collection:` to a name
    the registry does not define. `probe_retrieval.py` correctly refuses
    (`verdict: broken`, exit 3, nothing graded for that topic) — and the OLD
    `cmd_record` still exited 0, because its own definition of "measured
    something" was "any verdict other than nothing_measured", and `broken`
    satisfied that. DECISION: `broken` is an absence of evidence exactly as (c)
    says, so `record` exits 0 only when EVERY topic this run looked at produced
    a real graded verdict (`at_target` / `drift` / `outstanding`) — never when
    even ONE topic came back broken, whether that topic is the only one found
    (all-broken) or one of several (mixed). The mixed case is the one worth
    justifying explicitly, because the graded topics in a mixed run genuinely
    WERE measured and their records ARE written to history exactly as they
    would be on a fully clean run — only the process's own exit code goes
    non-zero. The alternative (exit 0 whenever at least one topic graded) is
    the exact silent-disappearance failure this fix exists to close: a topic
    whose `collection:` typo'd two months ago would keep coming back broken
    forever while three healthy neighbours kept the scheduled job green, and
    nobody watching only the exit code would ever find out. `broken` is
    therefore treated as record()'s own guilt signal, not folded into "at least
    one thing worked" — a topic that could not be measured is not allowed to
    hide behind the topics that could. `cmd_record`'s `graded` list also
    excludes `degraded_path` records for exactly this reason — see (f), which
    is where that half of the rule is justified; an all-`degraded_path` run
    used to satisfy this same `graded` check because it checked only the
    verdict field, so a run with zero production-path evidence still exited 0.

(f) A `degraded_path` RUN MUST NOT BE ABLE TO EARN THE CERTIFICATE ON ITS OWN.
    `probe_retrieval.py` sets `degraded_path: true` when this environment's
    `google-genai` is off the version the lock file pins, which makes Gemini
    query expansion raise and get silently swallowed — retrieval still runs,
    still produces verdicts, but WITHOUT multilingual expansion, and the
    probe's own banner calls those verdicts "a LOWER BOUND on what production
    retrieves, never an upper one." MANDATE §8 asks for "green against
    production" — not against a narrower path the probe itself refuses to call
    equivalent. DECISION (the more conservative of two defensible answers, and
    the one this file takes): a `degraded_path` record is treated exactly like
    a `broken` one for streak purposes — dropped out of the gradable timeline
    entirely, neither extending nor breaking a run, tracked separately as
    `degraded_runs_in_window` so `status` never hides the fact from whoever
    reads it. The REJECTED alternative — trust a degraded `at_target` because
    a narrower search is logically a subset of production's, so anything it
    finds production would find too — is not adopted here even though the
    logic has a real appeal: it depends on query expansion being strictly
    additive for every journey, which this file has no way to verify without
    running the real path, and a certificate MANDATE §8 calls "against
    production" should not rest on an inference about a path production does
    not use. A degraded `outstanding`/`drift` was already untrustworthy either
    way (expansion could have found what the narrower path missed); treating
    degraded uniformly, regardless of which verdict it produced, keeps one
    rule instead of a verdict-dependent one and removes an entire axis of
    "was this the good kind of degraded or the bad kind" from the streak logic.

    This is a DIFFERENT question from `cmd_record`'s own exit code, the same
    way (c) and (e) are different questions about `broken` — and it has the
    same answer. An all-`degraded_path` run, even with verdict `at_target` on
    every topic, must not exit 0 at the job/scheduler level either: `graded`
    in `cmd_record` excludes `degraded_path` records exactly as `gradable` in
    `_streak` does, for the identical reason — a lower bound is not "green
    against production." Without this, the day this environment's
    `google-genai` drifts off the lock file's pin, the scheduled job keeps
    reporting success while `_streak` (correctly) never advances the 48h
    clock — a scheduler-green, streak-frozen split that nobody watching only
    the job's exit code would ever notice, for as long as the version stays
    drifted.

(g) `record` MUST ACTUALLY RE-MEASURE THE INVENTORY, NOT JUST HASH IT. Rule (a)
    resets the streak the moment `kb/inventory/<topic>.yaml`'s BYTES change —
    but a sha256 only answers "did we change our own claim", never "is our
    claim still true". Until this rule, `cmd_record` imported
    `probe_retrieval.py` (19 references) and never once called
    `scripts/kb/kb_inventory_probe.py` — the one script that actually queries
    live Qdrant and compares it to what the inventory recorded. So if
    PRODUCTION drifted (a point count moved, a payload shape mix changed)
    while the inventory FILE sat untouched, nothing here would ever notice:
    the sha stays constant, the streak keeps ticking, and the "measured
    against production" claim MANDATE §1/§8 makes about that inventory quietly
    stops being true without a single record ever saying so. Found by a
    completeness reviewer as the same question Guard 6 already answers for a
    different absence — "what does `cmd_record` consider a measurement".
    DECISION: every topic's `kb/inventory/<topic>.yaml` is now run through
    `kb_inventory_probe.py --json` (kind: topic; kind: retired_collection has
    no `--json` support yet, out of THIS file's scope to add — see that
    script's own docstring) inside the SAME per-topic loop that already runs
    `probe_retrieval.py`, and its verdict is recorded as `inventory_verdict` —
    a SEPARATE field from `verdict`, deliberately never AND'd into one
    collapsed value: an `at_target` retrieval verdict sitting next to a
    `drift` inventory verdict are two different facts about the SAME topic,
    and folding them into one boolean would lose exactly the distinction that
    makes the failure diagnosable. `cmd_record`'s exit code goes non-zero on
    `inventory_verdict in ("broken", "drift")` the same way it already does
    for a broken/degraded retrieval verdict — named separately in the PARTIAL
    message, never merged into "broken"/"degraded" language, so an operator
    reading cron output learns WHICH half of the measurement failed.
    NOT DONE HERE, and named honestly rather than silently left half-fixed:
    `_streak`/`cmd_status`'s 48h certificate does not yet drop a topic's
    streak on `inventory_verdict == "drift"` the way it already does for a
    broken/degraded retrieval verdict — MANDATE §8's "green against
    production, stayed green 48h" is a claim about the SAME 48h window for
    both dimensions, and this fix closes only `record`'s own exit code, not
    yet `status`'s certificate. A topic could therefore show
    `AT-TARGET-48H` today while its most recent inventory_verdict is `drift`,
    as long as the JOB itself still exited non-zero on that same run (rules
    (e)/(g) both fire, but only (e)/(f)'s records feed the streak walk today).
    Tracked as a residual, not a silent gap.

Nothing here writes to Qdrant or touches `probe_retrieval.py`'s/
`kb_inventory_probe.py`'s own grading — this file only runs those scripts as
subprocesses and interprets their `--json` output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# MANDATE §7's own dead-man-switch threshold for this exact probe ("probe silent
# 24h -> alert"), reused rather than invented: a gap this file tolerates is a gap
# the mandate has already declared acceptable for the SAME job, and a gap it does
# not tolerate is one the mandate already calls an incident.
MAX_GAP_HOURS = 24

# This file's own closed vocabulary for a per-topic RECORD's verdict. The first
# four are probe_retrieval.py's own (imported by name below, never restated as
# literals — a restated copy is exactly the kind of tripwire that goes blind the
# day the two drift, per the "compares two outputs of one generator" lesson).
# `nothing_measured` is added HERE because it is a fact about the campaign's
# current state (no journeys exist to run), not about any single probe run.
NOTHING_MEASURED = "nothing_measured"


def repo_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__)).resolve()
    for candidate in here.parents:
        if (candidate / ".git").exists() and (candidate / "apps").is_dir():
            return candidate
    raise SystemExit("repo root not found")


def _probe_retrieval_module():
    """Import probe_retrieval.py by path (it lives outside any package) so this
    file reads its VERDICT_BY_EXIT vocabulary from the source of truth instead of
    retyping it — the exact discipline `test_kb_topic_contract.py` already applies
    to `kb_inventory_probe.py`'s PAYLOAD_SHAPES, for the same reason."""
    import importlib.util

    cached = sys.modules.get("kb_probe_retrieval")
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(
        "kb_probe_retrieval", Path(__file__).with_name("probe_retrieval.py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["kb_probe_retrieval"] = module
    spec.loader.exec_module(module)
    return module


VERDICTS = frozenset(_probe_retrieval_module().VERDICT_BY_EXIT.values()) | {NOTHING_MEASURED}


def default_history_path(root: Path) -> Path:
    return root / "kb" / "ops" / "probe_history.jsonl"


def sha256_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# Sentinel for "this artifact does not exist yet". A real sha256 is 64 lowercase
# hex characters, so this can never collide with one by construction — a topic
# whose kb/topics/<t>.yaml or kb/inventory/<t>.yaml does not exist is a distinct,
# stable state from any version of that file that does, and its FIRST appearance
# must therefore register as a change (rule (a)), not as "no information yet".
MISSING_SHA = "missing"


def topics_path_for(root: Path, topic: str) -> Path:
    return root / "kb" / "topics" / ("%s.yaml" % topic)


def inventory_path_for(root: Path, topic: str) -> Path:
    return root / "kb" / "inventory" / ("%s.yaml" % topic)


def sha256_or_missing(path: Path) -> str:
    """sha256 of a file's bytes, or MISSING_SHA if it does not exist yet."""
    if not path.is_file():
        return MISSING_SHA
    return sha256_bytes(path)


def artifact_shas(root: Path, topic: str, journeys_path: Path) -> dict[str, str]:
    """The sha256 TRIPLE rule (a) actually asks about — journeys, topics, AND
    inventory — not just the journeys file this module originally hashed alone.
    See module docstring rule (a) for why all three are load-bearing."""
    return {
        "journeys": sha256_or_missing(journeys_path),
        "topics": sha256_or_missing(topics_path_for(root, topic)),
        "inventory": sha256_or_missing(inventory_path_for(root, topic)),
    }


def record_artifact_shas(record: dict) -> dict[str, str | None]:
    """The same triple, read back OUT of a history record. A record written
    before this schema existed simply has no keys here, which `.get` reports
    as None — a value that can never equal a real hash or MISSING_SHA, so an
    old-schema record correctly fails to match any current triple rather than
    silently comparing as equal on missing fields."""
    return {
        "journeys": record.get("journeys_sha256"),
        "topics": record.get("topics_sha256"),
        "inventory": record.get("inventory_sha256"),
    }


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_ts(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ── record ─────────────────────────────────────────────────────────────────


def run_probe_json(journeys_path: Path, collection: str, timeout_s: int = 300) -> dict:
    """Run probe_retrieval.py --json as a subprocess and return its parsed object.

    A crash or unparseable stdout is reported as this file's own `broken` shape
    (rule c: broken counts as nothing either way) rather than raised — a history
    recorder that dies because one topic's probe crashed would fail to record
    every OTHER topic in the same run, which is a worse silence than the one it
    would be reporting.
    """
    script = Path(__file__).with_name("probe_retrieval.py")
    try:
        proc = subprocess.run(
            [sys.executable, str(script), str(journeys_path),
             "--collection", collection, "--json"],
            capture_output=True, text=True, timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return {
            "journeys_file": str(journeys_path), "collection": collection,
            "verdict": "broken", "reason": "control_failed",
            "detail": "probe_retrieval.py timed out after %ds" % timeout_s,
            "exit_code": None, "degraded_path": False, "journeys": [],
        }
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {}
    except (ValueError, IndexError):
        return {
            "journeys_file": str(journeys_path), "collection": collection,
            "verdict": "broken", "reason": "control_failed",
            "detail": "probe_retrieval.py produced no parseable JSON "
                      "(rc=%s, stderr=%r)" % (proc.returncode, proc.stderr[-500:]),
            "exit_code": proc.returncode, "degraded_path": False, "journeys": [],
        }


def run_inventory_probe_json(inventory_path: Path, timeout_s: int = 300) -> dict:
    """Run scripts/kb/kb_inventory_probe.py --json as a subprocess and return
    its parsed object — rule (g): the thing that actually re-measures an
    inventory against LIVE production, instead of trusting a sha256 to stand
    in for a fact about a world that moves independently of the file.

    Same defensiveness as `run_probe_json`, for the identical reason: one
    topic's inventory probe crashing (or its inventory file not existing yet)
    must not stop every OTHER topic in the same record() run from being
    recorded — a missing file surfaces here as `FileNotFoundError` inside the
    subprocess (no valid JSON on stdout), caught by the same fallback as an
    unparseable-output crash, not special-cased.
    """
    script = repo_root() / "scripts" / "kb" / "kb_inventory_probe.py"
    try:
        proc = subprocess.run(
            [sys.executable, str(script), str(inventory_path), "--json"],
            capture_output=True, text=True, timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return {
            "inventory_file": str(inventory_path),
            "verdict": "broken", "reason": "control_failed",
            "detail": "kb_inventory_probe.py timed out after %ds" % timeout_s,
            "exit_code": None, "findings": [],
        }
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {}
    except (ValueError, IndexError):
        return {
            "inventory_file": str(inventory_path),
            "verdict": "broken", "reason": "control_failed",
            "detail": "kb_inventory_probe.py produced no parseable JSON "
                      "(rc=%s, stderr=%r)" % (proc.returncode, proc.stderr[-500:]),
            "exit_code": proc.returncode, "findings": [],
        }


def build_record(topic: str, journeys_path: Path, shas: dict[str, str],
                  probe_result: dict, inventory_result: dict) -> dict:
    verdict = probe_result.get("verdict") or "broken"
    if verdict not in VERDICTS:
        # Defensive, not reachable via the real subprocess today: an unrecognized
        # verdict is closer to broken (evidence about the probe itself, not the
        # topic) than to any real grading outcome.
        verdict = "broken"
    # Rule (g): the inventory's OWN verdict — deliberately a SEPARATE field,
    # never merged with `verdict` above. `at_target` retrieval next to `drift`
    # inventory are two different facts about the same topic; collapsing them
    # into one boolean would lose exactly the distinction that makes a later
    # failure diagnosable.
    inventory_verdict = inventory_result.get("verdict") or "broken"
    if inventory_verdict not in VERDICTS:
        inventory_verdict = "broken"
    return {
        "ts": now_utc().isoformat(),
        "topic": topic,
        "journeys_path": str(journeys_path),
        # Rule (a): the sha256 TRIPLE, one per artifact MANDATE §8 names —
        # never a single journeys-only hash. See artifact_shas()/module docstring.
        "journeys_sha256": shas["journeys"],
        "topics_sha256": shas["topics"],
        "inventory_sha256": shas["inventory"],
        "verdict": verdict,
        "exit_code": probe_result.get("exit_code"),
        "degraded_path": bool(probe_result.get("degraded_path")),
        "journeys": probe_result.get("journeys") or [],
        "detail": probe_result.get("detail"),
        # Rule (g): the LIVE re-measurement, distinct from the sha256 that only
        # answers "did the file's bytes change".
        "inventory_verdict": inventory_verdict,
        "inventory_exit_code": inventory_result.get("exit_code"),
        "inventory_findings": inventory_result.get("findings") or [],
    }


def cmd_record(args, root: Path) -> int:
    history_path = Path(args.history) if args.history else default_history_path(root)
    journeys_dir = root / "kb" / "journeys"
    files = sorted(journeys_dir.glob("*.yaml")) if journeys_dir.is_dir() else []

    records: list[dict] = []
    if not files:
        # Rule (b): zero journey files is a FACT about today's campaign state, and
        # it must be written down, not silently skipped. topic/journeys_path/shas
        # are null because there is nothing to name.
        records.append({
            "ts": now_utc().isoformat(), "topic": None, "journeys_path": None,
            "journeys_sha256": None, "topics_sha256": None, "inventory_sha256": None,
            "verdict": NOTHING_MEASURED, "exit_code": None,
            "degraded_path": False, "journeys": [],
            "detail": "0 kb/journeys/*.yaml files found on disk",
            "inventory_verdict": None, "inventory_exit_code": None,
            "inventory_findings": [],
        })
    else:
        for path in files:
            topic = path.stem
            shas = artifact_shas(root, topic, path)
            result = run_probe_json(path, args.collection)
            # Rule (g): every topic found gets its inventory RE-MEASURED against
            # live production, independent of whether its journeys probe found
            # anything to grade — the inventory question ("is our claim still
            # true") is orthogonal to the retrieval question ("does the suite
            # still pass").
            inv_result = run_inventory_probe_json(inventory_path_for(root, topic))
            if result.get("reason") == "no_journeys":
                # Rule (b) again, at the per-file granularity: this specific file
                # exists but declares nothing to run.
                rec = build_record(topic, path, shas, result, inv_result)
                rec["verdict"] = NOTHING_MEASURED
                rec["detail"] = result.get("detail") or "%s declares no journeys" % path.name
            else:
                rec = build_record(topic, path, shas, result, inv_result)
            records.append(rec)

    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")

    for rec in records:
        label = rec["topic"] or "(no topic)"
        print("[record] %-24s verdict=%-16s journeys_sha=%s"
              % (label, rec["verdict"], (rec["journeys_sha256"] or "-")[:12]))

    # Rule (e): `broken` and `nothing_measured` are BOTH an absence of evidence —
    # neither may let record() claim success. Rule (f) extends the same logic to
    # `degraded_path`: a record that produced a verdict but only on the
    # narrower, non-production path is not the "green against production" §8
    # asks for either, so it is excluded from `graded` the same way `broken` is
    # — never by inspecting the verdict field alone. `graded` is every record
    # that actually measured something real, on the real path, today.
    graded = [r for r in records
              if r["verdict"] not in (NOTHING_MEASURED, "broken")
              and not r.get("degraded_path")]
    broken = [r for r in records if r["verdict"] == "broken"]
    # A degraded record's verdict is never "broken" (build_record only ever
    # sets one or the other) — see rule (f) — so this is disjoint from `broken`
    # by construction, not by filtering it out here a second time.
    degraded = [r for r in records
                if r["verdict"] not in (NOTHING_MEASURED, "broken") and r.get("degraded_path")]
    # Rule (g): the inventory's OWN verdict, deliberately checked SEPARATELY
    # from `verdict` above — never AND'd into `graded`'s own definition. A
    # topic whose retrieval graded cleanly but whose inventory drifted still
    # counts toward `graded` (retrieval genuinely measured something), and
    # ALSO independently forces record()'s exit code non-zero below — two
    # distinct facts, two distinct reasons, reported apart.
    inventory_broken = [r for r in records if r.get("inventory_verdict") == "broken"]
    inventory_drift = [r for r in records if r.get("inventory_verdict") == "drift"]

    if not graded:
        print()
        print(
            "nothing measured cleanly — every topic this run produced no undegraded, "
            "gradable evidence (%d topic file(s) found: %d broken, %d degraded, rest "
            "nothing_measured). This is NOT success: record() intentionally does not "
            "exit 0 here." % (len(files), len(broken), len(degraded))
        )
        return 1

    if broken or degraded or inventory_broken or inventory_drift:
        # Rule (e)+(f)+(g), the mixed-run case: SOME topics graded cleanly, but
        # one or more came back broken/degraded on retrieval, OR broken/drifted
        # on the inventory re-measurement. Exit non-zero anyway — a retrieval
        # problem and an inventory problem are named as SEPARATE reasons below,
        # never folded into one another, so an operator reading cron output
        # learns which half of the measurement actually failed.
        parts = []
        if broken:
            parts.append(
                "%d broken (not measured): %s"
                % (len(broken), ", ".join(sorted(r["topic"] or "?" for r in broken)))
            )
        if degraded:
            parts.append(
                "%d degraded (measured, but on the narrower non-production path — "
                "rule (f) — and not counted as clean evidence): %s"
                % (len(degraded), ", ".join(sorted(r["topic"] or "?" for r in degraded)))
            )
        if inventory_broken:
            parts.append(
                "%d inventory-broken (kb_inventory_probe.py could not measure "
                "production for this topic — rule (g)): %s"
                % (len(inventory_broken),
                   ", ".join(sorted(r["topic"] or "?" for r in inventory_broken)))
            )
        if inventory_drift:
            parts.append(
                "%d inventory-drift (production has moved since the inventory's "
                "own measured_at; the sha256 alone would never have caught this "
                "— rule (g)): %s"
                % (len(inventory_drift),
                   ", ".join(sorted(r["topic"] or "?" for r in inventory_drift)))
            )
        print()
        print(
            "PARTIAL — %d of %d topic(s) graded cleanly; %s. record() intentionally "
            "does not exit 0 on a partial run: a broken, degraded, or inventory-drifted "
            "topic hiding behind its clean neighbours is exactly how it goes unnoticed "
            "for months while the scheduled job stays green."
            % (len(graded), len(records), "; ".join(parts))
        )
        return 1

    return 0


# ── status ─────────────────────────────────────────────────────────────────


def load_history(history_path: Path) -> list[dict]:
    if not history_path.is_file():
        return []
    records = []
    for line in history_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except ValueError:
            continue  # a corrupt line is not this file's job to repair
    return records


def _streak(records_same_sha: list[dict], reference: datetime) -> dict:
    """Walk the most-recent-first, same-sha history and answer §8's question.

    `records_same_sha` must already be filtered to ONE topic and ONE sha256 TRIPLE
    (the CURRENT files' — journeys, topics, inventory), and sorted ascending by
    timestamp — the caller's job, so this function has no way to silently mix two
    versions of any of the three artifacts together.
    """
    # rule (c): broken. rule (f): degraded_path — both are an absence of evidence
    # about PRODUCTION (broken never reached it; degraded ran a narrower path the
    # probe itself refuses to call equivalent) and are dropped from the gradable
    # timeline the same way, before the streak is walked.
    gradable = [r for r in records_same_sha
                if r["verdict"] != "broken" and not r.get("degraded_path")]
    broken_count = sum(1 for r in records_same_sha if r["verdict"] == "broken")
    degraded_count = sum(1 for r in records_same_sha if r.get("degraded_path"))

    if not gradable:
        return {
            "at_target_48h": False, "currently_at_target": False, "stale": None,
            "first_green": None, "elapsed_hours": 0.0, "runs_in_window": 0,
            "broken_runs_in_window": broken_count,
            "degraded_runs_in_window": degraded_count,
            "reason": "no gradable (non-broken, non-degraded) runs at the current sha",
        }

    latest = gradable[-1]
    latest_ts = parse_ts(latest["ts"])
    gap_to_now = (reference - latest_ts).total_seconds() / 3600
    stale = gap_to_now > MAX_GAP_HOURS  # rule (d), applied to the "now" edge too

    if latest["verdict"] != "at_target":
        return {
            "at_target_48h": False, "currently_at_target": False, "stale": stale,
            "first_green": None, "elapsed_hours": 0.0, "runs_in_window": 0,
            "broken_runs_in_window": broken_count,
            "degraded_runs_in_window": degraded_count,
            "reason": "latest run at current sha is %r, not at_target" % latest["verdict"],
        }

    first_green_ts = latest_ts
    prev_ts = latest_ts
    runs_in_window = 1
    for rec in reversed(gradable[:-1]):
        if rec["verdict"] != "at_target":
            break  # a non-at_target run inside the window ends the streak here
        ts = parse_ts(rec["ts"])
        gap_hours = (prev_ts - ts).total_seconds() / 3600
        if gap_hours > MAX_GAP_HOURS:
            break  # rule (d): a hole in the record, not evidence of 48h
        first_green_ts = ts
        prev_ts = ts
        runs_in_window += 1

    if stale:
        # rule (d): the streak that WAS built is real evidence up to latest_ts,
        # but it is not evidence that the topic is at target RIGHT NOW.
        elapsed = (latest_ts - first_green_ts).total_seconds() / 3600
        return {
            "at_target_48h": False, "currently_at_target": False, "stale": True,
            "first_green": first_green_ts.isoformat(), "elapsed_hours": round(elapsed, 1),
            "runs_in_window": runs_in_window, "broken_runs_in_window": broken_count,
            "degraded_runs_in_window": degraded_count,
            "reason": "last gradable run was %.1fh ago (> %dh) — no recent evidence"
                      % (gap_to_now, MAX_GAP_HOURS),
        }

    elapsed = (reference - first_green_ts).total_seconds() / 3600
    return {
        "at_target_48h": elapsed >= 48.0, "currently_at_target": True, "stale": False,
        "first_green": first_green_ts.isoformat(), "elapsed_hours": round(elapsed, 1),
        "runs_in_window": runs_in_window, "broken_runs_in_window": broken_count,
        "degraded_runs_in_window": degraded_count,
        "reason": "continuously at_target since first_green" if elapsed >= 48.0
                  else "at_target now, but only %.1fh of the 48h window covered" % elapsed,
    }


def cmd_status(args, root: Path) -> int:
    history_path = Path(args.history) if args.history else default_history_path(root)
    records = load_history(history_path)
    journeys_dir = root / "kb" / "journeys"

    topics = sorted({r["topic"] for r in records if r.get("topic")})
    if not records or not topics:
        print("nothing_measured — no history recorded (%s: %d record(s), %d topic(s))"
              % (history_path, len(records), len(topics)))
        return 1

    reference = now_utc()
    any_current = False
    edited_since_last_record = 0
    edited_topics: list[str] = []
    for topic in topics:
        topic_records = [r for r in records if r.get("topic") == topic]
        journeys_path = journeys_dir / ("%s.yaml" % topic)
        if not journeys_path.is_file():
            print("[status] %-24s MISSING — kb/journeys/%s.yaml no longer on disk, "
                  "%d historical record(s) orphaned" % (topic, journeys_path.name,
                                                          len(topic_records)))
            continue
        # Rule (a): the CURRENT triple — journeys, topics, inventory — not just
        # the journeys file. A record only continues the streak if ALL THREE
        # match today's bytes.
        current = artifact_shas(root, topic, journeys_path)
        same_sha = sorted(
            (r for r in topic_records if record_artifact_shas(r) == current),
            key=lambda r: r["ts"],
        )
        if topic_records and not same_sha:
            # Rule (a): every record on file predates at least one of the current
            # triple's bytes — kb/journeys/, kb/topics/, or kb/inventory/ changed
            # since the last recorded run, so there is zero continuing evidence,
            # not "unknown" evidence.
            edited_since_last_record += 1
            edited_topics.append(topic)
        result = _streak(same_sha, reference)
        any_current = any_current or result["at_target_48h"]
        verdict = "AT-TARGET-48H" if result["at_target_48h"] else (
            "STALE" if result["stale"] else "NOT-YET")
        print(
            "[status] %-24s %-14s first_green=%s elapsed=%.1fh runs=%d broken=%d "
            "degraded=%d — %s"
            % (topic, verdict, result["first_green"] or "-", result["elapsed_hours"],
               result["runs_in_window"], result["broken_runs_in_window"],
               result["degraded_runs_in_window"], result["reason"])
        )

    if edited_since_last_record:
        print()
        print("(%d topic(s) have history but every recorded sha256 triple predates "
              "the current journeys/topics/inventory bytes — kb/journeys/<t>.yaml, "
              "kb/topics/<t>.yaml, or kb/inventory/<t>.yaml changed since the last "
              "recorded run for that topic; the 48h clock for those restarted at "
              "zero per rule (a): %s)"
              % (edited_since_last_record, ", ".join(sorted(edited_topics))))

    return 0 if any_current else 1


# ── CLI ────────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_record = sub.add_parser("record", help="run every kb/journeys/*.yaml and append history")
    p_record.add_argument("--collection", default="legal_unified")
    p_record.add_argument("--history", default=None,
                           help="override the history file path (default kb/ops/probe_history.jsonl)")

    p_status = sub.add_parser("status", help="answer MANDATE §8's 48h-continuous question per topic")
    p_status.add_argument("--history", default=None)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    root = repo_root()
    if args.command == "record":
        return cmd_record(args, root)
    if args.command == "status":
        return cmd_status(args, root)
    raise AssertionError("unreachable: argparse enforces the subcommand vocabulary")


if __name__ == "__main__":
    raise SystemExit(main())
