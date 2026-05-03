"use client";
import { useMemo, useState, useEffect } from "react";
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
    <section>
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
              border: "1px solid var(--color-border-subtle)",
              background:
                k === kind ? "var(--accent-funnel)" : "var(--surface-raised)",
              color:
                k === kind ? "var(--text-on-accent)" : "var(--text-primary)",
              cursor: "pointer",
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
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--color-border-subtle)",
            background: "var(--surface-raised)",
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
            padding: "var(--space-2) var(--space-4)",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--color-border-subtle)",
            background: "var(--surface-raised)",
            color: "var(--text-primary)",
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
              background: "var(--surface-raised)",
              borderRadius: "var(--radius-lg)",
              alignItems: "center",
            }}
          >
            <DeadlineBadge date={new Date(d.date)} />
            <div>
              <strong style={{ display: "block", fontSize: "1.0625rem" }}>
                {d.title}
              </strong>
              <div
                style={{
                  color: "var(--text-secondary)",
                  fontSize: "0.875rem",
                  margin: "var(--space-1) 0",
                }}
              >
                {d.kind}
                {d.regency ? ` · ${d.regency}` : ""}
              </div>
              <p style={{ margin: 0, color: "var(--text-secondary)" }}>
                {d.description}
              </p>
            </div>
            <a
              href="https://wa.me/628213107363?text=Delega%20Bali%20Zero%20SPT"
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-primary"
              style={{
                padding: "var(--space-2) var(--space-4)",
                borderRadius: "var(--radius-md)",
                background: "var(--accent-funnel)",
                color: "var(--text-on-accent)",
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
    </section>
  );
}
