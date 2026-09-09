"use client";

import { useId, useState } from "react";
import { buildEmailIntent } from "../lib/destinations";
import { contactPageHref } from "../lib/destinations/contact-context";
import { contactSourcePage, contactTopics, isContactTopic, type ContactTopic } from "../lib/destinations/lead-handoff";
import { ContactHandoff } from "./ContactHandoff";
import styles from "./Contact.module.css";

const labels: Record<ContactTopic, string> = {
  general: "A general question", immigration: "Visas & residence", company: "Company setup & licensing",
  tax: "Tax & accounting", property: "Property due diligence", evoa: "E-VOA arrival planning",
  "second-home": "Second Home planning", portal: "Client portal access",
};

export function ContactOptions({ initialTopic, sourcePage }: { initialTopic: ContactTopic; sourcePage: string }) {
  const id = useId();
  const [topic, setTopic] = useState(initialTopic);
  const source = contactSourcePage(sourcePage);
  const email = buildEmailIntent({ subject: `Bali Zero — ${labels[topic]}`, body: `Hello Bali Zero, I would like to discuss ${contactTopics[topic]} (from ${source}).` });
  return <div className={styles.options}>
    <label htmlFor={id}>What would you like to discuss?</label>
    <select id={id} value={topic} onChange={(event) => {
      const nextTopic = event.target.value;
      if (!isContactTopic(nextTopic)) return;
      setTopic(nextTopic);
      if (window.location.pathname === "/contact") {
        window.history.replaceState(window.history.state, "", contactPageHref(nextTopic, source));
      }
    }}>
      {Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
    </select>
    <div className={styles.actions}><ContactHandoff topic={topic} sourcePage={source} className={styles.primary}>Continue on WhatsApp <span aria-hidden="true">↗</span></ContactHandoff><a className={styles.secondary} href={email}>Write an email <span aria-hidden="true">→</span></a></div>
    <p className={styles.note}>Your topic carries into the next step. Review your message before sending.</p>
  </div>;
}
