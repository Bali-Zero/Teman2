Both GOOGLE_API_KEY and GEMINI_API_KEY are set. Using GOOGLE_API_KEY.
Of course. As a specialist in this domain, I can provide a detailed strategic analysis for your Bali Zoning Map tool. This is a critical project, as the financial and emotional stakes for your clients are immense. The Ruslana case is a powerful anchor; we must build a tool that honors that reality by providing unparalleled clarity and trust.

Here is a comprehensive breakdown answering your questions, grounded in state-of-the-art UX principles for 2026.

***

### **1. State-of-the-Art (SOTA) in Investigation & Due Diligence UX (2026)**

The SOTA in investigative UX for 2026 has moved beyond simple dashboards. It's about **data fusion**, **narrative visualization**, and **proactive insight generation**. The best tools don't just present data; they reveal relationships, quantify risk, and suggest next steps. They turn overwhelming complexity into a clear, actionable story.

Here are five real-world examples that define the cutting edge:

1.  **Sayari Graph ([sayari.com](https://sayari.com/))**
    *   **What it is:** A tool for investigating corporate ownership, supply chains, and financial crime. It aggregates data from global public records.
    *   **SOTA UX Principles:**
        *   **Graph-Based Visualization:** Its core is not a table or a list, but a node-graph. It visually maps relationships between people, companies, and assets. For your tool, this is a post-DD product, but the *principle* is key: showing how a developer, a plot of land, and a specific permit are connected.
        *   **Data Provenance:** Every piece of information is clickable and traces back to its source document (e.g., a corporate registry filing). This builds immense trust. Your tool **must** cite the specific `RTRW` or `RDTR` document its data comes from for every query.
        *   **Pathfinding:** Sayari can find hidden connections between two entities that seem unrelated. Imagine a future version of your tool showing that the developer of a villa project in Canggu has a history of permit issues on another project in Uluwatu.

2.  **Chainalysis Storyline ([chainalysis.com](https://www.chainalysis.com/))**
    *   **What it is:** A cryptocurrency investigation tool that de-anonymizes transactions and visualizes the flow of funds.
    *   **SOTA UX Principles:**
        *   **Narrative Flow:** Storyline automatically visualizes complex transaction histories as a clean, chronological "story" rather than a messy graph. It simplifies the unintelligible.
        *   **Smart Labeling:** It automatically labels addresses associated with illicit activity (scams, darknet markets). This is directly applicable. Your tool should use clear, unambiguous labels: `⛔️ BLACK ZONE (Foreigner Ban)`, `⚠️ HIGH-RISK (PMA Required, Ownership Caps)`.
        *   **Focus on the Transaction:** It highlights the most important transactions and collapses the noise. Your tool should do the same: focus the user on the most critical risk factor for *their specific location* first, then allow them to explore secondary details.

3.  **Palantir Gotham ([palantir.com/platforms/gotham/](https://www.palantir.com/platforms/gotham/))**
    *   **What it is:** The archetypal intelligence and data fusion platform used by defense and financial institutions.
    *   **SOTA UX Principles:**
        *   **Geospatial-Temporal Fusion:** Gotham excels at placing data on both a map and a timeline simultaneously. For your tool, this means not just showing the *current* zone, but allowing a user to scrub a timeline to see if that zone has changed recently (e.g., "This was a Green Zone until 2024"). This is a huge value-add.
        *   **Object-Oriented Search:** Users don't just search for "text". They search for objects like `Person`, `Location`, `Event`. Your search should be structured: is the user searching for an `Address`, a `Developer Name`, or a `Land Certificate ID (NIB)`?
        *   **Collaborative Analysis:** It allows multiple analysts to work on the same investigation. A future feature for Bali Zero could be a shared "case file" where a client and your consultant can both view the map data and add notes.

4.  **LlamaRisk ([risk.llamalend.com](https://risk.llamalend.com/))**
    *   **What it is:** A dashboard that provides a clear, at-a-glance risk assessment for assets within the DeFi lending protocol LlamaLend.
    *   **SOTA UX Principles:**
        *   **Quantified Risk:** It doesn't just say "risky"; it provides a clear score and color code (e.g., "Liquidation Risk: 85%"). Your tool should do the same for PBG permit risk or ownership complications. "PBG Permit Success Likelihood: **Low (3/10)**".
        *   **Extreme Simplicity:** Despite the complexity underneath, the UI is radically simple. It’s a list with color codes. This proves that you don't need a visually complex interface to convey complex risk. The side panel is the hero.
        *   **Action-Oriented:** Every risk assessment is paired with an action the user can take. For you, the primary action is "Order Full Due Diligence."

5.  **Windy.com ([windy.com](https://www.windy.com/))**
    *   **What it is:** A professional weather forecasting tool that visualizes vast amounts of meteorological data on an interactive map.
    *   **SOTA UX Principles:**
        *   **Mastery of Layers:** Windy’s genius is its layer-switching sidebar. Users can fluidly toggle between wind, rain, waves, and air quality overlays. Your tool should adopt this for geospatial context. Let users toggle overlays for `Planned Roads`, `Sacred Sites (Pura)`, `Flood Plains`, `Public Infrastructure`. This provides context that is more valuable than the zoning data alone.
        *   **Precise Point-Based Queries:** The "click anywhere" interaction model is flawless. Clicking any point on the map provides a detailed forecast for that exact coordinate. This is the exact interaction you need. The user should feel confident they can click a single rice paddy and get the specific zoning for it.

### **2. Map Interaction: Interactive Zoom vs. Static Reveal**

Given your constraint of "Pure SVG inline map, no JS libraries, no map libs," a full, deep, Google-Maps-style interactive zoom is not feasible and would perform poorly. A purely static map would feel too simplistic.

**Recommendation: A Hybrid "Staged Zoom" Approach.**

This approach balances performance, user experience, and your technical constraints.

1.  **Level 1 (Island View):** The initial view is a static SVG of the entire island of Bali. The main regencies (Badung, Gianyar, Denpasar, etc.) are clearly delineated and are interactive elements (`<path>`). The ocean area is transparent, showing the dot grid background.
2.  **Interaction 1 (Click Regency):** User clicks on "Badung." The entire map smoothly scales up and centers on the Badung regency using CSS transforms (`transform: scale() translate()`). This *feels* like zooming but is extremely lightweight.
3.  **Level 2 (Regency View):** The user now sees a more detailed SVG of just the Badung regency. Here, the sub-districts (Kecamatan) or even villages (Desa) are the interactive elements.
4.  **Interaction 2 (Click Sub-District):** User clicks on "Kuta Utara." The path highlights with a glow border (per your design system), and the side panel populates with the detailed zoning information for that area.
5.  **The Power Feature (Search):** The primary interaction for motivated users will be the search bar. When a user searches for "Jalan Pantai Batu Bolong 99," your geocoder finds the coordinate, and the map directly animates to the correct Regency view, highlighting the specific zone and dropping a pin, while the side panel shows the precise data.

**Pros of this Hybrid Approach:**

*   **Performant:** Avoids heavy JS libraries and complex SVG manipulation. Leverages fast, hardware-accelerated CSS transforms.
*   **Guided UX:** It guides the user through a logical geographic hierarchy, which is helpful for those unfamiliar with Bali's geography.
*   **Feels Interactive:** The animated transitions provide the *feeling* of a dynamic interface without the technical overhead.
*   **Scalable:** You can add more granular SVG maps for specific high-interest areas (e.g., the Pererenan-Canggu coastline) over time.

**Cons:**

*   **Not True Zoom:** Users cannot perform a fluid "pinch-to-zoom." This is an acceptable trade-off to meet your "no map libs" constraint.
*   **Requires Multiple SVGs:** You will need to prepare and optimize a separate SVG file for each regency.

### **3. Tone Calibration: Conveying Trust Without Fear**

Your goal is to be an **authoritative expert**, not an alarmist. The tone should be calm, factual, and empowering. Ruslana's story is the "why," and your tool is the "how to prevent it."

**Tone Principles:**

*   **Factual & Referenced:** Always ground your warnings in data.
    *   *Instead of:* "This is a very dangerous zone for foreigners!"
    *   *Use:* "This area is designated **Tourism Accommodation (AK)**. Note: While foreign investment is possible, it is subject to a 67% ownership cap under a PT PMA company. Source: `BKPM Regulation 4/2021`."
*   **Empower, Don't Frighten:** The user should feel smarter and more in control after using the tool, not terrified.
    *   *Instead of:* "You're at risk of losing everything!"
    *   *Use:* "Understanding these zoning restrictions is the first step to securing your investment. We can help you navigate the correct legal structure for this zone."
*   **Use a "Risk Spectrum," Not a Binary "Safe/Unsafe":**
    *   **Green Zone (Residential):** "✅ **Low Risk.** Designated for residential use. PBG permits are generally straightforward for compliant structures. We still recommend verifying the specific land certificate (Sertifikat) status."
    *   **Yellow Zone (Mixed):** "⚠️ **Moderate Risk.** This zone allows for a mix of uses, but specific conditions apply. Permit applications require careful justification. A full DD is highly recommended."
    *   **Red Zone (Restricted):** "❌ **High Risk.** Foreign ownership and development are heavily restricted. Proceed with extreme caution and professional legal guidance."
    *   **Black Zone (Banned):** "⛔️ **Do Not Invest.** This is a conservation area (e.g., Green Belt / Jalur Hijau) where all new construction is prohibited. Any offer to sell this land for development is illegal."
*   **Handle the Case Study Delicately:**
    *   In the side panel for a red/black zone, include a small, discreet link:
        > "⚠️ **Real-World Risk:** Investments in similarly restricted zones have led to significant financial loss. *See the XO Pandawa case study.*"
    *   This makes the threat concrete but optional, allowing the user to opt-in to the "scary" story rather than being confronted by it.

### **4. Design Philosophy: Always Show the Risk**

You must adopt the philosophy of **"Trust, but Always Verify."** Never, ever display a zone as "100% Safe." Doing so would be a disservice to your clients and a massive liability for your business. The entire premise of due diligence is that risk is always present, it just varies in degree.

**Why this is the only correct approach:**

1.  **Reinforces Your Value:** If the tool shows a bunch of "perfectly safe" green zones, it devalues your core service. The user might think, "Great, it's green, I don't need to pay for a DD report." By showing the *nuance* of risk in *every* zone, you demonstrate that expert interpretation is always required.
2.  **Builds Real Trust:** Sophisticated clients know there's no such thing as a risk-free investment in Indonesia. Showing them the subtle risks (e.g., "village road access requires a contribution fee," "nearby temple proximity may restrict building height") proves you are a true expert, not a superficial salesperson.
3.  **Reduces Liability:** You are providing information, not a guarantee. The interface must make it clear that this is a powerful but preliminary tool, and the full USD 850 report is the definitive, legally actionable analysis.

Your UI should reflect this. Even in a Green Zone, the side panel should have a "Potential Considerations" section that lists the less-obvious risks to be checked in a full DD.

### **5. Handling Indonesian Legal Jargon**

This is critical for user comprehension. Use a **"Simple Term First, Jargon as Proof"** method.

**Implementation:**

1.  **Primary Display:** Use plain, intuitive English.
    *   "Official Zoning Plan"
    *   "Building Permit"
    *   "Land Title"
2.  **Secondary Display (for authenticity):** Place the Indonesian term in a monospace font next to the simple term.
    *   `Official Zoning Plan (RTRW)`
    *   `Building Permit (PBG)`
    *   `Land Title (Sertifikat)`
3.  **Tooltip Glossary:** Attach a small `(i)` icon to each term. On hover/click, a beautifully designed tooltip (following your glass/glow aesthetic) appears with a simple explanation.

**Example Tooltip Content:**

> **Official Zoning Plan (RTRW/RDTR)**
>
> This is the master plan created by the regional government that dictates the legal use for every plot of land. `RTRW` is the high-level regional plan, while `RDTR` is the more detailed local plan. Building outside the designated zone is illegal.

> **Building Permit (PBG)**
>
> This is the government's approval to construct a building. It replaced the old `IMB`. A PBG will only be issued if your building design and its intended use comply with the official Zoning Plan.

> **Land Title (Sertifikat Hak Milik - SHM)**
>
> This is a "Freehold" title, the strongest form of land right in Indonesia. **Crucially, SHM titles can only be legally held by Indonesian citizens.** Any scheme offering direct SHM ownership to a foreigner, often through nominees, carries extreme risk.

This approach makes the tool instantly understandable to a novice, while also providing the correct terminology for them to use when speaking with agents, notaries, or your own team.

### **6. Map vs. Side Panel Ratio**

Your intuition is correct; the value is in the details.

**Recommendation: 40% Map / 60% Side Panel on Desktop.**

*   **The Map is the `WHERE`:** Its job is to provide spatial orientation and be the selection interface. It's the query builder.
*   **The Panel is the `WHAT` and `SO WHAT`:** This is where the core value is delivered. It contains the zoning data, the risk analysis, the explanations, and the all-important Call-To-Action. Users will spend 80% of their time reading this panel.

On **mobile**, this becomes a stacked or tabbed interface. The default view could be the map. Upon tapping a zone or executing a search, a **bottom sheet** slides up, occupying 70-80% of the screen. This sheet would contain the same rich information as the desktop side panel and could be expanded to full screen if needed.

The 40/60 desktop ratio gives you ample real estate to design a truly informative and visually rich panel with your glass card system, typography, and glow effects, reinforcing the premium nature of your service.

### **7. Lead Capture: AFTER Showing Value**

**Unquestionably capture the lead AFTER showing the initial result.** Gating this tool would be a fatal mistake.

**The "Value First" Funnel:**

1.  **User lands on the page.** The interface is clean, beautiful, and immediately presents the map and a single, clear instruction: "Enter an address or click the map to see its official zoning."
2.  **User enters an address.**
3.  **INSTANTLY,** the side panel populates with the **free, high-level results:** Zone Color, Zone Name, and a primary risk summary. This is the "Aha!" moment where you prove your competence. The user gets an immediate dopamine hit of valuable information.
4.  **The information is valuable but incomplete.** It creates more questions than it answers: "Okay, it's a Yellow Zone, but what does that *really* mean for my guesthouse plan? What is 'moderate' PBG risk?"
5.  **The CTA becomes the logical next step.** Now that the user has a tangible, personal reason to be concerned, the button "Order Full Due Diligence Report for this Property (USD 850)" feels like the solution to their newfound problem. A secondary, softer CTA like "Request a Free Consultation" can capture leads who aren't ready for the full purchase.

Gating the tool would communicate a lack of confidence. Providing value first communicates expertise and abundance. It says, "We have so much valuable data that we can give this part away for free, because we know you'll need our help to understand the rest."

### **8. Design References (2024-2026)**

Here are five sites that embody the aesthetic and functional principles you should aim for:

1.  **Vercel ([vercel.com](https://vercel.com/))**: The gold standard for a dark, clean, and powerful developer-focused aesthetic. Note the use of subtle gradients, sharp typography, and glow effects. It feels precise and high-tech. This is your core visual reference.
2.  **Linear ([linear.app](https://linear.app/))**: A masterclass in information density and functional minimalism. Study their use of keyboard shortcuts, command menus (`Cmd+K`), and how they present complex data without any clutter. Their UI feels incredibly fast and efficient.
3.  **Arc Browser ([arc.net](https://arc.net/))**: While a browser, its website and branding are SOTA. It shows how to be playful and human while still being a serious, powerful tool. The use of color and animation is top-tier.
4.  **Mistral AI ([mistral.ai](https://mistral.ai/))**: Excellent example of a confident, minimalist, dark-themed site. Their "Le Chat" product interface is a great reference for a clean input/output interaction, which is similar to your search/results panel.
5.  **Oura Ring ([ouraring.com](https://ouraring.com/))**: Look at their mobile app and web dashboard. It’s a perfect example of taking complex biometric data and turning it into simple, actionable scores (Sleep Score, Readiness Score). This is exactly what you need to do with complex legal/zoning data.

### **9. What's Missing in the Current Plan?**

Your plan is strong, but to make it truly world-class, consider these additions:

1.  **A Robust Geocoding & Address Strategy:** You mention "type an address." This is notoriously difficult in Bali.
    *   You need a powerful geocoding engine (like Google Maps API, but monitor costs).
    *   You absolutely need a fallback: **"Can't find your address? Drop a pin on the map."**
    *   Integrate **[what3words](https://what3words.com/)**. It's widely used in places with poor street addressing and would be a huge UX win. Many people in Bali use it to share locations.
2.  **Historical Zoning Data:** This is a killer feature. Don't just show the *current* zone. If possible, show its history. A simple text line would be immensely powerful: "Note: This area was re-zoned from `Agriculture (ITR Pertanian)` to `Residential (ITR Perumahan)` in late 2023. Recent re-zones often face extra scrutiny." This is expert-level insight that no competitor will have.
3.  **Search by `NIB` (Nomor Induk Bidang):** For serious investors, agents, and notaries, the ultimate query is not an address but the official land plot registration number (`NIB`). Adding a search toggle to allow for `NIB` searches would make this a true "pro" tool and an industry standard overnight.
4.  **Client-Side PDF Summary:** After a user performs a search, present a button: "Download Free PDF Summary." This captures their email (a fair trade) and gives them a branded, one-page PDF with the map screenshot, the basic findings, and a very prominent ad for your full DD service. This PDF will get shared, becoming a marketing asset for you.
5.  **Contextual Overlays:** As mentioned with Windy.com, giving users the ability to toggle contextual data layers would be a massive advantage. Start with one or two high-value layers:
    *   `Planned Infrastructure`: Show where the new Gilimanuk-Mengwi toll road is planned.
    *   `Pura Restriction Zones`: Visualize the setback requirements from major temples.

By incorporating these elements, you will elevate the Bali Zoning Map from a simple utility to an indispensable part of the property investment lifecycle in Bali, cementing Bali Zero as the undisputed technology-driven authority in the market.
