"use client";

import { use, useEffect, useRef, useState } from "react";
import { useTranslation } from "@/i18n";
import { formatIDR } from "@balizero/core/utils";
import {
  AppFrame,
  AppShareBar,
  AppWhatsAppCTA,
  useFunnelApp,
  useHaptic,
  type FunnelAppName,
} from "@balizero/core";

/** Mirrors `backend/app/routers/garuda_voa.py::VoaResponse` exactly — a flat
 * response of enum/date/bool/string fields. There is no `stay_window` /
 * `checkpoints` nesting on the wire; the backend's own module docstring is
 * explicit that `VoaResponse` structurally cannot carry an internal
 * checkpoint (D-10/D-3/D-1) NOR the D-14 filing-window-opens date — the
 * source states that one two incompatible ways on the same page, so it is
 * withheld rather than published as fact. `published_filing_deadline`
 * (D-7) is the ONLY Safe Clock date this schema can ever carry.
 *
 * Same treatment for decline reasons (fix 2026-07-27, cross-family review):
 * the wire carries `reason_codes` — stable, neutral, language-agnostic
 * machine codes — NEVER the engine-internal English audit prose (which
 * could name an internal checkpoint like "D-10" and was never translated
 * for the id/it visitors this page also serves). See
 * `localizedDeclineReason` below for how a code becomes on-screen copy.
 *
 * `submit_by_date` (owner ruling 2026-07-27, issuance-only): Bali Zero's
 * OWN submit-by commitment for the online funnel — a VOA is issued in a
 * few hours, so we can accept a request up to the day before arrival,
 * counting weekends and Indonesian national holidays/cuti bersama as
 * closed (`backend/services/garuda_flow/operating_calendar.py`). This is
 * an internal operational commitment, NOT an immigration deadline — never
 * render it alongside `filingDeadlineLabel` (the D-7 government date) in a
 * way that implies the two are the same kind of thing. `null` for every
 * extension case and for an issuance case whose entry date falls past the
 * decreed 2026 calendar (fail-closed — never a guessed date). */
interface VoaCheckResult {
  hash: string;
  decision: string; // "ACCEPT" | "DECLINE"
  reason_codes: string[];
  case_type: string;
  nationality: string;
  entry_date: string;
  expiry_date: string;
  last_legal_day: string;
  expiry_is_estimated: boolean;
  published_filing_deadline: string;
  submit_by_date: string | null;
  price_idr: number | null;
  price_source: string | null;
  result_url: string;
}

/** Looks up a decline `reason_code` in `i18n/locales/{en,id,it}.json` under
 * `garudaVoa.result.declineReasons.<CODE>`. An unknown code — e.g. the
 * backend deployed a new `DeclineCode` before this frontend redeployed —
 * degrades to the neutral `declineReasons.unknown` fallback, NEVER to a
 * blank bullet and NEVER to the raw code string: `t()` (see `@/i18n`)
 * returns the lookup key itself when a key is missing from both the
 * current locale and the English default, so `value === key` is exactly
 * the "not found" signal for this i18n implementation. */
function localizedDeclineReason(
  t: (key: string) => string,
  code: string,
): string {
  const key = `garudaVoa.result.declineReasons.${code}`;
  const value = t(key);
  return value === key ? t("garudaVoa.result.declineReasons.unknown") : value;
}

/** The engine's own vocabulary (`backend/services/garuda_flow/eligibility.py::Decision`)
 * — checked in exactly ONE place so no call-site can drift from it. */
