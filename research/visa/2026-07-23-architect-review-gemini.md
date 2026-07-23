## SEAT VERDICT
FIX-FIRST

## CLAIM-BY-CLAIM
- **Regulatory Anchors (Lane Mandate)**: CONFIRMED. 
  - *Evidence (Web Search)*: Kepmen M.IP-08/2025 indeed reduced indexes to 110 effective June 2, 2025. Permen Imipas 10/2026 was signed July 7, 2026, revoking 10/2025 and adding 6 countries to the BVK list. Permen Imipas 5/2025 (effective March 7, 2025) officially revoked the Permenkumham 36/2021 guarantor rules. Golden Visa stats match exactly: 1,274 permits yielding Rp 52.1T as of May 18, 2026.
- **M1 (Broken feed)**: CONFIRMED.
  - *Evidence (Analysis)*: 0 rows in `visa_checks` since April, `401` on both frontend and backend endpoints, and swallowed exceptions in the Next.js frontend prove the v1 pipe is dead.
- **M2 (No RulePack)**: CONFIRMED.
  - *Evidence (Analysis)*: DB queries show 0 rows in `visa_rule_packs` and `visa_ruleset_activations`.
- **M3 (Runtime dark)**: CONFIRMED.
  - *Evidence (Analysis)*: Fly secrets `VISA_ENGINE_MATCH_MODE` and `VISA_ENGINE_FACTS_FINGERPRINT_KEYS_JSON` are absent.
- **M4 (Gate status)**: CONFIRMED. 
  - *Evidence (Analysis)*: G-a and G-c are blocked by M1. G-b lacks the independent artifact.
- **M5 (Traffic-vs-G-a)**: CONFIRMED. 
  - *Evidence (Math)*: At 7 requests/day, hitting 1,000 distinct requests requires 142 days, not 7. The G-a design is mathematically incompatible with current organic traffic.
- **Proposed 6-step critical path**: PARTIAL. 
  - *Evidence*: Step 0 is the correct immediate action, but Steps 1 and 3 rely on a flawed assumption that organic traffic will naturally hit 30 distinct codes across 7 categories in a short window.

## MISSED
- **P0 (Gate Design / Traffic Distribution Fallacy)**: The analysis misses that organic traffic follows a power law. 1,000 organic requests will heavily skew towards B1 (Tourism) and E33 (Digital Nomad). You will *never* organically hit 30 distinct codes (especially Bridging or niche Golden Visa codes) in a 7-day window without synthetic injection.
- **P1 (Launch Completeness Hazard)**: The plan treats the 30-code slice as the finish line for the RulePack. 30 codes may satisfy the G-a *gate* for volume, but ENFORCE (final flip) requires the full 110 bonified codes from M.IP-08/2025. Launching a "zero wrong answers" flagship with 72% of the catalog missing is a critical product risk.
- **P1 (Negative Constraints in G-c)**: The G-c (Grounding) gate design does not measure revocation evasion. A SHADOW verdict might recommend a dead B211A code or mandate revoked guarantor rules (Permenkumham 36/2021), and the engine might pass if the citations superficially match. The evaluator must explicitly scan for forbidden/obsolete regulatory references.
- **P2 (Regulatory Decay)**: The analysis treats the regulations as static post-launch. With a 3-4 month regulatory cadence, a green gate today decays rapidly. Watch items that will invalidate the gate post-flip include: additions/removals to the BVK list (Permen Imipas 10/2026 amendments), changes to Golden Visa thresholds (E28), and integration rules for new IT systems affecting Bridging Visas.

## CORRECTIONS
1. **Fix v1 feed immediately (Step 0)**: Do not repoint SHADOW to v2. V2 cannot launch until gates pass, creating a deadlock. Repair v1 using the proposed Next.js BFF route (`/api/visa/match`) that injects a backend service token. This satisfies Law 2 constraints by keeping the JWT off the frontend.
2. **Mandate High-Risk Codes in the 30-Code Slice (Step 1)**: The initial 30 codes authored MUST explicitly include the highest legal-risk branches: E28 family (Golden Visa - Rp52.1T at stake), E33 family (Remote Work - high volume/scrutiny), BVK (Permen Imipas 10/2026 nationality edges), and Bridging (overstay exact-date math).
3. **Renegotiate G-a Threshold (Step 3)**: Drop the 1,000/7d organic requirement. Replace it with a 14-day organic collection window **supplemented by targeted synthetic traffic** to guarantee all 7 categories and the 30 priority codes are exercised by the engine.
4. **Require 110 Codes for ENFORCE (Step 4/5)**: While G-a collects data on the 30-code slice, author the remaining 80 codes in parallel. The G-d drill and final ENFORCE flip must be strictly gated on the full 110-code RulePack being signed and active.
5. **Strengthen Evaluator (Step 4)**: Update the G-b/G-c cross-family grader to explicitly penalize outputs containing dead codes (B211*) or revoked laws (Permenkumham 36/2021).

## SEQUENCING VERDICT
The critical path order is fundamentally sound but requires the following deltas to be viable:
- **Step 0**: Keep as-is. Fixing the v1 feed is the absolute P0.
- **Step 1**: Keep as-is, but strictly enforce the inclusion of E28, E33, BVK, and Bridging in the first 30 codes.
- **Step 2**: Keep as-is.
- **Step 3**: *DELTA* — Modify the collection window criteria to rely on a mix of organic + synthetic traffic to force breadth across the 30 codes.
- **Step 4**: *DELTA* — Add "Author remaining 80 codes for full M.IP-08/2025 compliance" to the parallel workstream. Add "Strengthen Evaluator for negative constraints."
- **Step 5**: *DELTA* — Block the ENFORCE flip until Track B FASE 2 is complete (110 codes live).
agy exit=0
