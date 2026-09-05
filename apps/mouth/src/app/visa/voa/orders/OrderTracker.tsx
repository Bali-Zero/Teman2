"use client";

import { AppFrame } from "@balizero/core";
import { formatIDR } from "@balizero/core/utils";
import { buildWhatsAppLink } from "@/lib/whatsapp-utm";
import { humanizePracticeKey } from "./messages";
import { useOrderTracking } from "./useOrderTracking";
import type { OrderView, PracticeState } from "./types";

/**
 * GARUDA VOA — order tracker + visa delivery view (`/visa/voa/orders/{orderId}`).
 *
 * "Parcel tracker" is the mandate's own word: a customer reads their state the way
 * they read a delivery-tracking page, ending in "delivered". There is no separate
 * artifact-download endpoint in the frozen contract (`OrderView`/`PracticeView` only
 * ever carry `artifact_available: boolean` — see openapi.yaml line ~1258: "no document
 * identifier or capability is placed in a URL"), so this single page IS the delivery
 * page once `practice.state === "Delivered"` rather than a second route pointed at a
 * read operation that doesn't exist. `DeliveredPanel` below is the addressable,
 * independently-tested unit that satisfies that build item.
 *
 * `order_state` from `getOrderAndPractice` is the ONLY thing this page ever treats as
 * authoritative for payment. `browser_observation` is rendered as a "confirming…"
 * hint at most — never as success (contract: "Browser-return observation is
 * non-authoritative; only signed webhook reconciliation can show paid").
 */
export function OrderTracker({ orderId }: { orderId: string }) {
  const { state, retry } = useOrderTracking(orderId);

  if (state.step === "loading") {
    return (
      <AppFrame
        funnel="visa"
        title="Your Visa on Arrival"
        subtitle="Checking your order…"
      >
        <p style={{ color: "var(--color-text-muted)" }}>One moment.</p>
      </AppFrame>
    );
  }

  if (state.step === "error") {
    return (
      <AppFrame
        funnel="visa"
        title="Your Visa on Arrival"
        subtitle="We couldn't load your order."
      >
        <p role="alert" style={{ margin: 0, color: "var(--color-error)" }}>
          {state.message}
        </p>
        {state.retryable ? (
          <button
            type="button"
            onClick={retry}
            style={{
              padding: "0.9rem 1.4rem",
              borderRadius: 8,
              border: "none",
              background: "var(--accent-funnel, #ff3344)",
              color: "#0a0a0a",
              fontWeight: 600,
              cursor: "pointer",
              width: "fit-content",
            }}
          >
            Try again
          </button>
        ) : null}
        <WhatsAppHelp />
      </AppFrame>
    );
  }

  return <OrderTrackerReady order={state.order} />;
}

function OrderTrackerReady({ order }: { order: OrderView }) {
  const subtitle = subtitleFor(order);

  return (
    <AppFrame
      funnel="visa"
      title="Your Visa on Arrival"
      subtitle={subtitle}
      footer="One all-inclusive price. Government fees, where they apply, are never billed separately from this figure."
    >
      <div
        style={{
          display: "grid",
          gap: "var(--space-2, 0.5rem)",
        }}
      >
        <span style={{ fontSize: "0.85rem", color: "var(--color-text-muted)" }}>
          {order.order_state === "paid" ? "Total paid" : "Order total"}
        </span>
        <span style={{ fontSize: "1.6rem", fontWeight: 600 }}>
          {formatIDR(order.price_idr)}
        </span>
      </div>

      <ParcelSteps order={order} />

      {order.order_state === "awaiting_payment" ? (
        <AwaitingPaymentPanel />
      ) : null}

      {order.order_state === "failed" || order.order_state === "expired" ? (
        <ExceptionPanel
          heading={
            order.order_state === "failed"
              ? "This checkout couldn't be completed."
              : "This checkout session expired."
          }
          body="A consultant can verify your payment status before you try again."
        />
      ) : null}

      {order.order_state === "refunded" ? (
        <ExceptionPanel
          heading="This order was refunded."
          body="If you still need a Visa on Arrival, a consultant can start a new application with you."
        />
      ) : null}

      {order.order_state === "paid" && order.practice === null ? (
        <p
          aria-live="polite"
          style={{ margin: 0, color: "var(--color-text-muted)" }}
        >
          Payment confirmed — setting up your application now.
        </p>
      ) : null}

      {order.order_state === "paid" && order.practice ? (
        <PracticePanel practice={order.practice} />
      ) : null}
    </AppFrame>
  );
}

