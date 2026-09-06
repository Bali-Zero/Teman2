import Link from "next/link";
import type { ReactNode } from "react";
import { destinationIntents, getDestination } from "../../content/destinations";
import { servicePages, type ServicePage } from "../../content/service-pages";
import { ButtonLink, Card, Container, TextLink } from "../ui";
import styles from "./service-journeys.module.css";

const conversationSteps = [
  [
    "Share the context",
    "Tell us what you are planning and what is already in place.",
  ],
  [
    "Discuss the questions",
    "Use the conversation to identify what needs closer review.",
  ],
  [
    "Choose the next step",
    "Decide whether and how you want the Bali Zero team to help.",
  ],
] as const;

function ServiceFrame({ children }: { children: ReactNode }) {
  return (
    <>
      <a className={styles.skip} href="#main">
        Skip to content
      </a>
      <header className={styles.header}>
        <Link aria-label="Bali Zero home" className={styles.brand} href="/">
          <img alt="Bali Zero" height="62" src="/assets/logo.png" width="62" />
        </Link>
        <nav aria-label="Service navigation">
          <Link href="/services">All services</Link>
          <a href="https://my.balizero.com/">My Bali Zero ↗</a>
        </nav>
      </header>
      {children}
      <footer className={styles.footer}>
        <Link href="/">Bali Zero</Link>
        <a href="mailto:zantara@balizero.com">zantara@balizero.com</a>
      </footer>
    </>
  );
}

export function ServicesOverview() {
  const contact = destinationIntents.whatsapp({
    topic: "which Bali Zero service fits my plans",
  });
  return (
    <ServiceFrame>
      <Container as="main" className={styles.main} id="main">
        <nav aria-label="Breadcrumb" className={styles.breadcrumb}>
          <Link href="/">Home</Link>
          <span aria-hidden="true">/</span>
          <span aria-current="page">Services</span>
        </nav>
        <section className={styles.intro}>
          <span className={styles.eyebrow}>Bali Zero services</span>
          <h1>Start with the decision in front of you.</h1>
          <p>
            Choose an area to see who it helps, which questions to bring and how a
            conversation with our team can begin.
          </p>
        </section>
        <section aria-label="Service areas" className={styles.grid}>
          {servicePages.map((service, index) => (
            <Card className={styles.card} key={service.slug} tone="quiet">
              <span className={styles.index} aria-hidden="true">
                {String(index + 1).padStart(2, "0")}
              </span>
              <img
                alt={service.image.alt}
                height="816"
                src={service.image.src}
                width="1088"
              />
              <span className={styles.eyebrow}>{service.eyebrow}</span>
              <h2>{service.cardTitle}</h2>
              <p>{service.summary}</p>
              <Link href={`/services/${service.slug}`}>
                Explore this service <span aria-hidden="true">→</span>
              </Link>
            </Card>
          ))}
        </section>
        <aside className={styles.conversation}>
          <div>
            <span className={styles.eyebrow}>Not sure where to start?</span>
            <h2>Bring us the plan, not a category.</h2>
          </div>
          <ButtonLink
            className={styles.primary}
            href={contact}
            variant="copper"
          >
            Talk to our team <span aria-hidden="true">↗</span>
          </ButtonLink>
        </aside>
      </Container>
    </ServiceFrame>
  );
}

export function ServiceDetail({ service }: { service: ServicePage }) {
  const contact = destinationIntents.whatsapp({ topic: service.contactTopic });
  const tool = getDestination(service.toolDestinationId);
  return (
    <ServiceFrame>
      <Container as="main" className={styles.main} id="main">
        <nav aria-label="Breadcrumb" className={styles.breadcrumb}>
          <Link href="/">Home</Link>
          <span aria-hidden="true">/</span>
          <Link href="/services">Services</Link>
          <span aria-hidden="true">/</span>
          <span aria-current="page">{service.cardTitle}</span>
        </nav>
        <header className={styles.detailHero}>
          <div>
            <span className={styles.eyebrow}>{service.eyebrow}</span>
            <h1>{service.title}</h1>
            <p>{service.summary}</p>
            <ButtonLink
              className={styles.primary}
              href={contact}
              variant="copper"
            >
              Discuss this with our team <span aria-hidden="true">↗</span>
            </ButtonLink>
          </div>
          <img
            alt={service.image.alt}
            height="816"
            src={service.image.src}
            width="1088"
          />
        </header>
        <div className={styles.detailGrid}>
          <section>
            <span className={styles.eyebrow}>Who this helps</span>
            <h2>A useful starting point.</h2>
            <p>{service.whoItHelps}</p>
          </section>
          <section>
            <span className={styles.eyebrow}>Questions to discuss</span>
            <h2>Bring the context.</h2>
            <ul>
              {service.questions.map((question) => (
                <li key={question}>{question}</li>
              ))}
            </ul>
          </section>
        </div>
        <aside className={styles.toolAction}>
          <div>
            <span className={styles.eyebrow}>Optional independent starting point</span>
            <h2>{tool.label}</h2>
          </div>
          <TextLink href={tool.href}>
            Open {tool.label} <span aria-hidden="true">↗</span>
          </TextLink>
        </aside>
        <section className={styles.nextSteps}>
          <span className={styles.eyebrow}>How the next step works</span>
          <h2>A conversation before a commitment.</h2>
          <ol>
            {conversationSteps.map(([title, description], index) => (
              <li key={title}>
                <span aria-hidden="true">0{index + 1}</span>
                <div>
                  <h3>{title}</h3>
                  <p>{description}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>
        <aside className={styles.conversation}>
          <div>
            <span className={styles.eyebrow}>Your next step</span>
            <h2>Talk through the details.</h2>
          </div>
          <div className={styles.actions}>
            <ButtonLink
              className={styles.primary}
              href={contact}
              variant="copper"
            >
              Contact Bali Zero <span aria-hidden="true">↗</span>
            </ButtonLink>
            <Link href="/services">Back to all services</Link>
          </div>
        </aside>
      </Container>
    </ServiceFrame>
  );
}
