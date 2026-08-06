"""An explicit dedup key that MOVES with the measurement is worse than none.

TRAUMA (measured on the live 31-day spool, 2026-08-06): `send_alert` passed
`--dedup-key sentinel:<md5(message)>`, and the message carries the counter:

    🔴 Sentinel | BLIND HEAL-LOOP: 16 TERMINAL job(s) parked in DLQ but ZERO
                 healing actions for 99 consecutive cycles

378 sentinel events produced **255 distinct keys** — 36 real conditions wearing
255 identities. That key is not merely useless, it is actively harmful: in
`tg_notify.notify()` the rule is `key = dedup_key or sha1(condition_identity())`,
so an explicit key WINS. A moving explicit key therefore (a) suppresses the
gateway's own normaliser and (b) defeats every mute window, because each
re-measurement looks like a brand-new condition. 168 of those events were one
condition, announced every ~4h for a month, never healed.

Replayed over the same 378 events (29.3 days) with the 6/24/72/168h ladder,
scoring both branches of `dedup_key or derived`: 12.90/day → 3.41/day, and
5.73 → 0.24/day on p0. All 12 settings.json changes stay audible.

The cure has two halves and this file tests both:
  1. a named `condition` becomes `sentinel:<condition>` — stable by
     construction, and survives rewording of the message, which a derived key
     cannot;
  2. NO name means NO `--dedup-key` at all, so the gateway derives one. The
     normaliser is NOT re-implemented here: two constants that must agree,
     maintained in two files, is the drift this organism keeps relapsing into.

These assert on the ARGV the gateway is actually handed, because that is the
only surface that matters — asserting on a helper would prove the helper
(W116), not that send_alert speaks to the gateway the way this docstring says.
"""

from __future__ import annotations

import ast
import json
import os
import plistlib
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))


def _wire(tmp_path, monkeypatch, *, real_local_dedup: bool):
    """A fake gateway that records its argv — the real one is never spawned."""
    fake = tmp_path / "tg_notify.py"
    argv_log = tmp_path / "argv.jsonl"
    fake.write_text(textwrap.dedent(f"""
        import json, sys
        with open({str(argv_log)!r}, "a") as fh:
            fh.write(json.dumps(sys.argv[1:]) + "\\n")
        print("tg_notify: sent", file=sys.stderr)
    """).strip() + "\n")

    import sentinel_lib.alerter as alerter

    # Redirect BOTH the gateway and the local dedup store, so the test never
    # reads or writes fleet state (W96: a test that writes production state).
    monkeypatch.setattr(alerter, "_gateway_script", lambda: str(fake))
    monkeypatch.setattr(alerter, "DEDUP_FILE", str(tmp_path / "dedup.json"))
    if not real_local_dedup:
        # Most tests are about the KEY handed to the gateway; the 1h local
        # fast-path would hide the second send and is exercised separately.
        monkeypatch.setattr(alerter, "_load_dedup", lambda: {})
        monkeypatch.setattr(alerter, "_mark_sent", lambda k: None)
    alerter._argv_log = argv_log
    return alerter


@pytest.fixture
def sentinel(tmp_path, monkeypatch):
    return _wire(tmp_path, monkeypatch, real_local_dedup=False)


@pytest.fixture
def sentinel_with_local_dedup(tmp_path, monkeypatch):
    return _wire(tmp_path, monkeypatch, real_local_dedup=True)


def _keys(alerter) -> list[str | None]:
    """The --dedup-key of every gateway invocation, None when absent."""
    out = []
    if not alerter._argv_log.exists():
        return out
    for line in alerter._argv_log.read_text().splitlines():
        argv = json.loads(line)
        out.append(argv[argv.index("--dedup-key") + 1] if "--dedup-key" in argv else None)
    return out


# ------------------------------------------------------------------ guilt
def test_a_named_condition_survives_a_moving_measurement(sentinel):
    """THE trauma, verbatim: the same condition, re-measured, must keep one key."""
    sentinel.send_alert("BLIND HEAL-LOOP: 16 jobs parked for 3 cycles",
                        level="CRITICAL", condition="blind_heal_loop")
    sentinel.send_alert("BLIND HEAL-LOOP: 18 jobs parked for 99 cycles",
                        level="CRITICAL", condition="blind_heal_loop")
    assert _keys(sentinel) == ["sentinel:blind_heal_loop:critical"] * 2


def test_a_named_condition_survives_rewording(sentinel):
    """A name outlives an edit to the sentence — which is why it beats deriving."""
    sentinel.send_alert("BLIND HEAL-LOOP: 16 jobs parked", condition="blind_heal_loop")
    sentinel.send_alert("Heal loop idle: nothing has been retried in 4 days",
                        condition="blind_heal_loop")
    assert len(set(_keys(sentinel))) == 1


def test_no_condition_sends_no_key_so_the_gateway_derives_one(sentinel):
    """The half that is easy to get wrong: passing SOME key would beat the
    gateway's normaliser. Absence is the point, not a fallback."""
    sentinel.send_alert("something with no named condition 42")
    assert _keys(sentinel) == [None], (
        "an unnamed alert must reach the gateway with NO --dedup-key, or the "
        "explicit key wins over condition_identity() — the trauma, again"
    )


def test_the_key_never_carries_a_message_hash(sentinel):
    """Pins the exact defect: md5(message) must not reach the gateway."""
    import hashlib

    msg = "BLIND HEAL-LOOP: 16 jobs parked for 99 cycles"
    sentinel.send_alert(msg, condition="blind_heal_loop")
    key = _keys(sentinel)[0] or ""
    assert hashlib.md5(msg.encode()).hexdigest() not in key
    assert not any(len(p) == 32 and all(c in "0123456789abcdef" for c in p)
                   for p in key.split(":")), f"a bare hash is back in the key: {key}"


