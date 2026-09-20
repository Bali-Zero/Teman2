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
import { ContentLangSync } from "@/i18n/ContentLangSync";
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
import { useVoaLocale } from "../useVoaLocale";
import { voaCopy, type VoaCopyKey } from "../voa-copy";

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
  const locale = useVoaLocale();
  const t = voaCopy(locale);
  const stampRef = useRef<HTMLDivElement | null>(null);
  const [hash, setHash] = useState<string | null>(null);
  const [data, setData] = useState<VoaResult | null>(null);
  const [err, setErr] = useState<VoaCopyKey | null>(null);
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
          setErr("verdict.notFound");
          return;
        }
        const result = (await res.json()) as VoaResult;
        setData(result);
        // Verdict + price shown together (they render on the same screen) —
        // one event covers both funnel steps the mandate names.
        tracker.resultViewed(hash);
      } catch {
        setErr("verdict.networkError");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hash]);

  if (deleted) {
    return (
      <AppFrame
        funnel="visa"
        title={t("verdict.title")}
        subtitle={t("verdict.deleted.subtitle")}
      >
        <ContentLangSync locale={locale} />
        <p>
          <a href="/visa/voa">{t("verdict.startAgain")}</a>
        </p>
      </AppFrame>
    );
  }

  if (err) {
    return (
      <AppFrame funnel="visa" title={t("verdict.title")} subtitle={t(err)}>
        <ContentLangSync locale={locale} />
        <p>
          <a href="/visa/voa">{t("verdict.startAgain")}</a> {t("verdict.or")}{" "}
          <a
            href={buildWhatsAppLink("visa", t("hero.wa.message"))}
            target="_blank"
            rel="noopener noreferrer"
          >
            {t("verdict.error.wa")}
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
        title={t("verdict.title")}
        subtitle={t("verdict.loading.subtitle")}
      >
        <ContentLangSync locale={locale} />
        <p style={{ color: "var(--color-text-muted)" }}>
          {t("verdict.loading.body")}
        </p>
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
        title={t("verdict.title")}
        subtitle={t("verdict.decline.subtitle")}
      >
        <ContentLangSync locale={locale} />
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
                  {t("verdict.decline.oracle")}
                </a>
              ) : null}
              <a
                href={buildWhatsAppLink(
                  "visa",
                  t("verdict.decline.wa.message"),
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
                {t("verdict.decline.wa")}
              </a>
            </div>
          </section>
        ) : null}
        <AppShareBar
          url={publicUrl}
          title={t("verdict.decline.share.title")}
          onShare={(c) => tracker.shareClicked(c)}
        />
      </AppFrame>
    );
  }

  // ACCEPT
  return (
    <AppFrame
      funnel="visa"
      title={t("verdict.accept.title")}
      subtitle={
        data.published_filing_deadline
          ? // Deliberately NOT "your filing window": the clock below has a
            // `passed` branch, reachable because this result page is a
            // shareable URL over a stored check, and a header promising a live
            // window above a hero saying the day is gone is a page arguing
            // with itself. This sentence is true in every branch.
            t("verdict.accept.subtitle")
          : t("verdict.accept.subtitleNoDeadline")
      }
      footer={t("verdict.accept.priceFooter")}
    >
      <ContentLangSync locale={locale} />
      {data.published_filing_deadline ? (
        <SafeClockHero
          deadline={data.published_filing_deadline}
          handoffHref={buildWhatsAppLink("visa", t("verdict.wa.deadlineMsg"))}
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
          ariaLabel={t("verdict.stamp.aria", {
            price: formatIDR(data.price_idr),
          })}
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
        headline={t("verdict.human.headline")}
        description={t("verdict.human.description")}
        whatsappContext={[
          {
            label: t("verdict.wa.priceLabel"),
            value: formatIDR(data.price_idr),
          },
        ]}
        defaultLabel={t("verdict.human.cta")}
        postScrollLabel={t("verdict.human.cta")}
        stampRef={stampRef}
        onCaptured={({ leadIntentId }) => tracker.whatsappHandoff(leadIntentId)}
      />
      <NextSteps
        handoffHref={buildWhatsAppLink("visa", t("verdict.wa.beforePayMsg"))}
        hasDeadline={Boolean(data.published_filing_deadline)}
      />
      <AppShareBar
        url={publicUrl}
        title={t("verdict.share.title")}
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
 *
 * THE SENT-STATE COPY NAMES THE CONFIRMATION, and must keep naming it.
 * `auth/continue/page.tsx` is, in its own words, "the one page of the
 * magic-link flow a human sees": it shows WHOSE application the link opens
 * and offers a Continue button, and it exists because a generic Continue
 * behind an unbound landing GET was login CSRF (closed 2026-08-29). A
 * sentence promising the link goes "straight to the passport upload" sells a
 * flow one step shorter than the one the security fix deliberately built.
 */
function MagicLinkRequestForm({ resultId }: { resultId: string }) {
  const tracker = useFunnelApp("visa_voa", { trackView: false });
  const t = voaCopy(useVoaLocale());
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
          {t("entry.heading")}
        </h2>
        <p className="voa-entry__status" role="status">
          {t("entry.sent")}
        </p>
      </section>
    );
  }

  return (
    <section aria-labelledby="voa-entry-heading" className="voa-entry">
      <h2 className="voa-entry__heading" id="voa-entry-heading">
        {t("entry.heading")}
      </h2>
      <p className="voa-entry__body">{t("entry.body")}</p>
      <form className="voa-entry__form" onSubmit={submit}>
        <label className="voa-entry__label" htmlFor="voa-email">
          {t("entry.emailLabel")}
        </label>
        <input
          className="voa-entry__input"
          id="voa-email"
          onChange={(e) => setEmail(e.target.value)}
          placeholder={t("entry.emailPlaceholder")}
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
          {status === "sending" ? t("entry.sending") : t("entry.submit")}
        </button>
        {status === "error" ? (
          <p className="voa-entry__error" role="alert">
            {t("entry.error")}
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
  const t = voaCopy(useVoaLocale());
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
          {t("delete.cta")}
        </button>
      </p>
    );
  }

  if (state === "error") {
    return (
      <div style={{ display: "grid", gap: "var(--space-2, 0.6rem)" }}>
        <p role="alert" style={{ margin: 0, fontWeight: 600 }}>
          {t("delete.error")}
        </p>
        <button
          type="button"
          onClick={remove}
          style={{
            alignSelf: "start",
            padding: "0.6rem 1rem",
            borderRadius: 8,
            border: "1px solid var(--tx-tertiary)",
            background: "none",
            color: "inherit",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          {t("delete.retry")}
        </button>
      </div>
    );
  }

  // confirming | deleting
  const isDeleting = state === "deleting";
  return (
    <div style={{ display: "grid", gap: "var(--space-2, 0.6rem)" }}>
      <p style={{ margin: 0, fontSize: "0.9rem" }}>{t("delete.confirm")}</p>
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
          {isDeleting ? t("delete.deleting") : t("delete.yes")}
        </button>
        <button
          type="button"
          onClick={cancel}
          disabled={isDeleting}
          style={{
            padding: "0.6rem 1rem",
            borderRadius: 8,
            border: "1px solid var(--tx-tertiary)",
            background: "none",
            color: "inherit",
            cursor: isDeleting ? "default" : "pointer",
          }}
        >
          {t("delete.cancel")}
        </button>
      </div>
    </div>
  );
}
