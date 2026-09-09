import { SiteShell } from "../../components/SiteShell";
import content from "./company-content.json";
import styles from "./supporting.module.css";

const whatsapp = "https://wa.me/628213454721";
const topics = [
  {
    label: "Visa & immigration",
    href: "/services/immigration",
    detail:
      "Applications, residence and the questions around moving to Indonesia.",
  },
  {
    label: "Company & ownership",
    href: "/services/company-setup",
    detail: "PT PMA, business activities and getting established in Indonesia.",
  },
  {
    label: "Tax & property",
    href: "/services",
    detail:
      "The obligations and decisions that come with living and doing business in Bali.",
  },
];

export function CompanyPage({ kind }: { kind: keyof typeof content }) {
  const record = content[kind];
  const careers = kind === "careers";
  return (
    <SiteShell
      className={styles.root}
      context={{ label: "Our company", href: "/about" }}
    >
      <main id="main-content" className={styles.companyMain} tabIndex={-1}>
        <header className={styles.companyHero}>
          <div>
            <span className={styles.eyebrow}>
              Company · {careers ? "Careers" : "Press"}
            </span>
            <h1>{record.title}</h1>
            <p className={styles.lead}>{record.paragraphs[0]}</p>
          </div>
          <figure className={styles.companyImage}>
            <img
              src={
                careers ? "/assets/adit-site-bg.png" : "/assets/villa-wall.png"
              }
              alt={
                careers
                  ? "Adit, Bali Zero's setup supervisor"
                  : "Architectural detail in Bali"
              }
              width="900"
              height="1100"
            />
            <figcaption>
              {careers
                ? "People, experience and local knowledge."
                : "Bali. The place behind the work."}
            </figcaption>
          </figure>
        </header>
        <section
          className={styles.companyInvitation}
          aria-labelledby="invitation-heading"
        >
          <span className={styles.eyebrow}>
            {careers ? "Start a conversation" : "Press enquiries"}
          </span>
          <div>
            <h2 id="invitation-heading">
              {careers
                ? "Tell us what you do."
                : "A source for your next story."}
            </h2>
            <p>{record.paragraphs.at(-1)}</p>
            <div className={styles.actionRow}>
              <a
                className={styles.primaryLink}
                href={`${whatsapp}?text=${encodeURIComponent(careers ? "Hi Bali Zero, I would like to introduce myself for future opportunities." : "Hi Bali Zero, I have a media enquiry.")}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                {careers
                  ? "Introduce yourself on WhatsApp"
                  : "Contact us on WhatsApp"}{" "}
                ↗
              </a>
              {!careers && (
                <a
                  className={styles.textLink}
                  href="mailto:info@balizero.com?subject=Press%20enquiry"
                >
                  Email a press enquiry ↗
                </a>
              )}
            </div>
          </div>
        </section>
        <section
          className={styles.companyResources}
          aria-labelledby="resources-heading"
        >
          <div>
            <span className={styles.eyebrow}>
              {careers ? "Get to know us" : "Background reading"}
            </span>
            <h2 id="resources-heading">
              {careers
                ? "The work behind the name."
                : "Understand the context."}
            </h2>
            <a className={styles.textLink} href={careers ? "/team" : "/book"}>
              {careers ? "Meet the team" : "Read the Bali Zero book"} ↗
            </a>
          </div>
          <div>
            {topics.map((topic, index) => (
              <a
                key={topic.href}
                href={topic.href}
                className={styles.resourceRow}
              >
                <span className={styles.eyebrow}>0{index + 1}</span>
                <div>
                  <h3>{topic.label}</h3>
                  <p>{topic.detail}</p>
                </div>
                <span aria-hidden="true">↗</span>
              </a>
            ))}
            <a className={styles.textLink} href="/news">
              Read the journal ↗
            </a>
          </div>
        </section>
      </main>
    </SiteShell>
  );
}