# --------------------------------------------------------------- innocence
def test_different_jobs_stay_different_conditions(sentinel):
    """INNOCENCE: on the live corpus `Tier N needed — dropbox-intake` and
    `— login-healthcheck` are separate conditions and must NOT collapse."""
    sentinel.send_alert("Tier 3 needed — dropbox-intake",
                        condition="tier-escalation:dropbox-intake")
    sentinel.send_alert("Tier 3 needed — login-healthcheck",
                        condition="tier-escalation:login-healthcheck")
    assert len(set(_keys(sentinel))) == 2


def test_the_condition_is_namespaced_to_sentinel(sentinel):
    """A bare condition name must not be able to collide with another source's."""
    sentinel.send_alert("x", condition="blind_heal_loop")
    assert _keys(sentinel)[0].startswith("sentinel:")  # namespaced
    assert _keys(sentinel)[0].endswith(":info")     # severity-scoped


def test_level_still_routes_the_tier(sentinel):
    """INNOCENCE: naming a condition must not disturb the tier mapping."""
    sentinel.send_alert("a", level="CRITICAL", condition="c1")
    sentinel.send_alert("b", level="WARNING", condition="c2")
    tiers = []
    for line in sentinel._argv_log.read_text().splitlines():
        argv = json.loads(line)
        tiers.append(argv[argv.index("--tier") + 1])
    assert tiers == ["p0", "digest"]


def test_signature_stays_backward_compatible(sentinel):
    """~40 call sites pass (message) or (message, level=...). None may break."""
    assert sentinel.send_alert("positional only") is True
    assert sentinel.send_alert("with level", level="WARNING") is True
    assert sentinel.send_alert("positional level", "WARNING") is True
    assert len(_keys(sentinel)) == 3


def test_the_local_fastpath_still_saves_the_second_subprocess(sentinel_with_local_dedup):
    """INNOCENCE for the half NOT changed: the 1h exact-text guard still
    short-circuits a byte-identical repeat, so this diff did not quietly turn
    one suppression layer off while renaming another."""
    a = sentinel_with_local_dedup
    assert a.send_alert("identical text", condition="c") is True
    # True, like the gateway's own duplicate: one meaning, one value. The
    # short-circuit is proven by the ARGV count, not by the return.
    assert a.send_alert("identical text", condition="c") is True
    assert len(_keys(a)) == 1, "the second identical message spawned a gateway anyway"


def test_the_fastpath_does_not_swallow_a_changed_measurement(sentinel_with_local_dedup):
    """...and it must NOT suppress a re-measurement — that is the gateway's job,
    on the ladder. If the local guard ate these, naming the condition would be
    pointless because nothing would reach the gateway to be laddered."""
    a = sentinel_with_local_dedup
    assert a.send_alert("BLIND HEAL-LOOP: 16 jobs", condition="blind_heal_loop") is True
    assert a.send_alert("BLIND HEAL-LOOP: 17 jobs", condition="blind_heal_loop") is True
    assert _keys(a) == ["sentinel:blind_heal_loop:info"] * 2


# ------------------------------------------------- the wiring, not the helper
def test_the_blind_heal_loop_call_site_names_its_condition():
    """The 168-event offender. A parameter nothing passes is a parameter that
    changes nothing — this reads the caller, not the helper."""
    src = (REPO / "scripts" / "nuzantara-sentinel.py").read_text()
    assert 'send_alert(msg, level="CRITICAL", condition=cooldown_key)' in src, (
        "the BLIND HEAL-LOOP alert stopped naming its condition — 168 events "
        "over 29 days were this one call site"
    )


def _sendalert_calls(path: Path):
    """(lineno, first-arg template, names_a_condition) for every send_alert call."""
    out = []
    for node in ast.walk(ast.parse(path.read_text())):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "send_alert"):
            continue
        if not node.args:
            continue
        parts = []

        def walk(n):
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                parts.append(n.value)
            elif isinstance(n, ast.JoinedStr):
                for v in n.values:
                    walk(v)
            elif isinstance(n, ast.FormattedValue):
                parts.append("{" + ast.unparse(n.value) + "}")
            elif isinstance(n, ast.BinOp):
                walk(n.left)
                walk(n.right)

        walk(node.args[0])
        named = any(k.arg == "condition" for k in node.keywords)
        out.append((node.lineno, "".join(parts), named))
    return out


def test_every_escalation_call_site_names_the_job():
    """A COUNT would pin my own blind spot. This asserts the CLASS.

    First pass of this cure wired three `Tier N needed — <job>` sites and left a
    fourth. Measured against the spool afterwards: all 161 recorded escalation
    events came from the one left out (`process_job`, no backticks around the
    job) and the three wired ones had fired ZERO times in 29 days. A hand-written
    "expected 3" would have frozen exactly that mistake into the corpus, which is
    W107 recurring inside its own cure. So: every call site of the escalation
    family must name its condition, however many there turn out to be.
    """
    calls = _sendalert_calls(REPO / "scripts" / "nuzantara-sentinel.py")
    family = [(ln, t, named) for ln, t, named in calls if "needed —" in t]
    assert len(family) >= 4, f"escalation family shrank to {len(family)} — census changed"
    unnamed = [ln for ln, _, named in family if not named]
    assert not unnamed, (
        f"escalation call sites at lines {unnamed} do not name their condition; "
        f"every repeat of one job's escalation must share one identity"
    )


