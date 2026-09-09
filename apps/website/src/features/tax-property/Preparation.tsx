"use client";
import { useState } from "react";
import { serviceSectionContent } from "../../content/service-section-content";
import styles from "./tools.module.css";

export function Preparation({ family }: { family: "tax" | "property" }) {
  const source = serviceSectionContent[family];
  const [checked, setChecked] = useState<string[]>([]);
  const tax = family === "tax";
  return (
    <div className={styles.split}>
      <div>
        <section className={styles.section}>
          <p className={styles.eyebrow}>01 / Frame the review</p>
          <h2>
            {tax
              ? "Start with what was filed."
              : "Start with the land and its use."}
          </h2>
          <p>
            {tax
              ? "A tax gap review compares your records and previous filings with the obligations that apply to your circumstances. It starts with reconciliation, then identifies questions, corrections and the work needed."
              : "A zoning check brings the exact site and intended activity into the same review. The map is a starting point; the title, permits and proposed agreement still need their own examination."}
          </p>
          <ul className={styles.editorialList}>
            {source.review.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
        <section className={styles.section}>
          <p className={styles.eyebrow}>02 / Bring the evidence</p>
          <h2>A useful first conversation.</h2>
          <p>
            Use this preparation list to see what you have available. These
            selections stay on this page and are cleared when you leave; no
            documents are uploaded.
          </p>
          <div className={styles.sectionHeading}>
            <span role="status">
              {checked.length} of {source.documents.length} ready
            </span>
            <button
              className={styles.quiet}
              onClick={() => setChecked([])}
              disabled={!checked.length}
            >
              Reset checklist
            </button>
          </div>
          <div className={styles.checklist}>
            {source.documents.map((item) => (
              <label key={item}>
                <input
                  type="checkbox"
                  checked={checked.includes(item)}
                  onChange={(e) =>
                    setChecked((prev) =>
                      e.target.checked
                        ? [...prev, item]
                        : prev.filter((v) => v !== item),
                    )
                  }
                />
                <span>{item}</span>
              </label>
            ))}
          </div>
        </section>
        <section className={styles.section}>
          <p className={styles.eyebrow}>03 / Understand the next step</p>
          <h2>Review, findings, then a decision.</h2>
          <ol className={styles.editorialList}>
            {(tax
              ? [
                  "Review registrations, annual returns and the business financial records.",
                  "Reconcile the reporting periods, income and transactions that need checking.",
                  "Discuss proposed corrections and the scope of calculation or filing support.",
                  "Agree the work and quote with the team before implementation.",
                ]
              : [
                  "Identify the exact coordinates, site and intended use.",
                  "Review available zoning records and the applicable local planning documents.",
                  "Check the title, building approvals and draft agreement alongside the site findings.",
                  "Discuss missing records and conditions to resolve before deciding on the transaction.",
                ]
            ).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ol>
        </section>
        <section className={styles.section}>
          <h2>Questions worth asking.</h2>
          {source.faqs.map((faq) => (
            <details key={faq.question}>
              <summary>{faq.question}</summary>
              <p>{faq.answer}</p>
            </details>
          ))}
        </section>
      </div>
      <aside className={styles.dossier}>
        <p className={styles.eyebrow}>A closer look</p>
        <h2>
          {tax
            ? "Find the gap. Plan the correction."
            : "Know the site before you commit."}
        </h2>
        <p>
          {tax
            ? "This preparation guide does not calculate a tax liability, savings estimate or compliance score. Those depend on the records and a professional review."
            : "A map result does not establish ownership, grant permission or replace legal due diligence. Missing coverage is not permission to build."}
        </p>
        <a
          className={styles.primaryLight}
          href={`/contact?topic=${family}&from=${tax ? "%2Ftaxes%2Fgap" : "%2Fzoning"}`}
        >
          Discuss your {family === "tax" ? "tax records" : "property"} →
        </a>
        <a
          className={styles.lightLink}
          href={tax ? "/tax-calendar" : "/property/eligibility"}
        >
          {tax ? "Explore the calendar archive" : "Check property coordinates"}{" "}
          →
        </a>
        <div className={styles.asideRule}>
          <span className={styles.eyebrow}>Service scope</span>
          <ul>
            {source.included.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  );
}
