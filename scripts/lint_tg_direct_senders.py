#!/usr/bin/env python3
"""lint_tg_direct_senders.py — the anti-regrowth guard for the Telegram gateway.

The 2026-07-06 census found ~240 tracked files calling api.telegram.org
directly. Those are GRANDFATHERED (infra/tg-gateway/grandfathered.json) and
will migrate to scripts/tg_notify.py cohort by cohort. This lint fails CI when
a NEW file joins the direct-sender family, so it can only shrink.

Verdict logic:
  exit 0  — no new direct senders
  exit 1  — new direct sender(s) outside the grandfather list (guilt)
  exit 2  — blind-scan guard: zero files scanned (a lint that scanned nothing
            must not report "clean" — W84 green-but-dead)

Modes:
  --freeze     regenerate grandfathered.json from the current tree
  --prune      report grandfathered entries that no longer send directly
  --selftest   guilt+innocence fixtures in a temp tree

Registered in infra/guard-conformance/registry.json (superscar #3: a guard
ships only with both a guilt and an innocence proof).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PATTERN = "api.telegram.org"
# 2026-07-28: `.yml`/`.yaml` ADDED. The census that founded this lint could not
# see GitHub Actions at all — the surface where the alarms actually live — so
# "the family can only shrink" was true of a family with 20 uncounted members
# (18 workflows sending directly, 28 call sites). A guard whose scope
# structurally skips a surface reports clean about a place it never looked
# (superscar #3, UNDER-match). Widening the scope is only half the cure: see
# LEGACY_SCAN_SUFFIXES and check_monotone for how the register is allowed to
# enroll a newly-visible surface WITHOUT reopening the door to new senders.
SCAN_SUFFIXES = {
    ".sh", ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".plist", ".rb", ".pl", ".zsh", ".bash", ".yml", ".yaml",
}
# The surface the 2026-07-06 census could actually see. A register frozen
# before the scope widened does not declare its own scope, so this constant is
# what it MEANT. It is a historical fact, not a setting — never edit it.
LEGACY_SCAN_SUFFIXES = {
    ".sh", ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".plist", ".rb", ".pl", ".zsh", ".bash",
}
# NOTE (deliberate over-match, superscar #3 traded consciously): the scan is
# textual, so a MENTION in a comment/docstring counts as a hit. That is the
# safe direction — keep the URL string out of non-gateway files entirely.
GATEWAY_ALLOWLIST = {
    "scripts/tg_notify.py",        # the gateway itself
    "scripts/tg_digest_flush.py",  # its flusher
    "scripts/lint_tg_direct_senders.py",  # this lint (pattern is its constant)
    "scripts/tests/test_tg_gateway.py",   # the gateway's own test fixtures
    "scripts/tests/test_agent_job_telegram_gateway.py",  # asserts the string's ABSENCE
    ".github/workflows/tg-gateway.yml",   # the gateway's own CI job (names it in a comment)
    # The CI arm of the same family. It is NOT a second gateway: tg_notify.py
    # answers to a machine with a spool that a flusher drains later, so its
    # contract is "NEVER fail the caller" (main() returns 0 even when the send
    # failed and was spooled). On an ephemeral runner that spool dies with the
    # container, so on CI that same contract IS the W104 silence. The CI arm
    # inverts it: read the reply, fail the step loudly, no spool.
    "scripts/ci/telegram_notify.sh",
    # Redacts bot tokens FROM logs (#4102) — never sends. Its docstring
    # writes the URL as a worked example of what to strip, and its test
    # builds a FAKE_URL constant + a simulated traceback line to prove the
    # redaction filter catches a token even inside an exception message.
    # Zero requests.post/httpx calls in either file — the bare-substring
    # PATTERN match is on prose *about* the pattern, not code using it.
    "apps/backend-rag/backend/core/secret_log_redaction.py",
    "apps/backend-rag/backend/tests/core/test_telegram_token_never_reaches_a_log.py",
    # Refuses a bot TOKEN in the tree (2026-08-13) — never sends. Same shape as
    # the redaction pair above: zero urlopen/requests/httpx call sites in
    # either file, and the URL appears twice as prose and twice as a guilt
    # FIXTURE. The fixture is the point: the first draft of that lint was blind
    # to a token inside `api.telegram.org/bot<TOKEN>/sendMessage`, the likeliest
    # hiding place there is, because a leading `\b` cannot match after the `t`
    # of `bot`. Removing the URL from the corpus to appease a textual scan would
    # delete the one case that proves the fix — the bare-substring PATTERN match
    # here is on prose and fixtures ABOUT the pattern, not code using it.
    "scripts/lint_telegram_tokens.py",
    "scripts/tests/test_lint_telegram_tokens.py",
}

# Printed under the offender list. Kept next to GATEWAY_ALLOWLIST so the two stay
# in sync: the second remedy below is that constant, and it costs a reviewed edit
# to this file precisely so it is not the reflex.
HINT_FOR_PROSE = (
    "\nlint_tg: if a file above only DESCRIBES the endpoint rather than calling it "
    "(evidence pack, runbook, test fixture), there is no sender to migrate. Two "
    "remedies, in order of preference:\n"
    "  1. rephrase so the literal does not appear — e.g. \"a direct Bot API call\" "
    "instead of the host string. Costs one sentence, keeps the guard intact.\n"
    "  2. add the path to GATEWAY_ALLOWLIST in this file, with a comment saying why "
    "that file legitimately carries the pattern as prose. Costs a reviewed edit to "
    "the guard, and does not scale — prefer 1.\n"
    "The over-match is deliberate (see the comment above GATEWAY_ALLOWLIST): keeping "
    "the string out of non-gateway files is the point, not a side effect."
)


def _root() -> Path:
    return Path(os.environ.get("TG_LINT_ROOT", ".")).resolve()


def _grandfather_path(root: Path) -> Path:
    return root / "infra" / "tg-gateway" / "grandfathered.json"


def tracked_files(root: Path) -> list[Path]:
    env_list = os.environ.get("TG_LINT_FILES", "")
    if env_list:  # selftest fixture path: explicit file list, no git needed
        return [root / f for f in env_list.split(":") if f]
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files"],
            capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [root / line for line in out.splitlines() if Path(line).suffix in SCAN_SUFFIXES]


def scan(root: Path) -> tuple[set[str], int]:
    """Return (relative paths of direct senders, files scanned)."""
    senders: set[str] = set()
    scanned = 0
    for path in tracked_files(root):
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        scanned += 1
        if PATTERN in text:
            senders.add(str(path.relative_to(root)))
    return senders, scanned


def load_grandfathered(root: Path) -> set[str]:
    try:
        data = json.loads(_grandfather_path(root).read_text())
        return set(data.get("files", []))
    except (OSError, ValueError):
        return set()


def freeze(root: Path) -> int:
    senders, scanned = scan(root)
    if scanned == 0:
        print("lint_tg: BLIND SCAN — zero files scanned, refusing to freeze", file=sys.stderr)
        return 2
    payload = {
        "_doc": (
            "Direct api.telegram.org senders grandfathered at gateway birth "
            "(2026-07-06). This list only SHRINKS: migrate a file to "
            "scripts/tg_notify.py, then remove it here (or run --prune). "
            "New files must use the gateway — the lint fails CI otherwise."
        ),
        "frozen_at": "2026-07-06",
        # The scope this register actually covered when it was written. Without
        # it, a later reader cannot tell "no senders in .yml" from "nobody ever
        # looked at .yml" — and those two read identically in a green check.
        "scan_suffixes": sorted(SCAN_SUFFIXES),
        "files": sorted(senders - GATEWAY_ALLOWLIST),
    }
    gp = _grandfather_path(root)
    gp.parent.mkdir(parents=True, exist_ok=True)
    # indent=2 is not cosmetic: the repo's pre-commit runs prettier on staged
    # files, and prettier rewrites this JSON at 2. Writing 1 here (as this did
    # until 2026-07-28, when prettier first saw the file) makes `--freeze`
    # produce output its own commit hook rejects — a tool that cannot commit
    # what it generates gets run once and then avoided.
    gp.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"lint_tg: froze {len(payload['files'])} grandfathered direct senders")
    return 0


def _guard_new_direct_sender(senders: set, grandfathered: set) -> set:
    """The guard proper (censused in guard-conformance registry, superscar #3).

    GUILT: a file outside grandfathered+gateway that hits api.telegram.org is
    flagged. INNOCENCE: grandfathered legacy senders and the gateway itself
    are never flagged.
    """
    return senders - grandfathered - GATEWAY_ALLOWLIST


def check_monotone(root: Path) -> tuple[bool, set]:
    """Anti-bypass (Codex finding 2026-07-06): a PR could add a sender AND
    grandfather it in the same diff. The list may only SHRINK vs origin/main.
    Returns (ok, illegally_added). Skips gracefully when origin/main has no list
    yet (gateway-birth PR) or git is unavailable (selftest: TG_LINT_BASE_JSON).

    ONE exemption, added 2026-07-28 with the `.yml` widening. Growth is legal
    only for a file whose SUFFIX the base register could not see — enrolling a
    surface that was invisible is not the same act as adding a new sender to a
    surface already being watched. Without it, a blind surface can never be
    enrolled and therefore stays blind forever, which is how `.yml` went 22 days
    uncounted. The exemption cannot launder a new `.py` sender: its suffix was
    always visible, so it still FAILS. The base register declares the scope it
    froze (`scan_suffixes`); a register written before that key existed means
    LEGACY_SCAN_SUFFIXES, which is why that constant is a fact and not a knob.
    """
    base_override = os.environ.get("TG_LINT_BASE_JSON", "")
    try:
        if base_override:
            old_raw = Path(base_override).read_text()
        else:
            old_raw = subprocess.run(
                ["git", "-C", str(root), "show", "origin/main:infra/tg-gateway/grandfathered.json"],
                capture_output=True, text=True, check=True,
            ).stdout
        old_doc = json.loads(old_raw)
        old = set(old_doc.get("files", []))
    except Exception:
        print("lint_tg: monotone check skipped (no grandfathered.json on origin/main yet)")
        return True, set()

    base_suffixes = set(old_doc.get("scan_suffixes", sorted(LEGACY_SCAN_SUFFIXES)))
    newly_visible = SCAN_SUFFIXES - base_suffixes

    added = load_grandfathered(root) - old
    enrolled = {f for f in added if Path(f).suffix in newly_visible}
    if enrolled:
        print(f"lint_tg: {len(enrolled)} entr(y/ies) enrolled from a surface the base "
              f"register could not see ({', '.join(sorted(newly_visible))}) — allowed once, "
              f"in the same diff that makes the surface visible")
    illegal = added - enrolled
    return (not illegal), illegal


def lint(root: Path, prune: bool = False) -> int:
    senders, scanned = scan(root)
    if scanned == 0:
        print("lint_tg: BLIND SCAN — zero files scanned; not clean, BROKEN", file=sys.stderr)
        return 2
    grandfathered = load_grandfathered(root)
    offenders = _guard_new_direct_sender(senders, grandfathered)

    if prune:
        gone = grandfathered - senders
        if gone:
            print(f"lint_tg: {len(gone)} grandfathered files no longer send directly — prunable:")
            for f in sorted(gone):
                print(f"  - {f}")
        else:
            print("lint_tg: nothing to prune")

    if offenders:
        print(f"lint_tg: FAIL — {len(offenders)} NEW direct Telegram sender(s). "
              f"Use scripts/tg_notify.py (--tier p0|digest|log) instead:", file=sys.stderr)
        for f in sorted(offenders):
            print(f"  - {f}", file=sys.stderr)
        # The scan is a bare substring match on purpose (see the comment above
        # GATEWAY_ALLOWLIST), so a file that only WRITES ABOUT the endpoint —
        # an evidence pack, a runbook, a test fixture — lands here too, and for
        # that author "use tg_notify.py instead" is not actionable advice: there
        # is no sender to migrate. Measured 2026-08-31: nothing anywhere else in
        # this repo tells a pack author the literal is forbidden, so this message
        # is the only place the remedy can reach them.
        print(HINT_FOR_PROSE, file=sys.stderr)
        return 1

    mono_ok, added = check_monotone(root)
    if not mono_ok:
        print(f"lint_tg: FAIL — grandfathered.json GREW by {len(added)} entr(y/ies) vs "
              f"origin/main (the list only shrinks; migrate to the gateway instead):",
              file=sys.stderr)
        for f in sorted(added):
            print(f"  - {f}", file=sys.stderr)
        return 1

    print(f"lint_tg: clean ({scanned} files scanned, {len(grandfathered)} grandfathered)")
    return 0


def selftest() -> int:
    import tempfile

    failures = []

    def check(name, cond):
        print(("  ok  " if cond else "  FAIL") + f" {name}")
        if not cond:
            failures.append(name)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "infra" / "tg-gateway").mkdir(parents=True)
        (root / "scripts").mkdir()
        old = root / "scripts" / "old_sender.sh"
        old.write_text("curl https://api.telegram.org/botX/sendMessage\n")
        innocent = root / "scripts" / "clean_tool.py"
        innocent.write_text("print('uses gateway via tg_notify')\n")
        docmention = root / "scripts" / "README.txt"  # not in SCAN_SUFFIXES
        docmention.write_text("mentions api.telegram.org harmlessly\n")
        gateway = root / "scripts" / "tg_notify.py"
        gateway.write_text("API = 'https://api.telegram.org'\n")

        os.environ["TG_LINT_ROOT"] = str(root)
        os.environ["TG_LINT_FILES"] = "scripts/old_sender.sh:scripts/clean_tool.py:scripts/tg_notify.py"

        # freeze grandfathers the existing offender
        check("freeze exits 0", freeze(root) == 0)
        gf = json.loads((root / "infra/tg-gateway/grandfathered.json").read_text())["files"]
        check("old sender grandfathered", "scripts/old_sender.sh" in gf)
        check("gateway NOT grandfathered", "scripts/tg_notify.py" not in gf)

        # innocence: clean tree passes
        check("clean tree passes", lint(root) == 0)

        # guilt: a NEW direct sender fails
        new = root / "scripts" / "new_sender.py"
        new.write_text("requests.post('https://api.telegram.org/bot')\n")
        os.environ["TG_LINT_FILES"] += ":scripts/new_sender.py"
        check("new sender FAILS", lint(root) == 1)

        # innocence: gateway allowlist never flagged even when new
        os.environ["TG_LINT_FILES"] = "scripts/tg_notify.py:scripts/clean_tool.py"
        check("gateway alone passes", lint(root) == 0)

        # blind-scan guard
        os.environ["TG_LINT_FILES"] = "scripts/does_not_exist.py"
        check("blind scan → exit 2", lint(root) == 2)

        # monotone guard: grandfathered.json growing vs base = FAIL
        os.environ["TG_LINT_FILES"] = "scripts/old_sender.sh:scripts/clean_tool.py"
        base = root / "base_grandfathered.json"
        base.write_text(json.dumps({"files": []}))  # base list EMPTY, current has old_sender
        os.environ["TG_LINT_BASE_JSON"] = str(base)
        check("grandfather growth → FAIL", lint(root) == 1)
        base.write_text(json.dumps({"files": ["scripts/old_sender.sh"]}))  # base == current
        check("grandfather stable → pass", lint(root) == 0)
        os.environ.pop("TG_LINT_BASE_JSON", None)

        # ---- the .yml surface, widened 2026-07-28 -----------------------
        # These four cases exist because the widening added an EXEMPTION to the
        # monotone rule, and an exemption is a guard at inverted sign (W91): it
        # needs its own guilt and its own innocence, or it becomes the bypass
        # the monotone rule was written to close.
        wf = root / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "alarm.yml").write_text(
            '        run: curl -sS "https://api.telegram.org/bot$T/sendMessage" -d text=hi\n'
        )
        (wf / "clean.yml").write_text(
            '        run: bash scripts/ci/telegram_notify.sh --text "hi"\n'
        )
        gp = root / "infra" / "tg-gateway" / "grandfathered.json"

        # GUILT: the new surface is actually armed, not merely declared.
        gp.write_text(json.dumps({"files": ["scripts/old_sender.sh"]}))
        os.environ["TG_LINT_FILES"] = "scripts/old_sender.sh:.github/workflows/alarm.yml"
        check("NEW .yml direct sender FAILS", lint(root) == 1)

        # INNOCENCE: a workflow that routes through the CI arm holds no URL.
        os.environ["TG_LINT_FILES"] = "scripts/old_sender.sh:.github/workflows/clean.yml"
        check(".yml routed through the CI arm passes", lint(root) == 0)

        # ENROLLMENT: a newly-visible suffix may join the register once, in the
        # same diff that makes it visible (base declares no scan_suffixes).
        base.write_text(json.dumps({"files": ["scripts/old_sender.sh"]}))
        os.environ["TG_LINT_BASE_JSON"] = str(base)
        gp.write_text(json.dumps({"files": ["scripts/old_sender.sh", ".github/workflows/alarm.yml"]}))
        os.environ["TG_LINT_FILES"] = "scripts/old_sender.sh:.github/workflows/alarm.yml"
        check("newly-visible .yml may enroll", lint(root) == 0)

        # ...but an always-visible suffix may NOT ride along on that exemption.
        (root / "scripts" / "sneaky.py").write_text("post('https://api.telegram.org/bot')\n")
        gp.write_text(json.dumps({"files": [
            "scripts/old_sender.sh", ".github/workflows/alarm.yml", "scripts/sneaky.py",
        ]}))
        os.environ["TG_LINT_FILES"] = (
            "scripts/old_sender.sh:.github/workflows/alarm.yml:scripts/sneaky.py"
        )
        check("a .py can NOT ride the surface exemption", lint(root) == 1)

        # ...and once the base register declares .yml, the door shuts again.
        base.write_text(json.dumps({
            "files": ["scripts/old_sender.sh"], "scan_suffixes": sorted(SCAN_SUFFIXES),
        }))
        gp.write_text(json.dumps({"files": ["scripts/old_sender.sh", ".github/workflows/alarm.yml"]}))
        os.environ["TG_LINT_FILES"] = "scripts/old_sender.sh:.github/workflows/alarm.yml"
        check("with .yml declared, enrolling another .yml FAILS", lint(root) == 1)
        os.environ.pop("TG_LINT_BASE_JSON", None)

        os.environ.pop("TG_LINT_FILES", None)
        os.environ.pop("TG_LINT_ROOT", None)

    print("SELFTEST", "PASS" if not failures else f"FAIL ({failures})")
    return 0 if not failures else 1


def main() -> int:
    args = sys.argv[1:]
    if "--selftest" in args:
        return selftest()
    root = _root()
    if "--freeze" in args:
        return freeze(root)
    return lint(root, prune="--prune" in args)


if __name__ == "__main__":
    sys.exit(main())
