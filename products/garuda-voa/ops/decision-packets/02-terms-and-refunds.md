# Owner decision 2 — terms of sale and refund rule

> **This is a decision packet, not terms of service.** It lays out what can go wrong, who pays in
> each case, and the honest options — so Zero can decide. The binding customer-facing text must be
> drafted and signed off by an Indonesian-qualified lawyer (`TODO(legal)`); nothing here is legal
> prose and nothing here has been reviewed by counsel.

## 1. Failure taxonomy — every way a paid order fails to deliver

Money facts that apply to all rows:

- The price is one value the customer sees whole: IDR 790,000 issuance / 850,000 extension,
  resolved from an exact PricingTool catalogue key and never split on any customer-facing surface.
  **CORRECTED 2026-08-24 by the orchestrator, against this packet's own first draft**, which said
  the amount "already contains the PNBP government fee" and cited `product.yaml`. That citation
  pointed at a comment which was itself an inference: re-measured, the string "PNBP" appears zero
  times in the prices file, zero times in `pricing.py`, zero times anywhere in `garuda_flow`, and
  the VOA catalogue row carries no note at all. **Nothing on disk says whether 790,000 includes the
  government fee or sits on top of it**, and that difference decides whether a refund of "the full
  price" also returns money we already handed to the state. It is now owner decision 7(b). Every
  row below that turns on PNBP is written twice where the answer changes it.
  **ANSWERED 2026-08-25 by Zero, verbatim: "il prezzo include il PNBP".** The 790,000 / 850,000
  rows are all-inclusive — the traveller pays the government nothing further. Re-read row by row
  against that answer, **the disposition table below does not change**: its "PNBP status" column
  records whether the fee had been SPENT at that point in the practice, not whether it sits inside
  the price, and every full-refund row (1, 4, 5, 10) is a row where filing never happened and the
  fee was never paid. The doubled rows collapse to the inclusive reading; no text below is now
  unreachable, and this packet is signable as written. What the answer DOES move is margin, not
  policy: 790,000 is gross of the government fee, so the absorbed provider fee is charged against
  what remains after the state is paid.
- The payment provider fee (~3.5%, packet 1) is **NOT returned on a refund** (UNCONFIRMED until
  read off the live provider pricing page at signup, packet 1 §owner-steps). Every refund we issue
  costs us roughly IDR 27,650 even when the customer gets 100% back.
- The PNBP is spent at the moment of filing (PR-04, practice → `Submitted`). Whether Indonesian
  PNBP is refundable once paid: **UNCONFIRMED — `TODO(legal)`**; the working assumption everywhere
  below is that it is **not recoverable**.
- A refund is only real when the provider's refund webhook reconciles (OP-05/OP-06). Refunds never
  rewind the practice automatically (PR-F03); staff decide the practice side explicitly.
- Chargeback exposure runs ~120 days on foreign cards (packet 1); any "no refund" row below can
  still come back as a chargeback we must fight with evidence.

