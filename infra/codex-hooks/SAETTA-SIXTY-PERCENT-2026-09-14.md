# SAETTA Codex context boundary verification

Mandate: `SAETTA-FLEET-READY`. Read-only fleet checks on 2026-09-14 WITA.

The primary `.codex` seat on Pro, M5 and Mini already enforces the declared
60% threshold. No runtime reinstall or policy mutation was necessary.

| Host | Imperator | Builder | Dux | Enabled and trusted hook events |
| ---- | --------: | ------: | --: | ------------------------------: |
| Pro  |       0.6 |     0.6 | 0.6 |                           8 / 8 |
| M5   |       0.6 |     0.6 | 0.6 |                           8 / 8 |
| Mini |       0.6 |     0.6 | 0.6 |                           8 / 8 |

Evidence came from importing each host's installed `context_bridge.py`, reading
its local policy, calling `threshold(policy, role)`, and querying its real Codex
app-server `hooks/list`. All three responses contained no configuration errors.
The bridge selects the ChatGPT-bundled Codex binary on Pro and M5 and the
Codex-app binary on Mini. Credentials were neither read nor copied.

All three installed bridge files and the tested repository source share SHA-256:

`d489d68566ce819519a53d0ef068043796f9e3c846ca8d498622fc4001311334`

`test_sixty_percent_boundary.py` exercises `hook()` with isolated, synthetic
current-window token events at 500, 599, 600 and 601 tokens out of 1,000. Each
parent role continues below 600 and denies ordinary tools from 600 onward.
Native children use their own post-start token events, ignore inherited parent
history, and both mark return-required and deny ordinary tools at the same
boundary. The combined boundary and child-lifecycle suite passed 48 tests.

These boundary events are synthetic; this record does not claim a real model
session was deliberately filled to 60%. Installed code and hook activation were
checked live on all three hosts, and byte identity binds those copies to the
behavioral tests. Alternate account seats are outside this verification.

The conservative 40% fallback for an undeclared role remains intentional. It is
not used by imperator, builder, dux or native children on the verified seats.
Reinstallation preserves explicitly tuned thresholds; an ordinary reinstall
should not be used to overwrite an operator's policy.

Reproduce the focused behavioral checks from a repository worktree:

```sh
python -m pytest infra/codex-hooks/test_sixty_percent_boundary.py infra/codex-hooks/test_child_lifecycle.py -q
```

An initial inline Python probe was rejected by the arbitrary-exec guardrail.
No bypass was used. The boundary checks above are reviewable pytest cases using
the existing isolated test fixtures; installed state was not mutated.
