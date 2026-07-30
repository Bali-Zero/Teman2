"use client";

/**
 * Portal Visa — immigration status, documents, history.
 *
 * WS3 slice 9 (GARUDA Day Edition, 2026-07-24): day-theme token alignment,
 * mirroring slices 1-8. Masthead = copper rule + Cormorant serif
 * (--font-serif) in --tx-pure; cards read --bz-card / --bz-border + the
 * concept .panel shadow; status chips/banners read the semantic --state-*
 * tokens with the AA-verified 12% color-mix tints (WS2 operative-light
 * overrides: success 4.80 / warning 4.78 / danger 5.74 :1 on paper; the old
 * neon hexes were 1.48-2.45:1 — unreadable). Copper icon wells follow the
 * theme copper via color-mix. No hardcoded colors.
 */

import React, { useEffect, useState } from "react";
import { Plane, Calendar, FileText, Clock } from "lucide-react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
// From its own module, not the barrel: tests vi.mock "@/lib/api".
import { ApiError } from "@/lib/api/error-handler";
import { StatusBadge, PortalEmptyState } from "@/components/portal";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";
import { logger } from "@/lib/logger";
import type {
  VisaInfo,
  VisaHistoryItem,
  PortalDocument,
} from "@/lib/api/portal/portal.types";

// Day surface (concept .panel): warm-paper card, hairline warm border, soft
// navy shadow (near-invisible on dark). Shared by every card on this page.
const CARD_STYLE: React.CSSProperties = {
  background: "var(--bz-card)",
  borderColor: "var(--bz-border)",
  boxShadow: "0 14px 34px rgba(22, 33, 58, 0.07)",
  backdropFilter: "blur(24px)",
};

type StateTone = "success" | "warning" | "danger";

function toneToken(tone: StateTone): string {
  return tone === "success"
    ? "--state-success"
    : tone === "warning"
      ? "--state-warning"
      : "--state-danger";
}

// Status chip tones — same recipe as StatusBadge / CountdownChip: state-token
// fg on a 12% color-mix tint of the same token. AA-verified ON WHITE CARDS
// (success 4.59 / warning 4.55 / danger 5.28 :1 fg-on-tint).
function toneStyle(tone: StateTone): React.CSSProperties {
  const token = toneToken(tone);
  return {
    background: `color-mix(in srgb, var(${token}) 12%, transparent)`,
    color: `var(${token})`,
  };
}

// Chip tone for chips sitting INSIDE --glass-rim wells (document/history
// cards): the 12% tint over the 6% dark well sinks success/warning fg to
// ~4.0:1 — below the 4.5:1 floor. Hairline state border + bare state fg on
// the well instead (≥5.0:1) — same pattern as the copper KBLI chip
// (slice-6/7 finding).
function wellChipStyle(tone: StateTone): React.CSSProperties {
  const token = toneToken(tone);
  return {
    border: `1px solid color-mix(in srgb, var(${token}) 35%, transparent)`,
    color: `var(${token})`,
  };
}

// Day masthead (GARUDA Day Edition): copper rule + Cormorant serif headline
// per concept (--font-serif, wired on <html>); Inter everywhere else.
function VisaMasthead() {
  return (
    <section>
      <div
        aria-hidden="true"
        className="w-14 h-[3px] rounded-sm mb-4 bg-[var(--bz-copper)]"
      />
      <h1
        className="text-2xl font-semibold tracking-tight text-[var(--tx-pure)]"
        style={{ fontFamily: "var(--font-serif)" }}
      >
        Immigration Status
      </h1>
      <p className="text-sm text-[var(--tx-secondary)] mt-1">
        Your visa and permit information
      </p>
    </section>
  );
}

