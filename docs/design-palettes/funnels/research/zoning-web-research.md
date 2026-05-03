# Bali Zoning Map — Web Research Findings

> Date: 2026-04-12
> Sources: Brave Search, property law sites, Reddit, design platforms
> Purpose: Ground truth for the zoning map tool design decisions

---

## 1. Mapbox Studio Dark Dashboard UX

**Key findings:**
- Mapbox Studio uses a dark-v10 base (`#0a0a0a`-range) with desaturated map features — roads, water, land all rendered in grey tones with selective color highlights
- Controls placement: left sidebar for layers/styles (collapsible), map fills remaining space, floating toolbar top-center
- "Components" system hides complexity: simple toggles for common styling, "overrides" for power users — progressive disclosure pattern
- HD roads import lets users customize color + emissive strength for dark mode — single control point, not per-feature
- Key UX pattern: the map is ALWAYS the hero; controls are glass-overlaid, never competing

**Design implications for our tool:**
- Map should dominate 60-65% of width; side panel is secondary
- Controls should feel like overlays ON the map, not beside it
- Progressive disclosure: show zone summary first, expand for legal detail
- Desaturated default state → color only on selected/active regions

**Sources:**
- https://www.mapbox.com/mapbox-studio
- https://www.mapbox.com/blog/standard-style-updates-more-customization-options-to-personalize-the-map
- https://docs.mapbox.com/studio-manual/reference/styles/

---

## 2. Felt.com Collaborative Map Design

**Key findings:**
- Felt's core innovation: making maps feel like documents, not GIS tools
- "Hides complexity behind intuitive design" — their exact positioning
- Recently added custom basemaps including "Mapbox Monochrome dark" — dark mode is first-class
- Cloud-native: real-time collaboration, single-click sharing, embed support
- Data visualization layered ON maps, not replacing them — tooltips, callouts, annotations feel like editorial notes

**Design implications for our tool:**
- The zoning map should feel like a DOCUMENT you read, not a tool you operate
- Annotations/callouts for legal warnings should feel editorial (like margin notes)
- Side panel info should read like a brief/memo, not a form
- Single interaction to get value: click region → instant answer

**Sources:**
- https://www.felt.com/blog/map-backgrounds-and-styling-controls
- https://felt.com/platform/web-gis
- https://help.felt.com/getting-started/tour-the-interface

---

## 3. Legal Tech Investigation Tools UX

**Key findings from 2025-2026 dashboard trends:**
- Glassmorphism is the dominant pattern for complex data dashboards (Muzli 2026 roundup)
- AI agent monitoring dashboards use: compliance pulses, token tracking, workflow status in glass cards
- Context-aware personalization: time-of-day, user habits, role-based views
- Dark mode is now "not a trend but a user-centric requirement" (EncodeDots)
- Key pattern: contrast hierarchy for CTAs — dark bg makes action buttons pop
- Frosted glass + inner light leak = premium SaaS signal

**Real tools in the investigation/DD space:**
1. **Palantir Foundry** — ontology-driven data exploration, dark mode, map+timeline+graph views
2. **Chainalysis Reactor** — blockchain investigation, dark theme, node-graph + timeline
3. **Thomson Reuters Clear** — background check/investigation, structured report cards
4. **Relativity (RelativityOne)** — eDiscovery, document review with AI coding
5. **Lexis+ AI** — legal research with AI-generated briefs, citation verification

**Design implications:**
- Our tool should use structured "report cards" like Thomson Reuters Clear
- The investigation feel comes from: monospace fonts for data, structured grids, traffic-light status indicators
- NOT from: neon glows, cyber aesthetic, complex node graphs
- Trust = clean typography + structured data + cited sources

**Sources:**
- https://muz.li/blog/best-dashboard-design-examples-inspirations-for-2026/
- https://muz.li/inspiration/dark-mode/
- https://www.tech-rz.com/blog/dark-mode-design-best-practices-in-2026/

---

## 4. Bali Property Scams — Foreigner Stories

**Key findings:**
- **~10,500 properties in Bali held through nominee structures** representing ~$10.4 billion in at-risk assets (investlandbali.com)
- Common scam pattern: "freehold" sold to foreigner via Indonesian nominee → foreigner has ZERO legal recourse if nominee disappears
- Reddit thread (r/expats): "Found out the hard way that foreigners can't actually get the main Bali villa license everyone talks about" — emotional, high engagement
- "Fake influencers who travelled there to take a bunch of pictures of themselves in Bali, and then pretended to own a villa there on some BS story they put together with ChatGPT"
- Nominee arrangements are explicitly **illegal under Indonesian law and legally unenforceable**
- Red flags: anyone telling you foreigners can hold Hak Milik = scam

