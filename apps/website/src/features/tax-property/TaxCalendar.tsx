"use client";
import { useState } from "react";
import {
  filterDeadlines,
  TAX_ARCHIVE,
  TAX_KINDS,
  TAX_REGENCIES,
  type TaxFilter,
} from "./tax-calendar";
import styles from "./tools.module.css";

export function TaxCalendar() {
  const [kind, setKind] = useState<TaxFilter>("ALL");
  const [regency, setRegency] = useState("");
  const records = filterDeadlines(TAX_ARCHIVE, kind, regency);
  const exportHref = `/api/tax-calendar/ical?${new URLSearchParams({ kind, regency })}`;
  return (
    <>
      <aside className={styles.notice}>
        <strong>Historical calendar · April–July 2026</strong>
        <p>
          The previous calendar contains six archived records. Their dates and
          source notes have not been verified for current filing. There are no
          confirmed upcoming deadlines in this preview. Ask the tax team to
          confirm your taxpayer, period and local requirements.
        </p>
      </aside>
      <div className={styles.split}>
        <aside className={styles.sidebar}>
          <span className={styles.eyebrow}>Find a record</span>
          <fieldset className={styles.filters}>
            <legend>Obligation type</legend>
            {TAX_KINDS.map((k) => (
              <button
                type="button"
                key={k}
                aria-pressed={kind === k}
                onClick={() => setKind(k)}
              >
                {k === "ALL" ? "All obligations" : k}
              </button>
            ))}
          </fieldset>
          <label className={styles.field}>
            Regency
            <select
              value={regency}
              onChange={(e) => setRegency(e.target.value)}
            >
              <option value="">All regencies</option>
              {TAX_REGENCIES.map((r) => (
                <option key={r}>{r}</option>
              ))}
            </select>
          </label>
          <p className={styles.small}>
            National records remain visible when you select a regency.
          </p>
          <a
            className={styles.secondary}
            download="bali-tax-archive.ics"
            href={exportHref}
          >
            Export filtered archive (.ics) ↓
          </a>
          <a className={styles.textLink} href="/taxes/gap">
            Prepare a tax review →
          </a>
        </aside>
        <section aria-label="Tax calendar records">
          <div className={styles.sectionHeading}>
            <h2>Dates on record</h2>
            <span role="status">
              {records.length} {records.length === 1 ? "record" : "records"}
            </span>
          </div>
          {records.length ? (
            <ol className={styles.timeline}>
              {records.map((d) => (
                <li key={d.id}>
                  <time className={styles.date} dateTime={d.date.slice(0, 10)}>
                    <strong>{d.date.slice(8, 10)}</strong>
                    <span>
                      {new Date(d.date).toLocaleDateString("en-GB", {
                        month: "short",
                        year: "numeric",
                        timeZone: "UTC",
                      })}
                    </span>
                  </time>
                  <div>
                    <span className={styles.eyebrow}>
                      {d.kind} / {d.regency ?? "National"}
                    </span>
                    <h3>{d.title}</h3>
                    <details>
                      <summary>View archived record</summary>
                      <p className={styles.small}>Unverified source note</p>
                      <p>{d.description}</p>
                      <p className={styles.small}>
                        Retained from the previous calendar. No recurrence or
                        reminder subscription is enabled.
                      </p>
                      <a
                        className={styles.textLink}
                        href="/contact?topic=tax&from=%2Ftax-calendar"
                      >
                        Ask the tax team about this period →
                      </a>
                    </details>
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <div className={styles.empty}>
              <h3>No records match this view.</h3>
              <button
                className={styles.secondary}
                onClick={() => {
                  setKind("ALL");
                  setRegency("");
                }}
              >
                Reset filters
              </button>
            </div>
          )}
        </section>
      </div>
    </>
  );
}
