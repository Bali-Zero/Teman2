import type { Metadata } from "next";
import Link from "next/link";
import { SiteHeader } from "../../components/Entry";
import { Footer } from "../../components/Footer";
import { company, companyExpertise, workingSteps } from "../../content/company";
import { founders } from "../../content/team";
import styles from "../../components/Company.module.css";

export const metadata: Metadata = {
  title: "Our story — Bali Zero",
  description: "Meet the people behind Bali Zero in Kerobokan and explore how to work with our immigration, company, tax and property teams.",
};

export default function AboutPage() {
  return (
    <div className={styles.theme}>
      <a className="skip" href="#main">Skip to content</a>
      <SiteHeader />
      <main id="main" tabIndex={-1} className={styles.page}>
        <section className={styles.hero} aria-labelledby="about-heading">
          <div className={styles.heroCopy}>
            <span className={styles.eyebrow}>Our story · {company.location}</span>
            <h1 id="about-heading">Local knowledge.{" "}<br />A human connection.</h1>
            <p>Building a life or a business in Indonesia brings connected questions. Bali Zero brings immigration, company, tax and property guidance into the same conversation.</p>
            <Link className={styles.textLink} href="#our-beginning">Get to know Bali Zero <span aria-hidden="true">↓</span></Link>
          </div>
          <div className={styles.portraits}>
            {founders.map((person) => (
              <figure key={person.name}>
                <img src={person.image} alt={person.name} width="360" height="450" />
                <figcaption><strong>{person.name}</strong><span>{person.role}</span></figcaption>
              </figure>
            ))}
          </div>
        </section>
        <section className={styles.story} aria-labelledby="our-beginning">
          <div><span className={styles.eyebrow}>Our beginning</span><h2 id="our-beginning">A clearer way to get started.</h2></div>
          <div className={styles.prose}>
            <p>{company.beginning}</p><p>{company.approach}</p>
            <Link className={styles.textLink} href="/team">Meet our team <span aria-hidden="true">→</span></Link>
          </div>
        </section>
        <section className={styles.method} aria-labelledby="working-together">
          <div className={styles.methodIntro}><span className={styles.eyebrow}>How to work with us</span><h2 id="working-together">From a question{" "}<br />to a practical next step.</h2><p>Use the information here to prepare, then bring your particular situation to the team.</p></div>
          <ol className={styles.steps}>
            {workingSteps.map((step) => (
              <li key={step.title}><h3>{step.title}</h3><p>{step.description}</p><Link className={styles.textLink} href={step.href}>{step.label} <span aria-hidden="true">→</span></Link></li>
            ))}
          </ol>
        </section>
        <section className={styles.expertise} aria-labelledby="company-expertise">
          <div className={styles.expertiseIntro}><span className={styles.eyebrow}>Connected expertise</span><h2 id="company-expertise">The work behind{" "}<br />your next chapter.</h2><p>Explore each area to understand the questions, preparation and services involved.</p></div>
          <div className={styles.expertiseList}>
            {companyExpertise.map((area) => (
              <div key={area.title} className={styles.expertiseRow}>
                <h3><Link href={area.href}>{area.title}<span aria-hidden="true">↗</span></Link></h3><p>{area.description}</p>
              </div>
            ))}
          </div>
        </section>
        <section className={styles.knowledge} aria-labelledby="shared-knowledge">
          <span className={styles.eyebrow}>What we share</span><h2 id="shared-knowledge">Knowledge beyond the conversation.</h2>
          <p>Our Journal explores Indonesian regulatory changes, business questions, tax and property issues. Read around your situation, then use the related service pages to turn a broad topic into a focused question.</p>
          <Link className={styles.textLink} href="/journal">Read the Journal <span aria-hidden="true">→</span></Link>
        </section>
        <aside className={styles.invitation}>
          <div><span className={styles.eyebrow}>Let’s talk</span><h2>Start with your situation.</h2><p>A move, a business, a property decision. Tell us where you are in the process.</p></div>
          <Link className={styles.button} href="/contact?from=about">Talk to our team <span aria-hidden="true">→</span></Link>
        </aside>
      </main>
      <Footer />
    </div>
  );
}