const ACCEPT_DECISION = "ACCEPT";
function isAcceptedDecision(decision: string): boolean {
  return decision === ACCEPT_DECISION;
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

const labelStyle: React.CSSProperties = {
  fontSize: "0.62rem",
  letterSpacing: "0.15em",
  textTransform: "uppercase",
  opacity: 0.5,
  color: "var(--color-text-muted)",
  marginBottom: "var(--space-1, 0.3rem)",
};

const mutedItalicStyle: React.CSSProperties = {
  margin: 0,
  fontStyle: "italic",
  color: "var(--color-text-muted)",
};

export default function GarudaVoaResultPage({
  params,
}: {
  params: Promise<{ hash: string }>;
}) {
  const { hash } = use(params);
  const { t } = useTranslation();
  // Same closed-FunnelAppName band-aid as the wizard page — see that file's
  // comment. Runtime-identical, out of this lane's file ownership to fix.
  const tracker = useFunnelApp("voa" as unknown as FunnelAppName, {
    trackView: false,
  });
  const haptic = useHaptic();
  const stampRef = useRef<HTMLDivElement | null>(null);
  const [data, setData] = useState<VoaCheckResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  // Read straight off the URL (not next/navigation's useSearchParams, which
  // would force a Suspense boundary on this already-client page) — pure
  // copy-branching for the in-person-interview reminder, never sent to any
  // API and carries no PII.
  const [caseType, setCaseType] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    setCaseType(new URLSearchParams(window.location.search).get("case_type"));
  }, []);

  useEffect(() => {
    void (async () => {
      try {
        const res = await fetch(`/api/visa/voa/${hash}`);
        if (!res.ok) {
          setErr(t("garudaVoa.result.notFound"));
          return;
        }
        const json = (await res.json()) as VoaCheckResult;
        setData(json);
        tracker.resultViewed(json.hash);
        haptic(12);
      } catch {
        setErr(t("garudaVoa.result.networkError"));
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hash]);

  if (err)
    return (
      <AppFrame
        funnel="visa"
        title={t("garudaVoa.result.title")}
        subtitle={err}
      >
        <p>
          <a href="/visa/voa">{t("garudaVoa.result.startAgain")} →</a>
        </p>
      </AppFrame>
    );
  if (!data)
    return (
      <AppFrame
        funnel="visa"
        title={t("garudaVoa.result.title")}
        subtitle={t("garudaVoa.result.loading")}
      >
        <p style={{ color: "var(--color-text-muted)" }}>
          {t("garudaVoa.result.oneMoment")}
        </p>
      </AppFrame>
    );

  const publicUrl =
    typeof window !== "undefined"
      ? `${window.location.origin}/visa/voa/${data.hash}`
      : `/visa/voa/${data.hash}`;

  // Any decision value other than the engine's exact "ACCEPT" is treated as
  // a decline — err on the side of the safer, WhatsApp-handoff branch
  // rather than risk showing an "approved" stamp on an ambiguous value
  // (charter §6: a decline must never be a bare no; the inverse — a false
  // accept — is worse). See `isAcceptedDecision` for the one place this is
  // ever compared.
  const isEligible = isAcceptedDecision(data.decision);

  if (!isEligible) {
    return (
      <AppFrame
        funnel="visa"
        title={t("garudaVoa.result.decline.title")}
        subtitle={t("garudaVoa.result.decline.subtitle")}
      >
        {data.reason_codes.length > 0 ? (
          <ul
            style={{
              margin: 0,
              paddingLeft: 18,
              display: "grid",
              gap: "var(--space-2, 0.5rem)",
            }}
          >
            {data.reason_codes.map((code) => (
              <li key={code}>{localizedDeclineReason(t, code)}</li>
            ))}
          </ul>
        ) : null}
        <AppWhatsAppCTA
          source="garuda_voa"
          headline={t("garudaVoa.result.decline.ctaHeadline")}
          description={t("garudaVoa.result.decline.ctaDescription")}
          resultHash={data.hash}
          context={{ decision: data.decision }}
          whatsappContext={[
            {
              label: t("garudaVoa.result.decline.whatsappContextLabel"),
              value: data.reason_codes[0]
                ? localizedDeclineReason(t, data.reason_codes[0])
                : t("garudaVoa.result.decline.title"),
            },
          ]}
          defaultLabel={t("garudaVoa.wizard.whatsappLabel")}
          onCaptured={({ leadIntentId }) =>
            tracker.whatsappHandoff(leadIntentId)
          }
        />
        <AppShareBar
          url={publicUrl}
          title={t("garudaVoa.result.shareTitle")}
          onShare={(c) => tracker.shareClicked(c)}
        />
      </AppFrame>
    );
  }

  return (
    <AppFrame
      funnel="visa"
      title={t("garudaVoa.result.eligible.title")}
      subtitle={t("garudaVoa.result.eligible.subtitle")}
      footer={<>{t("garudaVoa.result.footer")}</>}
    >
      {/* FIX 5 (product honesty): the engine does not verify nationality
       * against an eligible-country list — this is the one calm caveat that
       * keeps an ACCEPT from overclaiming on that specific point. */}
      <p style={mutedItalicStyle}>
        {t("garudaVoa.result.eligible.nationalityCaveat")}
      </p>

      <section>
        <div style={labelStyle}>{t("garudaVoa.result.stayWindowHeading")}</div>
        <p style={{ margin: 0, fontSize: "clamp(1rem, 2.4vw, 1.2rem)" }}>
          {t("garudaVoa.result.entryLabel")}: {formatIsoDate(data.entry_date)}
          {" — "}
          {t("garudaVoa.result.mustLeaveByLabel")}:{" "}
          {formatIsoDate(data.expiry_date)}
        </p>
        {data.expiry_is_estimated ? (
          <p style={mutedItalicStyle}>
            {t("garudaVoa.result.expiryEstimatedNote")}
          </p>
        ) : null}
      </section>

      {/* Owner ruling 2026-07-27, issuance-only: Bali Zero's OWN submit-by
       * commitment — never a government deadline (see the interface
       * comment above and `submitByNote`'s copy). Only present when the
       * backend could compute it; a null here means either an extension
       * case (untouched by this rule) or a fail-closed issuance case, and
       * this section simply does not render. */}
      {data.submit_by_date ? (
        <section>
          <div style={labelStyle}>{t("garudaVoa.result.submitByHeading")}</div>
          <p style={{ margin: 0, fontSize: "clamp(1rem, 2.4vw, 1.2rem)" }}>
            <strong>{t("garudaVoa.result.submitByLabel")}</strong>:{" "}
            {formatIsoDate(data.submit_by_date)}
          </p>
          <p
            style={{
              margin: 0,
              fontSize: "var(--text-sm, 0.85rem)",
              color: "var(--color-text-muted)",
            }}
          >
            {t("garudaVoa.result.submitByNote")}
          </p>
        </section>
      ) : null}

      {data.reason_codes.length > 0 ? (
        <section>
          <div style={labelStyle}>{t("garudaVoa.result.reasonsHeading")}</div>
          <ul
            style={{
              margin: 0,
              paddingLeft: 18,
              display: "grid",
              gap: "var(--space-2, 0.5rem)",
            }}
          >
            {data.reason_codes.map((code) => (
              <li key={code}>{localizedDeclineReason(t, code)}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {/* Only the one published Ngurah Rai date the backend actually
       * returns — `published_filing_deadline` (D-7). No internal-checkpoint
       * shape to consume: VoaResponse structurally cannot carry D-10/D-3/D-1,
       * and it deliberately does not carry a filing-window-OPENS date either
       * — the source states that one two incompatible ways, so it is never
       * published as fact (see the router's module docstring). */}
      <section ref={stampRef}>
        <div style={labelStyle}>
          {t("garudaVoa.result.filingWindowHeading")}
        </div>
        <p style={{ margin: 0, fontSize: "clamp(1rem, 2.4vw, 1.2rem)" }}>
          <strong>{t("garudaVoa.result.filingDeadlineLabel")}</strong>:{" "}
          {formatIsoDate(data.published_filing_deadline)}
        </p>
        <p
          style={{
            margin: 0,
            fontSize: "var(--text-sm, 0.85rem)",
            color: "var(--color-text-muted)",
          }}
        >
          {t("garudaVoa.result.filingWindowDisclaimer")}
        </p>
      </section>

      {caseType === "extension" ? (
        <p style={mutedItalicStyle}>{t("garudaVoa.result.inPersonNote")}</p>
      ) : null}

      <section>
        <div style={labelStyle}>{t("garudaVoa.result.priceHeading")}</div>
        {data.price_idr ? (
          <>
            <div
              style={{
                fontFamily: "var(--font-serif, Georgia, serif)",
                fontSize: "clamp(1.5rem, 4vw, 2rem)",
                color: "var(--accent-funnel-text, var(--accent-funnel))",
              }}
            >
              {formatIDR(data.price_idr)}
            </div>
            <div
              style={{
                fontSize: "var(--text-sm, 0.85rem)",
                color: "var(--color-text-muted)",
              }}
            >
              {t("garudaVoa.result.priceNote", {
                source: data.price_source ?? "PricingTool",
              })}
            </div>
          </>
        ) : (
          <p style={mutedItalicStyle}>{t("garudaVoa.result.priceFallback")}</p>
        )}
      </section>

      <AppWhatsAppCTA
        source="garuda_voa"
        headline={t("garudaVoa.result.eligible.ctaHeadline")}
        description={t("garudaVoa.result.eligible.ctaDescription")}
        resultHash={data.hash}
        context={{ decision: data.decision, price_idr: data.price_idr }}
        whatsappContext={[
          {
            label: t("garudaVoa.result.whatsapp.priceLabel"),
            value: data.price_idr
              ? formatIDR(data.price_idr)
              : t("garudaVoa.result.whatsapp.priceUnknown"),
          },
        ]}
        defaultLabel={t("garudaVoa.wizard.whatsappLabel")}
        postScrollLabel={t("garudaVoa.result.eligible.ctaPostScroll")}
        stampRef={stampRef}
        onCaptured={({ leadIntentId }) => tracker.whatsappHandoff(leadIntentId)}
      />

      <AppShareBar
        url={publicUrl}
        title={t("garudaVoa.result.shareTitle")}
        onShare={(c) => tracker.shareClicked(c)}
      />
    </AppFrame>
  );
}
