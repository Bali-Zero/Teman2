"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppFrame, useFunnelApp } from "@balizero/core";
import { readCheckoutHandoff } from "../../checkoutHandoff";
import { useCheckout } from "./useCheckout";
import type { Applicant } from "../../orders/types";

/**
 * GARUDA VOA — checkout (`/visa/voa/checkout/{resultId}`). Owner decision 7(b): ONE
 * all-inclusive price, never split into fee + PNBP anywhere the customer can see. This
 * page never fetches or renders a price breakdown itself — the price only appears once,
 * on the order tracker, as the single `price_idr` the contract returns.
 *
 * `full_name` / `passport_number` come from the upload/review step
 * (`../../checkoutHandoff.ts`) — never re-typed here. `email` / `phone` are collected
 * here because `Applicant` (openapi.yaml) requires them and neither the eligibility
 * check nor the upload step ever asked for them.
 */
export function CheckoutFlow({ resultId }: { resultId: string }) {
  const router = useRouter();
  const tracker = useFunnelApp("visa_voa");
  const { state, submit } = useCheckout(resultId);
  const [fullName, setFullName] = useState("");
  const [passportNumber, setPassportNumber] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [missingHandoff, setMissingHandoff] = useState(false);

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
    if (!handoff.full_name || !handoff.passport_number) {
      setMissingHandoff(true);
      return;
    }
    setFullName(handoff.full_name);
    setPassportNumber(handoff.passport_number);
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

  if (missingHandoff) {
    return (
      <AppFrame
        funnel="visa"
        title="Checkout"
        subtitle="We need your reviewed passport details first."
      >
        <p>
          <a href={`/visa/voa/upload/${resultId}`}>
            Go back to upload your passport →
          </a>
        </p>
      </AppFrame>
    );
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
        <ReadOnlyField label="Full name" value={fullName} />
        <ReadOnlyField label="Passport number" value={passportNumber} />

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
          <p role="alert" style={{ margin: 0, color: "var(--color-error)" }}>
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
