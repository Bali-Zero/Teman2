import styles from "./Footer.module.css";

export function Footer() {
  return (
    <footer className={styles.footer}>
      <div className={styles.wrap}>
        <div className={styles.grid}>
          <div className={styles.identity}>
            <a aria-label="Bali Zero home" className={styles.brand} href="/">
              <img
                alt="Bali Zero"
                height="62"
                src="/assets/logo.png"
                width="62"
              />
            </a>
            <p>{"Bali, Indonesia"}</p>
            <p>{"Local knowledge. A human connection."}</p>
          </div>
          <div className={styles.column}>
            <span className={styles.eyebrow}>{"Explore"}</span>
            <a href="/#tools">{"Our tools"}</a>
            <a href="/services">{"Our services"}</a>
            <a href="/#evoa">{"E-VOA"}</a>
            <a href="/visa/second-home/studio">{"Second Home Studio"}</a>
            <a href="/news">{"The Bali Zero Journal"}</a>
            <a href="/book">{"The Bali Zero book"}</a>
          </div>
          <div className={styles.column}>
            <span className={styles.eyebrow}>{"Bali Zero"}</span>
            <a href="/about">{"Our story"}</a>
            <a href="/team">{"Our team"}</a>
            <a href="https://maps.app.goo.gl/whiMUTNchcDR5naz8">
              {"Client reviews"}
            </a>
            <a href="https://my.balizero.com/">{"My Bali Zero"}</a>
          </div>
          <div className={styles.column}>
            <span className={styles.eyebrow}>{"Connect"}</span>
            <a href="/contact">{"Contact & office visits"}</a>
            <a href="/v2/company/careers">{"Careers"}</a>
            <a href="/v2/company/press">{"Press"}</a>
            <a href="https://wa.me/628213454721">{"WhatsApp"}</a>
            <a href="mailto:zantara@balizero.com">{"zantara@balizero.com"}</a>
            <a href="tel:+628213454721">{"+62 821 3454 721"}</a>
          </div>
        </div>
        <div className={styles.base}>
          <span>{"© 2026 Bali Zero"}</span>
          <div>
            <a href="/v2/privacy">{"Privacy"}</a>
            <a href="/v2/terms">{"Terms"}</a>
            <a href="/v2/cookies">{"Cookies"}</a>
            <span>{"Website development preview"}</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
