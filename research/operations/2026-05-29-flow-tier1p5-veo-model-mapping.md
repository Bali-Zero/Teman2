---
date: 2026-05-29
domain: operations
client_case: flowkit-wr3-render
sources:
  - local: /Users/nuzantara/flowkit/agent/models.json
  - local: /Users/nuzantara/flowkit/agent/services/flow_client.py
  - local: /Users/nuzantara/flowkit/agent/models/enums.py
  - local: /Users/nuzantara/flowkit/extension/background.js
  - local: /Users/nuzantara/flowkit/extension/injected.js
  - local: /Users/nuzantara/flowkit/flow_agent.db (project + request tables)
  - local: /Users/nuzantara/logs/flowkit.err.log
  - upstream: https://github.com/crisng95/flowkit (origin/main, v1.1.0, pushed 2026-05-09)
  - web: https://www.digitalapplied.com/blog/google-ai-plans-free-plus-pro-ultra-2026
  - web: https://www.mindstudio.ai/blog/google-flow-pricing-credits-tiers-explained
  - web: https://blog.google/products-and-platforms/products/google-one/google-ai-subscriptions/
  - web: https://blog.google/innovation-and-ai/technology/ai/veo-3-1-ingredients-to-video/
  - web: https://www.keysight.com/blogs/en/tech/nwvs/2025/08/04/google-flow-ai-har-analysis
---

# FlowKit TIER1P5 Veo model mapping — research capture

**Research only. No code changes, no video-gen calls were made.** Read-only DB
inspection + upstream repo search + web search.

## TL;DR

- `PAYGATE_TIER_TIER1P5` is **almost certainly the backend paygate string for the
  new "Google AI Plus" consumer tier** ($7.99/mo, launched Google I/O 2026 — sits
  between Free and AI Pro; "1.5" = a half-step tier below TIER_ONE=Pro). *(inferred,
  not directly confirmed by any Google doc that names the string.)*
- The "ULTRA" badge in the Flow UI **contradicts** an AI-Plus reading and is the one
  fact that doesn't fit cleanly — see Q1. Treat the consumer-plan mapping as
  **inferred / stale-risk** until the live `/v1/credits` body is captured in full.
- **The exact internal Veo model-id string for TIER1P5 portrait i2v is NOT publicly
  discoverable.** Upstream FlowKit has never heard of TIER1P5; no GitHub repo,
  issue, PR, or web source contains `PAYGATE_TIER_TIER1P5` or a TIER1P5 model map.
  **It must be sniffed from the live outgoing request.** (unknown → must sniff)
- **Upstream repo: https://github.com/crisng95/flowkit** (428 stars, default branch
  `main`, last push 2026-05-09, latest tag v1.1.0).

---

## Q1 — What is PAYGATE_TIER_TIER1P5? How does it relate to the ULTRA badge?

**verified (local):** The live account is on this tier. `flow_agent.db` `project`
table shows every active project carries `user_paygate_tier = 'PAYGATE_TIER_TIER1P5'`,
and `~/logs/flowkit.err.log` logs `Syncing tier: PAYGATE_TIER_TIER1P5` repeatedly
through 2026-05-29 06:27. The string comes straight from `/v1/credits`
`userPaygateTier` (flow_client.py:117).

**inferred:** Google's 2026 consumer ladder (Google I/O 2026 + Google One AI Plans):

| Plan | Price | Flow credits/mo | Veo capability | Likely paygate string |
|---|---|---|---|---|
| Free | $0 | limited | Veo 2 / lite | (none / free) |
| **AI Plus** | **$7.99** | **200** | **Veo 3.1 Fast video, 128K ctx** | **→ PAYGATE_TIER_TIER1P5** (inferred) |
| AI Pro | $19.99 | 1,000 | Veo 3.1, native audio | → PAYGATE_TIER_ONE (inferred) |
| AI Ultra 5× | $100 | 12,500 | Veo 3.1, priority | → PAYGATE_TIER_TWO (inferred) |
| AI Ultra 20× | $249.99 | 12,500 | Veo 3.1, priority | → PAYGATE_TIER_TWO (inferred) |

