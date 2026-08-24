# Owner decision 1 — payment provider

> Prepared for Zero. Read the first line, then press one button. Researched by the Gemini seat,
> **corrected and re-costed by the orchestrator** against this product's real catalogue price —
> the research seat assumed a IDR 2,000,000 ticket, and the VOA sells for IDR 790,000.
>
> **Two things you need to know before the table, because they change the product, not just the
> integration:**
>
> 1. **Apple Pay cannot be offered.** Apple Pay has not launched as a payment service provider in
>    Indonesia, so no Indonesian gateway can present it — this is a market fact, not a provider
>    choice, and it holds for all three candidates. The mandate's promise says "card / Apple Pay /
>    Google Pay"; the deliverable is **card + Google Pay**. Nothing in the build should be sized
>    around Apple Pay, and no page should show its button.
> 2. **Fees eat 3.5% of this ticket.** At IDR 790,000 the all-in cost per foreign-card order is
>    about **IDR 27,650** (2.9% + IDR 2,000, plus 11% VAT on the fee). That is a real slice of a
>    790k all-inclusive price, and it is a margin question, not an engineering one — flagged here
>    rather than absorbed silently.
>
> **Every fee figure below is UNCONFIRMED until read off the provider's own live pricing page at
> signup.** The research seat did not cite sources for them, so they are treated as indicative:
> good enough to choose a provider, not good enough to quote a customer or size a budget. The
> owner-steps list ends with the step that confirms them.

**Recommendation:** Xendit. It provides industry-leading webhook reliability, native Google Pay on hosted checkouts, and clean API abstractions with identical fees to Midtrans for the methods we care about.

## Comparison Table

| Feature                | Xendit (RECOMMENDED)                                                                           | Midtrans                                                                        | Stripe (Indonesia)                 |
| :--------------------- | :--------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------ | :--------------------------------- |
| **Foreign Card Fee**   | 2.9% + IDR 2,000 (+ 11% VAT on fee)                                                            | 2.9% + IDR 2,000 (+ 11% VAT on fee)                                             | N/A (Does not support cards in ID) |
| **Local Methods Fee**  | QRIS: 0.7%, VA: ~IDR 4,000                                                                     | QRIS: 0.7%, VA: ~IDR 4,000                                                      | VA only (Invite-only preview)      |
| **Currency Handling**  | Charges in IDR; foreign bank converts & applies FX markup (cardholder bears it)                | Charges in IDR; foreign bank converts & applies FX markup (cardholder bears it) | N/A                                |
| **Apple / Google Pay** | Apple Pay: NO (unavailable in ID), Google Pay: YES (hosted checkout)                           | Apple Pay: NO, Google Pay: YES (Snap checkout)                                  | N/A                                |
| **Payout**             | IDR to ID bank; T+5 to T+7 days (Aggregator)                                                   | IDR to ID bank; T+2 to T+7 days                                                 | IDR to ID bank                     |
| **Onboarding**         | PT PMA Docs (NIB, NPWP, Akta, Director ID); ~2-5 days                                          | PT PMA Docs (NIB, NPWP, Akta, Director ID); ~3-7 days                           | Invite-only preview; Unknown TTL   |
| **Webhook Quality**    | Secret callback token (`x-callback-token`), exponential backoff retries, excellent idempotency | SHA512 signature, automatic retries up to 24h, good sandbox                     | Industry gold standard, but moot   |
| **Refunds**            | Partial supported; fee NOT returned                                                            | Partial supported; fee NOT returned                                             | N/A                                |

_Note: Apple Pay is fundamentally unavailable for domestic online checkouts through Indonesian payment gateways as it has not launched as a Payment Service Provider in Indonesia._

## What will bite us (Xendit)

1. **Chargeback exposure:** The service (VOA) is delivered days after payment. Foreign cardholders can issue chargebacks via their home bank up to 120 days later. Because Xendit settles in T+5 to T+7 days, a chargeback will instantly pull from our live balance, potentially causing a negative balance and halting further payouts.
   - **Mitigation:** Maintain a rolling IDR reserve buffer in the Xendit dashboard to absorb unexpected chargebacks without halting operations.
2. **Webhook signature gotchas & retries:** Xendit authenticates webhooks via a static verification token rather than a dynamic cryptographic signature, which requires strict constant-time string matching. Furthermore, if our server takes too long to process the VOA and doesn't return a 200 OK fast enough, Xendit will retry, potentially causing duplicate fulfillment.
   - **Mitigation:** Acknowledge the webhook immediately (HTTP 200) and process the actual fulfillment asynchronously, relying on our append-only payment journal to prevent duplicate processing.
3. **Currency Rounding on IDR:** IDR has no minor units (decimals). However, foreign card networks might attempt to authorize fractional equivalents. Sending a float to Xendit's API will cause the charge creation to fail.
   - **Mitigation:** Enforce strict integer casting (`Math.round` or `ceil`) and validation on the final IDR amount before calling the `create_intent` API.

## Cost at volume — re-costed at the real price

**The research seat's own table assumed a IDR 2,000,000 ticket and is superseded by this one.**
This product's catalogue price is IDR 790,000 for issuance and IDR 850,000 for the extension
(`services/garuda_flow/pricing.py`, resolved from PricingTool by exact key).

Per foreign-card order, at IDR 790,000:
`790,000 x 2.9% = 22,910` + `2,000` fixed = `24,910`, plus 11% VAT on the fee = **IDR 27,650**
(3.50% of the ticket). The extension at IDR 850,000 costs **IDR 29,582** (3.48%).

| Volume (orders/week) | Orders/month (x4) | Monthly fees, IDR |
| :------------------- | :---------------- | :---------------- |
| 10                   | 40                | 1,106,000         |
| 50                   | 200               | 5,530,000         |
| 200                  | 800               | 22,120,000        |

Local rails are dramatically cheaper where the buyer can use them — QRIS at 0.7% is about
IDR 5,500 on this ticket against IDR 27,650 on a foreign card, a 5x difference. Worth offering to
buyers already in Indonesia, and worth measuring the mix once live.

## What the owner must personally do

1. Create a Xendit account using the owner's email and configure Two-Factor Authentication.
2. Upload the PT PMA legal documents via the dashboard (NIB, NPWP, Akta Pendirian, SK Kemenkumham, and the Director's Passport/KITAS).
3. Connect the company's Indonesian IDR corporate bank account for settlement payouts.
4. Sign the digital Merchant Agreement (PKS) with Xendit to activate live mode.
5. Generate the API keys (Public, Secret, and Webhook Verification Token) in the dashboard.
   Put them in Fly secrets — never in the repo, never in a chat message.
6. **Read the live pricing page while you are in the dashboard and confirm the three numbers
   this packet treats as unconfirmed**: the foreign-card percentage, the fixed component, and
   whether VAT is charged on top of the fee. If any differs, tell the session — the cost table
   above is rebuilt from those three numbers alone.

## The provider-agnostic port

To ensure this decision remains REVERSIBLE, the code will be written against a provider-agnostic interface.

**Operations:**

- `create_intent(amount: int, currency: str, idempotency_key: str) -> PaymentIntent`
- `verify_webhook_signature(payload: str, signature: str) -> bool`
- `fetch_charge_status(charge_id: str) -> Status`
- `refund_charge(charge_id: str, amount: int) -> RefundResult`

**Invariants that must hold:**

- An `idempotency_key` must be provided on every `create_intent` operation.
- Cryptographic/Token signature verification must succeed before any state change is made.
- All state transitions are recorded in an append-only payment journal.
- An order transitions to `paid` ONLY from a successfully reconciled webhook and NEVER from a client-side browser redirect.
