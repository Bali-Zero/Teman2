---
date: 2026-05-29
domain: operations
client_case: none
sources:
  - "3-LLM panel 2026-05-29"
  - "agent_lease.py"
  - "cicatrix W-series"
---

# P1 Escalation — Redis lease registry fail-open vs fail-closed on hot-zone WRITE

> **Symbiosis Law 5 escalation.** Changing fail-open → fail-closed contradicts an
> explicit documented HARD constraint in `scripts/agent_lease.py`. That is a
> structural decision → must go through the operator. This doc is that escalation.
> **No code was changed.** `agent_lease.py` was read-only here.

## 1. Decision required

Should hot-zone **WRITE-lock** checks fail **CLOSED** (block the commit) when Redis
is down, overriding the current documented fail-open HARD constraint?

## 2. Current behavior

`scripts/agent_lease.py::_cmd_check` (lines 468-509) is the pre-commit hook entry
point. It has a **single lock type** (no read/write distinction) and **three
exit-0 escape hatches** before it can ever block:

1. `AGENT_LEASE_ENFORCEMENT in (false/0/no/off/disabled)` → exit 0 (kill switch)
2. `AgentLease()` raises `RedisUnavailable` → exit 0 (fail-open)
3. `lease.check_path(...)` raises any `Exception` → exit 0 (fail-open)

Verbatim (`agent_lease.py:468-509`):

```python
def _cmd_check(args) -> int:
    """check is the hot-path called from the pre-commit hook.

    Graceful degradation: Redis down → exit 0 + WARN log. Otherwise the
    pre-commit hook would become a hard dependency on Redis availability,
    which violates the brief's HARD constraint.

    Kill switch: AGENT_LEASE_ENFORCEMENT=false → exit 0 always.
    """
    enforcement = os.environ.get("AGENT_LEASE_ENFORCEMENT", "true").strip().lower()
    if enforcement in ("false", "0", "no", "off", "disabled"):
        # Kill switch active — never block
        return 0

    our_task_id = os.environ.get("TASK_ID") or os.environ.get("AGENT_TASK_ID")

    try:
        lease = AgentLease()
    except RedisUnavailable as e:
        LOG.warning("Redis unavailable — passing through (no enforcement): %s", e)
        return 0
    try:
        blocking, holder = lease.check_path(args.path, our_task_id=our_task_id)
    except Exception as e:
        LOG.warning("lease check error — passing through: %s", e)
        return 0
    if not blocking:
        return 0
    assert holder is not None
    print(
        f"BLOCKED: path '{args.path}' is leased by another task",
        file=sys.stderr,
    )
    _print_holder(holder, prefix="  holder: ")
    if our_task_id:
        print(f"  our task_id: {our_task_id}", file=sys.stderr)
    else:
        print(
            "  (no TASK_ID env set — pass TASK_ID=<id> if this is your own lease)",
            file=sys.stderr,
        )
    return 1
```

The only path that returns `1` (block) is: Redis up **AND** `AgentLease()`
constructs **AND** `check_path` reports a blocking holder. Every failure mode is
permissive.

## 3. The risk (panel verdict)

**All 3 LLMs (Gemini + Codex + DeepSeek) converged** on a "split-brain
catastrophic" verdict: because the only coordination point (Redis) is also the
single thing whose outage disables coordination, a Redis failure means **all ~160
cron jobs + every parallel session simultaneously gain hot-zone write access at
exactly the moment coordination is most needed** — the inversion is precisely
backwards from what a lock is for.

Blast surface during the open window: LaunchAgent wrappers, `migrations_v2/*.sql`,
auth/billing/pricing, `.github/workflows/`, sentinel/dlq scripts. This is the same
deploy-path-desync / sibling-race family that produced cicatrix W50/W51/W59/W62
(silent drift + concurrent writers on shared trees).

## 4. The tension

Fail-closed contradicts the explicitly documented HARD constraint.

Verbatim (`agent_lease.py:471-473`, docstring of `_cmd_check`):

```python
    Graceful degradation: Redis down → exit 0 + WARN log. Otherwise the
    pre-commit hook would become a hard dependency on Redis availability,
    which violates the brief's HARD constraint.
```

The original rationale: the pre-commit hook must NOT become a hard dependency on
Redis availability — a dev/agent on a healthy machine should never be unable to
commit just because a Redis box is down. The brief encoded this as non-negotiable.

Resolving the tension means one of:

- **(a)** override the HARD constraint for the WRITE path only (commits to
  hot-zone blocked until Redis returns OR explicit override);
- **(b)** keep fail-open but add a file-based fallback lock (`flock`) so there is
  SOME coordination when Redis is down, without hard-blocking;
- **(c)** accept the risk and add a Redis-health alert so the operator knows when
  the uncoordinated window is open.

## 5. Three options with tradeoffs

| Option | What changes | Pro | Con | Blast-radius |
|---|---|---|---|---|
| **A. Fail-CLOSED on hot-zone WRITE when Redis down** | Add read/write lock distinction; WRITE-lock check returns exit 1 on Redis outage unless `AGENT_LEASE_ENFORCEMENT=false`. Reads still fail-open. | Closes the split-brain hole exactly where it matters (writes). No silent simultaneous write access. | Directly overrides the documented HARD constraint. Redis outage now blocks ALL hot-zone commits → if Redis flaps, dev/agents are stuck until override or recovery. Needs read/write semantics that don't exist today. | High — every hot-zone committer (160 cron + sessions) blocked during any Redis outage; escape hatch is the env override. |
| **B. Keep fail-open + add `flock` file-based fallback** | On Redis-unavailable, acquire a local `flock` on a sentinel file per resource instead of returning exit 0 blindly. Best-effort same-host coordination; never hard-blocks. | Survives Redis outage with SOME coordination. Honors the HARD constraint (no Redis hard-dependency). Lowest friction; no behavior change for the happy path. | Only coordinates writers on the SAME host (flock is local) — cross-machine (Pro+Mini) still uncoordinated during outage. Adds a new lock surface + cleanup edge cases (stale flock). | Medium — single-host races closed; cross-host residual risk remains, but far smaller than status quo. |
| **C. Keep fail-open + Redis-down Telegram alert** | No logic change to the gate. Emit an operator alert whenever `_cmd_check` hits the Redis-unavailable / GET-failed path. | Zero behavior change; honors HARD constraint fully; cheapest to ship; operator-aware. | Does NOT close the hole — it just makes the open window visible. Relies on human reaction time during the exact window when many writers are active. | Unchanged from today — purely observability; the split-brain remains possible. |

## 6. Recommendation

The panel leaned **fail-closed for WRITE specifically (Option A)** because that is
the only choice that actually closes the split-brain on the write path. If
minimizing friction and respecting the HARD constraint is the priority, **Option B
is the lowest-friction middle path** — it adds real (same-host) coordination on
Redis outage without making Redis a hard dependency. I'd pick **B as the immediate
ship** (it's reversible, non-blocking, and buys most of the safety) and treat **A**
as the follow-up if cross-machine races are observed empirically.

## 7. What's needed from operator

A single choice:

- **A / B / C** — which option to implement.
- **Override the documented HARD constraint?** — yes/no (only A requires it; B and
  C preserve it).

Until a choice is made, the current fail-open behavior stays in place unchanged.
