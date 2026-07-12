"""Mata Garuda plist auto-heal watchdog — reinstalls a VANISHED launchd job.

Real remediation (not alert), inside the safe boundary the operator approved
(2026-07-02). It heals EXACTLY ONE failure class:

    a mata_garuda LaunchAgent whose repo snapshot exists, but which is
    ABSENT from ~/Library/LaunchAgents/ OR unknown to launchctl
    (e.g. a reboot/bootout dropped it) → reinstall from the repo snapshot
    (chmod 0644) + `launchctl bootstrap`.

It DELIBERATELY does NOT:
  * restart a loaded-but-crashing job — that is the W2 / cicatrix #7
    restart-storm the organism disarmed on purpose ("restart is the wrong
    cure for a dead heartbeat channel"). A job launchctl already knows is
    left alone; the reload only re-arms a job launchd forgot.
  * heal a plist whose LIVE content diverges from the snapshot — that could
    be a legitimate in-flight operator edit; clobbering it silently is worse
    than the drift. Divergence is REPORTED (stdout), never auto-fixed.

Circuit breaker: at most MAX_HEALS_PER_WINDOW reinstalls of the same label
per WINDOW_SECONDS. Beyond that it stops healing that label and reports —
so a plist that reinstalls-then-vanishes-again cannot storm. State lives in
a small JSON ledger under ~/.organism/.

Why python venv-direct (not a .sh): a .sh under ~/Desktop invoked by launchd
is TCC-dead (exit 127, W84) — the exact bug this whole cutover cured. As a
venv-python module (adhoc-signed) it is TCC-immune and repo-tracked (no
~/scripts HOME-fork, cicatrix #1). Depends only on stdlib (subprocess/json)
— respects the pydantic-only stack rule.

Exit 0 always (a watchdog must never itself go red and trigger noise); it
reports via stdout/heartbeat, and re-raises nothing.
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# ── config ───────────────────────────────────────────────────────────────────
LABEL_PREFIX = "com.matagaruda."
LA_DIR = Path.home() / "Library" / "LaunchAgents"
LEDGER = Path.home() / ".organism" / "matagaruda_plist_heal.ledger.json"
MAX_HEALS_PER_WINDOW = 3
WINDOW_SECONDS = 24 * 3600

# repo snapshot dir — resolved from THIS module's location
# (<repo>/apps/mata-garuda/mata_garuda/workers/plist_watchdog.py → up to repo).
_REPO_ROOT = Path(__file__).resolve().parents[4]
SNAPSHOT_DIR = _REPO_ROOT / "infra" / "launchagents"


def _uid() -> int:
    return os.getuid()


def _domain() -> str:
    return f"gui/{_uid()}"


def _launchctl_knows(label: str) -> bool:
    """True if launchctl has the label in its domain (loaded/known)."""
    r = subprocess.run(
        ["launchctl", "print", f"{_domain()}/{label}"],
        capture_output=True, text=True, timeout=15,
    )
    return r.returncode == 0


def _label_of(plist: Path) -> str:
    """Read the plist's declared :Label. launchctl keys on THIS, not the
    filename — some plists have stem != Label (e.g. com.matagaruda.kita-feed.daily
    declares Label com.matagaruda.kita-feed). Falls back to the filename stem
    if the plist can't be read."""
    try:
        r = subprocess.run(
            ["plutil", "-extract", "Label", "raw", "-o", "-", str(plist)],
            capture_output=True, text=True, timeout=15,
        )
        lbl = r.stdout.strip()
        if r.returncode == 0 and lbl:
            return lbl
    except (OSError, subprocess.SubprocessError):
        pass
    return plist.stem


def _load_ledger() -> dict:
    try:
        return json.loads(LEDGER.read_text())
    except (OSError, ValueError):
        return {}


def _save_ledger(led: dict) -> None:
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        tmp = LEDGER.with_suffix(".tmp")
        tmp.write_text(json.dumps(led))
        os.replace(tmp, LEDGER)
    except OSError:
        pass  # ledger is best-effort; never fail the watchdog on it


