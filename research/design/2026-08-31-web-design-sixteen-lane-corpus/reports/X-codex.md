---
lane: X2 — The Architecture of the Money Moment (adversarial)
seat: Codex / GPT-5
date: 2026-08-31
sources_verified_live: 0
sources_from_memory: 10
---

## Executive summary

- Do not charge at the provisional verdict: show IDR 790,000 first, inspect the passport, then request payment immediately before submission.
- “Supported” must mean “supported by your answers, pending document verification,” never “approved” or even “eligible” without qualification.
- Four semantic questions can triage the clean cases; ambiguity must open a human-review lane with no payment, not force a false yes/no.
- Trust is won through a visible refund matrix, a price lock, a case ledger, and an honest distinction between Bali Zero’s work and Immigration’s decision.
- Keep self-service for the green path, but place a named human and WhatsApp escape hatch before personal-data collection, not behind the payment wall.

## Finding 1 — The product is a state machine, not a five-screen funnel

### 1. Named example

Stripe’s PaymentIntent lifecycle is the useful model: a payment is not simply “paid” or “unpaid,” but moves through explicit states such as requiring a payment method, processing, succeeded, or cancelled. Wise’s transfer tracker applies the same principle after money moves: the user sees what has happened, what is pending, and what comes next.

- `FROM-MEMORY (unverified)` — Stripe, “PaymentIntent status lifecycle”: https://docs.stripe.com/payments/paymentintents/lifecycle
- `FROM-MEMORY (unverified)` — Wise Help Centre, transfer tracking: https://wise.com/help/articles/2932719/how-do-i-track-my-transfer

These examples are older than the 2025–2026 preference, but the mechanism still holds: systems handling irreversible money need explicit, recoverable states.

### 2. Measurable rule

Every case must have:

- One stable case ID created when the first answer is saved.
- One authoritative server-side state; the browser URL is not the state.
- An append-only event ledger recording answers, quote version, document decisions, payments, submission and Immigration updates.
- Idempotency on payment creation, document submission and refunds: repeating a request cannot produce a second charge or application.
- A version number on every answer set. A second device must detect and resolve a stale edit rather than overwrite newer answers.
- A quote with a currency, total, policy version and expiry. Once paid, the customer’s price is locked.
- A visible timestamp and next action for every pending state.
- Payment success derived from the payment provider’s server notification, not merely the browser returning to a success page.

The minimum state inventory is below. “Out of pocket” means who currently carries an unrecovered monetary cost, not who has spent time.

