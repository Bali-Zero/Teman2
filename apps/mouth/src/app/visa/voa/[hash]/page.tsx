"use client";

import { useEffect, useRef, useState } from "react";
import {
  AppFrame,
  AppShareBar,
  AppStampReveal,
  AppWhatsAppCTA,
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
  const stampRef = useRef<HTMLDivElement | null>(null);
  const [hash, setHash] = useState<string | null>(null);
  const [data, setData] = useState<VoaResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

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
        setData((await res.json()) as VoaResult);
      } catch {
        setErr("Network error. Please try again.");
      }
    })();
  }, [hash]);

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
                  style={{
                    display: "inline-block",
                    textAlign: "center",
                    padding: "0.9rem 1.4rem",
                    borderRadius: 8,
                    background: "var(--accent-funnel, #ff3344)",
                    color: "#0a0a0a",
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
          onShare={() => {}}
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
          ? `File by ${data.published_filing_deadline} at Ngurah Rai.`
          : "We'll confirm your exact filing deadline before you pay."
      }
      footer="One all-inclusive price. Government fees, where they apply, are never billed separately from this figure."
    >
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
      {/* Reachable only once `data` is set, which itself requires `hash` — see the
          two effects above — so this is never actually empty at render time. */}
      <MagicLinkRequestForm resultId={hash ?? ""} />
      <AppWhatsAppCTA
        source="garuda_voa"
        headline="Prefer a human to walk you through it?"
        description="Same practice, same portal, same price — a consultant drives the same steps with you."
        whatsappContext={[{ label: "Price", value: formatIDR(data.price_idr) }]}
        defaultLabel="Continue on WhatsApp →"
        postScrollLabel="Continue on WhatsApp →"
        stampRef={stampRef}
      />
      <AppShareBar
        url={publicUrl}
        title="Bali Zero — Visa on Arrival"
        onShare={() => {}}
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
 */
function MagicLinkRequestForm({ resultId }: { resultId: string }) {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | "error">(
    "idle",
  );

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus("sending");
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
      setStatus(res.status === 202 ? "sent" : "error");
    } catch {
      setStatus("error");
    }
  };

  if (status === "sent") {
    return (
      <p role="status" style={{ margin: 0, lineHeight: 1.6 }}>
        Check your email for a link to continue — it&apos;s valid for 15
        minutes.
      </p>
    );
  }

  return (
    <form
      onSubmit={submit}
      style={{ display: "grid", gap: "var(--space-2, 0.6rem)", maxWidth: 360 }}
    >
      <label htmlFor="voa-email" style={{ fontSize: "0.95rem" }}>
        Continue by email — we&apos;ll send a one-time link, no password.
      </label>
      <input
        id="voa-email"
        type="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="you@example.com"
        style={{
          padding: "0.6rem 0.7rem",
          borderRadius: 4,
          border: "1px solid var(--color-border-subtle)",
          background: "var(--surface-raised)",
          color: "var(--text-primary)",
          fontSize: "1rem",
        }}
      />
      <button
        type="submit"
        disabled={status === "sending"}
        style={{
          padding: "0.9rem 1.4rem",
          borderRadius: 8,
          border: "none",
          background: "var(--accent-funnel, #ff3344)",
          color: "#0a0a0a",
          fontWeight: 600,
          cursor: status === "sending" ? "default" : "pointer",
        }}
      >
        {status === "sending" ? "Sending…" : "Email me a link →"}
      </button>
      {status === "error" ? (
        <p role="alert" style={{ margin: 0, color: "var(--color-error)" }}>
          Something went wrong. Please try again.
        </p>
      ) : null}
    </form>
  );
}
