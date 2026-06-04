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

# NotebookLM grounding — NB-AGENTS (agent-craft ground-truth) lives on the
# antonellosiano@ account, reachable via the `default` nlm CLI profile.
_NB_AGENTS_ID = "6d449787-04e3-430e-acbe-d6fc38d379a9"
_NB_AGENTS_PROFILE = "default"
_NLM_BIN = os.environ.get("NLM_BIN", "nlm")


def ground_via_nlm(
    family: str,
    incident_summary: str,
    notebook_id: str = _NB_AGENTS_ID,
    profile: str = _NB_AGENTS_PROFILE,
    timeout: int = 90,
) -> Optional[str]:
    """Consult NB-AGENTS for the known pattern of this failure class.

    Returns a short ground-truth string to inject into the PROPOSE prompt, or
    None on ANY failure (Law 4: ungrounded propose is still valid, never block).
    The query carries only the abstract failure class + incident summary —
    engineering know-how, not client PII (boundary rectified 2026-06-04).
    """
    question = (
        "An autonomous agent must write a defensive guard/antibody for this "
        f"recurring production failure class ('{family}'). Incident: "
        f"{incident_summary[:600]} "
        "In 4-6 sentences, cite the KNOWN best-practice pattern (locking, "
        "isolation, idempotency, preflight, rollback) that prevents this class, "
        "and the specific pitfall to avoid. Be concrete and executable-minded."
    )
    try:
        proc = subprocess.run(
            [_NLM_BIN, "notebook", "query", "--profile", profile, notebook_id, question],
            capture_output=True, text=True, timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("grounding: nlm query failed (%s) — proceeding ungrounded", exc)
        return None
    if proc.returncode != 0:
        logger.warning("grounding: nlm rc=%s — proceeding ungrounded: %s",
                       proc.returncode, (proc.stderr or "")[:160])
        return None
    out = (proc.stdout or "").strip()
    # nlm may return JSON ({"value":{"answer":...}}) or plain text depending on flags.
    if out.startswith("{"):
        try:
            data = json.loads(out)
            out = (data.get("value", {}) or {}).get("answer", "") or str(data)
        except json.JSONDecodeError:
            pass
    out = out.strip()
    if not out:
        return None
    return out[:1500]  # cap injected context


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
    grounding: Optional[str] = None,
    feedback: Optional[str] = None,
    prev_antibody: Optional[str] = None,
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
    ground_block = ""
    if grounding:
        ground_block = (
            "KNOWN GROUND-TRUTH PATTERN (from the agent-craft knowledge base — "
            "use it to inform your antibody, but the antibody must still satisfy "
            f"the contract precisely):\n{grounding}\n\n"
        )
    retry_block = ""
    if feedback:
        retry_block = (
            "YOUR PREVIOUS ATTEMPT FAILED a replay. Here is the antibody you "
            f"produced:\n{(prev_antibody or '')[:1200]}\n\n"
            f"It FAILED this way:\n{feedback}\n\n"
            "Fix the specific failure above while still satisfying the contract. "
            "Do not regress the cases that already passed.\n\n"
        )
    user = (
        f"INCIDENT SUMMARY (what went wrong, no fix shown):\n{incident_summary}\n\n"
        f"{ground_block}"
        f"{retry_block}"
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
    attempts_used: int = 0                 # PROPOSE calls spent (retry-with-feedback)
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


def _score_antibody(probe: Probe, antibody_text: str, rep: "ProbeReport",
                    attempt: int = 1) -> list[str]:
    """Run the executable gate (original + variants) for one antibody.

    Mutates rep.original_passed / rep.variants_passed and appends notes.
    Returns the list of concrete failure strings (for retry feedback). The
    failures name the variant and the observed drift — that is the trace-based
    credit signal fed back to PROPOSE.
    """
    failures: list[str] = []
    ab_dir = Path(tempfile.mkdtemp(prefix="scar-antibody-"))
    ab_path = ab_dir / "antibody.sh"
    try:
        ab_path.write_text(antibody_text or "", encoding="utf-8")

        # Gate 2 — original replay
        orig = _run_in_sandbox(probe, antibody_path=ab_path)
        rep.original_passed = orig.passed
        if not orig.passed:
            msg = f"original replay FAILED: {orig.detail}"
            rep.notes.append(f"attempt {attempt}: antibody {msg}")
            failures.append(msg)

        # Gate 3 — hidden variants (generalization)
        for name, vbuild in probe.variants:
            out = _run_in_sandbox(probe, antibody_path=ab_path, variant_builder=vbuild)
            if out.passed:
                rep.variants_passed += 1
            else:
                msg = f"variant '{name}' FAILED: {out.detail}"
                rep.notes.append(f"attempt {attempt}: {msg}")
                failures.append(msg)
    finally:
        shutil.rmtree(ab_dir, ignore_errors=True)
    return failures


def run_probe(
    probe: Probe,
    key: Optional[str],
    offline: bool = False,
    prior_antibody: Optional[str] = None,
    ground: bool = False,
    max_attempts: int = 1,
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

    # --- OFFLINE / replay-only path (no PROPOSE) ----------------------------
    if offline or not key:
        if not prior_antibody:
            rep.notes.append("offline mode + no prior antibody: cannot evolve, replay-only no-op")
            return rep
        rep.notes.append("offline mode: replaying prior antibody (no proposal)")
        _score_antibody(probe, prior_antibody, rep)
        rep.antibody = prior_antibody
        rep.promoted = rep.baseline_failed and rep.original_passed and rep.all_variants_passed
        return rep

    # --- ONLINE path: generate -> verify -> repair (retry with feedback) ----
    grounding = None
    if ground:
        grounding = ground_via_nlm(probe.family, probe.incident_summary)
        if grounding:
            rep.notes.append("grounded via NB-AGENTS")

    feedback = None
    prev_antibody = None
    attempts = max(1, max_attempts)
    for attempt in range(1, attempts + 1):
        prop = propose_antibody(
            key, probe.incident_summary, probe.contract,
            grounding=grounding, feedback=feedback, prev_antibody=prev_antibody,
        )
        rep.attempts_used = attempt
        rep.proposal_ok = prop.ok
        rep.cost_usd += prop.cost_usd
        if not prop.ok:
            rep.proposal_error = prop.error
            rep.notes.append(f"attempt {attempt}: proposal failed: {prop.error}")
            if prior_antibody:
                rep.notes.append("degraded: replaying prior antibody after proposal failure")
                _score_antibody(probe, prior_antibody, rep)
                rep.antibody = prior_antibody
                rep.promoted = rep.baseline_failed and rep.original_passed and rep.all_variants_passed
            return rep

        rep.antibody = prop.antibody
        # reset per-attempt gate counters
        rep.original_passed = False
        rep.variants_passed = 0
        failures = _score_antibody(probe, prop.antibody, rep, attempt=attempt)

        if rep.original_passed and rep.all_variants_passed:
            rep.promoted = rep.baseline_failed
            if attempt > 1:
                rep.notes.append(f"repaired on attempt {attempt}")
            return rep

        # not all gates passed → build feedback for the next attempt
        if attempt < attempts and failures:
            feedback = "; ".join(failures)
            prev_antibody = prop.antibody
            rep.notes.append(f"attempt {attempt}: {len(failures)} gate failure(s) → retrying")
        else:
            # out of attempts (or original-replay failure with no variant info)
            break

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
# Antibody store — persist promoted antibodies so daily runs can replay them    #
# (vigilance) for free and only call the LLM for new/regressed probes.          #
# --------------------------------------------------------------------------- #

_DEFAULT_STORE = Path.home() / ".agent" / "decisions" / "agent-library-evolver" / "antibodies"


def _store_path(store_dir: Path, family: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", family)
    return store_dir / f"{safe}.sh"


def load_stored_antibody(store_dir: Path, family: str) -> Optional[str]:
    """Return the last promoted antibody for a family, or None if never promoted."""
    p = _store_path(store_dir, family)
    if p.is_file():
        try:
            return p.read_text(encoding="utf-8")
        except OSError:
            return None
    return None


def save_antibody(store_dir: Path, family: str, antibody: str) -> None:
    """Persist a promoted antibody (atomically). evolver-owned scope for cleanup."""
    store_dir.mkdir(parents=True, exist_ok=True)
    p = _store_path(store_dir, family)
    tmp = p.with_suffix(".sh.tmp")
    tmp.write_text(antibody, encoding="utf-8")
    tmp.replace(p)


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
    ap.add_argument("--ground", action="store_true",
                    help="consult NB-AGENTS for the known pattern before proposing (richer antibody)")
    ap.add_argument("--max-attempts", type=int, default=3,
                    help="retry-with-feedback: re-propose up to N times, feeding back the failed variant")
    ap.add_argument("--budget-usd", type=float, default=0.50, help="soft cost ceiling")
    ap.add_argument("--repo-root", default=str(Path.home() / "Desktop" / "nuzantara-deploy"))
    ap.add_argument("--telemetry-dir",
                    default=str(Path.home() / ".agent" / "decisions"
                               / "agent-library-evolver" / "telemetry"))
    ap.add_argument("--cleanup", action="store_true", help="reap evolver-owned scories")
    ap.add_argument("--apply-cleanup", action="store_true", help="actually delete scories")
    ap.add_argument("--daily", action="store_true",
                    help="vigilance mode: replay stored antibodies free; LLM only for new/stale probes")
    ap.add_argument("--store-dir", default=str(_DEFAULT_STORE),
                    help="where promoted antibodies are persisted")
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

    store_dir = Path(args.store_dir)
    results = []
    spent = 0.0
    promoted = 0
    new_or_stale = 0
    vigilance_ok = 0
    for probe in probes:
        stored = load_stored_antibody(store_dir, probe.family)

        if args.daily:
            # Vigilance: first, replay the stored antibody for FREE (offline).
            if stored is not None:
                watch = run_probe(probe, key=None, offline=True, prior_antibody=stored)
                if watch.promoted:
                    # Stored antibody still holds. Done — no LLM spend.
                    vigilance_ok += 1
                    results.append({**asdict(watch), "daily_state": "vigilance_pass"})
                    continue
                # Stored antibody no longer passes => STALE/regressed. Re-evolve.
                results_note = "stale_reevolve"
            else:
                results_note = "new_evolve"
            new_or_stale += 1
            if offline:
                # Can't evolve offline; flag for human (a new/regressed probe with no LLM).
                results.append({"family": probe.family, "daily_state": results_note,
                                "note": "offline: cannot evolve new/stale probe"})
                continue
            if spent >= args.budget_usd:
                results.append({"family": probe.family, "daily_state": results_note,
                                "skipped": "budget exhausted"})
                continue
            rep = run_probe(probe, key, offline=False, prior_antibody=stored, ground=args.ground, max_attempts=args.max_attempts)
            rep_d = {**asdict(rep), "daily_state": results_note}
        else:
            # Full run (every probe hits the LLM unless offline).
            if spent >= args.budget_usd and not offline:
                results.append({"family": probe.family, "skipped": "budget exhausted"})
                continue
            rep = run_probe(probe, key, offline=offline, prior_antibody=stored, ground=args.ground, max_attempts=args.max_attempts)
            rep_d = asdict(rep)

        spent += rep.cost_usd
        if rep.promoted:
            promoted += 1
            save_antibody(store_dir, probe.family, rep.antibody)  # persist the win
        results.append(rep_d)

    # Law 7 — numbers first. effective_antibodies is the real metric.
    summary = {
        "mode": ("daily" if args.daily else "full") + ("/offline" if offline else "/online"),
        "probes_run": len(results),
        "effective_antibodies": promoted,   # NEW antibodies promoted this run
        "vigilance_pass": vigilance_ok,     # stored antibodies that still hold (free)
        "evolved_new_or_stale": new_or_stale,
        "attempts_used": sum(r.get("attempts_used", 0) for r in results if isinstance(r, dict)),
        "cost_usd": round(spent, 4),
        "results": results,
    }
    _emit(summary)
    # exit 0 always on a clean run; promotion count is in the payload (no vanity exit).
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
