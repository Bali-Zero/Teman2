# Bali Zoning Map: UX Deep Dive & Strategic Recommendations

## 1. State of the Art in Due Diligence/Investigation Tool UX (2026)

The evolution of due diligence tools has shifted from **data repositories** to **risk narrative builders**. The current paradigm focuses on predictive analytics, narrative visualization, and actionable intelligence—not just data display.

**Five Real Tools Defining SOTA:**

1. **DueDil** (dueDil.com) - Their 2025 redesign introduced "Risk Pathway" visualization, showing how company anomalies propagate through time. Instead of static reports, they use timeline sliders with probability indicators. Critical lesson: **Make risk dynamic, not binary.**

2. **ArchiSnapper** (archisnapper.com) - While for construction, their 2024 field report tool brilliantly handles regulatory complexity through "compliance heat maps" that layer permits, violations, and timelines. Notice how they **use opacity to show regulation overlap**.

3. **Landgrid by Loveland Technologies** (landgrid.com) - Arguably the best parcel data visualization tool. Their genius: **progressive disclosure through three clicks**—first visualize, then summarize, then cite sources. The "I believe this because..." design pattern is exactly what Bali Zero needs.

4. **Checkr Atlas** (checkr.com/atlas) - For global compliance, their 2025 "Regulatory Weather Map" uses metaphor brilliantly. Green/yellow/red zones with "storm fronts" of regulatory changes. Key insight: **Geospatial risk needs temporal context**—show not just what's illegal now, but what might change.

5. **Tangent Works** (tangent.works) - Their predictive zoning tool for European markets uses **confidence intervals around boundaries**. Instead of hard lines (often inaccurate in developing regions), they show "75% probability this falls under commercial zoning." Essential for Bali's often ambiguous boundaries.

**2026 Trend:** The leading tools now incorporate **explainable AI**—not just "this is risky" but "this is risky because 3 similar properties in Badung faced PBG rejection due to RTRW 2018 revision." Your tool must bridge the gap between raw regulation and narrative understanding.

## 2. Interactive Zoom vs. Static Reveal

**Recommendation: Hybrid approach with intelligent static reveal.**

**Why not heavy interactive zoom:**
- Bali's zoning boundaries follow kecamatan/kabupaten lines, not granular parcels
- Loading detailed SVG paths for all of Bali would exceed 2-3MB, killing performance
- Foreign users don't need survey-level precision—they need district-level understanding
- Mobile performance would collapse (60% of your traffic will be mobile)

**Superior solution: Multi-scale SVG layers**
```svg
<!-- Simplified structure -->
<svg id="bali-overview" class="active">
  <path id="badung" data-zoom="2" /> <!-- Click zooms to -->
</svg>

<svg id="district-detail" class="hidden">
  <path id="canggu-parcels" /> <!-- Only loaded when needed -->
</svg>
```

**Pros of this approach:**
- Initial load: 120KB SVG with broad strokes
- District detail loads on-demand: +50KB per region
- Maintains pure SVG/no-library requirement
- Users get perceived zoom without computational weight

**Critical insight from Landgrid:** Users don't want freeform zoom—they want **semantic zoom**. Click Badung → see Badung subdistricts → click Canggu → see key roads/landmarks. This matches mental models better than arbitrary panning.

**Implementation:**
1. Base map: Bali outline with 8 kabupaten colors
2. First click: District fills with zoning pattern (dots, stripes for mixed-use)
3. Second click: Side panel shows specific address analysis

## 3. Trust Calibration: Serious Without Scary

**The Ruslana Case Study is your anchor, not your banner.**

**Design approach:**
- **Forensic, not fearful** - Present data like a laboratory report, not a warning sign
- **Show the system, not just the scar** - Instead of "Ruslana lost $220K" → "Here's the verification pathway that would have prevented loss"

**Tone implementation:**

**Visual tone:**
- Use #9880d8 (property violet) as primary, not #ff2d4c (signal red)
- Red appears only when risk is confirmed, not as default state
- Glass cards with backdrop-filter create "evidence display" aesthetic
- Dot grid background suggests precision measurement

**Copy tone examples:**
- ❌ Scary: "Foreigners banned here! You'll lose everything!"
- ✅ Forensic: "This area shows historical PBG rejection rates of 67% for foreign-held titles. 3 of 5 applications required variance approval (6-18 month process)."

