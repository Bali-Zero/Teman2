import type { Metadata } from "next";
import { Contact } from "../../components/Contact";
import { SiteHeader } from "../../components/Entry";
import { Footer } from "../../components/Footer";
import { isContactTopic } from "../../lib/destinations/lead-handoff";
import { resolveContactSource } from "../../lib/destinations/contact-context";
import styles from "../../components/Contact.module.css";

export const metadata: Metadata = { title: "Contact & office visits — Bali Zero", description: "Contact the Bali Zero team about visas, company setup, tax and property. Find our Kerobokan office, opening hours and appointment details." };

export default async function ContactPage({ searchParams }: { searchParams: Promise<{ topic?: string | string[]; from?: string | string[] }> }) {
  const query = await searchParams;
  const topic = isContactTopic(query.topic) ? query.topic : "general";
  const source = resolveContactSource(query.from);
  return <div className={styles.theme}><a className="skip" href="#main">Skip to content</a><SiteHeader /><main id="main" tabIndex={-1}><Contact dedicated initialTopic={topic} sourcePage={source} /></main><Footer /></div>;
}