def test_the_escalation_condition_carries_the_job_and_nothing_measured():
    """Innocence for the class rule: the condition must be the job, not the tier
    number — `Tier 3` and `Tier 4` for one job are the same condition escalating."""
    src = (REPO / "scripts" / "nuzantara-sentinel.py").read_text()
    for bad in ('condition=f"tier-escalation:{failure_type}"', "tier-escalation:{new_phase}"):
        assert bad not in src
    assert src.count('condition=f"tier-escalation:{job_id}"') == len(
        [1 for _, t, _ in _sendalert_calls(REPO / "scripts" / "nuzantara-sentinel.py")
         if "needed —" in t]
    ), "an escalation site names something other than the job"


# ------------------------------------------ the watcher, EXECUTED not grepped
WATCHER = REPO / "scripts" / "claude-settings-change-alert.sh"
PLIST = REPO / "infra" / "launchagents" / "com.balizero.claude-settings-watcher.plist"


def _run_watcher(home: Path, settings: str, alerter_body: str, **extra_env) -> dict:
    """Run the real script against a throwaway HOME and a fake alerter module."""
    (home / ".claude").mkdir(parents=True, exist_ok=True)
    (home / ".claude" / "settings.json").write_text(settings)
    lib = home / "scripts" / "sentinel_lib"
    lib.mkdir(parents=True, exist_ok=True)
    (lib / "__init__.py").write_text("")
    (lib / "alerter.py").write_text(alerter_body)
    (home / ".agent" / "decisions").mkdir(parents=True, exist_ok=True)
    calls = home / "calls.jsonl"
    env = {**os.environ, "HOME": str(home), "FAKE_CALLS": str(calls), **extra_env}
    proc = subprocess.run(["bash", str(WATCHER)], capture_output=True, text=True, env=env)
    state = home / ".agent" / "decisions" / "claude-settings-last-md5"
    hb = home / ".organism" / "last_seen" / "claude-settings-watcher.json"
    return {
        "rc": proc.returncode,
        "stderr": proc.stderr,
        "state": state.read_text().strip() if state.exists() else "",
        "calls": [json.loads(l) for l in calls.read_text().splitlines()] if calls.exists() else [],
        "heartbeat": json.loads(hb.read_text()) if hb.exists() else None,
    }


_FAKE_ALERTER = """
import json, os
def send_alert(message, level="INFO", condition=""):
    with open(os.environ["FAKE_CALLS"], "a") as fh:
        fh.write(json.dumps({"level": level, "condition": condition}) + "\\n")
    return True
"""

_OLD_ALERTER = """
import json, os
def send_alert(message, level="INFO"):          # predates `condition`
    with open(os.environ["FAKE_CALLS"], "a") as fh:
        fh.write(json.dumps({"level": level, "condition": None}) + "\\n")
    return True
"""

_RAISING_ALERTER = """
def send_alert(message, level="INFO", condition=""):
    raise TypeError("unsupported operand type(s) for -: 'float' and 'str'")
"""


def test_the_heartbeat_gene_fires_and_is_decoupled_from_the_news(tmp_path):
    """Promoting this plist made it an ORGAN, and an organ is born with genes.

    G2 matters MORE here than for a timer, and for the opposite reason. A cron
    that has not spoken in three days is broken; this one is fired by launchd on
    a WatchPaths event, so "silent for three days" means Zero did not edit
    settings.json — a fact about his week, not about the organ. Silence can
    therefore NEVER be read as a fault, which is precisely how a dead watcher
    stays invisible forever (superscar #2).

    So the heartbeat is written on EVERY fire, before the change comparison, and
    that is what is asserted: a run that finds nothing to report — the common
    case, the one that would otherwise leave no trace — still leaves proof of
    life. Grepping the wrapper for `.organism/last_seen` only proves the gene is
    present; a present gene that never fires is decoration.
    """
    home = tmp_path / "quiet"
    (home / ".agent" / "decisions").mkdir(parents=True, exist_ok=True)
    settings = '{"hooks": {"x": 1}}'
    first = _run_watcher(home, settings, _FAKE_ALERTER)
    assert first["calls"], "setup failed: the first run should alert"

    (home / ".organism" / "last_seen" / "claude-settings-watcher.json").unlink()
    second = _run_watcher(home, settings, _FAKE_ALERTER)   # nothing changed
    assert second["calls"] == first["calls"], "an unchanged file must not re-alert"
    assert second["heartbeat"], "a quiet run left no proof of life — silence is unreadable"
    assert second["heartbeat"]["status"] == "ok"
    assert second["heartbeat"]["organ"] == "claude-settings-watcher"


def test_the_heartbeat_carries_the_runs_real_verdict(tmp_path):
    """A wrapper that writes `ok` unconditionally passes the G2 grep and lies:
    it reports health for the run that failed to deliver. When the gateway does
    not take the news, the sidecar must say so — that is the only signal
    distinguishing "no changes to report" from "changes nobody received"."""
    out = _run_watcher(tmp_path / "broken", '{"hooks": {}}', _RAISING_ALERTER)
    assert not out["state"], "state advanced despite a failed delivery"
    assert out["heartbeat"] and out["heartbeat"]["status"] == "error", (
        f"the sidecar reported health for a run that delivered nothing: {out['heartbeat']}")


def test_the_kill_switch_stops_the_organ_without_unloading_it(tmp_path):
    """A WatchPaths organ cannot be quietened by editing a schedule, so without
    a kill switch the only way to stop it is unloading the plist — the
    "unarm to silence" move that turns a noisy organ into a dead one nobody
    remembers to revive.

    Deliberately disabled means NO heartbeat: an organ told not to work must not
    report that it is working. The fire log still records the invocation, so the
    silence remains explainable — the guard exits before the heartbeat but after
    the log, and that order is the whole point.
    """
    out = _run_watcher(tmp_path / "off", '{"hooks": {}}', _FAKE_ALERTER,
                       CLAUDE_SETTINGS_WATCHER_ENABLED="false")
    assert out["calls"] == [], "the kill switch did not stop the alert"
    assert out["heartbeat"] is None, "a disabled organ claimed it was working"
    assert out["rc"] == 0, "a deliberate stop must not look like a crash"


