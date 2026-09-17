"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppFrame, AppWhatsAppCTA, useFunnelApp } from "@balizero/core";
import { formatIDR } from "@balizero/core/utils";
import { buildWhatsAppLink } from "@/lib/whatsapp-utm";
import { readCheckoutHandoff } from "../../checkoutHandoff";
import { useCheckout } from "./useCheckout";
import type { Applicant } from "../../orders/types";

/**
 * GARUDA VOA — checkout (`/visa/voa/checkout/{resultId}`). Owner decision 7(b): ONE
 * all-inclusive price, never split into fee + PNBP anywhere the customer can see. This
 * page never fetches or renders a price breakdown itself — the price only appears once,
 * on the order tracker, as the single `price_idr` the contract returns (the
 * `paymentsLive={false}` panel below fetches that SAME single figure to remind the
 * customer of it while payment isn't live, never a breakdown).
 *
 * `full_name` / `passport_number` come from the upload/review step
 * (`../../checkoutHandoff.ts`) when it's present. When it's missing (customer skipped
 * upload, or the document store is unavailable — see `flag.ts`'s payment-switch doc for
 * why the funnel can't just dead-end there), this page collects them directly instead of
 * bouncing the customer back to upload: their passport photo goes to the team after
 * payment instead. `email` / `phone` are always collected here because `Applicant`
 * (openapi.yaml) requires them and neither the eligibility check nor the upload step ever
 * asked for them.
 */