**Emotional triggers to use in our tool:**
- Fear of total loss (USD 200K+ at stake)
- Social proof of scams being COMMON, not rare
- The nominee's legal power over YOUR money
- PBG rejection = building you can't use, can't sell
- The "everyone does it" myth debunked

**Design implications:**
- The Hak Milik warning must be the FIRST thing shown — not buried
- Use the $10.4B figure to establish scale
- Case study (Ruslana) adds human face to abstract risk
- Tone: protective ally, not fear-mongering — "We check so you don't get burned"

**Sources:**
- https://investlandbali.com/bali-property-for-foreigners/
- https://www.villabalisale.com/blog/avoid-property-scams-in-bali
- https://www.wearesynergypro.com/news/exposing-the-1-legal-mistake-that-could-cost-you-everything
- https://www.reddit.com/r/expats/comments/1rakwvj/found_out_the_hard_way_that_foreigners_cant/
- https://ilaglobalconsulting.com/property-construction-scams-bali/

---

## 5. Indonesia Foreign Land Ownership Rules

**Key findings (confirmed 2025-2026):**

| Title | Who can hold | Duration | Foreign access |
|-------|-------------|----------|----------------|
| **Hak Milik** (Freehold) | Indonesian citizens ONLY | Perpetual | ❌ NEVER for foreigners |
| **Hak Pakai** (Right to Use) | Foreigners with residency | 30yr + 20yr extension + 30yr renewal = 80yr | ✅ For residential |
| **HGB** (Right to Build) | PT PMA (foreign company) | 30yr + 20yr + 30yr = 80yr | ✅ Via PT PMA |
| **Hak Sewa** (Leasehold) | Anyone | 25-99yr negotiable | ✅ Simplest option |
| **Hak Guna Usaha** (Right to Exploit) | PT PMA | 35yr + 25yr | ✅ For agriculture/plantation |

**Critical rules:**
- PT PMA can purchase Hak Milik land → must be **converted to HGB** in company name
- Foreigners CAN own apartment units under Strata Title IF building is on HGB/Hak Pakai land AND foreigner has valid residence permit
- Nominee = illegal. Zero legal protection. The nominee IS the legal owner.
- When foreigner sells HGB to Indonesian, can be converted back to Hak Milik

**Design implications for our tool:**
- Show the ownership ladder visually: Hak Milik (banned) → HGB via PMA (safe) → Hak Pakai (residential) → Leasehold (simplest)
- Always show the LEGAL path first, then the scam path with warning
- "What can you actually do here?" is the key question per zone

**Sources:**
- https://business-indonesia.org/property_land_rights
- https://rumavi.com/en/property-guides/pt-pma-setup-guide-for-indonesia-property-villa-rentals-2026
- https://www.villabalisale.com/blog/can-foreigners-own-land-bali-legal
- https://sumbasunsetcliff.com/post/foreign-ownership-indonesia-land-guide

---

## 6. Bali RDTR Zoning Maps

**Key findings:**
- **GISTARU** (gistaru.atrbpn.go.id) = national geospatial zoning viewer, parcel-level detail
- **BATARA** = Badung-specific zoning portal + mobile app (Badung Tata Ruang)
- Provincial spatial plan: **Peraturan Daerah No. 2/2023** (provincial), refined by district RDTR
- **Perbup Badung No. 28/2023** = RDTR for WP Petang 2023-2043 (example)
- Since 2025, RDTR is integrated with **OSS (Online Single Submission)** system
- **"80% of Canggu villas fail" zoning compliance** (balipropertyscout.com headline — aggressive but directional)
- **Prov. Reg. No. 4/2026** = new law on Protection of Productive Land — limits conversion

**Zone categories confirmed:**
- Pink/Magenta = Perumahan (Residential)
- Yellow = Perdagangan & Jasa (Commercial/Mixed)
- Green = Pertanian (Agriculture)
- Dark Green = Hutan/Lindung (Protected/Forest)
- Orange = Pariwisata (Tourism)
- Blue = Perikanan/Laut (Maritime)
- Hatched = Sempadan (Buffer: river, coast, temple)

**Design implications:**
- Use official color mapping but translate to our dark palette
- Link to GISTARU as "verify yourself" trust builder
- "80% fail" stat is powerful for urgency (if citable)
- Zone viewer should feel like a simplified GISTARU, not replacement

