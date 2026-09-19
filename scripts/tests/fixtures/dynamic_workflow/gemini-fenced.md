```markdown
---
seat: gemini-3.1-pro-high
objective_sha256: 325ad09ef4863087b0f9b7be5428c91cf54ee0b9c0924f5e68361429909766e6
facts_cited: [F8, F11, F12, F14, C1, C3, C5, C6, C7]
assumptions: 2
---
ASSUMPTION 1: `kimi` and `tp1-*` models are live as stated in the brief text, taking precedence over the squad table which lists them as QUOTA_DEAD/TIMEOUT.
ASSUMPTION 2: The human owner will act as the final Gatekeeper or wait until 09:00 for the Claude quota reset, as C5 requires a fresh Opus 5 session outside the chain.

## Formation
| role | seat | why (F ref) | substitute if dead (F8) |
|---|---|---|---|
| Designer & Mapper (G1, G3) | tp1-qwen3.8-max | Strategy voice, instruction following, design (F12) | kimi |
| Verifier & Refuter | tp1-deepseek-v4-pro | Hard logic, counter-analysis, grader from different family (F12, C6) | tp1-glm-5.2 |
| Architect & Auditor | kimi | Long-context audit, evidence-pack verifier, design (F12) | jules |
| Gatekeeper | Human / Opus 5 (BLUE) | Final on-disk gate must be Opus 5 outside chain (C5) | Human owner |

## Tactics
| stage | seat(s) | in-script or window | parallel/serial | round cap | exit command | hands to next stage |
|---|---|---|---|---|---|---|
| 1. Engine Maps (G1) | tp1-qwen3.8-max, tp1-deepseek-v4-pro | window | serial | 2 | `git push && gh pr create` | PR with flag rewrites + copy |
| 2. Pack Signing | Owner | window | serial | 1 | `activate_pack` | Signed seq-23 pack on disk |
| 3. Tree UI (G3) | tp1-qwen3.8-max, kimi | window | serial | 2 | `vercel promote` | Promoted mouth UI |
| 4. Enum Bound | tp1-deepseek-v4-pro | in-script | serial | 1 | `pytest` | exact walk count from AST |
| 5. Replay & Fix (G2)| tp1-qwen3.8-max, tp1-glm-5.2 | in-script | parallel | 1 per red | `gh pr merge --auto` | Bounded walk report (0 reds) |

## Termination
The `fix-of-a-fix stops at depth 1` and `three reds for same cause` counters (C7) live inside the dynamic `Workflow` script's state dictionary. The script reads these counters before dispatching a fix task; if depth > 1 or cause count = 3, it aborts the loop and outputs `exit 1` for the owner to read and intervene.

## Evidence between stages
- **Stage 1 → 2**: A read-only diff proving `test_every_disclosure_flag_reports_the_walks_it_rewrites` prints 0 for the 11 non-criminal flags. (Avoids self-reported journals: F11).
- **Stage 2 → 3**: The exact sequence number (seq-23) of the newly activated pack on disk.
- **Stage 3 → 4**: The Vercel deployment URL and the green e2e test suite (`visa-oracle-v2.spec.ts`).
- **Stage 4 → 5**: The AST-derived exact product space bound (an array of valid paths), handed via file rather than channel (F14).

## Never
- Never keep a human review hold for the 11 non-criminal flags or `MINOR_GUARDIAN_PRIVACY_REVIEW` silently without an explicit owner decision.
- Never use a Claude model through a paid API; wait for 09:00 Makassar or use Owner session (C1).
- Never show the builder's claim to the grader first (C6).

## First move
Extract the AST of the rulepack to statically list the exact domains of the 11 non-criminal `DisclosedReviewFlag` members, mapping each to a deterministic named product or a dead end in `apps/backend-rag/backend/services/visa_engine/`.
· Bites: `engine-adapter.test.ts` · `test_every_disclosure_flag_reports_the_walks_it_rewrites` prints zero for non-criminal holds.

## Cost
- tp1-qwen3.8-max: ~15 calls
- tp1-deepseek-v4-pro: ~5 calls
- kimi: ~3 calls
- tp1-glm-5.2: ~10 calls (1 per red fix verification)
- Anthropic windows: 1 (Owner Opus 5 for final gate, when quota resets)
- Expected wall-clock: 3 hours

## Owner Decisions
1. Q1: Red vs copper accent for the Oracle UI? (Default: Copper)
2. Q2: Can any of the 11 non-criminal disclosures NOT be deterministic and MUST retain a human review hold? (Default: All 11 become deterministic dead-ends or distinct products)
3. Q3: Will you execute the signing and activation of the seq-23 pack once G1 is merged? (Default: Yes)
```