"1P5" reads naturally as **tier 1.5** — a tier inserted *below* the old TIER_ONE
without renumbering the existing enum. The $7.99 AI Plus tier is the only new tier
Google added in 2026 that fits an off-by-half-step name. Note: digitalapplied says
AI Plus gets **Veo 3.1 Fast** specifically (not the Ultra-quality path) — consistent
with TIER1P5 having access to the `_fast` / non-`_ultra` Veo family.

**stale-risk / contradiction — the ULTRA badge:** A UI "ULTRA" badge on an account
the API reports as TIER1P5 is inconsistent with the AI-Plus reading. Possible
explanations (none verified): (a) a promotional/trial ULTRA badge decoupled from the
paygate tier; (b) the badge reflects the *model quality available* rather than the
billing tier; (c) the account is on a different/grandfathered plan and TIER1P5 is a
Google-side A/B or migration bucket. **Do not assume AI Plus is correct for billing
decisions without confirming against the full `/v1/credits` payload** (it carries
more than just `userPaygateTier` — credit balance, serviceTier, entitlements).

## Q2 — Does TIER1P5 include Veo 3.1 image-to-video (frame_2_video) for PORTRAIT 9:16?

**unknown — NOT empirically proven for TIER1P5.** Important nuance found in the DB:

- `request` table: 29 HORIZONTAL video requests COMPLETED, **1 VERTICAL (portrait)
  COMPLETED**, 4 HORIZONTAL FAILED. This initially looks like proof portrait works.
- **But every one of those rows is dated 2026-05-12** (`created_at`/`updated_at`
  2026-05-12T19:32–23:42Z). The account did **not** flip to TIER1P5 until later —
  the TIER1P5 tier-sync log lines and the 502/403 failures are all *recent*
  (2026-05-29). So those successes were generated while the account was still
  TIER_TWO/TIER_ONE, using the old `_ultra` / `_fast` model strings. **There is zero
  record of a successful video — landscape OR portrait — on TIER1P5.**
- The 2026-05-12 FAILED rows even include `PUBLIC_ERROR_MODEL_ACCESS_DENIED`, i.e.
  tier-mismatch denials predate the current problem.

**inferred (capability, not entitlement):** Veo 3.1 *as a model* fully supports
native vertical/portrait i2v (Google, Jan 2026 "Ingredients to Video" + native
vertical output). So the *capability* exists. Whether the **TIER1P5 paygate grants
the account a portrait i2v model id** is the open question. The only TIER1P5 evidence
we have is the failure:
`502 "No model for tier=PAYGATE_TIER_TIER1P5 type=frame_2_video ratio=PORTRAIT"` —
and that 502 is FlowKit's **own** error (flow_client.py:386), raised because
`models.json` has no TIER1P5 key. It is **not** Google saying "no portrait model for
your tier." So we genuinely cannot tell from current data whether the fix is a
code-mapping addition or an account upgrade. **The sniff (Q4) resolves this:** if a
manual portrait generate in the Flow UI succeeds on this account, portrait i2v IS
entitled and we only need the model string; if the UI itself refuses portrait,
it's an entitlement/upgrade problem.

## Q3 — Exact internal Veo model-id string for TIER1P5 portrait i2v

**unknown, must sniff live request.** Do NOT guess. Findings:

- **Upstream FlowKit has no TIER1P5.** `git fetch` + `git show origin/main:agent/models.json`:
  upstream only defines `PAYGATE_TIER_ONE` and `PAYGATE_TIER_TWO`. The enum
  (`agent/models/enums.py:21`) is hard-typed `Literal["PAYGATE_TIER_ONE",
  "PAYGATE_TIER_TWO"]` — a third tier is unmodeled both in data and in the type.
- Upstream actually moved TIER_TWO `frame_2_video` to `veo_3_1_i2v_lite_low_priority`
  (commit 961ed67, 2026-05-09) for SERVICE_TIER_ADVANCED accounts. **Our local copy
  is stale/diverged** — it still has the older `_ultra` strings (local has 1
  uncommitted models.json change ahead of origin). Neither version mentions TIER1P5.
