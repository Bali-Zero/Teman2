## Station 6 — doctrine archaeology

Five files describe how this fleet is allowed to route work: `AGENTS.md` (§17 in
particular), `MODEL_ROSTER.md`, `FLEET_TOPOLOGY.json`, `MODEL_TOPOLOGY.json`, and
`.claude/skills/modus/SKILL.md` (§THE ARSENAL). They were written by many hands over three
months and they drift. Machines read some of them (`scripts/evidence_pack_lint.py` and
`scripts/tests/test_lint_roster_dispatch.py` enforce parts of the roster). People read the
rest.

Find every place where two of these sources state incompatible facts about the same thing.
For each contradiction, in `REPORT.md` under CLAIM, one entry:

```
- <topic> — <file A>:<line> says X · <file B>:<line> says Y · which one the code enforces (if
  any): <script:line or "none"> · which one is right, and why.
```

Rules and scoring notes:

- A contradiction is two sources asserting incompatible facts, not one source being
  incomplete or stale in wording. "Anthropic ×4" next to a six-account roster is a
  contradiction; a typo is not.
- Prefer contradictions that a machine enforces on one side — those are the ones that
  turn a doc into a lie the day the gate goes hard.
- Order by blast radius: what breaks first if the wrong one is believed.
- You are not asked to fix anything. If a fix is one line and obviously right, you may
  state it, but leave the files untouched.
- Some contradictions were planted for this exam. Some are real. You are not told which.
  Finding a real one we did not plant scores above finding a planted one.
