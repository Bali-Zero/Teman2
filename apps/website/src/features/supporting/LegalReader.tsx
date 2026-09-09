import { SiteShell } from "../../components/SiteShell";
import documents from "./legal-content.json";
import styles from "./supporting.module.css";

export type LegalDocument = keyof typeof documents;

export function LegalReader({ documentKey }: { documentKey: LegalDocument }) {
  const document = documents[documentKey];
  const versioned = documentKey.startsWith("v2-");
  const links = [
    {
      label: "Privacy",
      href: versioned ? "/v2/privacy" : "/privacy",
      key: versioned ? "v2-privacy" : "privacy",
    },
    {
      label: "Terms",
      href: versioned ? "/v2/terms" : "/terms",
      key: versioned ? "v2-terms" : "terms",
    },
    { label: "Cookies", href: "/v2/cookies", key: "v2-cookies" },
  ];
  return (
    <SiteShell
      className={styles.root}
      context={{ label: "Bali Zero", href: "/" }}
    >
      <main id="main-content" className={styles.legalLayout} tabIndex={-1}>
        <aside className={styles.legalRail}>
          <span className={styles.eyebrow}>The details</span>
          <nav aria-label="Legal documents" className={styles.documentNav}>
            {links.map((link) => (
              <a
                key={link.key}
                href={link.href}
                aria-current={link.key === documentKey ? "page" : undefined}
              >
                {link.label}
                <span aria-hidden="true">↗</span>
              </a>
            ))}
          </nav>
          <nav aria-label="On this page" className={styles.contents}>
            <span className={styles.eyebrow}>On this page</span>
            {document.contents.map((section) => (
              <a key={section.id} href={`#${section.id}`}>
                {section.title}
              </a>
            ))}
          </nav>
          <a className={styles.textLink} href="/contact">
            Contact Bali Zero ↗
          </a>
        </aside>
        {/* Build-time snapshot of authored JSX. No user content, scripts or source styles. */}
        <article
          aria-label={document.title}
          className={styles.legalArticle}
          dangerouslySetInnerHTML={{ __html: document.html }}
        />
      </main>
    </SiteShell>
  );
}
