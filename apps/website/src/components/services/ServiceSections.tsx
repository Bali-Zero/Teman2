import type { ServicePage } from "../../content/service-pages";
import { serviceSectionContent } from "../../content/service-section-content";
import { getServiceDossier } from "../../content/service-dossiers";
import { ServiceCatalog } from "./ServiceCatalog";
import styles from "./service-sections.module.css";

export function ServiceSectionNav() {
  return (
    <nav aria-label="On this service page" className={styles.jumpLinks}>
      <a href="#available-services">Available services</a>
      <a href="#service-scope">What’s included</a>
      <a href="#preparation">Documents & eligibility</a>
      <a href="#service-faqs">Common questions</a>
      <a href="#next-steps">Next steps</a>
    </nav>
  );
}

export function ServiceSections({ service }: { service: ServicePage }) {
  const content = serviceSectionContent[service.slug];
  return (
    <div className={styles.sections}>
      <section
        id="available-services"
        aria-labelledby="catalog-heading"
        className={styles.section}
      >
        <div className={styles.sectionHeading}>
          <span className={styles.eyebrow}>01 / Available services</span>
          <h2 id="catalog-heading">Find the support you need.</h2>
          <p>
            Start with the situation each service addresses. Open its dossier
            for the differences, preparation and work to include in your quote.
          </p>
        </div>
        <ServiceCatalog
          title={service.cardTitle}
          groups={content.catalog.map((group) => ({
            ...group,
            services: group.services.map(getServiceDossier),
          }))}
        />
      </section>
      <section
        id="service-scope"
        aria-labelledby="scope-heading"
        className={`${styles.section} ${styles.scope}`}
      >
        <div className={styles.sectionHeading}>
          <span className={styles.eyebrow}>02 / What’s included</span>
          <h2 id="scope-heading">A clear scope, from the start.</h2>
          <p>
            Depending on the service, support can include the work below. Your
            quote confirms the deliverables for your case.
          </p>
        </div>
        <ul className={styles.scopeList}>
          {content.included.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>
      <section
        id="preparation"
        aria-labelledby="preparation-heading"
        className={styles.section}
      >
        <div className={styles.sectionHeading}>
          <span className={styles.eyebrow}>03 / Documents & eligibility</span>
          <h2 id="preparation-heading">Prepare for a useful review.</h2>
          <p>
            These are starting points for the conversation. The final checklist
            and eligibility review depend on your circumstances and chosen
            service.
          </p>
        </div>
        <ol className={styles.reviewQuestions}>
          {service.questions.map((question) => (
            <li key={question}>{question}</li>
          ))}
        </ol>
        <div className={styles.preparationGrid}>
          <div>
            <h3>Documents to have at hand</h3>
            <ul>
              {content.documents.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
          <div>
            <h3>What we need to understand</h3>
            <ul>
              {content.review.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        </div>
      </section>
      <section
        id="service-faqs"
        aria-labelledby="faq-heading"
        className={`${styles.section} ${styles.faqs}`}
      >
        <div className={styles.sectionHeading}>
          <span className={styles.eyebrow}>04 / Common questions</span>
          <h2 id="faq-heading">Before you take the next step.</h2>
        </div>
        <div>
          {content.faqs.map(({ question, answer }) => (
            <details key={question} className={styles.faq}>
              <summary>
                {question}
                <span className={styles.toggle} aria-hidden="true">
                  +
                </span>
              </summary>
              <p>{answer}</p>
            </details>
          ))}
        </div>
      </section>
    </div>
  );
}