**Sources:**
- https://balipropertyrules.com/guides/bali-zoning-foreigners/
- https://baliexception.com/info/land-zone-in-bali-indonesia-explained/
- https://www.balipropertyscout.com/blog/bali-property-zoning-guide
- https://bali-home-immo.com/blog/bali-2026-zoning-laws-explained
- https://megabalirealty.com/land-zoning-in-bali/

---

## 7. PBG Building Permits — Bali Reality

**Key findings:**
- PBG (Persetujuan Bangunan Gedung) replaced old IMB system
- **Cost: IDR 10M - 100M+ (€600-€6,000)** depending on project complexity
- **Common rejection causes:**
  1. Land zoning mismatch (building residential on agricultural)
  2. Setback violations (too close to river/coast/temple buffer)
  3. Cultural violations — flat roofs rejected, must be traditional linmas (pyramid) style
  4. Height exceeding 15m limit in many areas
  5. Shadows on sacred sites (temple buffer = Suci zone)
- **SIMBG** (Sistem Informasi Manajemen Bangunan Gedung) = online application system
- "Early dialogue with community leaders (banjar) is now essential" — adat/custom rules are STRICTER than national
- Bingin demolition (July 2025) = government demolished buildings in coastal buffer zone

**Key stat:** Designs that "look fine on paper can still offend if it blocks views or shadows a sacred site"

**Design implications:**
- PBG risk should be zone-dependent, not generic
- Cultural rules (roof style, banjar approval) are the hidden killer — mention them
- Bingin demolition = real enforcement case study to cite
- Show PBG as a PROCESS risk, not just a yes/no

**Sources:**
- https://balivisa.co/staying-compliant-with-new-bali-imb-building-permit-rules-2026/
- https://emasestate.com/everything-you-need-to-know-about-building-permits-in-bali/
- https://prestigepropertybali.com/blog/the-investors-ultimate-guide-to-pbg-slf-building-legally-in-bali
- https://www.mrfixitbali.com/building-construction/licences-permits-and-zoning/PBG-SLF-new-building-approvals.html

---

## 8. Pitch.com Minimalism & Dark Design References

**Key findings from dashboard design trends:**
- Pitch.com uses extreme whitespace, large sans-serif type, minimal chrome
- Dark mode SaaS pattern 2026: `#0a0a0a` base → `#141414` surface → `#1f1f1f` elevated
- Signal color used sparingly — ONE accent, rest is grey hierarchy
- Typography-driven: large display type for headlines, tight leading, Inter/SF Pro
- Cards have minimal borders — depth conveyed by shadow + backdrop-filter, not outlines

**Additional design references (from Muzli 2026 + research):**
1. **Linear** (linear.app) — the gold standard for dark-mode SaaS. Dot grid, glass panels, scroll-driven reveals
2. **Raycast** (raycast.com) — command-palette-first, extreme dark, subtle dot grid
3. **Vercel** (vercel.com/dashboard) — deployment dashboard, dark, hover-lift cards
4. **Cal.com** — scheduling, dark mode, mouse-aware glow borders on pricing
5. **Supabase** (supabase.com) — database dashboard, dark, glow borders, glass cards

**Design implications:**
- Our tool must follow the Linear/Vercel pattern: dark base, glass cards, minimal chrome
- Typography hierarchy does 80% of the work — not decorative effects
- The map itself should feel like part of the dark surface, not floating above it
- Frosted glass side panel = the Palette D way

**Sources:**
- https://linear.app
- https://raycast.com
- https://vercel.com
- https://pitch.com
- https://muz.li/blog/best-dashboard-design-examples-inspirations-for-2026/

---

## Synthesis — Cross-cutting Design Principles

1. **Progressive disclosure**: zone summary → ownership rules → PBG risk → DD CTA
2. **Trust through structure**: monospace for data, clear hierarchy, cited sources
3. **Fear without panic**: show the risk, show the path forward, show the price
4. **Map as document**: annotations, not dashboards; briefs, not forms
5. **Dark mode done right**: `#0a0a0a` base, glass cards, ONE accent color (red for danger, violet for property category)
6. **Lead capture AFTER value**: show zone → then ask for email — proven by Cal.com / Linear freemium patterns
7. **Indonesian jargon as badges**: show Indonesian term (RDTR, PBG, Hak Milik) as labeled badge with plain-English translation tooltip
8. **Case study as social proof**: Ruslana story = "we caught this for a real client" — not marketing, but evidence