def test_the_launchagent_names_the_script_not_an_inline_shell(tmp_path):
    """The plist used to be `bash -c 'echo …; exec <script>'`. That thin wrapper
    decided what the organ-conformance gate was allowed to SEE: the gate read
    the two-command inline string as the organ's body and found no heartbeat, no
    kill switch and no `set -u` — genes that all existed one level down, in a
    file it never opened. The gate was right and the plist was lying by framing.

    So the payload is the script itself. Asserted here, not only in the gate,
    because reintroducing an `echo … ; exec` for one debug line would silently
    re-blind every content gene at once.
    """
    payload = plistlib.loads(PLIST.read_bytes())
    argv = payload["ProgramArguments"]
    assert argv == ["/Users/nuzantara/scripts/claude-settings-change-alert.sh"], (
        f"the launchd payload stopped naming the script: {argv}")
    assert payload["WatchPaths"] == ["/Users/nuzantara/.claude/settings.json"]


@pytest.mark.parametrize("junk", ["1 2", "(", "", "abc", "-\n-"])
def test_a_corrupt_sequence_counter_cannot_silence_the_watcher(tmp_path, junk):
    """The counter file is state the script READS to build its own key, so it is
    also state that can KILL it. `SEQ=$(( $(cat f) + 1 ))` on `1 2` or `(` makes
    bash's arithmetic fail; SEQ is then never assigned, and `set -u` aborts on
    the expansion below — before the alert, on this change and on every future
    one. A hand-edit or a truncated write would mute the producer permanently at
    exit 0, which is the exact shape of "exists but is not armed".

    Guilt is asserted where it hurts: the ALERT must still go out.
    """
    home = tmp_path / str(abs(hash(junk)))
    (home / ".agent" / "decisions").mkdir(parents=True, exist_ok=True)
    (home / ".agent" / "decisions" / "claude-settings-alert-seq").write_text(junk)
    out = _run_watcher(home, '{"hooks": {}}', _FAKE_ALERTER)
    assert len(out["calls"]) == 1, f"corrupt counter {junk!r} silenced the watcher: {out}"
    assert out["calls"][0]["condition"].endswith("#1"), (
        f"the counter did not fall back to a usable value: {out['calls'][0]}")
    assert out["state"], "delivery succeeded but the state was not advanced"


def test_the_watcher_names_the_TRANSITION_not_the_new_state(tmp_path):
    """The fourth producer, where the same rule gives the OPPOSITE answer.

    The first three families collapse re-measurements — that is the point. Here
    it would be a REGRESSION: each alert is a different change needing its own
    session restart, and 6 of the 11 measured gaps sit inside the 6h window.

    But the NEW STATE alone is not the answer either, and the spool holds the
    counter-example: md5 7af809… at 18:05, 2555ea… at 20:39, 7af809… again at
    23:33. That third fire is a real change — the file came back to a content
    the running session has since stopped using — which a state-keyed alert
    would have called a duplicate. The event is the TRANSITION.
    """
    home = tmp_path / "h"
    first = _run_watcher(home, '{"a": 1}', _FAKE_ALERTER)
    assert len(first["calls"]) == 1
    c1 = first["calls"][0]["condition"]
    assert c1.startswith("settings-json:") and "->" in c1, c1
    # A broken hash yields "settings-json:->", which satisfies both checks
    # above — assert the NEW side is really a hash. The md5 helper has two
    # branches (macOS /sbin/md5, Linux md5sum) and only one runs per platform,
    # so the other must not be free to return nothing (superscar #2).
    new_side = c1.split("->", 1)[1].split("#")[0]
    assert len(new_side) == 12 and all(ch in "0123456789abcdef" for ch in new_side), c1
    assert c1.rsplit("#", 1)[1].isdigit(), c1

    second = _run_watcher(home, '{"a": 2}', _FAKE_ALERTER)
    c2 = second["calls"][-1]["condition"]
    assert c2 != c1

    # A -> B -> A: the third fire must NOT reuse the first key.
    third = _run_watcher(home, '{"a": 1}', _FAKE_ALERTER)
    c3 = third["calls"][-1]["condition"]
    assert c3 not in (c1, c2), f"A->B->A collapsed onto an earlier key: {c3}"

    # ...and one step FURTHER, which is where a transition alone breaks: the
    # fourth change repeats the transition of the second, and it is still a
    # separate change needing a separate restart.
    fourth = _run_watcher(home, '{"a": 2}', _FAKE_ALERTER)
    c4 = fourth["calls"][-1]["condition"]
    assert c4 not in (c1, c2, c3), f"A->B->A->B reused an earlier key: {c4}"
    assert len({c1, c2, c3, c4}) == 4


def test_the_watcher_stays_silent_when_nothing_changed(tmp_path):
    """INNOCENCE: WatchPaths can fire on a touch that changed no bytes."""
    home = tmp_path / "h"
    _run_watcher(home, '{"a": 1}', _FAKE_ALERTER)
    again = _run_watcher(home, '{"a": 1}', _FAKE_ALERTER)
    assert len(again["calls"]) == 1, "an unchanged file alerted twice"


def test_an_older_alerter_still_delivers(tmp_path):
    """Deploy skew must degrade to a delivered-but-unnamed alert, never to
    silence — the outer handler exits 0, so a TypeError would lose it."""
    home = tmp_path / "h"
    r = _run_watcher(home, '{"a": 1}', _OLD_ALERTER)
    assert len(r["calls"]) == 1 and r["calls"][0]["condition"] is None
    assert r["state"], "state must still advance when the alert was delivered"


