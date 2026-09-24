# Sol council review

Seat: codex-gpt-5.6-sol, xhigh. Native independent read-only session portal_reply_council_sol.
Candidate: 082696bdb629a6023788b8a4f3edd21ec9323d8d.
Verdict: PASS-WITH-CONDITIONS. No P0/P1 findings.

- P2: old automatic-notice writers can still default source=FALSE during rolling replacement. The historical-source limitation includes this narrow window; wait for all producers to replace before claiming the new behavior.
- P2: never-attempted outbox rows are not age-bounded; inspect pending age on activation after an outage.
- P2: an earlier uncertain provider attempt followed by explicit rejection can end failed. Already tracked by issue #7304.

Atomic persistence, lease fencing, three-attempt limit, keyed Brevo-only delivery, assignment/auth, kill switch and cached-error UI were found coherent. The reviewer inspected the diff, source, spec, pack and prior gate and ran git diff --check. No tests rerun; no edits, sends, production rows or release actions.
