# News Room publication repair

Mission `newsroom-section-boundaries`, BLUE, Gear 2. External builder; release requires the authorized Claude release owner.

The staging converter split an unlabelled Bali Zero Take at character offsets 200 and 400. The published property article consequently displayed `IDR 25` and `0 million` in different sections. The fallback TLDR also ended mid-sentence. The candidate preserves editorial sections and summarizes at sentence or word boundaries, avoiding a cutoff inside currency/number/scale phrases. It repairs the existing MDX body while preserving every frontmatter value and the existing URL.

The public verifier had a separate false negative: Next.js renders the approved cover through `/_next/image?url=...`, while the verifier compared the wrapper path with the original cover path. The candidate unwraps only a Bali Zero optimizer URL with exactly one source, then verifies the original public cover path and exact alt text. Wrong images, wrong alt text, external hosts, missing source parameters, and duplicate source parameters fail.

## Validation and review

- Backend regression suite: 75 tests passed after the parser corrections. The initial converter failed the new boundary cases. The review follow-up reproduced four additional failures (currency scale, heading variants, styled labels) before correction.
- Bridge suite: 76 tests passed after the optimizer correction. Before correction, the real-shaped optimizer case and the external-image rejection test failed.
- Ruff and `git diff --check` passed on the candidate. Existing formatting outside changed definitions is preserved.
- Existing MDX compiled successfully; frontmatter equality against HEAD and the rejoined amount were checked. Final receipts and empirical gate remain required after the candidate is frozen.
- Independent Opus 5 xhigh quality review returned PASS with findings. Currency-scale and heading-format findings were reproduced and fixed; the all-empty take now has a composer roundtrip assertion. Existing `Any` import is present and exercised by the tests. The first-paragraph summary policy remains intentional; all facts and analysis remain in the body. Frontmatter contains complete sentences, with no fragments from the body corruption.

## Editorial state recovered from canonical Pro records

| Item ID                         | Fact / independent gate                         | Action                                                                                                                                      |
| ------------------------------- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `news_20260911_180456_7b5f0603` | PASS / PASS                                     | Recheck current fingerprint and cover eligibility after the parser is deployed; then canonical publish with an idempotent key and `latest`. |
| `news_20260911_180626_9099f9c9` | BLOCK / BLOCK                                   | Hold: campaign source is unverified and the evidence contains contradictions.                                                               |
| `news_20260912_183911_659b3e85` | BLOCK / BLOCK                                   | Hold: case-specific source support is missing and practical guidance was flagged for revision.                                              |
| `news_20260911_180503_803cd994` | BLOCK / BLOCK                                   | Hold: the defining regulatory claims and implementation date lack verified primary support.                                                 |
| `news_20260912_183731_10fc51d7` | Existing article; body repair in this candidate | Keep URL/canonical unchanged; verify the deployed repair before confirming live.                                                            |

Gate findings are reviewer results, not independently established legal facts. No new articles were submitted or published by this continuation. The villa gate record changed during recovery; therefore a release owner must bind the latest passing result to the current content fingerprint before submission.

At 07:21 UTC the already-live property page returned HTTP 200 on desktop and mobile, with matching title, canonical, SEO title, OG image and `datePublished=2026-09-14T00:00:00.000Z`. The candidate cover checker passed against both real HTML responses. Both responses still contained the split body text: the repaired body is not yet deployed. The old canonical verifier previously reported Latest success; a direct call to the homepage-slot helper is not a Latest check, so final Latest proof must use the canonical branch for Latest.

## Sibling checks

Checked 2026-09-14 around 07:13–07:16 UTC: no open PR overlapped the five changed paths; the native agent tree contained only this root. Mini worktree leases and Mini/Pro fleet session lists showed unrelated work. Pro was reachable, at `4829401880`, ahead of this branch's base `6eb13d09a8`; fetching Pro and checking the five paths showed no intervening changes. The unrelated dirty `.secrets.baseline` remains excluded. Repeat the four sibling probes before push.

## Release handoff

1. Independently verify the frozen candidate and normal PR checks; merge/deploy through the authorized release seat only.
2. Install the Bridge verifier change through its existing runtime workflow; preserve its configured identity and write-arming state.
3. Verify the property URL/title/canonical/datePublished/OG/Latest and that `IDR 250 million` and `alternative rates` are contiguous in the body.
4. Re-read the villa article, fingerprint-bound gate and ready cover; submit only if all mandatory gates pass, using the canonical publisher, an idempotent request key, and `position=latest`.
5. Keep Nakula, Tax Court and SPP-TDLN unpublished until their substantive evidence failures are corrected and new canonical gates pass. Never override a red result.

Bites: the converter-to-EnrichedArticle-to-MDX regression exercises the public article consumer; the Bridge publication test verifies that only the approved optimized cover can enable live confirmation. The deployed property page and the villa publication remain release-owner observations, not claims of this candidate. Sibling evidence is recorded above.
