"use client";

import { useRef, useState } from "react";
import { buildEmailIntent } from "../lib/destinations";
import { contactTopics, type ContactTopic } from "../lib/destinations/lead-handoff";
import { assistantContactContext, contactPageHref } from "../lib/destinations/contact-context";
import { ContactHandoff } from "./ContactHandoff";
import styles from "./ZantaraEntry.module.css";

export function ZantaraEntry() {
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const [{ topic, source }, setContext] = useState<{ topic: ContactTopic; source: string }>({ topic: "general", source: "/" });

  return (
    <>
      <button data-assistant-entry ref={trigger} type="button" className={styles.trigger} aria-haspopup="dialog" onClick={() => { setContext(assistantContactContext(new URL(window.location.href))); dialog.current?.showModal(); }}>
        <svg aria-hidden="true" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M20 11.5a8 8 0 0 1-8 8H4l1.6-3.2A8 8 0 1 1 20 11.5Z" /></svg>
        Zantara
      </button>
      <dialog ref={dialog} className={styles.dialog} aria-labelledby="zantara-title" aria-describedby="zantara-availability" onClose={() => trigger.current?.focus()}>
        <div className={styles.heading}>
          <div><span>Bali Zero assistant</span><h2 id="zantara-title">Zantara</h2></div>
          <button className={styles.close} aria-label="Close Zantara" type="button" onClick={() => dialog.current?.close()}>×</button>
        </div>
        <div className={styles.content}>
          <span className={styles.status}>Chat unavailable in this preview</span>
          <div className={styles.context}><span>You're asking about</span><strong>{contactTopics[topic]}</strong><small>From {source}</small></div>
          <p id="zantara-availability">You can still speak with the Bali Zero team about your plans. Choose how you’d like to get in touch.</p>
          <ContactHandoff className={styles.primary} topic={topic} sourcePage={source}>Continue on WhatsApp <span aria-hidden="true">↗</span></ContactHandoff>
          <a className={styles.secondary} href={buildEmailIntent({ subject: `Bali Zero — ${contactTopics[topic]}`, body: `Hello Bali Zero, I would like to discuss ${contactTopics[topic]} (from ${source}).` })}>Email the team <span aria-hidden="true">→</span></a>
          <a className={styles.secondary} href={contactPageHref(topic, source)}>Contact & office details <span aria-hidden="true">→</span></a>
          <p className={styles.note}>Opening a contact link does not send a message.</p>
        </div>
      </dialog>
    </>
  );
}