| State | What the screen must say | What the system owes the user | Who is out of pocket |
|---|---|---|---|
| New | “Check whether GARUDA VOA fits your trip. No payment or upload yet.” | Explain the four-question process, total-price principle and government-decision boundary. | No one |
| Answers started | “1 of 4 answered — saved.” | Save after every answer and provide a private resume method. | No one |
| Answers abandoned | “Your check is incomplete. Continue or delete it.” | Preserve it for a disclosed period; allow deletion. | No one |
| Answers complete, unsupported | “GARUDA VOA does not support this trip based on these answers.” | Show the decisive answer, allow correction, offer a human-reviewed alternative. | No one |
| Answers complete, ambiguous | “We cannot decide this safely online.” | Route to a human without charging or requiring a passport unless genuinely necessary. | Bali Zero bears review time |
| Provisionally supported | “Supported by your answers — passport check still required.” | Show the price, refund boundary and remaining steps before requesting personal data. | No one |
| Quote displayed | “Total: IDR 790,000. Government fee and Bali Zero service included.” | Preserve the quote until its displayed expiry; disclose what can change it. | No one |
| Upload started | “Uploading securely; do not close this page.” | Resume interrupted upload without duplicating files. | No one |
| Upload received | “Passport received; payment has not been taken.” | Acknowledge receipt immediately and disclose the review time. | No one |
| Upload unreadable | “We cannot read the passport image. No payment has been taken.” | Name the defect—glare, crop, blur or missing page—and accept replacement. | No one |
| Passport fails a hard rule | “The passport details do not support GARUDA VOA.” | Identify the relevant field without vague “verification failed” language; provide review. | No one |
| Passport contradicts answers | “The passport says X; your answer said Y.” | Let the user correct the answer, then recompute eligibility and price. | No one |
| Document verified | “Passport check passed. Review everything before paying.” | Present the exact extracted fields and editable answers. | No one |
| Quote expired before payment | “The earlier quote expired. Nothing was charged.” | Show old and new totals and require fresh consent. | No one |
| Payment initiated | “Waiting for payment confirmation.” | Show the rail, amount, expiry and safe retry instructions. | Possibly user; provider confirmation pending |
| Payment pending | “Your bank may have completed this payment. Do not pay again.” | Reconcile asynchronously and prevent a second payment attempt until status is known. | User may be temporarily out of pocket |
| Payment failed | “Payment was not completed. No confirmed charge exists.” | Preserve the verified application and allow another rail. | Usually no one; provider fees may exist |
| Payment succeeded | “IDR 790,000 received. We have not claimed Immigration approval.” | Issue a receipt, lock the price and move automatically toward submission. | User |
| Duplicate payment | “We found two payments. The duplicate is being refunded.” | Begin an automatic refund and show its reference and expected rail-dependent timing. | User until refund settles |
| Paid but application cannot be assembled | “We received payment, but cannot submit because…” | Halt, identify the problem and apply the disclosed refund rule without making the customer chase. | User; Bali Zero may owe refund |
| Submission queued | “Ready for submission; not yet sent to Immigration.” | Give a submission deadline and cancellation consequences. | User |
| Submission attempted, provider unavailable | “Immigration’s service is temporarily unavailable; your application is safe.” | Retry without duplicate submission; let the user choose refund if the promised deadline becomes impossible. | User; Bali Zero may absorb fees |
| Submitted | “Submitted to Indonesian Immigration at [time].” | Provide a submission receipt/reference and freeze the submitted data. | User; government fee may now be spent |
| Under Immigration review | “Immigration is reviewing the application. Bali Zero cannot accelerate or guarantee the decision.” | Show last update, realistic range and next escalation time. | User |
| More information required | “Immigration requested [item] by [deadline].” | Notify through more than one channel, preserve the original request and confirm receipt of the response. | User |
| Approved | “Approved — download and verify your visa.” | Provide the official document, instructions and a field-by-field identity check. | User has received the purchased outcome |
| Refused | “Immigration refused the application. This is the decision and this is what happens to each part of your payment.” | Show the official reason where available, the refund matrix and human escalation. | User, except amounts Bali Zero refunds |
| Cancelled before submission | “Cancelled before government submission.” | Apply the pre-submission refund policy and issue a traceable refund. | User until refund settles |
| Refund pending | “Refund initiated: [amount], [rail], [reference].” | Track it as carefully as the original payment. | User |
| Refunded | “Refund completed.” | Provide proof and close or reopen the case explicitly. | No one |
| Closed for inactivity | “This case was paused, not silently deleted.” | Require fresh checks for time-sensitive answers and quotes on reopening. | Depends on prior payment state |
| Opened on second device | “This case was updated elsewhere at [time].” | Show the latest version before accepting edits. | No change |
| Shared link opened by another person | “Verify access to continue.” | Reveal no passport, payment or verdict detail until authentication succeeds. | No change |
| Disputed or charged back | “Your bank disputed the payment; submission status is…” | Do not cancel a submitted government application as if payment reversal undid it; route to a human. | Bali Zero may be out of pocket |
| Internal error | “We have your case; this page failed to load.” | Preserve state, give a reference, provide another channel and never ask for a blind repeat payment. | Depends on last durable state |

A closed tab for three days is therefore not exceptional. The case reopens from its durable state, revalidates only time-sensitive facts and never silently changes “paid” back to “start.”

### 3. What to steal for Bali Zero

Replace the visual five-step funnel with a case ledger that happens to have five customer-facing stages:

1. Trip check.
2. Passport check.
3. Review and payment.
4. Submitted to Immigration.
5. Decision.

Below the headline, show a timestamped history: “Answers saved,” “Passport checked,” “Payment received,” “Submitted.” The Visa Oracle should hand its answer set and case ID into GARUDA VOA instead of making the buyer start again. The final status page must remain useful during days of silence.

### 4. What to avoid

Avoid the fashionable single progress bar—“Step 4 of 5”—when the underlying process contains waiting, correction and refusal. A progress bar describes page position, not legal or financial state. It becomes deceptive when “90% complete” remains unchanged for three days.

Also avoid treating the success redirect as proof of payment, silently restarting an expired case, or showing “Something went wrong” after money moved. Those are not cosmetic bugs; they destroy the customer’s ability to determine who holds the money.