function subtitleFor(order: OrderView): string {
  if (order.order_state === "awaiting_payment") {
    return order.browser_observation === "browser_return_observed"
      ? "We're confirming your payment — this can take a minute."
      : "Complete your payment to start your application.";
  }
  if (order.order_state === "paid") {
    if (order.practice?.state === "Delivered") {
      return "Your visa has been delivered.";
    }
    return "Payment confirmed — here's where your application stands.";
  }
  if (order.order_state === "failed") return "Checkout couldn't be completed.";
  if (order.order_state === "expired") return "Checkout session expired.";
  if (order.order_state === "refunded") return "This order was refunded.";
  return "Tracking your Visa on Arrival application.";
}

const ORDER_STEP_ORDER: OrderView["order_state"][] = [
  "awaiting_payment",
  "paid",
];

const PRACTICE_STEP_ORDER: PracticeState[] = [
  "Received",
  "In review",
  "Submitted",
  "Approved",
  "Delivered",
];

/** A simple ordered progress list — like a parcel's "Placed → Picked up → Out for
 * delivery → Delivered" — never inventing a state the backend didn't send. `Blocked`
 * and `Rejected` are exception branches rendered separately (`PracticePanel` below),
 * not points on this happy-path line. */
function ParcelSteps({ order }: { order: OrderView }) {
  const isException =
    order.order_state === "failed" ||
    order.order_state === "expired" ||
    order.order_state === "refunded";
  if (isException) return null;

  const orderStepIndex = ORDER_STEP_ORDER.indexOf(
    order.order_state as (typeof ORDER_STEP_ORDER)[number],
  );
  const practiceState = order.practice?.state;
  const practiceStepIndex =
    practiceState && practiceState !== "Blocked" && practiceState !== "Rejected"
      ? PRACTICE_STEP_ORDER.indexOf(practiceState)
      : -1;

  const steps: { label: string; done: boolean; current: boolean }[] = [
    { label: "Order placed", done: true, current: false },
    {
      label: "Payment confirmed",
      done: orderStepIndex >= 1,
      current: orderStepIndex === 0,
    },
    ...PRACTICE_STEP_ORDER.map((label, i) => ({
      label,
      done: orderStepIndex >= 1 && practiceStepIndex > i,
      current: orderStepIndex >= 1 && practiceStepIndex === i,
    })),
  ];

  return (
    <ol
      aria-label="Application progress"
      style={{
        display: "grid",
        gap: "var(--space-2, 0.5rem)",
        listStyle: "none",
        margin: 0,
        padding: 0,
      }}
    >
      {steps.map((step) => (
        <li
          key={step.label}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.6rem",
            color:
              step.done || step.current
                ? "var(--text-primary, rgba(255,255,255,0.96))"
                : "var(--color-text-muted)",
            fontWeight: step.current ? 600 : 400,
          }}
        >
          <span aria-hidden="true">
            {step.done ? "✓" : step.current ? "●" : "○"}
          </span>
          <span>{step.label}</span>
        </li>
      ))}
    </ol>
  );
}

/**
 * `getOrderAndPractice`'s `OrderView` (unlike `createOrderFromCheck`'s `OrderCheckout`)
 * carries no `checkout_url` — the contract never lets this read-only view hand back a
 * live provider capability. A customer who lands here still `awaiting_payment` (e.g.
 * they closed the payment tab and came back later) therefore has no self-service resume
 * button this page can honestly render; a consultant reopening checkout for them is the
 * real path, not a link this component would have to invent.
 */
