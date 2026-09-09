import { destinations } from "../content/destinations";
import styles from "./LegacySections.module.css";

export function Reviews() {
  return (
    <section className={styles.reviews} id="google-reviews" aria-labelledby="google-title">
      <div className={styles.reviewIntro}>
        <span className={styles.eyebrow}>Before you decide</span>
        <h2 id="google-title">Their experience.{" "}<br />Your perspective.</h2>
        <p>Hear from people who have worked with Bali Zero. Read their full reviews, in their own words.</p>
      </div>
      <a className={styles.reviewCard} href={destinations.googleReviews.href} target="_blank" rel="noopener noreferrer">
        <span className={styles.sourceLabel}>Google Reviews <span aria-hidden="true">↗</span></span>
        <strong>Read the full story.</strong>
        <p>Individual experiences, review dates and the latest rating — directly on Google.</p>
        <span className={styles.sourceNote}>Opens the public Google profile</span>
      </a>
      <figure className={styles.reviewPortrait}>
        <img alt="Adit, Bali Zero Supervisor and Lead Setup" src="/assets/adit-site-bg.png" width="1023" height="1537" loading="lazy" />
        <figcaption><span>From the Bali Zero team</span><strong>Adit</strong><span>Supervisor · Lead Setup</span></figcaption>
      </figure>
    </section>
  );
}
