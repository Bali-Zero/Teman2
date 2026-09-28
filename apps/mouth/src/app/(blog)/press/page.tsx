import type { Metadata } from "next";

export const metadata: Metadata = {
  alternates: {
    canonical: "https://balizero.com/press",
  },
  title: "Press",
  description:
    "Media enquiries and press resources for Bali Zero — Indonesia's leading expat services firm.",
};

export default function PressPage() {
  return (
    <div
      className="max-w-3xl mx-auto px-6 md:px-10"
      style={{
        padding:
          "clamp(56px, 7vw, 96px) clamp(24px, 4vw, 40px) clamp(48px, 6vw, 80px)",
      }}
    >
      <div
        className="text-[10px] font-semibold uppercase tracking-[0.2em] mb-4"
        style={{ color: "var(--text-tertiary)" }}
      >
        Company · Press
      </div>

      <h1
        className="font-extrabold tracking-tight mb-6"
        style={{ fontSize: "clamp(28px, 4vw, 44px)", lineHeight: 1.1 }}
      >
        Press &amp; Media
      </h1>

      <p
        className="text-[17px] leading-relaxed mb-10"
        style={{ color: "var(--text-secondary)", maxWidth: "72ch" }}
      >
        If you&apos;re covering Indonesian visa law, foreign business ownership,
        PT PMA, or the expat ecosystem in Bali — we&apos;re a primary source.
        Antonello and the team are available for comment, background, and
        on-record interviews.
      </p>

      <div
        className="rounded-lg px-6 py-5"
        style={{
          background: "var(--surface-raised)",
          border: "1px solid var(--border-subtle)",
        }}
      >
        <p
          className="text-[11px] font-semibold uppercase tracking-[0.15em] mb-2"
          style={{ color: "var(--text-tertiary)" }}
        >
          Press enquiries
        </p>
        <p className="text-[15px]" style={{ color: "var(--text-secondary)" }}>
          Reach us via WhatsApp or email — we respond within one business day.
        </p>
      </div>
    </div>
  );
}
