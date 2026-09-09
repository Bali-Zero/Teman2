import Link from "next/link";
import { SiteShell } from "../../components/SiteShell";
import {
  founders,
  boardMember,
  responsibilityGroups,
  teamMembers,
} from "../../content/team";
import source from "./book-content.json";
import {
  bookAssist,
  bookHref,
  bookServices,
  type BookLocale,
} from "./book-model";
import { BookServices } from "./BookServices";
import { BookKeys } from "./BookKeys";
import common from "./supporting.module.css";
import styles from "./book.module.css";

export function BookReader({
  chapter = "cover",
  locale = "en",
}: {
  chapter?: string;
  locale?: BookLocale;
}) {
  const index = source.chapters.findIndex((item) => item.id === chapter);
  const t = source.translations[locale];
  const a = bookAssist[locale];
  const previous =
    index > 0 ? bookHref(source.chapters[index - 1].id, locale) : undefined;
  const next =
    index < source.chapters.length - 1
      ? bookHref(source.chapters[index + 1].id, locale)
      : undefined;
  const isCover = chapter === "cover";
  return (
    <SiteShell
      className={common.root}
      context={{ label: "Bali Zero", href: "/about" }}
    >
      <BookKeys previous={previous} next={next} />
      <main
        id="main-content"
        className={styles.book}
        lang={locale}
        tabIndex={-1}
      >
        <div className={styles.bookBar}>
          <Link href={bookHref("cover", locale)} className={styles.bookTitle}>
            Bali Zero · The book
          </Link>
          <nav aria-label="Book language" className={styles.locales}>
            {Object.entries(source.locales).map(([key, label]) => (
              <Link
                href={bookHref(chapter, key as BookLocale)}
                hrefLang={key}
                lang={key}
                key={key}
                aria-current={key === locale ? "page" : undefined}
              >
                {label}
              </Link>
            ))}
          </nav>
        </div>
        <div
          className={`${styles.layout} ${isCover ? styles.coverLayout : ""}`}
        >
          <aside className={styles.rail}>
            <span className={common.eyebrow}>{a.contents}</span>
            <nav aria-label={a.contents}>
              {source.chapters.map((item) => (
                <Link
                  key={item.id}
                  href={bookHref(item.id, locale)}
                  aria-current={item.id === chapter ? "page" : undefined}
                >
                  <span>{String(item.index + 1).padStart(2, "0")}</span>
                  {t.chapters[item.index]}
                </Link>
              ))}
            </nav>
            <span className={styles.folio}>
              {String(index + 1).padStart(2, "0")} / 08
            </span>
          </aside>
          <article className={styles.chapter}>
            {isCover ? (
              <div className={styles.cover}>
                <span className={common.eyebrow}>{t.coverTagline}</span>
                <h1>
                  Bali
                  <br />
                  <em>Zero.</em>
                </h1>
                <p>{t.coverSubtitle}</p>
                <Link className={styles.actionLink} href={next!}>
                  {a.start} →
                </Link>
                <figure>
                  <img
                    src="/assets/hero-sunset-future.png"
                    alt="Bali coastline in the evening"
                    width="1200"
                    height="800"
                  />
                </figure>
              </div>
            ) : (
              <>
                <header className={styles.chapterHeading}>
                  <span className={common.eyebrow}>
                    {String(index + 1).padStart(2, "0")} · {t.chapters[index]}
                  </span>
                  <h1>
                    {chapter === "team"
                      ? a.team
                      : chapter === "impact"
                        ? a.impact
                        : chapter === "technology"
                          ? a.tech
                          : t.chapters[index]}
                  </h1>
                </header>
                {(chapter === "manifesto" || chapter === "origin") && (
                  <div className={styles.story}>
                    <div className={styles.storyDate}>
                      {chapter === "manifesto" ? "2006" : "2020"}
                      <span>Bali, Indonesia</span>
                    </div>
                    <div>
                      <p className={styles.dropcap}>
                        {chapter === "manifesto" ? t.manifestoP1 : t.originP1}
                      </p>
                      <p>
                        {chapter === "manifesto" ? t.manifestoP2 : t.originP2}
                      </p>
                      <Link className={styles.actionLink} href="/about">
                        Bali Zero ↗
                      </Link>
                    </div>
                  </div>
                )}
                {chapter === "team" && (
                  <>
                    <div className={styles.leaders}>
                      {[...founders, boardMember].map((person) => (
                        <figure key={person.name}>
                          <img
                            src={person.image}
                            alt={person.name}
                            width="360"
                            height="420"
                            loading="lazy"
                          />
                          <figcaption>
                            <h2>{person.name}</h2>
                            <p>{person.role}</p>
                          </figcaption>
                        </figure>
                      ))}
                    </div>
                    <div className={styles.teamGroups}>
                      {responsibilityGroups.map((group) => (
                        <section key={group.id}>
                          <h2>{group.title}</h2>
                          <ul>
                            {group.people
                              .map((name) =>
                                teamMembers.find(
                                  (person) => person.name === name,
                                )!,
                              )
                              .map((person) => (
                                <li key={person.name}>
                                  <strong>{person.name}</strong>
                                  <span>{person.role}</span>
                                </li>
                              ))}
                          </ul>
                        </section>
                      ))}
                    </div>
                    <Link className={styles.actionLink} href="/team">
                      {a.fullTeam} ↗
                    </Link>
                  </>
                )}
                {chapter === "services" && (
                  <>
                    <p className={styles.note}>{a.serviceNote}</p>
                    <BookServices
                      services={bookServices()}
                      categories={t.servicesCategories}
                      cta={t.askOnWhatsApp}
                      language={source.locales[locale]}
                    />
                    <Link className={styles.actionLink} href="/services">
                      {a.services} ↗
                    </Link>
                  </>
                )}
                {chapter === "impact" && (
                  <>
                    <p className={styles.chapterLead}>{a.impactBody}</p>
                    <ol className={styles.steps}>
                      {a.steps.map((step, i) => (
                        <li key={step}>
                          <span className={styles.stepNumber}>0{i + 1}</span>
                          <Link
                            href={
                              ["/kbli", "/services", "/contact?from=book"][i]
                            }
                          >
                            {step}
                            <span aria-hidden="true">↗</span>
                          </Link>
                        </li>
                      ))}
                    </ol>
                    <figure className={styles.landscape}>
                      <img
                        src="/assets/villa-wall.png"
                        alt="Architectural detail in Bali"
                        width="1200"
                        height="800"
                        loading="lazy"
                      />
                    </figure>
                  </>
                )}
                {chapter === "technology" && (
                  <>
                    <p className={styles.chapterLead}>{a.techBody}</p>
                    <div className={styles.toolFeature}>
                      <img
                        src="/assets/tool-kbli-illustration.png"
                        alt="Illustration for the KBLI activity directory"
                        width="700"
                        height="600"
                        loading="lazy"
                      />
                      <div>
                        {a.toolLabels.map((label, i) => (
                          <Link
                            key={label}
                            href={
                              ["/kbli", "/services", "/contact?from=book"][i]
                            }
                          >
                            <span className={common.eyebrow}>0{i + 1}</span>
                            <h2>{label}</h2>
                            <span aria-hidden="true">↗</span>
                          </Link>
                        ))}
                      </div>
                    </div>
                  </>
                )}
                {chapter === "contact" && (
                  <div className={styles.contact}>
                    <p className={styles.chapterLead}>{t.contactBody}</p>
                    <a
                      className={styles.contactNumber}
                      href={`${source.contacts.whatsappUrl}?text=${encodeURIComponent(t.contactCta)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {source.contacts.whatsapp}
                      <span aria-hidden="true">↗</span>
                    </a>
                    <a
                      className={styles.actionLink}
                      href={`mailto:${source.contacts.email}`}
                    >
                      {source.contacts.email} ↗
                    </a>
                  </div>
                )}
              </>
            )}
            <nav aria-label="Chapter navigation" className={styles.chapterNav}>
              {previous ? (
                <Link href={previous}>
                  <span>{a.previous}</span>← {t.chapters[index - 1]}
                </Link>
              ) : (
                <span />
              )}{" "}
              {next ? (
                <Link href={next}>
                  <span>{a.next}</span>
                  {t.chapters[index + 1]} →
                </Link>
              ) : (
                <Link href={bookHref("cover", locale)}>{t.chapters[0]} ↗</Link>
              )}
            </nav>
          </article>
        </div>
      </main>
    </SiteShell>
  );
}
