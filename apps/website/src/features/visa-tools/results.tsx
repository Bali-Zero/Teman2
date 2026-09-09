"use client";
import { useEffect, useState } from "react";
import type { ClockResult, MatchResult, PublicVisaKind } from "./public-api";
import { servicePriceIdentities } from "../../content/service-price-identities";
import { AppFrame } from "./ui";
import { buildWhatsAppLink } from "./whatsapp";

export function daysFromBaliToday(date: string, now = new Date()): number {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Makassar",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const value = (type: string) =>
    parts.find((part) => part.type === type)?.value;
  const today = `${value("year")}-${value("month")}-${value("day")}`;
  return Math.round(
    (Date.parse(`${date}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`)) /
      86_400_000,
  );
}
const dateLabel = (date: string) =>
  new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${date}T00:00:00Z`));
function ShareResult() {
  const [notice, setNotice] = useState("");
  return (
    <>
      <div className="visa-tool-actions">
        <button
          type="button"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(window.location.href);
              setNotice(
                "Result link copied. Anyone with this link can view your result.",
              );
            } catch {
              setNotice(
                "Could not copy. You can copy this page’s address from your browser.",
              );
            }
          }}
        >
          Copy result link
        </button>
        <button type="button" onClick={() => window.print()}>
          Print result
        </button>
      </div>
      {notice && (
        <p role="status" className="visa-tool-small">
          {notice}
        </p>
      )}
    </>
  );
}
export function VisaResult({
  kind,
  reference,
}: {
  kind: PublicVisaKind;
  reference: string;
}) {
  const [data, setData] = useState<ClockResult | MatchResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setError(null);
    fetch(`/api/visa/${kind}/${reference}`, {
      signal: controller.signal,
      cache: "no-store",
      credentials: "omit",
    })
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok)
          throw new Error(body.error ?? "This result is unavailable.");
        return body;
      })
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
      })
      .catch((issue) => {
        if (!controller.signal.aborted)
          setError(
            issue instanceof Error
              ? issue.message
              : "This result is unavailable.",
          );
      });
    return () => controller.abort();
  }, [kind, reference, attempt]);
  const title = kind === "clock" ? "Your visa timeline" : "Your visa route";
  return (
    <AppFrame
      title={title}
      subtitle="A saved planning result, with the reasoning and next steps kept together."
    >
      {error ? (
        <section className="visa-tool-card">
          <h2>We cannot show this result yet.</h2>
          <p role="alert">{error}</p>
          <p>
            No eligibility, price or deadline is being inferred from the
            reference.
          </p>
          <div className="visa-tool-actions">
            <button type="button" onClick={() => setAttempt((n) => n + 1)}>
              Try again
            </button>
            <a href={`/visa/${kind}`}>
              Start a new {kind === "clock" ? "timeline" : "match"}
            </a>
            <a href={`/legacy/visa/${kind}/${reference}`}>
              Open the existing result service
            </a>
          </div>
        </section>
      ) : data?.hash === reference ? (
        <>
          {kind === "clock" ? (
            <ClockResultView result={data as ClockResult} />
          ) : (
            <MatchResultView result={data as MatchResult} />
          )}
          <ShareResult />
        </>
      ) : (
        <p role="status">Loading your saved result…</p>
      )}
    </AppFrame>
  );
}
export function ClockResultView({
  result,
  now,
}: {
  result: ClockResult;
  now?: Date;
}) {
  const days = daysFromBaliToday(result.expiry_date, now);
  const elapsed = days < 0;
  return (
    <div className="visa-tool-result-grid">
      <section className="visa-tool-card visa-tool-wide">
        <p className="visa-tool-eyebrow">
          {result.visa_type} · Recorded expiry
        </p>
        <h2>{dateLabel(result.expiry_date)}</h2>
        <p>
          {elapsed
            ? `${Math.abs(days)} days past the recorded expiry.`
            : days === 0
              ? "The recorded expiry is today."
              : `${days} days until the recorded expiry.`}
        </p>
        {elapsed && (
          <p className="visa-tool-error">
            If you are still in Indonesia, compare this date with your latest
            permit and contact the team promptly if you have no valid extension.
            This saved calculation does not know whether your permit has since
            changed.
          </p>
        )}
        <dl className="visa-tool-facts">
          <div>
            <dt>Entry date used</dt>
            <dd>{dateLabel(result.entry_date)}</dd>
          </div>
          <div>
            <dt>Extension model</dt>
            <dd>
              {result.extensions_possible} × {result.extension_days} days
            </dd>
          </div>
        </dl>
        <p className="visa-tool-small">
          Extension availability in this model is not confirmation that you
          qualify for an extension. Check the conditions of your issued permit.
        </p>
      </section>
      <section className="visa-tool-card visa-tool-wide">
        <h2>
          {elapsed ? "The timeline behind this result" : "Dates to prepare for"}
        </h2>
        <ol className="visa-tool-timeline">
          {result.checkpoints.map((checkpoint, index) => (
            <li key={`${checkpoint.at}-${index}`}>
              <p className="visa-tool-eyebrow">
                {checkpoint.label} · {dateLabel(checkpoint.at)}
              </p>
              <h3>{checkpoint.title}</h3>
              <p>{checkpoint.body}</p>
            </li>
          ))}
        </ol>
        {result.checkpoints.length === 0 && (
          <p>No checkpoints were supplied for this result.</p>
        )}
      </section>
      <section className="visa-tool-card visa-tool-wide">
        <h2>
          {elapsed ? "Review your current status" : "Keep this timeline useful"}
        </h2>
        <p>
          {elapsed
            ? "Bring your latest permit and any extension confirmation to a case review. A past planning date alone does not establish your immigration status."
            : "Keep the permit date and the planning date together. Email reminders and the case discussion remain available in the existing result service."}
        </p>
        <div className="visa-tool-actions">
          <a
            href={buildWhatsAppLink("visa")}
            target="_blank"
            rel="noopener noreferrer"
          >
            Discuss my timeline
          </a>
          {!elapsed && (
            <a href={`/legacy/visa/clock/${result.hash}`}>
              Reminders and case discussion
            </a>
          )}
          <a href="/visa/clock">Recalculate with different details</a>
        </div>
      </section>
    </div>
  );
}
export function MatchResultView({ result }: { result: MatchResult }) {
  const referral = result.referral_mode || !result.recommended_visa;
  // Saved Match GET does not persist the PricingTool source; never present that amount as a current quote.
  const verifiedEstimate =
    result.estimated_cost_idr !== null &&
    Object.values(servicePriceIdentities).some(
      (identity) => identity.key === result.cost_source,
    );
  return (
    <div className="visa-tool-result-grid">
      <section className="visa-tool-card visa-tool-wide">
        <p className="visa-tool-eyebrow">
          {referral
            ? "Individual review needed"
            : "Suggested route to investigate"}
        </p>
        <h2>
          {referral
            ? "Your case needs a closer look."
            : result.recommended_visa}
        </h2>
        <p>{result.reason}</p>
        <dl className="visa-tool-facts">
          <div>
            <dt>Purpose supplied</dt>
            <dd>{result.purpose.replaceAll("_", " ")}</dd>
          </div>
          <div>
            <dt>Planned stay</dt>
            <dd>{result.duration_months} months</dd>
          </div>
          <div>
            <dt>Passport country</dt>
            <dd>{result.nationality}</dd>
          </div>
          <div>
            <dt>Budget band</dt>
            <dd>{result.budget_band.replaceAll("_", " ")}</dd>
          </div>
        </dl>
      </section>
      {!referral && (
        <>
          <section className="visa-tool-card">
            <h2>Price & timing</h2>
            {verifiedEstimate ? (
              <p>
                {new Intl.NumberFormat("en-ID", {
                  style: "currency",
                  currency: "IDR",
                  maximumFractionDigits: 0,
                }).format(result.estimated_cost_idr!)}
                <br />
                <span className="visa-tool-small">
                  Saved estimate · {result.cost_source}. Confirm the current
                  quote and inclusions before proceeding.
                </span>
              </p>
            ) : (
              <p>
                A verified current price is not available with this saved
                result. Request a current quote before committing.
              </p>
            )}
            <p>
              {result.processing_days === null
                ? "No processing estimate was supplied."
                : `The service estimates approximately ${result.processing_days} business days after filing. This is not a guaranteed completion date.`}
            </p>
          </section>
          <section className="visa-tool-card">
            <h2>Other routes to discuss</h2>
            {result.alternatives.length ? (
              <ul>
                {result.alternatives.map((code) => (
                  <li key={code}>{code}</li>
                ))}
              </ul>
            ) : (
              <p>
                The service did not suggest an alternative for these answers.
              </p>
            )}
            <p className="visa-tool-small">
              An alternative code is a discussion point, not a confirmed
              entitlement.
            </p>
          </section>
        </>
      )}
      <section className="visa-tool-card visa-tool-wide">
        <h2>Before you proceed</h2>
        {result.pre_arrival_steps.length ? (
          <ol>
            {result.pre_arrival_steps.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
        ) : (
          <p>
            Discuss your purpose, intended activity and travel dates with the
            team so the preparation requirements can be confirmed.
          </p>
        )}
        <div className="visa-tool-actions">
          <a
            className="visa-tool-primary"
            href={buildWhatsAppLink("visa")}
            target="_blank"
            rel="noopener noreferrer"
          >
            Discuss this route
          </a>
          <a href={`/legacy/visa/match/${result.hash}`}>
            Open the case discussion
          </a>
          <a href="/visa/match">Compare different answers</a>
        </div>
      </section>
    </div>
  );
}
