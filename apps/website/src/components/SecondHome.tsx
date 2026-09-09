import styles from "./ToolEntries.module.css";
import art from "./HomeTools.module.css";
export function SecondHome() {
  return (
    <section
      aria-labelledby="studio-title"
      className={art.studio}
      id="second-home-studio"
    >
      <div className={art.studioTopline}>
        <span className={art.eyebrow}>{"Second Home Studio"}</span>
        <span>{"A little room for a bigger life."}</span>
      </div>
      <div className={art.studioGrid}>
        <div className={art.studioVisual}>
          <img
            alt="An open book unfolds into a Balinese doorway, garden and terraces: a new chapter taking shape."
            height="1086"
            loading="lazy"
            src="/assets/second-home-book.png"
            width="1448"
          />
          <span className={art.artCaption}>
            {"Every new chapter starts with a possibility."}
          </span>
        </div>
        <div className={art.studioCopy}>
          <h2 id="studio-title">
            {"A new chapter."}
            <br />
            <em>{"On your terms."}</em>
          </h2>
          <p className={art.studioLead}>
            {
              "Considering a longer-term life in Indonesia? Explore a Second Home plan before discussing your circumstances with our team."
            }
          </p>

          <p className={art.studioThought} id="studio-thought">
            {
              "Bring six starting points: age, preferred route, capital, family, timing and location. The Studio turns your choices into a plan you can revisit and discuss."
            }
          </p>
          <a
            className={art.primary}
            href="/visa/second-home/studio"
          >
            {"Open Second Home Studio "}
            <span aria-hidden="true">{"↗"}</span>
          </a>
          <p className={art.small}>A planning guide; your circumstances still need individual review.</p>
          <div className={`${styles.branches}`} aria-label="Second Home reading options">
            <a href="/visa/second-home">Read the Second Home guide →</a>
            <span className={styles.languages}><a href="/visa/second-home/it" lang="it">Italiano</a><a href="/visa/second-home/id" lang="id">Bahasa Indonesia</a></span>
          </div>
          <a
            aria-label="Contact our team about Ari’s Second Home Studio project"
            className={art.host}
            href="https://wa.me/628213454721?text=Hello%20Bali%20Zero%2C%20I%20would%20like%20to%20discuss%20Second%20Home%20Studio%20with%20Ari."
          >
            <span className={art.hostPortrait}>
              <img alt="Ari" loading="lazy" src="/assets/ari-cutout-v19.png" />
            </span>
            <span className={art.hostCopy}>
              <span className={art.hostLabel}>
                {"A familiar face for a new chapter"}
              </span>
              <strong>
                {"Ari "}
                <span>{"· Second Home Studio"}</span>
              </strong>
              <span className={art.hostContact}>
                {"Talk through your plans "}
                <span aria-hidden="true">{"↗"}</span>
              </span>
            </span>
          </a>
        </div>
      </div>
    </section>
  );
}
