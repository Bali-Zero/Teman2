# Conductor receipt authority boundary

## Routed child handshake

A routed receipt is not authority while it is `ISSUED`. The parent starts one
Python wrapper with `spawn_registered_child`, observes that direct child through
the OS, and records `LAUNCHING`. Only then does the parent release two inherited,
one-shot pipes:

- the receipt claim token;
- optional bounded, opaque launch context for transient provider spec/task data.

The wrapper calls `await_launch_registration()` and `read_launch_context()`, then
calls `ReceiptLedger.claim_routed_from_current_process()`. The ledger derives the
claimant identity locally from PID, process start, and executable observations; it
does not accept caller-supplied task or runtime labels. The task/session binding is
copied from the receipt.

The registered wrapper remains the supervisor while it starts and waits for the
provider CLI as a subprocess. It must not replace itself with `exec`, because an
executable change deliberately invalidates the authority binding. The same wrapper
completes with `complete_routed_from_current_process()`. A dead, replaced, or
PID-reused wrapper is terminally rejected before policy use.

The claim token and launch context are never placed in argv, environment values,
the receipt log, or the index. Descriptor numbers are environment metadata, not
authority. Provider bridges must not log or persist decoded launch context.

Caller-labelled `claim`, `validate_active`, `complete`, and their runtime CLI argv
builders are restricted to explicit `manual + legacy_non_launch` receipts. They
cannot authorize routed launches.

## Ledger integrity threat model

The JSONL log and JSON index are a matched pair. Any mismatch, chain gap, duplicate
or replay, reorder, truncation, invalid lifecycle transition, rollback visible
between the pair, or implausible future timestamp fails closed. Private modes,
no-follow opens, atomic replacement, locks, and hash chains improve corruption
detection.

They do **not** prevent a malicious process running as the same UID from rewriting
and re-hashing every local artifact. No local secret stored under that UID changes
this boundary. `ledger_integrity_report()` therefore declares:

```text
same_uid_tamper_resistant = false
shadow_eligible = true
enforcement_ready = false
```

`require_enforcement_ready()` blocks autonomous `ENFORCED` mode. `SHADOW` may run
with this limitation declared. Enforced authority requires a privileged or
separate-UID broker (and a migration of the ledger trust anchor); until then, this
storage must never be described as tamper-proof.
