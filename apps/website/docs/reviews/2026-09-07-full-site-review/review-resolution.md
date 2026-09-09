# R19 review resolution

> Active-work update — the owner redirected this continuation to palette and typography before final closure. VR-1 has a CSS correction and passing focused proof. The independent follow-up was interrupted after the redirect: exit 143, status `no_final_result`, no verdict. The original FAIL and later correction remain distinct. A pre-design WIP checkpoint is now authorized at `output/checkpoints/2026-09-07-pre-design`; its owner will verify the archive and hashes, with final acceptance still pending. Journal local technical proof remains complete. No whole-site acceptance, completion handoff, or state acceptance update is recorded. The first-review record below remains historical evidence pending the next authorized review.

Date: 2026-09-07 (WITA). Status: **OPEN — first independent visual review FAIL.** This record does not approve a release or production transport arming.

## Independent review provenance

The actual first Claude review is retained in `claude-visual-review.md`, with `claude-review-receipt.json`, `claude-tool-trace.json`, and `claude-auth-route.json`. Initialized model: `claude-opus-5`; auxiliary model usage includes `claude-haiku-4-5-20251001`, not a claimed second independent review. Execution exited 0 without timeout/error; acceptance was FAIL.

The review used 39 Read invocations and 27 unique hash-stable inputs: 19 PNGs, two metrics files, six source files. It read all focused metrics; main metrics were only partially read (desktop through tax plus homepage tablet), with no tablet PNG. It performed no live browser/test execution and no production approval. The first verdict, screenshots, metrics, and receipts are preserved, with original source hashes pinned at review completion in `claude-review-artifact-verification.json`. The later corrected source and captures receive separate evidence and a follow-up verdict; source files are not falsely described as permanently immutable.

## Findings

| ID | Finding | Disposition | Required closure evidence |
| --- | --- | --- | --- |
| VR-1 | Homepage “Explore all services →” is occluded by lifted tool cards at desktop/tablet; `.tools` uses negative top margin and z-index | **BLOCKER OPEN** | Narrow layout correction, fresh affected build and 1440/768/390/360 observations, CTA visibility/clickability, independent follow-up |
| VR-2 | Portal disclaimer has no inset | Minor observation; no acceptance blocker assigned by reviewer | Record owner disposition; do not invent a fix |
| VR-3 | Ari project arrow wraps at 390px | Minor observation; no acceptance blocker assigned by reviewer | Record owner disposition; do not invent a fix |
| VR-4 | Tax card artwork sits lower when its heading wraps | Minor observation; no acceptance blocker assigned by reviewer | Record owner disposition; do not invent a fix |

VR-1 evidence includes `home-1440-viewport.png` and `home-tools-1440.png` under the final capture directory. The earlier automated no-overflow checks did not detect this visual overlap; their pass does not override the reviewer finding. The mobile homepage Journal element screenshot's sticky-header artifact is a separate capture limitation, not the cause or explanation for VR-1.

## Earlier findings already closed

| ID / area | Resolution | Evidence |
| --- | --- | --- |
| BR-1: GET body framing | Proof HTTP ingress and authority reject unexpected GET framing before bodyless Request construction | Independent boundary PASS; actual HTTP negative cases |
| BR-2: server-only misuse | Explicit marker plus installed Next client/server alias guard proof | Independent boundary PASS; no full negative Next build claim |
| Skip focus | Seven content routes focus MAIN and next Tab reaches anchor | Integrated tests and focused browser receipt |
| Missing-route recovery | Branded 404 with Home and Services recovery | Four desktop/mobile focused cases and tablet screenshots |
| Service navigation targets | Two measured header links 44px; contact action 48px | Focused measurements and coordinating reviewer |
| Service accessible names | Four distinct link names | Integrated tests and focused receipt |

## Persistent limitations

The local Magazine factories remain unwired from the production/preview loader; current preview stays synthetic fixture mode. Canonical access proof is a local metadata/not-found simulation, not production admission. No universal withdrawal recall, database/object-store atomicity, deployed D1 parity, full PNG decoder, cross-process nonce store, or full negative Client Component build is claimed. External destinations were checked for public reachability/identity, not authenticated outcomes or legal accuracy. Aborted request traces and the separate Journal screenshot artifact remain recorded.

Completion handoff, state acceptance update, final document hash verification, and checkpoint closure wait for the actual correction and independent follow-up result.