def test_a_typeerror_from_inside_is_not_mistaken_for_an_old_signature(tmp_path):
    """The first cure caught TypeError from the CALL, which cannot tell "this
    alerter predates the kwarg" from "send_alert raised a TypeError inside" — a
    non-numeric ts in the local dedup json does exactly that. Detect the
    SIGNATURE. And an undelivered alert must not advance the state."""
    home = tmp_path / "h"
    r = _run_watcher(home, '{"a": 1}', _RAISING_ALERTER)
    assert r["rc"] == 0, "the watcher must never break its launchd job"
    assert r["state"] == "", (
        "state advanced on an undelivered alert — the next run would compare "
        "equal hashes and the alert is gone for good"
    )
    assert "not delivered" in r["stderr"]


def test_no_call_site_hands_a_hash_to_condition():
    """A condition built from the message would re-create the trauma with a
    different spelling. Scan every caller in the tree, not just the ones I
    happened to edit (W107: census the producers).

    Shell is scanned too: the first version of this test looked only at .py and
    was therefore blind to `ALERT_CONDITION=`, which is exactly where a hash
    lived. A scan that excludes the language the defect is written in reports
    clean by construction.
    """
    offenders = []
    paths = [p for pat in ("scripts/**/*.py", "apps/**/*.py", "scripts/**/*.sh")
             for p in REPO.glob(pat)]
    for path in paths:
        if "/tests/" in str(path) or path.name == Path(__file__).name:
            continue
        try:
            text = path.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            names = ("condition=" in line) or ("ALERT_CONDITION=" in line)
            low = line.lower()
            # Case-insensitively — the watcher's variables are MD5_SHORT and
            # LAST_MD5, so a lowercase-only scan walked straight past the one
            # construction this test claims to judge.
            hashy = any(h in low for h in ("md5", "sha1", "sha256", "hexdigest"))
            # ...and the rule is about WHAT is hashed, not that a hash appears.
            # Hashing the MESSAGE is the trauma: the message carries the
            # measurement, so the key moves with it. Hashing an observed
            # artifact (a settings file's content) names a real entity and is
            # the opposite thing. Naming the distinction beats an allow-list,
            # which would excuse the next offender by location (W109).
            hashes_the_message = any(
                t in low for t in ("message", "msg", "text", "alert_msg", "full_message")
            )
            if names and hashy and hashes_the_message:
                offenders.append(f"{path.relative_to(REPO)}:{i}  {line.strip()[:80]}")
    assert not offenders, "a condition built from a hash is the trauma:\n  " + "\n  ".join(offenders)


# ------------------------------------- the layers the fake gateway cannot show
def test_same_text_different_conditions_both_reach_the_gateway(sentinel_with_local_dedup):
    """The local fast-path keyed on the message ALONE, so two different
    conditions that happen to word themselves identically collided BEFORE the
    gateway could tell them apart — the second was answered False here and
    worker:b was never reported at all."""
    a = sentinel_with_local_dedup
    assert a.send_alert("worker unavailable", condition="worker:a") is True
    assert a.send_alert("worker unavailable", condition="worker:b") is True
    assert _keys(a) == ["sentinel:worker:a:info", "sentinel:worker:b:info"]


def test_a_severity_upgrade_is_not_eaten_by_the_local_fastpath(sentinel_with_local_dedup):
    """Same text, INFO then CRITICAL. A severity upgrade is news."""
    a = sentinel_with_local_dedup
    assert a.send_alert("disk pressure", level="INFO", condition="disk") is True
    assert a.send_alert("disk pressure", level="CRITICAL", condition="disk") is True
    assert len(_keys(a)) == 2


def test_the_level_is_part_of_the_gateway_key(sentinel):
    """tg_notify resolves the key BEFORE it looks at the tier, and its dedup
    block returns "deduped" whatever the tier — so a key spanning severities
    lets a WARNING mute the CRITICAL that follows. One job's escalation from
    UNKNOWN/WARNING to DETERMINISTIC/CRITICAL is the whole point of the alert."""
    sentinel.send_alert("Tier 4 needed — j", level="WARNING", condition="tier-escalation:j")
    sentinel.send_alert("Tier 3 needed — j", level="CRITICAL", condition="tier-escalation:j")
    keys = _keys(sentinel)
    assert keys == ["sentinel:tier-escalation:j:warning", "sentinel:tier-escalation:j:critical"]


def test_a_repeat_at_the_same_severity_still_collapses(sentinel):
    """INNOCENCE for the line above: adding the level must not un-collapse the
    repeats the ladder exists to mute."""
    for _ in range(3):
        sentinel.send_alert("Tier 4 needed — j", level="WARNING", condition="tier-escalation:j")
    assert len(set(_keys(sentinel))) == 1


def test_every_escalation_marks_only_on_a_real_send():
    """The 4h local cooldown and the gateway's 6h window are two clocks. At
    t=4h05 the branch reopens, the gateway can still answer "deduped", and
    marking regardless records an escalation nobody received — pushing the next
    real attempt to t=8h05. `_check_blind_heal_loop` always had this right;
    the three job sites did not, and NAMING the condition is precisely what
    makes the gateway start answering "deduped" there."""
    src = (REPO / "scripts" / "nuzantara-sentinel.py").read_text()
    tree = ast.parse(src)
    ungated = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)):
            continue
        call = node.value
        if getattr(call.func, "id", "") != "mark_escalation_sent":
            continue
        # An Expr statement means it is NOT the body of `if send_alert(...)`.
        ungated.append(node.lineno)
    # Every mark must sit inside an `if send_alert(...)` body.
    marks = [n.lineno for n in ast.walk(tree)
             if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "mark_escalation_sent"]
    gated = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and isinstance(node.test, ast.Call) \
                and getattr(node.test.func, "id", "") == "send_alert":
            gated += [n.lineno for n in ast.walk(node)
                      if isinstance(n, ast.Call)
                      and getattr(n.func, "id", "") == "mark_escalation_sent"]
    assert marks, "no mark_escalation_sent call sites found — census broke"
    assert set(marks) == set(gated), (
        f"mark_escalation_sent at lines {sorted(set(marks) - set(gated))} runs whether or not "
        f"the alert was delivered"
    )


