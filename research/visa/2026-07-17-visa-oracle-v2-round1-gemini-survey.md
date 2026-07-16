---
date: 2026-07-17
domain: visa
client_case: none — product research (Visa Oracle v2 rebuild)
sources: multi-LLM panel round 1 (lane: gemini-3.1-pro-high)
status: round-1 raw lane output, faithfully preserved
adversarial_review: codex
---

# DEEP RESEARCH — Visa Oracle Decision Tree (Lane: GLOBAL SURVEY / WIDTH)

## 1. Government Exemplars: The Bureaucratic Standard

Government websites have a unique mandate: they must be accessible to everyone, across all devices, with absolute clarity, while handling extreme edge cases. The best ones turn complex law into simple questions.

### GOV.UK ("Check if you need a UK visa")
*   **The Interaction:** The absolute gold standard for public service design. It uses a pattern called "Smart Answers." One question per page, massive typography, high contrast, radio buttons that are easy to tap on mobile. 
*   **Why it Works:** It relies on aggressive progressive disclosure. It doesn’t explain *all* visa types; it asks for your nationality, then your purpose (work, study, visit), then specific sub-conditions (e.g., "Are you an academic?"). The URL updates with each answer (e.g., `/check-uk-visa/y/indonesia/work/longer_than_six_months`), making states sharable and back-button safe.
*   **What to Steal:** One-question-per-page (OQPP) architecture. The "Start now" green button. The summary page at the end showing exactly *how* you arrived at the answer, with links to change individual answers without restarting.

### Canada IRCC ("Come to Canada" Wizard)
*   **The Interaction:** A multi-step questionnaire that feels like a rigorous qualification filter. Uses a progress bar and contextual help accordions ("?" icons next to complex terms).
*   **Why it Works:** It effectively manages the anxiety of the applicant. When asking complex questions (e.g., "Do you have a provincial nomination?"), it provides immediate inline definitions so the user doesn't have to Google it and break the flow.
*   **What to Steal:** Inline, expanding glossary terms. When asking a legal definition (e.g., "Are you a digital nomad?"), give a hyper-concise tooltip or accordion definition.

### Australia Home Affairs (Visa Finder)
*   **The Interaction:** A faceted search approach. Users select their purpose, and it filters a grid of visa cards down to the matching options.
*   **Why it Works:** It handles the scenario where a user might be eligible for *multiple* visas (e.g., Working Holiday vs. Student). It allows side-by-side comparison.
*   **What to Steal:** The "Compare Visas" output state. If Visa Oracle determines a user could do B211A *or* E33G (Remote Worker), show a distinct, scannable comparison table (Cost vs. Duration vs. Requirements).

### Estonia e-Residency
*   **The Interaction:** Highly branded, aspiration-driven funnel. Less of a "check eligibility" and more of an "onboarding to a lifestyle."
*   **Why it Works:** It uses beautiful micro-copy and illustrations. It makes a government process feel like signing up for a premium SaaS product.
*   **What to Steal:** The emotional tone. Immigration is stressful; the UX should be calming, authoritative, and deeply aesthetic.

---

## 2. Private Immigration/Visa Tech: Speed & Conversion

Private companies need to convert visitors into paying customers. Their UX is optimized for speed, reduced friction, and immediate trust.

### Atlys / iVisa
*   **The Interaction:** Heavy reliance on geolocation and auto-detection. "You are in [US], flying to [Indonesia]." Massive search bars.
*   **Why it Works:** Immediate time-to-value. They don't make you search for your country if they can detect it. They use clear, bold pricing and processing times upfront to drive urgency.
*   **What to Steal:** Auto-detect origin country (with easy override). Display the "Output" (Visa Name, Cost, Days to Process) as a persistent sticky header once determined.

### Boundless (US Immigration)
*   **The Interaction:** A highly empathetic, narrative-driven interview. "Let's find out if you qualify." It uses conversational UI rather than stark forms.
*   **Why it Works:** Family immigration (marriage green cards) is high-stakes. Boundless uses soft UI, reassuring checkmarks, and progress rings to build trust over a 15-minute questionnaire.
*   **What to Steal:** The "Eligibility Confidence Score" or reassuring success states. "Great news! Based on your answers, you are a strong candidate for the E33G Remote Worker visa."

### Deel / SafetyWing (Borderless/Remote Tools)
*   **The Interaction:** Map-based or card-based visual exploration. "Where do you want to go?"
*   **Why it Works:** Nomads are visual and destination-driven.
*   **What to Steal:** Visualizing the requirements. Using clean, modern iconography for things like "Must earn $2,000/mo" or "Proof of savings."

---

## 3. Cross-Domain Interview UX Masters

The best decision trees aren't in immigration; they are in consumer SaaS.

### Typeform / Linear
*   **The Interaction:** Keyboard-first navigation. Press 'A', 'B', 'C', or 'Enter' to proceed. 
*   **Why it Works:** Power users and fast readers hate using the mouse.
*   **What to Steal:** Keyboard shortcuts for the entire wizard. It makes the app feel lightning-fast and "pro."

### TurboTax
*   **The Interaction:** The "Shoebox" method. It takes a terrifying legal domain (tax code) and breaks it into plain English scenarios. "Did you buy a house this year?"
*   **Why it Works:** It never asks a user to categorize themselves legally until it has to. It asks behavioral questions, then does the legal mapping in the background.
*   **What to Steal:** Don't ask "Do you require a C314 Investor KITAS?" Ask "Are you investing money into an Indonesian company?" Let the Oracle do the mapping.

