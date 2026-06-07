#!/usr/bin/env python3
"""Federation P6 — the "SHOULD we parallelize?" gate (conservative static estimator).

This module is the missing decision between CLASSIFY and DISPATCH in
``federation_orchestrator.py``. Before P6 the orchestrator ALWAYS fanned out
every matched specialist (``route_after_checkpoint`` was unconditional). P6 adds
a deterministic, **default-serial** hypothesis so the fan-out becomes the gated
exception it should be — never the rule.

Design contract (spec ``research/operations/specs/P6-parallelize-gate.md``):

* **The default is SERIAL.** ``parallelizable_hypothesis`` returns ``True`` only
  when the evidence positively supports it; ANY ambiguity, missing signal, or
  detected shared artifact yields ``False`` (serial / single-orchestrator).
* **It is a HYPOTHESIS, not a verdict** (spec §3.1). The estimate is static and
  coarse (keyword + role-diversity + file-overlap heuristics). It is allowed to
  be wrong; the cost of a wrong ``True`` is one fan-out that the runtime monitor
  then re-serializes (spec §3.2 — revocability).
* **The decision is REVOCABLE** (spec §3.2). This module only produces the
  *starting* hypothesis. The orchestrator/runtime is responsible for
  re-serializing branches when emergent dependencies appear (e.g. two branches
  request a lease on the same hot-zone via ``agent_lease.py``). See
  ``revoke_if_shared_artifact`` for the hook that expresses this.
* **No LLM call on the conservative path** (spec §3.1). Escalation-to-Claude for
  ambiguous/high-risk tasks is *optional and documented*, NOT implemented here —
  this module stays deterministic so the gate tests are falsifiable.
* **Coders on the same artifact are NEVER parallelized** (spec §4 cond. 2,
  Google arXiv 2512.08296 ``−70%`` on sequential coding). This is the one hard
  prohibition the estimator enforces structurally, not heuristically.

The four kinds of parallelism (spec §0):

================================  ==========  ===========================
kind                              degrades?   estimator verdict
================================  ==========  ===========================
breadth-of-research               no          may be True
specialist roles (disjoint)       no          may be True
structurally-independent pieces   no          may be True (if disjoint)
coders on the SAME artifact       yes (−70%)  ALWAYS False
================================  ==========  ===========================
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

# ─────────────────────────────────────────────────────────────────────────────
# Constants — the bayesian prior cap (spec §3.3) and merge-cost bands (§3.5).
# ─────────────────────────────────────────────────────────────────────────────

#: Initial coder-concurrency ceiling (Google arXiv 2512.08296 hard 3-4 ceiling).
#: Applies to CPU-bound concurrent *coders*, NOT to short I/O-bound infra agents
#: (search/explore). A bayesian *prior*, updatable with local feedback — never a
#: dogma (spec §3.3, §3.6). The gate enforces it as a ceiling, not a target.
DEFAULT_CODER_CAP: int = 4

#: Minimum number of distinct work-streams for parallelism to even be considered.
#: Below this there is nothing to parallelize → serial.
MIN_PARALLEL_STREAMS: int = 2


class MergeCost(str, Enum):
    """Coarse estimate of the cost to recompose parallel branches (spec §3.5).

    ``HIGH`` overlapping/uncontracted artifacts → parallelism is net-negative →
    the gate chooses serial even when the work *looks* independent.
    """

    LOW = "low"
    MED = "med"
    HIGH = "high"


# ─────────────────────────────────────────────────────────────────────────────
# Heuristic keyword banks (deterministic; coarse by design — spec §3.1).
# ─────────────────────────────────────────────────────────────────────────────

# Breadth-of-research / exploration: the +90.2% regime (spec §0 row 1).
_BREADTH_KEYWORDS: tuple[str, ...] = (
    "research",
    "investigate",
    "explore options",
    "survey",
    "compare approaches",
    "find sources",
    "gather",
    "review the landscape",
    "deep research",
    "multiple angles",
    "pros and cons",
    "trade-off",
    "trade-offs",
    "ricerca",
    "indaga",
    "esplora",
    "confronta",
)

# Phrases that betray a SINGLE linear artifact being edited → never parallel.
# These are the "coder on the same file" signatures (spec §4 cond. 2, G1/G3).
_SINGLE_ARTIFACT_KEYWORDS: tuple[str, ...] = (
    "this file",
    "this function",
    "this module",
    "this class",
    "this method",
    "one-line",
    "one line",
    "typo",
    "rename",
    "linear refactor",
    "refactor of 1 file",
    "refactor a single",
    "fix with known cause",
    "known cause",
    "single file",
    "the same file",
    "questo file",
    "questa funzione",
    "rinomina",
)


# ─────────────────────────────────────────────────────────────────────────────
# Result dataclass
# ─────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class ParallelizeDecision:
    """The starting hypothesis produced by the gate.

    ``hypothesis`` is the headline bool consumed by the dispatcher. Everything
    else is the audit trail: *why* the gate decided what it did, plus the
    inputs (``estimated_files_touched``, ``estimated_merge_cost``) the runtime
    monitor needs to police revocation.
    """

    hypothesis: bool
    reason: str
    estimated_files_touched: list[str] = field(default_factory=list)
    estimated_merge_cost: MergeCost = MergeCost.HIGH
    estimated_streams: int = 0
    coder_cap: int = DEFAULT_CODER_CAP
    revocable: bool = True  # always True — the dispatcher MUST honour §3.2.

    def as_classification_fields(self) -> dict:
        """Flatten into the keys merged onto the orchestrator ``classification``.

        Kept JSON-serialisable (enum → str) because ``classification`` is written
        to ``audit.jsonl`` and may cross the Telegram boundary.
        """
        return {
            "parallelizable_hypothesis": self.hypothesis,
            "parallelizable_reason": self.reason,
            "estimated_files_touched": list(self.estimated_files_touched),
            "estimated_merge_cost": self.estimated_merge_cost.value,
            "estimated_streams": self.estimated_streams,
            "coder_cap": self.coder_cap,
            "parallelizable_revocable": self.revocable,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Internal estimators (pure functions — easy to unit-test in isolation)
# ─────────────────────────────────────────────────────────────────────────────
def _count_infra_streams(classification: dict) -> int:
    """Count the disjoint *infrastructural* (role-diverse) specialist streams.

    These are short, I/O-bound, role-DISTINCT agents (search / explore / sandbox)
    — the regime where multi-agent fan-out does NOT degrade (spec §0 row 2,
    §3.3). They each read/produce their own artifact, so running them
    concurrently is the safe kind of parallelism.
    """
    streams = 0
    for flag in ("needs_search", "needs_explore", "needs_sandbox"):
        if classification.get(flag):
            streams += 1
    return streams


def _looks_breadth(task: str) -> bool:
    """True when the task text reads as breadth-first research/exploration."""
    t = task.lower()
    return any(kw in t for kw in _BREADTH_KEYWORDS)


def _looks_single_artifact(task: str) -> bool:
    """True when the task text betrays a single linear artifact being edited.

    This is the conservative guard for G1 (sequential→single) and the structural
    half of G3 (coder-same-artifact): if the work is described as touching one
    file/function/etc., it is NEVER a parallel candidate.
    """
    t = task.lower()
    return any(kw in t for kw in _SINGLE_ARTIFACT_KEYWORDS)


def _estimate_files_touched(classification: dict, task: str) -> list[str]:
    """Best-effort COARSE estimate of artifacts the work will touch.

    Pure heuristic over the domains the classifier already matched, plus any
    explicit file-ish tokens in the task. Returned as opaque labels — the only
    thing the gate does with them is measure *overlap* (the merge-cost / G4
    signal). Never authoritative; the runtime lease-registry is.
    """
    labels: list[str] = []
    for dom in classification.get("domains", []) or []:
        if dom and dom != "general":
            labels.append(f"domain:{dom}")
    # explicit path-ish tokens (e.g. foo/bar.py, scripts/x.py)
    for tok in re.findall(r"[\w./-]+\.\w{1,5}", task):
        if "/" in tok or tok.endswith((".py", ".ts", ".sql", ".yaml", ".yml", ".md")):
            labels.append(f"file:{tok}")
    # de-dup, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for lbl in labels:
        if lbl not in seen:
            seen.add(lbl)
            out.append(lbl)
    return out


def _estimate_merge_cost(
    files_touched: list[str], streams: int, has_explicit_contract: bool
) -> MergeCost:
    """Estimate recomposition cost (spec §3.5).

    * disjoint file labels + a formalised contract → ``LOW``
    * disjoint labels, no contract → ``MED``
    * any overlap, or nothing to disambiguate it → ``HIGH``
    """
    if streams < MIN_PARALLEL_STREAMS:
        return MergeCost.HIGH
    # overlap = fewer distinct labels than streams (two streams sharing a label)
    distinct = len(set(files_touched))
    if distinct and distinct < streams:
        return MergeCost.HIGH  # at least two streams collide on an artifact
    if has_explicit_contract and distinct >= streams:
        return MergeCost.LOW
    if distinct >= streams:
        return MergeCost.MED
    # no file signal at all → cannot prove disjointness → conservative HIGH
    return MergeCost.HIGH


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────
def parallelizable_hypothesis(
    classification: dict,
    task: str,
    *,
    has_explicit_contract: bool = False,
    coder_cap: int = DEFAULT_CODER_CAP,
) -> ParallelizeDecision:
    """Produce the conservative, default-serial parallelization hypothesis.

    Returns a :class:`ParallelizeDecision`. ``hypothesis is True`` ONLY when ALL
    of these hold (spec §4):

    1. the work is breadth-first research OR ≥2 role-distinct specialist streams
       (NOT coders on a shared artifact);
    2. it is not described as a single linear artifact edit (G1/G3 guard);
    3. there are at least :data:`MIN_PARALLEL_STREAMS` streams and no more than
       ``coder_cap`` (spec §3.3 ceiling, G5);
    4. estimated merge cost is not ``HIGH`` (net-positive, spec §3.5 / G4).

    ANY other situation — including "no signal at all" — returns
    ``hypothesis=False`` (serial / single-orchestrator). The estimate is static,
    deterministic, and LLM-free; it is explicitly a *revocable hypothesis*
    (``revocable=True``) that the runtime monitor may override (spec §3.2).

    Args:
        classification: the orchestrator ``classification`` dict (must carry the
            ``needs_*`` flags + ``domains`` already produced by ``classify_node``).
        task: the raw task text (used only for keyword/file heuristics).
        has_explicit_contract: set True when an a-priori contract (OpenAPI /
            AsyncAPI / signature — the P4 contracts) binds the parallel pieces
            (spec §3.4). Lowers merge cost. Defaults False (conservative).
        coder_cap: the (updatable) coder-concurrency ceiling (spec §3.3).

    Returns:
        ParallelizeDecision with a default-serial bias.
    """
    files_touched = _estimate_files_touched(classification, task)

    # ── Hard prohibition first: a single linear artifact edit is NEVER parallel.
    #    Covers G1 (sequential→single) and the structural half of G3.
    if _looks_single_artifact(task):
        return ParallelizeDecision(
            hypothesis=False,
            reason="single-artifact / linear edit detected → serial (G1/G3)",
            estimated_files_touched=files_touched,
            estimated_merge_cost=MergeCost.HIGH,
            estimated_streams=0,
            coder_cap=coder_cap,
        )

    breadth = _looks_breadth(task)
    infra_streams = _count_infra_streams(classification)

    # ── How many disjoint work-streams do we plausibly have?
    #    Breadth research counts as a multi-angle stream even with 0 infra flags;
    #    otherwise it is the count of role-distinct specialist agents.
    streams = infra_streams
    if breadth and streams < MIN_PARALLEL_STREAMS:
        # breadth fan-out of reads is itself the (safe) parallelism
        streams = max(streams, MIN_PARALLEL_STREAMS)

    # ── Nothing to parallelize → serial (covers the "no signal" default → False).
    if streams < MIN_PARALLEL_STREAMS:
        return ParallelizeDecision(
            hypothesis=False,
            reason="fewer than 2 disjoint streams → serial (default posture)",
            estimated_files_touched=files_touched,
            estimated_merge_cost=MergeCost.HIGH,
            estimated_streams=streams,
            coder_cap=coder_cap,
        )

    # ── Cap ceiling (G5): never exceed the coder-concurrency prior.
    if streams > coder_cap:
        return ParallelizeDecision(
            hypothesis=False,
            reason=f"streams {streams} exceed coder_cap {coder_cap} → serial (G5)",
            estimated_files_touched=files_touched,
            estimated_merge_cost=MergeCost.HIGH,
            estimated_streams=streams,
            coder_cap=coder_cap,
        )

    merge_cost = _estimate_merge_cost(files_touched, streams, has_explicit_contract)

    # ── Net-cost gate (G4): high merge cost → parallelism is net-negative → serial.
    if merge_cost == MergeCost.HIGH:
        return ParallelizeDecision(
            hypothesis=False,
            reason="estimated merge cost HIGH (artifact overlap / no contract) "
            "→ serial (G4)",
            estimated_files_touched=files_touched,
            estimated_merge_cost=merge_cost,
            estimated_streams=streams,
            coder_cap=coder_cap,
        )

    # ── All conditions met: a positive, but REVOCABLE, parallel hypothesis.
    kind = "breadth-first research" if breadth else "role-distinct specialists"
    return ParallelizeDecision(
        hypothesis=True,
        reason=f"{kind}; {streams} disjoint streams; merge_cost={merge_cost.value} "
        "→ parallel HYPOTHESIS (revocable at runtime per §3.2)",
        estimated_files_touched=files_touched,
        estimated_merge_cost=merge_cost,
        estimated_streams=streams,
        coder_cap=coder_cap,
    )


def revoke_if_shared_artifact(
    decision: ParallelizeDecision, contended_resources: list[str]
) -> ParallelizeDecision:
    """Re-serialize a parallel hypothesis when a shared artifact is observed.

    This is the *revocability* hook (spec §3.2, gate G2). The orchestrator/runtime
    calls it when the lease-registry (``agent_lease.py``) reports that two
    branches contend on the same hot-zone — a dependency the static estimator
    could not see. It downgrades a ``True`` hypothesis back to serial; it never
    upgrades a ``False`` one (revocation is one-directional toward safety).

    Args:
        decision: the prior hypothesis.
        contended_resources: hot-zone identifiers observed under contention by
            ≥2 branches (empty = no contention observed).

    Returns:
        The same decision if no contention, else a serial decision recording why.
    """
    if not decision.hypothesis or not contended_resources:
        return decision
    return ParallelizeDecision(
        hypothesis=False,
        reason="REVOKED: shared artifact(s) contended at runtime "
        f"({', '.join(sorted(set(contended_resources)))}) → re-serialized (G2)",
        estimated_files_touched=decision.estimated_files_touched,
        estimated_merge_cost=MergeCost.HIGH,
        estimated_streams=decision.estimated_streams,
        coder_cap=decision.coder_cap,
    )