## Finding 2 — Charge after document preflight, immediately before submission

### 1. Named example

W3C’s error-prevention criterion for financial and legal submissions requires at least one of reversibility, input checking, or a review-and-confirm mechanism. GOV.UK’s “Check answers” pattern embodies the review mechanism by placing a complete, editable summary before commitment.

- `FROM-MEMORY (unverified)` — WCAG 2.2, Error Prevention (Legal, Financial, Data): https://www.w3.org/WAI/WCAG22/Understanding/error-prevention-legal-financial-data.html
- `FROM-MEMORY (unverified)` — GOV.UK Design System, “Check answers”: https://design-system.service.gov.uk/patterns/check-answers/

### 2. Measurable rule

The fairest default is **pay-on-submission readiness**:

- The four-question verdict is free.
- The user sees IDR 790,000 before uploading.
- Bali Zero checks the passport before requesting payment.
- The user reviews all extracted and supplied facts.
- Payment is requested only when Bali Zero is ready to submit.
- Payment and submission are distinct ledger events.
- Any price change before payment requires a new review screen; any non-customer-caused increase after payment is borne by Bali Zero.
- No application is promoted to payment-ready while a document warning or eligibility ambiguity remains unresolved.

The alternatives fail differently:

| Structure | Honest advantage | Main failure |
|---|---|---|
| Pay immediately after verdict | Low abandonment before upload; simple operations | Charges before Bali Zero knows whether the passport is usable |
| Pay after passport preflight | Money follows evidence; one clear checkout | Bali Zero bears the cost of reviewing non-buyers |
| Deposit, then balance | Shares review cost | Two charges and two refund boundaries look like fee fragmentation |
| Pay only after approval | Maximum buyer protection | Bali Zero finances government fees and assumes collection and refusal risk |

The recommended pre-payment copy is:

> **Total today: IDR 790,000.** This includes the government fee and Bali Zero’s service. We checked your passport before asking you to pay. After payment, we submit the application to Indonesian Immigration. Immigration alone decides approval.

Immediately beneath it:

> **If something goes wrong:** before submission, any cancelled or unsubmitable application is refunded under the cases shown below. After submission, any government fee already paid may be non-refundable. If refusal or loss was caused by Bali Zero’s error, Bali Zero refunds the full IDR 790,000. Approval is never guaranteed.

The phrase “may be non-refundable” is intentionally provisional here: the production copy must replace it with the verified rule and exact refundable amount. A vague legal footnote is not acceptable. The interface needs a matrix for: customer cancellation, failed document check, duplicate charge, Bali Zero error, government-system outage and Immigration refusal.

### 3. What to steal for Bali Zero

On GARUDA VOA, move the payment boundary to after passport verification. On Visa Oracle, make the price a quote—not a payment request—and carry it forward. On the home page, “the price is the whole price” can link to the actual refund matrix rather than a marketing assurance.

### 4. What to avoid

Avoid “100% secure payment,” shield icons and refund promises without cases. Security badges do not explain who keeps IDR 790,000 after refusal. Avoid splitting “government fee” into a late checkout addition; the all-inclusive price is a core trust promise. Also avoid “pay only if approved” unless Bali Zero truly accepts financing and collection risk.

## Finding 3 — Four questions can triage; they cannot eliminate uncertainty

### 1. Named example

The official US ESTA service is a relevant structural example because it separates trip and passport eligibility questions from the government decision. It is not evidence for Indonesian rules.

- `FROM-MEMORY (unverified)` — US Customs and Border Protection, ESTA: https://esta.cbp.dhs.gov/
- `FROM-MEMORY (unverified)` — GOV.UK Design System, “Question pages”: https://design-system.service.gov.uk/patterns/question-pages/

### 2. Measurable rule

Use four semantic questions, even if a question contains two tightly related fields:

1. **“Which country issued the passport you will travel with?”**  
   Ask about the actual travel document, not abstract citizenship. If the user has two passports, require selection of one.

2. **“What type of passport is it, and when does it expire?”**  
   Collect document type and an exact expiry date. The rules engine calculates validity at arrival; never ask the customer to interpret a legal threshold.

3. **“When and where will you enter Indonesia?”**  
   Collect intended arrival date and checkpoint. Both are time-sensitive and must be rechecked when a paused case resumes.

4. **“What will you do in Indonesia, and when will you leave?”**  
   Use concrete purposes and a planned departure date. Do not ask buyers to choose a visa category they do not understand.

