# Gemini research: Magazine media and withdrawal semantics

Status: completed with qualified findings. Date: 2026-09-07 (WITA). Scope: one technical question against a sanitized architecture description, without production access or a new implementation review.

## Execution and observable provenance

The existing agy CLI at /Users/nuzantara/.local/bin/agy, version 1.1.27, completed with exit 0 and SUCCESS. There were two CLI launches for one question: the first stopped at argument validation (exit 2, missing argument for --print); the corrected launch produced one model turn. No fallback model was called.

Requested model: gemini-3.1-pro-high, effort high. The runtime init selected the same slug. The actual provider backend model is not independently observable: neither the runtime-selected alias nor Gemini's final self-report establishes a separate provider attestation.

The trace records three completed search_web calls and two completed read_url_content calls: [MDN CORP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Resource-Policy) and [Next connection](https://nextjs.org/docs/app/api-reference/functions/connection). These are real observed browse calls. Exported events contain their parameters and completion states, not returned page bodies. Cloudflare was searched, but no Gemini page-read event for it exists.

The command requested --mode plan and --sandbox, but stderr warned that plan mode had no effect with slash-command expansion disabled; init reported permission_mode always-proceed. Consequently this receipt attests only the observed read-only web operations, not enforced read-only isolation. No file, command, production, or subagent tool execution appeared in the trace.

The existing OAuth/subscription CLI route was requested. No credential or auth configuration was inspected; common API-key and application-credential environment variables were removed by name before launch. No new key or paid endpoint was configured. Account, billing tier, and actual authentication transport remain unattested.

## Findings retained after source checks

1. CORP same-origin blocks ordinary no-cors image embedding from a distinct R19 origin. A different subdomain is a different origin. This is a response-use restriction, not evidence that the network request never happened. [Fetch normative check](https://fetch.spec.whatwg.org/#cross-origin-resource-policy-check), independently checked by the coordinator; [MDN browser explanation](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Cross-Origin_Resource_Policy), opened by this audit subagent.
2. An explicitly designed successful CORS image load has different requirements, including the server's CORS permission. Adding crossorigin alone proves no successful delivery. No such path was tested or authorized here. [HTML crossorigin behavior](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/crossorigin), opened separately by this audit subagent.
3. connection() excludes subsequent work from prerendering by waiting for a request. HTTP response no-store constrains compliant HTTP-cache storage and reuse. Neither contract establishes an atomic database snapshot, invalidates every application/client cache, or recalls an existing DOM. [Next connection](https://nextjs.org/docs/app/api-reference/functions/connection) and [RFC 9111 response no-store](https://www.rfc-editor.org/rfc/rfc9111.html#section-5.2.2.5), independently checked by the coordinator. The separate [Next caching guide](https://nextjs.org/docs/app/guides/caching-without-cache-components) documents explicit data caching under its stated configuration; it is not a deployment audit.
4. D1 Sessions provide sequential consistency and bookmark freshness bounds. The documented example can advance from one database version to another after concurrent writes. Inference: a session alone does not prove that separate edition/story/rights reads share one frozen snapshot. first-primary is not an atomic-read certificate. [Cloudflare D1 read replication](https://developers.cloudflare.com/d1/best-practices/read-replication/), opened independently by this audit subagent. No live D1 binding was queried.

## Corrections to the raw Gemini answer

The attached final answer remains advisory evidence. Reject its universal guarantees that every image attempt hits the origin and that connection() removes all App Router caching. Also reject the claim that every intervening withdrawal inevitably causes a torn read: final visibility/version/rights checks can detect changes and fail closed. Removing an ineligible image while retaining an eligible story can be the intended policy.

Separate reads still do not prove atomicity, but this research does not re-open the accepted fixture mitigation or reproduce a new defect. Gemini's mandatory single-query prescription is unsupported as the only solution. Any future coherent snapshot or revision-bound projection needs its own implementation and consistency evidence. SSE/WebSockets are possible mechanisms for an explicitly chosen open-screen refresh policy, not a requirement established by these sources.

## Decision boundary

This research introduces no additional blocker for the deterministic local fixture. Production remains unarmed. Before connecting it, prove the authorized browser media-delivery path, define the read-consistency and withdrawal freshness contract, and test relevant caching/navigation behavior. Already delivered bytes or screenshots cannot be recalled by these headers. A requirement to update already-open screens needs an explicit refresh policy and its own evidence.

Current Next documentation can describe a newer patch than the locally reported 16.3.1; no upgrade or exact-version behavior claim is made. The coordinator reported documentation version 16.3.4. Source validation and Gemini browsing are recorded separately in gemini-primary-sources.json. Only the final model answer, tool metadata, and sanitized execution evidence are retained; no private reasoning transcript is included.
