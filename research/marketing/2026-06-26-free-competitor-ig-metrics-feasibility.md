---
date: 2026-06-26
domain: marketing
client_case: Bali Zero external-bench — measuring engagement (saves, shares, reach) of competitor IG profiles we don't own (Lets Move Indonesia, Emerhub, Flado + ~12 editorial reference brands), free-first, no account-ban risk
author: deep-researcher (Antonello/Bali Zero)
status: draft
partial: false
sources:
  - Meta for Developers — Business Discovery reference (developers.facebook.com/docs/instagram-platform/.../business-discovery/)
  - Instagram Official APIs — Comprehensive Reference April 2026 (gist.github.com/jameschapman2c/65eff9f54a2d350b17a6ce5127b9fe42)
  - business_discovery media-edge query examples (medium.com/@ritikkhndelwal; github imakashsahu/jainj2305; elfsight 2026 guide; keyapi.ai)
  - Socialinsider Instagram Engagement Report (15M posts, Oct 2025–Mar 2026)
  - Instagram 2026 ranking-signal coverage (Hootsuite, Buffer, Later, Sprout, Mosseri statements)
  - Socialcrawl "Instagram Scraping 2026" + instaloader GitHub (v4.15.1) + Bellingcat toolkit
  - Social Blade FAQ / reviews (whop, monetizepros, selecthub)
  - PeekStories "Saved Posts Privacy 2026"; Spinthiras "Reel Views 2026"; AMZG "How IG Changed View Counting"
---

# Free Ways to Estimate Competitor Instagram Engagement (Saves / Shares / Reach) — 2026 Feasibility

## Question

Are there any FREE ways — including indirect/back-door/grey-area methods — to obtain or reliably ESTIMATE the engagement performance (SAVES, SHARES/DM-sends, REACH/impressions) of an Instagram profile we do NOT own? Constraint: zero paid APIs unless authorized, no scraping that risks our own account bans. Three named competitors (Lets Move Indonesia, Emerhub, Flado) + ~12 editorial reference brands. We already run a monthly external-bench reading public post design; we have Playwright, Ollama, and Gemini/Claude/Codex OAuth subs.

## TL;DR

- NO. Real saves, shares, and reach of a profile you don't own are not exposed by any surface — web, app, oEmbed, Graph API, or scraper. They are owner-only Insights, by deliberate Meta design. Every claim that a free tool "gives you saves/shares" is false or modeled.
- The real free path: Instagram Graph API `business_discovery` returns, for any PUBLIC professional account, per-post `like_count`, `comments_count`, and (2026) `view_count`, plus caption/timestamp/media_type. Build a save/forward PROXY from those + comment text.
- Proxy is directional, not precise: format + save-intent comment language + view-to-follower ratio rank "likely-forwarded" content well enough to steer editorial, but never reproduce the absolute save/share number.

## The Hard Wall — what is public vs owner-only in 2026

Saves, shares/sends, reach, and impressions are **aggregate Insights visible only to the account owner** (Professional/Creator account). Confirmed consistently across sources. Two corollaries that matter:

- **Saves are doubly private**: the owner sees the *count* but not *who* saved; a third party sees *nothing*. Researching a competitor by saving their posts is invisible to them (zero risk on that axis). [PeekStories 2026]
- **Shares/sends are now the #1 ranking signal** ("sends per reach", per Mosseri), which is exactly why Meta guards them — they are never published on a post. [Hootsuite/Buffer/Sprout 2026]

**Did view counts go public?** Partially, and this changed in 2025-2026:
- View count is shown on the reel/video UI to **anyone** (it is the first number on a reel, screenshot-shared in creator communities). [Spinthiras 2026]
- Late-2025 Meta changed *how* views are counted: passive grid/Explore scrolls no longer count; a view now requires meaningful active engagement. So the public view number is "stricter" than before but still public. [AMZG 2026]
- **Reach/impressions remain owner-only** even where the public view count is shown. View != reach (one viewer can generate multiple views; reach is unique accounts). Do not treat a public view count as reach.

**Net**: the only third-party-visible engagement signals are **likes, comments, comment text, view count (reels), follower/following/media counts, and posting cadence**. Saves/shares/reach: never.

