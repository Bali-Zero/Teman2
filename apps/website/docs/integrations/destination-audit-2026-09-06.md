# Destination audit — 2026-09-06

Audit timezone: Asia/Makassar (WITA). The checks combined redirect-aware HTTP
requests with hydrated browser inspection. No customer account was accessed,
no form was submitted, and no contact message was sent. An HTTP 200 response
was recorded as reachable only after the rendered destination and intended
action were inspected.

The executable evidence table is
[`src/content/evidence/destinations-2026-09-06.ts`](../../src/content/evidence/destinations-2026-09-06.ts).
Its `result` and `intentMatch` fields deliberately separate transport reachability
from product correctness.

## Primary destinations

| ID                    | Requested destination                            | Result         | Intent     | Release action  | Evidence                                                                                                                                           |
| --------------------- | ------------------------------------------------ | -------------- | ---------- | --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `evoa`                | `https://balizero.com/visa/voa`                  | REACHABLE      | MATCH      | LINK            | The Visa on Arrival first step rendered. Its canonical URL points to `/visa`, so consumers must not infer a distinct canonical product page.       |
| `secondHomeStudio`    | `https://balizero.com/visa/second-home/studio`   | REACHABLE      | MATCH      | LINK            | The public six-step fit exploration rendered.                                                                                                      |
| `myBaliZero`          | `https://my.balizero.com/`                       | LOGIN_REQUIRED | MATCH      | LOGIN_COPY_ONLY | The root redirected to `/portal/login-upgraded`; only the account sign-in surface was verified.                                                    |
| `visaOracle`          | `https://visa.balizero.com/`                     | REDIRECT       | MATCH      | LINK            | One redirect reached the public visa selector at `https://balizero.com/visa`.                                                                      |
| `kbliNavigator`       | `https://balizero.com/kbli`                      | REACHABLE      | MATCH      | LINK            | The public KBLI 2025 navigator rendered.                                                                                                           |
| `taxIntelligence`     | `https://tax.balizero.com/`                      | REACHABLE      | PARTIAL    | LINK            | The product identifies itself specifically as **Tax Compliance Calendar**. Do not label it as a broader intelligence product.                      |
| `propertyEligibility` | `https://balizero.com/property/eligibility`      | REACHABLE      | MATCH      | LINK            | The public Property Eligibility Check rendered.                                                                                                    |
| `journal`             | `https://balizero.com/news`                      | REACHABLE      | MATCH      | LINK            | The hydrated Journal index rendered current story cards.                                                                                           |
| `googleReviews`       | `https://maps.app.goo.gl/whiMUTNchcDR5naz8`      | REDIRECT       | MATCH      | LINK            | The short link reached the Bali Zero place profile. The live snapshot displayed 4.9 stars and 679 reviews, while the reference prototype said 693. |
| `googleLocation`      | `https://maps.google.com/?q=Bali+Zero+Kerobokan` | REDIRECT       | MATCH      | LINK            | The Bali Zero place profile in Kerobokan rendered.                                                                                                 |
| `companyAbout`        | `https://balizero.com/v2/company/about`          | REACHABLE      | MATCH      | LINK            | The expected public About Bali Zero page rendered.                                                                                                 |
| `team`                | `https://balizero.com/team`                      | REACHABLE      | MATCH      | LINK            | The expected public team directory rendered.                                                                                                       |
| `privacy`             | `https://balizero.com/v2/privacy`                | REACHABLE      | MATCH      | LINK            | The public privacy notice rendered.                                                                                                                |
| `terms`               | `https://balizero.com/v2/terms`                  | REACHABLE      | MATCH      | LINK            | The public terms notice rendered.                                                                                                                  |
| `cookies`             | `https://balizero.com/v2/cookies`                | REACHABLE      | MATCH      | LINK            | The public cookie notice rendered.                                                                                                                 |
| `whatsapp`            | `https://wa.me/628213454721`                     | REDIRECT       | MATCH      | LINK            | WhatsApp opened the Bali Zero contact surface; nothing was sent.                                                                                   |
| `email`               | `mailto:zantara@balizero.com`                    | NOT_TESTED     | NOT_TESTED | LINK            | Recipient syntax is covered by tests. A mail client was not opened.                                                                                |
| `telephone`           | `tel:+628213454721`                              | NOT_TESTED     | NOT_TESTED | LINK            | E.164 syntax is covered by tests. A dialer was not opened.                                                                                         |
| `telegram`            | `https://t.me/Balizerobot`                       | BLOCKED        | MISMATCH   | SUPPRESS        | The public page exposed unrelated adult/spam bot content. The destination must not ship.                                                           |

The contextual WhatsApp intents for Second Home Studio and E-VOA both reached
WhatsApp with their encoded topic and contact name preserved. They were not
sent. Intent builders are centralized in
[`src/lib/destinations/intents.ts`](../../src/lib/destinations/intents.ts).

## Journal originals

All six original story routes returned the expected H1 and hydrated article
body. The categories and dates below were visible in the rendered pages.

| Story                                                                                   | Result            | Rendered metadata                  |
| --------------------------------------------------------------------------------------- | ----------------- | ---------------------------------- |
| `/business/balis-sub-50k-villa-boom-accessible-luxury-or-due-diligence-trap`            | REACHABLE / MATCH | BUSINESS; Sep 4, 2026; 3 min read  |
| `/business/the-villa-dream-has-a-new-wall`                                              | REACHABLE / MATCH | BUSINESS; Jun 23, 2026; 4 min read |
| `/business/indonesias-kbli-2025-shake-up-the-transition-rules-every-business-must-know` | REACHABLE / MATCH | BUSINESS; Sep 4, 2026; 3 min read  |
| `/business/the-it-escape-route`                                                         | REACHABLE / MATCH | BUSINESS; Jun 23, 2026; 3 min read |
| `/visas/bali-immigration-brings-permit-services-to-discovery-mall`                      | REACHABLE / MATCH | VISAS; Jul 11, 2026; 3 min read    |
| `/business/indonesias-nib-the-one-business-id-every-investor-must-have`                 | REACHABLE / MATCH | BUSINESS; Jul 11, 2026; 3 min read |

## Journal filters and search

The following URLs preserved their parameter but rendered the same unfiltered
index and story set as `/news` after hydration:

- `?category=trends`
- `?category=visas`
- `?category=taxes`
- `?category=property`
- `?q=pt+pma`
- `?q=kitas`
- `?q=digital+nomad`

They are REACHABLE but MISMATCH. Until the Journal implements parameter-aware
results, route category/search actions to `/news` or render their labels as
non-clickable metadata.

## Release fallbacks

- Resolve outbound actions through `getReleasableDestination`. It returns
  `null` for blocked destinations, currently Telegram.
- Describe My Bali Zero only as existing client account access. Document
  storage, application tracking, chat, and security behavior were not tested.
- Use **Tax Compliance Calendar** as the tax product name.
- Prefer a non-numeric Google reviews CTA. A displayed count becomes stale and
  must be refreshed from the live listing before release.
- Keep the Journal index and six originals linkable. Do not promise working
  search or category filtering until their rendered results diverge correctly.
- When an approved service destination fails, use the explicit
  `unavailableFallback` in the destination contract; do not invent eligibility,
  duration, price, or outcome claims.