- `gh api search/code q='PAYGATE_TIER_TIER1P5'` → **0 results across all of GitHub.**
  Same repo: `TIER1P5` → 0; sibling repo `crisng95/flowboard` → 0.
- Upstream issues/PRs/branches: no TIER1P5 work. (Closest issue #20 "Add Veo 3.1 Lite
  model support" — unrelated to tiers.)
- Web reverse-engineering (Keysight HAR analysis, MindStudio, AISandbox notes):
  confirm the backend is `aisandbox-pa.googleapis.com` and uses `userPaygateTier` /
  `videoModelKey`, but **none publish a TIER1P5 → model map or any 2026 model-id list.**

**Candidate strings (analogy only — NONE sourced, do not ship):**
`veo_3_1_i2v_s_fast_portrait` (the TIER_ONE portrait string — most plausible since
AI Plus likely gets the Fast, non-Ultra family) / `veo_3_1_i2v_lite_low_priority`
(upstream's universal 0-credit fallback that "works on every tier") / a new
TIER1P5-specific suffix. **Each is a guess. The accepted string must come from the
wire.**

## Q4 — Empirical capture (the authoritative path)

**Because the TIER1P5 model string is NOT publicly discoverable, the correct action
is to sniff the real outgoing request body when a video is generated manually in the
Flow UI on this account.** The accepted body carries the exact `videoModelKey` Google
accepts for TIER1P5.

How FlowKit sends video (flow_client.py:392): the body is
`{"requests":[{"aspectRatio": ..., "videoModelKey": <model_key>, "startImage": ...}],
"clientContext": {... "userPaygateTier": ...}, "useV2ModelConfig": true}`, POSTed by
the extension to `https://aisandbox-pa.googleapis.com/...`. The `videoModelKey` is
resolved *only* from `models.json` — that's the single thing to fill in for TIER1P5.

**Recommended sniff procedure (operator action, not code change):**
1. Open `labs.google/fx/tools/flow` in the FlowKit Chrome profile, on this account.
2. Open DevTools → Network, filter `aisandbox-pa.googleapis.com`.
3. Manually create a **portrait 9:16 image-to-video** clip in the Flow UI.
4. If the UI **succeeds** → inspect the outgoing request payload → copy the exact
   `videoModelKey` string (and note `aspectRatio` + any `serviceTier`). That string
   is the verified TIER1P5 portrait i2v key to add to `models.json` under a new
   `"PAYGATE_TIER_TIER1P5"` block. Repeat for LANDSCAPE and for start_end / r2v.
   → confirms Q2 = portrait IS entitled; fix is pure code-mapping.
5. If the UI **refuses/greys out portrait** → TIER1P5 does not entitle portrait i2v;
   fix is an **account upgrade** (AI Pro/Ultra), not a code change.

**Cheaper capture option (no manual click needed):** the extension already
monkey-patches `window.fetch` in `extension/injected.js` (currently only to read TRPC
media-URL *responses*). A one-line read-only console log of the *request* body for
`aisandbox-pa.googleapis.com` POSTs would capture the exact key the next time *any*
generate happens. (Noted as an option — implementing it is a code change, out of
scope for this research task.)

---

## Code-fix shape (for later — NOT applied here)

When the sniffed strings are known, the change is mechanical:
1. `agent/models.json` → add a `"PAYGATE_TIER_TIER1P5"` block under `video_models`
   with the sniffed `frame_2_video` / `start_end_frame_2_video` /
   `reference_frame_2_video` keys for LANDSCAPE + PORTRAIT.
2. `agent/models/enums.py:21` → extend the `PaygateTier` Literal to include
   `"PAYGATE_TIER_TIER1P5"` (otherwise pydantic validation may reject it).
3. Verify no other hard-coded 2-tier assumptions (the many `... or "PAYGATE_TIER_ONE"`
   defaults in `operations.py` are fine — they're fallbacks, not allowlists).

Until the strings are sniffed: **do not invent the model id.**