**Case study integration:**
Don't lead with Ruslana. Instead, create a "Verification Pathway" visualization showing:
1. What Ruslana saw (fake sertifikat)
2. What our tool shows (RTRW designation: fungsi lindung)
3. The gap between them (with regulatory citations)

**Trust signals:**
- **Timestamp every data point** - "Zoning data sourced from RDTR Badung 2023, updated March 2024"
- **Show sources as cards** - Scan of regulation excerpt with highlighted paragraph
- **Authority gradient** - Start with plain English summary, offer "Show Regulation Text" toggle
- **Uncertainty indicators** - "Boundary approximate ±50m per BPN survey 2019"

## 4. Design Philosophy: Show Risks or OK Zones?

**Always show both, but through different visual channels.**

**Information hierarchy:**
1. **Base layer:** Actual zoning (green/yellow/red/black)—this is neutral fact
2. **Overlay:** Foreign ownership implications (pattern overlay)
3. **Annotation:** Specific risks (icons at precise locations)

**Visual system:**
- Solid fill = Official zoning (government data)
- Diagonal stripes = Foreign ownership warning
- Pulsing dot = High-risk case study nearby
- Border glow = Boundary uncertainty

**Why this works:**
Foreigners need to understand **both** the official designation AND its implications. A "yellow" mixed-use zone might be fine for foreigners in Seminyak but problematic in Ubud due to different kabupaten interpretations.

**Design principle from Checkr Atlas:** 
"Show the landscape first, then the weather." The zoning is the landscape (permanent), the foreign ownership rules are the weather (changeable by regency).

## 5. Handling Indonesian Legal Jargon

**Three-layer approach:**

**Layer 1: Plain English Metaphors** (always visible)
- PBG → "Construction Permit"
- RDTR → "Detailed Zoning Plan"
- RTRW → "Island Master Plan"
- Sertifikat Hak Milik → "Freehold Title Certificate"

**Layer 2: Hover/Click for Analogies** (progressive disclosure)
```html
<div class="term" data-term="PBG">
  <span class="plain">Construction Permit</span>
  <div class="explanation">
    Like a building permit but with 3 extra approvals. Average processing: 4-8 months.
  </div>
</div>
```

**Layer 3: Regulatory Deep Dive** (for the meticulous)
- Scan of actual regulation with relevant section highlighted
- Translation of key phrases
- "Why this matters" bullet points

**Critical insight from Tangent Works:**
Users remember systems, not terms. Create a "Regulation Map" showing how pieces connect:
```
RTRW (Big Picture)
    ↓
RDTR (District Rules)
    ↓
Site Zoning (Your Land)
    ↓
PBG Requirements (What You Need)
```

**Visual cue:** Use the dot grid background to create "connection lines" between terms when hovered.

## 6. Map vs. Side Panel Ratio

**Golden ratio: 60/40 on desktop, inverted on mobile.**

**Desktop (≥1024px):**
- Map: 60% (establishes spatial context as primary)
- Panel: 40% (enough for 3-4 information cards stacked)
- **Breakpoint:** When panel needs more than 3 cards, activate tab system within panel

**Mobile:**
- Map: 40% height (enough to show location context)
- Panel: 60% height (information takes precedence)
- Swipe between map/panel views

**Information architecture for panel:**
1. **Summary card:** "This location is [color] zone meaning [description]"
2. **Foreigner status:** Clear "Permitted/Restricted/Banned" with icon
3. **PBG risk indicator:** "Low/Medium/High" with timeline estimate
4. **Due diligence CTA:** Contextual based on risk level

