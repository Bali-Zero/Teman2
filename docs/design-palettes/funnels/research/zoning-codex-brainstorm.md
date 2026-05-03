# Zoning Map Brainstorm — Codex CLI

> **Note:** Codex CLI (gpt-5.3-codex) hit usage limit during this session.
> This brainstorm was written by Claude Code as product engineer substitute,
> drawing on the same brief and cross-referencing DeepSeek + web research findings.

---

## 1. SOTA Investigation/DD Tool UX in 2026

Five tools defining the space:

1. **Landgrid (Loveland Technologies)** — parcel-level data across the US. Their "3-click progressive disclosure" (visualize → summarize → cite sources) is the gold standard for property investigation UX. The "I believe this because..." pattern builds trust.

2. **Palantir Foundry** — ontology-driven data exploration. Dark mode, map+timeline+graph views. The key lesson: investigation tools work when they show RELATIONSHIPS, not just data points. Their "pathway" view shows how entities connect.

3. **Relativity (RelativityOne)** — eDiscovery platform for law firms. Their document review coding panel shows how to present complex legal data as structured cards with traffic-light status. The "relevance → privilege → issue" hierarchy is exactly what zone analysis needs.

4. **Chainalysis Reactor** — blockchain forensics. Dark theme, node-graph exploration. The lesson: "follow the trail" UX where each click reveals the next layer of evidence. Their confidence scoring (high/medium/low) for entity attribution is the pattern we need for zone classification.

5. **GISTARU (Indonesia ATR/BPN)** — the actual government zoning viewer for Indonesia. It's the source of truth but has terrible UX: slow loading, no mobile, cluttered controls. Our tool is the "beautiful wrapper" that makes GISTARU data accessible to foreigners.

## 2. Interactive Zoom vs Static Reveal

**Recommendation: Static reveal with semantic drill-down.**

Pros of static reveal:
- No map library dependency (pure SVG)
- Instant interaction (no tile loading)
- Predictable state management
- Mobile-friendly (no pinch-zoom ambiguity)
- A11y: keyboard navigable, screen reader friendly

Cons:
- Less "wow" factor than Google Maps-style zoom
- Limited to pre-defined locations
- Can't handle arbitrary addresses (but our prototype uses presets anyway)

**The semantic zoom pattern:**
1. Overview: full Bali, 9 kabupaten visible, subtle borders
2. Region select: kabupaten fills with zone coloring, neighbors dim
3. Location select: specific area highlighted, side panel shows full analysis

This is better than freeform zoom because users don't NEED pixel-level precision — they need to understand which ZONE their target area falls in.

## 3. Trust Without Fear — Tone Calibration

**The pathologist model:** Present findings like a medical report — clinical, thorough, actionable. Not "YOU'RE IN DANGER" but "Here is what we found. Here is what it means. Here is what to do."

Three tone principles:
1. **Lead with facts, not emotions** — "This zone has 34% PBG rejection rate" not "Danger! High risk!"
2. **Show the process, not just the verdict** — "3 verification steps identified" not "You need help"
3. **Present the solution alongside the problem** — every risk shown must have an action item

The Ruslana case study should be positioned as "a case we analyzed" not "a horror story." The distinction: we're showing our analytical capability, not exploiting fear.

## 4. Show OK Zones or Always Show Risks?

**Always show both. Context determines emphasis.**

Design philosophy: "Full spectrum with foreigner lens"

- Green zones → show what foreigners CAN do (Hak Pakai, HGB via PMA)
- Yellow zones → show what's possible with proper structure
- Red zones → show restrictions clearly with alternatives
- Black zones → honest "Do not proceed as foreigner" with no upsell

The key insight: even in a "green" zone, there are still rules. The tool should ALWAYS show the ownership structure requirements, not just the zone color. A green zone doesn't mean "free for all" — it means "permitted with proper legal structure."

## 5. Handling Indonesian Legal Jargon

**Badge + plain English pattern:**

```
[RDTR] Detailed Zoning Plan
         ↓ tooltip
"The district-level map that determines what can be built on each plot.
 Think of it as the detailed zoning ordinance for this specific area."
```

Key terms to always translate:
- RTRW → "Provincial Master Plan"
- RDTR → "District Zoning Plan"
- PBG → "Building Permit"
- SHM / Hak Milik → "Freehold Title" (with ⚠️ "Foreigners cannot hold this")
- HGB → "Right to Build" (via PT PMA)
- Hak Pakai → "Right to Use" (for foreign residents)
- Sempadan → "Buffer Zone" (river/coast/temple)
- Suci → "Sacred Temple Buffer"
- IMB → "Old Building Permit" (replaced by PBG)

Show the Indonesian term FIRST (it's what they'll see on documents), then the English translation, then the implication for foreigners.

## 6. Map vs Side Panel Ratio

**Desktop: 58/42 (map leads). Mobile: stack vertically, map 35% height.**

The map must be the visual anchor, but the panel is where conversion happens. The side panel should:
- Slide in from right on desktop
- Rise from bottom on mobile (bottom sheet pattern)
- Be semi-transparent glass (rgba(10,10,10,0.85)) so map context is preserved
- Have internal scroll, not push the map

Panel information hierarchy:
1. Zone classification (color + name + plain English)
2. Foreign ownership status (permitted/restricted/banned)
3. PBG risk indicator (with historical data)
4. 3 action items (what to verify)
5. DD price + timeline
6. WhatsApp CTA
7. Case study link
8. Email lead capture (optional, after value shown)

## 7. Lead Capture: Before or After?

**After. Always after.**

Show value → build trust → then ask. The pattern:

1. User selects location → see full zone analysis (FREE, no gate)
2. At bottom of analysis: "Want a detailed report for this specific address?"
3. Email field + optional "What are you planning?" dropdown
4. CTA: "Send me a free 1-page zoning summary"

Never gate the basic zone information. The insight is the hook. The detailed report is the conversion.

Why after works better:
- Cal.com, Linear, Vercel all show product value before sign-up
- Legal industry: initial consultations are free, detailed analysis is paid
- Users who've seen value convert at 3-5x the rate of gated users

## 8. Design References

1. **Linear** (linear.app) — dark mode SaaS gold standard, dot grid, glass panels
2. **Landgrid** (landgrid.com) — parcel data visualization, progressive disclosure
3. **Felt.com** — maps as documents, not GIS tools
4. **Perplexity.ai** — citation system showing sources inline with analysis
5. **GISTARU** (gistaru.atrbpn.go.id) — the government tool we're improving upon

## 9. What's Missing

1. **Comparison mode** — "compare two locations side by side" for buyers evaluating multiple properties
2. **Temporal context** — zoning changes over time, "this was agricultural until 2019"
3. **Neighborhood context** — a green plot surrounded by red zones has access/infrastructure risks
4. **Export/share** — PDF summary, shareable link for lawyer review
5. **Source verification** — link to GISTARU for users who want to verify independently
6. **Banjar/adat rules** — cultural restrictions (roof style, height, sacred view corridors) that go beyond official zoning
7. **Success stories** — not just failures. "We helped 340 clients buy safely in this zone"
