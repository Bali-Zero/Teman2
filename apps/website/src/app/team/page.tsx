import type { Metadata } from "next";
import Link from "next/link";
import { SiteHeader } from "../../components/Entry";
import { Footer } from "../../components/Footer";
import { boardMember, founders, responsibilityGroups, teamMembers } from "../../content/team";
import styles from "../../components/Team.module.css";
import "../../styles/brand-fonts.css";

export const metadata: Metadata = {
  title: "Our team — Bali Zero",
  description: "Meet the founders and team behind Bali Zero, with responsibilities across setup, tax, accounting and digital projects.",
};

export default function TeamPage() {
  return (
    <div className={styles.pageTheme}>
      <a className="skip" href="#main">Skip to content</a>
      <SiteHeader />
      <main id="main" className={styles.page} tabIndex={-1}>
        <div className={styles.pageIntro}>
          <span className={styles.eyebrow}>The people · Kerobokan, Bali</span>
          <h1>Good advice starts with people.</h1>
          <p>Find the people behind the work, from company setup and advisory to tax, accounting and the tools that help you prepare.</p>
          <nav aria-label="Team responsibilities" className={styles.groupNav}>
            <a href="#leadership-heading">Leadership</a>
            {responsibilityGroups.map((group) => <a href={`#${group.id}`} key={group.id}>{group.title}</a>)}
          </nav>
        </div>
        <section aria-labelledby="leadership-heading" className={styles.section}>
          <div className={styles.leadershipIntro}><span className={styles.eyebrow}>The people behind Bali Zero</span><h2 id="leadership-heading">Our founders &amp; leadership</h2><Link className={styles.teamLink} href="/about">Our company story <span aria-hidden="true">→</span></Link></div>
          <div className={styles.leadershipGrid}>
            {[...founders, boardMember].map((person) => (
              <article className={styles.leader} key={person.name}>
                <img src={person.image} alt={person.name} width="360" height="420" loading="lazy" />
                <h3>{person.name}</h3><p>{person.role}</p>
              </article>
            ))}
          </div>
        </section>
        {responsibilityGroups.map((group) => (
          <section aria-labelledby={group.id} className={styles.responsibilityGroup} key={group.id}>
            <div className={styles.groupIntro}><span className={styles.eyebrow}>The people you can turn to</span><h2 id={group.id}>{group.title}</h2><p>{group.description}</p><Link className={styles.teamLink} href={group.link.href}>{group.link.label} <span aria-hidden="true">→</span></Link></div>
            <div className={styles.groupDirectory}>
              {group.people.map((name) => teamMembers.find((person) => person.name === name)!).map((person) => (
                <article className={styles.person} key={person.name}>
                  <div className={styles.portrait}>
                    <img src="/assets/team-ivory-atlas.png" alt={person.name} width="1086" height="1448" loading="lazy" style={{ left: `${person.column * -100}%`, top: `${person.row * -100}%` }} />
                  </div>
                  <h3>{person.name}</h3><p>{person.role}</p>
                  {person.project && <Link className={styles.projectLink} href={person.project.href}>{person.project.label} <span aria-hidden="true">→</span></Link>}
                </article>
              ))}
            </div>
          </section>
        ))}
        <aside className={styles.invitation}>
          <div><h2>Not sure who to speak to?</h2><p>Tell us what you’re planning. We’ll start the conversation.</p></div>
          <Link href="/contact?from=team" className={styles.teamLink}>Talk to our team <span aria-hidden="true">→</span></Link>
        </aside>
      </main>
      <Footer />
    </div>
  );
}
