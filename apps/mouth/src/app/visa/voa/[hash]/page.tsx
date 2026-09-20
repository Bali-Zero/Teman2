"use client";

import { useEffect, useRef, useState } from "react";
import {
  AppFrame,
  AppShareBar,
  AppStampReveal,
  AppWhatsAppCTA,
  useFunnelApp,
} from "@balizero/core";
import { formatIDR } from "@balizero/core/utils";
import { buildWhatsAppLink } from "@/lib/whatsapp-utm";
import { EmptyStampReveal } from "@/components/garuda/EmptyStampReveal";
import {
  buildDeclineEducation,
  primaryDeclineCode,
  type DeclineCode,
  type EligibilitySubmission,
} from "@/components/garuda/declineEducation";
import { VOA_PRIMARY_ACTION_STYLE } from "../voa-action-style";
import { NextSteps } from "../NextSteps";
import { SafeClockHero } from "../SafeClock";

/**
 * GARUDA VOA — public result page (owner decision 5, constraints 5a/5b).
 *
 * The API only ever returns `{verdict, reason_codes, ...}` — no PII, no
 * prose (contracts/openapi.yaml EligibilityResult). The DECLINE education
 * copy is built entirely client-side from the answers this browser tab
 * already holds (localStorage, written by the wizard before it submitted);
 * the backend is never asked to echo them back. See declineEducation.ts.
 */

interface AcceptedResult {
  verdict: "ACCEPT";
  reason_codes: [];
  published_filing_deadline?: string;
  price_idr: number;
}

interface DeclinedResult {
  verdict: "DECLINE";
  reason_codes: DeclineCode[];
}

type VoaResult = AcceptedResult | DeclinedResult;

/** Answers the wizard persisted client-side before submitting (see page.tsx persistKey). */
function readSubmittedAnswers(): EligibilitySubmission {
  const fallback: EligibilitySubmission = {
    case_type: "issuance",
    nationality: "",
    purpose: "tourism",
    travellers: 1,
    self_pay: true,
    extension_already_used: false,
  };
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem("bz.garuda_voa.wizard");
    if (!raw) return fallback;
    const parsed = JSON.parse(raw) as {
      values?: {
        case_type?: EligibilitySubmission["case_type"];
        purpose?: EligibilitySubmission["purpose"];
        trip?: {
          nationality?: string;
          travellers?: number;
          self_pay?: boolean;
        };
        dates?: { extension_already_used?: boolean };
      };
    };
    const v = parsed.values ?? {};
    return {
      case_type: v.case_type ?? fallback.case_type,
      nationality: v.trip?.nationality ?? fallback.nationality,
      purpose: v.purpose ?? fallback.purpose,
      travellers: v.trip?.travellers ?? fallback.travellers,
      self_pay: v.trip?.self_pay ?? fallback.self_pay,
      extension_already_used:
        v.dates?.extension_already_used ?? fallback.extension_already_used,
    };
  } catch {
    return fallback;
  }
}