| #   | Failure case                                                                       | Fault                                          | Bali Zero has spent                     | PNBP status                                                                       | Proposed disposition                                                                                                                                                                  | Why                                                                                                                                                                    |
| --- | ---------------------------------------------------------------------------------- | ---------------------------------------------- | --------------------------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Documents never arrive / unusable; deadline passes                                 | Customer                                       | Staff time; provider fee lost on refund | Never paid (cannot file without documents)                                        | **Full refund** if the practice never left `Received`/`Blocked` pre-filing; owner may instead elect a retained admin portion — but that requires a number in the terms, `TODO(legal)` | Arguing over an undelivered service on a 790k ticket costs more in time and chargeback risk than the refund; the fee is the cost of the clean exit                     |
| 2   | Customer supplied wrong info (nationality, passport validity, dates); refused      | Customer                                       | Depends on when caught                  | Branch: caught in review before PR-04 → not paid; discovered after filing → spent | **Branch**: pre-filing → full refund; post-filing → none                                                                                                                              | Pre-filing the money is intact and ours to return; post-filing the government fee is gone because of the customer's own false statement                                |
| 3   | Immigration refuses the application, reason outside our control (PR-07 `Rejected`) | Nobody's                                       | Full filing work                        | Spent, unrecoverable (UNCONFIRMED)                                                | **None**                                                                                                                                                                              | The service sold is preparation + filing, and it was performed; this is the row that produces the angriest customers, so it must be stated pre-purchase in plain words |
| 4   | Bali Zero misses the filing deadline                                               | **Ours**                                       | Full work, wasted                       | Never paid (we missed it)                                                         | **Full refund, always, no branch**                                                                                                                                                    | Our fault is the one case with no honest alternative; refund plus a WhatsApp offer to fix it manually at no charge                                                     |
| 5   | Customer cancels before we file                                                    | Customer                                       | Staff time; provider fee lost           | Not yet paid                                                                      | **Full refund**                                                                                                                                                                       | This row _is_ the cut-off definition (§2); before filing, the money is whole                                                                                           |
| 6   | Customer cancels after we file (`Submitted`/`Approved`)                            | Customer                                       | Full filing work                        | Spent                                                                             | **None**                                                                                                                                                                              | The irreversible spend has happened at the customer's request; cancelling a filing already with the authority is not a service failure                                 |
| 7   | Customer never travels                                                             | Customer                                       | Full work; eVOA issued                  | Spent                                                                             | **None**                                                                                                                                                                              | The eVOA usability window (`EVOA_USABILITY_WINDOW_DAYS`) and the trip itself are the customer's risk once the visa is delivered                                        |
| 8   | eVOA issued; customer refused entry at the port                                    | Authority / customer                           | Full work; delivered                    | Spent                                                                             | **None**                                                                                                                                                                              | What was sold is issuance; admission at the border is the authority's decision and was never promised — the terms must say this explicitly, `TODO(legal)`              |
| 9   | Duplicate charge (OP-08)                                                           | **Operational error — ours or the provider's** | —                                       | —                                                                                 | **Not a policy question.** Full refund of the second charge, immediately, every time                                                                                                  | The state machine already treats it as an incident: journal `payment.duplicate_charge_detected`, one remediation case, staff paged. Policy text should not mention it  |
| 10  | Refund webhook arrives before its paid event (OP-05)                               | Provider ordering anomaly                      | Nothing                                 | Never paid                                                                        | **Full refund by construction**                                                                                                                                                       | The order goes terminal `refunded` with no practice released; the late paid event is quarantined (OP-F04). Nothing to decide                                           |

Two rows have a real branch — 1 and 2 pre-filing. Everything else collapses to one rule:
**before filing the money is returnable, after filing it is not; our fault is always a full refund.**

## 2. The one number to choose: the cancellation cut-off

**Proposal: the cut-off is the PR-04 transition.** A cancellation requested while the practice is
in `not_started`, `Received`, `In review`, or `Blocked` (resume target `In review`) is a **full
refund**. Once the practice is `Submitted` (or later), there is **no cancellation refund**.

Anchored to state, not to hours: `Submitted` is a journal-backed, observable fact with filing
evidence attached (PR-04 guard). A clock-based cut-off ("24 hours after payment") is arguable with
a customer and misaligned with the actual spend, which happens at filing, not at time T.

The consequence to accept: staff must be able to see a pending cancellation request before
advancing PR-04, and a race (customer cancels while staff is filing) resolves **in the customer's
favor if the request predates the PR-04 journal entry** — the journal is the arbiter. Owner
approves or moves this line.

## 3. UU PDP posture — consent and cross-border

Article numbers cited below are from UU No. 27 Tahun 2022 (UU PDP). Exact subsection numbering is
**UNCONFIRMED** where noted — verify against the official text before any of this reaches a
customer-facing page.

**At the point of submission.** The funnel already gates on this (happy-path and retention feature
files): before anything is persisted, the customer sees a policy-derived notice and must
explicitly acknowledge it — acknowledgement is not inferred from page view, button press, or a
preselected control. The notice must state, in plain language:

- what is collected: name, passport number, passport photo (read by OCR), email, phone;
- why: to assess VOA eligibility, and — if they buy — to prepare and file the application;
- how long it is kept: 90 days, per decision packet 3 (reference only — that packet owns the number);
- that they can delete their result themselves (below);
- where the data is processed (see cross-border).

