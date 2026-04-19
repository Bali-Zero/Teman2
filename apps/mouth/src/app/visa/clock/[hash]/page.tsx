"use client";

import { useEffect, useState } from "react";
import {
  AppEmailOptIn,
  AppFrame,
  AppResultTimeline,
  AppShareBar,
  AppWhatsAppCTA,
  useFunnelApp,
  type TimelineCheckpoint,
} from "@balizero/core";

interface ClockResult {
  hash: string;
  visa_type: string;
  entry_date: string;
  expiry_date: string;
  extensions_possible: number;
  extension_days: number;
  checkpoints: {
    label: string;
    at: string;
    title: string;
    body: string;
  }[];
  result_url: string;
}

export default function VisaClockResultPage({
  params,
}: {
  params: { hash: string };
}) {
  const tracker = useFunnelApp("visa_clock", { trackView: false });
  const [data, setData] = useState<ClockResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const res = await fetch(`/api/visa/clock/${params.hash}`);
        if (!res.ok) {
          setErr("We could not find this timeline. It may have expired.");
          return;
        }
        const json = (await res.json()) as ClockResult;
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
      <AppFrame title="Visa Clock" subtitle={err}>
        <p>
          <a href="/visa/clock">Start a new timeline →</a>
        </p>
      </AppFrame>
    );
  if (!data)
    return (
      <AppFrame title="Visa Clock" subtitle="Loading your timeline…">
        <p style={{ color: "var(--color-text-muted)" }}>Just a moment.</p>
      </AppFrame>
    );

  const today = new Date().toISOString().slice(0, 10);
  const checkpoints: TimelineCheckpoint[] = data.checkpoints.map((c) => ({
    ...c,
    past: c.at < today,
  }));
  const daysLeft = Math.max(
    0,
    Math.ceil((new Date(data.expiry_date).getTime() - Date.now()) / 86_400_000),
  );
  const publicUrl =
    typeof window !== "undefined"
      ? `${window.location.origin}/visa/clock/${data.hash}`
      : `/visa/clock/${data.hash}`;

  return (
    <AppFrame
      title={`Your ${data.visa_type} timeline`}
      subtitle={`Expires ${formatIsoDate(data.expiry_date)} — ${daysLeft} days from today.`}
      footer={
        <>
          Timeline generated {formatIsoDate(today)}. Government fees may change
          — <a href="https://balizero.com/pricing">pricing reference</a>.
        </>
      }
    >
      <AppResultTimeline
        checkpoints={checkpoints}
        expiryDate={data.expiry_date}
      />

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

      <AppWhatsAppCTA
        source="visa_clock"
        headline={`Want our team to file the ${data.visa_type} renewal?`}
        description={`Fixed fee, processed in ~14 days. Start on WhatsApp — we'll pick up in under 5 hours.`}
        resultHash={data.hash}
        context={{
          visa_type: data.visa_type,
          entry_date: data.entry_date,
          expiry_date: data.expiry_date,
        }}
        whatsappContext={[
          { label: "Visa", value: data.visa_type },
          { label: "Entry", value: formatIsoDate(data.entry_date) },
          { label: "Expiry", value: formatIsoDate(data.expiry_date) },
          {
            label: "Days left",
            value: String(daysLeft),
          },
        ]}
        onCaptured={({ leadIntentId }) => tracker.whatsappHandoff(leadIntentId)}
      />

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
  return d.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}