def _breaker_ok(led: dict, label: str, now: float) -> bool:
    """True if healing `label` is still under the rate cap in the window."""
    stamps = [t for t in led.get(label, []) if now - t < WINDOW_SECONDS]
    led[label] = stamps
    return len(stamps) < MAX_HEALS_PER_WINDOW


def _record_heal(led: dict, label: str, now: float) -> None:
    led.setdefault(label, []).append(now)


def _heal(label: str, snapshot: Path) -> tuple[bool, str]:
    """Reinstall a vanished job from its snapshot + bootstrap. Best-effort."""
    target = LA_DIR / snapshot.name
    try:
        LA_DIR.mkdir(parents=True, exist_ok=True)
        # copy snapshot → live location, restrictive perms
        target.write_bytes(snapshot.read_bytes())
        os.chmod(target, 0o644)
        # validate before loading
        lint = subprocess.run(["plutil", "-lint", str(target)],
                              capture_output=True, text=True, timeout=15)
        if lint.returncode != 0:
            return False, f"lint-fail: {lint.stdout.strip()}"
        boot = subprocess.run(
            ["launchctl", "bootstrap", _domain(), str(target)],
            capture_output=True, text=True, timeout=30,
        )
        if boot.returncode != 0 and not _launchctl_knows(label):
            return False, f"bootstrap-fail: {boot.stderr.strip() or boot.returncode}"
        return True, "reinstalled+bootstrapped"
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _emit_heartbeat(status: str, meta: dict) -> None:
    """Best-effort organism heartbeat so the watchdog itself is observable."""
    try:
        d = Path.home() / ".organism" / "last_seen"
        d.mkdir(parents=True, exist_ok=True)
        payload = {"ts": time.time(), "status": status,
                   "organ_id": "pro.matagaruda_plist_watchdog", "metadata": meta}
        tmp = d / ".pro.matagaruda_plist_watchdog.json.tmp"
        final = d / "pro.matagaruda_plist_watchdog.json"
        tmp.write_text(json.dumps(payload))
        os.replace(tmp, final)
    except OSError:
        pass


def main() -> int:
    now = time.time()
    led = _load_ledger()
    healed, diverged, breaker_tripped, ok = [], [], [], 0

    snapshots = sorted(glob.glob(str(SNAPSHOT_DIR / f"{LABEL_PREFIX}*.plist")))
    for snap_path in snapshots:
        snapshot = Path(snap_path)
        live = LA_DIR / snapshot.name
        # launchctl keys on the declared Label, which may differ from the stem.
        label = _label_of(snapshot)

        present = live.exists()
        known = _launchctl_knows(label)

        if present and known:
            # loaded & known — leave it alone (W2 boundary). Report divergence only.
            try:
                if live.read_bytes() != snapshot.read_bytes():
                    diverged.append(label)
            except OSError:
                pass
            ok += 1
            continue

        # VANISHED (absent from disk OR unknown to launchctl) → heal candidate
        if not _breaker_ok(led, label, now):
            breaker_tripped.append(label)
            continue
        success, detail = _heal(label, snapshot)
        if success:
            _record_heal(led, label, now)
            healed.append(label)
        else:
            healed.append(f"{label}:FAILED({detail})")

    _save_ledger(led)

    print(f"[matagaruda-plist-watchdog] snapshots={len(snapshots)} ok={ok} "
          f"healed={len(healed)} diverged={len(diverged)} breaker_tripped={len(breaker_tripped)}")
    for h in healed:
        print(f"  HEALED: {h}")
    for d in diverged:
        print(f"  DIVERGED (report-only, not touched): {d}")
    for b in breaker_tripped:
        print(f"  BREAKER-TRIPPED (>{MAX_HEALS_PER_WINDOW}/{WINDOW_SECONDS}s): {b}")

    status = "ok"
    if any("FAILED" in h for h in healed) or breaker_tripped:
        status = "degraded"
    _emit_heartbeat(status, {"healed": len([h for h in healed if "FAILED" not in h]),
                             "diverged": len(diverged),
                             "breaker_tripped": len(breaker_tripped)})
    return 0  # a watchdog never goes red on its own


if __name__ == "__main__":
    sys.exit(main())