## Free official / semi-official surfaces

### Instagram Graph API — `business_discovery` (THE free path)

This is the sanctioned, ToS-clean, $0 way to read a competitor's public professional account. It is a nested query on YOUR own connected IG Business account.

**Verbatim working query shape** (field string, confirmed across multiple 2026 implementations):

```
business_discovery.username(COMPETITOR_USERNAME){
  username, name, id, biography, website, profile_picture_url,
  followers_count, follows_count, media_count,
  media{ id, caption, comments_count, like_count, view_count,
         media_type, media_url, permalink, timestamp, children }
}
```

**What it returns** (verified — note: several 2026 blog posts wrongly claim it returns "account-level only". They show a minimal example that omits the `media{}` edge. The April-2026 comprehensive reference and multiple working code samples confirm the media edge):
- Account: `followers_count`, `follows_count`, `media_count`, `biography`, `website`, `username`, `profile_picture_url`, `id`.
- Per post (paginated): `like_count`, `comments_count`, `view_count` (2026 addition, reels/video), `caption`, `timestamp`, `media_type`, `media_url`, `permalink`, `children` (carousel).

**What it NEVER returns for accounts you don't own**: saves, shares/sends, reach, impressions, saved_count, share_count. Confirmed by Meta docs and every secondary source.

**Setup / gotchas**:
- Requires a Meta Developer app (Business type) + a Facebook Page + YOUR own IG **Business/Creator** account connected to it + a long-lived access token (`instagram_basic` + `pages_show_list`/`instagram_manage_insights`). Free.
- Target account must itself be **public** AND a **Professional (Business/Creator)** account. Personal/private accounts return nothing — verify each competitor is professional first.
- Caveat: media IDs from `business_discovery` cannot be re-fetched via separate GET calls — they only work nested. So you snapshot in one paginated pass.
- **Rate limit**: ~200 calls/hour/user (rolling). Trivial for ~15 accounts polled daily/weekly.
- App review: NOT required for business_discovery on your own token used for internal analytics (only required if you serve many third-party users).

### Other Meta surfaces
- **oEmbed**: embed HTML + `author_name`/`author_url`/`thumbnail_url` only — no engagement numbers. Since April 2025 it dropped `thumbnail_url`/`author_name` in some paths and routes through Graph API; needs an app token. Useless for metrics.
- **`?__a=1` / `__a=1&__d=dis`**: effectively dead for structured public JSON — not in any current official reference, killed/gated years ago; relying on it is brittle and login-walled. Do not build on it.
- **Public profile/web JSON** (`web_profile_info`): still exists as Instagram's *internal* endpoint (what scrapers hit), NOT an official surface — see risk frame below.

## Free / open-source tooling

**Instaloader** — the live, maintained ($0, self-hostable) option: v4.15.1, ~12.1k stars, last commit April 2026 [GitHub]. It hits Instagram's **internal** endpoints (`i.instagram.com/api/v1/users/web_profile_info`, GraphQL), NOT the Graph API. For public profiles without login it can pull: captions, hashtags, like counts, comment counts, view counts, timestamps, media type, posting cadence — i.e., the **same public surface** as business_discovery, plus it works on any public account (not just professional ones).

- It does **NOT** and **cannot** return saves/shares/reach. No OSS tool can — that data isn't in the response. (Issue tracker even documents IG threatening bans on instaloader activity.)
- Maintained-vs-abandoned 2026: instaloader = alive. Apify IG Scraper, Bright Data, SocialCrawl = alive but **paid** (out of scope unless authorized). The Python "private API" wrappers (instagrapi etc.) require login -> high ban risk.
- **The estimation debunk**: only SocialCrawl advertises an `estimated_reach` field — and it is explicitly a **computed/modeled** field (its docs also list `engagement_rate`, `content_category`), not real Meta reach. No tool, free or paid, returns *real* saves/shares/reach. Anything labelled "competitor reach/saves" is a model output, treat as a guess.

## Proxy / derived signals — the realistic answer

Since saves/shares/reach are unreachable, build a **forwardability/save-likelihood model** from the public signals you CAN get (likes, comments, comment text, view_count, format, cadence, followers). Published 2025-2026 evidence makes this directionally sound:

**Socialinsider Engagement Report (15M posts, Oct 2025–Mar 2026)** gives the strongest public anchor — median saves/shares/comments by format:

| Format | Comments (median) | Shares (median) | Saves (median) | Comment-rate | Share-rate | Save-rate |
|---|---|---|---|---|---|---|
| Reels | 33 | 5 | 35 | 0.06% | 0.10% | — |
| Carousels | 25 | 3 | 37 | — | — | 0.05% |
| Images | 20 | 1 | 10 | 0.03% | 0.07% | 0.02% |

Key inferences for the proxy:
1. **Format is the single biggest predictor.** Carousels dominate SAVES (educational/reference content "bookmarked for later"); Reels dominate SHARES and comments. So tagging each competitor post by `media_type` already predicts *which behavior* it drove, before counting anything. This is the cheapest, most reliable proxy.
2. **Comment-to-like ratio** = "did it spark a scroll or a conversation". Higher ratio -> deeper engagement; useful relative ranking within one account, but note 2025 saw comments fall ~16% as behavior migrated to invisible saves/sends — so absolute comment counts undercount real engagement.
3. **Save-intent / share-intent language in comment TEXT** is the highest-signal free proxy for the invisible metrics. Run Ollama (local, $0, PII-safe) over fetched comments to detect:
   - Save intent: "saving this", "bookmarking", "need this later", bookmark emoji, "noted".
   - Share intent: "sending this to @", "tag a friend", "@name look", "sharing with my...".
   - Frequency of these per post correlates with the actual save/send the algorithm rewards (Instagram itself treats "send this to a friend" as the #1 distribution signal). This is correlational, not a count of real sends.
4. **View-to-follower ratio (reels)**: `view_count / followers_count`. Ratio >> 1 means the reel travelled beyond the follower base — a strong proxy that the post was *shared/distributed* (since reach isn't visible, outsized views are the visible shadow of reach). This is your best free reach-proxy for reels.
5. **Engagement rate (public-only)** = `(likes + comments) / followers`. Standard, comparable across competitors. Augment with view-to-follower for reels.

**How good is the proxy?** Honest assessment: it is **ordinal, not cardinal**. It will reliably rank *which competitor content types and topics get forwarded/saved* (carousel how-to on KBLI vs reel reaction), which is exactly what the editorial bench needs. It will NOT reproduce the actual save/share *number* — those benchmarks (37 median saves/carousel) are population medians, not per-post truth, and engagement is power-law distributed so medians hide huge variance. Use the model to choose what to make, never to report "Emerhub got 412 saves".

## Third-party estimation tools (free tier)

- **Social Blade** (free): shows follower/following history, growth trends, and a modeled "engagement rate" + grade. Follower/growth tracking is reliable; the engagement-rate and any reach/estimate figures are **modeled from public likes/comments**, NOT Meta data, and real-time/estimate numbers are explicitly flagged as less reliable. Free tier is fine for tracking competitor follower growth and cadence; ignore its "reach"/projection numbers as anything but a guess.
- Everything that claims competitor "saves/reach" with a free tier is modeling public likes/comments — same debunk as SocialCrawl. Paid tiers (Apify, Bright Data, premium analytics suites) = out unless Zero authorizes; even then, no real saves/shares/reach, only better-modeled estimates and convenience.

## Disagreements / open questions resolved

- **Disagreement (resolved)**: keyapi.ai and elfsight 2026 guide imply business_discovery returns *account-level only*, no per-post like/comment. CONTRADICTED by the April-2026 comprehensive reference + 3 working code samples that request `media{like_count,comments_count,view_count,...}`. Resolution: trust the working query strings + Meta media-edge spec — business_discovery DOES return per-post likes/comments/views. The minimal blog examples simply omitted the media edge.
- **Open**: exact ToS posture of running `business_discovery` against accounts purely for competitive benchmarking is clean (it's an official, documented, low-volume read on your own token). Instaloader on internal endpoints is a grey area (next section).

## Legal / ToS / ban-risk frame

| Method | Reads | Login/cookies? | Account-ban risk to OUR business accounts | Verdict |
|---|---|---|---|---|
| **Graph API `business_discovery`** | public pro-account likes/comments/views/caption/cadence | No (app token, own IG Business) | **None** — sanctioned, documented, official | USE — primary |
| **Social Blade free tier** | follower growth, modeled ER | No | None (they scrape, not us) | USE for growth/cadence only; ignore estimates |
| **Saving competitor posts manually** for design study | post design, captions | Own login (normal use) | None — invisible to them, normal behavior | OK (current bench) |
| **Instaloader, low rate, residential IP, no login** | public likes/comments/views/captions | No login = lower risk, but hits internal endpoints | **Low-to-moderate** — even moderate use triggers 429/temp-locks; ToS-grey | Avoid unless business_discovery insufficient; if used, no login, tiny volume, never from an account we care about |
| **Instaloader/instagrapi WITH login/cookies** | more, incl. private | Yes | **High** — direct ban vector for the logged-in account | DO NOT — endangers our accounts |
| **Automated scraping at scale / proxies / TLS-spoof** | bulk | varies | **High** + clear ToS violation | DO NOT |
| **Paid scrapers (Apify/Bright Data/SocialCrawl)** | public, modeled estimates | No | Low (their infra) but **paid** | Out unless Zero authorizes; still no real saves/shares/reach |

PII note: competitor follower handles and commenter usernames are personal data — keep aggregate; don't persist commenter-level PII in shared artifacts (UU PDP / SYMBIOSIS Law 2).

## Checklist for action

- [ ] Stand up a Meta Developer app (Business) + connect Bali Zero's own IG Business account; mint a long-lived token (`instagram_basic`, `instagram_manage_insights`). $0.
- [ ] Verify each of the 3 competitors + 12 editorial brands is a PUBLIC Professional account (business_discovery returns nothing otherwise); flag any personal/private for manual-only tracking.
- [ ] Build a weekly Playwright/Python poller calling `business_discovery.username(X){...,media{like_count,comments_count,view_count,caption,media_type,timestamp,permalink}}` for all ~15 accounts (well under 200 calls/hr). Snapshot to local store (no commenter PII).
- [ ] Compute per-post proxy fields: format tag, engagement_rate=(likes+comments)/followers, comment-to-like ratio, view-to-follower ratio (reels), and run local Ollama save-intent/share-intent detection over comment text.
- [ ] Feed the external-bench agent ordinal "forwardability/save-likelihood" scores per competitor content type — use to choose what to make, never to report absolute save/share counts.
- [ ] Track competitor follower growth + cadence via Social Blade free tier as a secondary; discard its modeled reach/ER numbers.
- [ ] Do NOT deploy any logged-in scraper or paid API without Zero's explicit authorization.

## Sources

1. Meta for Developers — Business Discovery reference; oEmbed reference (developers.facebook.com, fetched 2026-06-26).
2. Instagram Official APIs — Comprehensive Reference, April 2026 (gist.github.com/jameschapman2c/65eff9f54a2d350b17a6ce5127b9fe42) — confirms `business_discovery` media edge incl. `view_count`; oEmbed fields; "no official surface for saves/shares/reach of other accounts".
3. business_discovery media-edge working queries: medium.com/@ritikkhndelwal; github imakashsahu/Instagram-Graph-API-Python; github jainj2305/instagramGraphAPI; elfsight 2026 guide; keyapi.ai (the last two omit the media edge — used to surface and resolve the disagreement).
4. Socialinsider Instagram Engagement Report — 15M posts, Oct 2025–Mar 2026 (format-level save/share/comment medians).
5. Instagram 2026 ranking signals — Hootsuite, Buffer, Later, Sprout (sends/saves as top signals; Mosseri statements).
6. Socialcrawl "Instagram Scraping 2026"; instaloader GitHub v4.15.1 + issue #2555 (ban threats); Bellingcat toolkit; Mailerfind 2026 (instaloader alive; only SocialCrawl computes `estimated_reach` = modeled).
7. Social Blade FAQ + reviews (whop, monetizepros, selecthub) — follower/growth reliable, ER/estimates modeled.
8. PeekStories "Saved Posts Privacy 2026" (saves invisible to third parties); Spinthiras "Reel Views 2026" + AMZG "How IG Changed View Counting" (view count public, counting rules tightened late-2025, reach owner-only).