export default function VoaResultPage({
  params,
}: {
  params: Promise<{ hash: string }>;
}) {
  const tracker = useFunnelApp("visa_voa", { trackView: false });
  const stampRef = useRef<HTMLDivElement | null>(null);
  const [hash, setHash] = useState<string | null>(null);
  const [data, setData] = useState<VoaResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [deleted, setDeleted] = useState(false);

  useEffect(() => {
    void params.then((p) => setHash(p.hash));
  }, [params]);

  useEffect(() => {
    if (!hash) return;
    void (async () => {
      try {
        const res = await fetch(`/api/visa/voa/eligibility-checks/${hash}`, {
          credentials: "include",
        });
        if (!res.ok) {
          setErr(
            "We couldn't find this check. It may have expired, or the link is wrong.",
          );
          return;
        }
        const result = (await res.json()) as VoaResult;
        setData(result);
        // Verdict + price shown together (they render on the same screen) —
        // one event covers both funnel steps the mandate names.
        tracker.resultViewed(hash);
      } catch {
        setErr("Network error. Please try again.");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hash]);

  if (deleted) {
    return (
      <AppFrame
        funnel="visa"
        title="Visa on Arrival"
        subtitle="This check has been deleted."
      >
        <p>
          <a href="/visa/voa">Start again →</a>
        </p>
      </AppFrame>
    );
  }

  if (err) {
    return (
      <AppFrame funnel="visa" title="Visa on Arrival" subtitle={err}>
        <p>
          <a href="/visa/voa">Start again →</a> or{" "}
          <a
            href={buildWhatsAppLink(
              "visa",
              "Hi Bali Zero, I'd like help with a Visa on Arrival.",
            )}
            target="_blank"
            rel="noopener noreferrer"
          >
            message us on WhatsApp
          </a>
          .
        </p>
      </AppFrame>
    );
  }

  if (!data) {
    return (
      <AppFrame
        funnel="visa"
        title="Visa on Arrival"
        subtitle="Checking your case…"
      >
        <p style={{ color: "var(--color-text-muted)" }}>One moment.</p>
      </AppFrame>
    );
  }

  const publicUrl =
    typeof window !== "undefined"
      ? `${window.location.origin}/visa/voa/${hash}`
      : `/visa/voa/${hash}`;

  if (data.verdict === "DECLINE") {
    const answers = readSubmittedAnswers();
    const code = primaryDeclineCode(data.reason_codes);
    const edu = code ? buildDeclineEducation(code, answers) : null;

    return (
      <AppFrame
        funnel="visa"
        title="Visa on Arrival"
        subtitle="This isn't a wall — here's what we found and what to do next."
      >
        <div
          ref={stampRef}
          style={{
            display: "flex",
            justifyContent: "center",
            paddingTop: "var(--space-4, 1.5rem)",
          }}
        >
          <EmptyStampReveal />
        </div>
        <DeleteCheckControl
          resultId={hash ?? ""}
          onDeleted={() => setDeleted(true)}
        />
        {edu ? (
          <section
            style={{
              display: "grid",
              gap: "var(--space-3, 0.9rem)",
              maxWidth: 520,
            }}
          >
            <p style={{ margin: 0, lineHeight: 1.6 }}>{edu.mirror}</p>
            <p style={{ margin: 0, lineHeight: 1.6 }}>{edu.forbids}</p>
            <p style={{ margin: 0, lineHeight: 1.6, fontWeight: 600 }}>
              {edu.alternative}
            </p>
            <div
              style={{
                display: "grid",
                gap: "var(--space-2, 0.6rem)",
                maxWidth: 320,
              }}
            >
              {edu.routeKind === "oracle" ? (
                <a
                  href="/visa/match"
                  onClick={() =>
                    tracker.ctaClicked("try_visa_match", "/visa/match")
                  }
                  style={{
                    display: "inline-block",
                    textAlign: "center",
                    padding: "0.9rem 1.4rem",
                    borderRadius: 8,
                    ...VOA_PRIMARY_ACTION_STYLE,
                    textDecoration: "none",
                    fontWeight: 600,
                  }}
                >
                  Try Visa Match →
                </a>
              ) : null}
              <a
                href={buildWhatsAppLink(
                  "visa",
                  "Hi Bali Zero, I checked the Visa on Arrival online and would like help with my case.",
                )}
                target="_blank"
                rel="noopener noreferrer"
                onClick={() =>
                  tracker.ctaClicked("continue_on_whatsapp_decline", "wa.me")
                }
                style={{
                  display: "inline-block",
                  textAlign: "center",
                  padding: "0.9rem 1.4rem",
                  borderRadius: 8,
                  background: "#25D366",
                  color: "#0a0a0a",
                  textDecoration: "none",
                  fontWeight: 600,
                }}
              >
                Continue on WhatsApp →
              </a>
            </div>
          </section>
        ) : null}
        <AppShareBar
          url={publicUrl}
          title="Bali Zero — Visa on Arrival check"
          onShare={(c) => tracker.shareClicked(c)}
        />
      </AppFrame>
    );
  }

  // ACCEPT
  return (
    <AppFrame
      funnel="visa"
      title="Visa on Arrival — you're eligible"
      subtitle={
        data.published_filing_deadline
          ? // Deliberately NOT "your filing window": the clock below has a
            // `passed` branch, reachable because this result page is a
            // shareable URL over a stored check, and a header promising a live
            // window above a hero saying the day is gone is a page arguing
            // with itself. This sentence is true in every branch.
            "What we found, what it costs, and what happens next."
          : "We'll confirm your exact filing deadline before you pay."
      }
      footer="One all-inclusive price. Government fees, where they apply, are never billed separately from this figure."
    >
      {data.published_filing_deadline ? (
        <SafeClockHero
          deadline={data.published_filing_deadline}
          handoffHref={buildWhatsAppLink(
            "visa",
            "Hi Bali Zero, I'd like to check my Visa on Arrival filing deadline.",
          )}
        />
      ) : null}
      <div
        ref={stampRef}
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "var(--space-2, 0.5rem)",
          paddingTop: "var(--space-4, 1.5rem)",
        }}
      >
        <AppStampReveal
          code={formatIDR(data.price_idr)}
          ariaLabel={`Approved — ${formatIDR(data.price_idr)}`}
        />
      </div>
      {/* ORDER IS THE POINT, and it was backwards. The step that OPENS the
          application used to render BELOW "delete this check" — a destructive
          control ahead of the only forward path on the screen. Reachable only
          once `data` is set, which itself requires `hash` (see the two effects
          above), so this is never actually empty at render time. */}
      <MagicLinkRequestForm resultId={hash ?? ""} />
      <DeleteCheckControl
        resultId={hash ?? ""}
        onDeleted={() => setDeleted(true)}
      />
      <AppWhatsAppCTA
        source="garuda_voa"
        headline="Prefer a human to walk you through it?"
        description="Same practice, same portal, same price — a consultant drives the same steps with you."
        whatsappContext={[{ label: "Price", value: formatIDR(data.price_idr) }]}
        defaultLabel="Continue on WhatsApp →"
        postScrollLabel="Continue on WhatsApp →"
        stampRef={stampRef}
        onCaptured={({ leadIntentId }) => tracker.whatsappHandoff(leadIntentId)}
      />
      <NextSteps
        handoffHref={buildWhatsAppLink(
          "visa",
          "Hi Bali Zero, I have a question about my Visa on Arrival before I pay.",
        )}
        hasDeadline={Boolean(data.published_filing_deadline)}
      />
      <AppShareBar
        url={publicUrl}
        title="Bali Zero — Visa on Arrival"
        onShare={(c) => tracker.shareClicked(c)}
      />
    </AppFrame>
  );
}

/**
 * Requests a magic-link account from `EligibilityResult`'s own result_id
 * (contracts/openapi.yaml `/api/visa/voa/auth/magic-links`). Always shows the
 * same "check your email" copy on success — the endpoint itself is
 * non-enumerating (202 regardless of whether the email matched anything),
 * and this form must not create a second oracle on top of that.
 *
 * THIS IS THE DOOR, and it did not look like one. `/visa/voa/upload/{id}` is
 * behind the `garuda_session` cookie that ONLY the magic-link exchange sets
 * (`upload/api-client.ts`'s header; `auth/exchange/route.ts` redirects there
 * after confirming the cookie landed). A direct link from this screen to the
 * upload page would put an unauthenticated visitor on a screen whose first
 * request fails — which is why the answer here is copy and hierarchy, not a
 * new link. Two things were measured before this was rewritten: the screen
 * carried exactly ONE heading (its own h1), so the entry to the application
 * was a bare `<label>`; and the email field's boundary read
 * `--color-border-subtle` at 1.40:1 against its own fill, under SC 1.4.11's
 * 3:1 for the boundary of an interactive control. Both cures live in
 * `voa-r19.css`'s `.voa-entry` block, with the arithmetic in its docblock.
 */
function MagicLinkRequestForm({ resultId }: { resultId: string }) {
  const tracker = useFunnelApp("visa_voa", { trackView: false });
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | "error">(
    "idle",
  );

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus("sending");
    let httpStatus: number | null = null;
    try {
      const res = await fetch("/api/visa/voa/auth/magic-links", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key":
            globalThis.crypto?.randomUUID?.() ??
            `magic-${Date.now()}-${Math.random()}`,
        },
        body: JSON.stringify({ result_id: resultId, email }),
        credentials: "include",
      });
      httpStatus = res.status;
      if (res.status === 202) {
        setStatus("sent");
        // The CTA that continues the money funnel — never the email
        // address itself, only that a request happened.
        tracker.emailSubscribed("voa_magic_link_request");
      } else {
        setStatus("error");
        tracker.formSubmitFailed("/api/visa/voa/auth/magic-links", httpStatus);
      }
    } catch {
      setStatus("error");
      tracker.formSubmitFailed("/api/visa/voa/auth/magic-links", httpStatus);
    }
  };

  if (status === "sent") {
    return (
      <section aria-labelledby="voa-entry-heading" className="voa-entry">
        <h2 className="voa-entry__heading" id="voa-entry-heading">
          Start your application
        </h2>
        <p className="voa-entry__status" role="status">
          Check your email for a link to continue — it&apos;s valid for 15
          minutes. Opening it takes you straight to the passport upload.
        </p>
      </section>
    );
  }

  return (
    <section aria-labelledby="voa-entry-heading" className="voa-entry">
      <h2 className="voa-entry__heading" id="voa-entry-heading">
        Start your application
      </h2>
      <p className="voa-entry__body">
        We email you a one-time link — no password. It opens your upload page
        and expires in 15 minutes, so send it to an inbox only you read.
      </p>
      <form className="voa-entry__form" onSubmit={submit}>
        <label className="voa-entry__label" htmlFor="voa-email">
          Your email
        </label>
        <input
          className="voa-entry__input"
          id="voa-email"
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          required
          type="email"
          value={email}
        />
        <button
          className="voa-entry__submit"
          disabled={status === "sending"}
          style={VOA_PRIMARY_ACTION_STYLE}
          type="submit"
        >
          {status === "sending" ? "Sending…" : "Email me the link →"}
        </button>
        {status === "error" ? (
          <p className="voa-entry__error" role="alert">
            Something went wrong. Please try again.
          </p>
        ) : null}
      </form>
    </section>
  );
}

