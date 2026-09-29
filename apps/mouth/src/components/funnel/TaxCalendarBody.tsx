"use client";
import { useMemo, useState, useEffect, type CSSProperties } from "react";
import { DeadlineBadge } from "@balizero/core";
import type { TaxDeadline } from "@/app/api/tax-calendar/deadlines";
import { trackTaxDashboardViewed } from "@/lib/analytics";

export function TaxCalendarBody({
  deadlines,
  regencies,
}: {
  deadlines: TaxDeadline[];
  regencies: string[];
}) {
  const [kind, setKind] = useState<TaxDeadline["kind"] | "ALL">("ALL");
  const [regency, setRegency] = useState("");

  useEffect(() => {
    trackTaxDashboardViewed("active", deadlines.length);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = useMemo(() => {
    return deadlines.filter(
      (d) =>
        (kind === "ALL" || d.kind === kind) &&
        (!regency || d.regency === regency || !d.regency),
    );
  }, [deadlines, kind, regency]);

  return (
    <section style={{ fontFamily: "var(--font-sans)" }}>
      <header
        style={{
          display: "flex",
          gap: "var(--space-3)",
          marginBottom: "var(--space-6)",
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        {(["ALL", "PPh", "PPN", "LKPM", "PB1"] as const).map((k) => (
          <button
            key={k}
            onClick={() => setKind(k)}
            className={k === kind ? "pill pill-active" : "pill"}
            style={{
              padding: "var(--space-2) var(--space-4)",
              borderRadius: "999px",
              border: "1px solid var(--r19-line)",
              background:
                k === kind ? "var(--r19-copper)" : "var(--r19-surface)",
              color: k === kind ? "var(--r19-cta-ink)" : "var(--r19-ink)",
              cursor: "pointer",
              fontFamily: "var(--font-sans)",
            }}
          >
            {k}
          </button>
        ))}
        <select
          value={regency}
          onChange={(e) => setRegency(e.target.value)}
          style={{
            padding: "var(--space-2) var(--space-3)",
            borderRadius: "8px",
            border: "1px solid var(--r19-line)",
            background: "var(--r19-surface)",
            color: "var(--r19-ink)",
            fontFamily: "var(--font-sans)",
          }}
        >
          <option value="">All regencies</option>
          {regencies.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        <a
          href="/api/tax-calendar/ical"
          download="bali-tax-deadlines.ics"
          className="btn"
          style={{
            display: "inline-flex",
            alignItems: "center",
            minHeight: "44px",
            padding: "var(--space-2) var(--space-4)",
            borderRadius: "8px",
            border: "1px solid var(--r19-line)",
            background: "var(--r19-surface)",
            color: "var(--r19-ink)",
            fontFamily: "var(--font-sans)",
            textDecoration: "none",
          }}
        >
          Export iCal
        </a>
      </header>
      <ul
        style={{
          display: "grid",
          gap: "var(--space-4)",
          listStyle: "none",
          padding: 0,
          margin: 0,
        }}
      >
        {filtered.map((d) => (
          <li
            key={d.id}
            style={{
              display: "grid",
              gridTemplateColumns: "auto 1fr auto",
              gap: "var(--space-4)",
              padding: "var(--space-4)",
              background: "var(--r19-surface)",
              border: "1px solid var(--r19-line)",
              borderRadius: "8px",
              alignItems: "center",
            }}
          >
            <div
              style={
                {
                  "--color-border-subtle": "var(--r19-line)",
                  "--state-danger": "var(--r19-copper)",
                  "--state-success": "var(--r19-copper)",
                  "--state-warning": "var(--r19-copper)",
                  background: "var(--r19-wash)",
                  borderRadius: "8px",
                  padding: "var(--space-1)",
                } as CSSProperties
              }
            >
              <DeadlineBadge date={new Date(d.date)} />
            </div>
            <div>
              <strong
                style={{
                  color: "var(--r19-ink)",
                  display: "block",
                  fontFamily: "var(--font-serif)",
                  fontSize: "1.0625rem",
                  fontWeight: 500,
                }}
              >
                {d.title}
              </strong>
              <div
                style={{
                  color: "var(--r19-muted)",
                  fontFamily: "var(--font-sans)",
                  fontSize: "0.875rem",
                  margin: "var(--space-1) 0",
                }}
              >
                {d.kind}
                {d.regency ? ` · ${d.regency}` : ""}
              </div>
              <p
                style={{
                  color: "var(--r19-muted)",
                  fontFamily: "var(--font-sans)",
                  margin: 0,
                }}
              >
                {d.description}
              </p>
            </div>
            <a
              href="https://wa.me/628213454721?text=Delega%20Bali%20Zero%20SPT"
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-primary"
              style={{
                display: "inline-flex",
                alignItems: "center",
                minHeight: "44px",
                padding: "var(--space-2) var(--space-4)",
                borderRadius: "8px",
                background: "var(--r19-copper)",
                color: "var(--r19-cta-ink)",
                fontFamily: "var(--font-sans)",
                textDecoration: "none",
                fontWeight: 600,
                whiteSpace: "nowrap",
              }}
            >
              Delegate to us
            </a>
          </li>
        ))}
      </ul>
      <p
        style={{
          marginTop: "var(--space-6)",
          color: "var(--r19-muted)",
          fontFamily: "var(--font-sans)",
          fontSize: "0.8125rem",
        }}
      >
        Dates shown are the next occurrence per obligation. PPh 25, PPN and both
        SPT Tahunan returns move forward if the computed date lands on a
        Saturday or Sunday; they are not shifted for Indonesian public holidays.
        LKPM and PB1 dates are shown as computed, unshifted.
      </p>
    </section>
  );
}
