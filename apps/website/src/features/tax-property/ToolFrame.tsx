import type { ReactNode } from "react";
import { SiteShell } from "../../components/SiteShell";
import styles from "./tools.module.css";

export function ToolFrame({
  family,
  title,
  intro,
  children,
}: {
  family: "Tax" | "Property";
  title: string;
  intro: string;
  children: ReactNode;
}) {
  return (
    <SiteShell
      context={{
        label: `${family} services`,
        href: `/services/${family.toLowerCase()}`,
      }}
    >
      <main id="main-content" className={styles.page} tabIndex={-1}>
        <header className={styles.intro}>
          <p className={styles.eyebrow}>Bali Zero / {family} desk</p>
          <h1>{title}</h1>
          <p className={styles.standfirst}>{intro}</p>
        </header>
        <nav className={styles.journeyNav} aria-label={`${family} tools`}>
          {family === "Tax" ? (
            <>
              <a href="/tax-calendar">Calendar</a>
              <a href="/taxes/gap">Tax gap review</a>
              <a href="/services/tax">Services & preparation</a>
            </>
          ) : (
            <>
              <a href="/property/eligibility">Property check</a>
              <a href="/prime">Zoning atlas</a>
              <a href="/zoning">Due diligence</a>
              <a href="/services/property">Property services</a>
            </>
          )}
        </nav>
        {children}
      </main>
    </SiteShell>
  );
}
