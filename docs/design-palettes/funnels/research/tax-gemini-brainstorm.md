As a Senior Product Designer and UX Researcher, here is my unvarnished, opinionated take on designing the Bali Zero Tax Compliance Calendar. 

You are designing for a high-anxiety context. Expats in Indonesia are terrified of arbitrary enforcement, language barriers, and sudden fines. If you design this like a standard government portal or a generic calendar, you will trigger their anxiety. Instead, we must design a **"Guardian UI"**—an interface that feels so hyper-competent, calm, and automated that the user instantly thinks, *"Thank God, I can just pay them to deal with this."*

Here are the direct answers to your design and strategy questions.

### 1. What is the SOTA for "compliance dashboard" UX in 2026? Name 5+ real products.
The State of the Art has moved away from "calendars of doom" to **"Inbox Zero for Compliance"** and **Continuous Trust States**. 
1. **Deel:** Replaces legal jargon with plain English and binary states (Action Needed vs. Compliant). 
2. **Stripe Tax:** Uses intelligent progress bars and automated threshold monitoring. The UI is completely devoid of panic-inducing colors.
3. **Vanta / Drata:** Turns a binary pass/fail (SOC2/Compliance) into a gamified, always-on "98% Compliant" ring chart.
4. **Rippling:** Treats compliance like a unified, prioritized action inbox rather than a scattered calendar. 
5. **Pulley / Carta:** Equity compliance that uses horizontal timelines with milestone checkpoints rather than traditional monthly grids.

### 2. How do Cron/Notion/Linear handle dense calendar data without overwhelming users?
They use **Progressive Disclosure** and **Semantic Zooming**.
*   **Micro-indicators over text:** In a year view, you don't show the words "SPT Annual". You show a 4px #b89a40 dot. 
*   **Dimming the irrelevant:** Past events and low-priority items drop to 30% opacity. Only the *next* immediate action gets full opacity and a hover-lift shadow.
*   **Hover States (The Linear Way):** Density is hidden behind lightning-fast, zero-delay tooltips. You hover a dot, and a beautiful frosted glass popover explains the exact requirement. 

### 3. Should the year strip be horizontal (Jan→Dec) or radial (clock-style)?
**Horizontal, 100%.** 
Do not use radial/clock-style timelines. They are a designer's vanity trap. They force the user's eye to move in circles and text to render at awkward angles, heavily degrading legibility. To match the Vercel/Linear aesthetic, use a sleek, horizontal, horizontally-scrollable track (like a GitHub contribution graph or Vercel deploy timeline) with a subtle vertical glowing line indicating `TODAY`.

### 4. Should we show ALL deadlines or only the user's filtered ones on the year strip?
**ONLY the filtered ones.** 
The golden rule of compliance UX: *Never show a user a terrifying legal obligation that does not apply to them.* Showing a foreign individual a "PT PMA Corporate Tax" deadline creates cognitive friction and unnecessary panic. 
*UX Magic:* When the user switches profiles, use Framer Motion (spring physics) to smoothly animate the irrelevant dots disappearing and the new dots popping in. This visually proves the tool's "intelligence."

### 5. How to handle the "what if I miss it" fear WITHOUT weaponizing it?
Flip the framing from **Punitive** to **Protective**. 
*   **Don't:** "18 days left to file or you will be fined IDR 1M/month." (Weaponized)
*   **Do:** "Status: Protected. We are preparing your filing for March 31." (Calm, expert)
Never use red (#ff2d4c) for upcoming deadlines. Red means "System Error" or "Failed." Use your Gold (#b89a40) with a slow, pulsing opacity for upcoming deadlines, and solid white/grey for future ones. The messaging must imply that Bali Zero is a shield between them and the tax office.

### 6. Should the profile selector be a quiz (3 questions) or a single dropdown?
**Neither. Use a Segmented Control (Pill Tabs).**
A quiz adds too much friction for a marketing page. A dropdown hides the options, preventing the user from realizing the tool is dynamic. 
Put the 4 profiles in a glowing, horizontal segmented control immediately above the timeline. Let users rapidly click through them (Individual → Investor → PT PMA) and watch the calendar react instantly. It feels like a high-end web app, not a static site.

### 7. Best way to make Indonesian tax law approachable for an expat?
**The "Translation" Pattern.** 
Expats feel stupid when confronted with acronyms like "LKPM" or "PPh 4(2)". Never show an acronym without its plain-English equivalent. 
*   *UI Execution:* `Employee Income Tax (PPh 21)` or `Investment Report (LKPM)`. 
*   Add a subtle dotted underline to every tax term. Hovering it reveals a frosted-glass tooltip: *"LKPM: A mandatory quarterly report to the Investment Board proving your PMA is active. Missing this can freeze your business license."*

### 8. Provide 5 design references with URLs for calendar/compliance UX.
1.  **Vercel Ship / Special Event Pages:** Look at how they handle dark-mode timelines and glowing milestones. (vercel.com)
2.  **Linear Roadmaps:** The gold standard for horizontal timelines, dark mode density, and grouped milestones. (linear.app/features/roadmaps)
3.  **Vanta Trust Centers:** Look at their use of "continuous compliance" UI. (vanta.com/trust)
4.  **Stripe Tax:** Masterclass in explaining complex global tax liabilities in a calm, non-threatening UI. (stripe.com/tax)
5.  **Notion Calendar (Cron):** For how to handle colored dots, "today" indicators, and high-density time management. (calendar.notion.so)

### 9. For the countdown cards — should urgency be shown via color, icon, animation, or text?
**Text and subtle Iconography only.** 
*   **No animations.** A ticking clock or pulsing red border induces panic, which causes bounce rates. We want calm trust. 
*   **Visuals:** Use a solid, beautifully rendered 2D icon (e.g., a gold shield or a calendar with a checkmark). 
*   **Text:** "Next Milestone: Annual SPT · 18 days away". 
*   If you must use a visual indicator of time, use a static, conic progress ring (e.g., a ring that is 80% full) rather than a ticking countdown.

### 10. What are we missing? What would make this tool genuinely useful vs just pretty?
You are missing the **"Done" State** and the **"Local Nuance."**
1.  **The "Done" State:** A calendar full of future obligations is overwhelming. To build trust, the UI should visually demonstrate what *has already been handled*. Show the past 3 months with solid, glowing green/gold checkmarks. It subcommunicates: *"Look at all the things you didn't have to worry about because we handled them."*
2.  **The Local Nuance (The Flex):** Indonesian tax deadlines shift if they fall on a national holiday (Hari Libur Nasional). Build a tiny badge into the UI that says: *“* Adjusted for Idul Fitri holiday.”* This is a massive trust-builder. It proves Bali Zero isn't just a generic ChatGPT wrapper; you actually know the local ground reality. 
3.  **Actionability:** A date isn't enough. The countdown card should include a tiny bulleted list of *what they actually need to provide*. (e.g., *Required: 12 months of bank statements, active EFIN*). This bridges the gap between a date and the actual service Bali Zero provides.
