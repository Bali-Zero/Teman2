Here is my brutally honest, constructive review of the Tax Compliance Calendar tool, speaking from the perspective of a Senior Product Designer analyzing this for Bali Zero's specific audience (expats/businesses in Indonesia).

### 1. UX Flow: Profile → Filter → Deadlines → Lead Capture → CTA
**Friction Points:** You have a severe case of **CTA cannibalization**. 
By placing "Email me my personalized tax calendar" *before* the main conversion event ("Let us handle your filings → WhatsApp"), you are offering users an "out" right when their intent is highest. They will input their email, get the calendar, and bounce, thinking they can manage it themselves. 
*Fix:* The primary goal is the WhatsApp conversation. The email capture should be a secondary fallback (e.g., a text link below the primary button: *"Not ready to commit? Send this calendar to my email."*) or triggered via exit-intent on desktop. 

### 2. Visual: Dark Glass Aesthetic & Contrast
The #0a0a0a (true black/deep charcoal) with #b89a40 (muted gold) is highly premium and aligns perfectly with a "white-glove" service.
**Contrast Issues:** You are using 5 distinct colors (Gold, Blue, Green, Teal, Violet) on a near-black background. Standard blue and violet often fail WCAG AAA and sometimes AA contrast ratios against black. They will look muddy. 
*Fix:* You must use high-luminance, pastel, or neon variants of these colors (e.g., Tailwind's `blue-400` or `violet-400`). Furthermore, "mouse-aware glow" is a desktop-only vanity metric; ensure the fallback solid borders on mobile still feel premium.

### 3. Data: Indonesian Tax Deadlines
The data is directionally excellent, especially the inclusion of LKPM and PB1 (which many generic calendars miss).
**The Danger:** The Indonesian MoF recently rolled out **PMK 81/2024** (effective Jan 1, 2025, with core system rollouts happening throughout 2025/2026). This regulation drastically alters payment and reporting dates, unifying many of them to the 15th and 20th. 
*Fix:* Add a subtle but visible "Updated for Core Tax System (CTAS) / PMK 81" badge. This signals extreme competence. Also, include a standard legal disclaimer that dates can shift based on local regency holidays (especially in Bali with Nyepi, Galungan, etc.).

### 4. Copy Tone: Calm & Protective vs. Fear
**Brilliant execution here.** The "Guardian UI" philosophy is completely working. 
Translating "SPT" to "like IRS Form 1040" is an absolute masterstroke of localized UX. You are reducing cognitive load instantly. The "Recently Handled" section with green checkmarks is the best part of this design—it visually demonstrates the relief of having a professional handle the burden. It says "look at all this work you *didn't* have to do."

### 5. Mobile: 390x844 Responsive Concerns
**High Concern:** The acronym tooltips on hover. "Hover" does not exist on iOS/Android. If a user taps an acronym, what happens? If it opens a tooltip, they have to tap elsewhere to dismiss it, which can cause accidental clicks on CTAs or links. 
*Fix:* On mobile, do not use tooltips. Use a persistent glossary section at the bottom, or an inline accordion (e.g., tapping "SPT" expands a tiny inline definition right below it). The horizontal scroll strip is fine, but ensure you have a visual gradient "fade" on the right edge so users inherently know they can swipe.

### 6. A11y: Accessibility Gaps
**Major Gap: Color as the only indicator.** You are using 5 colors of dots to indicate deadline types. This completely fails WCAG 1.4.1 (Use of Color). Colorblind users (up to 8% of males) will just see a row of indistinguishable grey dots.
*Fix:* Pair the colors with icons, shapes, or letters. For example: a Gold square for Tax, a Blue circle for VAT, a Green triangle for BPJS. 

### 7. Conversion: Will this convert?
Yes. It visually manifests an invisible, highly stressful problem, and then immediately provides a reasonably priced button to make the problem go away. 
*To improve conversion:* Add a micro-copy trust signal directly below the price. "From IDR 5M/year • Cancel anytime • Zero late fees guaranteed."

### 8. Biggest Weakness & Strength
*   **Biggest Weakness:** Mobile interaction paradigms (tooltips) and accessibility failures regarding color-coding. Also, the competing lead-capture email form.
*   **Biggest Strength:** The psychological framing. The "Recently Handled" section combined with US/Western-friendly analogies (IRS Form 1040) creates immediate trust and relief.

### 9. Ratings (Out of 10)
*   **UX:** 7.5 (Docked for CTA cannibalization and mobile hover assumptions).
*   **Visual Design:** 9.0 (Premium, restrained, modern).
*   **Data Accuracy:** 8.5 (Good, but requires PMK 81/2024 verification).
*   **Conversion Potential:** 9.0 (Once the CTA hierarchy is fixed, this is a highly persuasive tool).

### 10. Three Specific Actionable Improvements
1.  **Fix the CTA Hierarchy:** Make "Talk to Asya on WhatsApp" a sticky, full-width button at the bottom of the mobile viewport. Move the "Email me my calendar" to an exit-intent popup on desktop, and a low-emphasis text link on mobile.
2.  **Make the Dots Accessible (WCAG):** Do not rely solely on color for the 5 deadline types on the year strip. Add a tiny 1-2 letter initial inside the dot (e.g., `[T]` for Tax, `[V]` for VAT, `[B]` for BPJS), or use distinct geometric shapes. 
3.  **Adapt Tooltips for Touch:** On mobile viewports, disable tooltips entirely. Instead, make the acronyms actionable buttons that trigger a clean, native-feeling "Bottom Sheet" (half-screen modal) that explains the term and includes a mini CTA ("Need help with your SPT?").
rover/out listeners with this combined logic:
['pointerover', 'focusin'].forEach(evt => {
  document.addEventListener(evt, (e) => {
    const dot = e.target.closest('.year-strip__dot');
    if (!dot) return;
    
    dotTip.innerHTML = `<strong>${dot.dataset.tipTitle}</strong>${dot.dataset.tipBody}`;
    dotTip.classList.add('show');
    dotTip.setAttribute('aria-hidden', 'false');
  });
});

['pointerout', 'focusout'].forEach(evt => {
  document.addEventListener(evt, (e) => {
    if (e.target.closest('.year-strip__dot')) {
      dotTip.classList.remove('show');
      dotTip.setAttribute('aria-hidden', 'true');
    }
  });
});
```

**3. Implement Smart Tooltip Bounds for Mobile**
Update the positioning logic inside your event listener to calculate viewport bounds so the tooltip never bleeds off the edge of the mobile screen.
```javascript
// Add this inside the focusin/pointerover event listener (after dotTip.classList.add('show'))
const r = dot.getBoundingClientRect();
const tipRect = dotTip.getBoundingClientRect();

// Center the tooltip relative to the dot
let leftPos = r.left + (r.width / 2) - (tipRect.width / 2);

// Boundary detection (16px padding from screen edges)
if (leftPos < 16) {
  leftPos = 16;
} else if (leftPos + tipRect.width > window.innerWidth - 16) {
  leftPos = window.innerWidth - tipRect.width - 16;
}

dotTip.style.left = `${leftPos}px`;
dotTip.style.top = `${r.bottom + 8}px`;
```
