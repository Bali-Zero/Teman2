"use client";

import { useEffect, useState } from "react";
import {
  AppFrame,
  AppShareBar,
  AppWhatsAppCTA,
  useFunnelApp,
} from "@balizero/core";

interface MatchResult {
  hash: string;
  recommended_visa: string | null;
  reason: string;
  estimated_cost_idr: number | null;
  cost_source: string | null;
  processing_days: number | null;
  pre_arrival_steps: string[];
  alternatives: string[];
  referral_mode: boolean;
  result_url: string;
}

export default function VisaMatchResultPage({
  params,
}: {
  params: { hash: string };
}) {
  const tracker = useFunnelApp("visa_match", { trackView: false });
  const [data, setData] = useState<MatchResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const res = await fetch(`/api/visa/match/${params.hash}`);
        if (!res.ok) {
          setErr("We could not find this recommendation. It may have expired.");
          return;
        }
        const json = (await res.json()) as MatchResult;
        setData(json);
        tracker.resultViewed(json.hash);
      } catch {
        setErr("Network error. Try again.");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.hash]);

  if (err)
    return (
      <AppFrame title="Visa Match" subtitle={err}>
        <p>
          <a href="/visa/match">Start again →</a>
        </p>
      </AppFrame>
    );
  if (!data)
    return (
      <AppFrame title="Visa Match" subtitle="Computing your match…">
        <p style={{ color: "var(--color-text-muted)" }}>Just a moment.</p>
      </AppFrame>
    );

  const publicUrl =
    typeof window !== "undefined"
      ? `${window.location.origin}/visa/match/${data.hash}`
      : `/visa/match/${data.hash}`;

  // ── Referral mode: no recommendation, send to WA directly. ──
  if (data.referral_mode || !data.recommended_visa) {
    return (
      <AppFrame
        title="Your case needs a conversation"
        subtitle="The form can't capture everything. A 15-minute WhatsApp review with our visa team is faster than any guess."
      >
        <p style={{ lineHeight: 1.6 }}>{data.reason}</p>
        <AppWhatsAppCTA
          source="visa_match"
          headline="Free 15-minute visa review"
          description="Tell us what you're trying to do. We'll pick the right route and the real cost."
          resultHash={data.hash}
          whatsappContext={[
            { label: "Case", value: "Non-standard / borderline" },
            { label: "Route", value: "Free 15-min review requested" },
          ]}
          onCaptured={({ leadIntentId }) =>
            tracker.whatsappHandoff(leadIntentId)
          }
        />
        <AppShareBar
          url={publicUrl}
          title="Bali Zero — Visa review"
          onShare={(c) => tracker.shareClicked(c)}
        />
      </AppFrame>
    );
  }

  // ── Normal result mode. ──
  return (
    <AppFrame
      title={`For you: ${data.recommended_visa}`}
      subtitle={
        data.processing_days
          ? `Processing ~${data.processing_days} business days once we file.`
          : undefined
      }
      footer={
        <>
          Recommendation based on the rules in{" "}
          <a href="https://balizero.com/docs/visa-types">
            visa-types reference
          </a>
          . Cost from our PricingTool (source:{" "}
          {data.cost_source ?? "PricingTool"}). Gov fees may vary — we confirm
          before filing.
        </>
      }
    >
      <div
        style={{
          padding: "var(--space-4)",
          background: "var(--surface-raised)",
          borderRadius: 12,
          display: "grid",
          gap: "var(--space-3)",
        }}
      >
        <p style={{ margin: 0, lineHeight: 1.6 }}>{data.reason}</p>
        {data.estimated_cost_idr ? (
          <div>
            <strong style={{ fontSize: "var(--text-2xl)" }}>
              IDR {formatIdr(data.estimated_cost_idr)}
            </strong>
            <div
              style={{
                fontSize: "var(--text-sm)",
                color: "var(--color-text-muted)",
              }}
            >
              Bali Zero fee. Government fees billed at cost.
            </div>
          </div>
        ) : (
          <p
            style={{
              margin: 0,
              fontStyle: "italic",
              color: "var(--color-text-muted)",
            }}
          >
            Let's confirm the exact fee on WhatsApp — your case has specifics.
          </p>
        )}
      </div>

      <section>
        <h2
          style={{ fontSize: "var(--text-lg)", marginBottom: "var(--space-2)" }}
        >
          Pre-arrival checklist
        </h2>
        <ol
          style={{
            paddingLeft: 18,
            margin: 0,
            display: "grid",
            gap: "var(--space-2)",
            lineHeight: 1.5,
          }}
        >
          {data.pre_arrival_steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </section>

      {data.alternatives.length > 0 ? (
        <section>
          <h2
            style={{
              fontSize: "var(--text-md)",
              marginBottom: "var(--space-2)",
            }}
          >
            Alternatives
          </h2>
          <p
            style={{
              margin: 0,
              color: "var(--color-text-muted)",
              fontSize: "var(--text-sm)",
              lineHeight: 1.5,
            }}
          >
            If your case changes: {data.alternatives.join(" · ")}. Ask us on
            WhatsApp and we'll explain the trade-off.
          </p>
        </section>
      ) : null}

      <AppWhatsAppCTA
        source="visa_match"
        headline={`Start the ${data.recommended_visa} application`}
        description="We file the paperwork and handle imigrasi. Typical first reply on WhatsApp in under 5 hours."
        resultHash={data.hash}
        context={{
          recommended_visa: data.recommended_visa,
          estimated_cost_idr: data.estimated_cost_idr,
        }}
        whatsappContext={[
          { label: "Visa", value: data.recommended_visa },
          data.estimated_cost_idr
            ? {
                label: "Est. cost",
                value: `IDR ${formatIdr(data.estimated_cost_idr)}`,
              }
            : { label: "Cost", value: "To confirm" },
          data.processing_days
            ? {
                label: "Processing",
                value: `~${data.processing_days} business days`,
              }
            : { label: "Processing", value: "To confirm" },
        ]}
        onCaptured={({ leadIntentId }) => tracker.whatsappHandoff(leadIntentId)}
      />

      <AppShareBar
        url={publicUrl}
        title={`Bali Zero — Visa recommendation: ${data.recommended_visa}`}
        onShare={(c) => tracker.shareClicked(c)}
      />
    </AppFrame>
  );
}

function formatIdr(n: number): string {
  return n.toLocaleString("id-ID");
}