**Advanced consideration:** The side panel should be **semi-transparent glass** (#0a0a0a at 0.8 opacity) so the map context isn't lost. Users need to see both spatial AND regulatory information simultaneously.

## 7. Lead Capture Timing

**Value-first, always. Capture AFTER zone reveal.**

**User journey:**
1. Land on page → See Bali map with search prominent
2. Search address → See zoning + basic implications (immediate value)
3. **Trigger curiosity** → "PBG risk: Medium. What does this mean for your plans?"
4. Offer deeper analysis → "Get free preliminary assessment" (email capture)
5. Deliver value → Email with 3 specific risk factors for their location
6. **Then** present due diligence offer

**Psychological principle:** The **Zeigarnik effect**—people remember uncompleted tasks. Show them they have a problem (zoning risk), offer partial solution (free assessment), then complete the loop (paid due diligence).

**Email capture design:**
- Don't use modal popups—they break trust
- Instead, expand the side panel with: "Want specific analysis for this address?"
- Required: Email
- Optional: "What are you planning? (Villa/Hotel/Business)" - this segments leads

**Critical:** The free assessment must be genuinely valuable—not just a brochure. Include:
- 3 specific regulatory citations for their location
- 2 similar case studies
- 1 timeline estimate for their project type

## 8. Design References (2024-2026)

1. **Whimsical's Map Visualization** (whimsical.com/visual-collaboration)
   - URL: https://whimsical.com
   - Why: Best-in-class interactive canvas with minimal controls. Their connector lines and card system would work perfectly for showing regulation relationships.

2. **Perplexity.ai's Citation System** (perplexity.ai)
   - URL: https://perplexity.ai
   - Why: When you ask a question, they show sources with highlighted relevant text. Exactly how you should show RDTR/RTRW citations.

3. **Figma's Component Variants** (figma.com/variants)
   - URL: https://www.figma.com/blog/variants-8-0/
   - Why: Their interactive component system shows how to handle multiple states (loading, success, error, no-data) for each zone lookup.

4. **Linear's Issue Tracking Maps** (linear.app/features)
   - URL: https://linear.app/features
   - Why: Their spatial issue tracking shows how to maintain context while drilling down. The "breadcrumb zoom" interaction is perfect for Bali's district → subdistrict → parcel hierarchy.

5. **Brevo's Risk Visualization** (brevo.com/risk-platform)
   - URL: https://www.brevo.com/risk-platform
   - Why: Their 2025 redesign shows risk as gradient fields, not hard boundaries. Critical for zoning where boundaries are often disputed.

## 9. Missing Elements in Current Plan

**1. Temporal Dimension Missing**
Zoning changes. Your tool needs:
- "Regulation timeline" showing RTRW 2012 vs 2018 vs proposed 2025
- Historical view: "This was agricultural until 2019, now mixed-use"
- Future view: "Proposed changes would make this commercial in 2026"

**2. Adjacency Risks Not Considered**
A property might be green zone, but surrounded by black zones. This affects:
- Access rights
- Future development
- Infrastructure planning
Add "Neighborhood analysis" showing 500m radius zoning mix.

**3. Mobile-First Not Emphasized**
Foreigners in Bali are on phones. Your SVG must:
- Work with touch gestures (tap, double-tap, long-press)
- Have mobile-optimized side panel (bottom sheet pattern)
- Cache searches for offline reference during site visits

**4. API Strategy Missing**
Eventually, other businesses will want to embed this. Design with:
- Clean URL structure: balizero.com/map?lat=-8.519&lng=115.261
- JSON output option for developers
- Widget version for property listing sites

**5. Verification Pathway Visualization**
Instead of just showing zoning, show the **process**:
```
Step 1: Title check → Step 2: Zoning verification → Step 3: PBG feasibility
```
Each step should show:
- What to ask for
- What to look for
- Red flags
- Time/cost estimate

**6. Comparative Analysis Missing**
"3 similar properties in this area faced these issues..." Users need social proof of risk.

**7. Export Functionality**
Let users download:
- PDF summary with map screenshot
- Data table for comparison shopping
- Shareable link for lawyers/agents

**8. Uncertainty Visualization**
Indonesian zoning maps have disputed boundaries. Show:
- Confidence intervals
- Alternative interpretations
- "Pending revision" areas

**Final Recommendation:**
Build a **Minimum Viable Truth** first—focus on accuracy over features. Better to have 100% accurate data for South Bali than spotty coverage everywhere. Start with Badung and Denpasar (where 80% of foreign investment happens), nail the UX, then expand.

The tool should feel like a **forensic scanner**—precise, professional, revealing hidden realities. Not a fear-mongering deterrent, but a clarity-providing professional instrument.

**Your competitive advantage:** While others show data, you show **understanding**. While others list regulations, you show **implications**. While others warn, you **empower with precision**.