export function CheckoutFlow({
  resultId,
  paymentsLive,
}: {
  resultId: string;
  paymentsLive: boolean;
}) {
  const router = useRouter();
  const tracker = useFunnelApp("visa_voa");
  const { state, submit } = useCheckout(resultId);
  const [fullName, setFullName] = useState("");
  const [passportNumber, setPassportNumber] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [handoffPresent, setHandoffPresent] = useState(false);

  // Checkout attempt: the funnel's money step. Never the applicant's own
  // values — field names only, matching the wizard/visa-match pattern.
  useEffect(() => {
    if (state.step === "error") {
      tracker.formSubmitFailed("/api/visa/voa/orders", state.httpStatus);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state]);

  useEffect(() => {
    const handoff = readCheckoutHandoff(resultId);
    if (handoff.full_name && handoff.passport_number) {
      setFullName(handoff.full_name);
      setPassportNumber(handoff.passport_number);
      setHandoffPresent(true);
    }
  }, [resultId]);

  // A created order never stays on this page — awaiting_payment hands off to the
  // provider, anything else (already paid/failed/expired/refunded on replay) hands off
  // to the tracker, which is the only place order state is rendered from. This page
  // must never itself render a success state off a 201 response.
  useEffect(() => {
    if (state.step !== "created") return;
    const { order } = state;
    if (order.order_state === "awaiting_payment" && order.checkout_url) {
      window.location.href = order.checkout_url;
      return;
    }
    router.replace(`/visa/voa/orders/${order.order_id}`);
  }, [state, router]);

  if (!paymentsLive) {
    return <PaymentActivatingPanel resultId={resultId} tracker={tracker} />;
  }

  const applicant: Applicant = {
    full_name: fullName,
    email,
    phone,
    passport_number: passportNumber,
  };
  const canSubmit =
    fullName.trim().length > 0 &&
    passportNumber.trim().length > 0 &&
    email.trim().length > 0 &&
    phone.trim().length > 0 &&
    state.step !== "submitting" &&
    state.step !== "created";

  return (
    <AppFrame
      funnel="visa"
      title="Checkout"
      subtitle="A few details and you're set."
      footer="One all-inclusive price. Government fees, where they apply, are never billed separately from this figure."
    >
      <form
        style={{
          display: "grid",
          gap: "var(--space-3, 0.9rem)",
          maxWidth: 420,
        }}
        onSubmit={(e) => {
          e.preventDefault();
          if (canSubmit) {
            tracker.formSubmitted(Object.keys(applicant));
            void submit(applicant);
          }
        }}
      >
        {handoffPresent ? (
          <>
            <ReadOnlyField label="Full name" value={fullName} />
            <ReadOnlyField label="Passport number" value={passportNumber} />
          </>
        ) : (
          <>
            <p
              style={{
                margin: 0,
                fontSize: "0.9rem",
                color: "var(--color-text-muted)",
              }}
            >
              No upload needed now — you&apos;ll send a photo of your passport
              page to our team after payment.
            </p>
            <label
              htmlFor="voa-checkout-full-name"
              style={{ display: "grid", gap: "0.3rem" }}
            >
              <span style={{ fontSize: "0.95rem", fontWeight: 600 }}>
                Full name (as in passport)
              </span>
              <input
                id="voa-checkout-full-name"
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                style={inputStyle}
              />
            </label>
            <label
              htmlFor="voa-checkout-passport-number"
              style={{ display: "grid", gap: "0.3rem" }}
            >
              <span style={{ fontSize: "0.95rem", fontWeight: 600 }}>
                Passport number
              </span>
              <input
                id="voa-checkout-passport-number"
                type="text"
                required
                value={passportNumber}
                onChange={(e) => setPassportNumber(e.target.value)}
                style={inputStyle}
              />
            </label>
          </>
        )}

        <label
          htmlFor="voa-checkout-email"
          style={{ display: "grid", gap: "0.3rem" }}
        >
          <span style={{ fontSize: "0.95rem", fontWeight: 600 }}>Email</span>
          <input
            id="voa-checkout-email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            style={inputStyle}
          />
        </label>

        <label
          htmlFor="voa-checkout-phone"
          style={{ display: "grid", gap: "0.3rem" }}
        >
          <span style={{ fontSize: "0.95rem", fontWeight: 600 }}>Phone</span>
          <input
            id="voa-checkout-phone"
            type="tel"
            required
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+62…"
            style={inputStyle}
          />
        </label>

        {state.step === "error" ? (
          <p
            role="alert"
            style={{
              margin: 0,
              color: "var(--tx-pure)",
              borderLeft: "3px solid var(--bz-border)",
              paddingLeft: "0.75rem",
            }}
          >
            {state.message}
          </p>
        ) : null}

        <button
          type="submit"
          disabled={!canSubmit}
          style={{
            padding: "0.9rem 1.4rem",
            borderRadius: 8,
            border: "none",
            background: "var(--accent-funnel, #ff3344)",
            color: "#0a0a0a",
            fontWeight: 600,
            cursor: canSubmit ? "pointer" : "default",
            opacity: canSubmit ? 1 : 0.5,
          }}
        >
          {state.step === "submitting" || state.step === "created"
            ? "Preparing checkout…"
            : "Continue to payment →"}
        </button>
      </form>
    </AppFrame>
  );
}

/**
 * `GARUDA_PAYMENTS_LIVE=false` view. Card payment (Xendit) is awaiting provider approval
 * and production still runs a sandbox key — this panel never renders the order form and
 * never calls `createOrder`, so no `checkout_ready_email` (with a sandbox link) is ever
 * enqueued for a real tourist. The customer instead finishes on WhatsApp, at the same
 * price, with the team.
 */
function PaymentActivatingPanel({
  resultId,
  tracker,
}: {
  resultId: string;
  tracker: ReturnType<typeof useFunnelApp>;
}) {
  const [priceIdr, setPriceIdr] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await fetch(
          `/api/visa/voa/eligibility-checks/${resultId}`,
          { credentials: "include" },
        );
        if (!res.ok) return;
        const body = (await res.json()) as {
          verdict?: string;
          price_idr?: number;
        };
        if (
          !cancelled &&
          body.verdict === "ACCEPT" &&
          typeof body.price_idr === "number"
        ) {
          setPriceIdr(body.price_idr);
        }
      } catch {
        // Never invent a number — the panel simply omits the price line.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [resultId]);

  // No name, passport number, email or phone in this message — the customer's own
  // identity crosses to WhatsApp only once they send it themselves.
  const whatsappHref = buildWhatsAppLink(
    "visa",
    `Hi Bali Zero, I completed my Visa on Arrival application online (ref ${resultId.slice(0, 8)}) and I'm ready to pay.`,
  );

  return (
    <AppFrame
      funnel="visa"
      title="Payment"
      subtitle="You're ready — card payment is being switched on."
      footer="One all-inclusive price. Government fees, where they apply, are never billed separately from this figure."
    >
      <div
        style={{
          display: "grid",
          gap: "var(--space-3, 0.9rem)",
          maxWidth: 420,
        }}
      >
        {priceIdr !== null ? (
          <p role="status" style={{ margin: 0, lineHeight: 1.6 }}>
            {`Your application is ready and your price is held: ${formatIDR(priceIdr)} all-inclusive.`}
          </p>
        ) : null}
        <p
          role={priceIdr === null ? "status" : undefined}
          style={{ margin: 0, lineHeight: 1.6 }}
        >
          Online card payment opens here very soon. Finish now with our team on
          WhatsApp — same price, same steps, nothing extra to pay.
        </p>
        {/* AppWhatsAppCTA, not a bare wa.me link: it records a lead_intents row under
            `garuda_voa` before opening WhatsApp, so a tourist who reached payment while
            card collection is off is a lead the team can find, not a lost click. If the
            capture call fails the component still opens WhatsApp. */}
        <AppWhatsAppCTA
          source="garuda_voa"
          headline="Finish with our team"
          description="Same practice, same price — a consultant completes the payment step with you."
          context={{ step: "payment_activating" }}
          whatsappContext={[
            { label: "Step", value: "Payment" },
            { label: "Ref", value: resultId.slice(0, 8) },
            ...(priceIdr !== null
              ? [{ label: "Price", value: formatIDR(priceIdr) }]
              : []),
          ]}
          defaultLabel="Continue on WhatsApp →"
          onCaptured={({ leadIntentId }: { leadIntentId: string }) => {
            tracker.ctaClicked("voa_payment_activating_whatsapp", "wa.me");
            tracker.whatsappHandoff(leadIntentId);
          }}
        />
        <noscript>
          <a href={whatsappHref}>Continue on WhatsApp →</a>
        </noscript>
      </div>
    </AppFrame>
  );
}

function ReadOnlyField({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "grid", gap: "0.3rem" }}>
      <span style={{ fontSize: "0.95rem", fontWeight: 600 }}>{label}</span>
      <span
        style={{
          padding: "0.6rem 0.7rem",
          borderRadius: 4,
          border: "1px solid var(--color-border-subtle)",
          background: "var(--surface-raised)",
          color: "var(--text-primary)",
        }}
      >
        {value}
      </span>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  padding: "0.6rem 0.7rem",
  borderRadius: 4,
  border: "1px solid var(--color-border-subtle)",
  background: "var(--surface-raised)",
  color: "var(--text-primary)",
  fontSize: "1rem",
};