# ------------------------------------------- the REAL gateway, not a stand-in
@pytest.fixture
def real_gateway(tmp_path, monkeypatch):
    """Drive send_alert into the actual tg_notify.py, hermetically.

    Every test above stubs the gateway, which proves the ARGV and nothing else.
    That surface is necessary and not sufficient: the key is only half a
    contract, and the ladder, the identity fallback and the tier interaction
    all live on the other side of that subprocess boundary. TG_SPOOL_DIR and an
    empty secrets file keep it off the network and off fleet state.
    """
    spool = tmp_path / "spool"
    monkeypatch.setenv("TG_SPOOL_DIR", str(spool))
    monkeypatch.setenv("TG_SECRETS_FILE", str(tmp_path / "no-secrets.env"))
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    import sentinel_lib.alerter as alerter
    monkeypatch.setattr(alerter, "DEDUP_FILE", str(tmp_path / "dedup.json"))
    alerter._spool = spool
    return alerter


def _spooled_keys(alerter) -> list[str]:
    out = []
    for name in ("archive-p0.jsonl", "pending.jsonl", "log-only.jsonl"):
        f = alerter._spool / name
        if f.exists():
            out += [json.loads(l)["key"] for l in f.read_text().splitlines() if l.strip()]
    return out


def test_the_local_key_cannot_be_forged_by_message_content(real_gateway):
    """The LOCAL fast-path key is built from (level, condition, message), and
    how those three are joined is load-bearing, not cosmetic.

    Any separator-join is forgeable, because nothing forbids a message from
    containing the separator. With `\\x1f` as the joiner these two alerts
    serialise to the SAME bytes:

        (WARNING, "worker:a",       "down\\x1fhard")
        (WARNING, "worker:a\\x1fdown", "hard")

    so the second one is swallowed HERE — it returns True and the gateway never
    sees it, which is the original trauma reappearing one layer lower and
    harder to see, since the argv assertions upstream all still pass. A length
    prefix cannot be forged by data.

    Asserted through the REAL gateway, on the observable that matters: two
    distinct pieces of news, two records in the spool. This was the last
    survivor of the mutation set — the cure was written and asserted by
    nothing.
    """
    real_gateway.send_alert("down\x1fhard", level="WARNING", condition="worker:a")
    real_gateway.send_alert("hard", level="WARNING", condition="worker:a\x1fdown")
    keys = _spooled_keys(real_gateway)
    assert len(keys) == 2, f"the second alert was eaten by a forged local key: {keys}"


def test_real_gateway_keeps_two_conditions_apart(real_gateway):
    """End-to-end: two conditions, two keys, two records in the spool."""
    real_gateway.send_alert("Tier 4 needed — a", condition="tier-escalation:a")
    real_gateway.send_alert("Tier 4 needed — b", condition="tier-escalation:b")
    keys = _spooled_keys(real_gateway)
    assert len(set(keys)) == 2, f"the real gateway collapsed two conditions: {keys}"


def test_real_gateway_mutes_the_repeat_of_one_condition(real_gateway):
    """The ladder, exercised for real: the same condition re-measured inside the
    first window reaches the gateway and is suppressed THERE — which is the
    whole design, and what the md5 key made impossible."""
    assert real_gateway.send_alert("BLIND HEAL-LOOP: 3 cycles",
                                   condition="blind_heal_loop") is True
    # True, not False: the operator HAS this news. What proves the suppression
    # is the spool holding one record, not the return value.
    assert real_gateway.send_alert("BLIND HEAL-LOOP: 99 cycles",
                                   condition="blind_heal_loop") is True
    assert len(_spooled_keys(real_gateway)) == 1


def test_real_gateway_lets_a_severity_upgrade_through(real_gateway):
    """Objection 5, proven on the real thing: tg_notify resolves the key before
    it reads the tier, so without the level in the key this CRITICAL would be
    swallowed by the WARNING that preceded it."""
    assert real_gateway.send_alert("Tier 4 needed — j", level="WARNING",
                                   condition="tier-escalation:j") is True
    assert real_gateway.send_alert("Tier 3 needed — j", level="CRITICAL",
                                   condition="tier-escalation:j") is True
    assert len(set(_spooled_keys(real_gateway))) == 2


def test_real_gateway_derives_an_identity_when_nothing_is_named(real_gateway):
    """The unnamed half: two re-measurements of one sentence must land on ONE
    derived identity — proving the fallback is really condition_identity() and
    not something this corpus re-implemented."""
    assert real_gateway.send_alert("Pro machine heartbeat STALE — last seen 3h ago.") is True
    assert real_gateway.send_alert("Pro machine heartbeat STALE — last seen 9h ago.") is True
    assert len(_spooled_keys(real_gateway)) == 1


