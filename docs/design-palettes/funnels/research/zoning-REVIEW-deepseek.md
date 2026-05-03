# Bali Zoning Map Tool — UX & Product Review

**Overall Impression:** This is an exceptionally well-executed prototype that succeeds in its primary goal: transforming fear into trust through clarity, honesty, and utility. The craftsmanship—especially for a vanilla HTML/CSS/JS implementation—is impressive. It feels like a serious legal instrument, not a marketing gimmick, which is its greatest strength.

---

## 1. **UX/Product — Side Panel Hierarchy**  
**Score: 8/10**  
The hierarchy is mostly logical, but suffers from one critical tension: **the scam warning is too dominant**. Placing the "Hak Milik scam warning" *immediately* below the zone header, and keeping it *always visible*, is like yelling "DON'T TRUST ANYONE!" before introducing yourself. It's necessary, but its persistent, high-contrast placement creates anxiety before the user has even processed the specific zone data.  
**Recommendation:** Move it below the "Foreign Ownership Status" table. Let the user first see the *specific* legal status for their chosen location, then deliver the universal warning as contextual reinforcement. The action items ("What to verify") should also move up—they are practical next steps and belong closer to the ownership table.

## 2. **Trust Calibration**  
**Score: 9/10**  
It feels like a serious legal instrument. **Elements that build trust:**  
- **Black zone integrity:** The "DO NOT BUY" message with no CTA is a powerful signal of honesty.  
- **Data transparency:** Source citations (GISTARU), specific PBG risk percentages, and clear zone definitions.  
- **Professional restraint:** Dark mode, clean typography, and absence of flashy animations.  
- **Case study link:** Specific, credible ("caught a USD 220K fake freehold").  
**Minor trust erosion:** The hand-drawn map, while charming, slightly undermines geographic precision. Some users might question data accuracy if the map feels "illustrative."

## 3. **Conversion Flow**  
**Score: 8/10**  
The sequence is correct: **Problem → Diagnosis → Solution → Lead Capture.**  
- Value (personalized zoning analysis) is delivered *before* the USD 850 DD CTA.  
- The free "1-page zoning summary" email capture after the CTA is smart—it catches leads who aren't ready to commit.  
**Suggestion:** The WhatsApp button should have a pre-filled message template ("Hi, I'm interested in Due Diligence for [Location]") to reduce friction. The email field could also benefit from a privacy disclaimer ("No spam, zoning summary only").

## 4. **Data Quality & Realism**  
**Score: 7/10**  
The 10 demo locations are well-chosen to represent the spectrum of zoning challenges. However:  
- **Amber zone for Canggu/Seminyak** feels optimistic; in reality, many sub-zones there are *de facto* red/black due to agrarian designations. The tool should more strongly caveat that "amber" can hide parcel-level prohibitions.  
- **PBG risk percentages** (e.g., "High – 68%") are compelling but lack attribution. A footnote explaining the methodology (e.g., "Based on 2023 rejections for foreign-owned villas") would bolster credibility.  
- **Ownership table** is accurate for foreign buyers. Good inclusion of "HGB via PMA" and clear "Not Allowed" red cells.

## 5. **Missing Critical Elements**  
**Score: 6/10**  
What’s missing to make it 10x more useful:  
- **Parcel-level zoning overlay:** The biggest gap. Buyers care about *their specific plot*, not just the *kabupaten*. A disclaimer: "This is regional zoning; parcel-level verification requires official site survey" is essential.  
- **"Last Updated" date:** Indonesian zoning changes frequently. A timestamp (e.g., "Data sourced Q1 2024") is critical for trust.  
- **Print/PDF export** of the side panel for sharing with lawyers or partners.  
- **Audit trail:** A subtle "Verification ID" (e.g., #BZ-UBUD-1243) that ties to an internal record, suggesting rigor.

## 6. **SVG Map Approach**  
**Score: 7/10**  
The hand-drawn style is acceptable for clarity and brand distinction, but sacrifices some authority. **Recommendation:** Keep the stylized base map but add a **toggle** between "Stylized" and "Administrative" views. The latter could use actual GIS-derived kabupaten borders (still simplified) to satisfy users who need geographic precision. The clickable regions and keyboard nav are excellently implemented.

## 7. **Black Zone Integrity**  
**Score: 10/10**  
The "no upsell" approach is **correct and brilliant.** It transforms skepticism into trust. Showing "DO NOT BUY" with *no* CTA except an honest alternative ("Consider leasehold in neighboring Gianyar") positions Bali Zero as a fiduciary, not a sales engine. This alone could be the core of their marketing: "We turn down business to protect you."

## 8. **Mobile Layout**  
**Score: 8/10**  
Vertical stack (map on top, panel below) is the right pattern for readability. However, the map becomes a static preview on mobile—**pinch-to-zoom and pan should be enabled** even if simplified. The horizontally scrolling preset buttons are smart. The stat strip moving to 2-column is effective. Ensure the search autocomplete dropdown is touch-friendly with larger tap targets.

## 9. **Indonesian Jargon Handling**  
**Score: 9/10**  
The badge (color + text) + tooltip approach is sufficient. "HGB," "Hak Pakai," and "PBG" are unavoidable jargon; the tooltips provide quick education. Consider adding a **hoverable glossary icon** next to each term that persists on mobile (tap to reveal). The English translations ("Right to Use") are clear.

## 10. **Competitive Edge**  
**Score: 9/10**  
**What makes it better:**  
- **Fear-to-trust narrative** is directly addressed, unlike static PDF guides or agent vague promises.  
- **Interactive personalization:** Immediate feedback for *their* chosen location.  
- **Honesty hierarchy:** Black zone treatment is unmatched.  
- **Accessibility focus:** ARIA, keyboard nav, reduced motion—rare in property tools.  
**Where it could be worse:** Lack of parcel-level data means it can't replace a site survey. Some competitors might offer "zoning certificates" (often shallow) that feel more definitive. Bali Zero should emphasize that this tool is the *starting point*, not the final word.

---

**Final Summary:**  
This prototype is **85% of the way to a world-class trust-building tool.** Its core strength is ethical design—the black zone honesty and transparent data presentation. To elevate it:  
1. Reorder the side panel to soften the initial scam warning.  
2. Add parcel-level disclaimers and data timestamps.  
3. Consider a map view toggle for geographic purists.  
4. Enable mobile map interaction.  

**Overall Score: 8.3/10** — A remarkably solid foundation that already achieves its primary psychological mission: replacing uncertainty with structured, credible clarity.