/**
 * Self-service deletion (design-A §2, DELIBERA-fase2 lane S6,
 * `products/garuda-voa/journeys/self-service-deletion.feature`). Deletion is
 * authorized by the same creator-bound `garuda_result_session` HttpOnly
 * cookie the page's own GET already relies on — this page never reads or
 * carries that cookie itself, `credentials: "include"` sends it same-origin,
 * exactly like the GET above and `MagicLinkRequestForm`'s POST. The contract
 * (`deleteEligibilityResult`) always answers 204 (bound-and-erased or a
 * no-op alike — non-enumerating, verbatim); a non-204 here is a network or
 * server fault, not a "you may not delete this" answer, so a failure gets a
 * retry, never a different copy.
 *
 * One quiet text link → inline confirm (two controls, R19 "one control per
 * state" respected by treating confirm as its own state) → the terminal
 * "Deleted" screen the parent renders once `onDeleted` fires. Copper marks
 * this as the visitor's OWN thing to remove (R19 law: copper = ownership,
 * never a generic action); the error tone deliberately avoids both copper
 * and `--color-error` (red) per DELIBERA (d) — no dedicated error token
 * exists yet for this surface (S3's lane), so weight carries the alert
 * instead of a colour.
 */
function DeleteCheckControl({
  resultId,
  onDeleted,
}: {
  resultId: string;
  onDeleted: () => void;
}) {
  const [state, setState] = useState<
    "idle" | "confirming" | "deleting" | "error"
  >("idle");
  const idempotencyKeyRef = useRef<string | null>(null);

  const startConfirm = () => {
    idempotencyKeyRef.current =
      globalThis.crypto?.randomUUID?.() ??
      `voa-delete-${Date.now()}-${Math.random()}`;
    setState("confirming");
  };

  const cancel = () => setState("idle");

  const remove = async () => {
    setState("deleting");
    try {
      const res = await fetch(
        `/api/visa/voa/eligibility-checks/${encodeURIComponent(resultId)}`,
        {
          method: "DELETE",
          credentials: "include",
          headers: { "Idempotency-Key": idempotencyKeyRef.current ?? "" },
        },
      );
      if (res.status === 204) {
        onDeleted();
        return;
      }
      setState("error");
    } catch {
      setState("error");
    }
  };

  if (state === "idle") {
    return (
      <p style={{ margin: 0 }}>
        <button
          type="button"
          onClick={startConfirm}
          style={{
            background: "none",
            border: "none",
            padding: 0,
            font: "inherit",
            fontSize: "0.85rem",
            color: "var(--bz-copper-text, var(--color-text-muted))",
            textDecoration: "underline",
            cursor: "pointer",
          }}
        >
          Delete this check
        </button>
      </p>
    );
  }

  if (state === "error") {
    return (
      <div style={{ display: "grid", gap: "var(--space-2, 0.6rem)" }}>
        <p role="alert" style={{ margin: 0, fontWeight: 600 }}>
          Couldn&apos;t delete this check. Please try again.
        </p>
        <button
          type="button"
          onClick={remove}
          style={{
            alignSelf: "start",
            padding: "0.6rem 1rem",
            borderRadius: 8,
            border: "1px solid var(--color-border-subtle)",
            background: "none",
            color: "inherit",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Try again
        </button>
      </div>
    );
  }

  // confirming | deleting
  const isDeleting = state === "deleting";
  return (
    <div style={{ display: "grid", gap: "var(--space-2, 0.6rem)" }}>
      <p style={{ margin: 0, fontSize: "0.9rem" }}>
        Delete this check? This can&apos;t be undone.
      </p>
      <div style={{ display: "flex", gap: "0.75rem" }}>
        <button
          type="button"
          onClick={remove}
          disabled={isDeleting}
          style={{
            padding: "0.6rem 1rem",
            borderRadius: 8,
            border: "1px solid var(--bz-copper-text, currentColor)",
            background: "none",
            color: "var(--bz-copper-text, inherit)",
            fontWeight: 600,
            cursor: isDeleting ? "default" : "pointer",
          }}
        >
          {isDeleting ? "Deleting…" : "Yes, delete"}
        </button>
        <button
          type="button"
          onClick={cancel}
          disabled={isDeleting}
          style={{
            padding: "0.6rem 1rem",
            borderRadius: 8,
            border: "1px solid var(--color-border-subtle)",
            background: "none",
            color: "inherit",
            cursor: isDeleting ? "default" : "pointer",
          }}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
