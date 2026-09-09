# Magazine publication boundary — local R19 slice

Date: 2026-09-07 WITA. Scope: local proof, no production connection or release.

## Decision

The Magazine publication repository remains the editorial authority. The website
projects current published records into its existing R19 Journal components.
It owns presentation and a strict allowlist decoder, not publication, approval,
quarantine, correction authoring or another article route. Canonical article
metadata remains the Magazine /stories/{slug} route. The current slice selects
stories belonging to the current edition; it is not a full breaking-news feed.

The old website snapshot remains historical test data but is no longer wired to
/ or /journal. The v1 MDX characterization proof remains isolated and records
known defects. It is not promoted into a publisher.

## Evidence from the existing engine

- apps/zantara-media/zantara_media/magazine/composer.py emits building content.
  A verified lifecycle label is not approval to publish.
- apps/bali-zero-magazine/app/api/machine/publications/editions/route.ts owns the
  authenticated ingress, staging, audit candidate and promotion boundary.
- apps/bali-zero-magazine/lib/server/publication-repository.ts owns finalization,
  the actual published_at timestamp, current story version and current edition.
  getCurrentStory requires a published current version and excludes the latest
  quarantine overlay. Edition entries pin historical versions, so the website
  resolves each candidate again through getCurrentStory.
- lib/server/magazine-read-model.ts exposes internal source-system and evidence
  fields, catches some read failures as null, and does not read correction prose
  or visibility events into its revision timeline. It is not serialized wholesale.
- lib/server/asset-eligibility.ts requires approved rights/usage, verified status,
  passed DLP/sanitization and acceptable deduplication state. Latest status events
  can revoke original eligibility.
- app/api/story-media/[slug]/route.ts is the public route; digest media requires
  internal authorization. lib/server/security.ts returns no-store and CORP
  same-origin. Cross-origin delivery to this standalone website is unproven.

## Implementation contract

src/lib/server/magazine-publication.ts wraps the legacy repository with a
SELECT-only capability. It reads current edition identities, deduplicates
placements, suppresses quarantined/unpublished candidates, and obtains evidence,
revision dates and eligibility for the current version. It rechecks all included
story heads and selected fixture image rights after assembly. This mitigates
observed concurrent changes; sequential D1 reads are not an atomic snapshot.

The v2 envelope exposes only publisher/version/status/provenance and explicit
article fields. No raw source health, story IDs, claim IDs, root identifiers,
notes, payloads or exception strings cross the projection. Evidence links require
an explicit origin allowlist and reject credentials, query and fragment fields.
Origin approval does not prove that arbitrary publisher/citation text is safe:
a future real transport must bind an explicitly approved public projection.

The decoder rejects a corrupt response atomically. Empty, unavailable, malformed,
withdrawn and unpublished are distinct. A current superseded lifecycle, missing
publication date, unsafe URL, wrong canonical route or duplicate article rejects
the response. No date is inferred from fetch time. Amended labels and Revision
published timestamps are supported; correction explanations are not invented.

Both pages use Next connection() for request-time reading. Current HTTP evidence
shows private/no-cache/no-store responses and preview noindex/nofollow/noarchive.
With WEBSITE_EDITORIAL_FIXTURE absent, both pages render unavailable. With value
1, both use a new deterministic in-memory fixture DB per request. There is no
fallback to fixture data after a real service fails.

## What the fixture proves

magazine-fixture.ts applies the real Magazine SQL migrations to local SQLite and
uses the existing stage/finalize repository methods. It publishes three synthetic
non-regulatory stories, an amended second version, a quarantined story and a
building candidate. It seeds synthetic rights and visibility rows. It does not
exercise machine ingress authorization, audit/promotion gates, R2 canonical-byte
validation, real data, network transport or live deployment parity.

The original local SVG is available only for the eligible internal-owned fixture.
Publisher media is always absent. Fixture story/source destinations are disabled,
with a visible sample-content notice. A text-only card is legitimate when media
is absent; unrelated photographs are never substituted.

## Next production prerequisite

Define and verify an authenticated, version-bound read transport and consistent
snapshot/visibility policy from the existing authority. Verify canonical access,
public evidence approval, cache invalidation and same-origin media delivery.
Resolve current-edition versus breaking coverage explicitly. Do not arm that
transport or change publication/access gates as part of this local slice.

## Research clarification at closeout

The completed Gemini pass and separate primary-source checks are recorded in
gemini-research.md, gemini-research-receipt.json and gemini-primary-sources.json.
They add no blocker to the deterministic fixture or its tested final recheck.

- [Fetch CORP](https://fetch.spec.whatwg.org/#cross-origin-resource-policy-check)
  restricts ordinary no-cors image use across origins. A successful CORS or
  same-origin delivery design requires explicit authorization and tests; adding
  an image attribute alone does not establish it.
- [Next connection](https://nextjs.org/docs/app/api-reference/functions/connection)
  defers subsequent work to the request. [HTTP no-store](https://www.rfc-editor.org/rfc/rfc9111.html#section-5.2.2.5)
  constrains HTTP caches. Neither gives atomic database reads, universal cache
  invalidation or recall of already delivered content.
- [D1 Sessions](https://developers.cloudflare.com/d1/best-practices/read-replication/)
  establish sequential consistency and freshness bounds, not proof that our
  separate reads share one frozen snapshot. The future contract must prove its
  chosen version/visibility policy. A single-query design is not the only
  possible solution established by these sources.

The owner must explicitly choose any freshness requirement for already-open
screens; refresh mechanisms then need their own evidence. No such requirement,
transport implementation, publication or access change is authorized here.
