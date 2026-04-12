---

## 1. SOTA for "compliance dashboard" UX in 2026
**Current leaders (2024–2025) pushing the state forward:**  
- **Rippling** (HR/compliance) – unified timeline, proactive alerts  
- **Deel** (global payroll/compliance) – country-specific cards, plain-English summaries  
- **Vanta** (security compliance) – real-time progress rings, checklist breakdowns  
- **Pulley** (cap table/compliance) – deadline heatmaps by entity type  
- **Remote.com** – visual tax calendar with "handled" toggle  
- **Carta** – investor reporting timelines with "done/upcoming" segregation  

SOTA trend: **Proactive, not reactive** – dashboards predict deadlines based on entity profile, show "handled by us" badges, and explain *why* each deadline matters in simple terms.

---

## 2. How Cron/Notion/Linear handle dense calendar data without overwhelm
- **Cron** (now part of Notion Calendar): Uses **horizontal stacking** of events in day view, **faded past events**, **color-coding by calendar**, and **month-scale dot indicators** (tiny dots under dates).
- **Notion Timeline**: **Collapsible rows**, **filter by property**, **gantt-style bars** for duration.
- **Linear**: **Issue grouping** by cycle, **status pills** (Backlog, Next, Done), **hover-to-peek details**, **keyboard nav**.

**Takeaway for Bali Zero:**  
Use **dot density** on year strip (more dots = busier month), **hover reveals detail**, **group similar deadlines** (e.g., "Monthly Withholding" as one dot with count), **collapse past months**.

---

## 3. Year strip: horizontal vs radial
**Horizontal.**  
Why: Radial calendars (like Google’s 12-month “clock”) are novel but less scannable for deadline density. Expats are already stressed about foreign tax systems; novelty adds cognitive load. Horizontal strip aligns with mental model (Jan→Dec timeline).  
**But** – add a **conic gradient ring** *around* the current month as a visual accent (hinting at radial style without sacrificing usability).

---

## 4. Show ALL deadlines or only filtered ones?
**Only filtered deadlines.**  
Show users *only* what applies to them. If a PT PMA selects their profile, they see all PT PMA deadlines. This reduces visual noise and reinforces "this is *your* calendar."  
Add a toggle: **"Show all Indonesian tax deadlines"** for the curious.

---

## 5. Handle "what if I miss it" fear WITHOUT weaponizing it
- **Protective framing**: "We’ll remind you 7 days before" / "Our team files this for you"  
- **Status badges**: "Handled by Bali Zero" (green check) vs "Requires your input" (yellow).  
- **Microcopy**: "Missed deadlines can lead to fines. **We prevent that**."  
- **Visual tone**: Use gold (#b89a40) for deadlines (authoritative, not alarmist), not red. Red only for "past due" if they enter a past date in simulation.  
- **Add a small "Penty Help" link**: "If you’ve missed a deadline, we can help fix it →" (reassuring, not fear-driven).

---

## 6. Profile selector: quiz or dropdown?
**Single dropdown with clear icons + short descriptions.**  
Quizzes add friction and feel like "marketing engagement bait." Expats want quick answers.  
Example dropdown option:  
`[🏢] PT PMA company – monthly & annual corporate filings + VAT`  
`[👥] PT PMA + employees – all above + BPJS employment reports`  
Hover on each shows deadline count: "~48 deadlines/year."

---

## 7. Making Indonesian tax law approachable for German/American/Italian expats
- **Map to familiar concepts**: "SPT Tahunan = Annual Tax Return," "PPh 21 = Monthly Employee Withholding," "PB1 = Bali Hospitality Tax."  
- **Flag system**: 🇮🇩 for Indonesian-specific, 🏝️ for Bali-specific.  
- **Explain why**: "BPJS Ketenagakerjaan = mandatory employment insurance (like Sozialversicherung in Germany)."  
- **Glossary tooltip**: dotted underline on terms → hover reveals plain English.  
- **Show relatable deadlines first**: "March 31 – Annual Personal Tax Return (like IRS April 15)."

---

## 8. 5 design references with URLs
1. **Linear Timeline** – https://linear.app – clean cycle grouping  
2. **Vercel Analytics Dashboard** – https://vercel.com/analytics – glassy cards, conic charts  
3. **Cron Calendar (Notion)** – https://cron.com – month dot indicators, hover expansion  
4. **Stripe Radar** – https://stripe.com/radar – risk visualization with calm urgency  
5. **Apple Fitness Rings** – https://www.apple.com/fitness – conic progress, completion motivation

---

## 9. Countdown cards – urgency expression
**Tiered urgency system:**  
- >30 days: grey border, no icon  
- 7–30 days: gold border, ⏳ icon  
- <7 days: subtle pulsing gold border (CSS animation, not annoying), 🔔 icon  
**Text**: "in 18 days" (neutral), "due in 3 days" (bold), "due tomorrow" (bold + gold).  
Never use red unless deadline is past.

---

## 10. What’s missing? Making it genuinely useful vs just pretty
**Missing:**
1. **Holiday shift indicator**: "Note: If deadline falls on public holiday, due next business day." Show with a small 🏖️ icon.
2. **"Mark as done"**: Let users check off (psychological reward) – even if Bali Zero handles it.
3. **PDF export**: "Download this calendar as PDF" (people print/post on fridge).
4. **Timezone note**: "Deadlines refer to WITA (Bali time)."
5. **Integration hint**: "Sync this calendar with Google Calendar" (API later, but signal intent).
6. **What you’re NOT responsible for**: e.g., "As a foreign individual, you don’t need VAT filings." Reduces anxiety.
7. **Pro tip callouts**: "Set reminder 3 days before to gather receipts."
8. **Progress bar**: "You’ve completed 8/24 filings this year" – builds trust in system.
9. **Live date simulation**: Let user pick "Today's date" to see how deadlines adjust.
10. **"Ask Asya" button** on each deadline card – directly to WhatsApp pre-filled with question.

**Proposed better structure:**  
Make the card **interactive demo** of their **actual compliance dashboard** if they sign up. The home page version is a preview – after email capture, they get a personalized URL with all above features.

---

**Final recommendation:**  
Build a **horizontal timeline** with **filtered deadlines only**, **conic ring highlight** on current month, **tiered countdown cards**, **dropdown selector**, and **exportable PDF + sync promise**. Lead with "We handle this for you" not "You must do this." The tool should feel like a **protective shield**, not a scary checklist.
