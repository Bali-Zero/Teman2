---
adversarial_review: codex
review_disposition: COORDINATOR_SCOPE_SPEC_PENDING_INDEPENDENT_FINAL_GATE
---

# B06 declared-source context contract

The operation artifact declares source revision8061c88e; the public inventory declares5f2e0ad9. These historical identities must not be replaced with current-main hashes while retaining the historical revision label.

The 21 operation records consume their exact hash-pinned source-identity projection. The test input root materializes actual source bytes for that declared revision: matching working-tree bytes are accepted; otherwise only local Git objects for the exact commit are allowed. Each object must match its recorded SHA256 before writing an owned temporary test snapshot. Missing or wrong context fails; there is no skip or network fetch.

All eighteen original testcase function bodies and assertions remain unchanged. Their shared input fixture now explicitly selects the source context declared by their records. No fixture is silently replaced, no current-source hash is treated as a historical hash, and no observed failure becomes PASS without checking actual bytes.

Inventory integrity separately checks all6029 identities and4231 public source paths against the inventory's own declared revision, retaining source hashes and every line-range assertion. Its original compressed projection,21 legacy records,1566 traced rows,4463 untraced rows and21001 syntax signals remain historical facts.

Acceptance requires the full38-test suite on current main, unchanged original eighteen testcase ASTs, unchanged operation/inventory artifact bytes, no new lint findings, an exact final source review, and the original block_closed:false posture. Current runtime semantics and business membership remain unproved.

## Adversarial review

The first main integration exposed mutable working-tree hashes. The second exposed that two legacy testcase checks also require physical source bytes. Therefore a digest-only fixture cannot replace those checks: the revised test root supplies and hashes actual bytes at the declared revision. The next current-main integration is the bounded acceptance attempt; any further failure stops this correction for a new specification rather than weakening a check.

Native queries, production repair, credential changes and repeated restore/Redis exercises are outside this contract.