def test_auth_sentinel_names_which_credentials_not_how_many():
    """OBJ2, and it survived a mutation because I fixed it without testing it.

    `emit_alert` puts the count in the headline and each credential on a later
    line; `condition_identity()` reads the first line with digits stripped. So
    "1 credenziale" for a revoked Codex token and "1 credenziale" for an Agy
    login two hours later derive the SAME identity and the second is muted — a
    different credential needing a different gesture, silently lost. Before this
    diff the moving md5 key accidentally protected it; naming the condition is
    what makes the loss possible, so naming the SET is what closes it.
    """
    src = (REPO / "scripts" / "auth_sentinel.py").read_text()
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "emit_alert")
    calls = [n for n in ast.walk(fn)
             if isinstance(n, ast.Call) and ast.unparse(n.func).endswith("send_alert")]
    assert calls, "emit_alert no longer sends an alert — census broke"
    primary = calls[0]
    cond = next((k.value for k in primary.keywords if k.arg == "condition"), None)
    assert cond is not None, "emit_alert does not name its condition"
    rendered = ast.unparse(cond)
    if isinstance(cond, ast.Name):  # resolve `condition = <expr>` in the body
        rendered = next(
            (ast.unparse(n.value) for n in ast.walk(fn)
             if isinstance(n, ast.Assign)
             and any(getattr(t, "id", "") == cond.id for t in n.targets)),
            rendered,
        )
    assert "p.arm" in rendered and "sorted" in rendered, (
        f"the condition must name WHICH credentials, sorted so scan order is not "
        f"an identity: got {rendered}"
    )


def test_deduped_reports_the_operator_HAS_the_news(real_gateway):
    """The return contract, on the real gateway.

    Once callers gate their 4h cooldown on this value, "deduped" must not read
    as failure: it means the gateway already carried this condition to the
    operator inside the mute window. Reporting False there re-arms the alert
    every 5 minutes for the whole window — a subprocess storm that changes no
    message, because every one of them is deduped again. False is reserved for
    "it did not get through".
    """
    assert real_gateway.send_alert("Tier 4 needed — j", condition="tier-escalation:j") is True
    assert real_gateway.send_alert("Tier 4 needed — j, now 9 fails",
                                   condition="tier-escalation:j") is True
    assert len(_spooled_keys(real_gateway)) == 1, "the second one must be suppressed, not sent"


def test_a_real_failure_still_reports_false(sentinel):
    """INNOCENCE for the line above: a broken gateway must still say False, or
    `mark_escalation_sent` would record an escalation nobody received."""
    broken = Path(sentinel._argv_log).parent / "broken.py"
    broken.write_text("import sys; sys.exit(3)\n")
    sentinel._gateway_script = lambda: str(broken)
    assert sentinel.send_alert("x", condition="c") is False


def test_the_watchers_launchagent_is_tracked_and_points_at_the_promoted_script():
    """Promoting the script without its plist tracks the payload and not the
    ACTIVATION: the corpus would stay green while nothing invoked it, which is
    superscar #2 wearing a green test. The plist is the thing that says WHEN
    this runs, and it is what makes the WatchPaths reasoning above (fires on
    change, not on a timer, so a stuck state file retries rather than storms)
    a fact about the deployment rather than an assumption in a comment."""
    import plistlib

    plist = REPO / "infra" / "launchagents" / "com.balizero.claude-settings-watcher.plist"
    d = plistlib.loads(plist.read_bytes())
    assert d["Label"] == "com.balizero.claude-settings-watcher"
    assert any("claude-settings-change-alert.sh" in str(a) for a in d["ProgramArguments"])
    assert d["WatchPaths"], "no WatchPaths — the retry-not-storm argument dies with it"
    assert any(str(w).endswith(".claude/settings.json") for w in d["WatchPaths"])
    # launchd will not start a second instance of a running job, and this adds
    # a 30s floor on top — which is what bounds the unlocked read/write of the
    # state file to a theoretical race rather than a live one.
    assert int(d.get("ThrottleInterval", 0)) >= 30

    pairs = json.loads((REPO / "infra" / "home-fork" / "declared-pairs.json").read_text())["pairs"]
    declared = {p["repo"] for p in pairs}
    assert "infra/launchagents/com.balizero.claude-settings-watcher.plist" in declared
    assert "scripts/claude-settings-change-alert.sh" in declared


def test_the_auth_fallback_keeps_the_identity_the_primary_path_fixed():
    """OBJ: the except-branch keyed on `auth-sentinel-<host>`, host-wide, which
    erases the per-credential identity one line above — a Codex failure and a
    different Agy failure two hours later would share a key and the second
    would be muted. An exception branch is not a place where identity is
    cheaper. It also returned True without looking at the subprocess."""
    src = (REPO / "scripts" / "auth_sentinel.py").read_text()
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "emit_alert")
    handlers = [h for h in ast.walk(fn) if isinstance(h, ast.ExceptHandler)]
    assert handlers, "the fallback branch vanished — census broke"
    body = "\n".join(ast.unparse(h) for h in handlers)
    assert "--dedup-key" in body
    key_line = next(l for l in body.splitlines() if "--dedup-key" in l)
    assert "condition" in key_line, (
        f"the fallback key drops the per-credential identity: {key_line.strip()}"
    )
    assert "sentinel:" in key_line, (
        f"the fallback invents its own namespace instead of the alerter's: {key_line.strip()}"
    )
    assert "return True" not in body, "the fallback still claims success blindly"


def test_the_local_key_cannot_be_confused_by_a_separator_in_the_data(sentinel_with_local_dedup):
    """`f"{level}|{condition}|{message}"` is not injective: condition="worker:a"
    with message="b|c" serialises identically to condition="worker:a|b" with
    message="c", so the second alert would be swallowed locally. Nothing
    forbids `|` in a job id. The separator is \\x1f (unit separator), which no
    message carries."""
    a = sentinel_with_local_dedup
    assert a.send_alert("b|c", condition="worker:a") is True
    assert a.send_alert("c", condition="worker:a|b") is True
    assert len(_keys(a)) == 2, "two distinct alerts collapsed on the local key"


