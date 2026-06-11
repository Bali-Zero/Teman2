---
date: 2026-06-12
domain: design
client_case: MYTHOS balizero.com redesign — Visa funnel + KBLI navigator tool pages
sources:
  - rocket.new/templates/counsel-authoritative-legal-landing-page-template (editorial legal template, 2026-03)
  - studioslate.com.au/work/thornfield-legal (premium legal site, Lighthouse 100)
  - fuselabcreative.com/chatbot-interface-design-guide (regulated-context chat UI)
  - arahi.ai/chat-embed (native embedded chat patterns)
  - ethora.com/blog/chatbot-ui-examples-and-best-practices (2026-05, chat UX)
  - uplup.com/blog/how-to-build-a-quiz-funnel (2026-05, quiz funnel UX)
  - growthlens / lollypop.design / revenuecat / funnelfox (funnel + progress + bridge patterns)
  - paperstreet.com, smotrow.com, walkeradvertising, karozieminski.substack.com (editorial design trends 2026)
---

# Editorial-elegance brief — Visa funnel + KBLI navigator (light theme)

Built from Exa deep-research (June 2026 sources) after Antonello rejected the mechanical
"dark de-darkened" conversion of these two tool pages. Fixed system: warm paper `#f7f6f2`,
white `#fff` cards, navy `#1e3863` (masthead+footer+headings), single red `#FF2D4C`
(one primary action/page), Cormorant Garamond display + Inter body, 8pt rhythm, Economist/FT.

**Verdict in one line:** build both pages as *law-review editorial documents that happen to
be interactive* — not SaaS widgets. In regulated/legal, restraint reads as competence; clutter
reads as insecurity.

## A. Editorial elegance — the rules
1. Order: structure → type → spacing → surface → accent → motion → imagery. Red is the LAST thing added.
2. One oversized Cormorant statement per SECTION (not per element) — works because rationed.
3. Whitespace budget 1.5–2× comfortable: ≥96–128px between sections, ≥48px card padding, ≥24px min air.
4. Thin navy hairlines (~1px @14% opacity) instead of boxes/shadows to organize.
5. Borders give depth; drop-shadows banned. Flat #fff cards on #f7f6f2 separate by value contrast + 1px border.
6. Reduced palette + ONE red per viewport. Two reds visible = one is wrong.
7. Copy IS interface — write labels, not lorem. "The right Indonesian visa, matched to your stay" not "Find your visa".
8. Hierarchy by scale+weight, not color. Modular scale ~14/16/20/28/40/64. Body Inter 16–18px (16 floor).
9. Hover quiet (border-color shift / 1px underline grow). NO parallax.
10. Motion: CSS fade-slide on scroll (IntersectionObserver), staggered, `prefers-reduced-motion` honored.
11. Card-based modular UI for dense regulatory info (category pill + one-line + date).
12. Speed = elegance: self-host+subset fonts `font-display:swap`, WebP ≤200–400KB, ≥90 mobile PageSpeed.

## B. Hero — THE decision (CONFIRMED with Antonello 2026-06-12)
**Both pages: typographic editorial hero, NO hero image.** Stock/AI photos lose trust instantly in legal.
- Visa funnel → Cormorant line + Inter sub + single red "Find my visa". Calm invitation, low-friction quiz start.
- KBLI navigator → hero IS the search: Cormorant headline above a generous search field + 3–4 example chips.
- Team photo reserved for homepage/about, NOT tool pages. Animated/abstract hero = wrong posture.

## C. Visa funnel UX
- One question per screen (wizard). 5–8 questions max (conversion sweet spot); each must change the recommendation.
- 3–5 result buckets (visa types). Persistent progress bar EVERY screen, achievement-framed
  ("Step 3 of 6 · Stay & purpose", "3 answers captured"), total count from screen 1.
- Quiet fade-slide transitions; Back + Save&exit; easiest question first.
- **Pre-result "bridge" screen** ("Matching you…") that reflects their answers back — highest-leverage premium move.
- RESULT screen (stats-wall): verdict in Cormorant (visa name) → 1–2 sentence rationale echoing THEIR answers
  → numbers as editorial fact (PricingTool cost + timeline + validity, "tombstone") → ONE red WhatsApp CTA framed
  as delivery not toll → trust signals under it → source citation (Permenkumham). Email optional/soft, after value.

## D. KBLI navigator + embedded Zantara chat
- Search-first hero (field + 3–4 example chips). Results = modular editorial cards
  (code Cormorant + judul + plain-language line + risk pill + PMA pill). Detail page = editorial document
  (oversized code/judul masthead, hairline, scannable sections, hard numbers as small tombstone cluster).
- Chat: collapsible, NEVER auto-open. Launcher "Ask Zantara about this code" (page-aware). Inherits font stack +
  #fff surface + navy text, red only on send. Custom Zantara mark, not generic bot. Open with capability transparency
  + 3–5 quick-reply chips ("Can foreigners own this?" "Minimum capital?" "Related codes" "Talk to a human"), free-text second.
  Typing indicator + small avatar (don't fake humanity). **REGULATED: source citations inline+expandable on every
  regulatory claim; calibrated hedging when uncertain; always-visible human-escalation to WhatsApp.** Messages <60 words.
  WCAG 2.2 AA.

## E. Numbers / trust for regulated services
- Stats-wall "tombstone": oversized Cormorant figures + quiet graphite descriptor (visa cost/timeline, KBLI capital/risk).
- Concrete dated specific numbers beat round/vague. Keep dates CURRENT (stale date kills trust).
- Prices from PricingTool, presented as editorial fact attached to the CTA (not a floating line).
- Credentials integrated as a quiet band (years, cases, regulatory citations) not a testimonial carousel.
- Schema: LegalService/Organization + FAQPage.

## F. Anti-patterns forbidden
Stock/AI hero photos · autoplay video bg · carousels/sliders · parallax-everywhere · blocking loaders (bridge OK) ·
>2 fonts · multiple/aggressive red CTAs · pop-ups / auto-open chat · third-party-widget-looking chat ·
"Ask me anything" blank chat · chat with no escalation + no citations · walls of text (>60 words) ·
>8 quiz questions / hard email-gate before value / deficit progress · drop-shadow fake depth / SaaS rounded cards /
purple gradients · sharp cramped boxes · stale/undated numbers.

## G. North stars
1. rocket.new "Counsel" editorial legal template — manifesto hero no image, parchment field, hairline, single accent,
   animated stats-wall, scroll-reveal not parallax, single CTA. Closest direct precedent. (Swap Fraunces→Cormorant, parchment→#f7f6f2.)
2. Thornfield Legal / Studio Slate — content architecture + performance-as-elegance (Lighthouse 100, two fonts, tiered cards, tagged news grid).
3. Fuselab chatbot guide + Arahi chat-embed — the regulated-context chat (capability transparency, inline source citations,
   calibrated uncertainty, human-escalation-first, native font-stack inheritance, never-auto-open).

## Rejected
- Personal-injury "aggressive multi-CTA / sticky-urgency" posture (walkeradvertising) — wrong audience; corporate
  sources explicitly contradict. Kept only its trust/speed/structured-content/accessibility points.
- Named firms in the prior (rate-limited) research pass (Sidley/Kirkland/Gibson Dunn/etc.) NOT found in Exa sources —
  patterns corroborated, names not citable. Use §G north stars instead.

**Approved direction mockup:** `~/Desktop/mythos-b2-preview/visa-redesign-{desktop,mobile}.png` (Antonello OK 2026-06-12).
