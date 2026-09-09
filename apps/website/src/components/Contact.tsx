import { destinations } from "../content/destinations";
import { office } from "../content/office";
import type { ContactTopic } from "../lib/destinations/lead-handoff";
import { ContactOptions } from "./ContactOptions";
import styles from "./Contact.module.css";

export function Contact({ dedicated = false, initialTopic = "general", sourcePage = "/" }: {
  dedicated?: boolean; initialTopic?: ContactTopic; sourcePage?: string;
}) {
  const Heading = dedicated ? "h1" : "h2";
  const OfficeHeading = dedicated ? "h2" : "h3";
  return (
    <section className={`${styles.contact} ${dedicated ? styles.full : ""}`} id="contact" aria-labelledby="contact-heading">
      <div>
        <span className={styles.eyebrow}>A real conversation</span>
        <Heading id="contact-heading">Tell us what{" "}<br />you’re planning.</Heading>
        <p>A move, a business, a tax question or a property decision. Choose a topic so your first conversation starts in the right place.</p>
        <ContactOptions initialTopic={initialTopic} sourcePage={sourcePage} />
      </div>
      <aside className={styles.office} aria-labelledby="office-heading">
        <span className={styles.eyebrow}>Find us in Bali</span>
        <OfficeHeading id="office-heading">Our Kerobokan office.</OfficeHeading>
        <address>{office.address}</address>
        <a href={destinations.googleLocation.href} target="_blank" rel="noopener noreferrer">Open directions <span aria-hidden="true">↗</span></a>
        <dl><dt>Office hours</dt><dd>{office.hours}<span>{office.timezone}</span><span>{office.closed}</span></dd><dt>Plan your visit</dt><dd>{office.appointments}</dd></dl>
        <div className={styles.officeLinks}><a href="tel:+628213454721">+62 821 3454 721</a><a href={destinations.email.href}>zantara@balizero.com</a></div>
      </aside>
      {dedicated && <div className={styles.preparation}>
        <div><h2>Before we talk.</h2><ul><li>Have your main question and intended timeline in mind.</li><li>Tell the team whether you are planning a move or already in Indonesia.</li><li>The team will explain which documents are needed for your situation.</li></ul></div>
        <div><h2>Already working with us?</h2><p>Use your client portal for the documents, application updates and conversations available in your account.</p><a className={styles.secondary} href={destinations.myBaliZero.href}>Open my client portal <span aria-hidden="true">↗</span></a><p className={styles.note}>If you need help signing in, choose “Client portal access” above.</p></div>
      </div>}
    </section>
  );
}
