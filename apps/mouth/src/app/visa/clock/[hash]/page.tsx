"use client";

import { use, useEffect, useRef, useState } from "react";
import {
  AppEmailOptIn,
  AppFrame,
  AppResultTimeline,
  AppShareBar,
  AppStampReveal,
  AppWhatsAppCTA,
  useFunnelApp,
  useHaptic,
  type TimelineCheckpoint,
} from "@balizero/core";
import { ChatAccordion } from "@/components/visa/ChatAccordion";

interface ClockResult {
  hash: string;
  visa_type: string;
  entry_date: string;
  expiry_date: string;
  extensions_possible: number;
  extension_days: number;
  checkpoints: { label: string; at: string; title: string; body: string }[];
  result_url: string;
  session_jwt: string | null;
}

export default function VisaClockResultPage({
  params,
}: {
  params: Promise<{ hash: string }>;
}) {
  const { hash } = use(params);
  const tracker = useFunnelApp("visa_clock", { trackView: false });
  const haptic = useHaptic();
  const stampRef = useRef<HTMLDivElement>(null);
  const [data, setData] = useState<ClockResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const res = await fetch(`/api/visa/clock/${hash}`);
        if (!res.ok) {
          setErr("We could not find this timeline. It may have expired.");
          return;
        }
        const json = (await res.json()) as ClockResult;
        setData(json);
        tracker.resultViewed(json.hash);
        haptic(12); // stamp reveal haptic
      } catch {
        setErr("Network error. Try again.");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hash]);

  if (err)
    return (
      <AppFrame funnel="visa" title="Visa Clock" subtitle={err}>
        <p>
          <a href="/visa/clock">Start a new timeline →</a>
        </p>
      </AppFrame>
    );
  if (!data)
    return (
      <AppFrame funnel="visa" title="Visa Clock" subtitle="Loading your timeline…">
        <p style={{ color: "var(--color-text-muted)" }}>One moment.</p>
      </AppFrame>
    );

  const today = new Date().toISOString().slice(0, 10);
  const checkpoints: TimelineCheckpoint[] = data.checkpoints.map((c) => ({ ...c, past: c.at < today }));
  const daysLeft = Math.max(0, Math.ceil((new Date(data.expiry_date).getTime() - Date.now()) / 86_400_000));
  const publicUrl =
    typeof window !== "undefined"
      ? `${window.location.origin}/visa/clock/${data.hash}`
      : `/visa/clock/${data.hash}`;

  return (
    <AppFrame
      funnel="visa"
      title={`Your ${data.visa_type} timeline`}
      subtitle={`Expires ${formatIsoDate(data.expiry_date)} — ${daysLeft} days from today.`}
      footer={
        <>
          Timeline generated {formatIsoDate(today)}. Government fees may change —{" "}
          <a href="https://balizero.com/pricing" style={{ color: "var(--accent-funnel-text)" }}>
            pricing reference
          </a>
          .
        </>
      }
    >
      {/* Stamp reveal */}
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
        <div
          style={{
            fontSize: "0.58rem",
            letterSpacing: "0.2em",
            textTransform: "uppercase",
            opacity: 0.5,
            color: "var(--color-text-muted)",
          }}
        >
          Your visa
        </div>
        <AppStampReveal code={data.visa_type} />
        <p
          style={{
            fontFamily: "var(--font-serif, Georgia, serif)",
            margin: "var(--space-2, 0.5rem) 0 0",
            fontSize: "clamp(1rem, 2.4vw, 1.2rem)",
          }}
        >
          Valid until {formatIsoDate(data.expiry_date)}
        </p>
      </div>

      {/* Timeline section */}
      <section style={{ display: "grid", gap: "var(--space-2, 0.6rem)" }}>
        <div
          style={{
            fontSize: "0.62rem",
            letterSpacing: "0.15em",
            textTransform: "uppercase",
            opacity: 0.5,
            color: "var(--color-text-muted)",
          }}
        >
          Five-checkpoint timeline
        </div>
        <AppResultTimeline checkpoints={checkpoints} expiryDate={data.expiry_date} />
      </section>

      {/* Chat accordion — only present on fresh POST result (session_jwt non-null) */}
      {data.session_jwt ? (
        <ChatAccordion
          checkHash={data.hash}
          sessionJwt={data.session_jwt}
          daysRemaining={daysLeft}
        />
      ) : null}

      {/* Email opt-in */}
      <section>
        <AppEmailOptIn
          app="visa_clock"
          resultHash={data.hash}
          promise="Get reminder emails at each of the 5 checkpoints. One-click unsubscribe."
          payload={{
            visa_type: data.visa_type,
            entry_date: data.entry_date,
            expiry_date: data.expiry_date,
          }}
          endpoint="/api/visa/clock/email"
          onSubscribed={() => tracker.emailSubscribed("clock_5_reminders")}
        />
      </section>

      {/* WhatsApp CTA — sticky after scroll past stamp */}
      <AppWhatsAppCTA
        source="visa_clock"
        headline={`Want our team to file the ${data.visa_type} renewal?`}
        description="Fixed fee, processed in ~14 days. Start on WhatsApp — we'll pick up in under 5 hours."
        resultHash={data.hash}
        context={{ visa_type: data.visa_type, entry_date: data.entry_date, expiry_date: data.expiry_date }}
        whatsappContext={[
          { label: "Visa", value: data.visa_type },
          { label: "Entry", value: formatIsoDate(data.entry_date) },
          { label: "Expiry", value: formatIsoDate(data.expiry_date) },
          { label: "Days left", value: String(daysLeft) },
        ]}
        defaultLabel="Start on WhatsApp →"
        postScrollLabel={`Start the ${data.visa_type} renewal →`}
        stampRef={stampRef}
        onCaptured={({ leadIntentId }) => tracker.whatsappHandoff(leadIntentId)}
      />

      {/* Share bar */}
      <AppShareBar
        url={publicUrl}
        title={`Bali Zero — ${data.visa_type} timeline`}
        onShare={(channel) => tracker.shareClicked(channel)}
      />
    </AppFrame>
  );
}

function formatIsoDate(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}
