# Pricing integration contract

Last rechecked: 2026-09-07, Asia/Makassar.

## Authoritative public route

Use only:

```text
GET https://nuzantara-rag.fly.dev/api/pricing/service?key=<exact-catalogue-key>
```

The live route returned the catalogue row for the exact key
`E33 Second Home (5 Years)` with HTTP 200. The audit records that semantic
match without copying the price into website source or documentation.

Repository evidence:

- [`dynamic_pricing.py`](../../../backend-rag/backend/app/routers/dynamic_pricing.py)
  resolves one exact key through `PricingService` and returns 404 rather than
  guessing a near match.
- [`public_endpoints.py`](../../../backend-rag/backend/app/auth/public_endpoints.py)
  exposes only the exact `/api/pricing/service` path to anonymous visitors.
- [`router_manifest.py`](../../../backend-rag/backend/app/setup/router_manifest.py)
  registers the pricing router in both API process groups.
- [`test_public_pricing_lookup.py`](../../../backend-rag/backend/tests/routers/test_public_pricing_lookup.py)
  binds the public route to the PricingService single source of truth and
  protects the exact-match behavior.

`/api/pricing/all`, `/api/pricing/search`, and `/api/pricing/scenario` are not
public website integration routes.

## Consumer behavior

The website consumer should perform a server-side `fetch` using
`URLSearchParams` and a pinned exact catalogue key. This needs no production
dependency.

- HTTP 200: validate the expected key and required response fields, then render
  the returned price.
- HTTP 404: treat the key as absent or changed; omit the price and keep a
  consultation CTA.
- HTTP 422: treat the request contract as invalid; omit the price and surface a
  developer-visible diagnostic without publishing it to visitors.
- HTTP 503, timeout, malformed JSON, or any other failure: omit the price and
  keep a consultation CTA.

Never use approximate search for a displayed price. Never introduce a cached,
hardcoded, rounded, reformatted, or inferred price as a fallback. Rendering no
price is safer than publishing a number detached from PricingService.
