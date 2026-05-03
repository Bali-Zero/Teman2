"use client";

import { use, useEffect, useRef, useState } from "react";
import {
  AppFrame,
  AppShareBar,
  AppStampReveal,
  AppWhatsAppCTA,
  useFunnelApp,
  useHaptic,
} from "@balizero/core";
import { ChatAccordion } from "@/components/visa/ChatAccordion";
import { HandoffWaLink } from "@/components/visa/HandoffWaLink";

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
  nationality: string;
  purpose: string;
  duration_months: number;
  budget_band: string;
  session_jwt: string | null;
}

export default function VisaMatchResultPage({
  params,
}: {
  params: Promise<{ hash: string }>;
}) {
  const { hash } = use(params);
  const tracker = useFunnelApp("visa_match", { trackView: false });
  const haptic = useHaptic();
  const stampRef = useRef<HTMLDivElement | null>(null);
  const [data, setData] = useState<MatchResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const res = await fetch(`/api/visa/match/${hash}`);
        if (!res.ok) { setErr("We could not find this recommendation. It may have expired."); return; }
        const json = (await res.json()) as MatchResult;
        setData(json);
        tracker.resultViewed(json.hash);
        haptic(12); // stamp reveal haptic
      } catch { setErr("Network error. Try again."); }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hash]);

  if (err) return (<AppFrame funnel="visa" title="Visa Match" subtitle={err}><p><a href="/visa/match">Start again →</a></p></AppFrame>);
  if (!data) return (<AppFrame funnel="visa" title="Visa Match" subtitle="Computing your match…"><p style={{ color: "var(--color-text-muted)" }}>One moment.</p></AppFrame>);

  const publicUrl = typeof window !== "undefined"
    ? `${window.location.origin}/visa/match/${data.hash}`
    : `/visa/match/${data.hash}`;

  // Referral mode: no stamp, hand off directly
  if (data.referral_mode || !data.recommended_visa) {
    return (
      <AppFrame funnel="visa" title="Your case needs a conversation" subtitle="The form can't capture everything. A 15-minute WhatsApp review with our visa team is faster than any guess.">
        <p style={{ lineHeight: 1.6 }}>{data.reason}</p>
        {/* TODO(Task 12): fire visaWaClick telemetry with source=wizard_abstained */}
        <HandoffWaLink
          phone={process.env.NEXT_PUBLIC_WA_PHONE ?? "+6285156005858"}
          nationality={data.nationality}
          purpose={data.purpose}
          durationMonths={data.duration_months}
          budgetBand={data.budget_band}
          reason={data.reason}
        />
        <AppShareBar url={publicUrl} title="Bali Zero — Visa review" onShare={(c) => tracker.shareClicked(c)} />
      </AppFrame>
    );
  }

  return (
    <AppFrame
      funnel="visa"
      title={`Your visa: ${data.recommended_visa}`}
      subtitle={data.processing_days ? `Processing ~${data.processing_days} business days once we file.` : undefined}
      footer={<>Recommendation based on your answers. Cost from PricingTool (source: {data.cost_source ?? "PricingTool"}). Gov fees may vary — we confirm before filing.</>}
    >
      {/* Stamp reveal */}
      <div ref={stampRef} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "var(--space-2, 0.5rem)", paddingTop: "var(--space-4, 1.5rem)" }}>
        <div style={{ fontSize: "0.58rem", letterSpacing: "0.2em", textTransform: "uppercase", opacity: 0.5, color: "var(--color-text-muted)" }}>
          Your visa
        </div>
        <AppStampReveal code={data.recommended_visa} />
      </div>

      {/* Why it fits */}
      <section>
        <div style={{ fontSize: "0.62rem", letterSpacing: "0.15em", textTransform: "uppercase", opacity: 0.5, color: "var(--color-text-muted)", marginBottom: "var(--space-1, 0.3rem)" }}>
          Why it fits
        </div>
        <p style={{ margin: 0, fontSize: "clamp(1rem, 2.4vw, 1.1rem)", lineHeight: 1.6 }}>
          {data.reason}
        </p>
      </section>

      {/* Estimated cost */}
      <section>
        <div style={{ fontSize: "0.62rem", letterSpacing: "0.15em", textTransform: "uppercase", opacity: 0.5, color: "var(--color-text-muted)", marginBottom: "var(--space-1, 0.3rem)" }}>
          Estimated cost
        </div>
        {data.estimated_cost_idr ? (
          <>
            <div style={{ fontFamily: "var(--font-serif, Georgia, serif)", fontSize: "clamp(1.5rem, 4vw, 2rem)", color: "var(--accent-funnel-text, var(--accent-funnel))" }}>
              IDR {formatIdr(data.estimated_cost_idr)}
            </div>
            <div style={{ fontSize: "var(--text-sm, 0.85rem)", color: "var(--color-text-muted)" }}>
              Bali Zero fee. Government fees billed at cost.
            </div>
          </>
        ) : (
          <p style={{ margin: 0, fontStyle: "italic", color: "var(--color-text-muted)" }}>
            Let&apos;s confirm the exact fee on WhatsApp — your case has specifics.
          </p>
        )}
      </section>

      {/* Pre-arrival checklist */}
      <section>
        <div style={{ fontSize: "0.62rem", letterSpacing: "0.15em", textTransform: "uppercase", opacity: 0.5, color: "var(--color-text-muted)", marginBottom: "var(--space-1, 0.3rem)" }}>
          Pre-arrival checklist
        </div>
        <ol style={{ paddingLeft: 18, margin: 0, display: "grid", gap: "var(--space-2, 0.5rem)", lineHeight: 1.5 }}>
          {data.pre_arrival_steps.map((step) => (<li key={step}>{step}</li>))}
        </ol>
      </section>

      {/* Alternatives */}
      {data.alternatives.length > 0 ? (
        <section>
          <div style={{ fontSize: "0.62rem", letterSpacing: "0.15em", textTransform: "uppercase", opacity: 0.5, color: "var(--color-text-muted)", marginBottom: "var(--space-1, 0.3rem)" }}>
            Alternatives
          </div>
          <p style={{ margin: 0, color: "var(--color-text-muted)", fontSize: "var(--text-sm, 0.9rem)" }}>
            If your case changes: {data.alternatives.join(" · ")}. Ask us on WhatsApp for the trade-off.
          </p>
        </section>
      ) : null}

      {/* Ask follow-up questions (chat) */}
      {data.session_jwt ? (
        <ChatAccordion checkHash={data.hash} sessionJwt={data.session_jwt} />
      ) : null}

      {/* WhatsApp CTA — sticky after scroll past stamp */}
      <AppWhatsAppCTA
        source="visa_match"
        headline={`Start the ${data.recommended_visa} application`}
        description="We file the paperwork and handle imigrasi. Typical first reply on WhatsApp in under 5 hours."
        resultHash={data.hash}
        context={{ recommended_visa: data.recommended_visa, estimated_cost_idr: data.estimated_cost_idr }}
        whatsappContext={[
          { label: "Visa", value: data.recommended_visa },
          data.estimated_cost_idr
            ? { label: "Est. cost", value: `IDR ${formatIdr(data.estimated_cost_idr)}` }
            : { label: "Cost", value: "To confirm" },
          data.processing_days
            ? { label: "Processing", value: `~${data.processing_days} business days` }
            : { label: "Processing", value: "To confirm" },
        ]}
        defaultLabel="Start on WhatsApp →"
        postScrollLabel={`Start the ${data.recommended_visa} application →`}
        stampRef={stampRef}
        onCaptured={({ leadIntentId }) => tracker.whatsappHandoff(leadIntentId)}
      />

      {/* Share */}
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
