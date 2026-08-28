# `tailnet_acl/` — guilt fixtures

Each file reintroduces exactly ONE defect that `audit_policy()` in
`scripts/tests/test_tailnet_acl_deny_by_default.py` must catch. They are not valid policies and
must never be pasted into the Tailscale admin console. They exist so the guard is proven to go
red, not merely observed to be green — a guard with only innocence tests can report success and
never failure.
