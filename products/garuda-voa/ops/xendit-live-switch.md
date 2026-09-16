# GARUDA VOA — the Xendit live switch, and what card collection costs

> Written 2026-09-15 by mission W-L (Mini). Owner ruling D11 (Zero, 15/09): Xendit is awaiting
> approval; everything else ships to production; collection stays in sandbox behind a switch.

## 1. State on 2026-09-15 (measured on production with a synthetic applicant, no PII)

| step                                            | state                                                                                                                  |
| ----------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| eligibility check → price 750.000 → result page | live                                                                                                                   |
| magic-link email → session                      | live (email from `zantara@` in 6 s, exchange 303, session cookie set)                                                  |
| passport details → checkout                     | live once the checkout PR ships (typed details when upload is unavailable)                                             |
| order + Xendit invoice                          | **wired, but the key on Fly is a placeholder**: `POST /api/visa/voa/orders` answers `503 PAYMENT_PROVIDER_UNAVAILABLE` |
| paid webhook → practice on kita → tracker       | code live, never exercised (0 orders, 0 practices)                                                                     |

While payments are not live, the customer checkout shows «card payment is being switched on» and
hands off to WhatsApp with the lead captured. The browser does not create an order, so no
customer can receive a checkout email carrying a sandbox link.

## 2. The switch — three variable names, set together

| where                                                  | variable                       | value                                                                           |
| ------------------------------------------------------ | ------------------------------ | ------------------------------------------------------------------------------- |
| Fly `nuzantara-rag`                                    | `GARUDA_XENDIT_SECRET_KEY`     | the Xendit key (`xnd_development_…` for test mode, `xnd_production_…` for live) |
| Fly `nuzantara-rag`                                    | `GARUDA_XENDIT_CALLBACK_TOKEN` | the webhook verification token from the same Xendit mode                        |
| Fly `nuzantara-rag` **and** Vercel (mouth, Production) | `GARUDA_PAYMENTS_LIVE`         | `true` only for live; unset for sandbox                                         |

Two independent locks, enforced in `services/payments/xendit.py`: a production key without
`GARUDA_PAYMENTS_LIVE=true` is refused, and `GARUDA_PAYMENTS_LIVE=true` with a test key is refused.
Either mismatch leaves the order lane unwired (orders 503) and logs `configuration refused` — it
never sends a customer to the wrong kind of invoice. Vercel reads env at deploy time: redeploy the
production deployment after changing it.

Set secrets with hidden input, never on the command line:
`fly secrets import --stage -a nuzantara-rag` (paste `NAME=value` lines, Ctrl-D), then deploy.

In the Xendit dashboard, for the same mode: Settings → Webhooks → Invoices paid →
`https://nuzantara-rag.fly.dev/api/visa/voa/webhooks/payment`, and register `balizero.com` as an
allowed website (contract §4(c)(iv)).

**Order of operations.** (1) Test-mode keys on Fly, flag unset → run the synthetic sandbox
purchase (order → test card → webhook → practice on kita → tracker). (2) Only after that is green
and Xendit approves: live key + callback token on Fly, `GARUDA_PAYMENTS_LIVE=true` on Fly and
Vercel, redeploy both.

## 3. Card fees against the all-inclusive price

Sources: the signed Services Agreement v2026.03 (accepted 2026-09-14; SCHEDA on M5
`~/Desktop/logo/marketing/GARUDA-VOA/contracts/xendit/`) fixes the **Minimum Fee of USD 50 per
month** when the month's fees are lower, fees VAT-exclusive, and forbids surcharging the customer
(our fee is absorbed — compliant). The contract does not print card rates: it points to
xendit.co/en-id/pricing, which refused automated reads on 2026-09-15 (HTTP 403). Two rate figures
exist on disk and disagree, so both are shown:

- **A** — 3.5% + Rp 6.000 (`product.yaml` decision 1, as relayed at ratification);
- **B** — 2.9% + Rp 2.000 (`ops/decision-packets/01-payment-provider.md`, marked unconfirmed).

VAT 11% is added on the fee. PNBP Rp 500.000 is inside the price (decision 7(b); amount sourced
in `research/visa/2026-08-23-voa-product-regulatory-and-engine-audit.md` §1.2). USD 50 =
Rp 883.031 at 17.660,6 IDR/USD (open.er-api.com, 2026-09-15 00:02 UTC).

| per order            | fee + VAT (A)     | left after PNBP + fee (A) | fee + VAT (B)     | left (B)   |
| -------------------- | ----------------- | ------------------------- | ----------------- | ---------- |
| issuance Rp 750.000  | Rp 35.798 (4,77%) | Rp 214.202                | Rp 26.363 (3,52%) | Rp 223.638 |
| extension Rp 850.000 | Rp 39.682 (4,67%) | Rp 310.318                | Rp 29.582 (3,48%) | Rp 320.418 |

| issuance orders / month | margin after PNBP, fees and minimum top-up (A) | (B)          |
| ----------------------- | ---------------------------------------------- | ------------ |
| 5                       | Rp 269.836 (Rp 53.967 per order)               | Rp 269.836   |
| 10                      | Rp 1.519.836 (Rp 151.984 per order)            | Rp 1.519.836 |
| 20                      | Rp 4.019.836 (Rp 200.992 per order)            | Rp 4.019.836 |
| 40                      | Rp 8.568.100 (Rp 214.202 per order)            | Rp 8.945.500 |

Below the minimum the top-up makes both scenarios cost the same USD 50. The minimum stops
mattering at 28 issuance orders a month under A and 38 under B. Not included: team time,
refunds and chargebacks (always ours, plus a non-refundable fee), fees on failed attempts.

**Before selling:** read the real card rate in the dashboard and correct row A or B here.