export default function VisaPage() {
  const router = useRouter();
  const { error } = useToast();
  const [visaInfo, setVisaInfo] = useState<VisaInfo | null>(null);
  const [needsClientSelection, setNeedsClientSelection] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadVisaInfo();
  }, []);

  const loadVisaInfo = async () => {
    try {
      setIsLoading(true);
      setNeedsClientSelection(false);
      const data = await api.portal.getVisaStatus();
      setVisaInfo(data);
    } catch (err) {
      if (
        err instanceof Error &&
        err.message === "Superuser: select a client via ?as_client=<id>"
      ) {
        setNeedsClientSelection(true);
        return;
      }
      // Branch on the real HTTP status. This read `err.status` and
      // `err.response.status`, neither of which the api client ever set, so
      // `is403` was permanently false and the 403 copy below was dead code.
      const is403 = err instanceof ApiError && err.statusCode === 403;
      error(
        "Failed to load visa information",
        is403 ? "Your account needs verification." : "Please try again later",
        {
          label: is403 ? "Contact your team" : "Chat with your team",
          onClick: () => router.push("/portal/messages"),
        },
      );
      logger.error("Failed to load portal visa info", {}, err as Error);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6 animate-in fade-in duration-500">
        <section>
          <div
            className="h-7 w-48 rounded animate-pulse"
            style={{ background: "var(--bz-border)" }}
          />
          <div
            className="h-4 w-64 rounded mt-2 animate-pulse"
            style={{ background: "var(--bz-border)", opacity: 0.5 }}
          />
        </section>
        <div
          className="rounded-xl border p-6 space-y-4 animate-pulse"
          style={CARD_STYLE}
        >
          <div
            className="h-5 w-32 rounded"
            style={{ background: "var(--bz-border)" }}
          />
          <div
            className="h-10 w-full rounded"
            style={{ background: "var(--bz-border)", opacity: 0.5 }}
          />
          <div className="grid grid-cols-2 gap-3">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="h-14 rounded"
                style={{ background: "var(--bz-border)", opacity: 0.4 }}
              />
            ))}
          </div>
        </div>
        <div
          className="rounded-xl border p-6 space-y-3 animate-pulse"
          style={CARD_STYLE}
        >
          <div
            className="h-5 w-28 rounded"
            style={{ background: "var(--bz-border)" }}
          />
          {[1, 2].map((i) => (
            <div
              key={i}
              className="h-16 rounded"
              style={{ background: "var(--bz-border)", opacity: 0.4 }}
            />
          ))}
        </div>
      </div>
    );
  }

  if (!visaInfo) {
    return (
      <div className="space-y-6 animate-in fade-in duration-500">
        <VisaMasthead />
        <PortalEmptyState
          icon={Plane}
          title={
            needsClientSelection
              ? "Select a client to view visa information"
              : "No visa information"
          }
          description={
            needsClientSelection
              ? "Choose a client from the portal selector to inspect their immigration status."
              : "Visa details will appear here once your immigration process begins."
          }
        />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <VisaMasthead />

      {/* Current Visa */}
      {visaInfo.current ? (
        <section className="rounded-xl border p-6 space-y-4" style={CARD_STYLE}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Plane
                className="w-5 h-5"
                style={{ color: "var(--bz-accent-warm)" }}
              />
              <h2 className="text-lg font-semibold">Current Visa</h2>
            </div>
            <StatusBadge status={visaInfo.current.status} />
          </div>

          <div className="space-y-3">
            <InfoRow label="Visa Type" value={visaInfo.current.type} />
            <InfoRow
              label="Permit Number"
              value={visaInfo.current.permitNumber}
            />
            <InfoRow label="Sponsor" value={visaInfo.current.sponsor} />

            <div
              className="pt-3 border-t"
              style={{ borderColor: "var(--bz-border)" }}
            >
              <InfoRow
                label="Issue Date"
                value={new Date(visaInfo.current.issueDate).toLocaleDateString(
                  "en-US",
                  {
                    month: "long",
                    day: "numeric",
                    year: "numeric",
                  },
                )}
              />
              <InfoRow
                label="Expiry Date"
                value={new Date(visaInfo.current.expiryDate).toLocaleDateString(
                  "en-US",
                  {
                    month: "long",
                    day: "numeric",
                    year: "numeric",
                  },
                )}
                chip={
                  visaInfo.current.daysRemaining !== null
                    ? {
                        text:
                          visaInfo.current.daysRemaining <= 0
                            ? `Expired ${Math.abs(visaInfo.current.daysRemaining)}d ago`
                            : visaInfo.current.daysRemaining <= 365
                              ? `⏰ ${visaInfo.current.daysRemaining}d left`
                              : `${Math.floor(visaInfo.current.daysRemaining / 30)}mo left`,
                        tone:
                          visaInfo.current.daysRemaining <= 0
                            ? "danger"
                            : visaInfo.current.daysRemaining <= 60
                              ? "warning"
                              : "success",
                      }
                    : undefined
                }
              />
            </div>
          </div>

          {/* Days Remaining Banner with 2-month Alert */}
          {visaInfo.current.daysRemaining !== null && (
            <div
              className={cn(
                "mt-4 p-4 rounded-lg flex items-start gap-3 border",
                visaInfo.current.daysRemaining <= 60 &&
                  "animate-pulse border-2",
              )}
              style={
                visaInfo.current.daysRemaining <= 60
                  ? {
                      background:
                        "color-mix(in srgb, var(--state-danger) 8%, transparent)",
                      borderColor:
                        "color-mix(in srgb, var(--state-danger) 40%, transparent)",
                    }
                  : {
                      background:
                        "color-mix(in srgb, var(--state-success) 6%, transparent)",
                      borderColor:
                        "color-mix(in srgb, var(--state-success) 25%, transparent)",
                    }
              }
            >
              <Clock
                className="w-5 h-5 mt-0.5"
                style={{
                  color:
                    visaInfo.current.daysRemaining <= 60
                      ? "var(--state-danger)"
                      : "var(--state-success)",
                }}
              />
              <div className="flex-1">
                <div className="flex items-baseline gap-2">
                  <span
                    className="text-2xl font-bold font-mono"
                    style={{
                      color:
                        visaInfo.current.daysRemaining <= 60
                          ? "var(--state-danger)"
                          : "var(--state-success)",
                    }}
                  >
                    {visaInfo.current.daysRemaining}
                  </span>
                  <span
                    className="text-sm font-semibold"
                    style={{
                      color:
                        visaInfo.current.daysRemaining <= 60
                          ? "var(--state-danger)"
                          : "var(--state-success)",
                    }}
                  >
                    days remaining
                  </span>
                </div>
                <p
                  className="text-xs mt-1"
                  style={{
                    color:
                      visaInfo.current.daysRemaining <= 60
                        ? "var(--state-danger)"
                        : "var(--bz-text-2)",
                    fontWeight:
                      visaInfo.current.daysRemaining <= 60 ? 500 : 400,
                  }}
                >
                  {visaInfo.current.daysRemaining <= 60
                    ? "Your visa expires in less than 2 months. Please contact us immediately to begin renewal."
                    : "Your visa is valid. We will notify you when renewal is needed."}
                </p>
              </div>
            </div>
          )}
        </section>
      ) : (
        <PortalEmptyState icon={Plane} title="No active visa information" />
      )}

      {/* Documents */}
      {visaInfo.documents && visaInfo.documents.length > 0 && (
        <section className="rounded-xl border p-6 space-y-4" style={CARD_STYLE}>
          <div className="flex items-center gap-2">
            <FileText
              className="w-5 h-5"
              style={{ color: "var(--bz-accent-warm)" }}
            />
            <h2 className="text-lg font-semibold">Related Documents</h2>
          </div>

          <div className="space-y-2">
            {visaInfo.documents.map((doc) => (
              <DocumentCard key={doc.id} document={doc} />
            ))}
          </div>
        </section>
      )}

      {/* History */}
      {visaInfo.history && visaInfo.history.length > 0 && (
        <section className="rounded-xl border p-6 space-y-4" style={CARD_STYLE}>
          <div className="flex items-center gap-2">
            <Calendar
              className="w-5 h-5"
              style={{ color: "var(--bz-accent-warm)" }}
            />
            <h2 className="text-lg font-semibold">Visa History</h2>
          </div>

          <div className="space-y-3">
            {visaInfo.history.map((item) => (
              <HistoryCard key={item.id} item={item} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

// Sub-components
function InfoRow({
  label,
  value,
  chip,
}: {
  label: string;
  value: string;
  chip?: { text: string; tone: StateTone };
}) {
  return (
    <div className="flex items-center justify-between py-2">
      <span className="text-sm" style={{ color: "var(--bz-text-2)" }}>
        {label}
      </span>
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-right">{value}</span>
        {chip && (
          <span
            className="text-[10px] px-1.5 py-0.5 rounded-full font-semibold"
            style={toneStyle(chip.tone)}
          >
            {chip.text}
          </span>
        )}
      </div>
    </div>
  );
}

function DocumentCard({ document }: { document: PortalDocument }) {
  const getStatusStyle = (status: string): React.CSSProperties => {
    switch (status) {
      case "verified":
        return wellChipStyle("success");
      case "pending":
        return wellChipStyle("warning");
      case "expired":
        return wellChipStyle("danger");
      default:
        return {
          border: "1px solid var(--bz-border)",
          color: "var(--bz-text-2)",
        };
    }
  };

  return (
    <div
      className="rounded-lg border p-3 transition-colors"
      style={{
        background: "var(--glass-rim)",
        borderColor: "var(--bz-border)",
      }}
    >
      <div className="flex items-center gap-3">
        <div
          className="p-2 rounded-md"
          style={{
            background: "color-mix(in srgb, var(--bz-copper) 10%, transparent)",
          }}
        >
          <FileText
            className="w-4 h-4"
            style={{ color: "var(--bz-accent-warm)" }}
          />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">{document.name}</p>
          <div className="flex items-center gap-2 mt-0.5">
            <span
              className="text-xs px-2 py-0.5 rounded-full font-medium"
              style={getStatusStyle(document.status)}
            >
              {document.status}
            </span>
            <span className="text-xs" style={{ color: "var(--bz-text-2)" }}>
              {document.size}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function HistoryCard({ item }: { item: VisaHistoryItem }) {
  const statusStyle = (() => {
    const s = item.status?.toLowerCase();
    if (s === "active" || s === "approved" || s === "completed")
      return wellChipStyle("success");
    if (s === "expired" || s === "rejected" || s === "cancelled")
      return wellChipStyle("danger");
    if (s === "pending" || s === "processing") return wellChipStyle("warning");
    return { border: "1px solid var(--bz-border)", color: "var(--bz-text-2)" };
  })();

  return (
    <div
      className="rounded-lg border p-3 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg"
      style={{
        background: "var(--glass-rim)",
        borderColor: "var(--bz-border)",
      }}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium">{item.type}</p>
          <p className="text-xs mt-0.5" style={{ color: "var(--bz-text-2)" }}>
            {item.period}
          </p>
        </div>
        <span
          className="text-xs px-2 py-1 rounded-full font-medium"
          style={statusStyle}
        >
          {item.status}
        </span>
      </div>
    </div>
  );
}
