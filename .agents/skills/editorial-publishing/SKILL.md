---
name: editorial-publishing
description: Publish or verify Bali Zero News Room articles and WR2 Instagram carousels for Zero or Damar. Load when asked to list editorial items, publish News Room content, choose homepage placement, publish a carousel, verify live URLs, or register an already-published Instagram post.
---

# Editorial Publishing

Apply this protocol only to explicit requests received through an authenticated session from
Zero or Damar. It covers News Room articles and WR2 Instagram carousels. It does not authorize
client messages, email, WhatsApp, other social channels, manual merges, deploys, destructive
operations, or bypassing an artefact gate.

## Shared rules

- Treat an explicit publish order as the human act allowed by Legge 5; never initiate it.
- Read current state from the canonical service. Never edit staging or WR2 queue JSON directly.
- Never infer an editorial choice from a UI/API default or from an earlier item.
- If one mandatory choice is missing, ask one short, specific question and do not submit.
- Stop on a red fact, approval, completeness, duplicate, credential, or eligibility gate.
- Do not retry a failed gate blindly and do not treat verbal confirmation as a bypass.
- Keep states honest: `queued`/`publication_pending` is not `published`; `live` requires proof.

## News Room

When listing, include a stable response number, technical ID, title, date/source, category,
editorial status, fact-gate result, cover status, assigned position, and publication URL/state
when present.

Before publishing, require one explicit position from:

- `Latest`
- `Hero Main`
- `Hero 2`, `Hero 3`, `Hero 4`, `Hero 5`
- `Insight 1`, `Insight 2`, `Insight 3`

If it is missing, ask exactly: “Dove lo pubblico: Latest, Hero Main, Hero 2–5 oppure Insight
1–3?” Do not send the publish request until answered.

For a batch, require either one common position or a complete article-to-position map. `Latest`
may repeat; each Hero or Insight slot may appear only once in the operation. If a selected slot
is occupied, show its current title and URL and obtain explicit replacement confirmation.
Serialize homepage-slot changes so each one is integrated and verified before the next.

Preflight the current item: eligibility, fact gate, cover, slug uniqueness, public category,
explicit position, and slot conflicts. Submit through the canonical publisher. Record operation
ID, PR, expected URL, and position. Say `IN CODA` while the PR/checks are pending. Never merge or
force a gate. Say `LIVE` and provide the link only after the public URL opens and the expected
title/content matches.

## WR2 carousel

When listing, include stable response number, slug/title, approval state, slide completeness,
caption readiness, render status, publish eligibility, Instagram URL, and metrics state.

Before real publication:

1. Verify `approval_state=approved`, eligible status, complete ordered slides, successful
   renderer output, no existing Instagram publication, and an empty anti-double-post ledger.
2. Generate/load the deterministic caption and show the exact final text plus character count.
3. Obtain explicit approval of that exact caption. An edit invalidates the approval and dry-run.
4. Execute the canonical publisher with `confirm=false` and report the actual validation result.
5. Only after a green dry-run ask: “Verifica superata. Pubblico ora su @balizero0?”
6. Send `confirm=true` only after the subsequent explicit yes in the same flow.
7. Report success only with the Instagram permalink and persisted ledger/queue state.

“Segna come pubblicato” is a separate registration flow for a post already published outside
WR2. Require its real Instagram URL, canonicalize and deduplicate it, then clearly report that
the action recorded an external post and did not publish anything.

## Failure result

Return `BLOCCATO`, name the exact failed gate, state that nothing was published, and give only
the safe corrective next action.