Before payment, the engine must resolve: travel-document eligibility, current nationality list, purpose, intended stay, arrival timing, checkpoint, passport-validity rule and any answer that creates a mandatory manual review. After eligibility—but before submission—collect identity fields, passport image, contact information and other application evidence.

The answer “it depends” is a legitimate product state:

> **We cannot decide this safely online.** Your trip may still be possible, but one detail needs a person to check it. No payment has been taken. Send this case to [name] on WhatsApp or request a reply by [service-level time].

The “no” branch should say:

> **GARUDA VOA does not support this trip based on your planned [purpose/date/passport].** You have not been charged and do not need to upload your passport. Review the answer or ask us to check another route.

Show alternatives only after a human or rules engine has established that they are plausible. An unsupported user should not be upsold automatically into a more expensive product.

### 3. What to steal for Bali Zero

Let Visa Oracle own the four questions and pass a signed answer snapshot into GARUDA VOA. Replace the blunt verdict “supported” with:

> **Supported by your answers**  
> Next: we check the passport before you pay.

Every answer remains editable until final review. Editing a decisive answer invalidates the old verdict and recomputes the quote; it does not preserve a flattering green badge.

### 4. What to avoid

Avoid legal jargon, visa-index questions, or “Are you eligible?”—that asks the customer to perform Bali Zero’s job. Avoid using passport upload as a hidden fifth eligibility question after payment. Avoid an optimistic default when the rules service is unavailable; operational uncertainty must produce manual review, not approval theatre.

## Finding 4 — Trust is determined by information order

### 1. Named example

Nielsen Norman Group’s usability heuristics—visibility of system status, user control, error prevention and correspondence with the real world—remain useful because they describe durable interaction failures rather than a visual trend. GOV.UK confirmation pages similarly distinguish “received” from “completed.”

- `FROM-MEMORY (unverified)` — Nielsen Norman Group, “10 Usability Heuristics”: https://www.nngroup.com/articles/ten-usability-heuristics/
- `FROM-MEMORY (unverified)` — GOV.UK Design System, “Confirmation pages”: https://design-system.service.gov.uk/patterns/confirmation-pages/

Both are older foundations; their continued value is that money, status and correction still require the same cognitive clarity.

### 2. Measurable rule

The sequence should be:

1. Identify Bali Zero and the exact service.
2. State that Immigration decides.
3. Explain the four-question check.
4. Complete the check.
5. Show provisional verdict, IDR 790,000 total, inclusions and refund boundary.
6. Show a named human and support channel.
7. Explain why the passport is needed, who sees it and how long it is retained.
8. Upload and verify the passport.
9. Show a complete editable review.
10. Take payment.
11. Issue payment receipt.
12. Issue a distinct government-submission receipt.
13. Track waiting, requests, approval or refusal.

Before any personal data, the buyer must be able to answer: Who is this company? What will it do? What will it cost? What is not guaranteed? What happens if it cannot submit? Why is my passport needed?

The price must appear before passport upload. Hiding it until after upload exploits sunk effort and resembles the scam pattern the user already fears. Showing payment before passport verification creates the opposite failure: money moves before Bali Zero knows whether it can perform.

### 3. What to steal for Bali Zero

Put the named case owner beside the passport request, even if formal assignment occurs after payment: “Ari’s visa team checks this before you pay.” Give WhatsApp as an escape hatch without making it the only record. The case page remains the authoritative ledger; WhatsApp links back to it.

On the home page, replace generic trust badges with a link to an anonymized example timeline: checked, paid, submitted, decision. Operational transparency is stronger proof than decorative security claims.

### 4. What to avoid

Avoid premature celebration—confetti after payment, “You’re all set,” or a large green check before government submission. Payment success is not visa success. Avoid urgency timers unless the quote or legal deadline genuinely expires. Avoid requesting a passport merely to reveal the price.

## Finding 5 — Waiting is part of the purchased service

### 1. Named example

Traveloka’s help and order-status model is locally relevant: customers buying time-dependent travel services expect a durable order record, notification and a route to intervention when the supplier is still processing.

- `FROM-MEMORY (unverified)` — Traveloka Indonesia Help Centre: https://www.traveloka.com/en-id/help

### 2. Measurable rule

Every waiting screen must display:

- Current state in plain language.
- Last material update with absolute date and local time.
- The next actor: customer, Bali Zero, payment provider or Immigration.
- The next expected event.
- A range or “no reliable estimate,” never false precision.
- The exact time Bali Zero will investigate if nothing changes.
- A named support route and case ID.
- Notification controls for email and WhatsApp.
- No invented activity such as “an agent is reviewing” unless an accountable person has accepted the task.

A polling animation is not progress. If the underlying status does not change, the screen should say so honestly.

### 3. What to steal for Bali Zero

Turn tracking into the main post-payment product. The customer should be able to leave for three days and return to the same case history. When Immigration requests more information, show the original request, deadline, uploaded response and Bali Zero’s confirmation as separate events.

### 4. What to avoid

Avoid percentage-complete indicators for external government review. Avoid “usually approved in X days” presented as a promise. Avoid support messages that live only in one employee’s WhatsApp history; they must be summarized into the case ledger.

## Finding 6 — The strongest objection: self-service may be the wrong trust architecture

### 1. Named example

WhatsApp Business is the de facto conversational surface for many Indonesian service transactions. Its strength is not sophisticated workflow; it is identity, familiarity, asynchronous voice notes and access to a person in an uncertain purchase.

- `FROM-MEMORY (unverified)` — WhatsApp Business: https://www.whatsapp.com/business/

### 2. Measurable rule

The case against GARUDA VOA self-service is strong:

- Visa eligibility is high-consequence and rules change.
- Buyers may not distinguish a provisional eligibility result from approval.
- A passport upload to an unfamiliar domain is a severe trust request.
- Four questions necessarily compress edge cases.
- WhatsApp permits clarification in the customer’s own language.
- A human can notice family context, dual passports, unusual travel documents or contradictory dates before the system creates false confidence.
- For a service premium above the government fee, human reassurance may be part of what the customer believes they are buying.

Test the objection rather than debating taste. Randomly route eligible traffic, with consent, into:

- Structured self-service with visible human escape hatch.
- Human-first WhatsApp with the same total price and eligibility policy.

Compare completed submissions, time to submission, manual minutes per completed case, document-rework rate, refund rate, duplicate-payment rate, support contacts, abandonment before upload and post-payment complaint rate. Segment by language, device speed, family versus solo traveller and returning versus first-time visitor. “Conversion” alone is insufficient if the winning lane produces more wrong applications or support cost.

### 3. What to steal for Bali Zero

Use a hybrid gate:

- Green, exact answers: continue self-service.
- Yellow, ambiguous or conflicting answers: human review before upload or payment.
- Red, unsupported: clear refusal of this product plus human route for alternatives.
- Human help remains visible on every screen.
- The structured case record survives any switch to WhatsApp, so the customer does not repeat the story.

This preserves the speed and auditability of self-service without pretending automation can safely own every judgment.

### 4. What to avoid

Avoid two bad extremes: a bot disguised as a human, or an unstructured WhatsApp funnel where pricing, consent and refund promises vary by agent. Human-first may convert because it feels safer, but without a shared case record it also creates undocumented promises, passport files in chat histories and inconsistent legal explanations.

The self-service flow is therefore not wrong if it is a narrow green lane with an honest human off-ramp. It is wrong if “four questions” is treated as permission to automate ambiguity.

## What I could not verify

- The current 2026 list of nationalities, passport types and Indonesian entry checkpoints eligible for e-VOA.
- The current passport-validity, intended-stay, purpose, onward-travel and application-timing rules.
- Whether IDR 790,000 still contains the correct government fee and how the remaining service component is legally represented.
- Whether the government fee is refundable before submission, after submission, after technical failure or after Immigration refusal.
- Bali Zero’s actual refund policy, error-remedy policy and authority to promise a full refund when its own mistake causes loss.
- Whether Bali Zero can operationally complete passport preflight before payment, and the sustainable service-level time for that check.
- The expiry, settlement, duplicate-payment, refund and chargeback behaviour of the specific QRIS, BCA/Mandiri virtual-account and card providers.
- Current Indonesian personal-data requirements for passport collection, access logging, storage location, retention and deletion.
- Whether a shared resume link may lawfully expose any case status before email, phone or one-time-password verification.
- Current contents and availability of every URL cited above; all ten sources are `FROM-MEMORY (unverified)` because this lane prohibited live web access.
- Any controlled evidence that self-service converts better than a human-first WhatsApp journey for Bali Zero’s actual audience. The proposed experiment is required before trusting that conclusion.