def test_the_ocr_gate_names_which_surface_degraded():
    """Seven DISTINCT context literals — portal document OCR, vision RAG, the
    CRM passport extractor, intake, pdf_vision... Dropping the context fused
    them, so a portal block at 10:00 and a vision-RAG block at 11:00 shared one
    identity and the second degraded service never reached Telegram. A shared
    remediation does not make the affected surfaces interchangeable.

    The number is MEASURED, not narrated: the comment said "six", and counting
    files says eight — neither is the entity. What sizes the key space is the
    set of distinct literals the gate can be handed, so that is what is counted
    here. The one non-literal call site is a forwarding wrapper, and it is
    asserted to stay a forwarder: if it ever hardcoded its own context, two
    surfaces would fuse again with the census still reading seven.
    """
    literals, forwarders = set(), []
    for path in REPO.glob("apps/**/*.py"):
        if "/tests/" in str(path):
            continue
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and getattr(node.func, "id", "")
                    in ("note_cloud_ocr_blocked", "_note_cloud_ocr_blocked")):
                continue
            arg = node.args[0] if node.args else None
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                literals.add(arg.value)
            else:
                forwarders.append(f"{path}:{node.lineno} -> {ast.unparse(arg) if arg else '()'}")
    assert len(literals) == 7, f"the OCR context census moved: {sorted(literals)}"
    assert all("context" in f for f in forwarders), (
        f"a wrapper stopped forwarding its caller's context — surfaces fuse: {forwarders}")
    src = (REPO / "apps" / "backend-rag" / "backend" / "services" / "multimodal"
           / "cloud_vision_gate.py").read_text()
    call = next(n for n in ast.walk(ast.parse(src))
                if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "send_alert")
    cond = next(k.value for k in call.keywords if k.arg == "condition")
    rendered = ast.unparse(cond)
    assert "context" in rendered, f"the OCR condition fuses every surface: {rendered}"


def test_a_standing_halt_does_not_change_family_on_the_next_run():
    """A JSON corruption announces itself as `halt:corrupt-registry` on the run
    that DETECTS it; every later run takes the HALT-file branch instead. That
    branch used to name one cause, so a single incident wore two families — and
    the false checksum identity could then mute a real checksum mismatch. The
    stored reason is already in the message; the identity is "a halt stands"."""
    src = (REPO / "scripts" / "nuzantara-sentinel.py").read_text()
    conds = re.findall(r'condition="(halt:[^"]+)"', src)
    assert "halt:standing" in conds, f"the standing-halt branch names a cause: {conds}"
    detectors = [c for c in conds if c != "halt:standing"]
    assert "halt:standing" not in detectors
    assert len(set(conds)) == len(set(detectors)) + 1, conds


def test_each_openclaw_restart_is_its_own_episode():
    """Two successful restarts two hours apart are two events, and a burst of
    them IS the restart-loop signal. One stable name would hide exactly that,
    then escalate the silence to a week. `_record_openclaw_restart()` stamps
    the attempt; that stamp is the episode id."""
    src = (REPO / "scripts" / "nuzantara-sentinel.py").read_text()
    assert 'condition=f"openclaw-restarted:{_last_openclaw_restart_ts()}"' in src
    assert "def _last_openclaw_restart_ts()" in src, "the episode id has no source"
    # ...and it must read the record the restart path just wrote, not the clock:
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "_last_openclaw_restart_ts")
    body = ast.unparse(fn)
    assert "OPENCLAW_RESTART_RECORD" in body and "time.time()" not in body


def test_the_auth_fallback_reports_what_the_subprocess_actually_did(monkeypatch, tmp_path):
    """EXECUTED, not grepped. The first version of this cure wrote `rc = _run(...)`
    and `return rc == 0` — but `_run` returns a TUPLE `(exit_code, output)`, so the
    comparison was always False and every successful fallback reported failure.
    The test that shipped with it asserted the STRING "rc == 0" was present, which
    is true of the broken code: it proved the text, not the behaviour (W116)."""
    sys.path.insert(0, str(REPO / "scripts"))
    import importlib
    auth = importlib.import_module("auth_sentinel")

    calls = []
    real_run = auth._run

    def fake_run(cmd, **kw):
        # Intercept ONLY the gateway call. Stubbing every _run also stubs the
        # `hostname -s` probe, and the host then leaks into the key under test —
        # a fixture measuring its own bluntness rather than the code (W108).
        if any("tg_notify" in str(c) for c in cmd):
            calls.append(cmd)
            return (0, "tg_notify: spooled")
        return real_run(cmd, **kw)

    monkeypatch.setattr(auth, "_run", fake_run)
    # force the fallback: make the primary path raise
    import sentinel_lib.alerter as alerter
    monkeypatch.setattr(alerter, "send_alert",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(auth, "REPO", REPO)

    probe = auth.Probe(arm="codex", family="openai", status=auth.ACTION,
                       detail="token revoked", fix_cmd="codex login")
    assert auth.emit_alert([probe]) is True, "a successful fallback reported failure"
    # calls[0] is the `hostname -s` probe; the gateway call is the last one.
    gw = next(c for c in calls if "--dedup-key" in c)
    key = gw[gw.index("--dedup-key") + 1]

    # ...and the identity must be the SAME BYTES the primary path builds.
    assert key == "sentinel:auth:codex:warning", key

    # exit 0 with a failed gateway: tg_notify.main() returns 0 even when both
    # notify() and the emergency spool fail, so the exit code is not the verdict.
    calls.clear()

    def fake_run_broken(cmd, **kw):
        if any("tg_notify" in str(c) for c in cmd):
            calls.append(cmd)
            return (0, "tg_notify: internal error")
        return real_run(cmd, **kw)

    monkeypatch.setattr(auth, "_run", fake_run_broken)
    assert auth.emit_alert([probe]) is False, "exit 0 was mistaken for delivery"