function AwaitingPaymentPanel() {
  return (
    <p style={{ margin: 0, color: "var(--color-text-muted)" }}>
      Haven&apos;t finished paying yet?{" "}
      <a
        href={buildWhatsAppLink(
          "visa",
          "Hi Bali Zero, I need help finishing payment for my Visa on Arrival order.",
        )}
        target="_blank"
        rel="noopener noreferrer"
      >
        A consultant can help you complete it →
      </a>
    </p>
  );
}

function PracticePanel({
  practice,
}: {
  practice: NonNullable<OrderView["practice"]>;
}) {
  if (practice.state === "Delivered") {
    return <DeliveredPanel practice={practice} />;
  }
  if (practice.state === "Blocked") {
    return (
      <ExceptionPanel
        heading="We need something from you before we can continue."
        body={
          practice.required_action_key
            ? humanizePracticeKey(practice.required_action_key)
            : "A consultant can tell you exactly what's needed."
        }
      />
    );
  }
  if (practice.state === "Rejected") {
    return (
      <ExceptionPanel
        heading="Your application couldn't be approved as submitted."
        body={
          practice.customer_reason_key
            ? humanizePracticeKey(practice.customer_reason_key)
            : "A consultant can review it with you and explain the options."
        }
      />
    );
  }
  return null;
}

/** The "visa delivery page" build item. Contract has no bytes-download operation for
 * the finished document (`artifact_available` is a boolean flag only) — delivery
 * happens through the existing practice channels (email/WhatsApp), not a link this
 * page can construct itself, so this panel confirms the state honestly rather than
 * fabricating a download it cannot back. */
function DeliveredPanel({
  practice,
}: {
  practice: NonNullable<OrderView["practice"]>;
}) {
  return (
    <section
      aria-label="Visa delivered"
      style={{
        display: "grid",
        gap: "var(--space-2, 0.6rem)",
        padding: "var(--space-3, 1rem)",
        borderRadius: 12,
        border: "1px solid var(--color-border-subtle)",
        background: "var(--surface-raised)",
      }}
    >
      <p style={{ margin: 0, fontWeight: 600 }}>
        Your Visa on Arrival has been delivered.
      </p>
      <p style={{ margin: 0, lineHeight: 1.6 }}>
        {practice.artifact_available
          ? "We've sent your document to the email on file. Check your inbox (and spam folder)."
          : "Our team is finalizing your document and will send it to your email shortly."}
      </p>
      <a
        href={buildWhatsAppLink(
          "visa",
          "Hi Bali Zero, I have a question about my delivered Visa on Arrival.",
        )}
        target="_blank"
        rel="noopener noreferrer"
        style={{
          display: "inline-block",
          width: "fit-content",
          padding: "0.7rem 1.1rem",
          borderRadius: 8,
          background: "#25D366",
          color: "#0a0a0a",
          textDecoration: "none",
          fontWeight: 600,
        }}
      >
        Questions? Continue on WhatsApp →
      </a>
    </section>
  );
}

function ExceptionPanel({ heading, body }: { heading: string; body: string }) {
  return (
    <section
      style={{
        display: "grid",
        gap: "var(--space-2, 0.6rem)",
        padding: "var(--space-3, 1rem)",
        borderRadius: 12,
        border: "1px solid var(--color-border-subtle)",
      }}
    >
      <p style={{ margin: 0, fontWeight: 600 }}>{heading}</p>
      <p style={{ margin: 0, lineHeight: 1.6 }}>{body}</p>
      <WhatsAppHelp />
    </section>
  );
}

function WhatsAppHelp() {
  return (
    <a
      href={buildWhatsAppLink(
        "visa",
        "Hi Bali Zero, I need help with my Visa on Arrival order.",
      )}
      target="_blank"
      rel="noopener noreferrer"
      style={{
        display: "inline-block",
        width: "fit-content",
        padding: "0.7rem 1.1rem",
        borderRadius: 8,
        background: "#25D366",
        color: "#0a0a0a",
        textDecoration: "none",
        fontWeight: 600,
      }}
    >
      Continue on WhatsApp →
    </a>
  );
}