Legal basis: consent (Art. 20) is what the funnel currently operationalizes for the pre-purchase
check; whether the paid-order side should instead rely on contractual necessity under Art. 20 is a
counsel question — **UNCONFIRMED, `TODO(legal)`**. Note that a passport photo and travel document
data may fall under UU PDP's "specific" (sensitive) personal-data category (Art. 4 — exact
classification of travel documents **UNCONFIRMED**), which narrows the lawful bases and raises the
bar for consent (Art. 22 lists what valid consent must disclose; subsection numbering
UNCONFIRMED).

**Retention.** 90 days as proposed in decision packet 3 — not re-decided here. One friction to be
aware of: card chargebacks can arrive up to ~120 days out (packet 1), and packet 3 itself flags
150 days as the alternative for exactly this reason. That tension lives in packet 3; this packet
only notes that the refund/chargeback evidence window depends on it.

**Customer rights and the self-service delete.** The result page carries a delete control that
completes without an email round trip (self-service-deletion feature). What it removes: the result
row, the answers, contact data, the session binding, and derived per-result fields — leaving only
coarse monthly aggregate counts. What it does **not** remove: anything created after purchase —
the order, payment record, practice, and any statutory records. The deletion feature is explicitly
scoped to results from which "no order, payment, practice, or statutory record has been created."
Post-purchase erasure is therefore a staff-mediated request, and transaction records may need to
survive for tax obligations regardless (Indonesian tax record-keeping is commonly cited as 10
years under UU KUP Art. 28 — **UNCONFIRMED, `TODO(legal)`**). The customer-facing notice must not
promise deletion we cannot deliver. The rights themselves — access, rectification, erasure,
consent withdrawal — are UU PDP Arts. 5–13 range (right to erasure commonly cited as Art. 8;
exact mapping **UNCONFIRMED**). Exercise path: self-service for the result, WhatsApp/staff request
for the rest; sanctions exposure for ignoring them runs to administrative fines up to 2% of annual
revenue (commonly cited as Art. 57 — **UNCONFIRMED**).

**Cross-border (the important one).** OCR is local-first by guardrail G-OCR-LOCAL; cloud
reinforcement, if ever invoked, receives only redacted material behind an enforceable egress gate
(SM-G10). As long as redaction actually removes identifying material, no cross-border transfer of
personal data occurs. **If any cloud model ever sees identifiable customer data, UU PDP Art. 56
applies as a cascade**, in this order:

1. the recipient country has equal or higher personal-data protection (adequacy);
2. failing that, an adequate and binding safeguard protects the transfer;
3. failing both, the data subject's **explicit consent** to the transfer.

Before that path is ever used, Bali Zero would need, at minimum (`TODO(legal)` for the exact
instruments — do not assume any of this exists today):

- a documented transfer assessment naming the recipient country and its adequacy status;
- if adequacy fails: a binding safeguard instrument with the vendor (e.g., contractual clauses
  meeting the "adequate and binding" standard of Art. 56 — the exact recognized instrument list is
  **UNCONFIRMED**) and a signed data-processing agreement with that vendor;
- if both fail: a separate, explicit transfer consent captured at intake — the generic submission
  acknowledgement is not enough;
- the privacy notice updated to name the transfer, the destination, and the safeguard.

The honest default is simpler: keep the redaction gate unbypassable and never use the Art. 56
path. That is a decision the owner makes once, here, rather than per-incident.

## 4. What the owner must personally do

1. **Approve or move the cut-off** (§2): full refund until the practice reaches `Submitted`.
2. **Pick dispositions for the two open rows** (§1, rows 1 and 2 pre-filing): full refund, or a
   retained admin portion — if the latter, supply the number for counsel to write.
3. **Decide the Art. 56 posture**: ban identifiable-data cloud egress outright (recommended, and
   it is what G-OCR-LOCAL already implies), or commission the transfer instruments before any use.
4. **Commission the real documents**: terms of sale, refund policy, and privacy notice, drafted or
   reviewed by an Indonesian-qualified lawyer from this packet — including the PNBP refundability
   answer, the UU PDP article verification, the tax-record retention rule, and the sensitive-data
   classification of passport data (all marked `TODO(legal)` above).
5. **Set the operational refund authority**: who on staff may trigger a refund in the provider
   dashboard, and confirm the rolling IDR reserve for chargebacks from packet 1 covers the
   refund-heavy rows (4, 5, and chargebacks on row 3).
6. **Sign** — nothing in this file is customer-facing until items 3 and 4 are done.
