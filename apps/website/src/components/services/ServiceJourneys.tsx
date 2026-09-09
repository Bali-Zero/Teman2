import Link from "next/link";
import type { ReactNode } from "react";
import { destinationIntents, getDestination } from "../../content/destinations";
import { servicePages, type ServicePage } from "../../content/service-pages";
import { serviceSectionContent } from "../../content/service-section-content";
import { ButtonLink, Container, TextLink } from "../ui";
import "../../styles/brand-fonts.css";
import styles from "./service-journeys.module.css";
import { ServiceSectionNav, ServiceSections } from "./ServiceSections";
import { SiteShell } from "../SiteShell";

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
  return <SiteShell mainId="main">{children}</SiteShell>;
}

export function ServicesOverview() {
  const contact = destinationIntents.whatsapp({
    topic: "which Bali Zero service fits my plans",
  });
  return (
    <ServiceFrame>
      <Container as="main" className={`${styles.main} ${styles.overview}`} id="main" tabIndex={-1}>
        <nav aria-label="Breadcrumb" className={styles.breadcrumb}>
          <Link href="/">Home</Link>
          <span aria-hidden="true">/</span>
          <span aria-current="page">Services</span>
        </nav>
        <section className={styles.intro}><div className={styles.introVoice}>
          <span className={styles.eyebrow}>Bali Zero services</span>
          <h1>Start with the decision in front of you.</h1>
          <p>
            Choose an area to see who it helps, which questions to bring and how a
            conversation with our team can begin.
          </p>
        </div><nav className={styles.familyIndex} aria-label="Choose a service family"><span className={styles.eyebrow}>Four areas of practice</span>{servicePages.map((service, index) => <Link key={service.slug} href={`/services/${service.slug}`}><span className={styles.index}>0{index + 1}</span><span>{service.cardTitle}</span><span aria-hidden="true">↗</span></Link>)}</nav></section>
        <section aria-label="Service areas" className={styles.collection}>
          {servicePages.map((service, index) => (
            <article className={styles.family} data-family={service.slug} key={service.slug}>
              <div className={styles.familyImage}><span className={styles.plateLabel}>Bali Zero / 0{index + 1}</span>
              <img
                alt={service.image.alt}
                height="816"
                src={service.image.src}
                width="1088"
              />
              </div><div className={styles.familyCopy}><span className={styles.eyebrow}>{service.eyebrow}</span>
              <h2>{service.cardTitle}</h2>
              <p>{service.summary}</p>
              {service.slug === "tax" && <nav className={styles.taxChapters} aria-label="Explore tax support">{serviceSectionContent.tax.catalog.map((group, groupIndex) => <Link key={group.title} href={"/services/tax#catalog-" + (groupIndex + 1)}><span>0{groupIndex + 1}</span>{group.title}<span aria-hidden="true">↗</span></Link>)}</nav>}
              <Link
                href={`/services/${service.slug}`}
                aria-label={`Explore this service: ${service.cardTitle}`}
              >
                Explore this service <span aria-hidden="true">→</span>
              </Link>
            </div></article>
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
      <Container as="main" className={`${styles.main} ${styles.detail}`} data-family={service.slug} id="main" tabIndex={-1}>
        <nav aria-label="Breadcrumb" className={styles.breadcrumb}>
          <Link href="/">Home</Link>
          <span aria-hidden="true">/</span>
          <Link href="/services">Services</Link>
          <span aria-hidden="true">/</span>
          <span aria-current="page">{service.cardTitle}</span>
        </nav>
        <header className={styles.detailHero}>
          <div className={styles.heroVoice}>
            <span className={styles.eyebrow}>{service.eyebrow}</span>
            <h1>{service.title}</h1>
            <p className={styles.heroSummary}>{service.summary}</p>
            <div className={styles.heroActions}><a className={styles.primary} href="#available-services">Explore the services <span aria-hidden="true">↓</span></a><a href={contact}>Discuss this with our team ↗</a></div>
          </div>
          <aside className={styles.orientation}>
            <div className={styles.orientationLead}><img alt={service.image.alt} height="816" src={service.image.src} width="1088" /><div><span className={styles.eyebrow}>Who this helps</span><p>{service.whoItHelps}</p></div></div>
            <nav className={styles.heroIndex} aria-label={"Start exploring " + service.cardTitle}><span className={styles.eyebrow}>Where to start</span>{serviceSectionContent[service.slug].catalog.map((group, index) => <a key={group.title} href={"#catalog-" + (index + 1)}><span className={styles.index}>0{index + 1}</span><span>{group.title}</span><span aria-hidden="true">↓</span></a>)}</nav>
          </aside>
        </header>
        <ServiceSectionNav />
        <ServiceSections service={service} />
        <aside className={styles.toolAction}>
          <div>
            <span className={styles.eyebrow}>Optional independent starting point</span>
            <h2>{tool.label}</h2>
          </div>
          <TextLink href={tool.href}>
            Open {tool.label} <span aria-hidden="true">↗</span>
          </TextLink>
        </aside>
        <section id="next-steps" className={styles.nextSteps}>
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
