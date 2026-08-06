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
    assert a.send_alert("identical text", condition="c") is False
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


def _run_watcher(home: Path, settings: str, alerter_body: str) -> dict:
    """Run the real script against a throwaway HOME and a fake alerter module."""
    (home / ".claude").mkdir(parents=True, exist_ok=True)
    (home / ".claude" / "settings.json").write_text(settings)
    lib = home / "scripts" / "sentinel_lib"
    lib.mkdir(parents=True, exist_ok=True)
    (lib / "__init__.py").write_text("")
    (lib / "alerter.py").write_text(alerter_body)
    (home / ".agent" / "decisions").mkdir(parents=True, exist_ok=True)
    calls = home / "calls.jsonl"
    env = {**os.environ, "HOME": str(home), "FAKE_CALLS": str(calls)}
    proc = subprocess.run(["bash", str(WATCHER)], capture_output=True, text=True, env=env)
    state = home / ".agent" / "decisions" / "claude-settings-last-md5"
    return {
        "rc": proc.returncode,
        "stderr": proc.stderr,
        "state": state.read_text().strip() if state.exists() else "",
        "calls": [json.loads(l) for l in calls.read_text().splitlines()] if calls.exists() else [],
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
    new_side = c1.split("->", 1)[1]
    assert len(new_side) == 12 and all(ch in "0123456789abcdef" for ch in new_side), c1

    second = _run_watcher(home, '{"a": 2}', _FAKE_ALERTER)
    c2 = second["calls"][-1]["condition"]
    assert c2 != c1

    # A -> B -> A: the third fire must NOT reuse the first key.
    third = _run_watcher(home, '{"a": 1}', _FAKE_ALERTER)
    c3 = third["calls"][-1]["condition"]
    assert c3 not in (c1, c2), f"A->B->A collapsed onto an earlier key: {c3}"


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
            hashy = any(h in line for h in ("md5", "sha1", "sha256", "hexdigest"))
            if names and hashy:
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
