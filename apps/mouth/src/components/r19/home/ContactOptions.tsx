"use client";

import { useId, useState } from "react";
import {
  HomeContactLink,
  contactTopics,
  type ContactTopic,
} from "./HomeContactLink";
import styles from "./Contact.module.css";
export type { ContactTopic } from "./HomeContactLink";

export function ContactOptions({
  initialTopic = "general",
}: {
  initialTopic?: ContactTopic;
  sourcePage?: string;
}) {
  const id = useId();
  const [topic, setTopic] = useState(initialTopic);
  const email =
    "mailto:zantara@balizero.com?subject=" +
    encodeURIComponent("Bali Zero — " + contactTopics[topic]) +
    "&body=" +
    encodeURIComponent(
      "Hello Bali Zero, I would like to discuss " +
        contactTopics[topic] +
        " (from the homepage).",
    );
  return (
    <div className={styles.options}>
      <label htmlFor={id}>What would you like to discuss?</label>
      <select
        id={id}
        value={topic}
        onChange={(event) => {
          const next = event.target.value;
          if (Object.prototype.hasOwnProperty.call(contactTopics, next))
            setTopic(next as ContactTopic);
        }}
      >
        {Object.entries(contactTopics).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
      <div className={styles.actions}>
        <HomeContactLink
          topic={topic}
          section="contact"
          className={styles.primary}
        >
          Continue on WhatsApp <span aria-hidden="true">↗</span>
        </HomeContactLink>
        <a className={styles.secondary} href={email}>
          Write an email <span aria-hidden="true">→</span>
        </a>
      </div>
      <p className={styles.note}>
        Your topic carries into the next step. Review your message before
        sending.
      </p>
    </div>
  );
}
