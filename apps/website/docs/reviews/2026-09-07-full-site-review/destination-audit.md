# Public destination audit

Date: 2026-09-07 WITA. HTTP identity checks occurred at 2026-09-06 18:50 UTC;
public entry text and controls were rechecked at 18:57 UTC.

Fifteen public web destinations returned HTTP 200 after any redirects. No
missing page, 4xx/5xx response or timeout was observed in this set. This is
reachability and page identity evidence, not proof of every tool workflow,
account feature, legal statement, service promise or page accessibility.

The sanitized `destination-http.json` receipt records each GET, time, redirects,
status and server-rendered title/H1. Requests used no credentials or browser
cookies. Raw responses, response cookies and redirect query strings were not
retained. The read was bounded to six HTTPS redirects and a request timeout.

| Destination | Observed result | Scope of conclusion |
| --- | --- | --- |
| [E-VOA](https://balizero.com/visa/voa) | 200 at `/visa/voa`; Visa on Arrival title/H1; new/extend choices and Next | Public application entry matches the link; no application or payment attempted |
| [Second Home Studio](https://balizero.com/visa/second-home/studio) | 200 at the requested path; Second Home Studio / Check your fit; age choices and Continue | Public fit-questionnaire entry matches the link; no answers submitted |
| [My Bali Zero](https://my.balizero.com/) | 307 to `/portal/login`, 308 to `/portal/login-upgraded`, then 200; Login title and email field | **Account is authentication-gated.** Public sign-in reachable; no login or private account capability verified |
| [Visa Oracle](https://visa.balizero.com/) | 302 to `https://balizero.com/visa`, then 200; Bali Visa Eligibility & Selection title; in-Indonesia/planning links | Relevant visa exploration entry exists, although its current page title differs from Visa Oracle; no recommendation or cost outcome validated |
| [KBLI Navigator](https://balizero.com/kbli) | 200 at `/kbli`; KBLI Navigator title and KBLI 2025 H1; search, sectors and view controls | Navigator entry matches the link; no search, chat or classification outcome validated |
| [Tax Compliance Calendar](https://tax.balizero.com/) | 200 at the requested origin; matching title/H1; tax-type filters, regency selector and iCal link | Calendar entry matches the link. Rendered cards include overdue historical obligations; freshness and legal deadline accuracy remain unverified |
| [Property Check](https://balizero.com/property/eligibility) | 200 at the requested path; Property Eligibility Check title/H1; coordinates input and Analyze | Checker entry matches the link; no location query or legal outcome submitted/validated |
| [Public news index](https://balizero.com/news) | 200; Indonesia News & Regulatory Intelligence title | Legacy registry destination reachable; R19 currently uses local `/journal`. No article facts reviewed |
| [Google reviews listing](https://maps.app.goo.gl/whiMUTNchcDR5naz8) | 302 to Google Maps place path containing Bali Zero, then 200 | Google destination reachable and redirect identity matches; hydrated listing, rating and review count **unverified** |
| [Google office search](https://maps.google.com/?q=Bali+Zero+Kerobokan) | Two 302 redirects to Google Maps, then 200 | Search destination reachable; resolved place and displayed address **unverified** |
| [Our story](https://balizero.com/v2/company/about) | 200; About Bali Zero title | Public company page reachable; historical claims not independently verified |
| [Public team directory](https://balizero.com/team) | 200; Team title/H1 | Legacy registry destination reachable; R19 uses local `/team`. No parity claim with the approved local roster |
| [Privacy](https://balizero.com/v2/privacy) | 200; Privacy Policy title/H1 | Notice exists at the linked public destination; not a legal adequacy review |
| [Terms](https://balizero.com/v2/terms) | 200; Terms of Service title/H1 | Notice exists at the linked public destination; not a legal adequacy review |
| [Cookies](https://balizero.com/v2/cookies) | 200; Cookie Policy title/H1 | Notice exists at the linked public destination; not a cookie behavior audit |

## Contact intents and inactive destinations

Source checks preserve the approved `wa.me` recipient, public team email and
telephone destinations. Service tests verify the contextual WhatsApp text is
URL encoded and introduces no extra query fields. WhatsApp, email and dialer
intents were not launched and nothing was sent. These remain **source-checked
intents**, not successful delivery or telephone reachability claims.

Telegram is blocked by the existing destination contract and absent from the
current presentation. This audit did not reactivate or probe it. The public
news and team URLs above are retained registry entries, not instructions to
replace the current local Journal or Team navigation.

## Public entry feature evidence

`destination-public-entry.json` records the six tool entry pages' server-rendered
headings, controls and short public text excerpts. This is direct HTTP evidence,
not an interaction or a legal fact check; numeric or regulatory text in those
excerpts is unverified external copy and must not be adopted as R19 evidence.

The parent independently inspected these six destinations and My Bali Zero in
live CUA. It reported the same entry controls listed above, including My Bali
Zero's email input and Pass Portal at `/portal/login-upgraded`. These are
**parent browser observations**, not browser actions performed by this document's
author. The seven first screens therefore contain relevant public interfaces,
rather than only an HTTP 200 landing or soft-404 response. No data was entered,
no form was submitted and no authentication was attempted. Deeper workflows,
private account features, legal accuracy and operational outcomes remain outside
the completed verification.

## Separate web-reader observations and limits

Web-reader opens supplemented the direct HTTP checks. It exposed the public
Second Home entry, KBLI search surface, property entry and news index. Some
reader results carried older crawl dates, so they do not establish current
runtime health; the separately timestamped direct GET receipt does. The reader
declined E-VOA and My Bali Zero with its URL-safety error; that is a retrieval
tool limitation, not evidence that those destinations failed. Direct public
GETs returned the page and sign-in surface recorded above.

No legal, price, deadline, eligibility or performance assertion from these
external pages was adopted into R19. The existing `Since 2020` line is inherited
owner-approved R19 copy, not a founding date newly verified by this pass.
Repetition on company-owned pages is not independent evidence. No new factual
claim is approved by this destination audit.
