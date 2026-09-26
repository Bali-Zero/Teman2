"use client";

import { useEffect, useRef, useState } from "react";
import {
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
import { useVoaCounter } from "../VoaCounter";
import { mergeCheckoutHandoff } from "../checkoutHandoff";
import { voaCopy, type VoaCopyKey } from "../voa-copy";
import {
  clearSubmittedAnswersForHash,
  readSubmittedAnswersForHash,
} from "../submittedAnswers";

/**
 * GARUDA VOA — public result page (owner decision 5, constraints 5a/5b).
 *
 * The API only ever returns `{verdict, reason_codes, ...}` — no PII, no
 * prose (contracts/openapi.yaml EligibilityResult). The DECLINE education
 * copy is built entirely client-side from the answers this browser tab
 * already holds (sessionStorage, written by the wizard before it submitted);
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
const SUBMITTED_FALLBACK: EligibilitySubmission = {
  case_type: "issuance",
  nationality: "",
  purpose: "tourism",
  travellers: 1,
  self_pay: true,
  extension_already_used: false,
};

/**
 * Reads the wizard's hand-off, gated on it being stamped for THIS `hash` —
 * a shared link, another device, or a second check run later in the same
 * tab all carry no entry (or the wrong one) and get no mirror, same as
 * before this fix (see submittedAnswers.ts's TTL/hash-stamp doc). No
 * fallback to the wizard's own resume key any more: that key is never
 * hash-bound, so reading it here would reopen the exact stale-mirror risk
 * this gate exists to close.
 */
function readSubmittedAnswers(hash: string): EligibilitySubmission | null {
  const fallback = SUBMITTED_FALLBACK;
  if (typeof window === "undefined") return null;
  const values = readSubmittedAnswersForHash(hash);
  if (!values) return null;
  const v = values as {
    case_type?: EligibilitySubmission["case_type"];
    purpose?: EligibilitySubmission["purpose"];
    trip?: { nationality?: string; travellers?: number; self_pay?: boolean };
    dates?: { extension_already_used?: boolean };
  };
  return {
    case_type: v.case_type ?? fallback.case_type,
    nationality: v.trip?.nationality ?? fallback.nationality,
    purpose: v.purpose ?? fallback.purpose,
    travellers: v.trip?.travellers ?? fallback.travellers,
    self_pay: v.trip?.self_pay ?? fallback.self_pay,
    extension_already_used:
      v.dates?.extension_already_used ?? fallback.extension_already_used,
  };
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
  const { report } = useVoaCounter();

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
        // The counter's strip turns from the catalogue floor to THIS figure,
        // and keeps it for the upload and checkout screens of this tab.
        report(
          result.verdict === "ACCEPT"
            ? { resultId: hash, verdict: "ACCEPT", priceIdr: result.price_idr }
            : { resultId: hash, verdict: "DECLINE" },
        );
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
      <VerdictSheet
        title={t("verdict.title")}
        lede={t("verdict.deleted.subtitle")}
      >
        <ContentLangSync locale={locale} />
        <p className="voa-flow__lede">
          <a href="/visa/voa">{t("verdict.startAgain")}</a>
        </p>
      </VerdictSheet>
    );
  }

  if (err) {
    return (
      <VerdictSheet title={t("verdict.title")} lede={t(err)}>
        <ContentLangSync locale={locale} />
        <p className="voa-flow__lede">
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
      </VerdictSheet>
    );
  }

  if (!data) {
    return (
      <VerdictSheet
        title={t("verdict.title")}
        lede={t("verdict.loading.subtitle")}
      >
        <ContentLangSync locale={locale} />
        <p className="voa-flow__lede">{t("verdict.loading.body")}</p>
      </VerdictSheet>
    );
  }

  const publicUrl =
    typeof window !== "undefined"
      ? `${window.location.origin}/visa/voa/${hash}`
      : `/visa/voa/${hash}`;

  if (data.verdict === "DECLINE") {
    // No answers in this browser (a shared link, another device, an
    // expired or hash-mismatched entry): the mirror would echo defaults or
    // another check's answers as if the visitor had said them, so it is
    // left out and the rest of the explanation stands on its own.
    const answers = readSubmittedAnswers(hash ?? "");
    const code = primaryDeclineCode(data.reason_codes);
    const edu = code
      ? buildDeclineEducation(code, answers ?? SUBMITTED_FALLBACK, t)
      : null;
    // One copper action per screen: the Oracle route when the code has one,
    // otherwise the WhatsApp route takes the copper.
    const oracleLeads = edu?.routeKind === "oracle";

    return (
      <VerdictSheet
        title={t("verdict.title")}
        lede={t("verdict.decline.subtitle")}
      >
        <ContentLangSync locale={locale} />
        <div className="voa-offer">
          <div ref={stampRef} className="voa-offer__stamp">
            <EmptyStampReveal />
          </div>
          {edu ? (
            <section className="voa-decline">
              {answers ? <p>{edu.mirror}</p> : null}
              <p>{edu.forbids}</p>
              <p className="voa-decline__alt">{edu.alternative}</p>
              <div className="voa-routes">
                {oracleLeads ? (
                  <a
                    href="/visa/match"
                    className="voa-route voa-route--primary"
                    onClick={() =>
                      tracker.ctaClicked("try_visa_match", "/visa/match")
                    }
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
                  className={
                    oracleLeads ? "voa-route" : "voa-route voa-route--primary"
                  }
                  onClick={() =>
                    tracker.ctaClicked("continue_on_whatsapp_decline", "wa.me")
                  }
                >
                  {t("verdict.decline.wa")}
                </a>
              </div>
            </section>
          ) : null}
        </div>
        <div className="voa-verdict__quiet">
          <DeleteCheckControl
            resultId={hash ?? ""}
            onDeleted={() => setDeleted(true)}
          />
          <AppShareBar
            url={publicUrl}
            title={t("verdict.decline.share.title")}
            onShare={(c) => tracker.shareClicked(c)}
          />
        </div>
      </VerdictSheet>
    );
  }

  // ACCEPT — the stamp, the exact price and the key, on one sheet. ORDER IS
  // THE POINT: the step that OPENS the application sits beside the price and
  // above "delete this check", never behind a destructive control.
  return (
    <VerdictSheet
      title={t("verdict.accept.title")}
      lede={
        data.published_filing_deadline
          ? // Deliberately NOT "your filing window": the clock below has a
            // `passed` branch, reachable because this result page is a
            // shareable URL over a stored check, and a header promising a live
            // window above a hero saying the day is gone is a page arguing
            // with itself. This sentence is true in every branch.
            t("verdict.accept.subtitle")
          : t("verdict.accept.subtitleNoDeadline")
      }
    >
      <ContentLangSync locale={locale} />
      <div className="voa-offer">
        <div ref={stampRef} className="voa-offer__stamp">
          <AppStampReveal
            code={formatIDR(data.price_idr)}
            ariaLabel={t("verdict.stamp.aria", {
              price: formatIDR(data.price_idr),
            })}
          />
          <p className="voa-offer__note">{t("verdict.accept.priceFooter")}</p>
        </div>
        {/* Reachable only once `data` is set, which itself requires `hash`
          (see the two effects above), so this is never actually empty. */}
        <MagicLinkRequestForm resultId={hash ?? ""} />
      </div>
      {data.published_filing_deadline ? (
        <SafeClockHero
          deadline={data.published_filing_deadline}
          handoffHref={buildWhatsAppLink("visa", t("verdict.wa.deadlineMsg"))}
        />
      ) : null}
      <NextSteps
        handoffHref={buildWhatsAppLink("visa", t("verdict.wa.beforePayMsg"))}
        hasDeadline={Boolean(data.published_filing_deadline)}
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
      <div className="voa-verdict__quiet">
        <DeleteCheckControl
          resultId={hash ?? ""}
          onDeleted={() => setDeleted(true)}
        />
        <AppShareBar
          url={publicUrl}
          title={t("verdict.share.title")}
          onShare={(c) => tracker.shareClicked(c)}
        />
      </div>
    </VerdictSheet>
  );
}

/**
 * The verdict leg's sheet — the same filed paper the wizard sits on, under
 * the same counter, instead of core's AppFrame (whose inline chrome the
 * funnel's stylesheet cannot reach, and which core's other funnels share).
 */
function VerdictSheet({
  title,
  lede,
  children,
}: {
  title: string;
  lede?: string;
  children: React.ReactNode;
}) {
  return (
    <section
      role="region"
      aria-label={title}
      data-funnel="visa"
      className="voa-sheet voa-sheet--flow"
    >
      <header className="voa-flow__head">
        <h1 className="voa-flow__title">{title}</h1>
        {lede ? <p className="voa-flow__lede">{lede}</p> : null}
      </header>
      {children}
    </section>
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
        // The checkout in this tab prefills it instead of asking again.
        mergeCheckoutHandoff(resultId, { email });
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
          {t("entry.sent.heading")}
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
        clearSubmittedAnswersForHash(resultId);
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
