import Link from "next/link";
import { founders } from "../content/team";
import styles from "./Team.module.css";

export function Team() {
  return (
    <section className={styles.band} id="team" aria-labelledby="team-heading">
      <div className={styles.bandIntro}>
        <span className={styles.eyebrow}>The people behind Bali Zero</span>
        <h2 id="team-heading">Local roots. Personal commitment.</h2>
      </div>
      <div className={styles.founders}>
        {founders.map((founder) => (
          <figure className={styles.founder} key={founder.name}>
            <img alt={founder.name} src={founder.image} width="88" height="104" loading="lazy" />
            <figcaption><strong>{founder.name}</strong><span>{founder.role}</span></figcaption>
          </figure>
        ))}
      </div>
      <div className={styles.bandLinks}>
        <Link className={styles.teamLink} href="/team" prefetch={false}>
          Meet our team <span aria-hidden="true">→</span>
        </Link>
        <Link className={styles.storyLink} href="/about" prefetch={false}>
          Our story <span aria-hidden="true">→</span>
        </Link>
      </div>
    </section>
  );
}
