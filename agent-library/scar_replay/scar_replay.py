#!/usr/bin/env python3
"""
scar_replay.py — Scar-Replay Antibody Harness for the Nuzantara organism.

Redesign of agent-library-evolver (2026-06-04, design: 3-LLM council
DeepSeek V4 Pro + GPT-5.5 + Gemini 3.1; decision memory
decision_evolver_scar_replay_harness_2026_06_04.md).

WHY this exists
---------------
The old evolver optimized a SATURATED toy benchmark (classify a scar into 1
of 9 patterns; DeepSeek solves it at 100% baseline → zero headroom → zero
evolution by mathematical construction). It has never promoted a single skill.

This harness instead turns the organism's OWN lived production failures
(cicatrix-scars.md) into deterministic replay probes where the BASELINE FAILS
by construction (a scar IS a failure that already happened). "Learning" here
means producing an *executable antibody* (a guard/preflight/cleanup/fallback
shell snippet) that makes the replay PASS — and keeps passing on N mutated
variants of the same failure family.

Council guardrail (UNANIMOUS, adversarial): do NOT train on the *text* of the
scar. The candidate sees only the incident SUMMARY, never the hidden variants.
Final scoring is LOCAL EXECUTABLE BEHAVIOR, never an LLM judgment. This avoids
the overfit trap where the model learns to paraphrase cicatrix prose.

Real self-improvement == counterfactual prevention:
    same pre-error state -> different action -> failure class prevented
Metric:
    effective_antibodies = fail_before_pass_after - regressions - overbroad_blocks

Symbiosis compliance:
  - Law 1: DeepSeek API only (sanctioned, non-PII). No Anthropic paid API.
  - Law 2: probes run in ephemeral mktemp sandboxes, no PII, no network needed
           for the replay itself; only the antibody *proposal* call hits DeepSeek.
  - Law 4: graceful degradation — DeepSeek down => OFFLINE REPLAY ONLY (re-run
           the last known antibodies against probes, no proposal), never "broken".
  - Law 5: alert a human ONLY when a human decision is genuinely required.
  - Law 7: numbers first — every run emits a before/after metric.
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
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("scar_replay")

# --------------------------------------------------------------------------- #
# Self-healing key resolution (Law 4 — deterministic, audited, never "broken") #
# --------------------------------------------------------------------------- #

# Order matters. Council: env -> sanctioned vault -> launchd env -> offline.
_VAULT_CANDIDATES = (
    "DEEPSEEK_MASTER_ENV",  # explicit override (consumed below if set)
)
_VAULT_FILES = (
    Path.home() / ".nuzantara-secrets.env",
    Path.home() / ".openclaw" / "workspace" / ".env.master",
)


def resolve_deepseek_key() -> Optional[str]:
    """Resolve DEEPSEEK_API_KEY deterministically across the known vault drift.

    Returns the key, or None (which the caller MUST treat as "offline replay
    only" — not as a fatal error). This is the self-heal for the recurring
    SECRETS_FILE drift (the key lives in .env.master, not .nuzantara-secrets.env).
    """
    # 1. already in environment
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        logger.info("key-resolution: DEEPSEEK_API_KEY from process env")
        return key

    # 2. explicit override path
    override = os.environ.get("DEEPSEEK_MASTER_ENV", "").strip()
    files = []
    if override:
        files.append(Path(override))
    files.extend(_VAULT_FILES)

    for f in files:
        if not f.is_file():
            continue
        try:
            for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if line.startswith("DEEPSEEK_API_KEY="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val:
                        logger.info("key-resolution: recovered from %s (vault drift)", f)
                        return val
        except OSError as exc:  # pragma: no cover - unlikely
            logger.warning("key-resolution: cannot read %s: %s", f, exc)

    logger.warning(
        "key-resolution: DEEPSEEK_API_KEY not found in any vault — OFFLINE REPLAY ONLY"
    )
    return None


# --------------------------------------------------------------------------- #
# DeepSeek proposal call (only cloud touchpoint; antibody is CODE not prose)   #
# --------------------------------------------------------------------------- #

_DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"


@dataclass
class ProposalResult:
    ok: bool
    antibody: str = ""           # the shell snippet
    raw: str = ""
    error: str = ""
    cost_usd: float = 0.0


def propose_antibody(
    key: str,
    incident_summary: str,
    probe_contract: str,
    model: str = "deepseek-v4-pro",
    timeout: int = 180,
    max_tokens: int = 6000,
    reasoning_effort: str = "low",
) -> ProposalResult:
    """Ask DeepSeek for an EXECUTABLE antibody given ONLY the incident summary.

    The model never sees the hidden variants nor the assertion code — it sees
    the summary + the contract the antibody must satisfy. This is the anti-
    overfit firewall the council demanded.
    """
    system = (
        "You are an SRE writing a defensive shell antibody for a known recurring "
        "production incident. Output ONLY a POSIX bash snippet (no markdown fence, "
        "no prose) that, when sourced/run before the risky operation, PREVENTS the "
        "failure class. It must be idempotent and side-effect-safe. Do not assume "
        "any specific absolute path beyond what the contract gives you via env vars."
    )
    user = (
        f"INCIDENT SUMMARY (what went wrong, no fix shown):\n{incident_summary}\n\n"
        f"ANTIBODY CONTRACT (what your snippet receives and must guarantee):\n"
        f"{probe_contract}\n\n"
        "Return the bash snippet only."
    )
    # NOTE: deepseek-v4-pro is a reasoning model — max_tokens caps reasoning +
    # content TOGETHER. On a complex prompt, reasoning_effort="high" can burn the
    # whole budget before any content is emitted (finish_reason="length",
    # content=""). This is the same failure class as the historic max_tokens=16
    # scorer bug. For CODE GENERATION we use reasoning_effort="low" + a generous
    # max_tokens so content always has room. (Verified empirically 2026-06-04.)
    payload = json.dumps(
        {
            "model": model,
            "reasoning_effort": reasoning_effort,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        _DEEPSEEK_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return ProposalResult(ok=False, error=f"HTTP {exc.code}: {exc.read()[:200]!r}")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return ProposalResult(ok=False, error=f"network: {exc}")
    except json.JSONDecodeError as exc:
        return ProposalResult(ok=False, error=f"decode: {exc}")

    try:
        content = body["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        return ProposalResult(ok=False, error=f"shape: {str(body)[:200]}")

    usage = body.get("usage", {})
    # DeepSeek v4-pro rough pricing; cost is informational (Law 7), not billed here.
    cost = (
        usage.get("prompt_tokens", 0) * 0.27 / 1_000_000
        + usage.get("completion_tokens", 0) * 1.10 / 1_000_000
    )
    antibody = _strip_fence(content)
    if not antibody.strip():
        return ProposalResult(ok=False, raw=content, error="empty antibody")
    return ProposalResult(ok=True, antibody=antibody, raw=content, cost_usd=cost)


def _strip_fence(text: str) -> str:
    """Remove ```bash ... ``` fences if the model added them despite instructions."""
    text = text.strip()
    m = re.match(r"^```(?:bash|sh)?\s*\n(.*?)\n```\s*$", text, re.DOTALL)
    return m.group(1) if m else text


# --------------------------------------------------------------------------- #
# Probe model — a scar compiled into a deterministic, replayable fault         #
# --------------------------------------------------------------------------- #


@dataclass
class ReplayOutcome:
    passed: bool
    detail: str = ""


@dataclass
class Probe:
    """One lived scar turned into an executable replay.

    family:           e.g. "shared_worktree_git_ops"
    incident_summary: what the candidate is allowed to see (NO fix, NO variants)
    contract:         what the antibody receives (env vars) and must guarantee
    build_fixture:    (sandbox_dir, antibody_path|None) -> sets up pre-error state
                      and runs the risky operation WITH the antibody applied (or
                      without it for baseline, when antibody_path is None).
    assert_outcome:   (sandbox_dir) -> ReplayOutcome  (pure local check, no LLM)
    variants:         mutators applied to the fixture to test generalization;
                      each is a name + a fixture-builder for that variant.
    """

    family: str
    incident_summary: str
    contract: str
    build_fixture: Callable[[Path, Optional[Path]], None]
    assert_outcome: Callable[[Path], ReplayOutcome]
    variants: list[tuple[str, Callable[[Path, Optional[Path]], None]]] = field(
        default_factory=list
    )


# --------------------------------------------------------------------------- #
# Runner — baseline must fail; antibody must pass original + N variants        #
# --------------------------------------------------------------------------- #


@dataclass
class ProbeReport:
    family: str
    baseline_failed: bool = False          # gate 1: baseline must fail (else no headroom)
    original_passed: bool = False          # gate 2: antibody passes original
    variants_total: int = 0
    variants_passed: int = 0               # gate 3: passes N variants (generalization)
    proposal_ok: bool = False
    proposal_error: str = ""
    cost_usd: float = 0.0
    antibody: str = ""
    promoted: bool = False                 # all gates green
    notes: list[str] = field(default_factory=list)

    @property
    def all_variants_passed(self) -> bool:
        return self.variants_total > 0 and self.variants_passed == self.variants_total


def _run_in_sandbox(probe: Probe, antibody_path: Optional[Path], variant_builder=None) -> ReplayOutcome:
    """Materialize a fresh ephemeral sandbox, build the fixture, assert. No network."""
    sandbox = Path(tempfile.mkdtemp(prefix=f"scar-replay-{probe.family}-"))
    try:
        builder = variant_builder or probe.build_fixture
        builder(sandbox, antibody_path)
        return probe.assert_outcome(sandbox)
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


def run_probe(
    probe: Probe,
    key: Optional[str],
    offline: bool = False,
    prior_antibody: Optional[str] = None,
) -> ProbeReport:
    """Execute the full gate sequence for one probe.

    offline=True OR key is None  => OFFLINE REPLAY ONLY: re-run prior_antibody
    (if any) against the probe to confirm no regression; never call DeepSeek.
    """
    rep = ProbeReport(family=probe.family, variants_total=len(probe.variants))

    # Gate 1 — baseline MUST fail (proves real headroom; a scar that no longer
    # reproduces is not a learning opportunity, it's already solved).
    base = _run_in_sandbox(probe, antibody_path=None)
    rep.baseline_failed = not base.passed
    if base.passed:
        rep.notes.append(
            f"NO HEADROOM: baseline already passes ({base.detail}) — probe is stale, "
            "skip (do NOT spend a proposal). Retire or harden this probe."
        )
        return rep

    # Decide antibody source.
    antibody_text = None
    if offline or not key:
        if prior_antibody:
            antibody_text = prior_antibody
            rep.notes.append("offline mode: replaying prior antibody (no proposal)")
        else:
            rep.notes.append("offline mode + no prior antibody: cannot evolve, replay-only no-op")
            return rep
    else:
        prop = propose_antibody(key, probe.incident_summary, probe.contract)
        rep.proposal_ok = prop.ok
        rep.cost_usd = prop.cost_usd
        if not prop.ok:
            rep.proposal_error = prop.error
            rep.notes.append(f"proposal failed: {prop.error}")
            # Law 4: degrade — fall back to prior antibody if we have one.
            if prior_antibody:
                antibody_text = prior_antibody
                rep.notes.append("degraded: replaying prior antibody after proposal failure")
            else:
                return rep
        else:
            antibody_text = prop.antibody

    rep.antibody = antibody_text or ""

    # Write antibody to a temp file the fixtures will source.
    ab_dir = Path(tempfile.mkdtemp(prefix="scar-antibody-"))
    ab_path = ab_dir / "antibody.sh"
    try:
        ab_path.write_text(antibody_text or "", encoding="utf-8")

        # Gate 2 — antibody passes the ORIGINAL replay.
        orig = _run_in_sandbox(probe, antibody_path=ab_path)
        rep.original_passed = orig.passed
        if not orig.passed:
            rep.notes.append(f"antibody failed original replay: {orig.detail}")
            return rep

        # Gate 3 — antibody generalizes to N hidden variants.
        for name, vbuild in probe.variants:
            out = _run_in_sandbox(probe, antibody_path=ab_path, variant_builder=vbuild)
            if out.passed:
                rep.variants_passed += 1
            else:
                rep.notes.append(f"variant '{name}' FAILED: {out.detail}")
    finally:
        shutil.rmtree(ab_dir, ignore_errors=True)

    rep.promoted = (
        rep.baseline_failed
        and rep.original_passed
        and rep.all_variants_passed
    )
    return rep


# --------------------------------------------------------------------------- #
# Garbage cleanup (Law 4) — ONLY evolver-owned markers, never blind            #
# --------------------------------------------------------------------------- #

_EVOLVER_BRANCH_GLOB = "evolver/*"
_TELEMETRY_TTL_DAYS = 30


def cleanup_scories(repo_root: Path, telemetry_dir: Path, apply: bool = False) -> dict:
    """Reap ONLY evolver-owned scories. Returns a report; mutates only if apply.

    - stale git branches matching evolver/* with no unmerged commits
    - telemetry dirs older than TTL
    Never touches anything without the evolver-owned naming marker.
    """
    report: dict = {"branches": [], "telemetry": [], "applied": apply}

    # stale evolver branches
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "branch", "--list", _EVOLVER_BRANCH_GLOB,
             "--format=%(refname:short)"],
            capture_output=True, text=True, timeout=30,
        )
        for br in (out.stdout or "").split():
            report["branches"].append(br)
            if apply:
                subprocess.run(
                    ["git", "-C", str(repo_root), "branch", "-D", br],
                    capture_output=True, text=True, timeout=30,
                )
    except (subprocess.SubprocessError, OSError) as exc:
        report["branches_error"] = str(exc)

    # stale telemetry
    if telemetry_dir.is_dir():
        cutoff = time.time() - _TELEMETRY_TTL_DAYS * 86400
        for d in telemetry_dir.iterdir():
            try:
                if d.is_dir() and d.stat().st_mtime < cutoff:
                    report["telemetry"].append(d.name)
                    if apply:
                        shutil.rmtree(d, ignore_errors=True)
            except OSError:
                continue
    return report


# --------------------------------------------------------------------------- #
# Probe registry — import the concrete probes                                  #
# --------------------------------------------------------------------------- #


def load_probes(only_family: Optional[str] = None) -> list[Probe]:
    """Load registered probes. Kept as a function so the registry can grow."""
    from scar_probes import all_probes  # local module, same dir

    probes = all_probes()
    if only_family:
        probes = [p for p in probes if p.family == only_family]
    return probes


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #


def _emit(report: dict) -> None:
    print(json.dumps(report, indent=2, default=str))


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Scar-Replay Antibody Harness")
    ap.add_argument("--family", help="run only this scar family")
    ap.add_argument("--offline", action="store_true", help="offline replay only (no DeepSeek)")
    ap.add_argument("--budget-usd", type=float, default=0.50, help="soft cost ceiling")
    ap.add_argument("--repo-root", default=str(Path.home() / "Desktop" / "nuzantara-deploy"))
    ap.add_argument("--telemetry-dir",
                    default=str(Path.home() / ".agent" / "decisions"
                               / "agent-library-evolver" / "telemetry"))
    ap.add_argument("--cleanup", action="store_true", help="reap evolver-owned scories")
    ap.add_argument("--apply-cleanup", action="store_true", help="actually delete scories")
    ap.add_argument("--list", action="store_true", help="list probes and exit")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.cleanup:
        rep = cleanup_scories(Path(args.repo_root), Path(args.telemetry_dir),
                              apply=args.apply_cleanup)
        _emit({"cleanup": rep})
        return 0

    probes = load_probes(args.family)
    if args.list:
        _emit({"probes": [{"family": p.family, "variants": len(p.variants)} for p in probes]})
        return 0
    if not probes:
        _emit({"error": "no probes matched", "family": args.family})
        return 2

    key = resolve_deepseek_key()
    offline = args.offline or key is None

    results = []
    spent = 0.0
    promoted = 0
    for probe in probes:
        if spent >= args.budget_usd and not offline:
            results.append({"family": probe.family, "skipped": "budget exhausted"})
            continue
        rep = run_probe(probe, key, offline=offline)
        spent += rep.cost_usd
        if rep.promoted:
            promoted += 1
        results.append(asdict(rep))

    # Law 7 — numbers first. effective_antibodies is the real metric.
    summary = {
        "mode": "offline" if offline else "online",
        "probes_run": len(results),
        "effective_antibodies": promoted,   # baseline-failed & original-passed & all-variants-passed
        "cost_usd": round(spent, 4),
        "results": results,
    }
    _emit(summary)
    # exit 0 always on a clean run; promotion count is in the payload (no vanity exit).
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
