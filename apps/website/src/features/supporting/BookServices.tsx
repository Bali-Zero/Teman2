"use client";
import { useState } from "react";
import { ServicePrice } from "../../components/services/ServicePrice";
import { servicePriceIdentities } from "../../content/service-price-identities";
import type { BookService } from "./book-model";
import styles from "./book.module.css";

export function BookServices({
  services,
  categories,
  cta,
  language,
}: {
  services: BookService[];
  categories: Record<string, string>;
  cta: string;
  language: string;
}) {
  const [category, setCategory] = useState("visa");
  return (
    <div>
      <div className={styles.filters} aria-label="Service category">
        {Object.entries(categories).map(([key, label]) => (
          <button
            key={key}
            type="button"
            aria-pressed={category === key}
            onClick={() => setCategory(key)}
          >
            {label}
          </button>
        ))}
      </div>
      <div className={styles.services} lang="en">
        {services
          .filter((service) => service.category === category)
          .map((service) => {
            const priceIdentity = Object.values(servicePriceIdentities).find(
              (identity) =>
                identity.category === service.pricingCategory &&
                identity.key === service.pricingItemKey,
            );
            return (
              <article className={styles.service} key={service.serviceKey}>
                <div>
                  <h2>{service.title}</h2>
                  <p>{service.description}</p>
                </div>
                <div className={styles.serviceBody}>
                  <details>
                    <summary>
                      Scope & preparation <span aria-hidden="true">+</span>
                    </summary>
                    <div className={styles.serviceDetail}>
                      <h3>Scope to discuss</h3>
                      <ul>
                        {service.scope.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                      <h3>Have these ready</h3>
                      <ul>
                        {service.preparation.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                      <p>{service.limit}</p>
                      <a href={service.href}>Read the service dossier ↗</a>
                    </div>
                  </details>
                  {priceIdentity ? (
                    <ServicePrice
                      name={service.title}
                      serviceKey={priceIdentity.key}
                    />
                  ) : (
                    <p className={styles.quote}>Scope-based quotation</p>
                  )}
                  <a
                    className={styles.actionLink}
                    href={`https://wa.me/628213454721?text=${encodeURIComponent(service.waMessage + (language === "English" ? "" : ` (${language})`))}`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {cta} ↗
                  </a>
                </div>
              </article>
            );
          })}
      </div>
    </div>
  );
}