### Duolingo
*   **The Interaction:** Gamified onboarding. Immediate interaction before creating an account.
*   **Why it Works:** Sunk-cost fallacy. By the time you get your result, you are invested.
*   **What to Steal:** Micro-animations (loading spinners that say "Checking immigration databases...", even if it's instant) to create a perception of deep, customized work being done.

---

## 4. Indonesian Official Ecosystem Analysis

### The Current State (evisa.imigrasi.go.id / Molina / M-Paspor)
*   **The UX:** Functional but deeply flawed. It suffers from confusing categorization (mixing index codes with descriptions), fragile session management (infinite loops, random resets), anxiety-inducing payment gateways with hidden steps, and a lack of clear guidance on *which* visa to pick before you start the application.
*   **Expat Pain Points:** "I don't know the difference between a B211A and a 211A." "The site crashed after I paid." "I got an email that looks like a scam." "I picked the wrong purpose and got rejected with no refund."
*   **The Gap Visa Oracle Fills:** The official site is a *processing engine*. Visa Oracle is the *diagnostic engine*. The official site assumes you know what you want; Visa Oracle figures out what you *need*.

### What Ditjen Imigrasi Would Value (Showcase Potential)
To impress Jakarta, the tool must not be seen as a replacement for Molina, but as the ultimate "Front Door" that perfectly tees up clean applications for their system.
*   **They will value:** Massive reduction in support tickets/rejected applications. Clear, flawless mapping of user intent to the *exact current legal index codes* (showing Bali Zero respects and deeply understands their taxonomy).
*   **Overstepping:** Trying to take the payment or process the e-Visa directly inside the tool in a way that obfuscates the official channel, or criticizing the official site's downtime. The stance should be: "We guide them perfectly, so your system receives perfect data."

---

## 5. The Steal-List: TOP 20 Patterns for Visa Oracle

Here are the concrete features to implement, ranked by impact/effort.

| Rank | Pattern | Source | Why it Matters for Immigration | Effort |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **One-Question-Per-Page (OQPP)** | GOV.UK, Typeform | Reduces cognitive load. Users only think about one constraint at a time. | S |
| **2** | **Keyboard-First Navigation (1-9, Enter)** | Linear, Typeform | Makes the tool feel impossibly fast and premium. | S |
| **3** | **Behavioral Questions, Not Legal Ones** | TurboTax | Expats don't know index codes. Ask "What will you do?", not "Which visa do you want?" | M |
| **4** | **Sharable State URLs (`/quiz/us/work/investor`)** | GOV.UK | Allows users to bookmark their result or share it with a partner/lawyer. | M |
| **5** | **Auto-detect Nationality (GeoIP)** | Atlys | Removes the very first point of friction. "Looks like you're from the US..." | S |
| **6** | **Inline Glossary Accordions** | Canada IRCC | Prevents users from opening a new tab to Google "What is a sponsor?" | M |
| **7** | **The "Confidence" Loading Screen** | Duolingo | An artificial 1.5s delay showing "Analyzing options... Checking new regulations..." builds perceived value. | S |
| **8** | **Answer Review Summary** | GOV.UK | At the result page, show: "You said: US Citizen -> Staying 6 mos -> Not working. [Edit]" | S |
| **9** | **Side-by-Side Comparison** | AUS Home Affairs | If eligible for 2 visas (e.g., VOA vs B211A), show a direct pricing/duration comparison table. | M |
| **10** | **Interactive Eligibility Checklist** | Boundless | On the result page, a checklist: "To get this, you will need: [ ] Passport [ ] $2k Bank Statement." | M |
| **11** | **Dynamic "Cost Calculator" Widget** | Deel | A sticky widget that updates the total estimated cost (Visa Fee + Agency Fee) as they answer. | M |
| **12** | **"Reassurance" Microcopy** | Typeform | Small text under buttons: "Don't worry, you can change this later." Reduces selection anxiety. | S |
| **13** | **Visual Document Previews** | SafetyWing | Instead of saying "Bank statement," show a blurred, stylized vector image of an acceptable bank statement. | L |
| **14** | **The "Edge Case" Escape Hatch** | Typeform | If a user hits a dead end (e.g., a banned nationality), gracefully exit to a "Talk to a Human" lead form. | S |
| **15** | **Index Code Transparency (For Imigrasi)** | Custom | On the result page, prominently display the official index code (e.g., E33G) to build authority with the Govt. | S |
| **16** | **"Next Steps" Timeline** | GOV.UK | A vertical stepper showing what happens after they choose this visa (Apply -> Pay -> Wait 5 days -> Fly). | M |
| **17** | **Dark Mode / Glassmorphism UI** | Apple, Vercel | Essential for the "stunning/premium" requirement. Visually separates from the dry government sites. | M |
| **18** | **"Save for Later" via Email** | TurboTax | Capture the lead: "Send these results to my email to review later." | M |
| **19** | **Contextual Warnings** | Custom | e.g., If they select "Working," a polite but firm warning: "Note: Working on a tourist visa risks deportation." | S |
| **20** | **The "Apply Now" Handoff** | iVisa | A seamless transition from the Oracle's result directly into Bali Zero's service onboarding flow. | L |

## Adversarial review

**Seat:** codex (GPT-5.6-terra-high adversarial grading, 2026-07-17)
**Verdict:** SURVIVES-WITH-CAVEATS

Challenged points:
- GeoIP detects location, not nationality — should prefill only with explicit user confirmation, never
  presented as a silent inferred fact.
- B211A is treated as current in the survey, but the official visa list now presents C1/C2 in its place.
- The "checking databases" fake-delay UX pattern would be deceptive if implemented literally — no such
  check actually runs behind it.

This section is an appended R1-gate artifact (generator≠grader); the file body above is preserved
verbatim as the faithful record of this panel lane's original output.
